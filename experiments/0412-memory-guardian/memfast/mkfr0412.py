#!/usr/bin/env python3
"""BC5 experiment 0412, tag fr412 (README section 64; the maintainer's rule of 2026-11-13: a GPU fault is a bug to
remove at its source, not something the game is to get up from): the FAULT RECORD.
BC5_FAULT_RECORD=1 (default off in the test build; meant to become the default): at the first GPU fault or ring
timeout the emulator writes one self-contained record for us under ~/bc5-data/captures/faults/<date-time>/ and ENDS
the game (exit code 86, one stderr line naming the record) instead of reopening the device and going on. Nothing in
the record is read by a later run.
  record.txt        what happened, in words: time, the fault's address and status (read or write), the catcher's
                    classification (the kind, the view or heap, by data / lazy / eager, the chunk imported or not, a
                    GPU mapping or not, under a view at all), the pin, counts of views, buffers and mappings, the
                    capture directory with the journal and the dumped buffers of the timed-out jobs, and what is NOT
                    in it (the kernel's own lines: the launcher adds them, the emulator cannot read dmesg)
  journal-tail.txt  the last 4 MiB of the journal: the probe's summary of the timed-out jobs, the last submissions,
                    the ledger (pinned, available, PSI), the frame lines of the last seconds
  layout-views.txt, layout-buffers.txt, layout-mappings.txt   the views, the imported ranges, the GPU mappings then
  meminfo.txt, pressure.txt, environment.txt (every BC5_* and KYTY_* variable), process.txt (binary, command line)
The exit does not cut a save (tag sg412, saveguard0412.inc, put into the tree by mksg0412.py as
src/bc5/save_guard0412.hpp): before it, a save being written through the host's calls is let finish (5 s at most),
nothing new starts, what was written is synced; record.txt says whether a save was in flight and how the wait ended.
Input: the main unit after mknl0412.py (the catcher's code is reused). One anchor for the glue, one for the call.
usage: mkfr0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import sys

T = b" // exp 0412 (tag fr412)\n"

GLUE = b'''// Experiment 0412 (tag fr412): BC5_FAULT_RECORD. A GPU fault is a bug to remove at its source: write what is needed to
// find it, then end the game. No reopen, no recovery.
namespace fr412 {
inline bool on() {
	static const bool v = [] {
		const char* e = std::getenv("BC5_FAULT_RECORD");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return v;
}
} // namespace fr412
static void fr412_copy(const std::string& from, const std::string& to, long tail_bytes) {
	FILE* in = std::fopen(from.c_str(), "rb");
	if (in == nullptr) return;
	FILE* out = std::fopen(to.c_str(), "wb");
	if (out != nullptr) {
		if (tail_bytes > 0 && std::fseek(in, 0, SEEK_END) == 0) {
			const long size = std::ftell(in);
			std::fseek(in, size > tail_bytes ? size - tail_bytes : 0, SEEK_SET);
		}
		char   buf[65536];
		size_t n = 0;
		while ((n = std::fread(buf, 1, sizeof(buf), in)) != 0) std::fwrite(buf, 1, n, out);
		std::fclose(out);
	}
	std::fclose(in);
}
[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc) {
	const double t = timing_now();
	{ // one record: a second thread that arrives here while the first writes is held
		static std::atomic<bool> once {false};
		if (once.exchange(true)) {
			for (;;) std::this_thread::sleep_for(std::chrono::hours(1));
		}
	}
	// The save guard (tag sg412): the exit must not cut a save. A save being written through the host's calls is let
	// finish (5 s at most), nothing new starts, then what was written is flushed and synced. The outcome goes into
	// the record.
	const sg412::Closed sg      = sg412::close(5000);
	int                 sg_sync = -2; // -2 no save directory was mounted in this run, -1 it could not be opened, else syncfs's result
	if (sg.complete) std::fflush(nullptr);
	if (sg412::g_root_set.load()) {
		const int fd = ::open(sg412::g_root, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
		sg_sync      = fd < 0 ? -1 : ::syncfs(fd);
		if (fd >= 0) ::close(fd);
	}
	char         stamp[32] = "unknown";
	{
		const time_t now = std::time(nullptr);
		struct tm    tm {};
		if (localtime_r(&now, &tm) != nullptr) std::strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", &tm);
	}
	const std::string home = std::getenv("HOME") != nullptr ? std::getenv("HOME") : ".";
	const std::string base = home + "/bc5-data/captures/faults";
	const std::string dir  = base + "/" + stamp;
	mkdir(base.c_str(), 0700);
	mkdir(dir.c_str(), 0700);
	// what lay at the address (the catcher's questions)
	const bool     junk = (fault >> 40u) != 0;
	const uint64_t page = (junk ? fault & ((1ull << 40u) - 1) : fault) & ~0xfffull;
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	if (fault != 0) Libs::LibKernel::Memory::Bc5GuestRangesIn(page, page + 0x1000ull, &guest);
	bool        under = false, lazy = false, eager = false, imported = false;
	int         kind = -1;
	std::string name;
	uint64_t    view_va = 0, view_size = 0;
	if (FILE* fv = std::fopen((dir + "/layout-views.txt").c_str(), "w")) {
		std::fprintf(fv, "# file (0 direct, 1 private) va size file_offset flags(E eager, L lazy, D by data) name\\n");
		for (auto& S: g_d) {
			if (dstate_fd(S) < 0) continue;
			const auto views_p = direct_views(S);
			for (const auto& v: views_p->v) {
				std::fprintf(fv, "%d 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " %s %s\\n", S.kind, v.va, v.size, v.off, v.eager ? "E" : (v.lazy ? "L" : "D"), v.name.c_str());
				if (fault != 0 && !under && page >= v.va && page < v.va + v.size) {
					under     = true;
					lazy      = v.lazy;
					eager     = v.eager;
					kind      = S.kind;
					name      = v.name;
					view_va   = v.va;
					view_size = v.size;
					imported  = direct_covered_end(S, (v.off + (page - v.va)) & ~(kDChunk - 1)) != 0;
				}
			}
		}
		std::fclose(fv);
	}
	if (FILE* fb = std::fopen((dir + "/layout-buffers.txt").c_str(), "w")) {
		std::fprintf(fb, "# file (0 direct, 1 private) file_offset size\\n");
		for (auto& S: g_d) {
			for (const auto& b: S.bos) std::fprintf(fb, "%d 0x%" PRIx64 " 0x%" PRIx64 "\\n", S.kind, b.off, b.size);
		}
		std::fclose(fb);
	}
	bool   mapped = false;
	size_t n_maps = 0;
	if (g_dev) {
		const auto maps = g_dev->mappings();
		n_maps          = maps.size();
		if (FILE* fm = std::fopen((dir + "/layout-mappings.txt").c_str(), "w")) {
			std::fprintf(fm, "# gpu_va size\\n");
			for (const auto& m: maps) {
				std::fprintf(fm, "0x%" PRIx64 " 0x%" PRIx64 "\\n", static_cast<uint64_t>(m.va), static_cast<uint64_t>(m.size));
				if (fault != 0 && page >= m.va && page < m.va + m.size) mapped = true;
			}
			std::fclose(fm);
		}
	}
	fr412_copy("/proc/meminfo", dir + "/meminfo.txt", 0);
	fr412_copy("/proc/pressure/memory", dir + "/pressure.txt", 0);
	if (FILE* fe = std::fopen((dir + "/environment.txt").c_str(), "w")) {
		for (char** e = environ; e != nullptr && *e != nullptr; e++) {
			if (std::strncmp(*e, "BC5", 3) == 0 || std::strncmp(*e, "KYTY", 4) == 0) std::fprintf(fe, "%s\\n", *e);
		}
		std::fclose(fe);
	}
	if (FILE* fp = std::fopen((dir + "/process.txt").c_str(), "w")) {
		char    exe[1024] = "";
		ssize_t k = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
		if (k > 0) exe[k] = 0;
		std::fprintf(fp, "binary %s\\npid %d\\ncommand line:", exe, static_cast<int>(getpid()));
		if (FILE* fc = std::fopen("/proc/self/cmdline", "rb")) {
			int c = 0;
			while ((c = std::fgetc(fc)) != EOF) std::fputc(c == 0 ? ' ' : c, fp);
			std::fclose(fc);
		}
		std::fprintf(fp, "\\n");
		std::fclose(fp);
	}
	if (!g_dump_dir.empty()) fr412_copy(g_dump_dir + "/direct.log", dir + "/journal-tail.txt", 4l << 20);
	if (FILE* f = std::fopen((dir + "/record.txt").c_str(), "w")) {
		std::fprintf(f, "BC5 GPU fault record (exp 0412, tag fr412). A GPU fault is a bug to remove at its source; the game was ended here.\\n\\n");
		std::fprintf(f, "when: %s, %.3f s after the emulator's start\\n", stamp, t);
		std::fprintf(f, "what the host saw: a submission %s (rc %d); the kernel's last fault address 0x%" PRIx64 ", status 0x%08x (%s)\\n", timed_out ? "timed out after 2 s" : "failed", rc, fault, status,
		             fault == 0 ? "no fault address: a hang without a page fault" : ((status & (1u << 18u)) != 0 ? "a WRITE, by the status' bit 18" : "a READ, by the status' bit 18"));
		if (fault != 0) {
			std::fprintf(f, "kind: %s\\n", mr412::classify(junk, !guest.empty(), under, lazy, eager, imported, mapped));
			std::fprintf(f, "the address: %s; guest range there: %s; under a view: %s", junk ? "a bit above 40 is set (the facts below are for its low 40 bits)" : "a plain guest address", guest.empty() ? "no" : "yes",
			             under ? "yes" : "NO");
			if (under) {
				std::fprintf(f, ": \\"%s\\" (%s file, %s), view 0x%" PRIx64 "+0x%" PRIx64 ", the address is 0x%" PRIx64 " into it; its 2 MiB chunk %s", name.c_str(), kind == 0 ? "direct" : "private",
				             eager ? "eager" : (lazy ? "lazy" : "by data"), view_va, view_size, page - view_va, imported ? "is imported" : "is NOT imported (the CPU never wrote it, or its heap is lazy)");
			}
			std::fprintf(f, "; a GPU mapping at the address: %s\\n", mapped ? "yes" : "no");
		}
		std::fprintf(f, "memory: pinned direct %.1f MiB in %zu buffers, private %.1f MiB in %zu; %zu GPU mappings (meminfo.txt, pressure.txt)\\n", static_cast<double>(g_d[0].bytes) / 1048576.0, g_d[0].bos.size(),
		             static_cast<double>(g_d[1].bytes) / 1048576.0, g_d[1].bos.size(), n_maps);
		std::fprintf(f, "saves (tag sg412): %s. At the request: %d save call(s) of the host in flight, %d save mount(s) written and not yet unmounted, the last save call began %" PRId64 " ms before (-1: none in this run). "
		                "Waited %" PRId64 " ms (5000 at most); left then: %d call(s), %d mount(s); %d caller(s) held from starting something new. Sync of the save directory: %s.\\n",
		             sg412::verdict(sg), sg.ops_at_request, sg.dirty_at_request, sg.last_op_age_ms, sg.waited_ms, sg.ops_left, sg.dirty_left, sg.held,
		             sg_sync == 0 ? "done" : (sg_sync == -2 ? "not needed (no save directory was mounted)" : "FAILED"));
		std::fprintf(f, "the capture directory of this run (the whole journal, the dumped buffers of the timed-out jobs): %s\\n", g_dump_dir.empty() ? "(none: logging was off)" : g_dump_dir.c_str());
		std::fprintf(f, "the timed-out job's own buffer: %s\\n", BC5_DIAG_ENV("BC5_DIRECT_TIMEOUT_PROBE") != nullptr
		                                                              ? "dumped in the capture directory as ib-timeout-<n>-<kind>-<dwords>.bin, with the probe's summary in the journal (BC5_DIRECT_TIMEOUT_PROBE was set)"
		                                                              : "NOT KEPT: BC5_DIRECT_TIMEOUT_PROBE was not set in this run, so which packet the GPU was in cannot be read afterwards (the buffer is kept only with that variable: it costs a copy of every buffer)");
		std::fprintf(f, "\\nin this directory: journal-tail.txt (the probe's summary of the timed-out jobs, the last submissions, the ledger, the frame lines), layout-views.txt, layout-buffers.txt,\\n"
		                "layout-mappings.txt, meminfo.txt, pressure.txt, environment.txt (every BC5_* and KYTY_* variable), process.txt.\\n");
		std::fprintf(f, "\\nNOT known to the emulator, added by the launcher when it can (dmesg.txt, build.txt): the kernel's own fault lines (client, RW, the ring), the devcoredump's path, the binary's md5.\\n"
		                "Nothing here is read by a later run.\\n");
		std::fclose(f);
	}
	journal("fault record (exp 0412, tag fr412): written to %s; the game ends here (BC5_FAULT_RECORD)\\n", dir.c_str());
	std::fprintf(stderr, "[bc5] GPU FAULT at 0x%" PRIx64 " (status 0x%08x), %.1f s after the start: the record is in %s; the game ends here (exit 86). A GPU fault is a bug to fix, not something to get up from. Saves: %s.\\n", fault,
	             status, t, dir.c_str(), sg412::verdict(sg));
	if (sg.complete) std::fflush(nullptr); // not when a save call is still in flight: it may hold a stream
	else std::fflush(stderr);
	_exit(86);
}
'''


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag nl412" in s and b"tag fr412" not in s, "refused: not the unit after mknl0412.py, or already edited"
    GLUE.decode("ascii")
    a = b"static void recover_after_timeout(const bc5::direct::SubmitResult& r) {\n"
    s = once(s, a, GLUE + a)
    a = b'#include "loader/symbolDatabase.h"\n\n#if defined(KYTY_BC5_DIRECT)\n'  # the file's top level, before any namespace opens
    s = once(s, a, b'#include "bc5/save_guard0412.hpp" // exp 0412 (tag sg412): the save guard of the fault record\n' + a)
    assert s.index(b"save_guard0412.hpp") < s.index(b"\nnamespace ")
    a = b"\t\tmr412_would_learn(r.fault_addr, static_cast<uint32_t>(r.fault_status)); // exp 0412 (tag mr412)\n"
    s = once(s, a, a + b"\t\tif (fr412::on()) fr412_record_and_exit(r.fault_addr, static_cast<uint32_t>(r.fault_status), r.timed_out, r.rc);" + T)
    g = s.index(b"[[noreturn]] static void fr412_record_and_exit(")
    for need in (b"namespace mr412 {", b"static std::shared_ptr<const DViews> direct_views(const DState& S) {", b"static uint64_t direct_covered_end(const DState& S, uint64_t off) {",
                 b"static double timing_now() {", b"static std::string       g_dump_dir;"):
        assert s.index(need) < g, ("must be defined before the glue", need[:40])
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
