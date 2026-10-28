// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0349: the kernel's real IB size limit on the GFX ring, measured. One process, one context: for each
// size (dwords) an IB of single-dword NOPs (PKT3 NOP with count 0x3fff = 0xffff1000, the padding RADV uses) in a GTT
// BO exactly sized (page-rounded) and, with --larger, in a BO 1 MiB bigger; one IB per submit; the cs ioctl's rc and
// the fence's state are printed per size. A refused IB never reaches the GPU; an accepted one runs NOPs only. Stops at
// the first fence timeout. Does nothing without --submit (CLAUDE.md hard rule 5).
//   ib-probe --submit [--larger] [--node /dev/dri/renderD128] [--timeout-ms 2000] size...   (sizes in dwords, decimal or 0x…)
#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <unistd.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {

struct Bo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr;
    std::uint64_t va = 0, size = 0;
    void *cpu = nullptr;
};

bool alloc(amdgpu_device_handle dev, std::uint64_t bytes, Bo &b) {
    amdgpu_bo_alloc_request req{};
    req.alloc_size = bytes;
    req.phys_alignment = 4096;
    req.preferred_heap = AMDGPU_GEM_DOMAIN_GTT;
    if (amdgpu_bo_alloc(dev, &req, &b.bo) != 0) return false;
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, bytes, 4096, 0, &b.va, &b.va_handle, 0) != 0) return false;
    if (amdgpu_bo_va_op(b.bo, 0, bytes, b.va, 0, AMDGPU_VA_OP_MAP) != 0) return false;
    if (amdgpu_bo_cpu_map(b.bo, &b.cpu) != 0) return false;
    b.size = bytes;
    return true;
}

void release(Bo &b) {
    if (b.cpu != nullptr) amdgpu_bo_cpu_unmap(b.bo);
    if (b.va != 0) amdgpu_bo_va_op(b.bo, 0, b.size, b.va, 0, AMDGPU_VA_OP_UNMAP);
    if (b.va_handle != nullptr) amdgpu_va_range_free(b.va_handle);
    if (b.bo != nullptr) amdgpu_bo_free(b.bo);
    b = Bo{};
}

} // namespace

int main(int argc, char **argv) {
    bool submit = false, larger = false;
    std::string node = "/dev/dri/renderD128";
    std::uint64_t timeout_ms = 2000;
    std::vector<std::uint64_t> sizes;
    for (int a = 1; a < argc; ++a) {
        if (!std::strcmp(argv[a], "--submit")) submit = true;
        else if (!std::strcmp(argv[a], "--larger")) larger = true;
        else if (!std::strcmp(argv[a], "--node") && a + 1 < argc) node = argv[++a];
        else if (!std::strcmp(argv[a], "--timeout-ms") && a + 1 < argc) timeout_ms = std::strtoull(argv[++a], nullptr, 0);
        else sizes.push_back(std::strtoull(argv[a], nullptr, 0));
    }
    if (!submit || sizes.empty()) {
        std::fprintf(stderr, "usage: ib-probe --submit [--larger] [--node dev] [--timeout-ms n] size-in-dwords...\n(nothing is submitted without --submit)\n");
        return 2;
    }
    const int fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (fd < 0) { std::perror(node.c_str()); return 1; }
    amdgpu_device_handle dev = nullptr;
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize(fd, &major, &minor, &dev) != 0) { std::fprintf(stderr, "amdgpu_device_initialize failed\n"); return 1; }
    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(dev, &ctx) != 0) { std::fprintf(stderr, "amdgpu_cs_ctx_create failed\n"); return 1; }
    std::printf("ib-probe: %s, libdrm amdgpu %u.%u; NOP IBs on the GFX ring, one IB per submit, fence timeout %llu ms%s\n", node.c_str(), major, minor,
                static_cast<unsigned long long>(timeout_ms), larger ? ", BO 1 MiB larger than the IB" : ", BO exactly the IB (page-rounded)");
    int rc_all = 0;
    for (const std::uint64_t n : sizes) {
        const std::uint64_t ib_bytes = n * 4;
        const std::uint64_t bo_bytes = ((ib_bytes + 4095) & ~std::uint64_t{4095}) + (larger ? (1ull << 20) : 0);
        Bo b;
        if (!alloc(dev, bo_bytes, b)) {
            std::printf("size %llu dwords: BO of %llu bytes: alloc/map FAILED\n", static_cast<unsigned long long>(n), static_cast<unsigned long long>(bo_bytes));
            release(b);
            rc_all = 1;
            continue;
        }
        auto *p = static_cast<std::uint32_t *>(b.cpu);
        for (std::uint64_t i = 0; i < bo_bytes / 4; ++i) p[i] = 0xffff1000u; // PKT3(NOP, 0x3fff): one dword each
        amdgpu_bo_list_handle list = nullptr;
        amdgpu_bo_handle bos[1] = {b.bo};
        int rc = amdgpu_bo_list_create(dev, 1, bos, nullptr, &list);
        if (rc != 0) {
            std::printf("size %llu dwords: bo_list_create rc %d\n", static_cast<unsigned long long>(n), rc);
            release(b);
            rc_all = 1;
            continue;
        }
        amdgpu_cs_ib_info ib{};
        ib.ib_mc_address = b.va;
        ib.size = static_cast<std::uint32_t>(n);
        amdgpu_cs_request req{};
        req.ip_type = AMDGPU_HW_IP_GFX;
        req.ring = 0;
        req.resources = list;
        req.number_of_ibs = 1;
        req.ibs = &ib;
        rc = amdgpu_cs_submit(ctx, 0, &req, 1);
        int frc = 0;
        std::uint32_t expired = 0;
        if (rc == 0) {
            amdgpu_cs_fence f{};
            f.context = ctx;
            f.ip_type = AMDGPU_HW_IP_GFX;
            f.ring = 0;
            f.fence = req.seq_no;
            frc = amdgpu_cs_query_fence_status(&f, timeout_ms * 1000000ull, 0, &expired);
        }
        std::printf("size %llu dwords (0x%llx; %llu bytes) in a BO of %llu bytes: cs rc %d%s\n", static_cast<unsigned long long>(n), static_cast<unsigned long long>(n),
                    static_cast<unsigned long long>(ib_bytes), static_cast<unsigned long long>(bo_bytes), rc,
                    rc == 0 ? (frc == 0 ? (expired != 0 ? ", fence signaled: the IB ran" : ", fence TIMED OUT") : ", fence query failed") : " (refused before the GPU)");
        std::fflush(stdout);
        amdgpu_bo_list_destroy(list);
        if (rc == 0 && (frc != 0 || expired == 0)) {
            std::printf("stopping at the first fence timeout; the BO is left mapped\n");
            return 3;
        }
        release(b);
    }
    amdgpu_cs_ctx_free(ctx);
    amdgpu_device_deinitialize(dev);
    close(fd);
    return rc_all;
}
