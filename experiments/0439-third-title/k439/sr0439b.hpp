// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag sr439b): the frame-dump catcher for the third title's progressive blackening (the name-writing
// scene; the touchpad fix tc439 made the brush work and the black still came, 11-22 22:4x). Free of the host: the
// descriptor decode, the per-frame walk of a submit's pieces, the NaN/Inf census of a surface's bytes, the dark-fraction
// auto-arm and the capture's state machine. The host glue (bc5LleAgc.cpp, mksr439b.py) feeds it the pieces of every
// submit while a frame is recorded, and calls the census and the dump at the title's flips after a drain. Det-tested by
// test_sr0439b.cpp on any machine.
//
// What one capture gives (BC5_0439_FRAME_DUMP=<private dir>): frame F is recorded from one flip to the next (every
// submit on every ring: each draw's colour targets, each draw's and dispatch's user-data V#s, inline or one or two table
// levels deep, the clears); at F's flip every surface found is censused (NaN, Inf, zero, dark per format) and dumped raw
// (tiled as the GPU left it); F+1 is recorded on and censused at its flip. A second capture follows 5 s later. The reader
// (sr439read.py) names the first op in frame order whose output surface holds NaN/Inf while the surfaces it read did not.
//
// Sources (Mesa ab2374a, 2026-10-22):
//   - context and SH register offsets and fields: src/amd/registers/gfx10.json (CB_COLOR0_BASE 0x28c60 .. ATTRIB3
//     0x28ee0, CB_TARGET_MASK 0x28238, CB_COLOR_CONTROL 0x28808 MODE[6:4], DB_RENDER_CONTROL 0x28000,
//     SPI_SHADER_PGM_LO_PS 0xb020, SPI_SHADER_USER_DATA_PS_0 0xb030 (32), COMPUTE_PGM_LO 0xb830, COMPUTE_USER_DATA_0
//     0xb900 (16)); enums ColorFormat, SurfaceNumber, CBMode;
//   - descriptors: src/amd/registers/gfx10-rsrc.json (SQ_IMG_RSRC_WORD1 BASE_ADDRESS_HI[7:0] FORMAT[28:20] WIDTH_LO[31:30];
//     WORD2 WIDTH_HI[11:0] HEIGHT[27:14]; WORD3 SW_MODE[24:20] TYPE[31:28]; WORD4 DEPTH[12:0]; SQ_BUF_RSRC_WORD1
//     BASE_ADDRESS_HI[15:0] STRIDE[29:16]; WORD3 FORMAT[18:12] TYPE[31:30]); enum GFX10_FORMAT;
//   - image TYPE values 8..15 (SQ_RSRC_IMG_1D .. 2D_MSAA_ARRAY): TODO(verify) against amdgfxregs.h; buffer TYPE 0.
//   - packets as in dc0439.hpp / fp0439.hpp (sid.h): SET_CONTEXT_REG 0x69, LOAD_CONTEXT_REG 0x61,
//     LOAD_CONTEXT_REG_INDEX 0x9f, CLEAR_STATE 0x12, SET_SH_REG 0x76, LOAD_SH_REG 0x5f, LOAD_SH_REG_INDEX 0x63, draws
//     dc439::is_draw, DISPATCH_DIRECT 0x15 / INDIRECT 0x16, DMA_DATA 0x50 (SRC_SEL dword1 [30:29] = 2 data,
//     DST_ADDR dwords 4-5, BYTE_COUNT dword 6 [25:0]: TODO(verify) the gfx10 field positions).
// What the census reads is the surface as the GPU left it in memory: a DCC-compressed target is counted raw and flagged
// (its numbers are not the pixels); tiled layouts are counted as they are (a count does not need the pixel order).
#pragma once

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <deque>
#include <string>
#include <unordered_map>
#include <vector>

namespace bc5::sr439b {

enum class Kind : uint8_t { Other, U8x4, U10x3, F16, F32, F11F11F10, F10F11F11 };
inline const char* kind_name(Kind k) {
	switch (k) {
	case Kind::U8x4: return "u8x4";
	case Kind::U10x3: return "u10x3";
	case Kind::F16: return "f16";
	case Kind::F32: return "f32";
	case Kind::F11F11F10: return "r10g11b11f"; // GFX10 11_11_10_FLOAT / COLOR_11_11_10
	case Kind::F10F11F11: return "r11g11b10f"; // GFX10 10_11_11_FLOAT / COLOR_10_11_11 (PIPE R11G11B10_FLOAT)
	default: return "other";
	}
}
struct Fmt {
	Kind     kind = Kind::Other;
	uint32_t bpe  = 0; // bytes per element (0: not a format we size)
};

// GFX10_FORMAT (image and buffer descriptors).
inline Fmt from_gfx10(uint32_t f) {
	switch (f) {
	case 13: return {Kind::F16, 2};             // 16_FLOAT
	case 29: return {Kind::F16, 4};             // 16_16_FLOAT
	case 71: return {Kind::F16, 8};             // 16_16_16_16_FLOAT
	case 22: case 140: return {Kind::F32, 4};   // 32_FLOAT, 32_FLOAT_CLAMP
	case 64: return {Kind::F32, 8};             // 32_32_FLOAT
	case 74: return {Kind::F32, 12};            // 32_32_32_FLOAT
	case 77: return {Kind::F32, 16};            // 32_32_32_32_FLOAT
	case 43: return {Kind::F11F11F10, 4};       // 11_11_10_FLOAT
	case 36: return {Kind::F10F11F11, 4};       // 10_11_11_FLOAT
	case 56: case 130: return {Kind::U8x4, 4};  // 8_8_8_8_UNORM, _SRGB
	case 50: case 44: return {Kind::U10x3, 4};  // 2_10_10_10_UNORM, 10_10_10_2_UNORM
	case 1: case 5: return {Kind::Other, 1};    // 8_UNORM, 8_UINT
	case 14: case 18: case 7: case 11: return {Kind::Other, 2};
	case 20: case 21: case 23: case 27: case 60: case 48: case 54: return {Kind::Other, 4};
	case 62: case 63: case 65: case 69: return {Kind::Other, 8};
	case 72: case 73: return {Kind::Other, 12};
	case 75: case 76: return {Kind::Other, 16};
	default: return {};
	}
}

// CB_COLORn_INFO FORMAT (ColorFormat) with NUMBER_TYPE (SurfaceNumber, 7 FLOAT, 0 UNORM, 6 SRGB).
inline Fmt from_cb(uint32_t format, uint32_t number) {
	const bool fl = number == 7, un = number == 0 || number == 6;
	switch (format) {
	case 2: return fl ? Fmt {Kind::F16, 2} : Fmt {Kind::Other, 2};
	case 5: return fl ? Fmt {Kind::F16, 4} : Fmt {Kind::Other, 4};
	case 12: return fl ? Fmt {Kind::F16, 8} : Fmt {Kind::Other, 8};
	case 4: return fl ? Fmt {Kind::F32, 4} : Fmt {Kind::Other, 4};
	case 11: return fl ? Fmt {Kind::F32, 8} : Fmt {Kind::Other, 8};
	case 14: return fl ? Fmt {Kind::F32, 16} : Fmt {Kind::Other, 16};
	case 7: return fl ? Fmt {Kind::F11F11F10, 4} : Fmt {Kind::Other, 4};
	case 6: return fl ? Fmt {Kind::F10F11F11, 4} : Fmt {Kind::Other, 4};
	case 10: return un ? Fmt {Kind::U8x4, 4} : Fmt {Kind::Other, 4};
	case 9: case 8: return un ? Fmt {Kind::U10x3, 4} : Fmt {Kind::Other, 4};
	case 1: return {Kind::Other, 1};
	case 3: return {Kind::Other, 2};
	default: return {};
	}
}

struct Desc {
	bool     ok = false, image = false;
	uint64_t base = 0, bytes = 0;
	uint32_t w = 0, h = 0, d = 1, fmt = 0, sw_mode = 0, type = 0, stride = 0;
	Fmt      f;
	bool     compressed = false; // census v2: SQ_IMG_RSRC_WORD6 COMPRESSION_EN [21] (gfx10-rsrc.json): its bytes are not pixels
	uint32_t word6 = 0, word7 = 0; // exp 0439 (tag dk439): the V#'s DCC words as read (metadata address: word6 [31:24] and word7)
};

constexpr uint32_t kMaxDim   = 16384;
constexpr uint64_t kMaxBytes = 512ull << 20;

// An image V# (8 dwords; the first 5 decoded).
inline Desc decode_image(const uint32_t* d) {
	Desc r;
	r.type = d[3] >> 28;
	if (r.type < 8) return r;
	r.base = ((static_cast<uint64_t>(d[1] & 0xffu) << 32) | d[0]) << 8;
	r.fmt  = (d[1] >> 20) & 0x1ffu;
	r.w    = (((d[1] >> 30) & 3u) | ((d[2] & 0xfffu) << 2)) + 1;
	r.h    = ((d[2] >> 14) & 0x3fffu) + 1;
	r.d    = (d[4] & 0x1fffu) + 1;
	if (r.type != 10 && r.type != 12 && r.type != 13 && r.type != 15) r.d = 1; // only 3D and arrays have a depth
	r.sw_mode    = (d[3] >> 20) & 0x1fu;
	r.compressed = ((d[6] >> 21) & 1u) != 0;
	r.word6 = d[6], r.word7 = d[7]; // exp 0439 (tag dk439)
	r.f          = from_gfx10(r.fmt);
	if (r.base == 0 || r.f.bpe == 0 || r.w > kMaxDim || r.h > kMaxDim || r.d > 2048) return r;
	r.bytes = static_cast<uint64_t>(r.w) * r.h * r.d * r.f.bpe;
	if (r.bytes > kMaxBytes) return r;
	r.image = true;
	r.ok    = true;
	return r;
}

// A buffer V# (4 dwords). Accepted only with the usual X,Y,Z,W selects or a float format, a size and a base.
inline Desc decode_buffer(const uint32_t* d) {
	Desc r;
	if ((d[3] >> 30) != 0) return r;
	r.base   = (static_cast<uint64_t>(d[1] & 0xffffu) << 32) | d[0];
	r.stride = (d[1] >> 16) & 0x3fffu;
	r.fmt    = (d[3] >> 12) & 0x7fu;
	const bool xyzw = (d[3] & 0xfffu) == 0xfacu;
	r.f      = from_gfx10(r.fmt);
	if (r.f.kind == Kind::Other && !xyzw) return r;
	if (r.f.bpe == 0) r.f = {Kind::Other, 4}; // census v2: a raw / structured buffer is NOT counted as floats (exp 0439 run 2346: 1143 such false NaN surfaces)
	r.bytes = static_cast<uint64_t>(d[2]) * (r.stride != 0 ? r.stride : 1u);
	if (r.base == 0 || (r.base & 3u) != 0 || d[2] == 0 || r.bytes < 4 || r.bytes > kMaxBytes) return r;
	r.ok = true;
	return r;
}

// ---- the census ----
struct Census {
	uint64_t elems = 0, nan = 0, inf = 0, zero = 0, dark = 0, bytes = 0;
	bool     done  = false;
	void add(const Census& o) {
		elems += o.elems, nan += o.nan, inf += o.inf, zero += o.zero, dark += o.dark, bytes += o.bytes;
		done = true;
	}
};
// One small float of e exponent bits and m mantissa bits at bit `at` of v.
inline void small_float(uint32_t v, int at, int e, int m, Census& c) {
	const uint32_t x = (v >> at) & ((1u << (e + m)) - 1u), ex = x >> m, mn = x & ((1u << m) - 1u);
	if (ex == (1u << e) - 1u) (mn != 0 ? c.nan : c.inf)++;
}
// Counts p[0..n) as kind k (n is cut to whole 4-byte words; f16 counts per half).
inline Census count(const uint8_t* p, uint64_t n, Kind k) {
	Census c;
	c.bytes = n;
	c.done  = true;
	n &= ~3ull;
	for (uint64_t i = 0; i < n; i += 4) {
		uint32_t v;
		std::memcpy(&v, p + i, 4);
		switch (k) {
		case Kind::F16:
			for (int s = 0; s < 32; s += 16) {
				const uint32_t hlf = (v >> s) & 0xffffu;
				c.elems++;
				if ((hlf & 0x7c00u) == 0x7c00u) ((hlf & 0x3ffu) != 0 ? c.nan : c.inf)++;
				else if ((hlf & 0x7fffu) == 0) c.zero++;
			}
			break;
		case Kind::F32:
			c.elems++;
			if ((v & 0x7f800000u) == 0x7f800000u) ((v & 0x7fffffu) != 0 ? c.nan : c.inf)++;
			else if ((v & 0x7fffffffu) == 0) c.zero++;
			break;
		case Kind::F10F11F11: // 10_11_11_FLOAT = R11G11B10: R [10:0] e5m6, G [21:11] e5m6, B [31:22] e5m5 (Mesa ab2374a
		                      // src/amd/common/gfx10_format_table.py:37 maps PIPE_FORMAT_R11G11B10_FLOAT to it)
			c.elems++;
			small_float(v, 0, 5, 6, c), small_float(v, 11, 5, 6, c), small_float(v, 22, 5, 5, c);
			c.zero += v == 0;
			break;
		case Kind::F11F11F10: // 11_11_10_FLOAT, the mirror: R [9:0] e5m5, G [20:10] e5m6, B [31:21] e5m6 (TODO(verify))
			c.elems++;
			small_float(v, 0, 5, 5, c), small_float(v, 10, 5, 6, c), small_float(v, 21, 5, 6, c);
			c.zero += v == 0;
			break;
		case Kind::U8x4: {
			c.elems++;
			const uint32_t a = v & 0xffu, b = (v >> 8) & 0xffu, g = (v >> 16) & 0xffu;
			c.dark += std::max(a, std::max(b, g)) < 16u;
			c.zero += v == 0;
			break;
		}
		case Kind::U10x3: {
			c.elems++;
			const uint32_t a = v & 0x3ffu, b = (v >> 10) & 0x3ffu, g = (v >> 20) & 0x3ffu;
			c.dark += std::max(a, std::max(b, g)) < 64u;
			c.zero += v == 0;
			break;
		}
		default:
			c.elems++;
			c.zero += v == 0;
			break;
		}
	}
	return c;
}

// The dark fraction of a display surface (8 bits a channel, 4 bytes a pixel), from `samples` evenly spaced pixels.
inline double dark_fraction(const uint8_t* px, uint64_t pixels, uint32_t samples = 4096) {
	if (pixels == 0 || samples == 0) return 0.0;
	uint32_t dark = 0;
	for (uint32_t i = 0; i < samples; i++) {
		const uint64_t k = pixels * i / samples;
		const uint8_t* q = px + 4 * k;
		dark += std::max(q[0], std::max(q[1], q[2])) < 16u;
	}
	return static_cast<double>(dark) / samples;
}

// ---- the auto-arm: a slow rise of the dark fraction (not a fade to black) ----
// Arms when the fraction has stood at >= base + rise and >= `floor` for `hold` seconds, base being the median of the
// samples from 10 s to 4 s before the rise began, with no sample in the hold at >= `fade` (a fade to black reaches it
// within a second; the blackening went 86-98 %). Once armed it stays latched until the fraction stays below `rearm`
// for 10 s (once per scene).
struct AutoArm {
	double rise = 0.20, floor = 0.60, fade = 0.99, hold = 2.0, rearm = 0.40;
	std::deque<std::pair<double, double>> s; // (t, dark)
	bool   latched = false;
	double low_since = -1.0, above_since = -1.0;
	bool feed(double t, double d) {
		s.emplace_back(t, d);
		while (!s.empty() && s.front().first < t - 20.0) s.pop_front();
		if (latched) {
			if (d < rearm) {
				if (low_since < 0) low_since = t;
				if (t - low_since >= 10.0) latched = false, low_since = -1.0;
			} else
				low_since = -1.0;
			return false;
		}
		std::vector<double> base;
		const double t0 = above_since >= 0 ? above_since : t;
		for (const auto& [ts, v]: s)
			if (ts >= t0 - 10.0 && ts <= t0 - 4.0) base.push_back(v);
		if (base.size() < 3) return above_since = -1.0, false;
		std::sort(base.begin(), base.end());
		const double b = base[base.size() / 2];
		if (d < floor || d < b + rise || d >= fade) return above_since = -1.0, false;
		if (above_since < 0) above_since = t;
		for (const auto& [ts, v]: s)
			if (ts >= above_since && v >= fade) return above_since = -1.0, false;
		if (t - above_since < hold) return false;
		latched     = true;
		above_since = -1.0;
		return true;
	}
};

// exp 0439 (tag dk439): a histogram of DCC key bytes (one byte per 256-byte block of the target): 0xff, 0x00 and the
// rest, with the most common other value. What each code means is not claimed here; the census records the bytes.
struct KeyHist {
	uint64_t n = 0, ff = 0, z = 0, other = 0;
	uint64_t cnt[256] {};
	void add(const uint8_t* p, size_t len) {
		for (size_t i = 0; i < len; i++) cnt[p[i]]++;
		n += len;
	}
	void top(uint32_t& v, uint64_t& c) const {
		v = 0, c = 0;
		for (uint32_t k = 1; k < 255; k++)
			if (cnt[k] > c) v = k, c = cnt[k];
	}
	void finish() {
		ff    = cnt[0xff];
		z     = cnt[0];
		other = n - ff - z;
	}
};

// ---- the walk: one frame's ops and the surfaces they bind ----
struct Surface {
	uint64_t base = 0, bytes = 0;
	uint32_t w = 0, h = 0, d = 1, fmt = 0, sw_mode = 0, first_op = 0;
	Fmt      f;
	bool     cb = false, image = false, buffer = false, dcc = false, cb_float_fmt = false;
	uint32_t cb_writes = 0, refs = 0;
	// exp 0439 (tag dk439): a CB target's CB_COLORn_DCC_CONTROL and DCC_BASE (regs 0x318 + n*0xf + 6 and + 0xd, with
	// CB_COLORn_DCC_BASE_EXT 0x3a8 + n; tools/bc5-agc/regdb/gfx10.json), an image's V# words 6 and 7, and the census's
	// histogram of the target's DCC key bytes at the end of the frame (0xff, 0x00, other; the most common other value)
	uint64_t dcc_base = 0;
	uint32_t dcc_control = 0, word6 = 0, word7 = 0;
	uint64_t keys_n = 0, keys_ff = 0, keys_00 = 0, keys_other = 0;
	uint32_t keys_top = 0, keys_top_n = 0;
	Census   at[2]; // at the end of frame F and of F+1
	std::string file;
};
struct OpRef {
	uint32_t surf = 0;
	bool     cb   = false; // a colour target this draw writes (else a V# it may read or write)
};
struct Op {
	uint32_t seq = 0, submit = 0;
	int      ring = 0;
	char     kind = 'd'; // 'd' draw, 'c' dispatch
	uint64_t pgm = 0;
	uint32_t cb_mode = 1; // CB_COLOR_CONTROL MODE at the draw
	std::vector<OpRef> refs;
};
struct Clear {
	uint32_t seq = 0, submit = 0;
	int      ring = 0;
	std::string what;
};

// ---- the raw events (tag sr439b-raw; the dump session's offline per-program resolver, the maintainer's consent) ----
// events.bin, little-endian records: u32 magic 0x39343345 ("E439"), u32 type, u32 bytes (the whole record), then:
//   1 EVENT  u32 seq, u32 submit, i32 ring, u32 piece, u32 dword, u32 kind ('d' / 'c'), u32 n, n x (u32 reg, u32 value):
//            SH registers (reg = offset from 0xb000 >> 2, flag 0x10000 clear) and context registers (offset from
//            0x28000 >> 2, flag 0x10000 set), the host's shadow state at the op
//   2 BLOCK  u32 seq, u32 level, u64 address, u32 length, u64 hash, the bytes (level 1: 0x200 at each mapped pointer
//            pair of the op's user data; level 2: 0x600 at each 8-aligned mapped qword inside a level-1 block)
//   3 REF    u32 seq, u32 level, u64 address, u32 length, u64 hash: the same bytes as an earlier BLOCK (dedup by content)
//   4 PGM    u64 address, u32 length, the bytes (a program's first sight: the largest readable power of two up to 0x20000)
//   5 PIECE  u32 submit, i32 ring, u32 piece, u64 address, u32 dwords, the dwords (every piece of every submit of F)
// SH registers per event: compute 0x207..0x209, 0x20c, 0x20d, 0x212, 0x213, 0x240..0x24f; draws, per stage base
// (PS 0x08, VS 0x48, GS 0x88, ES 0xc8, HS 0x108, LS 0x148): base + 0..19 (PGM_LO/HI, RSRC1/2, then 16 user data).
// Context registers per draw: 0x007, 0x010..0x01f, 0x08e, 0x318..0x3bf. TODO(verify) the stage bases other than PS
// against gfx10.json (they come from the dump session's notes).
class Raw {
public:
	static constexpr size_t kCap = 256ull << 20;
	std::vector<uint8_t> out;
	bool     full = false;
	uint64_t blocks = 0, refs = 0, programs = 0;
	std::unordered_map<uint64_t, bool> seen_blocks, seen_pgms;
	static uint64_t fnv(const uint8_t* p, size_t n) {
		uint64_t h = 1469598103934665603ull;
		for (size_t i = 0; i < n; i++) h = (h ^ p[i]) * 1099511628211ull;
		return h ^ n;
	}
	void begin(uint32_t type, uint32_t bytes) { put32(0x39343345u), put32(type), put32(bytes); }
	void put32(uint32_t v) { out.insert(out.end(), reinterpret_cast<uint8_t*>(&v), reinterpret_cast<uint8_t*>(&v) + 4); }
	void put64(uint64_t v) { out.insert(out.end(), reinterpret_cast<uint8_t*>(&v), reinterpret_cast<uint8_t*>(&v) + 8); }
	void putb(const uint8_t* p, size_t n) { out.insert(out.end(), p, p + n); }
	bool room(size_t n) {
		if (out.size() + n > kCap) full = true;
		return !full;
	}
};

class Recorder {
public:
	static constexpr size_t kMaxSurfaces = 4096, kMaxOps = 200000, kMaxClears = 20000;
	std::vector<Surface> surf;
	std::vector<Op>      ops;
	std::vector<Clear>   clears;
	uint32_t             submits = 0, ptr_tables = 0, unreadable = 0;
	Raw*                 raw = nullptr; // set while the raw events are collected (frame F)

	void reset() { *this = Recorder(); }

	// One submit's pieces in order (src, n), on `ring`. readable(a, bytes) must say whether guest memory is there.
	template <class Pieces, class Readable>
	void submit(const Pieces& pieces, int ring, Readable readable) {
		const uint32_t sub = submits++;
		RingState&     rs  = rings_[ring]; // the context and SH registers carry over between a ring's jobs, as on the GPU
		uint32_t       k   = 0;
		for (const auto& pc: pieces) {
			piece_ = k++;
			if (raw != nullptr && raw->room(36 + 4 * pc.second)) {
				raw->begin(5, static_cast<uint32_t>(36 + 4 * pc.second));
				raw->put32(sub), raw->put32(static_cast<uint32_t>(ring)), raw->put32(piece_), raw->put64(reinterpret_cast<uint64_t>(pc.first)), raw->put32(static_cast<uint32_t>(pc.second));
				raw->putb(reinterpret_cast<const uint8_t*>(pc.first), 4 * pc.second);
			}
			walk(pc.first, pc.second, ring, sub, rs.cx, rs.sh, readable);
		}
	}

private:
	struct Ctx {
		std::array<uint32_t, 0x400> v {};
		std::array<bool, 0x400>     ok {};
		void set(uint32_t r, uint32_t x) {
			if (r < 0x400) v[r] = x, ok[r] = true;
		}
		uint32_t get(uint32_t r, uint32_t dflt = 0) const { return r < 0x400 && ok[r] ? v[r] : dflt; }
	};
	struct RingState {
		Ctx                         cx;
		std::array<uint32_t, 0x400> sh {};
	};
	std::unordered_map<int, RingState>     rings_;
	uint32_t                               piece_ = 0, dword_ = 0;
	std::unordered_map<uint64_t, uint32_t> index_; // (base ^ fmt<<48 ^ kind) -> surface

	uint32_t add(const Desc& d, bool cb, bool dcc, uint32_t seq) {
		const uint64_t key = d.base ^ (static_cast<uint64_t>(d.fmt) << 48) ^ (static_cast<uint64_t>(d.image ? 1 : 2) << 60) ^ (cb ? 1ull << 63 : 0);
		if (auto it = index_.find(key); it != index_.end()) {
			Surface& s = surf[it->second];
			s.bytes    = std::max(s.bytes, d.bytes);
			s.refs++;
			return it->second;
		}
		if (surf.size() >= kMaxSurfaces) return UINT32_MAX;
		Surface s;
		s.base = d.base, s.bytes = d.bytes, s.w = d.w, s.h = d.h, s.d = d.d, s.fmt = d.fmt, s.sw_mode = d.sw_mode, s.f = d.f;
		s.cb = cb, s.image = d.image && !cb, s.buffer = !d.image && !cb, s.dcc = dcc, s.first_op = seq, s.refs = 1;
		s.word6 = d.word6, s.word7 = d.word7; // exp 0439 (tag dk439)
		surf.push_back(s);
		index_.emplace(key, static_cast<uint32_t>(surf.size() - 1));
		return static_cast<uint32_t>(surf.size() - 1);
	}

	// The V#s in user data u[0..n): inline, and through pointer pairs one and two levels deep.
	template <class Readable>
	void scan_user_data(const uint32_t* u, uint32_t n, Op& op, Readable& readable, int depth) {
		for (uint32_t i = 0; i + 4 <= n; i++) {
			if (i + 8 <= n) {
				const Desc d = decode_image(u + i);
				if (d.ok && readable(d.base, d.bytes)) {
					ref(op, add(d, false, d.compressed, op.seq), false);
					i += 7;
					continue;
				}
			}
			const Desc b = decode_buffer(u + i);
			if (b.ok && readable(b.base, b.bytes)) {
				ref(op, add(b, false, false, op.seq), false);
				i += 3;
				continue;
			}
		}
		if (depth >= 2) return;
		uint32_t followed = 0;
		for (uint32_t i = 0; i + 1 < n && followed < 64; i++) {
			const uint64_t a = (static_cast<uint64_t>(u[i + 1]) << 32) | u[i];
			if ((a & 3u) != 0 || u[i + 1] == 0 || u[i + 1] > 0xffffu) continue;
			if (!readable(a, 256)) {
				unreadable++;
				continue;
			}
			uint32_t t[64];
			const auto* m = reinterpret_cast<const volatile uint32_t*>(a);
			for (int k = 0; k < 64; k++) t[k] = m[k];
			ptr_tables++;
			followed++;
			scan_user_data(t, 64, op, readable, depth + 1);
		}
	}
	static void ref(Op& op, uint32_t s, bool cb) {
		if (s == UINT32_MAX) return;
		for (auto& r: op.refs)
			if (r.surf == s) return void(r.cb = r.cb || cb);
		op.refs.push_back({s, cb});
	}
	void clear(int ring, uint32_t sub, std::string what) {
		if (clears.size() < kMaxClears) clears.push_back({static_cast<uint32_t>(ops.size()), sub, ring, std::move(what)});
	}

	template <class Readable>
	void walk(const uint32_t* w, size_t n, int ring, uint32_t sub, Ctx& cx, std::array<uint32_t, 0x400>& sh, Readable& readable) {
		for (size_t q = 0; q < n;) {
			const uint32_t h = w[q], ty = h >> 30u, cnt = (h >> 16u) & 0x3fffu;
			size_t         len = 1;
			if (ty == 3 || ty == 0) len = cnt == 0x3fffu ? 1 : cnt + 2;
			if (q + len > n) break;
			const uint32_t  op = (h >> 8u) & 0xffu;
			const uint32_t* p  = w + q;
			dword_             = static_cast<uint32_t>(q);
			if (ty == 3 && cnt != 0x3fffu) {
				if (op == 0x69 && len >= 3) {
					for (size_t k = 2; k < len; k++) cx.set((p[1] & 0xffffu) + static_cast<uint32_t>(k - 2), p[k]);
				} else if (op == 0x12) {
					clear(ring, sub, "CLEAR_STATE cmd " + std::to_string(len >= 2 ? p[1] & 0xfu : 0u));
					cx.ok.fill(false);
				} else if (op == 0x9f && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					const uint32_t c = p[4] & 0x3fffu;
					const bool     pairs = (p[3] >> 31) != 0;
					if (a != 0 && c != 0 && c <= 4096 && readable(a, static_cast<uint64_t>(c) * (pairs ? 8 : 4))) {
						const auto* m = reinterpret_cast<const volatile uint32_t*>(a);
						for (uint32_t k = 0; k < c; k++) pairs ? cx.set(m[2 * k] & 0xffffu, m[2 * k + 1]) : cx.set((p[3] & 0xffffu) + k, m[k]);
					}
				} else if (op == 0x61 && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					for (size_t k = 3; k + 1 < len; k += 2) {
						const uint32_t r = p[k] & 0xffffu, c = p[k + 1] & 0x3fffu;
						if (a != 0 && c != 0 && readable(a + 4ull * r, 4ull * c)) {
							const auto* m = reinterpret_cast<const volatile uint32_t*>(a + 4ull * r);
							for (uint32_t j = 0; j < c; j++) cx.set(r + j, m[j]);
						}
					}
				} else if (op == 0x76 && len >= 3) {
					for (size_t k = 2; k < len; k++)
						if (const uint32_t r = (p[1] & 0xffffu) + static_cast<uint32_t>(k - 2); r < 0x400) sh[r] = p[k];
				} else if (op == 0x5f && len >= 5) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					for (size_t k = 3; k + 1 < len; k += 2) {
						const uint32_t r = p[k] & 0xffffu, c = p[k + 1] & 0x3fffu;
						if (a != 0 && c != 0 && r + c <= 0x400 && readable(a + 4ull * r, 4ull * c)) {
							const auto* m = reinterpret_cast<const volatile uint32_t*>(a + 4ull * r);
							for (uint32_t j = 0; j < c; j++) sh[r + j] = m[j];
						}
					}
				} else if (op == 0x63 && len >= 5 && (p[3] >> 31) != 0) {
					const uint64_t a = (p[1] & ~3u) | (static_cast<uint64_t>(p[2] & 0xffffu) << 32);
					const uint32_t c = p[4] & 0x3fffu;
					if (a != 0 && c != 0 && c <= 4096 && readable(a, 8ull * c)) {
						const auto* m = reinterpret_cast<const volatile uint32_t*>(a);
						for (uint32_t k = 0; k < c; k++)
							if (const uint32_t r = m[2 * k] & 0xffffu; r < 0x400) sh[r] = m[2 * k + 1];
					}
				} else if (op == 0x50 && len >= 7 && ((p[1] >> 29) & 3u) == 2) { // DMA_DATA from data: a fill
					const uint64_t dst = p[4] | (static_cast<uint64_t>(p[5]) << 32);
					clear(ring, sub, "DMA_DATA fill 0x" + hex(dst) + " bytes " + std::to_string(p[6] & 0x3ffffffu) + " value 0x" + hex(p[2]));
				} else if (is_draw(op) && ops.size() < kMaxOps) {
					draw(ring, sub, cx, sh, readable);
				} else if ((op == 0x15 || op == 0x16) && ops.size() < kMaxOps) {
					Op o;
					o.seq = static_cast<uint32_t>(ops.size()), o.submit = sub, o.ring = ring, o.kind = 'c';
					o.pgm = (static_cast<uint64_t>(sh[0x20c]) << 8) | (static_cast<uint64_t>(sh[0x20d] & 0xffu) << 40);
					scan_user_data(sh.data() + 0x240, 16, o, readable, 0);
					if (raw != nullptr) emit(o, nullptr, sh, readable);
					ops.push_back(std::move(o));
				}
			}
			q += len;
		}
	}
	static bool is_draw(uint32_t op) { return op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x30 || op == 0x35 || op == 0x38; }
	static std::string hex(uint64_t v) {
		char b[24];
		std::snprintf(b, sizeof(b), "%llx", static_cast<unsigned long long>(v));
		return b;
	}

	template <class Readable>
	void draw(int ring, uint32_t sub, const Ctx& cx, const std::array<uint32_t, 0x400>& sh, Readable& readable) {
		Op o;
		o.seq = static_cast<uint32_t>(ops.size()), o.submit = sub, o.ring = ring, o.kind = 'd';
		o.pgm     = (static_cast<uint64_t>(sh[0x08]) << 8) | (static_cast<uint64_t>(sh[0x09] & 0xffu) << 40);
		o.cb_mode = (cx.get(0x202, 0x10) >> 4) & 7u;
		const uint32_t tm = cx.get(0x08e, 0xffffffffu);
		if (o.cb_mode != 1) clear(ring, sub, "CB_COLOR_CONTROL MODE " + std::to_string(o.cb_mode) + " draw");
		if ((cx.get(0x000) & 3u) != 0) clear(ring, sub, "DB_RENDER_CONTROL depth/stencil clear draw");
		for (uint32_t m = 0; m < 8; m++) {
			const uint32_t b = 0x318 + m * 0xf;
			if (((tm >> (4 * m)) & 0xfu) == 0 || !cx.ok[b]) continue;
			const uint32_t info = cx.get(b + 4);
			const Fmt      f    = from_cb((info >> 2) & 0x1fu, (info >> 8) & 7u);
			if (((info >> 2) & 0x1fu) == 0 || f.bpe == 0) continue;
			Desc d;
			d.base    = (static_cast<uint64_t>(cx.get(b)) << 8) | (static_cast<uint64_t>(cx.get(0x390 + m) & 0xffu) << 40);
			const uint32_t a2 = cx.get(0x3b0 + m), a3 = cx.get(0x3b8 + m), view = cx.get(b + 3);
			d.w       = ((a2 >> 14) & 0x3fffu) + 1, d.h = (a2 & 0x3fffu) + 1;
			d.d       = std::max(((view >> 13) & 0x1fffu) + 1, (a3 & 0x1fffu) + 1);
			d.fmt     = 1000 + ((info >> 2) & 0x1fu) * 8 + ((info >> 8) & 7u); // the CB format, told apart from GFX10_FORMAT
			d.sw_mode = (a3 >> 14) & 0x1fu;
			d.f       = f;
			d.bytes   = static_cast<uint64_t>(d.w) * d.h * d.d * f.bpe;
			d.image   = true;
			if (d.base == 0 || d.bytes > kMaxBytes || !readable(d.base, d.bytes)) continue;
			const uint32_t s = add(d, true, ((info >> 28) & 1u) != 0, o.seq);
			if (s != UINT32_MAX) surf[s].cb_writes++;
			if (s != UINT32_MAX && ((info >> 28) & 1u) != 0 && surf[s].dcc_base == 0) { // exp 0439 (tag dk439)
				surf[s].dcc_base    = (static_cast<uint64_t>(cx.get(b + 0xd)) << 8) | (static_cast<uint64_t>(cx.get(0x3a8 + m) & 0xffu) << 40);
				surf[s].dcc_control = cx.get(b + 6);
			}
			if (s != UINT32_MAX && (info >> 13) & 1u) clear(ring, sub, "CB fast clear enabled on target " + std::to_string(s) + " (CLEAR_WORD0 0x" + hex(cx.get(b + 0xb)) + ")");
			ref(o, s, true);
		}
		scan_user_data(sh.data() + 0x0c, 32, o, readable, 0);
		if (raw != nullptr) emit(o, &cx, sh, readable);
		ops.push_back(std::move(o));
	}

	template <class Readable>
	void block(uint32_t seq, uint32_t level, uint64_t a, uint32_t len, Readable& readable) {
		if (!readable(a, len)) return;
		std::vector<uint8_t> b(len);
		const auto*          m = reinterpret_cast<const volatile uint8_t*>(a);
		for (uint32_t i = 0; i < len; i++) b[i] = m[i];
		const uint64_t h   = Raw::fnv(b.data(), len);
		const bool     dup = raw->seen_blocks.count(h) != 0;
		if (!raw->room(40 + (dup ? 0 : len))) return;
		raw->begin(dup ? 3 : 2, 40 + (dup ? 0 : len));
		raw->put32(seq), raw->put32(level), raw->put64(a), raw->put32(len), raw->put64(h);
		if (!dup) raw->putb(b.data(), len), raw->seen_blocks[h] = true, raw->blocks++;
		else raw->refs++;
		if (level != 1) return;
		for (uint32_t i = 0; i + 8 <= len; i += 8) {
			uint64_t q;
			std::memcpy(&q, b.data() + i, 8);
			if ((q & 3u) == 0 && (q >> 48) == 0 && (q >> 32) != 0) block(seq, 2, q, 0x600, readable);
		}
	}
	template <class Readable>
	void program(uint64_t a, Readable& readable) {
		if (a == 0 || raw->seen_pgms.count(a) != 0) return;
		raw->seen_pgms[a] = true;
		uint32_t len = 0x20000; // the dump session: a real program of 0xc4c4 bytes (0x80001ff200); the largest readable power of two up to this
		while (len >= 0x100 && !readable(a, len)) len /= 2;
		if (len < 0x100 || !raw->room(24 + len)) return;
		raw->begin(4, 24 + len);
		raw->put64(a), raw->put32(len);
		const auto* m = reinterpret_cast<const volatile uint8_t*>(a);
		for (uint32_t i = 0; i < len; i++) raw->out.push_back(static_cast<uint8_t>(m[i]));
		raw->programs++;
	}
	// One op's event: its shadow registers, its level-1 and level-2 blocks, its programs.
	template <class Readable>
	void emit(const Op& o, const Ctx* cx, const std::array<uint32_t, 0x400>& sh, Readable& readable) {
		std::vector<std::pair<uint32_t, uint32_t>> regs;
		std::vector<uint64_t>                      pgms;
		const auto shr = [&](uint32_t r) { regs.emplace_back(r, sh[r]); };
		std::vector<uint32_t> bases;
		if (o.kind == 'c') {
			for (uint32_t r: {0x207u, 0x208u, 0x209u, 0x20cu, 0x20du, 0x212u, 0x213u}) shr(r);
			for (uint32_t r = 0x240; r < 0x250; r++) shr(r);
			pgms.push_back(o.pgm);
			bases = {0x240};
		} else {
			for (uint32_t b: {0x08u, 0x48u, 0x88u, 0xc8u, 0x108u, 0x148u}) {
				for (uint32_t r = b; r < b + 20; r++) shr(r);
				pgms.push_back((static_cast<uint64_t>(sh[b]) << 8) | (static_cast<uint64_t>(sh[b + 1] & 0xffu) << 40));
				bases.push_back(b + 4);
			}
			const auto cr = [&](uint32_t r) { regs.emplace_back(0x10000u | r, cx->get(r)); };
			cr(0x007);
			for (uint32_t r = 0x010; r < 0x020; r++) cr(r);
			cr(0x08e);
			for (uint32_t r = 0x318; r < 0x3c0; r++) cr(r);
		}
		const uint32_t bytes = static_cast<uint32_t>(12 + 28 + 8 * regs.size());
		if (!raw->room(bytes)) return;
		raw->begin(1, bytes);
		raw->put32(o.seq), raw->put32(o.submit), raw->put32(static_cast<uint32_t>(o.ring)), raw->put32(piece_), raw->put32(dword_), raw->put32(static_cast<uint32_t>(o.kind));
		raw->put32(static_cast<uint32_t>(regs.size()));
		for (auto& [r, v]: regs) raw->put32(r), raw->put32(v);
		for (uint32_t b: bases) // level 1: every adjacent user-data pair that is a mapped pointer
			for (uint32_t i = 0; i + 1 < 16; i++) {
				const uint64_t a = (static_cast<uint64_t>(sh[b + i + 1]) << 32) | sh[b + i];
				if ((a & 3u) == 0 && sh[b + i + 1] != 0 && sh[b + i + 1] <= 0xffffu) block(o.seq, 1, a, 0x200, readable);
			}
		for (uint64_t p: pgms) program(p, readable);
	}
};

// ---- the capture's state machine (the host calls it at every flip of a registered display buffer) ----
enum class Act { None, Record, CensusDump, CensusOnly };
struct Machine {
	int    state   = 0; // 0 idle, 1 armed, 2 recording F, 3 recording F+1, 4 waiting for the second capture
	int    capture = 0; // 0 the onset, 1 five seconds later
	double second_at = 0, combo_since = -1;
	bool   combo = false;
	// A pad combination held: arm at the flip it has been held 1 s.
	void pad(bool both, double t) {
		if (both && !combo) combo_since = t;
		combo = both;
	}
	bool arm(const char* why) {
		if (state != 0) return false;
		(void)why;
		state = 1, capture = 0;
		return true;
	}
	Act flip(double t) {
		if (state == 0 && combo && combo_since >= 0 && t - combo_since >= 1.0) combo_since = -1, arm("pad");
		switch (state) {
		case 1: state = 2; return Act::Record;
		case 2: state = 3; return Act::CensusDump;
		case 3:
			if (capture == 0) state = 4, second_at = t + 5.0;
			else state = 0;
			return Act::CensusOnly;
		case 4:
			if (t >= second_at) {
				capture = 1, state = 2;
				return Act::Record;
			}
			return Act::None;
		default: return Act::None;
		}
	}
	bool recording() const { return state == 2 || state == 3; }
};

} // namespace bc5::sr439b
