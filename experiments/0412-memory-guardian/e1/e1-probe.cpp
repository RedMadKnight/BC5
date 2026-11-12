// SPDX-License-Identifier: GPL-2.0-only
// e1-probe: BC5 experiment 0412, E1 (E1-plan.md): what gfx1013 does at a page without backing.
//
//   e1-probe --dump-ib <prefix>           write <prefix>-clear.bin and <prefix>-copy.bin (placeholder VAs); no GPU
//   e1-probe --submit --case N [--render-node PATH]      one case, one process (needs BC5_WITH_AMDGPU)
//     0 control           clear `real`, copy `real` -> `out`
//     1 PRT read          copy `prt` -> `out`
//     2 read-only read    copy `zero` (mapped readable only) -> `out`
//     3 PRT write         clear `prt`; then case 0's jobs in a new context
//     4 read-only write   clear `zero`; then case 0's jobs in a new context
//
// Hard rule 5 (CLAUDE.md): --submit runs shaders on the GPU (GFX ring) and can hang or reset the machine. Never in
// tests or CI; only in its own slot, with the kernel log streamed and the maintainer's word (given 2026-11-13).
//
// Programs: the gfx10 buffer-clear program is the backend's (bc5/dispatch_min.hpp, from IGT). The gfx10 buffer-copy
// program below is taken verbatim from IGT lib/amdgpu/amd_shaders.c:321-324 (buffercopy_cs_shader_gfx10),
// igt-gpu-tools @ 9d4b6ef512b4e2e4d05129c6519313fd13a306d2, which is
//   SPDX-License-Identifier: MIT, Copyright 2014, 2022 Advanced Micro Devices, Inc.
// (permission notice in that file: free of charge, to deal in the Software without restriction, provided the
// copyright notice and the permission notice are included in all copies or substantial portions).
// Its packet sequence is IGT's amdgpu_memcpy_dispatch_test (lib/amdgpu/compute_utils/amd_dispatch.c:249-400, same
// commit): the same state as the clear dispatch, user data 0x240..0x243 = the source's V# and 0x244..0x247 = the
// destination's V# {va lo, va hi | 0x100000 (stride 16), 0x400 records, 0x1104bfac for gfx10}, DISPATCH_DIRECT 0x10
// groups. So the copy IB is build_memset_ib() for the source with the four "value" dwords replaced by the
// destination's V#.
#include "bc5/dispatch_min.hpp"
#include "bc5/pm4.hpp"

#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

#ifdef BC5_WITH_AMDGPU
#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace {

// IGT lib/amdgpu/amd_shaders.c:321-324 @ 9d4b6ef (MIT, AMD): buffer_load_format_xyzw from s[0:3], s_waitcnt,
// buffer_store_format_xyzw to s[4:7], s_endpgm; the record index is TGID_X * 64 + the thread id.
[[maybe_unused]] constexpr std::array<std::uint32_t, 8> kBufferCopyCsGfx10 = {0xD7460001, 0x04010C08, 0xE00C2000, 0x80000201,
                                                             0xBF8C3F70, 0xE01C2000, 0x80010201, 0xBF810000};
constexpr std::uint32_t kBytes = 16384; // IGT's bo_dst_size: 1024 records of 16 bytes, 16 groups of 64 threads
constexpr std::uint32_t kSentinel = 0x5e1f0244u; // marks the user-data dwords 0x244..0x247 to be replaced
constexpr std::uint32_t kClearValue = 0x22222222u;

std::vector<std::uint32_t> clear_ib(std::uint64_t shader_va, std::uint64_t dst_va) {
    bc5::dispatch_min::MemsetParams p;
    p.shader_va = shader_va;
    p.dst_va = dst_va;
    p.dst_bytes = kBytes;
    p.value = kClearValue;
    p.gfx_ring = true;
    return bc5::dispatch_min::build_memset_ib(p);
}

// The copy IB: the clear IB for the source, with the "value" user data replaced by the destination's V#.
// Returns an empty vector if the four sentinel dwords are not found exactly once, in a row.
std::vector<std::uint32_t> copy_ib(std::uint64_t shader_va, std::uint64_t src_va, std::uint64_t dst_va) {
    bc5::dispatch_min::MemsetParams p;
    p.shader_va = shader_va;
    p.dst_va = src_va;
    p.dst_bytes = kBytes;
    p.value = kSentinel;
    p.gfx_ring = true;
    std::vector<std::uint32_t> ib = bc5::dispatch_min::build_memset_ib(p);
    std::size_t at = ib.size(), found = 0;
    for (std::size_t i = 0; i + 4 <= ib.size(); ++i) {
        if (ib[i] == kSentinel && ib[i + 1] == kSentinel && ib[i + 2] == kSentinel && ib[i + 3] == kSentinel) {
            at = i;
            found++;
            i += 3;
        }
    }
    std::size_t singles = 0;
    for (const std::uint32_t w : ib) singles += w == kSentinel ? 1u : 0u;
    if (found != 1 || singles != 4) return {};
    ib[at] = static_cast<std::uint32_t>(dst_va);
    ib[at + 1] = static_cast<std::uint32_t>(dst_va >> 32) | 0x100000u; // stride 16, as the source's V#
    ib[at + 2] = kBytes / 16;                                          // records (IGT: 0x400)
    ib[at + 3] = bc5::dispatch_min::kIgtVsharpWord3;                   // 0x1104bfac
    return ib;
}

int write_dwords(const std::string &path, const std::vector<std::uint32_t> &ib) {
    std::ofstream out(path, std::ios::binary);
    for (const std::uint32_t w : ib) {
        const unsigned char b[4] = {static_cast<unsigned char>(w), static_cast<unsigned char>(w >> 8),
                                    static_cast<unsigned char>(w >> 16), static_cast<unsigned char>(w >> 24)};
        out.write(reinterpret_cast<const char *>(b), 4);
    }
    if (!out) {
        std::fprintf(stderr, "cannot write %s\n", path.c_str());
        return 1;
    }
    std::printf("wrote %zu dwords to %s\n", ib.size(), path.c_str());
    return 0;
}

int dump(const std::string &prefix) {
    const std::vector<std::uint32_t> c = clear_ib(0x100000000ull, 0x200000000ull);
    const std::vector<std::uint32_t> y = copy_ib(0x100000000ull, 0x200000000ull, 0x300000000ull);
    if (y.empty()) {
        std::fprintf(stderr, "copy IB: the value dwords were not found exactly once\n");
        return 1;
    }
    std::printf("clear IB %zu dwords, copy IB %zu dwords; they differ in", c.size(), y.size());
    std::size_t n = 0;
    for (std::size_t i = 0; i < c.size() && i < y.size(); ++i) {
        if (c[i] != y[i]) {
            std::printf(" [%zu] %08x->%08x", i, c[i], y[i]);
            n++;
        }
    }
    std::printf(" (%zu dwords)\n", n);
    return write_dwords(prefix + "-clear.bin", c) | write_dwords(prefix + "-copy.bin", y);
}

#ifdef BC5_WITH_AMDGPU

double ms_since(std::chrono::steady_clock::time_point t0) {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
}

struct Gpu {
    int fd = -1;
    amdgpu_device_handle dev = nullptr;
};

struct Buf {
    const char *name = "";
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle vah = nullptr;
    std::uint64_t va = 0, size = 0;
    void *cpu = nullptr;
};

// A BO with a CPU mapping, GPU-mapped at a VA from libdrm's allocator with the given page flags.
bool make(Gpu &g, Buf &b, const char *name, std::uint64_t size, std::uint32_t domain, std::uint64_t page_flags) {
    b.name = name;
    b.size = size;
    amdgpu_bo_alloc_request req{};
    req.alloc_size = size;
    req.phys_alignment = 4096;
    req.preferred_heap = domain;
    int rc = amdgpu_bo_alloc(g.dev, &req, &b.bo);
    if (rc == 0) rc = amdgpu_va_range_alloc(g.dev, amdgpu_gpu_va_range_general, size, 2ull << 20, 0, &b.va, &b.vah, 0);
    int map_rc = -1;
    if (rc == 0) map_rc = rc = amdgpu_bo_va_op_raw(g.dev, b.bo, 0, size, b.va, page_flags, AMDGPU_VA_OP_MAP);
    if (rc == 0) rc = amdgpu_bo_cpu_map(b.bo, &b.cpu);
    std::printf("buffer %-6s: %llu bytes, GPU VA 0x%llx, page flags 0x%llx, va_op rc %d, all rc %d\n", name,
                static_cast<unsigned long long>(size), static_cast<unsigned long long>(b.va),
                static_cast<unsigned long long>(page_flags), map_rc, rc);
    return rc == 0;
}

void fault_line(Gpu &g, const char *when) {
#ifdef AMDGPU_INFO_GPUVM_FAULT
    drm_amdgpu_info_gpuvm_fault f{};
    const int rc = amdgpu_query_info(g.dev, AMDGPU_INFO_GPUVM_FAULT, sizeof(f), &f);
    std::printf("GPUVM_FAULT %s: rc %d addr 0x%llx status 0x%08x vmhub %u\n", when, rc,
                static_cast<unsigned long long>(f.addr), f.status, f.vmhub);
#else
    std::printf("GPUVM_FAULT %s: not in these headers\n", when);
#endif
}

void show(const Buf &b) {
    const auto *p = static_cast<const unsigned char *>(b.cpu);
    std::uint64_t nz = 0, a5 = 0, v22 = 0;
    for (std::uint64_t i = 0; i < kBytes; ++i) {
        nz += p[i] != 0 ? 1u : 0u;
        a5 += p[i] == 0xA5 ? 1u : 0u;
        v22 += p[i] == 0x22 ? 1u : 0u;
    }
    std::printf("content %-6s: first 16 bytes", b.name);
    for (int i = 0; i < 16; ++i) std::printf(" %02x", p[i]);
    std::printf("; of %u bytes: %llu non-zero, %llu are 0xA5 (never written), %llu are 0x22 (the clear's value)\n", kBytes,
                static_cast<unsigned long long>(nz), static_cast<unsigned long long>(a5),
                static_cast<unsigned long long>(v22));
}

struct Job {
    int rc = 0;
    std::uint32_t expired = 0;
    double ms = 0;
};

// One IB on the GFX ring in the given context; waits up to 3 s for its fence.
Job run(Gpu &g, amdgpu_context_handle ctx, Buf &cmd, const std::vector<std::uint32_t> &ib,
        const std::vector<amdgpu_bo_handle> &bos, const char *what) {
    Job j;
    if (ib.empty() || ib.size() * 4 > cmd.size) {
        std::printf("job %s: no IB\n", what);
        j.rc = -1;
        return j;
    }
    std::memcpy(cmd.cpu, ib.data(), ib.size() * 4);
    amdgpu_bo_list_handle list = nullptr;
    std::vector<amdgpu_bo_handle> l = bos;
    j.rc = amdgpu_bo_list_create(g.dev, static_cast<std::uint32_t>(l.size()), l.data(), nullptr, &list);
    if (j.rc != 0) {
        std::printf("job %s: bo list rc %d\n", what, j.rc);
        return j;
    }
    amdgpu_cs_ib_info info{};
    info.ib_mc_address = cmd.va;
    info.size = static_cast<std::uint32_t>(ib.size());
    amdgpu_cs_request req{};
    req.ip_type = AMDGPU_HW_IP_GFX;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &info;
    std::printf("job %s: submitting %zu dwords\n", what, ib.size());
    std::fflush(stdout);
    const auto t0 = std::chrono::steady_clock::now();
    j.rc = amdgpu_cs_submit(ctx, 0, &req, 1);
    int frc = 0;
    if (j.rc == 0) {
        amdgpu_cs_fence fence{};
        fence.context = ctx;
        fence.ip_type = AMDGPU_HW_IP_GFX;
        fence.ring = 0;
        fence.fence = req.seq_no;
        frc = amdgpu_cs_query_fence_status(&fence, 3'000'000'000ull, 0, &j.expired);
    }
    j.ms = ms_since(t0);
    std::printf("job %s: submit rc %d, fence rc %d, signalled %u, %.2f ms%s\n", what, j.rc, frc, j.expired, j.ms,
                j.rc == 0 && frc == 0 && j.expired ? "" : "  <-- NOT COMPLETED");
    std::fflush(stdout);
    if (j.rc == 0 && frc != 0) j.rc = frc;
    amdgpu_bo_list_destroy(list);
    return j;
}

int submit(const std::string &node, int which) {
    std::fprintf(stderr, "e1-probe: --submit runs shaders on the GPU (GFX ring). A bad submission can hang or reset the machine.\n");
    Gpu g;
    g.fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    std::uint32_t major = 0, minor = 0;
    if (g.fd < 0 || amdgpu_device_initialize(g.fd, &major, &minor, &g.dev) != 0) {
        std::fprintf(stderr, "cannot open %s\n", node.c_str());
        return 1;
    }
    std::printf("case %d on %s, DRM %u.%u\n", which, node.c_str(), major, minor);
    const std::uint64_t rw = AMDGPU_VM_PAGE_READABLE | AMDGPU_VM_PAGE_WRITEABLE;
    Buf sh_clear, sh_copy, cmd, real, out, zero;
    bool ok = make(g, sh_clear, "shclr", 4096, AMDGPU_GEM_DOMAIN_VRAM, rw | AMDGPU_VM_PAGE_EXECUTABLE) &&
              make(g, sh_copy, "shcpy", 4096, AMDGPU_GEM_DOMAIN_VRAM, rw | AMDGPU_VM_PAGE_EXECUTABLE) &&
              make(g, cmd, "cmd", 4096, AMDGPU_GEM_DOMAIN_GTT, rw | AMDGPU_VM_PAGE_EXECUTABLE) &&
              make(g, real, "real", 65536, AMDGPU_GEM_DOMAIN_GTT, rw) && make(g, out, "out", 65536, AMDGPU_GEM_DOMAIN_GTT, rw) &&
              make(g, zero, "zero", 65536, AMDGPU_GEM_DOMAIN_GTT, AMDGPU_VM_PAGE_READABLE); // readable ONLY
    // prt: a VA range with no BO, mapped as PRT (as bc5::direct::Device::map_prt_window does).
    std::uint64_t prt_va = 0;
    amdgpu_va_handle prt_vah = nullptr;
    const std::uint64_t prt_size = 2ull << 20;
    int prt_rc = -1;
    if (ok) {
        prt_rc = amdgpu_va_range_alloc(g.dev, amdgpu_gpu_va_range_general, prt_size, 2ull << 20, 0, &prt_va, &prt_vah, 0);
        if (prt_rc == 0) prt_rc = amdgpu_bo_va_op_raw(g.dev, nullptr, 0, prt_size, prt_va, AMDGPU_VM_PAGE_PRT, AMDGPU_VA_OP_MAP);
        std::printf("buffer prt   : %llu bytes, GPU VA 0x%llx, no BO, AMDGPU_VM_PAGE_PRT, rc %d\n",
                    static_cast<unsigned long long>(prt_size), static_cast<unsigned long long>(prt_va), prt_rc);
    }
    if (!ok || ((which == 1 || which == 3) && prt_rc != 0)) {
        std::fprintf(stderr, "setup failed; nothing submitted\n");
        return 1;
    }
    std::memset(sh_clear.cpu, 0, 4096);
    std::memcpy(sh_clear.cpu, bc5::dispatch_min::kBufferClearCsGfx10.data(), sizeof(bc5::dispatch_min::kBufferClearCsGfx10));
    std::memset(sh_copy.cpu, 0, 4096);
    std::memcpy(sh_copy.cpu, kBufferCopyCsGfx10.data(), sizeof(kBufferCopyCsGfx10));
    std::memset(real.cpu, 0x5A, 65536);
    std::memset(out.cpu, 0xA5, 65536);
    std::memset(zero.cpu, 0, 65536);
    const std::vector<amdgpu_bo_handle> bos = {sh_clear.bo, sh_copy.bo, cmd.bo, real.bo, out.bo, zero.bo};
    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(g.dev, &ctx) != 0) return 1;
    fault_line(g, "before");

    Job first;
    switch (which) {
    case 0:
        first = run(g, ctx, cmd, clear_ib(sh_clear.va, real.va), bos, "clear real");
        if (first.rc == 0 && first.expired) first = run(g, ctx, cmd, copy_ib(sh_copy.va, real.va, out.va), bos, "copy real -> out");
        break;
    case 1: first = run(g, ctx, cmd, copy_ib(sh_copy.va, prt_va, out.va), bos, "copy prt -> out"); break;
    case 2: first = run(g, ctx, cmd, copy_ib(sh_copy.va, zero.va, out.va), bos, "copy zero(read-only) -> out"); break;
    case 3: first = run(g, ctx, cmd, clear_ib(sh_clear.va, prt_va), bos, "clear prt"); break;
    case 4: first = run(g, ctx, cmd, clear_ib(sh_clear.va, zero.va), bos, "clear zero(read-only)"); break;
    default: std::fprintf(stderr, "no such case\n"); return 1;
    }
    const bool done = first.rc == 0 && first.expired;
    fault_line(g, "after the job");
    show(real);
    show(out);
    show(zero);
    if (!done) {
        // A hung job: the kernel's timeout and ring reset take about 12 s (F53). Wait, then look again.
        std::printf("the job did not complete: waiting 15 s for the kernel's timeout and reset\n");
        std::fflush(stdout);
        std::this_thread::sleep_for(std::chrono::seconds(15));
        fault_line(g, "15 s later");
        std::uint32_t state = 0, hangs = 0;
        const int qrc = amdgpu_cs_query_reset_state(ctx, &state, &hangs);
        std::printf("context reset state: rc %d state %u hangs %u\n", qrc, state, hangs);
        show(real);
        show(out);
        show(zero);
    }
    if (which >= 3) {
        // Does the ring still run jobs? A new context: the old one may be marked guilty.
        amdgpu_context_handle ctx2 = nullptr;
        if (amdgpu_cs_ctx_create(g.dev, &ctx2) == 0) {
            std::memset(out.cpu, 0xA5, 65536);
            Job a = run(g, ctx2, cmd, clear_ib(sh_clear.va, real.va), bos, "follow-up: clear real");
            if (a.rc == 0 && a.expired) run(g, ctx2, cmd, copy_ib(sh_copy.va, real.va, out.va), bos, "follow-up: copy real -> out");
            fault_line(g, "after the follow-up");
            show(real);
            show(out);
            show(zero);
            amdgpu_cs_ctx_free(ctx2);
        } else {
            std::printf("follow-up: no new context\n");
        }
    }
    std::printf("case %d: %s\n", which, done ? "the job completed" : "THE JOB DID NOT COMPLETE");
    std::fflush(stdout);
    // No teardown of mappings on purpose after a hang: the process exit frees everything.
    if (done) amdgpu_cs_ctx_free(ctx);
    return done ? 0 : 2;
}

#endif // BC5_WITH_AMDGPU

} // namespace

int main(int argc, char **argv) {
    std::string node = "/dev/dri/renderD128", prefix;
    bool do_submit = false;
    int which = -1;
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--submit") do_submit = true;
        else if (a == "--case" && i + 1 < argc) which = std::atoi(argv[++i]);
        else if (a == "--render-node" && i + 1 < argc) node = argv[++i];
        else if (a == "--dump-ib" && i + 1 < argc) prefix = argv[++i];
        else {
            std::fputs("usage: e1-probe --dump-ib <prefix> | --submit --case 0..4 [--render-node PATH]\n", stderr);
            return 1;
        }
    }
    if (!prefix.empty()) return dump(prefix);
    if (!do_submit || which < 0 || which > 4) {
        std::puts("e1-probe: nothing done without --submit --case 0..4 (or --dump-ib <prefix>)");
        return 0;
    }
#ifdef BC5_WITH_AMDGPU
    return submit(node, which);
#else
    (void)node;
    std::fputs("e1-probe: built without BC5_WITH_AMDGPU; --submit is not available\n", stderr);
    return 1;
#endif
}
