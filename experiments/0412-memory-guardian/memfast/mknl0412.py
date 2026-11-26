#!/usr/bin/env python3
"""BC5 experiment 0412, tag nl412 (README section 61; the maintainer's order of 2026-11-13: no learned windows): the
learned path is REMOVED from the main unit, not switched.
Input: the shared unit of patch 4651d1d3 (src/libs/bc5LleAgc.cpp a81efd2c), or the integrator's candidate with one more
stderr line (30f9ef2b); nothing of exp 0412's private chain is needed.
What goes:
  - the learned file: learned_path(), learned_load() (the read), learned_add() (the window, the list, the write);
  - learned_apply(): the pass before a submission that forced the windows' chunks, mapped anonymous memory in them,
    filled their holes with the zero buffer and put 2 MiB of zero buffer behind every eager heap;
  - map_window(), have_insert(), scratch_fill(): used by that pass only. Nothing fills g_scratch any more; the two
    places that release or clear it stay (they find it empty), and scratch_bo() stays (the pin cap's cover uses it).
What stays:
  - the catcher: every GPU fault is journaled as "would learn ..." with what lay at its address, now ALWAYS (the
    switch BC5_GUARD_LEARN_LOG no longer decides it; set or not, nothing is ever added or written for a fault);
  - the alias path (BC5_DIRECT_ALIASES, alias_learn and its file) is NOT touched by this script: it is a second
    remembered list and needs its own decision;
  - BC5_GUARD_MAP_RULE and BC5_GUARD_PRT_BG keep their meaning (default off).
One line at the first submission says the path is gone.
Each anchor occurs exactly once. usage: mknl0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out> [--keep-guards]
  --keep-guards: the 2 MiB zero guard behind each eager heap (exp 0037) and scratch_fill stay; see the code's comment."""
import hashlib
import sys

T = b" // exp 0412 (tag nl412)\n"

K1 = b'''// Experiment 0412 (tag nl412): the K1 catcher, BC5_GUARD_K1_STAT=1 (default off; no behaviour changes). The rule that
// replaces the learned windows for GPU-written memory is "import exactly what the title binds, when it binds it". This
// counts how far today's hint is from that: for every new target base, was its own chunk imported at bind time, and
// how much did the +-32 MiB window around it pin.
static bool k1412_on() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_GUARD_K1_STAT");
		return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
	}();
	return on;
}
// 1: the 2 MiB chunk of the direct or private file under this guest address is imported; 0: it is under a view and
// not imported; -1: no view holds the address.
static int k1412_imported(uint64_t va) {
	for (auto& S: g_d) {
		if (dstate_fd(S) < 0) continue;
		const auto views_p = direct_views(S);
		for (const auto& v: views_p->v) {
			if (va < v.va || va >= v.va + v.size) continue;
			return direct_covered_end(S, (v.off + (va - v.va)) & ~(kDChunk - 1)) != 0 ? 1 : 0;
		}
	}
	return -1;
}
static void k1412_note(const char* name, uint64_t addr, int before, uint64_t window_bytes) {
	static uint64_t binds = 0, base_missing = 0, no_view = 0, window_total = 0, lines = 0;
	binds++;
	if (before == 0) base_missing++;
	if (before < 0) no_view++;
	window_total += window_bytes;
	if ((before == 0 || window_bytes != 0) && lines++ < 200) {
		journal("k1 stat (exp 0412, tag nl412): t %.3f s: %s base 0x%" PRIx64 " bound: its own chunk was %s; the +-32 MiB window pinned %.1f MiB more\\n", timing_now(), name, addr,
		        before > 0 ? "imported" : (before == 0 ? "NOT imported (a K1 case: the bind is what brought it in)" : "under no view"), static_cast<double>(window_bytes) / 1048576.0);
	}
	if ((binds & 63u) == 0) {
		journal("k1 stat (exp 0412, tag nl412): t %.0f s: %" PRIu64 " new target bases; own chunk not imported at the bind %" PRIu64 ", under no view %" PRIu64 "; the windows pinned %.1f MiB in all\\n",
		        timing_now(), binds, base_missing, no_view, static_cast<double>(window_total) / 1048576.0);
	}
}
'''


def cut_function(s, head, note):
    """Replace the function that starts with the line `head` (at column 0) and ends at the next "\n}\n" by a comment."""
    assert s.count(head) == 1, ("a function head does not occur exactly once", head[:60], s.count(head))
    a = s.index(head)
    assert a == 0 or s[a - 1:a] == b"\n", ("the head is not at the start of a line", head[:60])
    e = s.index(b"\n}\n", a) + 3
    body = s[a:e]
    assert body.count(b"\n}\n") == 1 and b"\nstatic " not in body[len(head):], ("the cut would take more than one function", head[:60])
    return s[:a] + b"// " + note + T + s[e:], len(body)


def once(s, old, new):
    assert s.count(old) == 1, ("an anchor does not occur exactly once", old[:70], s.count(old))
    return s.replace(old, new)


def main():
    assert len(sys.argv) in (3, 4) and sys.argv[1] != sys.argv[2], __doc__
    keep_guards = len(sys.argv) > 3 and sys.argv[3] == "--keep-guards"
    s = open(sys.argv[1], "rb").read()
    assert b"\r" not in s and b"tag mr412" in s and b"tag nl412" not in s, "refused: not the shared unit with mr412, or already edited"
    n0 = len(s)
    # The K1 catcher (DESIGN-learned-windows.md section 7, step 2; both variants): BC5_GUARD_K1_STAT=1. For every new
    # target base the hint path sees (colour, depth, stencil, HTILE) it journals whether the 2 MiB chunk AT the base
    # was imported when the title bound it, and how much the +-32 MiB window around it then pinned. A count of what the
    # guesses still cover; no behaviour changes. Default off.
    a = b"static void hint_targets(const uint32_t* ib, uint32_t num_dwords) {\n"
    s = once(s, a, K1 + a)
    a = b"\t\t\t\tconst uint64_t asked = direct_force(dlo, lo + window);\n"
    s = once(s, b"\t\t\t\tconst uint64_t dlo = lo > below ? lo - below : 0;\n" + a,
             b"\t\t\t\tconst uint64_t dlo = lo > below ? lo - below : 0;\n"
             b"\t\t\t\tconst int      k1_before = k1412_on() ? k1412_imported(lo) : -1; // exp 0412 (tag nl412)\n"
             b"\t\t\t\tconst uint64_t k1_bytes  = g_d[0].bytes + g_d[1].bytes;\n" + a +
             b"\t\t\t\tif (k1412_on()) k1412_note(b.name, addr, k1_before, g_d[0].bytes + g_d[1].bytes - k1_bytes); // exp 0412 (tag nl412)\n")
    if keep_guards:
        # The variant that keeps ONE thing of the pass, in the top session's words (2026-11-13): the 2 MiB zero guard
        # behind an eager heap is a rule from the title's behaviour (it reads up to 64 KiB past its GPU heaps' ends,
        # exp 0037), applied to every such heap from the layout, with no memory of a fault; what the maintainer rejects
        # is the remembered list. Its proper form is the K3 rule (true holes), and the guard goes when that rule is in.
        s = once(s, b"\t// Experiment 0037: the GPU reads up to 64 KiB past the end of the title's GPU heaps (four\n",
                 b"\t// exp 0412 (tag nl412): what follows is a RULE, not a learned window: it comes from the title's behaviour and is\n"
                 b"\t// applied to every eager heap from the layout, with no memory of a fault. Its proper form is the K3 rule (the\n"
                 b"\t// console's behaviour over true holes, DESIGN-learned-windows.md section 7); this guard goes when that rule is in.\n"
                 b"\t// Experiment 0037: the GPU reads up to 64 KiB past the end of the title's GPU heaps (four\n")
        s = once(s, b"\tlearned_load();\n\tif (!g_dev) return;\n\tstatic uint64_t applied_gen = 0;\n", b"\tif (!g_dev) return; // exp 0412 (tag nl412): no learned file\n\tstatic uint64_t applied_gen = 0;\n")
        s = once(s, b"\tfor (auto& S: g_d) {\n\t\tif (dstate_fd(S) >= 0) t_pinned_views[S.kind == 0 ? 0 : 1] = direct_views(S);\n\t}\n"
                    b"\tfor (const auto& [a, n]: g_learned) map_window(a, a + n, have, \"learned\", a);\n\tfor (auto& pin: t_pinned_views) pin.reset();\n",
                 b"\t// exp 0412 (tag nl412): no window is forced or mapped for a past fault\n")
        s = once(s, b"\tfor (const auto& [a, n]: g_learned) scratch_fill(a, a + n, have);\n", b"\t// exp 0412 (tag nl412): no zero buffer over a past fault's window; only the guards behind the eager heaps below\n")
        cuts = [
            (b"static const char* learned_path() {\n", b"learned_path(): removed with the learned file"),
            (b"static void learned_load() {\n", b"learned_load(): removed; no learned file is read"),
            (b"static void learned_add(uint64_t fault_addr) {\n", b"learned_add(): removed; a GPU fault adds no window and writes no file (mr412_would_learn journals it)"),
            (b"static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {\n",
             b"map_window(): removed; no window is forced or mapped for a past fault"),
        ]
    else:
      cuts = [
        (b"static const char* learned_path() {\n", b"learned_path(): removed with the learned file"),
        (b"static void learned_load() {\n", b"learned_load(): removed; no learned file is read"),
        (b"static void learned_add(uint64_t fault_addr) {\n", b"learned_add(): removed; a GPU fault adds no window and writes no file (mr412_would_learn journals it)"),
        (b"static void have_insert(std::vector<bc5::direct::Mapping>& have, bc5::direct::Mapping m) {\n", b"have_insert(): removed with map_window and scratch_fill"),
        (b"static void map_window(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have, const char* what, uint64_t addr) {\n",
         b"map_window(): removed; no window is forced or mapped for a past fault"),
        (b"static void scratch_fill(uint64_t lo, uint64_t hi, std::vector<bc5::direct::Mapping>& have) {\n",
         b"scratch_fill(): removed; no zero buffer over addresses the guest has no range at, and none behind the eager heaps"),
        (b"static void learned_apply() {\n", b"learned_apply(): removed; nothing of the learned windows runs before a submission"),
      ]
    removed = 0
    for head, note in cuts:
        s, n = cut_function(s, head, note)
        removed += n
    # the list itself
    s = once(s, b"static std::vector<std::pair<uint64_t, uint64_t>> g_learned;\n", b"// g_learned: removed with the learned windows" + T)
    # the catcher: always, and without the list
    s = once(s, b"\tif (mr412::learn_log() == 0 || fault == 0) return;\n", b"\tif (fault == 0) return; // exp 0412 (tag nl412): always; BC5_GUARD_LEARN_LOG no longer decides\n")
    s = once(s, b"\tbool           listed = false;\n\tfor (const auto& [a, b]: g_learned) {\n\t\tif (a == lo && b == 0x6000000ull) listed = true;\n\t}\n", b"")
    s = once(s, b'window 0x%" PRIx64 "+0x6000000 %s; mode %d, no file written\\n",', b'the window it would once have learned 0x%" PRIx64 "+0x6000000; nothing is added or written (tag nl412)\\n",')
    s = once(s, b'mapped ? "yes" : "no", g_mr412_bg ? "on" : "off", lo, listed ? "already on this run\'s list" : "new", mr412::learn_log());\n',
             b'mapped ? "yes" : "no", g_mr412_bg ? "on" : "off", lo);\n')
    # the fault path: no learning call
    s = once(s, b"\t\telse if (r.fault_addr != 0) learned_add(r.fault_addr);\n", b"\t\t// exp 0412 (tag nl412): no learned_add; the line above (mr412_would_learn) is all that happens for a fault\n")
    # the submit path: no pass; one line once
    a = b"\tif (!guard0412_defer_apply()) learned_apply(); // exp 0412 (tag g412): BC5_GUARD_APPLY_MIN_MS\n"
    if keep_guards:
        s = once(s, a, b"\t{ // exp 0412 (tag nl412): say once what is left of the learned pass\n"
                       b"\t\tstatic bool nl412_said = false;\n"
                       b"\t\tif (!nl412_said) {\n"
                       b"\t\t\tnl412_said = true;\n"
                       b"\t\t\tjournal(\"learned windows: removed from this build (exp 0412, tag nl412, guards kept): no file is read, no window is applied; the 2 MiB zero guard behind each eager heap stays; a GPU fault is journaled as \\\"would learn\\\" and adds nothing\\n\");\n"
                       b"\t\t}\n"
                       b"\t}\n" + a)
        for gone in (b"learned_path(", b"learned_load(", b"learned_add(", b"map_window(", b"g_learned."):
            left = [ln for ln in s.split(b"\n") if gone in ln and not ln.lstrip().startswith(b"//") and b"// " not in ln.split(gone)[0] and b'"' not in ln.split(gone)[0][-40:]]
            assert not left, ("still used", gone, left[0][:120])
        assert b"static void learned_apply() {" in s and b"scratch_fill(end, end + guard, have);" in s
        open(sys.argv[2], "wb").write(s)
        print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()} ({n0} -> {len(s)} bytes; guards kept)")
        return
    new = (b"\t{ // exp 0412 (tag nl412): the learned pass is gone; say so once\n"
           b"\t\tstatic bool nl412_said = false;\n"
           b"\t\tif (!nl412_said) {\n"
           b"\t\t\tnl412_said = true;\n"
           b"\t\t\t(void)guard0412_defer_apply();\n"
           b"\t\t\tjournal(\"learned windows: removed from this build (exp 0412, tag nl412): no file is read, no window is applied, no zero buffer fills holes or follows the eager heaps; a GPU fault is journaled as \\\"would learn\\\" and adds nothing\\n\");\n"
           b"\t\t}\n"
           b"\t}\n")
    s = once(s, a, new)
    # nothing may still call what was cut
    for gone in (b"learned_path(", b"learned_load(", b"learned_add(", b"have_insert(", b"map_window(", b"scratch_fill(", b"learned_apply(", b"g_learned."):
        left = [ln for ln in s.split(b"\n") if gone in ln and not ln.lstrip().startswith(b"//")]
        left = [ln for ln in left if b"// " not in ln.split(gone)[0] and b'"' not in ln.split(gone)[0][-40:]]
        assert not left, ("still used", gone, left[0][:120])
    assert b"static void mr412_would_learn(" in s and b"alias_learn(r.fault_addr)" in s and b"scratch_bo()" in s
    open(sys.argv[2], "wb").write(s)
    print(f"bc5LleAgc.cpp {hashlib.md5(s).hexdigest()} ({n0} -> {len(s)} bytes; {removed} bytes of seven functions cut)")


if __name__ == "__main__":
    main()
