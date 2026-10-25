#!/usr/bin/env python3
# BC5 experiment 0322: the dcb-aware ordering fix for the two-ring split of the BVH build (exps 0320, 0321). In
# src/libs/bc5LleAgc.cpp of the shared tree as integrated on the box (md5 5bccbb80). BC5_DIRECT_RING_DEPS_AWARE=1.
#   - Exp 0321 showed: "every GFX job after the compute rings' last jobs" (RING_DEPS=dcb) runs clean, a dependency only
#     for the compute buffers refused to the GFX ring does not — the title's own graphics buffers carry dispatches of the
#     RT build that read the count passes' output. So the dependency now goes to (a) a compute buffer ("acb…") submitted
#     to the GFX ring while compute rings are in use (the refused ones), and (b) a dcb in which the filter's packet walk
#     saw a dispatch (type-3 op 0x15 DISPATCH_DIRECT or 0x16 DISPATCH_INDIRECT); a draw-only dcb keeps running side by
#     side with the compute rings. As in 0321: Device::set_ring_deps(base | 2) around the submit call under g_dev_mutex
#     (exp 0129's kernel CS dependency on each compute ring's last fence), restored right after; the EFAULT retry too.
#   - The flag is a thread-local cleared at submit_now's start and set in the filter's walk (the walk that also carries
#     exp 0054's indirect-draw check); a buffer the walk did not cover counts as draw-only.
#   - Journaled once per second: dependencies by kind (refused acb / dcb with a dispatch) and the draw-only dcbs skipped,
#     in that second and in all, plus the compute-ring job and refusal counters — "ring deps (exp 0322)" lines.
# usage: patch0322.py <src root of the shared tree> <out dir>
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        ('''static int job_ring(const char* kind) {
''', 1, '''// Experiment 0322: a cross-ring dependency for the GFX-ring jobs that can read the compute rings' output — compute
// buffers on the GFX ring (exp 0290's refusal; the acb head/tail pieces) and graphics buffers that carry a dispatch —
// the job starts after every compute ring's last job (Device::set_ring_deps bit 1, exp 0129). Applied around the
// submit call only, under g_dev_mutex; draw-only dcbs run side by side with the compute rings as before.
namespace x0322 {
static bool on() {
	static const bool v = BC5_DIAG_ENV("BC5_DIRECT_RING_DEPS_AWARE") != nullptr;
	return v;
}
static int base_mask() { // BC5_DIRECT_RING_DEPS as ring_deps_env() reads it
	static const int v = [] {
		const char* e = std::getenv("BC5_DIRECT_RING_DEPS");
		if (e == nullptr) return 0;
		if (std::strcmp(e, "acb") == 0) return 1;
		if (std::strcmp(e, "dcb") == 0) return 2;
		return 3;
	}();
	return v;
}
static thread_local bool     t_dispatch = false; // the filter's walk saw a DISPATCH_DIRECT / DISPATCH_INDIRECT in this buffer
static std::atomic<uint64_t> g_dep_acb {0}, g_dep_dcb {0}, g_skip_dcb {0};
// True (and the mask set) when this submission must start after the compute rings' last jobs.
static bool arm(const char* kind, int qring) {
	if (!on() || qring != bc5::direct::kGfxRing || compute_ring_env() < 0 || !g_dev) return false;
	const bool acb = std::strncmp(kind, "acb", 3) == 0;
	const bool dcb = std::strncmp(kind, "dcb", 3) == 0;
	if (!acb && !dcb) return false;
	if (dcb && !t_dispatch) {
		g_skip_dcb.fetch_add(1, std::memory_order_relaxed);
		return false;
	}
	g_dev->set_ring_deps(base_mask() | 2);
	(acb ? g_dep_acb : g_dep_dcb).fetch_add(1, std::memory_order_relaxed);
	static double   last = 0;
	static uint64_t la = 0, ld = 0, ls = 0;
	const double    now = timing_now();
	if (now - last >= 1.0) {
		const uint64_t a = g_dep_acb.load(), d = g_dep_dcb.load(), s = g_skip_dcb.load();
		journal("ring deps (exp 0322): in the last %.1f s %" PRIu64 " compute buffers on the GFX ring and %" PRIu64 " dcbs with a dispatch given the compute rings' last jobs as dependencies, %" PRIu64 " draw-only dcbs skipped (in all %" PRIu64 " / %" PRIu64 " / %" PRIu64 "; %" PRIu64 " compute-ring jobs, %" PRIu64 " refusals so far)\\n",
		        last == 0 ? 0.0 : now - last, a - la, d - ld, s - ls, a, d, s, g_comp_jobs.load(), g_comp_refused.load());
		last = now;
		la = a; ld = d; ls = s;
	}
	return true;
}
static void disarm() {
	if (g_dev) g_dev->set_ring_deps(base_mask());
}
} // namespace x0322
static int job_ring(const char* kind) {
'''),
        ('''	const int qring = ring; // ADR 0009: the compute ring takes the MEC form as it is
''', 1, '''	const int qring = ring; // ADR 0009: the compute ring takes the MEC form as it is
	x0322::t_dispatch = false; // experiment 0322: set by the filter's walk below when this buffer carries a dispatch
'''),
        ('''			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
''', 1, '''			if (type == 3 && (op == 0x15 || op == 0x16)) x0322::t_dispatch = true; // experiment 0322: this buffer dispatches
			if (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054
'''),
        ('''	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
''', 1, '''	const bool dep0322 = x0322::arm(kind, qring); // experiment 0322: this job waits for the compute rings
	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	if (dep0322) x0322::disarm();
	mec_back(r.executed_offsets);
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
'''),
        ('''		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
		mec_back(r.executed_offsets);
	}
''', 1, '''		const bool dep0322r = x0322::arm(kind, qring); // experiment 0322: the retry keeps the dependency
		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
		if (dep0322r) x0322::disarm();
		mec_back(r.executed_offsets);
	}
'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0322.py <src root> <out dir>')
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    diff = []
    for rel, edits in EDITS.items():
        path = os.path.join(root, rel)
        src = open(path, encoding='utf-8').read()
        print(f'{rel}: md5 {hashlib.md5(src.encode("utf-8")).hexdigest()[:8]} in')
        dst = src
        for k, (old, n, new) in enumerate(edits, 1):
            c = dst.count(old)
            if c != n:
                print(f'{rel}: edit {k}: anchor found {c} times, expected {n}:\n{old}')
                sys.exit(1)
            dst = dst.replace(old, new)
        target = os.path.join(out, os.path.basename(rel))
        open(target, 'w', encoding='utf-8', newline='\n').write(dst)
        diff += difflib.unified_diff(src.splitlines(True), dst.splitlines(True), 'a/' + rel, 'b/' + rel)
        print(f'{rel}: {len(edits)} edits -> {target}, md5 {hashlib.md5(dst.encode("utf-8")).hexdigest()[:8]} out')
    open(os.path.join(out, 'patch_0322.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0322.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
