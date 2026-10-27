# 0341 — the RT-on arms 1, 2 and 4 of exp 0340 in one private build, each behind its own switch

**Question.** Exp 0340 (F413) named the two RT-on machine-down classes left on one ring: a runaway
`DISPATCH_INDIRECT` whose argument triple passes the CP check's per-dimension limits (F403, devcd1 of 10-27: 818 ×
820 × 819 groups, then a TCP read fault), and a stray store over a sync label the CP waits on (F360/F406, devcd8).
Its design's arms 1, 2 and 4 are built here, offline, in the backend alone (the emulator's objects stay the shared
normal build's 9382b1e9; only `libbc5_backend.a` changes), each default off behind a switch, so that the test can
turn them on one at a time: does the private build pass the backend's unit tests, build, and run the RT-off S6N route
600 s on one ring with all three on — and then, on the maintainer's yes, his RT-on play?

**Setup — the backend (`backend/`, GPL-2.0, on this branch).**

| arm | switch (environment, read by `Device::open` until the host's option parsing carries it; the `FilterOptions` / `OpenOptions` fields exist) | what it does |
|---|---|---|
| 1 | `BC5_DIRECT_GPU_CHECK_PRODUCT=1` (or `x_limit[:yz_min]`, default 65536:1); needs the CP check (`BC5_DIRECT_GPU_CHECK`) | `indirect_check::ProductLimit`: after the three per-dimension `COND_WRITE`s, a second flag word is set when y > yz_min or z > yz_min (two `COND_WRITE`s), confirmed and synced to the PFP, and a `COND_EXEC` on it runs one more `COND_WRITE`, x > x_limit → the dispatch's flag 0. The CP cannot multiply; the staircase refuses every grid that is not one-dimensional and has more than 2^16 groups along x (F403's triples), and passes a 1-D builder of 2^20. 44 dwords more per checked dispatch, two `PFP_SYNC_ME`s instead of one. GFX form only. `FilterStats::product_checks`. |
| 1 | `BC5_DIRECT_ARGS_HISTOGRAM=1` | `Device::submit` reads the three counts of every GFX-form `DISPATCH_INDIRECT` with a known base at filter time (through `mapped`; stale for arguments the GPU writes later — a histogram, not a verdict), bins them by log2 class, and prints on stderr every 500,000 dispatches and at close: the classes, how many the staircase would refuse, how many the per-dimension limits would. `FilterStats::args_sampled`. |
| 2 | `BC5_DIRECT_SHADOW_LABELS=1` | `bc5/shadow_labels.hpp` (new unit): on the main IB of a GFX-ring job, every label the IB both writes (`RELEASE_MEM` with a value, `WRITE_DATA` to memory) and waits on (`WAIT_REG_MEM[64]`, memory space, after a writer) gets an 8-byte slot in the job's scratch after the flag area (64 slots a job, zeroed per job); each writer is followed by a copy writing the slot, each such wait polls the slot. The title's label is still written (its CPU polls it). The IB's own `COND_EXEC` counts grow around the copies (`insert_before`, which now also appends at the IB's end); an IB whose count would overflow is left alone and counted. `FilterStats::shadow_labels / shadow_writes / shadow_waits / shadow_overflow / shadow_failed`; a summary line at close. |
| 4 | `BC5_DIRECT_BO_JOURNAL=1` | `OpenOptions::bo_journal`: one stderr line (`bc5-direct: bo <what> va 0x… size 0x…`) for every mapping made or undone — userptr (and ro), shared (with id and offset), alias — and the device's own BOs (scratch slots, the snapshot ring, the code area), so a fault address (0xd5200001000, 0xa8256950000, 0xb20407c00000) can be placed. |

The backend prints its switch line once at open (`bc5-direct: experiment 0341 switches: …`). Unit tests (Catch2):
`tests/indirect_check_test.cpp` + the staircase's packet sequence, sizes and refs, a draw and the plain path
unchanged, an insert at the IB's end; `tests/shadow_labels_test.cpp` (new): a label written twice and waited on
(the copies, the redirected wait, `patch`), waits before their writer and register polls untouched, a second
label's slot, the slot limit, an IB without waits, the `COND_EXEC` growth. The host (bc5LleAgc.cpp) is untouched:
the switches reach the backend through the environment.

**Run.** `build0341.sh` on the box (the worktree's `backend/` copied beside it): a private archive and the tests
from `~/bc5-work/exp0341/backend` (cmake, clang, Release, `BC5_WITH_AMDGPU=ON`, `BC5_BUILD_TESTS=ON`, Catch2 from an
earlier test build's cache), the tests run, then the shared normal build's link command (ninja compdb) with the
private archive in place of `~/bc5-work/backend-ubuntu/libbc5_backend.a` → `~/bc5-work/exp0341/kyty_emulator`;
nothing shared is written. Then `s6n0341.sh <live saves> R1 600` (exp 0339's chain: RT off, one ring, the private
wd, the live saves compared only; `BC5_0341_SWITCHES` all four by default, checked in the emulator's environ):
pass = 600 s, no crash / kernel / TIMEOUT line, flips against 0339's 36.9–38.6/s, the histogram's classes and its
"would refuse" counts (expected 0 with RT off), the shadow summary (labels per job, nothing left alone), the bo
lines. The RT-on test is the maintainer's play on a test shortcut with the switches, after his yes.

**Result (2026-10-27, 08:49–09:08; GO: build, then one RT-off run).**
- *Build.* Four attempts on the box, all under -Werror with 0 warnings: (1) one test expectation of my own wrong —
  the shadow copy now goes right before its writer, inside the same `COND_EXEC` range, so a skipped writer skips its
  copy too (the copy after the range would have run unconditionally); (2) 60 test cases, 32,340 assertions passed,
  the emulator relinked (4fc189ad) — and the title crashed at 5 s (`runtimeLinker.cpp:1165`, a null read, `raw/R1-*`):
  the new fields in `FilterOptions` / `FilterStats` / `OpenOptions` had changed the structs the host's objects were
  compiled against; (3) the switches and their counts moved into the backend's `Device` (the headers now differ from
  main by comments only), archive 1a…/emulator **a1976905**; (4) a periodic shadow summary (a killed emulator never
  reaches the close summary), emulator **b052d860** = the tested binary. `raw/backend-tests.out`, `raw/binaries.txt`.
- *R2, the regression run* (a1976905; S6N, RT off, one ring, all four switches on, 600 s): **pass** — 0 crash /
  kernel / TIMEOUT lines, fdinfo `drm-engine-gfx` only, 0 `compute ring:` lines, the live saves 88374d489b09ac70
  unchanged; **36.6 flips/s** (median 387 per 10 s) against exp 0339's 36.9 and 38.6 on the same chain without the
  arms: within the run-to-run spread, at its lower end (two `PFP_SYNC_ME`s per checked dispatch, a `RELEASE_MEM` per
  sync more). `raw/R2-*`.
- *R3, 120 s on b052d860:* pass; the shadow summary every 2000 shadowed jobs (`raw/R3-0341-lines.txt`): **in 18,000
  jobs 127,606 labels, 255,212 writes copied, 127,606 waits redirected** — about 7 labels a job, each written twice
  (the `WRITE_DATA` 0 and the `RELEASE_MEM` 1 of F360's triple) and waited on once, exactly the shape the guard was
  built for; **16 labels without a slot** (one job in a thousand holds more than 64) and **0 IBs left alone**; the
  product staircase on 124,272 dispatches in 120 s.
- *The argument histogram* (`raw/R2-0341.txt`, 1,000,017 triples read at filter time in R2's first ~5 min): the
  legitimate classes are one-dimensional — x of 2^6…2^15 with y = z = 1 — and the stale reads show as `0.1.1`
  (205,116) and `2^31.2^31.2^31` (215,391: the host read the arguments before the GPU wrote them, as exp 0050 found);
  the staircase "would refuse" 239,806 of them and the per-dimension limits 267,357 — stale values, not verdicts: the CP
  decides on the final values, and the route ran as before. No class with y > 1 and x > 2^16 exists among the
  non-stale reads, so the staircase costs the RT-off work nothing and would catch F403's 818 × 820 × 819.
- *The bo journal* (R2: 62,491 lines): 37,010 shared maps, 316 scratch slots, the alias maps of the learned windows
  at 0xffff8011ce000000… (the kernel's sign-extended high half), the scratch at 0x100000000000 + 4 GiB per slot; no
  userptr maps on this title (every title mapping is a shared memfd one).

**Verdict.** The three arms build, pass the backend's tests and run the RT-off route on one ring 600 s without a
cost beyond the run-to-run spread: the shadow labels take over every end-of-pipe sync of the title (seven a job), the
staircase is in place on every checked dispatch, the mappings are journaled. The RT-on question — does F403's
runaway grid get refused, does F360's stray store no longer hang the CP — is the maintainer's play on a test
shortcut with the switches (`BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1`, the histogram and the bo
journal as he likes; one ring), after his yes. Follow-ups: 128 shadow slots (one job in a thousand overflows 64);
reading the flag words back after a job to count the CP's actual refusals; the switches into the host's option
parsing at integration (the headers' comments say so).

**The maintainer's RT-on play (2026-10-27, 10:37–11:23; his yes: "Tak, zagram na skrócie test 0341 z RT on").**
The "BC5 emulator (test 0341)" shortcut: b052d860, `play-pkg-0341t.sh` (play-pkg.sh plus a log per start,
`BC5_DIRECT_COMPUTE_RING=-1`, `BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1`, and
`KYTY_BC5_INPUT_CONFIG=~/bc5-work/exp0341/input-rton.cfg` exported after the settings loop), his own saves. He
played before the laptop streams were started and before pstore was installed (still `pstore_disable=Y`, no reboot
since 07:32), so what is known comes from the box afterwards: the three per-start logs
(`raw/maintainer-test/play-*.log.gz`), the two GPU journals on the box (`~/bc5-data/captures/play-20261027-1037`,
`-1101`, 379 and 428 MB; excerpts around the two stalls in `raw/maintainer-test/journal-*-stall-*.txt.gz`), the
kernel log of the boot.
- *Ray tracing was on.* A log's header lists `bc5-run.env` (with the shared `input.cfg`), not the environment the
  launcher exported; the switch itself prints only when the flip changes it (`ray tracing off at the flip`), and no
  log has that line, so the start state (on) and the private configuration (`RayTracing.PPSA03671=on`) agreed. The
  work shows it: the product staircase ran on **43,056,776 checked dispatches in 1,421 s** (first game) and
  **19,660,060 in ~1,310 s** (second), 30 k/s and 15 k/s, against R3's ~1 k/s with RT off: the BVH builders'
  indirect dispatches.
- *Three starts, two games, no machine-down.* 10:37:28 (1,421 s, exit 0), 11:01:47 (9 s, exit 0: a restart, no crash
  line), 11:01:58 (~1,315 s, exit 0). **No amdgpu line in the kernel log** (only IPv6 MLD notices and a DualSense
  reconnect at 10:59), no new devcoredump (the last is 07:28's devcd1), **0 `TIMEOUT` lines** in both journals; the
  cpu-wait give-ups of 16–59 ms are the usual ones. Before 0341 the second title's plays hung on the GFX ring with RT on (F332 at
  111–118 s on two rings, F404, F413's two machine-downs) and even with RT off (F399: three freezes on 10-26).
- *The guards' counts.* Shadow labels: 3,107,558 labels in 298,000 jobs (first game) and 3,199,803 in 304,000
  (second), ~10.5 a job (RT off: ~7), each written twice and waited on once; 119 and 131 labels found no slot, 0 IBs
  left alone. Whether the staircase actually refused a grid is not counted (the flag words are not read back).
- *Frame rate.* 31.7 and 39.1 flips/s on average over the fps counter's lines (RT off on one ring: 36.6–38.6).
- *Two long stalls, both recovered.* (1) First game, t 528→563 s (~10:46:16–10:46:51): **34.4 s without a flip with
  the game thread outside the host for 34.4 s** — the title's own CPU work (a load), GPU busy 29 ms. (2) Second game,
  t 864.9→886.9 s (~11:16:23–11:16:45), the freeze the maintainer saw: the dcb #1197600 (6,866 dwords, submitted at
  864.912 s) and the four GFX jobs after it **waited 22.0 s for their fences** (`fence 22007.37 ms`), the game thread
  stood at the flip for 22.04 s, the frame profile counts **soft-CP passes 22,009.5 ms in 469**, the audio went on
  (one trace line a second), and the journal wrote nothing else in those 22 s. With `lockup_timeout` at its 2,000 ms
  default on 7.2.9 (F316), a GPU job running 22 s would have timed out and been reset; no kernel line
  means the jobs were held before the hardware, on the host side (the soft CP or a dependency). Before 0341 none of
  the 13 GPU journals of 10-25…10-27 has a frame longer than 4.1 s. Which wait held them is open.
- *The language list.* He switched the system language to Polish in the F2 overlay (System tab, exp 0337; saved as
  `SystemLanguage=Polish` into the private `input-rton.cfg` at 11:03) and the list kept running up while he chose.
  The overlay feeds the left stick to ImGui as `AddKeyAnalogEvent(ImGuiKey_GamepadLStick*, down = |v| > 0.25,
  analog = |v|)`: the down state has a dead zone, the analog value does not, and ImGui's gamepad navigation scrolls
  the focused window by the left stick's analog magnitude every frame — any stick drift scrolls the list. The
  imgui_impl_sdl2 backend maps the axis through its dead zone first (value 0 below 8000/32767). To fix at
  integration.
- *Temperatures.* He saw lower GPU and CPU temperatures than in earlier sessions; nothing was sampled (11:28 idle:
  edge 52 °C, Tctl 54 °C). `sampleplay0341.sh` now also records `edge` and `Tctl` once a minute.
- The live saves are now **dc9d4f25fc2d41ca** (his play; 88374d489b09ac70 before).

**Verdict of the play.** RT on, one ring, the staircase and the shadow labels: 46 minutes in two games without a GPU
hang, a reset or a machine-down, for the first time with ray tracing on. One 22-s host-side stall that recovered by
itself is new with this configuration. Next: the integration into the shared builds (D19, the maintainer's yes),
with the overlay's dead zone; the 22-s hold read from the journal excerpt.

**The 22-s hold of 2026-10-27 11:16 (second game, t 864.9→886.9 s), read from the journal excerpt and the host's code
(laptop only; the bvh session, main 9650af6).** The five GFX jobs were not held by the GPU, by a fence, by the ring-order
dependencies or by the shadow labels: they were held in the host's completion queue of the game thread (`bc5-cq0`),
behind the soft CP's replays of the buffers submitted just before them, and the game thread stood in `drain()` at the
flip until that queue was empty.
- *What the numbers mean.* The timing line's `fence` is `now − queued_ns` (the completion thread, patch 0001
  `completion_thread`: `total_ms − j.cs_ms`), the time from the job's queueing to the moment its fence item was taken
  off the queue — not the time inside `amdgpu_cs_query_fence_status`, which is bounded by `BC5_DIRECT_FENCE_TIMEOUT_MS`
  (2,000 ms) and journals ` TIMEOUT` and wedges the device when it expires (`Device::finish`); no such line exists, so
  the five fence waits themselves took under 2 s each (in all likelihood microseconds). `GPU busy 22050.7 ms` is the
  union of the jobs' [queued, done) intervals (`frame_profile_done`), the same delay seen from the other side.
  `at the flip 22037.9` is `drain()` at the EOP flip: `play-pkg.sh` unsets `BC5_DIRECT_FLIP_DEFER` (exp 0171, F68) so the
  flip path calls `drain()`, which spins until `g_cq_items == 0` — every item of both completion queues, fences and
  posts alike. `soft-CP passes 22009.5 ms in 469` is `frame_profile_post`: the wall time of the post items run by
  `bc5-cq0` in that frame (only index 0 is counted), 469 of them; in the frames before, 73–750 posts took 0.1–1.2 ms
  in all.
- *The GPU had run the jobs at once.* On one ring (`COMPUTE_RING=-1`, `RING_DEPS=dcb` adds no dependency since
  `last_seq_comp` stays 0: `Device::submit`) the hardware runs jobs in submission order, and the ring thread's jobs
  #1197601–#1197622, submitted after #1197600 (and #1197621/#1197622 after #1197620), completed at 864.903–864.913 s
  with sub-ms fences. So #1197600's fence was signalled by ~864.91 s, and what the completion thread of the game thread
  did between taking #1197595's fence item (done 864.900 s) and #1197600's (886.909 s) is the hold: 22.0 s in the post
  items queued between the two, i.e. the soft-CP replays (`chain_post_soft_locked` / `soft_posts_end` → `post()`) of the
  game thread's buffers handed over around 864.80–864.90 s (its 7,332-dword DCB and the 40-dword wait buffers). Then
  41 ms of posts between #1197600 and #1197605, and nothing between the last three. The frame after shows
  `soft-CP passes 0.1 ms in 19` and a 36.6 ms sync; the fps counter goes from 13–15 flips/s before (gaps 70–264 ms,
  "7 flips in 1.817 s, longest gap 1067 ms" at 866.264 s) to 42 after: the title crossed a transition during the hold.
- *The one 2-s primitive a post can reach.* A post runs `SoftCp::submit` → `execute` over the title's own buffer with
  the chain's marks (`t_gpu_done`): packets the GPU executed are skipped for their memory side effects, the rest are
  executed by the host, and a `WAIT_REG_MEM[64]` on memory is **polled with a hard-coded 2,000,000,000 ns deadline**
  (`SoftCp::wait_reg_mem`), then given up. Of the host's 2-s bounds (the fence, `wait_idle`, the synchronous submit, the
  ring thread's `BC5_DIRECT_ACB_WAIT_MS`), it is the only one on a post's path; the hold tail's bound is 100 ms and the
  game thread's DCB waits 8 ms. **22,009.5 ms = 11 × 2,000 ms + 9.5 ms**, the 9.5 ms being what ~460 ordinary posts
  cost (0.02 ms each, as in the frames before). The alternative reading, 469 posts of ~47 ms each, has no 47-ms
  bound anywhere in the host and no writer that could satisfy a poll every 47 ms with nothing being submitted.
- *Why no line came.* The soft CP's timeout is an `LOGF_COLOR` line (`[bc5-cp] WAIT_REG_MEM on 0x… timed out`); the
  launchers run the emulator with `--printf-direction Silent`, so `Log::IsSilent()` is true and every `LOGF` of the
  session is dropped before it is formatted (the play log holds only `fprintf(stderr)` lines: `bc5-direct:`,
  `fps counter`, `audio trace`, and the ten `[bc5] stubbed import` lines). Its counter `g_waits_timed_out` is printed by
  another `LOGF`, and only when the journal is not `min`. `GIVEN UP` is the journal word for the game thread's CPU-served
  waits (`cpu-wait`, 8 ms) and the hold tail (100 ms): the game thread spent 0.0 ms in label waits in that frame
  (`label waits 0.0`, `inside the host 10.1 ms`), and with one ring the hold tail is never entered (`two_rings` needs
  `compute_ring_env() >= 0`), so neither could have written anything. No journal line exists for a soft-CP poll.
- *Which wait.* Not decidable from the excerpt (the journal has no line for it, and the box has no other record: the
  LOGF stream was never written). The replay polls only a wait **without a mark**: a memory wait in a game-thread DCB is
  either left to the GPU (its label written earlier in the IB; `executed_offsets_of` marks it executed) or served on the
  CPU and marked `{0}` (`set_gpu_executed(p, len, {0})`, every exit of the wait block), and graphics buffers carry no
  nested IBs (`piece check … nested 0`). So a polled wait means its mark did not reach the replay: the marks travel
  through the chain slot (`s.marks`, filled by `ChainInSubmit::~ChainInSubmit` and `chain_submit`, posted and cleared by
  `chain_post_soft_locked`), and `execute` treats an **empty** mark set as "nothing ran" and executes every packet
  (`done = !t_gpu_done.empty() && …`); a replay after a failed submission journals `replayed in full`, a replay with
  lost or empty marks journals nothing. Eleven polls fit one 7,332-dword DCB replayed without marks (its waits on labels
  the GPU had written are satisfied at once; the ones on labels of work the title submits after the flip are not, and
  with the game thread in `drain()` that work cannot come: each runs to the deadline). Why the title's sync pattern
  changed at that moment is its own (the transition); why the marks were missing is the bug to find.
- *The shadow labels cannot do this.* `executed_offsets_of` runs on `main_out` right after `policy::filter`, before the
  tracker, the CU tables, the staircase and the shadow pass (`Device::submit`), so the marks index the title's original
  buffer; the replay runs over that buffer, where the title's label is still written by the original writer (the copy is
  an extra packet before it) and the wait still names the title's label; the 131 labels without a slot keep their
  original GPU wait; the `COND_EXEC` growth is in the GPU's copy only. The soft CP never sees a slot. The product
  staircase could at most refuse a dispatch whose shader writes a label a later packet waits on — such waits are served
  on the CPU with the 8-ms give-up and journaled; none in the window.
- *What released it.* The eleventh deadline: with the last poll given up the replays finished, `bc5-cq0` reached the
  five fence items (long signalled), `drain()` saw the queues empty, the flip went at 886.950 s and the next frame was
  ordinary. Nothing else changed: no kernel line, no reset, the ring thread idle throughout (the title's queues were not
  fed because the title waits for the flip).
- *Exposure.* `drain()` also waits for `bc5-cq1`'s items (the ring thread's posts, with `BC5_DIRECT_RING_ASYNC=1`), so a
  compute buffer's replay waiting for the next frame's label would hold the flip the same way (run 110's shape); not
  seen here (index 1 is not profiled; nothing of the ring thread was queued after 864.913 s). Before 0341 the RT-on plays
  never reached a transition; the RT-off route has no such sync pattern (0 stalls in 0339's and 0341's 600 s).

**Proposal (host, patch 0001; no GPU change; the bvh session can write it).**
1. *Make it visible* (needed before any fix is judged): `SoftCp::wait_reg_mem` journals, through `Direct::journal`, every
   poll that lasts over 50 ms and every timeout (label, function, reference, value, the buffer's kind, pointer and
   offset, and whether `t_gpu_done` was empty), counts `soft-CP waits / timed out` in the frame profile, and
   `completion_thread` journals any post over 100 ms with the buffer it replayed. One line per event, nothing per frame.
2. *Bound the replay's wait.* The 2-s deadline is the standalone soft CP's (no GPU; ASTRO BOT, F20). In direct mode a
   replay runs after the job's fence: a label still unwritten then can only come from work the title has not submitted,
   and while `drain()` holds the game thread at the flip it never will. Give replays their own bound
   (`BC5_DIRECT_SOFT_WAIT_MS`, 8 ms like the DCB waits, the deadline kept for the ring thread's own inline pass, source 1),
   or do not poll at all in a replay whose marks are empty (the replay is then a full host execution of a buffer the GPU
   already ran). Either turns a 22-s hold into ≤ 88 ms. Also possible, more invasive: `drain()` at the flip waiting for
   `g_cq_fences == 0` instead of `g_cq_items == 0` (the flip needs the GPU done, not the bookkeeping) — it changes when
   the frame's EOP events fire relative to the flip, so not first.
3. *Find the missing marks* with 1's lines (which buffer, empty marks or a lost entry), then fix the bookkeeping.
Nothing from the box can add to this now: the window's journal lines are all in the excerpt, and the soft CP's lines
were never written. The next RT-on play with 1 in the build decides it.
