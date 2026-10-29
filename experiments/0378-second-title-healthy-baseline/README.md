# 0378 — The second title's healthy-frame register baseline (RT on, stall sampler 0377)

**Date.** 2026-10-29 10:40–10:57. **Box.** One run of the second title (B1, 10:43:29–10:53:42) on the top session's
GO, the first in the box order. Lock line `top exp 0378 | second-title baseline, scripted route RT on, ~10 min | …`
in `~/bc5-work/BOX-LOCK` (cleared by the script at the end), claim and done lines in `~/bc5-work/BOX-QUEUE` and
`~/bc5-work/exp0378/CLAIM.txt`. The kernel log was streamed to the laptop for the whole run
(`raw/B1-kernel-stream.txt`). After the run, the B1 journal was read (targeted greps only), and then the done line
was written.

**Question.** F524 (ASTRO BOT) says that the F403 class's CP pointers (PFP 0xea0–0xea1, ME 0x779–0x77b) are also
where healthy frames wait. F526 separated the hang from those healthy waits by "no EOP in flight, EA/RMI idle". Exp
0377 added the `COMPUTE_*` registers (F530, F531). On the title that actually hangs, with RT on:

1. How often do healthy frames sit at those pointers? What do their status registers read, compared with the 09:48
   F403 capture (F525/F526)? Can a single sample tell "parked in the healthy wait" from "the F403 hang"?
2. Which `COMPUTE_*` programs and grids show up on `gfx_0.0.0`? Can they be matched to the host journal's dispatch
   list, as F528/F529 plan for a hang?

## Setup

- **Build and launcher.**
  - Shared normal build `~/bc5-work/kytyplus-build/src/kyty_emulator`, md5 58c4a627 (F504), as installed.
  - `play-pkg.sh` md5 55531ab6, read but unchanged. The run used a private copy, `exp0378/play-pkg-0378.sh`
    (`raw/play-pkg-0378.diff`). It has 4 lines changed (own log, own working directory, own save directory, own copy
    of the learned file) and 1 line added (the RT-on input configuration hook), as in exps 0350–0372.
  - Kernel 7.2.9-ogc3.1, boot c2c3162a (`raw/B1-box-settings.txt`, `raw/B1-start.txt`).
- **Route.** The S6N route, exactly as `s6n0372.sh`:
  - exp 0196's route save copy (`saves-before-152617`) in the private wd;
  - `exp0203/o2-continue.cmd` (✕ at 85 s, down, down, ✕, ✕);
  - RT on: the input configuration carries `RayTracing.PPSA03671=on`, and no RT-off drop line appeared by 180 s.
  - The script is `s6n0378.sh`, made from `s6n0372.sh` by `mk-s6n0378.pl` (literal edits; `bash -n` and a dry run
    of the request schedule passed on the laptop).
- **Live saves.** Read 1e451f8fefd534f3 before and after, and compared only (`raw/s6n-saves.txt`). They were never
  written: the route loads its own copy.
- **Sampler.** The installed stall sampler, `/usr/local/sbin/bc5-gpu-stall-sampler`: `VERSION = "0377"`, sha256
  ff65042a…, registers only, `wave_scan=off`, installed by the maintainer at 10:34.
  - The script checked the version and the service before starting.
  - It wrote `once` into `~/bc5-data/captures/gpu-stall/force` 40 times, ≥ 5 s apart: 20 at run t 183–278 s
    (10:46:33–10:48:09) and 20 at t 450–545 s (10:51:00–10:52:36) (`raw/B1-forced-times.txt`).
  - It never wrote a wave request (F520).
  - Each request was written only after that loop pass's kernel check, so a hang would have stopped further requests.
- **What was copied.** `regs-1.txt` and `summary.txt` of the 40 sampler directories (`raw/B1-samples/`): register
  values and the decoded dispatch only, no dumps. Also the sampler's log lines for the run (`raw/B1-stalls-log.txt`)
  and the run's summary files. The play log, the journal and everything under `~/bc5-data` stay on the box.
  - Journal: `~/bc5-data/captures/play-20261029-1043/gc/direct.log`, 200 MB. Only its program-naming lines were
    counted (`raw/B1-journal-programs.txt`).
- **Analysis.** `ana0378.py` (laptop, Python 3.14.0, `-I`) decodes fields from Linux v7.2 `gc_10_1_0_sh_mask.h`
  (blob 9b7d219e…, the same as `decode0376.py`; fetched from git.kernel.org `/plain/…?h=v7.2`). It compares the 40
  samples with:
  - exp 0376's five hang samples (`../0376-f403-first-live-capture/raw/sampler-event/`);
  - the seven class devcoredumps (`../0376-…/raw/class-dumps-cp-regs.txt`). That extract lists `GRBM_STATUS2`
    twice; the script keeps the first value, which is F525's.

  Output: `raw/ana.txt`. Command:
  `python -I ana0378.py <dir>/gc_10_1_0_sh_mask.h raw/B1-samples ../0376-f403-first-live-capture/raw`.

## Result

### The run

**B1 passed** (`raw/B1-summary.txt`, `raw/B1-verdict.txt`):

- 600 s, launcher exit 0; 22,571 flips in 596.5 s (37.8 flips/s); ~41 flips/s from journal t 150 s to the end
  (`raw/B1-flips-per-10s.txt`), so both sample blocks fall in the running scene.
- 0 crash lines, 0 kernel amdgpu lines (the stream holds only IPv6 MLD notices), 0 TIMEOUT lines, 0 devcoredumps.
- The live saves were unchanged; the package mount was gone afterwards (`mountpoint` inside the `ubuntu` container);
  no emulator or launcher was left.
- **The sampler under RT-on load.** All 40 forced samples read 50 registers with 0 errors, in 0.2 ms (33), 0.3 ms
  (6) and 0.8 ms (1). Every sample had `gfx_0.0.0` pending. `GRBM_GFX_CNTL` read 0 before and after the
  `COMPUTE_*` block in all 40, so no select was in place.

### Q1 — F524 on the second title

**12 of 40 samples sat at PFP 0xea0–0xea1 with ME 0x779–0x77b** (7 at 0xea1/0x77b, 3 at 0xea0/0x77b, 1 at
0xea1/0x77a, 1 at 0xea0/0x779). Five more had ME 0x779/0x77b with PFP 0xe9f. The other common pair was PFP
0x172e / ME 0xe19 (6 samples). That pair is the idle box's pair too (the 10:35 idle read): GRBM 0x00003028 and
`CP_STAT` 0 with the fence still pending, so the CP is idle between submissions.

**The status registers of those parked samples include the hang's own values** (`raw/ana.txt`; hang = F525's
five samples):

| register | hang (09:48) | parked healthy (12) |
|---|---|---|
| `GRBM_STATUS` | 0xa0407028 | 0xa0407028 ×6, 0xa0406028, 0xa0003028, 0xa0002028, 0xa5f16028, 0xe5f16028, 0xe5504028 |
| `GRBM_STATUS2` | 0x52000008 | 0x52110008 ×5, 0x52118008 ×2, 0x52100008, 0x51100008, 0x50100008, 0x52130008, 0x52138008 |
| `GRBM_STATUS_SE0/SE1` | 0x0a000036 | 0x0a000036 (SE0 ×4, SE1 ×5), 0x0a000016, 0x0a000034, 0xee60003c, … |
| `CP_STALLED_STAT1` | 0xc00 | 0xc00 ×12 |
| `CP_STALLED_STAT2` | 0x18000 | 0x18000 ×5, 0x218000 ×4, 0x210000, 0 ×2 |
| `CP_STALLED_STAT3` | 0x800 | 0x800 ×10, 0 ×2 |
| `CP_BUSY_STAT` | 0x400400 | 0x400400 ×5, 0x448400 ×2, 0x40400, 0x440400, 0x42c500, 0x468400, 0x400 |
| `CP_STAT` | 0x9403a600 / 0x9503a600 | 0x9403a600 ×2, 0x9503a600 ×2, 0x94078600 ×2, … |

- **One healthy sample, 10:47:29, matches the hang in every status register the sampler reads except one bit.**
  Its values: PFP 0xea0, ME 0x779, `GRBM_STATUS` 0xa0407028, SE0 0x0a000016 (F490's value), SE1 0x0a000036,
  `CP_STALLED_STAT1/2/3` 0xc00/0x18000/0x800, `CP_BUSY_STAT` 0x400400, `CP_STAT` 0x9403a600.
  - Its `GRBM_STATUS2` is 0x52100008. The hang's is 0x52000008. They differ only in bit 20, `EA_LINK_BUSY`
    (`gc_10_1_0_sh_mask.h:5550, 5577`).
- **Three more samples (10:46:59, 10:47:54, 10:47:59) equal the hang in `GRBM_STATUS`, SE0/SE1,
  `CP_STALLED_STAT1–3`, `CP_BUSY_STAT` and `CP_STAT`, and differ only in `GRBM_STATUS2`.** They read 0x52110008
  (`EA_BUSY` and `EA_LINK_BUSY` set), or 0x52118008 at 10:47:59 (`UTCL2_BUSY` as well). A fourth, 10:51:05, has the
  same `GRBM_STATUS`, SE0/SE1 and `GRBM_STATUS2` 0x52110008, but other CP values (`CP_STALLED_STAT2` 0x210000,
  `CP_BUSY_STAT` 0x40400, `CP_STAT` 0x80058600).
- **So on the second title, F526's separators are not specific to the hang.**
  - "No EOP in flight": `EOP_DONE_BUSY` was clear in 7 of the 12 parked samples.
  - "EA idle": `EA_BUSY` was clear in 3 of the 12.
  - `CB_CLEAN`, `DB_CLEAN`, `GE_BUSY` clear (the hang's graphics-idle state) held in 7 of the 12.
  - The hang's `GRBM_STATUS` and SE values (F524's "told apart by") occur in healthy frames as well.
  - **The F403 state is a healthy wait state that does not end.** That fits F525's reading: a microcode wait loop
    on `ME_WAITING_ON_PARTIAL_FLUSH`.
- **Single-sample rules** (fires = "looks like the hang"; `raw/ana.txt`):

  | rule | healthy, 40 | parked healthy, 12 | hang samples, 5 | class dumps, 7 |
  |---|---|---|---|---|
  | C: `CP_STALLED_STAT2.ME_WAITING_ON_PARTIAL_FLUSH` | 17 | 9 | 5 | 7 |
  | C + `EA_BUSY` clear + `EOP_DONE_BUSY` clear | 2 | 2 | 5 | 7 |
  | … + `CB_CLEAN`, `DB_CLEAN`, `GE_BUSY` clear | 1 | 1 | 5 | 7 |
  | E: `GRBM_STATUS2.EA_LINK_BUSY` clear | 5 (the CP-idle samples) | 0 | 5 | 7 |
  | **C and E** | **0** | **0** | **5** | **7** |

  Every one of the 7 class dumps has `GRBM_STATUS2` 0x52000008 or 0x50000008 (10-27 07:28), with `EA_LINK_BUSY`
  clear. All 12 parked healthy samples have it set, and so do all nine of exp 0375's ASTRO BOT samples at the
  pointers (0x52130008, F526). **`ME_WAITING_ON_PARTIAL_FLUSH` with `EA_LINK_BUSY` clear separates them in one
  sample on this data.**
  - The data is small: 40 healthy samples of one run, and 12 hang records from 7 events.
  - What `EA_LINK_BUSY` means (the EA's link to the data fabric, presumably), and why a healthy partial-flush wait
    always shows it, is TODO(verify).
- **Proposed early-warning rule (design only; nothing installed or changed).**
  - **When.** Only while a ring's fence is pending and unchanged for ≥ 100 ms. The sampler already tracks fence age
    at its 25-ms poll, and a frame here takes 26 ms (`raw/B1-0358.txt`).
  - **What.** Read two registers per poll, `CP_STALLED_STAT2` and `GRBM_STATUS2`: 2 unhalted reads of the kind
    F523 and this run found safe.
  - **Rule.** Flag `f403-early` when `ME_WAITING_ON_PARTIAL_FLUSH` (bit 15) is set and `EA_LINK_BUSY` (bit 20) is
    clear on 3 consecutive polls with the same fence. Write one line to `stalls.log` with the time and the
    `COMPUTE_*` block.
  - **Effect.** The flag comes at ~150 ms instead of 0.5 s. That leaves the five samples, the event and the
    2-s kernel timeout unchanged, but gives the host (or a later sampler) ~1.8 s of warning.
  - **Before it is built.**
    - A healthy-frame run of the rule's register pair at the poll rate. Forced samples are random in time; a
      polled watch would show whether a healthy wait ever holds C+E for 50 ms.
    - The `EA_LINK_BUSY` TODO above.
    - The maintainer's yes to install.

### Q2 — the healthy `COMPUTE_*` values on `gfx_0.0.0`

**The `COMPUTE_*` registers read back on gfx1013 under load, and they follow the title's dispatches.** That settles
F531's first TODO(verify) (readback) for the gfx ME. 21 distinct program addresses appeared in 40 samples
(`raw/ana.txt`, the compute table):

- **17 in the title's `0x11d0…` code window.** The most frequent were:
  - 0x11d0288800, grid [61440 1 1] × 64 threads, 4 samples, at PFP 0x614/0x63a/0x172e;
  - 0x11d023c300, ~[40550–40578 1 1] × 32, 3 samples;
  - 0x11d0374f00, [36291] / [35194] / [119] × 32, 3 samples;
  - 0x11d03a2000, [46] / [19] / [3] × 64, 3 samples.

  The parked samples' programs were 0x11d0322b00 [104 59 1] 8×8, 0x11d04f2500 [62], 0x11d03f6100 [208 117 1] 8×8,
  0x11d03f7900 [320 180 1] 8×8, 0x11d0349300 [1076] 8×4, 0x11d0507100 [5354] 8×8, 0x11d03a2000 [46],
  0x11d036b400 [104 59 1], 0x11d021a400 [1] 16×4, 0x909936c00 [16], and program 0 with [1792] twice.
- **2 in the `0x0909…` window** (F250's BVH family): 0x909939900, grids 528, 48 and 56, and 0x909936c00. Both have
  initiator 0x61 (`USE_THREAD_DIMENSIONS`).
- **1 from another client**, 0x800000003900 [320 180 1], initiator 0x2045 (`TUNNEL_ENABLE`). `COMPUTE_PGM_HI` 0x80
  is the high byte F253 attributes to Mesa. The idle box at 10:35 read 0x800000000400.
- **Program 0 with a non-zero grid in 9 samples** ([1792 1 1] ×3, [4 32 4] ×2, [8654], [32], [2397], [320 180 1],
  …). What a zero `COMPUTE_PGM_LO/HI` with a live grid means is TODO(verify). Possibilities are a program set in a
  way that does not pass through these registers, or a dispatch whose state the CP had not loaded at the read.
- **The initiator agrees with the thread counts.** Every 0x8041 sample (`CS_W32_EN`, bit 15,
  `gc_10_1_0_sh_mask.h:17070`) has 32-thread groups ([32 1 1] or [8 4 1]). The 0x41 samples have 64-thread groups,
  except 0x11d0287900's [8 1 1]. The registers therefore read one dispatch's coherent state.
- **F527's three candidates were never sampled** (0x11d028dd00, 0x11d02a1600, 0x11d02a1800), nor F506/F528's
  0x11d028ae00. 40 random samples are too few for the absence to mean anything.

**The normal play journal has no dispatch list, so a healthy sample cannot be matched against it.**

- The 200-MB journal of B1 names program addresses only in 37 lines (`raw/B1-journal-programs.txt`): `cs prefix`
  lines (11 programs, 10 of them 0x0909…) and `flat aperture` lines (5 programs).
- Of the 19 title programs sampled, one is among them: 0x11d0287900, a `cs prefix` program, sampled with grid
  [1 1 1].
- The journal's main lines are `timing`, `acb rest`, `frame profile`, `flip label`, `wait detail` and the like. None
  of them carries a dispatch's program.
- **For a hang, F528's path stands.** The timeout probe's `ib-timeout-*-dcb-*.bin` holds the stuck buffer. Its
  `SET_SH_REG` writes to `COMPUTE_PGM_LO/HI` (and the indirect dispatches' arguments) can be walked as
  `walk0376.sh` did, and matched to the sampler's `pgm=`.
- **A healthy-frame match needs a dispatch journal**, which the normal launcher does not enable. F149's run used
  `BC5_DIRECT_DRAW_JOURNAL`; it is not in `play-pkg.sh` and was not turned on here, since the launcher stays
  unchanged.

## Verdict

**Baseline recorded; the sampler is safe under the RT-on second title.**

- **Q1.** The F403 pointers are a common healthy wait on the second title too (12/40). Healthy frames there reach
  the hang's status values: one sample matched in every status register but `EA_LINK_BUSY`. So the class is not
  told apart by `GRBM_STATUS`, SE0/SE1 or the EOP/EA bits (F524, F526 refined).
- **The single-sample test.** `ME_WAITING_ON_PARTIAL_FLUSH` set with `EA_LINK_BUSY` clear held in 0/40 healthy
  samples and in 12/12 hang records. Proposed as a sampler early-warning rule (design above, nothing installed);
  its bit's meaning and a polled healthy check come first.
- **Q2.** The `COMPUTE_*` registers name the gfx ring's programs and grids under load. The normal journal cannot be
  matched against them: it has no dispatch list. For a hang, the probe's dcb walk (F528) is the match.

No GPU hang, so no sampler event to keep. Not touched: the shared builds, `play-pkg.sh`, patch 0001, the
sampler.

## Findings (for HANDOFF)

- **F533** — The registers-only stall sampler 0377 is safe under the RT-on second title: 40 forced samples, 0 errors,
  B1 passed. Experiment 0378. High for one run.
- **F534** — F524 on the second title: 12/40 parked. Healthy parked frames reach the hang's status values, so F524's
  and F526's separators are not hang-specific there. Experiment 0378 (`raw/ana.txt`). High for the values.
- **F535** — The single-sample separator (C and E), with the early-warning design. Experiment 0378. Medium: small
  sample; the bit's meaning is TODO(verify).
- **F536** — The `COMPUTE_*` registers read back under load and follow the title's dispatches. 21 programs were seen;
  9 samples had program 0; F527's candidates were not seen. Experiment 0378. High for the readback.
- **F537** — The normal play journal has no dispatch list: only 16 programs in 37 lines, and 1 of 19 sampled
  programs matched. A hang matches through the probe's dcb walk; a healthy match needs a dispatch journal.
  Experiment 0378 (`raw/B1-journal-programs.txt`). High.
