# cap0401: do the e-series catchers and the journal grow memory over a play? (exp 0401 series e7, tag cap)

The question (the top session, 2026-11-04 evening): the maintainer reports "Ram się dusi" while playing e6 (GTT 12,889
of 13,312 MiB, MemAvailable 216 MiB, swap 1.4 GiB at t≈684 s). Do the catchers and the journal that e6 runs with grow
memory over a play? Laptop only; no box access.

**Verdict.**
- **No catcher and no journal buffer grows per submission, per frame or per run.** Every per-submission buffer is freed
  when its job completes, at most 128 jobs fly at once, and the rings and counters are fixed. The journal's heap is one
  1 MiB stdio buffer.
- **Two maps of exp 0403's `BC5_DIRECT_ACB_INHERIT` have no bound in the code.** They take one entry per new key and
  never drop one: `g_inh_prog` by compute program address, and the per-queue census by SET_SH_REG kind. They grow only
  with what the title sends: a few KiB per thousand programs, not per frame. On this title's route the census stays
  empty.
- These two now have a cap, each behind its own default-off switch (below). It is insurance only, not the cure for
  "Ram się dusi".
- **The data puts the pressure in GTT, not in the catchers.**
  - With every catcher on, the 15-minute routes held GTT flat after the load and lost under 1 MiB/min of MemAvailable.
  - The maintainer's own plays on the same build and switches grew GTT by about 90 MiB/min, to 12,6xx-13,003 MiB.
  - No catcher allocates GPU memory or maps guest memory, so none of that GTT growth can be theirs.
  - GTT is the guest's pinned memory: the zero skip's (zsk) and the lazy chunks' (lzr) ground.
- **The journal file is the one thing that does grow: ~0.5 GB per 15 min in every arm.** It costs disk, page cache and
  writeback, not heap. The top session's follow-up adds `BC5_DIRECT_JOURNAL_QUIET` (§6), default off.
  - With it on, the per-submission, per-job, per-wait and per-flip lines are not written: at least ~13 MB a minute,
    ~44 % of the bytes.
  - Summaries, the memory line, timeout output, catchers' first lines and every error or warning line stay.
  - The dropped lines are kept in a ring and written just before a fence timeout.

## 1. The buffers, per catcher

Lines are in e6's unit `src/libs/bc5LleAgc.cpp` d1cfd9bb (`scratchpad/e7/e6tree`). Sizes are measured with clang 22:
`CatchSlot` 56 B, `FlDraw` 264 B, `FlVal` 24 B, `InheritProg` 32 B. A libstdc++ map node costs 32 B more, then malloc
rounds it: about 80 B per program and 64 B per census kind.

The in-flight bound: the backend refuses a submission whose slot is still busy (`backend/src/direct.cpp:261` `kSlots =
128`, `:1067` "the host lets fewer jobs fly than there are slots", -EBUSY). So at most 128 `PendingJob`s exist at once,
each freed by the completion thread (`completion_thread`, `cq_push` 7793).

| Catcher | Buffer (unit line) | Grows per | Freed? | Bound in the code | 15 min at ~50 flips/s |
|---|---|---|---|---|---|
| `BC5_DIRECT_FL_CRUMBS` (exp 0404) | crumbs ring in the backend's existing 64 KiB GDS shadow BO (6565-6579, 7080) | nothing: 64 entries × 128 B + 0x100 at +0x8000, the entry is `made++ % 64` (6924) | (fixed) | 8.25 KiB, no new BO | 0 |
| | `g_fl_state` (7117): one `FlState`, its stack (6619) | push at CLEAR_STATE 1 | popped | 8 deep (6798) | 0 |
| | `fl_scan`'s `ranges` (6701) | COND_EXEC | at return | 32 (6812) | 0 |
| | `FlPlan::draws` (6679, 6863), moved into `PendingJob::fl_plan` (7318, 9108) | draw with crumbs | at completion | the buffer's draws × 264 B; ≤ 128 jobs | 0. rA: 1.41 M draws in 32,769 buffers, ~43 a buffer, ~11 KiB a job |
| | `fl_ib`, `old_to_new`, `new_to_old`, `unit_at`, the drop copy (6908-6976, 7132, 8985) | submission | at `submit_now`'s return | ~4 × the buffer | 0 |
| | journal (7171-7217) | draws | (file) | 16 lines, then every 4096th; a summary per 16,384 buffers | ~350 lines |
| `BC5_DIRECT_TABLE_CATCHER` (exp 0402 item 4, series e) | `catch_slots` (8506), moved into `PendingJob::catch_slots` (7317, 9107) | submission | at completion (7761) or at once (9091) | 256 slots (6464) × 56 B; each slot hashes ≤ 64 KiB, nothing copied | 0; ≤ 1.8 MiB in flight |
| | counters (6452) | | | atomics | 0 |
| | journal (6491-6503) | changed slots | (file) | 64 lines, then every 1024th; a summary per 65,536 checks | 4,007-4,311 lines a route (`raw/night/*-journal.txt`) |
| `BC5_DIRECT_ACB_INHERIT=journal` (exp 0403) | `g_inh` (4283): a `full_state::Tracker` per guest queue | new queue | never | queues × ~140 KiB (RegFile arrays, `full_state.hpp`; the overflow map ≤ 64 Ki registers; the stack `kMaxStack`) | 0 after the first frames |
| | **`g_inh_prog` (4284)** | **new program address in a bound dispatch (4324)** | **never** | **none** | **+80 B per new program: the title's distinct compute programs, not frames; count not journaled** |
| | `g_inh_ring` (4285) | physical ring | never | ≤ 5 rings | 0 |
| | `g_inh_census` (4286): `ops` | opcode | never | 256 | 0 |
| | **its `sh` (4451)** | **new (first register, count) of a SET_SH_REG on a guest ring** | **never** | **none (2^24 keys possible)** | **0 on this title: "the ring census on queue 0 found no non-IB type-3 packets" (README, series e3)** |
| | `g_inh_drop` (4287) | skip mode only | taken at submit | cleared above 4096 (4405) | 0 (journal mode) |
| | `ds`, `inh`, `pre` (4309, 4345, 4355) | call | at return | the part | 0 |
| | journal (4423, 4442, 4461) | parts | (file) | 64, then every 1024th; census every 1024th slice | 0 lines in r5/r6/rA/rB/rC/rp0/rp1 |
| `BC5_DIRECT_MEM_LINE` (series e3, on by default) | one detached thread (6250), stack buffers (6234), two temporary paths | 10 s | at once | fixed | 0; ~90 lines (~14 KB) |
| Direct journal, `direct.log` (1533-1576) | `journal_min` mode (the launchers' `BC5_DIRECT_JOURNAL=min`): one `FILE*`, `setvbuf` 1 MiB (1538), flushed ≥ every 0.5 s and after each memory line | lines | (file) | 1 MiB of heap | 0 heap. The file holds 484-510 MB a route on the NVMe (`~/bc5-data/captures/play-*/gc`) in every arm: e2's control rB 507 MB, rp0/rp1 (FL and gpu off) 510 MB, r5/r6 (all on) 484/487 MB. So it is the base build's, not the catchers'. Its pages are page cache (reclaimable, inside MemAvailable). Other mode: fopen/fclose per line, 0 heap |
| exp 0405 gpu group (`BC5_R3_*`: REWIND_CATCH, DROP_CATCH, MEMSEM_SIGNAL, SUBMIT_EOP_EVENT, COND_WRITE, WAIT_IDLE, TS_100MHZ) | counters `g_r3gpu_count[16]`, `drop_op[256]`, `nop_sub[64]`, `seen[6]` (557-560) | | | static, ~2.7 KiB | 0 |
| | G6's EVENT_WRITE_EOP slots `g_r3gpu_eop_slots[4096][6]` (722) | chained ioctl | ring (`& 4095`) | 96 KiB static | 0 |
| | G6 unchained: a `Direct::post` closure (738) | ioctl | run by the completion thread | the queue | 0 |
| | `r3gpu_summary` (766-802): two strings | 10 s | at return | ≤ 320 entries | 0; ≤ 90 lines of ≤ ~4 KB |
| | first-occurrence lines (563-751) | new kind | (file) | 256 + 64 + 9 kinds | ≤ 329 lines a run |

## 2. The data

**The routes' memory lines** (`raw/night/<tag>-memline.txt`, every 10 s; summarised by
`scratchpad/e7/cap/memstat.py`; G = 113 s; slope = least squares over t ≥ G+60, per minute):

| Arm | Catchers on | Available at G+60 → G+900, MiB | Slope, MiB/min | Swap G+60 → end | GTT after G+60 | GTT slope |
|---|---|---|---|---|---|---|
| r5 (e5) | FL_CRUMBS, TABLE, INHERIT, gpu | 539 → 534 (min 511) | −0.2 | 555 → 553 | 12,049 | 0.0 |
| r6 (e6) | the same | 703 → 689 (min 669) | −0.5 | 771 → 767 | 12,054 | 0.0 |
| rA (e4) | FL_CRUMBS, TABLE, INHERIT | 520 → 507 (min 487) | −0.9 | 544 → 542 | 12,051 | 0.0 |
| rC (e4) | the same | 492 → 495 (min 472) | −0.4 | 544 → 558 | 12,064 | 0.0 |
| rp0 (e6p) | TABLE, INHERIT only | 514 → 495 (min 445) | 0.0 | 551 → 576 | 12,083 | 0.0 |
| rp1 (e6p) | TABLE, INHERIT only | 659 → 739 (min 417) | +7.7 | 758 → 1,029 | 12,097 | 0.0 |
| rB (e2) | no memory line (e2 predates it); sampler floor 523 | | | | | |

- *What it shows.* Over 15 minutes, with every catcher on, MemAvailable moved by −14 to +3 MiB after the load. GTT
  stayed flat to the MiB. The arms with FL_CRUMBS and the gpu group off (rp0/rp1) drift as much or more: rp1 swapped
  out 270 MiB with its catchers off.
  - That is an upper bound for everything on the box, catchers included, on this route: under 1 MiB/min.
  - The floors in the README tables (r6 668 against rB 523) differ by box state, not by switches: a6 had 1,276 with a
    GTT plateau 750 MiB lower.
- *The start arms* (90 s, one value at the save-slot list): s0 425, scrumbs 573, sall 524; t0 547, tgpu 582, tall 475;
  t6 530, t6all 481. The catcher-on arms sit on both sides of their base by ±150 MiB. That is box-state noise, and 90 s
  cannot show growth.
- *The maintainer's plays on e6* (his shortcut: r6's words, with audio `set,room`). These are the memory curves in
  `hang1954-0401.md` §4, from the plays' own memory lines:
  - The 19:47 play: GTT 12,053 → 12,620 MiB from 70 s to 420 s (+97 MiB/min); available 655 → 282; swap 689 → 1,183.
  - The 19:58 play: GTT 11,983 → 13,003 from 70 s to 774 s (+87 MiB/min); available 161 MiB at its minimum; swap
    peaked at 1,715; PSI full peaked at 61 %.
  - The same build and the same catchers held GTT flat on the scripted route. So the growth comes with the play
    (moving through the world), in the guest's pinned memory.
  - Over 130-734 s of 19:58: available −178 MiB and swap +954 MiB, against GTT +682 MiB.
    - The rest (~450 MiB) cannot be split from these lines. It could be zram's own compressed pool, page cache, or
      host heap.
    - The catchers' code gives them no path to that much: the only growing maps take ~80 B per new program.
- *What the data cannot show.*
  - `TABLE_CATCHER` and `ACB_INHERIT=journal` were on in every arm, so there is no off arm for them.
  - MemAvailable is system-wide (desktop, page cache, zram), and the night records hold no per-process RSS or heap.
  - The routes are scripted and stay in one place, so content-driven growth (new programs into `g_inh_prog`) is barely
    exercised.
  - `g_inh_prog`'s size is never journaled.
  - The 500 MB journals stay on the box: their make-up is not known here.
  - A next catcher would settle the host side in a free play. That is one more line every 10 s from the memory-line
    thread:
    - the host heap: glibc `mallinfo2()`, in use and mmapped;
    - the process: `/proc/self/status` VmRSS, RssAnon, RssFile, RssShmem and VmSwap.
    - Not written here: it would anchor in `mem_line_loop`, where lzr may add its own counts.

## 3. The edit: `mkcap0401.py`

Two switches, each off by default and read once, as `bc5::env_on` reads them (unset, empty and "0" are off):

| Switch | Caps | Default when on |
|---|---|---|
| `BC5_DIRECT_INHERIT_PROG_CAP` | `g_inh_prog` | 65,536 programs (~5 MiB of nodes) |
| `BC5_DIRECT_INHERIT_CENSUS_CAP` | each guest queue's census `sh` | 4,096 kinds (~256 KiB) |

- An on value that is a decimal number from 2 to 2^32 is the cap. Any other on value ("1", "on", "abc") takes the
  default.
- A full map records no new key. The refusal is counted, and journaled the first time and every 65,536th:
  `exp 0401 e7: acb inherit program map full at N entries (cap N): a new program is not recorded (K so far)`, and the
  same with "census" / "SET_SH_REG kind". Keys already in keep counting.
- A program that was not recorded reads as "never bound in a part of its own". Queue mode then leaves that head on the
  ring's state ("unknown, fallback ring"), today's answer for an unknown program. Nothing more is dropped.
- *Off* (cap 0): `cap_slot` returns `&m[key]`, the element today's `operator[]` gives, and the updates are today's
  lines. Both maps exist only with `BC5_DIRECT_ACB_INHERIT` on; with it off none of this code runs and the caps are
  never read.
- *The state line.* At the first use (the first tracked acb part) it journals and prints one line on stderr:
  `[bc5] exp 0401 e7: acb inherit caps: programs <N|off>, census <N|off> per queue`. For box0401.sh's binary check:
  `BC5_DIRECT_INHERIT_PROG_CAP`, `BC5_DIRECT_INHERIT_CENSUS_CAP`, `exp 0401 e7: acb inherit caps: programs %s, census %s per queue`.

**Where.** Everything lies in the unit's exp 0403 block, between `// Experiment 0403 (exp 0401 series e3;
BC5_DIRECT_ACB_INHERIT` and `// Experiment 0401 (BC5_DIRECT_ACB_CS_PREFIX=1`. The script asserts this for every anchor.
- *Functions touched:*
  - `acb_inherit_track`: its four `g_inh_prog` lines become `inh_prog_note(pgm, d.w32, part);`;
  - `acb_inherit_census`: its `c.sh[...]++` line becomes `inh_census_sh(c, ...)`.
- *New:* `cap_parse`, `cap_slot` (template), `InhCaps`/`inh_caps`, `g_inh_cap_refused`, `inh_cap_refused`,
  `inh_prog_note`, `inh_census_sh`, inserted after `g_inh_skip_heads`. Also the CPU test's seams `bc5_cap0401_parse`,
  `_slot`, `_caps`, `_prog_note`, `_prog_size`, `_prog_get`, `_census`, `_census_size`, `_census_get` and `_refused`.
  The seams sit after `acb_inherit_census_slice`, inside the `KYTY_BC5_DIRECT` block; they are always compiled in and
  never called by the emulator, as exp 0405's gpu seams.
- *Output lines (d1cfd9bb → e01074da, with §6's journal edit):*
  - 1551-1757: the journal block;
  - 1762-1768: the call in `journal`;
  - 4505-4586: the cap block;
  - 4620: `acb_inherit_track`;
  - 4744: `acb_inherit_census`;
  - 4767-4834: the seams.

  Everything else is unchanged.

**The chain.** zsk → lzr → cap. The script pins its one input in `PINNED` (one dict, d1cfd9bb today), and the top
session re-pins it there. Run on the laptop with zsk's and lzr's current scripts and a re-pinned copy: d1cfd9bb →
8710207e → 8ddf48f3 → bcbdd308 (§5). It was also run on a stand-in chain with zsk- and lzr-like lines in
`sync_mappings` and before `mem_line_start`: the output was today's plus exactly those lines.

## 4. The CPU test: `cap0401.cpp`

Built on the box `--gate cap0401.cpp <out> --like src/libs/bc5LleAgc.cpp`. Gate row:
`cap0401.cpp src/libs/bc5LleAgc.cpp BC5_DIRECT_INHERIT_PROG_CAP,BC5_DIRECT_INHERIT_CENSUS_CAP,BC5_DIRECT_JOURNAL_QUIET cap0401`.
- It calls the real code through the seams: `cap_parse`, `cap_slot`, the unit's own switch reading,
  `acb_inherit_track`'s update (`inh_prog_note`) and the real `acb_inherit_census`.
- It sets `BC5_DIRECT_ACB_INHERIT=journal` and `BC5_DIRECT_MEM_LINE=0` itself, before the first call.
- *The play's journal mode.* It runs itself again once with `BC5_DIRECT_JOURNAL=min` (`CAP0401_REEXEC=1` marks the
  second run, as gpu0405 does), so the journal case runs in the play's mode. If the re-exec fails, it says so and goes
  on in the other mode.
- *The real `journal()`.* The journal case gives `journal()` a directory of its own: `./gc-cap0401`, inside the fresh
  directory the box runs each setting in. It then reads `direct.log` back. It runs last; before it no directory is
  set, so the earlier cases write nothing.
- No game, GPU, window, sound, network or USB. The direct path is never opened.
- A 60-s watchdog prints a FAIL line. The end line is `cap0401: on|off|mixed <items> N of N; end`, and the exit code
  is 0 only then. An argument that disagrees with the switches gives exit 2.

| Case | What | Checks |
|---|---|---|
| parse | 19 values: unset, "", "0", "1", "2", "64", "65536", "00", "01", "02", "abc", "on", "12x", " 5", "-5", "+5", 2^32, 2^32+1, a 26-digit number; each against the expected value and against the test's own reading | 38 |
| slot | 20,000 pseudo-random keys over 3,000 against a reference written apart: cap 0 (= operator[]), cap 100, cap distinct−1, cap distinct, cap 2^20, no keys. Size, refusals, every (key, count) | 23 |
| switches | the unit read the caps the test reads | 2 |
| programs | on: cap + 1,000 programs, cap held, 1,000 refused, the first kept and counted again in the other wave mode, a refused one stays out. Off: 70,000 all held, 0 refused (today's) | on 13, off 8 |
| census | on: cap + 50 SET_SH_REG kinds, cap held, 50 refused, a held kind counted again, a refused one absent. Off: 5,000 all held. Either way the opcode count takes all of them, a NOP and a 2-dword SET_SH_REG are as today | on 7, off 6 |
| quiet kinds | 29 lines built with the unit's own format strings, through `journal_quiet_kind` (pure, either setting). Each of kinds 1-6 is dropped. These stay: a retried or failed submit line, the summaries, the memory line, cpu-wait GIVEN UP and its detail, sampled and first-occurrence catcher lines, the quiet count itself, another timing line, a line without its newline, a line cut at the buffer, the first half of a mapping line, an empty line. These are triggers (−1): a TIMEOUT submit line, the table catcher and the crumbs at the timeout, the timeout probe, `timeout:`, `reopen:` | 29 |
| quiet ring | a ring of its own: 3 lines back in order and emptied; 8,292 lines give the last 8,192, oldest first; a 191-byte line kept whole, a 192-byte line cut to 187 bytes + "...\n" | 7 |
| quiet journal | the real `journal()` with 16 lines: 7 droppable, then a TIMEOUT line, a catcher-at-timeout line and one more droppable line. On: `direct.log` holds the state line, then the 6 kept lines, then the 7 dropped ones between the two markers, oldest first, then the two timeout lines. The last line is not written. The counts are 2/2/1/1/1/1, and the byte total and the summary text match. Off: `direct.log` is the 16 lines byte for byte, and the counts are 0 | on 13, off 10 |

**Counts:**
- on: 132 of 132;
- off: 123 of 123, and unset gives the same (it prints `off`);
- mixed: quiet alone 126, both caps alone 129.

**Stand-in run (laptop).**
- *Build.* `scratchpad/e7/cap/mkstandin.py` cuts the output unit's real text into one TU:
  - the journal: `journal_min_file`, the quiet block, `journal`, `timing_now`;
  - `InheritProg`, `InheritCensus` and the three maps;
  - `acb_inherit_mode`, the cap block, `acb_inherit_census` and the seams.

  The stubs are `g_dump_dir`, `g_journal_min` (built both ways, `-DSTANDIN_MIN=0/1`), `SoftCp::now_ns`,
  `Log::Bc5LoggingOn` and a POSIX `unistd.h`. Windows writes LF only with `_set_fmode(_O_BINARY)`. It was linked
  with `cap0401.cpp` (clang 22, `-Wall -Wextra -Werror`).
- *Runs.* The re-exec is Linux-only, so each journal mode was its own build.
  - Each mode: on 132/132, off 123/123, unset 123/123, quiet alone 126/126, the caps alone 129/129.
  - Caps 100/10 with quiet `yes`: 132/132.
  - Off: the `direct.log` of the two modes is byte-identical.
  - A wrong argument: exit 2.
- *Mutations.* None of these prints "; end":
  - a cap that lets 5 more in: on 65 of 83 (before the quiet cases);
  - cap 0 not equal to operator[]: off 70 of 77;
  - no ring flush at a timeout: on 131 of 132;
  - rule 6 looser (`" ... OK rc "`, retried dropped too): on 127, off 122;
  - the off path taking the quiet branch: off 115 of 123.

## 5. Laptop checks

- *Applies.* To e7's input tree: `src/libs/bc5LleAgc.cpp e01074dab59f975d31a6bfd9a632f69a`.
- *Refuses.* Its own output ("has the edit already") and another md5 ("not the pinned input").
- *Undo.* Built into the script: undoing the five edits gives the input back byte for byte. `diff` input → output
  shows three insertions (the cap block, the seams, the journal block) and three replaced spans:
  - `acb_inherit_track`: 4 lines → 1;
  - `acb_inherit_census`: 1 → 1;
  - `journal`: 7 lines inserted after its logging check.
- *Formats.* The script asserts that the unit still writes each line a quiet rule keys on with the exact format the
  rule was written for (`QUIET_FORMATS`).
- *Balance.* Braces 2007/2007 → 2072/2072; parentheses +319 of each; brackets +45 of each. The input's own odd
  parenthesis and bracket counts (strings and comments) are unchanged. `cap0401.cpp` balances. The inserted text is
  ASCII, LF, and there is no BOM.
- *Syntax.* VS clang++ 22.1 (x86_64-pc-windows-msvc), `-fsyntax-only -ferror-limit=0 -std=c++20 -Wall -Wextra
  -Werror`, with e5 gpucheck's POSIX stand-ins, `backend/include`, fmt from `refs/Inori_GPCS4` (-isystem) and
  magic_enum from `refs/InoriRus_Kyty`, and `-D_CRT_SECURE_NO_WARNINGS -D_CRT_NONSTDC_NO_WARNINGS` (otherwise MSVC
  flags each new `getenv`):
  - *Without `KYTY_BC5_DIRECT`:* input and output give the same 5 messages. The journal block sits outside the direct
    block, so it reads its switch without `bc5::env_on`, whose header comes with the backend; a first draft that used
    it was caught here.
  - *With `-DKYTY_BC5_DIRECT=1`:* the same 19 messages, all in today's Linux-only code (`mincore`, `pread`, memfd,
    `SEEK_DATA`, …), none in the new lines.
  - *Stricter:* the stand-in TU (the unit's real new text) and `cap0401.cpp` are clean under `-Wshadow -Wconversion
    -Wsign-conversion -Wpedantic` too.
- *The chain, run on the laptop.*
  - zsk's current `mkzsk0401.py` (571c04b5): d1cfd9bb → 8710207e.
  - lzr's `mklzr0401.py` (3e864318): → 8ddf48f3.
  - This script with `PINNED` re-pinned: → bcbdd308.
  - A stand-in chain (zsk- and lzr-like lines elsewhere) gives today's output plus exactly those lines.
- *Not checked.*
  - GCC or the box's own compile command.
  - The link against every emulator object, and the gate run on the box, including its re-exec into the min mode.
  - `acb_inherit_track`'s new line inside a real tracked part (it needs a device).
  - Any play with the caps or quiet on, and so the real bytes quiet saves (§6 gives the estimate).
  - The number of distinct programs `g_inh_prog` holds after a real play (not journaled).

## 6. `BC5_DIRECT_JOURNAL_QUIET` (the top session's follow-up)

**Why.** `direct.log` reaches 484-510 MB per 15-min route in every arm (§1); that is about 29.6 MB a minute. Its
pages are page cache and dirty-page writeback, while MemAvailable sits near 200 MiB in his plays.

**Which writers make the bulk.** No committed record counts `direct.log` by line kind:
- `raw/night/*-journal.txt` gives only the size and three counts;
- `*-probe.txt` holds only crumbs lines.

So the writers come from the code and the play's environment.
- *The environment.* `bc5-run.env`, as the run manifests list it (e.g. exp 0399's `raw/Z1.manifest.txt`), sets
  `BC5_DIRECT_JOURNAL=min`, `BC5_DIRECT_TIMING=1`, `BC5_DIRECT_FRAME_PROFILE=1` and `BC5_DIRECT_TIMEOUT_PROBE=1`, with
  no per-draw or per-dispatch journal (`DISPATCH_JOURNAL`, `DRAW_JOURNAL`, `FIND_VA`, `OPS_DUMP` and `WAIT_TRACE`
  unset).
- *The code.* All 215 `journal(` calls were read (`scratchpad/e7/cap/jsites.txt`). In that environment, these write
  a line per event with no sampling:

| Rule | Line (unit line in d1cfd9bb) | Per | Bytes a line | Lines/s at the 19:47 play's rate | KB/s |
|---|---|---|---|---|---|
| 1 | `timing: t … s dcb N dwords: sync … ms, hints … ms qN` (8384) | submission | ~73 | ~965 | ~70 |
| 2 | `timing: #N done at t … s, … device: prepare … fence … ms, N BOs` (7746; 9152 synchronous) | completed job | ~145 | ~965 | ~140 |
| 4 | `timing: t … s flip N/N, VideoOutSubmitFlip took … ms` (10234) | flip | ~60 | ~50 | ~3 |
| 6 | `submit #N … OK rc 0 … ms` (7742, 9131) | 64th submission | ~140 | ~15 | ~2 |
| 3 | `timing: t … s after that wait (dcb N dwords)` (5243) | CPU-served wait | ~50 | not known here | — |
| 5 | `acb rest a..b of N dwords: state prefix of N dwords replayed first` (6286) | acb rest with a prefix | ~75 | not known here | — |

- *The rate.* The 19:47 play reached submission #412,349 at journal t 427.3 s (`hang1954-0401.md` §4), about 965
  submissions a second over the whole play. Its journal had 1,147,977 lines in about 430 s, about 2,670 a second.
- *The share.* Rules 1, 2, 4 and 6 come to ~2,000 lines/s (~75 % of the lines) and ~215 KB/s, ~12.9 MB a minute (~44 %
  of the bytes). Rules 3 and 5 add an amount not known here.
- *Not dropped.* The frame profile is per flip too (~50/s × ~470 B ≈ 23 KB/s), but it is a summary the routes gate on
  (`run0401t.sh`), so it stays.
- *The rest.* About 280 KB/s in ~670 lines/s is not attributable from the laptop: long lines, rarer kinds and the
  catchers' sampled lines.
- *Measuring it on the box.* A read-only one-liner over an existing journal, e.g. r6's
  `~/bc5-data/captures/play-20261104-1452/gc/direct.log`:

  ```
  awk '{k=$1" "$2; if (k=="timing: t") k=(/ dwords: sync/?"timing/submission":/after that wait/?"timing/wait":/ flip /?"timing/flip":k); n[k]++; b[k]+=length($0)+1}
       END {for (k in n) printf "%12d %9d %s\n", b[k], n[k], k}' direct.log | sort -rn | head -25
  ```
- *Measured by the switch itself.* With it on, its count line (at most every 10 s) gives the bytes it did not write.

**The estimate.** Quiet saves at least ~13 MB a minute of `direct.log`, page cache and writeback (~44 % of the
journal's bytes) at the 19:47 play's submission rate. The per-wait and acb-rest lines add more. The remaining ~16 MB a
minute is unchanged.
- The same per-submission lines could also be removed by unsetting `BC5_DIRECT_TIMING` in `bc5-run.env`. Quiet keeps
  three things that would lose: the timing summary (every 128 submissions), the cpu-wait lines, and the run-up to a
  fence timeout (the ring).

**What it does** (`mkcap0401.py` edit 5; the unit's `journal()`, which only this unit calls; the non-min path's own
`fprintf` lines at 8886/9141 are not journal lines and stay):
- *Off* (unset, empty, "0"):
  - each line takes today's path after one flag test;
  - the first journaled line prints `[bc5] exp 0401 e7: journal quiet off` on stderr;
  - `direct.log` is byte-identical (the test checks it in both journal modes).
- *On.* Each line is formatted into a 1024-byte buffer and classified by its text (`journal_quiet_kind`):
  - A whole line (newline-ended, not cut) of kinds 1-6 is not written. It goes to a ring of the last 8,192 lines (192
    bytes a slot, 1.5 MiB of BSS, touched only when on), and is counted by kind and bytes.
  - A line that marks a fence timeout first writes the ring, oldest first, between `journal quiet (exp 0401 e7): the
    last N lines it did not write, oldest first, before the timeout line below:` and `journal quiet (exp 0401 e7): end
    of the lines it did not write`. The markers are a `submit #` line with TIMEOUT, "at the timeout", `timeout probe:
    `, `timeout: ` and `reopen: `.
  - Everything else is written as today: summaries, the memory line, the timeout probe, the crumbs at a timeout,
    catchers' first-occurrence and sampled lines, and FAILED, TIMEOUT, GIVEN UP and retried lines. Lines longer than
    the buffer take today's path.
  - At most every 10 s, a count line: `journal quiet (exp 0401 e7): t … s: not written so far: per-submission timing
    N, per-job timing N, per-wait timing N, per-flip timing N, acb rest N, submit progress N; N lines, N bytes in all`.
  - The state line: `exp 0401 e7: journal quiet on, not written: …`.
- *Costs and limits.*
  - One `vsnprintf` per line, in place of the `vfprintf`.
  - A mutex only for dropped lines and flushes.
  - The ring covers ~4 s of dropped lines. It helps only when the host reaches the timeout path. A machine-down loses
    what the 0.5-s flush had not written, as today; it now loses fewer lines, because fewer are written.
- *Who reads these lines.* `timeline1954.py` and similar hang analyses read the per-submission timing lines, which
  quiet leaves out except in the ring. Use it for plays meant to be light, not for hang hunts.
- *For box0401.sh's binary check:* `BC5_DIRECT_JOURNAL_QUIET`, `exp 0401 e7: journal quiet %s`,
  `journal quiet (exp 0401 e7): t %.1f s: not written so far`.

## Files

| File | md5 |
|---|---|
| `mkcap0401.py` | `87fea1fbbca6d0fdc573242cbd68021b` |
| `cap0401.cpp` | `e7abc7acfb2593fd7a17a4d70454cd72` |
| input `src/libs/bc5LleAgc.cpp` (e6) | `d1cfd9bb1f1b3485bed4207a7f064d4f` |
| output `src/libs/bc5LleAgc.cpp` | `e01074dab59f975d31a6bfd9a632f69a` |
| zsk (571c04b5) → lzr (3e864318) → this script re-pinned: in / out | `8ddf48f372f7c555c1b3abe609d0905b` / `bcbdd3082bf5371393989bb69b1f76fa` |
