# 0219 — when the label of a given-up wait is written, against the GPU jobs

**Question.** The maintainer wants the game-thread wait limit to be dynamic. Exp 0215 (F274) showed the slow
label waits are not host stalls: the title keeps running at 2–3 cores while they last. So the rule has to
know the label's writer, which the host does not track (F263). Is it a job still on the GPU (a shader or
CP write), or the title's CPU code? If it is a job, the rule would be "keep waiting while GPU work is in
flight". If it is CPU code, the rule would be "keep waiting while the title runs".

**Setup.**
- Diagnostic: `patch_0219.diff`, produced by `patch0219.py` from the shared tree's `bc5LleAgc.cpp`
  (md5 b210fa8e…, of 2026-10-21 23:45). It is behind `BC5_DIRECT_FLIP_TRACE=1`, off by default, and only
  journals. Nothing waits longer and nothing more is submitted.
  - After a cpu-wait is given up, a thread of its own (`bc5-flipw`) reads the wait's label every ~50 µs,
    for up to 2 s. It journals each change of the value and the moment the wait would have been
    satisfied. With that it gives the jobs in flight on each completion queue (cq0: the game thread's
    jobs, cq1: the doorbell consumer's) and the last job completed by then.
  - While a label is watched, and for 20 ms after it flips, every job's completion is journaled too
    (CPU time at which the completion thread saw its fence).
  - A game-thread wait served after 4 ms or more gets the same summary at its end, and completions are
    journaled for 5 ms after it.
  - Reading: a label that a job writes flips while that job is in flight, just before its completion
    is seen. A label the title's CPU code writes can flip with no job in flight, and its next
    completion is no closer than at a random moment.
- Build: `build0219.py` (as exp 0216's build0216.py) compiles the patched file with the shared build's
  flags and links `~/bc5-work/exp0219/kyty_emulator` from the shared build's other objects. The shared
  tree, binaries and objects are not written.
- Run: `run0219.sh build|bench|extract`, each step started by hand. The bench step is the water
  session's `bench0201.sh tcpW5 600` (the private lake save copy) with that binary,
  `BC5_DIRECT_WAIT_TRACE=1`, `BC5_DIRECT_FLIP_TRACE=1` and the default 8-ms limit, so give-ups occur.
- Analysis: `ana0219.py` on the extract. For each flip it takes the jobs in flight and the first job
  completion after it. The baseline is the same measure at moments spread evenly (every 0.5 ms) over
  the stretches where completions were journaled.
  - `chain0219.py` lists the jobs done around each give-up, with the compute buffers held back just
    before it (wait-trace lines).
  - `sync0219.py` checks the windows against every `timing: #N done` line of the journal, which also
    covers jobs a thread finishes inline. A short read-only grep at 21:41 provided those lines.
- Risk: the bench submits to `amdgpu` as every play does. A GPU hang can take the machine down
  (F262), so the run was attended and started only on the supervisor's Go. The diagnostic itself
  submits nothing.
- When: tcpW5, 2026-10-22 21:22–21:32:49, on the box supervisor's Go after the maintainer's play.
  - It used the old `play-pkg.sh` (reflections off), so it compares with tcpW1–W4.
  - Build 21:21:55–21:22:21, rc 0. Its 4 warnings were already in the file, none in the patch.
  - The full 600 s ran, with 0 fault lines, 0 ring timeout or reset lines and 0 fence timeouts. The
    boot id was unchanged and no new amdgpu line appeared. The laptop's kernel stream showed only MLD
    lines.
- Committed: the scripts, `patch_0219.diff`, and `raw/` with the build output and the bench output.
  - Also in `raw/`: the 328 flip-trace, cpu-wait and wait-detail lines (`tcpW5-flip.txt`) and the
    outputs of the three analyses (`tcpW5-ana.txt`, `tcpW5-chain.txt`, `tcpW5-sync.txt`).
  - The 16-MB extract and the 516k timing lines stay in `~/bc5-work/exp0219/raw`.

**Result.** 13 waits were given up (tcpW4: 14), all on the game thread. All 13 labels were satisfied
later, between 0.63 and 27.96 ms after the give-up (median 11.8 ms). Counted from the start of the wait
that is 8.9–36.7 ms (median 21.6). In every case the value went from 0x907616589 to 0, and nothing
else changed in between. Four labels were involved: 0x12004b5438 (5 times), 0x12004b3c38 (4),
0x12004b4838 (3, all in the first 14 s) and 0x12004b4c38 (1).

| | give-ups (13) |
| --- | --- |
| Jobs in flight on both queues at the give-up | **0 in all 13** |
| Jobs done between the give-up and the flip | 0–3; every one was submitted after the give-up |
| Jobs a thread finished inline in those windows (`timing: #N` without a queue entry) | 0 |
| A compute buffer (acb) in flight at the flip, or done at most 0.6 ms before it | 13 of 13 |
| No graphics buffer (dcb) in flight or done between the give-up and the flip | 9 of 13 |

- **The GPU had nothing of ours to do when the wait gave up.** Every job number has its `timing: #N
  done` line (516,481 of them). No job, queued or inline, was running at a give-up. The jobs that
  finished before the flip were all submitted after it.
- **The label is written by a compute buffer submitted after the give-up.** In 9 of 13 no graphics
  buffer ran between the give-up and the flip, so only a compute buffer (or the CPU) can have written
  it. The flips sit at that buffer's end:
  - #1, #2, #11, #12, #13: the flip came 0.6–1.2 ms before the completion of an acb that was in
    flight (2657, 5508, 5544 dwords).
  - #7: 15 µs after acb #107054 (1393 dwords, 0.2 ms on the GPU) completed. It was the only job to
    finish in the 14 ms since the give-up.
  - #5, #6, #8, #9: within 0.2 ms of a compute buffer of 825–865 dwords. It recurs for label
    0x12004b5438, usually together with a graphics buffer of ~2,800 dwords.
- **That compute buffer was itself held back on a label wait.** In all 8 give-ups the wait trace
  covers, a compute buffer was "held back by its wait" in the 30 ms before. That wait was on a label
  with value 0x9076d6d8c (waiting for 0), "no pending write" (for give-up #7 it was 0x12004b4bc8 =
  label − 0x70). The wait trace's caps ended the held-back lines at t 204 s and the graphics lines at
  t 445 s, so give-ups #9–#13 are not covered. Such held-back lines come about 100 times a second, so
  being near one alone proves little. Give-up #7 is clear:
  - 100.369 s: acb 1397 is held back on 0x12004b4bc8.
  - 100.370 s: the game thread waits on 0x12004b4c38.
  - 100.379 s: it gives up, with 0 jobs in flight.
  - No job completes for 14 ms.
  - About 100.3925 s: acb #107054 is submitted (0.5 ms after its sync). It was numbered before the
    frame's graphics buffer #107055, whose sync came at about 100.3929 s.
  - 100.393007 s: #107054 is done, and the label flips 15 µs later.
  So the compute queue's label flipped while no job of ours was on the GPU and before the waiting
  frame's buffer was submitted. Something outside the jobs the host tracks wrote it: the title's CPU
  code, or a host path that is not a job.
- Served game-thread waits of 4 ms or more (8): all ended with jobs in flight (none with 0 on both
  queues). One had a completion within 0.5 ms after.
- Baseline, the next completion after an evenly spread moment: median 1.1 ms, within 0.5 ms 27.5 %. The
  flips' next completion: median 0.81 ms, within 0.5 ms 5 of 13. This alone would not tell a writer.
  The in-flight counts and the held-back compute buffers do.

**Verdict.** The given-up labels are written by the GPU, by a compute buffer near its end. But that
buffer is not yet submitted when the wait gives up. It sits behind its own wait on a compute-side
label that no tracked job writes. So at every give-up the GPU is idle: the game thread, the compute
queue and the GPU all wait for one outside write, and it comes 0.6–28 ms later.
- **"Wait while GPU work is in flight" fails.** In flight is 0 at all 13 give-ups, so this rule
  would give up at once. With exp 0215's result, neither a GPU-activity nor a CPU-progress rule fits.
- **The signal that fits is the compute queue's own blocked wait.** The host already keeps it:
  `g_unready_label`, and `g_unready_writes`, the labels that the held-back buffer writes after its
  wait.
  - If the game thread's label is in `g_unready_writes`, its writer is known and waiting for its own
    label. Then the wait should stay, bounded (100 ms, F264/F265/F271), unless the compute queue's
    label is written by the waiting buffer itself. That case is a real cycle, which run 123's
    `cycle broken` already handles for PM4 writes.
  - The opposite choice is exp 0055's `BC5_DIRECT_DCB_WAIT_UNBLOCKED_MS`, which keeps the short limit
    for a blocked queue "where a cycle is possible". These give-ups were not cycles: in 9 of 13 the
    label flipped without the waiting buffer having reached the GPU.
- **Not shown here:** whether the game thread's label is in `g_unready_writes` at the give-up, and who
  writes the compute-side label (title CPU code, or the host). A v2 of the diagnostic would show both:
  - at the give-up, journal `g_unready_label`, its value, and whether the waited label is in
    `g_unready_writes` (and the compute label in this buffer's `written`);
  - watch the compute-side label too;
  - put a user-space hardware write watchpoint (`perf_event_open`, `PERF_TYPE_BREAKPOINT`) on both
    labels in every thread, so that a CPU writer is caught with its thread name and a flip without a
    hit is a GPU write.
- **Until then:** the bounded wall-clock limit (100 ms) stays the safe choice. All 13 waits here would
  have been served within 37 ms, and tcpW2/W2b at 100 ms kept one give-up each, during loading.
- One run, at the lake bench. Labels and sizes recur, so the pattern looks like one chain per frame
  slot (labels 0x400 apart). Other scenes may have other writers.
