# 0020 — Past the intro: what the game needs from the host after its video (F43)

**Question.** With the GPU path carrying the game through its whole intro (experiment 0018, run
93), what stops it next, and can the host provide it without system modules (there is no firmware
dump to load any from)?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`; host as of experiment 0018 on
the dma-buf backing (`KYTY_BC5_DMABUF=1`), run command as in experiment 0017. Function names of
unresolved imports come from a public NID table (`ps5rs`, `data/nids.csv`).

**Result.**

*Run 93* (experiment 0018) ended in 124 calls to two unresolved `sce::Json` imports
(`Value::referValue(const String&)`, `Value::toString(String&) const`) and a null write.
KytyPlus has an HLE `Json2` library; it lacked those two and 26 more the game imports
(`Array`/`Object` iterators, copy constructors, setters, `getUInteger`, `String` comparisons).
All 28 were added (patch 0001, `libJson2.cpp`; layout assumptions for iterators and the object
iterator's pair are marked `TODO(verify)`). Without the GPU every `Json2` import resolves;
116 imports of other libraries remain unresolved (kernel 30, voice chat 17, audio propagation
16, …), none of them called so far.

*Run 94* (15:44, GPU): 14,199 submissions, none failed, 933 flips, the whole intro again. No
unresolved JSON call any more. The game now stops on **its own assertion**: in its network
module's JSON helper a value it expects to be a boolean has another type, and the assert handler
writes through a null pointer. Which document and which member is not visible in the log, so the
library got a trace (`KYTY_BC5_JSON_TRACE=1`: keys, types, parsed and produced text).

*Run 95* (16:39, GPU, `KYTY_BC5_JSON_TRACE=1`): the same end, now readable. The document is
one of the game's own data files, an array of objects; for each object the game reads its
mandatory members through `operator[]` and tests an optional one, absent from this file, with
`Value::referValue(key)` first. The added `referValue` created a missing member as null and
returned it, the game took that for "present", fetched the member through `operator[]` and
asserted on its type. So `referValue` is the game's existence test: it must answer **null for a
missing member** (a pointer return; the mangled name does not carry the return type —
`TODO(verify)`). Changed accordingly; no GPU run yet.

*Run 96* (16:44, GPU, the corrected `referValue`; capture `kytyplus-20261001-1644`,
`raw/run96-summary.txt`): **the game gets past that file and starts drawing its own scene.**
37 documents parsed, no assertion, no access violation, one unresolved import called once (a
keyboard-code conversion). 15,101 submissions, 997 flips. From submission 14,267 (87.6 s in) the
frame's main command buffer is a different one: 24,000–25,400 dwords, about 2,000 packets
passed, 16 context pushes per buffer, 15–17 ms on the GPU. What it draws is a star field with a
nebula, the backdrop of the game's first interactive screen (screenshots kept out of the
repository).

Two things happened to it:

1. *The first of these buffers timed out* on a write fault of the texture pipe at 0x559f05000,
   memory the CPU had never touched and no render-target register named. The fault region was
   learned and the device reopened; the reopen costs 14 s (12 s of waiting for the kernel's own
   timeout and ring reset, 2 s to import 5.4 GiB again), during which the game's loader threads
   kept filling memory.
2. *Five seconds and 43 good scene frames later every draw buffer failed with `-ENOMEM`* (49
   submissions; the kernel: `Not enough memory for command submission!`, `amdgpu_vm_validate()
   failed.`), and the game stalled waiting for its labels. At that point 6,780 MiB of direct
   memory were imported in 371 BOs, and a draw's BO list names all of them.

The mechanism, measured afterwards without the GPU (`mem_info_gtt_total`, `ttm` module
parameter, a map-only run with the breakdown below): everything a submission's BO list names
must sit in amdgpu's GTT domain at the same time. On the dev box that domain is 7,597 MiB —
exactly `ttm.pages_limit` (1,944,861 pages), which defaults to half of the RAM (`TODO(verify)`
against `amdgpu_ttm.c` of this kernel that the one is derived from the other). The emulator's
own Vulkan side already holds 1.2–1.6 GiB of it (57 MiB when the emulator is not running), so
the ceiling for the game's memory is about 6 GiB, and the game reserves 12.4 GiB of direct
memory. Short lists (ADR 0005 xx) do not help a buffer with draws: its shaders read through
descriptors the filter does not follow, so it lists everything.

What the host got for it (no GPU run yet):

- a journal line per 512 MiB of growth and on every `-ENOMEM`: imported memory by the name the
  game gave each mapping (reserved / holding data / imported), with the driver's GTT numbers;
- `BC5_DIRECT_LAZY_NAMES=name[,name]`: views with these names are imported only where a hint or
  a learned fault asks, not for holding data. The game's CPU heap (`orbis_user_malloc`, 2.0 GiB
  reserved) is the candidate: no command-buffer operand of run 96 points into it (113,034 into
  the GPU heap, 42,628 into the address range of the game's loaded modules, 31,636 into the driver library's memory). Whether
  shaders read it shows as learned faults.

Map-only run with the heap lazy, 45 s (intro stage): GPU heap 1,484 MiB with data of 2,172
reserved, texture memory 796 of 4,608, resource memory 366 of 3,232, CPU heap 617 of 2,014 (38
imported, by chunks it shares with small neighbours).

The lazy heap is a stopgap worth about a gigabyte. The remedy that matches the size of the
problem is outside the repository: raising `ttm.pages_limit` on the kernel command line, which
is the maintainer's decision on their machine. A third lever is the emulator's own share. Its Vulkan client (`fdinfo`, map-only run, 32 s in)
asks for 658 MiB of GTT and 700 MiB of VRAM; the 512 MiB carve-out holds 176 MiB of the
latter and the rest spills over, 1,183 MiB resident in GTT. What it keeps there in a mode
where it renders nothing but the presented frame is not looked at yet.

*Run 97* (17:09, GPU, `BC5_DIRECT_LAZY_NAMES=orbis_user_malloc`, 200 s; capture
`kytyplus-20261001-1709`, `raw/run97-summary.txt`): **27,273 submissions, none failed, no
fault, 1,866 flips — the game reaches its title screen and waits for a button.** After the
intro it renders, in real time, the studio's logo forming out of particles and then the title
with its prompt, over the star field: 933 scene frames in 113.5 s, 8.2 frames per second, the
main command buffer 14.1–22.8 ms on the GPU (median 15.8). The run ends on its 200 s limit.

No shader read the CPU heap: 677 MiB of it held data at the end and none of that was asked for
by a fault. Without it the imports end at 6,094 MiB; the driver's GTT counter stood at 7,327 of
7,597 MiB when 5,740 MiB were imported, so the title screen fits with a few hundred MiB to
spare. (One `Not enough memory for command submission!` in the kernel log during the run is not
ours — no submission of the host failed; the emulator's own Vulkan client retries on it.)
By name at 5,740 MiB: texture memory 3,236, GPU heap 1,670, resource memory 652, shared GPU
heap 126, CPU heap 46.

Where a scene frame's 122 ms go (70 s window, 8,039 submissions, about 14 per frame): 62 ms in
the device path — the submission ioctl 21 ms (1,173 BOs in a draw's list), waiting for fences
15 ms, the mapping sync 15 ms, the rest lists, hints and copying — and as much again outside it
(filter, journal and IB dumps, the soft CP, the game).

**Verdict (2026-10-01, 17:20).** Passed for its question: what stopped the game after the intro
was a host library's contract and then the driver's GTT accounting, both handled without system
modules; the game is at its title screen. Open after it: input (the screen wants a button), the
GTT ceiling once a level loads (F44), frame time (8 fps here against 12 in the intro).

**Addendum, run 98** (17:21, GPU, 400 s, the maintainer at the controller; capture
`kytyplus-20261001-1721`, `raw/run98-summary.txt`). Input works: a button press on the
DualSense takes the game off its title screen, a second one picks a save slot, and the game
starts loading its first level behind an animated tunnel (7–8 fps, from about 160 s; the audio plays at its proper
speed, the picture does not). 31,807 submissions without a failure up to there. At 246.6 s, with
6,444 MiB imported and the driver's GTT counter at 7,595 of 7,597 MiB, submissions start to fail
with `-ENOMEM` (277 by the end of the run); the loading screen keeps animating at under one
frame per second and the load does not finish. By name at that moment: texture memory 3,566
MiB, GPU heap 1,678, resource memory 1,018, shared GPU heap 126, CPU heap 46 (lazy; 728 with
data). Imports stop growing at 6,940 MiB. No save-data import is missing: one unresolved import
is called in the whole run, once, the keyboard-code conversion of run 96.

So the ceiling of F44 is what stands between the title screen and the first level; the lazy CPU
heap moved it by the 0.7 GiB it could.
