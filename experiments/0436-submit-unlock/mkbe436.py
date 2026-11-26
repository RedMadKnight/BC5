# BC5 experiment 0436 (tag su436): the backend half of the candidate, applied to backend/src/direct.cpp as on main
# (52f74d0e, the source of the shared archive's direct.cpp.o). Run once on a clean copy:
#   python -I mkbe436.py <path to direct.cpp>
# Every replacement must match exactly once, or nothing is written.
import sys

p = sys.argv[1]
s = open(p, encoding="utf-8", newline="").read()


def rep(old, new, count=1):
    global s
    n = s.count(old)
    assert n == count, (old[:70], n)
    s = s.replace(old, new)


rep("#include <mutex>\n", "#include <mutex>\n#include <shared_mutex>\n")
rep("""    std::mutex mutex;
    // Device::sorted_mappings: the sorted list""", """    std::mutex mutex;
    // Experiment 0436 (tag su436): held shared by a job of submit(..., before_call) from before its prepare to the end
    // of its bookkeeping, across the kernel call made without `mutex`; taken exclusively, before `mutex`, by every
    // removal of a mapping or BO (unmap_userptr, unmap_shared, unmap_aliases, free_shared, the destructor). Order:
    // flight_mu, then mutex. Nobody waits for the host's locks while holding it.
    std::shared_mutex flight_mu;
    // Experiment 0436: the kept BO lists named by a job between its prepare and its kernel call's return; a list
    // replaced meanwhile (another job's new full list) is destroyed by its last user, not at once.
    std::map<amdgpu_bo_list_handle, int> list_users;
    void list_drop(amdgpu_bo_list_handle h) {
        if (h != nullptr && list_users.count(h) == 0) amdgpu_bo_list_destroy(h);
    }
    // Device::sorted_mappings: the sorted list""")
rep("""    void snap_commit(std::uint64_t seq) {
        if (snap_job.empty()) return;
        std::erase_if(snap_spans, [this](const SnapSpan &x) { return !snap_in_flight(x); });
        for (const auto &[x0, x1] : snap_job) snap_spans.push_back({x0, x1, cur, seq});
        snap_job.clear();
    }""", """    // exp 0436: the job's spans and slot are passed in (with the kernel call outside the lock, another ring's job may
    // have been prepared since: `cur` and snap_job are no longer this job's)
    void snap_commit(std::uint64_t seq, int slot, std::vector<std::pair<std::uint64_t, std::uint64_t>> &job) {
        if (job.empty()) return;
        std::erase_if(snap_spans, [this](const SnapSpan &x) { return !snap_in_flight(x); });
        for (const auto &[x0, x1] : job) snap_spans.push_back({x0, x1, slot, seq});
        job.clear();
    }""")
rep("""    impl_->summary(); // experiment 0341
    if (impl_->full_list) amdgpu_bo_list_destroy(impl_->full_list);""", """    std::unique_lock<std::shared_mutex> flight(impl_->flight_mu); // exp 0436: no job of submit() is in its kernel call
    impl_->summary(); // experiment 0341
    impl_->list_drop(impl_->full_list);""")
FX = "    std::unique_lock<std::shared_mutex> flight(impl_->flight_mu); // exp 0436 (tag su436): after every prepared job's kernel call\n"
for sig in ("bool Device::unmap_userptr(std::uint64_t cpu_va) {\n", "bool Device::unmap_shared(std::uint64_t gpu_va) {\n",
            "void Device::unmap_aliases() {\n", "bool Device::free_shared(std::uint32_t id) {\n"):
    rep(sig + "    std::lock_guard lock(impl_->mutex);\n", sig + FX + "    std::lock_guard lock(impl_->mutex);\n")
rep("""        if (impl_->full_list) {
            amdgpu_bo_list_destroy(impl_->full_list);
            impl_->full_list = nullptr;
        }""", """        if (impl_->full_list) {
            impl_->list_drop(impl_->full_list); // exp 0436: no job can hold it here (flight_mu is ours)
            impl_->full_list = nullptr;
        }""")
rep("""SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns, bool with_gds, int ring) {
    SubmitResult r;
    std::lock_guard lock(impl_->mutex);""", """SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns, bool with_gds, int ring) {
    return submit_impl(ib, opt, timeout_ns, with_gds, ring, nullptr);
}

SubmitResult Device::submit(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                            std::uint64_t timeout_ns, bool with_gds, int ring, const std::function<void()> &before_call) {
    return submit_impl(ib, opt, timeout_ns, with_gds, ring, &before_call);
}

SubmitResult Device::submit_impl(std::span<const std::uint32_t> ib, const policy::FilterOptions &opt,
                                 std::uint64_t timeout_ns, bool with_gds, int ring,
                                 const std::function<void()> *before_call) {
    SubmitResult r;
    // Experiment 0436 (tag su436): with before_call in async mode the kernel call runs without `mutex` (see direct.hpp).
    const bool split = before_call != nullptr && async_;
    std::shared_lock<std::shared_mutex> flight;
    if (split) flight = std::shared_lock<std::shared_mutex>(impl_->flight_mu);
    std::unique_lock lock(impl_->mutex);""")
rep("""    impl_->slot_ring[impl_->cur] = ring;
    const double t_enter = now_ms();""", """    impl_->slot_ring[impl_->cur] = ring;
    const int cur = impl_->cur; // exp 0436: this job's slot (impl_->cur moves on with another ring's job once the lock is let go)
    const double t_enter = now_ms();""")
rep("""        if (r.rc == 0 && full) {
            if (impl_->full_list) amdgpu_bo_list_destroy(impl_->full_list);""", """        if (r.rc == 0 && full) {
            impl_->list_drop(impl_->full_list); // exp 0436: one a job still uses in its kernel call is destroyed by it""")
rep("""    r.list_ms = now_ms() - t_list;
    if (r.rc != 0) return r;
""", """    r.list_ms = now_ms() - t_list;
    if (r.rc != 0) return r;
    // exp 0436: the kept list this job uses stays alive until its kernel call has returned
    const bool list_held = split && list != nullptr && list == impl_->full_list;
    if (list_held) impl_->list_users[list]++;
    auto list_done = [&]() {
        if (list_held) {
            auto it = impl_->list_users.find(list);
            if (--it->second == 0) {
                impl_->list_users.erase(it);
                if (list != impl_->full_list) amdgpu_bo_list_destroy(list); // replaced meanwhile: its last user
            }
        } else if (list != impl_->full_list) {
            amdgpu_bo_list_destroy(list);
        }
    };
""")
rep("""    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    if (r.rc == 0) impl_->hi_reg = hi_next; // experiment 0348: the CP's base-1 register as this job leaves it""",
    """    std::vector<std::pair<std::uint64_t, std::uint64_t>> snap_mine; // exp 0436: this job's DMA snapshot spans
    snap_mine.swap(impl_->snap_job);
    if (split) { // exp 0436 (tag su436): the kernel call without the lock; the caller keeps this ring's order
        lock.unlock();
        (*before_call)();
    }
    const double t0 = now_ms();
    r.rc = amdgpu_cs_submit(impl_->ctx, 0, &req, 1);
    if (split) lock.lock();
    // experiment 0348: the CP's base-1 register as this job leaves it; a compute job never changes it (exp 0436: and
    // must not write back the value it read before a GFX job's kernel call outside the lock)
    if (r.rc == 0 && !comp) impl_->hi_reg = hi_next;""")
rep("""        r.slot = static_cast<std::uint32_t>(impl_->cur);
        r.pending = r.rc == 0;
        if (r.pending) {
            if (!da_recs.empty()) impl_->da_pending[impl_->cur] = std::move(da_recs); // experiment 0381, read in finish()
            impl_->slot_seq[impl_->cur] = req.seq_no;
            (comp ? impl_->last_seq_comp[ring] : impl_->last_seq) = req.seq_no;
            impl_->snap_commit(req.seq_no); // experiment 0122
        }
        r.submit_ms = now_ms() - t0;
        if (list != impl_->full_list) amdgpu_bo_list_destroy(list);""", """        r.slot = static_cast<std::uint32_t>(cur);
        r.pending = r.rc == 0;
        if (r.pending) {
            if (!da_recs.empty()) impl_->da_pending[cur] = std::move(da_recs); // experiment 0381, read in finish()
            impl_->slot_seq[cur] = req.seq_no;
            (comp ? impl_->last_seq_comp[ring] : impl_->last_seq) = req.seq_no;
            impl_->snap_commit(req.seq_no, cur, snap_mine); // experiment 0122
        }
        r.submit_ms = now_ms() - t0;
        list_done();""")
rep("""    r.fence_ms = r.submit_ms - r.cs_ms;
    if (list != impl_->full_list) amdgpu_bo_list_destroy(list);""", """    r.fence_ms = r.submit_ms - r.cs_ms;
    list_done();""")
open(p, "w", encoding="utf-8", newline="").write(s)
print("mkbe436: ok")
