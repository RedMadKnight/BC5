// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag sr439c, 11-23, the top session's order "locate the stage"): the pass census. In an armed frame every
// pass's output surfaces are copied by the GPU right after the pass, inside the title's own stream, so that a bad frame
// and a good frame can be compared pass by pass. Free of the host (det-tested by test_sr0439c.cpp): the copy geometry,
// the packets, the sampled hash, the memory plan with its degrade order and the arming state machine. The host glue is
// mksr439c.py (the unit: the walk, the blocks, the census after the frame) and mksr439cbe.py (the backend: the arena
// buffer and the block placement).
//
// A pass here is one piece of a submit (a chained or called IB segment, or the root's own packets): the copies of the
// surfaces the piece's ops wrote go at the piece's end (before its outgoing chain packet). In the third title's GFX
// frame the draws sit in ~130 chained pieces of about two draws each (README, F902 class), so a piece is close to a
// pass. A compute job laid out flat (fl439) gets its copies at the job's end.
//
// What is copied (the 11-22 23:48 captures: all outputs of one frame are 16-17 GB, colour targets alone 5.8-6.0 GB, and
// the box has ~1.2 GB MemAvailable and ~1.1 GB GTT headroom in this title, so whole surfaces cannot be copied):
//   - a 2D surface in a 64 KiB swizzle mode: the 64 KiB tiles covering a screen window (default the character's box,
//     x 0.10-0.60, y 0.25-1.00 of the surface) and every `stride`-th tile elsewhere;
//   - anything else (linear, 4 KiB modes, buffers): the first 64 KiB and every `stride`-th 64 KiB chunk;
//   - a DCC colour target also gets its whole key range (one byte per 256 bytes).
// The degrade order when the plan does not fit the budget (the top session's, in this order): 1 skip the surfaces whose
// sampled hash did not change over the survey frame (inputs, not outputs; colour and depth targets are never skipped),
// 2 copy depth targets at every other incarnation, 3 split the frame's copies over two consecutive armed frames (A takes
// the first half of the planned bytes in frame order, B the rest). What still does not fit is skipped and counted.
//
// Sources:
//   - packets: EVENT_WRITE 0x46, RELEASE_MEM 0x49 (8 dwords; dword 1 EVENT_TYPE[5:0] EVENT_INDEX[11:8], dword 2
//     DATA_SEL[31:29], dwords 3-4 the address, 5-6 the data), WAIT_REG_MEM 0x3c (7 dwords; dword 1 FUNCTION[2:0]
//     MEM_SPACE[4], dwords 2-3 the address, 4 the reference, 5 the mask, 6 the poll interval), DMA_DATA 0x50 (7 dwords;
//     dword 1 CP_SYNC[31] SRC_SEL[30:29] DST_SEL[21:20], dwords 2-3 source, 4-5 destination, 6 BYTE_COUNT): the layouts
//     backend/src/direct.cpp (its epilogue RELEASE_MEM 0xC0064900 and its CP DMA wait 0xC0055000 / 0xE0300000, Mesa
//     0866ae7 si_emit_cp_dma), backend/include/bc5/shadow_labels.hpp and k439/pw0439.hpp read; DST_SEL 0 = the
//     address directly, past GL2 (Mesa sid.h V_411_DST_ADDR): TODO(verify); BYTE_COUNT kept at 1 MiB a packet, under
//     the 21-bit field of the oldest form (TODO(verify) the gfx10 width);
//   - events (tools/bc5-agc/regdb/gfx10.json, enum VGT_EVENT_TYPE): CS_PARTIAL_FLUSH 7, CACHE_FLUSH_AND_INV_TS_EVENT 20;
//     EVENT_INDEX 4 for a partial flush (the title's own EVENT_WRITE event 7 index 4, indirect_check.hpp), 5 for an
//     end-of-pipe RELEASE_MEM (direct.cpp's epilogue);
//   - depth target (gfx10.json): DB_DEPTH_SIZE_XY 0x2801c (X_MAX[13:0], Y_MAX[29:16]), DB_Z_INFO 0x28040 (FORMAT[1:0]
//     enum ZFormat: 1 Z_16, 2 Z_24, 3 Z_32_FLOAT; SW_MODE[8:4]), DB_Z_WRITE_BASE 0x28050, DB_Z_WRITE_BASE_HI 0x28070;
//   - swizzle modes: 64 KiB modes 8-11, 16-19, 24-27 (Mesa addrlib AddrSwizzleMode ADDR_SW_64KB_*: TODO(verify)); a
//     64 KiB block holds 2^(16 - log2 bpe) elements, width 2^ceil(bits/2) by height 2^floor(bits/2), and the blocks lie
//     row-major over the padded surface (addrlib's block dimensions and macro-block order: TODO(verify));
//   - on a compute ring only CS_PARTIAL_FLUSH before the copies; that the MEC runs DMA_DATA with CP_SYNC: TODO(verify)
//     (BC5_0439_PASS_MEC=0 keeps the compute rings untouched).
// Plants for the det test (compile-time, never in a build): BC5_SR439C_PLANT_NOCHAIN, _NOWINDOW, _NOSPLIT.
#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

namespace bc5::sr439c {

// ---- copy geometry ----
struct Window {
	double x0 = 0.10, x1 = 0.60, y0 = 0.25, y1 = 1.00; // the character in the writing scene's shots (11-23): x 0.13-0.50, y 0.25-1
};
// "x0,x1,y0,y1" in [0, 1]; anything malformed keeps the default
inline Window parse_window(const char* s) {
	Window w;
	if (s == nullptr || *s == 0) return w;
	double      v[4];
	const char* p = s;
	for (int i = 0; i < 4; i++) {
		char* end = nullptr;
		v[i]      = std::strtod(p, &end);
		if (end == p || *end != (i < 3 ? ',' : 0)) return w;
		p = end + (i < 3 ? 1 : 0);
	}
	for (double x: v)
		if (!(x >= 0 && x <= 1)) return w;
	if (v[0] >= v[1] || v[2] >= v[3]) return w;
	return {v[0], v[1], v[2], v[3]};
}
inline bool is_64k_mode(uint32_t sw) { return (sw >= 8 && sw <= 11) || (sw >= 16 && sw <= 19) || (sw >= 24 && sw <= 27); }
inline uint32_t log2u(uint32_t v) {
	uint32_t r = 0;
	while ((1u << (r + 1)) <= v) r++;
	return r;
}
struct Geo {
	bool     tiled = false;
	uint32_t bw = 0, bh = 0, tx = 0, ty = 0; // block size in elements, blocks across and down
	uint64_t bytes = 0;                      // the padded size (tiled), or the size as given
};
constexpr uint64_t kTile = 64 * 1024;
inline Geo geo(uint32_t w, uint32_t h, uint32_t d, uint32_t bpe, uint32_t sw, uint64_t bytes) {
	Geo g;
	g.bytes = bytes;
	if (w == 0 || h == 0 || bpe == 0 || (bpe & (bpe - 1)) != 0 || bpe > 16 || !is_64k_mode(sw)) return g;
	const uint32_t bits = 16 - log2u(bpe);
	g.bw = 1u << ((bits + 1) / 2), g.bh = 1u << (bits / 2);
	g.tx = (w + g.bw - 1) / g.bw, g.ty = (h + g.bh - 1) / g.bh;
	g.bytes = static_cast<uint64_t>(g.tx) * g.ty * std::max(d, 1u) * kTile;
	g.tiled = true;
	return g;
}
struct Range {
	uint64_t off = 0, len = 0; // in the surface
	bool     window = false;   // inside the window (kept on disk for the offline reader)
};
// The surface's ranges to copy, merged where contiguous (same window flag). A tiled surface: the window's tiles and every
// stride-th other tile (by index); otherwise the first 64 KiB and every stride-th 64 KiB chunk. Only the first slice of
// a 3D or array surface.
inline std::vector<Range> ranges(const Geo& g, uint32_t w, uint32_t h, const Window& win, uint32_t stride) {
	std::vector<Range> out;
	stride = std::max(stride, 1u);
	auto put = [&](uint64_t off, uint64_t len, bool in) {
		if (len == 0) return;
		if (!out.empty() && out.back().off + out.back().len == off && out.back().window == in) out.back().len += len;
		else out.push_back({off, len, in});
	};
	if (g.tiled) {
		const uint32_t cx0 = static_cast<uint32_t>(win.x0 * w) / g.bw, cx1 = (static_cast<uint32_t>(win.x1 * w) + g.bw - 1) / g.bw;
		const uint32_t cy0 = static_cast<uint32_t>(win.y0 * h) / g.bh, cy1 = (static_cast<uint32_t>(win.y1 * h) + g.bh - 1) / g.bh;
		for (uint32_t y = 0; y < g.ty; y++)
			for (uint32_t x = 0; x < g.tx; x++) {
				const uint64_t t  = static_cast<uint64_t>(y) * g.tx + x;
#ifdef BC5_SR439C_PLANT_NOWINDOW
				const bool in = false;
#else
				const bool     in = x >= cx0 && x < cx1 && y >= cy0 && y < cy1;
#endif
				if (in || t % stride == 0) put(t * kTile, kTile, in);
			}
		return out;
	}
	const uint64_t n = (g.bytes + kTile - 1) / kTile;
	for (uint64_t t = 0; t < n; t++)
		if (t == 0 || t % stride == 0) put(t * kTile, std::min(kTile, g.bytes - t * kTile), false);
	return out;
}
inline uint64_t total(const std::vector<Range>& r) {
	uint64_t s = 0;
	for (const auto& x: r) s += x.len;
	return s;
}

// ---- packets ----
inline uint32_t pkt3(uint32_t op, uint32_t body) { return 0xC0000000u | ((body - 1) << 16) | (op << 8); }
constexpr uint32_t kCsPartialFlush = 7, kCacheFlushAndInvTs = 20;
constexpr uint32_t kDmaChunk = 1u << 20;
// GFX ring: an end-of-pipe CACHE_FLUSH_AND_INV_TS_EVENT writing `value` to the fence, and the ME waiting for it, so
// every earlier draw and dispatch is done and its colour and depth data are out of the CB/DB caches.
inline void flush_gfx(std::vector<uint32_t>& o, uint64_t fence, uint32_t value) {
	o.insert(o.end(), {pkt3(0x49, 7), kCacheFlushAndInvTs | (5u << 8), 1u << 29, static_cast<uint32_t>(fence), static_cast<uint32_t>(fence >> 32), value, 0u, 0u});
	o.insert(o.end(), {pkt3(0x3c, 6), 3u | (1u << 4), static_cast<uint32_t>(fence), static_cast<uint32_t>(fence >> 32), value, 0xffffffffu, 4u});
}
// Compute ring: CS_PARTIAL_FLUSH, the title's own form.
inline void flush_mec(std::vector<uint32_t>& o) { o.insert(o.end(), {pkt3(0x46, 1), kCsPartialFlush | (4u << 8)}); }
// CP DMA src -> dst, each packet with CP_SYNC (the ME waits for it: the title's next pass cannot overwrite the source
// before the copy has read it); source read through GL2, destination written directly.
inline void dma(std::vector<uint32_t>& o, uint64_t src, uint64_t dst, uint64_t bytes) {
	for (uint64_t at = 0; at < bytes; at += kDmaChunk) {
		const uint32_t n = static_cast<uint32_t>(std::min<uint64_t>(kDmaChunk, bytes - at));
		const uint64_t s = src + at, d = dst + at;
		o.insert(o.end(), {pkt3(0x50, 6), 0xE0000000u, static_cast<uint32_t>(s), static_cast<uint32_t>(s >> 32), static_cast<uint32_t>(d), static_cast<uint32_t>(d >> 32), n});
	}
}
inline size_t dma_dwords(uint64_t bytes) { return 7 * ((bytes + kDmaChunk - 1) / kDmaChunk); }
constexpr size_t kFlushGfxDwords = 15, kFlushMecDwords = 2;

// The last packet of a buffer, and whether it is a chain (INDIRECT_BUFFER 0x3f / 0x33, size dword bit 20; ib_chain.hpp).
// at: its first dword, or n when the buffer has no complete packet.
inline size_t last_packet(const uint32_t* b, size_t n, bool& chain) {
	size_t last = n;
	chain       = false;
	for (size_t i = 0; i < n;) {
		const uint32_t h = b[i], ty = h >> 30, cnt = (h >> 16) & 0x3fffu;
		size_t         len = 1;
		if (ty == 3 || ty == 0) len = cnt == 0x3fffu ? 1 : cnt + 2;
		if (i + len > n) break;
		last = i;
		const uint32_t op = (h >> 8) & 0xffu;
		chain = ty == 3 && (op == 0x3f || op == 0x33) && len >= 4 && (b[i + 3] & (1u << 20)) != 0;
#ifdef BC5_SR439C_PLANT_NOCHAIN
		chain = false;
#endif
		i += len;
	}
	return last;
}
// Whether a COND_EXEC (0x22; dword 4 EXEC_COUNT[13:0], the dwords it may skip) reaches the dword `at` or past it: then
// nothing may be inserted at `at` (the count would no longer match).
inline bool cond_exec_reaches(const uint32_t* b, size_t n, size_t at) {
	for (size_t i = 0; i < n;) {
		const uint32_t h = b[i], ty = h >> 30, cnt = (h >> 16) & 0x3fffu;
		size_t         len = 1;
		if (ty == 3 || ty == 0) len = cnt == 0x3fffu ? 1 : cnt + 2;
		if (i + len > n) break;
		if (ty == 3 && ((h >> 8) & 0xffu) == 0x22 && len >= 5 && i + len + (b[i + 4] & 0x3fffu) >= at) return true;
		i += len;
	}
	return false;
}

// ---- the depth target (sr0439b's walk does not track the DB) ----
// Context registers 0x000..0x01f as SET_CONTEXT_REG (0x69), LOAD_CONTEXT_REG (0x61) and LOAD_CONTEXT_REG_INDEX (0x9f)
// leave them (the same packet forms sr0439b.hpp's walk reads), CLEAR_STATE (0x12) forgetting them; at a draw (dc439's
// draw opcodes) depth() names the Z surface written, when DB_Z_INFO.FORMAT is valid and the write base is not 0.
struct Depth {
	bool     ok = false;
	uint64_t base = 0;
	uint32_t w = 0, h = 0, bpe = 0, sw = 0;
};
struct DbTrack {
	uint32_t v[0x20] {};
	bool     known[0x20] {};
	void     set(uint32_t r, uint32_t x) {
        if (r < 0x20) v[r] = x, known[r] = true;
	}
	Depth depth() const {
		Depth d;
		if (!known[0x10] || !known[0x14] || !known[0x07]) return d;
		const uint32_t fmt = v[0x10] & 3u;
		if (fmt == 0) return d;
		d.bpe  = fmt == 1 ? 2 : 4; // Z_16; Z_24 and Z_32_FLOAT in 32 bits
		d.sw   = (v[0x10] >> 4) & 0x1fu;
		d.base = (static_cast<uint64_t>(v[0x14]) << 8) | (static_cast<uint64_t>(known[0x1c] ? v[0x1c] & 0xffu : 0u) << 40);
		d.w = (v[0x07] & 0x3fffu) + 1, d.h = ((v[0x07] >> 16) & 0x3fffu) + 1;
		d.ok = d.base != 0;
		return d;
	}
	static bool is_draw(uint32_t op) { return op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x30 || op == 0x35 || op == 0x38; }
	// Walks b[0..n); each draw with a valid depth target calls at(depth). readable(a, bytes) as sr0439b's.
	template <class Readable, class At>
	void walk(const uint32_t* b, size_t n, Readable&& readable, At&& at) {
		for (size_t q = 0; q < n;) {
			const uint32_t h = b[q], ty = h >> 30, cnt = (h >> 16) & 0x3fffu;
			size_t         len = 1;
			if (ty == 3 || ty == 0) len = cnt == 0x3fffu ? 1 : cnt + 2;
			if (q + len > n) break;
			const uint32_t  op = (h >> 8) & 0xffu;
			const uint32_t* p  = b + q;
			if (ty == 3 && cnt != 0x3fffu) {
				if (op == 0x69 && len >= 3) {
					for (size_t k = 2; k < len; k++) set((p[1] & 0xffffu) + static_cast<uint32_t>(k - 2), p[k]);
				} else if (op == 0x12) {
					for (bool& k: known) k = false;
				} else if (op == 0x9f && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					const uint32_t c = p[4] & 0x3fffu;
					const bool     pairs = (p[3] >> 31) != 0;
					if (a != 0 && c != 0 && c <= 4096 && readable(a, static_cast<uint64_t>(c) * (pairs ? 8 : 4))) {
						const auto* m = reinterpret_cast<const volatile uint32_t*>(a);
						for (uint32_t k = 0; k < c; k++) pairs ? set(m[2 * k] & 0xffffu, m[2 * k + 1]) : set((p[3] & 0xffffu) + k, m[k]);
					}
				} else if (op == 0x61 && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					for (size_t k = 3; k + 1 < len; k += 2) {
						const uint32_t r = p[k] & 0xffffu, c = p[k + 1] & 0x3fffu;
						if (r < 0x20 && a != 0 && c != 0 && readable(a + 4ull * r, 4ull * c)) {
							const auto* m = reinterpret_cast<const volatile uint32_t*>(a + 4ull * r);
							for (uint32_t j = 0; j < c; j++) set(r + j, m[j]);
						}
					}
				} else if (is_draw(op)) {
					if (const Depth d = depth(); d.ok) at(d);
				}
			}
			q += len;
		}
	}
};

// ---- the resolve arm (tag rsv439, BC5_0439_DCC_RESOLVE=1): the title's register state, for putting it back ----
// The GFX ring's context registers (0x000..0x3ff from 0x28000), SH registers (0x000..0x3ff from 0xb000), the two
// UCONFIG registers dc439's decompress writes (VGT_PRIMITIVE_TYPE 0x242 with index 1, GE_CNTL 0x25b; dc0439.hpp) and
// the last NUM_INSTANCES, as the stream leaves them: SET_CONTEXT_REG 0x69, LOAD_CONTEXT_REG 0x61,
// LOAD_CONTEXT_REG_INDEX 0x9f, SET_SH_REG 0x76, LOAD_SH_REG 0x5f, LOAD_SH_REG_INDEX 0x63 (pairs), SET_UCONFIG_REG 0x79 /
// _INDEX 0x7a, NUM_INSTANCES 0x2f (the forms sr0439b.hpp's walk reads); CLEAR_STATE 0x12: cmd 1 or 3 pushes the
// context and clears it, cmd 2 pops it back when `stack` (the root buffer, where the device's state stack emulation
// does the same, state_stack.hpp), and every cmd clears it inside chained or called pieces (where the policy turns
// 1 and 2 into 0).
struct RegState {
	std::array<uint32_t, 0x400> ctx {}, sh {};
	std::array<bool, 0x400>     ctx_ok {}, sh_ok {};
	// cblog: where each context register's value came from: 1 SET_CONTEXT_REG, 2 LOAD_CONTEXT_REG(_INDEX) from a table
	// (0 unknown since the frame's start or a clear), and the piece it came in (CtxTrack::piece at the time)
	std::array<uint8_t, 0x400>  ctx_kind {};
	std::array<uint16_t, 0x400> ctx_piece {};
	uint32_t prim = 0, ge = 0, inst = 1;
	bool     prim_ok = false, ge_ok = false, inst_ok = false;
};
struct CtxTrack {
	RegState              s;
	std::vector<RegState> pushed;
	uint16_t              piece = 0; // cblog: the piece being walked (set by the caller)
	uint8_t               kind  = 1; // cblog: 1 a direct set, 2 a table load (set around the loads below)
	void set_ctx(uint32_t r, uint32_t v) {
		if (r < 0x400) s.ctx[r] = v, s.ctx_ok[r] = true, s.ctx_kind[r] = kind, s.ctx_piece[r] = piece;
	}
	void set_sh(uint32_t r, uint32_t v) {
		if (r < 0x400) s.sh[r] = v, s.sh_ok[r] = true;
	}
	// Walks b[0..n); at each draw calls at(*this).
	template <class Readable, class At>
	void walk(const uint32_t* b, size_t n, bool stack, Readable&& readable, At&& at) {
		for (size_t q = 0; q < n;) {
			const uint32_t h = b[q], ty = h >> 30, cnt = (h >> 16) & 0x3fffu;
			size_t         len = 1;
			if (ty == 3 || ty == 0) len = cnt == 0x3fffu ? 1 : cnt + 2;
			if (q + len > n) break;
			const uint32_t  op = (h >> 8) & 0xffu;
			const uint32_t* p  = b + q;
			if (ty == 3 && cnt != 0x3fffu) {
				if (op == 0x69 && len >= 3) {
					for (size_t k = 2; k < len; k++) set_ctx((p[1] & 0xffffu) + static_cast<uint32_t>(k - 2), p[k]);
				} else if (op == 0x12) {
					const uint32_t cmd = len >= 2 ? p[1] & 0xfu : 0;
					if (stack && (cmd == 1 || cmd == 3)) pushed.push_back(s);
					if (stack && cmd == 2 && !pushed.empty()) {
						const RegState top = pushed.back();
						pushed.pop_back();
						s.ctx = top.ctx, s.ctx_ok = top.ctx_ok;
					} else {
						s.ctx_ok.fill(false);
						s.ctx_kind.fill(0);
					}
				} else if (op == 0x9f && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					const uint32_t c = p[4] & 0x3fffu;
					const bool     pairs = (p[3] >> 31) != 0;
					if (a != 0 && c != 0 && c <= 4096 && readable(a, static_cast<uint64_t>(c) * (pairs ? 8 : 4))) {
						const auto* m = reinterpret_cast<const volatile uint32_t*>(a);
						kind = 2;
						for (uint32_t k = 0; k < c; k++) pairs ? set_ctx(m[2 * k] & 0xffffu, m[2 * k + 1]) : set_ctx((p[3] & 0xffffu) + k, m[k]);
						kind = 1;
					}
				} else if (op == 0x61 && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					for (size_t k = 3; k + 1 < len; k += 2) {
						const uint32_t r = p[k] & 0xffffu, c = p[k + 1] & 0x3fffu;
						if (a != 0 && c != 0 && readable(a + 4ull * r, 4ull * c)) {
							const auto* m = reinterpret_cast<const volatile uint32_t*>(a + 4ull * r);
							kind = 2;
							for (uint32_t j = 0; j < c; j++) set_ctx(r + j, m[j]);
							kind = 1;
						}
					}
				} else if (op == 0x76 && len >= 3) {
					for (size_t k = 2; k < len; k++) set_sh((p[1] & 0xffffu) + static_cast<uint32_t>(k - 2), p[k]);
				} else if (op == 0x5f && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					for (size_t k = 3; k + 1 < len; k += 2) {
						const uint32_t r = p[k] & 0xffffu, c = p[k + 1] & 0x3fffu;
						if (a != 0 && c != 0 && r + c <= 0x400 && readable(a + 4ull * r, 4ull * c)) {
							const auto* m = reinterpret_cast<const volatile uint32_t*>(a + 4ull * r);
							for (uint32_t j = 0; j < c; j++) set_sh(r + j, m[j]);
						}
					}
				} else if (op == 0x63 && len >= 5 && (p[3] >> 31) != 0) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					const uint32_t c = p[4] & 0x3fffu;
					if (a != 0 && c != 0 && c <= 4096 && readable(a, 8ull * c)) {
						const auto* m = reinterpret_cast<const volatile uint32_t*>(a);
						for (uint32_t k = 0; k < c; k++) set_sh(m[2 * k] & 0xffffu, m[2 * k + 1]);
					}
				} else if ((op == 0x79 || op == 0x7a) && len >= 3) {
					const uint32_t r0 = p[1] & 0xffffu;
					for (size_t k = 2; k < len; k++) {
						const uint32_t r = r0 + static_cast<uint32_t>(k - 2);
						if (r == 0x242) s.prim = p[k], s.prim_ok = true;
						if (r == 0x25b) s.ge = p[k], s.ge_ok = true;
					}
				} else if (op == 0x2f && len >= 2) {
					s.inst = p[1], s.inst_ok = true;
				} else if (DbTrack::is_draw(op)) {
					at(*this);
				}
			}
			q += len;
		}
	}
};
// One resolve block for a decompress IB `dc` made by dc0439.hpp build() (CLEAR_STATE push at its start, pop at its
// end): the push becomes CLEAR_STATE cmd 0 (what the policy makes of it, and what the decompress was written for), the
// pop is dropped, and the title's state as `st` holds it is written back after: every known context register (runs of
// SET_CONTEXT_REG), the SH registers the decompress writes (SPI_SHADER_PGM_RSRC3_PS 0x007, PS 0x008..0x00b,
// RSRC3_VS 0x046, VS 0x048..0x04d), VGT_PRIMITIVE_TYPE (index 1) and GE_CNTL, NUM_INSTANCES. Registers the title
// never set since its last clear stay at the clear state, as they were. Returns false (out unchanged) when dc has not
// the expected bracket.
inline bool resolve_block(const std::vector<uint32_t>& dc, const RegState& st, std::vector<uint32_t>& out) {
	if (dc.size() < 4 || dc[0] != pkt3(0x12, 1) || dc[1] != 1 || dc[dc.size() - 2] != pkt3(0x12, 1) || dc[dc.size() - 1] != 2) return false;
	out.insert(out.end(), {pkt3(0x12, 1), 0u});
	out.insert(out.end(), dc.begin() + 2, dc.end() - 2);
	for (uint32_t r = 0; r < 0x400;) {
		if (!st.ctx_ok[r]) {
			r++;
			continue;
		}
		uint32_t e = r;
		while (e < 0x400 && st.ctx_ok[e] && e - r < 128) e++;
		out.push_back(pkt3(0x69, 1 + (e - r)));
		out.push_back(r);
		for (uint32_t k = r; k < e; k++) out.push_back(st.ctx[k]);
		r = e;
	}
	for (const uint32_t r: {0x007u, 0x008u, 0x009u, 0x00au, 0x00bu, 0x046u, 0x048u, 0x049u, 0x04au, 0x04bu, 0x04cu, 0x04du})
		if (st.sh_ok[r]) out.insert(out.end(), {pkt3(0x76, 2), r, st.sh[r]});
	if (st.prim_ok) out.insert(out.end(), {pkt3(0x7a, 2), 0x242u | (1u << 28), st.prim});
	if (st.ge_ok) out.insert(out.end(), {pkt3(0x79, 2), 0x25bu, st.ge});
	if (st.inst_ok) out.insert(out.end(), {pkt3(0x2f, 1), st.inst});
	return true;
}

// ---- the sampled hash (the "unchanged" test of the degrade order and of the reader) ----
// 64 samples of 64 bytes spread over [0, bytes); read(off, dst, n) reads the guest memory (false: gone).
template <class Read>
inline uint64_t sampled_hash(uint64_t bytes, Read&& read) {
	uint64_t h = 1469598103934665603ull;
	uint8_t  b[64];
	if (bytes < 64) return 0;
	for (uint32_t i = 0; i < 64; i++) {
		const uint64_t off = ((bytes - 64) * i / 63) & ~uint64_t {63};
		if (!read(off, b, 64)) return 0;
		for (uint8_t x: b) h = (h ^ x) * 1099511628211ull;
	}
	return h | 1; // 0 means unread
}
inline uint64_t fnv(const uint8_t* p, size_t n) {
	uint64_t h = 1469598103934665603ull;
	for (size_t i = 0; i < n; i++) h = (h ^ p[i]) * 1099511628211ull;
	return h;
}

// ---- the plan: what the survey frame found, and the level that fits ----
struct PlanItem {
	uint64_t bytes   = 0;     // the copy of one incarnation
	bool     target  = false; // a colour or depth target the op wrote (never skipped by the hash)
	bool     depth   = false;
	bool     changed = true; // the survey's sampled hash changed (or the surface is a target)
	uint32_t depth_k = 0;    // its depth incarnation number (level 2 keeps the even ones)
};
struct Plan {
	int      level = 0; // 0 all, 1 hash skip, 2 + depth half rate, 3 + two frames
	uint64_t need[4] {};
	uint64_t budget = 0, arena = 0, split_at = 0; // split_at: frame A copies while the running total is below it
	bool     truncated = false;
};
inline bool keep(const PlanItem& x, int level) {
	if (level >= 1 && !x.target && !x.changed) return false;
	if (level >= 2 && x.depth && (x.depth_k & 1u) != 0) return false;
	return true;
}
inline Plan plan(const std::vector<PlanItem>& items, uint64_t budget) {
	Plan p;
	p.budget = budget;
	for (int l = 0; l <= 2; l++)
		for (const auto& x: items)
			if (keep(x, l)) p.need[l] += x.bytes;
	// level 3: the split point where the running total reaches half, and the larger half
	uint64_t run = 0, half = p.need[2] / 2;
	p.split_at = 0;
	for (const auto& x: items) {
		if (!keep(x, 2)) continue;
		if (run < half && run + x.bytes >= half) p.split_at = run + x.bytes;
		run += x.bytes;
	}
	if (p.split_at == 0) p.split_at = run;
	p.need[3] = std::max(p.split_at, run - p.split_at);
#ifdef BC5_SR439C_PLANT_NOSPLIT
	p.need[3] = run;
#endif
	p.level   = 3;
	for (int l = 0; l <= 3; l++)
		if (p.need[l] <= budget) {
			p.level = l;
			break;
		}
	p.arena     = std::min(p.need[p.level], budget);
	p.truncated = p.need[p.level] > budget;
	return p;
}
// The budget: the word's cap, less than MemAvailable - 768 MiB and the GTT headroom - 256 MiB (each known when > 0).
inline uint64_t budget(uint64_t cap, uint64_t mem_available, uint64_t gtt_total, uint64_t gtt_used) {
	uint64_t b = cap;
	constexpr uint64_t kMemReserve = uint64_t {768} << 20, kGttReserve = uint64_t {256} << 20;
	if (mem_available > 0) b = std::min<uint64_t>(b, mem_available > kMemReserve ? mem_available - kMemReserve : 0);
	if (gtt_total > 0) {
		const uint64_t room = gtt_total > gtt_used ? gtt_total - gtt_used : 0;
		b = std::min<uint64_t>(b, room > kGttReserve ? room - kGttReserve : 0);
	}
	return b & ~(kTile - 1);
}

// ---- arming ----
// "60,100": seconds since the first flip, each fires once
inline std::vector<double> parse_times(const char* s) {
	std::vector<double> t;
	if (s == nullptr) return t;
	std::string x(s);
	size_t      at = 0;
	while (at < x.size()) {
		const size_t e = x.find(',', at);
		const std::string f = x.substr(at, e == std::string::npos ? std::string::npos : e - at);
		char* end = nullptr;
		const double v = std::strtod(f.c_str(), &end);
		if (end != f.c_str() && *end == 0 && v >= 0) t.push_back(v);
		if (e == std::string::npos) break;
		at = e + 1;
	}
	std::sort(t.begin(), t.end());
	return t;
}
enum class Act { None, Survey, SurveyEnd, Copy, CopyEnd };
// idle -> (arm) -> survey frame -> at its flip: SurveyEnd (drain, plan, arena) -> copy frame A -> CopyEnd (drain, census)
// -> [copy frame B -> CopyEnd] -> idle. A pad hold (L3 + R3, 1 s) or a scripted time arms; an arm while busy waits.
struct Machine {
	int    state = 0; // 0 idle, 1 armed, 2 survey, 3 copy A, 4 copy B
	bool   split = false, combo = false;
	double combo_since = -1, t0 = -1;
	int    pending = 0; // arms waiting
	std::vector<double> times;
	size_t next_time = 0;
	void pad(bool both, double t) {
		if (both && !combo) combo_since = t;
		combo = both;
	}
	Act flip(double t) {
		if (t0 < 0) t0 = t;
		if (combo && combo_since >= 0 && t - combo_since >= 1.0) combo_since = -1, pending++;
		while (next_time < times.size() && t - t0 >= times[next_time]) next_time++, pending++;
		switch (state) {
		case 0:
			if (pending == 0) return Act::None;
			pending--;
			state = 2;
			return Act::Survey;
		case 2: state = 3; return Act::SurveyEnd; // the copy frame A starts at this flip, after the plan
		case 3:
			if (split) {
				state = 4;
				return Act::CopyEnd; // A's census; B starts at this flip
			}
			state = 0;
			return Act::CopyEnd;
		case 4: state = 0; return Act::CopyEnd;
		default: return Act::None;
		}
	}
	bool frame_b() const { return state == 4; }
};

} // namespace bc5::sr439c
