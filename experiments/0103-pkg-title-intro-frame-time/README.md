# 0103 — where the second title's intro frame goes: 9 ms of host sync (fixed) and one 34 ms buffer

**Question.** The second title's start-up logo movie runs at about 17 fps. The same logo in
ASTRO BOT runs at 60. Where does the frame time go: the movie's pace, host work, or the GPU?

**Setup.**
- Run 372 (2026-10-14 23:10, maintainer present) had dumped the intro's buffers (`BC5_DIRECT_IB_DUMP`,
  private, `~/bc5-data/captures/ibdump-372`).
- Unattended, intro only, 40 s each, the play shortcut's settings (undeferred flips, `multi`,
  aliases), a fresh save, no input:
  - run 373 (23:17): `BC5_DIRECT_DRAW_JOURNAL=30:60` (CPU side only);
  - run 374 (23:20): `BC5_DIRECT_SKIP_PGM=11d03f7900` (the 4K temporal anti-aliasing dispatch)
    plus the new `BC5_DIRECT_REMEMBER_UNMAPPED=1`;
  - run 375 (23:26): `BC5_DIRECT_REMEMBER_UNMAPPED=1` alone.
- Tools in this directory:
  - `markers.py`: lists per dumped buffer the title's pass-name markers (SET_UCONFIG 0x342 plus
    WRITE_DATA to 0xc343), waits, dispatches and draws;
  - `jobfence.py`: sums each buffer's submit-to-done time (fence) per frame from the
    `BC5_DIRECT_TIMING` journal;
  - `frameprof.py`: summarises the frame profile lines.
- New host knob (patch `0001-bc5-lle-agc.patch`, off by default): `BC5_DIRECT_REMEMBER_UNMAPPED=1`.
  - Before, a light buffer (no draws, dispatches or nested buffers) with an unmapped operand forced
    the full sync walk over the guest's VMAs.
  - With the knob, the pages that a forced sync left unmapped are remembered for 2 s. A later light
    buffer whose only unmapped operands lie in those pages does not force the walk again.
  - The packet is dropped either way, so the GPU stream is the same. Only host time changes.

**Result.**

The intro is not a movie player. Behind the logo the title runs its whole renderer every frame:
- shadow maps, water, ray-traced reflections and global illumination;
- tone mapping, temporal AA and the upscale to a 3840×2160 display buffer.

Frame time (median, 20–38 s of the intro):

| | run 372 | run 374 | run 375 |
|---|---|---|---|
| fps | 16.9 | 18.6 | 18.2 |
| frame | 62 ms | 53 ms | 54 ms |
| game thread inside the host | 14.9 ms | 6.7 ms | 6.7 ms |
| of it, sync | 9.2 ms | 0.2 ms | 0.2 ms |
| game thread blocked at the flip | 35 ms | 34 ms | 35 ms |
| fence of the post-processing buffer (1097 dwords) | 34.9 ms | 34.0 ms | 34.9 ms |

1. **Host sync, 9 ms a frame, removed.** The 84-dword graphics buffer submitted right after every
   flip has one operand in a host page (0x7f…) that is never mapped for the GPU. Each frame this
   forced the full sync walk (9.0–9.8 ms). With the knob: one walk, then the page is remembered
   ("remember unmapped: dcb 84 dwords, operand page 0x7f7385889000"), and sync drops to
   0.2 ms a frame. ASTRO BOT does not pay this cost (sync 0.1 ms a frame in its 09:21 run).
2. **One GPU buffer takes 34–35 ms, every frame, to within 0.1 ms.** It is the last
   post-processing buffer: tone mapping, temporal AA, upscale and radiance capture, with two
   3840×2160 dispatches and two 1280×720 draws.
   - Everything submitted before it has finished when it is submitted.
   - Everything submitted after it (the copy to the display buffer and the compute tails) ends at
     the same moment.
   - The game thread waits for it at the flip.
3. **Its time is not in the obvious shaders.**
   - Dropping the 4K temporal AA dispatch saved 0.9 ms (run 374).
   - The other programs in the buffer have 7–238 instructions and no loops or sleeps.
   - Its two waits are self-waits: a label set to 0, written to 1 by an end-of-pipe RELEASE_MEM,
     then waited for. The same pattern costs 0.15 ms in the scene buffer before it.
   - The completions do not follow the 60 Hz grid (phase concentration 0.18 over 334 frames),
     so this is not a vblank wait.
   - No GPU page faults in dmesg.
4. **It scales with the output resolution.** In the menu with the maintainer's lower settings
   (run 371, 2560×1440 output, journal of 20:37), the same buffer takes 18 ms and the whole
   menu scene 2 ms. 34 / 18 = 1.9, against a pixel ratio of 2.25.
5. The GPU governor (`cyan-skillfish-governor-smu`, range 1850–2000 MHz) patches `gpu_metrics`, so
   its activity (95–100 % during the intro) and clock readings cannot settle whether the GPU
   computes or waits during those 34 ms.

**Verdict.** Partly passed.
- The host's share is fixed: the knob removes 9 ms a frame (16.9 → 18.2–18.6 fps in the intro).
  It also applies to the menu, where the same buffer forced the walk (7.8–10 ms a frame in run
  371). The knob stays off by default until a full play-through with it.
- The rest is one post-processing buffer at 34 ms for work that should take a few ms. It scales
  with the output size, but not through the anti-aliasing shader.

Open, both need the maintainer present (new GPU behaviour):
- GPU timestamps between the buffer's passes (an end-of-pipe RELEASE_MEM to our own BO), to see
  which pass holds the 34 ms;
- or one `bc5-gpu-hang-dump` (umr, halts waves briefly) during the intro, to see what the CP and
  the waves are doing inside that buffer.

Candidates:
- a cache or TLB pathology on the 4K targets: guest memory is 4 KiB shmem pages (`shmem_enabled`
  is `never`, `amd_iommu=off`), so no large GPU fragments;
- a pass whose work depends on the output size in a way the shaders alone do not show.
