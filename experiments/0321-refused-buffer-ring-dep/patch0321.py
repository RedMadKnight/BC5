#!/usr/bin/env python3
# BC5 experiment 0321: the ordering fix for the two-ring split of the BVH build (exp 0320) — a cross-ring dependency for
# each compute buffer refused to the GFX ring. In src/libs/bc5LleAgc.cpp of the shared tree as integrated on the box
# (md5 5bccbb80). BC5_DIRECT_RING_DEPS_REFUSED=1.
#   - A compute buffer ("acb…" kind) that is submitted to the GFX ring while compute rings are in use
#     (BC5_DIRECT_COMPUTE_RING >= 0) is there because exp 0290's refusal kept it off the compute ring (or because the acb
#     head/tail logic put a piece there). Right before its submission — under g_dev_mutex, which submit_now holds — the
#     device's ring-dependency mask is set to "GFX after the compute rings' last jobs" (Device::set_ring_deps(2), exp
#     0129's kernel CS dependency on each compute ring's last fence: the scheduler starts the job after them, no CPU
#     wait), and restored to BC5_DIRECT_RING_DEPS's value right after the submit call (both call sites: the first and
#     the EFAULT retry). Every other job keeps the default (no dependency): the title's dcbs and the compute-ring chains
#     run side by side as before, so the overlap exp 0129 measured stays for them.
#   - Journaled once per second: how many refused buffers took the dependency in that second and in all, and the
#     compute-ring job count — "ring deps (exp 0321)" lines.
# usage: patch0321.py <src root of the shared tree> <out dir>
import difflib, hashlib, os, sys

EDITS = {
    'src/libs/bc5LleAgc.cpp': [
        ('''static int job_ring(const char* kind) {
''', 1, '''// Experiment 0321: a cross-ring dependency for each compute buffer that runs on the GFX ring while the compute rings
// are in use (exp 0290's refusal; the acb head/tail pieces) — the GFX job starts after every compute ring's last job
// (Device::set_ring_deps bit 1, exp 0129). Applied around the submit call only, under g_dev_mutex.
namespace x0321 {
static bool on() {
	static const bool v = BC5_DIAG_ENV("BC5_DIRECT_RING_DEPS_REFUSED") != nullptr;
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
static std::atomic<uint64_t> g_deps {0};
// True (and the mask set) when this submission is a compute buffer on the GFX ring with compute rings in use.
static bool arm(const char* kind, int qring) {
	if (!on() || std::strncmp(kind, "acb", 3) != 0 || qring != bc5::direct::kGfxRing || compute_ring_env() < 0 || !g_dev) return false;
	g_dev->set_ring_deps(base_mask() | 2);
	const uint64_t n = g_deps.fetch_add(1, std::memory_order_relaxed) + 1;
	static double   last = 0;
	static uint64_t last_n = 0;
	const double    now = timing_now();
	if (now - last >= 1.0) {
		journal("ring deps (exp 0321): %" PRIu64 " compute buffers on the GFX ring given the compute rings' last jobs as dependencies in the last %.1f s (%" PRIu64 " in all; %" PRIu64 " compute-ring jobs, %" PRIu64 " refusals so far)\\n",
		        n - last_n, last == 0 ? 0.0 : now - last, n, g_comp_jobs.load(), g_comp_refused.load());
		last   = now;
		last_n = n;
	}
	return true;
}
static void disarm() {
	if (g_dev) g_dev->set_ring_deps(base_mask());
}
} // namespace x0321
static int job_ring(const char* kind) {
'''),
        ('''	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	mec_back(r.executed_offsets);
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
''', 1, '''	const bool dep0321 = x0321::arm(kind, qring); // experiment 0321: the refused buffer waits for the compute rings
	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
	if (dep0321) x0321::disarm();
	mec_back(r.executed_offsets);
	if (qring != bc5::direct::kGfxRing && (g_comp_jobs++ & 0xffffu) == 0) {
'''),
        ('''		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
		mec_back(r.executed_offsets);
	}
''', 1, '''		const bool dep0321r = x0321::arm(kind, qring); // experiment 0321: the retry keeps the dependency
		r       = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, with_gds, qring);
		if (dep0321r) x0321::disarm();
		mec_back(r.executed_offsets);
	}
'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0321.py <src root> <out dir>')
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
    open(os.path.join(out, 'patch_0321.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0321.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
