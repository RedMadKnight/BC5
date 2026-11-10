# audit0406 — performance-costing diagnostics in the current play setup (laptop only)

Date 2026-11-05. Laptop only: files and history in `C:\Users\kjani\Downloads\bc5\bc5-0401` and Codex's
`Documents\ChatGPT\BC5\audit\switch-history\REPORT.md`. No ssh, no box. No repo file edited.

Sources, short names used below:
- `P` = `backend/kytyplus-patches/0001-bc5-lle-agc.patch` (the host; `bc5LleAgc.cpp` is P:27367-35609)
- `D` = `backend/src/direct.cpp`
- `R401` = `experiments/0401-mesa-preamble-switches/README.md`
- `CAP` = `experiments/0401-mesa-preamble-switches/cap0401-notes.md`
- `H` = `experiments/0401-mesa-preamble-switches/hang1954-0401.md`
- `mkunit` / `mkcap` / `mkgpu` = the 0401 edit scripts `mkunit0401.py`, `mkcap0401.py`, `mkgpu0405.py`
- `Z1` = `experiments/0399-*/raw/Z1.manifest.txt` (the last committed dump of the effective play env, 2026-11-01:
  `bc5-run.env` + launcher). Today's `bc5-run.env` on the box was NOT read (box off limits); Z1 stands in for it.
- `SC` = `experiments/0401-mesa-preamble-switches/shortcut0401.sh` (his shortcut's words, series e8 since 11-05)

Limits: the 0401 binary's unit is P's unit plus the 0401 edit scripts (R401 "Setup"; the e-series chain). Lines quoted
from P are main's unit; the 0401-only switches are quoted from the edit scripts. Nothing below is measured on the box
by me; "measured" means a cited committed number.

## 0. Headline

1. The big win is already taken. `BC5_DIRECT_JOURNAL_QUIET=1` cut `direct.log` from 385 MB to 24 MB over 1,042 s
   (r6c vs r7m, same save; R401:525-526), i.e. ~22 MB/min to ~1.4 MB/min. F353's page-cache mechanism (normal build:
   309 MiB swapped, 45,700 major faults in 5 min, vs lean 30 MiB / 3,000; HANDOFF F353) is now mostly removed for the
   journal. What remains of the journal is almost exactly the frame profile's estimated rate (~23 KB/s, CAP:283;
   24 MB / 1,042 s = 23 KB/s), so the frame profile is now the dominant writer.
2. The largest remaining cost I can find is not a log: `BC5_DIRECT_TIMEOUT_PROBE=1` makes every asynchronous job
   copy its whole submitted IB and its executed-offset list into heap vectors at submit (P:34536), and reads the env
   with an uncached `getenv` each time. At ~965 submissions/s (CAP:279) and IB sizes up to 248,896 dwords for the hung
   acb (H, e8c2 devcd1) and 1,671,120 for the largest job (F768), this is memcpy + malloc/free (large blocks via mmap,
   so page faults and munmap) per job, only to have the buffer if that job times out. Not measured. Code fix, not env.
3. Env-only drops with no evidence loss: `BC5_DIRECT_ACB_INHERIT=journal` (0 hits in every play and route; census
   empty), `BC5_R3_REWIND_CATCH`, `BC5_R3_DROP_CATCH` (answered), and two no-ops: `KYTY_BC5_MEASURE` (no effect while
   logging is on) and `BC5_DIRECT_PIECES_DRY` (read nowhere in this code).
4. Several "on" switches are presence-parsed: `=0` keeps them ON (TIMING, FRAME_PROFILE, TIMEOUT_PROBE, AUDIO_TRACE,
   MEASURE, FPS_COUNTER). Only unset disables them. And `BC5_DIRECT_JOURNAL` must stay `min`: unset or any other value
   brings back the heavy crash journal AND turns asynchronous jobs off (P:28562 `g_async = g_journal_min`).

## 1. Item table

Columns: purpose/origin; behaviour vs pure diagnostic; overlap; cost; verdict + the true off value and the value
that restores today's behaviour.

### 1.1 `BC5_DIRECT_JOURNAL=min` (exp 0022, run 100; P:27478-27482, 27560-27566)
- Purpose: the "min" journal: one buffered `FILE*`, 1 MiB `setvbuf`, `fflush` at most every 0.5 s
  (`journal_min_file`, P:28498-28513), `fsync` only on a failure/timeout (P:34561-34563, 33090-33091, 33254). The other
  mode (unset or any value but `min`) writes raw+filtered IB files and an `fsync` per submission (P:34308-34343) and
  cost 81 of 167 ms of a frame (P:27479-27481).
- Behaviour: NOT a pure diagnostic. `g_async = g_journal_min` (P:28562): without `min` jobs are synchronous. Also
  `min` turns off `dump_cb` (P:27614), `record_dispatch` dumps (P:28151) and the per-submission files.
- Cost: lowest journal mode; flush ≤ 2/s.
- Verdict: KEEP, high. Parser: `strcmp(e,"min")==0` (P:27564-27565). Never unset it to "turn logging off"; to stop
  the journal file unset `BC5_GC_DUMP_DIR` (journal() returns on an empty dir, P:28516) or set `BC5_LOGGING=0`
  (P:4576-4579; only exactly "0" is off).

### 1.2 `BC5_GC_DUMP_DIR=~/bc5-data/captures/play-<time>/gc` (P:27587-27598)
- What is dumped: with `JOURNAL=min` nothing per buffer. `dump_cb` (ib1/ib2 files, limit 4000) returns when
  `g_journal_min` (P:27614); `record_dispatch` likewise (P:28151); the per-submission `direct-NNNNNN-*.bin` only in the
  non-min mode (P:34308). What it does hold: `direct.log`; `ib-timeout-<n>-<kind>-<dwords>.bin` per timed-out job
  (TIMEOUT_PROBE, P:32827-32836, fsync'd); `timeout-snap.bin` only with `BC5_DIRECT_SNAP_ON_TIMEOUT` (P:32732; not in
  Z1); `umr-waves-*.txt` only with `BC5_DIRECT_UMR_ON_TIMEOUT` (P:32690-32702; not in Z1). So: only at a timeout.
- Behaviour: pure diagnostic (the directory gates every journal line).
- Cost: the journal's bytes (see 1.4/1.6). No per-buffer dumps.
- Verdict: KEEP (the hang record lives here), high. Parser: non-empty string → on; unset or empty → off.

### 1.3 `BC5_DIRECT_TIMEOUT_PROBE=1` (exp 0160; 0260 fsync; 0272 dispatch counts; P:32815-32834, 33256, 34536)
- Purpose: at a fence timeout, write the buffer the GPU ran to `ib-timeout-*.bin` (fsync), then journal its waits,
  label writes, dispatches and grids with memory "as the GPU left it", and fsync the journal.
- Behaviour: pure diagnostic on the GPU side; on the CPU side it copies every async job's IB: `it.job.ib_copy.assign
  (sub_ib, sub_ib + sub_n); it.job.ran_copy = r.executed_offsets;` (P:34536), with `BC5_DIAG_ENV(...)` = `getenv` per
  submission (not cached; the probe's own check at P:32827 is per timeout only).
- Purpose still open: yes. Every hang read used it: 0371 ("the host's timeout probe (journal lines 781,180-781,940)",
  0371 README:83); e8c2 F403 read ("The probe counts 3,805 dispatches, 2,187 of them indirect", H §"e8c2"; inputs
  `ib-timeout-00169867-acb-56426.bin`, `ib-timeout-00169868-dcb-2190.bin`); 19:54/06:40 draw class (`probe1954.py`).
- Overlap: devcoredump also carries IB #0 as fetched (H: "IB #0 is the acb: 248,896 host dwords") and the registers.
  The probe adds what devcd lacks: memory values now (labels, dims, indirect args), executed/DROPPED marks, the IB of
  the job behind it on the ring, and the journal-side context. Not redundant.
- Cost (reasoned, not measured): per submission one heap allocation + memcpy of the whole IB and the offsets vector,
  freed at completion; ≤128 in flight (CAP §1, `kSlots = 128`). At ~965 submissions/s and sizes of thousands to
  hundreds of thousands of dwords this is MB/s of copying plus mmap/munmap page faults for blocks above glibc's mmap
  threshold, on the game/ring threads, in a process the box is short of RAM for. The 0367 profile did not list it among
  the render thread's top functions (0367 README:13-16), so it is not a dominant cost; "libraries ... memcpy of IBs"
  is named in 0367 README:53.
- Verdict: KEEP the switch (needed), but MERGE/fix in code (medium confidence on gain): cache the env read; at timeout
  copy the IB from the job's device slot (the submitted copy lives in the slot until its fence) or keep copies only for
  a small ring of the last N jobs. Parser: `!= nullptr` (P:32827, 34536): `=0` is still ON; only unset is off. Restore:
  `BC5_DIRECT_TIMEOUT_PROBE=1`.

### 1.4 `BC5_DIRECT_TIMING=1` (exp 0022 step 3, run 77; P:31724-31726, 33165, 33764-33765, 33854-33879, 34580, 35455-35458)
- Purpose: per-submission timing lines (`timing: t … dwords: sync … hints …`, P:33877), per-job done lines
  (P:33241, 34580), per-flip VideoOutSubmitFlip line (P:35458), per CPU-served wait (P:31726), and a split summary
  every 128 submissions (P:33861-33862).
- Behaviour: pure diagnostic.
- Overlap: with QUIET on, its per-event lines are not written but kept in QUIET's 8,192-line ring and replayed before
  a timeout line (CAP §6). The F403 e8c2 read used that run-up ("The hung acb was synced at about t 289.83 (its
  2,026.5-ms wait ended at 291.858)", H, "*1. Our memory layer…*"; e8c2 ran r7m's words, i.e. quiet on). Dropping TIMING
  would empty the ring of its timing lines and lose the 128-submission summary (CAP:299-301).
- Cost: measured as part of the journal: rules 1, 2, 4 ≈ 2,000 lines/s ≈ 213 KB/s (CAP:270-281). With QUIET the bytes
  are not written; CPU remains: `timing_now()` and one `vsnprintf` per line into QUIET's buffer + ring copy under a
  mutex for dropped lines (CAP:322-324): ~2,000 formats/s, reasoned ≈ 1-2 ms CPU per second. Exp 0172: the whole
  journal+timing+frame profile cost 0-2.6 flips/s in short runs (0172 README:20-35).
- Verdict: KEEP with QUIET (medium-high). Parser: `!= nullptr` (P:31724, 33165, 33764, 35455): `=0` still ON.

### 1.5 `BC5_DIRECT_JOURNAL_QUIET=1` (exp 0401 e7 cap; mkcap:264-384, CAP §6)
- Purpose: drop the per-submission/job/wait/flip timing lines, acb-rest prefix lines and good every-64th submit lines;
  keep the last 8,192 (192 B a slot, 1.5 MiB BSS) and write them before a fence-timeout marker; a count line ≤ every
  10 s.
- Behaviour: pure diagnostic (direct.log content only; byte-identical off, CAP:305-308).
- Cost: measured gain 385 MB → 24 MB over 1,042 s (R401:525-526). Residual CPU: one vsnprintf per line, mutex on
  dropped lines (CAP:322-324). Ring covers ~4 s (CAP:325).
- Verdict: KEEP, high. Parser: env_on reading (mkcap:379-380): unset, "" and "0" off. Restore old behaviour:
  unset or `=0`.

### 1.6 `BC5_DIRECT_FRAME_PROFILE=1` (exp 0027 et seq.; P:33338-33420)
- Purpose: one `frame profile:` line per flip with the game thread's host time split (sync, hints, prepare, list, cs,
  fence, waits, outside), GPU busy, soft-CP polls.
- Behaviour: pure diagnostic.
- Overlap: FPS_COUNTER gives flips/s and gaps (stderr), not the split. TIMING gives per-submission times. The frame
  profile is what route scripts gate on (`run0401t.sh` per CAP:283-284) and what slowdown reads use (R401 Play 1: "at
  t 256 a flip took 103 ms, of it GPU busy 3.2 ms, outside the direct path 75 ms").
- Cost: per submission ~5 short mutex sections (`frame_profile_*`, P:33343-33405); per flip ~470 B ≈ 23 KB/s
  (CAP:283). Inference: that is about all of the quiet journal's remaining 23 KB/s (24 MB / 1,042 s), so ≈ 1.4 MB/min
  of page cache and writeback.
- Verdict: KEEP for scripted routes; drop-candidate for plain play only if the remaining 1.4 MB/min matters (low gain,
  medium). Better: sample every Nth flip in code. Parser: `!= nullptr` (P:33338): only unset is off.

### 1.7 Memory line, `BC5_DIRECT_MEM_LINE` (exp 0401 e3; mkunit:988-1045)
- Purpose: every 10 s MemAvailable, swap, PSI, GTT; flushes the min journal after each line (so the line before a crash
  survives); one detached thread, fixed buffers (CAP §1).
- Behaviour: pure diagnostic. Open purpose: yes (the memory story is the current main problem; R401 e7/e8 tables).
- Overlap: exp 0330's external sampler runs only in route tests (`run0401t.sh:11`), not in his play.
- Cost: ~90 lines/15 min (~14 KB) (CAP §1); one fflush per 10 s; three small file reads.
- Verdict: KEEP, high. Parser: on unless exactly "0" (mkunit:1043-1044; empty = on). Off: `BC5_DIRECT_MEM_LINE=0`.

### 1.8 `BC5_DIRECT_TABLE_CATCHER=1` (exp 0401 series e = exp 0402 item 4; mkunit:207-323)
- Purpose: F403 sub-class B. At submit, FNV-hash indirect-argument and LOAD_*_REG_INDEX tables (≤256 slots, ≤64 KiB
  each, mkunit:244-259); at completion and at a timeout rehash and journal changes (first 64, then every 1024th; all
  ≤64 at the timeout; a summary every 65,536 checks; mkunit:261-286).
- Behaviour: pure diagnostic (reads only).
- Open: yes, F403 is open; its timeout output fed the e8c2 read ("The table catcher shows 24 of 256 hashed slots
  changing by small float steps", H:816). The ~578k changes per play are counts, not lines (R401:95; 4,007-4,311
  lines a route, CAP §1).
- Overlap: the probe gives the values now; the catcher adds "at submit vs now". Different.
- Cost: reasoned small: a hash of usually 12-20 B slots plus LOAD tables per submission, a rehash and a
  `sorted_mappings()` shared_ptr copy per job; ≤1.8 MiB in flight (CAP §1). Not measured; e8's catcher-on arms ran
  32-35 flips/s (R401 e8 table) with no catcher-off control.
- Verdict: KEEP while F403 is open, medium. Parser: env_on (mkunit:228): unset/""/"0" off. Restore `=1`.

### 1.9 `BC5_DIRECT_ACB_INHERIT=journal` (+ ring census) (exp 0403 via 0401 e2/e3; mkunit:350-360, 700-760; R401:78-83, 106-114)
- Purpose: F403 hypothesis "an acb part dispatches with a program inherited from an earlier part". In journal mode the
  ring thread applies every acb part to a per-queue full-state tracker and counts every non-IB type-3 packet on ring
  slices (census).
- Behaviour: pure diagnostic in `journal` mode ("No submission changes", R401:80; with CS_PREFIX=0 as in SC).
- Open purpose: answered negative so far: 0 `acb inherit` lines in r5/r6/rA/rB/rC/rp0/rp1 (CAP §1), in the 19:54 play
  ("the play has 0 `acb inherit (exp 0403)` lines. Its 226 census lines report … none", H:248-249) and 155 s of e2
  (R401:95).
- Cost: reasoned: a tracker apply per acb part on the ring thread (R401:36: "with the switch on, the ring thread
  applies every acb part to its queue's tracker, as piece_check does for every dcb"); the same tracker's
  `apply_level` is 10.4 % of the render thread's samples for dcbs (0367 README:15). Plus the census walk per slice.
  Memory: `g_inh` ~140 KiB per queue, `g_inh_prog` unbounded ~80 B per program (CAP §1).
- Verdict: DROP-candidate, medium-high (no evidence lost; CPU gain unmeasured, plausibly the largest env-only one).
  Off: unset, "" or "0" (mkunit:353-354). Restore: `BC5_DIRECT_ACB_INHERIT=journal`.

### 1.10 `BC5_R3_REWIND_CATCH=1`, `BC5_R3_DROP_CATCH=1` (exp 0405 G4/G8 via 0401 e5; mkgpu:5-6, 92-93, 193-240; gpu0405-notes:95-151)
- Purpose: count REWIND with VALID clear; count packets the policy drops per opcode and custom NOP sub-codes.
- Behaviour: pure counters, first-occurrence lines, a summary per 10 s (≤90 lines, CAP §1).
- Open: answered: "drop catcher (G8) counted only opcode 0x4a, 112,152 times, and never 0x20" (R401:327). Neither is
  tied to the draw class or F403.
- Cost: one table lookup per packet in the soft-CP walk (gpu0405-notes:151); static counters ~2.7 KiB.
- Verdict: DROP-candidate, high confidence, low gain. Parser: env_on (mkgpu:72-76). Restore `=1`.

### 1.11 `KYTY_BC5_MEASURE=1` (exp 0174; P:27266-27270)
- Only effect: keeps the audio trace on when the session's logging is off. Logging is on in play, so no effect.
- Verdict: DROP (cleanup), high. Parser `!= nullptr`: unset to remove.

### 1.12 `KYTY_BC5_AUDIO_TRACE=1` (exp 0162, 0372 pad-route lines; P:27258-27301)
- Purpose: once a second per active port: push rate, held time, SDL queue; pad-route drop counts.
- Behaviour: pure diagnostic. Used by `replug0401t.sh:48` (the audio replug check: "pad route:" lines).
- Cost: per call a few counters; ~1 stderr line/s per port + `fflush(stderr)` (P:27297) ≈ tens of KB/min in
  play-last.log.
- Verdict: keep for audio/replug tests; drop-candidate for plain play (low gain, high confidence). Parser
  `!= nullptr`: only unset is off.

### 1.13 `KYTY_BC5_FPS_COUNTER=1` (exp 0172; P:10453-10480)
- One stderr line/s; one mutex per flip. Used by `run0401t.sh:187-188` and in every result table (flips/s, gaps).
- Verdict: KEEP, high (cheapest frame-rate record; ignores the logging switch). Parser `!= nullptr`.

### 1.14 `KYTY_BC5_INPUT_RECORD=~/bc5-work/route-record.txt` (P:37045-37075)
- Records pad events as INPUT_CMD lines; `fopen(…,"w")` per start (overwrites), `fflush` per event, stick moves at
  most every 30 ms. Feeds the scripted routes (memory: route keys).
- Cost: a few small writes per second at most.
- Verdict: KEEP, high. Parser: non-empty path → on; unset/empty off.

### 1.15 `BC5_DIRECT_PIECES_DRY=1` (exp 0155-era measurement; F133-F135)
- Not read anywhere in this code: 0 hits in P and in `backend/` (grep `PIECES_DRY`, `_DRY`). The dry tracker work it
  once gated now runs as part of the pieces path unconditionally (P:31538-31610, `dry_here`, ADR 0008 pieces). The
  string "pieces dry" was in the 0177-era binary (0177 README:46).
- Verdict: DROP from the env (no effect either way), high for this tree; medium that the binary matches.

### 1.16 Lean list (`KYTY_BC5_LEAN`, exp 0177; P:4170-4184, 4626-4638, 57045-57070)
- Compile-out: `BC5_DIAG_ENV` → null, `Bc5LoggingOn()` false, journal mode fixed to "min" (P:27560-27561), plus a
  priority-101 constructor that unsets 34 names, including `BC5_DIRECT_DRAW_ARGS_JOURNAL` (P:57067; F766's fix is in
  this tree).
- Gap: none of the 0401 switches (TABLE_CATCHER, ACB_INHERIT, MEM_LINE, JOURNAL_QUIET, R3_*, FL_*) is on the list,
  and they read `std::getenv`, not `BC5_DIAG_ENV`. No lean 0401 build exists (`raw/play-pkg-0401.diff`: "there is no
  private lean build"), so no live effect today.

### 1.17 `BO_JOURNAL`, `ARGS_HISTOGRAM`, `DRAW_ARGS_JOURNAL` (the coordinator's question)
- `BC5_DIRECT_BO_JOURNAL`, `BC5_DIRECT_ARGS_HISTOGRAM`: 0 hits in this worktree's `backend/` (and in P). They exist in
  Codex's candidate tree (REPORT.md:32, `direct.cpp:580/581` there, presence-parsed; F767 changed them to env_on).
  So not in the code this worktree builds. Not set in Z1 or SC. Default off.
- `BC5_DIRECT_DRAW_ARGS_JOURNAL`: here at D:508, parsed non-empty and not "0" (so `=0` is off). Not set in Z1 or SC.
  On the lean list (P:57067). Default off.
- Caveat: the box's current `bc5-run.env` was not read; Z1 is from 11-01.

### 1.18 Stall sampler (exp 0370-0377) and CPU sampler (exp 0162/0174)
- Stall sampler: a separate root service polling fences/registers, not in the emulator (P has 0 hits). Cost on the
  laptop ~0.4 % of a core per healthy poll stream (0373 README:62, 120); register samples 0.1-0.2 ms (F523). It uses
  mlockall (0373 README:67), so its RSS is pinned. Whether it runs during today's plays: not found (no launcher in this
  tree starts it; F583 says "no sampler event" for a 10-29 play).
- `cpu-sampler.sh` (1 line/s) started by `play-pkg.sh` (0174 README:14-15): measured "costs nothing measurable"
  (0177 README:62-66, 25.5 vs 25.6 flips/s).
- Verdict: no change; low gain.

### 1.19 Breadcrumbs (exp 0277/0393) and FL catchers (exp 0404)
- `BC5_DIRECT_BREADCRUMBS`: not in P (0 hits); exp 0393 ran a private binary (F768: +2.2 % level 1, +4.9 % level 2;
  "Patch 0001 is unchanged"). Not in play.
- FL_CRUMBS / FL_PROBE_STATE / MESHLET / F2: off in the e8 shortcut (SC:31-34 "No lazy release, no F2, no FL catchers").

### 1.20 stderr / play-last.log
- AMM/APR traces are gated (`KYTY_BC5_AMM_TRACE`, P:38362-38372; `KYTY_BC5_APR_FILE_JOURNAL`, P:38391-38402); neither
  is in Z1 or SC. The "exp 040x … on/off" lines print once per switch at init (R401:286, ≤ ~40 lines). gc-layer
  per-flip lines are off by default (`BC5_GC_LOG`, P:27483-27493: "they were a fifth of a 780 MB capture"). Hot-path
  stderr not found beyond audio trace and fps counter (not audited line by line across all 57k lines).

## 2. Ranking (likely gain × low risk)

| # | Item | Action | Gain | Risk to evidence | Confidence |
|---|---|---|---|---|---|
| 1 | TIMEOUT_PROBE per-job IB copy (P:34536) | code: cache getenv; copy at timeout from the slot, or ring of last N | CPU + heap/mmap churn per job; unmeasured, plausibly the largest left | none if the timeout copy stays | medium |
| 2 | ACB_INHERIT=journal + census | unset | ring-thread tracker apply per acb part + census walk | none (0 hits everywhere) | medium-high |
| 3 | FRAME_PROFILE in plain play | unset in play, keep in routes; or sample in code | ~1.4 MB/min page cache, 5 locks/submit | loses slowdown split in his plays | medium |
| 4 | R3_REWIND_CATCH, R3_DROP_CATCH | unset | one lookup per packet | none (answered) | high, low gain |
| 5 | AUDIO_TRACE in plain play | unset in play, keep in audio tests | tiny | loses audio pacing record | high, tiny gain |
| 6 | MEASURE, PIECES_DRY | unset | zero (cleanup) | none | high |
| 7 | QUIET formats dropped lines | code: classify by format string before vsnprintf | ~2k formats/s | none | low gain |
| 8 | JOURNAL_DONTNEED (exp 0330, not in main) | port | little now that the journal is ~1.4 MB/min | none | low |

Keep: JOURNAL=min, GC_DUMP_DIR, TIMEOUT_PROBE, TIMING (with QUIET), QUIET, MEM_LINE, TABLE_CATCHER (while F403 is open),
FPS_COUNTER, INPUT_RECORD.

## 3. True off values (parser read)

| Switch | Parser | Off | `=0` | Restore today |
|---|---|---|---|---|
| BC5_DIRECT_JOURNAL | `=="min"` (P:27564) | — (unset = heavy journal + sync jobs) | heavy mode | `min` |
| BC5_GC_DUMP_DIR | non-empty (P:27590) | unset/empty | n/a | the path |
| BC5_LOGGING | off only "0" (P:4576) | `0` | off | unset |
| BC5_DIRECT_TIMING | `!=nullptr` | unset only | ON | `1` |
| BC5_DIRECT_FRAME_PROFILE | `!=nullptr` (P:33338) | unset only | ON | `1` |
| BC5_DIRECT_TIMEOUT_PROBE | `!=nullptr` (P:32827, 34536) | unset only | ON | `1` |
| KYTY_BC5_AUDIO_TRACE / _MEASURE / _FPS_COUNTER | `!=nullptr` (P:27265, 27268, 10457) | unset only | ON | `1` |
| KYTY_BC5_INPUT_RECORD | non-empty path (P:37052) | unset/empty | writes a file named "0" | the path |
| BC5_DIRECT_JOURNAL_QUIET | env_on (mkcap:380) | unset/""/0 | off | `1` |
| BC5_DIRECT_TABLE_CATCHER | env_on (mkunit:228) | unset/""/0 | off | `1` |
| BC5_DIRECT_ACB_INHERIT | ""/0/unset off; journal/wave/skip; else -1 (mkunit:353-358) | unset/0 | off | `journal` |
| BC5_DIRECT_MEM_LINE | on unless "0" (mkunit:1043-1044) | `0` | off | unset |
| BC5_R3_REWIND_CATCH / _DROP_CATCH | env_on (mkgpu:72-76) | unset/""/0 | off | `1` |
| BC5_DIRECT_DRAW_ARGS_JOURNAL | non-empty, not "0" (D:508) | unset/0 | off | — (not set) |
| BC5_DIRECT_PIECES_DRY | not read | — | — | — |

## 4. Hang-record kit (minimal, keeps the evidence the hang reads used)

What the last reads actually used: the devcoredump (registers, IB #0) for the class; `ib-timeout-*.bin` + probe lines
(dispatch counts, ran/DROPPED, labels, dims) for F403 (e8c2) and the draw class; the quiet ring's run-up (sync time of
the hung acb); cpu-wait GIVEN UP and zero-skip canary lines (unconditional journal lines, kept by QUIET); the table
catcher's at-timeout line (H:816); the memory line (R401: "r7all was not short of memory when it hung").

Kit:
1. devcoredump via the udev rule (kernel side; costs nothing during play, 0324 README "Not touched").
2. `BC5_GC_DUMP_DIR=<capture>/gc`, `BC5_DIRECT_JOURNAL=min` (also functional).
3. `BC5_DIRECT_TIMEOUT_PROBE=1` — with the code fix of §1.3 so it stops copying every IB.
4. `BC5_DIRECT_TIMING=1` + `BC5_DIRECT_JOURNAL_QUIET=1` — that is the "small ring of the last submits": 8,192 lines,
   ~4 s, written only at a timeout.
5. Memory line (default on).
6. `KYTY_BC5_FPS_COUNTER=1`.
7. While F403 is open: `BC5_DIRECT_TABLE_CATCHER=1`.

"One devcoredump + a small ring" is not quite enough: F403's read needed the probe's memory-now values and dispatch
counts, which neither devcd nor a submit ring has. With the FL catchers off, a draw-class (19:54/06:40) hang will be
recorded by class (devcd: GE/PA/SPI/SX busy, ME 0x956/0xb8b) and by the probe, but the stuck draw will not be named
(that needed `BC5_DIRECT_FL_CRUMBS`, H §"r7all 06:40"; crumbs add end-of-pipe load, R401:153). That is the accepted
trade of the e8 shortcut, not a new loss.

Proposed env diff for plain play (needs his yes and the top's GO; launcher/env writes are box writes):
- unset `BC5_DIRECT_ACB_INHERIT`, `BC5_R3_REWIND_CATCH`, `BC5_R3_DROP_CATCH` (SC words);
- unset `KYTY_BC5_MEASURE`, `BC5_DIRECT_PIECES_DRY` (bc5-run.env; no effect today);
- optional: unset `KYTY_BC5_AUDIO_TRACE` and `BC5_DIRECT_FRAME_PROFILE` for plain play only (keep both in test
  launchers: replug check and route gating read them).
Rollback: put the same words back with the values in §3's last column.

## 5. Not found / open
- No committed per-kind byte breakdown of a quiet journal; the frame-profile attribution of the remaining 23 KB/s is an
  inference from two rates.
- No measurement of TIMEOUT_PROBE's copy cost, ACB_INHERIT's CPU, or TABLE_CATCHER's CPU (no on/off arm exists for
  the last two, CAP §2 "What the data cannot show").
- Today's box `bc5-run.env` and `play-pkg.sh` contents (box off limits); Z1 (11-01) used instead.
- Whether the stall sampler service runs during his plays today.
