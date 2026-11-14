// BC5 experiment 0412: CPU test of dw0412.inc (tags tl412, dc412): the walk over a command buffer's dispatches.
//   - generated buffers (4,000) of known packets against what the generator recorded: every dispatch found, in
//     order, with its offset, kind, initiator, groups, program and user data as set before it (by SET_SH_REG or by
//     a loaded table), and nothing else reported;
//   - one-dword NOPs, type-2 fillers and type-0 packets are stepped over; a packet running past the end stops the walk;
//   - a table that cannot be read leaves the registers as they were; a LOAD_SH_REG_INDEX without bit 31 is ignored;
//   - the indirect form with and without SET_BASE; candidates() gives both readings; the counter counts, reports
//     the rarest first and answers seen(); both switches are off when unset.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror dw0412.cpp -o dw0412
#include <algorithm>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <tuple>
#include <vector>

#include "dw0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}
static uint32_t pkt3(uint32_t op, uint32_t body) { return 0xc0000000u | ((body - 1) << 16u) | (op << 8u); }

int main() {
	std::mt19937_64 rng(0x6477343132);
	for (int it = 0; it < 4000; it++) {
		std::vector<uint32_t>                             ib;
		std::map<uint64_t, std::vector<uint32_t>>         mem; // readable tables
		std::vector<dw412::Dispatch>                      want;
		uint32_t pl = 0, ph = 0, ud[16] = {}, udk = 0;
		bool     plk = false, phk = false;
		uint64_t b1 = 0;
		uint64_t table_no = 0;
		auto     set = [&](uint32_t reg, uint32_t v) {
            if (reg == 0x20c) pl = v, plk = true;
            else if (reg == 0x20d) ph = v, phk = true;
            else if (reg >= 0x240 && reg < 0x250) ud[reg - 0x240] = v, udk |= 1u << (reg - 0x240);
		};
		const int packets = 1 + static_cast<int>(rng() % 40);
		for (int p = 0; p < packets; p++) {
			switch (rng() % 12) {
				case 0: ib.push_back(0xffff1000u); break; // a one-dword NOP
				case 1: ib.push_back(0x80000000u); break; // type 2
				case 2: { // type 0
					const uint32_t c = static_cast<uint32_t>(rng() % 4);
					ib.push_back((c << 16u) | 0x1234u);
					for (uint32_t k = 0; k <= c; k++) ib.push_back(static_cast<uint32_t>(rng()));
					break;
				}
				case 3:
				case 4: { // SET_SH_REG over the program or the user data or elsewhere
					const uint32_t regs[] = {0x20c, 0x20d, 0x240, 0x244, 0x24c, 0x24f, 0x100, 0x23e, 0x250};
					const uint32_t reg = regs[rng() % 9], cnt = 1 + static_cast<uint32_t>(rng() % 5);
					ib.push_back(pkt3(0x76, 1 + cnt));
					ib.push_back(reg | (static_cast<uint32_t>(rng() % 2) << 28u)); // high bits of the offset dword are not the register
					for (uint32_t k = 0; k < cnt; k++) {
						const uint32_t v = static_cast<uint32_t>(rng());
						ib.push_back(v);
						set(reg + k, v);
					}
					break;
				}
				case 5: { // LOAD_SH_REG_INDEX: readable, unreadable, or without bit 31
					const uint64_t ta   = 0x1100000000ull + (table_no++) * 0x100; // every table at its own address
					const uint32_t tn   = 1 + static_cast<uint32_t>(rng() % 6);
					const int      mode = static_cast<int>(rng() % 4); // 0, 1 readable; 2 unreadable; 3 no bit 31
					std::vector<uint32_t> t;
					for (uint32_t k = 0; k < tn; k++) {
						const uint32_t regs[] = {0x20c, 0x20d, 0x241, 0x24e, 0x300};
						const uint32_t reg = regs[rng() % 5], v = static_cast<uint32_t>(rng());
						t.push_back(reg | 0x00760000u), t.push_back(v);
						if (mode <= 1) set(reg, v);
					}
					if (mode != 2) mem[ta] = t;
					else mem.erase(ta);
					ib.push_back(pkt3(0x63, 4));
					ib.push_back(static_cast<uint32_t>(ta) | 1u), ib.push_back(static_cast<uint32_t>(ta >> 32u) | 0x00550000u);
					ib.push_back(mode == 3 ? 0u : 0x80000000u), ib.push_back(tn);
					break;
				}
				case 6: { // SET_BASE, index 1 or another
					const uint32_t idx = (rng() % 3) == 0 ? 0u : 1u;
					const uint64_t a   = 0x1180000000ull + (rng() % 4096) * 0x1000;
					ib.push_back(pkt3(0x11, 3)), ib.push_back(idx), ib.push_back(static_cast<uint32_t>(a)), ib.push_back(static_cast<uint32_t>(a >> 32u));
					if (idx == 1) b1 = a;
					break;
				}
				case 7: { // an unrelated packet
					const uint32_t body = 1 + static_cast<uint32_t>(rng() % 8);
					ib.push_back(pkt3(0x46 + static_cast<uint32_t>(rng() % 3), body));
					for (uint32_t k = 0; k < body; k++) ib.push_back(static_cast<uint32_t>(rng()));
					break;
				}
				default: { // a dispatch
					dw412::Dispatch d;
					d.at            = static_cast<uint32_t>(ib.size());
					d.program_known = plk && phk;
					d.program       = (static_cast<uint64_t>(pl) | (static_cast<uint64_t>(ph & 0xff) << 32u)) << 8u;
					std::memcpy(d.ud, ud, sizeof(ud));
					d.ud_known  = udk;
					d.initiator = (rng() % 2) != 0 ? 0x8041u : 0x41u;
					const int form = static_cast<int>(rng() % 3);
					if (form == 0) {
						d.op = 0x15, d.gx = 1 + static_cast<uint32_t>(rng() % 100), d.gy = 1 + static_cast<uint32_t>(rng() % 4), d.gz = 1, d.groups_known = true;
						ib.push_back(pkt3(0x15, 4)), ib.push_back(d.gx), ib.push_back(d.gy), ib.push_back(d.gz), ib.push_back(d.initiator);
					} else if (form == 1) {
						const uint32_t off = static_cast<uint32_t>(rng() % 0x1000) & ~3u;
						d.op = 0x16, d.args = b1 != 0 ? b1 + off : 0;
						ib.push_back(pkt3(0x16, 2)), ib.push_back(off), ib.push_back(d.initiator);
					} else {
						const uint64_t a = 0x1187000000ull + (rng() % 0x100000) * 4;
						d.op = 0x16, d.args = a;
						ib.push_back(pkt3(0x16, 3)), ib.push_back(static_cast<uint32_t>(a)), ib.push_back(static_cast<uint32_t>(a >> 32u)), ib.push_back(d.initiator);
					}
					want.push_back(d);
					break;
				}
			}
		}
		std::vector<dw412::Dispatch> got;
		const bool whole = dw412::walk(
		    ib.data(), static_cast<uint32_t>(ib.size()),
		    [&](uint64_t a, uint32_t pairs, std::vector<uint32_t>& out) {
			    const auto f = mem.find(a);
			    if (f == mem.end() || f->second.size() < 2ull * pairs) return false;
			    out = f->second;
			    return true;
		    },
		    [&](const dw412::Dispatch& d) { got.push_back(d); });
		check(whole, "a well-formed buffer is walked whole");
		bool same = got.size() == want.size();
		for (size_t k = 0; same && k < got.size(); k++) {
			const auto &g = got[k], &w = want[k];
			same = g.at == w.at && g.op == w.op && g.program_known == w.program_known && (!w.program_known || g.program == w.program) && g.initiator == w.initiator &&
			       g.groups_known == w.groups_known && g.gx == w.gx && g.gy == w.gy && g.gz == w.gz && g.args == w.args && g.ud_known == w.ud_known && std::memcmp(g.ud, w.ud, sizeof(g.ud)) == 0;
		}
		check(same, "every dispatch as the generator recorded it, and nothing else");
		if (!ib.empty() && (ib.back() >> 30u) == 3 && dw412::packet_len(ib.back()) == 1) continue; // ends in a one-dword NOP: cutting it leaves a whole buffer
		if (ib.size() >= 2) { // cut the last dword off: whole only when the cut removed a whole one-dword packet
			uint32_t i = 0, last = 0;
			while (i < ib.size()) last = i, i += dw412::packet_len(ib[i]);
			const bool cut_whole = dw412::walk(ib.data(), static_cast<uint32_t>(ib.size() - 1), [](uint64_t, uint32_t, std::vector<uint32_t>&) { return false; }, [](const dw412::Dispatch&) {});
			check(cut_whole == (last == ib.size() - 1), "a packet running past the end stops the walk");
		}
	}
	{
		dw412::Dispatch d;
		d.ud[0] = 0xa5ae8000u, d.ud[1] = 0x03000011u, d.ud[2] = 0x00000800u, d.ud[3] = 0x00005204u, d.ud[4] = 0x11630600u, d.ud[5] = 0xc0100000u;
		d.ud_known = 0x3f;
		std::vector<std::tuple<uint32_t, char, uint64_t>> c;
		dw412::candidates(d, [&](uint32_t k, char f, uint64_t a) { c.emplace_back(k, f, a); });
		auto has = [&](uint32_t k, char f, uint64_t a) { return std::find(c.begin(), c.end(), std::make_tuple(k, f, a)) != c.end(); };
		check(has(0, 'b', 0x11a5ae8000ull), "the buffer reading of user data 0-1");
		check(has(4, 't', 0x1163060000ull), "the texture reading of user data 4");
		check(!has(4, 'b', 0x0011630600ull) && !has(1, 'b', 0x0003000011ull), "no buffer reading when the next dword's low byte is zero");
		d.ud_known = 0x1; // only dword 0 known: no buffer reading (the high part is unknown)
		c.clear();
		dw412::candidates(d, [&](uint32_t k, char f, uint64_t a) { c.emplace_back(k, f, a); });
		check(c.size() == 1 && has(0, 't', 0xa5ae800000ull), "an unknown dword gives no reading");
	}
	{
		dw412::Counter  c;
		dw412::Dispatch a, b, u;
		a.op = 0x15, a.program = 0x11d0423100ull, a.program_known = true, a.initiator = 0x8041, a.gx = 39, a.gy = 1, a.gz = 1, a.groups_known = true;
		b = a, b.program = 0x11d042ba00ull, b.initiator = 0x41, b.gx = 8;
		u.op = 0x16, u.initiator = 0x8061;
		check(c.seen(a) == 0, "seen() is 0 before the first");
		c.add(a, 1.0);
		for (int k = 0; k < 5; k++) c.add(b, 2.0 + k);
		c.add(a, 9.0), c.add(u, 9.5);
		check(c.dispatches == 8 && c.unknown_program == 1 && c.seen(a) == 2 && c.seen(b) == 5 && c.seen(u) == 1, "the counts");
		std::vector<uint64_t> order;
		double                first_a = -1, last_a = -1;
		uint64_t              groups_a = 0;
		c.report(2, [&](const dw412::Key& k, const dw412::Val& v) {
			order.push_back(v.n);
			if (k.program == a.program) first_a = v.first_t, last_a = v.last_t, groups_a = v.groups;
		});
		check(order == std::vector<uint64_t>({1, 2}), "the rarest first, cut at the asked number");
		check(first_a == 1.0 && last_a == 9.0 && groups_a == 78, "first and last time, groups summed");
		dw412::Dispatch a2 = a;
		a2.initiator = 0x41;
		check(c.seen(a2) == 0, "another initiator is another key");
	}
	check(dw412::packet_len(0xffff1000u) == 1 && dw412::packet_len(0x80000000u) == 1 && dw412::packet_len(0xc0031500u) == 5 && dw412::packet_len(0x00030000u) == 5, "packet lengths");
	check(!dw412::tl_on() && !dw412::dc_on(), "both off when the variables are unset");
	std::printf("dw0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
