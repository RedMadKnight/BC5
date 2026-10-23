# 0240 — The night lake: frame order around the linear-depth pass, and the G-buffer's holes

**Question.** Exp 0239 (F298) found that the water's slot-4 image is a linear depth made by one pass
(PS 0x11d0160b00). In the menu scene that pass reads the G-buffer target 0x113f230000, which the
water draws render into. That suggested a per-frame loop. In a lake frame:
- what does the writer read?
- do the water's main draws read this frame's linear depth or the previous frame's?
- does the G-buffer target itself carry the patchwork?

**Setup.**
- BC-250 dev box, 2026-10-23, granted by the top session: up to two runs, the second only if the
  first lands in a menu. One run, Q1, 19:04–19:11, then an analysis lock until 19:13. Boot 31c1a6ac,
  unchanged; `/var/home` at 69 %.
- `ab0240.sh` and `bench0240.sh` are exp 0239's, renamed: same conditions, 26 frozen-view shots, no
  bench image dumps. The draw journal was filtered on the pixel shaders of the writer
  (0x11d0160b00), the two downsamplers (0x11d015f100, 0x11d015f600) and both water draws
  (0x11d01ff900 main, 0x11d01d7100 full-screen): `BC5_DIRECT_DRAW_JOURNAL=150:12
  BC5_DIRECT_DRAW_JOURNAL_EVERY=15 BC5_DIRECT_DRAW_JOURNAL_PS=...`. The kernel log was streamed to
  the laptop, and the game shot was checked live.
- `jr0240.py` groups the matched draws by flip interval (the host's `frame profile` lines) and
  submission (`dcb` timing lines). The graphics ring runs submissions in the order the journal
  shows them. For each group of water main draws it reports whether that frame's writer came
  before or after. Exp 0212's `desc0212.py` decodes the inline descriptors.
- **Reads of the G-buffer target.** The top session added a read of 0x113f230000. Rather than spend
  the second run, I took four reads by hand during Q1's frozen view. Each was `mem0212.py dump` of
  `113f230000:1860000` through `/proc/<pid>/mem`, the same read-only read the bench uses: gb1 at
  19:07:35, gb2–gb4 at 19:09:28–32.
  - The extent is 3328×1872 at 32_FLOAT in `ADDR_SW_64KB_R_X`: 128×128-element blocks, 26 × 15 of
    them, 25,559,040 bytes.
  - `gen0240.py` (exp 0237's generator, with the element size as an argument) extracted the
    4-byte-element pattern from Mesa addrlib @ ab2374a into `swz0240-4.json`.
  - `gb0240.py` de-swizzles at 16 pipes (F296), picks the width by block-row shear, and compares
    the image with the next screenshot's patch mask, as `sum0238.py` does. The far value tested
    is the window's most common one.
- **The reads are the title's data: summarised on the box, then deleted.** One render (gb3) is kept
  in `~/bc5-data/priv/exp0240` (mode 700). `raw/Q1.desc.txt` keeps the image lines; the full list
  of per-frame buffer descriptors stays on the box.

**Result** (`raw/Q1.ab.txt`, `raw/Q1.jr.txt`, `raw/Q1.desc.txt`, `raw/Q1.gbuffer.txt`).
- **Box state.** No kernel fault, timeout or reset: the amdgpu count stayed at 578, the run's `.out`
  has 0 fault lines, and the stream has only routine lines. The live saves' checksum was the same
  before and after (f6475842373bf369). The run wrote about 175 MB: run directory 78 MB and journal
  95 MB, of which 560 matched draws took 122 KB.
- **Q1 loaded the lake save and switched from clean to patched.** It was 0.9–1.0 % for ts00–ts12,
  mixed at ts13–ts17 (3.5, 13.5, 7.5, 0.9, 11.9 %), and 16.6–24.0 % from ts18 on (ts21 at 7.5 %).
- **Frame order: in 54 of 54 frames the water's main draws ran after that frame's writer.** That
  held in the clean and the patched windows alike, over 14 windows of 4 frames (2 frames at window
  starts had no writer journalled).
  - Every frame runs the same sequence (`raw/Q1.jr.txt`):
    1. the water's full-screen draw (submission 2–4, into 0x113f230000);
    2. the writer and both downsamplers (submission 3–5);
    3. the water's main draws (submission 8–12, four `DRAW_INDEX_2`);
    4. **both downsamplers again**, in the same submission, into the same 0x113a7a0000 and
       0x113ab20000. The depth pyramid is rebuilt after the main draws, perhaps because they also
       write linear depth through one of their unjournaled colour targets 1–4.
  - So the main draws read the linear depth of the current frame, made from the G-buffer before
    them.
- **The G-buffer target 0x113f230000 is view depth, cleared every frame to 10,000, and in patched
  frames it has holes where the screen's patches are.**
  - The reads hold 5.3–10,000. Two of them caught the target before the lake surface was drawn in
    that frame: gb1 in the clean phase, gb4 in the patched one. Each has the shore drawn and 67.5 %
    of the lake window at 10,000. So the target is cleared to the far value every frame and the
    lake surface is drawn into it anew.
  - gb3, the most complete patched read (shear 1.74), has the cleared value over 23.8 % of the
    window. Against ts24 that value covers 90.8 % of patch pixels and 6.6 % of the others
    (phi +0.80), and the depth step across the patch edges is ×12.0 the window's. Against ts25:
    73.2 % against 11.1 %, phi +0.59, ×9.2.
  - gb2 (shear 5.6) gives phi +0.51, ×9.6.
  - By eye, gb3's render shows the screen's checkerboard as holes in the lake's surface depth.
  - The clean phase has only gb1, which caught the target mid-frame, so there is no complete clean
    read of the G-buffer. Exp 0238 showed the slot-4 image, derived from it, without cells in clean
    frames.
- **The writer's inputs in a lake frame are not visible in the journal.** Its pixel-stage user data
  holds buffer descriptors (V#s), not the inline images of the menu's full-size draws. The first 32
  dwords of its tables hold neither 0x113f2300 nor 0x1140a900. The water's full-screen draw's
  vertex-stage table does hold both. The image lines of `raw/Q1.desc.txt` confirm the rest:
  - the main draws read 0x113cb40000 in vertex slot 4;
  - the downsamplers read it, then 0x113a7a0000;
  - the main draws' pixel stage reads the same three kinds of texture as in exps 0235/0238 (2048²
    BC4, 512² 16_FLOAT, 4×4 8_8_8_8_UNORM).

**Verdict.**
- **The patches are holes in the G-buffer's depth where the lake surface was not written.** The
  target is cleared to the far value every frame. In patched frames, cells of the lake stay at
  that value: they are visible in the target itself, in the linear depth made from it (F297), and
  on screen.
- **No loop through these two targets.** The G-buffer is cleared every frame, and the linear-depth
  pass runs before the water's main draws, which read this frame's image. So the main draws cannot
  feed their own input. F298's loop hypothesis does not hold in that form. Whatever keeps the
  state for seconds lies elsewhere.
- **The holes come from a draw before the linear-depth pass.** They are in its output, so they were
  already in the G-buffer when it ran. Exp 0238's renders show that output with the lake surface
  drawn, either whole or with holes, so a draw before the writer puts the surface depth there.
  The water's full-screen draw (PS 0x11d01d7100, submission 2–4) is the only water draw before it,
  so it is the candidate. Its vertex-stage table holds the G-buffer target and 0x1140a90000.
- **Next:** what makes the water's full-screen draw skip cells (its discard condition and inputs, for
  example a per-tile mask from the compute dispatches journalled right after it in J1), and a
  complete clean read of the G-buffer for contrast.
