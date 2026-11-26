#!/usr/bin/env python3
"""BC5 experiment 0412, tag zp412 (README section 40): the zero skip's poll before every submission.
The zero skip (exp 0379) leaves all-zero chunks unpinned with a canary of zeros mapped for the GPU, and learns of the
CPU's first write into such a chunk only at a direct sync (zskip_take_back's SEEK_DATA), which is throttled: the blind
window of section 33 (mean 59 ms, tens of submissions inside it).
BC5_GUARD_ZSKIP_POLL_SUBMIT=1: submit_now, under the device mutex and before it takes the mapping list for this buffer,
does one fstat of the direct file; when its block count has changed since the last look (a write into a hole allocates
a page; so does a read fault and a kernel write), it runs zskip_take_back and, if a chunk came back, a full sync that
pins it and puts the real mapping in the canary's place. Data the title wrote before it submitted a buffer is thereby
under the GPU's mapping when that buffer reaches the kernel; only a write that races a buffer already handed over is
still unseen until the next submission, and no ordering of the title's can rely on that one.
Input: the main unit after mknscan0412.py. No behaviour change with the switch unset (one test of a constant).
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mkzpoll0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

T = b" // exp 0412 (tag zp412)\n"
INC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "zpoll0412.inc"), "rb").read()
assert b"\r" not in INC and INC.decode("ascii")

GLUE = INC + b'''// Experiment 0412 (tag zp412): BC5_GUARD_ZSKIP_POLL_SUBMIT. The zero skip's poll before every submission: see mkzpoll0412.py.
static void zpoll412_submit() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_GUARD_ZSKIP_POLL_SUBMIT");
		return e != nullptr && e[0] == '1';
	}();
	if (!on || g_zskip.empty()) return;
	DState&   S  = g_d[0];
	const int fd = dstate_fd(S);
	if (fd < 0) return;
	static uint64_t seen = ~0ull, looks = 0, grew = 0, took = 0, took_subs = 0, spent_ns = 0, last_ns = 0, lines = 0;
	const uint64_t  t0 = SoftCp::now_ns();
	struct stat     st {};
	looks++;
	if (fstat(fd, &st) == 0 && zp412::look(seen, static_cast<uint64_t>(st.st_blocks))) { // seen = the sample taken BEFORE the scan (zpoll0412.inc, R12)
		grew++;
		const uint64_t before = g_zstat_cpu + g_zstat_hits;
		zskip_take_back(S, fd);
		const uint64_t n = g_zstat_cpu + g_zstat_hits - before;
		if (n != 0) {
			took += n;
			took_subs++;
			S.blocks = ~0ull; // a full sync: pin what came back and map it in the canary's place, before this buffer goes out
			direct_sync_one(S, true); // the pin allocates pages: the next submission sees a changed count and scans once more
			if (lines++ < 60 || (lines & 63u) == 0) {
				journal("zero skip poll (exp 0412, tag zp412): t %.3f s: %" PRIu64 " chunks taken back before submission %" PRIu64 " (%.2f ms)\\n", timing_now(), n, g_submits.load(),
				        static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
			}
		}
	}
	const uint64_t t1 = SoftCp::now_ns();
	spent_ns += t1 - t0;
	if (t1 - last_ns >= 10'000'000'000ull) {
		last_ns = t1;
		journal("zero skip poll (exp 0412, tag zp412): t %.0f s: %" PRIu64 " looks, the file had grown at %" PRIu64 ", %" PRIu64 " chunks taken back at %" PRIu64 " submissions; %.1f MiB still skipped; %.1f ms spent in all\\n",
		        timing_now(), looks, grew, took, took_subs, static_cast<double>(g_zskip.bytes()) / 1048576.0, static_cast<double>(spent_ns) / 1e6);
	}
}
'''


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    assert b"tag ns412" in s and b"tag zp412" not in s, "refused: not the expected input"
    assert b"\r" not in s
    GLUE.decode("ascii")
    edits = []
    a = b"static void nscan412_submit(const uint32_t* ib, uint32_t num_dwords, const char* kind) {\n"
    edits.append((a, GLUE + a))
    a = b"\tnscan412_submit(ib, num_dwords, kind); // exp 0412 (tag ns412)\n"
    edits.append((a, b"\tzpoll412_submit();" + T + a))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:60], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:60], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    g = out.index(b"static void zpoll412_submit() {")
    for need in (b"static void zskip_take_back(DState& S, int fd) {", b"static void direct_sync_one(DState& S, bool force) {", b"static uint64_t g_zstat_cpu = 0"):
        assert out.index(need) < g, ("must be defined before the glue", need[:40])
    assert b"g_submits" in out[:g], "g_submits is not declared before the glue"
    call = out.index(b"\tzpoll412_submit();")
    sn = out.index(b"static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {")
    assert sn < call < out.index(b"std::shared_ptr<const std::vector<bc5::direct::Mapping>> maps_p = g_dev->sorted_mappings();", sn), "the call is not before submit_now's mapping list"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
