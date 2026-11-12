// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0415: CPU test of src/bc5/apr_posix.hpp (KYTY_BC5_APR_POSIX's read path), Linux only (the box's
// container). A file of 3 MiB + 123 bytes with a known pattern is read through read_to in both modes (staged, direct)
// and compared byte for byte with the pattern: aligned and unaligned offsets and lengths, a read that crosses the end
// of the file, one that starts at and one past the end, a chunk smaller than the read, a missing file and a
// directory. Then the case the fallback exists for: a destination the kernel refuses (pages mapped PROT_NONE that
// only the process's own SIGSEGV handler makes accessible, as the host's lazy pages are): the direct read must end
// with every byte in place, the refused part having gone through the staging copy, and the handler must have seen one
// fault per refused page. Ends with "test0415apr: <passed> of <run>; end".
// usage: test0415apr <scratch directory>
#include "bc5/apr_posix.hpp"

#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <sys/mman.h>

namespace ap = bc5::apr_posix;

static int g_run = 0, g_ok = 0;
static void check(bool v, const char* what) {
	g_run++;
	if (v) {
		g_ok++;
	} else {
		std::printf("FAIL: %s\n", what);
	}
}

static uint8_t pat(uint64_t i) {
	return static_cast<uint8_t>((i * 2654435761ull >> 13) ^ (i >> 3) ^ 0x5a);
}

static const uint64_t kFile = 3ull * 1024 * 1024 + 123;
static const uint64_t kPage = 4096;

static volatile sig_atomic_t g_faults    = 0;
static uint8_t*              g_region    = nullptr;
static uint64_t              g_region_sz = 0;

static void on_segv(int, siginfo_t* si, void*) {
	const auto a = reinterpret_cast<uint8_t*>(si->si_addr);
	if (g_region == nullptr || a < g_region || a >= g_region + g_region_sz) _exit(99); // not ours: a real crash
	g_faults = g_faults + 1;
	mprotect(g_region + (static_cast<uint64_t>(a - g_region) / kPage) * kPage, kPage, PROT_READ | PROT_WRITE);
}

static bool same(const uint8_t* got, uint64_t off, uint64_t n) {
	for (uint64_t i = 0; i < n; i++) {
		if (got[i] != pat(off + i)) return false;
	}
	return true;
}

int main(int argc, char** argv) {
	if (argc < 2) {
		std::printf("usage: test0415apr <scratch directory>\n");
		return 2;
	}
	const std::string dir  = argv[1];
	const std::string path = dir + "/test0415apr.bin";
	{
		std::vector<uint8_t> all(kFile);
		for (uint64_t i = 0; i < kFile; i++) all[i] = pat(i);
		FILE* f = std::fopen(path.c_str(), "wb");
		if (f == nullptr || std::fwrite(all.data(), 1, all.size(), f) != all.size() || std::fclose(f) != 0) {
			std::printf("cannot write %s\n", path.c_str());
			return 2;
		}
	}
	// open_for_read: what the file holds of a range.
	{
		uint64_t r  = 7;
		int      fd = ap::open_for_read(path.c_str(), 0, 100, &r);
		check(fd >= 0 && r == 100, "open: a range inside the file");
		if (fd >= 0) close(fd);
		fd = ap::open_for_read(path.c_str(), kFile - 10, 100, &r);
		check(fd >= 0 && r == 10, "open: a range that crosses the end");
		if (fd >= 0) close(fd);
		fd = ap::open_for_read(path.c_str(), kFile, 100, &r);
		check(fd >= 0 && r == 0, "open: a range that starts at the end");
		if (fd >= 0) close(fd);
		fd = ap::open_for_read(path.c_str(), kFile + 5000, 100, &r);
		check(fd >= 0 && r == 0, "open: a range past the end");
		if (fd >= 0) close(fd);
		fd = ap::open_for_read((dir + "/no-such-file").c_str(), 0, 100, &r);
		check(fd < 0 && r == 0, "open: a missing file");
		fd = ap::open_for_read(dir.c_str(), 0, 100, &r);
		check(fd < 0 && r == 0, "open: a directory is refused");
	}
	// read_to in both modes against the pattern.
	struct Case {
		uint64_t off, size, chunk, expect;
		const char* name;
	};
	const Case cases[] = {
	    {0, 4096, 4u << 20, 4096, "one page at 0"},
	    {12345, 70001, 4u << 20, 70001, "unaligned offset and length"},
	    {4096 * 3, 2u << 20, 8192, 2u << 20, "2 MiB in 8 KiB chunks"},
	    {1, kFile - 1, 4u << 20, kFile - 1, "the whole file but its first byte"},
	    {kFile - 5000, 9000, 4u << 20, 5000, "crossing the end: a short read"},
	    {kFile - 1, 1, 4u << 20, 1, "the last byte"},
	    {kFile - 4097, 8192, 1000, 4097, "an unaligned tail in 1000-byte chunks"},
	    {kFile, 4096, 4u << 20, 0, "at the end: nothing"},
	    {kFile + 99999, 4096, 4u << 20, 0, "past the end: nothing"},
	    {100, 0, 4u << 20, 0, "a size of 0"},
	};
	for (const bool direct: {false, true}) {
		for (const Case& c: cases) {
			std::vector<uint8_t> buf(static_cast<size_t>(c.size) + 64, 0xee);
			uint64_t             n = 99, staged = 99;
			const int            rc = ap::read_to(path.c_str(), c.off, c.size, buf.data() + 32, direct, c.chunk, &n, &staged);
			bool guard = true;
			for (int i = 0; i < 32; i++) guard = guard && buf[static_cast<size_t>(i)] == 0xee && buf[static_cast<size_t>(32 + c.expect + static_cast<uint64_t>(i))] == 0xee;
			const std::string what = std::string(direct ? "direct: " : "staged: ") + c.name;
			check(rc == 0 && n == c.expect && same(buf.data() + 32, c.off, n) && guard && staged == (direct ? 0 : c.expect), what.c_str());
		}
		uint64_t n = 99;
		uint8_t  one[8];
		check(ap::read_to((dir + "/no-such-file").c_str(), 0, 8, one, direct, 4096, &n) == -1 && n == 0, direct ? "direct: a missing file is -1" : "staged: a missing file is -1");
	}
	// The destination the kernel refuses.
	struct sigaction sa {};
	sa.sa_sigaction = on_segv;
	sa.sa_flags     = SA_SIGINFO;
	sigemptyset(&sa.sa_mask);
	sigaction(SIGSEGV, &sa, nullptr);
	g_region_sz = 8 * kPage;
	struct Refuse {
		uint64_t first_refused; // pages from here on are PROT_NONE
		bool     direct;
		const char* name;
	};
	const Refuse refuses[] = {
	    {3, true, "direct: pages 3-7 refused"},
	    {0, true, "direct: every page refused"},
	    {7, true, "direct: the last page refused"},
	    {3, false, "staged: pages 3-7 refused (the old path's behaviour)"},
	};
	for (const Refuse& r: refuses) {
		g_region = static_cast<uint8_t*>(mmap(nullptr, g_region_sz, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
		if (g_region == MAP_FAILED) {
			check(false, "mmap");
			break;
		}
		mprotect(g_region + r.first_refused * kPage, (8 - r.first_refused) * kPage, PROT_NONE);
		g_faults        = 0;
		uint64_t n = 0, staged = 0;
		const uint64_t off = 100; // unaligned in the file
		const int      rc  = ap::read_to(path.c_str(), off, g_region_sz, g_region, r.direct, 4u << 20, &n, &staged);
		const uint64_t refused = (8 - r.first_refused) * kPage;
		bool           ok      = rc == 0 && n == g_region_sz && same(g_region, off, n) && g_faults == static_cast<sig_atomic_t>(8 - r.first_refused);
		// direct: the kernel copies up to the first refused page (it may stop earlier), the rest is staged
		ok = ok && (r.direct ? (staged >= refused && staged <= g_region_sz) : staged == g_region_sz);
		check(ok, r.name);
		if (!ok) std::printf("  rc %d, read %llu, staged %llu, faults %d\n", rc, static_cast<unsigned long long>(n), static_cast<unsigned long long>(staged), static_cast<int>(g_faults));
		munmap(g_region, g_region_sz);
		g_region = nullptr;
	}
	// pread_all alone on a refused destination: a short count and the flag, no fault taken.
	{
		g_region = static_cast<uint8_t*>(mmap(nullptr, g_region_sz, PROT_NONE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
		uint64_t  readable = 0;
		const int fd       = ap::open_for_read(path.c_str(), 0, g_region_sz, &readable);
		bool      efault   = false;
		g_faults           = 0;
		const uint64_t n   = fd >= 0 && g_region != MAP_FAILED ? ap::pread_all(fd, g_region, readable, 0, 4u << 20, &efault) : 1;
		check(fd >= 0 && n == 0 && efault && g_faults == 0, "pread_all: a refused destination is a short count and the flag, without a fault");
		if (fd >= 0) close(fd);
		if (g_region != MAP_FAILED) munmap(g_region, g_region_sz);
		g_region = nullptr;
	}
	std::remove(path.c_str());
	std::printf("test0415apr: %d of %d; end\n", g_ok, g_run);
	return g_ok == g_run ? 0 : 1;
}
