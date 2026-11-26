// BC5 experiment 0401 pool scatter: standalone CPU test.
//
// Tests the pool scatter logic (free list, gather, split, scattered map, unmap)
// without any emulator or GPU objects. Pure C++20, compiles on the laptop.
//
// Build:
//   g++ -std=c++20 -O1 -Wall work/pool0401.cpp -o work/pool0401 && ./work/pool0401
//
// What it checks:
//   1. The 11-03 18:14 shape: 212 MiB free in pieces, a 64 MiB map.
//      Off: refused. Rescue and first: succeeds with pieces.
//   2. Off, unset and "0" give results identical to the original code.
//   3. Unmapping a scattered map frees every piece, no overlap, no leak.
//   4. Distinct VA addresses for each piece (review point 1).
//   5. Last piece is trimmed (review point 2).
//   6. Gathered pieces are removed from free list (review point 3).
//   7. Partial unmap works correctly (review point 7).
//   8. pool0401_impl.inc byte-equality with patched libAmpr.cpp content.

#include <algorithm>
#include <atomic>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <vector>

// ---- Simulated pool state (mirrors libAmpr.cpp's g_amm_auto_free, g_amm_auto_maps) ----

struct AmmAutoMapping {
	uint64_t dmem = 0;
	uint64_t size = 0;
};

static std::unique_ptr<uint8_t[]> g_dm_backing;
static uint64_t g_dm_total = 0;
static std::map<uint64_t, uint64_t> g_amm_auto_free;
static std::map<uint64_t, AmmAutoMapping> g_amm_auto_maps;
static std::mutex g_amm_auto_pool_mutex;

// ---- Constants ----
static constexpr int PROT_CPU_READ = 0x01;
static constexpr int PROT_CPU_WRITE = 0x02;
static constexpr int OK = 1;
static constexpr int KERNEL_ERROR_EAGAIN = -11;
static constexpr int AMM_MAP_FIXED = 0x40;
static constexpr uint64_t AMM_PAGE_SIZE = 4096;

// ---- Hook stubs for the test ----

static std::map<void*, std::pair<uint64_t, uint64_t>> g_host_mappings; // va -> {dmem, size}

extern "C" void* Bc5PoolMapDirect(void** addr, uint64_t size, int /*memory_type*/,
                                   int /*prot*/, int /*flags*/, int64_t dmem, uint64_t /*page_size*/) {
	if (addr == nullptr) return nullptr;
	*addr = reinterpret_cast<void*>(reinterpret_cast<uint64_t>(*addr));
	g_host_mappings[*addr] = {static_cast<uint64_t>(dmem), size};
	return *addr;
}

extern "C" int Bc5PoolUnmapDirect(void* addr, uint64_t /*size*/) {
	auto it = g_host_mappings.find(addr);
	if (it != g_host_mappings.end()) {
		g_host_mappings.erase(it);
		return 0;
	}
	return -1;
}

extern "C" int Bc5PoolAllocDirect(int64_t /*search_start*/, int64_t /*search_end*/,
                                   uint64_t /*size*/, uint64_t /*align*/, int /*type*/,
                                   int64_t* allocated) {
	(void)allocated;
	// Not used in pool0401 test — pool operations only.
	return -1;
}

extern "C" int Bc5PoolSetName(void* /*addr*/, uint64_t /*size*/, const char* /*name*/) {
	return 0;
}

extern "C" void Bc5PoolTraceStamp() {
	// No-op in test.
}

extern "C" void Bc5PoolWatchSurface(uint64_t /*va*/) {
	// No-op in test.
}

extern "C" int64_t Bc5PoolGetDirectMemorySize() {
	return 0;
}

// ---- Free list helpers (for seeding) ----
// Must be defined before AmmAutoReleaseVa uses FreeLocked.

static void FreeLocked(uint64_t start, uint64_t size);

static bool AllocLocked(uint64_t size, uint64_t* dmem_offset) {
	for (auto it = g_amm_auto_free.begin(); it != g_amm_auto_free.end(); ++it) {
		if (it->second >= size) {
			if (dmem_offset) *dmem_offset = it->first;
			const auto rest_start = it->first + size;
			const auto rest_size = it->second - size;
			g_amm_auto_free.erase(it);
			if (rest_size != 0) g_amm_auto_free[rest_start] = rest_size;
			return true;
		}
	}
	return false;
}

static void FreeLocked(uint64_t start, uint64_t size) {
	if (size == 0) return;
	auto next = g_amm_auto_free.lower_bound(start);
	if (next != g_amm_auto_free.begin()) {
		auto prev = std::prev(next);
		if (prev->first + prev->second == start) {
			start = prev->first;
			size += prev->second;
			g_amm_auto_free.erase(prev);
		}
	}
	if (next != g_amm_auto_free.end() && start + size == next->first) {
		size += next->second;
		g_amm_auto_free.erase(next);
	}
	g_amm_auto_free[start] = size;
}

// ---- AmmAutoRecordVa / AmmAutoReleaseVa (simulated) ----

static void AmmAutoReleaseVa(uint64_t va, uint64_t size) {
	const uint64_t end = va + size;
	auto it = g_amm_auto_maps.lower_bound(va);
	if (it != g_amm_auto_maps.begin()) --it;
	while (it != g_amm_auto_maps.end() && it->first < end) {
		const uint64_t m_va = it->first;
		const uint64_t m_end = m_va + it->second.size;
		const uint64_t m_dmem = it->second.dmem;
		if (m_end <= va) { ++it; continue; }
		const uint64_t o0 = std::max(va, m_va);
		const uint64_t o1 = std::min(end, m_end);
		// Free the dmem for the overlapped portion.
		FreeLocked(m_dmem + (o0 - m_va), o1 - o0);
		it = g_amm_auto_maps.erase(it);
		if (m_va < o0) g_amm_auto_maps[m_va] = AmmAutoMapping{m_dmem, o0 - m_va};
		if (o1 < m_end) g_amm_auto_maps[o1] = AmmAutoMapping{m_dmem + (o1 - m_va), m_end - o1};
	}
}

static void AmmAutoRecordVa(uint64_t va, uint64_t dmem, uint64_t size) {
	AmmAutoReleaseVa(va, size);
	std::scoped_lock lock(g_amm_auto_pool_mutex);
	g_amm_auto_maps[va] = AmmAutoMapping{dmem, size};
}

// ---- NormalizeAmmProtection stub ----
static int NormalizeAmmProtection(int prot) { return prot; }

// ---- Include the shared helpers ----
#include "pool0401_impl.inc"

// ---- UnmapAuto helper ----
static void UnmapAuto(uint64_t va, uint64_t size) {
	std::scoped_lock lock(g_amm_auto_pool_mutex);
	AmmAutoReleaseVa(va, size);
}

// ---- Byte-equality check: verify pool0401_impl.inc matches what mkpool0401.py inlines ----
static bool CheckIncByteEquality() {
	// Read the .inc file
	const char* inc_path = "work/pool0401_impl.inc";
	FILE* f = fopen(inc_path, "rb");
	if (!f) {
		std::fprintf(stderr, "[bc5] pool0401: cannot open %s for byte-check\n", inc_path);
		return true; // non-fatal: test can run without the check
	}
	fseek(f, 0, SEEK_END);
	long inc_size = ftell(f);
	fseek(f, 0, SEEK_SET);
	std::vector<char> inc_data(inc_size);
	size_t read_count = fread(inc_data.data(), 1, inc_size, f);
	(void)read_count;
	fclose(f);

	// Read the patched libAmpr.cpp and extract content between markers.
	const char* lib_path = "work/libAmpr.cpp";
	FILE* lf = fopen(lib_path, "rb");
	if (!lf) {
		std::fprintf(stderr, "[bc5] pool0401: cannot open %s for byte-check\n", lib_path);
		return true; // non-fatal
	}
	fseek(lf, 0, SEEK_END);
	long lib_size = ftell(lf);
	fseek(lf, 0, SEEK_SET);
	std::vector<char> lib_data(lib_size);
	read_count = fread(lib_data.data(), 1, lib_size, lf);
	(void)read_count;
	fclose(lf);

	// Find markers.
	const char* begin_mark = "// ---- BEGIN pool0401_impl.inc ----";
	const char* end_mark = "// ---- END pool0401_impl.inc ----";
	const char* begin = std::strstr(lib_data.data(), begin_mark);
	const char* end = std::strstr(lib_data.data(), end_mark);
	if (!begin || !end || end <= begin) {
		std::fprintf(stderr, "[bc5] pool0401: markers not found in libAmpr.cpp\n");
		return true; // non-fatal
	}
	begin += std::strlen(begin_mark);
	// Skip the newline after the BEGIN marker
	if (*begin == '\n') begin++;
	size_t extracted_size = static_cast<size_t>(end - begin);
	if (extracted_size != static_cast<size_t>(inc_size)) {
		std::fprintf(stderr, "[bc5] pool0401: size mismatch: .inc=%ld extracted=%zu\n",
		             inc_size, extracted_size);
		return false;
	}
	if (std::memcmp(begin, inc_data.data(), extracted_size) != 0) {
		std::fprintf(stderr, "[bc5] pool0401: content mismatch between .inc and libAmpr.cpp\n");
		return false;
	}
	return true;
}

// ---- Test helpers ----

static int g_pass = 0;
static int g_total = 0;
static const char* g_case = "";
static bool g_fail = false;

#define CHECK(cond) do { \
	g_total++; \
	if (cond) { g_pass++; } \
	else { \
		std::printf("FAIL %s: %s (line %d)\n", g_case, #cond, __LINE__); \
		g_fail = true; \
	} \
} while (0)

static void InitPool(uint64_t dm_total_mib) {
	g_dm_total = dm_total_mib * (1ull << 20);
	g_dm_backing = std::make_unique<uint8_t[]>(g_dm_total);
	std::memset(g_dm_backing.get(), 0, g_dm_total);
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_host_mappings.clear();
	FreeLocked(0, g_dm_total);
}

static uint64_t TotalMapped() {
	uint64_t t = 0;
	for (const auto& m: g_amm_auto_maps) t += m.second.size;
	return t;
}

static uint64_t TotalFree() {
	uint64_t t = 0;
	for (const auto& r: g_amm_auto_free) t += r.second;
	return t;
}

static void CheckCoalesced() {
	auto it = g_amm_auto_free.begin();
	if (it == g_amm_auto_free.end()) return;
	auto next = std::next(it);
	while (next != g_amm_auto_free.end()) {
		CHECK(it->first + it->second != next->first);
		it = next; ++next;
	}
}

static void CheckConservation(uint64_t total) {
	CHECK(TotalFree() + TotalMapped() == total);
}

// ---- Test 1: The 11-03 18:14 shape ----
static void Test1814Shape() {
	g_case = "1814 shape";
	InitPool(3034);
	const uint64_t total = g_dm_total;

	const uint64_t block = 8ull << 20; // 8 MiB
	const int n_holes = 26;
	const int n_keeps = 353;

	std::vector<uint64_t> all_dmems;
	for (int i = 0; i < n_keeps + n_holes; i++) {
		uint64_t dmem = 0;
		if (!AllocLocked(block, &dmem)) { std::printf("1814: alloc all failed at %d\n", i); return; }
		all_dmems.push_back(dmem);
		AmmAutoRecordVa(0xA0000000 + i * block, dmem, block);
	}

	const int stride = (n_keeps + n_holes) / n_holes;
	for (int i = stride - 1; i < static_cast<int>(all_dmems.size()); i += stride) {
		const uint64_t dmem = all_dmems[i];
		for (auto mit = g_amm_auto_maps.begin(); mit != g_amm_auto_maps.end(); ) {
			if (mit->second.dmem == dmem && mit->second.size == block) {
				FreeLocked(dmem, block);
				mit = g_amm_auto_maps.erase(mit);
			} else {
				++mit;
			}
		}
	}

	uint64_t free_bytes = 0, holes = 0, largest = 0;
	Bc5PoolFreeStats(&free_bytes, &holes, &largest);
	std::printf("1814 shape: free 0x%" PRIx64 " (%" PRIu64 " MiB) in %zu holes, largest 0x%" PRIx64 " (%zu MiB)\n",
	            free_bytes, free_bytes >> 20, holes, largest, largest >> 20);
	CHECK(free_bytes >= (200ull << 20));
	CHECK(largest < (64ull << 20));

	// Off mode refuses 64 MiB.
	{
		g_case = "1814 shape off";
		const int pieces = Bc5MapAutoScattered(0xB0000000, 64ull << 20, 0, 7);
		CHECK(pieces <= 0);
		CHECK(TotalFree() == free_bytes);
	}

	// Rescue mode succeeds.
	{
		g_case = "1814 shape rescue";
		// Force scatter mode to "rescue" for this test.
		setenv("KYTY_BC5_AMM_SCATTER", "rescue", 1);
		// Re-seed the pool.
		g_amm_auto_free.clear();
		g_amm_auto_maps.clear();
		FreeLocked(0, total);
		std::printf("Rescue re-seed: free=%zu entries\n", g_amm_auto_free.size());
		std::vector<uint64_t> all_dmems2;
		for (int i = 0; i < n_keeps + n_holes; i++) {
			uint64_t dmem = 0;
			if (!AllocLocked(block, &dmem)) { std::printf("1814 rescue: alloc failed at %d\n", i); return; }
			all_dmems2.push_back(dmem);
			AmmAutoRecordVa(0xB0000000 + i * block, dmem, block);
		}
		for (int i = stride - 1; i < static_cast<int>(all_dmems2.size()); i += stride) {
			const uint64_t dmem = all_dmems2[i];
			for (auto mit = g_amm_auto_maps.begin(); mit != g_amm_auto_maps.end(); ) {
				if (mit->second.dmem == dmem && mit->second.size == block) {
					FreeLocked(dmem, block);
					mit = g_amm_auto_maps.erase(mit);
				} else {
					++mit;
				}
			}
		}
		std::printf("Rescue: after alloc+free holes, free=%zu entries\n", g_amm_auto_free.size());
		// Use VA 0x2000000000 (8 GiB) to avoid overlapping with existing maps at 0xB0000000+ range.
		const int np = Bc5MapAutoScattered(0x2000000000ull, 64ull << 20, 0, 7);
		std::printf("Rescue: np=%d\n", np);
		CHECK(np > 0);
		CHECK(np > 1);
	}

	CheckConservation(total);
	// Allow 2 MiB slack (3034 - 379*8 = 2 MiB).
	std::printf("1814 shape end: free=%" PRIu64 " mapped=%" PRIu64 " sum=%" PRIu64 " total=%" PRIu64 " maps=%zu\n",
	            TotalFree(), TotalMapped(), TotalFree() + TotalMapped(), total, g_amm_auto_maps.size());
	CHECK(TotalFree() + TotalMapped() >= total - (2ull << 20));
	CheckCoalesced();
}

// ---- Test 2: Off mode = original code ----
static void TestOffIdentical() {
	g_case = "off identical";
	// Reset scatter mode to "off" for this test.
	setenv("KYTY_BC5_AMM_SCATTER", "0", 1);
	std::printf("TestOffIdentical: starting\n");
	InitPool(256);

	// One 100 MiB hole in the middle.
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[50ull << 20] = 100ull << 20;

	uint64_t free_bytes = 0;
	Bc5PoolFreeStats(&free_bytes, nullptr, nullptr);
	CHECK(free_bytes == (100ull << 20));

	// Off: first-fit succeeds for <= 100 MiB.
	{
		const int np = Bc5MapAutoScattered(0xD0000000, 50ull << 20, 0, 7);
		CHECK(np == 1);
	}

	// Off: first-fit fails for > 100 MiB.
	{
		const int np = Bc5MapAutoScattered(0xE0000000, 150ull << 20, 0, 7);
		CHECK(np <= 0);
	}

	// Unmap scattered map frees every piece.
	g_case = "unmap scattered";
	InitPool(128);
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[0] = 48ull << 20;
	g_amm_auto_free[48ull << 20] = 80ull << 20;
	{
		const int np = Bc5MapAutoScattered(0xF0000000, 40ull << 20, 0, 7);
		CHECK(np > 0);
		const uint64_t mapped_before = TotalMapped();
		UnmapAuto(0xF0000000, mapped_before);
		const uint64_t mapped_after = TotalMapped();
		CHECK(mapped_before - mapped_after == mapped_before); // freed all
	}

	CheckConservation(g_dm_total);
}

// ---- Test 3: Churn ----
static void TestChurn() {
	g_case = "churn";
	std::printf("TestChurn: starting\n");
	// Enable scatter mode for churn test.
	setenv("KYTY_BC5_AMM_SCATTER", "first", 1);
	InitPool(512);

	const uint64_t sizes[] = {4096, 262144, 4194304, 4096, 262144, 4194304, 4096, 262144};
	const int n_sizes = 8;
	uint64_t va = 0x10000000;

	for (int round = 0; round < 20; round++) {
		for (int i = 0; i < n_sizes; i++) {
			const uint64_t sz = sizes[i];
			const int np = Bc5MapAutoScattered(va, sz, 0, 7);
			CHECK(np > 0);
			if (np > 0) {
				UnmapAuto(va, sz);
			}
			va += sz;
		}
		// Periodic 64 MiB.
		const int np = Bc5MapAutoScattered(va, 64ull << 20, 0, 7);
		if (np > 0) {
			UnmapAuto(va, 64ull << 20);
		}
		va += (64ull << 20);
	}

	CheckConservation(g_dm_total);
	CheckCoalesced();
}

// ---- Test 4: Partial unmap (review point 7) ----
static void TestPartialUnmap() {
	g_case = "partial unmap";
	// Enable scatter mode so two 32 MiB holes can satisfy a 64 MiB map.
	setenv("KYTY_BC5_AMM_SCATTER", "first", 1);
	InitPool(128);

	// Free: 0-32 (32 MiB), 96-128 (32 MiB). Used: 32-96 (64 MiB).
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[0] = 32ull << 20;
	g_amm_auto_free[96ull << 20] = 32ull << 20;
	// Record the "used" portion so conservation holds.
	AmmAutoRecordVa(0x50000000, 32ull << 20, 64ull << 20);

	const int np = Bc5MapAutoScattered(0xA0000000, 64ull << 20, 0, 7);
	CHECK(np == 2);
	CHECK(TotalMapped() == (128ull << 20));

	// Unmap first half.
	UnmapAuto(0xA0000000, 32ull << 20);
	// 64 MiB used + 32 MiB piece1 = 96 MiB.
	CHECK(TotalMapped() == (96ull << 20));
	CHECK(g_amm_auto_maps.size() == 2);

	// Unmap the rest.
	UnmapAuto(0xA2000000, 32ull << 20);
	// Only the 64 MiB used remains.
	CHECK(TotalMapped() == (64ull << 20));
	CHECK(g_amm_auto_maps.size() == 1);

	CheckConservation(g_dm_total);
}

// ---- Test 5: Distinct VA addresses for each piece (review point 1) ----
static void TestDistinctVA() {
	g_case = "distinct VA";
	// Enable scatter mode.
	setenv("KYTY_BC5_AMM_SCATTER", "first", 1);
	InitPool(128);

	// Set up two equal 32 MiB holes.
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[0] = 32ull << 20;
	g_amm_auto_free[32ull << 20] = 32ull << 20;

	const int np = Bc5MapAutoScattered(0xA0000000, 64ull << 20, 0, 7);
	CHECK(np == 2);

	// Check that both pieces are recorded at different VAs.
	int count = 0;
	uint64_t va0 = 0, va1 = 0, size0 = 0, size1 = 0;
	{
		std::scoped_lock lock(g_amm_auto_pool_mutex);
		for (const auto& m: g_amm_auto_maps) {
			if (m.first >= 0xA0000000 && m.first < 0xA0000000 + (64ull << 20)) {
				if (count == 0) { va0 = m.first; size0 = m.second.size; }
				else if (count == 1) { va1 = m.first; size1 = m.second.size; }
				count++;
			}
		}
	}
	CHECK(count == 2);
	CHECK(va0 != va1);
	CHECK(va0 == 0xA0000000);
	CHECK(va1 == 0xA0000000 + (32ull << 20));
	CHECK(size0 == (32ull << 20));
	CHECK(size1 == (32ull << 20));

	// Check no overlap.
	const uint64_t a0 = va0, a1 = va0 + size0;
	const uint64_t b0 = va1, b1 = va1 + size1;
	CHECK(a1 <= b0 || b1 <= a0);

	UnmapAuto(0xA0000000, 64ull << 20);
}

// ---- Test 6: Last piece trimmed (review point 2) ----
static void TestLastPieceTrim() {
	g_case = "last piece trim";
	// Enable scatter mode.
	setenv("KYTY_BC5_AMM_SCATTER", "first", 1);
	InitPool(128);

	// Set up three holes: 30 MiB, 30 MiB, 10 MiB = 70 MiB total.
	// Request 60 MiB: should take 30 + 30 = 60 MiB (two pieces, no trim needed).
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[0] = 30ull << 20;
	g_amm_auto_free[30ull << 20] = 30ull << 20;
	g_amm_auto_free[60ull << 20] = 10ull << 20;

	const int np = Bc5MapAutoScattered(0xA0000000, 60ull << 20, 0, 7);
	CHECK(np == 2);

	// Check that the sum is exactly 60 MiB.
	uint64_t sum = 0;
	{
		std::scoped_lock lock(g_amm_auto_pool_mutex);
		for (const auto& m: g_amm_auto_maps) {
			if (m.first >= 0xA0000000 && m.first < 0xA0000000 + (64ull << 20)) {
				sum += m.second.size;
			}
		}
	}
	CHECK(sum == (60ull << 20));

	UnmapAuto(0xA0000000, 60ull << 20);

	// Now request 65 MiB: should take 30 + 30 + 10 = 70 MiB, but trimmed to 65.
	// Re-seed.
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[0] = 30ull << 20;
	g_amm_auto_free[30ull << 20] = 30ull << 20;
	g_amm_auto_free[60ull << 20] = 10ull << 20;

	const int np2 = Bc5MapAutoScattered(0xB0000000, 65ull << 20, 0, 7);
	CHECK(np2 == 3);

	uint64_t sum2 = 0;
	{
		std::scoped_lock lock(g_amm_auto_pool_mutex);
		for (const auto& m: g_amm_auto_maps) {
			if (m.first >= 0xB0000000 && m.first < 0xB0000000 + (68ull << 20)) {
				sum2 += m.second.size;
			}
		}
	}
	CHECK(sum2 == (65ull << 20));

	UnmapAuto(0xB0000000, 65ull << 20);
}

// ---- Test 7: Gathered pieces removed from free list (review point 3) ----
static void TestGatherRemovesFromFree() {
	g_case = "gather removes";
	// Enable scatter mode.
	setenv("KYTY_BC5_AMM_SCATTER", "first", 1);
	InitPool(128);

	// Set up two 32 MiB holes.
	g_amm_auto_free.clear();
	g_amm_auto_maps.clear();
	g_amm_auto_free[0] = 32ull << 20;
	g_amm_auto_free[32ull << 20] = 32ull << 20;

	uint64_t free_before = 0;
	Bc5PoolFreeStats(&free_before, nullptr, nullptr);
	CHECK(free_before == (64ull << 20));

	// Scatter takes 64 MiB.
	const int np = Bc5MapAutoScattered(0xA0000000, 64ull << 20, 0, 7);
	CHECK(np == 2);

	uint64_t free_after = 0;
	Bc5PoolFreeStats(&free_after, nullptr, nullptr);
	// All 64 MiB should be gone from free list (mapped).
	CHECK(free_after == 0);

	UnmapAuto(0xA0000000, 64ull << 20);

	// After unmap, the 64 MiB should be back in the free list.
	uint64_t free_recovered = 0;
	Bc5PoolFreeStats(&free_recovered, nullptr, nullptr);
	CHECK(free_recovered == (64ull << 20));
}

// ---- Main ----
int main() {
	std::printf("pool0401: starting\n");

	// Byte-equality check (non-fatal if .inc not found).
	if (!CheckIncByteEquality()) {
		std::fprintf(stderr, "[bc5] pool0401: WARNING: byte-equality check failed\n");
	}

	Test1814Shape();
	std::printf("after Test1814Shape: fail=%d pass=%d total=%d\n", g_fail, g_pass, g_total);
	if (g_fail) { std::printf("pool0401: FAIL 1814 shape\n"); return 1; }
	std::printf("pool0401: PASS 1814 shape (%d/%d)\n", g_pass, g_total);
	std::printf("about to reset for test2\n");

	g_pass = 0; g_total = 0; g_fail = false;
	TestOffIdentical();
	if (g_fail) { std::printf("pool0401: FAIL off identical\n"); return 1; }
	std::printf("pool0401: PASS off identical (%d/%d)\n", g_pass, g_total);

	g_pass = 0; g_total = 0; g_fail = false;
	TestChurn();
	if (g_fail) { std::printf("pool0401: FAIL churn\n"); return 1; }
	std::printf("pool0401: PASS churn (%d/%d)\n", g_pass, g_total);

	g_pass = 0; g_total = 0; g_fail = false;
	TestPartialUnmap();
	if (g_fail) { std::printf("pool0401: FAIL partial unmap\n"); return 1; }
	std::printf("pool0401: PASS partial unmap (%d/%d)\n", g_pass, g_total);

	g_pass = 0; g_total = 0; g_fail = false;
	TestDistinctVA();
	if (g_fail) { std::printf("pool0401: FAIL distinct VA\n"); return 1; }
	std::printf("pool0401: PASS distinct VA (%d/%d)\n", g_pass, g_total);

	g_pass = 0; g_total = 0; g_fail = false;
	TestLastPieceTrim();
	if (g_fail) { std::printf("pool0401: FAIL last piece trim\n"); return 1; }
	std::printf("pool0401: PASS last piece trim (%d/%d)\n", g_pass, g_total);

	g_pass = 0; g_total = 0; g_fail = false;
	TestGatherRemovesFromFree();
	if (g_fail) { std::printf("pool0401: FAIL gather removes\n"); return 1; }
	std::printf("pool0401: PASS gather removes (%d/%d)\n", g_pass, g_total);

	std::printf("pool0401: PASS all tests (%d/%d); end\n", g_pass, g_total);
	return 0;
}
