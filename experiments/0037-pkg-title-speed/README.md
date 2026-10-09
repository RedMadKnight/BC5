# 0037 — the second title from 7 to 24 fps

**Question.** After experiment 0036 the second title (started from its PS5 package) renders its
first 3D scene at 6.7 fps. Where does a frame go, and how much of it is the host's? The
maintainer also reported that the title runs at about 20 fps in KytyPS5: what does KytyPS5 do
that the host does not?

**Setup.** BC-250, the track-B host (KytyPlus f266548 + patch 0001 at this commit, the backend at
this commit), the title's package through `bc5-mount`. Launcher `run-pkg.sh` here (new knobs:
`EAGER_NAMES`, `LEARNED`, `PRINTF_DIR=Silent`; screenshots up to 600 s) with
`PACK_DIR=~/bc5-data/sysmodules-pack-hle-ampr`, the guest log off, an automatic cross press every
30 s from 120 s. Unattended runs 50–60 of 420–600 s, 2026-10-09 11:30–13:30. Measurement: the
direct path's per-frame profile (`BC5_DIRECT_FRAME_PROFILE`) summarised over a time window by
`frameprof.py`; the threads' stacks sampled by attaching gdb once a second (`pc-sampler.sh`).
KytyPS5 (github.com/KytyPS5/KytyPS5 at 7b9997b, GPL-2.0; KytyPlus's libAmpr shares 43 function
names with it) was read for its AMPR, ATRAC9 and system-service changes since KytyPlus forked.
ASTRO BOT regression: run 149 (420 s). Desktop shortcut and `play-pkg.sh` (here) for playing.

**Result.** The frame, in the title's first 3D scene, after each change (medians):

| Run | Change | fps | frame ms | host sync ms | outside the host ms | GPU ms |
|---|---|---|---|---|---|---|
| 50 | (0036: the title's GPU heaps imported eagerly) | 6.7 | 147 | 34 | 100 | 11 |
| 54 | the direct path's views cached per change of the guest's ranges; APR queues per priority | 8.3 | 117 | 25 | 79 | 11 |
| 57 | the device keeps its mapping list sorted, rebuilt only when a mapping changes | 12.8 | 75 | 26 | 37 | 11 |
| 60 | private-memory views cached too, found by binary search | 24.2 | 39 | 8 | 18 | — |

What each change removed:

| Change | Evidence before | Where |
|---|---|---|
| Views of direct memory built once per change (`Bc5MappedRangesGeneration`, a counter every mutator of the guest's ranges bumps) instead of on every sync | 11,500 views (most of them the title's AMM pages) rebuilt with their names on every sync: 51 ms of every 128 submissions | `memory.cpp`, `bc5LleAgc.cpp` `direct_views` |
| `Device::sorted_mappings()`: the device's 12,000 mappings sorted once per change | every submission copied and sorted the list on the ring thread; the game's render thread waited on that thread (15 of 40 samples in a mutex), counted as "outside the host" | `backend/src/direct.cpp`, `submit_one` |
| Private-region views cached, the range of each region found by binary search | each sync walked all 11,600 ranges for each of 140 regions and copied them (8 of 40 ring-thread samples, 6 of 40 render-thread samples) | `Bc5ForEachPrivateRegion`, `direct_views` |
| APR submissions queue per priority, as KytyPS5 c045f08 does | one queue for all: a submission waiting on an address held every priority behind it | `libAmpr.cpp` |

Also in this round, for stability rather than speed:

| Change | Why | Source |
|---|---|---|
| AMM pages named `AMM`; `EAGER_NAMES` includes them | GPU faults at AMM addresses (0x81…) the direct path had imported only where the CPU wrote | — |
| Zero buffer under holes the guest has no range in: learned fault windows, and 2 MiB after each eagerly imported heap of 32 MiB or more (`BC5_DIRECT_GUARD_KIB`, `BC5_DIRECT_NO_SCRATCH`) | the GPU reads up to 64 KiB past the end of the title's heaps (faults at 0x12bb004000, 0x12bb006000, 0x12bc001000, 0x12c4610000); each fault is a 14 s freeze, and twice the title crashed after one | — |
| ATRAC9 channel configurations 6–7 translated to mono / dual mono instead of rejected | they are vibration layouts; decoding them gives the title its haptics streams | KytyPS5 b10bd53 |
| `SystemServiceReceiveEvent` delivers an entitlement update after `AppContentInitialize` | the title's entitlement query thread waited forever | KytyPS5 62643c3 |
| Separate learned-fault files for the two titles (`BC5_DIRECT_LEARNED` in `run-pkg.sh`); 51 of the second title's entries removed from ASTRO BOT's | the files had been shared | — |

ASTRO BOT after all of it (run 149, 420 s): in play at 53 fps (frame 18.5 ms), one transient
EBUSY on a state replay, as before.

Not solved, stability. Of runs 51–60 three went their whole length without a fault (54, 55,
57; 480–600 s). The others stopped: three after a GPU fault at an address no mapping could
explain (51: 0x5ec72eb81000, 59: 0x12565686f000, 60: 0xc012ce73a000 at about 400 s; a pointer
read from data, not a page next to one), in run 59 after an async-compute queue had waited 3 s
on a value that never came (`bc5-q`, 0x12004b53c8 equal to 0); two after faults just past a heap
before the zero buffer existed (52, 58, the latter followed by a null read in the title); one
after a timeout without a fault (53); one at a null read in the title at +0x3d5cb8c (56). The
scene stays the same title backdrop through the presses; whether the title's menu should be
visible there is not known.

**Verdict.** Passed for speed: a frame of the first 3D scene went from 147 ms to 39 ms and the
title runs at 24 fps where it renders, the rate reported for KytyPS5; the host's sync went from
34 to 8 ms a frame. Open: the faults at garbage addresses and the cross-queue wait that stop the
title after some minutes.
