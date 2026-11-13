#!/usr/bin/env python3
"""BC5 experiment 0412, tag kc412 and the first-failure catcher's arming line (README section 85).
  unit    BC5_GUARD_COVER_LOG=1 (default off): one journal line for every mapping rebuild in which a K1r cover gave
          way to the title's data (kc0412.inc, kc0412.cpp). Log only. Input: a main unit with tags bd412 and wc412
          (mkbd0412.py's output, 8f07ccf6 from candidate F's unit).
  memory  KYTY_BC5_MEM_FIRSTFAIL (tag ff412) says at the process's start that it is armed, so that a run without
          failure lines can be told from a run without the catcher. Input: the host's src/kernel/memory.cpp with ff412
          (candidate F's f51c803e).
Every anchor exactly once.
usage: mkkc0412.py unit <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>
       mkkc0412.py memory <memory.cpp in> <memory.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

KC_GLUE = rb'''// Experiment 0412 (tag kc412): BC5_GUARD_COVER_LOG, the host's part. Called by the mapping rebuild only (one thread).
static kc412::Tally g_kc_tally;
static uint64_t     g_kc_total = 0;
static void kc412_dropped(const DMap& m, const std::vector<DMap>& want) {
	if (!kc412::on() || !k1r412_is_cover(m.id)) return;
	g_kc_tally.add(kc412::after(m.va, m.size, want, [](uint32_t id) { return k1r412_is_cover(id); }), m.va, m.size);
}
static void kc412_rebuilt(const std::vector<DView>& views) {
	if (!kc412::on()) return;
	static bool said = false;
	if (!said) {
		said = true;
		journal("cover log (exp 0412, tag kc412): BC5_GUARD_COVER_LOG on, armed: every mapping rebuild in which a K1r cover gives way to the title's data is journaled\n");
	}
	const kc412::Tally& t = g_kc_tally;
	if (t.n[kc412::kData] != 0) {
		const char* name = "no view";
		for (const auto& v: views) {
			if (t.first_data_va >= v.va && t.first_data_va < v.va + v.size) {
				name = v.name.c_str();
				break;
			}
		}
		g_kc_total += t.n[kc412::kData];
		journal("cover log (exp 0412, tag kc412): t %.2f s: %" PRIu64 " cover pieces (%.2f MiB) gave way to the title's data, the first at 0x%" PRIx64 " in %s; %" PRIu64 " re-covered, %" PRIu64 " gone with their view; %" PRIu64 " gave way since the start\n",
		        timing_now(), t.n[kc412::kData], static_cast<double>(t.bytes[kc412::kData]) / 1048576.0, t.first_data_va, name, t.n[kc412::kCover], t.n[kc412::kGone], g_kc_total);
	}
	g_kc_tally = kc412::Tally {};
}
'''

ARM = rb'''// exp 0412 (tag ff412, 2026-11-14): the arming line. Without it "the catcher printed nothing" cannot be told from
// "the catcher was not on" (exp 0419's nine walks of 2026-11-13).
[[maybe_unused]] static const bool g_ff412_armed = [] {
	if (ff412::on()) {
		std::fprintf(stderr, "[bc5] mem firstfail (exp 0412, tag ff412): KYTY_BC5_MEM_FIRSTFAIL on, armed: the wrapped memory calls, the AMM auto pool's refused borrow and the exit on a reserved AMM page report here\n");
		std::fflush(stderr);
	}
	return true;
}();
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


def unit(s):
    assert b"tag bd412" in s and b"tag wc412" in s and b"tag kc412" not in s, "refused: not mkbd0412.py's output, or already edited"
    KC_GLUE.decode("ascii")
    a = b"// At a GPU fault: was it under the cover, and was it a write?\n"
    s = once(s, a, b"// Experiment 0412 (tag kc412): kc0412.inc, the cover -> data log.\n" + body_of("kc0412.inc", b"kc412") + KC_GLUE + a)
    a = b"\t\t\t\tg_dev->unmap_shared(m.va);\n\t\t\t\tunmapped++;\n"
    s = once(s, a, b"\t\t\t\tkc412_dropped(m, want); // exp 0412 (tag kc412)\n" + a)
    a = b"\t\tconst uint64_t t_drop = SoftCp::now_ns(); // experiment 0169\n"
    s = once(s, a, b"\t\tkc412_rebuilt(views); // exp 0412 (tag kc412)\n" + a)
    return s


def memory(s):
    assert b"tag ff412" in s and b"g_ff412_armed" not in s, "refused: no ff412, or already edited"
    ARM.decode("ascii")
    a = b"static ff412::Ring g_ff412_ring;\nstatic std::mutex  g_ff412_mutex;\n"
    return once(s, a, a + ARM)


def main():
    assert len(sys.argv) == 4 and sys.argv[1] in ("unit", "memory") and sys.argv[2] != sys.argv[3], __doc__
    s = open(sys.argv[2], "rb").read()
    assert b"\r" not in s
    s = unit(s) if sys.argv[1] == "unit" else memory(s)
    open(sys.argv[3], "wb").write(s)
    print(f"{'bc5LleAgc.cpp' if sys.argv[1] == 'unit' else 'memory.cpp'} {hashlib.md5(s).hexdigest()}")


if __name__ == "__main__":
    main()
