#!/usr/bin/env python3
# BC5 exp 0439 (tag fn439, the top session's "fences" of 11-23 ~21:20): the backend half of the kernel-submit record, on
# direct.cpp after mksr439cbe. Diagnosis only, normal and lean alike but inert unless BC5_0439_FN_RECORD=1 (one static
# test per submit). Each kernel submit (amdgpu_cs_submit) is recorded: GFX or compute, the libdrm ring index, the rc,
# the returned fence (seq_no; the libdrm amdgpu_cs_fence kept whole), every IB's GPU address and size, and the CS
# dependencies passed (ip, ring, seq). extern "C" bc5_fn439_write(path) writes the last 1024 records with each fence's
# status queried now without waiting (amdgpu_cs_query_fence_status, timeout 0: "signaled" or "pending"). The IB
# addresses let the kernel's devcoredump ring contents (INDIRECT_BUFFER packets of the hardware ring) be matched to our
# jobs: which hardware compute ring each job was queued on, without root.
#   python mkfn439be.py <direct.cpp>   (in place; every anchor exactly once)
import sys

p = sys.argv[1]
s = open(p, 'rb').read().decode('utf-8')
assert '\r' not in s and 'fn439' not in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''#include <cstdlib>
''', '''#include <cstdlib>
namespace { // exp 0439 (tag fn439): the kernel-submit record
struct Fn439Rec {
    std::uint64_t   t_ns = 0, seq = 0, rt_ns = 0;
    int             comp = 0, ring = 0, rc = 0;
    std::uint32_t   n_ibs = 0, n_deps = 0;
    std::uint64_t   ib_va[4] = {};
    std::uint32_t   ib_dw[4] = {};
    amdgpu_cs_fence dep[8] = {};
    amdgpu_cs_fence fence = {};
};
std::mutex      g_fn439_mu;
Fn439Rec        g_fn439[1024];
std::uint64_t   g_fn439_n = 0;
bool fn439_on() {
    static const bool v = [] {
        const char *e = std::getenv("BC5_0439_FN_RECORD");
        return e != nullptr && e[0] == '1' && e[1] == 0;
    }();
    return v;
}
std::uint64_t fn439_now() { return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
std::uint64_t fn439_rt() { return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::system_clock::now().time_since_epoch()).count()); }
struct Fn439Va { // a GEM VA operation of ours (map, unmap, replace, clear), as passed to the kernel
    std::uint64_t rt_ns = 0, offset = 0, size = 0, addr = 0, flags = 0, k = 0;
    std::uint32_t ops = 0;
    int           rc = 0;
    const void   *bo = nullptr;
};
Fn439Va         g_fn439_va[4096];
std::uint64_t   g_fn439_nva = 0;
int fn439_va_op(amdgpu_device_handle dev, amdgpu_bo_handle bo, std::uint64_t offset, std::uint64_t size, std::uint64_t addr, std::uint64_t flags, std::uint32_t ops) {
    const int rc = amdgpu_bo_va_op_raw(dev, bo, offset, size, addr, flags, ops);
    if (fn439_on()) {
        std::lock_guard<std::mutex> fl(g_fn439_mu);
        Fn439Va &v = g_fn439_va[g_fn439_nva++ % 4096];
        v = Fn439Va{};
        v.rt_ns = fn439_rt(), v.offset = offset, v.size = size, v.addr = addr, v.flags = flags, v.ops = ops, v.rc = rc, v.bo = bo, v.k = g_fn439_n;
    }
    return rc;
}
} // namespace
#define amdgpu_bo_va_op_raw fn439_va_op // exp 0439 (tag fn439): every VA op of this file is recorded (the call above is before it)
// exp 0439 (tag fn439): the last 1024 kernel submits with their fences' status now; 0, or -1 when off or the file fails
extern "C" int bc5_fn439_write(const char *path) {
    if (!fn439_on() || path == nullptr) return -1;
    FILE *f = std::fopen(path, "w");
    if (f == nullptr) return -1;
    std::lock_guard<std::mutex> lk(g_fn439_mu);
    const std::uint64_t now = fn439_now();
    std::fprintf(f, "# exp 0439 (tag fn439): kernel submits, oldest first: n ip ring(libdrm) seq rc ms_ago realtime status | IBs va:dwords | deps ip/ring/seq\\n");
    for (std::uint64_t k = g_fn439_n > 1024 ? g_fn439_n - 1024 : 0; k < g_fn439_n; ++k) {
        Fn439Rec &r = g_fn439[k % 1024];
        std::uint32_t expired = 0;
        const char   *st = "not-submitted";
        if (r.rc == 0) {
            const int q = amdgpu_cs_query_fence_status(&r.fence, 0, 0, &expired);
            st = q != 0 ? "query-failed" : (expired != 0 ? "signaled" : "pending");
        }
        std::fprintf(f, "%llu %s %d %llu %d %.1f %llu.%09llu %s |", static_cast<unsigned long long>(k), r.comp ? "comp" : "gfx", r.ring, static_cast<unsigned long long>(r.seq), r.rc,
                     static_cast<double>(now - r.t_ns) / 1e6, static_cast<unsigned long long>(r.rt_ns / 1000000000ull), static_cast<unsigned long long>(r.rt_ns % 1000000000ull), st);
        for (std::uint32_t i = 0; i < r.n_ibs && i < 4; ++i) std::fprintf(f, " 0x%llx:%u", static_cast<unsigned long long>(r.ib_va[i]), r.ib_dw[i]);
        std::fprintf(f, " |");
        for (std::uint32_t i = 0; i < r.n_deps && i < 8; ++i) std::fprintf(f, " %u/%u/%llu", r.dep[i].ip_type, r.dep[i].ring, static_cast<unsigned long long>(r.dep[i].fence));
        std::fprintf(f, "\\n");
    }
    std::fprintf(f, "# VA operations, oldest first: realtime op(1 map 2 unmap 3 clear 4 replace) addr size offset flags bo rc after_submit_n\\n");
    for (std::uint64_t k = g_fn439_nva > 4096 ? g_fn439_nva - 4096 : 0; k < g_fn439_nva; ++k) {
        const Fn439Va &v = g_fn439_va[k % 4096];
        std::fprintf(f, "va %llu.%09llu %u 0x%llx 0x%llx 0x%llx 0x%llx %p %d %llu\\n", static_cast<unsigned long long>(v.rt_ns / 1000000000ull), static_cast<unsigned long long>(v.rt_ns % 1000000000ull), v.ops,
                     static_cast<unsigned long long>(v.addr), static_cast<unsigned long long>(v.size), static_cast<unsigned long long>(v.offset), static_cast<unsigned long long>(v.flags), v.bo, v.rc,
                     static_cast<unsigned long long>(v.k));
    }
    std::fclose(f);
    return 0;
}
''')
rep('''    r.seq_no = req.seq_no;
    if (async_) {''', '''    r.seq_no = req.seq_no;
    if (fn439_on()) { // exp 0439 (tag fn439): this submit, as the kernel got it
        std::lock_guard<std::mutex> fl(g_fn439_mu);
        Fn439Rec &x = g_fn439[g_fn439_n++ % 1024];
        x = Fn439Rec{};
        x.t_ns = fn439_now();
        x.rt_ns = fn439_rt();
        x.seq = req.seq_no;
        x.comp = comp ? 1 : 0;
        x.ring = ring;
        x.rc = r.rc;
        x.n_ibs = n_ibs;
        for (std::uint32_t i = 0; i < n_ibs && i < 4; ++i) {
            x.ib_va[i] = ib_info[i].ib_mc_address;
            x.ib_dw[i] = ib_info[i].size;
        }
        x.n_deps = n_deps;
        for (std::uint32_t i = 0; i < n_deps && i < 8; ++i) x.dep[i] = deps[i];
        if (r.rc == 0) x.fence = impl_->fence_of(ring, req.seq_no);
    }
    if (async_) {''')
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('mkfn439be: patched', p)
