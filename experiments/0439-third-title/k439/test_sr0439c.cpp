// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag sr439c): det test of bc5/sr0439c.hpp. PASS, or the failing checks. Plants (each must FAIL):
// -DBC5_SR439C_PLANT_NOCHAIN, -DBC5_SR439C_PLANT_NOWINDOW, -DBC5_SR439C_PLANT_NOSPLIT.
#include "sr0439c.hpp"

#include <cstdio>
#include <cstring>

using namespace bc5::sr439c;
static int fails = 0;
#define CHECK(c)                                                                                                       \
	do {                                                                                                               \
		if (!(c)) {                                                                                                    \
			std::printf("FAIL line %d: %s\n", __LINE__, #c);                                                           \
			fails++;                                                                                                   \
		}                                                                                                              \
	} while (0)

int main() {
	// geometry: 32 bpp 64 KiB block 128x128, 64 bpp 128x64, 16 bpp 256x128, 8 bpp 256x256
	{
		Geo g = geo(3072, 1728, 1, 4, 27, 0);
		CHECK(g.tiled && g.bw == 128 && g.bh == 128 && g.tx == 24 && g.ty == 14 && g.bytes == 24ull * 14 * kTile);
		g = geo(3072, 1728, 1, 8, 9, 0);
		CHECK(g.tiled && g.bw == 128 && g.bh == 64 && g.ty == 27);
		g = geo(100, 100, 1, 2, 24, 0);
		CHECK(g.bw == 256 && g.bh == 128 && g.tx == 1 && g.ty == 1);
		CHECK(geo(256, 256, 1, 1, 8, 0).bw == 256);
		CHECK(!geo(3072, 1728, 1, 4, 0, 1000).tiled && geo(3072, 1728, 1, 4, 0, 1000).bytes == 1000); // linear
		CHECK(!geo(64, 64, 1, 4, 5, 4096).tiled);                                                      // a 4 KiB mode
		CHECK(!geo(64, 64, 1, 12, 27, 100).tiled);                                                     // 12 bytes: not a power of two
	}
	// ranges: the window's tiles plus every stride-th; merged; the default window on a 24x14-tile target
	{
		const Geo    g = geo(3072, 1728, 1, 4, 27, 0);
		const Window w;
		const auto   r  = ranges(g, 3072, 1728, w, 16);
		uint64_t     in = 0, out = 0;
		for (const auto& x: r) (x.window ? in : out) += x.len / kTile;
		// window x 307..1843 -> tiles 2..14 (13), y 432..1728 -> tiles 3..13 (11): 143 tiles
		CHECK(in == 143);
		uint64_t want_out = 0;
		for (uint64_t t = 0; t < 24 * 14; t++) {
			const uint64_t x = t % 24, y = t / 24;
			const bool     inw = x >= 2 && x < 15 && y >= 3 && y < 14;
			if (!inw && t % 16 == 0) want_out++;
		}
		CHECK(out == want_out);
		for (size_t i = 1; i < r.size(); i++) CHECK(r[i].off >= r[i - 1].off + r[i - 1].len);
		CHECK(total(r) == (in + out) * kTile);
		// a buffer of 1 MiB + 5 bytes, stride 4: chunks 0, 4, 8, 12, 16 (the last 5 bytes)
		const auto b = ranges(geo(0, 0, 1, 0, 0, (1u << 20) + 5), 0, 0, w, 4);
		CHECK(b.size() == 5 && b[4].off == 16 * kTile && b[4].len == 5);
		const auto one = ranges(geo(0, 0, 1, 0, 0, 100), 0, 0, w, 16);
		CHECK(one.size() == 1 && one[0].len == 100);
	}
	// window parsing
	{
		const Window a = parse_window("0.1,0.2,0.3,0.4");
		CHECK(a.x0 == 0.1 && a.y1 == 0.4);
		const Window b = parse_window("0.5,0.2,0,1");
		CHECK(b.x0 == 0.10); // malformed: the default
		CHECK(parse_window(nullptr).x1 == 0.60);
	}
	// packets: the same headers as the backend's own (RELEASE_MEM 0xC0064900, DMA_DATA 0xC0055000) and WAIT_REG_MEM
	{
		std::vector<uint32_t> o;
		flush_gfx(o, 0x110000000040ull, 7);
		CHECK(o.size() == kFlushGfxDwords);
		CHECK(o[0] == 0xC0064900u && o[1] == (20u | (5u << 8)) && o[2] == (1u << 29) && o[3] == 0x40 && o[4] == 0x1100 && o[5] == 7);
		CHECK(o[8] == 0xC0053C00u && o[9] == 0x13u && o[10] == 0x40 && o[11] == 0x1100 && o[12] == 7 && o[13] == 0xffffffffu);
		o.clear();
		flush_mec(o);
		CHECK(o.size() == kFlushMecDwords && o[0] == 0xC0004600u && o[1] == (7u | (4u << 8)));
		o.clear();
		dma(o, 0x5053890000ull, 0x110000100000ull, (2u << 20) + 64);
		CHECK(o.size() == 21 && o.size() == dma_dwords((2u << 20) + 64));
		CHECK(o[0] == 0xC0055000u && o[1] == 0xE0000000u && o[2] == 0x53890000u && o[3] == 0x50 && o[6] == (1u << 20));
		CHECK(o[7 + 2] == 0x53990000u && o[7 + 4] == 0x00200000u && o[14 + 6] == 64);
	}
	// the last packet and the chain bit; COND_EXEC reach
	{
		const uint32_t chain_size = 100u | (1u << 20);
		uint32_t       b[]        = {0xC0004600u, 7u, 0xC0023F00u, 0x1000u, 0x50u, chain_size};
		bool           ch         = false;
		CHECK(last_packet(b, 6, ch) == 2 && ch);
		b[5] = 100u;
		CHECK(last_packet(b, 6, ch) == 2 && !ch);
		uint32_t c[] = {0xC0032200u, 0, 0, 0, 2u, 0xC0004600u, 7u, 0xC0004600u, 7u};
		CHECK(cond_exec_reaches(c, 9, 5) && cond_exec_reaches(c, 9, 7) && !cond_exec_reaches(c, 9, 8));
	}
	// the depth tracker: SET_CONTEXT_REG of DB_DEPTH_SIZE_XY, DB_Z_INFO and the write bases, a draw, CLEAR_STATE
	{
		const uint32_t b[] = {
		    0xC0016900u, 0x007u, (1727u << 16) | 3071u,            // DB_DEPTH_SIZE_XY 3072 x 1728
		    0xC0016900u, 0x010u, 3u | (27u << 4),                  // DB_Z_INFO Z_32_FLOAT, SW_MODE 27
		    0xC0016900u, 0x014u, 0x50123400u,                      // DB_Z_WRITE_BASE (>> 8)
		    0xC0016900u, 0x01cu, 0x12u,                            // DB_Z_WRITE_BASE_HI
		    0xC0012D00u, 3u, 2u,                                   // DRAW_INDEX_AUTO
		    0xC0001200u, 0u,                                       // CLEAR_STATE
		    0xC0012D00u, 3u, 2u,                                   // a draw with no depth target known
		};
		DbTrack t;
		std::vector<Depth> seen;
		t.walk(b, sizeof(b) / 4, [](uint64_t, uint64_t) { return false; }, [&](const Depth& d) { seen.push_back(d); });
		CHECK(seen.size() == 1 && seen[0].base == ((0x50123400ull << 8) | (0x12ull << 40)) && seen[0].w == 3072 && seen[0].h == 1728 && seen[0].bpe == 4 && seen[0].sw == 27);
	}
	// the resolve arm: the register tracker (root stack, piece clear) and the resolve block
	{
		const uint32_t b[] = {
		    0xC0016900u, 0x318u, 0x11u,       // CB_COLOR0_BASE
		    0xC0017600u, 0x008u, 0x22u,       // SPI_SHADER_PGM_LO_PS
		    0xC0017900u, 0x25bu, 0x80u,       // GE_CNTL
		    0xC0002F00u, 3u,                  // NUM_INSTANCES 3
		    0xC0001200u, 1u,                  // CLEAR_STATE push
		    0xC0016900u, 0x318u, 0x99u,       // the internal draw's own value
		    0xC0012D00u, 3u, 2u,              // its draw
		    0xC0001200u, 2u,                  // CLEAR_STATE pop
		    0xC0012D00u, 3u, 2u,              // the title's draw
		};
		CtxTrack t;
		std::vector<uint32_t> seen;
		t.walk(b, sizeof(b) / 4, true, [](uint64_t, uint64_t) { return false; }, [&](const CtxTrack& x) { seen.push_back(x.s.ctx_ok[0x318] ? x.s.ctx[0x318] : 0); });
		CHECK(seen.size() == 2 && seen[0] == 0x99 && seen[1] == 0x11); // the pop put the title's value back
		// cblog: the source of a value (S a direct set, in which piece) and a clear forgetting it
		{
			CtxTrack s3;
			s3.piece = 7;
			const uint32_t one[] = {0xC0016900u, 0x318u, 0x11u};
			s3.walk(one, 3, false, [](uint64_t, uint64_t) { return false; }, [](const CtxTrack&) {});
			CHECK(s3.s.ctx_ok[0x318] && s3.s.ctx_kind[0x318] == 1 && s3.s.ctx_piece[0x318] == 7);
			const uint32_t clr[] = {0xC0001200u, 0u};
			s3.walk(clr, 2, false, [](uint64_t, uint64_t) { return false; }, [](const CtxTrack&) {});
			CHECK(!s3.s.ctx_ok[0x318] && s3.s.ctx_kind[0x318] == 0);
		}
		CtxTrack u;
		seen.clear();
		u.walk(b, sizeof(b) / 4, false, [](uint64_t, uint64_t) { return false; }, [&](const CtxTrack& x) { seen.push_back(x.s.ctx_ok[0x318] ? x.s.ctx[0x318] : 0); });
		CHECK(seen.size() == 2 && seen[1] == 0); // in a piece the pop is a clear
		// the block: push -> clear, pop dropped, the state written back
		std::vector<uint32_t> dc = {pkt3(0x12, 1), 1u, pkt3(0x2d, 2), 3u, 2u, pkt3(0x12, 1), 2u}, out;
		CHECK(resolve_block(dc, t.s, out));
		CHECK(out[0] == pkt3(0x12, 1) && out[1] == 0 && out[2] == pkt3(0x2d, 2));
		bool ctx_back = false, sh_back = false, ge_back = false, inst_back = false;
		for (size_t i = 0; i + 2 < out.size(); i++) {
			ctx_back = ctx_back || (out[i] == pkt3(0x69, 2) && out[i + 1] == 0x318 && out[i + 2] == 0x11);
			sh_back  = sh_back || (out[i] == pkt3(0x76, 2) && out[i + 1] == 0x008 && out[i + 2] == 0x22);
			ge_back  = ge_back || (out[i] == pkt3(0x79, 2) && out[i + 1] == 0x25b && out[i + 2] == 0x80);
		}
		inst_back = out[out.size() - 2] == pkt3(0x2f, 1) && out.back() == 3;
		CHECK(ctx_back && sh_back && ge_back && inst_back);
		for (size_t i = 0; i + 1 < out.size(); i++) CHECK(!(out[i] == pkt3(0x12, 1) && out[i + 1] == 2)); // no pop left
		std::vector<uint32_t> bad = {pkt3(0x2d, 2), 3u, 2u}, o2;
		CHECK(!resolve_block(bad, t.s, o2) && o2.empty());
	}
	// the sampled hash
	{
		std::vector<uint8_t> m(1 << 20, 0);
		auto           rd = [&m](uint64_t off, uint8_t* d, size_t n) { std::memcpy(d, m.data() + off, n); return true; };
		const uint64_t h0 = sampled_hash(m.size(), rd);
		m[m.size() / 2]   = 1; // not on a sample: same hash
		const uint64_t h1 = sampled_hash(m.size(), rd);
		m[0]              = 1;
		const uint64_t h2 = sampled_hash(m.size(), rd);
		CHECK(h0 != 0 && h0 == h1 && h2 != h0);
		CHECK(sampled_hash(10, rd) == 0);
	}
	// the plan and its levels
	{
		std::vector<PlanItem> it;
		for (int i = 0; i < 10; i++) it.push_back({100, true, false, true, 0});              // targets 1000
		for (int i = 0; i < 10; i++) it.push_back({100, false, false, false, 0});            // unchanged inputs 1000
		for (int i = 0; i < 4; i++) it.push_back({50, true, true, true, uint32_t(i)});       // depth 200
		Plan p = plan(it, 5000);
		CHECK(p.level == 0 && p.need[0] == 2200 && !p.truncated);
		p = plan(it, 1200);
		CHECK(p.level == 1 && p.need[1] == 1200);
		p = plan(it, 1100);
		CHECK(p.level == 2 && p.need[2] == 1100);
		p = plan(it, 600);
		CHECK(p.level == 3 && p.need[3] <= 600 && p.split_at >= 550 && p.split_at <= 600 && !p.truncated);
		p = plan(it, 300);
		CHECK(p.level == 3 && p.truncated && p.arena == 300);
		CHECK(budget(1ull << 30, 1200ull << 20, 0, 0) == (432ull << 20));
		CHECK(budget(1ull << 30, 0, 13ull << 30, (12ull << 30) + (512ull << 20)) == (256ull << 20));
	}
	// arming
	{
		Machine m;
		m.times = parse_times("60,100");
		CHECK(m.times.size() == 2 && m.times[1] == 100);
		CHECK(m.flip(10) == Act::None); // t0 = 10
		CHECK(m.flip(69) == Act::None);
		CHECK(m.flip(70.1) == Act::Survey);
		CHECK(m.flip(70.2) == Act::SurveyEnd);
		m.split = true;
		CHECK(m.flip(70.3) == Act::CopyEnd && m.frame_b());
		CHECK(m.flip(70.4) == Act::CopyEnd && !m.frame_b());
		m.split = false;
		CHECK(m.flip(80) == Act::None);
		m.pad(true, 80.5);
		CHECK(m.flip(81) == Act::None);
		CHECK(m.flip(81.6) == Act::Survey); // held 1.1 s
		m.pad(false, 81.7);
		CHECK(m.flip(81.8) == Act::SurveyEnd);
		CHECK(m.flip(110.0) == Act::CopyEnd); // the 100 s time fired meanwhile: pending
		CHECK(m.flip(110.1) == Act::Survey);
		CHECK(parse_times("x,5,-1").size() == 1);
	}
	std::printf(fails == 0 ? "test_sr0439c: PASS\n" : "test_sr0439c: %d FAILED\n", fails);
	return fails == 0 ? 0 : 1;
}
