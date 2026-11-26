#!/usr/bin/env python3
"""BC5 experiment 0412, tag ng412 (README section 37): heaps the title mapped without a GPU bit are not pinned.
Input: the main unit after mklock, mksect, mkgap, mkbuf, mkret, mkuse, mkzcat and mkprot (DView::prot exists).
  - nogpu0412.inc (the text nogpu0412.cpp tests) goes in before zcat0412.inc's block;
  - the glue nogpu412_apply() goes in after the guardian's put-off set (g_g412_off, guard0412.inc): it takes
    ng412::plan()'s chunks, keeps those a hint or a learned window forced and those already imported, takes the rest
    out of the sync's import list and makes them the put-off set, so that guard0412_want() maps the zero buffer under
    their views exactly as BC5_GUARD_CAP_ACT does; every 10 s it reads the zero buffer back and journals when the GPU
    has written into it. With BC5_GUARD_CAP_ACT on it does nothing (the two would share one set);
  - its prototype beside guard0412_cap's, and its call right after guard0412_cap() in direct_sync_one.
BC5_GUARD_NOGPU_UNPIN unset: the call returns after one test of an empty list.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mknogpu0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag ng412)\n"

GLUE = b'''
// Experiment 0412 (tag ng412): BC5_GUARD_NOGPU_UNPIN. After the import list of a sync is made: the chunks under views of
// the listed heaps without a GPU bit leave it and become the put-off set (the zero buffer goes under their views in
// guard0412_want). A forced chunk and one that is imported already stay as they are.
static void nogpu412_apply(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need) {
	const std::vector<std::string>& list = ng412::names();
	if (list.empty() || S.kind != 0) return;
	if (g412::cfg().cap_act) {
		static bool said = false;
		if (!said) journal("guard nogpu (exp 0412, tag ng412): BC5_GUARD_CAP_ACT is on: BC5_GUARD_NOGPU_UNPIN does nothing\\n");
		said = true;
		return;
	}
	std::vector<uint64_t> off;
	for (const uint64_t c: ng412::plan(views, kDChunk, list)) {
		if (S.forced.count(c) == 0 && direct_covered_end(S, c) == 0) off.push_back(c);
	}
	if (!off.empty() && !need.empty()) {
		std::vector<uint64_t> rest;
		std::set_difference(need.begin(), need.end(), off.begin(), off.end(), std::back_inserter(rest));
		need.swap(rest);
	}
	static uint64_t changes = 0;
	if (off != g_g412_off) {
		g_g412_off_changed = true;
		const uint64_t n = changes++;
		if (n < 24 || (n & 63u) == 0) {
			journal("guard nogpu (exp 0412, tag ng412): %zu chunks (%.1f MiB) under views without a GPU bit are not pinned, the zero buffer under their views (change %" PRIu64 ")\\n",
			        off.size(), static_cast<double>(off.size() * kDChunk) / 1048576.0, n + 1);
		}
		g_g412_off.swap(off);
	}
	// The catcher: has the GPU written into the zero buffer? (It is shared with the holes' scratch mappings.)
	static uint64_t last_ns = 0, last_bad = ~0ull;
	const uint64_t  now = SoftCp::now_ns();
	if (g_scratch_fd >= 0 && now - last_ns >= 10'000'000'000ull) {
		last_ns = now;
		static std::vector<unsigned char> buf(kDChunk);
		uint64_t bad = 0, first = 0;
		if (pread(g_scratch_fd, buf.data(), buf.size(), 0) == static_cast<ssize_t>(buf.size())) {
			for (size_t i = 0; i < buf.size(); i++) {
				if (buf[i] != 0) {
					if (bad++ == 0) first = i;
				}
			}
			if (bad != last_bad) {
				journal("guard nogpu (exp 0412, tag ng412): t %.0f s: the zero buffer has %" PRIu64 " non-zero bytes%s; %zu chunks (%.1f MiB) not pinned now\\n", timing_now(), bad,
				        bad != 0 ? (std::string(", the first at +0x") + [&] { char b[24]; std::snprintf(b, sizeof(b), "%" PRIx64, first); return std::string(b); }()).c_str() : "",
				        g_g412_off.size(), static_cast<double>(g_g412_off.size() * kDChunk) / 1048576.0);
				last_bad = bad;
			}
		}
	}
}
'''


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "nogpu0412.inc"), "rb").read()
    assert b"tag pr412" in s and b"namespace ng412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    GLUE.decode("ascii")
    edits = []
    a = b"// Experiment 0412 (tag zc412): BC5_GUARD_ZSKIP_STAT, the zero skip's blind window.\n"
    edits.append((a, b"// Experiment 0412 (tag ng412): BC5_GUARD_NOGPU_UNPIN, heaps without a GPU bit are not pinned.\n" + inc + a))
    a = b"static bool                  g_g412_off_changed = false;\n"
    edits.append((a, a + GLUE))
    a = b"static void guard0412_cap(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need); // exp 0412 (tag g412b)\n"
    edits.append((a, a + b"static void nogpu412_apply(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need);" + T))
    a = b"\tguard0412_cap(S, views, need); // exp 0412 (tag g412b): BC5_GUARD_CAP_ACT puts soft chunks over the cap off\n"
    edits.append((a, a + b"\tnogpu412_apply(S, views, need);" + T))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    g = out.index(b"static void nogpu412_apply(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need) {")
    for need in (b"static int                                         g_scratch_fd = -1;", b"namespace ng412", b"static std::vector<uint64_t> g_g412_off;"):
        assert out.index(need) < g, ("must be defined before the glue", need[:40])
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
