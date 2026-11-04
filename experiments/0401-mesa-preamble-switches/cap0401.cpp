// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e7, tag cap: the CPU test of mkcap0401.py's src/libs/bc5LleAgc.cpp (cap0401-notes.md), the caps
// on exp 0403's two maps that only grow: BC5_DIRECT_INHERIT_PROG_CAP (g_inh_prog, one entry per compute program a bound acb
// dispatch ran) and BC5_DIRECT_INHERIT_CENSUS_CAP (each guest queue's census of SET_SH_REG kinds). It calls the unit through
// its seams (bc5_cap0401_*): the real cap_parse and cap_slot, the unit's own reading of the two switches, acb_inherit_track's
// update of g_inh_prog (inh_prog_note) and the real acb_inherit_census. No game, no GPU, no window, no sound device, no
// network: the direct path is never opened (Direct::init_once is not called), so nothing is submitted anywhere.
// BC5_DIRECT_ACB_INHERIT=journal is set here before the first call (acb_inherit_census counts only with it on, and the unit
// reads it once), and BC5_DIRECT_MEM_LINE=0.
// The third switch, BC5_DIRECT_JOURNAL_QUIET (the journal without its per-event lines): the pure line classification and
// the ring of dropped lines through their seams, then the real journal() end to end: the test gives it a journal directory
// of its own (./gc-cap0401, in the fresh directory the box runs it in) and reads direct.log back. The play's journal mode is
// "min" (BC5_DIRECT_JOURNAL=min, read when the unit is loaded), so the test runs itself again once with it set
// (CAP0401_REEXEC=1 marks the second run, as gpu0405 does); if that fails it goes on in the other mode and says so.
// Each switch is read from the environment as the unit reads it: unset, empty and "0" are off; for the caps a decimal value
// from 2 to 2^32 is the cap and any other on value takes the default (65536 programs, 4096 census kinds per queue). Each
// case runs with its own switch on or off; off, it checks today's behaviour: every new key is taken, as today's operator[]
// takes it, and direct.log holds every line exactly as written.
// Output: one line per case, then "cap0401: on N of N; end" (all three on), "cap0401: off N of N; end" (all off or unset) or
// "cap0401: mixed <the ones on> N of N; end"; without "; end" something failed. Exit 0 only after the end line. A watchdog
// ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate cap0401.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage: BC5_DIRECT_INHERIT_PROG_CAP=1 BC5_DIRECT_INHERIT_CENSUS_CAP=1 BC5_DIRECT_JOURNAL_QUIET=1 cap0401 on   |
//        (each =0 or unset) cap0401 off   |   cap0401

#include <unistd.h>

#include <atomic>
#include <cerrno>
#include <chrono>
#include <cinttypes>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

// The seams of mkcap0401.py's unit (always compiled in, never called by the emulator).
extern "C" uint64_t bc5_cap0401_parse(const char* e, uint64_t dflt);
extern "C" uint64_t bc5_cap0401_slot(const uint32_t* keys, uint64_t n, uint64_t cap, uint32_t* out_keys, uint64_t* out_counts, uint64_t out_cap, uint64_t* refused);
extern "C" void     bc5_cap0401_caps(uint64_t* prog, uint64_t* census);
extern "C" int      bc5_cap0401_prog_note(uint64_t pgm, int w32);
extern "C" uint64_t bc5_cap0401_prog_size();
extern "C" int      bc5_cap0401_prog_get(uint64_t pgm, uint64_t* own32, uint64_t* own64);
extern "C" void     bc5_cap0401_census(const uint32_t* p, uint32_t len);
extern "C" uint64_t bc5_cap0401_census_size(uint64_t* ops_76);
extern "C" uint64_t bc5_cap0401_census_get(uint32_t key);
extern "C" uint64_t bc5_cap0401_refused(int which);
extern "C" int      bc5_cap0401_quiet_kind(const char* s, uint64_t n, int complete);
extern "C" uint64_t bc5_cap0401_quiet_ring(const char* const* lines, uint64_t n, char* out, uint64_t out_cap, uint64_t* again);
extern "C" int      bc5_cap0401_journal_open(const char* dir);
extern "C" void     bc5_cap0401_journal(const char* text);
extern "C" void     bc5_cap0401_journal_flush();
extern "C" int      bc5_cap0401_journal_min();
extern "C" int      bc5_cap0401_journal_quiet();
extern "C" uint64_t bc5_cap0401_quiet_count(int kind);
extern "C" void     bc5_cap0401_quiet_summary(char* out, uint64_t cap);

namespace cap0401 {

static int                      g_pass       = 0;
static int                      g_total      = 0;
static int                      g_case_pass  = 0;
static int                      g_case_total = 0;
static std::atomic<const char*> g_case {"init"};

static void Check(bool ok, const char* what, int line) {
	g_total++;
	g_case_total++;
	if (ok) {
		g_pass++;
		g_case_pass++;
	} else {
		std::printf("cap0401: FAIL %s (line %d): %s\n", g_case.load(), line, what);
		std::fflush(stdout);
	}
}
#define CHECK(cond) Check((cond), #cond, __LINE__)

static void Begin(const char* name) {
	g_case       = name;
	g_case_pass  = 0;
	g_case_total = 0;
}
static void End(const char* sw) {
	std::printf("cap0401: case %s (%s): %d of %d\n", g_case.load(), sw, g_case_pass, g_case_total);
	std::fflush(stdout);
}

constexpr uint64_t kProgDefault   = 65536; // the unit's kInhProgCapDefault
constexpr uint64_t kCensusDefault = 4096;  // the unit's kInhCensusCapDefault
constexpr uint64_t kTwo32         = 1ull << 32u;

// The test's own reading of a switch (written apart from the unit's cap_parse): 0 off, else the cap.
static uint64_t ExpectCap(const char* e, uint64_t dflt) {
	if (e == nullptr || e[0] == 0 || std::strcmp(e, "0") == 0) return 0;
	if (e[0] < '0' || e[0] > '9') return dflt; // strtoull would take blanks and signs
	char* end = nullptr;
	errno     = 0;
	const unsigned long long v = std::strtoull(e, &end, 10);
	if (errno != 0 || end == nullptr || *end != 0 || v < 2 || v > kTwo32) return dflt;
	return v;
}

// 1. cap_parse, the switch's reading, for values a maintainer could type (default 7 here, to tell it from a value).
static void Parse() {
	Begin("parse");
	struct Row {
		const char* e;
		uint64_t    want;
	};
	static const Row rows[] = {
		{nullptr, 0}, {"", 0}, {"0", 0}, {"1", 7}, {"2", 2}, {"64", 64}, {"65536", 65536}, {"00", 7}, {"01", 7}, {"02", 2}, {"abc", 7}, {"on", 7}, {"12x", 7},
		{" 5", 7}, {"-5", 7}, {"+5", 7}, {"4294967296", kTwo32}, {"4294967297", 7}, {"99999999999999999999999999", 7},
	};
	for (const Row& r: rows) {
		const uint64_t got = bc5_cap0401_parse(r.e, 7);
		if (got != r.want) std::printf("cap0401:   parse \"%s\": %" PRIu64 ", want %" PRIu64 "\n", r.e == nullptr ? "(unset)" : r.e, got, r.want);
		CHECK(got == r.want);
		CHECK(got == ExpectCap(r.e, 7)); // the unit's reading and the test's agree
	}
	End("pure");
}

// 2. cap_slot over a map of the test's own: cap 0 is operator[] (today's), a cap keeps the first keys and their counts.
static std::vector<uint32_t> Keys(uint64_t n, uint32_t space, uint32_t seed) {
	std::vector<uint32_t> v(n);
	uint32_t              x = seed;
	for (uint64_t k = 0; k < n; k++) {
		x    = x * 1103515245u + 12345u;
		v[k] = (x >> 8u) % space;
	}
	return v;
}
static void SlotOne(const std::vector<uint32_t>& keys, uint64_t cap) {
	// The reference, written apart from the unit: cap 0 counts every key; a cap keeps the first cap distinct keys, in the
	// order they first came, with all their counts, and refuses every later new key.
	std::map<uint32_t, uint64_t> ref;
	std::set<uint32_t>           kept;
	uint64_t                     ref_refused = 0;
	for (const uint32_t k: keys) {
		if (cap == 0 || kept.count(k) != 0 || kept.size() < cap) {
			kept.insert(k);
			ref[k]++;
		} else {
			ref_refused++;
		}
	}
	std::vector<uint32_t> ok(keys.size() + 1);
	std::vector<uint64_t> oc(keys.size() + 1);
	uint64_t              refused = ~0ull;
	const uint64_t        size    = bc5_cap0401_slot(keys.data(), keys.size(), cap, ok.data(), oc.data(), ok.size(), &refused);
	CHECK(size == ref.size());
	CHECK(refused == ref_refused);
	if (cap != 0) CHECK(size <= cap);
	bool     same = size == ref.size();
	uint64_t i    = 0;
	for (const auto& [k, c]: ref) {
		if (i >= size || ok[i] != k || oc[i] != c) same = false;
		i++;
	}
	CHECK(same);
}
static void Slot() {
	Begin("slot");
	const std::vector<uint32_t> keys = Keys(20000, 3000, 0x0401u);
	std::set<uint32_t>          distinct(keys.begin(), keys.end());
	SlotOne(keys, 0);                    // today's operator[]
	SlotOne(keys, 100);                  // full early: most keys refused
	SlotOne(keys, distinct.size() - 1);  // the last new key refused
	SlotOne(keys, distinct.size());      // exactly room: the same as today
	SlotOne(keys, 1u << 20u);            // more room than keys: the same as today
	SlotOne(std::vector<uint32_t>(), 4); // nothing
	End("pure");
}

// 3. The unit read the switches as the test does.
static void Switches(uint64_t want_prog, uint64_t want_census, const char* mode) {
	Begin("switches");
	uint64_t prog = ~0ull, census = ~0ull;
	bc5_cap0401_caps(&prog, &census);
	std::printf("cap0401:   the unit's caps: programs %" PRIu64 ", census %" PRIu64 " (0: off)\n", prog, census);
	CHECK(prog == want_prog);
	CHECK(census == want_census);
	End(mode);
}

// 4. g_inh_prog through acb_inherit_track's update (one bound dispatch per call): off takes every program; on keeps cap of
// them, refuses the rest (counted), and keeps counting the ones it holds.
static uint64_t Pgm(uint64_t k) {
	return 0x0011d0000000ull + k * 0x100u; // COMPUTE_PGM_LO/HI as an address: 256-byte steps, as inherit_pgm gives them
}
static void Programs(uint64_t cap) {
	Begin("programs");
	const bool     big      = cap > 200000; // a cap this test will not fill: checked as off
	const uint64_t extra    = 1000;
	const uint64_t n        = cap == 0 ? 70000 : big ? 1000 : cap + extra;
	const uint64_t refused0 = bc5_cap0401_refused(0);
	CHECK(bc5_cap0401_prog_size() == 0);
	uint64_t recorded = 0;
	for (uint64_t k = 0; k < n; k++) recorded += static_cast<uint64_t>(bc5_cap0401_prog_note(Pgm(k), static_cast<int>(k & 1u)));
	const int again = bc5_cap0401_prog_note(Pgm(0), 1); // a program already held, now in the other wave mode
	uint64_t  o32 = 0, o64 = 0;
	CHECK(again == 1);
	CHECK(bc5_cap0401_prog_get(Pgm(0), &o32, &o64) == 1 && o32 == 1 && o64 == 1);
	CHECK(bc5_cap0401_prog_get(Pgm(1), &o32, &o64) == 1 && o32 == 1 && o64 == 0);
	if (cap == 0 || big) {
		CHECK(recorded == n);
		CHECK(bc5_cap0401_prog_size() == n);
		CHECK(bc5_cap0401_refused(0) == refused0);
		CHECK(bc5_cap0401_prog_get(Pgm(n - 1), &o32, &o64) == 1);
	} else {
		CHECK(recorded == cap);
		CHECK(bc5_cap0401_prog_size() == cap);
		CHECK(bc5_cap0401_refused(0) - refused0 == extra);
		CHECK(bc5_cap0401_prog_get(Pgm(cap - 1), &o32, &o64) == 1);
		CHECK(bc5_cap0401_prog_get(Pgm(cap), &o32, &o64) == 0);     // the first one refused is not there
		CHECK(bc5_cap0401_prog_get(Pgm(n - 1), &o32, &o64) == 0);
		CHECK(bc5_cap0401_prog_note(Pgm(cap), 0) == 0);             // and stays out
		CHECK(bc5_cap0401_refused(0) - refused0 == extra + 1);
		CHECK(bc5_cap0401_prog_size() == cap);
	}
	std::printf("cap0401:   %" PRIu64 " programs noted, %" PRIu64 " held, %" PRIu64 " refused\n", n, bc5_cap0401_prog_size(), bc5_cap0401_refused(0) - refused0);
	End(cap == 0 ? "off" : "on");
}

// 5. The census through the real acb_inherit_census (this thread's queue: t_queue_idx -1): off counts every SET_SH_REG kind;
// on keeps cap kinds per queue. The opcode counts (bounded by 256) and other packets are as today either way.
static uint32_t SetSh(uint32_t reg, uint32_t* pk) { // SET_SH_REG (0x76), one register: 3 dwords; returns its census key
	pk[0] = 0xC0017600u; // PKT3, count 1 (Mesa sid.h PKT3_SET_SH_REG 0x76)
	pk[1] = reg;
	pk[2] = 0x0401u;
	return (reg << 8u) | 1u; // acb_inherit_census's key: first register << 8 | count (len - 2)
}
static void Census(uint64_t cap) {
	Begin("census");
	const bool     big      = cap > 60000; // the keys below use one register each (at most 65536): checked as off
	const uint64_t extra    = 50;
	const uint64_t n        = cap == 0 ? 5000 : big ? 1000 : cap + extra;
	const uint64_t refused0 = bc5_cap0401_refused(1);
	uint64_t       ops0     = ~0ull;
	CHECK(bc5_cap0401_census_size(&ops0) == 0 && ops0 == 0);
	uint32_t pk[3];
	for (uint64_t k = 0; k < n; k++) {
		SetSh(static_cast<uint32_t>(k), pk);
		bc5_cap0401_census(pk, 3);
	}
	const uint32_t key0 = SetSh(0, pk);
	bc5_cap0401_census(pk, 3);                 // a kind already held
	const uint32_t nop[2] = {0xC0001000u, 0u}; // NOP (0x10), 2 dwords: an opcode count only, as today
	bc5_cap0401_census(nop, 2);
	SetSh(7, pk);
	bc5_cap0401_census(pk, 2); // a SET_SH_REG cut to 2 dwords: no kind, as today (len >= 3)
	uint64_t       ops  = 0;
	const uint64_t size = bc5_cap0401_census_size(&ops);
	CHECK(ops == n + 2); // every SET_SH_REG counted by opcode, the cap or not
	CHECK(bc5_cap0401_census_get(key0) == 2);
	if (cap == 0 || big) {
		CHECK(size == n);
		CHECK(bc5_cap0401_refused(1) == refused0);
		CHECK(bc5_cap0401_census_get((static_cast<uint32_t>(n - 1) << 8u) | 1u) == 1);
	} else {
		CHECK(size == cap);
		CHECK(bc5_cap0401_refused(1) - refused0 == extra);
		CHECK(bc5_cap0401_census_get((static_cast<uint32_t>(cap - 1) << 8u) | 1u) == 1);
		CHECK(bc5_cap0401_census_get((static_cast<uint32_t>(cap) << 8u) | 1u) == 0); // refused
	}
	std::printf("cap0401:   %" PRIu64 " SET_SH_REG kinds sent, %" PRIu64 " held, %" PRIu64 " refused\n", n, size, bc5_cap0401_refused(1) - refused0);
	End(cap == 0 ? "off" : "on");
}

// ---- BC5_DIRECT_JOURNAL_QUIET ------------------------------------------------------------------------------------------
// The lines below are formatted with the unit's own format strings (mkcap0401.py asserts the unit still writes them so).
static std::string Fmt(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static std::string Fmt(const char* fmt, ...) {
	char    b[1024];
	va_list ap;
	va_start(ap, fmt);
	std::vsnprintf(b, sizeof(b), fmt, ap);
	va_end(ap);
	return b;
}
static int Kind(const std::string& s, bool complete = true) {
	return bc5_cap0401_quiet_kind(s.data(), s.size(), complete ? 1 : 0);
}
static const char* const kRules[7] = {"", "per-submission timing", "per-job timing", "per-wait timing", "per-flip timing", "acb rest", "submit progress"};
// The two submit-line forms the completion thread and submit_now write (one format).
static std::string SubmitLine(uint64_t n, const char* verdict, int rc, const char* timeout, const char* retried) {
	return Fmt("submit #%" PRIu64 " %s %u dwords at %p: pass %" PRIu64 " rewrite %" PRIu64 " drop %" PRIu64 " unmapped %" PRIu64 " cc %" PRIu64 " mappings %zu ... %s rc %d%s%s %.2f ms\n",
	           n, "dcb", 1200u, reinterpret_cast<const void*>(0x7f0012340000ull), uint64_t {900}, uint64_t {3}, uint64_t {2}, uint64_t {0}, uint64_t {1}, size_t {99}, verdict, rc,
	           timeout, retried, 0.12);
}

// 6. Which line kinds quiet mode drops (pure: journal_quiet_kind; it does not depend on the switch).
static void QuietKinds() {
	Begin("quiet kinds");
	struct Row {
		std::string line;
		bool        complete;
		int         want;
		const char* what;
	};
	const std::string sync = Fmt("timing: t %.3f s %s %u dwords: sync%s %.1f ms, hints %.1f ms q%d\n", 12.345, "dcb", 1200u, " (lazy)", 0.0, 0.1, -1);
	const Row         rows[] = {
        {sync, true, 1, "a submission's timing line"},
        {Fmt("timing: t %.3f s %s %u dwords: sync%s %.1f ms, hints %.1f ms q%d\n", 12.345, "acb", 77u, "", 1.5, 0.0, 3), true, 1, "the same, forced sync"},
        {Fmt("timing: #%" PRIu64 " done at t %.3f s, %.1f ms after the sync and hints; device: prepare %.2f list %.2f cs %.2f fence %.2f ms, %u BOs%s\n", uint64_t {412349}, 427.646, 0.4,
             0.12, 0.01, 0.05, 361.9, 213u, " (short list)"),
         true, 2, "a job's timing line"},
        {Fmt("timing: t %.3f s after that wait (%s %u dwords)\n", 12.4, "dcb", 300u), true, 3, "a wait's timing line"},
        {Fmt("timing: t %.3f s flip %d/%d, VideoOutSubmitFlip took %.1f ms\n", 12.5, 0, 1, 0.3), true, 4, "a flip's timing line"},
        {Fmt("acb rest %u..%u of %u dwords: state prefix of %u dwords replayed first\n", 10u, 300u, 300u, 120u), true, 5, "an acb rest"},
        {SubmitLine(128, "OK", 0, "", ""), true, 6, "a submit line that went well"},
        {SubmitLine(192, "OK", 0, "", " (retried)"), true, 0, "a retried submit line"},
        {SubmitLine(256, "FAILED", -14, "", ""), true, 0, "a failed submit line"},
        {SubmitLine(320, "FAILED", -62, " TIMEOUT", ""), true, -1, "a submit line that timed out"},
        {"timing split over 128 submissions: probe 1.0 ms, anon sync 2.0\n", true, 0, "the timing summary"},
        {"frame profile: t 12.360 s, 20.0 ms since the last flip; game thread inside the host 5.0 ms\n", true, 0, "the frame profile"},
        {"memory (exp 0401): t 10.0 s: available 500 MiB, swap used 600 MiB, psi some 0.00 full 0.00 (avg10, %), full total 0 ms, gtt 12000 of 13312 MiB\n", true, 0, "the memory line"},
        {"cpu-wait WAIT_REG_MEM64 at 12 on 0x12004b38: GIVEN UP after 4.1 ms\n", true, 0, "a wait given up"},
        {"  wait detail: function 3, value 0x1, reference 0x2, mask 0xffffffff\n", true, 0, "its detail"},
        {"acb state restore (exp 0381): t 1.000 s dcb 1200 dwords, 40 registers in 60 dwords (1 such buffers)\n", true, 0, "a catcher's sampled line"},
        {"fl crumbs (exp 0404): submit #39849 dcb op 24 at 2799 (+2889 in the copy), entry 0: stages 00482030 (1 draws so far)\n", true, 0, "a first-occurrence line"},
        {"table catcher (exp 0401): at completion, submit #5 dcb op 24 at 7: 0x1 16 bytes changed since submit (1 changes so far)\n", true, 0, "a catcher at completion"},
        {"table catcher (exp 0401): at the timeout, submit #5 dcb: 3 slots hashed at submit, 0 changed\n", true, -1, "a catcher at the timeout"},
        {"fl crumbs (exp 0404): at the timeout of submit #5 dcb: issued #5 +7, done #5 +3\n", true, -1, "the crumbs at the timeout"},
        {"timeout probe: dcb 1200 dwords dumped to /x/ib-timeout.bin\n", true, -1, "the timeout probe"},
        {"timeout: fault 0x0 status 0x00000000\n", true, -1, "the timeout line"},
        {"reopen: ok\n", true, -1, "the reopen line"},
        {"journal quiet (exp 0401 e7): t 20.0 s: not written so far: per-submission timing 1\n", true, 0, "the quiet count"},
        {"timing: t 1.000 s something else\n", true, 0, "another timing line"},
        {sync.substr(0, sync.size() - 1), true, 0, "a timing line without its newline (a partial line)"},
        {sync, false, 0, "a timing line cut at the buffer (never dropped)"},
        {"map 0x1000 +0x2000 ... ", true, 0, "the first half of a mapping line"},
        {"", true, 0, "nothing"},
	};
	for (const Row& r: rows) {
		const int got = Kind(r.line, r.complete);
		if (got != r.want) std::printf("cap0401:   kind of %s: %d, want %d\n", r.what, got, r.want);
		CHECK(got == r.want);
	}
	End("pure");
}

// 7. The ring of dropped lines (pure: a ring of the test's own): oldest first, the last 8192, a long line cut, emptied.
static void QuietRing() {
	Begin("quiet ring");
	std::vector<char> out(1u << 20u);
	uint64_t          again = 9;
	{
		const char* const three[3] = {"a\n", "b\n", "c\n"};
		CHECK(bc5_cap0401_quiet_ring(three, 3, out.data(), out.size(), &again) == 3);
		CHECK(std::string(out.data()) == "a\nb\nc\n");
		CHECK(again == 0);
	}
	{
		std::vector<std::string> s;
		for (int k = 0; k < 8192 + 100; k++) s.push_back("L" + std::to_string(k) + "\n");
		std::vector<const char*> p;
		for (const auto& x: s) p.push_back(x.c_str());
		CHECK(bc5_cap0401_quiet_ring(p.data(), p.size(), out.data(), out.size(), &again) == 8192);
		std::string want;
		for (int k = 100; k < 8192 + 100; k++) want += s[static_cast<size_t>(k)];
		CHECK(std::string(out.data()) == want);
	}
	{
		const std::string fits(190, 'x'), cut(191, 'y'); // + "\n": 191 bytes fit the 192-byte slot, 192 do not
		const std::string l1 = fits + "\n", l2 = cut + "\n";
		const char* const two[2] = {l1.c_str(), l2.c_str()};
		CHECK(bc5_cap0401_quiet_ring(two, 2, out.data(), out.size(), &again) == 2);
		CHECK(std::string(out.data()) == l1 + std::string(187, 'y') + "...\n");
	}
	End("pure");
}

// 8. The real journal(), end to end, in the journal mode the unit was loaded with: quiet on, the kinds above are not
// written, the rest is, and the dropped lines come out before the first timeout line; off, direct.log is every line as
// written (today's).
static void QuietJournal(bool quiet) {
	Begin("quiet journal");
	const bool min = bc5_cap0401_journal_min() != 0;
	std::printf("cap0401:   the journal mode: %s\n", min ? "min (the play's: one buffered file)" : "not min (a file opened per line)");
	std::error_code             ec;
	const std::filesystem::path dir = std::filesystem::current_path() / "gc-cap0401";
	std::filesystem::create_directories(dir, ec);
	std::filesystem::remove(dir / "direct.log", ec);
	CHECK(bc5_cap0401_journal_open(dir.string().c_str()) == 1);
	CHECK(bc5_cap0401_journal_quiet() == (quiet ? 1 : 0));
	const std::string t[] = {
		"memory (exp 0401): t 10.0 s: available 500 MiB, swap used 600 MiB, psi some 0.00 full 0.00 (avg10, %), full total 0 ms, gtt 12000 of 13312 MiB\n", // 0 kept
		Fmt("timing: t %.3f s %s %u dwords: sync%s %.1f ms, hints %.1f ms q%d\n", 12.345, "dcb", 1200u, " (lazy)", 0.0, 0.1, -1),                          // 1 kind 1
		Fmt("timing: #%" PRIu64 " done at t %.3f s, %.1f ms after the sync and hints; device: prepare %.2f list %.2f cs %.2f fence %.2f ms, %u BOs%s\n", uint64_t {100}, 12.35, 0.4, 0.12,
		    0.01, 0.05, 0.21, 213u, ""), // 2 kind 2
		"frame profile: t 12.360 s, 20.0 ms since the last flip; game thread inside the host 5.0 ms\n",       // 3 kept
		Fmt("timing: t %.3f s flip %d/%d, VideoOutSubmitFlip took %.1f ms\n", 12.361, 0, 1, 0.3),              // 4 kind 4
		Fmt("timing: t %.3f s after that wait (%s %u dwords)\n", 12.37, "dcb", 300u),                          // 5 kind 3
		"cpu-wait WAIT_REG_MEM64 at 12 on 0x12004b38: GIVEN UP after 4.1 ms\n",                               // 6 kept
		Fmt("acb rest %u..%u of %u dwords: state prefix of %u dwords replayed first\n", 10u, 300u, 300u, 120u), // 7 kind 5
		SubmitLine(128, "OK", 0, "", ""),                                                                      // 8 kind 6
		"map 0x1000 +0x2000 ... ",                                                                             // 9 kept (a first half)
		"ok\n",                                                                                                // 10 kept
		SubmitLine(192, "OK", 0, "", " (retried)"),                                                            // 11 kept
		Fmt("timing: #%" PRIu64 " done at t %.3f s, %.1f ms after the sync and hints; device: prepare %.2f list %.2f cs %.2f fence %.2f ms, %u BOs%s\n", uint64_t {101}, 12.4, 0.5, 0.1,
		    0.01, 0.05, 0.3, 200u, " (short list)"), // 12 kind 2
		SubmitLine(256, "FAILED", -62, " TIMEOUT", ""),                                                               // 13 kept, the first timeout line
		"table catcher (exp 0401): at the timeout, submit #256 dcb: 3 slots hashed at submit, 0 changed\n",            // 14 kept (a timeout line, nothing left)
		Fmt("timing: t %.3f s %s %u dwords: sync%s %.1f ms, hints %.1f ms q%d\n", 14.5, "dcb", 800u, "", 0.0, 0.0, -1), // 15 kind 1, held
	};
	const uint64_t bytes0 = bc5_cap0401_quiet_count(0);
	for (const std::string& s: t) bc5_cap0401_journal(s.c_str());
	bc5_cap0401_journal_flush();
	std::ifstream     in(dir / "direct.log", std::ios::binary);
	std::stringstream got;
	got << in.rdbuf();
	std::string all, want;
	for (const std::string& s: t) all += s;
	if (!quiet) {
		CHECK(got.str() == all); // today's: every line, as written
		for (int k = 0; k <= 6; k++) CHECK(bc5_cap0401_quiet_count(k) == 0);
	} else {
		const std::string state = "exp 0401 e7: journal quiet on, not written: "; // the state line's start (mkcap0401.py)
		std::string       g     = got.str();
		const size_t      nl    = g.find('\n');
		CHECK(g.compare(0, state.size(), state) == 0 && nl != std::string::npos);
		const std::string rest = nl == std::string::npos ? std::string() : g.substr(nl + 1);
		want = t[0] + t[3] + t[6] + t[9] + t[10] + t[11] +
		       "journal quiet (exp 0401 e7): the last 7 lines it did not write, oldest first, before the timeout line below:\n" + t[1] + t[2] + t[4] + t[5] + t[7] + t[8] + t[12] +
		       "journal quiet (exp 0401 e7): end of the lines it did not write\n" + t[13] + t[14];
		if (rest != want) std::printf("cap0401:   direct.log after its state line:\n%s---- want:\n%s----\n", rest.c_str(), want.c_str());
		CHECK(rest == want);
		const uint64_t per[7] = {0, 2, 2, 1, 1, 1, 1};
		for (int k = 1; k <= 6; k++) {
			if (bc5_cap0401_quiet_count(k) != per[k]) std::printf("cap0401:   %s: %" PRIu64 ", want %" PRIu64 "\n", kRules[k], bc5_cap0401_quiet_count(k), per[k]);
			CHECK(bc5_cap0401_quiet_count(k) == per[k]);
		}
		const uint64_t b = t[1].size() + t[2].size() + t[4].size() + t[5].size() + t[7].size() + t[8].size() + t[12].size() + t[15].size();
		CHECK(bc5_cap0401_quiet_count(0) - bytes0 == b);
		char sum[512] = {};
		bc5_cap0401_quiet_summary(sum, sizeof(sum));
		const std::string tail = Fmt(": per-submission timing 2, per-job timing 2, per-wait timing 1, per-flip timing 1, acb rest 1, submit progress 1; 8 lines, %" PRIu64 " bytes in all\n", b);
		const std::string s(sum);
		CHECK(s.rfind("journal quiet (exp 0401 e7): t ", 0) == 0);
		CHECK(s.size() >= tail.size() && s.compare(s.size() - tail.size(), tail.size(), tail) == 0);
		std::printf("cap0401:   %s", sum);
	}
	End(quiet ? "on" : "off");
}

static bool SwitchOn(const char* name) { // bc5::env_on's reading
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
}

} // namespace cap0401

int main(int argc, char** argv) {
	using namespace cap0401;
	// Once: again, in the play's journal mode (BC5_DIRECT_JOURNAL=min is read when the unit is loaded).
	if (std::getenv("CAP0401_REEXEC") == nullptr) {
		::setenv("CAP0401_REEXEC", "1", 1);
		::setenv("BC5_DIRECT_JOURNAL", "min", 1);
		::setenv("BC5_DIRECT_MEM_LINE", "0", 1);
		::execv("/proc/self/exe", argv);
		std::printf("cap0401: note: running again with BC5_DIRECT_JOURNAL=min failed (%s); going on in this journal mode\n", std::strerror(errno));
	}
	::setenv("BC5_DIRECT_ACB_INHERIT", "journal", 1); // acb_inherit_census counts only with it on (read once, at the first call)
	::setenv("BC5_DIRECT_MEM_LINE", "0", 1);
	const uint64_t prog   = ExpectCap(std::getenv("BC5_DIRECT_INHERIT_PROG_CAP"), kProgDefault);
	const uint64_t census = ExpectCap(std::getenv("BC5_DIRECT_INHERIT_CENSUS_CAP"), kCensusDefault);
	const bool     quiet  = SwitchOn("BC5_DIRECT_JOURNAL_QUIET");
	const int      n_on   = (prog != 0 ? 1 : 0) + (census != 0 ? 1 : 0) + (quiet ? 1 : 0);
	const char*    mode   = n_on == 3 ? "on" : n_on == 0 ? "off" : "mixed";
	std::string    items;
	for (const auto& [on, name]: {std::pair<bool, const char*> {prog != 0, "BC5_DIRECT_INHERIT_PROG_CAP"}, {census != 0, "BC5_DIRECT_INHERIT_CENSUS_CAP"}, {quiet, "BC5_DIRECT_JOURNAL_QUIET"}}) {
		if (!on) continue;
		items += items.empty() ? "" : ",";
		items += name;
	}
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("cap0401: the argument says %s but the switches say %s %s\n", argc == 2 ? argv[1] : "too much", mode, items.c_str());
		return 2;
	}
	std::thread([] {
		std::this_thread::sleep_for(std::chrono::seconds(60));
		std::printf("cap0401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();

	Parse();
	Slot();
	Switches(prog, census, n_on == 0 ? "off" : "on");
	Programs(prog);
	Census(census);
	QuietKinds();
	QuietRing();
	QuietJournal(quiet); // last: the journal has no directory before it, so the cases above wrote nothing there

	std::fflush(stderr);
	if (n_on != 0 && n_on != 3) {
		std::printf("cap0401: mixed %s %d of %d%s\n", items.c_str(), g_pass, g_total, g_pass == g_total ? "; end" : "");
	} else {
		std::printf("cap0401: %s %d of %d%s\n", mode, g_pass, g_total, g_pass == g_total ? "; end" : "");
	}
	std::fflush(stdout);
	std::_Exit(g_pass == g_total ? 0 : 1);
}
