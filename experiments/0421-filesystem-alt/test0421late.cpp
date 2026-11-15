// BC5 experiment 0421: CPU test of late_import.hpp (tag fs421). Laptop: VS clang++ -std=c++20 -O1 -Wall -Wextra -Werror.
#include "late_import.hpp"

#include <cstdio>
#include <vector>

using bc5::late_import::Limits;
using bc5::late_import::State;
using bc5::late_import::due;
using bc5::late_import::delay_of;
using bc5::late_import::pick;

static int g_fail = 0, g_n = 0;
#define CHECK(x)                                                         \
	do {                                                                 \
		g_n++;                                                           \
		if (!(x)) {                                                      \
			g_fail++;                                                    \
			std::printf("FAIL line %d: %s\n", __LINE__, #x);             \
		}                                                                \
	} while (0)

static constexpr uint64_t S  = 1'000'000'000ull;
static constexpr uint64_t MS = 1'000'000ull;
static constexpr uint64_t C  = 2ull << 20u; // a chunk

int main() {
	const Limits L {30 * S, 250 * MS, 1};
	{ // nothing written: nothing waits
		State s;
		CHECK(pick(s, {}, 10 * S, L).empty());
		CHECK(s.next_due_ns == 0 && !due(s, 100 * S));
	}
	{ // one chunk: waits 30 s, then goes once
		State s;
		CHECK(pick(s, {5 * C}, 40 * S, L).empty());
		CHECK(s.next_due_ns == 70 * S);
		CHECK(!due(s, 69 * S) && due(s, 70 * S));
		CHECK(pick(s, {5 * C}, 69 * S, L).empty());
		const auto got = pick(s, {5 * C}, 70 * S, L);
		CHECK(got.size() == 1 && got[0] == 5 * C);
		CHECK(s.next_due_ns == 0 && s.imported == 1);
		CHECK(pick(s, {}, 71 * S, L).empty()); // imported: no longer in `written`
		CHECK(s.seen.empty());
	}
	{ // three chunks seen together: one per pass, passes 250 ms apart; repeats and order do not matter
		State s;
		CHECK(pick(s, {9 * C, 3 * C, 3 * C, 6 * C}, 0 + 1, L).empty());
		std::vector<uint64_t> w = {3 * C, 6 * C, 9 * C};
		auto g1 = pick(s, w, 30 * S + 1, L);
		CHECK(g1.size() == 1 && g1[0] == 3 * C);
		CHECK(s.next_due_ns == 30 * S + 1 + 250 * MS);
		w = {6 * C, 9 * C};
		CHECK(pick(s, w, 30 * S + 100 * MS, L).empty()); // inside the gap
		auto g2 = pick(s, w, 30 * S + 1 + 250 * MS, L);
		CHECK(g2.size() == 1 && g2[0] == 6 * C);
		w = {9 * C};
		auto g3 = pick(s, w, 31 * S, L);
		CHECK(g3.size() == 1 && g3[0] == 9 * C);
		CHECK(s.imported == 3 && s.next_due_ns == 0);
	}
	{ // a chunk that leaves `written` (imported by K1 at the filter) and comes back starts again
		State s;
		CHECK(pick(s, {2 * C}, 10 * S, L).empty());
		CHECK(pick(s, {}, 20 * S, L).empty());
		CHECK(pick(s, {2 * C}, 41 * S, L).empty());
		CHECK(s.next_due_ns == 71 * S);
	}
	{ // a chunk seen later waits its own time; an earlier due one goes first
		State s;
		CHECK(pick(s, {8 * C}, 10 * S, L).empty());
		CHECK(pick(s, {1 * C, 8 * C}, 20 * S, L).empty());
		CHECK(s.next_due_ns == 40 * S);
		auto g = pick(s, {1 * C, 8 * C}, 40 * S, L);
		CHECK(g.size() == 1 && g[0] == 8 * C);
		CHECK(s.next_due_ns == 50 * S);
	}
	{ // per_pass 2
		State s;
		const Limits L2 {1 * S, 0, 2};
		CHECK(pick(s, {1 * C, 2 * C, 3 * C}, 1, L2).empty());
		auto g = pick(s, {1 * C, 2 * C, 3 * C}, 1 * S + 1, L2);
		CHECK(g.size() == 2 && g[0] == 1 * C && g[1] == 2 * C);
		CHECK(s.next_due_ns == 1 * S + 1);
	}
	{ // the switch's value
		CHECK(delay_of(nullptr) == 0 && delay_of("") == 0 && delay_of("0") == 0);
		CHECK(delay_of("1") == 30 * S && delay_of("on") == 30 * S);
		CHECK(delay_of("5") == 5 * S && delay_of("60") == 60 * S && delay_of("3600") == 3600 * S);
		CHECK(delay_of("4") == 30 * S && delay_of("3601") == 30 * S && delay_of("20s") == 30 * S && delay_of("00") == 30 * S);
		CHECK(delay_of("99999999999999999999") == 30 * S);
	}
	std::printf("test0421late: %d of %d checks passed\n", g_n - g_fail, g_n);
	return g_fail == 0 ? 0 : 1;
}
