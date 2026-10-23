# 0250 — The night lake: does a render-size/HTILE mismatch make the patches?

**Question.** After exp 0248 (F307), the top session put forward a hypothesis that joins two of its
observations:
- the title changes its render size from frame to frame (3328×1872, 2048×1152);
- only the patched-phase reads held words outside 0..1, which are probably compressed tiles.

The hypothesis: if the depth buffer's HTILE (per-8×8-tile hierarchical-Z and compression metadata)
is cleared or decompressed for one size while the frame draws at the other, the full-screen water
draw's GEQUAL test would fail per tile, giving cells that come and go with the size changes.
Three checks were proposed:
1. Do the cells match 8×8 HTILE tiles, or groups of them?
2. Do patched windows line up with one render size, or with switches between sizes?
3. How is the per-frame depth clear done (F305: no journalled draw clears depth)? A compute or DMA
   write to `DB_HTILE_DATA_BASE`?

**Setup.**
- Checks 1 and 2 use committed data only: the README findings of exps 0194 and 0237, and the
  journal summaries of exp 0240's run Q1 and exp 0248's run H1.
- **`sz0250.py`** pairs every window of a `jr0240.py` summary with the frozen-view shots before
  and after it, by wall time. It lists the G-buffer target's size in each journalled frame
  (`raw/sizes.txt`).
- **`db0250.py`** decodes the depth registers that exp 0245's "bake db" line carries.
  `jr0245.py` parsed them but did not print them. The fields come from Mesa's gfx10 register
  JSON (`tools/bc5-agc/regdb/gfx10.json`):
  - `DB_Z_INFO` (FORMAT, SW_MODE, TILE_SURFACE_ENABLE, ZRANGE_PRECISION, ALLOW_EXPCLEAR,
    DECOMPRESS_ON_N_ZPLANES);
  - `DB_DEPTH_SIZE_XY`, `DB_DEPTH_VIEW`, `DB_HTILE_DATA_BASE`;
  - `DB_RENDER_CONTROL` / `_OVERRIDE`.

  It prints each distinct description of the depth buffer 0x1129ec0000 and their order. In an
  unfiltered window it also prints the entries before each frame's first depth write, and every
  journal line that holds the HTILE base.
- **`grep0250.sh`** is the read-only box step, run with no emulator under this experiment's lock
  line, after exp 0249 (top session's grant). It does two things:
  - It counts `BC5_DIRECT_DRAW_JOURNAL_EVERY` strings in the binaries used. The switch comes from
    exp 0194's `edit0194.py`; patch 0001 (`backend/kytyplus-patches/0001-bc5-lle-agc.patch`) has no
    such switch.
  - It runs `db0250.py` over H1's journal (filtered, exp 0248) and Z2's (unfiltered, exp 0245),
    which are still on the box.
- The patch 0001 journal holds draws and dispatches only. DMA_DATA and other CP writes are not in
  it, and a dispatch's user data appear only for a few hard-coded passes.

**Result.**
1. **Shape: the cells are not screen tiles.**
   - Exp 0194 saw them as a checkerboard near the camera and rectangles of several sizes farther
     out, aligned with the water plane.
   - Exp 0237's depth image has its cells "in the same perspective as the screenshot's cells".
   - HTILE covers fixed 8×8-pixel screen tiles. A stale or mis-pitched HTILE would therefore give
     screen-aligned blocks or bands, not cells that shrink with distance along the lake's plane.
2. **Render size per frame: no separation** (`raw/sizes.txt`).
   - **Q1** (exp 0240: 14 windows of 4–5 frames, clean ts00–ts12, patched from ts18):
     - Clean windows ran at 3328×1872 (4 frames), 3072×1728 (twice, 4 frames each),
       2816×1584 → 3072×1728, and 3072×1728 again at ts12/ts13 (0.9/3.5 %).
     - Patched windows ran at a steady 3072×1728 (ts18/ts19, 23.0/24.0 %), at 2304×1296 →
       2560×1440 (ts21/ts22, 7.5/19.1 %), and at a steady 3328×1872 (ts24/ts25, 20.4 %).
     - After the last shot the run kept drawing at 3328, 2560 and 3328 again; its state there is
       unknown.
   - **H1** (exp 0248): its one window switched 3328×1872 → 2048×1152 in a clean moment (ts00, 1.0 %).
   - So neither a size nor a switch inside the window marks patched frames. The windows are 4–6
     frames every 15 s, so a switch just before a window is not excluded.
   - The cells also stay put while the size keeps changing. Exp 0194 measured 0.2–0.3 % of water
     pixels changing over 21 s of a frozen view, and patched phases last tens of seconds (F292).
     Q1 changes size within most 15-s intervals.
3. **The depth buffer per render size, and the clear** (`raw/H1.surf.txt`, `raw/Z2.surf.txt`; the
   box step ran 21:47–21:49 with no emulator, `/var/home` at 70 %).
   - **One depth address, one HTILE per size.** The depth buffer keeps its base 0x1129ec0000 at
     every size, but its HTILE base and its stencil buffer move with the size:

     | size | DB_HTILE_DATA_BASE | = depth base + | stencil |
     |---|---|---|---|
     | 3328×1872 | 0x112b720000 | 26 × 15 blocks of 64 KiB (0x1860000) | 0x112b7a0000 (HTILE 512 KiB) |
     | 3072×1728 | 0x112b3c0000 | 24 × 14 blocks (0x1500000) | |
     | 2048×1152 | 0x112a7c0000 | 16 × 9 blocks (0x900000) | 0x112a7f0000 (HTILE 192 KiB) |
     | 3840×2160 | 0x112bea0000 | 30 × 17 blocks (0x1fe0000) | |

     - Each HTILE sits right after that size's depth data, and the stencil right after the HTILE.
     - All sizes have the same `DB_Z_INFO` fields: Z_32_FLOAT, `SW_MODE` 24, TILE_SURFACE_ENABLE 1
       (HTILE in use), ZRANGE_PRECISION 1, ALLOW_EXPCLEAR 0, DECOMPRESS_ON_N_ZPLANES 0.
     - **So the sizes alias.** A smaller size's HTILE and stencil lie inside a larger size's depth
       data. The 2048×1152 HTILE starts 9 MiB into the buffer, at block row 5.5 of the 3328-wide
       layout, which is screen rows of about 700–900 of 1872, across the lake. The 3072×1728 HTILE
       lies in the 3328 surface's last block rows. A frame at one size writes, as depth, memory
       that another size reads as HTILE.
     - That is safe only if each frame re-initialises its own HTILE before the depth test uses it.
   - **Each frame's description is consistent with its own size.** In H1's six frames, three at
     3328 then three at 2048, every journalled draw on the depth buffer had the depth size and
     HTILE of its own colour target's size. In Z2's unfiltered window the same holds for the 3328
     and 3072 frames.
   - **Every frame also uses the buffer at 3840×2160.** In Z2, each 3328 frame has, after the water
     draws, a pass on a 3840×2160 colour target (0x114c6c0000) whose draws describe the same depth
     base at 3840×2160, with HTILE 0x112bea0000 and stencil 0x112bf40000.
     - One of them (PS 0x11d01e1700) writes depth there (`Z on+write GEQUAL`, exp 0245's
       `raw/Z2.db.txt` #306).
     - The 3840 depth data spans 0x1129ec0000–0x112bea0000, so it covers the 3328 HTILE and stencil
       (0x112b720000–).
     - The six draws with `DB_RENDER_CONTROL` 0x60 (F305's compression-disable passes) carry the 3328
       description: 4 under the 3840×2160 target (PS 0x11d01e1700) and 2 under the G-buffer target
       (PS 0x11d0208400).
     - So the 3328 HTILE is overwritten within every frame, not only when the size changes.
   - **The clear itself is not in the journal.**
     - No journalled draw sets DEPTH_CLEAR_ENABLE (F305).
     - In Z2, the entries before each frame's first depth write are dispatches (e.g. CS
       0x11d042ba00, 0x11d042b100, 0x11d0287900 and 0x11d0288a00, exp 0094's copy kernel) and small
       draws.
     - Outside the "bake db" lines, the HTILE bases appear only in register state: the title's
       `LOAD_CONTEXT_REG_INDEX` tables, the tracked context, and the backend's `DB_HTILE` hint lines.
       No line ties them to a dispatch. The journal shows a dispatch's user data only for a few
       hard-coded passes, and DMA_DATA not at all.
   - **`_EVERY`** (`raw/binaries.txt`): exp 0194's binary holds the `BC5_DIRECT_DRAW_JOURNAL_EVERY`
     string once. Exp 0245's private binary and the shared build's binary hold it 0 times.
     - Exps 0245 (run Z3) and 0248 (run H1) ran exp 0245's binary, so the switch was ignored. Each
       got one window because the switch did not exist there, not because of the filter.
     - That corrects F305's "`_EVERY` does not repeat unfiltered windows" and F307's "did not repeat
       even a `_PS`-filtered window".

**Verdict.**
- **A screen-space HTILE mismatch tied to the size changes does not explain the patches by itself.**
  The cells follow the water plane in perspective (check 1), and clean and patched frames run at
  the same sizes (check 2).
- **The title's depth layout makes its HTILE depend on a per-frame re-initialisation.** Each
  size's HTILE and stencil sit inside a larger size's depth data, and the 3840×2160 pass writes
  depth over the 3328 HTILE in every frame. Correct rendering then depends on each frame
  re-initialising its HTILE, by a clear that is not a journalled draw and was not found among the
  journalled dispatches.
- If that clear were missed, or done for another size, the depth test would compare against stale
  HTILE words left from other memory. Whether that can produce cells in the water plane's
  perspective is open. A stale HTILE alone gives 8×8-tile structure, so it would need to interact
  with geometry, for example through hierarchical-Z rejection of the lake's own depth writers.
- **Next (exp 0251), using a binary that has `_EVERY`:**
  - journal clean and patched windows of the depth-only writers with their indirect arguments,
    and the depth description per frame;
  - add `_FIND` on the HTILE bases, in register form (base >> 8) and as a buffer descriptor's low
    dword, to catch a dispatch that clears them;
  - add a journal line for `DMA_DATA` and `WRITE_DATA` packets that write into the depth buffer's
    memory, since a CP fill is not otherwise visible.
