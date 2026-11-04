// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e7, tag zsk: the CPU test of mkzsk0401.py's src/libs/bc5LleAgc.cpp, experiment 0379's zero
// skip (BC5_DIRECT_ZERO_SKIP) carried onto the e6 unit (zsk0401-notes.md). It needs no game, no GPU, no window, no sound
// device and no network: it calls the unit's own zero-skip functions through the extern "C" seams bc5_zsk0401_*. The
// direct path is never initialised (Direct::init_once is not called, no device is opened, nothing is imported, mapped or
// submitted). The "direct memory" is a sparse memfd of the test's own; the canary is the unit's own memfd, made by
// zskip_resolve without a BO (bc5_zsk0401_reset(1)) and watched by the unit's own canary thread.
// Switch: BC5_DIRECT_ZERO_SKIP, read as the unit reads it (set, non-empty and not "0": on). On, whatever its value, the
// test writes its zero list (zsk0401-list.txt) into the current directory (a fresh one) and points the switch at that file
// before the unit first reads it. Off (=0 or unset), it checks that nothing happens: the list is not read, nothing is
// placed, and a hint, a CPU write and a device reopen change nothing.
// Both modes run exp 0379's five Catch2 cases of backend/tests/zero_skip_test.cpp (the list's round trip and parser, the
// scans' mask, all_zero, the skip set) against the unit's copy of bc5/zero_skip.hpp.
// Output: one line per case, then "zsk0401: on N of N; end" or "zsk0401: off N of N; end"; without "; end" something
// failed. Exit 0 only after the end line. A watchdog ends a hang after 60 s with a FAIL line.
// Build: build0401.py ... --gate zsk0401.cpp <out> --like src/libs/bc5LleAgc.cpp (the unit's compile command; linked with
// every emulator object but main.cpp.o, the private bc5LleAgc.cpp.o among them), -std=c++20 -Wall -Wextra -Werror.
// usage (each in a fresh directory): BC5_DIRECT_ZERO_SKIP=1 zsk0401 on | BC5_DIRECT_ZERO_SKIP=0 zsk0401 off | zsk0401 off

#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

// The seams of mkzsk0401.py's unit (always compiled in, never called by the emulator).
extern "C" int      bc5_zsk0401_switch(char* path, size_t cap);
extern "C" uint32_t bc5_zsk0401_list(const char* text, char* out, size_t cap, uint32_t* bad);
extern "C" size_t   bc5_zsk0401_mask(uint64_t heap_size, const uint8_t* scans, const size_t* lens, size_t n_scans, uint64_t min_bytes, uint64_t* info, uint64_t* runs, size_t cap);
extern "C" int      bc5_zsk0401_all_zero(const void* p, size_t n);
extern "C" uint64_t bc5_zsk0401_set(int op, uint64_t a, uint64_t b, uint64_t k);
extern "C" uint64_t bc5_zsk0401_place_set(const char* text, uint64_t base);
extern "C" uint64_t bc5_zsk0401_state(int what, uint64_t a);
extern "C" int      bc5_zsk0401_reset(int cpu_canary);
extern "C" int      bc5_zsk0401_sync_start(int kind, const char* const* names, const uint64_t* offs, const uint64_t* sizes, const int* eager, size_t n, uint64_t* blocks);
extern "C" int      bc5_zsk0401_hint(int kind, uint64_t c, int learned, uint64_t* blocks);
extern "C" void     bc5_zsk0401_take_back(int kind, int fd, uint64_t* blocks);
extern "C" size_t   bc5_zsk0401_pieces(uint64_t va, uint64_t size, uint32_t run, uint64_t lo, uint64_t hi);
extern "C" void     bc5_zsk0401_disable();

namespace zsk0401 {

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
		std::printf("zsk0401: FAIL %s (line %d): %s\n", g_case.load(), line, what);
		std::fflush(stdout);
	}
}
#define CHECK(cond) Check((cond), #cond, __LINE__)

static void Begin(const char* name) {
	g_case       = name;
	g_case_pass  = 0;
	g_case_total = 0;
}
static void End(const char* mode) {
	std::printf("zsk0401: case %s (%s): %d of %d\n", g_case.load(), mode, g_case_pass, g_case_total);
	std::fflush(stdout);
}

constexpr uint64_t M      = 1ull << 20u;
constexpr uint64_t kChunk = 2 * M;
constexpr uint64_t kNone  = ~0ull; // the st_blocks mark of a state that wants a full sync
constexpr uint64_t kMark  = 7;     // a mark the unit leaves alone unless it wants a full sync

// bc5_zsk0401_state's indices (mkzsk0401.py).
enum {
	kBytes,
	kRuns,
	kSlices,
	kCanaryId,
	kOff,
	kHeapsRead,
	kPlaced,
	kHints,
	kCpu,
	kHits,
	kPieces,
	kStop,
	kContains,
	kRunOf,
	kLeft,
	kFlag,
	kLearned,
	kCanaryFd,
	kHeapsSeen
};
static uint64_t St(int what, uint64_t a = 0) {
	return bc5_zsk0401_state(what, a);
}

// The session's list (exp 0379's format). Heap A (64 MiB: runs of 8, 4 and 16 MiB) matches its views; heap B's views span
// 34 MiB, not the listed 32, so it is refused and its canary slice stays unused.
static const char* const kList = "# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start\n"
                                 "heap ZskHeapA 0x4000000 3\n"
                                 "zero ZskHeapA 0x0 0x800000\n"
                                 "zero ZskHeapA 0x1000000 0x400000\n"
                                 "zero ZskHeapA 0x2000000 0x1000000\n"
                                 "heap ZskHeapB 0x2000000 3\n"
                                 "zero ZskHeapB 0x0 0x400000\n";
constexpr uint64_t kBaseA = 0x2000000, kBaseB = 0x6000000, kFileSize = 0x9000000;
// The views: heap A in two eager views and one lazy view beyond them (a heap's span is its eager views'), heap B in one.
static const char* const kNames[] = {"ZskHeapA", "ZskHeapA", "ZskHeapA", "ZskHeapB"};
static const uint64_t    kOffs[]  = {kBaseA, kBaseA + 0x2800000, 0x8400000, kBaseB};
static const uint64_t    kSizes[] = {0x2800000, 0x1800000, 0x200000, 0x2200000};
static const int         kEager[] = {1, 1, 0, 1};

static int         g_direct = -1; // the test's direct memory (a memfd of kFileSize, sparse)
static std::string g_list_path;

static int SyncStart(int kind, uint64_t* blocks) {
	return bc5_zsk0401_sync_start(kind, kNames, kOffs, kSizes, kEager, 4, blocks);
}
static bool Poke(int fd, uint64_t off, unsigned char v) {
	return pwrite(fd, &v, 1, static_cast<off_t>(off)) == 1;
}
// Waits up to ms for run's canary flag to read want (the unit's watcher looks at one slice per 50 ms).
static bool WaitFlag(uint64_t run, uint64_t want, int ms) {
	const auto until = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
	while (std::chrono::steady_clock::now() < until) {
		if (St(kFlag, run) == want) return true;
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
	return St(kFlag, run) == want;
}
static int CanaryFd() {
	return static_cast<int>(St(kCanaryFd)) - 1;
}

// ---- both modes ------------------------------------------------------------------------------------------------------
static void Switch(bool on) {
	Begin("switch");
	char path[4096] = {};
	CHECK(bc5_zsk0401_switch(path, sizeof path) == (on ? 1 : 0));
	if (on) {
		CHECK(g_list_path == path); // the unit reads the list the test pointed it at
	} else {
		CHECK(path[0] == 0);
	}
	End(on ? "on" : "off");
}

// exp 0379's Catch2 case "the list round-trips through its text form".
static void ListRoundTrip(const char* mode) {
	Begin("list round trip");
	const char* text = "# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start\n"
	                   "heap RenderGpuWcLarge 0xac600000 5\n"
	                   "zero RenderGpuWcLarge 0x0 0x800000\n"
	                   "zero RenderGpuWcLarge 0x99200000 0x10000000\n"
	                   "heap CommitIABufferAllocator 0xab000000 5\n"
	                   "zero CommitIABufferAllocator 0x2ec00000 0x7400000\n";
	char        out[4096] = {};
	uint32_t    bad       = 99;
	CHECK(bc5_zsk0401_list(text, out, sizeof out, &bad) == 2);
	CHECK(bad == 0);
	CHECK(std::strcmp(out, text) == 0);
	CHECK(bc5_zsk0401_list("", out, sizeof out, &bad) == 0); // an empty (or unreadable) list: no heap, nothing bad
	CHECK(bad == 0);
	End(mode);
}

// exp 0379's Catch2 case "the parser drops bad, unaligned, out-of-heap, overlapping and orphan runs".
static void ListParser(const char* mode) {
	Begin("list parser");
	const char* text = "# c\n"
	                   "heap H 0x10000000 3\r\n"     // 256 MiB, CRLF
	                   "zero H 0x0 0x400000\n"
	                   "zero H 0x200000 0x200000\n"  // overlaps the run before
	                   "zero H 0x500000 0x200000\n"  // not chunk aligned
	                   "zero H 0xff00000 0x400000\n" // past the heap's end
	                   "zero X 0x0 0x200000\n"       // no such heap
	                   "zero H 0x800000 0x0\n"       // empty
	                   "garbage\n"
	                   "heap H 0x10 1\n" // a second H
	                   "zero H 0x1000000 0x600000\n";
	char        out[4096] = {};
	uint32_t    bad       = 0;
	CHECK(bc5_zsk0401_list(text, out, sizeof out, &bad) == 1);
	CHECK(bad == 7);
	CHECK(std::strcmp(out, "# bc5 zero list v1 (experiment 0379): chunks all-zero in every scan, offsets from the heap's start\n"
	                       "heap H 0x10000000 3\n"
	                       "zero H 0x0 0x400000\n"
	                       "zero H 0x1000000 0x600000\n") == 0);
	End(mode);
}

// exp 0379's Catch2 case "the mask keeps only chunks zero in every scan, and runs respect the minimum".
static void Mask(const char* mode) {
	Begin("zero mask");
	const uint64_t size    = 21 * M; // 10 whole chunks and a partial one
	const uint8_t  scans[] = {1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, /* chunk 6 held data in the second scan: */ 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, /* a short scan: */ 1};
	const size_t   lens[]  = {11, 11, 1};
	uint64_t       info[3] = {}, runs[16] = {};
	CHECK(bc5_zsk0401_mask(size, scans, lens, 0, 0, info, runs, 8) == 0); // no scan yet: nothing is known to be zero
	CHECK(info[0] == 11 && info[1] == 0);
	CHECK(bc5_zsk0401_mask(size, scans, lens, 2, 0, info, runs, 8) == 3);
	CHECK(info[1] == 2 && info[2] == 9 * kChunk);
	CHECK(runs[0] == 0 && runs[1] == 8 * M);
	CHECK(runs[2] == 10 * M && runs[3] == 2 * M);
	CHECK(runs[4] == 14 * M && runs[5] == 6 * M); // the partial chunk 10 is not listed
	CHECK(bc5_zsk0401_mask(size, scans, lens, 2, 8 * M, info, runs, 8) == 1);
	CHECK(runs[0] == 0 && runs[1] == 8 * M);
	CHECK(bc5_zsk0401_mask(size, scans, lens, 3, 0, info, runs, 8) == 1); // a short scan clears the chunks it did not cover
	CHECK(info[2] == kChunk);
	End(mode);
}

// exp 0379's Catch2 case "all_zero finds a single set byte anywhere".
static void AllZero(const char* mode) {
	Begin("all_zero");
	static unsigned char b[kChunk + 3] = {};
	CHECK(bc5_zsk0401_all_zero(b, sizeof b) == 1);
	for (const size_t at: {size_t {0}, size_t {7}, size_t {4096}, sizeof b - 1}) {
		b[at] = 0x40;
		CHECK(bc5_zsk0401_all_zero(b, sizeof b) == 0);
		b[at] = 0;
	}
	End(mode);
}

// exp 0379's Catch2 case "the skip set places runs, gives chunks and runs back, and keeps run indices" (the seams' own set).
static void SkipSet(const char* mode) {
	Begin("skip set");
	enum { kClear, kAdd, kHas, kRunOf1, kSetBytes, kRunCount, kRunLeft, kEraseChunk, kEraseRun, kInCount, kInAt, kEmpty };
	auto           S    = [](int op, uint64_t a = 0, uint64_t b = 0, uint64_t k = 0) { return bc5_zsk0401_set(op, a, b, k); };
	const uint64_t base = 0x40000000ull;
	S(kClear);
	CHECK(bc5_zsk0401_place_set("heap H 0x4000000 4\nzero H 0x0 0x800000\nzero H 0x1000000 0x400000\n", base) == 12 * M);
	CHECK(S(kRunCount) == 2);
	CHECK(S(kHas, base) == 1);
	CHECK(S(kHas, base + 6 * M) == 1);
	CHECK(S(kHas, base + 8 * M) == 0);
	CHECK(S(kRunOf1, base + 16 * M) == 2); // run 1
	CHECK(S(kRunOf1, base + 8 * M) == 0);  // none
	CHECK(S(kInCount, base + 1 * M, base + 18 * M) == 5);
	const uint64_t want[5] = {base, base + 2 * M, base + 4 * M, base + 6 * M, base + 16 * M};
	bool           in_ok   = true;
	for (uint64_t k = 0; k < 5; k++) in_ok = in_ok && S(kInAt, base + 1 * M, base + 18 * M, k) == want[k];
	CHECK(in_ok);
	// a CPU write in chunk 1 of run 0
	CHECK(S(kEraseChunk, base + 2 * M) == 1);
	CHECK(S(kEraseChunk, base + 2 * M) == 0);
	CHECK(S(kRunLeft, 0) == 6 * M);
	CHECK(S(kSetBytes) == 10 * M);
	// a canary hit in run 0 takes the rest of it back
	CHECK(S(kEraseRun, 0) == 6 * M);
	CHECK(S(kEraseRun, 0) == 0);
	CHECK(S(kRunLeft, 0) == 0);
	CHECK(S(kSetBytes) == 4 * M);
	CHECK(S(kRunOf1, base + 16 * M) == 2); // run 1 keeps its index (its canary slice)
	// a later run never takes a chunk that is already skipped
	CHECK(S(kAdd, base + 16 * M, 4 * M) == 2);
	CHECK(S(kSetBytes) == 4 * M);
	CHECK(S(kRunOf1, base + 16 * M) == 2);
	S(kClear);
	CHECK(S(kEmpty) == 1);
	CHECK(S(kSetBytes) == 0);
	End(mode);
}

// zskip_release: a real mapping first unmaps the canary mappings it overlaps, and only those.
static void Pieces(const char* mode) {
	Begin("canary mappings released");
	const uint64_t v = 0x20000000000ull;
	CHECK(bc5_zsk0401_pieces(0, 0, 0, 0, 0) == 0); // no device: zskip_map never mapped one
	CHECK(bc5_zsk0401_pieces(v, 2 * M, 2, 0, 0) == 1);
	CHECK(bc5_zsk0401_pieces(v + 2 * M, 1 * M, 2, 0, 0) == 2);
	CHECK(bc5_zsk0401_pieces(v + 4 * M, 2 * M, 2, 0, 0) == 3);
	CHECK(bc5_zsk0401_pieces(0, 0, 0, v + 2 * M + M / 2, v + 4 * M) == 2); // the 1-MiB one starts before lo and overlaps
	CHECK(bc5_zsk0401_pieces(0, 0, 0, v + 2 * M, v + 4 * M) == 2);         // nothing else lies there
	CHECK(bc5_zsk0401_pieces(0, 0, 0, v + 1 * M, v + 1 * M + 1) == 1);     // the first one
	CHECK(bc5_zsk0401_pieces(0, 0, 0, v + 4 * M, v + 6 * M) == 0);
	CHECK(St(kPieces) == 0);
	End(mode);
}

// ---- on --------------------------------------------------------------------------------------------------------------
// Without a device the canary cannot be made: the placed runs are cleared and the skip is off for the session.
static void NoDevice() {
	Begin("no device: nothing skipped");
	CHECK(bc5_zsk0401_reset(0) == 0);
	uint64_t b = kMark;
	CHECK(SyncStart(0, &b) == 0);
	CHECK(b == kMark);
	CHECK(St(kHeapsRead) == 2);
	CHECK(St(kHeapsSeen) == 2);   // A placed, B refused (its span)
	CHECK(St(kPlaced) == 28 * M); // A's three runs were placed ...
	CHECK(St(kBytes) == 0);       // ... and cleared: no canary, nothing skipped
	CHECK(St(kRuns) == 0);
	CHECK(St(kCanaryId) == 0);
	CHECK(St(kOff) == 1);
	b = kMark;
	CHECK(SyncStart(0, &b) == 0); // off for the session
	CHECK(b == kMark);
	End("on");
}

static void Placement() {
	Begin("placement");
	CHECK(bc5_zsk0401_reset(1) == 0);
	uint64_t b = kMark;
	CHECK(SyncStart(1, &b) == 0); // the private memory's state: never
	CHECK(b == kMark);
	CHECK(St(kHeapsRead) == 0);
	CHECK(SyncStart(0, &b) == 1);
	CHECK(b == kNone); // a full sync, so the eager loop leaves the chunks out at once
	CHECK(St(kHeapsRead) == 2);
	CHECK(St(kHeapsSeen) == 2);
	CHECK(St(kBytes) == 28 * M);
	CHECK(St(kPlaced) == 28 * M);
	CHECK(St(kRuns) == 3);   // A's runs 0, 1 and 2
	CHECK(St(kSlices) == 4); // one canary slice per run of the list, B's included
	CHECK(St(kCanaryId) == 1);
	CHECK(St(kCanaryFd) != 0);
	CHECK(St(kOff) == 0);
	CHECK(St(kContains, kBaseA) == 1);
	CHECK(St(kContains, kBaseA + 6 * M) == 1);
	CHECK(St(kContains, kBaseA + 8 * M) == 0);
	CHECK(St(kContains, kBaseA + 16 * M) == 1);
	CHECK(St(kContains, kBaseA + 18 * M) == 1);
	CHECK(St(kContains, kBaseA + 20 * M) == 0);
	CHECK(St(kContains, kBaseA + 32 * M) == 1);
	CHECK(St(kContains, kBaseA + 46 * M) == 1);
	CHECK(St(kContains, kBaseA + 48 * M) == 0);
	CHECK(St(kContains, kBaseB) == 0); // B refused
	CHECK(St(kRunOf, kBaseA + 18 * M) == 2); // run 1
	CHECK(St(kLeft, 0) == 8 * M);
	CHECK(St(kLeft, 1) == 4 * M);
	CHECK(St(kLeft, 2) == 16 * M);
	CHECK(St(kLeft, 3) == 0);
	CHECK(St(kFlag, 0) == 0 && St(kFlag, 1) == 0 && St(kFlag, 2) == 0 && St(kFlag, 3) == 0);
	CHECK(bc5_zsk0401_reset(1) == -1); // a watcher reads the slices now: nothing is reset under it
	b = kMark;
	CHECK(SyncStart(0, &b) == 0); // placed once
	CHECK(b == kMark);
	End("on");
}

// direct_force's take-back: a hint window takes a skipped chunk back, a learned window (map_window's guard) does not.
static void HintLearned() {
	Begin("hint and learned window");
	uint64_t b = kMark;
	CHECK(bc5_zsk0401_hint(0, kBaseA + 2 * M, 1, &b) == 0); // learned: stays skipped
	CHECK(b == kMark);
	CHECK(St(kContains, kBaseA + 2 * M) == 1);
	CHECK(St(kHints) == 0);
	CHECK(St(kLearned) == 0); // the guard ended with its scope
	CHECK(bc5_zsk0401_hint(0, kBaseA + 2 * M, 0, &b) == 1); // a hint: back
	CHECK(b == kNone);
	CHECK(St(kContains, kBaseA + 2 * M) == 0);
	CHECK(St(kHints) == 1);
	CHECK(St(kLeft, 0) == 6 * M);
	CHECK(St(kBytes) == 26 * M);
	b = kMark;
	CHECK(bc5_zsk0401_hint(0, kBaseA + 2 * M, 0, &b) == 0); // once
	CHECK(bc5_zsk0401_hint(0, kBaseA + 8 * M, 0, &b) == 0); // not on the list
	CHECK(bc5_zsk0401_hint(1, kBaseA + 4 * M, 0, &b) == 0); // the private memory's state: never
	CHECK(b == kMark);
	CHECK(St(kContains, kBaseA + 4 * M) == 1);
	CHECK(St(kHints) == 1);
	End("on");
}

// zskip_take_back's SEEK_DATA walk: a chunk the CPU wrote leaves the skip set.
static void CpuWrite() {
	Begin("CPU write");
	CHECK(Poke(g_direct, kBaseA + 32 * M + 0x1234, 0x11)); // run 2, its first chunk
	CHECK(Poke(g_direct, kBaseA + 9 * M, 0x22));           // not on the list
	CHECK(Poke(g_direct, kBaseA + 2 * M + 5, 0x33));       // a chunk the hint took back already
	uint64_t b = kMark;
	bc5_zsk0401_take_back(1, g_direct, &b); // the private memory's state: nothing
	CHECK(St(kCpu) == 0);
	bc5_zsk0401_take_back(0, g_direct, &b);
	CHECK(b == kMark); // the caller is in its full sync already
	CHECK(St(kCpu) == 1);
	CHECK(St(kContains, kBaseA + 32 * M) == 0);
	CHECK(St(kContains, kBaseA + 34 * M) == 1);
	CHECK(St(kLeft, 2) == 14 * M);
	CHECK(St(kBytes) == 24 * M);
	bc5_zsk0401_take_back(0, g_direct, &b); // the same file again: nothing more
	CHECK(St(kCpu) == 1);
	CHECK(St(kBytes) == 24 * M);
	End("on");
}

// The canary: a write into a run's slice is seen by the unit's watcher, forces a full sync and takes the run back.
static void CanaryHit() {
	Begin("canary hit");
	CHECK(CanaryFd() >= 0);
	CHECK(Poke(CanaryFd(), 1 * kChunk + 4096 + 5, 0x5a)); // "the GPU" wrote into run 1's slice
	CHECK(WaitFlag(1, 1, 10000));
	uint64_t b = kMark;
	CHECK(SyncStart(0, &b) == 0);
	CHECK(b == kNone); // a hit forces a full sync
	b = kMark;
	bc5_zsk0401_take_back(0, g_direct, &b);
	CHECK(b == kNone);
	CHECK(St(kFlag, 1) == 2);
	CHECK(St(kHits) == 1);
	CHECK(St(kLeft, 1) == 0);
	CHECK(St(kContains, kBaseA + 16 * M) == 0);
	CHECK(St(kContains, kBaseA + 18 * M) == 0);
	CHECK(St(kBytes) == 20 * M);
	CHECK(St(kContains, kBaseA + 4 * M) == 1); // the other runs stay
	CHECK(St(kContains, kBaseA + 34 * M) == 1);
	CHECK(St(kFlag, 0) == 0 && St(kFlag, 2) == 0 && St(kFlag, 3) == 0);
	b = kMark;
	CHECK(SyncStart(0, &b) == 0);
	CHECK(b == kMark); // done: no more full syncs for it
	End("on");
}

// exp 0401 e7's one change of behaviour: a hit on a run that hints took back in full is retired. 0379 left its flag at 1,
// and every later sync was a full one while anything stayed skipped.
static void LateHit() {
	Begin("hit after a full take-back");
	uint64_t b = kMark;
	CHECK(bc5_zsk0401_hint(0, kBaseA, 0, &b) == 1);
	CHECK(bc5_zsk0401_hint(0, kBaseA + 4 * M, 0, &b) == 1);
	CHECK(bc5_zsk0401_hint(0, kBaseA + 6 * M, 0, &b) == 1);
	CHECK(St(kLeft, 0) == 0);
	CHECK(St(kBytes) == 14 * M);
	CHECK(St(kHints) == 4);
	CHECK(Poke(CanaryFd(), 0 * kChunk + 77, 0x33)); // a write that reached run 0's slice before the hints
	CHECK(WaitFlag(0, 1, 10000));
	b = kMark;
	CHECK(SyncStart(0, &b) == 0);
	CHECK(b == kNone); // seen once ...
	b = kMark;
	bc5_zsk0401_take_back(0, g_direct, &b);
	CHECK(b == kMark); // ... and retired: nothing was left to take back
	CHECK(St(kFlag, 0) == 2);
	CHECK(St(kHits) == 1);
	CHECK(St(kBytes) == 14 * M);
	b = kMark;
	CHECK(SyncStart(0, &b) == 0);
	CHECK(b == kMark); // 0379 forced a full sync here, at every call
	End("on");
}

// A device reopen ends the skip for the session.
static void Reopen() {
	Begin("device reopen");
	bc5_zsk0401_disable();
	CHECK(St(kBytes) == 0);
	CHECK(St(kRuns) == 0);
	CHECK(St(kPieces) == 0);
	CHECK(St(kOff) == 1);
	CHECK(St(kCanaryId) == 0);
	CHECK(St(kStop) == 1);
	uint64_t b = kMark;
	CHECK(SyncStart(0, &b) == 0); // everything is imported from here on
	CHECK(b == kMark);
	CHECK(bc5_zsk0401_hint(0, kBaseA + 34 * M, 0, &b) == 0);
	bc5_zsk0401_take_back(0, g_direct, &b);
	CHECK(b == kMark);
	End("on");
}

// ---- off -------------------------------------------------------------------------------------------------------------
static void OffNothing() {
	Begin("off: nothing placed");
	CHECK(bc5_zsk0401_reset(1) == 0); // even with a canary at hand
	uint64_t b = kMark;
	CHECK(SyncStart(0, &b) == 0);
	CHECK(SyncStart(1, &b) == 0);
	CHECK(b == kMark);
	CHECK(St(kHeapsRead) == 0); // no list is read
	CHECK(St(kHeapsSeen) == 0);
	CHECK(St(kBytes) == 0);
	CHECK(St(kRuns) == 0);
	CHECK(St(kSlices) == 0);
	CHECK(St(kCanaryId) == 0);
	CHECK(St(kCanaryFd) == 0);
	CHECK(St(kOff) == 0);
	End("off");
}

static void OffSteps() {
	Begin("off: hint, CPU write, reopen");
	uint64_t b = kMark;
	CHECK(bc5_zsk0401_hint(0, kBaseA, 0, &b) == 0);
	CHECK(Poke(g_direct, kBaseA + 32 * M, 0x44));
	bc5_zsk0401_take_back(0, g_direct, &b);
	CHECK(b == kMark);
	CHECK(St(kCpu) == 0);
	CHECK(St(kHints) == 0);
	bc5_zsk0401_disable();
	CHECK(St(kStop) == 0); // nothing to end
	CHECK(St(kOff) == 0);
	End("off");
}

} // namespace zsk0401

int main(int argc, char** argv) {
	using namespace zsk0401;
	const char* e    = std::getenv("BC5_DIRECT_ZERO_SKIP");
	const bool  on   = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
	const char* mode = on ? "on" : "off";
	if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("zsk0401: the argument says %s but BC5_DIRECT_ZERO_SKIP says %s\n", argc == 2 ? argv[1] : "too much", mode);
		return 2;
	}
	std::thread([] {
		std::this_thread::sleep_for(std::chrono::seconds(60));
		std::printf("zsk0401: FAIL watchdog: case \"%s\" still running after 60 s\n", g_case.load());
		std::fflush(stdout);
		std::_Exit(3);
	}).detach();

	g_direct = memfd_create("zsk0401-direct", MFD_CLOEXEC);
	if (g_direct < 0 || ftruncate(g_direct, static_cast<off_t>(kFileSize)) != 0) {
		std::printf("zsk0401: FAIL no memfd for the direct memory\n");
		return 2;
	}
	if (on) { // the test's list, before the unit first reads the switch
		char cwd[4096] = {};
		if (getcwd(cwd, sizeof cwd) == nullptr) {
			std::printf("zsk0401: FAIL no current directory\n");
			return 2;
		}
		g_list_path = std::string(cwd) + "/zsk0401-list.txt";
		FILE* f     = std::fopen(g_list_path.c_str(), "w");
		if (f == nullptr || std::fputs(kList, f) < 0 || std::fclose(f) != 0) {
			std::printf("zsk0401: FAIL cannot write %s\n", g_list_path.c_str());
			return 2;
		}
		std::printf("zsk0401: BC5_DIRECT_ZERO_SKIP=%s, pointed at the test's list %s\n", e, g_list_path.c_str());
		::setenv("BC5_DIRECT_ZERO_SKIP", g_list_path.c_str(), 1);
	}

	Switch(on);
	ListRoundTrip(mode);
	ListParser(mode);
	Mask(mode);
	AllZero(mode);
	SkipSet(mode);
	if (on) {
		NoDevice();
		Placement();
		HintLearned();
		CpuWrite();
		CanaryHit();
		LateHit();
		Pieces(mode);
		Reopen();
	} else {
		OffNothing();
		OffSteps();
		Pieces(mode);
	}

	std::printf("zsk0401: %s %d of %d%s\n", mode, g_pass, g_total, g_pass == g_total ? "; end" : "");
	std::fflush(stdout);
	std::fflush(stderr);
	std::_Exit(g_pass == g_total ? 0 : 1); // the unit's canary watcher keeps running: no static destructors under it
}
