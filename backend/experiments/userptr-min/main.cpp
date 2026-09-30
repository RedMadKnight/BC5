// SPDX-License-Identifier: GPL-2.0-only
// userptr-min: phase-2 task 4 (HANDOFF Q1). Can anonymous CPU memory be handed to the GPU as a
// userptr BO and mapped at a GPU virtual address equal to the CPU pointer, so that a game's
// pointers work unchanged on both sides (the 1:1 mapping BC5's direct mode needs)?
//
//   userptr-min --info                       print the plan; no GPU access
//   userptr-min --submit [--mib N] [--render-node PATH] [--any-va] [--repeat N]
//
// --submit (BC5_WITH_AMDGPU only) mmaps N MiB (default 64), creates a userptr BO from it, maps it
// at GPU VA == CPU VA (or at a libdrm-chosen VA with --any-va), runs the memset dispatch of ADR 0004
// into that VA on the GFX ring, and verifies every dword on the CPU. Nothing is copied. Hard rule
// 5 (CLAUDE.md): --submit can hang or reset the machine; never run by tests, CI or scripts.
#include "bc5/dispatch_min.hpp"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>

#ifdef BC5_WITH_AMDGPU
#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>
#endif

namespace {

int usage() {
    std::fputs("usage: userptr-min --info | --submit [--mib N] [--render-node PATH] [--any-va] "
               "[--repeat N]\n",
               stderr);
    return 2;
}

#ifdef BC5_WITH_AMDGPU

struct Device {
    int fd = -1;
    amdgpu_device_handle dev = nullptr;
    ~Device() {
        if (dev) amdgpu_device_deinitialize(dev);
        if (fd >= 0) close(fd);
    }
};

struct Bo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr;
    std::uint64_t va = 0;
    std::uint64_t size = 0;
    void *cpu = nullptr;
    bool cpu_mapped = false;
    ~Bo() {
        if (cpu_mapped) amdgpu_bo_cpu_unmap(bo);
        if (va) amdgpu_bo_va_op(bo, 0, size, va, 0, AMDGPU_VA_OP_UNMAP);
        if (va_handle) amdgpu_va_range_free(va_handle);
        if (bo) amdgpu_bo_free(bo);
    }
};

bool alloc_vram(amdgpu_device_handle dev, std::uint64_t size, std::uint32_t domain, Bo &b) {
    b.size = size;
    amdgpu_bo_alloc_request req{};
    req.alloc_size = size;
    req.phys_alignment = 4096;
    req.preferred_heap = domain;
    if (amdgpu_bo_alloc(dev, &req, &b.bo) != 0) return false;
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &b.va,
                              &b.va_handle, 0) != 0)
        return false;
    if (amdgpu_bo_va_op(b.bo, 0, size, b.va, 0, AMDGPU_VA_OP_MAP) != 0) return false;
    if (amdgpu_bo_cpu_map(b.bo, &b.cpu) != 0) return false;
    b.cpu_mapped = true;
    return true;
}

double now_ms() {
    return std::chrono::duration<double, std::milli>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

int submit(const std::string &node, std::uint64_t mib, bool any_va, int repeat) {
    std::fprintf(stderr, "userptr-min: --submit runs a shader on the GPU (GFX ring). A bad "
                         "submission can hang or reset the machine.\n");
    const std::uint64_t bytes = mib << 20;
    Device d;
    d.fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (d.fd < 0) {
        std::perror(node.c_str());
        return 1;
    }
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize(d.fd, &major, &minor, &d.dev) != 0) {
        std::fprintf(stderr, "amdgpu_device_initialize failed\n");
        return 1;
    }
    drm_amdgpu_info_device dev_info{};
    amdgpu_query_info(d.dev, AMDGPU_INFO_DEV_INFO, sizeof(dev_info), &dev_info);
    std::printf("virtual address range: 0x%llx..0x%llx (high 0x%llx..0x%llx)\n",
                static_cast<unsigned long long>(dev_info.virtual_address_offset),
                static_cast<unsigned long long>(dev_info.virtual_address_max),
                static_cast<unsigned long long>(dev_info.high_va_offset),
                static_cast<unsigned long long>(dev_info.high_va_max));

    // 1. Anonymous CPU memory, page-aligned and populated (a game heap stands in for this).
    void *mem = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE,
                     -1, 0);
    if (mem == MAP_FAILED) {
        std::perror("mmap");
        return 1;
    }
    std::memset(mem, 0, bytes);
    const auto cpu_va = reinterpret_cast<std::uint64_t>(mem);
    std::printf("cpu memory: %llu MiB at 0x%llx\n", static_cast<unsigned long long>(mib),
                static_cast<unsigned long long>(cpu_va));

    // 2. userptr BO over it.
    Bo user;
    user.size = bytes;
    double t0 = now_ms();
    int rc = amdgpu_create_bo_from_user_mem(d.dev, mem, bytes, &user.bo);
    double t1 = now_ms();
    if (rc != 0) {
        std::fprintf(stderr, "amdgpu_create_bo_from_user_mem failed: %d\n", rc);
        return 1;
    }
    std::printf("userptr BO created in %.2f ms\n", t1 - t0);

    // 3. GPU VA == CPU VA (the 1:1 question), or any VA as a control.
    std::uint64_t gpu_va = cpu_va;
    if (any_va) {
        if (amdgpu_va_range_alloc(d.dev, amdgpu_gpu_va_range_general, bytes, 4096, 0, &gpu_va,
                                  &user.va_handle, 0) != 0) {
            std::fprintf(stderr, "va range alloc failed\n");
            return 1;
        }
    }
    t0 = now_ms();
    rc = amdgpu_bo_va_op(user.bo, 0, bytes, gpu_va, 0, AMDGPU_VA_OP_MAP);
    t1 = now_ms();
    if (rc != 0) {
        std::fprintf(stderr, "amdgpu_bo_va_op(MAP at 0x%llx) failed: %d (%s)\n",
                     static_cast<unsigned long long>(gpu_va), rc, std::strerror(-rc));
        return 1;
    }
    user.va = gpu_va;
    std::printf("mapped at gpu va 0x%llx (%s cpu va) in %.2f ms\n",
                static_cast<unsigned long long>(gpu_va), gpu_va == cpu_va ? "==" : "!=", t1 - t0);

    // 4. The memset dispatch writes straight into it.
    Bo shader, cmd;
    if (!alloc_vram(d.dev, 4096, AMDGPU_GEM_DOMAIN_VRAM, shader) ||
        !alloc_vram(d.dev, 4096, AMDGPU_GEM_DOMAIN_GTT, cmd)) {
        std::fprintf(stderr, "buffer allocation failed\n");
        return 1;
    }
    std::memset(shader.cpu, 0, 4096);
    std::memcpy(shader.cpu, bc5::dispatch_min::kBufferClearCsGfx10.data(),
                sizeof(bc5::dispatch_min::kBufferClearCsGfx10));

    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(d.dev, &ctx) != 0) return 1;
    amdgpu_bo_handle list_bos[3] = {shader.bo, user.bo, cmd.bo};
    amdgpu_bo_list_handle list = nullptr;
    if (amdgpu_bo_list_create(d.dev, 3, list_bos, nullptr, &list) != 0) return 1;

    int failures = 0;
    for (int r = 0; r < repeat; ++r) {
        const std::uint32_t value = 0x5a000000u + static_cast<std::uint32_t>(r);
        bc5::dispatch_min::MemsetParams p;
        p.shader_va = shader.va;
        p.dst_va = gpu_va;
        p.dst_bytes = static_cast<std::uint32_t>(bytes);
        p.value = value;
        p.rsrc1 = bc5::dispatch_min::kConsoleRsrc1;
        p.vsharp_word3 = bc5::dispatch_min::kConsoleVsharpWord3;
        const auto ib = bc5::dispatch_min::build_memset_ib(p);
        std::memcpy(cmd.cpu, ib.data(), ib.size() * sizeof(std::uint32_t));

        amdgpu_cs_ib_info ib_info{};
        ib_info.ib_mc_address = cmd.va;
        ib_info.size = static_cast<std::uint32_t>(ib.size());
        amdgpu_cs_request req{};
        req.ip_type = AMDGPU_HW_IP_GFX;
        req.ring = 0;
        req.resources = list;
        req.number_of_ibs = 1;
        req.ibs = &ib_info;

        t0 = now_ms();
        rc = amdgpu_cs_submit(ctx, 0, &req, 1);
        std::uint32_t expired = 0;
        if (rc == 0) {
            amdgpu_cs_fence fence{};
            fence.context = ctx;
            fence.ip_type = AMDGPU_HW_IP_GFX;
            fence.ring = 0;
            fence.fence = req.seq_no;
            rc = amdgpu_cs_query_fence_status(&fence, 5'000'000'000ull, 0, &expired);
        }
        t1 = now_ms();
        if (rc != 0 || !expired) {
            std::fprintf(stderr, "submit or fence failed (rc %d, expired %u)\n", rc, expired);
            failures++;
            break;
        }
        // 5. Verify on the CPU through the original pointer: no copy, no cpu_map.
        const auto *out = static_cast<const std::uint32_t *>(mem);
        std::uint64_t bad = 0;
        double t2 = now_ms();
        for (std::uint64_t i = 0; i < bytes / 4; ++i) bad += out[i] != value ? 1u : 0u;
        double t3 = now_ms();
        std::printf("run %d: gpu fill %.2f ms (%.2f GB/s), cpu verify %.2f ms, %llu of %llu dwords "
                    "differ from 0x%08x\n",
                    r, t1 - t0, static_cast<double>(bytes) / ((t1 - t0) * 1e6), t3 - t2,
                    static_cast<unsigned long long>(bad), static_cast<unsigned long long>(bytes / 4),
                    value);
        if (bad != 0) failures++;
    }
    amdgpu_bo_list_destroy(list);
    amdgpu_cs_ctx_free(ctx);
    return failures == 0 ? 0 : 1;
}

#endif // BC5_WITH_AMDGPU

} // namespace

int main(int argc, char **argv) {
    std::string mode;
    std::string node = "/dev/dri/renderD128";
    std::uint64_t mib = 64;
    bool any_va = false;
    int repeat = 3;
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--info") {
            mode = "info";
        } else if (a == "--submit") {
            mode = "submit";
        } else if (a == "--render-node" && i + 1 < argc) {
            node = argv[++i];
        } else if (a == "--mib" && i + 1 < argc) {
            mib = std::stoull(argv[++i]);
        } else if (a == "--repeat" && i + 1 < argc) {
            repeat = std::stoi(argv[++i]);
        } else if (a == "--any-va") {
            any_va = true;
        } else {
            return usage();
        }
    }
    if (mode == "info") {
        std::printf("userptr-min: mmap %llu MiB, userptr BO, map at GPU VA == CPU VA, memset "
                    "dispatch into it, verify on the CPU. Needs --submit and BC5_WITH_AMDGPU.\n",
                    static_cast<unsigned long long>(mib));
        return 0;
    }
#ifdef BC5_WITH_AMDGPU
    if (mode == "submit") return submit(node, mib, any_va, repeat);
#else
    (void)node;
    (void)any_va;
    (void)repeat;
    if (mode == "submit") {
        std::fputs("built without BC5_WITH_AMDGPU; only --info is available\n", stderr);
        return 2;
    }
#endif
    return usage();
}
