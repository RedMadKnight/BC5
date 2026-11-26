// SPDX-License-Identifier: GPL-2.0-only
// dmabuf-min: experiment 0017 (ADR 0006). Can a range of a memfd — how KytyPlus backs the guest's
// direct memory upstream — be handed to the GPU as a dma-buf (udmabuf) imported into amdgpu and
// mapped at a GPU virtual address equal to the CPU address of a MAP_SHARED view of it, so that
// the GPU works on the very pages the guest sees without a userptr BO, whose pages the kernel
// walks again on every submission (experiment 0016, run 80: 28 ms per CS with 5.8 GB listed)?
//
//   dmabuf-min --info                      print the plan; no GPU access
//   dmabuf-min --import [options]          memfd, udmabufs, amdgpu import, VA map; no submission
//   dmabuf-min --submit [options]          the same, then the memset dispatch of ADR 0004 into the
//                                          first chunk through its guest address, verified through
//                                          the memfd view, and the cost of a CS that lists all
//                                          the chunks against one that lists as many userptr BOs
//   options: --mib N (total, default 256)  --chunk-mib M (default 32, at most the udmabuf module's
//            size_limit_mb)  --repeat R (timed submissions per list, default 50)
//            --render-node PATH
//
// --submit (BC5_WITH_AMDGPU only) can hang or reset the machine (CLAUDE.md hard rule 5); never
// run by tests, CI or scripts.
#include "bc5/dispatch_min.hpp"

#include <algorithm>
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
#include <linux/udmabuf.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <xf86drm.h>

#ifndef MFD_ALLOW_SEALING
#define MFD_ALLOW_SEALING 0x0002U
#endif
#ifndef F_ADD_SEALS
#define F_ADD_SEALS 1033
#endif
#ifndef F_SEAL_SHRINK
#define F_SEAL_SHRINK 0x0002
#endif
#endif

namespace {

int usage() {
    std::fputs("usage: dmabuf-min --info | --import | --submit  [--mib N] [--chunk-mib M] "
               "[--repeat R] [--render-node PATH]\n",
               stderr);
    return 2;
}

#ifdef BC5_WITH_AMDGPU

double now_ms() {
    return std::chrono::duration<double, std::milli>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

struct Vram {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr;
    std::uint64_t va = 0;
    void *cpu = nullptr;
};

bool alloc_bo(amdgpu_device_handle dev, std::uint64_t size, std::uint32_t domain, Vram &b) {
    amdgpu_bo_alloc_request req{};
    req.alloc_size = size;
    req.phys_alignment = 4096;
    req.preferred_heap = domain;
    if (amdgpu_bo_alloc(dev, &req, &b.bo) != 0) return false;
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &b.va, &b.va_handle,
                              0) != 0)
        return false;
    if (amdgpu_bo_va_op(b.bo, 0, size, b.va, 0, AMDGPU_VA_OP_MAP) != 0) return false;
    return amdgpu_bo_cpu_map(b.bo, &b.cpu) == 0;
}

// One submission on the GFX ring with the given BO list; returns the CS ioctl and fence times.
bool submit_ib(amdgpu_context_handle ctx, amdgpu_bo_list_handle list, std::uint64_t ib_va,
               std::uint32_t ib_dwords, double &cs_ms, double &fence_ms) {
    amdgpu_cs_ib_info ib_info{};
    ib_info.ib_mc_address = ib_va;
    ib_info.size = ib_dwords;
    amdgpu_cs_request req{};
    req.ip_type = AMDGPU_HW_IP_GFX;
    req.ring = 0;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &ib_info;
    const double t0 = now_ms();
    int rc = amdgpu_cs_submit(ctx, 0, &req, 1);
    const double t1 = now_ms();
    std::uint32_t expired = 0;
    if (rc == 0) {
        amdgpu_cs_fence fence{};
        fence.context = ctx;
        fence.ip_type = AMDGPU_HW_IP_GFX;
        fence.ring = 0;
        fence.fence = req.seq_no;
        rc = amdgpu_cs_query_fence_status(&fence, 5'000'000'000ull, 0, &expired);
    }
    cs_ms = t1 - t0;
    fence_ms = now_ms() - t1;
    if (rc != 0 || !expired) {
        std::fprintf(stderr, "submit or fence failed (rc %d, expired %u)\n", rc, expired);
        return false;
    }
    return true;
}

int run(const std::string &node, std::uint64_t mib, std::uint64_t chunk_mib, int repeat, bool do_submit) {
    if (do_submit) {
        std::fprintf(stderr, "dmabuf-min: --submit runs a shader on the GPU (GFX ring). A bad "
                             "submission can hang or reset the machine.\n");
    }
    const std::uint64_t bytes = mib << 20, chunk = chunk_mib << 20;
    if (chunk == 0 || bytes % chunk != 0) {
        std::fprintf(stderr, "--mib must be a multiple of --chunk-mib\n");
        return 2;
    }
    const std::size_t chunks = static_cast<std::size_t>(bytes / chunk);

    const int fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (fd < 0) {
        std::perror(node.c_str());
        return 1;
    }
    amdgpu_device_handle dev = nullptr;
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize(fd, &major, &minor, &dev) != 0) {
        std::fprintf(stderr, "amdgpu_device_initialize failed\n");
        return 1;
    }

    // 1. The "physical memory": a sealed memfd, as udmabuf demands (F_SEAL_SHRINK, no F_SEAL_WRITE),
    //    and a MAP_SHARED view of it at a low fixed address, like a guest view.
    const int memfd = static_cast<int>(syscall(SYS_memfd_create, "dmabuf-min", MFD_ALLOW_SEALING));
    if (memfd < 0 || ftruncate(memfd, static_cast<off_t>(bytes)) != 0 ||
        fcntl(memfd, F_ADD_SEALS, F_SEAL_SHRINK) != 0) {
        std::perror("memfd_create/ftruncate/F_ADD_SEALS");
        return 1;
    }
    const std::uint64_t want = 0x6000000000ull;
    void *view = mmap(reinterpret_cast<void *>(want), bytes, PROT_READ | PROT_WRITE,
                      MAP_SHARED | MAP_FIXED_NOREPLACE, memfd, 0);
    if (view == MAP_FAILED) {
        std::perror("mmap view");
        return 1;
    }
    const auto cpu_va = reinterpret_cast<std::uint64_t>(view);
    auto *words = static_cast<std::uint32_t *>(view);
    // Touch only the first page of every chunk: udmabuf has to bring in the rest itself.
    for (std::size_t k = 0; k < chunks; ++k) words[k * chunk / 4] = 0xc0ffee00u + static_cast<std::uint32_t>(k);
    std::printf("memfd: %llu MiB, view at 0x%llx, %zu chunks of %llu MiB\n",
                static_cast<unsigned long long>(mib), static_cast<unsigned long long>(cpu_va), chunks,
                static_cast<unsigned long long>(chunk_mib));

    // 2. One udmabuf per chunk, imported into amdgpu, mapped at GPU VA == CPU VA of the view.
    const int ud = open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
    if (ud < 0) {
        std::perror("/dev/udmabuf");
        return 1;
    }
    std::vector<amdgpu_bo_handle> imported(chunks, nullptr);
    double t_create = 0, t_import = 0, t_map = 0;
    for (std::size_t k = 0; k < chunks; ++k) {
        udmabuf_create c{};
        c.memfd = static_cast<std::uint32_t>(memfd);
        c.flags = UDMABUF_FLAGS_CLOEXEC;
        c.offset = k * chunk;
        c.size = chunk;
        double t0 = now_ms();
        const int buf = ioctl(ud, UDMABUF_CREATE, &c);
        double t1 = now_ms();
        if (buf < 0) {
            std::perror("UDMABUF_CREATE");
            return 1;
        }
        amdgpu_bo_import_result res{};
        int rc = amdgpu_bo_import(dev, amdgpu_bo_handle_type_dma_buf_fd, static_cast<std::uint32_t>(buf), &res);
        double t2 = now_ms();
        close(buf); // the BO keeps the dma-buf
        if (rc != 0) {
            std::fprintf(stderr, "amdgpu_bo_import(dma-buf) failed: %d (%s)\n", rc, std::strerror(-rc));
            return 1;
        }
        imported[k] = res.buf_handle;
        if (k == 0) {
            amdgpu_bo_info info{};
            amdgpu_bo_query_info(res.buf_handle, &info);
            std::printf("imported BO: alloc_size %llu, preferred_heap 0x%x, alloc_flags 0x%llx\n",
                        static_cast<unsigned long long>(res.alloc_size), info.preferred_heap,
                        static_cast<unsigned long long>(info.alloc_flags));
        }
        rc = amdgpu_bo_va_op(res.buf_handle, 0, chunk, cpu_va + k * chunk, 0, AMDGPU_VA_OP_MAP);
        double t3 = now_ms();
        if (rc != 0) {
            std::fprintf(stderr, "amdgpu_bo_va_op(MAP at 0x%llx) failed: %d (%s)\n",
                         static_cast<unsigned long long>(cpu_va + k * chunk), rc, std::strerror(-rc));
            return 1;
        }
        t_create += t1 - t0;
        t_import += t2 - t1;
        t_map += t3 - t2;
    }
    std::printf("per chunk: UDMABUF_CREATE %.2f ms, amdgpu import %.2f ms, VA map %.3f ms\n",
                t_create / static_cast<double>(chunks), t_import / static_cast<double>(chunks),
                t_map / static_cast<double>(chunks));
    std::uint64_t kept = 0;
    for (std::size_t k = 0; k < chunks; ++k) kept += words[k * chunk / 4] == 0xc0ffee00u + k ? 1u : 0u;
    std::printf("view contents after the imports: %llu of %zu chunk markers intact\n",
                static_cast<unsigned long long>(kept), chunks);
    if (!do_submit) {
        std::printf("import and VA map: OK (no submission)\n");
        return kept == chunks ? 0 : 1;
    }

    // 3. The memset dispatch writes the first chunk through its guest address.
    // One command BO per IB: an IB rewritten in place can be executed from the GPU's stale copy
    // (F25; the first version of this tool reran the first fill that way).
    Vram shader, cmd, cmd2, cmd3;
    if (!alloc_bo(dev, 4096, AMDGPU_GEM_DOMAIN_VRAM, shader) || !alloc_bo(dev, 4096, AMDGPU_GEM_DOMAIN_GTT, cmd) ||
        !alloc_bo(dev, 4096, AMDGPU_GEM_DOMAIN_GTT, cmd2) || !alloc_bo(dev, 4096, AMDGPU_GEM_DOMAIN_GTT, cmd3)) {
        std::fprintf(stderr, "buffer allocation failed\n");
        return 1;
    }
    std::memset(shader.cpu, 0, 4096);
    std::memcpy(shader.cpu, bc5::dispatch_min::kBufferClearCsGfx10.data(),
                sizeof(bc5::dispatch_min::kBufferClearCsGfx10));
    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(dev, &ctx) != 0) return 1;

    int failures = 0;
    {
        std::vector<amdgpu_bo_handle> bos = {shader.bo, cmd.bo, cmd2.bo, imported[0]};
        amdgpu_bo_list_handle list = nullptr;
        if (amdgpu_bo_list_create(dev, static_cast<std::uint32_t>(bos.size()), bos.data(), nullptr, &list) != 0) return 1;
        const std::uint32_t value = 0x5a17da7au;
        bc5::dispatch_min::MemsetParams p;
        p.shader_va = shader.va;
        p.dst_va = cpu_va;
        p.dst_bytes = static_cast<std::uint32_t>(chunk);
        p.value = value;
        p.rsrc1 = bc5::dispatch_min::kConsoleRsrc1;
        p.vsharp_word3 = bc5::dispatch_min::kConsoleVsharpWord3;
        const auto ib = bc5::dispatch_min::build_memset_ib(p);
        std::memcpy(cmd.cpu, ib.data(), ib.size() * sizeof(std::uint32_t));
        double cs = 0, fence = 0;
        if (!submit_ib(ctx, list, cmd.va, static_cast<std::uint32_t>(ib.size()), cs, fence)) return 1;
        std::uint64_t bad = 0;
        for (std::uint64_t i = 0; i < chunk / 4; ++i) bad += words[i] != value ? 1u : 0u;
        std::printf("gpu fill of chunk 0 through its guest address: cs %.2f ms, fence %.2f ms; %llu of %llu "
                    "dwords differ from 0x%08x in the memfd view\n",
                    cs, fence, static_cast<unsigned long long>(bad), static_cast<unsigned long long>(chunk / 4),
                    value);
        // and the other way: the CPU writes, a second fill of half the chunk leaves the rest alone
        for (std::uint64_t i = chunk / 8; i < chunk / 4; ++i) words[i] = 0x0badf00du;
        p.dst_bytes = static_cast<std::uint32_t>(chunk / 2);
        p.value = 0x11223344u;
        const auto ib2 = bc5::dispatch_min::build_memset_ib(p);
        std::memcpy(cmd2.cpu, ib2.data(), ib2.size() * sizeof(std::uint32_t));
        if (!submit_ib(ctx, list, cmd2.va, static_cast<std::uint32_t>(ib2.size()), cs, fence)) return 1;
        std::uint64_t bad2 = 0;
        for (std::uint64_t i = 0; i < chunk / 8; ++i) bad2 += words[i] != 0x11223344u ? 1u : 0u;
        for (std::uint64_t i = chunk / 8; i < chunk / 4; ++i) bad2 += words[i] != 0x0badf00du ? 1u : 0u;
        std::printf("second fill (half the chunk) next to CPU-written data: %llu wrong dwords (first dword 0x%08x, "
                    "first of the CPU half 0x%08x)\n",
                    static_cast<unsigned long long>(bad2), words[0], words[chunk / 8]);
        if (bad != 0 || bad2 != 0) failures++;
        amdgpu_bo_list_destroy(list);
    }

    // 4. What a CS costs with every chunk on the list: imported dma-bufs against userptr BOs
    //    over as much anonymous memory. The IB is a few NOPs.
    for (std::uint32_t i = 0; i < 16; ++i) static_cast<std::uint32_t *>(cmd3.cpu)[i] = 0xffff1000u;
    auto time_list = [&](const std::vector<amdgpu_bo_handle> &extra, const char *name) {
        std::vector<amdgpu_bo_handle> bos = {cmd3.bo};
        bos.insert(bos.end(), extra.begin(), extra.end());
        amdgpu_bo_list_handle list = nullptr;
        if (amdgpu_bo_list_create(dev, static_cast<std::uint32_t>(bos.size()), bos.data(), nullptr, &list) != 0) {
            std::fprintf(stderr, "bo list (%s) failed\n", name);
            failures++;
            return;
        }
        std::vector<double> cs_times;
        double fence_sum = 0;
        for (int r = 0; r < repeat; ++r) {
            double cs = 0, fence = 0;
            if (!submit_ib(ctx, list, cmd3.va, 16, cs, fence)) {
                failures++;
                break;
            }
            cs_times.push_back(cs);
            fence_sum += fence;
        }
        amdgpu_bo_list_destroy(list);
        if (cs_times.empty()) return;
        std::sort(cs_times.begin(), cs_times.end());
        std::printf("CS with %zu %s BOs (%llu MiB): first-sorted min %.3f ms, median %.3f ms, max %.3f ms; "
                    "fence avg %.3f ms\n",
                    extra.size(), name, static_cast<unsigned long long>(mib), cs_times.front(),
                    cs_times[cs_times.size() / 2], cs_times.back(), fence_sum / static_cast<double>(cs_times.size()));
    };
    time_list({}, "no extra");
    time_list(imported, "imported dma-buf");

    void *anon = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_POPULATE, -1, 0);
    if (anon == MAP_FAILED) {
        std::perror("mmap anon");
        return 1;
    }
    std::vector<amdgpu_bo_handle> userptrs;
    for (std::size_t k = 0; k < chunks; ++k) {
        amdgpu_bo_handle bo = nullptr;
        auto *p = static_cast<std::uint8_t *>(anon) + k * chunk;
        if (amdgpu_create_bo_from_user_mem(dev, p, chunk, &bo) != 0 ||
            amdgpu_bo_va_op(bo, 0, chunk, reinterpret_cast<std::uint64_t>(p), 0, AMDGPU_VA_OP_MAP) != 0) {
            std::fprintf(stderr, "userptr chunk %zu failed\n", k);
            return 1;
        }
        userptrs.push_back(bo);
    }
    time_list(userptrs, "userptr");
    amdgpu_cs_ctx_free(ctx);
    return failures == 0 ? 0 : 1;
}

#endif // BC5_WITH_AMDGPU

} // namespace

int main(int argc, char **argv) {
    std::string mode;
    std::string node = "/dev/dri/renderD128";
    std::uint64_t mib = 256, chunk_mib = 32;
    int repeat = 50;
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--info") mode = "info";
        else if (a == "--import") mode = "import";
        else if (a == "--submit") mode = "submit";
        else if (a == "--render-node" && i + 1 < argc) node = argv[++i];
        else if (a == "--mib" && i + 1 < argc) mib = std::stoull(argv[++i]);
        else if (a == "--chunk-mib" && i + 1 < argc) chunk_mib = std::stoull(argv[++i]);
        else if (a == "--repeat" && i + 1 < argc) repeat = std::stoi(argv[++i]);
        else return usage();
    }
    if (mode == "info") {
        std::printf("dmabuf-min: a sealed memfd of %llu MiB viewed at a fixed address, %llu MiB udmabuf "
                    "chunks imported into amdgpu and mapped at GPU VA == CPU VA. --import stops there; "
                    "--submit fills chunk 0 on the GPU, verifies it through the view and times a CS "
                    "that lists all chunks against userptr BOs. Needs BC5_WITH_AMDGPU.\n",
                    static_cast<unsigned long long>(mib), static_cast<unsigned long long>(chunk_mib));
        return 0;
    }
#ifdef BC5_WITH_AMDGPU
    if (mode == "import") return run(node, mib, chunk_mib, repeat, false);
    if (mode == "submit") return run(node, mib, chunk_mib, repeat, true);
#else
    (void)node;
    (void)repeat;
    if (mode == "import" || mode == "submit") {
        std::fputs("built without BC5_WITH_AMDGPU; only --info is available\n", stderr);
        return 2;
    }
#endif
    return usage();
}
