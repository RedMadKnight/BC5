# 0244 — The night lake: what the water's full-screen draw reads, and whether it can leave holes

**Question.** Exp 0240 (F299) found the lake's patches as holes in the G-buffer's depth (0x113f230000),
present before the linear-depth pass. The water's full-screen draw (PS 0x11d01d7100, ES 0x11d00bdf00)
is the only water draw before that pass. Does its program discard cells, and on what input? Also: a
complete G-buffer read from a clean frame, for contrast.

**Setup.**
- BC-250 dev box, 2026-10-23, granted by the top session for ~30 min after exp 0242. Part 1 ran
  19:51–19:53, run Y1 19:53–19:59, the analysis until 20:01. Boot 31c1a6ac; `/var/home` at 69 %.
- **Part 1, the programs (analysis only, no emulator).** The private disassembly listings from
  earlier experiments (`~/bc5-data/priv/11d01d7100.dis`, `11d00bdf00.dis`; llvm-mc
  `-mcpu=gfx1013`) were summarised on the box by `code0244.py`.
  - It follows where each scalar register comes from: a user-data dword, a load from a table at
    an offset, or a constant-buffer load (`s_buffer_load`).
  - It reports each memory read by the origin of its descriptor, plus every exec-mask write
    (discard), branch, export and `s_endpgm`.
  - Only mnemonics, register origins, offsets and counts leave the box (`raw/ps.code.txt`,
    `raw/es.code.txt`).
  - A slip: one quick check echoed the first three lines of the pixel program's listing
    (mnemonics with register operands, hex constants masked). That was reported to the top
    session; no other listing text left the box.
- **Part 2, one bench run (Y1).** `ab0244.sh` and `bench0244.sh` are exp 0240's, renamed, with the
  same conditions: the exp 0194 build (comm `kyty_emulator`), the 3-s `dmesg` poll and kernel
  stream, `/var/home` under 80 %, and the live saves checksummed. The draw journal was filtered on
  the full-screen draw, the water's main draws and the linear-depth writer.
  - During the frozen view, `capl0244.sh` ran `cap0244.py` six times, 20 s apart. Each capture
    took:
    - the full-screen draw's constant buffer (the V# in its user-data dwords 8–11) at the address
      of its latest journalled draw, checked against the journalled head;
    - the T# at that buffer's offset 0x6e0 (the one image the program reads, from part 1);
    - the G-buffer target 0x113f230000.
  - The image behind that T# was not read by the captures (format 1 was not in their checked
    list), so it was read three times by hand at 19:58 (`mem0212.py dump`, 256 KiB).
  - `ana0244.py` de-swizzles each G-buffer read (as exp 0240) and compares it with the next shot's
    patch mask.
- **The captures are the title's data: summarised, then deleted (148 MB).** One render (cap4) is
  kept in `~/bc5-data/priv/exp0244`.

**Result** (`raw/ps.code.txt`, `raw/es.code.txt`, `raw/Y1.*`).
- **The full-screen draw's pixel program has no discard.**
  - 119 instructions, with no exec-mask write and no branch, and one `s_endpgm`.
  - Four exports, mrt0–mrt3, all unconditional.
  - Its memory reads: 11 `s_buffer_load`s of constants from the buffer in user-data dwords 8–11,
    and one `image_load`. The T# for that load is itself loaded from the same buffer at offset
    0x6e0.
  - The vertex program (48 instructions) reads one vertex buffer through a table in user-data
    dword 4, and exports a position and a primitive: the draw's three vertices.
- **Box state.** Y1 loaded the lake save. No kernel fault, timeout or reset: the amdgpu count stayed
  at 578, the run's `.out` has 0 fault lines, and the stream has only routine lines. The live
  saves' checksum was the same before and after (f6475842373bf369). The run wrote about 175 MB:
  run directory 79 MB and journal 95 MB.
- **Y1 switched both ways.** It was patched at ts00–ts05 (19.7–28.5 %), mostly clean at
  ts06–ts14 (0.9–11.4 %, under 5 % at ts07, ts08, ts09, ts11, ts13), patched again at ts15–ts17
  (18–21 %), 6–9 % at ts18–ts20, and patched at ts21–ts25 (24.6–28.8 %).
- **The one image is a static noise texture.** Its constant buffer was read six times (four heads
  matched the journal, two had been reused), and every time offset 0x6e0 held the same T#:
  - base 0x8090390000, 128×128, format 1 (8_UNORM, Mesa `GFX10_FORMAT`);
  - type 13 (`SQ_RSRC_IMG_2D_ARRAY` in Mesa's `gfx9.json` @ 0866ae7; the gfx10 file does not list
    the type, TODO(verify));
  - `ADDR_SW_4KB_S`.

  Read three times (256 KiB, 16 slices' worth; the array's size is in a T# word the captures did
  not decode), it was the same each time. Every slice holds each of the 256 byte values exactly 64
  times, with mean 127.5. That is the shape of a dither or
  blue-noise texture, not a per-cell mask.
- **The G-buffer target:**
  - In the patched stretches its holes line up with the next shot's patches: cap1, cap2 and cap6
    give phi +0.52, +0.58 and +0.58, with the depth step across the patch edges ×8.2–11.8.
  - cap5 (patched, 18.4 %) has its edges on the screen's (×12.7) but the other polarity
    (phi −0.25), as twice in exp 0238.
  - cap4 is a complete read (shear 0.99) and also has holes. It was taken at 19:56:38, between
    ts12 (11.4 %) and ts13 (1.3 %), in a flickering stretch, so it is not a clean reference.
  - cap3, the one read from a steadily clean stretch (ts08 and ts09 both 0.9 %), caught the
    target before the lake surface was drawn (70 % of the window at 10,000).
  - **So there is still no complete clean read.**

**Verdict.**
- **The water's full-screen draw cannot make the holes in its program.** It has no discard and
  writes its four targets unconditionally from constants and a static noise texture.
- **So either it does not write the lake's surface depth, or a fixed-function test stops it in
  cells.** A depth or stencil test against a buffer that already has the cell pattern would do
  that. The draw journal does not record the depth/stencil state (`DB_DEPTH_CONTROL`,
  `DB_STENCIL_CONTROL`, stencil reference) or the depth target of a draw. Its "hint DB_*" lines
  only name buffers once per address.
- **Next, needing the top session's go:** extend patch 0001's draw journal to record each journalled
  draw's depth/stencil state and depth target. That means rebuilding the bench's private exp 0194
  binary, not the shared builds. Then journal the full-screen draw and the draws before it in
  patched and clean frames. Separately, a complete clean G-buffer read needs reads timed in a
  steadily clean stretch, e.g. several reads 0.5 s apart.
