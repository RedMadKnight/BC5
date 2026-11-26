# 0245 — The night lake: the depth/stencil state of the water's full-screen draw

**Question.** Exp 0244 (F303) found that the water's full-screen draw (PS 0x11d01d7100) has no
discard and writes its targets unconditionally. Yet the G-buffer has holes where the lake's patches
are (F299). Does a depth or stencil test stop the draw in those cells, and which draws write the
buffer it tests?

**Setup.**
- BC-250 dev box, 2026-10-23, granted by the top session after exp 0246: a private build, run A,
  and run B only if A warranted it. Build 20:21–20:23, run Z2 20:23–20:29, run Z3 20:32–20:38,
  then analysis until 20:39. Boot 31c1a6ac; `/var/home` at 69–70 %.
- **The private build** follows exps 0219/0226 (`build0226.py`):
  - `patch0245.py` adds one "bake db" line per journalled draw to a copy of the shared tree's
    `bc5LleAgc.cpp`, in every journal mode. The line holds:
    - `DB_DEPTH_CONTROL`, `DB_STENCIL_CONTROL`, `DB_STENCILREFMASK(_BF)`, `DB_SHADER_CONTROL`;
    - `DB_RENDER_CONTROL/OVERRIDE`, `DB_Z_INFO`/`DB_STENCIL_INFO`, `DB_DEPTH_VIEW`/`SIZE_XY`;
    - the depth and stencil read/write and HTILE bases, the depth bounds and the clear values.

    Context offsets come from `tools/bc5-agc/regdb/gfx10.json`.
  - `build0245.py` compiles that one unit with the shared build's flags (`ninja -t compdb -x`; the
    first attempt failed on an unexpanded response file). It links
    `~/bc5-work/exp0245/kyty_emulator` from the shared build's other objects: today's, after exp
    0243, so with F288's read-ahead fix and F301's ATRAC9 vibration decoder, neither of which
    touches the water.
  - `~/src/KytyPlus`, the shared objects and binaries were not written.
  - **This is not exp 0194's binary.** It is today's shared tree plus this journal line, run through
    the bench's launcher copy (old values: no PRT, old skip list).
- `ab0245.sh` and `bench0245.sh` are exp 0244's, renamed, with `BC5_EMU` pointing at the private
  binary (comm `kyty_emulator`). Same conditions: the 3-s `dmesg` poll and kernel stream,
  `/var/home` under 80 %, the live saves checksummed, and the game shot checked live.
- Run A (Z2): `BC5_DIRECT_DRAW_JOURNAL=165:120`, unfiltered, about three frames.
- Run B (Z3): `BC5_DIRECT_DRAW_JOURNAL=150:120` with `_EVERY=15`, meant for windows through the run.
- `jr0245.py` decodes the "bake db" lines with the regdb's field layouts. `cmp0245.py` compares
  the depth-writing draws before each full-screen draw.

**Result** (`raw/Z2.*`, `raw/Z3.*`, `raw/Z2Z3.cmp.txt`, `raw/build.txt`).
- **Box state.** Both runs loaded the lake save. No kernel fault, timeout or reset: the amdgpu count
  stayed at 578, the runs' `.out` have 0 fault lines, and the streams have only routine lines. The
  live saves' checksum was the same before and after both runs (f6475842373bf369). Each run wrote
  about 170 MB: run directory 79 MB and journal 88 MB. The journal windows held 315 KB (Z2) and
  259 KB (Z3) of draw lines.
- **Z2's window was a clean moment** (ts03 at 0.8 %). Z2 was mostly clean overall, patched at
  ts04–ts06 (9–15 %).
- **The full-screen draw is depth-tested:** `DB_DEPTH_CONTROL` 0x007007e2 decodes to Z_ENABLE 1,
  Z_WRITE_ENABLE 0, ZFUNC 6 (FRAG_GEQUAL), STENCIL_ENABLE 0. `DB_SHADER_CONTROL` 0x810 has
  KILL_ENABLE 0 and Z_EXPORT_ENABLE 0.
  - Its depth buffer is 0x1129ec0000: format 3 (Z_32_FLOAT), swizzle mode 24 (`ADDR_SW_64KB_Z_X`,
    addrlib's numbering).
  - The stencil buffer is 0x112b7a0000 or 0x112b420000, format 1 (STENCIL_8). It is not tested.
- **The order on that depth buffer, every frame** (`raw/Z2.cmp.txt`):
  1. About 133 draws that write depth: the G-buffer draws and depth-only ones (colour mask 0),
     most of them `DRAW_INDIRECT` (0x24) with GPU-written arguments. Among them are PS 0x11d1d88300
     (12) and 0x11d1dd6400 (7), both depth-only.
  2. The full-screen water draw (test only).
  3. Further draws.
  4. The water's 4 main draws (GREATER, writing depth and stencil).
  5. 4 draws by PS 0x11d0208400 (writing depth).
  6. Two passes with `DB_RENDER_CONTROL` 0x60 (both compression-disable bits).
  7. Depth-tested passes.

  No journalled draw has DEPTH_CLEAR_ENABLE. The buffer is cleared every frame (F299), so that
  clear happens outside the journalled draws (a compute or command-processor clear).
- **Run B journalled only its first window.** `_EVERY` does not repeat an unfiltered window. That
  window (t 150) fell at a patched moment (ts00 22.1 %, ts01 7.3 %).
  - Comparing Z2's clean frames with Z3's patched ones is confounded: most pixel-shader addresses
    differ by small amounts between the two runs (e.g. 0x11d29e9600 / 0x11d29e9300), while the
    water's shaders stay put.
  - By role, the patched frames issue 119–120 depth writers against 132–133, with every role within
    ±1–4. That cannot name a draw.

**Verdict.**
- **The full-screen water draw is gated by the depth test.** It writes the G-buffer only where its
  fragments pass GEQUAL against the depth that about 130 earlier draws have written, and it does
  not write depth itself. A cell where an earlier draw left a nearer depth blocks it, and the
  G-buffer keeps its cleared far value there: the holes of F299.
- **Which earlier draw does that is open.** Most depth writers before it are GPU-driven indirect
  draws, so what they cover is decided on the GPU, and two runs cannot be compared draw by draw.
- **Next:**
  1. Read the depth buffer 0x1129ec0000 in patched and clean frames of one run, de-swizzled with
     addrlib's `ADDR_SW_64KB_Z_X` pattern, to see what depth the hole cells hold and its shape.
  2. A within-run journal of clean and patched frames filtered on the depth-only writers, with
     their indirect-argument buffers.
- The private binary and its object (~179 MB) stay in `~/bc5-work/exp0245` for that follow-up.
