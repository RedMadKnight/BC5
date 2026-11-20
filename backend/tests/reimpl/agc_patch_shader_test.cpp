// SPDX-License-Identifier: GPL-2.0-only
// Clean-room tests of the libSceAgc re-creation, part 2 of the behavioural description: packet
// patch helpers, packet utilities, GetSize functions, shader creation / fusing / linking,
// interpolant mappings, prim state and GS oversubscription. Every expected value below is worked
// by hand from the description; all shader blobs, code buffers and the primitive table are
// synthetic (made up here, no console data).
#include <catch2/catch_test_macros.hpp>

#include "bc5/reimpl/agc.hpp"
#include "bc5/reimpl/module.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace agc = bc5::reimpl::agc;
using agc::RegPair;
using agc::Shader;
using u8 = std::uint8_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;

// Comparison and printing of register pairs for the checks below. Defined in the module's
// namespace so argument-dependent lookup finds it from Catch and std::array.
namespace bc5::reimpl::agc {
inline bool operator==(const RegPair &a, const RegPair &b) {
    return a.offset == b.offset && a.value == b.value;
}
} // namespace bc5::reimpl::agc

template <> struct Catch::StringMaker<bc5::reimpl::agc::RegPair> {
    static std::string convert(const bc5::reimpl::agc::RegPair &p) {
        char text[40];
        std::snprintf(text, sizeof text, "{0x%x, 0x%08x}", p.offset, p.value);
        return text;
    }
};

namespace {

constexpr std::int32_t kWrong = static_cast<std::int32_t>(0x8a6c000cu);
constexpr std::int32_t kMagic = static_cast<std::int32_t>(0x8a6c0003u);
constexpr std::int32_t kVersion = static_cast<std::int32_t>(0x8a6c0004u);
constexpr std::int32_t kRegNotFound = static_cast<std::int32_t>(0x8a6c0005u);
constexpr std::int32_t kHalves = static_cast<std::int32_t>(0x8a6c0008u);
constexpr std::int32_t kCreated = static_cast<std::int32_t>(0x8a6c001fu);
constexpr std::int32_t kNotInit = static_cast<std::int32_t>(0x8a6c002fu);
constexpr std::int32_t kTarget = static_cast<std::int32_t>(0x8a6c003du);
constexpr std::int32_t kDebug = static_cast<std::int32_t>(0x8a6c0042u);

constexpr u32 kNormalSoc = 0x12345600u;

u64 addr(const void *p) { return static_cast<u64>(reinterpret_cast<std::uintptr_t>(p)); }

// ---- synthetic primitive table (0x23f1c, 18 x uint32) -----------------------------------------
// Made-up classes: T(p) = p % 5 for p = 1..18 (so T(1) = 1, T(5) = 0, T(18) = 3); an off-by-one
// index (table[p] instead of table[p-1]) would be visible.
class SyntheticPrimTable final : public bc5::reimpl::FirmwareData {
  public:
    SyntheticPrimTable() {
        for (u32 i = 0; i < 18; ++i) {
            table_[i] = (i + 1) % 5;
        }
    }
    const std::uint8_t *get(const char *module, std::uint64_t vaddr, std::uint64_t size) override {
        if (module == nullptr || std::strcmp(module, "libSceAgc") != 0) {
            return nullptr;
        }
        if (vaddr < kBase || vaddr + size > kBase + sizeof(table_)) {
            return nullptr;
        }
        return reinterpret_cast<const std::uint8_t *>(table_.data()) + (vaddr - kBase);
    }

  private:
    static constexpr std::uint64_t kBase = 0x23f1c;
    std::array<u32, 18> table_{};
};

SyntheticPrimTable g_prim_table;

u32 synthetic_class(u32 prim_type) { return (prim_type >= 1 && prim_type <= 18) ? prim_type % 5 : 2; }

// Each test: fresh module globals and imports, no firmware data; firmware data reset at the end.
struct Env {
    Env() {
        agc::testing::reset();
        agc::testing::clear_imports();
        bc5::reimpl::set_firmware_data(nullptr);
    }
    ~Env() { bc5::reimpl::set_firmware_data(nullptr); }
    Env(const Env &) = delete;
    Env &operator=(const Env &) = delete;
};

// ---- register descriptors (section 4) -----------------------------------------------------------
void set_desc(u64 vaddr, u32 offset, u32 value) {
    RegPair *d = agc::testing::descriptor(vaddr);
    REQUIRE(d != nullptr);
    d->offset = offset;
    d->value = value;
}

void set_desc2(u64 vaddr, u32 lo, u32 hi) {
    RegPair *d = agc::testing::descriptor(vaddr);
    REQUIRE(d != nullptr);
    d[0] = RegPair{lo, 0};
    d[1] = RegPair{hi, 0};
}

// The resolved values agc2.md section 4 lists for the default target.
void resolve_all() {
    set_desc2(0x45c90, 0x20c, 0x20d);
    set_desc2(0x45ce0, 0x008, 0x009);
    set_desc2(0x45ca0, 0x0c8, 0x0c9);
    set_desc2(0x45cd0, 0x148, 0x149);
    set_desc2(0x45cb0, 0x088, 0x089);
    set_desc2(0x45cc0, 0x108, 0x109);
    set_desc(0x459d8, 0x08a, 0);
    set_desc(0x459f0, 0x08b, 0);
    set_desc(0x459e0, 0x10a, 0);
    set_desc(0x459f8, 0x10b, 0);
    set_desc(0x45f28, 0x100, 0x00ffffff);
    set_desc(0x45db8, 0x191, 0);
    set_desc(0x45a68, 0x2d5, 0x2000);
    set_desc(0x45a30, 0x29b, 2);
    set_desc(0x458c8, 0x25b, 0);
    set_desc(0x458f0, 0x262, 0);
    set_desc(0x45a58, 0x242, 0);
    set_desc(0x458d8, 0x1ff, 0);
    set_desc(0x45f58, 0x291, 0);
    set_desc(0x45f00, 0x2d3, 0);
    set_desc(0x45f48, 0x1b1, 0);
    set_desc(0x45f10, 0x207, 0);
    set_desc(0x45f08, 0x260, 0);
    set_desc(0x45f30, 0x081, 0);
}

// ---- fake imports -----------------------------------------------------------------------------
std::vector<u32> g_ud_args;
u32 fake_user_data_packet_size(u32 payload_bytes) {
    g_ud_args.push_back(payload_bytes);
    if (payload_bytes == 0) {
        return 2;
    }
    if (payload_bytes == 4) {
        return 3;
    }
    return 100;
}
int fake_pa_debug_false() { return 0; }
int fake_pa_debug_true() { return 1; }

void install_user_data_size() {
    g_ud_args.clear();
    REQUIRE(agc::testing::set_import("VhLnEiTuuWo",
                                     reinterpret_cast<void *>(&fake_user_data_packet_size)));
}
void install_pa_debug(bool value) {
    REQUIRE(agc::testing::set_import(
        "HMnVBVUyajk",
        value ? reinterpret_cast<void *>(&fake_pa_debug_true)
              : reinterpret_cast<void *>(&fake_pa_debug_false)));
}

// ---- packet helpers -----------------------------------------------------------------------------
template <std::size_t N> using Pkt = std::array<u32, N>;

u32 with_opcode(u32 header, u32 opcode) { return (header & 0xffff00ffu) | ((opcode & 0xffu) << 8); }

// Wrong opcode byte -> 0x8a6c000c and not one dword changed.
template <std::size_t N, typename Fn> void check_rejects(const Pkt<N> &good, Fn fn) {
    for (u32 op : {0x10u, 0x00u, 0xffu, 0x3du}) {
        Pkt<N> p = good;
        p[0] = with_opcode(p[0], op);
        if (p[0] == good[0]) {
            continue;
        }
        const Pkt<N> before = p;
        CHECK(fn(p.data()) == kWrong);
        CHECK(p == before);
    }
}

// ---- shader info block ------------------------------------------------------------------------
struct InfoBlock {
    RegPair uc0;        // +0x00
    RegPair stages;     // +0x08 (value at +0x0c)
    RegPair unused[2];  // +0x10
    RegPair gs_out;     // +0x20
    RegPair uc1;        // +0x28
};
static_assert(sizeof(InfoBlock) == 0x30);
static_assert(offsetof(InfoBlock, uc0) == agc::kInfoUcSlot0);
static_assert(offsetof(InfoBlock, stages) == agc::kInfoStagesEnable);
static_assert(offsetof(InfoBlock, gs_out) == agc::kInfoGsOutPrim);
static_assert(offsetof(InfoBlock, uc1) == agc::kInfoUcSlot1);

} // namespace

// =================================================================================================
// A.1 / B.1 / C.1 packet patch helpers
// =================================================================================================

TEST_CASE("jump patch with mode (Ikfdt-rIqCE) rewrites address, size and mode", "[agc][patch]") {
    Env env;
    const Pkt<4> good{0xC0023F00u, 0xAAAAAAAAu, 0x00000000u, 0xFFFFFFFFu};
    Pkt<4> p = good;
    CHECK(agc::agcJumpPatchSetTargetEx(p.data(), 6, 0x123456789ABCDEF5ull, 0x1ABCDEu) == 0);
    // d1 keeps its low 2 bits (2), takes address bits 2..31; d2 = high 32 bits;
    // d3: bits 28..29 = mode & 3 = 2, bits 0..19 = size & 0xfffff, mask 0xcff00000 kept.
    CHECK(p == Pkt<4>{0xC0023F00u, 0x9ABCDEF6u, 0x12345678u, 0xEFFABCDEu});

    Pkt<4> q{0xC0023F00u, 0u, 0u, 0x0F200000u};
    CHECK(agc::agcJumpPatchSetTargetEx(q.data(), 1, 0x10ull, 0x10u) == 0);
    CHECK(q == Pkt<4>{0xC0023F00u, 0x10u, 0u, 0x1F200010u});

    check_rejects(good, [](u32 *pk) { return agc::agcJumpPatchSetTargetEx(pk, 1, 0x1000, 4); });
}

TEST_CASE("sceAgcJumpPatchSetTarget keeps mode bits", "[agc][patch]") {
    Env env;
    const Pkt<4> good{0xC0023F00u, 0xAAAAAAAAu, 0u, 0xFFFFFFFFu};
    Pkt<4> p = good;
    CHECK(agc::sceAgcJumpPatchSetTarget(p.data(), 0x123456789ABCDEF5ull, 0x1ABCDEu) == 0);
    CHECK(p == Pkt<4>{0xC0023F00u, 0x9ABCDEF6u, 0x12345678u, 0xFFFABCDEu});
    check_rejects(good, [](u32 *pk) { return agc::sceAgcJumpPatchSetTarget(pk, 0x1000, 4); });
}

TEST_CASE("Sh/Cx/Uc register-indirect patches", "[agc][patch]") {
    Env env;
    struct Kind {
        u32 header;
        std::int32_t (*set_address)(u32 *, u64);
        std::int32_t (*set_num)(u32 *, u32);
        std::int32_t (*add)(u32 *, std::int32_t);
    };
    const Kind kinds[] = {
        {0xC0036300u, agc::sceAgcSetShRegIndirectPatchSetAddress,
         agc::sceAgcSetShRegIndirectPatchSetNumRegisters, agc::sceAgcSetShRegIndirectPatchAddRegisters},
        {0xC0039F00u, agc::sceAgcSetCxRegIndirectPatchSetAddress,
         agc::sceAgcSetCxRegIndirectPatchSetNumRegisters, agc::sceAgcSetCxRegIndirectPatchAddRegisters},
        {0xC0036400u, agc::sceAgcSetUcRegIndirectPatchSetAddress,
         agc::sceAgcSetUcRegIndirectPatchSetNumRegisters, agc::sceAgcSetUcRegIndirectPatchAddRegisters},
        // The Uc builder sets header bit 2 on socId 0x840f00; the opcode byte is still 0x64.
        {0xC0036404u, agc::sceAgcSetUcRegIndirectPatchSetAddress,
         agc::sceAgcSetUcRegIndirectPatchSetNumRegisters, agc::sceAgcSetUcRegIndirectPatchAddRegisters},
    };
    for (const Kind &k : kinds) {
        INFO("header " << std::hex << k.header);
        const Pkt<5> good{k.header, 0x00000001u, 0xDEADBEEFu, 0x80000000u, 0xFFFFC005u};

        Pkt<5> p = good;
        CHECK(k.set_address(p.data(), 0x0000ABCD12345677ull) == 0);
        CHECK(p == Pkt<5>{k.header, 0x12345675u, 0x0000ABCDu, 0x80000000u, 0xFFFFC005u});

        p = good;
        CHECK(k.set_num(p.data(), 0x14007u) == 0);
        CHECK(p[4] == 0xFFFFC007u);
        CHECK(p[3] == 0x80000000u);

        p = good;
        CHECK(k.add(p.data(), 0x10) == 0);
        CHECK(p[4] == 0xFFFFC015u);
        p = good;
        CHECK(k.add(p.data(), -6) == 0); // 5 - 6 wraps modulo 2^14, bits 14..31 kept
        CHECK(p[4] == 0xFFFFFFFFu);
        p = good;
        p[4] = 0x00003FFFu;
        CHECK(k.add(p.data(), 1) == 0); // no carry into bit 14
        CHECK(p[4] == 0x00000000u);

        check_rejects(good, [&](u32 *pk) { return k.set_address(pk, 0x1000); });
        check_rejects(good, [&](u32 *pk) { return k.set_num(pk, 3); });
        check_rejects(good, [&](u32 *pk) { return k.add(pk, 3); });
    }
    // An opcode of a sibling kind is rejected (Sh helper on a Cx packet etc.).
    Pkt<5> cx{0xC0039F00u, 0, 0, 0x80000000u, 1};
    const Pkt<5> cx_before = cx;
    CHECK(agc::sceAgcSetShRegIndirectPatchSetAddress(cx.data(), 0x1000) == kWrong);
    CHECK(agc::sceAgcSetUcRegIndirectPatchSetNumRegisters(cx.data(), 7) == kWrong);
    CHECK(cx == cx_before);
}

TEST_CASE("COND_EXEC patches (DCB and async twins)", "[agc][patch]") {
    Env env;
    using EndFn = std::int32_t (*)(u32 *, const void *);
    using AddrFn = std::int32_t (*)(u32 *, u64);
    const EndFn end_fns[] = {agc::sceAgcCondExecPatchSetEnd, agc::sceAgcAsyncCondExecPatchSetEnd};
    const AddrFn addr_fns[] = {agc::sceAgcCondExecPatchSetCommandAddress,
                               agc::sceAgcAsyncCondExecPatchSetCommandAddress};
    for (EndFn fn : end_fns) {
        std::array<u32, 32> buf{};
        buf[0] = 0xC0032200u;
        buf[4] = 0xABCDC123u;
        CHECK(fn(buf.data(), buf.data() + 5 + 7) == 0);
        CHECK(buf[4] == 0xABCDC007u); // 7 dwords after the 5-dword packet, bits 14..31 kept
        CHECK(fn(buf.data(), buf.data() + 5) == 0);
        CHECK(buf[4] == 0xABCDC000u);
        CHECK(fn(buf.data(), buf.data() + 4) == 0); // (4 - 5) & 0x3fff
        CHECK(buf[4] == 0xABCDFFFFu);

        std::array<u32, 32> bad = buf;
        bad[0] = 0xC0032300u;
        const std::array<u32, 32> bad_before = bad;
        CHECK(fn(bad.data(), bad.data() + 9) == kWrong);
        CHECK(bad == bad_before);
    }
    for (AddrFn fn : addr_fns) {
        const Pkt<5> good{0xC0032200u, 0x00000003u, 0x11111111u, 0u, 0x00001234u};
        Pkt<5> p = good;
        CHECK(fn(p.data(), 0xFFEE0000ABCDEF04ull) == 0);
        CHECK(p == Pkt<5>{0xC0032200u, 0xABCDEF07u, 0xFFEE0000u, 0u, 0x00001234u});
        check_rejects(good, [&](u32 *pk) { return fn(pk, 0x1000); });
    }
}

TEST_CASE("REWIND valid-bit patches", "[agc][patch]") {
    Env env;
    using Fn = std::int32_t (*)(u32 *, u8);
    for (Fn fn : {static_cast<Fn>(agc::sceAgcRewindPatchSetRewindState),
                  static_cast<Fn>(agc::sceAgcAsyncRewindPatchSetRewindState)}) {
        Pkt<2> p{0xC0005900u, 0x7FFFFFFFu};
        CHECK(fn(p.data(), 1) == 0);
        CHECK(p[1] == 0xFFFFFFFFu);
        CHECK(fn(p.data(), 2) == 0); // only bit 0 of the argument
        CHECK(p[1] == 0x7FFFFFFFu);
        CHECK(fn(p.data(), 3) == 0);
        CHECK(p[1] == 0xFFFFFFFFu);
        p[1] = 0x80000001u;
        CHECK(fn(p.data(), 0) == 0);
        CHECK(p == Pkt<2>{0xC0005900u, 0x00000001u});
        check_rejects(Pkt<2>{0xC0005900u, 0u}, [&](u32 *pk) { return fn(pk, 1); });
    }
}

TEST_CASE("DMA_DATA source / destination patches", "[agc][patch]") {
    Env env;
    const Pkt<7> good{0xC0055000u, 0x80000001u, 0x11111111u, 0x22222222u,
                      0x33333333u, 0x44444444u, 0x04000010u};
    Pkt<7> p = good;
    CHECK(agc::sceAgcDmaDataPatchSetDstAddressOrOffset(p.data(), 0x123456789ABCDEF3ull) == 0);
    CHECK(p == Pkt<7>{0xC0055000u, 0x80000001u, 0x11111111u, 0x22222222u, 0x9ABCDEF3u,
                      0x12345678u, 0x04000010u});
    p = good;
    CHECK(agc::sceAgcDmaDataPatchSetSrcAddressOrOffsetOrImmediate(p.data(), 0xFEDCBA9876543211ull) ==
          0);
    CHECK(p == Pkt<7>{0xC0055000u, 0x80000001u, 0x76543211u, 0xFEDCBA98u, 0x33333333u,
                      0x44444444u, 0x04000010u});
    check_rejects(good, [](u32 *pk) { return agc::sceAgcDmaDataPatchSetDstAddressOrOffset(pk, 1); });
    check_rejects(good, [](u32 *pk) {
        return agc::sceAgcDmaDataPatchSetSrcAddressOrOffsetOrImmediate(pk, 1);
    });
}

TEST_CASE("sceAgcBranchPatchSetCompareAddress", "[agc][patch]") {
    Env env;
    Pkt<14> good{};
    good[0] = 0xC00C3F00u;
    good[1] = 0x00000301u;
    good[2] = 0xAAAAAAAFu;
    good[3] = 0x12121212u;
    for (std::size_t i = 4; i < 14; ++i) {
        good[i] = static_cast<u32>(0x1000u + i);
    }
    Pkt<14> p = good;
    CHECK(agc::sceAgcBranchPatchSetCompareAddress(p.data(), 0x0000ABCD87654321ull) == 0);
    Pkt<14> want = good;
    want[2] = 0x87654327u; // low 3 bits kept (7), address & 0xfffffff8
    want[3] = 0x0000ABCDu;
    CHECK(p == want);
    check_rejects(good, [](u32 *pk) { return agc::sceAgcBranchPatchSetCompareAddress(pk, 8); });
}

TEST_CASE("RELEASE_MEM (end-of-pipe) patches", "[agc][patch]") {
    Env env;
    const Pkt<8> good{0xC0064900u, 0xFFFFFFFFu, 0x20000000u, 0x00000002u,
                      0x55555555u, 0x66666666u, 0x77777777u, 0x00000000u};
    SECTION("address") {
        Pkt<8> p = good;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchAddress(p.data(), 0x00001234ABCDEF0Full) == 0);
        Pkt<8> want = good;
        want[3] = 0xABCDEF0Eu;
        want[4] = 0x00001234u;
        CHECK(p == want);

        // interrupt select (d2 bits 24..26) == 4: success without writing
        p = good;
        p[2] = 0x24000000u;
        Pkt<8> before = p;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchAddress(p.data(), 0x1000) == 0);
        CHECK(p == before);
        // interrupt select 5 writes
        p = good;
        p[2] = 0x05000000u;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchAddress(p.data(), 0x00001234ABCDEF0Full) == 0);
        CHECK(p[3] == 0xABCDEF0Eu);
        CHECK(p[4] == 0x00001234u);
        check_rejects(good, [](u32 *pk) { return agc::sceAgcQueueEndOfPipeActionPatchAddress(pk, 4); });
    }
    SECTION("data") {
        Pkt<8> p = good;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchData(p.data(), 0x0102030405060708ull) == 0);
        Pkt<8> want = good;
        want[5] = 0x05060708u;
        want[6] = 0x01020304u;
        CHECK(p == want);
        // data select (bits 29..31) == 5: no write
        p = good;
        p[2] = 0xA0000000u;
        Pkt<8> before = p;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchData(p.data(), 1) == 0);
        CHECK(p == before);
        // interrupt select == 4: no write
        p = good;
        p[2] = 0x24000000u;
        before = p;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchData(p.data(), 1) == 0);
        CHECK(p == before);
        check_rejects(good, [](u32 *pk) { return agc::sceAgcQueueEndOfPipeActionPatchData(pk, 4); });
    }
    SECTION("gcr control") {
        Pkt<8> p = good;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchGcrCntl(p.data(), 0x1ABCu) == 0);
        CHECK(p[1] == 0xFFABCFFFu);
        p[1] = 0;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchGcrCntl(p.data(), 0xFFFu) == 0);
        CHECK(p[1] == 0x00FFF000u);
        check_rejects(good, [](u32 *pk) { return agc::sceAgcQueueEndOfPipeActionPatchGcrCntl(pk, 1); });
    }
    SECTION("event type and index") {
        Pkt<8> p = good;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchType(p.data(), 0x2f) == 0);
        CHECK(p[1] == 0xFFFFF6EFu); // index 6, type 0x2f, bits 6..7 and 12..31 kept
        p[1] = 0xFFFFFFFFu;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchType(p.data(), 0x2e) == 0);
        CHECK(p[1] == 0xFFFFF5EEu); // index 5
        p[1] = 0xFFFFFFFFu;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchType(p.data(), 0xC5) == 0);
        CHECK(p[1] == 0xFFFFF6C5u); // > 0x2e -> index 6, type & 0x3f
        p[1] = 0;
        CHECK(agc::sceAgcQueueEndOfPipeActionPatchType(p.data(), 0x0A) == 0);
        CHECK(p[1] == 0x0000050Au);
        check_rejects(good, [](u32 *pk) { return agc::sceAgcQueueEndOfPipeActionPatchType(pk, 1); });
    }
}

TEST_CASE("sceAgcAcquireMemSetEngine", "[agc][patch]") {
    Env env;
    const Pkt<8> good{0xC0065800u, 0x7FFFFFFFu, 1, 2, 3, 4, 5, 6};
    Pkt<8> p = good;
    CHECK(agc::sceAgcAcquireMemSetEngine(p.data(), 3) == 0);
    Pkt<8> want = good;
    want[1] = 0xFFFFFFFFu;
    CHECK(p == want);
    CHECK(agc::sceAgcAcquireMemSetEngine(p.data(), 2) == 0);
    CHECK(p == good);
    check_rejects(good, [](u32 *pk) { return agc::sceAgcAcquireMemSetEngine(pk, 1); });
}

TEST_CASE("WRITE_DATA patches", "[agc][patch]") {
    Env env;
    const Pkt<5> good{0xC0033700u, 0xFFFFFFFFu, 0x11111111u, 0x22222222u, 0x33333333u};
    using AddrFn = std::int32_t (*)(u32 *, u64);
    using ByteFn = std::int32_t (*)(u32 *, u8);
    for (AddrFn fn : {static_cast<AddrFn>(agc::agcWriteDataPatchSetAddress),
                      static_cast<AddrFn>(agc::agcWriteDataPatchSetAddress2)}) {
        Pkt<5> p = good;
        CHECK(fn(p.data(), 0x123456789ABCDEF3ull) == 0); // written whole, no masking
        CHECK(p == Pkt<5>{0xC0033700u, 0xFFFFFFFFu, 0x9ABCDEF3u, 0x12345678u, 0x33333333u});
        check_rejects(good, [&](u32 *pk) { return fn(pk, 8); });
    }
    for (ByteFn fn : {static_cast<ByteFn>(agc::agcWriteDataPatchSetCachePolicy),
                      static_cast<ByteFn>(agc::agcWriteDataPatchSetCachePolicy2)}) {
        Pkt<5> p = good;
        CHECK(fn(p.data(), 5) == 0); // 5 & 3 = 1 into bits 25..26
        CHECK(p[1] == 0xFBFFFFFFu);
        p[1] = 0;
        CHECK(fn(p.data(), 2) == 0);
        CHECK(p[1] == 0x04000000u);
        check_rejects(good, [&](u32 *pk) { return fn(pk, 1); });
    }
    {
        Pkt<5> p = good;
        CHECK(agc::agcWriteDataPatchSetDestination(p.data(), 0x15) == 0);
        CHECK(p[1] == 0x7FFFFAFFu); // bit 31 cleared, bit 30 = 1, bits 8..11 = 0xA
        p = good;
        CHECK(agc::agcWriteDataPatchSetDestination(p.data(), 0x20) == 0);
        CHECK(p[1] == 0x3FFFF0FFu);
        check_rejects(good, [](u32 *pk) { return agc::agcWriteDataPatchSetDestination(pk, 1); });
    }
    {
        Pkt<5> p = good;
        CHECK(agc::agcWriteDataPatchSetDstSel(p.data(), 0x13) == 0);
        CHECK(p[1] == 0xFFFFF3FFu); // bits 30/31 untouched
        p[1] = 0;
        CHECK(agc::agcWriteDataPatchSetDstSel(p.data(), 0x0F) == 0);
        CHECK(p[1] == 0x00000F00u);
        check_rejects(good, [](u32 *pk) { return agc::agcWriteDataPatchSetDstSel(pk, 1); });
    }
}

// ---- WAIT_REG_MEM sequences: 4-dword marker (opcode 0x79) + wait packet --------------------------

namespace {
using Seq32 = std::array<u32, 11>;
using Seq64 = std::array<u32, 13>;
constexpr u32 kMarker = 0xC0027900u; // opcode 0x79, COUNT 2 -> 4 dwords
Seq32 seq32() {
    return Seq32{kMarker,    0x11111111u, 0x12342222u, 0x33333333u, // marker
                 0xC0053C00u, 0x00000013u, 0xAAAAAAAAu, 0xF0F00000u, 0x44444444u, 0x55555555u,
                 0x66666666u};
}
Seq64 seq64() {
    return Seq64{kMarker,    0x11111111u, 0x12342222u, 0x33333333u, // marker
                 0xC0079300u, 0x00000013u, 0xAAAAAAADu, 0xF0F00000u, 0x44444444u, 0x45454545u,
                 0x55555555u, 0x56565656u, 0x66666666u};
}
constexpr u64 kWaitAddr = 0xFEDFBA987654321Full;
} // namespace

TEST_CASE("sceAgcWaitRegMemPatchAddress", "[agc][patch][waitregmem]") {
    Env env;
    SECTION("32-bit wait") {
        Seq32 s = seq32();
        CHECK(agc::sceAgcWaitRegMemPatchAddress(s.data(), kWaitAddr) == 0);
        Seq32 want = seq32();
        want[2] = 0x1234BA98u; // low half = address bits 32..47
        want[3] = 0x7654321Fu; // address bits 0..31
        want[6] = 0x7654321Eu; // (w2 & 3) | (address & 0xfffffffc)
        want[7] = 0xF0F3BA98u; // (w3 & 0xfffc0000) | ((address >> 32) & 0x3ffff)
        CHECK(s == want);
    }
    SECTION("64-bit wait") {
        Seq64 s = seq64();
        CHECK(agc::sceAgcWaitRegMemPatchAddress(s.data(), kWaitAddr) == 0);
        Seq64 want = seq64();
        want[2] = 0x1234BA98u;
        want[3] = 0x7654321Fu;
        want[6] = 0x7654321Du; // (w2 & 7) | (address & 0xfffffff8)
        want[7] = 0xF0F3BA98u;
        CHECK(s == want);
    }
    SECTION("wrong wait opcode: marker already written, then error") {
        Seq32 s = seq32();
        s[4] = 0xC0051000u;
        CHECK(agc::sceAgcWaitRegMemPatchAddress(s.data(), kWaitAddr) == kWrong);
        Seq32 want = seq32();
        want[4] = 0xC0051000u;
        want[2] = 0x1234BA98u;
        want[3] = 0x7654321Fu;
        CHECK(s == want);
    }
    SECTION("marker of wrong size or opcode: nothing written") {
        for (u32 marker : {0xC0037900u, 0xC0017900u, 0xC0027600u, 0xC0021000u}) {
            Seq32 s = seq32();
            s[0] = marker;
            const Seq32 before = s;
            CHECK(agc::sceAgcWaitRegMemPatchAddress(s.data(), kWaitAddr) == kWrong);
            CHECK(s == before);
        }
    }
}

TEST_CASE("WaitRegMem compare function / reference / mask", "[agc][patch][waitregmem]") {
    Env env;
    {
        Seq32 s = seq32();
        CHECK(agc::sceAgcWaitRegMemPatchCompareFunction(s.data(), 0x0E) == 0);
        Seq32 want = seq32();
        want[5] = 0x00000016u; // bits 0..2 = 6
        CHECK(s == want);
        Seq64 t = seq64();
        CHECK(agc::sceAgcWaitRegMemPatchCompareFunction(t.data(), 0x05) == 0);
        Seq64 want64 = seq64();
        want64[5] = 0x00000015u;
        CHECK(t == want64);
    }
    {
        Seq32 s = seq32();
        CHECK(agc::sceAgcWaitRegMemPatchReference(s.data(), 0xCAFEBABEu) == 0);
        Seq32 want = seq32();
        want[8] = 0xCAFEBABEu;
        CHECK(s == want);
        Seq64 t = seq64();
        CHECK(agc::sceAgcWaitRegMemPatchReference(t.data(), 0xCAFEBABEu) == 0);
        Seq64 want64 = seq64();
        want64[8] = 0xCAFEBABEu; // high half (w5) untouched
        CHECK(t == want64);
    }
    {
        Seq32 s = seq32();
        CHECK(agc::sceAgcWaitRegMemPatchMask(s.data(), 0x0F0F0F0Fu) == 0);
        Seq32 want = seq32();
        want[9] = 0x0F0F0F0Fu; // byte offset 0x14 of the wait packet
        CHECK(s == want);
        Seq64 t = seq64();
        CHECK(agc::sceAgcWaitRegMemPatchMask(t.data(), 0x0F0F0F0Fu) == 0);
        Seq64 want64 = seq64();
        want64[10] = 0x0F0F0F0Fu; // byte offset 0x18, high half (w7) untouched
        CHECK(t == want64);
    }
    // Rejections: wrong wait opcode, wrong marker size, wrong marker opcode -> nothing written.
    for (int which = 0; which < 3; ++which) {
        Seq32 s = seq32();
        if (which == 0) {
            s[4] = 0xC0053B00u;
        } else if (which == 1) {
            s[0] = 0xC0037900u;
        } else {
            s[0] = 0xC0027A00u;
        }
        const Seq32 before = s;
        CHECK(agc::sceAgcWaitRegMemPatchCompareFunction(s.data(), 3) == kWrong);
        CHECK(agc::sceAgcWaitRegMemPatchReference(s.data(), 3) == kWrong);
        CHECK(agc::sceAgcWaitRegMemPatchMask(s.data(), 3) == kWrong);
        CHECK(s == before);
    }
}

// =================================================================================================
// Packet utilities
// =================================================================================================

TEST_CASE("sceAgcGetPacketSize incl. one-dword NOP", "[agc][packet]") {
    Env env;
    Pkt<1> h{0xC0023F00u};
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 4u);
    h[0] = 0xC0001000u;
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 2u);
    h[0] = 0xFFFF1000u; // NOP, COUNT 0x3fff: one dword
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 1u);
    h[0] = 0xFFFF1003u; // flags in bits 0..7 do not matter
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 1u);
    h[0] = 0x3FFF1000u; // type bits not part of the test
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 1u);
    h[0] = 0xFFFF1100u; // COUNT 0x3fff but opcode 0x11: COUNT + 2
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 0x4001u);
    h[0] = 0xFFFE1000u; // NOP with COUNT 0x3ffe
    CHECK(agc::sceAgcGetPacketSize(h.data()) == 0x4000u);
}

TEST_CASE("sceAgcSetNop and sceAgcSetPacketPredication", "[agc][packet]") {
    Env env;
    Pkt<2> p{0xC0053C03u, 0x12345678u};
    CHECK(agc::sceAgcSetNop(p.data()) == 0);
    CHECK(p == Pkt<2>{0xC0051003u, 0x12345678u});

    Pkt<1> h{0xC0053C00u};
    CHECK(agc::sceAgcSetPacketPredication(h.data(), 1) == 0);
    CHECK(h[0] == 0xC0053C01u);
    CHECK(agc::sceAgcSetPacketPredication(h.data(), 2) == 0); // only == 1 sets
    CHECK(h[0] == 0xC0053C00u);
    h[0] = 0xC0053C03u;
    CHECK(agc::sceAgcSetPacketPredication(h.data(), 0) == 0);
    CHECK(h[0] == 0xC0053C02u);
    h[0] = 0x00000000u; // no opcode check
    CHECK(agc::sceAgcSetPacketPredication(h.data(), 1) == 0);
    CHECK(h[0] == 0x00000001u);
}

TEST_CASE("sceAgcSetRangePredication walks packets by size", "[agc][packet]") {
    Env env;
    // [4-dword jump][1-dword NOP][2-dword REWIND][3-dword packet], bodies with bit 0 clear.
    const std::array<u32, 10> stream{0xC0023F00u, 0x0u,        0x0u, 0x0u, 0xFFFF1000u,
                                     0xC0005900u, 0x0u,        0xC0017600u, 0x0u, 0x0u};
    std::array<u32, 10> s = stream;
    CHECK(agc::sceAgcSetRangePredication(s.data(), s.data() + s.size(), 1) == 0);
    std::array<u32, 10> want = stream;
    want[0] |= 1u;
    want[4] |= 1u;
    want[5] |= 1u;
    want[7] |= 1u;
    CHECK(s == want);

    CHECK(agc::sceAgcSetRangePredication(s.data(), s.data() + s.size(), 2) == 0); // != 1 clears
    CHECK(s == stream);

    s = want;
    CHECK(agc::sceAgcSetRangePredication(s.data(), s.data() + s.size(), 0) == 0);
    CHECK(s == stream);

    // A partial range only touches the packets that start inside it.
    s = stream;
    CHECK(agc::sceAgcSetRangePredication(s.data(), s.data() + 5, 1) == 0);
    std::array<u32, 10> partial = stream;
    partial[0] |= 1u;
    partial[4] |= 1u;
    CHECK(s == partial);

    // begin >= end: returns 0, nothing changed.
    s = stream;
    CHECK(agc::sceAgcSetRangePredication(s.data() + 4, s.data() + 4, 1) == 0);
    CHECK(agc::sceAgcSetRangePredication(s.data() + 5, s.data() + 4, 1) == 0);
    CHECK(s == stream);
}

TEST_CASE("data packet payload address / range", "[agc][packet]") {
    Env env;
    Pkt<8> nop5{0xC0051000u, 1, 2, 3, 4, 5, 6, 7}; // COUNT 5
    Pkt<1> one{0xFFFF1000u};                        // one-dword NOP

    void *out = reinterpret_cast<void *>(static_cast<std::uintptr_t>(0x1));
    // V++UgBtQhn0 (checked): sub-header -> +2 dwords; else one-dword NOP -> NULL; else +1 dword.
    CHECK(agc::agcGetDataPacketPayloadAddressChecked(&out, nop5.data(), 1) == 0);
    CHECK(out == nop5.data() + 2);
    CHECK(agc::agcGetDataPacketPayloadAddressChecked(&out, nop5.data(), 0) == 0);
    CHECK(out == nop5.data() + 1);
    CHECK(agc::agcGetDataPacketPayloadAddressChecked(&out, one.data(), 0) == 0);
    CHECK(out == nullptr);
    // AMBIGUOUS: with hasSubHeader != 0 the description gives packet + 2 dwords with no
    // one-dword-NOP check, even for the one-dword form. Read literally here.
    std::array<u32, 3> one_sub{0xFFFF1000u, 0, 0};
    CHECK(agc::agcGetDataPacketPayloadAddressChecked(&out, one_sub.data(), 7) == 0);
    CHECK(out == one_sub.data() + 2);

    // CQsSq6l6+kA (unchecked): packet + 4 bytes + (sub-header ? 4 : 0)
    CHECK(agc::sceAgcGetDataPacketPayloadAddress(&out, nop5.data(), 0) == 0);
    CHECK(out == nop5.data() + 1);
    CHECK(agc::sceAgcGetDataPacketPayloadAddress(&out, nop5.data(), -1) == 0);
    CHECK(out == nop5.data() + 2);
    CHECK(agc::sceAgcGetDataPacketPayloadAddress(&out, one.data(), 0) == 0);
    CHECK(out == one.data() + 1);

    agc::PayloadRange r{reinterpret_cast<void *>(static_cast<std::uintptr_t>(0x1)), 77};
    CHECK(agc::sceAgcGetDataPacketPayloadRange(&r, nop5.data(), 1) == 0);
    CHECK(r.begin == nop5.data() + 2);
    CHECK(r.size_bytes == 20u);
    CHECK(agc::sceAgcGetDataPacketPayloadRange(&r, nop5.data(), 0) == 0);
    CHECK(r.begin == nop5.data() + 1);
    CHECK(r.size_bytes == 24u);
    CHECK(agc::sceAgcGetDataPacketPayloadRange(&r, one.data(), 0) == 0);
    CHECK(r.begin == nullptr);
    CHECK(r.size_bytes == 0u);
}

// =================================================================================================
// GetSize functions
// =================================================================================================

TEST_CASE("constant GetSize values", "[agc][getsize]") {
    Env env;
    CHECK(agc::sceAgcCbDispatchGetSize() == 0x14u);
    CHECK(agc::sceAgcCbBranchGetSize() == 0x38u);
    CHECK(agc::sceAgcCbCondWriteGetSize() == 0x24u);
    CHECK(agc::sceAgcCbQueueEndOfPipeActionGetSize() == 0x20u);
    CHECK(agc::sceAgcDcbSetShRegistersIndirectGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbSetCxRegistersIndirectGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbSetUcRegistersIndirectGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbSetShRegisterDirectGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbSetCxRegisterDirectGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbSetUcRegisterDirectGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbAtomicGdsGetSize() == 0x2cu);
    CHECK(agc::sceAgcDcbAtomicMemGetSize() == 0x24u);
    CHECK(agc::sceAgcDcbCondExecGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbJumpGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbCopyDataGetSize() == 0x18u);
    CHECK(agc::sceAgcDcbDmaDataGetSize() == 0x1cu);
    CHECK(agc::sceAgcDcbQueueEndOfShaderActionGetSize() == 0x20u);
    CHECK(agc::sceAgcDcbDispatchIndirectGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbDrawIndexAutoGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbDrawIndexGetSize() == 0x18u);
    CHECK(agc::sceAgcDcbDrawIndexOffsetGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbDrawIndirectGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbDrawIndexIndirectGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbGetLodStatsGetSize() == 0x14u);
    CHECK(agc::sceAgcDcbSetBaseDispatchIndirectArgsGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbSetBaseDrawIndirectArgsGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbSetIndexSizeGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbSetIndexBufferGetSize() == 0x0cu);
    CHECK(agc::sceAgcDcbSetIndexCountGetSize() == 0x08u);
    CHECK(agc::sceAgcDcbSetNumInstancesGetSize() == 0x08u);
    CHECK(agc::sceAgcDcbStallCommandBufferParserGetSize() == 0x08u);
    CHECK(agc::sceAgcDcbRewindGetSize() == 0x08u);
    CHECK(agc::sceAgcDcbEndOcclusionQueryGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbSetZPassPredicationEnableGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbSetBoolPredicationEnableGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbSetPredicationDisableGetSize() == 0x10u);
    CHECK(agc::sceAgcDcbPrimeUtcl2GetSize() == 0x14u);
    CHECK(agc::sceAgcDcbSetIndexIndirectArgsGetSize() == 0x10u);
    CHECK(agc::sceAgcAcbAtomicGdsGetSize() == 0x2cu);
    CHECK(agc::sceAgcAcbAtomicMemGetSize() == 0x24u);
    CHECK(agc::sceAgcAcbCondExecGetSize() == 0x14u);
    CHECK(agc::sceAgcAcbJumpGetSize() == 0x10u);
    CHECK(agc::sceAgcAcbCopyDataGetSize() == 0x18u);
    CHECK(agc::sceAgcAcbDmaDataGetSize() == 0x1cu);
    CHECK(agc::sceAgcAcbDispatchIndirectGetSize() == 0x10u);
    CHECK(agc::sceAgcAcbEventWriteGetSize() == 0x08u);
    CHECK(agc::sceAgcAcbPrimeUtcl2GetSize() == 0x14u);
    CHECK(agc::sceAgcAcbRewindGetSize() == 0x08u);
    CHECK(agc::sceAgcAcbQueueEndOfShaderActionGetSize() == 0x20u);
}

TEST_CASE("parameterised GetSize values (32-bit arithmetic)", "[agc][getsize]") {
    Env env;
    CHECK(agc::sceAgcCbNopGetSize(0) == 0u);
    CHECK(agc::sceAgcCbNopGetSize(7) == 28u);
    CHECK(agc::sceAgcCbNopGetSize(0x40000001u) == 4u); // wraps in 32 bits, zero-extended

    CHECK(agc::sceAgcCbSetShRegisterRangeDirectGetSize(0) == 8u);
    CHECK(agc::sceAgcCbSetShRegisterRangeDirectGetSize(5) == 28u);
    CHECK(agc::sceAgcCbSetShRegisterRangeDirectGetSize(0x40000000u) == 8u);
    CHECK(agc::sceAgcCbSetShRegisterRangeDirectGetSize(0x3FFFFFFFu) == 0x100000004ull - 0x100000000ull);
    CHECK(agc::sceAgcCbSetUcRegisterRangeDirectGetSize(5) == 28u);
    CHECK(agc::sceAgcCbSetUcRegisterRangeDirectGetSize(0x40000000u) == 8u);

    CHECK(agc::sceAgcCbSetShRegistersDirectGetSize(3) == 36u);
    CHECK(agc::sceAgcCbSetUcRegistersDirectGetSize(3) == 36u);
    CHECK(agc::sceAgcCbSetShRegistersDirectGetSize(0x20000000u) == 0x80000000u);
    CHECK(agc::sceAgcCbSetUcRegistersDirectGetSize(0x20000000u) == 0x80000000u);

    CHECK(agc::sceAgcDcbWriteDataGetSize(0) == 0x10u);
    CHECK(agc::sceAgcDcbWriteDataGetSize(3) == 0x1cu);
    CHECK(agc::sceAgcDcbWriteDataGetSize(0x3FFFFFFCu) == 0u);

    CHECK(agc::sceAgcDcbContextStateOpGetSize(0) == 0x14u);
    CHECK(agc::sceAgcDcbContextStateOpGetSize(1) == 0x6cu);
    CHECK(agc::sceAgcDcbContextStateOpGetSize(2) == 0x6cu);
    CHECK(agc::sceAgcDcbContextStateOpGetSize(3) == 0x80u);
    CHECK(agc::sceAgcDcbContextStateOpGetSize(4) == 0u);
    CHECK(agc::sceAgcDcbContextStateOpGetSize(0xFFFFFFFFu) == 0u);

    CHECK(agc::sceAgcDcbEventWriteGetSize(0x38) == 0x10u);
    CHECK(agc::sceAgcDcbEventWriteGetSize(0x39) == 0x10u);
    CHECK(agc::sceAgcDcbEventWriteGetSize(0x3A) == 0x08u);
    CHECK(agc::sceAgcDcbEventWriteGetSize(0x37) == 0x08u);
    CHECK(agc::sceAgcDcbEventWriteGetSize(0xB8) == 0x08u);
    CHECK(agc::sceAgcDcbEventWriteGetSize(0x00) == 0x08u);

    CHECK(agc::sceAgcDcbBeginOcclusionQueryGetSize(0) == 0x10u);
    CHECK(agc::sceAgcDcbBeginOcclusionQueryGetSize(1) == 0x120u);
    CHECK(agc::sceAgcDcbBeginOcclusionQueryGetSize(2) == 0u);
    CHECK(agc::sceAgcDcbBeginOcclusionQueryGetSize(0xFFFFFFFFu) == 0u);
}

TEST_CASE("AcquireMem GetSize doubles with workaround bit 0", "[agc][getsize]") {
    Env env;
    agc::testing::set_workaround_mask(0);
    CHECK(agc::sceAgcDcbAcquireMemGetSize() == 0x20u);
    CHECK(agc::sceAgcAcbAcquireMemGetSize() == 0x20u);
    agc::testing::set_workaround_mask(1);
    CHECK(agc::sceAgcDcbAcquireMemGetSize() == 0x40u);
    CHECK(agc::sceAgcAcbAcquireMemGetSize() == 0x40u);
    agc::testing::set_workaround_mask(6); // bits 1 and 2 do not count
    CHECK(agc::sceAgcDcbAcquireMemGetSize() == 0x20u);
    CHECK(agc::sceAgcAcbAcquireMemGetSize() == 0x20u);
    agc::testing::set_workaround_mask(7);
    CHECK(agc::sceAgcDcbAcquireMemGetSize() == 0x40u);
    CHECK(agc::sceAgcAcbAcquireMemGetSize() == 0x40u);
}

TEST_CASE("GetSize functions that use sceAgcDriverUserDataGetPacketSize", "[agc][getsize]") {
    Env env;
    install_user_data_size(); // UD(0) = 2, UD(4) = 3

    CHECK(agc::sceAgcDcbDrawIndirectMultiGetSize() == (2u * 2u + 10u) * 4u);
    CHECK(g_ud_args == std::vector<u32>{0});
    g_ud_args.clear();
    CHECK(agc::sceAgcDcbDrawIndexIndirectMultiGetSize() == (2u * 2u + 10u) * 4u);
    CHECK(g_ud_args == std::vector<u32>{0});
    g_ud_args.clear();
    CHECK(agc::sceAgcDcbDrawIndexMultiInstancedGetSize() == (2u * 2u + 9u) * 4u);
    CHECK(g_ud_args == std::vector<u32>{0});

    using Fn = std::uint64_t (*)(u32);
    for (Fn fn : {static_cast<Fn>(agc::sceAgcDcbWaitOnAddressGetSize),
                  static_cast<Fn>(agc::sceAgcAcbWaitOnAddressGetSize)}) {
        g_ud_args.clear();
        CHECK(fn(0) == (2u + 3u) * 4u + 0x1cu);
        // The description: UD(4) is called first, then UD(0).
        CHECK(g_ud_args == std::vector<u32>{4, 0});
        CHECK(fn(1) == (2u + 3u) * 4u + 0x24u);
        CHECK(fn(2) == 0u);
        CHECK(fn(0xFFFFFFFFu) == 0u);
    }
}

// =================================================================================================
// sceAgcCreateShader
// =================================================================================================

namespace {

struct alignas(16) ShaderBlob {
    Shader hdr;                 // 0x000
    std::uint8_t gap0[0xa0];    // 0x060
    u64 sub[5];                 // 0x100 the `extra` sub-block
    std::uint8_t gap1[0x58];    // 0x128
    RegPair ctx[4];             // 0x180
    std::uint8_t gap2[0x60];    // 0x1a0
    RegPair sh[8];              // 0x200
    std::uint8_t gap3[0x40];    // 0x240
    InfoBlock info;             // 0x280
    std::uint8_t gap4[0x10];    // 0x2b0
    u32 ps[4];                  // 0x2c0
};
static_assert(offsetof(ShaderBlob, sub) == 0x100);
static_assert(offsetof(ShaderBlob, ctx) == 0x180);
static_assert(offsetof(ShaderBlob, sh) == 0x200);
static_assert(offsetof(ShaderBlob, info) == 0x280);
static_assert(offsetof(ShaderBlob, ps) == 0x2c0);

constexpr u32 kCodeBytes = 0x100;
struct alignas(256) CodeBuf {
    std::array<std::uint8_t, kCodeBytes> bytes;
};

void make_code(CodeBuf &c) {
    for (u32 i = 0; i < kCodeBytes; ++i) {
        c.bytes[i] = static_cast<std::uint8_t>(i * 7u);
    }
    const u64 barefoot = 0x746f6f6665726162ull;
    const u64 hash = 0x0123456789abcdefull;
    std::memcpy(c.bytes.data() + kCodeBytes - 0x30, &barefoot, 8);
    std::memcpy(c.bytes.data() + kCodeBytes - 0x28, &hash, 8);
}

// Synthetic header blob with self-relative offsets. sh list: [{0x1234,5}, {lo, lo_units},
// {lo+1, 0xABCDEFFF}, {lo, 0x99} (duplicate, must stay), ...], num_sh_regs = num_sh.
void make_blob(ShaderBlob &b, u8 stage, u32 target, u32 lo, u8 num_sh = 4, u32 lo_units = 0x10) {
    std::memset(&b, 0, sizeof b);
    b.hdr.magic = 0x34333231u;
    b.hdr.version = 0x18u;
    b.hdr.extra = offsetof(ShaderBlob, sub) - offsetof(Shader, extra);
    b.sub[0] = 0x40;
    b.sub[1] = 0; // stays 0
    b.sub[2] = 0x20;
    b.sub[3] = 0x8;
    b.sub[4] = 0x18;
    b.hdr.ctx_regs = offsetof(ShaderBlob, ctx) - offsetof(Shader, ctx_regs);
    b.hdr.sh_regs = offsetof(ShaderBlob, sh) - offsetof(Shader, sh_regs);
    b.hdr.info = offsetof(ShaderBlob, info) - offsetof(Shader, info);
    b.hdr.ps_inputs = offsetof(ShaderBlob, ps) - offsetof(Shader, ps_inputs);
    b.hdr.vs_outputs = 0; // stays 0
    b.hdr.header_bytes = static_cast<u32>(sizeof(ShaderBlob));
    b.hdr.code_bytes = kCodeBytes;
    b.hdr.target = target;
    b.hdr.num_ps_inputs = 1;
    b.hdr.stage = stage;
    b.hdr.num_ctx_regs = 1;
    b.hdr.num_sh_regs = num_sh;
    b.ctx[0] = RegPair{0x2d5, 0x2000};
    b.sh[0] = RegPair{0x1234, 5};
    b.sh[1] = RegPair{lo, lo_units};
    b.sh[2] = RegPair{lo + 1, 0xABCDEFFFu};
    b.sh[3] = RegPair{lo, 0x99};
    b.sh[4] = RegPair{0x4444, 0x4444};
    b.info.stages = RegPair{0x2d5, 0x2000};
    b.ps[0] = 0x05;
}

Shader *const kOutSentinel = reinterpret_cast<Shader *>(static_cast<std::uintptr_t>(0x5a5a5a5a));

void check_relocated(const ShaderBlob &b, u64 code) {
    const u64 base = addr(&b);
    CHECK(b.hdr.extra == base + 0x100);
    CHECK(b.sub[0] == addr(&b.sub[0]) + 0x40);
    CHECK(b.sub[1] == 0u);
    CHECK(b.sub[2] == addr(&b.sub[2]) + 0x20);
    CHECK(b.sub[3] == addr(&b.sub[3]) + 0x8);
    CHECK(b.sub[4] == addr(&b.sub[4]) + 0x18);
    CHECK(b.hdr.ctx_regs == addr(b.ctx));
    CHECK(b.hdr.sh_regs == addr(b.sh));
    CHECK(b.hdr.info == addr(&b.info));
    CHECK(b.hdr.ps_inputs == addr(b.ps));
    CHECK(b.hdr.vs_outputs == 0u);
    CHECK(b.hdr.code_address == code);
}

void setup_create(bool pa_debug = false) {
    resolve_all();
    agc::testing::set_soc_id(kNormalSoc);
    agc::testing::set_kernel_flag(false);
    install_pa_debug(pa_debug);
}

} // namespace

TEST_CASE("sceAgcCreateShader relocates and patches the program address", "[agc][shader]") {
    Env env;
    setup_create();
    CodeBuf code_buf;
    make_code(code_buf);
    const u64 code = addr(code_buf.bytes.data());

    struct StageCase {
        u8 stage;
        u32 lo;
    };
    for (const StageCase sc : {StageCase{0, 0x20c}, StageCase{1, 0x008}, StageCase{2, 0x0c8},
                               StageCase{3, 0x148}, StageCase{6, 0x088}, StageCase{7, 0x108}}) {
        INFO("stage " << int{sc.stage});
        ShaderBlob b;
        make_blob(b, sc.stage, 1, sc.lo);
        Shader *out = kOutSentinel;
        REQUIRE(agc::sceAgcCreateShader(&out, &b.hdr, code) == 0);
        CHECK(out == &b.hdr);
        check_relocated(b, code);
        const u64 a = code + 0x10ull * 256u;
        CHECK(b.sh[1] == RegPair{sc.lo, static_cast<u32>(a >> 8)});
        const u32 hi_add = static_cast<u32>((a >> 40) & 0xffu);
        CHECK(b.sh[2] == RegPair{sc.lo + 1, 0xABCDEF00u | ((0xFFu + hi_add) & 0xffu)});
        CHECK(b.sh[0] == RegPair{0x1234, 5});
        CHECK(b.sh[3] == RegPair{sc.lo, 0x99}); // only the first match is patched
        CHECK(b.ctx[0] == RegPair{0x2d5, 0x2000});
    }
}

TEST_CASE("sceAgcCreateShader HI byte add wraps within 8 bits", "[agc][shader]") {
    Env env;
    setup_create();
    CodeBuf code_buf;
    make_code(code_buf);
    const u64 code = addr(code_buf.bytes.data());
    // Pick an offset (in 256-byte units) that carries the address across a 2^40 boundary, so
    // (addr >> 40) differs from the code's own bits 40..47.
    // AMBIGUOUS: `addr = code + LO.value * 256` read as 64-bit arithmetic (LO.value * 256 can
    // exceed 32 bits).
    const u64 to_boundary = (1ull << 40) - (code & ((1ull << 40) - 1));
    const u64 units = (to_boundary + 255u) / 256u;
    REQUIRE(units <= 0xFFFFFFFFull);
    ShaderBlob b;
    make_blob(b, 0, 1, 0x20c, 4, static_cast<u32>(units));
    Shader *out = kOutSentinel;
    REQUIRE(agc::sceAgcCreateShader(&out, &b.hdr, code) == 0);
    const u64 a = code + units * 256u;
    const u32 hi_add = static_cast<u32>((a >> 40) & 0xffu);
    CHECK(b.sh[1].value == static_cast<u32>(a >> 8));
    CHECK(b.sh[2].value == (0xABCDEF00u | ((0xFFu + hi_add) & 0xffu)));
}

TEST_CASE("sceAgcCreateShader stages without a program-address patch", "[agc][shader]") {
    Env env;
    setup_create();
    CodeBuf code_buf;
    make_code(code_buf);
    const u64 code = addr(code_buf.bytes.data());
    for (u8 stage : {u8{4}, u8{5}, u8{8}, u8{9}, u8{0xff}}) {
        INFO("stage " << int{stage});
        ShaderBlob b;
        make_blob(b, stage, 1, 0x20c);
        Shader *out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == 0);
        CHECK(out == &b.hdr);
        check_relocated(b, code);
        CHECK(b.sh[1] == RegPair{0x20c, 0x10});
        CHECK(b.sh[2] == RegPair{0x20d, 0xABCDEFFFu});
    }
}

TEST_CASE("sceAgcCreateShader program register not found -> 0x8a6c0005", "[agc][shader]") {
    Env env;
    setup_create();
    CodeBuf code_buf;
    make_code(code_buf);
    const u64 code = addr(code_buf.bytes.data());
    SECTION("register absent") {
        ShaderBlob b;
        make_blob(b, 0, 1, 0x008); // stage 0 looks for 0x20c
        Shader *out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == kRegNotFound);
        CHECK(out == kOutSentinel);
        // Relocation and codeAddress happen before the search (behaviour steps 3, 4).
        check_relocated(b, code);
        CHECK(b.sh[1] == RegPair{0x008, 0x10});
    }
    SECTION("numShRegs == 0") {
        ShaderBlob b;
        make_blob(b, 0, 1, 0x20c, 0);
        Shader *out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == kRegNotFound);
        CHECK(out == kOutSentinel);
        CHECK(b.sh[1] == RegPair{0x20c, 0x10});
    }
    SECTION("register only beyond numShRegs") {
        ShaderBlob b;
        make_blob(b, 0, 1, 0x20c, 1); // pair at index 1 is outside [0, 1)
        Shader *out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == kRegNotFound);
        CHECK(out == kOutSentinel);
        CHECK(b.sh[1] == RegPair{0x20c, 0x10});
    }
}

TEST_CASE("sceAgcCreateShader validation order", "[agc][shader]") {
    Env env;
    agc::testing::set_soc_id(0x840fc0u);
    agc::testing::set_kernel_flag(false);
    install_pa_debug(false);
    CodeBuf code_buf;
    make_code(code_buf);
    const u64 code = addr(code_buf.bytes.data());

    auto expect_error = [&](ShaderBlob &b, std::int32_t err) {
        ShaderBlob before;
        std::memcpy(&before, &b, sizeof b);
        Shader *out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == err);
        CHECK(out == kOutSentinel);
        CHECK(std::memcmp(&before, &b, sizeof b) == 0); // validation errors change nothing
    };

    // Not initialised (descriptor 0x45c90 still the sentinel after reset()).
    {
        // Everything wrong: magic wins.
        ShaderBlob b;
        make_blob(b, 0, 0x8000000eu, 0x20c);
        b.hdr.magic = 0x34333232u;
        b.hdr.version = 0x17u;
        b.hdr.code_address = 0x1000;
        expect_error(b, kMagic);
        b.hdr.magic = 0x34333231u;
        expect_error(b, kVersion);
        b.hdr.version = 0x18u;
        expect_error(b, kCreated); // already created is checked before initialisation
        b.hdr.code_address = 0;
        expect_error(b, kNotInit); // before the target and debug checks
    }
    resolve_all();
    {
        ShaderBlob b;
        make_blob(b, 0, 0x8000000eu, 0x20c); // target 14 on SoC 0x840fc0 + debug bit
        expect_error(b, kTarget);            // target before debug-only
        b.hdr.target = 0x80000001u;
        expect_error(b, kDebug);
    }
    {
        install_pa_debug(true);
        ShaderBlob b;
        make_blob(b, 0, 0x80000001u, 0x20c);
        Shader *out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == 0);
        CHECK(out == &b.hdr);
        // Created once: the second call reports "already created".
        out = kOutSentinel;
        CHECK(agc::sceAgcCreateShader(&out, &b.hdr, code) == kCreated);
        CHECK(out == kOutSentinel);
    }
}

TEST_CASE("sceAgcCreateShader target checks (kernel flag, SoC)", "[agc][shader]") {
    Env env;
    resolve_all();
    install_pa_debug(false);
    CodeBuf code_buf;
    make_code(code_buf);
    const u64 code = addr(code_buf.bytes.data());

    struct Case {
        bool kflag;
        u32 soc;
        u32 target;
        bool ok;
    };
    const Case cases[] = {
        // kernel flag clear, ordinary SoC
        {false, kNormalSoc, 0, true},
        {false, kNormalSoc, 9, true},
        {false, kNormalSoc, 10, true},
        {false, kNormalSoc, 11, true},
        {false, kNormalSoc, 12, false},
        {false, kNormalSoc, 13, true},
        {false, kNormalSoc, 14, true},
        {false, kNormalSoc, 15, false},
        {false, kNormalSoc, 16, true},
        {false, kNormalSoc, 0x7fffffffu, true},
        // kernel flag set, ordinary SoC
        {true, kNormalSoc, 9, true},
        {true, kNormalSoc, 10, false},
        {true, kNormalSoc, 11, true},
        {true, kNormalSoc, 12, true},
        {true, kNormalSoc, 13, false},
        {true, kNormalSoc, 14, true},
        {true, kNormalSoc, 15, true},
        // SoC (mainSocId & 0xfffffff0) == 0x840fc0
        {false, 0x840fc0u, 9, true},
        {false, 0x840fc0u, 10, true},
        {false, 0x840fc0u, 11, true},
        {false, 0x840fc0u, 13, false},
        {false, 0x840fc5u, 14, false},
        {false, 0x840fcfu, 16, false},
        {true, 0x840fc0u, 12, true}, // 12 has no SoC check
        {true, 0x840fc0u, 15, false},
        {true, 0x840fc3u, 0x7fffffffu, false},
        // SoC outside the mask: accepted
        {false, 0x840fd0u, 14, true},
        {false, 0x840fe0u, 13, true},
        {true, 0x840f00u, 15, true},
    };
    for (const Case &c : cases) {
        INFO("kflag " << c.kflag << " soc " << std::hex << c.soc << " target " << c.target);
        agc::testing::set_kernel_flag(c.kflag);
        agc::testing::set_soc_id(c.soc);
        ShaderBlob b;
        make_blob(b, 0, c.target, 0x20c);
        Shader *out = kOutSentinel;
        const std::int32_t rc = agc::sceAgcCreateShader(&out, &b.hdr, code);
        if (c.ok) {
            CHECK(rc == 0);
            CHECK(out == &b.hdr);
        } else {
            CHECK(rc == kTarget);
            CHECK(out == kOutSentinel);
            CHECK(b.hdr.code_address == 0u);
        }
    }
}

// =================================================================================================
// Fused shader size / fusing
// =================================================================================================

TEST_CASE("fused shader size, both variants", "[agc][fuse]") {
    Env env;
    Shader first{};
    Shader second{};
    first.num_sh_regs = 3;
    second.num_sh_regs = 9;

    struct Pair {
        u8 a;
        u8 b;
        bool ok;
    };
    for (const Pair pr : {Pair{5, 7, true}, Pair{4, 6, true}, Pair{4, 7, false}, Pair{5, 6, false},
                          Pair{7, 5, false}, Pair{6, 4, false}, Pair{0, 0, false},
                          Pair{2, 3, false}}) {
        INFO("stages " << int{pr.a} << "," << int{pr.b});
        first.stage = pr.a;
        second.stage = pr.b;
        std::array<u64, 2> out64{0x1111, 0x2222};
        agc::FusedShaderSize out{0x3333, 0x4444, 0x5555};
        if (pr.ok) {
            CHECK(agc::agcGetFusedShaderSize64(out64.data(), &first, &second) == 0);
            CHECK(out64 == std::array<u64, 2>{9u * 8u, 4u});
            CHECK(agc::sceAgcGetFusedShaderSize(&out, &first, &second) == 0);
            CHECK(out.size_bytes == 72u);
            CHECK(out.alignment == 4u);
            CHECK(out.unused == 0x5555u); // the next 4 bytes are not written
        } else {
            CHECK(agc::agcGetFusedShaderSize64(out64.data(), &first, &second) == kHalves);
            CHECK(out64 == std::array<u64, 2>{0x1111, 0x2222});
            CHECK(agc::sceAgcGetFusedShaderSize(&out, &first, &second) == kHalves);
            CHECK(out.size_bytes == 0x3333u);
            CHECK(out.alignment == 0x4444u);
            CHECK(out.unused == 0x5555u);
        }
    }
}

namespace {

struct Half {
    Shader hdr;
    std::array<RegPair, 8> sh;
    InfoBlock info;
};

struct FuseRegs {
    u32 x;       // duplicated register
    u32 r1, r2;  // RSRC1/RSRC2
    u32 p;       // program LO
};
constexpr FuseRegs kHsRegs{0x100, 0x10a, 0x10b, 0x148};
constexpr FuseRegs kGsRegs{0x080, 0x08a, 0x08b, 0x0c8};
constexpr u64 kFirstCode = 0x000012ABCDEF0100ull;

// First half (ES/LS-type) and second half (GS/HS) with the given RSRC values.
void make_halves(Half &f, Half &s, bool hs, u32 f_r1, u32 f_r2, u32 o_r1, u32 o_r2, u32 f_stages,
                 u32 s_stages) {
    const FuseRegs &r = hs ? kHsRegs : kGsRegs;
    std::memset(&f, 0, sizeof f);
    std::memset(&s, 0, sizeof s);
    f.sh = {RegPair{r.x, 0x11111111u}, RegPair{r.r1, f_r1}, RegPair{0x50, 0x5050},
            RegPair{r.x, 0x22222222u}, RegPair{r.r2, f_r2}, RegPair{0, 0},
            RegPair{0, 0},             RegPair{0, 0}};
    f.hdr.magic = 0x34333231u;
    f.hdr.version = 0x18u;
    f.hdr.stage = hs ? 5 : 4;
    f.hdr.code_address = kFirstCode;
    f.hdr.extra = 0xDEAD0000ull;
    f.hdr.sh_regs = addr(f.sh.data());
    f.hdr.num_sh_regs = 5;
    f.hdr.info = addr(&f.info);
    f.info.stages = RegPair{0x2d5, f_stages};

    s.sh = {RegPair{r.r1, o_r1},       RegPair{r.x, 0xAAAAAAAAu}, RegPair{r.r2, o_r2},
            RegPair{r.p, 0x11},        RegPair{r.p + 1, 0xAABBCC33u}, RegPair{r.x, 0xBBBBBBBBu},
            RegPair{0x77, 0x88},       RegPair{0xEEEE, 0xEEEE}};
    s.hdr.magic = 0x34333231u;
    s.hdr.version = 0x18u;
    s.hdr.stage = hs ? 7 : 6;
    s.hdr.code_address = 0x5555000ull;
    s.hdr.extra = 0xBEEF0000ull;
    s.hdr.ctx_regs = 0x7777000ull;
    s.hdr.header_bytes = 0x1234;
    s.hdr.code_bytes = 0x777;
    s.hdr.target = 9;
    s.hdr.num_ps_inputs = 3;
    s.hdr.sh_regs = addr(s.sh.data());
    s.hdr.num_sh_regs = 7;
    s.hdr.info = addr(&s.info);
    s.info.stages = RegPair{0x2d5, s_stages};
}

using FuseFn = std::int32_t (*)(Shader *, const Shader *, Shader *, RegPair *);

// Expected fused register list (7 entries) for the given RSRC results.
std::array<RegPair, 7> fused_regs(bool hs, u32 r1, u32 r2) {
    const FuseRegs &r = hs ? kHsRegs : kGsRegs;
    return {RegPair{r.r1, r1},
            RegPair{r.x, 0x11111111u},
            RegPair{r.r2, r2},
            RegPair{r.p, 0xABCDEF01u},     // (uint32)(firstHalf.codeAddress >> 8)
            RegPair{r.p + 1, 0xAABBCC12u}, // low byte = (codeAddress >> 40) & 0xff (assigned)
            RegPair{r.x, 0x22222222u},
            RegPair{0x77, 0x88}};
}

void check_fused_header(const Shader &out, const Half &s, u8 stage, u64 extra, u64 sh_regs) {
    CHECK(out.magic == s.hdr.magic);
    CHECK(out.version == s.hdr.version);
    CHECK(out.stage == stage);
    CHECK(out.extra == extra);
    CHECK(out.code_address == s.hdr.code_address);
    CHECK(out.ctx_regs == s.hdr.ctx_regs);
    CHECK(out.info == s.hdr.info);
    CHECK(out.header_bytes == s.hdr.header_bytes);
    CHECK(out.code_bytes == s.hdr.code_bytes);
    CHECK(out.target == s.hdr.target);
    CHECK(out.num_ps_inputs == s.hdr.num_ps_inputs);
    CHECK(out.num_sh_regs == s.hdr.num_sh_regs);
    CHECK(out.sh_regs == sh_regs);
}

// RSRC inputs shared by the fuse tests.
constexpr u32 kFR1Hs = 0x23300015u; // bits 0..5 = 0x15, bits 28..29 = 2, junk 0x03300000
constexpr u32 kOR1Hs = 0x1C0FF00Au; // bits 0..5 = 0x0A, bits 28..29 = 1
constexpr u32 kFR1Gs = 0x43300015u; // bits 29..30 = 2
constexpr u32 kOR1Gs = 0x2C0FF00Au; // bits 29..30 = 1
constexpr u32 kFR2 = 0xF0F6002Cu;   // top 0xF, bits 1..5 = 0x16, bit 27 = 0, bits 16..17 = 2, bit 18 = 1
constexpr u32 kOR2 = 0x0801AB03u;   // top 0, bit 27 = 1, bits 1..5 = 1, bits 16..17 = 1, bit 18 = 0

} // namespace

TEST_CASE("sceAgcFuseShaderHalves HS and GS", "[agc][fuse]") {
    Env env;
    resolve_all();
    SECTION("HS with register buffer") {
        Half f, s;
        make_halves(f, s, true, kFR1Hs, kFR2, kOR1Hs, kOR2, 0x00600000u, 0x00200000u);
        const auto s_before = s.sh;
        Shader out{};
        std::array<RegPair, 8> buf{};
        buf.fill(RegPair{0xCDCDCDCD, 0xCDCDCDCD});
        REQUIRE(agc::sceAgcFuseShaderHalves(&out, &f.hdr, &s.hdr, buf.data()) == 0);
        check_fused_header(out, s, 3, f.hdr.extra, addr(buf.data()));
        // R1: bits 0..5 = max(0x15, 0x0A); bits 28..29 = max(2, 1); rest from out.
        // R2: top = max(0xF, 0); bits 1..5 and 27 from F; HS: bits 16..18 not touched.
        const auto want = fused_regs(true, 0x2C0FF015u, 0xF001AB2Du);
        for (std::size_t i = 0; i < 7; ++i) {
            INFO("pair " << i);
            CHECK(buf[i] == want[i]);
        }
        CHECK(buf[7] == RegPair{0xCDCDCDCD, 0xCDCDCDCD});
        CHECK(s.sh == s_before); // second half untouched
    }
    SECTION("GS in place (no register buffer)") {
        Half f, s;
        make_halves(f, s, false, kFR1Gs, kFR2, kOR1Gs, kOR2, 0x00600000u, 0x00400000u);
        Shader out{};
        REQUIRE(agc::sceAgcFuseShaderHalves(&out, &f.hdr, &s.hdr, nullptr) == 0);
        check_fused_header(out, s, 2, f.hdr.extra, addr(s.sh.data()));
        // R1: bits 29..30 = max(2, 1). R2: also bits 16..17 = max(2, 1), bit 18 = F's (1).
        const auto want = fused_regs(false, 0x4C0FF015u, 0xF006AB2Du);
        for (std::size_t i = 0; i < 7; ++i) {
            INFO("pair " << i);
            CHECK(s.sh[i] == want[i]);
        }
        CHECK(s.sh[7] == RegPair{0xEEEE, 0xEEEE});
    }
}

TEST_CASE("agcFuseShaderHalves2 (fd5Bp5tGTgo) scratch arithmetic", "[agc][fuse]") {
    Env env;
    resolve_all();
    SECTION("HS, scratch top from the formula") {
        // vF = 0x15*8+8 = 176, vO = 0x0A*8+8 = 88, vMax = 176; a = 44 + 0*8 = 44,
        // b = 88 + 15*8 = 208; m = 208 > vMax/2 = 88 -> top = ((208-44+7) >> 6) & 0xf = 2.
        Half f, s;
        make_halves(f, s, true, kFR1Hs, kFR2, kOR1Hs, kOR2, 0x00200000u, 0x00200000u);
        Shader out{};
        std::array<RegPair, 8> buf{};
        REQUIRE(agc::agcFuseShaderHalves2(&out, &f.hdr, &s.hdr, buf.data()) == 0);
        check_fused_header(out, s, 3, 0, addr(buf.data())); // extra cleared
        const auto want = fused_regs(true, 0x2C0FF015u, 0x2001AB2Du);
        for (std::size_t i = 0; i < 7; ++i) {
            INFO("pair " << i);
            CHECK(buf[i] == want[i]);
        }
    }
    SECTION("HS, vMax/2 >= m clears the top bits") {
        // F.R2 top 0, out.R2 top 1: a = 44 + 8 = 52, b = 88 + 0 = 88; m = 88 = vMax/2 -> top 0.
        Half f, s;
        make_halves(f, s, true, kFR1Hs, kFR2 & 0x0FFFFFFFu, kOR1Hs, kOR2 | 0x10000000u,
                    0x00200000u, 0x00200000u);
        Shader out{};
        std::array<RegPair, 8> buf{};
        REQUIRE(agc::agcFuseShaderHalves2(&out, &f.hdr, &s.hdr, buf.data()) == 0);
        CHECK(buf[2] == RegPair{0x10b, 0x0001AB2Du});
        CHECK(buf[0] == RegPair{0x10a, 0x2C0FF015u});
    }
    SECTION("GS in place") {
        Half f, s;
        make_halves(f, s, false, kFR1Gs, kFR2, kOR1Gs, kOR2, 0x00400000u, 0x00600000u);
        Shader out{};
        REQUIRE(agc::agcFuseShaderHalves2(&out, &f.hdr, &s.hdr, nullptr) == 0);
        check_fused_header(out, s, 2, 0, addr(s.sh.data()));
        const auto want = fused_regs(false, 0x4C0FF015u, 0x2006AB2Du);
        for (std::size_t i = 0; i < 7; ++i) {
            INFO("pair " << i);
            CHECK(s.sh[i] == want[i]);
        }
    }
}

TEST_CASE("shader fusing errors", "[agc][fuse]") {
    Env env;
    resolve_all();
    for (FuseFn fn : {static_cast<FuseFn>(agc::sceAgcFuseShaderHalves),
                      static_cast<FuseFn>(agc::agcFuseShaderHalves2)}) {
        {
            INFO("wrong stage pair: nothing written");
            Half f, s;
            make_halves(f, s, true, kFR1Hs, kFR2, kOR1Hs, kOR2, 0x00200000u, 0x00200000u);
            s.hdr.stage = 6; // (5,6)
            Shader out;
            std::memset(&out, 0xCD, sizeof out);
            Shader out_before;
            std::memcpy(&out_before, &out, sizeof out);
            const auto s_before = s.sh;
            std::array<RegPair, 8> buf{};
            CHECK(fn(&out, &f.hdr, &s.hdr, buf.data()) == kHalves);
            CHECK(std::memcmp(&out, &out_before, sizeof out) == 0);
            CHECK(s.sh == s_before);
            CHECK(buf == std::array<RegPair, 8>{});
        }
        {
            INFO("HS stage-enable bit 21 mismatch: out partly written");
            Half f, s;
            make_halves(f, s, true, kFR1Hs, kFR2, kOR1Hs, kOR2, 0x00200000u, 0x00000000u);
            Shader out;
            std::memset(&out, 0xCD, sizeof out);
            const auto s_before = s.sh;
            std::array<RegPair, 8> buf{};
            CHECK(fn(&out, &f.hdr, &s.hdr, buf.data()) == kHalves);
            CHECK(out.stage == 3);
            CHECK(out.magic == s.hdr.magic);
            CHECK(out.code_address == s.hdr.code_address);
            CHECK(s.sh == s_before);
            CHECK(buf == std::array<RegPair, 8>{}); // register copy comes after the check
        }
        {
            INFO("GS stage-enable bit 22 mismatch");
            Half f, s;
            make_halves(f, s, false, kFR1Gs, kFR2, kOR1Gs, kOR2, 0x00000000u, 0x00400000u);
            Shader out{};
            const auto s_before = s.sh;
            CHECK(fn(&out, &f.hdr, &s.hdr, nullptr) == kHalves);
            CHECK(out.stage == 2);
            CHECK(s.sh == s_before);
        }
        {
            INFO("only the stage's own bit is compared");
            Half f, s;
            // HS: bit 22 differs, bit 21 equal -> fine. GS: bit 21 differs, bit 22 equal -> fine.
            make_halves(f, s, true, kFR1Hs, kFR2, kOR1Hs, kOR2, 0x00600000u, 0x00200000u);
            Shader out{};
            CHECK(fn(&out, &f.hdr, &s.hdr, nullptr) == 0);
            make_halves(f, s, false, kFR1Gs, kFR2, kOR1Gs, kOR2, 0x00400000u, 0x00600000u);
            CHECK(fn(&out, &f.hdr, &s.hdr, nullptr) == 0);
        }
    }
}

// =================================================================================================
// Interpolant mappings (H5 variants A/B/C, H5b defaults)
// =================================================================================================

namespace {

// vs outputs: semantic in bits 0..7, slot in bits 8..12, bits 20/21 used by the special path.
const std::array<u32, 4> kVsOut{
    0x00000305u, // sem 5, slot 3
    0x00301A07u, // sem 7, slot 0x1A, bits 20+21
    0x00100C09u, // sem 9, slot 0x0C, bit 20
    0x00000F05u, // sem 5 again (first match wins)
};

// ps inputs (see each expected value's derivation below).
const std::array<u32, 8> kPsIn{
    0x21000005u, // A normal: sem 5 found, bit24, bits28..29 = 2
    0x10400005u, // B normal: sem 5 found, bit22, bits28..29 = 1
    0x30400042u, // C normal: not found, bit22, bits28..29 = 3
    0x00000007u, // D normal: sem 7 found, flags 0
    0xE1100007u, // E special s=1: sem 7, bit24, bits28..29 = 2, bits30..31 = 3
    0x90600009u, // F special s=2: sem 9, bit22, bits28..29 = 1, bits30..31 = 2
    0x41300055u, // G special s=3: not found, bit24, bits30..31 = 1
    0x40200066u, // H special s=2: not found, bits30..31 = 1
};

// Expected PS input control values with base 0.
//  A: slot 3 | bit5 (flat = bit24) | bits8..9 = 2 | bit10 = bit24                -> 0x623
//  B: slot 3 | bits8..9 = 1 | bit10 (bit22); bit5: A forces 1 (bit22), B/C = bit24 = 0
//  C: not found: bit5 = 1, bits8..9 = 3                                          -> 0x320
//  D: slot 0x1A, everything else 0                                               -> 0x1A
//  E: t = vs & ps = 0x00100007 (t20 = 1, t21 = 0): bits24..25 = 1, bit19, bit5 = 0, bit20 = 1,
//     bits21..22 = 3, bits8..9 = 2, slot 0x1A, bit10 = 1                          -> 0x0178061A
//  F: t = 0x9 (t20 = t21 = 0). A/B: bits24..25 = 2, bit19, bit5 = 1, bit20 = 1, bits21..22 = 2,
//     bits8..9 = 1, slot 0x0C, bit10 = 1 -> 0x0258052C. C (s == 2): bit20 = 0, bit5 = !t21 = 1,
//     bits21..22 = 2 and bits8..9 = psDesc bits30..31 = 2                         -> 0x0248062C
//  G: not found, s = 3: bits24..25 = 3, bit19, bit5 = 1, bit20 = 1, bits21..22 = 1 -> 0x03380020
//  H: not found, s = 2. A/B: bits24..25 = 2, bit19, bit5, bit20, bits21..22 = 1 -> 0x02380020;
//     C: bit20 = 0, bit5 = 1, bits21..22 = 1, bits8..9 = 1                        -> 0x02280120
const std::array<u32, 8> kExpectA{0x623, 0x523, 0x320, 0x1A, 0x0178061A, 0x0258052C, 0x03380020,
                                  0x02380020};
const std::array<u32, 8> kExpectB{0x623, 0x503, 0x320, 0x1A, 0x0178061A, 0x0258052C, 0x03380020,
                                  0x02380020};
// AMBIGUOUS: variant C's s == 2 special path (bits 8..9 = psDesc bits 30..31) is marked UNSURE in
// the description (hand-decoded); the update twin (vieBRwlh1Lw) is assumed bit-identical.
const std::array<u32, 8> kExpectC{0x623, 0x503, 0x320, 0x1A, 0x0178061A, 0x0248062C, 0x03380020,
                                  0x02280120};

constexpr RegPair kJunk{0xDEADBEEFu, 0xDEADBEEFu};

struct VsPs {
    Shader vs{};
    Shader ps{};
    VsPs(u32 num_ps = 8) {
        vs.vs_outputs = addr(kVsOut.data());
        vs.num_vs_outputs = 4;
        ps.ps_inputs = addr(kPsIn.data());
        ps.num_ps_inputs = num_ps;
    }
};

using MapFn = std::int32_t (*)(RegPair *, const Shader *, const Shader *);

void check_mapped(const std::array<RegPair, 33> &out, const std::array<u32, 8> &expect, u32 n) {
    for (u32 i = 0; i < n; ++i) {
        INFO("slot " << i << " ps " << std::hex << kPsIn[i]);
        CHECK(out[i] == RegPair{0x191 + i, expect[i]});
    }
}

void check_defaults(const std::array<RegPair, 33> &out, u32 from, u32 base = 0) {
    for (u32 i = from; i < 32; ++i) {
        INFO("slot " << i);
        CHECK(out[i] == RegPair{0x191 + i, (base & ~0x1fu) + i});
    }
    CHECK(out[32] == kJunk);
}

} // namespace

TEST_CASE("create interpolant mapping, variants A/B/C", "[agc][interp]") {
    Env env;
    resolve_all();
    struct Variant {
        MapFn fn;
        const std::array<u32, 8> *expect;
        const char *name;
    };
    const Variant variants[] = {
        {agc::sceAgcCreateInterpolantMapping, &kExpectA, "A"},
        {agc::agcCreateInterpolantMappingB, &kExpectB, "B"},
        {agc::agcCreateInterpolantMappingC, &kExpectC, "C"},
    };
    for (const Variant &v : variants) {
        INFO("variant " << v.name);
        VsPs sh;
        std::array<RegPair, 33> out;
        out.fill(kJunk);
        CHECK(v.fn(out.data(), &sh.vs, &sh.ps) == 0);
        check_mapped(out, *v.expect, 8);
        check_defaults(out, 8);

        // NULL pixel shader: 32 defaults.
        out.fill(kJunk);
        CHECK(v.fn(out.data(), &sh.vs, nullptr) == 0);
        check_defaults(out, 0);

        // No PS inputs: 32 defaults.
        VsPs none(0);
        out.fill(kJunk);
        CHECK(v.fn(out.data(), &none.vs, &none.ps) == 0);
        check_defaults(out, 0);
    }
}

TEST_CASE("update interpolant mapping, variants A/B/C", "[agc][interp]") {
    Env env;
    resolve_all();
    struct Variant {
        MapFn fn;
        const std::array<u32, 8> *expect;
        const char *name;
    };
    const Variant variants[] = {
        {agc::sceAgcUpdateInterpolantMapping, &kExpectA, "A"},
        {agc::agcUpdateInterpolantMappingB, &kExpectB, "B"},
        {agc::agcUpdateInterpolantMappingC, &kExpectC, "C"},
    };
    for (const Variant &v : variants) {
        INFO("variant " << v.name);
        VsPs sh;
        std::array<RegPair, 33> out;
        out.fill(kJunk);
        CHECK(v.fn(out.data(), &sh.vs, &sh.ps) == 0);
        check_mapped(out, *v.expect, 8);
        for (std::size_t i = 8; i < out.size(); ++i) {
            CHECK(out[i] == kJunk); // no default fill
        }

        VsPs three(3);
        out.fill(kJunk);
        CHECK(v.fn(out.data(), &three.vs, &three.ps) == 0);
        check_mapped(out, *v.expect, 3);
        CHECK(out[3] == kJunk);

        VsPs none(0);
        out.fill(kJunk);
        CHECK(v.fn(out.data(), &none.vs, &none.ps) == 0);
        for (const RegPair &p : out) {
            CHECK(p == kJunk);
        }
    }
}

TEST_CASE("interpolant mapping keeps the other bits of the PS input control default",
          "[agc][interp]") {
    Env env;
    resolve_all();
    set_desc(0x45db8, 0x191, 0xFFFFFFFFu); // a target whose default has every bit set
    const std::array<u32, 2> ps_in{kPsIn[0], kPsIn[4]};
    Shader vs{};
    vs.vs_outputs = addr(kVsOut.data());
    vs.num_vs_outputs = 4;
    Shader ps{};
    ps.ps_inputs = addr(ps_in.data());
    ps.num_ps_inputs = 2;
    std::array<RegPair, 33> out;
    out.fill(kJunk);
    CHECK(agc::sceAgcCreateInterpolantMapping(out.data(), &vs, &ps) == 0);
    // Normal path: bits 0..5 and 8..10 replaced, every other bit from the default.
    CHECK(out[0] == RegPair{0x191, 0xFFFFFEE3u});
    // AMBIGUOUS: special path read as assignments of bits 0..5, 8..10, 19..22 and 24..25 over the
    // default (all other bits from the default).
    CHECK(out[1] == RegPair{0x192, 0xFDFFFEDAu});
    // H5b: (base & ~0x1f) + i
    check_defaults(out, 2, 0xFFFFFFFFu);
}

// =================================================================================================
// Prim state and linking
// =================================================================================================

namespace {

InfoBlock make_info(u32 uc0, u32 stages, u32 gs_out, u32 uc1) {
    InfoBlock b{};
    b.uc0 = RegPair{0x25b, uc0};
    b.stages = RegPair{0x2d5, stages};
    b.unused[0] = RegPair{0xEEEE, 0xEEEE};
    b.unused[1] = RegPair{0xEEEE, 0xEEEE};
    b.gs_out = RegPair{0x29b, gs_out};
    b.uc1 = RegPair{0x262, uc1};
    return b;
}

} // namespace

TEST_CASE("sceAgcCreatePrimState", "[agc][prim]") {
    Env env;
    resolve_all();
    bc5::reimpl::set_firmware_data(&g_prim_table);

    InfoBlock main_info = make_info(0x1111, 0x2000, 0x3333, 0x4444);
    InfoBlock aux_info = make_info(0x5555, 0x0040, 0x7777, 0x8888);
    Shader main{};
    main.info = addr(&main_info);
    Shader aux{};
    aux.info = addr(&aux_info);

    agc::PrimStateCx cx{kJunk, kJunk};
    agc::PrimStateUc uc{{kJunk, kJunk, kJunk}};

    SECTION("main only, GS out prim type from the table") {
        for (u32 p : {1u, 4u, 5u, 17u, 18u, 0u, 19u, 0x45u}) {
            INFO("primType " << p);
            CHECK(agc::sceAgcCreatePrimState(&cx, &uc, nullptr, &main, p) == 0);
            CHECK(cx.stages_enable == RegPair{0x2d5, 0x2000});
            CHECK(cx.gs_out_prim_type == RegPair{0x29b, synthetic_class(p)});
            CHECK(uc.pairs[0] == RegPair{0x25b, 0x1111});
            CHECK(uc.pairs[1] == RegPair{0x262, 0x4444});
            CHECK(uc.pairs[2] == RegPair{0x242, p}); // primType not masked
        }
    }
    SECTION("default GS out prim value keeps bits 3..31") {
        set_desc(0x45a30, 0x29b, 0x12345672u);
        set_desc(0x45a58, 0x242, 0xFFFFFFFFu);
        CHECK(agc::sceAgcCreatePrimState(&cx, &uc, nullptr, &main, 4) == 0);
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 0x12345674u});
        CHECK(uc.pairs[2] == RegPair{0x242, 0xFFFFFFE4u});
    }
    SECTION("bit 5 set: GS out prim pair from the shader") {
        main_info.stages.value = 0x2020;
        CHECK(agc::sceAgcCreatePrimState(&cx, &uc, nullptr, &main, 4) == 0);
        CHECK(cx.stages_enable == RegPair{0x2d5, 0x2020});
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 0x3333});
        // aux ORs in; result bit 5 set -> main pair stays
        CHECK(agc::sceAgcCreatePrimState(&cx, &uc, &aux, &main, 4) == 0);
        CHECK(cx.stages_enable == RegPair{0x2d5, 0x2060});
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 0x3333});
        CHECK(uc.pairs[1] == RegPair{0x262, 0x8888});
    }
    SECTION("aux with bit 5 clear: aux GS out prim pair") {
        CHECK(agc::sceAgcCreatePrimState(&cx, &uc, &aux, &main, 4) == 0);
        CHECK(cx.stages_enable == RegPair{0x2d5, 0x2040});
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 0x7777});
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x1111});
        CHECK(uc.pairs[1] == RegPair{0x262, 0x8888});
        CHECK(uc.pairs[2] == RegPair{0x242, 4});
    }
    SECTION("aux setting bit 5: table value stays") {
        aux_info.stages.value = 0x20;
        CHECK(agc::sceAgcCreatePrimState(&cx, &uc, &aux, &main, 4) == 0);
        CHECK(cx.stages_enable == RegPair{0x2d5, 0x2020});
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 4});
    }
    SECTION("NULL outputs") {
        CHECK(agc::sceAgcCreatePrimState(nullptr, &uc, nullptr, &main, 3) == 0);
        CHECK(uc.pairs[2] == RegPair{0x242, 3});
        CHECK(agc::sceAgcCreatePrimState(&cx, nullptr, nullptr, &main, 3) == 0);
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 3});
        CHECK(agc::sceAgcCreatePrimState(nullptr, nullptr, &aux, &main, 3) == 0);
    }
}

TEST_CASE("prim type class without firmware data falls back to 2", "[agc][prim]") {
    Env env;
    resolve_all();
    // Documented deviation of the re-creation: no module file -> class 2 for every primType.
    InfoBlock main_info = make_info(0x1111, 0x2000, 0x3333, 0x4444);
    Shader main{};
    main.info = addr(&main_info);
    agc::PrimStateCx cx{kJunk, kJunk};
    for (u32 p : {1u, 4u, 18u}) {
        CHECK(agc::sceAgcCreatePrimState(&cx, nullptr, nullptr, &main, p) == 0);
        CHECK(cx.gs_out_prim_type == RegPair{0x29b, 2});
    }
    cx.gs_out_prim_type = RegPair{0x29b, 0xFFFFFFFFu};
    CHECK(agc::sceAgcUpdatePrimState(&cx, nullptr, 1) == 0);
    CHECK(cx.gs_out_prim_type.value == 0xFFFFFFFAu);
}

TEST_CASE("sceAgcUpdatePrimState", "[agc][prim]") {
    Env env;
    resolve_all();
    bc5::reimpl::set_firmware_data(&g_prim_table);

    struct Case {
        u32 stages;
        bool updates;
    };
    for (const Case c : {Case{0x2000, true}, Case{0x2004, false}, Case{0x2020, false},
                         Case{0x2024, false}, Case{0x2100, true}, Case{0xFFFFFF00u, true},
                         Case{0x0000001Bu, true}}) {
        INFO("stages " << std::hex << c.stages);
        agc::PrimStateCx cx{RegPair{0x2d5, c.stages}, RegPair{0x29b, 0xABCDEF0Fu}};
        CHECK(agc::sceAgcUpdatePrimState(&cx, nullptr, 4) == 0);
        CHECK(cx.stages_enable == RegPair{0x2d5, c.stages});
        CHECK(cx.gs_out_prim_type ==
              RegPair{0x29b, c.updates ? 0xABCDEF0Cu : 0xABCDEF0Fu}); // T(4) = 4
    }
    {
        agc::PrimStateCx cx{RegPair{0x2d5, 0}, RegPair{0x29b, 0xABCDEF0Fu}};
        CHECK(agc::sceAgcUpdatePrimState(&cx, nullptr, 18) == 0);
        CHECK(cx.gs_out_prim_type.value == 0xABCDEF0Bu); // T(18) = 3
        CHECK(agc::sceAgcUpdatePrimState(&cx, nullptr, 19) == 0);
        CHECK(cx.gs_out_prim_type.value == 0xABCDEF0Au); // out of range -> 2
        CHECK(agc::sceAgcUpdatePrimState(&cx, nullptr, 0) == 0);
        CHECK(cx.gs_out_prim_type.value == 0xABCDEF0Au);
        CHECK(agc::sceAgcUpdatePrimState(&cx, nullptr, 5) == 0);
        CHECK(cx.gs_out_prim_type.value == 0xABCDEF08u); // T(5) = 0
    }
    {
        agc::PrimStateUc uc{{RegPair{0x25b, 1}, RegPair{0x262, 2}, RegPair{0x242, 0x12345678u}}};
        CHECK(agc::sceAgcUpdatePrimState(nullptr, &uc, 0x123) == 0);
        CHECK(uc.pairs[0] == RegPair{0x25b, 1});
        CHECK(uc.pairs[1] == RegPair{0x262, 2});
        CHECK(uc.pairs[2] == RegPair{0x242, 0x12345763u}); // (v & ~0x1f) | primType, unmasked
        CHECK(agc::sceAgcUpdatePrimState(nullptr, nullptr, 3) == 0);
    }
}

TEST_CASE("sceAgcLinkShaders", "[agc][link]") {
    Env env;
    resolve_all();
    bc5::reimpl::set_firmware_data(&g_prim_table);
    agc::testing::set_soc_id(kNormalSoc);
    // Distinct uconfig defaults so default pairs are visible.
    set_desc(0x458c8, 0x25b, 0x9);
    set_desc(0x458f0, 0x262, 0xA);

    InfoBlock main_info = make_info(0x1111, 0x2000, 0x3333, 0x4444);
    InfoBlock aux_info = make_info(0x5555, 0x0040, 0x7777, 0x8888);
    // AMBIGUOUS: the interpolants are built from mainShader's vsOutputs ("exactly as
    // nid_dbOlWdppb4o", whose vsShader argument the link call does not have otherwise).
    Shader main{};
    main.info = addr(&main_info);
    main.vs_outputs = addr(kVsOut.data());
    main.num_vs_outputs = 4;
    Shader aux{};
    aux.info = addr(&aux_info);
    Shader ps{};
    ps.ps_inputs = addr(kPsIn.data());
    ps.num_ps_inputs = 8;

    agc::LinkOutput out;
    auto reset_out = [&] {
        for (RegPair &p : out.interpolants) {
            p = kJunk;
        }
        out.prim = agc::PrimStateCx{kJunk, kJunk};
    };
    agc::PrimStateUc uc{{kJunk, kJunk, kJunk}};

    SECTION("main + ps, no aux") {
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, &uc, nullptr, &main, &ps, 4) == 0);
        for (u32 i = 0; i < 8; ++i) {
            INFO("slot " << i);
            CHECK(out.interpolants[i] == RegPair{0x191 + i, kExpectA[i]});
        }
        for (u32 i = 8; i < 32; ++i) {
            CHECK(out.interpolants[i] == RegPair{0x191 + i, i});
        }
        CHECK(out.prim.stages_enable == RegPair{0x2d5, 0x2000});
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 4});
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x1111});
        CHECK(uc.pairs[1] == RegPair{0x262, 0x4444});
        CHECK(uc.pairs[2] == RegPair{0x242, 4});
    }
    SECTION("NULL pixel shader: 32 default interpolants") {
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, nullptr, nullptr, &main, nullptr, 1) == 0);
        for (u32 i = 0; i < 32; ++i) {
            CHECK(out.interpolants[i] == RegPair{0x191 + i, i});
        }
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 1});
    }
    SECTION("main with bit 5 set") {
        main_info.stages.value = 0x2020;
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, nullptr, nullptr, &main, &ps, 4) == 0);
        CHECK(out.prim.stages_enable == RegPair{0x2d5, 0x2020});
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 0x3333});
        CHECK(out.interpolants[0] == RegPair{0x191, kExpectA[0]});
    }
    SECTION("aux shader") {
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, &uc, &aux, &main, &ps, 4) == 0);
        CHECK(out.prim.stages_enable == RegPair{0x2d5, 0x2040});
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 0x7777});
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x1111});
        CHECK(uc.pairs[1] == RegPair{0x262, 0x8888});
        aux_info.stages.value = 0x20;
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, &uc, &aux, &main, &ps, 4) == 0);
        CHECK(out.prim.stages_enable == RegPair{0x2d5, 0x2020});
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 4});
    }
    SECTION("no main shader: defaults, interpolants untouched") {
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, &uc, nullptr, nullptr, &ps, 7) == 0);
        CHECK(out.prim.stages_enable == RegPair{0x2d5, 0x2000});
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 2});
        for (const RegPair &p : out.interpolants) {
            CHECK(p == kJunk);
        }
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x9});
        CHECK(uc.pairs[1] == RegPair{0x262, 0xA});
        CHECK(uc.pairs[2] == RegPair{0x242, 7});
        // aux alone still ORs in and supplies its pair when bit 5 stays clear
        reset_out();
        CHECK(agc::sceAgcLinkShaders(&out, &uc, &aux, nullptr, nullptr, 7) == 0);
        CHECK(out.prim.stages_enable == RegPair{0x2d5, 0x2040});
        CHECK(out.prim.gs_out_prim_type == RegPair{0x29b, 0x7777});
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x9});
        CHECK(uc.pairs[1] == RegPair{0x262, 0x8888});
    }
    SECTION("uconfig only, primType unmasked") {
        set_desc(0x45a58, 0x242, 0xFFFFFFFFu);
        CHECK(agc::sceAgcLinkShaders(nullptr, &uc, nullptr, &main, &ps, 0x45) == 0);
        CHECK(uc.pairs[2] == RegPair{0x242, 0xFFFFFFE5u});
        CHECK(agc::sceAgcLinkShaders(nullptr, nullptr, nullptr, &main, &ps, 1) == 0);
    }
    SECTION("socId 0x840f00: uc[1] = uc[0]'s source pair") {
        agc::testing::set_soc_id(0x840f00u);
        CHECK(agc::sceAgcLinkShaders(nullptr, &uc, &aux, &main, nullptr, 2) == 0);
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x1111});
        CHECK(uc.pairs[1] == RegPair{0x25b, 0x1111});
        CHECK(agc::sceAgcLinkShaders(nullptr, &uc, &aux, nullptr, nullptr, 2) == 0);
        CHECK(uc.pairs[0] == RegPair{0x25b, 0x9});
        CHECK(uc.pairs[1] == RegPair{0x25b, 0x9});
        agc::testing::set_soc_id(0x840f01u); // exact match only
        CHECK(agc::sceAgcLinkShaders(nullptr, &uc, &aux, &main, nullptr, 2) == 0);
        CHECK(uc.pairs[1] == RegPair{0x262, 0x8888});
    }
}

// =================================================================================================
// GS oversubscription
// =================================================================================================

namespace {

struct GsShader {
    Shader hdr{};
    std::array<RegPair, 6> ctx{};
    InfoBlock info{};
};

// A = 0x291 (bits 11..21), B = 0x2d3 (bits 0..8), C = 0x1b1, D = 0x207 (bits 21..23),
// E = 0x1ff (bits 0..9). Junk bits outside the fields used are set on purpose.
void make_gs(GsShader &g, u32 c_reg, u32 d_reg, bool stages_bit22) {
    g.ctx = {RegPair{0x2d3, 0x00000E03u},  // B & 0x1ff = 3
             RegPair{0x291, 0x004057FFu},  // (A >> 11) & 0x7ff = 10
             RegPair{0x207, d_reg},
             RegPair{0x1b1, c_reg},
             RegPair{0x1ff, 0x0000FC40u},  // E & 0x3ff = 0x40
             RegPair{0x010, 0x10}};
    g.hdr.ctx_regs = addr(g.ctx.data());
    g.hdr.num_ctx_regs = 6;
    g.info = make_info(0, stages_bit22 ? 0x00400000u : 0u, 0, 0);
    g.hdr.info = addr(&g.info);
}

} // namespace

TEST_CASE("sceAgcGetGsOversubscription budget 0 and 0xffffffff", "[agc][gs]") {
    Env env;
    resolve_all();
    set_desc(0x45f08, 0x260, 0x80000800u); // V0
    set_desc(0x45f30, 0x081, 0x01000001u); // V1
    GsShader g;
    make_gs(g, 0x10F, 0x01700000u, true);
    std::array<RegPair, 2> out{kJunk, kJunk};
    CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0, 0.5f) == 0);
    CHECK(out[0] == RegPair{0x260, 0x80000800u});
    CHECK(out[1] == RegPair{0x081, 0x01000001u});
    out = {kJunk, kJunk};
    CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0xFFFFFFFFu, 0.5f) == 0);
    CHECK(out[0] == RegPair{0x260, 0x80000FFFu}); // V0 | 0x7ff
    CHECK(out[1] == RegPair{0x081, 0x017F0001u}); // V1 | 0x7f0000
}

TEST_CASE("sceAgcGetGsOversubscription computed cases", "[agc][gs]") {
    Env env;
    resolve_all();
    std::array<RegPair, 2> out{kJunk, kJunk};
    GsShader g;

    SECTION("upper branch (v >= lowB), half = 0") {
        // y = (0x40+31)>>5 = 2; x = (3*10+31)>>5 = 1; m = 2, m1 = 2; k = 1+1+1 = 3 (D bits 21,22);
        // c = ((C>>2)&0xf)*2+2 = 8 (C = 0x10F, bit 7 clear).
        // lowA = (0x800/8/2)*2 = 256; lowB = ((0x80/3)*4/2)*2 = 168; highA = (0x1000/8/2)*2 = 512;
        // highB = (((0x17e/3)*4)/2)*2 = 508; lo = 168; cap = min(512, 508, 0x8000>>5, 0x400) = 508;
        // span = 340; v = 340*0.5 + 168 = 338 >= lowB: r = ((338-168)*0x7f)/(508-168) = 63.
        make_gs(g, 0x10F, 0x01700000u, true);
        CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0x8000, 0.5f) == 0);
        CHECK(out[0] == RegPair{0x260, 0x7FFu});
        CHECK(out[1] == RegPair{0x081, 63u << 16});
    }
    SECTION("budget limits the cap") {
        // As above with budget 0x2800: cap = min(512, 508, 320, 0x400) = 320; span = 152;
        // v = 320 (fraction 1); r = (152*0x7f)/340 = 56.
        make_gs(g, 0x10F, 0x01700000u, true);
        CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0x2800, 1.0f) == 0);
        CHECK(out[0] == RegPair{0x260, 0x7FFu});
        CHECK(out[1] == RegPair{0x081, 56u << 16});
    }
    SECTION("half = 1 (stages-enable bit 22 clear)") {
        // m = 2>>1 = 1 = m1: lowA = 128, lowB = 84, highA = 256, highB = 254; lo = 84;
        // cap = min(256, 254, 0x8000>>6, 0x400) = 254; v = 254: r = (170*0x7f)/170 = 0x7f.
        make_gs(g, 0x10F, 0x01700000u, false);
        CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0x8000, 1.0f) == 0);
        CHECK(out[0] == RegPair{0x260, 0x7FFu});
        CHECK(out[1] == RegPair{0x081, 0x7Fu << 16});
    }
    SECTION("lower branch (lo < v < lowB), non-zero defaults") {
        // C = 0x3C: c = 15*2+2 = 32; D = 0: k = 1. lowA = (0x800/32/2)*2 = 64;
        // lowB = ((0x80*4)/2)*2 = 512; highA = (0x1000/32/2)*2 = 128; highB = ((0x17e*4)/2)*2 = 1528;
        // lo = 64; cap = 128; span = 64; v = 64*0.25 + 64 = 80 < lowB:
        // r = min(((80-64) << 10) / (128-64), 0x400) = 256; f = 255;
        // out0 = (V0 & 0xfffff800) + 1 + 255*2; out1 = V1 | 0x7f0000.
        set_desc(0x45f08, 0x260, 0x80000ABCu);
        set_desc(0x45f30, 0x081, 0x01000001u);
        make_gs(g, 0x3C, 0, true);
        CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0x8000, 0.25f) == 0);
        CHECK(out[0] == RegPair{0x260, 0x800009FFu});
        CHECK(out[1] == RegPair{0x081, 0x017F0001u});
    }
    SECTION("upper branch keeps the other bits of the defaults") {
        set_desc(0x45f08, 0x260, 0x80000ABCu);
        set_desc(0x45f30, 0x081, 0xFFFFFFFFu);
        make_gs(g, 0x10F, 0x01700000u, true);
        CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0x8000, 0.5f) == 0);
        CHECK(out[0] == RegPair{0x260, 0x80000FFFu});
        CHECK(out[1] == RegPair{0x081, 0xFFBFFFFFu}); // (V1 & 0xff80ffff) | (63 << 16)
    }
    SECTION("v <= lo keeps the defaults") {
        set_desc(0x45f08, 0x260, 0x12345678u);
        set_desc(0x45f30, 0x081, 0x9ABCDEF0u);
        make_gs(g, 0x10F, 0x01700000u, true);
        CHECK(agc::sceAgcGetGsOversubscription(out.data(), &g.hdr, 0x8000, 0.0f) == 0);
        CHECK(out[0] == RegPair{0x260, 0x12345678u});
        CHECK(out[1] == RegPair{0x081, 0x9ABCDEF0u});
    }
}

// =================================================================================================
// agcGetShaderExportFlag, exported word, export table
// =================================================================================================

TEST_CASE("agcGetShaderExportFlag (ICkECTBxrMw)", "[agc][shader]") {
    Env env;
    std::array<RegPair, 4> ctx{RegPair{0x100, 2}, RegPair{0x1c2, 0x12}, RegPair{0x1c3, 2},
                               RegPair{0x1c2, 0x22}};
    Shader s{};
    s.ctx_regs = addr(ctx.data());
    u32 v = 0xFFFFFFFFu;

    s.num_ctx_regs = 2;
    CHECK(agc::agcGetShaderExportFlag(&v, &s) == 0);
    CHECK(v == 8u);

    ctx[1].value = 0x13;
    v = 0xFFFFFFFFu;
    s.num_ctx_regs = 3;
    CHECK(agc::agcGetShaderExportFlag(&v, &s) == 0);
    CHECK(v == 0u);

    s.num_ctx_regs = 0;
    v = 0xFFFFFFFFu;
    CHECK(agc::agcGetShaderExportFlag(&v, &s) == 0);
    CHECK(v == 0u);

    // AMBIGUOUS: read as "first pair with offset 0x1c2 AND low nibble 2", i.e. the scan continues
    // past an 0x1c2 pair whose nibble is not 2.
    s.num_ctx_regs = 4;
    v = 0xFFFFFFFFu;
    CHECK(agc::agcGetShaderExportFlag(&v, &s) == 0);
    CHECK(v == 8u);
}

TEST_CASE("exported word bi4pcLifd1k is zero", "[agc][export]") {
    Env env;
    CHECK(agc::g_exported_word == 0u);
    CHECK(sizeof(agc::g_exported_word) == 4u);
}

#define F(fn) reinterpret_cast<void *>(&agc::fn)

TEST_CASE("part-2 exports are published under their NIDs", "[agc][export]") {
    Env env;
    struct Want {
        const char *nid;
        void *address;
    };
    const Want wants[] = {
    {"GXBlM-ekzrI", F(sceAgcBranchPatchSetCompareAddress)},
    {"2BS4EtAaF28", F(sceAgcJumpPatchSetTarget)},
    {"Ikfdt-rIqCE", F(agcJumpPatchSetTargetEx)},
    {"Qrj4c+61z4A", F(sceAgcSetShRegIndirectPatchSetAddress)},
    {"nCUgItdN2ms", F(sceAgcSetShRegIndirectPatchSetNumRegisters)},
    {"z2duB-hHQSM", F(sceAgcSetShRegIndirectPatchAddRegisters)},
    {"vcmNN+AAXnY", F(sceAgcSetCxRegIndirectPatchSetAddress)},
    {"whb1RL7K4Ss", F(sceAgcSetCxRegIndirectPatchSetNumRegisters)},
    {"d-6uF9sZDIU", F(sceAgcSetCxRegIndirectPatchAddRegisters)},
    {"6lNcCp+fxi4", F(sceAgcSetUcRegIndirectPatchSetAddress)},
    {"fRG-JOH5+sI", F(sceAgcSetUcRegIndirectPatchSetNumRegisters)},
    {"vRoArM9zaIk", F(sceAgcSetUcRegIndirectPatchAddRegisters)},
    {"ORWsxIbk4TE", F(sceAgcCondExecPatchSetEnd)},
    {"YWTKOju587o", F(sceAgcCondExecPatchSetCommandAddress)},
    {"k-JpyR2dYAM", F(sceAgcAsyncCondExecPatchSetEnd)},
    {"3ZWa3AoyWZQ", F(sceAgcAsyncCondExecPatchSetCommandAddress)},
    {"ziVA3whp3p4", F(sceAgcRewindPatchSetRewindState)},
    {"eWaWyFegzgQ", F(sceAgcAsyncRewindPatchSetRewindState)},
    {"w6Dj1VJt5qY", F(sceAgcSetPacketPredication)},
    {"Lkf86B98qPc", F(sceAgcGetPacketSize)},
    {"K2mciNVxUCE", F(sceAgcSetNop)},
    {"n8vgpaQg6dA", F(sceAgcSetRangePredication)},
    {"CQsSq6l6+kA", F(sceAgcGetDataPacketPayloadAddress)},
    {"V++UgBtQhn0", F(agcGetDataPacketPayloadAddressChecked)},
    {"s+VGAMDQ0AQ", F(sceAgcGetDataPacketPayloadRange)},
    {"IxYiarKlXxM", F(sceAgcDmaDataPatchSetDstAddressOrOffset)},
    {"cdDRpqcFGbU", F(sceAgcDmaDataPatchSetSrcAddressOrOffsetOrImmediate)},
    {"3KDcnM3lrcU", F(sceAgcWaitRegMemPatchAddress)},
    {"n485EBnIWmk", F(sceAgcWaitRegMemPatchCompareFunction)},
    {"7nOoijNPvEU", F(sceAgcWaitRegMemPatchReference)},
    {"hXAnLgDHCoI", F(sceAgcWaitRegMemPatchMask)},
    {"0fWWK5uG9rQ", F(sceAgcQueueEndOfPipeActionPatchAddress)},
    {"J8YCgfKAMQs", F(sceAgcQueueEndOfPipeActionPatchGcrCntl)},
    {"T9fjQIINoeE", F(sceAgcQueueEndOfPipeActionPatchType)},
    {"MlEw1feXcjg", F(sceAgcQueueEndOfPipeActionPatchData)},
    {"W0WEyog0f74", F(sceAgcAcquireMemSetEngine)},
    {"fPSCdQxgpSw", F(agcWriteDataPatchSetAddress)},
    {"eAy8eGNsCuU", F(agcWriteDataPatchSetCachePolicy)},
    {"tmy-+rBpspY", F(agcWriteDataPatchSetDestination)},
    {"d4NZIlguzv0", F(agcWriteDataPatchSetAddress2)},
    {"y5K5tPktiL8", F(agcWriteDataPatchSetCachePolicy2)},
    {"EJBA4dbmvfg", F(agcWriteDataPatchSetDstSel)},
    {"Abendgtz+3o", F(sceAgcCbDispatchGetSize)},
    {"uZW-mqsxkrM", F(sceAgcCbBranchGetSize)},
    {"FuVbkyKlf+s", F(sceAgcCbCondWriteGetSize)},
    {"t7PlZ9nt5Lc", F(sceAgcCbNopGetSize)},
    {"hL7C0IRpWZI", F(sceAgcCbQueueEndOfPipeActionGetSize)},
    {"bxGoVxpdSPQ", F(sceAgcCbSetShRegisterRangeDirectGetSize)},
    {"JOWmDrl+j20", F(sceAgcCbSetUcRegisterRangeDirectGetSize)},
    {"yUBESvCCJ4I", F(sceAgcCbSetShRegistersDirectGetSize)},
    {"TGEZzUWLbrc", F(sceAgcCbSetUcRegistersDirectGetSize)},
    {"nNlUtdDDvZ0", F(sceAgcDcbSetShRegistersIndirectGetSize)},
    {"GBCh3zCihoU", F(sceAgcDcbSetCxRegistersIndirectGetSize)},
    {"UQGTw4xRlcM", F(sceAgcDcbSetUcRegistersIndirectGetSize)},
    {"QhPDD513V0w", F(sceAgcDcbSetShRegisterDirectGetSize)},
    {"1DeUNpRIDDA", F(sceAgcDcbSetCxRegisterDirectGetSize)},
    {"aP1Ki9G3++4", F(sceAgcDcbSetUcRegisterDirectGetSize)},
    {"-vnlTPPXPrw", F(sceAgcDcbAcquireMemGetSize)},
    {"1tB0xkLNjcw", F(sceAgcDcbAtomicGdsGetSize)},
    {"oz6zQq1JwCE", F(sceAgcDcbAtomicMemGetSize)},
    {"ou16V5hh5sg", F(sceAgcDcbCondExecGetSize)},
    {"H6vHS5cidSA", F(sceAgcDcbContextStateOpGetSize)},
    {"VEGu4dixjUg", F(sceAgcDcbJumpGetSize)},
    {"b5u0Jzm8TF8", F(sceAgcDcbCopyDataGetSize)},
    {"2ccJz9LQI+w", F(sceAgcDcbDmaDataGetSize)},
    {"p9tI+yTvx68", F(sceAgcDcbWriteDataGetSize)},
    {"zg6u-N6Otxs", F(sceAgcDcbQueueEndOfShaderActionGetSize)},
    {"w8HVkEeXPv8", F(sceAgcDcbDispatchIndirectGetSize)},
    {"WrdP9Zxx3lQ", F(sceAgcDcbDrawIndexAutoGetSize)},
    {"6ee9Hd3EWXQ", F(sceAgcDcbDrawIndexGetSize)},
    {"qMlfB1ZhMDc", F(sceAgcDcbDrawIndexOffsetGetSize)},
    {"cxPZ4Wgvdj8", F(sceAgcDcbDrawIndirectGetSize)},
    {"pYoKs3lPy88", F(sceAgcDcbDrawIndirectMultiGetSize)},
    {"r98I08t+LOg", F(sceAgcDcbDrawIndexIndirectMultiGetSize)},
    {"mStuvI0zOtc", F(sceAgcDcbDrawIndexIndirectGetSize)},
    {"mR9j7+SfM34", F(sceAgcDcbDrawIndexMultiInstancedGetSize)},
    {"C4l9fB17t8w", F(sceAgcDcbEventWriteGetSize)},
    {"rUuVjyR+Rd4", F(sceAgcDcbGetLodStatsGetSize)},
    {"9S4noWrUI0s", F(sceAgcDcbSetBaseDispatchIndirectArgsGetSize)},
    {"MMlmJAL7N5w", F(sceAgcDcbSetBaseDrawIndirectArgsGetSize)},
    {"ca4KPvp0qLQ", F(sceAgcDcbSetIndexSizeGetSize)},
    {"j4emHHndCPY", F(sceAgcDcbSetIndexBufferGetSize)},
    {"mljzuGDZRQ4", F(sceAgcDcbSetIndexCountGetSize)},
    {"6DFuRKT4C9w", F(sceAgcDcbSetNumInstancesGetSize)},
    {"+u6dKSLWM2o", F(sceAgcDcbStallCommandBufferParserGetSize)},
    {"43WJ08sSugE", F(sceAgcDcbWaitOnAddressGetSize)},
    {"QIXCsbipds0", F(sceAgcDcbRewindGetSize)},
    {"ms1xVoZ-Vwc", F(sceAgcDcbBeginOcclusionQueryGetSize)},
    {"P1CugZ99Uzc", F(sceAgcDcbEndOcclusionQueryGetSize)},
    {"XN+Iuu7XsM8", F(sceAgcDcbSetZPassPredicationEnableGetSize)},
    {"yheJGN-ay+A", F(sceAgcDcbSetBoolPredicationEnableGetSize)},
    {"vLrBL8DQiz8", F(sceAgcDcbSetPredicationDisableGetSize)},
    {"KjPeVduz6jU", F(sceAgcDcbPrimeUtcl2GetSize)},
    {"AFIh8SQkYlQ", F(sceAgcDcbSetIndexIndirectArgsGetSize)},
    {"ewobAQeMo5k", F(sceAgcAcbAcquireMemGetSize)},
    {"hcIxS8pmXF4", F(sceAgcAcbAtomicGdsGetSize)},
    {"da1Sm8-QDoU", F(sceAgcAcbAtomicMemGetSize)},
    {"ozKzBP4aki4", F(sceAgcAcbCondExecGetSize)},
    {"b-oySn+G2tE", F(sceAgcAcbJumpGetSize)},
    {"CbQh3DKMSno", F(sceAgcAcbCopyDataGetSize)},
    {"M0ttm8h7SKA", F(sceAgcAcbDmaDataGetSize)},
    {"PxKWV2fVAps", F(sceAgcAcbDispatchIndirectGetSize)},
    {"Y-5vneiBtzk", F(sceAgcAcbEventWriteGetSize)},
    {"eCjKaqeeQ5s", F(sceAgcAcbPrimeUtcl2GetSize)},
    {"0ZOG0jc9nRg", F(sceAgcAcbRewindGetSize)},
    {"idlaArvdXEs", F(sceAgcAcbWaitOnAddressGetSize)},
    {"F8NLhWvFemI", F(sceAgcAcbQueueEndOfShaderActionGetSize)},
    {"f3dg2CSgRKY", F(sceAgcCreateShader)},
    {"dolOmWH+huQ", F(agcGetFusedShaderSize64)},
    {"nQT5kYLv0cg", F(sceAgcGetFusedShaderSize)},
    {"nApJjpKNBl4", F(sceAgcFuseShaderHalves)},
    {"fd5Bp5tGTgo", F(agcFuseShaderHalves2)},
    {"MqAdbRMdNz4", F(sceAgcLinkShaders)},
    {"pdEV7bI6COI", F(sceAgcCreateInterpolantMapping)},
    {"SbuY2jN+axQ", F(sceAgcUpdateInterpolantMapping)},
    {"HV4j+E0MBHE", F(agcCreateInterpolantMappingB)},
    {"k0E7vkgqAuE", F(agcUpdateInterpolantMappingB)},
    {"dbOlWdppb4o", F(agcCreateInterpolantMappingC)},
    {"vieBRwlh1Lw", F(agcUpdateInterpolantMappingC)},
    {"D9sr1xGUriE", F(sceAgcCreatePrimState)},
    {"Y3ymLfZ1384", F(sceAgcUpdatePrimState)},
    {"NKIzURsgV7I", F(sceAgcGetGsOversubscription)},
    {"ICkECTBxrMw", F(agcGetShaderExportFlag)},
    };
    const auto exports = bc5::reimpl::agc::exports();
    auto find = [&](const char *nid) -> const bc5::reimpl::ExportEntry * {
        for (const bc5::reimpl::ExportEntry &e : exports) {
            if (e.nid != nullptr && e.library != nullptr && std::strcmp(e.nid, nid) == 0 &&
                std::strcmp(e.library, "libSceAgc") == 0) {
                return &e;
            }
        }
        return nullptr;
    };
    for (const Want &w : wants) {
        INFO("nid " << w.nid);
        const bc5::reimpl::ExportEntry *e = find(w.nid);
        REQUIRE(e != nullptr);
        CHECK(e->address == w.address);
        CHECK_FALSE(e->is_object);
    }
    const bc5::reimpl::ExportEntry *word = find("bi4pcLifd1k");
    REQUIRE(word != nullptr);
    CHECK(word->is_object);
    CHECK(word->address == static_cast<void *>(&agc::g_exported_word));
}

#undef F
