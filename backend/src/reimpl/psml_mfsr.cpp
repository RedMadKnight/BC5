// SPDX-License-Identifier: GPL-2.0-only
// libScePsml re-creation, main library "libScePsml" (MFSR, version 1 API): initialise, shared
// resources with the MFSR4K/8K package, contexts, requirement queries and the five per-frame
// dispatch exports.
//
// Per the original module's behaviour (clean-room description, see src/reimpl/PROVENANCE.md).
// The description gives the order of the recorded work, the raw packets, the shader slots, the
// object offsets the GPU work depends on and the quirks; several shader-ABI blocks (SRT B's
// fixed constant tables, label-block fields beyond the named ones) are not described and are
// laid out by us (TODO(verify) at each place). Opaque objects keep the described offsets.
#include "bc5/reimpl/psml_internal.hpp"

#include <atomic>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace bc5::reimpl::psml {

using namespace detail;

namespace {

constexpr std::uint64_t k2M = 0x200000;
constexpr std::uint32_t kMagicCreated = 0x9231;
constexpr std::uint32_t kMagicDispatched = 0xa9c4;
constexpr std::uint32_t kMagicReleased = 0x8313;
constexpr std::uint64_t kCtxObjectSize = 0x1ae0;
constexpr std::uint64_t kCtxTail = 0x2000;
constexpr std::uint64_t kSrObjectOffset = 0x5ffe20;
constexpr std::uint64_t kSrObjectSize = 0x1e0;
constexpr std::uint64_t kSecondMapSize = 0x600000;
constexpr std::uint64_t kRingSlotSize = 0x20000;
constexpr std::uint64_t kLabelSize = 0x400;
constexpr std::uint32_t kSrtASize = 0x2e4;
constexpr std::uint32_t kSrtBSize = 0xa48;

// INTEROP TABLES (description): per-profile shared VA size, maximum output size, library-chosen
// VA start.
constexpr std::uint64_t kProfileVaSize[3] = {0x06200000, 0x18200000, 0x12200000};
constexpr std::uint32_t kProfileMaxW[3] = {3840, 7680, 3840};
constexpr std::uint32_t kProfileMaxH[3] = {2168, 4328, 2168};
constexpr std::uint64_t kProfileVaStart[3] = {0xfb00000000ull, 0xfa00000000ull, 0xf900000000ull};
constexpr std::uint16_t kPackageId[3] = {0xf2f4, 0xf4f8, 0xa4a8};

// Agc format words (data format | swizzle << 32) as the description gives them.
constexpr std::uint64_t kFmtInternal = 0x000003ac0000001eull;
constexpr std::uint64_t kFmtRfm = 0x00000fac00000039ull;
constexpr std::uint64_t kFmtLut = 0x00000fac0000003eull; // 8 bytes per element, TODO(verify)
constexpr std::uint64_t kFmtScratch8 = 0x0000022c0000003eull;

// Group-A slots used by this part.
constexpr std::uint32_t kShExposure = 0x16e808;
constexpr std::uint32_t kShPrePass = 0x16e810;
constexpr std::uint32_t kShPrepare = 0x16e828;
constexpr std::uint32_t kShCopy = 0x16e838;
constexpr std::uint32_t kShCopyLut = 0x16e840;
constexpr std::uint32_t kShLutH = 0x16e848;
constexpr std::uint32_t kShLutV = 0x16e850;
constexpr std::uint32_t kShKernel0 = 0x16e858;

// ---- SharedResources object (0x1e0 bytes at the tail of the second mapping) --------------------
// Described offsets: 0x000 profile, 0x008/0x010 first mapping, 0x018/0x020 second mapping,
// 0x028 first-mapping end, 0x030 context memory base, 0x048/0x068/0x088 the three intermediate
// T#s, 0x0a8 profile-2 region, 0x0b0 4 GiB scratch, 0x0b8 package state, 0x0d0 package id,
// 0x0d8 network entries (0x28 each), 0x140 name, 0x158 four context slots (0x18 each).
// Our own placement of fields the description leaves open (TODO(verify)): 0x128 u32 weights
// size per network, 0x130 u32 extra size per network, 0x138 u8 "variant" byte of the entry,
// 0x13c f32 package override value, 0x150 f32 exposure value, 0x154 u8 name-rule flag,
// 0x1b8 u64 constant block per network, 0x1c8 f32 name-rule value.
namespace sr {
constexpr std::uint32_t kProfile = 0x000, kMap1 = 0x008, kMap1Size = 0x010, kMap2 = 0x018,
                        kMap2Size = 0x020, kMap1End = 0x028, kMemBase = 0x030, kTex = 0x048,
                        kRegion2 = 0x0a8, kScratch = 0x0b0, kTwoNets = 0x0b8, kConfigA = 0x0c0,
                        kConfigB = 0x0c8, kPackageId = 0x0d0, kEntries = 0x0d8,
                        kWeightsSize = 0x128, kExtraSize = 0x130, kVariant = 0x138,
                        kOverride = 0x13c, kName = 0x140, kExposure = 0x150, kNameFlag = 0x154,
                        kSlots = 0x158, kConstBlock = 0x1b8, kNameValue = 0x1c8;
// Network entry fields.
constexpr std::uint32_t kECode = 0x00, kEHeader = 0x08, kEExtra = 0x10, kEWeights = 0x18,
                        kEShader = 0x20;
} // namespace sr

// ---- Context object (0x1ae0 bytes at mapping end - 0x2000) ------------------------------------
namespace cx {
constexpr std::uint32_t kMagic = 0x000, kSlot = 0x004, kProfile = 0x008, kTexBudget = 0x010,
                        kTexAlign = 0x018, kInternal = 0x020, kRfmA = 0x088, kRfmB = 0x0a8,
                        kKeepHistory = 0x128, kKeepDepth = 0x148, kKeepReactive = 0x168,
                        kKeepLutA = 0x188, kKeepLutB = 0x1a8, kOptions = 0x228, kCapDepth = 0x32c,
                        kCapHistory = 0x338, kCapReactive = 0x344, kCapLut = 0x350,
                        kSrtTemplate = 0x358, kShared = 0x360, kOwned = 0x368, kReload = 0x36a,
                        kRfmMapA = 0x370, kRfmMapB = 0x380, kMap = 0x390, kRing = 0x3a0,
                        kLabels0 = 0x3a8, kLabels1 = 0x428, kRings = 0x4a8, kMt = 0x568,
                        kDist = 0x18f0, kThird = 0x1910, kNetInput = 0x1918, kOutput = 0x1920,
                        kGrid = 0x1928, kGrid2 = 0x1930, kExposureScratch = 0x1938, kPrev = 0x1950,
                        kPrevCamera = 0x1990, kFrameBits = 0x1a50, kTuning = 0x1a68,
                        kFlags = 0x1a8c, kLutWork = 0x1a90;
} // namespace cx

// Internal context-init parameters (6A.1 in the description; our C++ form).
struct InitParamsBase {
    std::uint32_t profile = 0;
    std::uint64_t unused = 0;
    const PhysicalBlock *blocks = nullptr;
    std::uint64_t block_count = 0;
    std::uint16_t width = 0;
    std::uint16_t height = 0;
    std::uint8_t options = 0;
    const TextureSizeInfo *depth = nullptr;
    const TextureSizeInfo *history = nullptr;
    const TextureSizeInfo *reactive = nullptr;
    const FsrLutSize *lut = nullptr;
    TextureSizeInfo conv[2] = {};
    void *caller_shared = nullptr;
    void *owned_shared = nullptr;
    std::uint32_t flags = 0;
};

// Copies keep the converted size records pointing at their own storage.
struct InitParams : InitParamsBase {
    InitParams() = default;
    InitParams(const InitParams &o) : InitParamsBase(o) { fix(o); }
    InitParams &operator=(const InitParams &o) {
        InitParamsBase::operator=(o);
        fix(o);
        return *this;
    }
    void fix(const InitParams &o) {
        if (o.depth == &o.conv[0]) {
            depth = &conv[0];
        }
        if (o.history == &o.conv[1]) {
            history = &conv[1];
        }
    }
};

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

bool profile_allowed(std::uint32_t profile) {
    const std::uint8_t bits = state().feature_bits;
    return profile == 0 || (profile == 1 && (bits & 1u) != 0) || (profile == 2 && (bits & 2u) != 0);
}

bool ctx_valid(const void *ctx) {
    if (ctx == nullptr) {
        return false;
    }
    const std::uint32_t m = ld<std::uint32_t>(ctx, cx::kMagic);
    return m == kMagicCreated || m == kMagicDispatched;
}

std::uint64_t format_for_bpe(std::uint32_t bpe) {
    // TODO(verify): our choice of a data format per element size for kept copies.
    switch (bpe) {
    case 1:
        return 0x00000fac00000001ull;
    case 2:
        return 0x00000fac00000007ull;
    case 8:
        return 0x00000fac0000003eull;
    case 16:
        return 0x00000fac0000004bull;
    default:
        return 0x00000fac00000016ull;
    }
}

std::uint64_t tex_size(std::uint32_t w, std::uint32_t h, std::uint64_t fmt, std::uint64_t *align) {
    std::uint64_t size = 0;
    texture_size(w, h, fmt, &size, align);
    return size;
}

// ---- mapping list (up to 0x102 entries of 2 MiB pages) ------------------------------------------
struct MappingList {
    struct Entry {
        std::uint64_t va;
        bool mapped;
    };
    std::vector<Entry> entries;
    std::int32_t add_range(std::uint64_t va, std::uint64_t size) {
        if ((va & (k2M - 1)) != 0 || (size & (k2M - 1)) != 0) {
            return -1;
        }
        for (std::uint64_t off = 0; off < size; off += k2M) {
            if (entries.size() >= 0x102) {
                return -1;
            }
            entries.push_back({va + off, false});
        }
        return 0;
    }
    std::int32_t map_all(const PhysicalBlock *blocks, std::uint64_t count, const char *name) {
        if (count < entries.size()) {
            return -1;
        }
        Imports &im = import_table();
        for (std::size_t i = 0; i < entries.size(); ++i) {
            void *where = ptr<void>(entries[i].va);
            const std::int32_t r =
                im.kernel_map_named_direct_memory != nullptr
                    ? im.kernel_map_named_direct_memory(
                          &where, k2M, 0x32, 0x90,
                          static_cast<std::int64_t>(blocks[i].direct_offset), k2M, name)
                    : -1;
            if (r != 0) {
                return r;
            }
            entries[i].mapped = true;
        }
        return 0;
    }
    void undo() {
        std::vector<BatchMapEntry> b;
        for (Entry &e : entries) {
            if (e.mapped) {
                b.push_back({ptr<void>(e.va), 0, k2M, 0, 0, 0, kBatchMapOpUnmap});
                e.mapped = false;
            }
        }
        if (b.empty()) {
            return;
        }
        Imports &im = import_table();
        if (im.kernel_batch_map2 != nullptr) {
            std::int32_t done = 0;
            im.kernel_batch_map2(b.data(), static_cast<std::int32_t>(b.size()), &done, 0);
        } else if (im.kernel_munmap != nullptr) {
            for (const BatchMapEntry &e : b) {
                im.kernel_munmap(e.start, e.length);
            }
        }
    }
};

void unmap(std::uint64_t base, std::uint64_t size) {
    if (size != 0 && import_table().kernel_munmap != nullptr) {
        import_table().kernel_munmap(ptr<void>(base), size);
    }
}

// ---- MT19937 kept inside the context (index at +0x568, 624 words at +0x56c) --------------------
void mt_seed(void *ctx, std::uint32_t seed) {
    std::uint8_t *s = bp(ctx) + cx::kMt + 4;
    std::uint32_t prev = seed;
    st<std::uint32_t>(s, 0, prev);
    for (std::uint32_t i = 1; i < 624; ++i) {
        prev = 1812433253u * (prev ^ (prev >> 30)) + i;
        st<std::uint32_t>(s, 4u * i, prev);
    }
    st<std::uint32_t>(ctx, cx::kMt, 624);
}

std::uint32_t mt_next(void *ctx) {
    std::uint8_t *s = bp(ctx) + cx::kMt + 4;
    std::uint32_t idx = ld<std::uint32_t>(ctx, cx::kMt);
    if (idx >= 624) {
        for (std::uint32_t i = 0; i < 624; ++i) {
            const std::uint32_t y = (ld<std::uint32_t>(s, 4u * i) & 0x80000000u) |
                                    (ld<std::uint32_t>(s, 4u * ((i + 1) % 624)) & 0x7fffffffu);
            std::uint32_t v = ld<std::uint32_t>(s, 4u * ((i + 397) % 624)) ^ (y >> 1);
            if ((y & 1u) != 0) {
                v ^= 0x9908b0dfu;
            }
            st<std::uint32_t>(s, 4u * i, v);
        }
        idx = 0;
    }
    std::uint32_t y = ld<std::uint32_t>(s, 4u * idx);
    st<std::uint32_t>(ctx, cx::kMt, idx + 1);
    y ^= y >> 11;
    y ^= (y << 7) & 0x9d2c5680u;
    y ^= (y << 15) & 0xefc60000u;
    y ^= y >> 18;
    return y;
}

float uniform(void *ctx, std::uint32_t dist_off) {
    const float lo = ld<float>(ctx, dist_off + 8);
    const float hi = ld<float>(ctx, dist_off + 12);
    return lo + (hi - lo) * static_cast<float>(static_cast<double>(mt_next(ctx)) / 4294967296.0);
}

// ------------------------------------------------------------------------------------------------
// Package (MFSR4K / MFSR8K) loader.
// ------------------------------------------------------------------------------------------------
std::int32_t package_load(void *srp, std::uint32_t profile) {
    const std::uint16_t id = kPackageId[profile];
    const bool two = profile == 2;
    st<std::uint8_t>(srp, sr::kTwoNets, two ? 1 : 0);
    st<std::uint16_t>(srp, sr::kPackageId, id);
    std::int32_t vi = 0;
    if (id != 0xa4a8) {
        vi = version_index(effective_version_string(), state().compiled_sdk_version);
        if (vi < 0) {
            return err::kProfileMismatch;
        }
    }
    // Profile 2's id has no file name in the original, so its open fails.
    const char *file = profile == 0   ? "MFSR4K_v070.psp"
                       : profile == 1 ? "MFSR8K_v070.psp"
                                      : nullptr;
    void *fp = file != nullptr ? pkg_open(file) : nullptr;
    if (fp == nullptr) {
        return err::kProfileMismatch; // 0x8a810011 internally, reported as 0x8a810003
    }
    std::uint8_t hdr[0x30];
    if (!pkg_read(fp, 0, hdr, sizeof hdr) || ld<std::uint16_t>(hdr, 4) != id ||
        ld<std::uint16_t>(hdr, 6) != 0x914) {
        pkg_close(fp);
        return err::kProfileMismatch;
    }
    const std::uint32_t per_version = hdr[0x28];
    const bool lz4 = hdr[0x29] == 1;
    const std::uint32_t table = ld<std::uint32_t>(hdr, 0x0c);
    const std::uint64_t map2 = ld<std::uint64_t>(srp, sr::kMap2);
    Bump alloc{map2, addr(srp)};
    const std::uint32_t nets = two ? 2u : 1u;
    for (std::uint32_t n = 1; n <= nets; ++n) {
        const std::uint64_t idx =
            (static_cast<std::uint64_t>(vi) << (per_version == 2 ? 1 : 0)) + n - 1;
        std::uint8_t e[0x40];
        if (!pkg_read(fp, table + 0x40 * idx, e, sizeof e)) {
            continue;
        }
        if (n == 1) {
            std::memset(bp(srp) + sr::kName, 0, 16);
            std::memcpy(bp(srp) + sr::kName, e, 15);
            log(kModuleName, "[PSML] kDefault %s",
                reinterpret_cast<const char *>(bp(srp) + sr::kName));
        }
        const std::uint32_t code_size =
            lz4 ? ld<std::uint32_t>(e, 0x38) : ld<std::uint32_t>(e, 0x1c);
        const std::uint64_t code = alloc.take(code_size, k2M);
        const std::uint64_t header = alloc.take(ld<std::uint32_t>(e, 0x14), 8);
        const std::uint64_t extra = alloc.take(ld<std::uint32_t>(e, 0x2c), 4);
        const std::uint64_t cblock = alloc.take(0x40, 4);
        const std::uint64_t weights = alloc.take(ld<std::uint32_t>(e, 0x24), 0x10000);
        if (header != 0) {
            pkg_read(fp, ld<std::uint32_t>(e, 0x10), ptr(header), ld<std::uint32_t>(e, 0x14));
        }
        if (extra != 0) {
            pkg_read(fp, ld<std::uint32_t>(e, 0x28), ptr(extra), ld<std::uint32_t>(e, 0x2c));
        }
        if (weights != 0) {
            pkg_read(fp, ld<std::uint32_t>(e, 0x20), ptr(weights), ld<std::uint32_t>(e, 0x24));
        }
        if (code != 0) {
            const std::uint32_t stored = ld<std::uint32_t>(e, 0x1c);
            if (!lz4) {
                pkg_read(fp, ld<std::uint32_t>(e, 0x18), ptr(code), stored);
            } else {
                const std::uint64_t scratch = ld<std::uint64_t>(srp, sr::kScratch);
                if (scratch != 0 && stored <= k2M &&
                    pkg_read(fp, ld<std::uint32_t>(e, 0x18), ptr(scratch), stored)) {
                    const std::int32_t got =
                        lz4_decompress(ptr(scratch), ptr(code), static_cast<std::int32_t>(stored),
                                       static_cast<std::int32_t>(code_size));
                    if (got != static_cast<std::int32_t>(code_size)) {
                        log(kModuleName, "[PSML] decompressed size mismatch (%d, %u)", got,
                            code_size);
                    }
                }
            }
        }
        // 27 fp16 values; 24 of them scaled by 128 into the 0x40-byte constant block.
        // TODO(verify): the block's element type (we keep fp16) and the place of the last three.
        if (cblock != 0) {
            std::uint16_t h[27] = {};
            const std::uint32_t hs = ld<std::uint32_t>(e, 0x34);
            pkg_read(fp, ld<std::uint32_t>(e, 0x30), h, hs < sizeof h ? hs : sizeof h);
            std::uint8_t *cb = ptr(cblock);
            std::memset(cb, 0, 0x40);
            for (int i = 0; i < 24; ++i) {
                st<std::uint16_t>(cb, 2u * static_cast<unsigned>(i),
                                  float_to_half(half_to_float(h[i]) * 128.0f));
            }
            std::memcpy(cb + 48, h + 24, 6);
        }
        void *shader = nullptr;
        if (state().trinity_mode == 1) {
            if (create_shader_checked(&shader, ptr<void>(header), ptr<void>(code)) != 0) {
                shader = nullptr;
            }
        }
        std::uint8_t *ent = bp(srp) + sr::kEntries + 0x28u * (n - 1);
        st<std::uint64_t>(ent, sr::kECode, code);
        st<std::uint64_t>(ent, sr::kEHeader, header);
        st<std::uint64_t>(ent, sr::kEExtra, extra);
        st<std::uint64_t>(ent, sr::kEWeights, weights);
        st<std::uint64_t>(ent, sr::kEShader, addr(shader));
        st<std::uint32_t>(srp, sr::kWeightsSize + 4u * (n - 1), ld<std::uint32_t>(e, 0x24));
        st<std::uint32_t>(srp, sr::kExtraSize + 4u * (n - 1), ld<std::uint32_t>(e, 0x2c));
        st<std::uint64_t>(srp, sr::kConstBlock + 8u * (n - 1), cblock);
    }
    // Configuration blocks (0x400 bytes, 32-byte aligned copies).
    const std::uint64_t ca = alloc.take(kLabelSize, 32);
    if (ca != 0 && pkg_read(fp, ld<std::uint32_t>(hdr, 0x10), ptr(ca), kLabelSize)) {
        st<std::uint64_t>(srp, sr::kConfigA, ca);
        char nm[17] = {};
        std::memcpy(nm, ptr(ca + 0x88), 16);
        log(kModuleName, "[PSML] config %s", nm);
    }
    if (two) {
        const std::uint64_t cbk = alloc.take(kLabelSize, 32);
        if (cbk != 0 && pkg_read(fp, ld<std::uint32_t>(hdr, 0x18), ptr(cbk), kLabelSize)) {
            st<std::uint64_t>(srp, sr::kConfigB, cbk);
        }
    }
    // Name rule of package 0xf2f4. TODO(verify): purpose and destination of the flag and value.
    if (id == 0xf2f4) {
        const char *name = reinterpret_cast<const char *>(bp(srp) + sr::kName);
        if (name[0] == 'P' && name[1] >= '0' && name[1] <= '9' && name[2] >= '0' &&
            name[2] <= '9' && (name[1] - '0') * 10 + (name[2] - '0') >= 60) {
            st<std::uint8_t>(srp, sr::kNameFlag, 1);
            st<float>(srp, sr::kNameValue, 6.0f);
        }
        if (std::strncmp(name, "P11_60", 7) != 0) {
            st<float>(srp, sr::kNameValue, 6.0f);
        }
    }
    pkg_close(fp);
    return 0;
}

// ------------------------------------------------------------------------------------------------
// Shared resources.
// ------------------------------------------------------------------------------------------------
std::uint64_t shared_blocks(std::uint32_t profile) { return kProfileVaSize[profile] / k2M + 3; }

void shared_requirement(MemoryRequirement *out, std::uint32_t profile) {
    *out = {k2M, k2M, shared_blocks(profile)};
}

std::int32_t shared_layout(void *srp, std::uint32_t profile) {
    const std::uint64_t base = ld<std::uint64_t>(srp, sr::kMap1);
    const std::uint64_t end = ld<std::uint64_t>(srp, sr::kMap1End);
    Bump alloc{base, end};
    const std::uint64_t boundary = align_up(base, 0x100000000ull);
    if (boundary + k2M <= end) {
        st<std::uint64_t>(srp, sr::kScratch, boundary);
        if (boundary == base) {
            alloc.cur = base + k2M;
        }
    }
    const std::uint32_t w = kProfileMaxW[profile];
    const std::uint32_t h = kProfileMaxH[profile];
    for (std::uint32_t i = 0; i < 3; ++i) {
        const std::uint64_t fmt = i == 0 ? kFmtInternal : kFmtRfm;
        std::uint64_t a = 0;
        const std::uint64_t size = tex_size(w, h, fmt, &a);
        const std::uint64_t t = alloc.take(size, k2M);
        build_texture_desc(bp(srp) + sr::kTex + 0x20u * i, t, w, h, fmt, 0);
    }
    if (profile == 2) {
        const std::uint64_t region = alloc.take(0xc000000ull, k2M);
        if (region == 0) {
            return err::kNotEnoughMemory;
        }
        st<std::uint64_t>(srp, sr::kRegion2, region);
    }
    return package_load(srp, profile);
}

std::int32_t shared_create(void **out, const SharedResourcesInitParameters *params) {
    const std::uint32_t p = params->profile;
    if (p > 2) {
        return err::kInvalidParameter; // our guard: the original indexes past its tables
    }
    const std::uint64_t va_size = kProfileVaSize[p];
    const std::uint64_t gap = p == 1 ? 0x40000000ull : 0x10000000ull;
    std::uint64_t start = params->virtual_address_start;
    if (start == 0) {
        start = kProfileVaStart[p];
    } else {
        const std::uint32_t sdk = state().compiled_sdk_version;
        if (sdk > 0x10ffffffu && (start & 0x3fffffffull) != 0) {
            log(kModuleName, "[PSML] m_virtualAddressStart must be 1 GiB aligned");
            return err::kInvalidParameter;
        }
        if (sdk == 0x10000000u && (start >> 32) != ((start + va_size + gap) >> 32)) {
            log(kModuleName, "[PSML] m_virtualAddressStart crosses a 4 GiB boundary");
            return err::kInvalidParameter;
        }
    }
    if (params->reserved != 0) {
        log(kModuleName, "[PSML] MfsrSharedResourcesInitParameters reserved must be 0");
        return err::kInvalidParameter;
    }
    if (params->block_count < shared_blocks(p)) {
        log(kModuleName, "[PSML] the number of blocks is not sufficient");
        return err::kInvalidParameter;
    }
    if (params->blocks == nullptr) {
        log(kModuleName, "[PSML] the block list is not set");
        return err::kInvalidParameter;
    }
    const std::uint64_t map2 = start + va_size + gap;
    MappingList list;
    if (list.add_range(start, va_size) != 0 || list.add_range(map2, kSecondMapSize) != 0) {
        return -1;
    }
    const std::int32_t r =
        list.map_all(params->blocks, params->block_count, "ScePsmlSharedResources");
    if (r != 0) {
        list.undo();
        return r;
    }
    void *srp = ptr<void>(map2 + kSrObjectOffset);
    std::memset(srp, 0, kSrObjectSize);
    st<std::uint32_t>(srp, sr::kProfile, p);
    st<std::uint64_t>(srp, sr::kMap1, start);
    st<std::uint64_t>(srp, sr::kMap1Size, va_size);
    st<std::uint64_t>(srp, sr::kMap2, map2);
    st<std::uint32_t>(srp, sr::kMap2Size, static_cast<std::uint32_t>(kSecondMapSize));
    st<std::uint64_t>(srp, sr::kMap1End, start + va_size);
    st<std::uint64_t>(srp, sr::kMemBase, map2 + 0x800000);
    *out = srp;
    // Quirk of the original: a layout or package failure is not reported; the object stays.
    if (shared_layout(srp, p) != 0) {
        log(kModuleName, "[PSML] shared resources created without a network package");
    }
    const std::uint64_t rfm_step = p == 1 ? 0x10000000ull : 0x4000000ull;
    for (std::uint32_t i = 0; i < 4; ++i) {
        std::uint8_t *slot = bp(srp) + sr::kSlots + 0x18u * i;
        st<std::uint64_t>(slot, 0, 0);
        st<std::uint64_t>(slot, 8, start + va_size + i * rfm_step);
        st<std::uint64_t>(slot, 16, map2 + 0x800000 + i * 0xa000000ull);
    }
    return 0;
}

std::int32_t shared_create_counted(void **out, const SharedResourcesInitParameters *params) {
    ModuleState &s = state();
    if (s.shared_count.fetch_add(1) >= 1) {
        s.shared_count.fetch_sub(1);
        return err::kSharedExists;
    }
    const std::int32_t r = shared_create(out, params);
    if (r != 0) {
        s.shared_count.fetch_sub(1);
    }
    return r;
}

std::int32_t shared_release(void *srp) {
    for (std::uint32_t i = 0; i < 4; ++i) {
        if (ld<std::uint64_t>(srp, sr::kSlots + 0x18u * i) != 0) {
            log(kModuleName, "[PSML] contexts are still alive");
            return err::kBadContext;
        }
    }
    const std::uint64_t m1 = ld<std::uint64_t>(srp, sr::kMap1);
    const std::uint64_t m1s = ld<std::uint64_t>(srp, sr::kMap1Size);
    const std::uint64_t m2 = ld<std::uint64_t>(srp, sr::kMap2);
    const std::uint64_t m2s = ld<std::uint32_t>(srp, sr::kMap2Size);
    unmap(m1, m1s);
    unmap(m2, m2s);
    return 0;
}

// ------------------------------------------------------------------------------------------------
// Context layout, requirement, creation.
// ------------------------------------------------------------------------------------------------
void tuning_defaults(void *ctx) {
    const std::int32_t vi = version_index(effective_version_string(), state().compiled_sdk_version);
    std::uint8_t *t = bp(ctx) + cx::kTuning;
    if (vi == 1) {
        st<std::int32_t>(t, 0x00, 0);
        st<float>(t, 0x04, 0.0f);
        st<float>(t, 0x08, 0.0f);
        st<std::int32_t>(t, 0x0c, 15);
    } else {
        st<std::int32_t>(t, 0x00, 1);
        st<float>(t, 0x04, 0.1f);
        st<float>(t, 0x08, 0.05f);
        st<std::int32_t>(t, 0x0c, 3);
    }
    st<float>(t, 0x10, 0.1f);
    st<float>(t, 0x14, 0.1f);
    st<float>(t, 0x18, 0.03f);
    st<float>(t, 0x1c, 0.03f);
    st<float>(t, 0x20, 0.0f);
}

void init_label(void *label, const void *config, std::uint64_t weights) {
    if (config != nullptr) {
        std::memcpy(label, config, kLabelSize);
    }
    const std::uint64_t old = ld<std::uint64_t>(label, 0x20);
    st<std::uint64_t>(label, 0x20, (old & 0xffff000000000000ull) | (weights & 0xffffffffffffull));
    const std::uint32_t v = ld<std::uint32_t>(label, 0xb4);
    if (v < 1 || v > 300) {
        st<std::uint32_t>(label, 0xb4, 70);
    }
    st<float>(label, 0x0c, 1.0f);
    flush_cpu_lines(label, kLabelSize);
}

void network_sizes(void *ctx, std::uint32_t profile, std::uint32_t w, std::uint32_t h) {
    std::uint32_t gw = w;
    std::uint32_t gh = h;
    if (profile == 2) {
        gw = w / 2;
        gh = h / 2;
    }
    st<std::uint32_t>(ctx, cx::kThird, w / 3);
    st<std::uint32_t>(ctx, cx::kThird + 4, h / 3);
    st<std::uint32_t>(ctx, cx::kNetInput, gw);
    st<std::uint32_t>(ctx, cx::kNetInput + 4, gh);
    st<std::uint32_t>(ctx, cx::kOutput, w);
    st<std::uint32_t>(ctx, cx::kOutput + 4, h);
    st<std::uint32_t>(ctx, cx::kGrid, gw);
    st<std::uint32_t>(ctx, cx::kGrid + 4, gh);
    st<std::uint32_t>(ctx, cx::kGrid2, gw);
    st<std::uint32_t>(ctx, cx::kGrid2 + 4, gh);
}

// Measure (create == false: base 0, unbounded) or allocate (create == true) the context arena.
std::int32_t context_layout(void *ctx, const InitParams &ip, bool create, std::uint64_t base,
                            std::uint64_t limit, std::uint64_t *end_out) {
    const std::uint32_t w = ip.width;
    const std::uint32_t h = ip.height;
    if (ip.profile == 1 && (w != 7680 || h != 4320)) {
        return err::kInvalidParameter;
    }
    network_sizes(ctx, ip.profile, w, h);
    st<std::uint32_t>(ctx, cx::kProfile, ip.profile);
    st<std::uint8_t>(ctx, cx::kOptions, ip.options);
    st<std::uint32_t>(ctx, cx::kFlags, ip.flags);
    const TextureSizeInfo zero{};
    std::memcpy(bp(ctx) + cx::kCapDepth, ip.depth != nullptr ? ip.depth : &zero, 12);
    std::memcpy(bp(ctx) + cx::kCapHistory, ip.history != nullptr ? ip.history : &zero, 12);
    std::memcpy(bp(ctx) + cx::kCapReactive, ip.reactive != nullptr ? ip.reactive : &zero, 12);
    const FsrLutSize zl{};
    std::memcpy(bp(ctx) + cx::kCapLut, ip.lut != nullptr ? ip.lut : &zl, 8);
    Bump a{base, limit};
    auto texture = [&](std::uint32_t off, std::uint32_t tw, std::uint32_t th, std::uint64_t fmt) {
        std::uint64_t al = 0;
        const std::uint64_t size = tex_size(tw, th, fmt, &al);
        const std::uint64_t t = a.take(size, al);
        if (create) {
            if (t != 0) {
                build_texture_desc(bp(ctx) + off, t, tw, th, fmt, 0);
            } else {
                std::memset(bp(ctx) + off, 0, 32);
            }
        }
        return size;
    };
    // 1. Keep copies (history slot 2, depth slot 4, reactive slot 6) and the internal texture.
    struct Keep {
        std::uint8_t bit;
        std::uint32_t off;
        const TextureSizeInfo *tsi;
    };
    const Keep keeps[3] = {{1, cx::kKeepHistory, ip.history},
                           {0, cx::kKeepDepth, ip.depth},
                           {2, cx::kKeepReactive, ip.reactive}};
    for (const Keep &k : keeps) {
        if ((ip.options & (1u << k.bit)) != 0 && k.tsi != nullptr) {
            texture(k.off, k.tsi->width, k.tsi->height, format_for_bpe(k.tsi->bytes_per_element));
        }
    }
    const std::uint32_t gw = ld<std::uint32_t>(ctx, cx::kGrid);
    const std::uint32_t gh = ld<std::uint32_t>(ctx, cx::kGrid + 4);
    std::uint64_t ial = 0;
    const std::uint64_t isize = tex_size(gw, gh, kFmtInternal, &ial);
    st<std::uint64_t>(ctx, cx::kTexBudget, isize);
    st<std::uint64_t>(ctx, cx::kTexAlign, ial);
    texture(cx::kInternal, gw, gh, kFmtInternal);
    // 2. FSR LUT keep copies and working textures. TODO(verify): their sizes.
    if ((ip.options & 8u) != 0 && ip.lut != nullptr) {
        texture(cx::kKeepLutA, ip.lut->horizontal, ip.lut->vertical, kFmtLut);
        texture(cx::kKeepLutB, ip.lut->horizontal, ip.lut->vertical, kFmtLut);
    }
    if ((ip.flags & kKSupportFsr) != 0) {
        texture(cx::kLutWork, static_cast<std::uint32_t>(align_up(w, 64)), 1, kFmtLut);
        texture(cx::kLutWork + 0x20, static_cast<std::uint32_t>(align_up(h, 64)), 1, kFmtLut);
    }
    // 3. SRT A template, 4. eight ring slots.
    const std::uint64_t tmpl = a.take(kSrtASize, 16);
    std::uint64_t rings[8];
    for (std::uint64_t &r : rings) {
        r = a.take(kRingSlotSize, 256);
    }
    if (!create) {
        *end_out = a.cur;
        return 0;
    }
    // 5. Label blocks (create only).
    const std::uint32_t nets = ip.profile == 2 ? 2u : 1u;
    for (std::uint32_t n = 0; n < nets; ++n) {
        for (std::uint32_t i = 0; i < 8; ++i) {
            st<std::uint64_t>(ctx, (n == 0 ? cx::kLabels0 : cx::kLabels1) + 8u * i,
                              a.take(kLabelSize, 256));
        }
    }
    st<std::uint64_t>(ctx, cx::kSrtTemplate, tmpl);
    for (std::uint32_t i = 0; i < 8; ++i) {
        std::uint8_t *slot = bp(ctx) + cx::kRings + 24u * i;
        st<std::uint64_t>(slot, 0, rings[i]);
        st<std::uint64_t>(slot, 8, rings[i]);
        st<std::uint64_t>(slot, 16, rings[i] == 0 ? 0 : rings[i] + kRingSlotSize);
    }
    st<std::uint32_t>(ctx, cx::kMagic, kMagicCreated);
    tuning_defaults(ctx);
    mt_seed(ctx, 0x112233);
    for (std::uint32_t d = 0; d < 2; ++d) {
        const std::uint32_t off = cx::kDist + 0x10u * d;
        st<std::uint64_t>(ctx, off, addr(bp(ctx) + cx::kMt));
        st<float>(ctx, off + 8, -1.0f);
        st<float>(ctx, off + 12, 1.0f);
    }
    *end_out = a.cur;
    return 0;
}

// SRT A template: buffer descriptors over the shared weights and the two RFM textures, texture
// descriptors of the three shared intermediate textures. TODO(verify): placement inside the
// template (ours: V# at +0x00/+0x10/+0x20, T#s at +0x40/+0x60/+0x80).
void fill_srt_template(void *ctx, const void *srp) {
    const std::uint64_t t = ld<std::uint64_t>(ctx, cx::kSrtTemplate);
    if (t == 0) {
        return;
    }
    std::uint8_t *p = ptr(t);
    std::memset(p, 0, kSrtASize);
    const std::uint32_t profile = ld<std::uint32_t>(srp, sr::kProfile);
    const std::uint64_t weights = ld<std::uint64_t>(srp, sr::kEntries + sr::kEWeights);
    // INTEROP TABLE (description, 0x6ab74): the per-profile VA sizes as the descriptor size.
    build_buffer_desc(p + 0x00, weights, static_cast<std::uint32_t>(kProfileVaSize[profile] / 4), 4,
                      true);
    build_buffer_desc(p + 0x10, tdesc_address(bp(ctx) + cx::kRfmA),
                      static_cast<std::uint32_t>(ld<std::uint64_t>(ctx, cx::kRfmMapA + 8) / 4), 4,
                      true);
    build_buffer_desc(p + 0x20, tdesc_address(bp(ctx) + cx::kRfmB),
                      static_cast<std::uint32_t>(ld<std::uint64_t>(ctx, cx::kRfmMapB + 8) / 4), 4,
                      true);
    for (std::uint32_t i = 0; i < 3; ++i) {
        std::memcpy(p + 0x40 + 0x20 * i,
                    static_cast<const std::uint8_t *>(srp) + sr::kTex + 0x20 * i, 32);
    }
}

std::uint64_t rfm_texture_size(std::uint32_t gw, std::uint32_t gh) {
    std::uint64_t a = 0;
    return tex_size(gw, gh + 8, kFmtRfm, &a);
}

// Returns the core status; *rfm_blocks is computed in every case (callers add it unconditionally).
std::int32_t context_requirement_core(MemoryRequirement *out, const InitParams &ip,
                                      std::uint64_t *rfm_blocks) {
    const std::uint32_t gw = ip.profile == 2 ? ip.width / 2u : ip.width;
    const std::uint32_t gh = ip.profile == 2 ? ip.height / 2u : ip.height;
    *rfm_blocks = 2 * ((rfm_texture_size(gw, gh) + k2M - 1) / k2M);
    if (out == nullptr) {
        return err::kNullPointer;
    }
    *out = {};
    if (!profile_allowed(ip.profile)) {
        return err::kInvalidParameter;
    }
    std::vector<std::uint8_t> scratch(kCtxObjectSize, 0);
    std::uint64_t end = 0;
    const std::int32_t r = context_layout(scratch.data(), ip, false, 0, ~std::uint64_t{0}, &end);
    if (r != 0) {
        return r;
    }
    *out = {k2M, k2M, (end + k2M - 1) / k2M};
    return 0;
}

void tsi_from_template(TextureSizeInfo *out, const void *tex) {
    *out = {};
    const std::uint32_t bpe = bytes_per_element(tdesc_format(tex));
    if (bpe == 0) {
        return;
    }
    std::uint32_t l = 0;
    while ((2u << l) <= bpe) {
        ++l;
    }
    *out = {1u << l, tdesc_width(tex), tdesc_height(tex)};
}

InitParams params_from_v1(const ContextInitParametersV1 *p, bool with_shared) {
    InitParams ip;
    ip.profile = p->profile;
    ip.unused = p->unused;
    ip.blocks = p->blocks;
    ip.block_count = p->block_count;
    ip.width = p->output_width;
    ip.height = p->output_height;
    if (with_shared) {
        ip.caller_shared = p->shared_resources;
    }
    if (p->depth_keep_template != nullptr) {
        tsi_from_template(&ip.conv[0], p->depth_keep_template);
        ip.depth = &ip.conv[0];
        ip.options |= 1;
    }
    if (p->history_keep_template != nullptr) {
        tsi_from_template(&ip.conv[1], p->history_keep_template);
        ip.history = &ip.conv[1];
        ip.options |= 2;
    }
    return ip;
}

InitParams params_from_v2(const ContextInitParametersV2 *p, bool reactive_aware, bool with_shared) {
    InitParams ip;
    ip.profile = p->profile;
    ip.unused = p->unused;
    ip.blocks = p->blocks;
    ip.block_count = p->block_count;
    ip.width = p->output_width;
    ip.height = p->output_height;
    ip.flags = p->flags;
    ip.depth = p->depth_keep_size;
    ip.history = p->history_keep_size;
    ip.reactive = p->reactive_keep_size;
    if (with_shared) {
        ip.caller_shared = p->shared_resources;
    }
    if (p->depth_keep_size != nullptr) {
        ip.options |= 1;
    }
    if (p->history_keep_size != nullptr) {
        ip.options |= 2;
    }
    if (reactive_aware && p->reactive_keep_size != nullptr) {
        ip.options |= 4;
    }
    if ((p->flags & 1u) != 0) {
        ip.lut = p->max_size_fsr_lut_for_keep_copy;
        if (ip.lut != nullptr) {
            ip.options |= 8;
        }
    }
    return ip;
}

InitParams params_simple(const SimpleInitParameters *p) {
    ModuleState &s = state();
    s.simple_history_size = {4, 3840, 2160};
    InitParams ip;
    ip.profile = p->profile == 1 ? 1u : 0u;
    ip.width = ip.profile == 1 ? 7680 : 3840;
    ip.height = ip.profile == 1 ? 4320 : 2160;
    ip.blocks = p->blocks;
    ip.block_count = p->block_count;
    ip.options = 2;
    ip.history = &s.simple_history_size;
    return ip;
}

std::int32_t context_map_and_init(void **out, const InitParams &ip, void *srp,
                                  std::uint64_t ctx_blocks, std::uint64_t rfm_blocks) {
    if (ip.profile != ld<std::uint32_t>(srp, sr::kProfile)) {
        return err::kProfileMismatch;
    }
    int slot = -1;
    for (int i = 0; i < 4; ++i) {
        if (ld<std::uint64_t>(srp, sr::kSlots + 0x18u * static_cast<unsigned>(i)) == 0) {
            slot = i;
            break;
        }
    }
    if (slot < 0) {
        return err::kTooManyContexts;
    }
    std::uint8_t *slotp = bp(srp) + sr::kSlots + 0x18u * static_cast<unsigned>(slot);
    const std::uint64_t rfm_window = ld<std::uint64_t>(slotp, 8);
    const std::uint64_t mem_window = ld<std::uint64_t>(slotp, 16);
    MappingList list;
    const std::uint64_t size = ctx_blocks * k2M;
    if (list.add_range(mem_window, size) != 0) {
        return -1;
    }
    std::int32_t r = list.map_all(ip.blocks, ctx_blocks, "ScePsmlMfsrContext");
    if (r != 0) {
        list.undo();
        return r;
    }
    void *ctx = ptr<void>(mem_window + size - kCtxTail);
    std::memset(ctx, 0, kCtxObjectSize);
    st<std::uint64_t>(ctx, cx::kMap, mem_window);
    st<std::uint64_t>(ctx, cx::kMap + 8, size);
    std::uint64_t end = 0;
    r = context_layout(ctx, ip, true, mem_window, mem_window + size - kCtxTail, &end);
    if (r != 0) {
        list.undo();
        return r;
    }
    // Output RFM areas: the next rfm_blocks caller blocks, second area at +32 MiB (+128 MiB p1).
    const std::uint64_t half = rfm_blocks / 2 * k2M;
    const std::uint64_t second = rfm_window + (ip.profile == 1 ? 0x8000000ull : 0x2000000ull);
    MappingList rfm;
    if (rfm.add_range(rfm_window, half) != 0 || rfm.add_range(second, half) != 0 ||
        (r = rfm.map_all(ip.blocks + ctx_blocks, ip.block_count - ctx_blocks,
                         "ScePsmlMfsrContextOutputRfm")) != 0) {
        log(kModuleName, "[PSML] Failed to map output RFM (%x)", static_cast<std::uint32_t>(r));
        rfm.undo();
        list.undo();
        return r != 0 ? r : -1;
    }
    const std::uint32_t gw = ld<std::uint32_t>(ctx, cx::kGrid);
    const std::uint32_t gh = ld<std::uint32_t>(ctx, cx::kGrid + 4);
    build_texture_desc(bp(ctx) + cx::kRfmA, rfm_window, gw, gh + 8, kFmtRfm, 0);
    build_texture_desc(bp(ctx) + cx::kRfmB, second, gw, gh + 8, kFmtRfm, 0);
    st<std::uint64_t>(ctx, cx::kRfmMapA, rfm_window);
    st<std::uint64_t>(ctx, cx::kRfmMapA + 8, half);
    st<std::uint64_t>(ctx, cx::kRfmMapB, second);
    st<std::uint64_t>(ctx, cx::kRfmMapB + 8, half);
    st<std::uint64_t>(ctx, cx::kShared, addr(srp));
    fill_srt_template(ctx, srp);
    // Per-ring label blocks from the shared configuration blocks.
    const std::uint32_t nets = ip.profile == 2 ? 2u : 1u;
    for (std::uint32_t n = 0; n < nets; ++n) {
        const std::uint64_t cfg = ld<std::uint64_t>(srp, n == 0 ? sr::kConfigA : sr::kConfigB);
        const std::uint64_t weights =
            ld<std::uint64_t>(srp, sr::kEntries + 0x28u * n + sr::kEWeights);
        for (std::uint32_t i = 0; i < 8; ++i) {
            const std::uint64_t lab =
                ld<std::uint64_t>(ctx, (n == 0 ? cx::kLabels0 : cx::kLabels1) + 8u * i);
            if (lab != 0) {
                init_label(ptr<void>(lab), ptr<void>(cfg), weights);
            }
        }
    }
    st<std::uint64_t>(slotp, 0, addr(ctx));
    *out = ctx;
    return 0;
}

std::int32_t context_create_core(void **out, const InitParams &ip) {
    ModuleState &s = state();
    if (s.initialised != 1) {
        return err::kNotInitialized;
    }
    if (ip.blocks == nullptr) {
        return err::kNullPointer;
    }
    *out = nullptr;
    if (ip.width < 960 || ip.height < 540) {
        return err::kOutputTooSmall;
    }
    if (ip.caller_shared == nullptr && ip.owned_shared == nullptr) {
        log(kModuleName, "[PSML] MfsrContextInitParameters shared resources must be given");
        return err::kSharedResourcesArg;
    }
    if (ip.caller_shared != nullptr && ip.owned_shared != nullptr) {
        log(kModuleName, "[PSML] either of the shared resources must be nullptr");
        return err::kSharedResourcesArg;
    }
    MemoryRequirement req{};
    std::uint64_t rfm = 0;
    std::int32_t r = context_requirement_core(&req, ip, &rfm);
    if (r != 0) {
        return r;
    }
    if (req.block_count + rfm > ip.block_count) {
        return err::kNotEnoughMemory;
    }
    const std::int32_t index = s.context_count.fetch_add(1);
    if (index >= 4) {
        s.context_count.fetch_sub(1);
        return err::kTooManyContexts;
    }
    void *srp = ip.caller_shared != nullptr ? ip.caller_shared : ip.owned_shared;
    void *ctx = nullptr;
    r = context_map_and_init(&ctx, ip, srp, req.block_count, rfm);
    if (r != 0) {
        s.context_count.fetch_sub(1);
        return r;
    }
    st<std::uint8_t>(ctx, cx::kSlot, static_cast<std::uint8_t>(index));
    st<std::uint8_t>(ctx, cx::kOwned, ip.owned_shared != nullptr ? 1 : 0);
    *out = ctx;
    return 0;
}

// ContextUnslot: clear the slot(s) holding the context and unmap its memory. Always returns
// kBadContext, which the caller ignores (quirk of the original).
std::int32_t context_unslot(void *ctx, void *srp) {
    const std::uint64_t a = ld<std::uint64_t>(ctx, cx::kRfmMapA);
    const std::uint64_t as = ld<std::uint64_t>(ctx, cx::kRfmMapA + 8);
    const std::uint64_t b = ld<std::uint64_t>(ctx, cx::kRfmMapB);
    const std::uint64_t bs = ld<std::uint64_t>(ctx, cx::kRfmMapB + 8);
    const std::uint64_t m = ld<std::uint64_t>(ctx, cx::kMap);
    const std::uint64_t ms = ld<std::uint64_t>(ctx, cx::kMap + 8);
    for (std::uint32_t i = 0; i < 4; ++i) {
        if (ld<std::uint64_t>(srp, sr::kSlots + 0x18u * i) == addr(ctx)) {
            st<std::uint64_t>(srp, sr::kSlots + 0x18u * i, 0);
            unmap(a, as);
            unmap(b, bs);
            unmap(m, ms);
        }
    }
    return err::kBadContext;
}

// ------------------------------------------------------------------------------------------------
// Dispatch.
// ------------------------------------------------------------------------------------------------
constexpr std::uint32_t kParamsSize = 0x1b0;
using Params = std::uint8_t[kParamsSize];

const void *slot_tex(const Params &p, std::uint32_t slot) { return ld<const void *>(p, 8u * slot); }

std::uint64_t ring_take(void *ctx, std::uint64_t size, std::uint64_t align) {
    const std::uint32_t ring = ld<std::uint8_t>(ctx, cx::kRing);
    std::uint8_t *slot = bp(ctx) + cx::kRings + 24u * ring;
    const std::uint64_t cur = ld<std::uint64_t>(slot, 8);
    const std::uint64_t end = ld<std::uint64_t>(slot, 16);
    if (cur == 0) {
        return 0;
    }
    const std::uint64_t p = align_up(cur, align);
    if (p + size > end) {
        return 0;
    }
    st<std::uint64_t>(slot, 8, p + size);
    return p;
}

bool is_2d(const void *t) { return t != nullptr && (ld<std::uint32_t>(t, 12) >> 28) == 9; }

std::int32_t strict_validation(const void *ctx, const Params &p) {
    for (std::uint32_t s : {0u, 1u, 2u, 4u}) {
        if (slot_tex(p, s) == nullptr) {
            return err::kMissingTexture;
        }
    }
    const std::uint8_t options = ld<std::uint8_t>(ctx, cx::kOptions);
    const bool reset = p[0x11c] != 0;
    const void *aux = ld<const void *>(p, 0x128);
    bool ok = ld<std::uint64_t>(p, 0x48) == 0 && ld<std::uint64_t>(p, 0x50) == 0 && p[0x11d] == 0 &&
              p[0x11e] == 0 && p[0x11f] == 0 && ld<std::uint32_t>(p, 0x130) == 0 &&
              ld<float>(p, 0x138) == 1.0f && ld<float>(p, 0x13c) == 1.0f &&
              ld<float>(p, 0x140) == 1.0f && ld<float>(p, 0x150) == 0.0f &&
              ld<float>(p, 0x154) == 0.0f;
    if (ok && !reset) {
        ok = ((options & 1u) != 0 || slot_tex(p, 3) != nullptr) &&
             ((options & 2u) != 0 || slot_tex(p, 7) != nullptr);
    }
    const std::uint32_t bits = ld<std::uint32_t>(ctx, cx::kFrameBits);
    if (ok && (bits & 2u) != 0) {
        ok = ((bits & 1u) != 0) == (aux != nullptr);
    }
    if (ok && aux != nullptr) {
        ok = (ld<std::uint32_t>(ctx, cx::kFlags) & kKSupportFsr) != 0 && is_2d(aux) &&
             is_2d(static_cast<const std::uint8_t *>(aux) + 0x50);
        if (ok && !reset && (options & 8u) == 0) {
            ok = is_2d(static_cast<const std::uint8_t *>(aux) + 0xa0);
        }
        if (ok) {
            ok = ld<std::uint32_t>(aux, 0xa8) < 2;
            for (std::uint32_t o = 0xac; ok && o < 0xf0; o += 4) {
                ok = ld<std::uint32_t>(aux, o) == 0;
            }
        }
    }
    return ok ? 0 : err::kInvalidParameter;
}

std::uint32_t power_value(std::uint32_t profile, std::uint32_t w, std::uint32_t h) {
    ModuleState &s = state();
    if (profile == 1 || profile == 2) {
        return 0;
    }
    const double f = static_cast<double>(w) * static_cast<double>(h) / 8294400.0;
    s.power_buckets[s.power_bucket_index & 7].fetch_add(static_cast<std::int32_t>(f * 1900.0));
    return s.timer_ticks > 35 ? static_cast<std::uint32_t>(f * 800.0) : 0u;
}

void builtin_pass(AgcCommandBuffer &cb, const void *shader, const void *ud, std::uint32_t dwords,
                  std::uint32_t x, std::uint32_t y, std::uint32_t z) {
    set_shader_registers_direct(cb, shader);
    write_user_data(cb, shader, ud, dwords);
    dispatch_if_enabled(cb, shader, x, y, z);
}

void *shader_at(std::uint32_t slot) { return state().group_a[slot_index(slot)]; }

std::uint32_t remap_keep_format(std::uint32_t src_fmt) {
    // Format remap table (module data at 0x6ac00, 0x28 bytes) read from the maintainer's module
    // file. TODO(verify): we index it by log2(bytes per element), 8 bytes per entry.
    const std::uint32_t bpe = bytes_per_element(src_fmt);
    // libScePsml keeps reading its module file here: this data is only reached past its PS5 Pro
    // gate, so BC5 never needs it (BC5_REIMPL_FW_DATA does not apply to libScePsml).
    FirmwareData *fd = firmware_data();
    const std::uint8_t *t = fd != nullptr ? fd->get(kModuleName, 0x6ac00, 0x28) : nullptr;
    if (t == nullptr || bpe == 0) {
        return src_fmt;
    }
    std::uint32_t l = 0;
    while ((2u << l) <= bpe && l < 4) {
        ++l;
    }
    return ld<std::uint32_t>(t, 8u * l) & 0x1ffu;
}

std::int32_t copy_texture(AgcCommandBuffer &cb, void *ctx, const void *src, std::uint32_t dst_off,
                          std::uint32_t cap_off, const Params &p) {
    if (src == nullptr) {
        return 0;
    }
    const std::uint32_t rw = ld<std::uint32_t>(p, 0xf0);
    const std::uint32_t rh = ld<std::uint32_t>(p, 0xf4);
    const std::uint32_t cap_bpe = ld<std::uint32_t>(ctx, cap_off);
    if (rw > ld<std::uint32_t>(ctx, cap_off + 4) || rh > ld<std::uint32_t>(ctx, cap_off + 8)) {
        return err::kNotEnoughMemory;
    }
    if (bytes_per_element(tdesc_format(src)) > cap_bpe) {
        return err::kKeepCopyTooLarge;
    }
    void *dst = bp(ctx) + dst_off;
    tdesc_set_size(dst, rw, rh);
    tdesc_set_format(dst, remap_keep_format(tdesc_format(src)));
    Imports &im = import_table();
    if (im.agc_dcb_push_marker != nullptr) {
        im.agc_dcb_push_marker(&cb, "Copy Texture", 0);
    }
    const std::uint64_t srt = ring_take(ctx, 0x48, 16);
    if (srt == 0) {
        return err::kScratchAllocFailed;
    }
    std::memcpy(ptr(srt), dst, 32);
    std::memcpy(ptr(srt + 32), src, 32);
    st<std::uint32_t>(ptr(srt), 64, ld<std::uint32_t>(p, 0xf8));
    st<std::uint32_t>(ptr(srt), 68, ld<std::uint32_t>(p, 0xfc));
    const std::uint32_t ud[2] = {static_cast<std::uint32_t>(srt),
                                 static_cast<std::uint32_t>(srt >> 32)};
    builtin_pass(cb, shader_at(kShCopy), ud, 2, tdesc_width(dst), tdesc_height(dst), 1);
    if (im.agc_dcb_pop_marker != nullptr) {
        im.agc_dcb_pop_marker(&cb);
    }
    return 0;
}

std::int32_t main_builder(AgcCommandBuffer &cb, void *ctx, const Params &p) {
    ModuleState &s = state();
    Imports &im = import_table();
    // 1. Strict validation.
    if (p[0x1a4] != 0) {
        const std::int32_t r = strict_validation(ctx, p);
        if (r != 0) {
            return r;
        }
    }
    void *srp = ptr<void>(ld<std::uint64_t>(ctx, cx::kShared));
    const std::uint32_t profile = ld<std::uint32_t>(ctx, cx::kProfile);
    const std::uint32_t ring = ld<std::uint8_t>(ctx, cx::kRing);
    const std::uint32_t gw = ld<std::uint32_t>(ctx, cx::kGrid);
    const std::uint32_t gh = ld<std::uint32_t>(ctx, cx::kGrid + 4);
    const std::uint32_t ow = ld<std::uint32_t>(ctx, cx::kOutput);
    const std::uint32_t oh = ld<std::uint32_t>(ctx, cx::kOutput + 4);
    const std::uint32_t rw = ld<std::uint32_t>(p, 0xf0);
    const std::uint32_t rh = ld<std::uint32_t>(p, 0xf4);
    const std::uint32_t flags = ld<std::uint32_t>(p, 0x120);
    const void *aux = ld<const void *>(p, 0x128);
    // 2. Resize the internal texture to the network grid.
    void *internal = bp(ctx) + cx::kInternal;
    if (tdesc_width(internal) != gw || tdesc_height(internal) != gh) {
        std::uint64_t al = 0;
        const std::uint64_t size = tex_size(gw, gh, kFmtInternal, &al);
        if (size > ld<std::uint64_t>(ctx, cx::kTexBudget) ||
            al > ld<std::uint64_t>(ctx, cx::kTexAlign)) {
            return -1;
        }
        tdesc_set_size(internal, gw, gh);
    }
    // 3. First dispatch / reload request.
    bool reset = p[0x11c] != 0;
    if (ld<std::uint8_t>(ctx, cx::kReload) == 1) {
        st<std::uint8_t>(ctx, cx::kReload, 0);
        tuning_defaults(ctx); // re-apply the default configuration
        reset = true;
    }
    if (ld<std::uint32_t>(ctx, cx::kMagic) == kMagicCreated) {
        reset = true;
        st<std::uint32_t>(ctx, cx::kMagic, kMagicDispatched);
    }
    const std::uint8_t *entry0 = static_cast<const std::uint8_t *>(srp) + sr::kEntries;
    // 4. Capture packets and the prepare pass, only when there is room.
    const std::uint32_t cap_bytes = aux != nullptr ? 0x248u : 0x158u;
    const std::uint32_t ud_size = im.driver_user_data_get_packet_size != nullptr
                                      ? im.driver_user_data_get_packet_size(0)
                                      : 3u;
    const std::uint32_t data_size =
        im.driver_data_packet_size != nullptr ? im.driver_data_packet_size(cap_bytes) : 0u;
    if (im.driver_user_data_write_packet != nullptr && im.driver_write_data_packet != nullptr &&
        cb_free_dwords(cb) >= ud_size + data_size) {
        cb.cursor += im.driver_user_data_write_packet(cb.cursor, 0, 0xd2000001u, nullptr, 0);
        std::vector<std::uint8_t> copy(cap_bytes, 0);
        std::memcpy(copy.data(), p, 0x158);
        if (aux != nullptr) {
            std::memcpy(copy.data() + 0x158, aux, 0xf0);
        }
        std::uint32_t *pkt = cb.cursor;
        im.driver_write_data_packet(pkt, 0x56000003u, copy.data(), cap_bytes);
        cb.cursor += data_size;
        void *payload = pkt + 1;
        if (im.agc_get_nop_payload != nullptr) {
            im.agc_get_nop_payload(&payload, pkt, 0);
        }
        if (payload != nullptr) {
            // Payload (from the tag dword) +0x12c: the copied aux pointer, aimed at the copy.
            st<std::uint64_t>(payload, 0x12c, addr(bp(payload) + 0x15c));
        }
        const std::uint64_t srt = ring_take(ctx, kSrtASize, 16);
        if (srt != 0) {
            std::uint8_t *a = ptr(srt);
            const std::uint64_t tmpl = ld<std::uint64_t>(ctx, cx::kSrtTemplate);
            if (tmpl != 0) {
                std::memcpy(a, ptr(tmpl), kSrtASize);
            }
            constexpr std::uint32_t kOrder[9] = {0, 1, 2, 7, 3, 4, 5, 6, 8};
            for (std::uint32_t i = 0; i < 9; ++i) {
                const void *t = slot_tex(p, kOrder[i]);
                if (t != nullptr) {
                    std::memcpy(a + 0x100 + 0x20 * i, t, 32);
                } else {
                    std::memset(a + 0x100 + 0x20 * i, 0, 32);
                }
            }
            constexpr std::uint32_t kAux[5] = {0x00, 0x20, 0x50, 0x70, 0xa0};
            for (std::uint32_t i = 0; i < 5; ++i) {
                if (aux != nullptr) {
                    std::memcpy(a + 0x220 + 0x20 * i,
                                static_cast<const std::uint8_t *>(aux) + kAux[i], 32);
                } else {
                    std::memset(a + 0x220 + 0x20 * i, 0, 32);
                }
            }
            const std::uint32_t power = power_value(profile, ow, oh);
            st<std::uint32_t>(a, 0x2e0, power);
            const std::uint64_t w0 = ld<std::uint64_t>(entry0, sr::kEWeights);
            const std::uint32_t ws0 = ld<std::uint32_t>(srp, sr::kWeightsSize);
            build_buffer_desc(a + 0x2c0, w0, ws0 / 4, 4, true);
            if (profile == 2) {
                build_buffer_desc(a + 0x2d0, ld<std::uint64_t>(entry0 + 0x28, sr::kEWeights),
                                  ld<std::uint32_t>(srp, sr::kWeightsSize + 4) / 4, 4, true);
            } else {
                std::memcpy(a + 0x2d0, a + 0x2c0, 16);
            }
            const std::uint32_t ud[2] = {static_cast<std::uint32_t>(srt),
                                         static_cast<std::uint32_t>(srt >> 32)};
            builtin_pass(cb, shader_at(kShPrepare), ud, 2, 1, 1, 1);
            if (power != 0) {
                barrier(cb, 0);
            }
        }
    }
    // 5. Network bracket open.
    if (cb_raw2(cb, 0xc0007000u, 0) != 0) {
        return err::kNoRoomForPacket;
    }
    // 6. FSR LUT passes.
    const std::uint32_t mflags = ld<std::uint32_t>(ctx, cx::kFlags);
    if ((mflags & kKSupportFsr) != 0 && aux != nullptr) {
        void *srt = embed_scratch(cb, 0xdf * 4 - 4, 4);
        if (srt == nullptr) {
            return err::kScratchAllocFailed;
        }
        std::memset(srt, 0, 0x378);
        std::memcpy(srt, bp(ctx) + cx::kLutWork, 0x40);
        st<std::uint32_t>(srt, 0x40, ow);
        st<std::uint32_t>(srt, 0x44, oh);
        std::memcpy(bp(srt) + 0x48, p + 0x100, 8);
        std::memcpy(bp(srt) + 0x50, static_cast<const std::uint8_t *>(aux) + 0x40, 16);
        std::memcpy(bp(srt) + 0x60, static_cast<const std::uint8_t *>(aux) + 0x90, 16);
        const std::uint32_t ud[2] = {static_cast<std::uint32_t>(addr(srt)),
                                     static_cast<std::uint32_t>(addr(srt) >> 32)};
        builtin_pass(cb, shader_at(kShLutH), ud, 2, (ow + 63) & ~63u, 1, 1);
        builtin_pass(cb, shader_at(kShLutV), ud, 2, (oh + 63) & ~63u, 1, 1);
    }
    // 7. Optional pre-pass (flags bit 16).
    if ((flags & (1u << 16)) != 0) {
        void *srt = embed_scratch(cb, 0xf * 4, 4);
        const std::uint64_t scratch8 = ring_take(ctx, 8, 8);
        if (srt == nullptr || scratch8 == 0) {
            return err::kScratchAllocFailed;
        }
        std::memset(srt, 0, 0xf * 4);
        if (slot_tex(p, 1) != nullptr) {
            std::memcpy(srt, slot_tex(p, 1), 32);
        }
        build_typed_buffer_desc(bp(srt) + 32, scratch8, kFmtScratch8, 8);
        std::memcpy(bp(srt) + 48, p + 0xf8, 8);
        const std::uint32_t ud[2] = {static_cast<std::uint32_t>(addr(srt)),
                                     static_cast<std::uint32_t>(addr(srt) >> 32)};
        builtin_pass(cb, shader_at(kShPrePass), ud, 2, rw, rh, 1);
        barrier(cb, 0x13);
    }
    // 8. SRT B for the main kernel. Offsets given by the description: sub-blocks at +0x1b8,
    // +0x288, +0x410, +0x414, +0x6f4, +0x734. TODO(verify): every other placement is ours, and
    // the fixed constant tables at +0x88..+0xbf / +0xe8..+0x127 are left zero (not described).
    const std::uint64_t srtb = ring_take(ctx, kSrtBSize, 16);
    void *hdr34 = embed_scratch(cb, 0x34 * 4, 4);
    if (srtb == 0 || hdr34 == nullptr) {
        return err::kScratchAllocFailed;
    }
    std::uint8_t *b = ptr(srtb);
    std::memset(b, 0, kSrtBSize);
    std::memset(hdr34, 0, 0x34 * 4);
    const bool sharpen = s.sharpening_permitted != 0 && ld<float>(p, 0x144) > 0.0f;
    const float sharpness = s.sharpening_permitted != 0 ? ld<float>(p, 0x144) : 0.0f;
    if (slot_tex(p, 1) != nullptr) {
        std::memcpy(b + 0x000, slot_tex(p, 1), 32);
    }
    std::memcpy(b + 0x020, internal, 32);
    st<std::uint64_t>(b, 0x040, 0x0fff000000000092ull);
    st<std::uint32_t>(b, 0x048, 0x05000000u);
    st<std::uint32_t>(b, 0x04c, 0x05500000u);
    const float fow = static_cast<float>(ow);
    const float foh = static_cast<float>(oh);
    const float frw = rw != 0 ? static_cast<float>(rw) : 1.0f;
    const float frh = rh != 0 ? static_cast<float>(rh) : 1.0f;
    const float sizes[8] = {fow, foh, 1.0f / fow, 1.0f / foh, frw, frh, 1.0f / frw, 1.0f / frh};
    std::memcpy(b + 0x050, sizes, sizeof sizes);
    std::memcpy(b + 0x070, p + 0x100, 8);
    st<float>(b, 0x078, frw / fow);
    st<float>(b, 0x07c, frh / foh);
    st<float>(b, 0x080, static_cast<float>(ld<std::uint32_t>(p, 0xf8)) + ld<float>(p, 0x100));
    st<float>(b, 0x084, static_cast<float>(ld<std::uint32_t>(p, 0xfc)) + ld<float>(p, 0x104));
    const float ratio = fow / frw;
    std::uint32_t mips = static_cast<std::uint32_t>(std::lround(7.0f * ratio + 1e-6f + 2.0f));
    if (sharpen) {
        mips = static_cast<std::uint32_t>(std::lround(7.0f * ratio + 1e-6f + 3.0f));
        mips = mips > 10 ? 10 : mips;
    } else {
        mips = mips > 9 ? 9 : mips;
    }
    st<std::uint32_t>(b, 0x0c0, mips);
    st<std::uint32_t>(b, 0x0c4, mips);
    st<float>(b, 0x0c8, ld<float>(p, 0x108) / frw);
    st<float>(b, 0x0cc, ld<float>(p, 0x10c) / frh);
    st<float>(b, 0x0d0, ld<float>(p, 0x110) / frw);
    st<float>(b, 0x0d4, ld<float>(p, 0x114) / frh);
    const float gamma = ld<float>(p, 0x118);
    const bool no_gamma = gamma == 0.0f || gamma == 1.0f;
    st<float>(b, 0x0d8, no_gamma ? 1.0f : 1.0f / gamma);
    const void *mv = slot_tex(p, 2);
    if (mv != nullptr) {
        std::memcpy(b + 0x128, mv, 32);
        if (reset) {
            st<std::uint32_t>(b, 0x128 + 0x0c, ld<std::uint32_t>(b, 0x128 + 0x0c) & 0xf000u);
        }
    }
    const void *prev_mv = (ld<std::uint8_t>(ctx, cx::kOptions) & 2u) != 0
                              ? bp(ctx) + cx::kKeepHistory
                              : slot_tex(p, 7);
    if (prev_mv != nullptr) {
        std::memcpy(b + 0x148, prev_mv, 32);
    }
    if (slot_tex(p, 4) != nullptr) {
        std::memcpy(b + 0x168, slot_tex(p, 4), 32);
    }
    // Sub-block at +0x1b8: reactive (slot 6), slot 8, render rect, jitter, 0x134/0x148 floats.
    if ((flags & (1u << 17)) != 0 && slot_tex(p, 6) != nullptr) {
        std::memcpy(b + 0x1b8, slot_tex(p, 6), 32);
    }
    if (slot_tex(p, 8) != nullptr) {
        std::memcpy(b + 0x1d8, slot_tex(p, 8), 32);
    }
    std::memcpy(b + 0x1f8, p + 0xf8, 8);
    std::memcpy(b + 0x200, p + 0xf0, 8);
    std::memcpy(b + 0x208, p + 0x100, 8);
    std::memcpy(b + 0x210, p + 0x134, 4);
    std::memcpy(b + 0x214, p + 0x148, 4);
    // Sub-block at +0x288: tuning/config from ctx+0x88..0x120, the random distributions, the
    // tuning block and the network entry.
    std::memcpy(b + 0x288, bp(ctx) + 0x88, 0x98);
    std::memcpy(b + 0x320, bp(ctx) + cx::kTuning, 0x24);
    st<float>(b, 0x344, uniform(ctx, cx::kDist));
    st<float>(b, 0x348, uniform(ctx, cx::kDist + 0x10));
    st<std::uint32_t>(b, 0x34c, ld<std::uint8_t>(srp, sr::kVariant));
    // +0x410: the package override value; +0x414: camera reprojection.
    const float override_value = ld<float>(srp, sr::kOverride);
    std::uint32_t e = aux != nullptr ? 1u : 0u;
    if (override_value > 0.0f) {
        e = 2;
        st<float>(b, 0x410, override_value);
    }
    float dp[4];
    depth_params(dp, ld<float>(p, 0xe8), ld<float>(p, 0xec), (flags & (1u << 15)) != 0);
    std::memcpy(b + 0x414, dp, 16);
    const bool explicit_matrix = p[0x15c] != 0;
    const float m15 = explicit_matrix ? ld<float>(p, 0x164 + 60) : ld<float>(p, 0xa8);
    st<std::uint32_t>(b, 0x424, m15 < 1.0f ? 1u : 0u);
    float tan_half_fov = 0.0f;
    if (explicit_matrix) {
        tan_half_fov = std::tan((3.14159265f / 4.0f) / (fow / foh));
    } else {
        const float m5 = ld<float>(p, 0x6c + 20);
        tan_half_fov = m5 != 0.0f ? 1.0f / m5 : 0.0f;
    }
    st<float>(b, 0x428, tan_half_fov);
    std::memcpy(b + 0x430, bp(ctx) + cx::kPrevCamera, 0x78);
    std::memcpy(bp(ctx) + cx::kPrevCamera, p + 0x6c, 0x78);
    // +0x6f4: the 64-byte network constant block with the sharpness at +0x3c; +0x734: FSR.
    const std::uint64_t cblock = ld<std::uint64_t>(srp, sr::kConstBlock);
    if (cblock != 0) {
        std::memcpy(b + 0x6f4, ptr(cblock), 0x40);
    }
    st<float>(b, 0x6f4 + 0x3c, sharpness);
    if (aux != nullptr) {
        std::memcpy(b + 0x734, static_cast<const std::uint8_t *>(aux) + 0x40, 16);
        std::memcpy(b + 0x744, static_cast<const std::uint8_t *>(aux) + 0x90, 16);
        st<std::uint32_t>(b, 0x754, ld<std::uint32_t>(aux, 0xa8) & 1u);
    }
    std::uint32_t option = (mips & 0xfu) << 16;
    option |= slot_tex(p, 5) != nullptr ? 1u : 0u;
    option |= (flags & (1u << 17)) != 0 ? 2u : 0u;
    option |= slot_tex(p, 8) != nullptr ? 4u : 0u;
    option |= aux != nullptr ? 8u : 0u;
    option |= no_gamma ? (1u << 7) : 0u;
    option |= (ld<float>(p, 0x110) == 0.0f && ld<float>(p, 0x114) == 0.0f) ? (1u << 8) : 0u;
    option |= sharpen ? (1u << 9) : 0u;
    // 9. Exposure pass.
    const std::uint64_t exp_scratch = ring_take(ctx, 5 * 4, 16);
    const std::uint64_t exp_srt = ring_take(ctx, 0x13 * 4, 16);
    if (exp_scratch == 0 || exp_srt == 0) {
        return err::kScratchAllocFailed;
    }
    st<std::uint64_t>(ctx, cx::kExposureScratch, exp_scratch);
    std::memset(ptr(exp_scratch), 0, 20);
    std::memset(ptr(exp_srt), 0, 0x13 * 4);
    const std::uint64_t label0 = ld<std::uint64_t>(ctx, cx::kLabels0 + 8u * ring);
    if (slot_tex(p, 5) != nullptr) {
        std::memcpy(ptr(exp_srt), slot_tex(p, 5), 32);
        st<float>(ptr(exp_srt), 32, -1.0f);
    } else {
        float ev = (1.0f / ld<float>(p, 0x64)) * ld<float>(p, 0x68) * 1e-4f;
        if (!std::isfinite(ev) || ev < 0.0f) {
            ev = 0.0f;
        }
        if (ev < 0x1p-40f) {
            ev = 0x1p-40f;
        }
        st<float>(srp, sr::kExposure, ev);
        st<float>(ptr(exp_srt), 32, ev);
        st<float>(ptr(exp_scratch), 0, 1.0f / ev);
        if (label0 != 0) {
            st<float>(ptr(label0), 0x0c, 1.0f / ev);
            flush_cpu_lines(ptr(label0), 64);
        }
    }
    st<std::uint64_t>(ptr(exp_srt), 36, exp_scratch);
    {
        const std::uint32_t ud[2] = {static_cast<std::uint32_t>(exp_srt),
                                     static_cast<std::uint32_t>(exp_srt >> 32)};
        builtin_pass(cb, shader_at(kShExposure), ud, 2, 1, 1, 1);
        // TODO(verify): with an exposure texture the original also writes an 8-byte label and a
        // release-memory/wait pair through two statically linked Agc helpers the description
        // does not detail; not emitted here.
    }
    // 10. Main kernel, six dispatches across the grid.
    const std::uint32_t v = ld<std::uint8_t>(srp, sr::kVariant) != 0 ? 1u : 0u;
    const std::uint32_t index = 12u * ((flags >> 14) & 1u) + 8u * ((flags >> 18) & 3u) + v +
                                2u * (sharpen ? 1u : 0u) + 4u * e;
    const void *kernel = index < 48 ? shader_at(kShKernel0 + 8u * index) : nullptr;
    const std::uint32_t chunk = 8u * ((gw + 7) / 48);
    const std::uint32_t height8 = (gh + 7) & ~7u;
    const std::uint32_t last = ((gw + 7) & ~7u) - 5u * chunk;
    const std::uint32_t tail = profile == 2 ? 3u : 4u;
    std::uint32_t ud[6] = {static_cast<std::uint32_t>(srtb),
                           static_cast<std::uint32_t>(srtb >> 32),
                           option,
                           0,
                           tail,
                           tail};
    set_shader_registers_direct(cb, kernel);
    for (std::uint32_t i = 0; i < 6; ++i) {
        ud[3] = i * chunk;
        write_user_data(cb, kernel, ud, 6);
        dispatch_if_enabled(cb, kernel, i < 5 ? chunk : last, height8, 1);
    }
    flush_cpu_lines(b, kSrtBSize);
    // 11. Barrier; 12. network bracket packets.
    barrier(cb, 0x13);
    if (cb_raw2(cb, 0xc0006f00u, 0x30000001u) != 0) {
        return err::kNoRoomForPacket;
    }
    if (im.agc_dcb_bracket_packet == nullptr ||
        im.agc_dcb_bracket_packet(&cb, 1, 0x230, 1, 0, 0, 0xc000, 4, 0, 0, 0, 1) == nullptr) {
        return err::kNoRoomForPacket;
    }
    if (cb_raw2(cb, 0xc0007000u, 1) != 0) {
        return err::kNoRoomForPacket;
    }
    // 13. Package network passes (network 0; networks 0 and 1 for profile 2).
    const std::uint32_t nets = profile == 2 ? 2u : 1u;
    for (std::uint32_t n = 0; n < nets; ++n) {
        const std::uint8_t *ent = entry0 + 0x28u * n;
        const void *net_shader = ptr<const void>(ld<std::uint64_t>(ent, sr::kEShader));
        const std::uint64_t label =
            ld<std::uint64_t>(ctx, (n == 0 ? cx::kLabels0 : cx::kLabels1) + 8u * ring);
        if (net_shader == nullptr) {
            continue; // deviation: no package network (the original would use a null shader)
        }
        load_shader_registers(cb, net_shader);
        if (label != 0) {
            void *l = ptr<void>(label);
            const std::uint64_t old = ld<std::uint64_t>(l, 0x20);
            st<std::uint64_t>(l, 0x20,
                              (old & 0xffff000000000000ull) |
                                  (ld<std::uint64_t>(ent, sr::kEWeights) & 0xffffffffffffull));
            // TODO(verify): placement of the grid, output address and computed offset.
            st<std::uint32_t>(l, 0x10, (gw + 7) & ~7u);
            st<std::uint32_t>(l, 0x14, height8);
            st<std::uint64_t>(l, 0x18,
                              tdesc_address(bp(ctx) + (n == 0 ? cx::kRfmA : cx::kRfmB)) << 8);
            st<std::uint32_t>(l, 0x28, 0);
            flush_cpu_lines(l, kLabelSize);
        }
        const std::uint64_t rec = ring_take(ctx, 16, 16);
        if (rec == 0) {
            return err::kScratchAllocFailed;
        }
        write_user_data_pairs(cb, net_shader, label, ptr<void>(rec));
        dispatch_if_enabled(cb, net_shader, 30, 1, 1);
        barrier(cb, 0x13);
    }
    // 14. Network bracket close.
    if (cb_raw2(cb, 0xc0006f00u, 0x70000002u) != 0) {
        return err::kNoRoomForPacket;
    }
    if (im.agc_dcb_bracket_packet == nullptr ||
        im.agc_dcb_bracket_packet(&cb, 0, 0xd, 0, 0, 0, 0xc000, 4, 0, 0, 0, 1) == nullptr) {
        return err::kNoRoomForPacket;
    }
    if (cb_raw2(cb, 0xc0007000u, 2) != 0) {
        return err::kNoRoomForPacket;
    }
    // 15. Keep copies.
    const std::uint8_t options = ld<std::uint8_t>(ctx, cx::kOptions);
    std::int32_t r = 0;
    if ((options & 2u) != 0) {
        r = copy_texture(cb, ctx, slot_tex(p, 2), cx::kKeepHistory, cx::kCapHistory, p);
    }
    if (r == 0 && (options & 1u) != 0) {
        r = copy_texture(cb, ctx, slot_tex(p, 4), cx::kKeepDepth, cx::kCapDepth, p);
    }
    if (r == 0 && (options & 4u) != 0 && (flags & (1u << 17)) != 0) {
        r = copy_texture(cb, ctx, slot_tex(p, 6), cx::kKeepReactive, cx::kCapReactive, p);
    }
    if (r != 0) {
        return r;
    }
    if ((options & 8u) != 0 && aux != nullptr) {
        const std::uint32_t cap_h = ld<std::uint32_t>(ctx, cx::kCapLut);
        const std::uint32_t cap_v = ld<std::uint32_t>(ctx, cx::kCapLut + 4);
        for (std::uint32_t i = 0; i < 2; ++i) {
            const void *src = static_cast<const std::uint8_t *>(aux) + 0x20 * i;
            void *dst = bp(ctx) + (i == 0 ? cx::kKeepLutA : cx::kKeepLutB);
            if (tdesc_width(src) > cap_h || tdesc_height(src) > cap_v) {
                continue;
            }
            tdesc_set_size(dst, tdesc_width(src), tdesc_height(src));
            if (im.agc_dcb_push_marker != nullptr) {
                im.agc_dcb_push_marker(&cb, "Copy Texture", 0);
            }
            const std::uint64_t srt = ring_take(ctx, 0x48, 16);
            if (srt == 0) {
                return err::kScratchAllocFailed;
            }
            std::memset(ptr(srt), 0, 0x48);
            std::memcpy(ptr(srt), dst, 32);
            std::memcpy(ptr(srt + 32), src, 32);
            const std::uint32_t ud2[2] = {static_cast<std::uint32_t>(srt),
                                          static_cast<std::uint32_t>(srt >> 32)};
            builtin_pass(cb, shader_at(kShCopyLut), ud2, 2, tdesc_width(dst), tdesc_height(dst), 1);
            if (im.agc_dcb_pop_marker != nullptr) {
                im.agc_dcb_pop_marker(&cb);
            }
        }
    }
    // 16. Closing user-data packet.
    if (cb_free_dwords(cb) < ud_size || im.driver_user_data_write_packet == nullptr) {
        return err::kScratchAllocFailed;
    }
    cb.cursor += im.driver_user_data_write_packet(cb.cursor, 0, 0xd2000000u, nullptr, 0);
    return 0;
}

void remember_frame(void *ctx, const Params &p) {
    std::memcpy(bp(ctx) + cx::kPrev + 0x00, p + 0xf0, 8);
    std::memcpy(bp(ctx) + cx::kPrev + 0x08, p + 0xf8, 8);
    std::memcpy(bp(ctx) + cx::kPrev + 0x10, p + 0x100, 8);
    std::memcpy(bp(ctx) + cx::kPrev + 0x18, p + 0xe8, 8);
    st<std::uint32_t>(ctx, cx::kPrev + 0x20, (ld<std::uint32_t>(p, 0x120) >> 17) & 1u);
    std::memcpy(bp(ctx) + cx::kPrev + 0x24, p + 0x134, 4);
    std::memcpy(bp(ctx) + cx::kPrev + 0x28, p + 0x148, 4);
    std::uint32_t bits = ld<std::uint32_t>(ctx, cx::kFrameBits) | 2u;
    bits = (bits & ~1u) | (ld<std::uint64_t>(p, 0x128) != 0 ? 1u : 0u);
    st<std::uint32_t>(ctx, cx::kFrameBits, bits);
}

std::int32_t common_dispatch(void *ctx, const DispatchCommandRegion *region, const Params &p) {
    ModuleState &s = state();
    if (s.initialised != 1) {
        return err::kNotInitialized;
    }
    if (!ctx_valid(ctx)) {
        return err::kBadContext;
    }
    if (region == nullptr) {
        return err::kNullPointer;
    }
    // Video-out gate (a third condition in the original is a stub that always lets it through).
    if (s.title_allows_mode1 == 0 && s.videoout_mode1 == 1) {
        return err::kVideoOutRefused;
    }
    AgcCommandBuffer cb{};
    cb_init(cb, region->start, static_cast<std::uint64_t>(region->size_dwords) * 4u);
    const std::uint32_t ring = ld<std::uint8_t>(ctx, cx::kRing);
    std::uint8_t *slot = bp(ctx) + cx::kRings + 24u * ring;
    st<std::uint64_t>(slot, 8, ld<std::uint64_t>(slot, 0));
    const std::int32_t r = main_builder(cb, ctx, p);
    if (r == 0) {
        pad_with_nop(cb);
        remember_frame(ctx, p);
        st<std::uint8_t>(ctx, cx::kRing, static_cast<std::uint8_t>((ring + 1) & 7u));
    }
    return r;
}

void cp(Params &d, std::uint32_t doff, const void *src, std::uint32_t soff, std::uint32_t n) {
    std::memcpy(d + doff, static_cast<const std::uint8_t *>(src) + soff, n);
}

void camera_common(Params &d, const void *s) {
    // Internal 0x00..0xcf from the camera-style caller layouts.
    cp(d, 0x00, s, 0x00, 0x40);
    st<std::uint64_t>(d, 0x40, 0);
    cp(d, 0x48, s, 0x40, 8);
    cp(d, 0x50, s, 0x48, 8);
    cp(d, 0x58, s, 0x58, 0xd0 - 0x58);
}

} // namespace

// ------------------------------------------------------------------------------------------------
// Exports (libScePsml).
// ------------------------------------------------------------------------------------------------
std::int32_t psmlInitialize() {
    ModuleState &s = state();
    system_info_gather();
    log(kModuleName, "[PSML] ### libScePsml.sprx Release version load ###");
    if (s.trinity_mode == 0) {
        log(kModuleName, "[PSML] MFSR isn't supported in sceKernelIsTrinityMode() == 0");
        return err::kNotTrinity;
    }
    if (s.initialised == 1) {
        return err::kAlreadyInitialized;
    }
    if (module_gpu_setup_once() != 0) {
        return err::kPlatformInitFailed;
    }
    s.flag_16ec38 = 1;
    const std::int32_t r = create_common_shader_set();
    if (r != 0) {
        return r;
    }
    event_thread_start();
    s.initialised = 1;
    return 0;
}

std::int32_t mfsrGetSharedResourcesInitRequirement(MemoryRequirement *out,
                                                   const SharedResourcesInitParameters *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (!profile_allowed(params->profile)) { // no null checks (quirk of the original)
        return err::kInvalidParameter;
    }
    shared_requirement(out, params->profile);
    return 0;
}

std::int32_t mfsrCreateSharedResources(void **out, const SharedResourcesInitParameters *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    return shared_create_counted(out, params);
}

std::int32_t mfsrReleaseSharedResources(void *shared) {
    ModuleState &s = state();
    if (s.initialised != 1) {
        return err::kNotInitialized;
    }
    if (shared == nullptr) {
        return err::kSharedResourcesArg;
    }
    const std::int32_t r = shared_release(shared);
    // Quirk of the original: the count is decremented whatever the result.
    s.shared_count.fetch_sub(1);
    return r;
}

namespace {
std::int32_t combined_requirement(MemoryRequirement *out, const InitParams &ip) {
    MemoryRequirement shared{};
    shared_requirement(&shared, ip.profile);
    std::uint64_t rfm = 0;
    const std::int32_t r = context_requirement_core(out, ip, &rfm);
    if (r != 0) {
        return r;
    }
    if (out->alignment != shared.alignment || out->block_size != shared.block_size) {
        std::abort(); // the original executes an invalid instruction here (cannot happen)
    }
    out->block_count += rfm + shared.block_count;
    return 0;
}
} // namespace

std::int32_t mfsrGetSimpleInitRequirement(MemoryRequirement *out,
                                          const SimpleInitParameters *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    return combined_requirement(out, params_simple(params));
}

std::int32_t mfsrGetContextAndSharedInitRequirement(MemoryRequirement *out,
                                                    const ContextInitParametersV1 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (params->profile != 0) {
        return err::kInvalidParameter;
    }
    return combined_requirement(out, params_from_v1(params, false));
}

std::int32_t mfsrGetContextInitRequirementV1(MemoryRequirement *out,
                                             const ContextInitParametersV1 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    std::uint64_t rfm = 0;
    const std::int32_t r = context_requirement_core(out, params_from_v1(params, false), &rfm);
    out->block_count += rfm; // done even on failure (a null `out` crashes, as in the original)
    return r;
}

std::int32_t mfsrGetContextInitRequirementV2(MemoryRequirement *out,
                                             const ContextInitParametersV2 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    std::uint64_t rfm = 0;
    const std::int32_t r =
        context_requirement_core(out, params_from_v2(params, false, false), &rfm);
    out->block_count += rfm;
    return r;
}

std::int32_t mfsrGetContextInitRequirementV3(MemoryRequirement *out,
                                             const ContextInitParametersV2 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    std::uint64_t rfm = 0;
    const std::int32_t r = context_requirement_core(out, params_from_v2(params, true, false), &rfm);
    out->block_count += rfm;
    return r;
}

namespace {
std::int32_t create_with_own_shared(void **out, InitParams ip) {
    MemoryRequirement shared{};
    shared_requirement(&shared, ip.profile);
    SharedResourcesInitParameters sp{};
    sp.profile = ip.profile;
    sp.blocks = ip.blocks;
    sp.block_count = shared.block_count < ip.block_count ? shared.block_count : ip.block_count;
    sp.virtual_address_start = 0;
    void *srp = nullptr;
    std::int32_t r = shared_create_counted(&srp, &sp);
    ip.blocks += shared.block_count;
    ip.block_count = ip.block_count > shared.block_count ? ip.block_count - shared.block_count : 0;
    if (r != 0) {
        return r;
    }
    ip.owned_shared = srp;
    // Quirk of the original: if this fails the shared resources stay (count stays 1).
    return context_create_core(out, ip);
}
} // namespace

std::int32_t mfsrCreateContextSimple(void **out, const SimpleInitParameters *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (out == nullptr || params == nullptr || params->blocks == nullptr) {
        return err::kNullPointer;
    }
    if (params->profile == 1 && (state().feature_bits & 1u) == 0) {
        return err::kInvalidParameter;
    }
    return create_with_own_shared(out, params_simple(params));
}

std::int32_t mfsrCreateContextWithOwnSharedResources(void **out,
                                                     const ContextInitParametersV1 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (out == nullptr || params == nullptr || params->blocks == nullptr) {
        return err::kNullPointer;
    }
    if (params->profile != 0) {
        return err::kInvalidParameter;
    }
    return create_with_own_shared(out, params_from_v1(params, false));
}

std::int32_t mfsrCreateContextV1(void **out, const ContextInitParametersV1 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (out == nullptr || params == nullptr || params->blocks == nullptr) {
        return err::kNullPointer;
    }
    if (params->reserved0 != 0 || params->reserved1 != 0) {
        log(kModuleName, "[PSML] MfsrContextInitParameters reserved fields must be 0");
        return err::kInvalidParameter;
    }
    return context_create_core(out, params_from_v1(params, true));
}

namespace {
std::int32_t check_lut_size(const FsrLutSize *lut) {
    if (lut->horizontal < 1 || lut->horizontal > 16384) {
        log(kModuleName, "[PSML] m_maxSizeFsrLutForKeepCopy horizontal is invalid (%u)",
            lut->horizontal);
        return err::kInvalidParameter;
    }
    if (lut->vertical < 1 || lut->vertical > 16384) {
        log(kModuleName, "[PSML] m_maxSizeFsrLutForKeepCopy vertical is invalid (%u)",
            lut->vertical);
        return err::kInvalidParameter;
    }
    return 0;
}
} // namespace

std::int32_t mfsrCreateContextV2(void **out, const ContextInitParametersV2 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (out == nullptr || params == nullptr || params->blocks == nullptr) {
        return err::kNullPointer;
    }
    if (params->reserved1 != 0) {
        log(kModuleName, "[PSML] MfsrContextInitParameters reserved field must be 0");
        return err::kInvalidParameter;
    }
    if (params->flags >= 2) {
        log(kModuleName, "[PSML] m_flags is invalid (%u)", params->flags);
        return err::kInvalidParameter;
    }
    if ((params->flags & 1u) != 0 && params->max_size_fsr_lut_for_keep_copy != nullptr) {
        const std::int32_t r = check_lut_size(params->max_size_fsr_lut_for_keep_copy);
        if (r != 0) {
            return r;
        }
    }
    return context_create_core(out, params_from_v2(params, false, true));
}

std::int32_t mfsrCreateContextV3(void **out, const ContextInitParametersV2 *params) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (out == nullptr || params == nullptr || params->blocks == nullptr) {
        return err::kNullPointer;
    }
    if (params->reserved1 != 0) {
        log(kModuleName, "[PSML] MfsrContextInitParameters reserved field must be 0");
        return err::kInvalidParameter;
    }
    if (params->flags >= 2) {
        log(kModuleName, "[PSML] m_flags is invalid (%u)", params->flags);
        return err::kInvalidParameter;
    }
    if (params->flags == 0 && params->max_size_fsr_lut_for_keep_copy != nullptr) {
        log(kModuleName, "[PSML] m_maxSizeFsrLutForKeepCopy is used without kSupportFsr");
        return err::kInvalidParameter;
    }
    if (params->flags == 1 && params->max_size_fsr_lut_for_keep_copy != nullptr) {
        const std::int32_t r = check_lut_size(params->max_size_fsr_lut_for_keep_copy);
        if (r != 0) {
            return r;
        }
    }
    for (int i = 0; i < 2; ++i) {
        if (params->reserved_textures[i] != nullptr) {
            log(kModuleName, "[PSML] m_reservedTextures[%d] must be nullptr", i);
            return err::kInvalidParameter;
        }
    }
    return context_create_core(out, params_from_v2(params, true, true));
}

std::int32_t mfsrReleaseContext(void *ctx) {
    ModuleState &s = state();
    if (s.initialised != 1) {
        return err::kNotInitialized;
    }
    if (!ctx_valid(ctx)) {
        return err::kBadContext;
    }
    st<std::uint32_t>(ctx, cx::kMagic, kMagicReleased);
    void *srp = ptr<void>(ld<std::uint64_t>(ctx, cx::kShared));
    const bool owned = ld<std::uint8_t>(ctx, cx::kOwned) != 0;
    (void)context_unslot(ctx, srp); // its constant 0x8a810005 is ignored (quirk of the original)
    if (owned) {
        // Quirk of the original: the shared count is NOT decremented here.
        (void)shared_release(srp);
    }
    if (s.context_count.fetch_sub(1) <= 0) {
        return err::kTooManyContexts;
    }
    return 0;
}

std::int32_t mfsrGetDispatchCommandSize(const void *ctx, std::uint32_t *out_dwords) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (!ctx_valid(ctx)) {
        return err::kBadContext;
    }
    if (out_dwords == nullptr) {
        return err::kNullPointer;
    }
    *out_dwords = 0x600;
    return 0;
}

std::int32_t mfsrDispatchExplicitMatrix(void *ctx, const DispatchCommandRegion *region,
                                        const void *params) {
    Params d = {};
    if (params != nullptr) {
        cp(d, 0x00, params, 0x00, 0x38);
        cp(d, 0x58, params, 0x40, 8);
        cp(d, 0x60, params, 0x48, 8);
        st<float>(d, 0x64, 1.0f);
        st<float>(d, 0x68, 1.0f);
        cp(d, 0x164, params, 0x50, 0x40);
        const float x = ld<float>(params, 0x90);
        const float y = ld<float>(params, 0x94);
        const float z = ld<float>(params, 0x98);
        st<float>(d, 0x160, std::sqrt(x * x + y * y + z * z));
        cp(d, 0xe8, params, 0x9c, 8);
        cp(d, 0xf0, params, 0xa4, 8);
        cp(d, 0x100, params, 0xac, 8);
        cp(d, 0x108, params, 0xb4, 8);
        cp(d, 0x110, params, 0xbc, 8);
        cp(d, 0x118, params, 0xc4, 5);
        st<std::uint32_t>(d, 0x120, ld<std::uint32_t>(params, 0xcc) & 0x80008000u);
        for (std::uint32_t o = 0x134; o <= 0x140; o += 4) {
            st<float>(d, o, 1.0f);
        }
        d[0x15c] = 1;
    }
    return params != nullptr ? common_dispatch(ctx, region, d) : err::kNullPointer;
}

std::int32_t mfsrDispatchFloatCamera(void *ctx, const DispatchCommandRegion *region,
                                     const void *params) {
    if (params == nullptr) {
        return err::kNullPointer;
    }
    Params d = {};
    camera_common(d, params);
    for (std::uint32_t i = 0; i < 3; ++i) {
        st<double>(d, 0xd0 + 8u * i, static_cast<double>(ld<float>(params, 0xd0 + 4u * i)));
    }
    cp(d, 0xe8, params, 0xdc, 8);
    cp(d, 0xf0, params, 0xe4, 8);
    cp(d, 0x100, params, 0xec, 8);
    cp(d, 0x108, params, 0xf4, 8);
    cp(d, 0x110, params, 0xfc, 8);
    cp(d, 0x118, params, 0x104, 4);
    cp(d, 0x11c, params, 0x108, 1);
    st<std::uint32_t>(d, 0x120, ld<std::uint32_t>(params, 0x10c) & 0x80008000u);
    cp(d, 0x124, params, 0x110, 4);
    cp(d, 0x130, params, 0x11c, 4);
    st<float>(d, 0x134, 1.0f);
    cp(d, 0x138, params, 0x120, 8);
    cp(d, 0x140, params, 0x128, 4);
    cp(d, 0x14c, params, 0x130, 8);
    cp(d, 0x154, params, 0x138, 4);
    return common_dispatch(ctx, region, d);
}

std::int32_t mfsrDispatchDoubleCamera(void *ctx, const DispatchCommandRegion *region,
                                      const void *params) {
    if (params == nullptr) {
        return err::kNullPointer;
    }
    Params d = {};
    camera_common(d, params);
    cp(d, 0xd0, params, 0xd0, 0x28);
    cp(d, 0x100, params, 0xf8, 8);
    cp(d, 0x108, params, 0x100, 8);
    cp(d, 0x110, params, 0x108, 8);
    cp(d, 0x118, params, 0x110, 4);
    cp(d, 0x11c, params, 0x114, 1);
    st<std::uint32_t>(d, 0x120, ld<std::uint32_t>(params, 0x118) & 0x80008000u);
    cp(d, 0x124, params, 0x11c, 4);
    cp(d, 0x130, params, 0x128, 4);
    st<float>(d, 0x134, 1.0f);
    cp(d, 0x138, params, 0x12c, 8);
    cp(d, 0x140, params, 0x134, 4);
    cp(d, 0x144, params, 0x13c, 4);
    cp(d, 0x14c, params, 0x13c, 8);
    cp(d, 0x154, params, 0x144, 4);
    return common_dispatch(ctx, region, d);
}

std::int32_t mfsrDispatchNative(void *ctx, const DispatchCommandRegion *region,
                                const void *params) {
    if (params == nullptr) {
        return err::kNullPointer;
    }
    Params d = {};
    cp(d, 0x00, params, 0x00, 0x158);
    st<std::uint64_t>(d, 0x40, 0);
    st<float>(d, 0x134, 1.0f);
    st<float>(d, 0x148, 0.0f);
    st<std::uint32_t>(d, 0x120, ld<std::uint32_t>(d, 0x120) & 0x80018000u);
    // Our guard: the original reads the context's m_flags before validating the handle.
    if (!ctx_valid(ctx) || (ld<std::uint32_t>(ctx, cx::kFlags) & kKSupportFsr) == 0) {
        st<std::uint64_t>(d, 0x128, 0);
    }
    return common_dispatch(ctx, region, d);
}

std::int32_t mfsrDispatchNativeValidated(void *ctx, const DispatchCommandRegion *region,
                                         const void *params) {
    if (params == nullptr) {
        return err::kNullPointer;
    }
    Params d = {};
    cp(d, 0x00, params, 0x00, 0x158);
    d[0x1a4] = 1;
    return common_dispatch(ctx, region, d);
}

std::int32_t mfsrGetMipLodBias(const void *ctx, float *out_bias, std::uint32_t render_width) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    if (!ctx_valid(ctx)) {
        return err::kBadContext;
    }
    if (out_bias == nullptr) {
        return err::kNullPointer;
    }
    *out_bias = std::log2(static_cast<float>(render_width) /
                          static_cast<float>(ld<std::uint32_t>(ctx, cx::kOutput))) -
                1.0f;
    return 0;
}

std::int32_t mfsrRequestCapture(void *ctx) {
    ModuleState &s = state();
    if (s.initialised != 1) {
        return err::kNotInitialized;
    }
    if (!ctx_valid(ctx)) {
        return err::kBadContext;
    }
    if (s.capture_message_printed == 0) {
        log(kModuleName, "[PSML] capture is not supported: this PRX is a Release version, "
                         "Debug Settings are needed");
        s.capture_message_printed = 1;
    }
    return 0;
}

std::int32_t mfsrContextNoOpA(void *ctx) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    return ctx_valid(ctx) ? 0 : err::kBadContext;
}

std::int32_t mfsrContextNoOpB(void *ctx) {
    if (state().initialised != 1) {
        return err::kNotInitialized;
    }
    return ctx_valid(ctx) ? 0 : err::kBadContext;
}

} // namespace bc5::reimpl::psml
