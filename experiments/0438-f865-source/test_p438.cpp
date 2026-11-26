// BC5 experiment 0438 (tag p438): the prologue merge against today's submission, on random gc call sequences.
// test_p438.sh cuts, unchanged, from the generated unit: the p438 namespace, p438_submit, p438_flush_alone, p438_defer
// and p438_take_into_chain. This file supplies stubs for submit_raw / submit_ib_packet (they record the buffers),
// Direct::chain_begin / chain_end (a submission = one chain with at least one buffer), soft_posts_end and the rest, and
// models gc_ioctl's cases with the hooks exactly where mkb438.py puts them:
//   0xc0488131: if (p438_defer(cc, cmds)) return; else today's chain of cc + 3 hib
//   0xc0188132: chain_begin; p438_take_into_chain(); the DCBs; chain_end
//   0xc0108102, 0xc020810c: p438_flush_alone(kAloneOther) first;  0xc0048116/7: p438_flush_alone(kAloneIdle);
//   the EOP flip: p438_flush_alone(kAloneFlip)
// Checks, per scenario: the buffers handed over (kind and dwords, in order) are identical with the merge on and off;
// the submissions with the merge on = off - (prologues merged); a prologue whose header IB writes memory is never kept;
// with the acb rings off nothing is kept.
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <random>
#include <string>
#include <vector>

namespace SoftCp {
inline uint64_t now_ns() { return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
} // namespace SoftCp
struct Buf {
	std::string           kind;
	std::vector<uint32_t> dw;
	bool operator==(const Buf& o) const { return kind == o.kind && dw == o.dw; }
};
static std::vector<Buf> g_out;
static int              g_in_chain = 0, g_chain_bufs = 0, g_submissions = 0, g_rings = 4;
namespace Direct {
inline void   chain_begin() { g_in_chain = 1; g_chain_bufs = 0; }
inline void   chain_end() {
    if (g_chain_bufs > 0) g_submissions++;
    g_in_chain = 0;
}
inline int    w428_rings() { return g_rings; }
inline double timing_now() { return 0.0; }
inline void   journal(const char*, ...) {}
} // namespace Direct
static void soft_posts_end() {}
static void submit_raw(const uint32_t* dwords, uint32_t num, const char* kind) {
	if (dwords == nullptr || num == 0 || dwords[0] == 0) return;
	if (!g_in_chain) std::abort(); // every gc path submits inside a chain
	g_out.push_back({kind, std::vector<uint32_t>(dwords, dwords + num)});
	g_chain_bufs++;
}
static void submit_ib_packet(const uint32_t* pkt, const char* kind) {
	if (pkt[0] == 0) return;
	const auto*    ib = reinterpret_cast<const uint32_t*>((static_cast<uint64_t>(pkt[2]) << 32u) | pkt[1]);
	const uint32_t n  = pkt[3] & 0xfffffu;
	submit_raw(ib, n, kind);
}
#include "p438_cut.inc"

static int fails = 0;
#define CHECK(c, ...)                                     \
	do {                                                  \
		if (!(c)) {                                       \
			std::printf("FAIL line %d: ", __LINE__);      \
			std::printf(__VA_ARGS__);                     \
			std::printf("\n");                            \
			fails++;                                      \
		}                                                 \
	} while (0)

// header IBs: a state preamble (SET_CONTEXT_REG-like type-3 packets), a 2-dword IB, and one that writes memory
static uint32_t g_pre[64][8], g_two[64][2], g_wr[8];
static uint32_t g_dcb[64][6];
static void     ib_pkt(uint32_t* p, const uint32_t* ib, uint32_t n) {
    const auto a = reinterpret_cast<uint64_t>(ib);
    p[0]         = 0xC0023F00u;
    p[1]         = static_cast<uint32_t>(a);
    p[2]         = static_cast<uint32_t>(a >> 32u);
    p[3]         = n;
}

struct Model {
	bool merge;
	void prologue(int k, bool writes_mem) {
		uint32_t cc[3]    = {0xC0012800u, 0x80000000u + static_cast<uint32_t>(k), 0x80000000u};
		uint32_t cmds[12] = {};
		ib_pkt(cmds + 0, g_pre[k % 64], 8);
		ib_pkt(cmds + 4, writes_mem ? g_wr : g_two[k % 64], writes_mem ? 8 : 2);
		ib_pkt(cmds + 8, g_two[(k + 1) % 64], 2);
		if (merge && p438_defer(cc, cmds)) {
			CHECK(!writes_mem, "a prologue whose header IB writes memory was kept (prologue %d)", k); // a CPU waiter may need it
			return;
		}
		Direct::chain_begin();
		submit_raw(cc, 3, "cc");
		for (int i = 0; i < 3; i++) submit_ib_packet(cmds + i * 4, "hib");
		Direct::chain_end();
		soft_posts_end();
	}
	void list(int k, int n) {
		Direct::chain_begin();
		if (merge) p438_take_into_chain();
		for (int i = 0; i < n; i++) submit_raw(g_dcb[(k + i) % 64], 6, "dcb");
		Direct::chain_end();
		soft_posts_end();
	}
	void other(int k) {
		if (merge) p438_flush_alone(p438::kAloneOther);
		Direct::chain_begin();
		uint32_t pkt[4];
		ib_pkt(pkt, g_dcb[k % 64], 6);
		submit_ib_packet(pkt, "dcb");
		Direct::chain_end();
		soft_posts_end();
	}
	void idle() {
		if (merge) p438_flush_alone(p438::kAloneIdle);
	}
	void flip() {
		if (merge) p438_flush_alone(p438::kAloneFlip);
	}
};

int main() {
	for (int i = 0; i < 64; i++) {
		for (int j = 0; j < 8; j++) g_pre[i][j] = 0xC0016900u + static_cast<uint32_t>(i * 8 + j); // SET_CONTEXT_REG-like
		g_two[i][0] = 0xC0001000u;                                                                      // a NOP
		g_two[i][1] = static_cast<uint32_t>(i);
		for (int j = 0; j < 6; j++) g_dcb[i][j] = 0xC0041000u + static_cast<uint32_t>(i * 6 + j);
	}
	g_wr[0] = 0xC0064900u; // RELEASE_MEM: the header writes memory
	for (int j = 1; j < 8; j++) g_wr[j] = 0;
	std::mt19937_64 rng(438);
	uint64_t        total_merged = 0, total_writes = 0, scenarios = 0, steps_n = 0;
	for (int scen = 0; scen < 400; scen++) {
		scenarios++;
		g_rings = scen % 10 == 9 ? 0 : 4; // every tenth: the acb rings off
		struct Step {
			int  op, k, n;
			bool w;
		};
		std::vector<Step> steps;
		const int         len = 20 + static_cast<int>(rng() % 200);
		for (int i = 0; i < len; i++) {
			const int r = static_cast<int>(rng() % 100);
			// mostly the frame's shape (prologue, list, flip), sometimes two prologues, other submits, idle, a writing header
			const int op = r < 35 ? 0 : r < 70 ? 1 : r < 80 ? 4 : r < 88 ? 2 : r < 94 ? 3 : 0;
			steps.push_back({op, static_cast<int>(rng() % 1000), 1 + static_cast<int>(rng() % 5), rng() % 25 == 0});
		}
		steps_n += steps.size();
		std::vector<Buf> out[2];
		int              subs[2] = {};
		uint64_t         merged = 0, alone_writes = 0;
		for (int m = 0; m < 2; m++) {
			g_out.clear();
			g_submissions = 0;
			{
				std::lock_guard lk(p438::g_m);
				p438::g_pending.clear();
			}
			for (auto& x: p438::g_n) x = 0;
			Model mod {m == 1};
			for (const auto& st: steps) {
				switch (st.op) {
					case 0: mod.prologue(st.k, st.w); break;
					case 1: mod.list(st.k, st.n); break;
					case 2: mod.other(st.k); break;
					case 3: mod.idle(); break;
					default: mod.flip(); break;
				}
			}
			mod.flip(); // the run ends at a flip: nothing stays pending
			out[m]  = g_out;
			subs[m] = g_submissions;
			if (m == 1) {
				merged       = p438::g_n[p438::kMerged].load();
				alone_writes = p438::g_n[p438::kAloneWrites].load();
				std::lock_guard lk(p438::g_m);
				CHECK(p438::g_pending.empty(), "scenario %d: prologues left pending", scen);
			}
		}
		CHECK(out[0] == out[1], "scenario %d: the buffers handed over differ (%zu off, %zu on)", scen, out[0].size(), out[1].size());
		CHECK(subs[1] == subs[0] - static_cast<int>(merged), "scenario %d: submissions off %d, on %d, merged %" PRIu64, scen, subs[0], subs[1], merged);
		if (g_rings == 0) CHECK(merged == 0, "scenario %d: merged with the acb rings off", scen);
		total_merged += merged;
		total_writes += alone_writes;
	}
	std::printf("p438 test: %" PRIu64 " scenarios, %" PRIu64 " steps; prologues merged %" PRIu64 ", kept out as writing memory %" PRIu64 "; %s (%d failures)\n", scenarios, steps_n, total_merged, total_writes,
	            fails == 0 ? "PASS" : "FAIL", fails);
	return fails == 0 ? 0 : 1;
}
