// BC5 experiment 0412: CPU test of zpoll0412.inc (tag zp412) on stand-ins: a file with a block count, skipped chunks,
// a scan that takes back every skipped chunk that holds data, a sync that pins what came back (the pin allocates, so
// the count grows), and CPU writes injected at chosen moments.
// The invariant: after the poll of a submission, no chunk that was written BEFORE that submission began is still
// skipped. The targeted case of the review of 2026-11-12 (R12): A is written, submission 1 scans and recovers A, B is
// written after the sync and before the old code's second read of the count, then submission 2 must recover B.
// The old rule (seen = the count read after the sync) is modelled too and must FAIL that case; the new one must pass
// it and 20,000 random interleavings.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror zpoll0412.cpp -o zpoll0412
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <random>
#include <set>

#include "zpoll0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

struct World {
	uint64_t      blocks = 100;
	std::set<int> skipped, data; // chunks left unpinned; chunks that hold CPU data
	uint64_t      seen = ~0ull;
	void write(int c) {
		if (data.insert(c).second) blocks += 8;
	}
	uint64_t scan() { // zskip_take_back's stand-in
		uint64_t n = 0;
		for (auto it = skipped.begin(); it != skipped.end();) {
			if (data.count(*it) != 0) {
				it = skipped.erase(it);
				n++;
			} else {
				++it;
			}
		}
		return n;
	}
	// One submission's poll. after_sync: a CPU write injected after the sync (-1: none). old_rule: the count is read
	// again after the sync and stored.
	void poll(int after_sync, bool old_rule) {
		if (zp412::look(seen, blocks)) {
			const uint64_t n = scan();
			if (n != 0) {
				blocks += 512 * n; // the sync pins what came back: the file grows
				if (after_sync >= 0) write(after_sync);
				if (old_rule) seen = blocks;
			} else if (after_sync >= 0) {
				write(after_sync);
			}
		} else if (after_sync >= 0) {
			write(after_sync);
		}
	}
	bool clean_for(const std::set<int>& written_before) const {
		for (const int c: written_before) {
			if (skipped.count(c) != 0) return false;
		}
		return true;
	}
};

static bool targeted(bool old_rule) {
	World w;
	w.skipped = {1, 2, 3};
	w.poll(-1, old_rule); // the first look of a session: nothing written yet
	w.write(1);           // A
	std::set<int> before = w.data;
	w.poll(2, old_rule); // submission 1: recovers A; B (chunk 2) is written after the sync
	if (!w.clean_for(before)) return false;
	before = w.data; // B was written before submission 2 began
	w.poll(-1, old_rule);
	return w.clean_for(before);
}

int main() {
	{
		uint64_t s = 5;
		check(!zp412::look(s, 5) && s == 5, "look: an unchanged count asks for no scan");
		check(zp412::look(s, 9) && s == 9, "look: a changed count asks for a scan and is kept");
	}
	check(targeted(false), "targeted (R12): B written after the sync is recovered before its next submission");
	check(!targeted(true), "targeted (R12): the old rule (the count read after the sync) misses B, as the review's model says");
	uint64_t old_fail = 0;
	for (int round = 0; round < 20000; round++) {
		for (int rule = 0; rule < 2; rule++) {
			std::mt19937_64 r2(static_cast<uint64_t>(round) * 7919u + 4122u); // the same interleaving for both rules
			World           w;
			for (int c = 0; c < 12; c++) w.skipped.insert(c);
			bool ok = true;
			for (int step = 0; step < 30 && ok; step++) {
				if (r2() % 2 == 0) w.write(static_cast<int>(r2() % 12)); // a write before the submission
				const std::set<int> before = w.data;
				const int           inj    = r2() % 3 == 0 ? static_cast<int>(r2() % 12) : -1;
				w.poll(inj, rule == 1);
				ok = w.clean_for(before);
			}
			if (rule == 0) check(ok, "random: nothing written before a submission is still skipped after its poll");
			else if (!ok) old_fail++;
		}
	}
	check(old_fail > 0, "random: the old rule fails in some interleavings (the test can see the defect)");
	std::printf("zpoll0412: old rule failed in %" PRIu64 " of 20000 random rounds\n", old_fail);
	std::printf("zpoll0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
