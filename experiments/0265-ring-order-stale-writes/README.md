# 0265 — the ring order's stale pending writes: count them, or skip them

**Question.** Exp 0255 (F322) found the same pair behind every surviving two-ring timeout:
- a graphics buffer waiting on the GPU for a compute-written hand-off slot (0x12004b3c38, …38 labels == 0);
- the "Lighting Prep" compute buffer waiting, at its first packet, for the graphics-written slot (0x12004b53c8, …c8
  labels == 0) that the next graphics buffer writes.

With honest registrations the ring order cannot form that cycle. So the hypothesis is that a wait kept for the GPU
(exp 0055, ADR 0009: `ring_will_satisfy`) was kept on a write that would not end it: the write had already run and the
title had re-armed the slot. Does that happen in play, how often, and on which labels? And does not keeping such waits
remove the machine-downs?

**Known before this experiment.**
- A write is registered right after its submission (`register_label_writes`). It is forgotten when the completion side
  processes its job (`forget_label_writes`), and the compute consumer finishes its own jobs.
- In between, a job that has already run on the GPU still counts as pending. If the title has re-armed the label in
  that window, `ring_will_satisfy` still answers yes for a write whose 0 is gone.
- The direct device has no non-blocking fence query (`Device::finish` waits and consumes the result,
  `backend/include/bc5/direct.hpp`). Adding one means rebuilding `libbc5_backend.a`.
- The box's archive (`~/bc5-work/backend-ubuntu`, 2026-10-19 16:37) is older than its sources: ninja's dry run would
  rebuild 15 steps. A rebuilt `direct.cpp.o` would therefore bring in unrelated changes.

**Setup.**
- `patch0265.py` makes `patch_0265.diff` (100 lines, 4 edits) on top of exp 0260's `bc5LleAgc.probe.cpp` (md5
  daca24cc: the integrated tree's 67859271 plus 0260's synced probe). The probe stays in, so a machine-down during these
  runs is recorded. Only `bc5LleAgc.cpp` changes; there is no backend change and no fence query.
  - A registered write keeps its label's value at registration (one read per registered write, only with the switch).
  - When `ring_will_satisfy` would answer yes, the write is stale if the label differs from that value now, while the
    wait still does not hold. Either its job has run and the label was re-armed, or it was re-armed before the job ran.
    Either way the write will not end the wait.
  - Not keeping a wait on such a write is always safe: the wait falls back to the paths that do not keep it, served on
    the CPU, held, or given up.
- Switch `BC5_DIRECT_RING_ORDER_STALE`, off when unset (D16):
  - `count`: journal "ring order: STALE pending write on <label> … the label was <value> at registration, <value>
    now; the wait (ring r) kept as before (count only) (n stale of m checked)" (the first 200, then every 256th), and
    change nothing else. GPU-neutral.
  - `skip`: the same line with "not kept for it", and the write is ignored.
- Build: `run0265.sh build`, a private binary `~/bc5-work/exp0265/kyty_emulator`, as exp 0260's: one unit, linked from
  the shared normal objects as they are at build time with a fresh compdb. The shared builds are untouched.
- Count runs: `count0265.sh [runs] [secs]`, by default 6 × 600 s, is exp 0260's `catch0260.sh` with this binary and
  `BC5_DIRECT_RING_ORDER_STALE=count`:
  - S6N's route from exp 0196's saves, each run with its own save restore;
  - a run is stopped at the first new kernel amdgpu line, and the chain stops after any run that is not a pass;
  - the live saves are snapshot at chain start (`exp0265/saves-before-<HHMM>`). Their checksum then must hold after
    every run's restore and at the end, or the chain stops. No value is hard-coded, because the maintainer plays and
    saves between runs;
  - per run, the STALE lines and a count per label (`S<n>-stale.txt`, `S<n>-stale-labels.txt`).

  `stream0265.sh` on the laptop streams the kernel log and the probe, TIMEOUT, STALE and hold lines, only while the
  chain's own lock line is there. Attended: the box supervisor's GO, the maintainer's approval in this session, and him
  reachable for a power-cycle.

**Result.**

*Build*, 2026-10-24 15:57:58–15:58:25, under my lock line (removed by the script's trap), no emulator, in the box
supervisor's slot after exp 0264.
- rc 0, with only the 4 warnings the file already had.
- `~/bc5-work/exp0265/kyty_emulator`, 166,432,688 bytes, md5 **98f0a58d**. It carries the new journal format.
- `bc5LleAgc.stale.cpp` md5 077299a7.
- Linked from the shared normal build's objects as they were after the supervisor's SaveData sidecar fix of 15:26 (F319,
  `libSaveData.cpp.o`; normal build ce2e5d7a then), with a fresh `ninja -t compdb -x`. The inputs are recorded in
  `~/bc5-work/exp0265/raw/build-inputs.txt` on the box.
- **Base, against the shared builds:**
  - `bc5LleAgc.cpp`: this binary's file is the shared tree's file as of 16:21 (daca24cc: the held tail, the CS prefix
    and exp 0260's synced probe, F317) plus only `patch0265.py`. In count mode it keeps exactly the waits the shared
    build keeps; the ring order and the hold are the same code. The comparison baseline is therefore the shared build's
    behaviour.
  - Other units: linked from the shared normal objects of 15:58 (after the SaveData fix, F319). It does **not** have
    the box supervisor's 0267 pad fix of 17:07 (F330; shared normal da4d3b0a, lean 639d8795). The count runs drive the
    title with scripted input (`KYTY_BC5_INPUT_CMD`), not a pad.

*Play review* (read-only, 17:02–17:05, on the supervisor's GO; `raw/play-review-1601-1605-1611.txt`): the maintainer's
play of 16:01–16:14 with a DualShock 4, in which he saw hitches in the second title (normal and lean). Do the held tail's
holds or give-ups line up with them?
- **16:01, second title, normal build ce2e5d7a:**
  - 8,519 frames, 54 over 100 ms, 9 over 250 ms;
  - 16,673 holds, none given up, the longest 80 ms;
  - no cpu-wait give-up, no unserved two-ring wait, no TIMEOUT.
- **16:05, second title:**
  - 5,228 frames, 83 over 100 ms, 16 over 250 ms;
  - 9,454 holds, 2 given up, both on 0x12004b3c38 (F262's label): 155 ms at t ≈ 131.6 and 408 ms at t ≈ 142.4.
- **16:11, ASTRO BOT** (no held tail there): 7,610 frames, 3 over 100 ms.
- **The lean build** writes no journal, so its hitches cannot be read this way.
- **Where the worst frames' time went** (the journal's frame profile):
  - mostly outside the host, i.e. the title's own threads: 642 of 806 ms, 642 of 676, 960 of 1,004, 772 of 810;
  - otherwise inside the host, in its mapping sync or IB prepare: sync 301 ms at t 142.459, sync 360 at 120.420,
    prepare 528 at 154.893;
  - at the flip, where a held chain is waited for, at most 80 ms. That once matches the run's longest hold, inside an
    806-ms frame that is mostly outside time.
- **The two give-ups follow stalls; they do not cause them:**
  - the 155-ms one comes in a frame where the title's thread was outside the host for 198 ms;
  - the 408-ms one comes in a frame where the owner sat 301 ms in the host's mapping sync inside `Direct::submit`. The
    holder leaves an owner in a submit alone (exp 0226), so the 100-ms bound could only act after it.
- **So the held tail does not explain the hitches.** They are the title's own threads stalling (the AnyPS5 session is
  checking the DS4 rumble fallback on the audio thread) and host stalls of 0.3–0.5 s in mapping sync and IB prepare.
  The box swapped during the day's runs (exp 0260's `K*-start.txt`/`K*-box-end.txt` counters), which would fit memory
  pressure, but that is not shown here.

*Data point W266a* (the water session's run of 17:03–17:05 on exp 0251's private binary of 2026-10-23, which has neither
the held tail nor exp 0260's synced probe). Read-only, 17:18, on the supervisor's GO, `read0265w.sh` (`raw/W266a-*.txt`).
- **The fault and the timeout.** At 17:05:28.82 there were six TCP write faults at 0x145e628000–0x145e62d000 (status
  0x00741051). At 17:05:30.83 comp_1.1.0 and gfx_0.0.0 timed out, and gfx again at 17:05:32.88; all three resets
  succeeded (the water session's `W266a.kern.txt`).
  - The thread names are the VM's last submitter ("Render Thread" at the faults, "bc5-ring" at the timeouts), so they do
    not attribute the job.
  - The journal: dcb #85856 (69,274 dwords) and acb #85864 (675 dwords) TIMEOUT. Then the host's fault query ("timeout:
    fault 0x145e628000"), and "learned … region 0x145a000000+0x6000000 (saved)".
  - The probe dumps survived, because the box did.
- **The fourth case of F322's pair** (`raw/W266a-dec.txt`). It is a different compute buffer: 675 dwords, 6 dispatches,
  programs 0x11d0219300–0x11d021ec00, from the lake. The same hand-off structure:
  - the acb's first packet is a WAIT_REG_MEM64 on **0x12004b5fc8 == 0**, and it writes **0x12004b6038 = 0**, its paired
    "…38" slot at +0x70;
  - the dcb waits (pfp) on 3c38 (offset 1269), 4438 (31435) and 4c38 (37669) == 0, and writes 4fc8 (26782), 53c8
    (51493), 57c8 (58119) and 5bc8 (58314) = 0;
  - so the stuck compute buffer again waits on the slot after the last one the stuck graphics buffer writes, which only
    the next graphics buffer writes;
  - and again neither buffer writes a label the other waits on.
- **Before the timeout** (`raw/W266a-labels-near-timeout.txt`): "two rings: dcb 242 dwords waits at 174 on
  0x12004b3038: NOT served after 4.03 ms" about 350 lines before (this binary gives up such waits). Also the ring order
  keeping a dcb wait on 0x12004b6038 for the GPU, as in F322.

*Count chain, run S1: a machine-down caught by exp 0260's probe.*
- **The chain** started 17:44:59 (`count0265.sh 6 600`), with the maintainer's approval in the tcp session ("Yes, I
  approve: start the exp 0265 count chain (count0265.sh 6 600) …"). Saves snapshot `saves-before-1744`
  (2f5d956c8f1b6ebd). S1 from 17:45:01, with the 0265 binary and `BC5_DIRECT_RING_ORDER_STALE=count` reaching the
  emulator.
- **The machine-down** (`raw/kernel-stream.txt`): at 17:46:59.277 `gfx_0.0.0` timed out, and its reset succeeded. At
  17:46:59.504 `comp_1.2.0` timed out, its **reset failed**, then "GPU reset begin", MODE1 at 17:47:03 and VRAM lost;
  ssh then died. There was no fault line, so it is the fault-less class (S6N/F316, F260, F262).
- **The probe** (exp 0260, F317) wrote its lines to disk and the stream carried them to the laptop
  (`raw/journal-stream.txt`, lines 105–1951). The stuck pair:
  - **acb #127637**, 11,383 dwords, TIMEOUT 2,045 ms: a ring-consumer chain of 786 dispatches.
    - Its only wait (offset 4, WAIT_REG_MEM64 on 0x12004b4fc8 == 0) reads "now 0x0 (met) DROPPED": **no wait was
      kept for the GPU** in it.
    - The 200 dispatches printed are all DISPATCH_INDIRECT of programs **0x909939400** (153) and **0x909936c00**
      (47), the BVH-build family the BVH session works on (F250's compaction is 0x909974400).
    - Its writes at offsets 16–63 have landed (now = value). From 9872 on none has: a 68-dword header write whose
      ASCII tag still reads "PSR_BVHC" against the written "PSR_BVHL"; counters one behind (0x11552 against 0x11553);
      the end label 0x12004b5038 = 0, still holding 0x907616589.
    - **So the compute ring stopped inside a dispatch between offsets ~63 and 9872**, with no wait involved. A wave
      that never ends would also explain why its queue reset failed (TODO(verify) with the devcoredump).
  - **dcb #127648**, 1,824 dwords, TIMEOUT 2,042 ms. It has two waits, both kept for the GPU and **not met**:
    0x12004b5438 at offset 1269 and 0x12004b5038 at 1679, the second being the hung chain's end-of-buffer write. So the
    graphics ring waited honestly behind the hung compute work.
- **The count before the hang:** 42 STALE lines, all of the harmless "landed" kind. In each, the label held the pending
  write's own value; the write had landed between the caller's check and the count. **Not one re-armed case.**
- The chain ended with the machine. The box supervisor put the saves back after the power-cycle (18:06) from the
  chain's snapshot (2f5d956c8f1b6ebd, mtimes kept), and kept the crashed live copy in
  `exp0265/saves-live-after-crash-1807`.
- **The synced dumps, decoded after the reboot** (read-only, ~18:10, on the supervisor's GO).
  - Both survived the machine-down because exp 0260 syncs them: `ib-timeout-00127637-acb-11383.bin` and
    `ib-timeout-00127648-dcb-1824.bin` in `play-20261024-1745/gc` (`raw/S1-capture-dir.txt`, `raw/S1-dec.txt`).
  - The whole compute chain lies inside one debug marker, **"Ray Tracing Update"** (offsets 44–11306,
    `raw/S1-acb-markers.txt`).
  - Its 786 dispatches as runs of one program (`raw/S1-acb-program-runs.txt`). There is no dispatch before offset 938.
    In the stall window (~63–9872):
    - 0x909939400, small direct dispatches (1–9 groups), 938–3358;
    - **286 indirect dispatches of 0x909936c00**, 3407–6732;
    - 0x909939700, small direct dispatches, 6764–8126;
    - **153 indirect dispatches of 0x909939900**, 8170–9842.
  - After 9872, never reached: 0x90985f200, 0x90986db00, 0x90986ea00 (6,144 groups), 0x909971300 ×13, 0x90992af00 ×11,
    … 0x9098eb200.
  - The chain writes no label inside the window, so the dumps cannot narrow it to one dispatch.
  - The indirect dispatches' arguments (group counts, read from memory at the base SET_BASE sets, as the probe's "op 16
    … base1" lines show) died with the process. The probe does not read them yet.
- **No devcoredump copy.** The kernel created one at 17:46:59.277 for the graphics ring's successful reset, but
  `~/bc5-data/captures/devcoredump/` does not exist after the reboot. The previous boot's journal, which ends at
  17:46:34, has no `bc5-devcoredump` line (`raw/S1-devcoredump-*.txt`). In a machine-down the probe's synced lines and
  dumps are the only record.

**Verdict.**
- **F322's mechanism is refuted for the case caught.** The machine-down that the probe recorded is not a kept wait
  that missed its 0, nor a cross-ring cycle. A compute dispatch of the BVH build never finished (no wait in the compute
  chain was even kept), and the graphics ring waited, correctly, for that chain's last write. The ring order's keep
  was honest, and the count found no stale keep at all.
- **For F322's four TCP-fault cases**, the same reading is now the likelier one: the compute buffer stuck in a
  dispatch rather than at its first wait. Their dumps cannot tell which, because those buffers' first waits may equally
  have been met.
- **The count and skip modes do not address this hang**, so they are not pursued.
- **Where it hung:** inside the title's "Ray Tracing Update" chain, before offset 9872. That is one of 0x909939400,
  0x909936c00 (286 indirect), 0x909939700 or 0x909939900 (153 indirect). Two indirect runs take their sizes from GPU
  memory, so a bad group count is one candidate for a dispatch that does not end; a shader loop is another.
- **Next** (for the BVH session and the probe):
  - The probe could read each indirect dispatch's three group counts at the timeout: `base1 + offset`, as it already
    does for indirect draws.
  - Exp 0199's lead (F255/F257) fits here and should be checked. The learned windows map one shared zero buffer R|W|X
    at every hole, so a write into one hole shows in all of them: a BVH builder's stray write could corrupt another
    pass's arguments or nodes.
