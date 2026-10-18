#!/usr/bin/env python3
# Experiment 0157, sixth step: for a filtered draw, the vertices it indexes: the index buffer (INDEX_BASE
# 0x26 / INDEX_TYPE 0x2a packets before the draw in the same buffer; Mesa sid.h), the first vertex buffer
# (the first V# of the table GS user data 4-5 point at), the index range and the bounding box of the first
# two floats of each vertex, plus the first vertex's eight dwords; and a re-check: the vertex range is
# remembered for 600 ms and, at every later filtered buffer, compared with memory, a change journaled once
# ("vertex rewrite ... ms after submission").
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


# a pre-scan of the buffer for INDEX_BASE / INDEX_TYPE, and the remembered ranges
rep("""			const uint32_t buf_no  = journaled;
			bool           counted = draw_journal_filter.second == 0 && draw_journal_ps.empty();
			if (counted) journaled++;""",
    """			const uint32_t buf_no  = journaled;
			bool           counted = draw_journal_filter.second == 0 && draw_journal_ps.empty();
			if (counted) journaled++;
			// Experiment 0157: INDEX_BASE (0x26: lo, hi) and INDEX_TYPE (0x2a) by offset, for the vertex lines.
			struct IdxState {
				size_t   off;
				uint64_t base;
				uint32_t type;
			};
			std::vector<IdxState> idx_states;
			{
				uint64_t ib_base = 0;
				uint32_t ib_type = 0;
				for (uint32_t i = 0; i < num_dwords;) {
					const uint32_t h = ib[i], type = h >> 30u;
					uint32_t       len = 1;
					if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
					if (i + len > num_dwords) break;
					if (type == 3) {
						const uint32_t op = (h >> 8u) & 0xffu;
						if (op == 0x26 && len >= 3) { ib_base = ib[i + 1] | (static_cast<uint64_t>(ib[i + 2] & 0xffffu) << 32u); idx_states.push_back({i, ib_base, ib_type}); }
						if (op == 0x2a && len >= 2) { ib_type = ib[i + 1] & 3u; idx_states.push_back({i, ib_base, ib_type}); }
					}
					i += len;
				}
			}
			struct VtxRange {
				uint64_t             addr;
				double               t;
				uint32_t             buf, off;
				std::vector<uint8_t> copy;
			};
			static std::vector<VtxRange> vtx_ranges;
			static std::mutex            vtx_mutex;
			{
				// the re-check of the remembered ranges (600 ms), on this buffer's submission
				std::lock_guard lock(vtx_mutex);
				const double    now = timing_now();
				for (auto it = vtx_ranges.begin(); it != vtx_ranges.end();) {
					if (now - it->t > 0.6) { it = vtx_ranges.erase(it); continue; }
					const uint32_t* m = read(it->addr, it->copy.size());
					if (m != nullptr && std::memcmp(m, it->copy.data(), it->copy.size()) != 0) {
						size_t first = 0;
						while (first < it->copy.size() && reinterpret_cast<const uint8_t*>(m)[first] == it->copy[first]) first++;
						journal("vertex rewrite: buf %u at %u range %010" PRIx64 "+%zx changed %.0f ms after submission (first byte %zx)\\n", it->buf, it->off, it->addr, it->copy.size(), (now - it->t) * 1000.0, first);
						it = vtx_ranges.erase(it);
						continue;
					}
					++it;
				}
			}""")

# the vertex line, after the bake table lines (end of the extras block)
rep("""							journal("bake table %s ud%u %010" PRIx64 ":%s\\n", stage == 0 ? "ps" : "gs", k, addr, tb);
						}
					}
				}""",
    """							journal("bake table %s ud%u %010" PRIx64 ":%s\\n", stage == 0 ? "ps" : "gs", k, addr, tb);
						}
					}
					// Experiment 0157: the vertices of a DRAW_INDEX_OFFSET_2 (0x35: max_size, index_offset, count;
					// Mesa sid.h) through the first V# (base dword 0 | dword 1 bits 15:0 << 32, stride dword 1 bits
					// 29:16) of the table GS user data 4-5 point at, and the index buffer set before the draw.
					if (((pkt[0] >> 8u) & 0xffu) == 0x35 && pkt.size() >= 4) {
						uint64_t ib_base = 0;
						uint32_t ib_type = 0;
						for (const IdxState& st: idx_states) {
							if (st.off >= off) break;
							ib_base = st.base;
							ib_type = st.type;
						}
						const uint64_t gtab = reg(S::Sh, 0x8c + 4) | (static_cast<uint64_t>(reg(S::Sh, 0x8c + 5) & 0xffffu) << 32u);
						const uint32_t* tv  = gtab != 0 ? read(gtab, 16) : nullptr;
						const uint64_t  vb  = tv != nullptr ? (tv[0] | (static_cast<uint64_t>(tv[1] & 0xffffu) << 32u)) : 0;
						const uint32_t  vst = tv != nullptr ? (tv[1] >> 16u) & 0x3fffu : 0;
						const uint32_t  isz = ib_type == 0 ? 2u : 4u, cnt = pkt[3];
						const uint64_t  ia  = ib_base + static_cast<uint64_t>(pkt[2]) * isz;
						if (ib_base != 0 && vb != 0 && vst != 0 && cnt != 0 && cnt <= 65536 && read(ia, static_cast<uint64_t>(cnt) * isz) != nullptr) {
							uint32_t imin = 0xffffffffu, imax = 0;
							for (uint32_t q = 0; q < cnt; q++) {
								const uint32_t idx = isz == 2 ? reinterpret_cast<const uint16_t*>(ia)[q] : reinterpret_cast<const uint32_t*>(ia)[q];
								imin = std::min(imin, idx), imax = std::max(imax, idx);
							}
							const uint64_t va0 = vb + static_cast<uint64_t>(imin) * vst, vlen = static_cast<uint64_t>(imax - imin + 1) * vst;
							if (vlen <= 0x100000 && read(va0, vlen) != nullptr) {
								float    xmin = 1e30f, xmax = -1e30f, ymin = 1e30f, ymax = -1e30f;
								uint32_t v0[8] = {};
								std::memcpy(v0, reinterpret_cast<const void*>(va0), std::min<size_t>(32, vst));
								for (uint32_t q = 0; q < cnt; q++) {
									const uint32_t idx = isz == 2 ? reinterpret_cast<const uint16_t*>(ia)[q] : reinterpret_cast<const uint32_t*>(ia)[q];
									float          xy[2];
									std::memcpy(xy, reinterpret_cast<const void*>(vb + static_cast<uint64_t>(idx) * vst), 8);
									xmin = std::min(xmin, xy[0]), xmax = std::max(xmax, xy[0]), ymin = std::min(ymin, xy[1]), ymax = std::max(ymax, xy[1]);
								}
								journal("bake vertices buf %u at %zu: idx %010" PRIx64 " +%u x%u (%u-bit) -> %u..%u | vb %010" PRIx64 " stride %u | box %.1f,%.1f-%.1f,%.1f | v0 %08x %08x %08x %08x %08x %08x %08x %08x\\n", buf_no, off, ib_base,
								        pkt[2], cnt, isz * 8, imin, imax, vb, vst, static_cast<double>(xmin), static_cast<double>(ymin), static_cast<double>(xmax), static_cast<double>(ymax), v0[0], v0[1], v0[2], v0[3], v0[4], v0[5], v0[6], v0[7]);
								std::lock_guard lock(vtx_mutex);
								if (vtx_ranges.size() < 4096) {
									VtxRange r {va0, timing_now(), buf_no, static_cast<uint32_t>(off), {}};
									r.copy.assign(reinterpret_cast<const uint8_t*>(va0), reinterpret_cast<const uint8_t*>(va0) + vlen);
									vtx_ranges.push_back(std::move(r));
								}
							}
						} else {
							journal("bake vertices buf %u at %zu: idx %010" PRIx64 " +%u x%u | vb %010" PRIx64 " stride %u: unreadable\\n", buf_no, off, ib_base, pkt[2], cnt, vb, vst);
						}
					}
				}""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
