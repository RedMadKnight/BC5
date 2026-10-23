#!/usr/bin/env python3
# BC5 experiment 0245: add the depth/stencil state of each journalled draw to patch 0001's draw journal, in a copy of
# the shared tree's bc5LleAgc.cpp (the shared tree and its build are not written; build0245.py compiles the copy).
# After the "draw journal buf ..." line of a matched draw it inserts one "bake db buf N at P: ..." line with, from the
# tracked context registers (Mesa's gfx10 register JSON, tools/bc5-agc/regdb/gfx10.json; context index = (byte
# address - 0x28000) / 4): DB_DEPTH_CONTROL 0x200, DB_STENCIL_CONTROL 0x10b, DB_STENCILREFMASK 0x10c,
# DB_STENCILREFMASK_BF 0x10d, DB_SHADER_CONTROL 0x203, DB_RENDER_CONTROL 0x000, DB_RENDER_OVERRIDE 0x003,
# DB_Z_INFO 0x010, DB_STENCIL_INFO 0x011, DB_DEPTH_VIEW 0x002, DB_DEPTH_SIZE_XY 0x007, the depth and stencil read/
# write bases DB_Z_READ_BASE .. DB_STENCIL_WRITE_BASE 0x012-0x015 with their _HI 0x01a-0x01d, DB_HTILE_DATA_BASE 0x005
# with _HI 0x01e (addresses as CB_COLOR0_BASE: (lo | (hi & 0xff) << 32) << 8), DB_DEPTH_BOUNDS_MIN/MAX 0x008/0x009,
# DB_DEPTH_CLEAR 0x00b and DB_STENCIL_CLEAR 0x00a. Printed in every journal mode (unfiltered windows too), only for
# draws the journal prints.
# usage: python3 -I patch0245.py <bc5LleAgc.cpp of the shared tree> <output copy>
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
anchor = "2 * xs, 2 * ys, xo - xs, yo - ys, ps, es, gs, cs);\n"
assert s.count(anchor) == 1, "anchor found %d times" % s.count(anchor)
assert "bake db buf" not in s, "already patched"
add = r'''				// Experiment 0245: the draw's depth/stencil state and buffers (tools/bc5-agc/regdb/gfx10.json; context
				// index = (byte address - 0x28000) / 4).
				if (!watch_quiet && matched) {
					auto base40 = [&](uint32_t lo, uint32_t hi) {
						return (static_cast<uint64_t>(reg(S::Context, lo)) | (static_cast<uint64_t>(reg(S::Context, hi) & 0xffu) << 32u)) << 8u;
					};
					journal("bake db buf %u at %zu: depth_control %08x stencil_control %08x refmask %08x refmask_bf %08x shader_control %08x"
					        " render_control %08x render_override %08x | z_info %08x stencil_info %08x view %08x size_xy %08x | z_read %010" PRIx64
					        " stencil_read %010" PRIx64 " z_write %010" PRIx64 " stencil_write %010" PRIx64 " htile %010" PRIx64 " | bounds %g..%g clear z %g s %u\n",
					        buf_no, off, reg(S::Context, 0x200), reg(S::Context, 0x10b), reg(S::Context, 0x10c), reg(S::Context, 0x10d),
					        reg(S::Context, 0x203), reg(S::Context, 0x000), reg(S::Context, 0x003), reg(S::Context, 0x010), reg(S::Context, 0x011),
					        reg(S::Context, 0x002), reg(S::Context, 0x007), base40(0x012, 0x01a), base40(0x013, 0x01b), base40(0x014, 0x01c),
					        base40(0x015, 0x01d), base40(0x005, 0x01e), flt(0x008), flt(0x009), flt(0x00b), reg(S::Context, 0x00a));
				}
'''
s = s.replace(anchor, anchor + add, 1)
open(out, "w", encoding="utf-8", newline="\n").write(s)
print("patched: %s -> %s (+%d lines)" % (src, out, add.count("\n")))
