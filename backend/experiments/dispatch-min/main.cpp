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
    std::string shader_file; // raw little-endian dwords; empty = the built-in IGT program
    std::string ib_file;     // --ib-file: submit these raw dwords as the IB instead (replay)
    // --ip compute [--ring N]: submit on the kernel's compute rings (AMDGPU_HW_IP_COMPUTE, four on
    // the BC-250: comp_1.0.0 .. comp_1.3.0) instead of the GFX ring. RADV leaves them unused on
    // gfx1013 (HANDOFF F6); whether they work for us is experiment 0016 step (e).
    unsigned ip = 0;         // AMDGPU_HW_IP_GFX
    unsigned ring = 0;
};

int usage() {
    std::fputs("usage: dispatch-min --dump-ib <file> | --info [--render-node PATH] | --submit "
               "[--render-node PATH] [--bytes N | --groups N] [--value HEX] [--console]\n"
               "       [--rsrc1 HEX] [--rsrc2 HEX] [--vsharp3 HEX] [--shader-file FILE]\n"
               "  --console  RSRC1/RSRC2/V# word 3 as Sony's libSceAgc dispatches the same program\n",
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

bool alloc(amdgpu_device_handle dev, std::uint64_t size, std::uint32_t domain, Bo &b) {
    b.dev = dev;
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
    return amdgpu_bo_cpu_map(b.bo, &b.cpu) == 0;
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
    if (!alloc(d.dev, 4096, AMDGPU_GEM_DOMAIN_VRAM, shader) ||
        !alloc(d.dev, bytes, AMDGPU_GEM_DOMAIN_VRAM, dst) ||
        !alloc(d.dev, 4096, AMDGPU_GEM_DOMAIN_GTT, cmd)) {
        std::fprintf(stderr, "buffer allocation failed\n");
        return 1;
    }
    std::memset(shader.cpu, 0, 4096);
    std::memcpy(shader.cpu, code.data(), code.size() * sizeof(std::uint32_t));
    std::memset(dst.cpu, 0, bytes);

    bc5::dispatch_min::MemsetParams p;
    p.shader_va = shader.va;
    p.dst_va = dst.va;
    p.dst_bytes = bytes;
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
    amdgpu_bo_handle list_bos[3] = {shader.bo, dst.bo, cmd.bo};
    amdgpu_bo_list_handle list = nullptr;
    if (amdgpu_bo_list_create(d.dev, 3, list_bos, nullptr, &list) != 0) return 1;

    amdgpu_cs_ib_info ib_info{};
    ib_info.ib_mc_address = cmd.va;
    ib_info.size = static_cast<std::uint32_t>(ib.size());
    amdgpu_cs_request req{};
    req.ip_type = opt.ip; // GFX by default (HANDOFF F6); --ip compute tries the MEC rings
    req.ring = opt.ring;
    req.resources = list;
    req.number_of_ibs = 1;
    req.ibs = &ib_info;

    int rc = amdgpu_cs_submit(ctx, 0, &req, 1);
    std::uint32_t expired = 0;
    if (rc == 0) {
        amdgpu_cs_fence fence{};
        fence.context = ctx;
        fence.ip_type = opt.ip;
        fence.ring = opt.ring;
        fence.fence = req.seq_no;
        rc = amdgpu_cs_query_fence_status(&fence, 2'000'000'000ull /* 2 s */, 0, &expired);
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
    const auto *out = static_cast<const std::uint32_t *>(dst.cpu);
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
            opt.ip = v == "compute" ? AMDGPU_HW_IP_COMPUTE : AMDGPU_HW_IP_GFX;
        } else if (a == "--ring" && i + 1 < argc) {
            opt.ring = static_cast<unsigned>(std::stoul(argv[++i]));
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
