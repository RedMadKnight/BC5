# 0021 — The emulator's own share of the GTT domain (F44, F46)

**Question.** The game's first level does not load because its memory, plus what the track-B
host itself keeps on the GPU, exceeds the driver's GTT domain (experiment 0020, runs 96 and 98).
What does the host's own Vulkan side keep there on the direct path, where it renders nothing but
the presented frame, and how much of it can go?

**Setup.** BC-250 dev box, 2026-10-01, kernel `7.2.4-ogc3.1.fc44`, Mesa 26.2.3 (RADV). KytyPlus
`f266548` with patch 0001. Map-only runs (`BC5_DIRECT_STAGE=maponly`: the game's memory is
imported, nothing is submitted to the GPU by BC5), 60 s each, the game in its intro.
Measurements: the per-client `drm-*` lines of `/proc/<pid>/fdinfo` 30–50 s in; a trace of every
allocation the emulator makes through its allocator (`KYTY_BC5_VMA_TRACE=1`, added for this:
kind, bytes, description, callers as offsets for `addr2line`).

**Result.**

| Emulator's Vulkan client | asked as GTT | asked as VRAM | resident in GTT | resident in VRAM |
|---|---|---|---|---|
| as it was | 643 MiB | 684 MiB | 1,155 MiB | 172 MiB |
| fixed buffers 96/16/16/16 MiB | 291 MiB | 524 MiB | 675 MiB | 140 MiB |
| the same, allocator blocks of 16 MiB | 115 MiB | 253 MiB | 115 MiB | 253 MiB |

What it was (live allocations at the end of a run, 927 MiB):

- four fixed buffers of KytyPlus's buffer cache, created at start-up for its own renderer:
  staging 512 MiB, device-local 128, stream 64, download 64 — **768 MiB**. On the direct path
  only the staging buffer does work (the presented frame is uploaded through it, 32 MiB a
  frame); `KYTY_BC5_CACHE_MIB=staging,stream,download,device` sets their sizes.
- five 3840×2160 images, 160 MiB: three frames of the presenter, two textures of the game's flip
  buffers. Left as they are.
- the rest of the difference to what the kernel reports is slack: the allocator carves
  allocations out of blocks of up to 256 MiB per memory type, and what was asked as VRAM does
  not fit the 512 MiB carve-out next to the desktop, so it spills into GTT.
  `KYTY_BC5_VMA_BLOCK_MIB=16` makes the blocks small; larger allocations become their own.

With both, everything the emulator asks as VRAM fits the carve-out and its GTT share drops from
1,155 to 115 MiB. Presentation is unchanged in the map-only runs (the same 28–29 flips in 60 s).

*Run 99* (17:46, GPU, both settings, 400 s, the maintainer at the controller; capture
`kytyplus-20261001-1746`): **47,325 submissions, none failed, no `-ENOMEM`, 3,299 flips.** On
the GPU the emulator's client holds the same 115 MiB of GTT and 253 MiB of VRAM (`fdinfo`,
200 s in). The level load that ran out of GTT at 6,444 MiB imported in run 98 goes on: imports
reach 6,950 MiB about 90 s into the load and stay there, with the GTT counter at 7,286 of
7,597 MiB at the last report (6,760 MiB imported). Frame rate is steady at 7.4 fps to the end.

The loading screen itself does not end within the run (226 s of it). The game is not idle
behind it: from the moment the imports stop growing it looks assets up at a steady 52 file
`stat` calls a second — 834 names, each tried once in eight directories and two extensions,
none found — which is about three assets a second. A missing file costs 3 ms on the mount, so
the pace is the game's, not the file system's; whether it is tied to the frame rate and whether
the list ends is for a longer run.

**Verdict (2026-10-01, 18:00).** Passed: about 1.0 GiB of GTT given back to the game by two
settings of the host, and with it the first level's load no longer hits the ceiling (about
0.3 GiB to spare at the point reached). Open after it, outside this experiment: the load does
not finish in four minutes.
