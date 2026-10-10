// SPDX-License-Identifier: GPL-2.0-only
// dispatch-min: phase-2 native compute dispatch (docs/decisions/0004-dispatch-min.md).
//
//   dispatch-min --dump-ib <file>   build the memset IB for placeholder VAs, write raw dwords
//   dispatch-min --info             (BC5_WITH_AMDGPU) print what the kernel reports; read-only
//   dispatch-min --submit           (BC5_WITH_AMDGPU) run it on the GFX ring. OFF by default.
//
// Hard rule 5 (CLAUDE.md): --submit can hang or reset the machine. It is never run by tests,
// CI or scripts, and only after the maintainer confirms the box is idle.
#include "bc5/dispatch_min.hpp"
#include "bc5/pm4.hpp"

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fstream>
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
#endif

namespace {

struct Options {
    std::string node = "/dev/dri/renderD128";
    std::uint32_t bytes = 16384;
    std::uint32_t value = 0x22222222u;
    std::uint32_t rsrc1 = bc5::dispatch_min::kIgtRsrc1;
    std::uint32_t rsrc2 = bc5::dispatch_min::kIgtRsrc2;
    std::uint32_t vsharp3 = bc5::dispatch_min::kIgtVsharpWord3;
    std::uint32_t cu_mask = 0xffffffffu; // --cu-mask HEX: COMPUTE_STATIC_THREAD_MGMT_SE0..3
    int repeat = 1;                      // --repeat N: submit the same IB N times, time each
    std::string shader_file; // raw little-endian dwords; empty = the built-in IGT program
    std::string ib_file;     // --ib-file: submit these raw dwords as the IB instead (replay)
    // --ip compute [--ring N]: submit on the kernel's compute rings (AMDGPU_HW_IP_COMPUTE, four on
    // the BC-250: comp_1.0.0 .. comp_1.3.0) instead of the GFX ring. RADV leaves them unused on
    // gfx1013 (HANDOFF F6); whether they work for us is experiment 0016 step (e).
    unsigned ip = 0;         // AMDGPU_HW_IP_GFX
    unsigned ring = 0;
    // --dst vram|gtt|gtt-uswc|udmabuf: where the program writes (experiment 0043: the bandwidth
    // of the memory kinds the game's memory could live in; udmabuf = a memfd handed to amdgpu as
    // dma-bufs in chunks, as the direct path imports the game's memory, ADR 0006).
    std::string dst = "vram";
    int print = 0; // --print N: the first N 16-byte records after the last run (experiment 0043)
};

int usage() {
    std::fputs("usage: dispatch-min --dump-ib <file> | --info [--render-node PATH] | --submit "
               "[--render-node PATH] [--bytes N | --groups N] [--value HEX] [--console]\n"
               "       [--rsrc1 HEX] [--rsrc2 HEX] [--vsharp3 HEX] [--shader-file FILE]\n"
               "  --console  RSRC1/RSRC2/V# word 3 as Sony's libSceAgc dispatches the same program\n"
               "  --dst vram|gtt|gtt-uswc|udmabuf  the memory the program writes (default vram)\n",
               stderr);
    return 2;
}

std::vector<std::uint32_t> load_shader(const std::string &path) {
    std::vector<std::uint32_t> code;
    std::ifstream in(path, std::ios::binary);
    if (!in) return code;
    unsigned char b[4];
    while (in.read(reinterpret_cast<char *>(b), 4)) {
        code.push_back(static_cast<std::uint32_t>(b[0]) | (static_cast<std::uint32_t>(b[1]) << 8) |
                       (static_cast<std::uint32_t>(b[2]) << 16) |
                       (static_cast<std::uint32_t>(b[3]) << 24));
    }
    // Keep the program up to its first s_endpgm (captures may carry padding after it).
    for (std::size_t i = 0; i < code.size(); ++i) {
        if (code[i] == 0xBF810000u) {
            code.resize(i + 1);
            break;
        }
    }
    return code;
}

int dump_ib(const std::string &path) {
    bc5::dispatch_min::MemsetParams p;
    p.shader_va = 0x0000'0001'0000'0000ull; // placeholders; real VAs come from amdgpu
    p.dst_va = 0x0000'0001'0001'0000ull;
    const auto ib = bc5::dispatch_min::build_memset_ib(p);
    std::ofstream out(path, std::ios::binary);
    for (std::uint32_t w : ib) {
        const unsigned char b[4] = {static_cast<unsigned char>(w & 0xff),
                                    static_cast<unsigned char>((w >> 8) & 0xff),
                                    static_cast<unsigned char>((w >> 16) & 0xff),
                                    static_cast<unsigned char>((w >> 24) & 0xff)};
        out.write(reinterpret_cast<const char *>(b), 4);
    }
    if (!out) {
        std::fprintf(stderr, "cannot write %s\n", path.c_str());
        return 1;
    }
    std::printf("wrote %zu dwords to %s\n", ib.size(), path.c_str());
    return 0;
}

std::vector<std::uint32_t> load_dwords(const std::string &path) {
    std::vector<std::uint32_t> words;
    std::ifstream in(path, std::ios::binary);
    unsigned char b[4];
    while (in && in.read(reinterpret_cast<char *>(b), 4)) {
        words.push_back(static_cast<std::uint32_t>(b[0]) | (static_cast<std::uint32_t>(b[1]) << 8) |
                        (static_cast<std::uint32_t>(b[2]) << 16) |
                        (static_cast<std::uint32_t>(b[3]) << 24));
    }
    return words;
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

bool open_device(const std::string &node, Device &d) {
    d.fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (d.fd < 0) {
        std::perror(node.c_str());
        return false;
    }
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize(d.fd, &major, &minor, &d.dev) != 0) {
        std::fprintf(stderr, "amdgpu_device_initialize failed on %s\n", node.c_str());
        return false;
    }
    return true;
}

int info(const std::string &node) {
    Device d;
    if (!open_device(node, d)) return 1;
    amdgpu_gpu_info gi{};
    if (amdgpu_query_gpu_info(d.dev, &gi) != 0) return 1;
    drm_amdgpu_info_device dev_info{};
    amdgpu_query_info(d.dev, AMDGPU_INFO_DEV_INFO, sizeof(dev_info), &dev_info);
    drm_amdgpu_info_hw_ip gfx{};
    amdgpu_query_hw_ip_info(d.dev, AMDGPU_HW_IP_GFX, 0, &gfx);
    drm_amdgpu_info_hw_ip compute{};
    amdgpu_query_hw_ip_info(d.dev, AMDGPU_HW_IP_COMPUTE, 0, &compute);
    std::printf("family %u, chip external rev 0x%x, asic id 0x%x\n", gi.family_id,
                gi.chip_external_rev, gi.asic_id);
    std::printf("CUs reported by the kernel: %u active (SE %u, SH/SE %u)\n",
                dev_info.cu_active_number, dev_info.num_shader_engines,
                dev_info.num_shader_arrays_per_engine);
    std::printf("GFX rings available: mask 0x%x; compute rings: mask 0x%x\n", gfx.available_rings,
                compute.available_rings);
    std::printf("note: the kernel count excludes CUs routed after boot (experiment 0004)\n");
    return 0;
}

struct Bo {
    amdgpu_device_handle dev = nullptr;
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr;
    std::uint64_t va = 0;
    void *cpu = nullptr;
    std::uint64_t size = 0;
    ~Bo() {
        if (cpu) amdgpu_bo_cpu_unmap(bo);
        if (va) amdgpu_bo_va_op(bo, 0, size, va, 0, AMDGPU_VA_OP_UNMAP);
        if (va_handle) amdgpu_va_range_free(va_handle);
        if (bo) amdgpu_bo_free(bo);
    }
};

bool alloc(amdgpu_device_handle dev, std::uint64_t size, std::uint32_t domain, Bo &b,
           std::uint64_t flags = 0) {
    b.dev = dev;
    b.size = size;
    amdgpu_bo_alloc_request req{};
    req.alloc_size = size;
    req.phys_alignment = 4096;
    req.preferred_heap = domain;
    req.flags = flags;
    if (amdgpu_bo_alloc(dev, &req, &b.bo) != 0) return false;
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &b.va,
                              &b.va_handle, 0) != 0)
        return false;
    if (amdgpu_bo_va_op(b.bo, 0, size, b.va, 0, AMDGPU_VA_OP_MAP) != 0) return false;
    return amdgpu_bo_cpu_map(b.bo, &b.cpu) == 0;
}

// A memfd handed to amdgpu as udmabufs of 32 MiB (the module's default limit), imported and
// mapped back to back at one GPU VA range; the CPU sees the memfd through its own mapping.
struct Imported {
    int memfd = -1;
    void *cpu = nullptr;
    std::uint64_t size = 0, chunk = 0, va = 0;
    amdgpu_va_handle va_handle = nullptr;
    std::vector<amdgpu_bo_handle> bos;
    ~Imported() {
        for (std::size_t k = 0; k < bos.size(); ++k) {
            amdgpu_bo_va_op(bos[k], 0, chunk, va + k * chunk, 0, AMDGPU_VA_OP_UNMAP);
            amdgpu_bo_free(bos[k]);
        }
        if (va_handle) amdgpu_va_range_free(va_handle);
        if (cpu) munmap(cpu, size);
        if (memfd >= 0) close(memfd);
    }
};

bool import_udmabuf(amdgpu_device_handle dev, std::uint64_t size, Imported &m) {
    m.chunk = 32ull << 20;
    if (size % m.chunk != 0) m.chunk = size; // small buffers: one chunk
    m.size = size;
    m.memfd = static_cast<int>(syscall(SYS_memfd_create, "dispatch-min", MFD_ALLOW_SEALING));
    if (m.memfd < 0 || ftruncate(m.memfd, static_cast<off_t>(size)) != 0 ||
        fcntl(m.memfd, F_ADD_SEALS, F_SEAL_SHRINK) != 0) {
        std::perror("memfd");
        return false;
    }
    m.cpu = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_SHARED, m.memfd, 0);
    if (m.cpu == MAP_FAILED) {
        m.cpu = nullptr;
        return false;
    }
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 2ull << 20, 0, &m.va,
                              &m.va_handle, 0) != 0)
        return false;
    const int ud = open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
    if (ud < 0) {
        std::perror("/dev/udmabuf");
        return false;
    }
    for (std::uint64_t off = 0; off < size; off += m.chunk) {
        udmabuf_create c{};
        c.memfd = static_cast<std::uint32_t>(m.memfd);
        c.flags = UDMABUF_FLAGS_CLOEXEC;
        c.offset = off;
        c.size = m.chunk;
        const int buf = ioctl(ud, UDMABUF_CREATE, &c);
        if (buf < 0) {
            std::perror("UDMABUF_CREATE");
            close(ud);
            return false;
        }
        amdgpu_bo_import_result res{};
        const int rc = amdgpu_bo_import(dev, amdgpu_bo_handle_type_dma_buf_fd,
                                        static_cast<std::uint32_t>(buf), &res);
        close(buf);
        if (rc != 0 ||
            amdgpu_bo_va_op(res.buf_handle, 0, m.chunk, m.va + off, 0, AMDGPU_VA_OP_MAP) != 0) {
            std::fprintf(stderr, "udmabuf import or map failed at +0x%llx\n",
                         static_cast<unsigned long long>(off));
            close(ud);
            return false;
        }
        m.bos.push_back(res.buf_handle);
    }
    close(ud);
    return true;
}

int submit(const Options &o) {
    std::fprintf(stderr, "dispatch-min: --submit runs a shader on the GPU (GFX ring). A bad "
                         "submission can hang or reset the machine.\n");
    const std::uint32_t bytes = o.bytes;
    std::vector<std::uint32_t> code(bc5::dispatch_min::kBufferClearCsGfx10.begin(),
                                    bc5::dispatch_min::kBufferClearCsGfx10.end());
    if (!o.shader_file.empty()) {
        code = load_shader(o.shader_file);
        if (code.empty() || code.size() > 1024) {
            std::fprintf(stderr, "cannot load a shader of 1..1024 dwords from %s\n",
                         o.shader_file.c_str());
            return 1;
        }
        const bool same = code.size() == bc5::dispatch_min::kBufferClearCsGfx10.size() &&
                          std::equal(code.begin(), code.end(),
                                     bc5::dispatch_min::kBufferClearCsGfx10.begin());
        std::printf("shader: %zu dwords from %s (%s the built-in IGT buffer-clear program)\n",
                    code.size(), o.shader_file.c_str(), same ? "identical to" : "differs from");
    }
    Device d;
    if (!open_device(o.node, d)) return 1;

    Bo shader, dst, cmd;
    Imported imp;
    std::vector<amdgpu_bo_handle> dst_bos;
    std::uint64_t dst_va = 0;
    void *dst_cpu = nullptr;
    bool ok = alloc(d.dev, 4096, AMDGPU_GEM_DOMAIN_VRAM, shader) &&
              alloc(d.dev, 4096, AMDGPU_GEM_DOMAIN_GTT, cmd);
    if (ok && o.dst == "udmabuf") {
        ok = import_udmabuf(d.dev, bytes, imp);
        dst_va = imp.va;
        dst_cpu = imp.cpu;
        dst_bos = imp.bos;
    } else if (ok) {
        const bool vram = o.dst == "vram";
        ok = alloc(d.dev, bytes, vram ? AMDGPU_GEM_DOMAIN_VRAM : AMDGPU_GEM_DOMAIN_GTT, dst,
                   o.dst == "gtt-uswc" ? AMDGPU_GEM_CREATE_CPU_GTT_USWC : 0);
        dst_bos = {dst.bo};
        dst_va = dst.va;
        dst_cpu = dst.cpu;
    }
    if (!ok) {
        std::fprintf(stderr, "buffer allocation failed (--dst %s)\n", o.dst.c_str());
        return 1;
    }
    std::memset(shader.cpu, 0, 4096);
    std::memcpy(shader.cpu, code.data(), code.size() * sizeof(std::uint32_t));
    std::memset(dst_cpu, 0, bytes);
    std::printf("destination: %s, %u bytes at GPU VA 0x%llx in %zu BO(s)\n", o.dst.c_str(), bytes,
                static_cast<unsigned long long>(dst_va), dst_bos.size());

    bc5::dispatch_min::MemsetParams p;
    p.shader_va = shader.va;
    p.dst_va = dst_va;
    p.dst_bytes = bytes;
    p.cu_mask = o.cu_mask;
    p.value = o.value;
    p.rsrc1 = o.rsrc1;
    p.rsrc2 = o.rsrc2;
    p.vsharp_word3 = o.vsharp3;
    std::printf("dispatch: %u bytes (%u groups), value 0x%08x, rsrc1 0x%08x rsrc2 0x%08x v# word3 "
                "0x%08x\n",
                bytes, bytes / bc5::dispatch_min::kBytesPerGroup, o.value, o.rsrc1, o.rsrc2,
                o.vsharp3);
    std::vector<std::uint32_t> ib = bc5::dispatch_min::build_memset_ib(p);
    if (!o.ib_file.empty()) {
        // Replay: the recorded IB as-is (already filtered/padded by the recorder), only the
        // command BO in the list. The destination check below is meaningless then.
        ib = load_dwords(o.ib_file);
        if (ib.empty() || ib.size() * 4 > 4096) {
            std::fprintf(stderr, "cannot load an IB of 1..1024 dwords from %s\n", o.ib_file.c_str());
            return 1;
        }
        while (ib.size() % 8 != 0) ib.push_back(bc5::pm4::kNopFiller);
        std::printf("replay: %zu dwords from %s (padded to 8)\n", ib.size(), o.ib_file.c_str());
    }
    std::memcpy(cmd.cpu, ib.data(), ib.size() * sizeof(std::uint32_t));

    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(d.dev, &ctx) != 0) return 1;
    std::vector<amdgpu_bo_handle> list_bos = {shader.bo, cmd.bo};
    list_bos.insert(list_bos.end(), dst_bos.begin(), dst_bos.end());
    amdgpu_bo_list_handle list = nullptr;
    if (amdgpu_bo_list_create(d.dev, static_cast<std::uint32_t>(list_bos.size()), list_bos.data(),
                              nullptr, &list) != 0)
        return 1;

    amdgpu_cs_ib_info ib_info{};
    ib_info.ib_mc_address = cmd.va;
    ib_info.size = static_cast<std::uint32_t>(ib.size());
    amdgpu_cs_request req{};
    req.ip_type = o.ip; // GFX by default (HANDOFF F6); --ip compute tries the MEC rings
    req.ring = o.ring;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &ib_info;

    // --repeat N: the same IB N times, each timed from the submit to its fence (experiment 0019:
    // throughput against the CU mask). The first run also pays for the first touch of the BOs.
    int rc = 0;
    std::uint32_t expired = 0;
    std::vector<double> times;
    for (int r = 0; r < (o.repeat < 1 ? 1 : o.repeat); ++r) {
        const auto t0 = std::chrono::steady_clock::now();
        rc = amdgpu_cs_submit(ctx, 0, &req, 1);
        expired = 0;
        if (rc == 0) {
            amdgpu_cs_fence fence{};
            fence.context = ctx;
            fence.ip_type = o.ip;
            fence.ring = o.ring;
            fence.fence = req.seq_no;
            rc = amdgpu_cs_query_fence_status(&fence, 2'000'000'000ull /* 2 s */, 0, &expired);
        }
        if (rc != 0 || !expired) break;
        times.push_back(std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count());
    }
    if (o.repeat > 1 && !times.empty()) {
        std::vector<double> sorted(times.begin() + (times.size() > 2 ? 1 : 0), times.end());
        std::sort(sorted.begin(), sorted.end());
        std::printf("cu mask 0x%08x, --dst %s: %zu runs, submit to fence: min %.3f ms, median %.3f ms, "
                    "max %.3f ms (first run %.3f ms, left out); %.1f GB/s at the median\n",
                    o.cu_mask, o.dst.c_str(), times.size(), sorted.front(), sorted[sorted.size() / 2],
                    sorted.back(), times.front(), bytes / (sorted[sorted.size() / 2] * 1e6));
    }
    amdgpu_bo_list_destroy(list);
    amdgpu_cs_ctx_free(ctx);
    if (rc != 0 || !expired) {
        std::fprintf(stderr, "submit or fence failed (rc %d, expired %u)\n", rc, expired);
        return 1;
    }
    if (!o.ib_file.empty()) {
        std::printf("replay done: fence signalled\n");
        return 0;
    }
    // CPU reference of the program: every 16-byte record holds the value in all four dwords.
    const auto *out = static_cast<const std::uint32_t *>(dst_cpu);
    if (o.print > 0) {
        drm_amdgpu_info_device di{};
        amdgpu_query_info(d.dev, AMDGPU_INFO_DEV_INFO, sizeof(di), &di);
        std::printf("gpu_counter_freq %u kHz (the s_memrealtime rate)\n", di.gpu_counter_freq);
        for (int r = 0; r < o.print && static_cast<std::uint32_t>(r) * 16 < bytes; ++r) {
            std::printf("record %d: %08x %08x %08x %08x", r, out[r * 4], out[r * 4 + 1], out[r * 4 + 2],
                        out[r * 4 + 3]);
            if (out[r * 4 + 1] != 0)
                std::printf("  (dword0 / dword1 x counter rate = %.1f MHz)",
                            static_cast<double>(out[r * 4]) / out[r * 4 + 1] * di.gpu_counter_freq / 1000.0);
            std::printf("\n");
        }
    }
    std::uint32_t bad = 0;
    for (std::uint32_t i = 0; i < bytes / 4; ++i) bad += out[i] != o.value ? 1u : 0u;
    std::printf("dispatch done: %u of %u dwords differ from 0x%08x\n", bad, bytes / 4, o.value);
    return bad == 0 ? 0 : 1;
}

#endif // BC5_WITH_AMDGPU

} // namespace

int main(int argc, char **argv) {
    std::string mode;
    std::string arg;
    Options o;
    auto hex = [](const char *s) { return static_cast<std::uint32_t>(std::stoul(s, nullptr, 16)); };
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--dump-ib" && i + 1 < argc) {
            mode = "dump";
            arg = argv[++i];
        } else if (a == "--info") {
            mode = "info";
        } else if (a == "--submit") {
            mode = "submit";
        } else if (a == "--render-node" && i + 1 < argc) {
            o.node = argv[++i];
        } else if (a == "--bytes" && i + 1 < argc) {
            o.bytes = static_cast<std::uint32_t>(std::stoul(argv[++i]));
        } else if (a == "--groups" && i + 1 < argc) {
            o.bytes = static_cast<std::uint32_t>(std::stoul(argv[++i])) *
                      bc5::dispatch_min::kBytesPerGroup;
        } else if (a == "--cu-mask" && i + 1 < argc) {
            o.cu_mask = static_cast<std::uint32_t>(std::stoul(argv[++i], nullptr, 16));
        } else if (a == "--repeat" && i + 1 < argc) {
            o.repeat = std::stoi(argv[++i]);
        } else if (a == "--value" && i + 1 < argc) {
            o.value = hex(argv[++i]);
        } else if (a == "--rsrc1" && i + 1 < argc) {
            o.rsrc1 = hex(argv[++i]);
        } else if (a == "--rsrc2" && i + 1 < argc) {
            o.rsrc2 = hex(argv[++i]);
        } else if (a == "--vsharp3" && i + 1 < argc) {
            o.vsharp3 = hex(argv[++i]);
        } else if (a == "--shader-file" && i + 1 < argc) {
            o.shader_file = argv[++i];
        } else if (a == "--ib-file" && i + 1 < argc) {
            o.ib_file = argv[++i];
        } else if (a == "--ip" && i + 1 < argc) {
            const std::string v = argv[++i];
            o.ip = v == "compute" ? AMDGPU_HW_IP_COMPUTE : AMDGPU_HW_IP_GFX;
        } else if (a == "--ring" && i + 1 < argc) {
            o.ring = static_cast<unsigned>(std::stoul(argv[++i]));
        } else if (a == "--print" && i + 1 < argc) {
            o.print = std::stoi(argv[++i]);
        } else if (a == "--dst" && i + 1 < argc) {
            o.dst = argv[++i];
            if (o.dst != "vram" && o.dst != "gtt" && o.dst != "gtt-uswc" && o.dst != "udmabuf")
                return usage();
        } else if (a == "--console") {
            o.rsrc1 = bc5::dispatch_min::kConsoleRsrc1;
            o.rsrc2 = bc5::dispatch_min::kConsoleRsrc2;
            o.vsharp3 = bc5::dispatch_min::kConsoleVsharpWord3;
        } else {
            return usage();
        }
    }
    if (mode == "dump") return dump_ib(arg);
#ifdef BC5_WITH_AMDGPU
    if (mode == "info") return info(o.node);
    if (mode == "submit") return submit(o);
#else
    (void)o;
    if (mode == "info" || mode == "submit") {
        std::fputs("built without BC5_WITH_AMDGPU; only --dump-ib is available\n", stderr);
        return 2;
    }
#endif
    return usage();
}
