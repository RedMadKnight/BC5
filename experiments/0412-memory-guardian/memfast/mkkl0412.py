#!/usr/bin/env python3
"""BC5 experiment 0412, tag kl412 (README section 71): under a LAZY view K1r covers only never-written chunks.
Found on 2026-11-13 15:32 (ASTRO BOT on g412zc, K1r on, the watched page 0x3082f6000): "the chunk WRITTEN by the CPU,
not imported; GPU: a read-only zero cover (K1r)". K1r covered every part of a view no imported buffer covers; under a
lazy view that includes memory the CPU has written (only hints import a lazy view), so a GPU read there returned
zeros where the title's data lies. With this edit such a piece gets no cover: it is unmapped as without K1r, and a
read there is a fault with a record. BC5_GUARD_K1R_COVER_WRITTEN=1 turns the rule off;
BC5_GUARD_K1R_WRITTEN_SCAN_MS (default 100) is the least time between two SEEK_DATA scans.
The rule and its CPU test: kl0412.inc, kl0412.cpp.
Input: the main unit after mkk1f0412.py.
usage: mkkl0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag k1f412" in s and b"tag kl412" not in s, "refused: not the unit after mkk1f0412.py, or already edited"
    inc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kl0412.inc"), "rb").read()
    assert b"\r" not in inc
    body = inc[inc.index(b"namespace kl412 {"):]
    assert body.rstrip().endswith(b"} // namespace kl412") and b"#include" not in body
    a = b"static void k1r412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want) {\n"
    s = once(s, a, b"// Experiment 0412 (tag kl412): kl0412.inc, under a lazy view K1r covers only never-written chunks.\n" + body +
             b"static void k1r412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want, int fd) { // exp 0412 (tag kl412): fd, the direct file\n")
    s = once(s, b"\t\tk1r412_want(S, views, want); // exp 0412 (tag k1r412)\n", b"\t\tk1r412_want(S, views, want, fd); // exp 0412 (tag k1r412; kl412: fd)\n")
    a = (b"\tuint64_t n = 0, bytes = 0;\n\tfor (const auto& v: views) {\n\t\tpieces.clear();\n"
         b"\t\tk1r412::cover(v.va, v.off, v.size, bos, kDChunk, pieces);\n")
    s = once(s, a, rb'''	uint64_t n = 0, bytes = 0;
	static kl412::Known kl; // exp 0412 (tag kl412)
	uint64_t            kl_dropped = 0;
	const uint64_t      kl_t0      = SoftCp::now_ns();
	const bool          kl_scan    = !kl412::cover_written() && kl.begin(kl_t0, kl412::period_ns());
	for (const auto& v: views) {
		pieces.clear();
		k1r412::cover(v.va, v.off, v.size, bos, kDChunk, pieces);
		if (v.lazy && !kl412::cover_written()) { // exp 0412 (tag kl412): a written chunk of a lazy view gets no zero cover
			kl_dropped += kl412::drop_written(pieces, v.va, v.off, kDChunk, kl, kl_scan, [fd](uint64_t choff) {
				const off_t d = lseek(fd, static_cast<off_t>(choff), SEEK_DATA);
				return d >= 0 && static_cast<uint64_t>(d) < choff + kDChunk;
			});
		}
''')
    a = b"\tconst uint64_t now = SoftCp::now_ns();\n\tif (n != last_n && now - last_ns >= 10'000'000'000ull) {\n\t\tlast_n  = n;\n\t\tlast_ns = now;\n"
    assert s.count(a) == 1, ("the k1r stat block", s.count(a))
    s = s.replace(a, rb'''	const uint64_t now = SoftCp::now_ns();
	if (kl_scan) kl.scan_ns += now - kl_t0; // exp 0412 (tag kl412): a rebuild's cover pass with its scan
	if (n != last_n && now - last_ns >= 10'000'000'000ull) {
		last_n  = n;
		last_ns = now;
		journal("k1r written chunks (exp 0412, tag kl412): t %.0f s: %s: %" PRIu64 " pieces under lazy views hold data and get NO cover (unmapped; a GPU read there faults by name); %zu chunks known written; %" PRIu64 " scans, %" PRIu64 " SEEK_DATA calls, %.1f ms in all (%.3f ms a scan)\n",
		        timing_now(), kl412::cover_written() ? "rule OFF (BC5_GUARD_K1R_COVER_WRITTEN)" : "rule on", kl_dropped, kl.written.size(), kl.scans, kl.asked, static_cast<double>(kl.scan_ns) / 1e6,
		        kl.scans != 0 ? static_cast<double>(kl.scan_ns) / 1e6 / static_cast<double>(kl.scans) : 0.0);
''')
    g = s.index(b"namespace kl412 {")
    assert s.index(b"static double timing_now() {") < g
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
