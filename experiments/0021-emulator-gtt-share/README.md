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

**Verdict (2026-10-01).** Passed without the GPU: about 1.0 GiB of GTT is given back to the
game by two settings of the host. Whether that is enough for the first level to load is for
the next GPU run (`KYTY_BC5_CACHE_MIB=96,16,16,16 KYTY_BC5_VMA_BLOCK_MIB=16` added to the run
command).
