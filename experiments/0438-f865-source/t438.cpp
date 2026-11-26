// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0438 (test t438): does a compute job run while a GFX job of the SAME VM waits on the GPU for a label it
// writes? One process, one fd, one VM (amdgpu_device_initialize2, no dedup, as the emulator), one context.
//   G (GFX ring): RELEASE_MEM timestamp -> WAIT_REG_MEM (PFP) label L == 1 -> RELEASE_MEM timestamp
//   C (compute ring 0), submitted 5 ms after G: RELEASE_MEM timestamp -> RELEASE_MEM L = 1 (32-bit data)
// Variants (the label's BO):
//   a   L in a udmabuf of a memfd, imported (amdgpu_bo_import dma_buf), as the emulator's direct memory
//   a0  L in a plain GTT BO
//   b   L in a GTT BO with AMDGPU_GEM_CREATE_EXPLICIT_SYNC
//   c   as a0, C with an explicit CS dependency on G (the deadlock control: must stall until the guard)
//   d   as a0, the writer on the GFX ring behind G (a GFX job S that writes L): must stall until the guard
//   d2  as a0, a GFX job S (no write) behind G, C depending on S: must stall until the guard
// Every job's BO list holds every BO (shared BOs: the implicit-sync question). The harness's guard: if L is still 0
// 300 ms after C's (or S's) submit, the test writes L = 1 from the CPU so that G ends with no ring timeout; that is a
// test bound, not product code. Stops at the first fence that does not signal within 2 s. Nothing without --submit.
// Packet layouts (gfx10): PKT3 header (3 << 30 | count << 16 | op << 8), WAIT_REG_MEM 0x3C (7 dwords), RELEASE_MEM 0x49
// (8 dwords: event_cntl, data/dst select, addr lo/hi, data lo/hi, ctx id), NOP 0x10: Mesa src/amd/common/sid.h and
// src/amd/common/ac_cmdbuf.c (si_cp_release_mem / ac_emit_cp_wait_mem), TODO(verify) the exact Mesa commit in the README.
//   t438 --submit [--node /dev/dri/renderD128] [variant...]   (run 2 default: a u b; u = L in a userptr BO as the emulator's)
// Run 1 (2026-11-20 11:49) showed that the CPU guard cannot release a GPU WAIT_REG_MEM: variant d ended in a gfx ring timeout
// (reset succeeded). Run 2 has no guard and only variants whose writer is a compute job of the same VM; a ring timeout is the
// finding, and the test stops there. The GPU timestamps are read after the jobs end: the kernel's end-of-job fence writes back
// GL2 (gfx_v10_0_ring_emit_fence: GCR_GL2_WB; torvalds/linux master, TODO(verify) on 7.3.3).
#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <linux/udmabuf.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr std::uint32_t pkt3(std::uint32_t op, std::uint32_t dwords) { return (3u << 30) | ((dwords - 2) << 16) | (op << 8); }
constexpr std::uint32_t kNop = 0xffff1000u;

double now_ms() {
    return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

struct Bo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle vh = nullptr;
    std::uint64_t va = 0, size = 0;
    volatile std::uint32_t *cpu = nullptr;
    int memfd = -1, dmabuf = -1;
    void *mm = nullptr;
    void *heap = nullptr; // a userptr's pages
};

bool map_va(amdgpu_device_handle dev, Bo &b) {
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, b.size, 4096, 0, &b.va, &b.vh, 0) != 0) return false;
    return amdgpu_bo_va_op(b.bo, 0, b.size, b.va, 0, AMDGPU_VA_OP_MAP) == 0;
}

bool alloc_gtt(amdgpu_device_handle dev, std::uint64_t bytes, std::uint64_t flags, Bo &b) {
    amdgpu_bo_alloc_request req{};
    req.alloc_size = bytes;
    req.phys_alignment = 4096;
    req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
    req.flags = flags;
    if (amdgpu_bo_alloc(dev, &req, &b.bo) != 0) return false;
    b.size = bytes;
    if (!map_va(dev, b)) return false;
    void *p = nullptr;
    if (amdgpu_bo_cpu_map(b.bo, &p) != 0) return false;
    b.cpu = static_cast<volatile std::uint32_t *>(p);
    return true;
}

bool alloc_udmabuf(amdgpu_device_handle dev, std::uint64_t bytes, Bo &b) { // the emulator's way (backend/src/direct.cpp)
    b.memfd = memfd_create("t438", MFD_ALLOW_SEALING | MFD_CLOEXEC);
    if (b.memfd < 0 || ftruncate(b.memfd, static_cast<off_t>(bytes)) != 0) return false;
    if (fcntl(b.memfd, F_ADD_SEALS, F_SEAL_SHRINK) != 0) return false;
    const int u = open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
    if (u < 0) return false;
    udmabuf_create c{};
    c.memfd = static_cast<std::uint32_t>(b.memfd);
    c.flags = UDMABUF_FLAGS_CLOEXEC;
    c.offset = 0;
    c.size = bytes;
    b.dmabuf = ioctl(u, UDMABUF_CREATE, &c);
    close(u);
    if (b.dmabuf < 0) return false;
    amdgpu_bo_import_result res{};
    if (amdgpu_bo_import(dev, amdgpu_bo_handle_type_dma_buf_fd, static_cast<std::uint32_t>(b.dmabuf), &res) != 0) return false;
    b.bo = res.buf_handle;
    b.size = bytes;
    if (!map_va(dev, b)) return false;
    b.mm = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, b.memfd, 0);
    if (b.mm == MAP_FAILED) return false;
    b.cpu = static_cast<volatile std::uint32_t *>(b.mm);
    return true;
}

bool alloc_userptr(amdgpu_device_handle dev, std::uint64_t bytes, Bo &b) { // the emulator's writable userptr (backend/src/direct.cpp)
    void *p = nullptr;
    if (posix_memalign(&p, 4096, bytes) != 0) return false;
    std::memset(p, 0, bytes);
    b.heap = p;
    if (amdgpu_create_bo_from_user_mem(dev, p, bytes, &b.bo) != 0) return false;
    b.size = bytes;
    if (!map_va(dev, b)) return false;
    b.cpu = static_cast<volatile std::uint32_t *>(p);
    return true;
}

void release(Bo &b) {
    if (b.va != 0) amdgpu_bo_va_op(b.bo, 0, b.size, b.va, 0, AMDGPU_VA_OP_UNMAP);
    if (b.vh != nullptr) amdgpu_va_range_free(b.vh);
    if (b.mm != nullptr && b.mm != MAP_FAILED) munmap(b.mm, b.size);
    else if (b.cpu != nullptr && b.heap == nullptr) amdgpu_bo_cpu_unmap(b.bo);
    if (b.bo != nullptr) amdgpu_bo_free(b.bo);
    if (b.heap != nullptr) std::free(b.heap);
    if (b.dmabuf >= 0) close(b.dmabuf);
    if (b.memfd >= 0) close(b.memfd);
    b = Bo{};
}

// RELEASE_MEM, bottom of pipe (event type 0x28, index 5), to memory; data_sel 1 = 32-bit data, 3 = the GPU clock
void release_mem(std::vector<std::uint32_t> &ib, std::uint64_t addr, std::uint32_t data_sel, std::uint32_t data) {
    ib.insert(ib.end(), {pkt3(0x49, 8), 0x28u | (5u << 8), data_sel << 29, static_cast<std::uint32_t>(addr), static_cast<std::uint32_t>(addr >> 32), data, 0u, 0u});
}
// WAIT_REG_MEM, memory, function 3 (==), engine 1 = PFP (GFX only)
void wait_mem(std::vector<std::uint32_t> &ib, std::uint64_t addr, std::uint32_t ref, bool pfp) {
    ib.insert(ib.end(), {pkt3(0x3C, 7), 3u | (1u << 4) | (pfp ? (1u << 8) : 0u), static_cast<std::uint32_t>(addr), static_cast<std::uint32_t>(addr >> 32), ref, 0xffffffffu, 4u});
}
void pad(std::vector<std::uint32_t> &ib) {
    while (ib.size() % 8 != 0) ib.push_back(kNop);
}

struct Job {
    std::uint32_t ip = AMDGPU_HW_IP_GFX;
    std::uint64_t seq = 0;
    double submitted = 0, done = -1;
};

int submit(amdgpu_context_handle ctx, amdgpu_bo_list_handle list, Bo &ib_bo, std::uint32_t off_dw, const std::vector<std::uint32_t> &ib, Job &j,
           const amdgpu_cs_fence *dep) {
    for (std::size_t k = 0; k < ib.size(); ++k) ib_bo.cpu[off_dw + k] = ib[k];
    amdgpu_cs_ib_info info{};
    info.ib_mc_address = ib_bo.va + off_dw * 4ull;
    info.size = static_cast<std::uint32_t>(ib.size());
    amdgpu_cs_request req{};
    req.ip_type = j.ip;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &info;
    amdgpu_cs_fence d{};
    if (dep != nullptr) {
        d = *dep;
        req.number_of_dependencies = 1;
        req.dependencies = &d;
    }
    const int rc = amdgpu_cs_submit(ctx, 0, &req, 1);
    j.seq = req.seq_no;
    j.submitted = now_ms();
    return rc;
}

bool signaled(amdgpu_context_handle ctx, const Job &j, std::uint64_t timeout_ns) {
    amdgpu_cs_fence f{};
    f.context = ctx;
    f.ip_type = j.ip;
    f.ring = 0;
    f.fence = j.seq;
    std::uint32_t expired = 0;
    return amdgpu_cs_query_fence_status(&f, timeout_ns, 0, &expired) == 0 && expired != 0;
}

} // namespace

int main(int argc, char **argv) {
    bool go = false;
    std::string node = "/dev/dri/renderD128";
    std::vector<std::string> vars;
    for (int a = 1; a < argc; ++a) {
        if (!std::strcmp(argv[a], "--submit")) go = true;
        else if (!std::strcmp(argv[a], "--node") && a + 1 < argc) node = argv[++a];
        else vars.emplace_back(argv[a]);
    }
    if (!go) {
        std::fprintf(stderr, "usage: t438 --submit [--node dev] [a u b a0 c d d2]  (nothing is submitted without --submit)\n");
        return 2;
    }
    if (vars.empty()) vars = {"a", "u", "b"}; // run 2 (the top session's ruling): c, d and d2 dropped; no CPU guard
    const int fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (fd < 0) { std::perror(node.c_str()); return 1; }
    amdgpu_device_handle dev = nullptr;
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize2(fd, false, &major, &minor, &dev) != 0) { std::fprintf(stderr, "amdgpu_device_initialize2 failed\n"); return 1; }
    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(dev, &ctx) != 0) { std::fprintf(stderr, "amdgpu_cs_ctx_create failed\n"); return 1; }
    std::printf("t438: %s, amdgpu DRM %u.%u; one fd, one VM, one context\n", node.c_str(), major, minor);
    int rc_all = 0;
    for (const std::string &v : vars) {
        Bo lab, ts, ibb;
        bool ok = alloc_gtt(dev, 65536, 0, ibb) && alloc_gtt(dev, 4096, 0, ts);
        if (v == "a") ok = ok && alloc_udmabuf(dev, 4096, lab);
        else if (v == "u") ok = ok && alloc_userptr(dev, 4096, lab);
        else if (v == "b") ok = ok && alloc_gtt(dev, 4096, AMDGPU_GEM_CREATE_EXPLICIT_SYNC, lab);
        else ok = ok && alloc_gtt(dev, 4096, 0, lab);
        if (!ok) {
            std::printf("%s: BO setup FAILED\n", v.c_str());
            release(lab); release(ts); release(ibb);
            rc_all = 1;
            continue;
        }
        lab.cpu[0] = 0;
        for (int k = 0; k < 16; ++k) ts.cpu[k] = 0;
        amdgpu_bo_handle bos[3] = {lab.bo, ts.bo, ibb.bo};
        amdgpu_bo_list_handle list = nullptr;
        if (amdgpu_bo_list_create(dev, 3, bos, nullptr, &list) != 0) { std::printf("%s: bo list FAILED\n", v.c_str()); return 1; }
        const std::uint64_t L = lab.va;
        // ts slots (64-bit): 0 G start, 1 G after the wait, 2 writer start
        std::vector<std::uint32_t> g, w;
        release_mem(g, ts.va + 0, 3, 0);
        wait_mem(g, L, 1, true);
        release_mem(g, ts.va + 8, 3, 0);
        pad(g);
        Job G, W, S;
        G.ip = AMDGPU_HW_IP_GFX;
        const bool writer_on_gfx = v == "d";
        W.ip = writer_on_gfx ? AMDGPU_HW_IP_GFX : AMDGPU_HW_IP_COMPUTE;
        release_mem(w, ts.va + 16, 3, 0);
        release_mem(w, L, 1, 1);
        pad(w);
        const double t0 = now_ms();
        int rc = submit(ctx, list, ibb, 0, g, G, nullptr);
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
        amdgpu_cs_fence gdep{ctx, AMDGPU_HW_IP_GFX, 0, 0, G.seq};
        if (rc == 0 && v == "d2") { // a GFX job behind G, the writer depending on it
            std::vector<std::uint32_t> s(8, kNop);
            S.ip = AMDGPU_HW_IP_GFX;
            rc = submit(ctx, list, ibb, 1024, s, S, nullptr);
            amdgpu_cs_fence sdep{ctx, AMDGPU_HW_IP_GFX, 0, 0, S.seq};
            if (rc == 0) rc = submit(ctx, list, ibb, 2048, w, W, &sdep);
        } else if (rc == 0) {
            rc = submit(ctx, list, ibb, 2048, w, W, v == "c" ? &gdep : nullptr);
        }
        if (rc != 0) {
            std::printf("%s: cs submit rc %d\n", v.c_str(), rc);
            return 1;
        }
        const bool guard = false; // run 2: no CPU guard (run 1 showed a CPU store does not release the GPU's poll)
        while (!signaled(ctx, W, 0) && now_ms() - W.submitted < 2000) std::this_thread::sleep_for(std::chrono::microseconds(200));
        if (signaled(ctx, W, 0)) W.done = now_ms();
        const bool g_ok = signaled(ctx, G, 2'000'000'000ull);
        if (g_ok) G.done = now_ms();
        const bool w_ok = W.done >= 0 || signaled(ctx, W, 2'000'000'000ull);
        if (w_ok && W.done < 0) W.done = now_ms();
        const auto t64 = [&](int k) { return static_cast<std::uint64_t>(ts.cpu[2 * k]) | (static_cast<std::uint64_t>(ts.cpu[2 * k + 1]) << 32); };
        const std::uint64_t g0 = t64(0), g1 = t64(1), w0 = t64(2);
        std::printf("%s: writer on %s%s; writer done %s ms after its submit; G done %.3f ms after G's submit; guard %s; GPU clock: G wait %" PRIu64 " ticks, writer start - G start %lld ticks\n",
                    v.c_str(), writer_on_gfx ? "GFX (behind G)" : "compute ring 0", v == "c" ? ", depending on G" : v == "d2" ? ", depending on a GFX job behind G" : "",
                    W.done >= 0 ? std::to_string(W.done - W.submitted).c_str() : "NOT", G.done >= 0 ? G.done - G.submitted : -1.0, guard ? "USED (the writer did not release G)" : "not used",
                    g1 >= g0 ? g1 - g0 : 0, static_cast<long long>(w0) - static_cast<long long>(g0));
        std::fflush(stdout);
        amdgpu_bo_list_destroy(list);
        if (!g_ok || !w_ok) {
            std::printf("%s: a fence did not signal within 2 s: stopping (BOs left)\n", v.c_str());
            return 3;
        }
        release(lab); release(ts); release(ibb);
        (void)t0;
    }
    amdgpu_cs_ctx_free(ctx);
    amdgpu_device_deinitialize(dev);
    close(fd);
    return rc_all;
}
