# BC5 experiment 0436 (tag su436): the host half of the candidate, applied to src/libs/bc5LleAgc.cpp of patch 8986853b
# (the unit as the shared tree has it). Run once on a clean copy:
#   python -I mkhost436.py <path to bc5LleAgc.cpp>
# Switch BC5_DIRECT_SUBMIT_UNLOCK, read in normal and lean: "0" = off (the shared behaviour: the same calls under the
# same locks); unset or anything else = on, in this TEST build only, so that the candidate's arm is its binary and no
# launcher word can be lost on the way (LESSONS R66). Every replacement must match exactly once, or nothing is written.
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old[:70], n)
    s = s.replace(old, new)


rep("""static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) {
		return;
	}
	const int qring = ring;""", """// Experiment 0436 (tag su436): BC5_DIRECT_SUBMIT_UNLOCK (on in this test build unless "0"), the kernel submit (DRM_IOCTL_AMDGPU_CS) outside the device
// mutex (exp 0432 note 8). A job is prepared under g_dev_mutex as before (probe, syncs, ud434's imports, hints, the
// backend's prepare); for the CS ioctl alone the backend lets its own lock go and calls back here to let g_dev_mutex go,
// then the device mutex is taken again for everything after the call (EFAULT retry, label writes, ho430's job record,
// the completion queue), so all of that keeps its order relative to the call. The jobs of one ring keep their order
// through a lock per ring (GFX, compute 0-3), taken before g_dev_mutex and held to the end of submit_now: the same ring's
// next job cannot be prepared before this one is in the kernel and recorded. A chain's F10 flight set is cleared after
// submit_now returns, as before, so F10/F16/F18 see the writer in flight for the whole time. Mapping removals wait in
// the backend until no prepared job is in its kernel call (flight lock), so the mappings a job was prepared against are
// still there when the kernel takes it. Async mode only (g_async); off, nothing changes.
static bool su436_on() {
	static const bool v = [] {
		const char* e  = std::getenv("BC5_DIRECT_SUBMIT_UNLOCK"); // the test build: on unless "0" (the candidate's arm is the binary)
		const bool  on = e == nullptr || e[0] == 0 || bc5::env_on(e);
		std::fprintf(stderr, "[bc5] exp 0436 (tag su436): BC5_DIRECT_SUBMIT_UNLOCK %s: the kernel submit runs %s the device mutex\\n", on ? "ON" : "off",
		             on ? "outside" : "inside");
		return on;
	}();
	return v;
}
static std::mutex            g_su436_ring_mu[bc5::direct::kComputeRings + 1]; // [kComputeRings] is the GFX ring
#ifndef BC5_LEAN
static std::atomic<uint64_t> g_su436_calls {0}; // kernel calls made outside the device mutex (normal build only)
#endif

static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, int ring, const Chain* chain) {
	if (g_stage == Stage::Off || !g_dev || ib == nullptr || num_dwords == 0) {
		return;
	}
	const int qring = ring;""")
rep("""	if (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(2); // exp 0430 F16: past the back-pressure, asking for the device
	const uint64_t  fs_ask = fs415_file() != nullptr ? SoftCp::now_ns() : 0; // experiment 0415 (fs415b)
	std::lock_guard lock(g_dev_mutex);""", """	if (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(2); // exp 0430 F16: past the back-pressure, asking for the device
	const uint64_t  fs_ask = fs415_file() != nullptr ? SoftCp::now_ns() : 0; // experiment 0415 (fs415b)
	// exp 0436 (tag su436): this ring's order, before the device mutex (lock order: ring, g_dev_mutex, backend)
	const bool su = su436_on() && g_async && (qring == bc5::direct::kGfxRing || (qring >= 0 && qring < bc5::direct::kComputeRings));
	std::unique_lock<std::mutex> su_ring;
	if (su) su_ring = std::unique_lock<std::mutex>(g_su436_ring_mu[qring == bc5::direct::kGfxRing ? bc5::direct::kComputeRings : qring]);
	std::unique_lock<std::mutex> lock(g_dev_mutex);""")
rep("""	const uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)
	auto r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
""", """	const uint64_t ls_t3 = SoftCp::now_ns(); // experiment 0415 (ls415c)
	bc5::direct::SubmitResult r;
	if (su) { // exp 0436 (tag su436): the backend calls back before the CS ioctl; the device mutex is taken again after it
		bool                        let_go = false;
		const std::function<void()> unlock_dev = [&lock, &let_go] {
			lock.unlock();
			let_go = true;
		};
		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring, unlock_dev);
		if (!lock.owns_lock()) lock.lock();
#ifndef BC5_LEAN
		if (let_go) {
			const uint64_t k = g_su436_calls.fetch_add(1);
			if (k == 0 || (k & 0x3ffffu) == 0) std::fprintf(stderr, "[bc5] exp 0436 (tag su436): %" PRIu64 " kernel submits made outside the device mutex so far\\n", k + 1);
		}
#else
		(void)let_go;
#endif
	} else {
		r = g_dev->submit(std::span<const uint32_t>(sub_ib, sub_n), opt, 2'000'000'000ull, true, qring);
	}
""")
if "#include <functional>" not in s:
    rep("#include <algorithm>\n", "#include <algorithm>\n#include <functional> // exp 0436 (tag su436)\n")
open(p, "w", encoding="utf-8", newline="").write(s)
print("mkhost436: ok")
