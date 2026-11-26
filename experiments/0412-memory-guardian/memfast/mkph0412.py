#!/usr/bin/env python3
"""BC5 experiment 0412, tag ph412 (README section 86): BC5_FAULT_POINTERS=1 (default off) adds pointers.txt to the
fault record: every place in the title's memory (the data extents of the direct file and of the private file) that
holds an address inside the faulted 2 MiB chunk, with the heap it lies in (ph0412.inc, ph0412.cpp). A catcher: it
reads memory once, when the game is being ended; it changes no mapping and no result.
Input: a main unit with tag kc412 (mkkc0412.py's output, 7af3f752). Every anchor exactly once.
usage: mkph0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

PH_GLUE = rb'''// Experiment 0412 (tag ph412): BC5_FAULT_POINTERS, the host's part. Called once by the fault record, after the save guard.
static void ph412_record(const std::string& dir, uint64_t page) {
	if (!ph412::on() || page == 0) return;
	const uint64_t lo = page & ~(kDChunk - 1), hi = lo + kDChunk;
	FILE*          out = std::fopen((dir + "/pointers.txt").c_str(), "w");
	if (out == nullptr) return;
	std::fprintf(out, "# exp 0412 (tag ph412): words of the title's memory whose low 40 bits lie in the faulted chunk 0x%" PRIx64 "+0x%" PRIx64 " (the fault page 0x%" PRIx64 ")\n", lo,
	             static_cast<uint64_t>(kDChunk), page);
	std::fprintf(out, "# file (0 direct, 1 private) file_offset holder_va word kind (pointer: nothing above bit 40; fields: a descriptor-like word) heap of the holder\n");
	const double                    t0 = timing_now();
	std::vector<uint8_t>            buf(4u << 20u);
	uint64_t                        hits = 0, plain = 0, bytes = 0;
	bool                            cut = false;
	std::map<std::string, uint64_t> by_heap;
	for (auto& S: g_d) {
		const int fd = dstate_fd(S);
		if (fd < 0) continue;
		std::vector<DView> views;
		if (S.kind == 0) views = direct_views(S)->v;
		off_t pos = 0;
		while (!cut) {
			const off_t d = lseek(fd, pos, SEEK_DATA);
			if (d < 0) break;
			const off_t h = lseek(fd, d, SEEK_HOLE);
			if (h <= d) break;
			for (off_t o = d; o < h && !cut;) {
				const size_t  want = static_cast<size_t>(std::min<off_t>(h - o, static_cast<off_t>(buf.size())));
				const ssize_t n    = pread(fd, buf.data(), want, o);
				if (n <= 0) break;
				bytes += static_cast<uint64_t>(n);
				ph412::scan(buf.data(), static_cast<size_t>(n), lo, hi, [&](size_t i, uint64_t w) {
					const uint64_t foff = static_cast<uint64_t>(o) + i;
					uint64_t       va   = foff;
					const char*    name = "private memory";
					if (S.kind == 0) {
						va   = 0;
						name = "under no view";
						for (const auto& v: views) {
							if (foff >= v.off && foff < v.off + v.size) {
								va   = v.va + (foff - v.off);
								name = v.name.c_str();
								break;
							}
						}
					}
					hits++;
					if (ph412::plain(w)) plain++;
					by_heap[name]++;
					if (hits <= 4000) std::fprintf(out, "%d 0x%" PRIx64 " 0x%" PRIx64 " 0x%016" PRIx64 " %s %s\n", S.kind, foff, va, w, ph412::plain(w) ? "pointer" : "fields", name);
				});
				o += n;
				if (timing_now() - t0 > 30.0) cut = true;
			}
			pos = h;
		}
	}
	std::fprintf(out, "# %" PRIu64 " words found (%" PRIu64 " plain pointers) in %.1f MiB read in %.1f s%s; the first 4000 are listed; by heap of the holder:\n", hits, plain,
	             static_cast<double>(bytes) / 1048576.0, timing_now() - t0, cut ? "; CUT at 30 s, not all memory was read" : "");
	for (const auto& [name, n]: by_heap) std::fprintf(out, "# %" PRIu64 " %s\n", n, name.c_str());
	std::fclose(out);
	journal("fault pointers (exp 0412, tag ph412): %" PRIu64 " words of the title's memory point into the faulted chunk 0x%" PRIx64 " (%" PRIu64 " plain pointers), %.1f MiB read in %.1f s%s: pointers.txt in the fault record\n",
	        hits, lo, plain, static_cast<double>(bytes) / 1048576.0, timing_now() - t0, cut ? ", CUT at 30 s" : "");
}
'''


def once(s, old, new):
    assert s.count(old) == 1, (s.count(old), old[:70])
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
    assert b"\r" not in s and b"tag kc412" in s and b"tag ph412" not in s, "refused: not a unit with kc412, or already edited"
    PH_GLUE.decode("ascii")
    a = b"[[noreturn]] static void fr412_record_and_exit(uint64_t fault, uint32_t status, bool timed_out, int rc) {\n"
    s = once(s, a, b"// Experiment 0412 (tag ph412): ph0412.inc, who holds a pointer to the faulted chunk.\n" + body_of("ph0412.inc", b"ph412") + PH_GLUE + a)
    a = b'\tfr412_copy("/proc/pressure/memory", dir + "/pressure.txt", 0);\n'
    s = once(s, a, a + b"\tph412_record(dir, fault != 0 ? page : 0); // exp 0412 (tag ph412)\n")
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
