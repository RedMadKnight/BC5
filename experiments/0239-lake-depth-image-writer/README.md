# 0239 — The night lake: the pass that writes the water's slot-4 image

**Question.** Exps 0237/0238 (F296, F297) found the screen's patchwork in the slot-4 image that the
water's vertex stage reads (0x113cb40000, a 16_FLOAT depth image), only in patched frames. The water
draws don't write it; a host hint names it as `CB0` of some other draw. Which pass writes it, with
which shaders and inputs?

**Setup.**
- BC-250 dev box, 2026-10-23, granted by the top session: at most two bench runs, J1 at 18:48–18:54
  and J2 at 18:56–18:59, then short analysis locks until 19:01. Boot 31c1a6ac, unchanged;
  `/var/home` at 69 % throughout.
- `ab0239.sh <tag> "<journal switches>"` is exp 0238's driver, one run per call, with the same
  conditions:
  - the exp 0194 build (comm `kyty_emulator`) and its launcher copy with the old values;
  - `KYTY_BC5_AMM_TRACE=1`;
  - the 3-s `dmesg` poll that stops the run on any new amdgpu fault, timeout or reset line;
  - `/var/home` under 80 %, and the live saves checksummed before and after.

  It ends with the journal's size and `jr0239.py`'s summary. `bench0239.sh` is exp 0235's bench,
  renamed: 26 frozen-view shots for the patch share, no image dumps. The kernel log was streamed to
  the laptop, and each game shot was checked live.
- The draw journal (patch 0001):
  - `BC5_DIRECT_DRAW_JOURNAL=<t0>:<N>` with no filter journals every draw and dispatch of the next N
    graphics pieces from t0. A piece is a graphics buffer, or a part of one between two waits. Each
    line gives colour target 0, `CB_TARGET_MASK`, the viewport, the shader programs and the packet.
  - `_PS=<prefixes>` journals only the draws with those pixel shaders, and adds their user data and
    descriptor tables.
  - `_FIND=<hex>` flags each draw or dispatch whose user data, or the 64 dwords behind a user-data
    pointer, holds the value. Here that is `113cb400`, the slot-4 image's base as a T# stores it.
- K1's journal showed 12–19 graphics buffers per frame (median 14), so run J1 used
  `BC5_DIRECT_DRAW_JOURNAL=165:14 BC5_DIRECT_DRAW_JOURNAL_FIND=113cb400`.
- Run J2 used `BC5_DIRECT_DRAW_JOURNAL=150:8 BC5_DIRECT_DRAW_JOURNAL_EVERY=15
  BC5_DIRECT_DRAW_JOURNAL_PS=11d0160b00,11d015f100,11d01ff900,11d01d7100
  BC5_DIRECT_DRAW_JOURNAL_FIND=113cb400`: J1's writer and downsampler and both water shaders, for
  their descriptors and order.
- `jr0239.py` lists the journal's passes in order, the draws into the target and the `_FIND` hits.
  Exp 0212's `desc0212.py` decodes the image and buffer descriptors of the filtered draws.
- Format names come from Mesa `src/amd/registers/gfx10-rsrc.json` @ 0866ae7, `GFX10_FORMAT`:
  13 16_FLOAT, 22 32_FLOAT, 29 16_16_FLOAT, 56 8_8_8_8_UNORM, 71 16_16_16_16_FLOAT, 175 BC4_UNORM.
  That settles the format-56 TODO in exp 0235's `img0235.py`.

**Result** (`raw/J1.*`, `raw/J2.*`, `raw/kernel-stream.txt`).
- **Box state.** No kernel fault, timeout or reset: the amdgpu count stayed at 578, both runs' `.out`
  have 0 fault lines, and the streams have only routine lines. The live saves' checksum was the same
  before and after both runs (f6475842373bf369). The runs wrote about 250 MB: J1 a 79 MB run
  directory and an 88 MB journal, J2 28 MB and 54 MB. No image was dumped.
- **J1 loaded the lake save and was clean throughout (0.6–0.9 %).** The unfiltered window held 190
  draw-journal lines (41.8 KB) and one `_FIND` hit.
  - The 14 "buffers" were the wait-split pieces of one 17,909-dword submission at t 165.0. That is
    one of about 14 submissions in the frame, not a whole frame: the water's main draws (PS
    0x11d01ff900) are in another submission.
- **The writer** is one full-screen `DRAW_INDEX_AUTO`: ES 0x11d00be800, PS 0x11d0160b00,
  `CB_TARGET_MASK` 0xf, colour target 0 = 0x113cb40000 at 3072×1728.
  - In that submission it follows the G-buffer draws (colour target 0 = 0x113f230000, mask 0xfffff,
    five targets), the water's full-screen draw (PS 0x11d01d7100) and a run of depth-only draws
    (mask 0).
  - Right after it come two more full-screen draws: PS 0x11d015f100 into 0x113a7a0000 at 1536×864
    (mask 0xff), then PS 0x11d015f600 into 0x113ab20000 at 768×432 (a downsample chain).
  - The one `_FIND` hit is PS 0x11d015f100, holding the image's base in user-data dword 0.
- **J2 failed to load.** Its game shot showed the title's Continue Game menu; the scripted input
  missed the load. Its emulator was stopped at 18:59:30, so it has no lake frames. The menu's
  background scene uses the same shaders, though: the PS-filtered journal recorded 27 full-screen
  draws over 16 pieces.
  - In every journalled menu frame the water's full-screen draw (into 0x113f230000) comes just
    before the writer (into 0x113cb40000).
  - **The writer's inputs** (pixel stage): slot 2 = 0x113f230000 as **32_FLOAT**, the colour target
    the G-buffer draws and both water draws render into; slot 4 = 0x1140a90000 as 16_16_FLOAT.
  - The downsampler (PS 0x11d015f100) reads 0x113cb40000 (16_FLOAT) and 0x1140a90000.
  - `_FIND` found 148 reads of the image: compute dispatches through descriptor tables (user-data
    dword 12, several shaders), draws through user-data dword 28 (PS 0x11d1c3f800, 55 times) and
    the downsampler. It is a linear-depth image that many later passes use.

**Verdict.**
- **The slot-4 image is a linear-depth image.** One full-screen pass (PS 0x11d0160b00) makes it
  every frame from the 32-bit float G-buffer target 0x113f230000 and a 16_16_FLOAT image. It then
  feeds a downsample chain and many later passes.
- **The water writes into the writer's input.** Both water draws render into 0x113f230000, and the
  writer reads it (shown in the menu scene, same shaders and addresses). With F297, this suggests a
  per-frame loop: the water's vertex stage reads a depth image made from what the water wrote. That
  would fit a state that holds for seconds and flips now and then.
- **Open:**
  - The writer's inputs in a lake frame. The addresses are the same as in the menu, but that is not
    shown.
  - The order within a lake frame: do the water's main draws read this frame's image or the
    previous frame's?
  - Whether 0x113f230000 itself carries the far cells in patched frames.
- **Next:** one run with J2's filter that reaches a patched lake frame, for the writer's inputs and
  the order. Then, if wanted, one dump of 0x113f230000 in a patched and a clean frame.
