# 0246 — What the BVH compaction 0x909974400 costs: a load-time burst, no GPU cost on the lake bench, and title-side waits only when the traversals walk its trees

**Question.** With the compaction skipped the second title's reflections run at the reflections-off frame rate (F275,
F277), and that is the launcher default since 2026-10-22. With it running the maintainer's play ran at half that rate
(F268), and one lake-bench run faulted (exp 0211 R11B: TCP writes in the 0x12 heap, ring resets). What does the
compaction do per frame? Is the 2× its own GPU work, or the traversals walking the trees built from its output? What
wrote the faulting addresses? (The top session's brief of 2026-10-23.)

**Setup.**
- *Offline (repo):* exp 0160 and F208/F234 (the compaction's inputs and its three consumers), exp 0190/F249 (when a
  walk pushes), F257/F260 (the TCP session's write-fault classes), and my local extract of the 0218 play journal.
- *Read-only box slot (2026-10-23 19:31–19:34, the top session's grant, `BOX-LOCK` held):* `r11x.sh` (here) grepped
  the journals of exp 0211's runs R11A, R11B and R11D, and `ibdisp.py` (here) listed the dispatches of R11B's two
  timeout-probe dumps (`ib-timeout-00118195-dcb-31651.bin`, `-00118205-acb-875.bin`). The dumps stay on the box.
- *Bench triple (2026-10-23 20:03–20:21, granted; the maintainer's yes in this session: "Zgoda na biegi B i C testu
  przy jeziorze bez pomijania kompaktacji, gdy nadzorca da boks."):* the exp 0194 lake bench through `bench0246.sh`
  (exp 0211's copy of the water session's `bench0205.sh`, only the lock text and output directory changed). It loads
  the maintainer's lake save from a private copy (the live saves are untouched), plays the outpost scene to the Parry
  prompt, then holds a frozen Photo Mode view of the lake. `SECS=300`, `LOADWAIT=90`. Shared build
  (`~/bc5-work/kytyplus-build/src/kyty_emulator`, rebuilt ~19:44 with the ATRAC9 vibration decoder, F300;
  `KYTY_BC5_AT9_VIBRATION` left at its default in every arm).
  - All arms: `BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_TIMEOUT_PROBE=1
    BC5_DIRECT_JOB_TS=240:290`, TF ring on (the launcher's default). Each run's environment is in `raw/*-env.txt`.
  - Arms, safest first: **A** (E46A) `BC5_DIRECT_SKIP_PGM=909974400` (today's default). **C** (E46C) the compaction
    on, the six traversal variants skipped
    (`11d049aa00,11d04a6000,11d040e200,11d040c900,11d04bb900,11d0488a00`). **B** (E46B) nothing skipped
    (`SKIP_PGM=1`).
  - `runarm.sh` (here) streamed the kernel log to the laptop (`raw/kernel-*.txt`) and would have stopped a run at its
    first amdgpu page fault or ring timeout. `xarm.sh` (here) pulled the journal lines in one pass after each run.
  - Statistics on the laptop: exp 0211's `frameprof.py` (per-flip "frame profile" lines) and `jtsum.py` (here; the
    per-job GPU intervals of the `JOB_TS` window).
- Raw: `raw/frame-stats.txt`, `raw/flip-gaps.txt`, `raw/skip-timelines.txt`, `raw/R11B-timeout-summary.txt`,
  `raw/bench-*.txt`, `raw/kernel-*.txt`, `raw/*-env.txt`.

**Result.**
- **The compaction is a load-time burst, not per-frame work.** Its skip counter (it prints at 1, 4,097, 8,193, …)
  logs its first dispatch at t 40–48 s and the 4,097th at t 87–110 s in every bench run that skips it (R11A, R11D,
  E46A). None reaches 8,193 by t 278–299. In the maintainer's play of exp 0218 the 8,193rd came at t 91 s, and no
  12,289th followed in the remaining 1,000 s (`raw/skip-timelines.txt`). It runs once per object as objects come in:
  one BASE_A per object (exp 0160), 56 objects in R11B's load buffer. The traversal variants, by contrast, run
  steadily: 4,096 skipped dispatches every 16–24 s in E46C, about six a frame, into the frozen view.
- **On the bench the three arms cost the same GPU time in every phase.** From `raw/frame-stats.txt`:

  | Arm | Load t 40–100: flips/s, GPU ms/frame (median) | Outpost t 100–170 | Frozen view t 180–240 | Frozen view t 240–290 | Flip gaps > 0.3 s (whole run) | Kernel faults / fence timeouts |
  |---|---|---|---|---|---|---|
  | A: compaction skipped | 35.2, 15.0 | 41.8, 14.9 | 28.7, 27.3 | 29.2, 27.1 | 2 | 0 / 0 |
  | C: compaction on, traversals skipped | 34.8, 15.0 | 42.2, 14.8 | 28.6, 27.2 | 28.6, 26.6 | 1 | 0 / 0 |
  | B: nothing skipped | 35.0, 15.2 | 41.7, 15.7 | 25.9, 26.7 | 28.1, 26.1 | 13 | 0 / 0 |

  In the `JOB_TS` window (t 240–290) the GPU's busy union is 76.9 % (A), 74.8 % (C) and 73.0 % (B) of the time line,
  with 45–45.5 k jobs in each. The longest single job is 20.0, 30.7 and 35.7 ms.
- **What B adds is waits on the title's side.** Its 13 flip gaps of 0.32–0.94 s are almost entirely time the game
  thread spent outside the host (`raw/flip-gaps.txt`, the "outside" column). Nine of them fall in the frozen view
  (t 193–244), against one in A and none in C. The GPU time per frame does not rise with them. That is the shape of
  F268's slow play at a smaller scale: 637 frames over 0.1 s outside the host against 85, with host-side GPU busy
  well under saturation.
- **R11B's fault: the load-time BVH build, writing through addresses read from memory.** R11B's fence timed out at
  t 106.0 s (#118195, 31,651 dwords). That is the end of the load burst, 4 s after the three later traversal variants
  first ran (t 102 in R11A, R11B and R11D alike). The dumped buffer holds 119 dispatches of frame work, then the
  build of 56 objects: 504 dispatches with the compaction family's user data (exp 0160's signature, with BASE_B
  0x1270b70400–0x1270c67000 and the ASCII "PSR_BVHL"), then 187 indirect consumer dispatches. The consumers carry
  0x11d039d400/0x11d039d800 and a table pointer 0x12c3ba9a50 (`raw/R11B-timeout-summary.txt`). No user-data pointer
  lies within 64 MiB of the faulted pages 0x1208a73000–0x1208a7c000. The writes went to heap the host had no guest
  memory for (the learned window 0x1206000000 followed, exp 0211), as in the TCP session's L7 case (F257). The dump
  cannot name the writer. B ran clean today, so one of the two nothing-skipped bench runs has faulted. Neither the
  maintainer's 15-minute F268 play nor F250's idle run F2, both with nothing skipped, faulted.
- Side observation for the water session, one run each: the frozen view's patch share was 9.5–37 % in A, 1.3–1.4 %
  in C and 9.5–27 % in B (`raw/bench-*.txt`). This is within the run-to-run spread of F269.

**Verdict.**
- The compaction 0x909974400 and its consumers are not a per-frame GPU cost. They run as a burst while objects load
  (thousands of dispatches in the first ~100 s, then a few per second at most), and on the bench they add no GPU time
  in the load, the outpost scene or the frozen view (C ≈ A). The traversals walking the trees built from the
  compaction's output (B) add no measurable GPU time either.
- F268's halving is therefore not GPU work of either path. With both on, the title's own thread waits outside the
  host: 13 stalls of 0.3–0.9 s on the bench against 1–2. That is F268's signature, so the cost is what the title
  waits for once its reflection rays hit real geometry. Candidates (untested): results it reads back and acts on
  (streaming for reflected objects, the APR queues), or labels written late. In play, with the camera moving over
  water, that would grow, as in F268. What the thread waits for needs a run with the wait and label traces
  (`BC5_DIRECT_WAIT_TRACE`, `BC5_DIRECT_LABEL_TRACE`) or the AMM/APR trace, in B against A.
- F275/F277's "the traversals cost nothing" holds with the compaction skipped, where the traversals walk only the
  trees the other builders make (exp 0190: pushes then come only from tessellated surfaces). F277's screenshot check
  is consistent with rays that miss and show the sky. The launcher default (compaction skipped) keeps play at full
  rate, and the reflections stay partial.
- The heap-write fault of R11B is the BVH build's, through memory-held addresses, and intermittent (one of two bench
  runs). It belongs with the TCP session's no-guest-memory class (L7).
- Limits: one run per arm, one route, a frozen Photo Mode view (the moving part is the 70-s outpost scene only).
  `JOB_TS` adds a timestamp per job in every arm alike.
