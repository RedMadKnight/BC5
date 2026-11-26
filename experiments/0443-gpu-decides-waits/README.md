# 0443 — GPU decides waits (design)

**Question.** The maintainer asked: why the GPU cannot decide here, as it does on the PS5. On the console the GPU decides every wait between queues. What would it take for our GPU to decide them too, and what in the stock amdgpu kernel of the box prevents it?

**Setup.** This is a design document; nothing ran. The kernel source is Linux v7.3 (commit `c03c1a14507d`), checked against the stable tags the box runs, v7.3.4 (`8310b43a`, the current image, 7.3.4-ogc8.1) and v7.3.3 (the second deployment, 7.3.3-ogc1.1). Every cited file is identical in all three, except `amdgpu_device.c` and `amdgpu_drv.c`. Their v7.3.4 changes are unrelated (BOCO, the UMD profile restore), but they shift `amdgpu_device.c` lines from about :583 on. Where a line moved, the v7.3.4 number is given in brackets. Whether the OGC patches touch these files is TODO(verify) against the OGC tree. `D` below means `drivers/gpu/drm/amd/amdgpu`. Host facts come from HANDOFF F845, F846, F898-F903, ADR 0009, and exp 0426, 0427, 0428 and 0439. Branch `exp/0443-gpu-decides-waits`. The number is claimed in the repo only: exp 0439 holds the box, and a box read needs the top's GO. `~/bc5-work/exp0443` gets created with the first box step.

**Result.** The design follows in sections 1-5.

**Verdict.** Open. The design stands, and its first test (section 5) needs no title. On the stock kernel the mapping cannot be made safe (section 6): it works unless 7 guest queues hold work at once, or two submissions race, or a completion window hits; the patch (section 4, `backend/kernel-patches/`) closes all three. The answer to the maintainer's question, in short:

- On the console every guest queue has its own hardware queue. A wait stops only that queue, and nothing else decides the wait.
- On the stock kernel one guest queue cannot be held on one hardware queue.
  - A libdrm compute ring index is a scheduler entity. Each time it goes idle, it re-picks among the 7 normal-priority hardware queues.
  - A context has only 4 compute entities.
  - Each kernel ring takes only 2 jobs onto the hardware at a time.
- So the host had to decide waits itself (holds, splits, drops), and those decisions make deadlocks the console cannot have (F902).
- The smallest change that gives a faithful mapping is a small amdgpu patch:
  - pin each compute entity to one ring, as the kernel already does for VCN and UVD;
  - allow 8 entities;
  - raise the hardware submission depth on compute rings (a module parameter does this today);
  - give compute a long job timeout (a module parameter does this today).
- KFD and user queues give nothing on gfx10 (exp 0426).

---

## 1. What a faithful mapping needs

The console's model:

- Each guest queue (the dcb's graphics queue and each acb's compute queue) is fed to its own hardware queue.
- A WAIT_REG_MEM stops only the queue that runs it. The other queues keep running, and one of them writes the label.
- The order inside one queue is the order the title wrote.
- No one outside the GPU decides whether a wait is met.

So we need:

1. **One independent hardware queue per guest queue.** It must be fixed for the guest queue's life, so the queue's order holds and no other queue's work sits behind its waits.
2. **A waiting queue must not block another.** Nothing else may be in front of the waiter on its hardware queue. And the kernel must not stop feeding other rings while one ring's job polls.
3. **GFX alone on its ring.** The dcbs on the GFX ring, and no acb behind a dcb wait (way 2 already does this, F846).
4. **A wait may last as long as the title makes it last.** That is up to a frame or a loading stall. The kernel's job timeout must not shoot it.

How many guest queues each title has in flight at once:

| title | guest compute queues seen | busy at the same time | source |
|---|---|---|---|
| the second title | 4 (32, 40, 38, 26) | 2 on the fight route (t_queue_idx 0 and 8: 1.4 M and 0.13 M jobs in 220 s) | ADR 0009:142; exp 0428 w428c counters |
| the third title | at least 7 (16, 24, 25, 40, 49, 50, 51) | at least 2 inside one frame (16 and 40 stand behind DISPATCH_INDIRECT at once, F898) | exp 0439 item 49 |
| The first title | 4 (26, 32, 38, 40) | 3 (32, 40 and 38; 26 gave 2040 jobs in a whole run, the others 15 k-793 k) | exp 0431 `raw/t1-W.out`, `-X`, `-Y`, `smoke0431.out` (`w428c` queue->ring lines) |

Plus the dcb (GFX) in each title. The need is therefore **up to 7-8 compute hardware queues, each fixed, plus GFX**. The gfx10 MEC has 2 MECs × 4 pipes × 8 queues (`D/gfx_v10_0.c:4763-4775`), but amdgpu sets up only 8 kernel compute queues (`num_kcq` default 8, `D/amdgpu_gfx.c:1468-1477`).

## 2. What amdgpu 7.3 gives

### 2.1 The compute rings

- `gfx_v10_0_compute_ring_init` names the rings `comp_%d.%d.%d` (MEC.pipe.queue) and gives each a hardware priority (`D/gfx_v10_0.c:4681-4709`).
- Queue acquisition spreads the 8 kernel queues across pipes ("multipipe", `D/amdgpu_gfx.c:154-171`, `:208-236`).
- One ring per pipe set is high priority: `comp_1.0.0` on this box, chosen by `amdgpu_gfx_is_high_priority_compute_queue` (`D/amdgpu_gfx.c:195-206`). That leaves **7 normal-priority rings**: `comp_1.0.1`, `1.1.0`, `1.1.1`, `1.2.0`, `1.2.1`, `1.3.0`, `1.3.1` (exp 0427, F845).
- Ring → pipe/queue registers: `D/gfx_v10_0.c:4938-4955`. The MQD carries the HQD quantum, so queues on one pipe time-slice (`D/gfx_v10_0.c:7015-7027`).
- `available_rings` in the INFO ioctl reports them (`D/amdgpu_kms.c:465-470`, `:594-632`).

### 2.2 How a CS picks a ring

- The CS names (ip, instance, ring). `amdgpu_ctx_get_entity` rejects `ring >= amdgpu_ctx_num_entities[hw_ip]` (`D/amdgpu_ctx.c:460-464`). For compute that number is **4** (`D/amdgpu_ctx.c:35-37`).
- An entity is created on first use. `amdgpu_ctx_init_entity` (`D/amdgpu_ctx.c:204-262`) gives it the list of *all* schedulers of the context's hardware priority (`:223-230`).
- Only VCN and UVD are pinned to one scheduler, because "the hw engine retains context among dependent jobs" (`:246-255`).
- The scheduler re-picks an entity's ring whenever its queue is empty and its last job is done: `drm_sched_entity_select_rq` (`drivers/gpu/drm/scheduler/sched_entity.c:576-616`).
- It picks the ring with the lowest score, i.e. the fewest jobs: `drm_sched_pick_best` (`sched_main.c:958-983`).

So **a libdrm compute index is not a hardware queue**. Two indexes may meet on one ring, and one index may move between rings. Exp 0427 measured this through HW_ID2 (F845).

### 2.3 Can one guest queue be kept on one hardware ring?

- **One entity per guest queue:** only 4 per context, and none of them is pinned (2.2).
- **Several contexts:** each context has its own 4 entities, but every one of them re-picks over the same 7 rings. More contexts give more entities, never a pinned one.
  - An entity with a job in flight stays put (`sched_entity.c:587`, `:601`). So a busy queue mostly stays on its ring; way 2 counted 2 moves in 220 s.
  - The guarantee is still missing exactly when it matters. An idle waiter's next job may land on the ring where another queue's job polls a wait.
- **Priorities:** a high-priority context (needs CAP_SYS_NICE or DRM master, `D/amdgpu_ctx.c:107`, `:110`, in the permit at `:100-125`) maps compute to the high-priority ring set, here `comp_1.0.0` alone (`:139-166`). That pins *one* queue, at most.
- **`num_kcq`:** with `amdgpu.num_kcq=2`, two compute rings exist, one high and one normal, so each priority has one ring and nothing can move. That gives **2 pinned queues** at most, fewer than the titles use. This is a module parameter (`D/amdgpu_drv.c:958-959`), and it also takes rings away from every other client.

**Answer:** with the stock kernel at most 2 guest compute queues can be pinned, and only by giving up all other compute rings. A faithful mapping for 4-8 queues is not possible.

### 2.4 Other entities on a ring while one job polls a wait

- Each ring's scheduler lets at most `credit_limit = ring->num_hw_submission` jobs onto the hardware (`D/amdgpu_device.c:2324`; [v7.3.4 :2322]). For compute that is `amdgpu_sched_hw_submission`, **default 2** (`D/amdgpu_drv.c:178`; `amdgpu_ring.c:232-255`; must be a power of two, `D/amdgpu_device.c:1618-1625` [:1616-1623]).
- A job that polls WAIT_REG_MEM holds its HQD's FIFO. Every later dword on that ring waits behind it, whichever entity it came from.
- Once 2 jobs sit on the ring, the scheduler stops feeding that ring altogether. Further jobs of every entity on it wait in software.
- Other rings are not affected:
  - each ring has its own scheduler thread;
  - each HQD runs its own queue;
  - queues on the same pipe share it by the HQD quantum, so a polling queue gives up its time slice (TODO(verify): measure that a polling queue does not starve its pipe neighbour; the test in section 5 covers it).
- With `hw_submission=2` a waiter and its writer can still share a ring:
  - **writer first:** fine;
  - **waiter first:** the writer is stuck behind the waiter, a deadlock until the timeout.

  The console never has this, because the writer is always on another hardware queue.

### 2.5 User-mode queues and KFD

- **KFD** (exp 0426): queues are made by the HWS on gfx10. A hung queue cannot be reset there. `hqd_reset` is a stub (`D/amdgpu_amdkfd_gfx_v10.c:1073-1085`), and an HWS hang goes to a full GPU reset (`amdkfd/kfd_device_queue_manager.c:2645-2748`), which on the BC-250 kills the box.
  - KFD would give each guest queue its own hardware queue with unlimited depth, and no job timeout.
  - The cost: the first hang takes the box down, and it means a second submission path (no drm_sched fences for the GFX side).
  - Not viable as the main path.
- **amdgpu user queues (userq):** only with MES, i.e. gfx11 and later. Nothing for gfx1013.

### 2.6 The job timeout

- The default is 2000 ms for every queue (`D/amdgpu_device.c:3582-3583` [:3585-3587]; the DOC at `D/amdgpu_drv.c:355-367`).
- `lockup_timeout` takes one value or four (`gfx,compute,sdma,video`); a negative value means infinite (`D/amdgpu_device.c:3594-3634` [to :3638]).
- The box runs `amdgpu.lockup_timeout=10000` since 2026-11-22 11:04 (F903), which is 10 s on all queues.
- A legitimate long wait needs a compute timeout longer than any wait the title writes. That is a frame or a loading stall, not 10 s. Options without a kernel change:
  - `lockup_timeout=10000,60000` (GFX keeps 10 s, compute 60 s);
  - `10000,-1` (compute never times out). With this a true compute hang is never reset, and the host must catch it (exp 0430's catcher).

  Either is the maintainer's kernel argument (a system change, his word).

## 3. The design, in steps

Each step has its own switch, default off, and each removes host logic. Steps land in this order. Each one is tested with the step-5 test first, then on the second title (the regression baseline, lean e3fd8b55 and its successors), and only then on the third.

### (a) A fixed guest queue → hardware queue binding — `BC5_0443_PIN`

- **Kernel side:** see section 4. The patch pins a compute entity to `scheds[ring]` and allows 8 entities.
- **Host side:**
  - a table guest queue → libdrm ring index, given out in order of first use, at most 7 normal rings;
  - over 7 queues, the least recently used queue that is idle shares (journalled; every share is a known risk, see deadlock D2).
- **Check:** HW_ID2 in a probe dispatch (exp 0427's tool) confirms the queue id per index once per run.
- **Removes:** way 2's move counter and its "not idle in 2 s" guard (`w428c`). Each queue's state is re-sent before every acb part (aq424, F846) only because a queue could move. With pinning the state goes in once per queue and on change (behind a sub-switch, since the HQD keeps COMPUTE_USER_DATA through the MQD preload; exp 0427).
- **Deadlock avoided:** D2, a waiter and its writer on one ring.

### (b) Every WAIT_REG_MEM kept for the GPU — `BC5_0443_KEEP_ALL`

- Keep every top-level and every piece wait, on every ring.
  - This means no "satisfied at submit, drop" (the keep rule, `:7852`) and no `self_waits_only` (`policy.hpp:151`, rule at `policy.cpp:526-542`).
  - It also means no dcb wait split (exp 0132 form, SPLIT_LATE).
- The filter still rewrites what it must for our hardware (addresses, GDS, register remaps). It no longer judges waits.
- Needs (a), and needs (c) at the same time. With (b) alone the host's holds deadlock (F902).
- **Removes:**
  - the keep and drop offset lists;
  - `ring_will_satisfy` (`:10577`);
  - the writer scan (`register_label_writes`, `:9700`, F899);
  - the split code;
  - candidate G (`BC5_0439_KEEP_XQ_WAITS`) and pw439 (`BC5_0439_PIECE_WAITS`), both subsumed.

### (c) Host holds and submit-time decisions off — `BC5_0443_NO_HOLDS`

- Submit every guest buffer to its queue's ring at once, in the title's order, and from the title's own submitting thread without blocking it.
- **Off:**
  - `acb_ready` holds (`:8055`);
  - the ng438 gate and wd438's "writer in flight";
  - r438's early registration;
  - F848's XQ presets and fence;
  - `chain_given_up_at`;
  - every "hold the thread until the label" path.
- The only waits left on the host are for its own resources (BO memory, the ring's credit), never for a guest label.
- **Removes:** all of the above, and with them F899's blindness, because nothing reads the pending-write table any more.
- **Deadlocks avoided:**
  - D1: F902's hold against a kept GPU wait;
  - D3: the geyser cycle of ADR 0009:138. The title rings the counter queue's doorbell only after it has submitted the graphics buffer that waits on the counter, so a host that blocks the title's thread in that submission never sees the writer.

### (d) What stays with the host

Labels that only the CPU or the host writes on the console's side:

- **Flips:** the flip label, and the display's "flip done" (`console-vs-host.md` §1).
- **EOP idents** the host emulates instead of the GPU's own EOP write, where the guest's RELEASE_MEM is rewritten.
- **AGC interrupts and events** the host turns into label writes.

Rules:

- **Write them as the console does:** to the label's memory, from the CPU, with a release store. Never hold a GPU job until the host has written one.
- **Visibility to a GPU wait:**
  - WAIT_REG_MEM polls memory through the CP, bypassing the GPU's caches for the poll (TODO(verify): gfx10 CP polling of system memory; the PM4 doc's `CACHE_POLICY` field and our F-row on it).
  - The labels live in GTT, cached and snooped on this APU (TODO(verify): the BO's domain and flags in `direct.cpp`). A CPU store therefore becomes visible to the next poll without a flush.
  - The poll interval is the packet's POLL_INTERVAL; ours is TODO(verify) from the filter's rewrite.
- **GPU-written labels a CPU thread waits on** (the title waiting on an EOP): those are read by the host, which polls or uses the job fence. The GPU's RELEASE_MEM with its cache action makes them visible.

So (d) is a short list of writers, none of which ever blocks a ring.

### Deadlocks possible here but not on the console

| id | deadlock | why the console cannot have it | which step removes it |
|---|---|---|---|
| D1 | a host hold against a kept GPU wait: the dcb waits on the GPU for an acb's label, and the host holds that acb until a later label of the dcb (F902) | nothing outside the GPU holds work | (c) |
| D2 | waiter ahead of its writer on one kernel ring (two guest queues share a ring, or an entity re-picks onto the waiter's ring) | each guest queue has its own hardware queue | (a), and the kernel patch |
| D3 | the host blocks the title's thread in a submission whose wait's writer the title submits later (geyser cycle, ADR 0009:138) | submission never blocks | (c) |
| D4 | ring credit: 2 jobs on the hardware; a third job, which is the writer, is in software behind a polling waiter on the same ring | no software depth limit per queue | (a) with one queue per ring. The waiter and its writer are never in one ring's FIFO, because a queue's own later work never writes what its earlier work waits for. Depth is raised (`sched_hw_submission`, section 4) only so a busy queue is not starved. |
| D5 | the kernel's job timeout kills a legitimate long wait and resets the GPU | no job timeout | the compute timeout (2.6) |
| D6 | a host-written label (d) written only after something the host waits for on the GPU | the console's CPU writes are independent of the GPU | (d): host writes never depend on a ring |

D2 with the stock kernel is the reason way 2 still needs splits and holds. It is what section 4 removes.

## 4. What cannot be had with the kernel as it is, and the smallest change

What cannot be had:

- No more than 2 pinned compute queues (`num_kcq=2`). A pinned queue for each of 4-8 guest queues is impossible.
- Any entity may re-pick onto a ring where another queue's job polls (D2).
- Without a module parameter, the 2-jobs-in-flight limit and the 2 s timeout also stand.

The smallest change, a patch to `D/amdgpu_ctx.c` alone:

1. In `amdgpu_ctx_init_entity`, for `AMDGPU_HW_IP_COMPUTE` with `ring < num_scheds`, use `scheds = &scheds[ring]; num_scheds = 1;`. This is the VCN/UVD branch at `:246-255` with a fixed index instead of `pick_best`. A single-scheduler entity never re-picks (`sched_entity.c:583`, `:612`).
   - Behind a new module parameter `amdgpu.compute_pin=1`, default 0, so every other client keeps load balancing.
2. `amdgpu_ctx_num_entities[AMDGPU_HW_IP_COMPUTE] = 8` (`:37`), so 7 normal queues can be addressed. The ctx's entity array is sized by `AMDGPU_MAX_ENTITY_NUM`, which is 4 (`D/amdgpu_ctx.h:37`, used at `:59`), so it also goes to 8.

Module parameters, no patch:

- `amdgpu.sched_hw_submission=8` or `16` (a power of two). This allows depth on the hardware per ring, so a queue's own later jobs sit in its HQD's ring buffer behind its waits, as on the console. It applies to all rings; the ring buffer grows with it (`amdgpu_ring.c:338`).
- `amdgpu.lockup_timeout=10000,60000` (or `10000,-1`), see 2.6.

The patch and the parameters are a kernel/system change on the box. They need the maintainer's word (a kernel package on an rpm-ostree image, with undo). The patch is in the repo as `backend/kernel-patches/0001-amdgpu-compute-pin.patch`, with how to build and load it in that directory's README; no build applies it (the top's answer of 2026-11-22). User queues and KFD: no (2.5).

Until the patch exists, steps (b) and (c) can run with **stock pinning by isolation**: at most as many guest queues as there are idle rings, with nothing else on the box using compute. Exp 0427 showed that an entity with work in flight stays on its ring. D2 can still happen when a queue goes idle and comes back, so on the stock kernel (b)+(c) is a test arm, not a play setting.

## 5. A first test that needs no title

The tool: `dispatch-min`'s compute-ring path (exp 0439's extension on its branch, tag `id439`), or `userdata-rings` (exp 0427, `backend/experiments/userdata-rings/`), extended. Both sit behind `--submit`, default off, never in CI. **Risk:** a GPU hang leads to the kernel's reset, and on the BC-250 a reset may take the machine down (R55/R60: after any GPU kernel line, no further run on that boot).

Each job is one IB:

- **W (waiter):** WAIT_REG_MEM `== 1` on label L in GTT, then a probe dispatch that stores HW_ID2 and a timestamp, then RELEASE_MEM of its fence.
- **R (writer):** a probe dispatch, then WRITE_DATA L = 1 (or RELEASE_MEM to L).
- **B (behind):** a probe dispatch only.

Arms. Each runs on two libdrm compute indexes, then twice more in separate contexts:

| arm | order | expected on the console model |
|---|---|---|
| T1 | R on ring 1, then W on ring 0 | W passes at once |
| T2 | W on ring 0, then R on ring 1 | W waits until R; both complete |
| T3 | W on ring 0, B on ring 0, then R on ring 1 | B completes after W (same queue order) |
| T4 | W on ring 0, B on ring **2**, then R on ring 1 | B completes before R is even submitted (a waiter blocks no other queue) |
| T5 | W, then R 500 ms later from the CPU (WRITE to L by the host, case (d)) | W passes within a poll interval of the CPU store |
| T6 | as T2 with R delayed 3 s | passes only if the compute timeout is above 3 s; shows the timeout's effect |

Each arm records:

- which HQD each job ran on (HW_ID2's queue and pipe ids);
- the start and end time of each job;
- whether a stock-kernel arm put W and R on one ring. That outcome is D2 in the wild, and the tool reports it instead of hanging: R is submitted only after W's HW_ID2 has been read, and if they match, R goes to another index.

On the stock kernel, T2-T4 show how often D2 happens. With the patch every arm must pass with W, R and B on the HQDs their indexes name.

This test runs on the box only with the top's GO, after exp 0439 has given the box back. It is the first box step of this experiment.

*Amended 2026-11-22 (agreed with exp 0444, which writes the one kit as `backend/experiments/wait-rings/` on `exp/0444-gpu-waits`).* The pre-read above is replaced: W's probe runs only after its wait, so its HW_ID2 does not exist before R is submitted, and a probe ahead of the wait would need a hand-encoded EOP with an L2 writeback.

The kit works this way:
- It submits every job, polls the fences every 1 ms, and rescues a stuck waiter with a CPU write of L 3 s after the last planned write. It stops with STUCK after 6 s.
- It then reads all HW_ID2 values and reports COLLISION, RESCUED, or AS EXPECTED / UNEXPECTED.
- A collision costs 3 s, never the kernel timeout.

The rescue depends on T5's answer (a CPU store reaching a polling wait), so T5 runs alone first, and nothing else runs if it fails. T6's writer delay is shorter than the rescue.

Added arms:
- T7: a 1000-round two-thread race, with a pair histogram, and a variant with a host lock around both ioctls (expected: 0 shared pairs).
- T8: a HIGH-priority context.
- GFX waits on compute and the reverse.
- A writer queued behind its own waiter on one entity.
- A three-ring pipe case.

## 6. The best mapping on the stock kernel, and how safe it is

The cites are at v7.3.4. `S` = `drivers/gpu/drm/scheduler`.

**Verdict first: it cannot be made safe without the patch.** It can be made to work unless one of two things happens:

- **(i) all 7 normal-priority compute rings hold unfinished work at the moment a guest queue's idle entity submits;**
- **(ii) two submissions race.** That race is closed only if the host makes every compute CS ioctl one at a time, and even then a window of a few instructions at job completion remains.

The second title (2-3 busy queues) and the first title (3 busy) are far from (i). The third title (7 or more queues) is at it.

How placement works:

- **The score is the number of unfinished jobs.**
  - `drm_sched_entity_push_job` increments the chosen ring's score (`S/sched_entity.c:642`), and `drm_sched_job_done` decrements it (`S/sched_main.c:169`).
  - The compute rings are created with no shared score (`gfx_v10_0.c:4709-4710`, `NULL`), so each ring counts its own jobs: queued in software plus on the hardware, from every context of every process.
  - `drm_sched_pick_best` takes the ring with the lowest score. On a tie it takes the first in list order (strict `<`, `S/sched_main.c:976`).
  - The list order is the ring creation order (`amdgpu_ring.c:380-381`): comp_1.0.1 first.
- **When a pick happens.** `drm_sched_entity_select_rq` runs in `drm_sched_job_arm` (`S/sched_main.c:644-650`). It re-picks only when the entity has no queued job (`S/sched_entity.c:587`) and its last job's fence has signalled (`:601`). A busy entity never moves.
- **A ring that holds a polling job** has score ≥ 1 for as long as the job polls. An idle entity therefore goes there only if no ring has score 0, or every ring has as many unfinished jobs as that one.
- **One entity per guest queue, over several contexts.** Index *i* of context *c* is one entity, and all of them share the same 7-ring list. More contexts give more entities, not more rings and not a pin. With 7-8 guest queues one context holds 4, a second the rest.
  - This is the mapping way 2 uses today (exp 0428).
  - It is as good as the stock kernel allows, because the guest queue → entity map never changes. Only the entity → ring map does.

Why sharing is impossible under three conditions:

- (a) the host submits compute CS ioctls one at a time;
- (b) at most 7 guest compute queues hold work at once;
- (c) no other process submits compute work. RADV does not use the gfx1013 compute queue (F6); KFD is not used.

Sketch, by induction over picks. Suppose no two entities with unfinished work share a ring. When an idle entity picks, at most 6 other entities have unfinished work, so at least one ring has score 0. pick_best takes a score-0 ring, which no other unfinished entity is on. So after the pick, sharing is still impossible.

The holes in the sketch:

1. **The arm/push race.** The pick (`amdgpu_cs.c:1301`, arm) and the score increment (`:1381`, push) are apart, and between them run the fence and BO checks under `notifier_lock` (`:1327-1387`). Two CS ioctls from two threads can both read the same score-0 ring and both take it, because ties go to the first ring. Our host submits from more than one thread since exp 0436 (the kernel submit outside the device mutex, F864). So today this race is open. Closing it means one host lock around every compute CS ioctl. That costs the concurrency exp 0436 bought (TODO: measure; only the compute submits need it, the GFX ring has one entity).
2. **The completion window.** `drm_sched_job_done` decrements the score (`S/sched_main.c:169`) before it signals the finished fence (`:174`). In between, the finished entity still counts as "staying" (`S/sched_entity.c:601`) while its ring already reads 0. Another entity can pick that ring, and the first entity's next job then stays on it too. The window is a few instructions wide, but it is not closed by anything the host can do.
3. **(b) fails for the third title.** With 7 or more queues holding work at once, an idle entity can find no score-0 ring. It then joins the ring with the fewest jobs, which may hold a polling waiter.

What a collision costs:

- **Writer ahead of its waiter on the shared ring:** only lost concurrency.
- **Waiter ahead of its writer:** the waiter polls forever, its HQD runs nothing else, and the writer sits behind it in the same FIFO. After `lockup_timeout` (10 s on the box) the kernel resets the GPU. On the BC-250 that may take the machine down (R55/R60, F412). So every collision of that order is a lost session.

Does priority or `sched_hw_submission` change it?

- **Priority.** A HIGH-priority context's compute entities get the high-priority ring set, comp_1.0.0 alone:
  - HIGH maps to `AMDGPU_GFX_PIPE_PRIO_HIGH` = `AMDGPU_RING_PRIO_2` (`amdgpu_ctx.c:119-121`, `amdgpu_gfx.h:56`);
  - only compute ring 0 has that priority (`amdgpu_gfx.c:195-206`, `gfx_v10_0.c:4706-4707`);
  - a one-scheduler entity never moves (`S/sched_entity.c:583`, `:612`).

  That is one guest queue fully pinned and alone, e.g. the queue whose labels the dcb waits on most. Cost:
  - the emulator needs CAP_SYS_NICE (`amdgpu_ctx.c:107`), a file capability on the binary set with the maintainer's sudo, or running as DRM master, which it is not;
  - all 4 entities of that context share comp_1.0.0, so only one guest queue may use that context;
  - its HQD runs at high pipe and queue priority, ahead of the GFX-side compute work, which changes timing (TODO(verify) on the second title).
- **`sched_hw_submission`.** It sets how many jobs each ring lets onto the hardware, not where an entity goes, so it does not change sharing. It does decide how a busy queue's later jobs wait: in software, or on the HQD's ring behind its own wait, which is the console's order. With pinning, 8 or 16 lets a queue run ahead as on the console. Without pinning, more depth on a shared ring only puts more of another queue's work behind a waiter.
- **`num_kcq=2`:** one normal ring, so every normal entity shares it. Worse, unless only one guest queue is normal-priority and one is HIGH (2 queues in all).

**The stock mapping to use until the patch:**

- one entity per guest queue, given out in first-use order over as many contexts as needed;
- every compute CS ioctl under one host lock;
- optionally the most-waited-on guest queue alone in a HIGH-priority context, if the maintainer grants CAP_SYS_NICE;
- the host reads HW_ID2 nowhere (no per-job probe in play). It logs only the count of guest queues with work at once, and warns when that count reaches 7.

This is "works unless 7 queues hold work at once or the completion window hits". The second title and the first title are well inside it. The third title is not.

## 7. Kernel arguments to put to the maintainer

All are his to set (`rpm-ostree kargs`); undo is `--delete=` of the same string.

| argument | value | reason |
|---|---|---|
| `amdgpu.lockup_timeout` | `10000,60000` (GFX 10 s, compute 60 s; SDMA and video keep the default) | A kept GPU wait on a compute ring may legitimately last a loading stall. The GFX ring keeps 10 s, so a real graphics hang is still reset (and dumped, F903) in 10 s. `-1` for compute (never) would leave a true compute hang to the host's catcher alone; not proposed. |
| `amdgpu.sched_hw_submission` | `8` (power of two, `amdgpu_device.c:1616-1623`) | Only with the patch: lets a pinned queue's later jobs sit on its own HQD behind its waits (the console's order) instead of in software. Without the patch it changes nothing about sharing; leave it at 2. Ring buffers grow 4× (`amdgpu_ring.c:338`): 8 jobs × max dwords per ring; memory cost TODO(verify), small next to the 512 MiB carve-out. |
| `amdgpu.compute_pin` | `1` | Only with the patched module (`backend/kernel-patches/0001-amdgpu-compute-pin.patch`). An unknown parameter on the stock module is ignored with a log line. |

The patch option, in one line for him: a 28-line change to amdgpu, default off, built out of tree against `7.3.4-ogc8.1`. It is loaded first per boot through `rpm-ostree usroverlay` (gone at reboot), then persistently as a layered kmod with a rollback deployment. It must be rebuilt for every new kernel; without the rebuild the stock module loads and the host falls back to section 6. Details in `backend/kernel-patches/README.md`.
