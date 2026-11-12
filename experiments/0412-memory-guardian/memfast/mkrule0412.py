#!/usr/bin/env python3
"""BC5 experiment 0412, tag mr412 (DESIGN-learned-windows.md, README section 53): the learned windows replaced by a rule.
Input: the main unit after mkzscan0412.py (g412w's, 1d27e927). Three switches, all off when unset (maprule0412.inc):
  BC5_GUARD_MAP_RULE=1|2   every chunk under a view is imported when the view exists (direct_sync_one's eager loop);
  BC5_GUARD_PRT_BG=1       one PRT mapping under the guest's span at device open (acts only with MAP_RULE on);
                           scratch_fill does nothing inside it;
  BC5_GUARD_LEARN_LOG=1|2  the catcher: every fault that would be learned is journaled with what lay at its address,
                           and neither the learned file nor the alias file is written.
  - maprule0412.inc (the text maprule0412.cpp tests) and mr412_prt_open() go in after g_dev's definition;
  - both device-open sites call mr412_prt_open() in place of the AMM window's PRT mapping (which it still makes);
  - mr412_would_learn() goes in before learned_add() and is called in recover_after_timeout() before the learning.
Each anchor occurs exactly once; the script undoes its edits and asserts that this gives the input back.
usage: mkrule0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
T = b" // exp 0412 (tag mr412)\n"

OPEN = b'''static bool g_mr412_bg = false; // exp 0412 (tag mr412): the PRT background span is mapped on the open device
// Experiment 0412 (tag mr412): the PRT mappings a freshly opened device gets. With BC5_GUARD_PRT_BG (and MAP_RULE) the
// whole guest span; otherwise, or when the kernel refuses the span, the AMM window alone as before (BC5_DIRECT_AMM_PRT).
static void mr412_prt_open() {
	g_mr412_bg = false;
	if (!g_dev) return;
	if (mr412::prt_bg()) {
		const uint64_t t0 = SoftCp::now_ns();
		g_mr412_bg        = g_dev->map_prt_window(mr412::kBgLo, mr412::kBgHi - mr412::kBgLo);
		journal("map rule (exp 0412, tag mr412): PRT background 0x%" PRIx64 "-0x%" PRIx64 ": %s, %.1f ms\\n", mr412::kBgLo, mr412::kBgHi, g_mr412_bg ? "mapped" : "REFUSED (the AMM window alone, as before)",
		        static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
		if (g_mr412_bg) return; // the AMM window lies inside the span
	}
	const bool amm_prt = std::getenv("BC5_DIRECT_AMM_PRT") != nullptr; // experiment 0102
	if (amm_prt) g_dev->map_prt_window(0x8000000000ull, 0x1000000000ull);
}
'''

CATCH = b'''// Experiment 0412 (tag mr412): BC5_GUARD_LEARN_LOG. What lay at the address of a GPU fault that would be learned: one
// journal line per fault, the sample the rule's design asks for. Called before the learning, on the thread that learns.
static void mr412_would_learn(uint64_t fault, uint32_t status) {
	if (mr412::learn_log() == 0 || fault == 0) return;
	const bool     junk = (fault >> 40u) != 0;
	const uint64_t page = (junk ? fault & ((1ull << 40u) - 1) : fault) & ~0xfffull;
	std::vector<std::pair<uint64_t, uint64_t>> guest;
	Libs::LibKernel::Memory::Bc5GuestRangesIn(page, page + 0x1000ull, &guest);
	bool        under = false, lazy = false, eager = false, imported = false, forced = false;
	int         prot = 0, kind = -1;
	std::string name;
	for (auto& S: g_d) {
		if (under || dstate_fd(S) < 0) continue;
		const auto views_p = direct_views(S);
		for (const auto& v: views_p->v) {
			if (page < v.va || page >= v.va + v.size) continue;
			const uint64_t c = (v.off + (page - v.va)) & ~(kDChunk - 1);
			under    = true;
			lazy     = v.lazy;
			eager    = v.eager;
			prot     = v.prot;
			kind     = S.kind;
			name     = v.name;
			imported = direct_covered_end(S, c) != 0;
			forced   = S.forced.count(c) != 0;
			break;
		}
	}
	const bool     mapped = g_dev && covered_sorted(*g_dev->sorted_mappings(), page, 4);
	const uint64_t lo     = (fault & ~0x3ffffffull) > 0x2000000ull ? (fault & ~0x3ffffffull) - 0x2000000ull : 0;
	bool           listed = false;
	for (const auto& [a, b]: g_learned) {
		if (a == lo && b == 0x6000000ull) listed = true;
	}
	journal("would learn (exp 0412, tag mr412): t %.3f s: fault 0x%" PRIx64 " status 0x%08x: %s; guest range %s; view %s%s%s prot 0x%x; chunk %s%s; GPU mapping %s; PRT background %s; window 0x%" PRIx64 "+0x6000000 %s; mode %d, no file written\\n",
	        timing_now(), fault, status, mr412::classify(junk, !guest.empty(), under, lazy, eager, imported, mapped), guest.empty() ? "no" : "yes", under ? name.c_str() : "none",
	        under ? (kind == 0 ? " (direct" : " (private") : "", under ? (eager ? ", eager)" : (lazy ? ", lazy)" : ", by data)")) : "", static_cast<unsigned>(prot), imported ? "imported" : "not imported", forced ? ", forced" : "",
	        mapped ? "yes" : "no", g_mr412_bg ? "on" : "off", lo, listed ? "already on this run's list" : "new", mr412::learn_log());
}
'''


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "maprule0412.inc"), "rb").read()
    assert b"tag zs412" in s and b"tag pr412" in s and b"tag mr412" not in s, "refused: not the expected input"
    assert b"\r" not in s and b"\r" not in inc
    inc.decode("ascii")
    OPEN.decode("ascii")
    CATCH.decode("ascii")
    edits = []
    a = b"static std::unique_ptr<bc5::direct::Device> g_dev;\n"
    edits.append((a, a + inc + OPEN))
    a = b'\tif (std::getenv("BC5_DIRECT_AMM_PRT") != nullptr) g_dev->map_prt_window(0x8000000000ull, 0x1000000000ull);\n'
    edits.append((a, b"\tmr412_prt_open(); // exp 0412 (tag mr412): the AMM window's PRT mapping, or the whole span with BC5_GUARD_PRT_BG\n"))
    a = b'\t\tif (g_dev && std::getenv("BC5_DIRECT_AMM_PRT") != nullptr) g_dev->map_prt_window(0x8000000000ull, 0x1000000000ull); // experiment 0102\n'
    edits.append((a, b"\t\tmr412_prt_open(); // exp 0412 (tag mr412): after a reopen, as at the first open (experiment 0102)\n"))
    a = b"\t\tif (v.eager) { // BC5_DIRECT_EAGER_NAMES: every chunk of the view\n"
    edits.append((a, b"\t\tif (v.eager || mr412::rule_for(S.kind)) { // BC5_DIRECT_EAGER_NAMES: every chunk of the view; exp 0412 (tag mr412): BC5_GUARD_MAP_RULE, of every view\n"))
    a = b"static void scratch_fill(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have) {\n\tif (!g_dev) return;\n"
    edits.append((a, a + b"\tif (g_mr412_bg && mr412::in_bg(lo, hi)) return; // exp 0412 (tag mr412): BC5_GUARD_PRT_BG, the hole is PRT already\n"))
    a = b"static void learned_add(uint64_t fault_addr) {\n"
    edits.append((a, CATCH + a))
    a = b"\tif (m11_learn_refused(fault_addr, lo, n)) return; // exp 0401 e11 (tag m11): BC5_DIRECT_LEARN_GUEST_ONLY\n"
    edits.append((a, a + b"\tif (mr412::learn_log() == 2) return; // exp 0412 (tag mr412): BC5_GUARD_LEARN_LOG=2, the line is written, nothing is added\n"))
    a = b'\tif (FILE* f = std::fopen(learned_path(), "a")) {\n'
    edits.append((a, b'\tif (FILE* f = mr412::learn_log() != 0 ? nullptr : std::fopen(learned_path(), "a")) { // exp 0412 (tag mr412): the catcher writes no file\n'))
    a = b"static void alias_learn(uint64_t fault_addr) {\n\tif (!aliases_on()) return;\n"
    edits.append((a, a + b"\tif (mr412::learn_log() == 2) return; // exp 0412 (tag mr412): BC5_GUARD_LEARN_LOG=2\n"))
    a = b'\tif (FILE* f = std::fopen(alias_path(), "a")) {\n'
    edits.append((a, b'\tif (FILE* f = mr412::learn_log() != 0 ? nullptr : std::fopen(alias_path(), "a")) { // exp 0412 (tag mr412): the catcher writes no file\n'))
    a = b"\t\tif (r.fault_addr != 0 && (r.fault_addr >> 40u) != 0 && aliases_on()) alias_learn(r.fault_addr); // experiment 0056\n"
    edits.append((a, b"\t\tmr412_would_learn(r.fault_addr, static_cast<uint32_t>(r.fault_status));" + T + a))
    out = s
    for old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", old[:70], out.count(old))
        out = out.replace(old, new)
    back = out
    for old, new in reversed(edits):
        assert back.count(new) == 1, ("undo", new[:70], back.count(new))
        back = back.replace(new, old)
    assert back == s, "undoing the edits does not give the input back"
    # order: everything the glue uses is defined or declared before it
    g1 = out.index(b"static void mr412_prt_open() {")
    for need in (b"static void journal(const char* fmt, ...) {", b"namespace SoftCp {", b"static std::unique_ptr<bc5::direct::Device> g_dev;", b"namespace mr412 {"):
        assert out.index(need) < g1, ("must be defined before mr412_prt_open", need[:40])
    g2 = out.index(b"static void mr412_would_learn(uint64_t fault, uint32_t status) {")
    for need in (b"static std::shared_ptr<const DViews> direct_views(const DState& S) {", b"static uint64_t direct_covered_end(const DState& S, uint64_t off) {", b"static int dstate_fd(const DState& S) {",
                 b"static bool covered_sorted(const std::vector<bc5::direct::Mapping>& maps, uint64_t a, uint64_t bytes);", b"static std::vector<std::pair<uint64_t, uint64_t>> g_learned;", b"static double timing_now()",
                 b"static bool g_mr412_bg = false;", b"\tint         prot = 0;"):
        assert out.index(need) < g2, ("must be defined before mr412_would_learn", need[:40])
    assert g1 < out.index(b"\tmr412_prt_open(); // exp 0412 (tag mr412): the AMM window's PRT mapping")
    assert g2 < out.index(b"static void learned_add(uint64_t fault_addr) {") < out.index(b"\t\tmr412_would_learn(r.fault_addr,")
    assert out.count(b"mr412_prt_open();") == 2 and out.count(b'std::getenv("BC5_DIRECT_AMM_PRT")') == 1
    assert out.count(b"map_prt_window(") == 2, "PRT windows are mapped in mr412_prt_open only"
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
