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

**Verdict.** Open. The JSON contract is fixed and the game renders its first own scene; the
next limit is the graphics driver's memory accounting, not the GPU path and not a missing
library.
