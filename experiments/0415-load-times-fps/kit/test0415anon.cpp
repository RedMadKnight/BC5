// BC5 exp 0415 (tag as415): CPU test of src/bc5/anon_sync.hpp, the pieces of stage S5 that the submission path and the
// checking thread share. No GPU, no emulator.
//   c++ -std=c++20 -O1 -I<tree>/src test0415anon.cpp -o test0415anon && ./test0415anon
#include "bc5/anon_sync.hpp"

#include <cstdio>
#include <vector>

static int g_n = 0, g_bad = 0;
#define CHECK(x)                                                    \
	do {                                                            \
		g_n++;                                                      \
		if (!(x)) {                                                 \
			g_bad++;                                                \
			std::printf("FAILED line %d: %s\n", __LINE__, #x);      \
		}                                                           \
	} while (0)

using namespace bc5::anon_sync;

int main() {
	uint64_t a = 0, b = 0;
	bool     ro = false;
	// the rule for one line of /proc/self/maps
	CHECK(parse_line("900000000-900010000 rw-p 00000000 00:00 0 ", &a, &b, &ro) && a == 0x900000000ull && b == 0x900010000ull && !ro);
	CHECK(parse_line("900000000-900010000 r-xp 00000000 00:00 0 ", &a, &b, &ro) && ro);
	CHECK(parse_line("900000000-900010000 r--p 00000000 00:00 0", &a, &b, &ro) && ro);
	CHECK(!parse_line("900000000-900010000 ---p 00000000 00:00 0 ", &a, &b, &ro));                               // not readable
	CHECK(!parse_line("900000000-900010000 rw-s 00000000 00:01 1234 /memfd:bc5-private (deleted)", &a, &b, &ro)); // a file
	CHECK(!parse_line("900000000-900010000 rw-p 00000000 00:00 0 [heap]", &a, &b, &ro));
	CHECK(!parse_line("900000000-900010000 rw-p 00000000 00:00 0 [anon:x]", &a, &b, &ro));
	CHECK(!parse_line("7f0000000000-7f0000010000 rw-p 00000000 00:00 0 ", &a, &b, &ro)); // the host's own mappings, above the span
	CHECK(!parse_line("10000-20000 rw-p 00000000 00:00 0 ", &a, &b, &ro));              // below the guest's span
	CHECK(!parse_line("fc0000000000-fc0000010000 rw-p 00000000 00:00 0 ", &a, &b, &ro)); // above it
	CHECK(parse_line("fbfffff000-fc00000000 rw-p 00000000 00:00 0 ", &a, &b, &ro));    // its last page
	CHECK(!parse_line("garbage", &a, &b, &ro));
	CHECK(!parse_line("", &a, &b, &ro));
	// the modes
	CHECK(mode_of(nullptr) == 0 && mode_of("") == 0 && mode_of("0") == 0);
	CHECK(mode_of("verify") == 1 && mode_of("1") == 1 && mode_of("thread") == 2);
	// the signature: the same input gives the same value; each field counts
	const uint64_t e = kSigEmpty;
	CHECK(sig_vma(e, 0x1000, 0x2000, false) == sig_vma(e, 0x1000, 0x2000, false));
	CHECK(sig_vma(e, 0x1000, 0x2000, false) != sig_vma(e, 0x1000, 0x2000, true));
	CHECK(sig_vma(e, 0x1000, 0x2000, false) != sig_vma(e, 0x1000, 0x3000, false));
	CHECK(sig_vma(e, 0x1000, 0x2000, false) != sig_vma(e, 0x2000, 0x2000, false));
	CHECK(sig_vma(e, 0x1000, 0x2000, false) != e);
	{
		// 64 pages = 4 grains. Resident runs are seen at the 64 KiB grain: a second page in the same grain changes
		// nothing, a page in another grain does.
		std::vector<unsigned char> v(64, 0);
		const uint64_t             s0 = sig_runs(e, 0x100000, 0x140000, v.data(), v.size());
		CHECK(s0 == e); // nothing resident: nothing folded
		v[3] = 1;
		const uint64_t s1 = sig_runs(e, 0x100000, 0x140000, v.data(), v.size());
		CHECK(s1 != s0);
		v[4] = 1; // the same run, the same grain
		CHECK(sig_runs(e, 0x100000, 0x140000, v.data(), v.size()) == s1);
		v[20] = 1; // another run in the second grain
		const uint64_t s2 = sig_runs(e, 0x100000, 0x140000, v.data(), v.size());
		CHECK(s2 != s1);
		v[20] = 0;
		CHECK(sig_runs(e, 0x100000, 0x140000, v.data(), v.size()) == s1);
		v[4] = 0x80 | 0; // bits other than bit 0 do not count
		CHECK(sig_runs(e, 0x100000, 0x140000, v.data(), v.size()) == s1);
		// the last run is cut at the VMA's end
		std::vector<unsigned char> w(20, 1); // 80 KiB, all resident
		CHECK(sig_runs(e, 0x100000, 0x114000, w.data(), w.size()) == fold(fold(e, 0x100000), 0x114000));
	}
	// the rule for leaving the walk out
	CHECK(!can_skip(0, 5, true, 5));  // the thread has not finished a pass
	CHECK(!can_skip(3, 5, false, 5)); // no walk stands (start, device reopen)
	CHECK(!can_skip(3, 5, true, 6));  // the thread saw something else than the walk
	CHECK(can_skip(3, 5, true, 5));
	// tag as415c: the "events" form
	CHECK(mode_of("events") == 3);
	CHECK(mode_of("thread") == 2);
	CHECK(mode_of("verify") == 1);
	CHECK(mode_of("0") == 0);
	{
		const uint64_t e0 = events().load();
		note(0x7f0000000000ull, 0x1000, true); // above the guest's span
		note(0x1000, 0x1000, true);            // below it
		note(0x200000, 0x1000, false);         // not readable
		note(0x200000, 0, true);               // empty
		CHECK(events().load() == e0);
		note(0x200000, 0x1000, true);
		CHECK(events().load() == e0 + 1);
		note(0x3f000, 0x2000, true); // straddles the span's start
		CHECK(events().load() == e0 + 2);
		note(kGuestMax, 0x1000, true); // the span's last byte
		CHECK(events().load() == e0 + 3);
		note(kGuestMax + 1, 0x1000, true);
		CHECK(events().load() == e0 + 3);
	}
	CHECK(events_moved(7, 7, false)); // no walk stands: walk
	CHECK(events_moved(8, 7, true));  // the counter moved
	CHECK(!events_moved(7, 7, true));
	CHECK(events_skip(false, true));   // nothing new, nothing anonymous: leave the walk out
	CHECK(!events_skip(true, true));   // the counter moved
	CHECK(!events_skip(false, false)); // an anonymous VMA exists: the old timing
	std::printf("test0415anon: %d of %d; end\n", g_n - g_bad, g_n);
	return g_bad == 0 ? 0 : 1;
}
