// BC5 experiment 0412: CPU test of rlabels0412.inc (tag rl412): what is kept for a reopen when one or two jobs time
// out, with the forget of all pending writes between the calls, as the unit does it.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror rlabels0412.cpp -o rlabels0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>

#include "rlabels0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

int main() {
	using V = std::vector<uint64_t>;
	// his case: two jobs time out in one hang; the pending list holds both jobs' writes at the first call
	for (const bool add: {false, true}) {
		V        pending = {1, 2, 3, 4, 5}, kept;
		uint64_t kept_for = 0;
		rl412::keep(kept, kept_for, pending, 1, add); // first timed-out job
		pending.clear();                              // forget_label_writes(all)
		rl412::keep(kept, kept_for, pending, 1, add); // second timed-out job, same reopen
		check(kept_for == 1, "two timeouts: kept for the reopen that follows");
		if (add) check(kept.size() == 5, "two timeouts, switch on: the first call's writes survive the second call");
		else check(kept.empty(), "two timeouts, switch off: today's behaviour, the second call empties what was kept");
	}
	// one job: the same either way
	for (const bool add: {false, true}) {
		V        pending = {7, 8}, kept = {99};
		uint64_t kept_for = 3; // something stale from an earlier reopen
		rl412::keep(kept, kept_for, pending, 5, add);
		check(kept == pending && kept_for == 5, "one timeout: the pending list replaces a stale one");
	}
	// random sequences against a model: with the switch on, what is kept for a reopen is every write pending at any
	// of that reopen's timeouts, in order; a new reopen starts afresh
	std::mt19937_64 rng(0x4120412);
	for (int it = 0; it < 2000; it++) {
		V        kept, model;
		uint64_t kept_for = 0, reopen = 1 + rng() % 3;
		const int calls = 1 + static_cast<int>(rng() % 4);
		for (int c = 0; c < calls; c++) {
			V pending;
			const int n = static_cast<int>(rng() % 6);
			for (int i = 0; i < n; i++) pending.push_back(rng() & 0xffff);
			if (rng() % 5 == 0) { // the reopen happened in between: the next timeout belongs to the next one
				reopen++;
				model.clear();
			}
			rl412::keep(kept, kept_for, pending, reopen, true);
			model.insert(model.end(), pending.begin(), pending.end());
			check(kept == model && kept_for == reopen, "model: everything pending at the timeouts of one reopen is kept, in order");
		}
	}
	check(!rl412::on(), "the switch is off when unset");
	std::printf("rlabels0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
