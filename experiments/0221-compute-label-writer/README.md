# 0221 — who writes the compute queue's label that the given-up waits depend on

**Question.** Exp 0219 (F279) found the chain behind the given-up game-thread waits:
- At the give-up the GPU has nothing of ours in flight.
- The waited label B is then written by a compute buffer near its end.
- That buffer is submitted only later, because it is held back on its own wait for a compute-side
  label C, which no tracked job writes.

Two things were left open:
1. Is B among the labels the held-back compute buffer writes past its wait (`g_unready_writes`)? If
   so, the host knows the writer at the give-up, and a dynamic rule can key on it.
2. Who writes C: the title's CPU code, the host (for example the soft CP's CPU-side label writes), or
   a GPU job? If it is a write by the waiting buffer, the chain is a real cycle and the give-up is
   right.

**Setup.**
- Diagnostic: `patch_0221.diff`, produced by `patch0221.py` from the shared tree's `bc5LleAgc.cpp`
  (md5 b210fa8e…, unchanged since exp 0219). It is exp 0219's journal-only flip trace
  (`BC5_DIRECT_FLIP_TRACE=1`, off by default) plus:
  - At each give-up, the compute queue's state:
    - `g_unready_label` (C, the label its held-back buffer waits on) and C's value;
    - whether B is among the labels that buffer writes past its wait (`g_unready_writes`, from its
      WRITE_DATA / RELEASE_MEM / 0x47 / 0x1e packets);
    - whether C is among the labels the waiting graphics buffer writes (its `written` list, which run
      123's cycle break uses).
  - The watcher thread `bc5-flipw` follows C as well, and journals C's changes with the jobs in flight.
  - `BC5_DIRECT_FLIP_TRACE_WP=1` adds hardware write breakpoints:
    - `perf_event_open`, `PERF_TYPE_BREAKPOINT`, `HW_BREAKPOINT_W`, 8 bytes, user space only, counting
      only: no samples, no signal, no single step;
    - on B and C, in every thread of the emulator's own process (`/proc/self/task`);
    - armed by the watcher right after a give-up, one give-up at a time, and closed when it ends;
    - read whenever B or C changes, and at the end. A CPU write shows as a count on the writing thread,
      named from `/proc/self/task/<tid>/comm`, and marked if it is the thread that gave up. A change
      with no count after arming is a write from outside the CPU: the GPU.
    - The breakpoints are armed only for the few ms around a give-up. Their cost is checked against
      tcpW5 by frame times; if they slowed frames noticeably they would be recorded and dropped.
  - `wptest0221.cpp` first checks, in the ubuntu distrobox where the emulator runs, that such
    breakpoints work there (one process, three threads, known writes).
- Build: `build0221.py`, as exp 0219's. The shared tree, binaries and objects are not written.
- Run: `run0221.sh wptest|build|bench|extract`, each step started by hand on the box supervisor's Go.
  The bench step is `bench0201.sh tcpW6 600` with that binary, `BC5_DIRECT_WAIT_TRACE=1`,
  `BC5_DIRECT_FLIP_TRACE=1`, `BC5_DIRECT_FLIP_TRACE_WP=1` and the default 8-ms limit.
  - It keeps the old launcher values, as tcpW1–W5 had them: `BC5_DIRECT_FLAT_APERTURE=0` and the old
    skip list are pinned in ENVX. `BC5_DIRECT_AMM_PRT` is unset, because the bench goes through
    exp 0194's `play-pkg-0194.sh`, which never sets it. The emulator's environment 60 s in is kept
    in `raw/`.
- Risk: the bench submits to `amdgpu` as every play does, and a GPU hang can take the machine down
  (F262). The run is attended. The diagnostic submits nothing.
- Analysis: `ana0221.py` (per give-up: the compute queue's state, B's and C's changes, the writers),
  and exp 0219's `ana0219.py` for the flip-versus-completion measures.
- A breakpoint armed during a watch counts a flip only if the label still held its give-up value when
  the arming ended. The watcher does not poll while it arms (5–18 ms for ~95 threads), so a flip
  during arming is seen late and is not covered.
- Step 2, v3 (`patch0221b.py` → `patch_0221b.diff`, `build0221b.py`, `run0221.sh` with `V=v3`,
  `ana0221b.py`). Run 1 showed that `g_unready_label` cannot find C, so v3 changes three things:
  - a hook in `acb_ready()`'s not-ready branch records each compute label found unsatisfied, with its
    time;
  - at a give-up, the watcher follows every compute label recorded in the 50 ms before;
  - the breakpoints go on a fixed list instead (`BC5_DIRECT_FLIP_TRACE_WP_LABELS`): 0x12004b37c8,
    0x12004b53c8, 0x12004b4fc8 and 0x12004b77c8, the four compute labels held back most often in
    tcpW5/W6. They are armed at the first give-up and kept.
  - It was linked after exp 0222 put patch_0216 (the APR readers' condition-variable wait) into the
    shared build; `raw/v3-linked-objects.txt` lists the objects.

**Result.**

*Self-test.* In the ubuntu distrobox, counting write breakpoints work: armed on 3 threads × 2 words in
5.3 ms, with exactly the expected counts on the right threads (`raw/wptest.out`). Arming one per thread
for ~90 threads takes 5–8 ms, most of it in a single call of ~4 ms.

*Run 1, tcpW6 (v2), 2026-10-22 21:59–22:09.*
- The full 600 s ran: 0 fault lines, 0 ring timeout or reset lines, 0 fence timeouts, boot
  unchanged, no new amdgpu line. The environment 60 s in had the pinned values and `AMM_PRT` absent
  (`raw/tcpW6-environ.txt`).
- 13 waits were given up, as in tcpW5. All 13 labels went 0x907616589 → 0, 2.1–46.6 ms after the
  give-up (median 14.9). The labels were 0x12004b3c38 (6), 0x12004b5438 (4) and 0x12004b4838 (3).
  Give-up #4 had waited 604 ms before it gave up, during the load.
- Jobs in flight at the give-up: 0 on both queues at 12 of 13; one had cq0 6, cq1 18. That is
  exp 0219's finding again (`raw/tcpW6-ana0219.txt`).
- **B is written by the GPU.** At 11 of the 13 flips the breakpoints were armed before the flip,
  and no thread's count rose at it. The other two (#1, #5) flipped while the watcher was still arming
  (17.8 and 8.5 ms), so they are not covered.
- **The thread that gave up writes B from the CPU between give-ups.** That thread is the title's
  "Render Thread", which runs our wait. It made 15,555 writes in all, 296–8,454 between one give-up and
  the next: about two a frame, presumably setting B back to 0x907616589 before the work that clears
  it. No other thread wrote B.
- **`g_unready_label` was 0 at all 13 give-ups.** It is one global: `acb_ready()` sets it when a
  compute buffer has an unsatisfied wait and resets it to 0 whenever a buffer is ready. The doorbell
  consumer calls `acb_ready()` for every queue's pending buffers, so the value is the last buffer
  checked, not whether a queue is held back.
  - Yet the wait trace shows a compute buffer held back 10–14 ms before each traced 0x12004b5438
    give-up (acb 319 on 0x12004b53c8 = B − 0x70). Before the two traced 0x12004b3c38 give-ups the
    last compute label held back was 0x12004b37c8 (B − 0x470), 10–13 ms before.
  - So run 1 never watched C.
  - Run 123's cycle break and exp 0055's `BC5_DIRECT_DCB_WAIT_UNBLOCKED_MS` read the same global.
    Both may see "not blocked" when a queue is blocked, and a stale label when it is not.
- Served game-thread waits of 4 ms or more: 7.
- Cost of the breakpoints: none seen. In the frozen view (t 150–590 s) tcpW6 ran 28.8 flips/s, with
  17 seconds that had a gap over 100 ms. tcpW5 (no breakpoints) ran 26.0 and 139, tcpW4 26.0 and 84.
  The runs differ more among themselves than any cost could show; the bench's water "patch share"
  also differed: ~1.6 % in tcpW6 against ~20 % in tcpW5.

*Run 2, tcpW7 (v3), 2026-10-22 22:21: failed at 88 s, through two mistakes of this session.*
- The binary was named `kyty_emulator-v3`. Linux cuts the process name to 15 characters, so it ran
  as `kyty_emulator-v` and `pgrep -x kyty_emulator` in bench0201/run-0194b never found it. The
  runner ended its loop at once, and the bench's remover dropped the BOX-LOCK about a minute in.
- A stopper started on the box to end the run at 600 s took its start time from parsing `ps`
  output. In the box's Polish locale the date did not parse, and the stopper sent TERM at 22:22:41
  (`raw/tcpW7-stop.log`), during the load.
- No GPU-side effect: no fault, no new amdgpu line, same boot.
- The fix for a rerun: keep the file name `kyty_emulator` (for example `~/bc5-work/exp0221/v3/
  kyty_emulator`), so that the bench's own lock and stop logic work and no stopper is needed.
- What the 88 s did record (journal t 0–88 s, the load; `raw/tcpW7-ana0221b.txt`): 4 give-ups, three on
  0x12004b4838 at t 7–13 s and one on 0x12004b5438 at t 61 s.
  - The breakpoints on the four fixed compute labels were armed at the first give-up: 91 threads each,
    in 0.5–17 ms, none failed.
  - **The compute labels were already satisfied at every give-up.** Each give-up had 1–4 compute labels
    held back 8–28 ms before, and all of them held 0 when the wait gave up. So the compute buffers had
    been released, but their work had not run yet.
  - **Compute label 0x12004b37c8 is armed by the CPU and released by the GPU.** After give-up #1 the
    Render Thread (the thread that gave up) wrote it 0 → 0x9076d6d8c (CPU write counted). 5.1 ms later
    it went 0x9076d6d8c → 0 with no CPU write counted: a GPU write. The breakpoints had been armed
    with the value still 0, so this change is covered. That is one covered release.
  - Between watches, the Render Thread wrote all four compute labels about once a frame:
    1,161–1,179 writes in the 48 s between #3 and #4, and 615 for 0x12004b77c8. The host thread
    `bc5-cq0`, the game thread's completion thread, wrote 0x12004b37c8 once; that write is not
    explained here.
- The consumer (`consumer0221.py` on tcpW5–W7): the doorbell consumer's CPU waits on compute buffers
  end in bursts, every ~10–30 ms. B's flip came within 1.1 ms after the end of such a burst at 6 of 13
  give-ups in tcpW5 and 4 of 13 in tcpW6. By chance that would be about 1 in 10–15. In tcpW5 #7 the
  held-back buffer's wait was served at 100.370 s, before the give-up, yet it was submitted only at
  ~100.3925 s, as a burst of consumer waits ended.

**Verdict.**
- **The given-up label's writer is the GPU** (11 of 11 covered flips). Its only CPU writer is the
  thread that waits, which re-arms it between frames. That confirms exp 0219: the label is the
  completion signal of GPU work that has not run yet when the wait gives up.
- **`g_unready_label` is not a usable signal**, for a dynamic rule or for the existing cycle-break
  and `DCB_WAIT_UNBLOCKED` logic. It is shared by all compute queues and overwritten by every
  `acb_ready()` call. A rule keyed on a blocked compute queue needs per-queue state.
  - v3's held-back table, the compute labels found unsatisfied with their times, is one way to get it.
  - Another is to keep each queue's first unready buffer: `t_unready` per queue rather than per thread.
- **This corrects exp 0219's chain.** Exp 0219 had the compute buffer still held back at the give-up.
  In tcpW7 its compute label was already satisfied at all 4 give-ups, and in tcpW5 #7 the wait was
  served before the give-up. The compute buffer was ready but not yet submitted.
  - The one covered release of a compute label was a GPU write, and the CPU only re-arms it (the Render
    Thread, once a frame). So nothing in the chain waits on the title's CPU code: both labels are
    "the CPU arms, the GPU signals".
  - The likely delay is on the host. The doorbell consumer does its CPU waits on compute buffers one
    after another, and a released buffer goes to the GPU only when that pass reaches it. About half the
    flips follow the end of such a pass within ~1 ms.
- **For the rule:** the waited label's writer is a compute buffer that is ready but still on the
  consumer's side. What a dynamic rule could key on is "the doorbell consumer has compute buffers
  pending", per queue, rather than `g_unready_label`. The better fix may be in the consumer itself:
  submit a queue's ready buffers while another queue's CPU wait is still on.
- **Shown here only in part:** a single covered compute-label release (tcpW7 ran 88 s), and timing
  that is suggestive for the consumer. A full v3 rerun, with the binary named `kyty_emulator` and a
  journal line when the consumer takes each doorbell entry, would show both directly.
- Until then the bounded 100-ms limit stays the safe choice. All 13 give-ups of tcpW6 were satisfied
  within 55 ms of the start of their wait, except #4, which had waited 604 ms during the load.
