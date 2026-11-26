#!/usr/bin/env python3
"""BC5 experiment 0412, tags bd412 and wc412 (PLAN-memory-wall.md step 3; README section 82).
  bd412  BC5_GUARD_BYDATA_NAMES=name[,name...] (default unset): option B's rule, one switch per heap. A heap named
         here is not imported whole even when BC5_DIRECT_EAGER_NAMES names it (bd0412.inc, bd0412.cpp). The log-only
         zero scan and the writers catcher keep reading it.
  wc412  BC5_GUARD_WRITERS=2: the writers catcher tells a CPU write from a GPU write by the soft-dirty bit
         (wc0412.inc, wc0412.cpp). =1 stays the catcher of tag ww412 with its lines unchanged.
Every anchor exactly once. Input: a main unit that carries tag ww412 (form 6, or candidate F's unit 59d17cf5).
usage: mkbd0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mkww0412  # the text of the function this script replaces

BD_GLUE = rb'''static const std::vector<std::string>& bd412_names() {
	static const std::vector<std::string> v = [] {
		auto n = bd412::parse(std::getenv("BC5_GUARD_BYDATA_NAMES"));
		for (const auto& s: n) std::fprintf(stderr, "[bc5] exp 0412 (tag bd412): BC5_GUARD_BYDATA_NAMES: the heap \"%s\" is imported by data, not whole\n", s.c_str());
		return n;
	}();
	return v;
}
static bool bd412_name(const char* name) {
	const auto& n = bd412_names();
	return !n.empty() && bd412::has(n, name);
}
'''

WC_GLUE = rb'''static std::map<std::string, std::vector<uint8_t>> g_ww_prev;      // tag ww412: each heap's flags at its last scan; only the scan thread, one scan at a time
static std::map<std::string, uint64_t>             g_ww_prev_base; // ... and its base then
static std::vector<wc412::MapLine>                 g_wc_maps;      // tag wc412: the direct file's mappings, read at this scan's start
static std::set<uint64_t>                          g_wc_before;    // slots (file offsets) that had a soft-dirty page before this scan's clear
static int                                         g_wc_pm = -1;   // /proc/self/pagemap
static int                                         g_wc_ok = 0;    // 0 not tried, 1 the soft-dirty bit works, -1 not available
static bool wc412_va_dirty(uint64_t va, uint64_t bytes) {
	const uint64_t        first = va / 4096, n = (va + bytes + 4095) / 4096 - first;
	std::vector<uint64_t> e(n);
	const ssize_t         r = pread(g_wc_pm, e.data(), n * 8, static_cast<off_t>(first * 8));
	return r > 0 && wc412::any_soft_dirty(e.data(), static_cast<size_t>(r) / 8);
}
static bool wc412_dirty(uint64_t off) { // a soft-dirty page at any address that maps the slot [off, off + kDChunk) of the direct file
	bool d = false;
	wc412::for_va(g_wc_maps, off, kDChunk, [&d](uint64_t va, uint64_t bytes) { d = d || wc412_va_dirty(va, bytes); });
	return d;
}
// At a scan's start, before the scan reads the file: the bits of every slot that was zero at the last scan, then the clear.
static void wc412_begin(int fd, uint32_t k) {
	if (wc412::level() < 2 || g_wc_ok < 0) return;
	const double t0 = timing_now();
	if (g_wc_pm < 0) g_wc_pm = open("/proc/self/pagemap", O_RDONLY | O_CLOEXEC);
	struct stat st {};
	std::string text;
	if (std::ifstream in("/proc/self/maps"); in) text.assign(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
	if (g_wc_pm >= 0 && fstat(fd, &st) == 0) g_wc_maps = wc412::parse_maps(text, major(st.st_dev), minor(st.st_dev), st.st_ino);
	else g_wc_maps.clear();
	static char* probe = static_cast<char*>(mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
	if (g_wc_maps.empty() || probe == MAP_FAILED) {
		g_wc_ok = -1;
		journal("writers (exp 0412, tag wc412): scan %u: the CPU/GPU split is NOT available (pagemap %d, %zu mappings of the direct file found in /proc/self/maps): the catcher goes on without it\n", k, g_wc_pm, g_wc_maps.size());
		return;
	}
	g_wc_before.clear();
	uint64_t looked = 0;
	if (g_wc_ok == 1) {
		for (const auto& [heap, flags]: g_ww_prev) {
			const uint64_t base = g_ww_prev_base[heap];
			for (size_t i = 0; i < flags.size(); i++) {
				if (flags[i] != 1) continue;
				looked++;
				const uint64_t off = base + static_cast<uint64_t>(i) * kDChunk;
				if (wc412_dirty(off)) g_wc_before.insert(off);
			}
		}
	}
	probe[0]         = 1; // the page exists
	const double t1  = timing_now();
	bool         ok  = false;
	if (const int f = open("/proc/self/clear_refs", O_WRONLY | O_CLOEXEC); f >= 0) {
		ok = write(f, "4", 1) == 1;
		close(f);
	}
	const double t2      = timing_now();
	const bool   cleared = ok && !wc412_va_dirty(reinterpret_cast<uint64_t>(probe), 4096);
	probe[0]             = 2;
	const bool set_again = wc412_va_dirty(reinterpret_cast<uint64_t>(probe), 4096);
	if (!cleared || !set_again) {
		g_wc_ok = -1;
		journal("writers (exp 0412, tag wc412): scan %u: the CPU/GPU split is NOT available: the soft-dirty bit does not work here (clear_refs written %d, the probe page clean after the clear %d, dirty after a write %d); the catcher goes on without it\n",
		        k, ok ? 1 : 0, cleared ? 1 : 0, set_again ? 1 : 0);
		return;
	}
	g_wc_ok = 1;
	journal("writers (exp 0412, tag wc412): scan %u: soft-dirty: %zu mappings of the direct file; %" PRIu64 " slots that were zero at the last scan looked at, %zu of them written by the CPU since the last clear; cleared for the whole process in %.1f ms (%.1f ms in all)\n",
	        k, g_wc_maps.size(), looked, g_wc_before.size(), (t2 - t1) * 1000.0, (timing_now() - t0) * 1000.0);
}
// The zero scan's hook (its background thread): one heap's flags of this scan against the last scan's.
static void ww412_scan(const std::string& heap, uint64_t base, const std::vector<uint8_t>& now, uint32_t k) {
	if (!ww412::on()) return;
	auto&          p = g_ww_prev[heap];
	ww412::Turned  t;
	size_t         named_all = 0;
	const bool     compared  = p.size() == now.size() && g_ww_prev_base[heap] == base;
	const bool     split     = compared && wc412::level() >= 2 && g_wc_ok == 1; // tag wc412
	{
		std::lock_guard lk(g_ww_mutex);
		named_all = g_ww_named.size();
		if (compared) t = ww412::classify(p, now, base, kDChunk, split ? now.size() : 8, [](uint64_t g) { return g_ww_named.count(g) != 0; });
	}
	if (compared) {
		uint64_t cpu = 0, gpu = 0, lines = 0;
		for (const uint64_t c: t.unnamed) {
			const bool by_cpu = split && (g_wc_before.count(c) != 0 || wc412_dirty(c));
			if (split) (by_cpu ? cpu : gpu)++;
			if (lines >= (split && !by_cpu ? 64u : 8u)) continue; // a chunk with no CPU write is the finding: up to 64 of them are written
			lines++;
			journal("writers (exp 0412, tag ww412): scan %u: %s: the chunk at file offset 0x%" PRIx64 " was all zero at the last scan and holds data now; no hint, force or packet operand named it%s\n", k, heap.c_str(), c,
			        !split ? "" : by_cpu ? "; the CPU wrote it (soft-dirty)" : "; NO CPU write since the last scan: a GPU writer nobody named");
		}
		journal("writers (exp 0412, tag ww412): scan %u: %s: %" PRIu64 " chunks (%" PRIu64 " MiB) turned non-zero since the last scan: %" PRIu64 " named by a hint, force or packet operand, %" PRIu64
		        " NOT named (upper bound of unknown GPU writers: a CPU write and a chunk that left its view count here too); %zu chunks named so far in all heaps\n",
		        k, heap.c_str(), t.turned, t.turned * (kDChunk >> 20u), t.named, t.turned - t.named, named_all);
		if (split) {
			journal("writers (exp 0412, tag wc412): scan %u: %s: of the %" PRIu64 " NOT named: %" PRIu64 " written by the CPU (soft-dirty; a GPU write as well is not excluded), %" PRIu64 " with NO CPU write (GPU writers nobody named)\n",
			        k, heap.c_str(), t.turned - t.named, cpu, gpu);
		}
	} else {
		journal("writers (exp 0412, tag ww412): scan %u: %s: first scan of this span (%zu slots): nothing to compare yet\n", k, heap.c_str(), now.size());
	}
	p                    = now;
	g_ww_prev_base[heap] = base;
}
'''


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def body_of(name, ns):
    inc = open(os.path.join(HERE, name), "rb").read()
    assert b"\r" not in inc
    body = inc[inc.index(b"namespace " + ns + b" {"):]
    assert body.rstrip().endswith(b"} // namespace " + ns) and b"#include" not in body
    return body


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag ww412" in s and b"tag bd412" not in s and b"tag wc412" not in s, "refused: not a unit with ww412, or already edited"
    BD_GLUE.decode("ascii")
    WC_GLUE.decode("ascii")
    # bd412: the list, before the eager names' reader; the reader obeys it
    a = b"// BC5_DIRECT_EAGER_NAMES=name[,name...]: views with these names are imported in full as soon as\n"
    s = once(s, a, b"// Experiment 0412 (tag bd412): bd0412.inc, BC5_GUARD_BYDATA_NAMES, option B's rule per heap.\n" + body_of("bd0412.inc", b"bd412") + BD_GLUE + a)
    a = (b"\tif (name == nullptr || names.empty()) return false;\n\treturn std::find(names.begin(), names.end(), name) != names.end();\n}\n\n"
         b"// Experiment 0415 (ls415d), KYTY_BC5_NAMES_FAST")
    s = once(s, a, b"\tif (bd412_name(name)) return false; // exp 0412 (tag bd412): this heap is imported by data\n" + a)
    a = b'e != nullptr && S.kind == 0) journal("direct memory: eager names: %s\\n", e);\n'
    s = once(s, a, a + b'\t\tif (const char* e = std::getenv("BC5_GUARD_BYDATA_NAMES"); e != nullptr && e[0] != 0 && S.kind == 0) journal("direct memory (exp 0412, tag bd412): by data, not whole, though eager by name: %s\\n", e);\n')
    # the zero scan and the catcher keep reading a heap that bd412 took out of the eager class
    a = b"\t\tif (!v.eager || v.name != name) continue;\n"
    s = once(s, a, b"\t\tif (!(v.eager || bd412_name(v.name.c_str())) || v.name != name) continue; // exp 0412 (tag bd412)\n")
    a = b"\t\t\tif (v.eager && v.name == name) h.ranges.emplace_back(v.off, v.off + v.size);\n"
    s = once(s, a, b"\t\t\tif ((v.eager || bd412_name(v.name.c_str())) && v.name == name) h.ranges.emplace_back(v.off, v.off + v.size); // exp 0412 (tag bd412)\n")
    # wc412: the catcher's scan function is replaced; its body and glue come before the catcher's own glue
    old = mkww0412.GLUE_A[mkww0412.GLUE_A.index(b"// The zero scan's hook"):]
    assert old.startswith(b"// The zero scan's hook") and old.rstrip().endswith(b"}")
    s = once(s, old, b"")
    a = b"static std::mutex         g_ww_mutex;\n"
    s = once(s, a, b"// Experiment 0412 (tag wc412): wc0412.inc, BC5_GUARD_WRITERS=2, the CPU/GPU split by the soft-dirty bit.\n#include <sys/sysmacros.h> // major, minor\n" + body_of("wc0412.inc", b"wc412") + a)
    a = b"// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) ---------------\n"
    s = once(s, a, WC_GLUE + a)
    a = b"static void zscan_run(int fd, std::vector<ZScanHeap> heaps, double t_start, uint32_t k) {\n\tsetpriority(PRIO_PROCESS, static_cast<id_t>(syscall(SYS_gettid)), 19);\n"
    s = once(s, a, a + b"\twc412_begin(fd, k); // exp 0412 (tag wc412)\n")
    # order: everything the glue uses is defined before it
    g = s.index(b"static void wc412_begin(")
    for need in (b"static void journal(const char* fmt, ...) {", b"static double timing_now() {", b"constexpr uint64_t kDChunk", b"static std::set<uint64_t> g_ww_named;", b"namespace wc412 {", b"namespace ww412 {"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    assert s.index(b"static bool bd412_name(") < s.index(b"static bool direct_eager_name(") < s.index(b"static void zscan_run(")
    assert g < s.index(b"static void ww412_scan(") < s.index(b"static void zscan_run(")
    for inc in (b"#include <fstream>", b"#include <sys/mman.h>", b"#include <sys/stat.h>", b"#include <fcntl.h>", b"#include <set>", b"#include <iterator>"):
        assert s.index(inc) < g, ("header missing before the glue", inc)
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
