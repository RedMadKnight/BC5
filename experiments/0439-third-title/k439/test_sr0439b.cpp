// BC5 exp 0439 (tag sr439b): det test of sr0439b.hpp on synthetic descriptors, command buffers and surfaces.
//   clang++ -std=c++20 -Wall -Wextra -Werror -o test_sr0439b test_sr0439b.cpp && ./test_sr0439b
#include "sr0439b.hpp"

#include <cstdio>
#include <cstdlib>
#ifdef _WIN32
#include <malloc.h>
#endif
#include <utility>
#include <vector>

namespace {
int g_fail = 0;
#define CHECK(c)                                                                                                       \
	do {                                                                                                               \
		if (!(c)) {                                                                                                    \
			std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c);                                                    \
			g_fail++;                                                                                                  \
		}                                                                                                              \
	} while (0)

using namespace bc5::sr439b;

// guest memory stand-in: aligned blocks whose host addresses are the "guest" addresses
struct Mem {
	std::vector<std::pair<uint64_t, uint64_t>> r;
	void* alloc(size_t n) {
		#ifdef _WIN32
		void* p = _aligned_malloc((n + 255) & ~size_t(255), 256);
#else
		void* p = std::aligned_alloc(256, (n + 255) & ~size_t(255));
#endif
		std::memset(p, 0, n);
		r.emplace_back(reinterpret_cast<uint64_t>(p), n);
		return p;
	}
	bool readable(uint64_t a, uint64_t n) const {
		for (auto& [b, s]: r)
			if (a >= b && a + n <= b + s) return true;
		return false;
	}
};

void image_vsharp(uint32_t* d, uint64_t base, uint32_t w, uint32_t h, uint32_t fmt, uint32_t type = 9) {
	const uint64_t b = base >> 8;
	const uint32_t wm = w - 1, hm = h - 1;
	d[0] = static_cast<uint32_t>(b);
	d[1] = static_cast<uint32_t>((b >> 32) & 0xff) | (fmt << 20) | ((wm & 3u) << 30);
	d[2] = (wm >> 2) | (hm << 14);
	d[3] = 0xfacu | (type << 28);
	d[4] = 0;
	d[5] = d[6] = d[7] = 0;
}
void buffer_vsharp(uint32_t* d, uint64_t base, uint32_t stride, uint32_t n, uint32_t fmt) {
	d[0] = static_cast<uint32_t>(base);
	d[1] = static_cast<uint32_t>(base >> 32) | (stride << 16);
	d[2] = n;
	d[3] = 0xfacu | (fmt << 12);
}
uint32_t pkt(uint32_t op, uint32_t count) { return 0xC0000000u | (count << 16) | (op << 8); }

void t_decode() {
	Mem      m;
	void*    px = m.alloc(64 * 32 * 8);
	uint32_t d[8];
	image_vsharp(d, reinterpret_cast<uint64_t>(px), 64, 32, 71);
	const Desc i = decode_image(d);
	CHECK(i.ok && i.image && i.base == reinterpret_cast<uint64_t>(px) && i.w == 64 && i.h == 32 && i.f.kind == Kind::F16 && i.bytes == 64 * 32 * 8);
	d[3] &= 0x0fffffffu; // TYPE 0: not an image
	CHECK(!decode_image(d).ok);
	image_vsharp(d, reinterpret_cast<uint64_t>(px), 64, 32, 999 & 0x1ff); // an unknown format
	CHECK(!decode_image(d).ok);
	buffer_vsharp(d, reinterpret_cast<uint64_t>(px), 16, 100, 0);
	const Desc b = decode_buffer(d);
	CHECK(b.ok && !b.image && b.bytes == 1600 && b.f.kind == Kind::Other); // census v2: a raw buffer is not counted as floats
	d[3] = 0x123u; // unusual selects, format 0: refused
	CHECK(!decode_buffer(d).ok);
	CHECK(from_cb(12, 7).kind == Kind::F16 && from_cb(12, 7).bpe == 8 && from_cb(10, 0).kind == Kind::U8x4 && from_cb(7, 7).kind == Kind::F11F11F10);
}

void t_count() {
	uint16_t h[8] = {0x3c00, 0x7c00, 0xfc00, 0x7e00, 0x0000, 0x8000, 0x7c01, 0x4000}; // 1, +inf, -inf, nan, 0, -0, nan, 2
	Census   c = count(reinterpret_cast<const uint8_t*>(h), sizeof(h), Kind::F16);
	CHECK(c.elems == 8 && c.inf == 2 && c.nan == 2 && c.zero == 2);
	float    f[4] = {1.0f, 0.0f, 0.0f, 0.0f};
	uint32_t nanv = 0x7fc00000u, infv = 0x7f800000u;
	std::memcpy(&f[1], &nanv, 4), std::memcpy(&f[2], &infv, 4);
	c = count(reinterpret_cast<const uint8_t*>(f), sizeof(f), Kind::F32);
	CHECK(c.elems == 4 && c.nan == 1 && c.inf == 1 && c.zero == 1);
	// 10_11_11_FLOAT = R11G11B10: R [10:0] e5m6 (exponent 31 = 0x7c0), G [21:11], B [31:22] e5m5 (0x3e0)
	uint32_t p[4] = {0x7c0u | 1u /* R nan */, 0x7c0u << 11 /* G inf */, (0x3e0u | 2u) << 22 /* B nan */, 0};
	c = count(reinterpret_cast<const uint8_t*>(p), sizeof(p), Kind::F10F11F11);
	CHECK(c.nan == 2 && c.inf == 1 && c.zero == 1);
	// the mirror 11_11_10: R [9:0] e5m5 (0x3e0), G [20:10] e5m6, B [31:21] e5m6
	uint32_t q[2] = {0x3e0u /* R inf */, 0x7c1u << 21 /* B nan */};
	c = count(reinterpret_cast<const uint8_t*>(q), sizeof(q), Kind::F11F11F10);
	CHECK(c.nan == 1 && c.inf == 1);
	{ // an image V# with COMPRESSION_EN (word 6 bit 21) is decoded as compressed
		uint32_t d[8];
		static uint8_t img[64 * 4];
		image_vsharp(d, reinterpret_cast<uint64_t>(img) & ~0xffull, 8, 8, 56);
		d[6] = 1u << 21;
		CHECK(decode_image(d).compressed);
		d[6] = 0;
		CHECK(!decode_image(d).compressed);
	}
	uint8_t px[4 * 4] = {0, 0, 0, 255, 200, 10, 10, 255, 5, 5, 15, 0, 16, 0, 0, 0};
	c = count(px, sizeof(px), Kind::U8x4);
	CHECK(c.dark == 2 && c.elems == 4);
	CHECK(dark_fraction(px, 4, 4) == 0.5);
}

void t_arm() {
	{ // a slow darkening: 0.3 for 12 s, then +0.06/s to 0.9
		AutoArm a;
		double  armed = -1;
		for (int i = 0; i <= 30 * 30; i++) {
			const double t = i / 30.0, d = t < 12 ? 0.3 : std::min(0.9, 0.3 + 0.06 * (t - 12));
			if (a.feed(t, d) && armed < 0) armed = t;
		}
		CHECK(armed > 17.0 && armed < 20.0); // >= 0.6 from t 17 (0.3 + 0.2 = 0.5 earlier), held 2 s
	}
	{ // a fade to black in half a second, black for 3 s, back
		AutoArm a;
		bool    any = false;
		for (int i = 0; i <= 30 * 30; i++) {
			const double t = i / 30.0;
			const double d = t < 12 ? 0.3 : t < 12.5 ? 0.3 + 1.4 * (t - 12) : t < 15.5 ? 1.0 : 0.3;
			any = a.feed(t, d) || any;
		}
		CHECK(!any);
	}
	{ // latched once a scene: a second rise right after does not arm; after 10 s below 0.4 it may again
		AutoArm a;
		int     n = 0;
		for (int i = 0; i <= 80 * 30; i++) {
			const double t = i / 30.0;
			double       d = 0.3;
			if (t >= 12 && t < 30) d = 0.85;
			if (t >= 31 && t < 33) d = 0.3;
			if (t >= 33 && t < 45) d = 0.85;
			if (t >= 60) d = 0.85;
			n += a.feed(t, d) ? 1 : 0;
		}
		CHECK(n == 2);
	}
}

void t_walk() {
	Mem   m;
	auto* rt  = static_cast<uint8_t*>(m.alloc(128 * 64 * 8)); // the draw's colour target: 128x64 16_16_16_16 FLOAT
	auto* uav = static_cast<uint8_t*>(m.alloc(32 * 32 * 4));  // the dispatch's image: 32x32 32_FLOAT, through a table
	auto* buf = static_cast<uint8_t*>(m.alloc(4096));         // an inline buffer V#
	auto* tbl = static_cast<uint32_t*>(m.alloc(0x200));
	image_vsharp(tbl + 8, reinterpret_cast<uint64_t>(uav), 32, 32, 22);
	const uint64_t rt_a = reinterpret_cast<uint64_t>(rt), tb = reinterpret_cast<uint64_t>(tbl);
	std::vector<uint32_t> ib;
	ib.push_back(pkt(0x12, 0)), ib.push_back(0); // CLEAR_STATE cmd 0
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x08e), ib.push_back(0xf); // CB_TARGET_MASK: MRT0
	ib.push_back(pkt(0x69, 5)), ib.push_back(0x318), ib.push_back(static_cast<uint32_t>(rt_a >> 8)), ib.push_back(0), ib.push_back(0), ib.push_back(0),
	    ib.push_back((12u << 2) | (7u << 8) | (1u << 28)); // BASE, PITCH, SLICE, VIEW, INFO 16_16_16_16 FLOAT DCC
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x390), ib.push_back(static_cast<uint32_t>(rt_a >> 40)); // BASE_EXT
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x3b0), ib.push_back((127u << 14) | 63u);                // ATTRIB2 128x64
	ib.push_back(pkt(0x76, 2)), ib.push_back(0x08), ib.push_back(0x12345678), ib.push_back(0x11);      // PS program
	ib.push_back(pkt(0x2d, 1)), ib.push_back(3), ib.push_back(2);                                      // DRAW_INDEX_AUTO
	uint32_t bv[4];
	buffer_vsharp(bv, reinterpret_cast<uint64_t>(buf), 0, 4096, 22);
	ib.push_back(pkt(0x76, 6)), ib.push_back(0x240), ib.push_back(static_cast<uint32_t>(tb)), ib.push_back(static_cast<uint32_t>(tb >> 32)),
	    ib.push_back(bv[0]), ib.push_back(bv[1]), ib.push_back(bv[2]), ib.push_back(bv[3]); // CS user data: table pointer, inline buffer
	ib.push_back(pkt(0x76, 2)), ib.push_back(0x20c), ib.push_back(0x00abcdef), ib.push_back(0x22);
	ib.push_back(pkt(0x15, 3)), ib.push_back(1), ib.push_back(1), ib.push_back(1), ib.push_back(0); // DISPATCH_DIRECT
	Recorder r;
	std::vector<std::pair<const uint32_t*, size_t>> pieces = {{ib.data(), ib.size()}};
	r.submit(pieces, 0, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); });
	CHECK(r.ops.size() == 2 && r.ops[0].kind == 'd' && r.ops[1].kind == 'c');
	CHECK(r.ops[0].pgm == (0x12345678ull << 8 | 0x11ull << 40) && r.ops[1].pgm == (0xabcdefull << 8 | 0x22ull << 40));
	CHECK(r.surf.size() == 3);
	bool cb = false, img = false, bf = false;
	for (auto& s: r.surf) {
		if (s.cb && s.base == rt_a && s.w == 128 && s.h == 64 && s.f.kind == Kind::F16 && s.dcc && s.cb_writes == 1) cb = true;
		if (s.image && s.base == reinterpret_cast<uint64_t>(uav) && s.f.kind == Kind::F32 && s.first_op == 1) img = true;
		if (s.buffer && s.base == reinterpret_cast<uint64_t>(buf) && s.bytes == 4096) bf = true;
	}
	CHECK(cb && img && bf);
	CHECK(r.ops[0].refs.size() == 1 && r.ops[0].refs[0].cb && r.ops[1].refs.size() == 2 && r.ptr_tables >= 1);
	CHECK(!r.clears.empty() && r.clears[0].what == "CLEAR_STATE cmd 0");
	// the same submit again: no new surfaces, more refs
	r.submit(pieces, 1, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); });
	CHECK(r.surf.size() == 3 && r.ops.size() == 4 && r.submits == 2);
	// a later job on ring 0 that only draws: the colour target set by the first job still applies
	std::vector<uint32_t> ib2 = {pkt(0x2d, 1), 3, 2};
	std::vector<std::pair<const uint32_t*, size_t>> p2 = {{ib2.data(), ib2.size()}};
	r.submit(p2, 0, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); });
	CHECK(r.ops.size() == 5 && r.ops[4].refs.size() == 1 && r.ops[4].refs[0].cb);
	r.submit(p2, 7, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); }); // another ring: nothing bound there
	CHECK(r.ops.size() == 6 && r.ops[5].refs.empty());
	{ // the raw events: every record framed, its size as its type says; the dispatch's table as a level-1 block
		Recorder rr;
		Raw      raw;
		rr.raw = &raw;
		rr.submit(pieces, 0, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); });
		rr.submit(pieces, 0, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); }); // the same table again: a REF
		size_t   at = 0;
		uint32_t n[6] = {};
		bool     framed = true, table = false;
		while (at + 12 <= raw.out.size()) {
			uint32_t h[3];
			std::memcpy(h, raw.out.data() + at, 12);
			if (h[0] != 0x39343345u || h[1] < 1 || h[1] > 5 || at + h[2] > raw.out.size()) {
				framed = false;
				break;
			}
			n[h[1]]++;
			uint32_t len = 0;
			uint64_t addr = 0;
			if (h[1] == 1) {
				uint32_t cnt;
				std::memcpy(&cnt, raw.out.data() + at + 36, 4);
				framed = framed && h[2] == 40 + 8 * cnt;
			} else if (h[1] == 2 || h[1] == 3) {
				std::memcpy(&addr, raw.out.data() + at + 20, 8);
				std::memcpy(&len, raw.out.data() + at + 28, 4);
				framed = framed && h[2] == 40 + (h[1] == 2 ? len : 0);
				table  = table || (addr == tb && len == 0x200);
			} else if (h[1] == 4) {
				std::memcpy(&len, raw.out.data() + at + 20, 4);
				framed = framed && h[2] == 24 + len;
			} else if (h[1] == 5) {
				std::memcpy(&len, raw.out.data() + at + 32, 4);
				framed = framed && h[2] == 36 + 4 * len;
			}
			at += h[2];
		}
		CHECK(framed && at == raw.out.size());
		std::printf("  raw: events %u blocks %u refs %u programs %u pieces %u table %d\n", n[1], n[2], n[3], n[4], n[5], table ? 1 : 0);
		CHECK(n[1] == 4 && n[5] == 2 && n[2] >= 1 && n[3] >= 1 && table);
	}
	// a target that is not readable is not recorded
	Recorder r2;
	r2.submit(pieces, 0, [](uint64_t, uint64_t) { return false; });
	CHECK(r2.surf.empty() && r2.ops.size() == 2);
}

void t_machine() {
	Machine k;
	CHECK(k.flip(0.0) == Act::None);
	k.pad(true, 1.0);
	CHECK(k.flip(1.5) == Act::None); // held 0.5 s
	CHECK(k.flip(2.05) == Act::Record);
	CHECK(k.recording() && k.flip(2.1) == Act::CensusDump && k.recording());
	CHECK(k.flip(2.13) == Act::CensusOnly && !k.recording());
	CHECK(k.flip(4.0) == Act::None);
	CHECK(k.flip(7.2) == Act::Record && k.capture == 1);
	CHECK(k.flip(7.23) == Act::CensusDump && k.flip(7.26) == Act::CensusOnly);
	CHECK(k.state == 0 && k.flip(20.0) == Act::None); // the combo was taken once; still held, no re-arm
	Machine a;
	CHECK(a.arm("auto") && !a.arm("auto") && a.flip(1) == Act::Record);
}
} // namespace

// exp 0439 (tag dk439): a DCC colour target keeps its DCC_CONTROL and DCC_BASE; an image keeps its V# words 6 and 7;
// the key histogram counts 0xff, 0x00 and the rest.
void t_dk439() {
	Mem   m;
	auto* rt  = static_cast<uint8_t*>(m.alloc(64 * 64 * 4));
	auto* tbl = static_cast<uint32_t*>(m.alloc(0x200));
	image_vsharp(tbl + 8, reinterpret_cast<uint64_t>(rt), 64, 64, 20); // the same target read as 32_UINT
	tbl[8 + 6] |= (1u << 21) | (0xe0u << 24);                         // COMPRESSION_EN, metadata address low byte
	tbl[8 + 7] = 0x00508de0u;
	const uint64_t rt_a = reinterpret_cast<uint64_t>(rt), tb = reinterpret_cast<uint64_t>(tbl);
	std::vector<uint32_t> ib;
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x08e), ib.push_back(0xf);
	ib.push_back(pkt(0x69, 5)), ib.push_back(0x318), ib.push_back(static_cast<uint32_t>(rt_a >> 8)), ib.push_back(0), ib.push_back(0), ib.push_back(0),
	    ib.push_back((4u << 2) | (4u << 8) | (1u << 28)); // INFO COLOR_32 UINT, DCC_ENABLE
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x31e), ib.push_back(0x00180028u);                         // DCC_CONTROL
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x325), ib.push_back(0x508de0e0u);                         // DCC_BASE: address >> 8
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x3a8), ib.push_back(0u);                                  // DCC_BASE_EXT: bits 40+
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x390), ib.push_back(static_cast<uint32_t>(rt_a >> 40));
	ib.push_back(pkt(0x69, 1)), ib.push_back(0x3b0), ib.push_back((63u << 14) | 63u);
	ib.push_back(pkt(0x76, 2)), ib.push_back(0x08), ib.push_back(0x12345678), ib.push_back(0x11);
	ib.push_back(pkt(0x2d, 1)), ib.push_back(3), ib.push_back(2);
	ib.push_back(pkt(0x76, 2)), ib.push_back(0x240), ib.push_back(static_cast<uint32_t>(tb)), ib.push_back(static_cast<uint32_t>(tb >> 32));
	ib.push_back(pkt(0x76, 2)), ib.push_back(0x20c), ib.push_back(0x00abcdef), ib.push_back(0x22);
	ib.push_back(pkt(0x15, 3)), ib.push_back(1), ib.push_back(1), ib.push_back(1), ib.push_back(0);
	Recorder r;
	std::vector<std::pair<const uint32_t*, size_t>> pieces = {{ib.data(), ib.size()}};
	r.submit(pieces, -1, [&m](uint64_t a, uint64_t n) { return m.readable(a, n); });
	bool cb = false, img = false;
	for (auto& s: r.surf) {
		if (s.cb && s.base == rt_a && s.dcc && s.dcc_control == 0x00180028u && s.dcc_base == 0x508de0e000ull) cb = true;
		if (s.image && s.base == rt_a && s.word7 == 0x00508de0u && ((s.word6 >> 21) & 1u) != 0 && (s.word6 >> 24) == 0xe0u && s.dcc) img = true;
	}
	if (!(cb && img))
		for (auto& s: r.surf)
			std::printf("  dk439 surf cb %d image %d base 0x%llx dcc %d ctl 0x%08x dcc_base 0x%llx w6 0x%08x w7 0x%08x\n", s.cb, s.image, static_cast<unsigned long long>(s.base), s.dcc, s.dcc_control,
			            static_cast<unsigned long long>(s.dcc_base), s.word6, s.word7);
	CHECK(cb && img);
	KeyHist h;
	const uint8_t k[8] = {0xff, 0xff, 0x00, 0x66, 0x66, 0x66, 0x28, 0xff};
	h.add(k, sizeof(k));
	h.finish();
	uint32_t tv = 0;
	uint64_t tc = 0;
	h.top(tv, tc);
	CHECK(h.n == 8 && h.ff == 3 && h.z == 1 && h.other == 4 && tv == 0x66 && tc == 3);
}

int main() {
	t_dk439();
	t_decode();
	t_count();
	t_arm();
	t_walk();
	t_machine();
	std::printf("test_sr0439b: %s (%d failed)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
	return g_fail == 0 ? 0 : 1;
}
