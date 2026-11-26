#!/usr/bin/env python3
# BC5 experiment 0251: two additions to the draw journal, in a copy that edit0194.py and patch0245.py have already
# patched (build0251.py):
#  1. after patch0245.py's "bake db" line, a "bake db2 buf N at P: ..." line with two more depth registers from the
#     tracked context (Mesa's gfx10 register JSON, tools/bc5-agc/regdb/gfx10.json; context index = (byte address -
#     0x28000) / 4): DB_HTILE_SURFACE 0x2af (0x28abc: FULL_CACHE, DST_OUTSIDE_ZERO_TO_ONE, PIPE_ALIGNED) and
#     DB_RENDER_OVERRIDE2 0x004 (0x28010: DECOMPRESS_Z_ON_FLUSH, HIZ_ZFUNC, PRESERVE_ZRANGE, ...). DB_Z_INFO's
#     TILE_SURFACE_ENABLE and ZRANGE_PRECISION are already in patch0245's z_info word (db0250.py decodes them);
#  2. for every buffer inside a journal window (all of them, matched draws or not), the DMA_DATA (0x50) and WRITE_DATA
#     (0x37) packets that write into the night lake's depth memory, 0x1129ec0000 .. 0x112c800000: the depth data of
#     every render size with their HTILE and stencil (exp 0250, F309). The per-frame HTILE clear is neither a journalled
#     draw nor a visible dispatch, so a CP fill is the other candidate. Raw dwords are printed; the destination is taken
#     as DMA_DATA dwords 4-5 and WRITE_DATA dwords 2-3 (Mesa src/amd/common/sid.h PKT3_DMA_DATA / PKT3_WRITE_DATA and
#     their use in ac_emit_cp_dma / radeon_emit sequences; TODO(verify) against ~/src/mesa on the box). A per-buffer
#     count of both packet kinds is printed when the buffer has any;
#  3. (added after run W251a, for W251b) for the same buffers an opcode census: the type-3 opcodes that
#     backend/policy/pm4-policy.tsv does not pass (its default verdict is drop), with counts and first offsets, and the
#     EVENT_WRITE event types. The journal records drops only as per-submit totals, so this is how a dropped HTILE
#     re-initialisation would show.
# usage: python3 -I patch0251.py <in copy> <out copy>
import sys

src, out = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
assert "bake db2 buf" not in s and "depth pool scan" not in s and "op census buf" not in s, "already patched"

anchor = "base40(0x015, 0x01d), base40(0x005, 0x01e), flt(0x008), flt(0x009), flt(0x00b), reg(S::Context, 0x00a));\n"
assert s.count(anchor) == 1, "patch0245's line found %d times" % s.count(anchor)
add = r'''					// Experiment 0251: DB_HTILE_SURFACE (ctx 0x2af) and DB_RENDER_OVERRIDE2 (ctx 0x004), gfx10.json.
					journal("bake db2 buf %u at %zu: htile_surface %08x render_override2 %08x\n", buf_no, off, reg(S::Context, 0x2af),
					        reg(S::Context, 0x004));
'''
s = s.replace(anchor, anchor + add, 1)

a1 = "\t\t\t// (the per-frame re-check of the vertex ranges became bc5_ranges_complete, at fence completion)\n"
assert s.count(a1) == 1, "edit0194's anchor found %d times" % s.count(a1)
scan = r'''			// Experiment 0251: DMA_DATA (0x50) and WRITE_DATA (0x37) packets of this buffer that write into the night lake's
			// depth memory (0x1129ec0000 .. 0x112c800000: every render size's depth data, HTILE and stencil, F309). Destination:
			// DMA_DATA dwords 4-5, WRITE_DATA dwords 2-3 (Mesa sid.h, TODO(verify)); raw control dwords printed.
			{
				uint32_t n_dma = 0, n_wd = 0, n_hit = 0;
				for (uint32_t i = 0; i < num_dwords;) {
					const uint32_t h = ib[i], type = h >> 30u;
					uint32_t       len = 1;
					if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (i + len > num_dwords) break;
					const uint32_t op = (h >> 8u) & 0xffu;
					if (type == 3 && op == 0x50 && len >= 7) {
						n_dma++;
						const uint64_t dst = ib[i + 4] | (static_cast<uint64_t>(ib[i + 5] & 0xffffu) << 32u);
						if (dst >= 0x1129ec0000ull && dst < 0x112c800000ull) {
							n_hit++;
							journal("depth pool dma_data buf %u at %u: dw1 %08x src %08x %08x dst %010" PRIx64 " dw6 %08x\n", buf_no, i, ib[i + 1], ib[i + 2],
							        ib[i + 3], dst, ib[i + 6]);
						}
					} else if (type == 3 && op == 0x37 && len >= 4) {
						n_wd++;
						const uint64_t dst = ib[i + 2] | (static_cast<uint64_t>(ib[i + 3] & 0xffffu) << 32u);
						if (dst >= 0x1129ec0000ull && dst < 0x112c800000ull) {
							n_hit++;
							journal("depth pool write_data buf %u at %u: dw1 %08x dst %010" PRIx64 " dwords %u\n", buf_no, i, ib[i + 1], dst, len - 4);
						}
					}
					i += len;
				}
				if (n_dma != 0 || n_wd != 0)
					journal("depth pool scan buf %u (%u dwords): dma_data %u, write_data %u, into the depth memory %u\n", buf_no, num_dwords, n_dma, n_wd, n_hit);
			}
			// Experiment 0251: the type-3 opcodes of this buffer that backend/policy/pm4-policy.tsv does not pass (its
			// default verdict is drop; 0x4a and 0x8e are dropped by name), and the EVENT_WRITE (0x46) event types (dword 1
			// bits 5:0, EVENT_INDEX bits 11:8; Mesa sid.h EVENT_TYPE/EVENT_INDEX, TODO(verify)).
			{
				static const uint8_t passed[] = {0x10, 0x11, 0x12, 0x13, 0x15, 0x16, 0x1e, 0x22, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2a, 0x2c,
				                                 0x2d, 0x2f, 0x33, 0x35, 0x37, 0x38, 0x3c, 0x3f, 0x40, 0x42, 0x46, 0x47, 0x49, 0x50, 0x58,
				                                 0x5e, 0x5f, 0x61, 0x63, 0x64, 0x68, 0x69, 0x76, 0x79, 0x7a, 0x93, 0x9b, 0x9f};
				uint32_t ops[256] = {}, first_at[256] = {}, events[64] = {};
				for (uint32_t i = 0; i < num_dwords;) {
					const uint32_t h = ib[i], type = h >> 30u;
					uint32_t       len = 1;
					if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (i + len > num_dwords) break;
					if (type == 3) {
						const uint32_t op = (h >> 8u) & 0xffu;
						if (std::find(std::begin(passed), std::end(passed), static_cast<uint8_t>(op)) == std::end(passed)) {
							if (ops[op]++ == 0) first_at[op] = i;
						}
						if (op == 0x46 && len >= 2) events[ib[i + 1] & 0x3fu]++;
					}
					i += len;
				}
				char ul[600] = {}, el[600] = {};
				int  uw = 0, ew = 0;
				for (uint32_t o = 0; o < 256 && uw < 560; o++)
					if (ops[o] != 0) uw += std::snprintf(ul + uw, sizeof(ul) - static_cast<size_t>(uw), " %02x x%u (first at %u)", o, ops[o], first_at[o]);
				for (uint32_t e = 0; e < 64 && ew < 560; e++)
					if (events[e] != 0) ew += std::snprintf(el + ew, sizeof(el) - static_cast<size_t>(ew), " %u x%u", e, events[e]);
				if (uw != 0 || ew != 0) journal("op census buf %u (%u dwords): not passed:%s | event_write types:%s\n", buf_no, num_dwords, uw ? ul : " none", ew ? el : " none");
			}
'''
s = s.replace(a1, scan + a1, 1)
open(out, "w", encoding="utf-8", newline="\n").write(s)
print("patched: %s -> %s (+%d lines)" % (src, out, (add + scan).count("\n")))
