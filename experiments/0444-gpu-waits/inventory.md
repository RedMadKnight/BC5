# Exp 0444 inventory: where the host decides a GPU wait, and what goes under BC5_DIRECT_GPU_WAITS

Sources:
- **The code inventoried.** Main d553cd8a has the shared patch 589ef163. The unit is `src/libs/bc5LleAgc.cpp`, md5 ed489aca, extracted with `ext.py`; it is cited as `U:line`. The backend files are main's `backend/`, cited as `path:line`.
- **Exp 0439's additions** are on branch `exp/0439-third-title` at 5ab8a128.
- **The two full reports:** [inventory-unit.md](inventory-unit.md) (ids H1-H25) and [inventory-backend.md](inventory-backend.md) (ids B1-B13, U1-U13, A1-A6, plus exp 0439 and dispatch-min). Both are delegated reads, which I checked on sampled lines.
- **The kernel facts** come from exp 0443's README (branch `exp/0443-gpu-decides-waits`, 9c1ecc97, item 2), cited here and not copied.

**Shared defaults that matter here.** These are in kSoft for every title (`switch_defaults.hpp`):
- `BC5_GC_MODE=direct`
- `BC5_DIRECT_CHAIN=2`
- `BC5_DIRECT_ACB_RINGS=4`
- `BC5_DIRECT_ACB_QUEUE_STATE=1`
- `BC5_DIRECT_ACB_MEC_INDIRECT=1`
- `BC5_DIRECT_ACB_SPLIT_LATE=3`

## 0. The precondition: the queue binding

**Today** (H18, H19, U6, B7):
- Every guest compute queue starts on libdrm compute ring 0.
- A queue moves once to ring `(++n) % 4`, at its 256th acb, after a 2-s wait-idle of all rings (U:7484-7512).
- Quiet queues share ring 0.
- Any acb that `compute_ring_refusal` refuses goes to the GFX ring (U:7571-7582). So one guest queue can be split over two rings, with no order between them.
- dcbs always go to GFX.
- H25's register prefixes exist because a libdrm ring index is not a fixed hardware queue.

**The kernel** (exp 0443 item 2, v7.3.4):
- **Entities, not rings.** A CS's ring index is a scheduler entity. There are 4 per context for compute (amdgpu_ctx.c:35-37, ctx.h:37), each spread over all 7 normal compute rings.
  - `drm_sched_entity_select_rq` re-picks the least-loaded ring whenever the entity is idle (sched_entity.c:576-612).
- **Ring depth.** Each ring admits 2 jobs to the hardware (`sched_hw_submission`).
  - A job polling WAIT_REG_MEM holds its HQD: every later job on that ring, from any context, waits behind it.
  - Other rings are not blocked.
- **So on the stock kernel, no guest queue can be bound to one hardware queue**, except one high-priority context, which needs CAP_SYS_NICE.
  - A GPU-decided wait deadlocks until the 10-s job timeout whenever the scheduler puts its writer behind it on the same ring.
  - It also deadlocks when the writer lands behind two jobs of a third queue that wait for the waiter.
- **Pinning options:**
  - (d) a small kernel patch: a compute entity bound to one scheduler, as the VCN branch is (ctx.c:246-255), with 8 entities.
  - (a) `amdgpu.num_kcq=2`, which gives only 2 pinned queues.

  Both are the maintainer's kernel decision.

**What the switch can guarantee without a kernel change:** nothing about order. It can do these:
- **Make collisions visible.** The title-free test reads HW_ID2 in each job and reports two queues on one HQD instead of hanging.
- **Make them rarer.** It keeps an entity per guest queue, never moves a queue on purpose, never sends a guest queue's buffer to the GFX ring, and spreads busy queues over contexts so each has its own entity.
  - A busy entity is not re-picked (sched_entity.c:587, :601).
  - Way 2 measured 2 moves in 220 s.

With the kernel patch, the switch gets the console's model as long as guest compute queues ≤ pinned rings. Seven normal rings plus the high-priority one are 8; the third title has at least 7 compute queues plus GFX.

**When there are more guest queues than rings** (open; for the design session and the top):
- Sharing is safe only between queues that never wait on each other, in either direction.
- The host cannot know that ahead of time; it would need the label write sets of whole frames.
- The proposal: the quietest queues share, and a catcher records a wait whose writer is found on its own ring's queue behind it.

## 1. The deletion map

Every item below is inactive when `BC5_DIRECT_GPU_WAITS=1`. With the switch off, every path stays byte for byte as today.

| group | items | what each stands in for on the console | under the switch |
|---|---|---|---|
| **Ring choice** | H18/U6 `acb_ring`, `w428_queue_ring`; H19 the 256-acb move; B7 the GFX fallback; H25 queue-state prefixes | the title's fixed queue-to-pipe binding | One entity per guest queue for the run, no move, no GFX fallback. An acb the policy refuses for compute is an error counted and reported, not rerouted; how many refusals there are is a measurement, not a guess. H25 stays while two guest queues can share an HQD. |
| **The wait decision** | H1/U1 `submit_split` wait loop (U:10501-10799); U2 `wait_satisfied`; H12 the CPU-served wait (acb 2 s on bc5-ring, game-thread dcb 8 ms) and its give-up; H13 the ADR 0008 piece split; H14 the two-ring wait / SPLIT_LATE; H10 the chain flush at an unmet wait; H22 cycle publication; H20 indirect draws dropped after a given-up wait | the CP blocking at the packet | The loop does not run. Every WAIT_REG_MEM / WAIT_REG_MEM64 goes to the GPU unchanged. No `set_gpu_executed` mark is needed, because the soft CP never polls (see H16). |
| **The filter** | B1 `self_waits_only` (policy.cpp:514-530); B2 `keep_wait_offsets` and its remaps (H2: U:15926-15933, 8333-8337, 13866-13869, 16409-16414); B3 the root options on every piece (direct.cpp:1527, exp 0439's pw439 site) | the CP executes every wait as written | `self_waits_only=false` for the root and every piece, and keep lists unused. B3 is fixed in both worlds, as pw439 mode 1 does (pieces get empty keep and drop lists): it is a defect, not a substitute (D26). B4, the unmapped-label drop, stays as fault protection but becomes loud: a counted line per drop. |
| **Holds** | H4/U5 `acb_ready` and the bc5-ring gate (U:1655-1705, 7754-7853); H5 the acb head split; H6 ng438 INFLIGHT_NG/OPEN_NG and `g_ng_live`; H17 the 10-s "proceeding" fallback; H15 the ADR 0013 HoldCond (dead); H21 inheriting dispatches (dead) | a compute queue blocks at its own wait while other queues go on | The bc5-ring consumer forwards every slice at once. This is F902's deadlock partner, and pw439 mode 2 shows that keeping piece waits without removing the hold deadlocks. The dead H15/H21 go in both worlds. |
| **Writer bookkeeping** | H3/U3/U4 `g_plw`, `register_label_writes`, `ring_will_satisfy`; H7 r438 early registration and PLWCV (unbounded game-thread wait, U:10279-10317); H8 ho430 F10/F16/F18 flushes and waits; H9/B9 ho430 F2 + F4 kernel dependency (`add_next_submit_dependency`); B10 `set_ring_deps` (no caller); exp 0439's cw439 | "the writer has not yet run": the host imitating the GPU's view of a label | None of it runs. `g_plw` may stay as a diagnostic, off by default. B10 is dead and goes. |
| **Host label writes** (must stay correct) | H11/U10 the flip-label CPU wait and **forced clear** (U:10525-10553); the flip clears by VideoOut (U:17838-17918); B8 shadow labels; soft-CP replays (H16, U:1494-1519); EOP interrupts `fire_eop` (U:707-719); the submit-and-EOP ioctl page | VideoOut clears a flip label at the flip; the CP writes labels in order | The forced clear and the 100-ms wait go: the GPU polls the label, and VideoOut's clear is a CPU store to userptr guest memory, so the GPU sees it. B8 is off, because it rewrites the wait's address. Its F360/F406 stray-store protection is lost under the switch, which the second title must test. With nothing dropped, the soft CP replays no label writes. EOP interrupts still fire from the replay after the job's fence: host events, not waits, unchanged. |
| **The soft CP's own poll** | H16 `SoftCp::wait_reg_mem` in replays, mostly waits inside IB2s | the CP's poll | Every wait is GPU-executed, so its case never runs; the switch marks them so. |
| **The chain hold** | U8 the ADR 0010 chain (`BC5_DIRECT_CHAIN=2`), with a watchdog of about 2 ms (U:8181-8185) | buffers reach the queue at once | It stays at first: it delays a writer by at most the watchdog, which is far below the 10-s timeout, and its submit order is ring order. Measure it before deleting it. |
| **Not wait decisions** (stay) | B4 the mapped check (made loud); B11 per-ring fences and the wedge rule; B12 the nested IB depth and piece cap (with IB_CHAIN, and a dropped target must be loud); A1-A6 GPU-side syncs; ds439; pc439 | — | unchanged |

**Defects found on the way.** Each is fixed in both worlds:
1. **B3** (pw439 mode 1): pieces match the root's keep and drop offsets.
2. **B8:** `BC5_DIRECT_SHADOW_LABELS` is read as "set at all" (direct.cpp:588), so `=0` turns it on. The second title's kTitleDefaults row (`{BC5_T2, "BC5_DIRECT_SHADOW_LABELS", "1"}`, F414/F415) sets it, and the table promises NAME=0 turns a row off: for this row `=0` never did. A per-title default is itself a defect to remove (D26).
3. **H7:** the PLWCV wait has no hard bound; it only logs at 100-ms steps. This is moot under the switch. With the switch off it stays as it is; that is the shared behaviour, and changing it is outside this experiment.

## 2. What the host still must do under the switch

- **Write the host-owned labels in memory before or while a queue polls them, never by rewriting a buffer.** These are:
  - flip-done clears (VideoOut);
  - the submit-and-EOP page;
  - any label the soft CP would replay. With nothing dropped there are none: the filter's remaining drops (graphics-only packets on compute rings, B6; unmapped targets, B4) are counted and reported per run.
- **Bind each guest queue to one entity** (section 0), and record per job which libdrm ring and, in tests, which HQD it ran on.
- **Catcher:**
  - Today, a kernel timeout on a waiting ring is the first sign; it is a GPU fault, a bug plus a record.
  - The planned catcher, for diagnosis builds and compiled out of lean: a watchdog that reads, for each ring's oldest unfinished job, its first unmet wait (the CPU reading the label) and records the label, the job, and the last known writer job with its ring and finish state. It must never write or serve the label.
