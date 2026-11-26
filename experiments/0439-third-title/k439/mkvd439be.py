#!/usr/bin/env python3
# BC5 exp 0439 (tag va439, the top session's order of 11-23 ~21:45): the deferred GPU unmap, on direct.cpp after
# mkfn439be. A private test arm, inert unless BC5_0439_VA_DEFER=1.
# Why (fn2 and k0, records bc5-private/rb-1123): a GEM VA unmap makes the kernel's page-table clear sync to every job of
# the VM still in flight (amdgpu_vm_clear_freed: amdgpu_sync_resv on the VM root's reservation, AMDGPU_SYNC_EQ_OWNER),
# and every later command submission syncs to that update (amdgpu_cs_vm_handling: vm->last_update) — torvalds master as
# read on 11-23, to be checked against the box's kernel. One unmap while a GFX job with kept piece waits runs (K1R's
# cover drop in fn2, a 16 KiB private page in k0) held every later compute job, the releaser of the GFX wait included.
# On the console a mapping never orders jobs.
# The arm: Impl::va_unmap, while the last GFX job is not signalled (amdgpu_cs_query_fence_status, timeout 0), keeps the
# unmap (and a BO free that follows it, through vd439_free) and returns 0; the kept unmaps are issued when no GFX job is
# in flight (checked at each submit), or at once when a new mapping would overlap one (va_map). Counts on stderr.
#   python mkvd439be.py <direct.cpp>   (in place; every anchor exactly once)
import sys

p = sys.argv[1]
s = open(p, 'rb').read().decode('utf-8')
assert '\r' not in s and 'vd439' not in s and 'fn439' in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''    int va_map(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va, std::uint64_t flags) {
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, flags, in_prt(va, size) ? AMDGPU_VA_OP_REPLACE : AMDGPU_VA_OP_MAP);
    }
    int va_unmap(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va) {
        if (in_prt(va, size)) return amdgpu_bo_va_op_raw(dev, nullptr, 0, size, va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_REPLACE);
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, 0, AMDGPU_VA_OP_UNMAP);
    }''', '''    int va_map(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va, std::uint64_t flags) {
        vd439_flush_overlap(va, size); // exp 0439 (tag va439): a kept unmap of this range goes first
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, flags, in_prt(va, size) ? AMDGPU_VA_OP_REPLACE : AMDGPU_VA_OP_MAP);
    }
    int va_unmap_now(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va) {
        if (in_prt(va, size)) return amdgpu_bo_va_op_raw(dev, nullptr, 0, size, va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_REPLACE);
        return amdgpu_bo_va_op_raw(dev, bo, offset, size, va, 0, AMDGPU_VA_OP_UNMAP);
    }
    // exp 0439 (tag va439): BC5_0439_VA_DEFER=1, the unmap kept while a GFX job is in flight
    struct Vd439 {
        amdgpu_bo_handle bo = nullptr;
        std::uint64_t    offset = 0, size = 0, va = 0;
    };
    std::vector<Vd439>            vd439_unmaps;
    std::vector<amdgpu_bo_handle> vd439_frees;
    std::uint64_t                 vd439_kept = 0, vd439_issued = 0, vd439_overlap = 0, vd439_freed = 0;
    static bool vd439_on() {
        static const bool v = [] {
            const char *e = std::getenv("BC5_0439_VA_DEFER");
            const bool  b = e != nullptr && e[0] == '1' && e[1] == 0;
            std::fprintf(stderr, "bc5-direct: exp 0439 (tag va439): GPU unmaps while a GFX job is in flight %s\\n", b ? "KEPT until it ends (BC5_0439_VA_DEFER=1)" : "issued at once");
            return b;
        }();
        return v;
    }
    bool vd439_gfx_busy() const {
        const std::uint64_t q = last_seq.load();
        if (q == 0) return false;
        amdgpu_cs_fence f = fence_of(kGfxRing, q);
        std::uint32_t   expired = 0;
        return amdgpu_cs_query_fence_status(&f, 0, 0, &expired) == 0 && expired == 0;
    }
    void vd439_report(const char *what) {
        const std::uint64_t n = vd439_kept + vd439_overlap;
        if (n <= 8 || (n & 0x3ffu) == 0)
            std::fprintf(stderr, "bc5-direct: exp 0439 (tag va439): %s; %llu unmaps kept so far, %llu issued later, %llu issued at once for an overlapping map, %llu BO frees deferred, %zu waiting\\n", what,
                         static_cast<unsigned long long>(vd439_kept), static_cast<unsigned long long>(vd439_issued), static_cast<unsigned long long>(vd439_overlap),
                         static_cast<unsigned long long>(vd439_freed), vd439_unmaps.size());
    }
    void vd439_free_ready() { // the BOs whose kept unmaps have all been issued
        for (std::size_t i = 0; i < vd439_frees.size();) {
            const amdgpu_bo_handle b = vd439_frees[i];
            bool                   used = false;
            for (const auto &u : vd439_unmaps) used = used || u.bo == b;
            if (used) { ++i; continue; }
            amdgpu_bo_free(b);
            vd439_frees.erase(vd439_frees.begin() + static_cast<std::ptrdiff_t>(i));
        }
    }
    void vd439_flush_idle() { // at each submit: the kept unmaps go when no GFX job is in flight
        if (vd439_unmaps.empty() || vd439_gfx_busy()) return;
        for (const auto &u : vd439_unmaps) va_unmap_now(u.bo, u.offset, u.size, u.va);
        vd439_issued += vd439_unmaps.size();
        vd439_unmaps.clear();
        vd439_free_ready();
    }
    void vd439_flush_overlap(std::uint64_t va, std::uint64_t size) {
        if (vd439_unmaps.empty()) return;
        bool any = false;
        for (std::size_t i = 0; i < vd439_unmaps.size();) {
            const Vd439 u = vd439_unmaps[i];
            if (u.va < va + size && va < u.va + u.size) {
                va_unmap_now(u.bo, u.offset, u.size, u.va);
                vd439_unmaps.erase(vd439_unmaps.begin() + static_cast<std::ptrdiff_t>(i));
                vd439_overlap++;
                any = true;
                continue;
            }
            ++i;
        }
        if (any) {
            vd439_free_ready();
            vd439_report("a new mapping overlapped a kept unmap: issued at once");
        }
    }
    int va_unmap(amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t va) {
        if (vd439_on() && vd439_gfx_busy()) {
            vd439_unmaps.push_back({bo, offset, size, va});
            vd439_kept++;
            vd439_report("an unmap kept while a GFX job is in flight");
            return 0;
        }
        return va_unmap_now(bo, offset, size, va);
    }
    void vd439_free(amdgpu_bo_handle b) { // a BO free after va_unmap: deferred while one of its unmaps is kept
        for (const auto &u : vd439_unmaps)
            if (u.bo == b) {
                vd439_frees.push_back(b);
                vd439_freed++;
                return;
            }
        amdgpu_bo_free(b);
    }''')
rep('''            impl_->va_unmap(it->bo, 0, it->size, it->va);
            amdgpu_bo_free(it->bo);''', '''            impl_->va_unmap(it->bo, 0, it->size, it->va);
            impl_->vd439_free(it->bo); // exp 0439 (tag va439)''')
rep('''        amdgpu_bo_free(b->bo);
        impl_->shared.erase(b);''', '''        impl_->vd439_free(b->bo); // exp 0439 (tag va439)
        impl_->shared.erase(b);''')
rep('''    std::unique_lock lock(impl_->mutex);
    const bool comp = ring != kGfxRing;''', '''    std::unique_lock lock(impl_->mutex);
    if (Impl::vd439_on()) impl_->vd439_flush_idle(); // exp 0439 (tag va439)
    const bool comp = ring != kGfxRing;''')
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('mkvd439be: patched', p)
