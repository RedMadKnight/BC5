// SPDX-License-Identifier: GPL-2.0-only
// libScePsml re-creation, sub-library libScePsml_mfsr2 (MFSR2 / "KPN9"): initialise, shared
// resources with the KPN9 package, contexts, and the dispatch recorder (frame constants, pre/post
// passes, the 17-pass or persistent network, tile tables, tensor descriptor table).
//
// Per the original module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md).
// Object layouts not visible to callers follow the description's offsets so the recorded GPU work
// sees the same data the original's shaders expect.
#include "bc5/reimpl/psml_internal.hpp"

#include <atomic>
#include <cmath>
#include <cstring>
#include <limits>
#include <vector>

namespace bc5::reimpl::psml {

using namespace detail;

namespace {

constexpr const char *kPrefix = "sce::Psml::Mfsr2::";
constexpr std::uint64_t kSharedVa = 0xf800000000ull;
constexpr std::uint64_t kContextStride = 0x08000000ull;
constexpr std::uint64_t kScratchSize = 0x0d600000ull;
constexpr std::uint64_t kScratchAlign = 0x10000ull;
constexpr std::uint64_t kSharedObjectSize = 0x430;
constexpr std::uint64_t kParamBlockSize = 0x400;
constexpr std::uint32_t kMaxW = 3840;
constexpr std::uint32_t kMaxH = 2160;
constexpr std::uint32_t kCtxMagicCreated = 0x8a32954bu;
constexpr std::uint32_t kCtxMagicDispatched = 0xa853fccau;
constexpr std::uint64_t kNetBlockSize = 0x400;
constexpr std::uint64_t kFrameBlockSize = 0xaa8;
constexpr std::uint64_t kSmallBlockSize = 0x100;
constexpr std::uint64_t kCtxHeaderSize = 0x188;
// Agc format words (data format | swizzle << 32), as the description gives them.
constexpr std::uint64_t kFmtShared = 0x000001ac00000084ull;
constexpr std::uint64_t kFmtT1 = 0x00000fac00000038ull;
constexpr std::uint64_t kFmtTensorT = 0x00000fac0000004bull;
constexpr std::uint64_t kFmtTyped8 = 0x0000022c0000003eull;
constexpr std::uint64_t kFmtSynth1x1 = 0x00000fac00000016ull; // TODO(verify): swizzle choice
constexpr const char *kPackageFile = "KPN9_v070.psp";

// Shader handle indices in state().mfsr2_shaders (handle globals 0x16e180 + 8*i).
constexpr int kShReprojection = 0;
constexpr int kShPostPlain = 2;
constexpr int kShPostSharpen = 3;
constexpr int kShHalfRes = 6;
constexpr int kShLuminance = 7;
constexpr int kShExposureResolve = 8;

struct Bump {
    std::uint64_t cur;
    std::uint64_t end;
    std::uint64_t take(std::uint64_t size, std::uint64_t align) {
        if (size == 0) {
            return 0;
        }
        const std::uint64_t p = align_up(cur, align);
        if (p + size > end || p + size < p) {
            return 0;
        }
        cur = p + size;
        return p;
    }
};

// Texture spec record (0x48 bytes) as kept in the shared object; our field placement follows the
// description's setter list: +0x00 address, +0x10 type, +0x14 width, +0x18 height, +0x1c/+0x20/
// +0x24 = 1, +0x28 format word, +0x30 tiling.
void write_spec(void *spec, std::uint64_t address, std::uint32_t w, std::uint32_t h,
                std::uint64_t fmt, std::uint32_t tiling) {
    std::memset(spec, 0, 0x48);
    st<std::uint64_t>(spec, 0x00, address);
    st<std::uint32_t>(spec, 0x10, 9);
    st<std::uint32_t>(spec, 0x14, w);
    st<std::uint32_t>(spec, 0x18, h);
    st<std::uint32_t>(spec, 0x1c, 1);
    st<std::uint32_t>(spec, 0x20, 1);
    st<std::uint32_t>(spec, 0x24, 1);
    st<std::uint64_t>(spec, 0x28, fmt);
    st<std::uint32_t>(spec, 0x30, tiling);
}

std::uint64_t tex_size(std::uint32_t w, std::uint32_t h, std::uint64_t fmt, std::uint64_t *align) {
    std::uint64_t size = 0;
    texture_size(w, h, fmt, &size, align);
    return size;
}

// ------------------------------------------------------------------------------------------------
// KPN9 package (sizing and loading).
// ------------------------------------------------------------------------------------------------
struct PackageRow {
    std::uint8_t raw[64];
    std::uint64_t a = 0, b = 0, c = 0;
};

std::uint32_t row_u32(const PackageRow &r, std::uint32_t off) {
    return ld<std::uint32_t>(r.raw, off);
}

// Opens and checks the package; reads header, info and rows. Returns nullptr on failure (file
// left open in `leaked` when the kind is wrong, which the load path does not close).
void *package_open(std::uint8_t (&hdr)[64], std::uint8_t (&info)[64], std::vector<PackageRow> &rows,
                   bool close_on_bad_kind) {
    void *fp = pkg_open(kPackageFile);
    if (fp == nullptr) {
        return nullptr;
    }
    if (!pkg_read(fp, 0, hdr, sizeof hdr) || ld<std::uint16_t>(hdr, 4) != 9) {
        if (close_on_bad_kind) {
            pkg_close(fp);
        } // else: quirk of the original, the load path leaks the open file
        return nullptr;
    }
    if (!pkg_read(fp, ld<std::uint32_t>(hdr, 0x08), info, sizeof info)) {
        pkg_close(fp);
        return nullptr;
    }
    const std::uint32_t n = info[0x10];
    const std::uint32_t table = ld<std::uint32_t>(info, 0x14);
    rows.resize(n);
    for (std::uint32_t i = 0; i < n; ++i) {
        if (!pkg_read(fp, table + 64ull * i, rows[i].raw, 64)) {
            std::memset(rows[i].raw, 0, 64);
        }
    }
    return fp;
}

std::uint64_t row_a_size(const PackageRow &r, bool compressed) {
    return compressed ? row_u32(r, 0x28) : row_u32(r, 0x1c);
}

// Requirement path: adds the package pieces to a running total (no bounds checks). The result
// is ignored by the caller.
std::int32_t package_size(void *record, std::uint64_t *total) {
    std::uint8_t hdr[64];
    std::uint8_t info[64];
    std::vector<PackageRow> rows;
    void *fp = package_open(hdr, info, rows, true);
    if (fp == nullptr) {
        return err::kShaderOrPackage;
    }
    const bool compressed = (hdr[0x2c] & 1u) != 0;
    std::memcpy(record, info, 16);
    st<std::uint32_t>(record, 0x10, (hdr[0x2c] & 2u) != 0 ? 0u : 1u);
    std::uint64_t cur = *total;
    auto add = [&cur](std::uint64_t size, std::uint64_t align) {
        if (size != 0) {
            cur = align_up(cur, align) + size;
        }
    };
    for (const PackageRow &r : rows) {
        add(row_a_size(r, compressed), 0x4000);
        add(row_u32(r, 0x14), 8);
        add(row_u32(r, 0x24), 0x4000);
    }
    add(ld<std::uint32_t>(info, 0x1c), 4);
    *total = cur;
    pkg_close(fp);
    return 0;
}

std::int32_t package_load(void *record, Bump &alloc, std::uint64_t scratch) {
    std::uint8_t hdr[64];
    std::uint8_t info[64];
    std::vector<PackageRow> rows;
    void *fp = package_open(hdr, info, rows, false);
    if (fp == nullptr) {
        return err::kShaderOrPackage;
    }
    const bool compressed = (hdr[0x2c] & 1u) != 0;
    std::memcpy(record, info, 16);
    st<std::uint32_t>(record, 0x10, (hdr[0x2c] & 2u) != 0 ? 0u : 1u);
    char name[17] = {};
    std::memcpy(name, info, 16);
    log(kModuleName, "[PSML][Mfsr2] Load parameter %s", name);
    for (PackageRow &r : rows) {
        r.a = alloc.take(row_a_size(r, compressed), 0x4000);
        r.b = alloc.take(row_u32(r, 0x14), 8);
        r.c = alloc.take(row_u32(r, 0x24), 0x4000);
    }
    const std::uint32_t const_size = ld<std::uint32_t>(info, 0x1c);
    const std::uint64_t consts = alloc.take(const_size, 4);
    // 1. Shader code, stored or LZ4-compressed through the first 16 MiB of the scratch region.
    for (PackageRow &r : rows) {
        if (!compressed) {
            if (r.a != 0) {
                pkg_read(fp, row_u32(r, 0x18), ptr(r.a), row_u32(r, 0x1c));
            }
            continue;
        }
        const std::uint32_t stored = row_u32(r, 0x1c);
        const std::uint32_t full = row_u32(r, 0x28);
        std::uint64_t staging = align_up(scratch, 256);
        if (scratch != 0 && staging + stored <= scratch + 0x1000000ull) {
            pkg_read(fp, row_u32(r, 0x18), ptr(staging), stored);
        } else {
            staging = 0;
        }
        if (r.a != 0 && staging != 0) {
            const std::int32_t n =
                lz4_decompress(ptr(staging), ptr(r.a), static_cast<std::int32_t>(stored),
                               static_cast<std::int32_t>(full));
            if (n != static_cast<std::int32_t>(full)) {
                log(kModuleName, "[PSML][Mfsr2] decompressed size mismatch (%d, %u)", n, full);
            }
        }
    }
    // 2. Headers (B) and blobs (C), then the layer shader.
    for (PackageRow &r : rows) {
        if (r.b != 0) {
            pkg_read(fp, row_u32(r, 0x10), ptr(r.b), row_u32(r, 0x14));
        }
        if (r.c != 0) {
            pkg_read(fp, row_u32(r, 0x20), ptr(r.c), row_u32(r, 0x24));
        }
        const std::uint32_t k = r.raw[0x30];
        if (k > 16) {
            continue; // our bound: the record holds 17 layer entries
        }
        std::uint8_t *entry = bp(record) + 0x18 + 0x28u * k;
        st<std::uint64_t>(entry, 0x08, r.a);
        st<std::uint64_t>(entry, 0x10, r.b);
        st<std::uint64_t>(entry, 0x18, r.c);
        st<std::uint32_t>(entry, 0x20, row_u32(r, 0x2c));
        if (state().trinity_mode == 1) {
            void *sh = nullptr;
            if (create_shader_checked(&sh, ptr<void>(r.b), ptr<void>(r.a)) == 0) {
                st<std::uint64_t>(entry, 0x00, addr(sh));
            }
        } else {
            st<std::uint64_t>(entry, 0x00, 0);
        }
    }
    // 3. Constants: 8x8 grid of 16-byte vectors transposed, then the 0x40-byte tail and 8 bytes.
    std::uint8_t cbuf[0x448] = {};
    pkg_read(fp, ld<std::uint32_t>(info, 0x18), cbuf, const_size < 0x448 ? const_size : 0x448);
    if (consts != 0) {
        for (std::uint32_t a = 0; a < 8; ++a) {
            for (std::uint32_t b = 0; b < 8; ++b) {
                std::memcpy(ptr(consts + 16ull * (a * 8 + b)), cbuf + b * 0x80 + a * 0x10, 16);
            }
        }
        if (const_size >= 0x440) {
            std::memcpy(ptr(consts + 0x400), cbuf + 0x400, 0x40);
        }
        st<std::uint64_t>(record, 0x2c0, consts);
        build_buffer_desc(bp(record) + 0x2c8, consts, 64, 16);
        build_buffer_desc(bp(record) + 0x2d8, consts + 0x400, 8, 8);
    }
    std::memcpy(bp(record) + 0x2e8, cbuf + 0x440, 8);
    // 4. Parameter block.
    const std::uint64_t pblock = ld<std::uint64_t>(record, 0x2f8);
    if (pblock != 0) {
        pkg_read(fp, ld<std::uint32_t>(hdr, 0x0c), ptr(pblock), kParamBlockSize);
    }
    pkg_close(fp);
    return 0;
}

// ------------------------------------------------------------------------------------------------
// Memory mapping helpers.
// ------------------------------------------------------------------------------------------------
std::int32_t map_blocks(std::uint64_t *out_base, std::uint64_t *out_size,
                        const Mfsr2MemoryBlock *blocks, std::uint64_t count, std::uint64_t va) {
    *out_base = va;
    *out_size = 0;
    for (std::uint64_t i = 0; i < count; ++i) {
        void *where = ptr<void>(va);
        const std::int32_t r =
            import_table().kernel_map_named_direct_memory != nullptr
                ? import_table().kernel_map_named_direct_memory(
                      &where, blocks[i].length, 0x32, 0x90,
                      static_cast<std::int64_t>(blocks[i].direct_offset), 0x200000, "SceMfsr2")
                : -1;
        if (r != 0) {
            log(kModuleName, "[PSML] sceKernelMapNamedDirectMemory failed (%08x)",
                static_cast<std::uint32_t>(r));
            return -1;
        }
        va += blocks[i].length;
        *out_size += blocks[i].length;
    }
    return 0;
}

void unmap(std::uint64_t base, std::uint64_t size) {
    if (size != 0 && import_table().kernel_munmap != nullptr) {
        import_table().kernel_munmap(ptr<void>(base), size);
    }
}

// ------------------------------------------------------------------------------------------------
// Requirements.
// ------------------------------------------------------------------------------------------------
std::int32_t shared_params_check(const Mfsr2SharedResourcesInitParameters *p, const char *fn) {
    if (p->profile != 0) {
        log(kModuleName, "%s%s: m_profile must be 0", kPrefix, fn);
        return err::k2InvalidProfile;
    }
    if (p->max_output_width != kMaxW || p->max_output_height != kMaxH) {
        log(kModuleName, "%s%s: the maximum output size must be 3840x2160", kPrefix, fn);
        return err::k2InvalidParameter;
    }
    return 0;
}

std::uint64_t shared_layout_size(void *record) {
    std::uint64_t cur = kSharedObjectSize;
    cur = align_up(cur, kScratchAlign) + kScratchSize;
    std::uint64_t a = 0;
    const std::uint64_t ts = tex_size(kMaxW, kMaxH, kFmtShared, &a);
    cur = align_up(cur, a) + ts;
    cur = align_up(cur, 4) + kParamBlockSize;
    (void)package_size(record, &cur); // a missing package simply contributes nothing
    return cur;
}

std::int32_t context_params_check(const Mfsr2ContextInitParameters *p, const char *fn) {
    if (p == nullptr) {
        log(kModuleName, "%s%s: params must not be nullptr", kPrefix, fn);
        return err::k2NullPointer;
    }
    if (p->profile != 0) {
        log(kModuleName, "%s%s: m_profile must be 0", kPrefix, fn);
        return err::k2InvalidProfile;
    }
    if (p->shared_resources == nullptr) {
        log(kModuleName, "%s%s: m_sharedResources must not be nullptr", kPrefix, fn);
        return err::k2NullSharedResources;
    }
    if (p->reserved0 != 0 || p->output_color_width == 0 || p->output_color_height == 0 ||
        p->input_color_space > 1) {
        log(kModuleName, "%s%s: invalid parameter", kPrefix, fn);
        return err::k2InvalidParameter;
    }
    if (ld<std::uint32_t>(p->shared_resources, 0x78) != 0) {
        log(kModuleName, "%s%s: m_profile must match", kPrefix, fn);
        return err::k2InvalidParameter;
    }
    return 0;
}

struct ContextLayout {
    std::uint64_t t1 = 0, t1_size = 0, t2 = 0, t2_size = 0, total = 0;
};

ContextLayout context_layout(std::uint64_t base, std::uint32_t w, std::uint32_t h) {
    ContextLayout l;
    std::uint64_t cur = base + kCtxHeaderSize;
    cur = align_up(cur, 4) + 8 * kNetBlockSize;
    cur += 8 * kFrameBlockSize;
    cur = align_up(cur, 0x100) + 8 * kSmallBlockSize;
    std::uint64_t a1 = 0;
    l.t1_size = tex_size(w, h, kFmtT1, &a1);
    l.t1 = align_up(cur, a1);
    cur = l.t1 + l.t1_size;
    std::uint64_t a2 = 0;
    l.t2_size = tex_size(w, h, kFmtShared, &a2);
    l.t2 = align_up(cur, a2);
    cur = l.t2 + l.t2_size;
    l.total = cur - base;
    return l;
}

// Tensor descriptor table (Appendix D, INTEROP: the network shaders read it). Rows: table
// offset, base offset from the shared scratch S, stride, element count.
struct TensorRow {
    std::uint16_t off;
    std::uint32_t base;
    std::uint8_t stride;
    std::uint32_t elements;
};
constexpr TensorRow kTensorRows[] = {
    {0x020, 0x0000000, 16, 0x1fa400}, {0x030, 0x1fa4000, 16, 0x1fa400},
    {0x040, 0x5eec000, 16, 0x38},     {0x050, 0x5eec380, 8, 8},
    {0x068, 0xbdd8000, 16, 0x1fa400}, {0x078, 0xbdd8000, 16, 0x3f4800},
    {0x088, 0x3f48000, 16, 0x1fa400}, {0x098, 0x5eec000, 16, 0x1fa400},
    {0x0a8, 0xbdd8000, 16, 0x1fa400}, {0x0b8, 0xbdd8000, 16, 0x3f4800},
    {0x0c8, 0x0000000, 16, 0x1fa400}, {0x0d8, 0x1fa4000, 16, 0x1fa400},
    {0x0e8, 0x3f48000, 16, 0x7e900},  {0x0f8, 0x4731000, 16, 0xfd200},
    {0x108, 0xbdd8000, 16, 0x7e900},  {0x118, 0xbdd8000, 16, 0x2f7600},
    {0x128, 0x0000000, 16, 0x7e900},  {0x138, 0x07e9000, 16, 0xfd200},
    {0x148, 0xbdd8000, 16, 0x7e900},  {0x158, 0xbdd8000, 16, 0x2f7600},
    {0x168, 0xbdd8000, 16, 0x7e900},  {0x178, 0xc5c1000, 16, 0xfd200},
    {0x188, 0x3f48000, 16, 0x3f480},  {0x198, 0x433c800, 16, 0x3f480},
    {0x1a8, 0xbdd8000, 16, 0x3f480},  {0x1b8, 0xbdd8000, 16, 0xfd200},
    {0x1c8, 0x0000000, 16, 0x3f480},  {0x1d8, 0x03f4800, 16, 0x3f480},
    {0x1e8, 0xbdd8000, 16, 0x3f480},  {0x1f8, 0xbdd8000, 16, 0xfd200},
    {0x208, 0x3f48000, 16, 0x3f480},  {0x218, 0x433c800, 16, 0x3f480},
    {0x228, 0xbdd8000, 16, 0x3f480},  {0x238, 0xbdd8000, 16, 0xfd200},
    {0x248, 0x0000000, 16, 0x3f480},  {0x258, 0x03f4800, 16, 0x3f480},
    {0x268, 0xbdd8000, 16, 0x3f480},  {0x278, 0xbdd8000, 16, 0xfd200},
    {0x288, 0x3f48000, 16, 0x3f480},  {0x298, 0x433c800, 16, 0x3f480},
    {0x2a8, 0x0000000, 16, 0x7e900},  {0x2b8, 0x07e9000, 16, 0xfd200},
    {0x2c8, 0xbdd8000, 16, 0x7e900},  {0x2d8, 0xbdd8000, 16, 0x2f7600},
    {0x2e8, 0x3f48000, 16, 0x7e900},  {0x2f8, 0x4731000, 16, 0xfd200},
    {0x308, 0x0000000, 16, 0x1fa400}, {0x318, 0x1fa4000, 16, 0x1fa400},
    {0x328, 0xbdd8000, 16, 0x1fa400}, {0x338, 0xbdd8000, 16, 0x7e9000},
    {0x348, 0x3f48000, 16, 0x1fa400}, {0x358, 0x5eec000, 16, 0x1fa400},
    {0x368, 0xbdd8000, 16, 0x1fa400}, {0x378, 0xbdd8000, 16, 0x7e9000},
    {0x388, 0x0000000, 16, 0x1fa400}, {0x398, 0x1fa4000, 16, 0x1fa400},
    {0x3a8, 0x3f48000, 16, 0x7e9000},
};

void build_tensor_table(void *block, std::uint64_t scratch) {
    build_texture_desc(block, scratch + 0x3f48000, 1920, 1080, kFmtTensorT, 1);
    for (const TensorRow &r : kTensorRows) {
        build_buffer_desc(bp(block) + r.off, scratch + r.base, r.elements, r.stride);
    }
}

void init_frame_constants(void *f, std::uint32_t w, std::uint32_t h) {
    std::memset(f, 0, kFrameBlockSize);
    st<float>(f, 0x00, 1.0f / static_cast<float>(w));
    st<float>(f, 0x04, 1.0f / static_cast<float>(h));
    st<std::uint32_t>(f, 0x38, w);
    st<std::uint32_t>(f, 0x3c, h);
    st<std::uint32_t>(f, 0x48, kMaxW);
    st<std::uint32_t>(f, 0x4c, kMaxH);
    st<float>(f, 0x58, 300.0f);
    st<float>(f, 0x5c, 10000.0f);
    st<std::uint32_t>(f, 0x88, 3);
    st<std::uint32_t>(f, 0x8c, 1);
    st<std::uint32_t>(f, 0x94, 1);
    st<std::uint32_t>(f, 0x98, 8);
    st<std::uint32_t>(f, 0x9c, 8);
    st<std::uint32_t>(f, 0xa0, 8);
    st<float>(f, 0xa4, 0.1f);
    st<std::uint32_t>(f, 0xac, 3);
    st<std::uint32_t>(f, 0xb4, 4);
    st<std::uint32_t>(f, 0xd0, 0x000fcfcau);
    const std::uint32_t sampler[4] = {0x00000092u, 0x00fff000u, 0x01500000u, 0};
    std::memcpy(bp(f) + 0xd4, sampler, 16);
}

// ------------------------------------------------------------------------------------------------
// Dispatch.
// ------------------------------------------------------------------------------------------------
bool finite(float v) { return std::isfinite(v); }

std::int32_t validate_texture(const void *t, int index, const std::uint32_t *rect) {
    static constexpr const char *kNames[5] = {"m_outputColor", "m_color", "m_motionVectors",
                                              "m_depth", "m_exposure"};
    if (t == nullptr) {
        log(kModuleName, "%sdispatch: %s must not be nullptr", kPrefix, kNames[index]);
        return err::k2MissingTexture;
    }
    const std::uint32_t fmt = tdesc_format(t);
    // The format translation table (183 entries of {channel layout, channel type}) is module data
    // read from the maintainer's module file.
    FirmwareData *fd = firmware_data();
    const std::uint8_t *table = fd != nullptr ? fd->get(kModuleName, 0x6ac70, 183 * 8) : nullptr;
    if (fmt >= 183 || table == nullptr) {
        return err::k2BadTexture;
    }
    const std::uint32_t layout = ld<std::uint32_t>(table, 8u * fmt);
    const std::uint32_t type = ld<std::uint32_t>(table, 8u * fmt + 4);
    if (index == 0) {
        if (fmt != 0x24 && fmt != 0x2b && fmt != 0x47) {
            return err::k2BadTexture;
        }
    } else if (index == 1) {
        if (type != 7) {
            return err::k2BadTexture;
        }
    } else if (type != 0 && type != 1 && type != 7) {
        return err::k2BadTexture;
    }
    const std::uint32_t d3 = ld<std::uint32_t>(t, 12);
    const std::uint32_t d4 = ld<std::uint32_t>(t, 16);
    if (layout < 1 || layout > 14 || (d3 >> 28) != 9 || ((d3 >> 12) & 0xf) != 0 ||
        ((d3 >> 16) & 0xf) != 0 || ((d4 >> 16) & 0x1fff) != 0 || (d4 & 0x1fff) != 0) {
        return err::k2BadTexture;
    }
    if (rect != nullptr) {
        const std::uint64_t tw = tdesc_width(t);
        const std::uint64_t th = tdesc_height(t);
        if (std::uint64_t{rect[0]} + rect[2] > tw || std::uint64_t{rect[1]} + rect[3] > th) {
            return err::k2BadTexture;
        }
    }
    return 0;
}

std::int32_t validate_dispatch(const void *ctx, const AgcCommandBuffer *cb,
                               const Mfsr2DispatchParameters *p) {
    if (ctx == nullptr) {
        return err::k2NullContext;
    }
    if (cb == nullptr || p == nullptr) {
        return err::k2NullPointer;
    }
    for (int i = 0; i < 3; ++i) {
        if (p->reserved1[i] != 0) {
            log(kModuleName, "%sdispatch: m_reserved1[%d] must be 0", kPrefix, i);
            return err::k2InvalidParameter;
        }
    }
    if (p->output_color == nullptr) {
        return err::k2MissingTexture;
    }
    if (!(p->pre_exposure > 0.0f) || !finite(p->pre_exposure)) {
        return err::k2InvalidParameter;
    }
    if (p->render_rect[2] < ld<std::uint16_t>(ctx, 0x16c) ||
        p->render_rect[3] < ld<std::uint16_t>(ctx, 0x16e)) {
        return err::k2RenderRectTooSmall;
    }
    if (!finite(p->jitter[0]) || !finite(p->jitter[1]) || !finite(p->motion_vector_scale[0]) ||
        !finite(p->motion_vector_scale[1]) || !finite(p->motion_vector_offset[0]) ||
        !finite(p->motion_vector_offset[1])) {
        return err::k2InvalidParameter;
    }
    if (p->option_flags > 0xf) {
        return err::k2InvalidParameter;
    }
    const std::uint32_t out_w = ld<std::uint16_t>(ctx, 0x168);
    const std::uint32_t out_h = ld<std::uint16_t>(ctx, 0x16a);
    if (tdesc_width(p->output_color) < out_w || tdesc_height(p->output_color) < out_h) {
        return err::k2BadTexture;
    }
    std::int32_t r = validate_texture(p->output_color, 0, nullptr);
    if (r == 0) {
        r = validate_texture(p->color, 1, p->render_rect);
    }
    if (r != 0) {
        return r;
    }
    if ((p->option_flags & 4u) == 0) {
        r = validate_texture(p->motion_vectors, 2, p->render_rect);
        if (r == 0) {
            r = validate_texture(p->depth, 3, p->render_rect);
        }
    } else {
        // kDilatedMotionVectors: depth is not validated here (as the original reads).
        r = validate_texture(p->motion_vectors, 2, nullptr);
        if (r == 0 &&
            (tdesc_width(p->motion_vectors) < out_w || tdesc_height(p->motion_vectors) < out_h)) {
            r = err::k2BadTexture;
        }
    }
    if (r != 0) {
        return r;
    }
    if (p->exposure != nullptr) {
        r = validate_texture(p->exposure, 4, nullptr);
        if (r != 0) {
            return r;
        }
    }
    if (p->reserved_pointer != nullptr) {
        return err::k2InvalidParameter;
    }
    const bool sharpen = (p->option_flags & 8u) != 0;
    if ((!sharpen && p->sharpness != 0.0f) ||
        (sharpen && !(p->sharpness >= 0.0f && p->sharpness <= 1.0f))) {
        return err::k2InvalidParameter;
    }
    return 0;
}

void copy32(void *f, std::uint32_t off, const void *src) {
    if (src != nullptr) {
        std::memcpy(bp(f) + off, src, 32);
    } else {
        std::memset(bp(f) + off, 0, 32);
    }
}
void copy_in_block(void *f, std::uint32_t dst, std::uint32_t src, std::uint32_t n) {
    std::memmove(bp(f) + dst, bp(f) + src, n);
}

// Frame constants (Appendix C.2). Returns nothing: failures of the embedded helpers are ignored.
void fill_frame_constants(void *ctx, void *f, const void *net, const void *record,
                          AgcCommandBuffer &cb, const Mfsr2DispatchParameters *p) {
    ModuleState &s = state();
    const std::uint32_t flags = p->option_flags;
    const bool auto_exp = (flags & 2u) != 0;
    const bool dilated = (flags & 4u) != 0;
    const bool sharpen = (flags & 8u) != 0;
    const std::uint32_t rw = p->render_rect[2];
    const std::uint32_t rh = p->render_rect[3];
    const std::uint32_t ow = ld<std::uint16_t>(ctx, 0x168);
    const std::uint32_t oh = ld<std::uint16_t>(ctx, 0x16a);
    const float frw = static_cast<float>(rw);
    const float frh = static_cast<float>(rh);
    const float fow = static_cast<float>(ow);
    const float foh = static_cast<float>(oh);
    const float pe = p->pre_exposure;
    std::uint32_t reset = p->reset != 0 ? 1u : 0u;
    if (ld<std::uint32_t>(ctx, 0) != kCtxMagicDispatched) {
        st<std::uint32_t>(ctx, 0, kCtxMagicDispatched);
        reset = 1;
    }
    s.mfsr2_dispatch_counter += 1;

    // Embedded helpers: a 1x1 texture holding 1.0 when there is no exposure texture, the 4-byte
    // auto-exposure buffer, and the 1x1 zero texture standing in for the absent extra mask.
    // TODO(verify): the order of the three embeddings.
    std::uint8_t exposure_t[32] = {};
    if (p->exposure != nullptr) {
        std::memcpy(exposure_t, p->exposure, 32);
    } else if (void *one = embed_scratch(cb, 4, 256); one != nullptr) {
        st<float>(one, 0, 1.0f);
        build_texture_desc(exposure_t, addr(one), 1, 1, kFmtSynth1x1, 0);
    }
    std::uint8_t aux_v[16] = {};
    if (auto_exp) {
        if (void *buf = embed_scratch(cb, 4, 16); buf != nullptr) {
            st<std::uint32_t>(buf, 0, 0);
            build_buffer_desc(aux_v, addr(buf), 1, 4);
        }
    }
    std::uint8_t mask_t[32] = {};
    if (void *zero = embed_scratch(cb, 4, 256); zero != nullptr) {
        st<std::uint32_t>(zero, 0, 0);
        build_texture_desc(mask_t, addr(zero), 1, 1, kFmtSynth1x1, 0);
    }

    st<float>(f, 0x008, 1.0f / frw);
    st<float>(f, 0x00c, 1.0f / frh);
    st<float>(f, 0x010, fow / frw);
    st<float>(f, 0x014, foh / frh);
    st<float>(f, 0x018, frw / fow);
    st<float>(f, 0x01c, frh / foh);
    st<float>(f, 0x020, p->jitter[0]);
    st<float>(f, 0x024, p->jitter[1]);
    std::memcpy(bp(f) + 0x028, bp(ctx) + 0x178, 8);
    st<float>(f, 0x030, p->motion_vector_scale[0] / (dilated ? fow : frw));
    st<float>(f, 0x034, p->motion_vector_scale[1] / (dilated ? foh : frh));
    st<std::uint32_t>(f, 0x040, rw);
    st<std::uint32_t>(f, 0x044, rh);
    st<std::uint32_t>(f, 0x050, auto_exp ? 1u : 0u);
    st<float>(f, 0x054, pe);
    st<float>(f, 0x058, 300.0f);
    st<std::uint32_t>(f, 0x060, reset);
    st<std::uint32_t>(f, 0x064, dilated ? 0u : 1u);
    st<std::uint32_t>(f, 0x068, 0); // extra mask never present
    st<std::uint32_t>(f, 0x084, flags & 1u);
    st<std::uint32_t>(f, 0x0b8, 0);
    st<std::uint32_t>(f, 0x0c8, 0);
    st<std::uint32_t>(f, 0x0bc, s.mfsr2_dispatch_counter);
    st<std::uint32_t>(f, 0x0cc, 0);
    copy32(f, 0x0e4, bp(ctx) + 0xb8);
    copy32(f, 0x104, p->motion_vectors);
    copy32(f, 0x124, p->depth);
    copy32(f, 0x144, p->color);
    copy32(f, 0x164, exposure_t);
    std::memcpy(bp(f) + 0x184, aux_v, 16);
    copy32(f, 0x194, bp(ctx) + 0xd8);
    copy32(f, 0x1b4, bp(ctx) + 0x98);
    copy32(f, 0x204, mask_t);
    copy32(f, 0x224, bp(ctx) + 0xb8);
    copy32(f, 0x244, p->output_color);
    copy32(f, 0x274, bp(ctx) + 0x98);
    copy32(f, 0x2b4, bp(ctx) + 0xd8);
    std::memset(bp(f) + 0x2d4, 0, 0x40);
    copy32(f, 0x314, bp(ctx) + 0xf8);
    copy32(f, 0x334, bp(ctx) + 0xf8);
    std::memcpy(bp(f) + 0x354, net, 0x40); // net[0x00..0x3F] as it is before this frame's setup
    std::memcpy(bp(f) + 0x394, static_cast<const std::uint8_t *>(record) + 0x2c8, 16);
    std::memcpy(bp(f) + 0x3a4, static_cast<const std::uint8_t *>(record) + 0x2d8, 16);
    std::memcpy(bp(f) + 0x3b4, static_cast<const std::uint8_t *>(record) + 0x2e8, 8);
    st<std::uint32_t>(f, 0x3bc, p->render_rect[0]);
    st<std::uint32_t>(f, 0x3c0, p->render_rect[1]);
    st<std::uint32_t>(f, 0x3c4, rw - 1);
    st<std::uint32_t>(f, 0x3c8, rh - 1);
    if (!dilated) {
        st<float>(f, 0x3cc, p->motion_vector_scale[0] * fow / frw);
        st<float>(f, 0x3d0, p->motion_vector_scale[1] * foh / frh);
        st<float>(f, 0x3d4, p->motion_vector_offset[0] * fow / frw);
        st<float>(f, 0x3d8, p->motion_vector_offset[1] * foh / frh);
    } else {
        st<float>(f, 0x3cc, p->motion_vector_scale[0]);
        st<float>(f, 0x3d0, p->motion_vector_scale[1]);
        st<float>(f, 0x3d4, p->motion_vector_offset[0]);
        st<float>(f, 0x3d8, p->motion_vector_offset[1]);
    }
    float dp[4];
    depth_params(dp, p->camera_near, p->camera_far, (flags & 1u) != 0);
    std::memcpy(bp(f) + 0x3dc, dp, 16);
    st<std::uint32_t>(f, 0x3ec,
                      reset | (auto_exp ? 2u : 0u) | ((flags & 1u) << 2) | (dilated ? 0u : 8u));
    st<std::uint32_t>(f, 0x3f0, p->render_rect[0]);
    st<std::uint32_t>(f, 0x3f4, p->render_rect[1]);
    st<float>(f, 0x3f8, frw / fow);
    st<float>(f, 0x3fc, frh / foh);
    st<float>(f, 0x400, p->jitter[0]);
    st<float>(f, 0x404, p->jitter[1]);
    st<std::uint32_t>(f, 0x408, rw - 1);
    st<std::uint32_t>(f, 0x40c, rh - 1);
    copy32(f, 0x410, p->color);
    copy32(f, 0x430, p->depth);
    copy32(f, 0x450, p->motion_vectors);
    st<float>(f, 0x470, fow / frw);
    st<float>(f, 0x474, foh / frh);
    st<std::uint32_t>(f, 0x478, ow);
    st<std::uint32_t>(f, 0x47c, oh);
    copy_in_block(f, 0x480, 0xd4, 16);
    st<std::uint32_t>(f, 0x490, 0x3f24dd2fu);
    st<float>(f, 0x494, pe);
    copy_in_block(f, 0x498, 0x000, 8);
    copy_in_block(f, 0x4a0, 0x3cc, 16);
    copy_in_block(f, 0x4b0, 0x0a4, 4);
    const float jx = p->jitter[0];
    const float jy = p->jitter[1];
    st<float>(f, 0x4b4, frw / fow * 0.5f + jx - 0.5f);
    st<float>(f, 0x4b8, frh / foh * 0.5f + jy - 0.5f);
    st<float>(f, 0x4bc, 1.0f / pe);
    st<float>(f, 0x4c0, frw / fow * 0.5f + jx);
    st<float>(f, 0x4c4, frh / foh * 0.5f + jy);
    copy_in_block(f, 0x4c8, 0x3dc, 16);
    st<std::uint32_t>(f, 0x4d8, rw);
    st<std::uint32_t>(f, 0x4dc, rh);
    st<float>(f, 0x4e0,
              p->color != nullptr ? 1.0f / static_cast<float>(tdesc_width(p->color)) : 0.0f);
    st<float>(f, 0x4e4,
              p->color != nullptr ? 1.0f / static_cast<float>(tdesc_height(p->color)) : 0.0f);
    copy_in_block(f, 0x4e8, 0x164, 32);
    copy_in_block(f, 0x508, 0x184, 16);
    copy_in_block(f, 0x518, 0x0e4, 32);
    copy_in_block(f, 0x538, 0x1b4, 32);
    const std::uint32_t sampler2[4] = {0x00008092u, 0x00fff000u, 0x05500000u, 0};
    std::memcpy(bp(f) + 0x558, sampler2, 16);
    copy_in_block(f, 0x568, 0x2b4, 32);
    copy_in_block(f, 0x588, 0x394, 16);
    copy_in_block(f, 0x598, 0x3a4, 16);
    copy_in_block(f, 0x5a8, 0x354, 32);
    copy_in_block(f, 0x5c8, 0x3b4, 8);
    copy_in_block(f, 0x5d0, 0x2f4, 32);
    st<std::uint32_t>(f, 0x5f0, auto_exp ? 1u : 0u);
    copy_in_block(f, 0x5f4, 0x184, 16);
    copy_in_block(f, 0x604, 0x164, 32);
    copy_in_block(f, 0x624, 0x018, 16);
    copy_in_block(f, 0x634, 0x314, 16);
    st<float>(f, 0x644, pe);
    st<std::uint32_t>(f, 0x648, 0);
    copy_in_block(f, 0x64c, 0x3bc, 8);
    copy_in_block(f, 0x654, 0x194, 16);
    copy_in_block(f, 0x664, 0x144, 32);
    st<std::uint32_t>(f, 0x684, rw);
    st<std::uint32_t>(f, 0x688, rh);
    copy_in_block(f, 0x68c, 0x204, 32);
    copy_in_block(f, 0x6ac, 0x070, 8);
    copy_in_block(f, 0x6b4, 0x010, 8);
    copy_in_block(f, 0x6bc, 0x224, 16);
    copy_in_block(f, 0x6cc, 0x244, 32);
    st<std::uint32_t>(f, 0x6ec, sharpen ? 1u : 0u);
    const float sh = sharpen ? std::exp2(2.0f * p->sharpness - 2.0f) : 0.0f;
    st<float>(f, 0x6f0, sh);
    const std::uint16_t shh = sharpen ? float_to_half(sh) : 0;
    st<std::uint16_t>(f, 0x6f4, shh);
    st<std::uint16_t>(f, 0x6f6, shh);
    st<std::uint64_t>(f, 0x6f8, 0);
    st<std::uint32_t>(f, 0x700, ow - 1);
    st<std::uint32_t>(f, 0x704, oh - 1);
    std::memset(bp(f) + 0x708, 0, 0xa3c - 0x708);
    std::memset(bp(f) + 0xa40, 0, kFrameBlockSize - 0xa40);
    if (auto_exp) {
        build_typed_buffer_desc(bp(f) + 0xa40, addr(bp(f) + 0xa98), kFmtTyped8, 8);
        st<std::uint64_t>(f, 0xa50, 0x0800000000000000ull);
        const float t = (frw / 16.0f) * (frh / 16.0f);
        st<float>(f, 0xa60, 1.0f / (t * 16384.0f));
        st<std::int64_t>(f, 0xa68, static_cast<std::int64_t>(t * std::log(0.001f) * 16384.0f));
        st<std::uint32_t>(f, 0xa70, 0x3da86834u);
        st<float>(f, 0xa74, reset == 0 ? 0.5f : 0.0f);
        st<std::uint64_t>(f, 0xa78, addr(bp(ctx) + 0x180));
        const std::uint64_t vbase =
            static_cast<std::uint64_t>(ld<std::uint32_t>(aux_v, 0)) |
            (static_cast<std::uint64_t>(ld<std::uint32_t>(aux_v, 4) & 0xffff) << 32);
        st<std::uint64_t>(f, 0xa80, vbase);
    }
    flush_cpu_lines(f, kFrameBlockSize);
}

// A pre/post pass: registers, binder user data, dispatch, barrier(1, 0x13).
void run_pass(AgcCommandBuffer &cb, const void *shader, const void *ud, std::uint32_t ud_dwords,
              std::uint32_t x, std::uint32_t y, std::uint32_t z) {
    load_shader_registers(cb, shader);
    write_user_data(cb, shader, ud, ud_dwords);
    dispatch_if_enabled(cb, shader, x, y, z);
}

// Reprojection-style pass split into slices of 128 groups along Z plus a remainder.
void run_sliced_pass(AgcCommandBuffer &cb, const void *shader, std::uint64_t frame,
                     std::uint32_t gx, std::uint32_t gy, std::uint32_t ow) {
    std::uint32_t ud[4] = {static_cast<std::uint32_t>(frame),
                           static_cast<std::uint32_t>(frame >> 32), 0x80, 0};
    run_pass(cb, shader, ud, 4, 128, gy, (ow + 7) >> 10);
    if ((gx & 127u) != 0) {
        ud[3] = gx & ~127u;
        write_user_data(cb, shader, ud, 4);
        dispatch_if_enabled(cb, shader, gx & 127u, gy, 1);
    }
    barrier(cb, 0x13);
}

void pre_passes(AgcCommandBuffer &cb, void *ctx, void *f, const Mfsr2DispatchParameters *p) {
    ModuleState &s = state();
    const std::uint32_t ow = ld<std::uint16_t>(ctx, 0x168);
    const std::uint32_t oh = ld<std::uint16_t>(ctx, 0x16a);
    const std::uint64_t frame = addr(f);
    if ((p->option_flags & 2u) != 0) {
        std::uint8_t ud[60] = {};
        if (p->color != nullptr) {
            std::memcpy(ud, p->color, 32);
        }
        st<std::uint64_t>(f, 0xa98, 0);
        build_typed_buffer_desc(ud + 32, frame + 0xa98, kFmtTyped8, 8);
        st<std::uint32_t>(ud, 48, p->render_rect[0]);
        st<std::uint32_t>(ud, 52, p->render_rect[1]);
        st<float>(ud, 56, 1.0f / p->pre_exposure);
        run_pass(cb, s.mfsr2_shaders[kShLuminance], ud, 15, p->render_rect[2], p->render_rect[3],
                 1);
        barrier(cb, 0x13);
        const std::uint64_t a40 = frame + 0xa40;
        const std::uint32_t ud2[2] = {static_cast<std::uint32_t>(a40),
                                      static_cast<std::uint32_t>(a40 >> 32)};
        run_pass(cb, s.mfsr2_shaders[kShExposureResolve], ud2, 2, 1, 1, 1);
        barrier(cb, 0x13);
    }
    // The alternative pre pass (handle 1) is selected by an internal flag that is never set.
    run_sliced_pass(cb, s.mfsr2_shaders[kShReprojection], frame, (ow + 7) >> 3, (oh + 3) >> 2, ow);
    const std::uint32_t ud3[2] = {static_cast<std::uint32_t>(frame),
                                  static_cast<std::uint32_t>(frame >> 32)};
    run_pass(cb, s.mfsr2_shaders[kShHalfRes], ud3, 2, ((ow >> 1) + 7) >> 3, ((oh >> 1) + 7) >> 3,
             1);
    barrier(cb, 0x13);
}

void post_pass(AgcCommandBuffer &cb, void *ctx, void *f) {
    ModuleState &s = state();
    const std::uint32_t ow = ld<std::uint16_t>(ctx, 0x168);
    const std::uint32_t oh = ld<std::uint16_t>(ctx, 0x16a);
    const void *sh = ld<std::uint32_t>(f, 0x6ec) != 0 ? s.mfsr2_shaders[kShPostSharpen]
                                                      : s.mfsr2_shaders[kShPostPlain];
    run_sliced_pass(cb, sh, addr(f), (ow + 7) >> 3, (oh + 7) >> 3, ow);
}

const void *layer_shader(const void *record, std::uint32_t k) {
    return ptr<const void>(ld<std::uint64_t>(record, 0x18 + 0x28u * k));
}

void network_mode0(AgcCommandBuffer &cb, void *net, const void *record) {
    void *scratch = embed_scratch(cb, 0x100, 4);
    write_user_data_pairs(cb, layer_shader(record, 2), addr(net), scratch);
    const std::uint32_t w = ld<std::uint32_t>(net, 0x3fc);
    const std::uint32_t h = ld<std::uint32_t>(net, 0x3f8);
    for (std::uint32_t k = 0; k < 17; ++k) {
        std::uint32_t x = 0;
        std::uint32_t y = 0;
        if (k <= 1 || k == 13 || k == 14) {
            x = ((w >> 1) + 31) >> 5;
            y = h >> 1;
        } else if (k <= 4 || k == 11 || k == 12) {
            x = ((w >> 2) + 31) >> 5;
            y = h >> 2;
        } else if (k <= 10) {
            x = ((w >> 3) + 31) >> 5;
            y = h >> 3;
        } else if (k == 15) {
            x = ((w >> 3) + 31) >> 5;
            y = h >> 1;
        } else {
            x = w >> 3;
            y = h >> 3;
        }
        const void *sh = layer_shader(record, k);
        if (sh == nullptr) {
            continue; // deviation: the original would use a null shader (missing package)
        }
        load_shader_registers(cb, sh);
        dispatch_if_enabled(cb, sh, x, y, 1);
        barrier(cb, 0);
    }
}

void network_mode1(AgcCommandBuffer &cb, void *ctx, void *net, const void *record) {
    const std::uint32_t ow = ld<std::uint16_t>(ctx, 0x168);
    const std::uint32_t oh = ld<std::uint16_t>(ctx, 0x16a);
    std::memset(net, 0, 0x200);
    st<std::uint32_t>(net, 0x1dc, 50);
    st<std::uint32_t>(net, 0x1e0, 50);
    st<std::uint32_t>(net, 0x1e4, 50);
    st<std::uint32_t>(net, 0x00, ow);
    st<std::uint32_t>(net, 0x04, oh);
    std::uint32_t table[30];
    (void)tile_table_a(table, static_cast<std::int32_t>(ow / 2), static_cast<std::int32_t>(oh / 2));
    std::memcpy(bp(net) + 0x18, table, sizeof table);
    (void)tile_table_b(table, static_cast<std::int32_t>(ow / 4), static_cast<std::int32_t>(oh / 4));
    std::memcpy(bp(net) + 0x90, table, sizeof table);
    (void)tile_table_c(table, static_cast<std::int32_t>(ow / 4), static_cast<std::int32_t>(oh / 4));
    std::memcpy(bp(net) + 0x108, table, sizeof table);
    st<std::uint64_t>(net, 0x10, 0);
    st<std::uint64_t>(net, 0x1e8, ld<std::uint64_t>(record, 0x30));
    st<std::uint64_t>(net, 0x1f0, ld<std::uint64_t>(record, 0x58));
    st<std::uint64_t>(net, 0x1f8, ld<std::uint64_t>(record, 0x80));
    flush_cpu_lines(net, 0x200);
    Imports &im = import_table();
    if (im.agc_dcb_push_marker_span != nullptr) {
        im.agc_dcb_push_marker_span(&cb, "KPN9::zone1", 12, 0);
    }
    const void *sh = layer_shader(record, 1);
    void *scratch = nullptr;
    if (im.agc_cb_nop != nullptr) {
        if (std::uint32_t *nop = im.agc_cb_nop(&cb, 0x41); nop != nullptr) {
            scratch = nop + 1;
            if (im.agc_get_nop_payload != nullptr) {
                im.agc_get_nop_payload(&scratch, nop, 0);
            }
        }
    }
    if (sh != nullptr) {
        write_user_data_pairs(cb, sh, addr(net), scratch);
        load_shader_registers(cb, sh);
        dispatch_if_enabled(cb, sh, 30, 1, 1);
    }
    barrier(cb, 0);
    if (im.agc_dcb_pop_marker != nullptr) {
        im.agc_dcb_pop_marker(&cb);
    }
}

std::int32_t phase_begin(AgcCommandBuffer &cb) {
    Imports &im = import_table();
    if (im.agc_dcb_bracket_packet == nullptr ||
        im.agc_dcb_bracket_packet(&cb, 1, 0x230, 1, 0, 0, 0xc000, 4, 0, 0, 0, 1) == nullptr) {
        return err::kNoRoomForPacket;
    }
    // Type-3 opcode 0x6F, one body dword (v << 28) + 1 with v = 3. TODO(verify): a PS5-specific
    // opcode; emitted verbatim.
    return cb_raw2(cb, 0xc0006f00u, (3u << 28) + 1u);
}

std::int32_t phase_end(AgcCommandBuffer &cb) {
    const std::int32_t r = cb_raw2(cb, 0xc0006f00u, 0x70000002u);
    if (r != 0) {
        return r;
    }
    Imports &im = import_table();
    if (im.agc_dcb_bracket_packet == nullptr ||
        im.agc_dcb_bracket_packet(&cb, 0, 0x0d, 0, 0, 0, 0xc000, 4, 0, 0, 0, 1) == nullptr) {
        return err::kNoRoomForPacket;
    }
    return 0;
}

std::int32_t dispatch_core(void *ctx, AgcCommandBuffer *cb, const Mfsr2DispatchParameters *p) {
    std::int32_t r = validate_dispatch(ctx, cb, p);
    if (r != 0) {
        return r;
    }
    Imports &im = import_table();
    const std::uint32_t ring = (ld<std::uint32_t>(ctx, 0x88) + 1) & 7u;
    st<std::uint32_t>(ctx, 0x88, ring);
    void *net = ptr<void>(ld<std::uint64_t>(ctx, 0x08 + 8u * ring));
    void *frame = ptr<void>(ld<std::uint64_t>(ctx, 0x48 + 8u * ring));
    void *shared = ptr<void>(ld<std::uint64_t>(ctx, 0x90));
    const void *record = bp(shared) + 0x80;
    // Network block preparation (T3 and T1 descriptors, output size).
    std::memcpy(bp(net) + 0x3b8, bp(ctx) + 0xf8, 32);
    std::memcpy(bp(net) + 0x3d8, bp(ctx) + 0x98, 32);
    st<std::uint32_t>(net, 0x3fc, ld<std::uint16_t>(ctx, 0x168));
    st<std::uint32_t>(net, 0x3f8, ld<std::uint16_t>(ctx, 0x16a));
    fill_frame_constants(ctx, frame, net, record, *cb, p);
    // Space for the begin marker and the capture record.
    const std::uint32_t need =
        (im.driver_user_data_get_packet_size != nullptr ? im.driver_user_data_get_packet_size(0)
                                                        : 3u) +
        (im.driver_data_packet_size != nullptr ? im.driver_data_packet_size(0x110) : 70u);
    if (cb_free_dwords(*cb) < need || im.driver_user_data_write_packet == nullptr ||
        im.driver_write_data_packet == nullptr) {
        return err::k2NoCommandSpace;
    }
    cb->cursor += im.driver_user_data_write_packet(cb->cursor, 0, 0xd2000001u, nullptr, 0);
    // Capture record: a tagged NOP whose payload holds the parameters and the texture T#s.
    std::uint8_t zeros[0x110] = {};
    std::uint32_t *rec = cb->cursor;
    im.driver_write_data_packet(rec, 0x56000080u, zeros, sizeof zeros);
    cb->cursor += im.driver_data_packet_size != nullptr ? im.driver_data_packet_size(0x110) : 70u;
    void *payload = rec + 1;
    if (im.agc_get_nop_payload != nullptr) {
        im.agc_get_nop_payload(&payload, rec, 0);
    }
    if (payload != nullptr) {
        std::uint8_t *tag = bp(payload);
        std::memcpy(tag + 4, p, sizeof *p);
        std::uint32_t at = 0x74;
        for (std::uint32_t i = 0; i < 5; ++i) {
            const void *t = ld<const void *>(p, 8u * i);
            if (t != nullptr) {
                std::memcpy(tag + at, t, 32);
                st<std::uint64_t>(tag, 4 + 8u * i, addr(tag + at));
                at += 32;
            }
        }
    }
    pre_passes(*cb, ctx, frame, p);
    if (ld<std::uint32_t>(record, 0x10) == 1) {
        (void)phase_begin(*cb);
        network_mode1(*cb, ctx, net, record);
        (void)phase_end(*cb);
    } else {
        network_mode0(*cb, net, record);
    }
    post_pass(*cb, ctx, frame);
    if (cb_free_dwords(*cb) >= 3) {
        cb->cursor += im.driver_user_data_write_packet(cb->cursor, 0, 0xd2000000u, nullptr, 0);
        return 0;
    }
    return err::kScratchAllocFailed;
}

} // namespace

// ------------------------------------------------------------------------------------------------
// Pure helpers: tile tables (Appendix B) and depth parameters.
// ------------------------------------------------------------------------------------------------
namespace {
inline std::int32_t wrap(std::int64_t v) {
    return static_cast<std::int32_t>(static_cast<std::uint32_t>(v));
}
inline std::uint32_t entry_word(std::int32_t start, std::uint32_t rows_field, std::int32_t c,
                                std::uint32_t base) {
    return static_cast<std::uint32_t>(start) * 128u + rows_field +
           static_cast<std::uint32_t>(c) * 0x80000u + base;
}
} // namespace

std::int32_t tile_table_a(std::uint32_t *out, std::int32_t w, std::int32_t h) {
    if (w < 240 || w > 3840 || (w % 4) != 0) {
        return -1;
    }
    if (h < 1 || h > 2160 || (h % 4) != 0) {
        return -2;
    }
    const std::uint32_t wr = static_cast<std::uint32_t>(w + 15) & 0x1ff0u;
    const std::uint32_t pad = (3840u - wr) % 240u;
    std::int32_t col = wrap(std::int64_t{wr} - 240 + pad);
    const std::int32_t h4 = h + 4;
    std::int32_t big_r = static_cast<std::int32_t>(
        ((((pad + wr) * static_cast<std::uint32_t>(h4) + 6239u) / 7200u + 7u) & 0xffe0u) | 0x18u);
    std::int32_t r = h;
    std::int32_t budget = 30;
    std::int32_t i = 0;
    do {
        if (i == 30) {
            return -3;
        }
        if (big_r > 32 && static_cast<std::uint32_t>((col / 240) * h4 + r) <=
                              static_cast<std::uint32_t>(budget * (big_r - 32))) {
            big_r -= 32;
        }
        r -= big_r;
        std::uint32_t base = 0x07d07f00u;
        std::int32_t c = wrap(std::int64_t{col} - pad);
        std::int32_t rows = big_r;
        std::int32_t start = r;
        if (r < -4 && c > 0) {
            start = r + h4;
            c -= 240;
            rows = big_r - 4;
            base = 0x07d87f00u;
            if (start < -4) {
                col -= 240;
                big_r += 32;
                const std::int32_t t = start & 31;
                const std::int32_t adj = t == 0 ? 0 : t - 32;
                rows = rows + start - adj;
                start = adj;
                r = 0;
            }
        }
        out[i] = entry_word(start, static_cast<std::uint32_t>(rows - 20) >> 5, c, base);
        if (r < 1) {
            col -= 240;
            r += h4;
        }
        if (r < 1) {
            r = h;
            col -= 240;
        }
        budget -= 1;
        i += 1;
    } while (col >= 0);
    for (; i < 30; ++i) {
        out[i] = 0xffffffffu;
    }
    return 0;
}

namespace {
std::int32_t tile_table_bc(std::uint32_t *out, std::int32_t w, std::int32_t h, bool c_variant) {
    const std::int32_t step = c_variant ? 120 : 240;
    if (w < step || w > 1920 || (w % 8) != 0) {
        return -1;
    }
    if (h < 1 || h > 1080 || (h % 2) != 0) {
        return -2;
    }
    std::int32_t pad = 0;
    std::int32_t col = 0;
    std::int32_t big_r = 0;
    const std::int32_t h4 = h + 4;
    if (!c_variant) {
        pad = static_cast<std::int32_t>(static_cast<std::uint16_t>(1936 - w) % 240u);
        col = w - 256 + pad;
        big_r = static_cast<std::int32_t>(
                    (((static_cast<std::uint32_t>(w - 16 + pad) * static_cast<std::uint32_t>(h4) +
                       6239u) /
                          7200u +
                      9u) &
                     0xfff8u)) -
                2;
    } else {
        pad = static_cast<std::int32_t>(static_cast<std::uint16_t>(1920 - w) % 120u);
        col = w - 120 + pad;
        big_r = static_cast<std::int32_t>(
            (((static_cast<std::uint32_t>(w + pad) * static_cast<std::uint32_t>(h4) + 3119u) /
                  3600u +
              3u) &
             0xfff8u) |
            4u);
    }
    std::int32_t r = h;
    std::int32_t budget = 30;
    std::int32_t i = 0;
    do {
        if (i == 30) {
            return -3;
        }
        if (big_r > 8 && static_cast<std::uint32_t>((col / step) * h4 + r) <=
                             static_cast<std::uint32_t>(budget * (big_r - 8))) {
            big_r -= 8;
        }
        r -= big_r;
        std::uint32_t base = 0x08007f00u;
        std::int32_t c = col - pad;
        std::int32_t rows = big_r;
        std::int32_t start = r;
        if (r < -4 && c > 0) {
            const std::int32_t s = r + h4;
            c -= step;
            rows = big_r - 4;
            base = 0x08087f00u;
            start = s;
            if (s < -4) {
                col -= step;
                big_r += 8;
                start = (s & 7) - 8 + ((s & 7) == 0 ? 8 : 0);
                r = 0;
                rows = rows + s - start;
            }
        }
        const std::uint32_t rows_field = c_variant ? static_cast<std::uint32_t>(rows) >> 3
                                                   : static_cast<std::uint32_t>(rows + 6) >> 3;
        out[i] = entry_word(start, rows_field, c, base);
        if (r < 1) {
            col -= step;
            r = (r == 0 ? 0 : r + 4) + h;
        }
        if (r < 1) {
            col -= step;
            r = h;
        }
        budget -= 1;
        i += 1;
    } while (col >= 0);
    for (; i < 30; ++i) {
        out[i] = 0xffffffffu;
    }
    return 0;
}
} // namespace

std::int32_t tile_table_b(std::uint32_t *out, std::int32_t w, std::int32_t h) {
    return tile_table_bc(out, w, h, false);
}
std::int32_t tile_table_c(std::uint32_t *out, std::int32_t w, std::int32_t h) {
    return tile_table_bc(out, w, h, true);
}

void depth_params(float out[4], float n, float f, bool inverted) {
    out[0] = 0.0f;
    out[2] = 1.0f;
    const bool inf = std::isinf(f) && f > 0.0f;
    if (!inverted) {
        out[1] = inf ? -n : -n * f / (f - n);
        out[3] = inf ? -1.0f : -f / (f - n);
    } else {
        out[1] = inf ? n : n * f / (f - n);
        out[3] = inf ? -0.0f : n / (f - n);
    }
}

// ------------------------------------------------------------------------------------------------
// Exports (libScePsml_mfsr2).
// ------------------------------------------------------------------------------------------------
std::int32_t sceMfsr2Initialize() {
    ModuleState &s = state();
    if (s.mfsr2_initialised != 0) {
        return err::k2AlreadyInitialized;
    }
    std::int32_t r = module_gpu_setup_once();
    if (r != 0) {
        return r;
    }
    system_info_gather();
    log(kModuleName, "[PSML] ### libScePsml.sprx Release version load ###");
    if (s.trinity_mode == 0) {
        log(kModuleName, "[PSML] MFSR2 isn't supported in sceKernelIsTrinityMode() == 0");
        return err::k2NotTrinity;
    }
    create_mfsr2_shaders();
    r = create_common_shader_set();
    if (r != 0) {
        return r;
    }
    s.mfsr2_initialised = 1;
    return 0;
}

std::int32_t
sceMfsr2GetSharedResourcesInitRequirement(MemoryRequirement *req,
                                          const Mfsr2SharedResourcesInitParameters *params) {
    if (state().mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    if (req == nullptr || params == nullptr) {
        log(kModuleName, "%sgetSharedResourcesInitRequirement: argument must not be nullptr",
            kPrefix);
        return err::k2NullPointer;
    }
    const std::int32_t r = shared_params_check(params, "getSharedResourcesInitRequirement");
    if (r != 0) {
        return r;
    }
    std::memset(state().package_scratch_a, 0, sizeof state().package_scratch_a);
    const std::uint64_t total = shared_layout_size(state().package_scratch_a);
    *req = {0x200000, 0x200000, (total + 0x1fffff) >> 21};
    return 0;
}

std::int32_t sceMfsr2CreateSharedResources(void **out_shared,
                                           const Mfsr2SharedResourcesInitParameters *params) {
    ModuleState &s = state();
    if (s.mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    if (s.mfsr2_shared_count.fetch_add(1) >= 1) {
        s.mfsr2_shared_count.fetch_sub(1);
        return err::k2TooManyObjects;
    }
    auto fail = [&s](std::int32_t e) {
        s.mfsr2_shared_count.fetch_sub(1);
        return e;
    };
    if (out_shared == nullptr || params == nullptr) {
        return fail(err::k2NullPointer);
    }
    if (params->profile != 0) {
        return fail(err::k2InvalidProfile);
    }
    if (params->reserved != 0) {
        return fail(err::k2InvalidParameter);
    }
    std::int32_t r = shared_params_check(params, "createSharedResources");
    if (r != 0) {
        return fail(r);
    }
    std::memset(s.package_scratch_a, 0, sizeof s.package_scratch_a);
    const std::uint64_t pages = (shared_layout_size(s.package_scratch_a) + 0x1fffff) >> 21;
    if (pages != params->block_count) {
        return fail(err::k2InvalidParameter);
    }
    std::uint64_t base = 0;
    std::uint64_t size = 0;
    if (map_blocks(&base, &size, params->blocks, params->block_count, kSharedVa) != 0) {
        unmap(base, size);
        *out_shared = nullptr;
        log(kModuleName, "%screateSharedResources: Failed to map memory.", kPrefix);
        return fail(err::k2InvalidParameter);
    }
    Bump alloc{base, base + size};
    const std::uint64_t obj = alloc.take(kSharedObjectSize, 8);
    const std::uint64_t scratch = alloc.take(kScratchSize, kScratchAlign);
    std::uint64_t ts_align = 0;
    const std::uint64_t ts_size = tex_size(kMaxW, kMaxH, kFmtShared, &ts_align);
    const std::uint64_t ts = alloc.take(ts_size, ts_align);
    if (obj == 0 || scratch == 0 || ts == 0) {
        unmap(base, size);
        *out_shared = nullptr;
        log(kModuleName, "%screateSharedResources: Failed to map memory.", kPrefix);
        return fail(err::k2InvalidParameter);
    }
    void *o = ptr<void>(obj);
    std::memset(o, 0, kSharedObjectSize);
    const std::uint64_t pblock = alloc.take(kParamBlockSize, 4);
    std::memset(s.package_scratch_b, 0, sizeof s.package_scratch_b);
    st<std::uint64_t>(s.package_scratch_b, 0x2f8, pblock);
    (void)package_load(s.package_scratch_b, alloc, scratch); // missing package is not an error
    st<std::uint64_t>(o, 0x000, scratch);
    build_texture_desc(bp(o) + 0x008, ts, kMaxW, kMaxH, kFmtShared, 9);
    write_spec(bp(o) + 0x028, ts, kMaxW, kMaxH, kFmtShared, 9);
    st<std::uint32_t>(o, 0x078, params->profile);
    std::memcpy(bp(o) + 0x080, s.package_scratch_b, 0x300);
    st<std::uint64_t>(o, 0x380, base);
    st<std::uint64_t>(o, 0x388, size);
    st<std::uint64_t>(o, 0x3a0, 0xf840000000ull);
    *out_shared = o;
    return 0;
}

std::int32_t sceMfsr2ReleaseSharedResources(void *shared) {
    ModuleState &s = state();
    if (s.mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    // No null check and no live-context check (quirk of the original).
    if (import_table().kernel_release_tool_memory != nullptr) {
        import_table().kernel_release_tool_memory(ld<std::uint64_t>(shared, 0x390),
                                                  ld<std::uint64_t>(shared, 0x398));
    }
    unmap(ld<std::uint64_t>(shared, 0x380), ld<std::uint64_t>(shared, 0x388));
    s.mfsr2_shared_count.fetch_sub(1);
    return 0;
}

std::int32_t sceMfsr2GetContextInitRequirement(MemoryRequirement *req,
                                               const Mfsr2ContextInitParameters *params) {
    if (state().mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    if (req == nullptr) {
        log(kModuleName, "%sgetContextInitRequirement: The argument req must not be nullptr",
            kPrefix);
        return err::k2NullPointer;
    }
    const std::int32_t r = context_params_check(params, "getContextInitRequirement");
    if (r != 0) {
        return r;
    }
    const ContextLayout l =
        context_layout(0, params->output_color_width, params->output_color_height);
    *req = {0x200000, 0x200000, (l.total + 0x1fffff) >> 21};
    return 0;
}

std::int32_t sceMfsr2CreateContext(void **out_context, const Mfsr2ContextInitParameters *params) {
    ModuleState &s = state();
    if (s.mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    if (s.mfsr2_context_count.fetch_add(1) >= 4) {
        s.mfsr2_context_count.fetch_sub(1);
        return err::k2TooManyObjects;
    }
    auto fail = [&s](std::int32_t e) {
        s.mfsr2_context_count.fetch_sub(1);
        return e;
    };
    if (out_context == nullptr) {
        log(kModuleName, "%screateContext: context must not be nullptr", kPrefix);
        return fail(err::k2NullPointer);
    }
    std::int32_t r = context_params_check(params, "createContext");
    if (r != 0) {
        return fail(r);
    }
    const std::uint32_t w = params->output_color_width;
    const std::uint32_t h = params->output_color_height;
    if (((context_layout(0, w, h).total + 0x1fffff) >> 21) != params->block_count) {
        return fail(err::k2InvalidParameter);
    }
    void *shared = params->shared_resources;
    // Slot: first zero busy flag set to 1 atomically.
    int slot = -1;
    for (int i = 0; i < 4 && slot < 0; ++i) {
        std::atomic_ref<std::uint32_t> flag(
            *ptr<std::uint32_t>(addr(shared) + 0x400 + 4u * static_cast<unsigned>(i)));
        std::uint32_t expected = 0;
        if (flag.compare_exchange_strong(expected, 1)) {
            slot = i;
        }
    }
    auto map_fail = [&](std::uint64_t base, std::uint64_t size) {
        unmap(base, size);
        if (slot >= 0) {
            std::atomic_ref<std::uint32_t>(
                *ptr<std::uint32_t>(addr(shared) + 0x400 + 4u * static_cast<unsigned>(slot)))
                .store(0);
        }
        *out_context = nullptr;
        log(kModuleName, "%screateContext: Failed to map memory.", kPrefix);
        return fail(err::k2InvalidParameter);
    };
    if (slot < 0) {
        return map_fail(0, 0);
    }
    const std::uint64_t va = ld<std::uint64_t>(shared, 0x380) + ld<std::uint64_t>(shared, 0x388) +
                             static_cast<std::uint64_t>(slot) * kContextStride;
    std::uint64_t base = 0;
    std::uint64_t size = 0;
    if (map_blocks(&base, &size, params->blocks, params->block_count, va) != 0) {
        return map_fail(base, size);
    }
    const ContextLayout l = context_layout(base, w, h);
    void *ctx = ptr<void>(base);
    std::memset(ctx, 0, kCtxHeaderSize);
    // T3 aliases the start of the shared scratch; T4 is a view of the shared texture.
    std::uint64_t a = 0;
    const std::uint64_t t3_size = tex_size(w, h, kFmtT1, &a);
    const std::uint64_t t4_size = tex_size(w, h, kFmtShared, &a);
    const std::uint64_t ts_size = tex_size(ld<std::uint32_t>(shared, 0x28 + 0x14),
                                           ld<std::uint32_t>(shared, 0x28 + 0x18), kFmtShared, &a);
    if (t3_size > 0x2000000ull || t4_size > ts_size || l.total > size) {
        return map_fail(base, size);
    }
    const std::uint64_t scratch = ld<std::uint64_t>(shared, 0x000);
    st<std::uint32_t>(ctx, 0x000, kCtxMagicCreated);
    for (std::uint32_t i = 0; i < 8; ++i) {
        const std::uint64_t nb = base + align_up(kCtxHeaderSize, 4) + i * kNetBlockSize;
        const std::uint64_t fb = base + 0x2188 + i * kFrameBlockSize;
        const std::uint64_t sb = base + 0x7700 + i * kSmallBlockSize;
        st<std::uint64_t>(ctx, 0x008 + 8u * i, nb);
        st<std::uint64_t>(ctx, 0x048 + 8u * i, fb);
        st<std::uint64_t>(ctx, 0x118 + 8u * i, sb);
        build_tensor_table(ptr<void>(nb), scratch);
        init_frame_constants(ptr<void>(fb), w, h);
    }
    st<std::uint32_t>(ctx, 0x088, 0);
    st<std::uint64_t>(ctx, 0x090, addr(shared));
    build_texture_desc(bp(ctx) + 0x098, l.t1, w, h, kFmtT1, 1);
    build_texture_desc(bp(ctx) + 0x0b8, l.t2, w, h, kFmtShared, 1);
    build_texture_desc(bp(ctx) + 0x0d8, ld<std::uint64_t>(shared, 0x28), w, h, kFmtShared, 9);
    build_texture_desc(bp(ctx) + 0x0f8, scratch, w, h, kFmtT1, 9);
    st<std::uint64_t>(ctx, 0x158, base);
    st<std::uint64_t>(ctx, 0x160, size);
    st<std::uint16_t>(ctx, 0x168, static_cast<std::uint16_t>(w));
    st<std::uint16_t>(ctx, 0x16a, static_cast<std::uint16_t>(h));
    st<std::uint16_t>(ctx, 0x16c, 1);
    st<std::uint16_t>(ctx, 0x16e, 1);
    st<std::uint32_t>(ctx, 0x170, kMaxW);
    st<std::uint32_t>(ctx, 0x174, kMaxH);
    st<std::uint64_t>(shared, 0x410 + 8u * static_cast<unsigned>(slot), base);
    *out_context = ctx;
    return 0;
}

std::int32_t sceMfsr2ReleaseContext(void *ctx) {
    ModuleState &s = state();
    if (s.mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    // No null check (quirk of the original). Read everything first: the header is unmapped.
    void *shared = ptr<void>(ld<std::uint64_t>(ctx, 0x90));
    const std::uint64_t base = ld<std::uint64_t>(ctx, 0x158);
    const std::uint64_t size = ld<std::uint64_t>(ctx, 0x160);
    unmap(base, size);
    for (std::uint32_t i = 0; i < 4; ++i) {
        if (ld<std::uint64_t>(shared, 0x410 + 8u * i) == addr(ctx)) {
            st<std::uint64_t>(shared, 0x410 + 8u * i, 0);
            std::atomic_ref<std::uint32_t> flag(*ptr<std::uint32_t>(addr(shared) + 0x400 + 4u * i));
            std::uint32_t expected = 1;
            flag.compare_exchange_strong(expected, 0);
            break;
        }
    }
    s.mfsr2_context_count.fetch_sub(1);
    return 0;
}

std::int32_t sceMfsr2GetDispatchCommandSize(const void *, std::uint32_t *out_dwords) {
    if (state().mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    *out_dwords = 0x800; // no null check (quirk of the original)
    return 0;
}

std::int32_t sceMfsr2Dispatch(void *ctx, const Mfsr2RawCommandSpan *span,
                              const Mfsr2DispatchParameters *params) {
    if (state().mfsr2_initialised != 1) {
        return err::k2NotInitialized;
    }
    if (span == nullptr) {
        return dispatch_core(ctx, nullptr, params);
    }
    AgcCommandBuffer cb{};
    cb_init(cb, span->start, static_cast<std::uint64_t>(span->size_dwords) * 4u);
    const std::int32_t r = dispatch_core(ctx, &cb, params);
    pad_with_nop(cb);
    return r;
}

} // namespace bc5::reimpl::psml
