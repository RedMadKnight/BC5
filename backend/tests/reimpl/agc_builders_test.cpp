// SPDX-License-Identifier: GPL-2.0-only
// Clean-room tests of the libSceAgc command-buffer builders (re-creation, see
// src/reimpl/PROVENANCE.md): every builder that takes a CommandBuffer, checked dword by dword
// against the behavioural description, plus the out-of-space protocol (strict and soft
// reservations), the draw-modifier rules, the ACQUIRE_MEM workaround variants, the queue-reset
// sequences and the context-state operations. Expected values are computed by hand from the
// description and written as literals. The driver imports are fakes defined here that write
// recognisable dwords and record their arguments; no GPU, no console data.
#include <catch2/catch_test_macros.hpp>

#include "bc5/reimpl/agc.hpp"
#include "bc5/reimpl/agc_cb.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>
#include <vector>

namespace agc = bc5::reimpl::agc;
namespace tst = bc5::reimpl::agc::testing;

namespace {

using u32 = std::uint32_t;
using u64 = std::uint64_t;
using i32 = std::int32_t;

constexpr u32 kSentinel = 0xDEADBEEFu;
constexpr std::size_t kGuard = 16; // sentinel dwords after the buffer's limit
constexpr u32 kNoChange = 0xFFFFFFFFu;
constexpr u64 kLabel = 0x00000012345678A0ull; // fake sync-label GPU address (never dereferenced)

struct Hex {
    u32 v;
};
bool operator==(Hex a, Hex b) { return a.v == b.v; }

} // namespace

namespace Catch {
template <> struct StringMaker<Hex> {
    static std::string convert(Hex h) {
        char buf[16];
        std::snprintf(buf, sizeof buf, "0x%08X", static_cast<unsigned>(h.v));
        return buf;
    }
};
} // namespace Catch

namespace {

// ---- out-of-space callback --------------------------------------------------------------------

struct OosLog {
    int calls = 0;
    agc::CommandBuffer *last_cb = nullptr;
    u32 last_required = 0;
    void *last_user = nullptr;
    bool result = false;
    u32 *chain_to = nullptr; // when set, the callback moves the buffer there (once)
    u32 chain_dwords = 0;
    u32 set_reserved = kNoChange; // when != kNoChange, the callback writes reserved_dwords
};

bool oos_callback(agc::CommandBuffer *c, u32 required, void *user) {
    auto *o = static_cast<OosLog *>(user);
    ++o->calls;
    o->last_cb = c;
    o->last_required = required;
    o->last_user = user;
    if (o->chain_to != nullptr) {
        c->begin = o->chain_to;
        c->cursor = o->chain_to;
        c->buffer_end = o->chain_to + o->chain_dwords;
        c->limit = c->buffer_end;
        o->chain_to = nullptr;
    }
    if (o->set_reserved != kNoChange) {
        c->reserved_dwords = o->set_reserved;
    }
    return o->result;
}

// A command buffer of `dwords` dwords over sentinel-filled memory with kGuard extra sentinel
// dwords behind its limit.
struct Buf {
    std::vector<u32> mem;
    OosLog oos;
    agc::CommandBuffer cb{};
    explicit Buf(u32 dwords = 256) : mem(std::size_t{dwords} + kGuard, kSentinel) {
        agc::init_command_buffer(&cb, mem.data(), std::uint64_t{dwords} * 4u, &oos_callback, &oos);
    }
    Buf(const Buf &) = delete;
    Buf &operator=(const Buf &) = delete;
    std::size_t used() const { return static_cast<std::size_t>(cb.cursor - mem.data()); }
    u32 *at(std::size_t i) { return mem.data() + i; }
};

// ---- fake libSceAgcDriver imports -------------------------------------------------------------

constexpr u32 kUdTag = 0x0DA7A000u;     // | dword count
constexpr u32 kSetTag = 0x5E100000u;    // set marker | count
constexpr u32 kPushTag = 0x5E200000u;   // push marker | count
constexpr u32 kPopTag = 0x5E300000u;    // pop marker | count
constexpr u32 kFlipFill = 0xF1F10000u;  // + index
constexpr u32 kWaitFill = 0xA1A10000u;  // + index
constexpr u32 kWlFill = 0x3C000000u;    // kind << 16 + index

struct UdCall {
    u32 *dst;
    i32 pipe;
    u32 header;
    std::vector<u32> payload;
    u32 bytes;
    bool payload_null;
};
struct MarkerCall {
    int kind; // 0 set, 1 push, 2 pop
    u32 *dst;
    i32 pipe;
    std::string text;
    u32 bytes;
    u32 color;
};
struct FlipCall {
    u32 **cursor;
    u32 n;
    i32 pipe;
    i32 a0;
    i32 a1;
    u32 a2;
    std::int64_t a3;
};
struct WaitCall {
    u32 **cursor;
    u32 n;
    i32 pipe;
    i32 a0;
    i32 a1;
};
struct WlCall {
    int kind; // 1 active, 2 complete, 3 stream inactive
    u32 *dst;
    i32 pipe;
    u32 stream;
    const u32 *indices;
    u32 value; // count (active) or workload index (complete)
};
struct Fake {
    std::vector<UdCall> ud;
    std::vector<MarkerCall> markers;
    std::vector<FlipCall> flips;
    std::vector<WaitCall> waits;
    std::vector<WlCall> wl;
    std::vector<std::pair<i32, u64>> raises;
    u32 marker_delta = 0; // added to the marker writers' return value
    i32 flip_rc = 0;
    i32 wait_rc = 0;
    i32 wl_rc = 0;
};
Fake g_fake;

// drv.md: 3 for 0 bytes, 4 for 1..4 bytes, ceil(n/4) + 7 otherwise.
u32 fake_ud_size(u32 bytes) {
    if (bytes == 0) {
        return 3;
    }
    const u64 d = (u64{bytes} + 3) / 4;
    return d == 1 ? 4u : static_cast<u32>(d + 7);
}

u32 fake_ud_write(u32 *dst, i32 pipe, u32 header, const void *payload, u32 bytes) {
    const u32 n = fake_ud_size(bytes);
    std::vector<u32> words((std::size_t{bytes} + 3) / 4, 0u);
    if (payload != nullptr && bytes != 0) {
        std::memcpy(words.data(), payload, bytes);
    }
    dst[0] = kUdTag | n;
    dst[1] = header;
    dst[2] = static_cast<u32>(pipe);
    for (u32 i = 3; i < n; ++i) {
        dst[i] = (i - 3 < words.size()) ? words[i - 3] : 0u;
    }
    g_fake.ud.push_back(UdCall{dst, pipe, header, words, bytes, payload == nullptr});
    return n;
}

u32 marker_common(int kind, u32 tag, u32 *dst, i32 pipe, const char *text, u32 bytes,
                  u32 color) {
    const u32 n = fake_ud_size(bytes);
    dst[0] = tag | n;
    dst[1] = color;
    dst[2] = static_cast<u32>(pipe);
    for (u32 i = 3; i < n; ++i) {
        dst[i] = 0x7E000000u + i;
    }
    g_fake.markers.push_back(MarkerCall{
        kind, dst, pipe, text != nullptr ? std::string(text, bytes) : std::string(), bytes, color});
    return n + g_fake.marker_delta;
}

u32 fake_set_marker(u32 *dst, i32 pipe, const char *text, u32 bytes, u32 color) {
    return marker_common(0, kSetTag, dst, pipe, text, bytes, color);
}
u32 fake_push_marker(u32 *dst, i32 pipe, const char *text, u32 bytes, u32 color) {
    return marker_common(1, kPushTag, dst, pipe, text, bytes, color);
}
u32 fake_pop_marker(u32 *dst, i32 pipe) {
    dst[0] = kPopTag | 3u;
    dst[1] = 0;
    dst[2] = static_cast<u32>(pipe);
    g_fake.markers.push_back(MarkerCall{2, dst, pipe, std::string(), 0, 0});
    return 3u + g_fake.marker_delta;
}

u32 fake_flip_size() { return 0x40; }
u32 fake_wait_size() { return 0x20; }

i32 fake_set_flip(u32 **cursor, u32 n, i32 pipe, i32 a0, i32 a1, u32 a2, std::int64_t a3) {
    g_fake.flips.push_back(FlipCall{cursor, n, pipe, a0, a1, a2, a3});
    if (g_fake.flip_rc != 0) {
        return g_fake.flip_rc;
    }
    for (u32 i = 0; i < n; ++i) {
        (*cursor)[i] = kFlipFill + i;
    }
    *cursor += n;
    return 0;
}

i32 fake_wait_safe(u32 **cursor, u32 n, i32 pipe, i32 a0, i32 a1) {
    g_fake.waits.push_back(WaitCall{cursor, n, pipe, a0, a1});
    if (g_fake.wait_rc != 0) {
        return g_fake.wait_rc;
    }
    for (u32 i = 0; i < n; ++i) {
        (*cursor)[i] = kWaitFill + i;
    }
    *cursor += n;
    return 0;
}

u32 fake_wl_active_size() { return 18; }
u32 fake_wl_complete_size() { return 12; }
u32 fake_wl_inactive_size() { return 9; }

void wl_fill(u32 *dst, int kind, u32 n) {
    for (u32 i = 0; i < n; ++i) {
        dst[i] = kWlFill + (static_cast<u32>(kind) << 16) + i;
    }
}
i32 fake_wl_active(u32 *dst, i32 pipe, u32 stream, const u32 *indices, u32 count) {
    g_fake.wl.push_back(WlCall{1, dst, pipe, stream, indices, count});
    if (g_fake.wl_rc == 0) {
        wl_fill(dst, 1, 18);
    }
    return g_fake.wl_rc;
}
i32 fake_wl_complete(u32 *dst, i32 pipe, u32 stream, u32 index) {
    g_fake.wl.push_back(WlCall{2, dst, pipe, stream, nullptr, index});
    if (g_fake.wl_rc == 0) {
        wl_fill(dst, 2, 12);
    }
    return g_fake.wl_rc;
}
i32 fake_wl_inactive(u32 *dst, i32 pipe, u32 stream) {
    g_fake.wl.push_back(WlCall{3, dst, pipe, stream, nullptr, 0});
    if (g_fake.wl_rc == 0) {
        wl_fill(dst, 3, 9);
    }
    return g_fake.wl_rc;
}

i32 fake_raise(i32 kind, u64 arg) {
    g_fake.raises.emplace_back(kind, arg);
    return static_cast<i32>(0x8A6D0003u);
}

template <typename F> void imp(const char *nid, F *fn) {
    INFO("import " << nid);
    REQUIRE(tst::set_import(nid, reinterpret_cast<void *>(fn)));
}

void install_fakes() {
    g_fake = Fake{};
    imp("VhLnEiTuuWo", &fake_ud_size);
    imp("-vc-xL+G8u0", &fake_ud_write);
    imp("zmw2uVSEj94", &fake_set_marker);
    imp("+b34-CLWc0s", &fake_push_marker);
    imp("LEnn-4ARRJM", &fake_pop_marker);
    imp("2PrsbRYyZi4", &fake_flip_size);
    imp("cwbxjPSJ7WQ", &fake_set_flip);
    imp("0MtUJ3BpGhE", &fake_wait_size);
    imp("u8BkdHb1+Po", &fake_wait_safe);
    imp("gyVTZWyySpM", &fake_wl_active_size);
    imp("WNyjOWq8-Vk", &fake_wl_complete_size);
    imp("k8rLr8nq-hE", &fake_wl_inactive_size);
    imp("UM9b9NunSrE", &fake_wl_active);
    imp("i6bfTi13ApA", &fake_wl_complete);
    imp("AU87qNukGi4", &fake_wl_inactive);
    imp("yuO+lNrj+Do", &fake_raise);
}

// ---- expectation helpers ----------------------------------------------------------------------

std::vector<u32> cat(std::initializer_list<std::vector<u32>> parts) {
    std::vector<u32> out;
    for (const auto &p : parts) {
        out.insert(out.end(), p.begin(), p.end());
    }
    return out;
}

// What fake_ud_write leaves for a packet without / with a 4-byte payload.
std::vector<u32> ud3(u32 header, u32 pipe) { return {kUdTag | 3u, header, pipe}; }
std::vector<u32> ud4(u32 header, u32 pipe, u32 payload) {
    return {kUdTag | 4u, header, pipe, payload};
}

void expect_dwords(const u32 *p, const std::vector<u32> &exp) {
    for (std::size_t i = 0; i < exp.size(); ++i) {
        INFO("dword " << i);
        CHECK(Hex{p[i]} == Hex{exp[i]});
    }
}

// The builder returned the buffer start, wrote exactly `exp`, advanced the cursor by its size and
// left the next dword alone.
void expect_packet(Buf &b, const u32 *ret, const std::vector<u32> &exp) {
    REQUIRE(ret == b.mem.data());
    CHECK(b.used() == exp.size());
    expect_dwords(b.mem.data(), exp);
    CHECK(Hex{b.mem[exp.size()]} == Hex{kSentinel});
}

void expect_untouched(const Buf &b) {
    for (std::size_t i = 0; i < b.mem.size(); ++i) {
        INFO("dword " << i);
        CHECK(Hex{b.mem[i]} == Hex{kSentinel});
    }
}

u64 addr_of(const void *p) { return static_cast<u64>(reinterpret_cast<std::uintptr_t>(p)); }
u32 lo_and(const void *p, u64 mask) { return static_cast<u32>(addr_of(p) & mask); }
u32 lo4(const void *p) { return lo_and(p, ~u64{3}); }
u32 hi(const void *p) { return static_cast<u32>(addr_of(p) >> 32); }

template <std::size_t N> void put(std::array<std::uint8_t, N> &a, std::size_t off, u64 v, int size) {
    std::memcpy(a.data() + off, &v, static_cast<std::size_t>(size)); // little endian host
}

// Queue-state slot with tables pointing at our own arrays.
struct SlotFixture {
    std::array<agc::RegPair, 4> cx{};
    std::array<agc::RegPair, 4> sh{};
    std::array<agc::RegPair, 20> uc{};
    std::array<u32, 6> stream{0x51515151u, 0x52525252u, 0x53535353u,
                              0x54545454u, 0x55555555u, 0x56565656u};
    tst::SlotView view(u32 version, bool trusted, u32 stream_bytes) {
        tst::SlotView v{};
        v.cx = cx.data();
        v.sh = sh.data();
        v.uc = uc.data();
        v.cx_count = 0x4123; // emitted & 0x3FFF -> 0x123
        v.sh_count = 0x4045; // -> 0x45
        v.uc_count = 20;
        v.uc_special_count = 8;
        v.sh_stream = stream.data();
        v.sh_stream_bytes = stream_bytes;
        v.resume_dcb = nullptr;
        v.resume_dwords = 0;
        v.version = version;
        v.trusted = trusted;
        return v;
    }
    std::vector<u32> h10() const {
        return {0xC0039F00u, lo4(cx.data()), hi(cx.data()), 0x80000000u, 0x123u};
    }
};

// H8 ConditionalRollNotify(op) with g_syncLabel = kLabel (22 dwords).
std::vector<u32> h8(u32 op, bool full) {
    const u64 cond = kLabel + (full ? 0u : 4u);
    return {0xC0032200u, static_cast<u32>(cond & ~u64{3}), static_cast<u32>(cond >> 32), 0u, 8u,
            // RELEASE_MEM(0x28, 0, 1, 3, 0, 0, 0, 0, 0, 4, 0), dword 7 patched
            0xC0064900u, 0x06000528u, 0x04010000u, 0u, 0u, 0u, 0u, 0x08100000u + op,
            // ATOMIC_MEM(engine 1, op 0x67, command 2, policy 0, label, src, 0, loop 400)
            0xC0071E00u, 0x40000267u, static_cast<u32>(kLabel), static_cast<u32>(kLabel >> 32),
            full ? 1u : 0u, full ? 0u : 1u, 0u, 0u, 6u};
}

// H9 ConditionalClearState (16 dwords).
std::vector<u32> h9() {
    return {0xC0032200u, static_cast<u32>(kLabel), static_cast<u32>(kLabel >> 32), 0u, 11u,
            0xC0001200u, 2u,
            0xC0071E00u, 0x40000267u, static_cast<u32>(kLabel), static_cast<u32>(kLabel >> 32),
            0u, 1u, 0u, 0u, 6u};
}

using BuilderFn = u32 *(*)(agc::CommandBuffer *);
struct BuilderCase {
    const char *name;
    u32 dwords;
    BuilderFn fn;
};

} // namespace

// =================================================================================================
// Out-of-space protocol (section 3.1)
// =================================================================================================

TEST_CASE("oos: callback gets (cb, reserve + n, userData); false -> NULL, nothing written",
          "[agc][builders][oos]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    Buf b(2);
    u32 *r = agc::sceAgcDcbSetCxRegisterDirect(&b.cb, agc::RegPair{0x10, 0x20});
    CHECK(r == nullptr);
    CHECK(b.oos.calls == 1);
    CHECK(b.oos.last_cb == &b.cb);
    CHECK(b.oos.last_required == 3u);
    CHECK(b.oos.last_user == &b.oos);
    CHECK(b.used() == 0);
    expect_untouched(b);

    SECTION("reservedDwords is part of the requirement and of the free space") {
        Buf c(8);
        c.cb.reserved_dwords = 6; // free = 8 - 6 = 2
        CHECK(agc::sceAgcDcbSetCxRegisterDirect(&c.cb, agc::RegPair{1, 2}) == nullptr);
        CHECK(c.oos.calls == 1);
        CHECK(c.oos.last_required == 9u); // 6 + 3
        expect_untouched(c);
        c.cb.reserved_dwords = 5; // free = 3: fits without the callback
        u32 *p = agc::sceAgcDcbSetCxRegisterDirect(&c.cb, agc::RegPair{1, 2});
        CHECK(c.oos.calls == 1);
        expect_packet(c, p, {0xC0016900u, 1u, 2u});
    }
    SECTION("exact fit needs no callback") {
        Buf c(3);
        u32 *p = agc::sceAgcDcbSetCxRegisterDirect(&c.cb, agc::RegPair{1, 2});
        CHECK(c.oos.calls == 0);
        expect_packet(c, p, {0xC0016900u, 1u, 2u});
        CHECK(c.cb.cursor == c.cb.limit);
    }
}

TEST_CASE("oos: a callback that chains to a new buffer makes the builder succeed there",
          "[agc][builders][oos]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    Buf b(2);
    std::vector<u32> second(64, kSentinel);
    b.oos.result = true;
    b.oos.chain_to = second.data();
    b.oos.chain_dwords = 64;
    u32 *r = agc::sceAgcDcbSetUcRegisterDirect(&b.cb, agc::RegPair{0x12345, 0xCAFE});
    REQUIRE(r == second.data());
    CHECK(b.oos.calls == 1);
    CHECK(b.cb.cursor == second.data() + 3);
    expect_dwords(second.data(), {0xC0017900u, 0x2345u, 0xCAFEu});
    expect_untouched(b);
}

TEST_CASE("oos: strict reservation honours the callback result and rechecks free space",
          "[agc][builders][oos]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("true without making room still fails") {
        Buf b(2);
        b.oos.result = true;
        CHECK(agc::sceAgcDcbSetShRegisterDirect(&b.cb, agc::RegPair{1, 2}) == nullptr);
        CHECK(b.oos.calls == 1);
        expect_untouched(b);
    }
    SECTION("false even though it made room fails (strict honours the result)") {
        Buf b(2);
        std::vector<u32> second(64, kSentinel);
        b.oos.result = false;
        b.oos.chain_to = second.data();
        b.oos.chain_dwords = 64;
        CHECK(agc::sceAgcDcbSetShRegisterDirect(&b.cb, agc::RegPair{1, 2}) == nullptr);
        CHECK(b.oos.calls == 1);
        CHECK(Hex{second[0]} == Hex{kSentinel});
    }
    SECTION("callback lowering reservedDwords and returning true succeeds") {
        Buf b(4);
        b.cb.reserved_dwords = 3; // free 1
        b.oos.result = true;
        b.oos.set_reserved = 0;
        u32 *p = agc::sceAgcDcbSetShRegisterDirect(&b.cb, agc::RegPair{0x12345, 7});
        CHECK(b.oos.calls == 1);
        CHECK(b.oos.last_required == 6u);
        expect_packet(b, p, {0xC0017600u, 0x2345u, 7u});
    }
    SECTION("reservedDwords + n overflowing 32 bits fails without calling back") {
        Buf b(8);
        b.cb.reserved_dwords = 0xFFFFFFFFu;
        b.oos.result = true;
        CHECK(agc::sceAgcDcbSetShRegisterDirect(&b.cb, agc::RegPair{1, 2}) == nullptr);
        CHECK(b.oos.calls == 0);
        expect_untouched(b);
    }
    SECTION("a later builder fills the remaining space after an earlier one") {
        Buf b(5);
        u32 *p1 = agc::sceAgcDcbSetIndexCount(&b.cb, 9);
        u32 *p2 = agc::sceAgcDcbSetUcRegisterDirect(&b.cb, agc::RegPair{3, 4});
        CHECK(p1 == b.at(0));
        CHECK(p2 == b.at(2));
        CHECK(b.oos.calls == 0);
        CHECK(agc::sceAgcDcbStallCommandBufferParser(&b.cb) == nullptr);
        CHECK(b.oos.calls == 1);
        CHECK(b.oos.last_required == 2u);
        expect_dwords(b.at(0), {0xC0001300u, 9u, 0xC0017900u, 3u, 4u, kSentinel});
    }
}

TEST_CASE("oos: default callback (none supplied) raises debug exception (1, 0) and fails",
          "[agc][builders][oos]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    std::array<u32, 4> mem{kSentinel, kSentinel, kSentinel, kSentinel};
    agc::CommandBuffer cb{};
    agc::init_command_buffer(&cb, mem.data(), 6, nullptr, nullptr); // 6 bytes -> 1 dword
    CHECK(cb.begin == mem.data());
    CHECK(cb.cursor == mem.data());
    CHECK(cb.buffer_end == mem.data() + 1);
    CHECK(cb.limit == mem.data() + 1);
    CHECK(cb.reserved_dwords == 0u);
    CHECK(agc::sceAgcDcbStallCommandBufferParser(&cb) == nullptr);
    REQUIRE(g_fake.raises.size() == 1);
    CHECK(g_fake.raises[0].first == 1);
    CHECK(g_fake.raises[0].second == 0u);
    CHECK(cb.cursor == mem.data());
    CHECK(Hex{mem[0]} == Hex{kSentinel});
}

TEST_CASE("oos: every fixed-size builder fits exactly and fails one dword short",
          "[agc][builders][oos]") {
    static const BuilderCase cases[] = {
        {"AcbAtomicMem", 9, [](agc::CommandBuffer *c) { return agc::sceAgcAcbAtomicMem(c, 1, 2, 0x1000, 0, 0, 0, 0); }},
        {"AcbAcquireMem", 8, [](agc::CommandBuffer *c) { return agc::sceAgcAcbAcquireMem(c, 0, 0, 0, 0); }},
        {"AcbCondExec", 5, [](agc::CommandBuffer *c) { return agc::sceAgcAcbCondExec(c, 0x1000, 4); }},
        {"AcbCopyData", 6, [](agc::CommandBuffer *c) { return agc::sceAgcAcbCopyData(c, 1, 0, 0x1000, 1, 0, 0x2000, 0, 0); }},
        {"AcbDispatchIndirect", 4, [](agc::CommandBuffer *c) { return agc::sceAgcAcbDispatchIndirect(c, 0x1000, 0); }},
        {"AcbDmaData", 7, [](agc::CommandBuffer *c) { return agc::sceAgcAcbDmaData(c, 0, 0, 0x1000, 0, 0, 0x2000, 4, 0, 0); }},
        {"AcbEventWrite", 2, [](agc::CommandBuffer *c) { return agc::sceAgcAcbEventWrite(c, 7); }},
        {"AcbJump", 4, [](agc::CommandBuffer *c) { return agc::sceAgcAcbJump(c, 0, 0x1000, 8); }},
        {"AcbRewind", 2, [](agc::CommandBuffer *c) { return agc::sceAgcAcbRewind(c, 1, 0); }},
        {"AcbPrimeUtcl2", 5, [](agc::CommandBuffer *c) { return agc::sceAgcAcbPrimeUtcl2(c, 1, 0, 0x4000, 1); }},
        {"AcbAtomicGds", 11, [](agc::CommandBuffer *c) { return agc::sceAgcAcbAtomicGds(c, 1, 0, 0, 0, 0, 4, 0, 0, 0, 0); }},
        {"AcbAtomicGdsOp8", 11, [](agc::CommandBuffer *c) { return agc::agcAcbAtomicGdsOp8(c, 1, 0, 0, 0, 0, 4, 0, 0, 0, 0); }},
        {"CbBranch", 14, [](agc::CommandBuffer *c) { return agc::sceAgcCbBranch(c, 0, 0, 0x1000, 0, 0, 0, 0x2000, 4, 0, 0x3000, 4); }},
        {"CbDispatch", 5, [](agc::CommandBuffer *c) { return agc::sceAgcCbDispatch(c, 1, 1, 1, 0); }},
        {"CbCondWrite", 9, [](agc::CommandBuffer *c) { return agc::sceAgcCbCondWrite(c, 0, 0, 0x1000, 1, 0x2000, 0, 0); }},
        {"CbMemSemaphore", 4, [](agc::CommandBuffer *c) { return agc::sceAgcCbMemSemaphore(c, 0x1000, 0, 0, 6); }},
        {"CbNop(6)", 6, [](agc::CommandBuffer *c) { return agc::sceAgcCbNop(c, 6); }},
        {"CbReleaseMem", 8, [](agc::CommandBuffer *c) { return agc::sceAgcCbReleaseMem(c, 0x14, 0, 0, 0, 0x1000, 0, 0, 0, 0, 0, 0); }},
        {"CbSetShRegisterRangeDirect(3)", 5, [](agc::CommandBuffer *c) { return agc::sceAgcCbSetShRegisterRangeDirect(c, 0x10, nullptr, 3); }},
        {"CbSetUcRegisterRangeDirect(3)", 5, [](agc::CommandBuffer *c) { return agc::sceAgcCbSetUcRegisterRangeDirect(c, 0x10, nullptr, 3); }},
        {"CbSetShRegistersDirect(1)", 3, [](agc::CommandBuffer *c) { static const agc::RegPair r[1] = {{0x10, 1}}; return agc::sceAgcCbSetShRegistersDirect(c, r, 1); }},
        {"CbSetUcRegistersDirect(1)", 3, [](agc::CommandBuffer *c) { static const agc::RegPair r[1] = {{0x10, 1}}; return agc::sceAgcCbSetUcRegistersDirect(c, r, 1); }},
        {"DcbSetCxRegisterDirect", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetCxRegisterDirect(c, agc::RegPair{1, 2}); }},
        {"DcbSetCfRegisterDirect", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetCfRegisterDirect(c, agc::RegPair{1, 2}); }},
        {"DcbSetUcRegisterDirect", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetUcRegisterDirect(c, agc::RegPair{1, 2}); }},
        {"DcbSetShRegisterDirect", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetShRegisterDirect(c, agc::RegPair{1, 2}); }},
        {"DcbAcquireMem", 8, [](agc::CommandBuffer *c) { return agc::sceAgcDcbAcquireMem(c, 0, 0, 0, 0, 0, 0); }},
        {"DcbAtomicMem", 9, [](agc::CommandBuffer *c) { return agc::sceAgcDcbAtomicMem(c, 0, 1, 2, 0, 0x1000, 0, 0, 0); }},
        {"DcbClearState", 2, [](agc::CommandBuffer *c) { return agc::sceAgcDcbClearState(c, 1); }},
        {"DcbSetCxRegistersIndirect", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetCxRegistersIndirect(c, 0x1000, 2); }},
        {"DcbSetShRegistersIndirect", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetShRegistersIndirect(c, 0x1000, 2); }},
        {"DcbSetUcRegistersIndirect", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetUcRegistersIndirect(c, 0x1000, 2); }},
        {"DcbCondExec", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbCondExec(c, 0x1000, 4); }},
        {"DcbJump", 4, [](agc::CommandBuffer *c) { return agc::sceAgcDcbJump(c, 0, 0, 0x1000, 8); }},
        {"DcbCopyData", 6, [](agc::CommandBuffer *c) { return agc::sceAgcDcbCopyData(c, 2, 0, 0x1000, 2, 0, 0x2000, 0, 0); }},
        {"DcbDmaData", 7, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDmaData(c, 0, 0, 0, 0x1000, 0, 0, 0x2000, 4, 0, 0, 0); }},
        {"DcbDispatchIndirect", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDispatchIndirect(c, 0, 0); }},
        {"DcbDrawIndexAuto", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndexAuto(c, 3, 0); }},
        {"DcbDrawIndex", 6, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndex(c, 3, 0x1000, 0); }},
        {"DcbDrawIndexOffset", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndexOffset(c, 0, 3, 0); }},
        {"DcbDrawIndirect", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndirect(c, 0, 0); }},
        {"DcbDrawIndexIndirect", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndexIndirect(c, 0, 0); }},
        {"DcbEventWrite(7)", 2, [](agc::CommandBuffer *c) { return agc::sceAgcDcbEventWrite(c, 7, 0); }},
        {"DcbEventWrite(0x38)", 4, [](agc::CommandBuffer *c) { return agc::sceAgcDcbEventWrite(c, 0x38, 0x1000); }},
        {"DcbGetLodStats", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbGetLodStats(c, 0, 0x1000, 0, 0, 0, 0, 0); }},
        {"DcbSetBaseIndirectArgs", 4, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetBaseIndirectArgs(c, 0, 0x1000); }},
        {"DcbSetIndexSize", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetIndexSize(c, 1, 0); }},
        {"DcbSetIndexSizeEx", 3, [](agc::CommandBuffer *c) { return agc::agcDcbSetIndexSizeEx(c, 1, 0, 1); }},
        {"DcbSetIndexBuffer", 3, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetIndexBuffer(c, 0x1000); }},
        {"DcbSetIndexCount", 2, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetIndexCount(c, 3); }},
        {"DcbSetNumInstances", 2, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetNumInstances(c, 3); }},
        {"DcbStallCommandBufferParser", 2, [](agc::CommandBuffer *c) { return agc::sceAgcDcbStallCommandBufferParser(c); }},
        {"DcbRewind", 2, [](agc::CommandBuffer *c) { return agc::sceAgcDcbRewind(c, 1); }},
        {"DcbPrimeUtcl2", 5, [](agc::CommandBuffer *c) { return agc::sceAgcDcbPrimeUtcl2(c, 1, 0, 0x4000, 1); }},
        {"DcbSetIndexIndirectArgs", 4, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetIndexIndirectArgs(c, 0x1000, 1); }},
        {"DcbSetPredication", 4, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetPredication(c, 1, 1, 0, 0x1000); }},
        {"DcbAtomicGds", 11, [](agc::CommandBuffer *c) { return agc::sceAgcDcbAtomicGds(c, 0, 1, 0, 0, 0, 0, 4, 0, 0, 0, 0); }},
        {"DcbAtomicGdsOp8", 11, [](agc::CommandBuffer *c) { return agc::agcDcbAtomicGdsOp8(c, 0, 1, 0, 0, 0, 0, 4, 0, 0, 0, 0); }},
    };
    for (const auto &bc : cases) {
        tst::reset();
        tst::clear_imports();
        install_fakes();
        INFO(bc.name);
        {
            Buf b(bc.dwords);
            u32 *p = bc.fn(&b.cb);
            CHECK(p == b.mem.data());
            CHECK(b.used() == bc.dwords);
            CHECK(b.oos.calls == 0);
            CHECK(Hex{b.mem[bc.dwords]} == Hex{kSentinel});
        }
        {
            Buf b(bc.dwords - 1);
            CHECK(bc.fn(&b.cb) == nullptr);
            CHECK(b.oos.calls == 1);
            CHECK(b.oos.last_required == bc.dwords);
            CHECK(b.used() == 0);
            expect_untouched(b);
        }
    }
}

TEST_CASE("oos: ReserveSoft builders ignore the callback result", "[agc][builders][oos]") {
    static const BuilderCase cases[] = {
        {"AcbSetMarker", 4, [](agc::CommandBuffer *c) { return agc::sceAgcAcbSetMarker(c, "abc", 0); }},
        {"DcbPushMarker", 4, [](agc::CommandBuffer *c) { return agc::sceAgcDcbPushMarker(c, "abc", 0); }},
        {"DcbSetMarkerSpan", 9, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetMarkerSpan(c, "abcdefgh", 5, 0); }},
        {"AcbPopMarker", 3, [](agc::CommandBuffer *c) { return agc::sceAgcAcbPopMarker(c); }},
        {"AcbWriteData(3)", 7, [](agc::CommandBuffer *c) { static const u32 d[3] = {1, 2, 3}; return agc::sceAgcAcbWriteData(c, 5, 0, 0x1000, d, 3, 0, 0); }},
        {"DcbWriteData(2)", 6, [](agc::CommandBuffer *c) { static const u32 d[2] = {1, 2}; return agc::sceAgcDcbWriteData(c, 0x0A, 0, 0x1000, d, 2, 0, 0); }},
        {"DcbSetCfRegisterRangeDirect(3)", 5, [](agc::CommandBuffer *c) { static const u32 d[3] = {1, 2, 3}; return agc::sceAgcDcbSetCfRegisterRangeDirect(c, 0x10, d, 3); }},
        {"DcbDrawIndirectMulti", 16, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndirectMulti(c, 0, 0, 1, 0x1000, 16, 0); }},
        {"DcbDrawIndexIndirectMulti", 16, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndexIndirectMulti(c, 0, 0, 1, 0x1000, 16, 0); }},
        {"DcbDrawIndexMultiInstanced", 15, [](agc::CommandBuffer *c) { return agc::sceAgcDcbDrawIndexMultiInstanced(c, 0, 0x1000, 0x2000, 3, 0); }},
        {"AcbWaitRegMem(0)", 14, [](agc::CommandBuffer *c) { return agc::sceAgcAcbWaitRegMem(c, 0, 3, 0, 0x1000, 1, 1, 0); }},
        {"DcbWaitRegMem(1)", 16, [](agc::CommandBuffer *c) { return agc::sceAgcDcbWaitRegMem(c, 1, 3, 0, 0, 0x1000, 1, 1, 0); }},
        {"AcbMemSemaphore(6)", 11, [](agc::CommandBuffer *c) { return agc::sceAgcAcbMemSemaphore(c, 0x1000, 0, 0, 6); }},
        {"DcbMemSemaphore(7)", 11, [](agc::CommandBuffer *c) { return agc::sceAgcDcbMemSemaphore(c, 0x1000, 0, 0, 7); }},
        {"DcbSetFlip", 0x40, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetFlip(c, 1, 2, 3, 4); }},
        {"AcbWaitUntilSafeForRendering", 0x20, [](agc::CommandBuffer *c) { return agc::sceAgcAcbWaitUntilSafeForRendering(c, 1, 2); }},
        {"AcbSetWorkloadsActive", 18, [](agc::CommandBuffer *c) { static const u32 idx[1] = {0}; return agc::sceAgcAcbSetWorkloadsActive(c, 1, addr_of(idx), 1); }},
        {"DcbSetWorkloadComplete", 12, [](agc::CommandBuffer *c) { return agc::sceAgcDcbSetWorkloadComplete(c, 1, 0); }},
        {"AcbSetWorkloadStreamInactive", 9, [](agc::CommandBuffer *c) { return agc::sceAgcAcbSetWorkloadStreamInactive(c, 1); }},
    };
    for (const auto &bc : cases) {
        INFO(bc.name);
        {
            tst::reset();
            tst::clear_imports();
            install_fakes();
            // Callback says "true" but makes no room: the builder fails, nothing written.
            Buf b(2);
            b.oos.result = true;
            CHECK(bc.fn(&b.cb) == nullptr);
            CHECK(b.oos.calls == 1);
            CHECK(b.oos.last_required == bc.dwords);
            CHECK(b.used() == 0);
            expect_untouched(b);
            CHECK(g_fake.ud.empty());
            CHECK(g_fake.markers.empty());
            CHECK(g_fake.flips.empty());
            CHECK(g_fake.waits.empty());
            CHECK(g_fake.wl.empty());
        }
        {
            tst::reset();
            tst::clear_imports();
            install_fakes();
            // Callback says "false" but chains to a big buffer: the builder succeeds there.
            Buf b(2);
            std::vector<u32> second(256, kSentinel);
            b.oos.result = false;
            b.oos.chain_to = second.data();
            b.oos.chain_dwords = 256;
            CHECK(bc.fn(&b.cb) == second.data());
            CHECK(b.oos.calls == 1);
            CHECK(b.cb.cursor > second.data());
            expect_untouched(b);
        }
    }
}

// =================================================================================================
// A.1 / B.1 / C.1 ACB builders
// =================================================================================================

TEST_CASE("AcbAcquireMem: packet, gcr bit15 rule, range and poll clamping", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("plain") {
        Buf b;
        // g 0x4000 -> 0xC000; t = 0x80 + 0x100 + 0xFF = 0x27F; poll 0x100 >> 4 = 0x10
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0x4000, 0x0000AB1234567880ull, 0x100, 0x100);
        expect_packet(b, p, {0xC0065800u, 0u, 2u, 0u, 0x12345678u, 0xABu, 0x10u, 0xC000u});
    }
    SECTION("size clamped to the end of the 48-bit space, poll clamped, gcr masked") {
        Buf b;
        // sz = min(0x1000FF, 0xFFFFFFFFFF00 - 0xFFFFFFFF0000 = 0xFF00) -> dw2 0xFF
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0xFFF80001u, 0xFFFFFFFF0000ull, 0x100000, 0xFFFFFFFFu);
        expect_packet(b, p, {0xC0065800u, 0u, 0xFFu, 0u, 0xFFFFFF00u, 0xFFu, 0xFFFFu, 1u});
    }
    SECTION("size bits 40..47 land in dw3") {
        Buf b;
        // sz = 0x1000000000FF: dw2 (u32)(sz >> 8) = 0, dw3 (sz >> 40) & 0xFF = 0x10
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0, 0, 0x100000000000ull, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0x10u, 0u, 0u, 0u, 0u});
    }
    SECTION("(base & 0xFF) + size is wrapped to 48 bits") {
        Buf b;
        // (0x80 + 0xFFFF000000000000) & 0xFFFFFFFFFFFF = 0x80; + 0xFF = 0x17F
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0, 0x80, 0xFFFF000000000000ull, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 1u, 0u, 0u, 0u, 0u, 0u});
    }
    SECTION("gcr with bits 14/15 = 0b11 is not changed") {
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0xC3A1, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0xC3A1u});
    }
}

TEST_CASE("AcbAcquireMem: workaround mask variants", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("W = 2, (g & 0x108) == 0x108 -> clear bits 2 and 3") {
        tst::set_workaround_mask(2);
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0x10C, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0x100u});
    }
    SECTION("W = 2 without both bits 3 and 8 -> unchanged") {
        tst::set_workaround_mask(2);
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0x104, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0x104u});
    }
    SECTION("W = 1, (g & 0x2A0) == 0 -> g &= 0xFFFFFD53, no extra packet") {
        tst::set_workaround_mask(1);
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0x15F, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0x153u});
    }
    SECTION("W = 1 without bit 8 -> unchanged") {
        tst::set_workaround_mask(1);
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0xA8, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0xA8u});
    }
    SECTION("W = 1, (g & 0x2A0) != 0 -> extra ACQUIRE_MEM first, then g without bit 8") {
        tst::set_workaround_mask(1);
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0x1A8, 0, 0x100, 0x40);
        expect_packet(b, p,
                      {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 4u, 0x100u,    // extra
                       0xC0065800u, 0u, 1u, 0u, 0u, 0u, 4u, 0xA8u});   // main
    }
    SECTION("W = 3 behaves as bit0 set") {
        tst::set_workaround_mask(3);
        Buf b;
        u32 *p = agc::sceAgcAcbAcquireMem(&b.cb, 0x15F, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0x153u});
    }
    SECTION("extra packet written but main does not fit -> NULL, extra stays") {
        tst::set_workaround_mask(1);
        Buf b(12);
        CHECK(agc::sceAgcAcbAcquireMem(&b.cb, 0x1A8, 0, 0, 0) == nullptr);
        CHECK(b.used() == 8);
        CHECK(b.oos.calls == 1);
        CHECK(b.oos.last_required == 8u);
        expect_dwords(b.at(0), {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0x100u, kSentinel});
    }
    SECTION("extra packet does not fit -> NULL, nothing written") {
        tst::set_workaround_mask(1);
        Buf b(7);
        CHECK(agc::sceAgcAcbAcquireMem(&b.cb, 0x1A8, 0, 0, 0) == nullptr);
        CHECK(b.used() == 0);
        expect_untouched(b);
    }
}

TEST_CASE("AcbDispatchIndirect / AcbEventWrite / AcbJump / AcbRewind", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("DispatchIndirect: flags & 0xA038 | trace[10] | 0x41") {
        tst::set_trace_initiator(10, 0x00100000u);
        Buf b;
        u32 *p = agc::sceAgcAcbDispatchIndirect(&b.cb, 0x123456789ABCDEF0ull, 0xFFFFFFFFu);
        expect_packet(b, p, {0xC0021600u, 0x9ABCDEF0u, 0x12345678u, 0x0010A079u});
    }
    SECTION("DispatchIndirect without trace mask and flags") {
        tst::set_trace_initiator(9, 0xFFFF0000u); // the direct-dispatch mask must not be used
        Buf b;
        u32 *p = agc::sceAgcAcbDispatchIndirect(&b.cb, 0x1000, 0);
        expect_packet(b, p, {0xC0021600u, 0x1000u, 0u, 0x41u});
    }
    SECTION("EventWrite: index 4 only for event 7") {
        Buf b;
        CHECK(agc::sceAgcAcbEventWrite(&b.cb, 7) == b.at(0));
        CHECK(agc::sceAgcAcbEventWrite(&b.cb, 0x4F) == b.at(2));
        CHECK(agc::sceAgcAcbEventWrite(&b.cb, 0x47) == b.at(4)); // & 0x3F = 7 but != 7
        CHECK(b.used() == 6);
        expect_dwords(b.at(0), {0xC0004600u, 0x407u, 0xC0004600u, 0x0Fu, 0xC0004600u, 0x07u});
    }
    SECTION("Jump: chain + valid bits, policy in 28-29") {
        Buf b;
        u32 *p = agc::sceAgcAcbJump(&b.cb, 0xFF, 0x123456789ABCDEF3ull, 0xFFFFFFFFu);
        expect_packet(b, p, {0xC0023F00u, 0x9ABCDEF0u, 0x12345678u, 0x3F9FFFFFu});
    }
    SECTION("Jump policy 1 size 0x10") {
        Buf b;
        u32 *p = agc::sceAgcAcbJump(&b.cb, 1, 0x2000, 0x10);
        expect_packet(b, p, {0xC0023F00u, 0x2000u, 0u, 0x1F900010u});
    }
    SECTION("Rewind") {
        Buf b;
        CHECK(agc::sceAgcAcbRewind(&b.cb, 1, 3) == b.at(0));
        CHECK(agc::sceAgcAcbRewind(&b.cb, 0, 0) == b.at(2));
        expect_dwords(b.at(0), {0xC0005900u, 0x81000000u, 0xC0005900u, 0u, kSentinel});
    }
}

TEST_CASE("AcbAtomicMem / AcbCondExec / AcbCopyData / AcbPrimeUtcl2", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("AtomicMem") {
        Buf b;
        u32 *p = agc::sceAgcAcbAtomicMem(&b.cb, 0xFF, 0x1F, 0x1122334455667788ull, 0xFE,
                                         0xAAAABBBBCCCCDDDDull, 0x0102030405060708ull, 0x12345);
        expect_packet(b, p,
                      {0xC0071E00u, 0x04000F7Fu, 0x55667788u, 0x11223344u, 0xCCCCDDDDu,
                       0xAAAABBBBu, 0x05060708u, 0x01020304u, 0x48Du});
    }
    SECTION("AtomicMem loop interval clamped to 0xFFF") {
        Buf b;
        u32 *p = agc::sceAgcAcbAtomicMem(&b.cb, 1, 0, 0, 0, 0, 0, 0xFFFFFFFFu);
        expect_packet(b, p, {0xC0071E00u, 1u, 0u, 0u, 0u, 0u, 0u, 0u, 0xFFFu});
    }
    SECTION("CondExec") {
        Buf b;
        u32 *p = agc::sceAgcAcbCondExec(&b.cb, 0x123456789ABCDEF7ull, 0x12345);
        expect_packet(b, p, {0xC0032200u, 0x9ABCDEF4u, 0x12345678u, 0u, 0x2345u});
    }
    SECTION("CopyData") {
        Buf b;
        u32 *p = agc::sceAgcAcbCopyData(&b.cb, 0x1F, 0xFF, 0x1111222233334444ull, 0x12, 5,
                                        0x5555666677778888ull, 3, 2);
        expect_packet(b, p,
                      {0xC0044000u, 0x06012F02u, 0x77778888u, 0x55556666u, 0x33334444u,
                       0x11112222u});
    }
    SECTION("CopyData write confirm") {
        Buf b;
        u32 *p = agc::sceAgcAcbCopyData(&b.cb, 0, 0, 0, 0, 0, 0, 0, 1);
        expect_packet(b, p, {0xC0044000u, 0x00100000u, 0u, 0u, 0u, 0u});
    }
    SECTION("PrimeUtcl2") {
        Buf b;
        u32 *p = agc::sceAgcAcbPrimeUtcl2(&b.cb, 0xFF, 3, 0x123456789ABCDEFFull, 0x12345);
        expect_packet(b, p, {0xC0035D00u, 0x0Fu, 0x9ABCC000u, 0x12345678u, 0x2345u});
    }
}

TEST_CASE("AcbDmaData: dword layout and special source selectors", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("selector bits 2/3 to 26..29") {
        Buf b;
        u32 *p = agc::sceAgcAcbDmaData(&b.cb, 8, 1, 0x1111222233334444ull, 4, 3,
                                       0x5555666677778888ull, 0x100, 0, 0);
        expect_packet(b, p,
                      {0xC0055000u, 0x02006000u, 0x77778888u, 0x55556666u, 0x33334444u,
                       0x11112222u, 0x24000100u});
    }
    SECTION("low selector bits, flags, byte count mask") {
        Buf b;
        u32 *p = agc::sceAgcAcbDmaData(&b.cb, 5, 2, 0x1000, 0x0A, 1, 0x2000, 0x04000010u, 1, 1);
        expect_packet(b, p, {0xC0055000u, 0x44102000u, 0x2000u, 0u, 0x1000u, 0u, 0xD8000010u});
    }
    // AMBIGUOUS: the description says the special selectors "replace the source address"; we read
    // that dw1/dw6 still use the caller's srcSel bits (0x25 & 3 = 1, bit2 set) and only dw2/dw3
    // change.
    SECTION("srcSel 0x25 -> source 0x30184") {
        Buf b;
        u32 *p = agc::sceAgcAcbDmaData(&b.cb, 0, 0, 0, 0x25, 0, 0xFFFFFFFFFFFFFFFFull, 4, 0, 0);
        expect_packet(b, p, {0xC0055000u, 0x20000000u, 0x30184u, 0u, 0u, 0u, 0x04000004u});
    }
    SECTION("srcSel 0x24 -> source 0x3017C") {
        Buf b;
        u32 *p = agc::sceAgcAcbDmaData(&b.cb, 0, 0, 0, 0x24, 0, 0xFFFFFFFFFFFFFFFFull, 4, 0, 0);
        expect_packet(b, p, {0xC0055000u, 0u, 0x3017Cu, 0u, 0u, 0u, 0x04000004u});
    }
    SECTION("srcSel 0x14 -> source 0x30174") {
        Buf b;
        u32 *p = agc::sceAgcAcbDmaData(&b.cb, 0, 0, 0, 0x14, 0, 0xFFFFFFFFFFFFFFFFull, 4, 0, 0);
        expect_packet(b, p, {0xC0055000u, 0u, 0x30174u, 0u, 0u, 0u, 0x04000004u});
    }
}

TEST_CASE("AcbAtomicGds and the 8-bit-opcode variant", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("AtomicGds full fields") {
        Buf b;
        u32 *p = agc::sceAgcAcbAtomicGds(&b.cb, 0x27F, 1, 3, 0xFF, 0x12345678ull, 0xABCD,
                                         0xFFFFFFFFu, 0xCAFEBABEu, 0x1111222233334444ull,
                                         0x5555666677778888ull);
        // opFlags 0x27F: bit 9 lands in bit 16 ((opFlags << 7) masked with 0x1007F), bit 5 -> 18,
        // bit 6 -> 20.
        expect_packet(b, p,
                      {0xC0091D00u, 0x0015007Fu, 0x13Fu, 0x5678u, 0xABCDu, 0x00FF00FFu,
                       0xCAFEBABEu, 0x33334444u, 0x11112222u, 0x77778888u, 0x55556666u});
    }
    SECTION("AtomicGds mode 1 with bit5 clear sets bit 17") {
        Buf b;
        u32 *p = agc::sceAgcAcbAtomicGds(&b.cb, 0x05, 1, 0, 0x40, 0x10, 0x20, 0x12345678u, 0, 0, 0);
        expect_packet(b, p,
                      {0xC0091D00u, 0x00020005u, 0u, 0x10u, 0x20u, 0x00340078u, 0u, 0u, 0u, 0u,
                       0u});
    }
    SECTION("Op8 keeps opcode bit 7, bit9 -> bit16") {
        Buf b;
        u32 *p = agc::agcAcbAtomicGdsOp8(&b.cb, 0x2FF, 0, 0, 0, 0, 0, 0, 0, 0, 0);
        expect_packet(b, p, {0xC0091D00u, 0x001500FFu, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u});
    }
    SECTION("Op8 mode 1") {
        Buf b;
        u32 *p = agc::agcAcbAtomicGdsOp8(&b.cb, 0x85, 1, 1, 0x3F, 1, 2, 0, 0, 1, 2);
        expect_packet(b, p, {0xC0091D00u, 0x00020085u, 0x13Fu, 1u, 2u, 0u, 0u, 1u, 0u, 2u, 0u});
    }
}

TEST_CASE("AcbWriteData: packet, address not masked, truncation", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("three dwords") {
        Buf b;
        const u32 data[3] = {0xA, 0xB, 0xC};
        u32 *p = agc::sceAgcAcbWriteData(&b.cb, 5, 2, 0x1122334455667788ull, data, 3, 1, 1);
        expect_packet(b, p, {0xC0053700u, 0x04110500u, 0x55667788u, 0x11223344u, 0xAu, 0xBu, 0xCu});
    }
    SECTION("(uint8)dstSel == 0 drops write confirm; one dword") {
        Buf b;
        const u32 data[1] = {0x77};
        u32 *p = agc::sceAgcAcbWriteData(&b.cb, 0x100, 0, 0x1003, data, 1, 0, 1);
        expect_packet(b, p, {0xC0033700u, 0u, 0x1003u, 0u, 0x77u});
    }
    // AMBIGUOUS: the only way to make the second reservation fail after ReserveSoft(n + 4)
    // succeeded is 32-bit wrap of n + 4 (n = 0xFFFFFFFD -> ReserveSoft(1)). We read the
    // description's u32 arithmetic literally: header written with count field (n + 2) << 16,
    // ReserveStrict(n - 1) fails through the callback and the header pointer is returned.
    SECTION("second reservation fails -> truncated packet, header pointer returned") {
        Buf b;
        const u32 data[1] = {0x99};
        u32 *p = agc::sceAgcAcbWriteData(&b.cb, 5, 0, 0x2000, data, 0xFFFFFFFDu, 0, 0);
        REQUIRE(p == b.at(0));
        CHECK(b.used() == 5);
        CHECK(b.oos.calls == 1);
        CHECK(b.oos.last_required == 0xFFFFFFFCu);
        expect_dwords(b.at(0), {0xFFFF3700u, 0x500u, 0x2000u, 0u, 0x99u, kSentinel});
    }
}

TEST_CASE("AcbWaitRegMem: 32/64-bit waits with driver markers", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("size 0") {
        Buf b;
        u32 *p = agc::sceAgcAcbWaitRegMem(&b.cb, 0, 0xF, 3, 0x0001ABCD12345677ull,
                                          0xFFFFFFFF00000005ull, 0x00000000FFFF0000ull, 0x1234);
        expect_packet(b, p,
                      cat({ud4(0xC801ABCDu, 1, 0x12345677u),
                           {0xC0053C00u, 0x06000017u, 0x12345674u, 0x0001ABCDu, 5u, 0xFFFF0000u,
                            0x123u},
                           ud3(0xC8000000u, 1)}));
        REQUIRE(g_fake.ud.size() == 2);
        CHECK(g_fake.ud[0].bytes == 4u);
        CHECK(g_fake.ud[1].bytes == 0u);
    }
    SECTION("size 1") {
        Buf b;
        u32 *p = agc::sceAgcAcbWaitRegMem(&b.cb, 1, 0xF, 3, 0x0001ABCD12345677ull,
                                          0xFFFFFFFF00000005ull, 0x00000000FFFF0000ull, 0x200000);
        expect_packet(b, p,
                      cat({ud4(0xC802ABCDu, 1, 0x12345677u),
                           {0xC0079300u, 0x06000017u, 0x12345670u, 0x0001ABCDu, 5u, 0xFFFFFFFFu,
                            0xFFFF0000u, 0u, 0xFFFFu},
                           ud3(0xC8000000u, 1)}));
    }
    SECTION("address high bits above 0x3FFFF are dropped in the packet, & 0xFFFF in the marker") {
        Buf b;
        u32 *p = agc::sceAgcAcbWaitRegMem(&b.cb, 0, 0, 0, 0xFFFFFFFF00000010ull, 0, 0, 0);
        expect_packet(b, p,
                      cat({ud4(0xC801FFFFu, 1, 0x10u),
                           {0xC0053C00u, 0x10u, 0x10u, 0x3FFFFu, 0u, 0u, 0u},
                           ud3(0xC8000000u, 1)}));
    }
    SECTION("size other than 0/1 -> NULL, nothing written") {
        Buf b;
        CHECK(agc::sceAgcAcbWaitRegMem(&b.cb, 2, 0, 0, 0x1000, 0, 0, 0) == nullptr);
        CHECK(agc::sceAgcAcbWaitRegMem(&b.cb, -1, 0, 0, 0x1000, 0, 0, 0) == nullptr);
        CHECK(b.used() == 0);
        CHECK(g_fake.ud.empty());
        expect_untouched(b);
    }
}

TEST_CASE("Acb markers: set / push / pop and span variants", "[agc][builders][acb][markers]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("SetMarker uses strlen") {
        Buf b;
        u32 *p = agc::sceAgcAcbSetMarker(&b.cb, "abc", 0x11223344u);
        expect_packet(b, p, {kSetTag | 4u, 0x11223344u, 1u, 0x7E000003u});
        REQUIRE(g_fake.markers.size() == 1);
        CHECK(g_fake.markers[0].kind == 0);
        CHECK(g_fake.markers[0].dst == b.at(0));
        CHECK(g_fake.markers[0].pipe == 1);
        CHECK(g_fake.markers[0].text == "abc");
        CHECK(g_fake.markers[0].bytes == 3u);
    }
    SECTION("SetMarker with NULL name -> length 0") {
        Buf b;
        u32 *p = agc::sceAgcAcbSetMarker(&b.cb, nullptr, 5);
        expect_packet(b, p, {kSetTag | 3u, 5u, 1u});
        REQUIRE(g_fake.markers.size() == 1);
        CHECK(g_fake.markers[0].bytes == 0u);
    }
    SECTION("SetMarkerSpan uses the explicit length") {
        Buf b;
        u32 *p = agc::sceAgcAcbSetMarkerSpan(&b.cb, "abcdefgh", 5, 0x77);
        expect_packet(b, p,
                      {kSetTag | 9u, 0x77u, 1u, 0x7E000003u, 0x7E000004u, 0x7E000005u,
                       0x7E000006u, 0x7E000007u, 0x7E000008u});
        REQUIRE(g_fake.markers.size() == 1);
        CHECK(g_fake.markers[0].text == "abcde");
        CHECK(g_fake.markers[0].bytes == 5u);
    }
    SECTION("PushMarker and PushMarkerSpan") {
        Buf b;
        u32 *p1 = agc::sceAgcAcbPushMarker(&b.cb, "hello world!", 1);
        u32 *p2 = agc::sceAgcAcbPushMarkerSpan(&b.cb, "xy", 2, 2);
        CHECK(p1 == b.at(0));
        CHECK(p2 == b.at(10)); // 12 bytes -> 3 + 7 = 10 dwords
        CHECK(b.used() == 14);
        CHECK(Hex{b.mem[0]} == Hex{kPushTag | 10u});
        CHECK(Hex{b.mem[10]} == Hex{kPushTag | 4u});
        REQUIRE(g_fake.markers.size() == 2);
        CHECK(g_fake.markers[0].kind == 1);
        CHECK(g_fake.markers[0].text == "hello world!");
        CHECK(g_fake.markers[1].text == "xy");
        CHECK(g_fake.markers[1].pipe == 1);
    }
    SECTION("PopMarker") {
        Buf b;
        u32 *p = agc::sceAgcAcbPopMarker(&b.cb);
        expect_packet(b, p, {kPopTag | 3u, 0u, 1u});
    }
    SECTION("driver returning a count other than the packet size -> NULL, cursor unchanged") {
        g_fake.marker_delta = 1;
        Buf b;
        CHECK(agc::sceAgcAcbSetMarker(&b.cb, "abc", 0) == nullptr);
        CHECK(agc::sceAgcAcbPushMarkerSpan(&b.cb, "abc", 3, 0) == nullptr);
        CHECK(agc::sceAgcAcbPopMarker(&b.cb) == nullptr);
        CHECK(b.used() == 0);
    }
}

TEST_CASE("Dcb markers use pipe 0", "[agc][builders][dcb][markers]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    Buf b;
    CHECK(agc::sceAgcDcbSetMarker(&b.cb, "abc", 9) == b.at(0));
    CHECK(agc::sceAgcDcbSetMarkerSpan(&b.cb, "abcd", 4, 9) == b.at(4));
    CHECK(agc::sceAgcDcbPushMarker(&b.cb, nullptr, 9) == b.at(8));
    CHECK(agc::sceAgcDcbPushMarkerSpan(&b.cb, "abcdefgh", 8, 9) == b.at(11));
    CHECK(agc::sceAgcDcbPopMarker(&b.cb) == b.at(20)); // 8 bytes -> 2 + 7 = 9 dwords
    CHECK(b.used() == 23);
    REQUIRE(g_fake.markers.size() == 5);
    for (const auto &m : g_fake.markers) {
        CHECK(m.pipe == 0);
    }
    CHECK(g_fake.markers[0].kind == 0);
    CHECK(g_fake.markers[1].kind == 0);
    CHECK(g_fake.markers[1].text == "abcd");
    CHECK(g_fake.markers[2].kind == 1);
    CHECK(g_fake.markers[3].kind == 1);
    CHECK(g_fake.markers[3].bytes == 8u);
    CHECK(g_fake.markers[4].kind == 2);
    expect_dwords(b.at(20), {kPopTag | 3u, 0u, 0u, kSentinel});
}

TEST_CASE("SetFlip and WaitUntilSafeForRendering forward to the driver", "[agc][builders][driver]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("DcbSetFlip") {
        Buf b;
        u32 *p = agc::sceAgcDcbSetFlip(&b.cb, 7, 3, 0x11, 0x123456789ull);
        REQUIRE(p == b.at(0));
        CHECK(b.used() == 0x40);
        REQUIRE(g_fake.flips.size() == 1);
        const FlipCall &f = g_fake.flips[0];
        CHECK(f.cursor == &b.cb.cursor);
        CHECK(f.n == 0x40u);
        CHECK(f.pipe == 0);
        CHECK(f.a0 == 7);
        CHECK(f.a1 == 3);
        CHECK(f.a2 == 0x11u);
        CHECK(f.a3 == 0x123456789ll);
        CHECK(Hex{b.mem[0x3F]} == Hex{kFlipFill + 0x3F});
    }
    SECTION("AcbSetFlip uses pipe 1") {
        Buf b;
        CHECK(agc::sceAgcAcbSetFlip(&b.cb, 1, 2, 3, 4) == b.at(0));
        REQUIRE(g_fake.flips.size() == 1);
        CHECK(g_fake.flips[0].pipe == 1);
    }
    SECTION("SetFlip driver error -> NULL") {
        g_fake.flip_rc = static_cast<i32>(0x8029000Au);
        Buf b;
        CHECK(agc::sceAgcDcbSetFlip(&b.cb, 1, 99, 3, 4) == nullptr);
        CHECK(agc::sceAgcAcbSetFlip(&b.cb, 1, 99, 3, 4) == nullptr);
        CHECK(g_fake.flips.size() == 2);
    }
    SECTION("DcbWaitUntilSafeForRendering") {
        Buf b;
        u32 *p = agc::sceAgcDcbWaitUntilSafeForRendering(&b.cb, 5, 2);
        REQUIRE(p == b.at(0));
        CHECK(b.used() == 0x20);
        REQUIRE(g_fake.waits.size() == 1);
        CHECK(g_fake.waits[0].cursor == &b.cb.cursor);
        CHECK(g_fake.waits[0].n == 0x20u);
        CHECK(g_fake.waits[0].pipe == 0);
        CHECK(g_fake.waits[0].a0 == 5);
        CHECK(g_fake.waits[0].a1 == 2);
    }
    SECTION("AcbWaitUntilSafeForRendering uses pipe 1; error -> NULL") {
        Buf b;
        // arg1 0xFFFFFFFF reaches the driver as buffer index -1 (forwarded unchanged)
        CHECK(agc::sceAgcAcbWaitUntilSafeForRendering(&b.cb, 5, 0xFFFFFFFFu) == b.at(0));
        g_fake.wait_rc = -1;
        CHECK(agc::sceAgcAcbWaitUntilSafeForRendering(&b.cb, 5, 2) == nullptr);
        REQUIRE(g_fake.waits.size() == 2);
        CHECK(g_fake.waits[0].pipe == 1);
        CHECK(g_fake.waits[0].a1 == -1);
    }
}

TEST_CASE("MemSemaphore with driver markers (Acb and Dcb)", "[agc][builders][driver]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("Acb signal (6): begin marker, NOP padding of e dwords, semaphore") {
        Buf b;
        u32 *p = agc::sceAgcAcbMemSemaphore(&b.cb, 0x0000BEEF12345678ull, 1, 3, 6);
        expect_packet(b, p,
                      cat({ud4(0xC901BEEFu, 1, 0x12345678u),
                           {0xC0011000u, kSentinel, kSentinel}, // sceAgcCbNop(cb, 3)
                           {0xC0023900u, 0x12345678u, 0xBEEFu, 0xC0110000u}}));
        CHECK(g_fake.ud.size() == 1);
    }
    SECTION("Acb wait (7): begin marker, semaphore, end marker") {
        Buf b;
        u32 *p = agc::sceAgcAcbMemSemaphore(&b.cb, 0x0000BEEF1234567Dull, 0, 0, 7);
        expect_packet(b, p,
                      cat({ud4(0xC902BEEFu, 1, 0x1234567Du),
                           {0xC0023900u, 0x12345678u, 0xBEEFu, 0xE0000000u},
                           ud3(0xC9000000u, 1)}));
    }
    SECTION("Acb other semSel: neither padding nor end marker") {
        Buf b;
        u32 *p = agc::sceAgcAcbMemSemaphore(&b.cb, 0x1000, 0, 1, 5);
        expect_packet(b, p,
                      cat({ud4(0xC9020000u, 1, 0x1000u),
                           {0xC0023900u, 0x1000u, 0u, 0xA0100000u}}));
    }
    SECTION("Dcb wait: begin marker with isAcb 1, end marker with isAcb 0") {
        Buf b;
        u32 *p = agc::sceAgcDcbMemSemaphore(&b.cb, 0x0000BEEF1234567Dull, 1, 0, 7);
        expect_packet(b, p,
                      cat({ud4(0xC902BEEFu, 1, 0x1234567Du),
                           {0xC0023900u, 0x12345678u, 0xBEEFu, 0xE0010000u},
                           ud3(0xC9000000u, 0)}));
    }
    SECTION("Dcb signal") {
        Buf b;
        u32 *p = agc::sceAgcDcbMemSemaphore(&b.cb, 0x2000, 0, 1, 6);
        expect_packet(b, p,
                      cat({ud4(0xC9010000u, 1, 0x2000u),
                           {0xC0011000u, kSentinel, kSentinel},
                           {0xC0023900u, 0x2000u, 0u, 0xC0100000u}}));
    }
}

TEST_CASE("Workload packets forward to the driver", "[agc][builders][driver]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    const u32 indices[2] = {3, 9};
    SECTION("Acb") {
        Buf b;
        CHECK(agc::sceAgcAcbSetWorkloadsActive(&b.cb, 3, addr_of(indices), 2) == b.at(0));
        CHECK(agc::sceAgcAcbSetWorkloadComplete(&b.cb, 3, 5) == b.at(18));
        CHECK(agc::sceAgcAcbSetWorkloadStreamInactive(&b.cb, 4) == b.at(30));
        CHECK(b.used() == 39);
        REQUIRE(g_fake.wl.size() == 3);
        CHECK(g_fake.wl[0].kind == 1);
        CHECK(g_fake.wl[0].dst == b.at(0));
        CHECK(g_fake.wl[0].pipe == 1);
        CHECK(g_fake.wl[0].stream == 3u);
        CHECK(g_fake.wl[0].indices == indices);
        CHECK(g_fake.wl[0].value == 2u);
        CHECK(g_fake.wl[1].kind == 2);
        CHECK(g_fake.wl[1].pipe == 1);
        CHECK(g_fake.wl[1].stream == 3u);
        CHECK(g_fake.wl[1].value == 5u);
        CHECK(g_fake.wl[2].kind == 3);
        CHECK(g_fake.wl[2].pipe == 1);
        CHECK(g_fake.wl[2].stream == 4u);
        CHECK(Hex{b.mem[17]} == Hex{kWlFill + 0x10000u + 17u});
        CHECK(Hex{b.mem[38]} == Hex{kWlFill + 0x30000u + 8u});
    }
    SECTION("Dcb") {
        Buf b;
        CHECK(agc::sceAgcDcbSetWorkloadsActive(&b.cb, 2, addr_of(indices), 1) == b.at(0));
        CHECK(agc::sceAgcDcbSetWorkloadComplete(&b.cb, 2, 63) == b.at(18));
        CHECK(agc::sceAgcDcbSetWorkloadStreamInactive(&b.cb, 2) == b.at(30));
        CHECK(b.used() == 39);
        REQUIRE(g_fake.wl.size() == 3);
        for (const auto &w : g_fake.wl) {
            CHECK(w.pipe == 0);
            CHECK(w.stream == 2u);
        }
        CHECK(g_fake.wl[0].indices == indices);
        CHECK(g_fake.wl[0].value == 1u);
        CHECK(g_fake.wl[1].value == 63u);
    }
    SECTION("driver error -> NULL, cursor unchanged") {
        g_fake.wl_rc = static_cast<i32>(0x8A6C0033u);
        Buf b;
        CHECK(agc::sceAgcAcbSetWorkloadsActive(&b.cb, 0, addr_of(indices), 2) == nullptr);
        CHECK(agc::sceAgcDcbSetWorkloadComplete(&b.cb, 0, 1) == nullptr);
        CHECK(agc::sceAgcAcbSetWorkloadStreamInactive(&b.cb, 0) == nullptr);
        CHECK(b.used() == 0);
        CHECK(g_fake.wl.size() == 3);
    }
}

TEST_CASE("AcbResetQueue: flag combinations", "[agc][builders][acb][reset]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    REQUIRE(agc::agcSetTrustedRange(0, ~u64{0}) == 0); // every caller untrusted -> id bit 22
    SlotFixture s0;
    SlotFixture s1;
    SECTION("bits 1, 7, 8: flush, SH stream copy, acquire 0xC3A1") {
        tst::set_slot(0, s0.view(7, false, 24));
        Buf b;
        u32 *p = agc::sceAgcAcbResetQueue(&b.cb, 0x0182, 0);
        expect_packet(b, p,
                      cat({ud4(0xCE600182u, 1, 7u),
                           {0xC0004600u, 0x407u},
                           {0x51515151u, 0x52525252u, 0x53535353u, 0x54545454u, 0x55555555u,
                            0x56565656u},
                           {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0xC3A1u},
                           ud3(0xCEE00000u, 1)}));
        REQUIRE(g_fake.ud.size() == 2);
        CHECK(g_fake.ud[0].bytes == 4u);
    }
    SECTION("bit 6 only on a trusted slot: acquire 0xC1") {
        tst::set_slot(1, s1.view(9, true, 24));
        Buf b;
        u32 *p = agc::sceAgcAcbResetQueue(&b.cb, 0x0040, 1);
        expect_packet(b, p,
                      cat({ud4(0xCE400040u, 1, 9u),
                           {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0xC1u},
                           ud3(0xCEC00000u, 1)}));
    }
    SECTION("bit 15 uses the active slot instead of queueSlot") {
        tst::set_slot(0, s0.view(7, false, 24));
        tst::set_slot(1, s1.view(9, true, 24));
        tst::set_active_slot(1, true);
        Buf b;
        u32 *p = agc::sceAgcAcbResetQueue(&b.cb, 0x8000, 0);
        expect_packet(b, p, cat({ud4(0xCE408000u, 1, 9u), ud3(0xCEC00000u, 1)}));
    }
    SECTION("bit 1 with an empty SH stream -> NULL, begin marker stays") {
        tst::set_slot(0, s0.view(7, false, 0));
        Buf b;
        CHECK(agc::sceAgcAcbResetQueue(&b.cb, 0x0002, 0) == nullptr);
        CHECK(b.used() == 4);
        expect_dwords(b.at(0), cat({ud4(0xCE600002u, 1, 7u), {kSentinel}}));
    }
    SECTION("bit 8 wins over bit 6; W = 1 does not touch 0xC3A1 (bit 3 clear)") {
        tst::set_workaround_mask(1);
        tst::set_slot(0, s0.view(7, true, 24));
        Buf b;
        u32 *p = agc::sceAgcAcbResetQueue(&b.cb, 0x0140, 0);
        expect_packet(b, p,
                      cat({ud4(0xCE400140u, 1, 7u),
                           {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0xC3A1u},
                           ud3(0xCEC00000u, 1)}));
    }
}

TEST_CASE("agcAcbCopyActiveShDefaults copies the active slot's SH stream", "[agc][builders][acb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SlotFixture s;
    SECTION("suspend not ready -> NULL") {
        tst::set_slot(0, s.view(7, true, 24));
        Buf b;
        CHECK(agc::agcAcbCopyActiveShDefaults(&b.cb) == nullptr);
        expect_untouched(b);
    }
    SECTION("empty stream -> NULL") {
        tst::set_slot(0, s.view(7, true, 0));
        tst::set_active_slot(0, true);
        Buf b;
        CHECK(agc::agcAcbCopyActiveShDefaults(&b.cb) == nullptr);
        expect_untouched(b);
    }
    SECTION("whole dwords") {
        tst::set_slot(0, s.view(7, true, 24));
        tst::set_active_slot(0, true);
        Buf b;
        u32 *p = agc::agcAcbCopyActiveShDefaults(&b.cb);
        expect_packet(b, p,
                      {0x51515151u, 0x52525252u, 0x53535353u, 0x54545454u, 0x55555555u,
                       0x56565656u});
    }
    SECTION("byte count not a multiple of 4: ceil reserved, only the bytes copied") {
        tst::set_slot(1, s.view(7, true, 10));
        tst::set_active_slot(1, true);
        Buf b;
        u32 *p = agc::agcAcbCopyActiveShDefaults(&b.cb);
        // little endian: bytes 8, 9 copied over the sentinel's low half
        expect_packet(b, p, {0x51515151u, 0x52525252u, 0xDEAD5353u});
    }
}

// =================================================================================================
// A.2 / B.2 / C.2 generic Cb builders
// =================================================================================================

TEST_CASE("CbBranch / CbDispatch / CbCondWrite / CbMemSemaphore", "[agc][builders][cb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("Branch with then target only") {
        Buf b;
        u32 *p = agc::sceAgcCbBranch(&b.cb, 0xFF, 0xF, 0x123456789ABCDEFFull,
                                     0x1111222233334444ull, 0x5555666677778888ull, 2,
                                     0xAAAABBBBCCCCDDDFull, 0x123456, 3, 0, 0x10);
        expect_packet(b, p,
                      {0xC00C3F00u, 0x703u, 0x9ABCDEF8u, 0x12345678u, 0x33334444u, 0x11112222u,
                       0x77778888u, 0x55556666u, 0xCCCCDDDCu, 0xAAAABBBBu, 0x20023456u, 0u, 0u,
                       0u});
    }
    SECTION("Branch with both targets; then address 0 gives control 0") {
        Buf b;
        u32 *p = agc::sceAgcCbBranch(&b.cb, 1, 2, 0x10, 0, 0, 3, 0, 0x40, 1, 0x0000000100000004ull, 8);
        expect_packet(b, p,
                      {0xC00C3F00u, 0x201u, 0x10u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 4u, 1u,
                       0x10000008u});
    }
    SECTION("Dispatch") {
        tst::set_trace_initiator(9, 0x00200000u);
        tst::set_trace_initiator(10, 0x00400000u); // indirect mask must not be used
        Buf b;
        u32 *p = agc::sceAgcCbDispatch(&b.cb, 1, 2, 3, 0xFFFF);
        expect_packet(b, p, {0xC0031500u, 1u, 2u, 3u, 0x0020A079u});
    }
    SECTION("CondWrite") {
        Buf b;
        u32 *p = agc::sceAgcCbCondWrite(&b.cb, 0xF, 7, 0x1111222233334444ull, 0xDEADC0DEu,
                                        0x5555666677778888ull, 0x12, 0xFF);
        expect_packet(b, p,
                      {0xC0074500u, 0x317u, 0x77778888u, 0x55556666u, 0x12u, 0xFFu, 0x33334444u,
                       0x11112222u, 0xDEADC0DEu});
    }
    SECTION("MemSemaphore (bare, no markers)") {
        Buf b;
        u32 *p = agc::sceAgcCbMemSemaphore(&b.cb, 0x0000BEEF1234567Full, 1, 3, 6);
        expect_packet(b, p, {0xC0023900u, 0x12345678u, 0xBEEFu, 0xC0110000u});
        CHECK(g_fake.ud.empty());
    }
}

TEST_CASE("CbNop: header only, count 0x3FFF for one dword, 0 -> NULL", "[agc][builders][cb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    Buf b;
    CHECK(agc::sceAgcCbNop(&b.cb, 0) == nullptr);
    CHECK(b.oos.calls == 0);
    CHECK(b.used() == 0);
    CHECK(agc::sceAgcCbNop(&b.cb, 1) == b.at(0));
    CHECK(agc::sceAgcCbNop(&b.cb, 2) == b.at(1));
    CHECK(agc::sceAgcCbNop(&b.cb, 4) == b.at(3));
    CHECK(b.used() == 7);
    expect_dwords(b.at(0),
                  {0xFFFF1000u, 0xC0001000u, kSentinel, 0xC0021000u, kSentinel, kSentinel,
                   kSentinel, kSentinel});
}

TEST_CASE("CbReleaseMem: fields, gcr bit9 rule, interrupt-only and GDS data", "[agc][builders][cb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("memory write") {
        Buf b;
        u32 *p = agc::sceAgcCbReleaseMem(&b.cb, 0x14, 0x100, 3, 1, 0x123456789ABCDEF7ull, 2,
                                         0x1111222233334444ull, 0, 0, 2, 0xFFFFFFFFu);
        expect_packet(b, p,
                      {0xC0064900u, 0x02300514u, 0x42030000u, 0x9ABCDEF4u, 0x12345678u,
                       0x33334444u, 0x11112222u, 0x07FFFFFFu});
    }
    SECTION("interruptSel 4 zeroes address and data; event > 0x2E uses index 6") {
        Buf b;
        u32 *p = agc::sceAgcCbReleaseMem(&b.cb, 0x2F, 0x200, 0, 0, 0x123456789ABCDEF7ull, 1,
                                         0x1111222233334444ull, 0, 0, 4, 5);
        expect_packet(b, p,
                      {0xC0064900u, 0x0020062Fu, 0x24000000u, 0u, 0u, 0u, 0u, 5u});
    }
    SECTION("dataSel 5 -> data = gdsCount << 16 | gdsOffset") {
        Buf b;
        u32 *p = agc::sceAgcCbReleaseMem(&b.cb, 7, 0, 1, 0, 0x1000, 5, 0xFFFFFFFFFFFFFFFFull,
                                         0x34, 0x12, 0, 0);
        expect_packet(b, p,
                      {0xC0064900u, 0x507u, 0xA0010000u, 0x1000u, 0u, 0x00120034u, 0u, 0u});
    }
}

TEST_CASE("Cb register range and register list builders", "[agc][builders][cb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    const u32 values[3] = {1, 2, 3};
    SECTION("SetShRegisterRangeDirect") {
        Buf b;
        u32 *p = agc::sceAgcCbSetShRegisterRangeDirect(&b.cb, 0x12345, values, 3);
        expect_packet(b, p, {0xC0037600u, 0x2345u, 1u, 2u, 3u});
    }
    SECTION("SetShRegisterRangeDirect with NULL values leaves the payload") {
        Buf b;
        u32 *p = agc::sceAgcCbSetShRegisterRangeDirect(&b.cb, 0x10, nullptr, 2);
        expect_packet(b, p, {0xC0027600u, 0x10u, kSentinel, kSentinel});
    }
    SECTION("SetShRegisterRangeDirect count 0 writes just the header") {
        Buf b;
        u32 *p = agc::sceAgcCbSetShRegisterRangeDirect(&b.cb, 0x10, values, 0);
        expect_packet(b, p, {0xC0007600u, 0x10u});
    }
    SECTION("RangeDirect count + 2 == 0 -> NULL") {
        Buf b;
        CHECK(agc::sceAgcCbSetShRegisterRangeDirect(&b.cb, 0x10, nullptr, 0xFFFFFFFEu) == nullptr);
        CHECK(agc::sceAgcCbSetUcRegisterRangeDirect(&b.cb, 0x10, nullptr, 0xFFFFFFFEu) == nullptr);
        CHECK(b.used() == 0);
    }
    SECTION("SetUcRegisterRangeDirect") {
        Buf b;
        u32 *p = agc::sceAgcCbSetUcRegisterRangeDirect(&b.cb, 0xC0123, values, 3);
        expect_packet(b, p, {0xC0037900u, 0x0123u, 1u, 2u, 3u});
    }
    const agc::RegPair regs[6] = {{0x10, 1}, {0x11, 2}, {0x12, 3}, {0x20, 4}, {0x05, 5}, {0x06, 6}};
    SECTION("SetShRegistersDirect: one packet per run of consecutive offsets, list order") {
        Buf b;
        u32 *p = agc::sceAgcCbSetShRegistersDirect(&b.cb, regs, 6);
        expect_packet(b, p,
                      {0xC0037600u, 0x10u, 1u, 2u, 3u, 0xC0017600u, 0x20u, 4u, 0xC0027600u, 5u,
                       5u, 6u});
    }
    SECTION("SetUcRegistersDirect") {
        Buf b;
        u32 *p = agc::sceAgcCbSetUcRegistersDirect(&b.cb, regs, 6);
        expect_packet(b, p,
                      {0xC0037900u, 0x10u, 1u, 2u, 3u, 0xC0017900u, 0x20u, 4u, 0xC0027900u, 5u,
                       5u, 6u});
    }
    SECTION("RegistersDirect count 0 -> NULL") {
        Buf b;
        CHECK(agc::sceAgcCbSetShRegistersDirect(&b.cb, regs, 0) == nullptr);
        CHECK(agc::sceAgcCbSetUcRegistersDirect(&b.cb, regs, 0) == nullptr);
        CHECK(b.used() == 0);
    }
    SECTION("a run that does not fit is skipped; result is the first written packet") {
        const agc::RegPair r2[7] = {{0x10, 1}, {0x11, 2}, {0x12, 3}, {0x13, 4},
                                    {0x14, 5}, {0x15, 6}, {0x30, 9}};
        Buf b(7);
        u32 *p = agc::sceAgcCbSetShRegistersDirect(&b.cb, r2, 7);
        CHECK(b.oos.calls == 1);
        CHECK(b.oos.last_required == 8u);
        expect_packet(b, p, {0xC0017600u, 0x30u, 9u});
    }
    SECTION("no run fits -> NULL") {
        Buf b(2);
        CHECK(agc::sceAgcCbSetUcRegistersDirect(&b.cb, regs, 1) == nullptr);
        expect_untouched(b);
    }
}

TEST_CASE("agcCbFillMemory: shader regs, user data, CU masks, dispatch, restore",
          "[agc][builders][cb][fill]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    // Fake internal shader object with only the offsets C.2 names.
    alignas(8) std::array<std::uint8_t, 0x30> desc{};      // u64 @0 -> slot struct, u16 @0x2A = u
    alignas(8) std::array<std::uint8_t, 8> slot_struct{};  // u16 @2 = start slot s
    alignas(8) std::array<std::uint8_t, 0x18> info{};      // u32 @0x10 = initiator
    const agc::RegPair shregs[2] = {{0x50, 0x111}, {0x51, 0x222}};
    put(slot_struct, 2, 0x0C, 2);
    put(desc, 0, addr_of(slot_struct.data()), 8);
    put(info, 0x10, 0xFFFF, 4);
    agc::Shader sh{};
    sh.extra = addr_of(desc.data());
    sh.sh_regs = addr_of(shregs);
    sh.info = addr_of(info.data());
    sh.num_sh_regs = 2;
    tst::set_fill_shader(&sh);
    tst::set_restore_pairs(agc::RegPair{0x10216, 0xAAAA}, agc::RegPair{0x217, 0xBBBB});
    tst::set_trace_initiator(9, 0x1000u);
    const u64 pattern[2] = {0x1111222233334444ull, 0x5555666677778888ull};

    SECTION("u = 9, default SoC mask") {
        put(desc, 0x2A, 9, 2);
        Buf b;
        u32 *p = agc::agcCbFillMemory(&b.cb, 0x0000123487654320ull, pattern, 0x20010);
        expect_packet(b, p,
                      {0xC0027600u, 0x50u, 0x111u, 0x222u,
                       0xC0097600u, 0x24Cu, 0x87654320u, 0x00101234u, 0x2001u, 0x0004BFACu,
                       0x33334444u, 0x11112222u, 0x77778888u, 0x55556666u, 3u,
                       0xC0017600u, 0x216u, 0x0003FCFFu,
                       0xC0017600u, 0x217u, 0x0003FCFFu,
                       0xC0031500u, 16u, 1u, 1u, 0xB079u,
                       0xC0017600u, 0x0216u, 0xAAAAu,
                       0xC0017600u, 0x217u, 0xBBBBu});
    }
    SECTION("u = 2 and SoC 0x840FC0 (low 5 bits ignored)") {
        put(desc, 0x2A, 2, 2);
        tst::set_soc_id(0x840FDFu);
        Buf b;
        u32 *p = agc::agcCbFillMemory(&b.cb, 0x1000, pattern, 0x10);
        expect_packet(b, p,
                      {0xC0027600u, 0x50u, 0x111u, 0x222u,
                       0xC0027600u, 0x24Cu, 0x1000u, 0x00100000u,
                       0xC0017600u, 0x216u, 0x00FF00FFu,
                       0xC0017600u, 0x217u, 0x00FF00FFu,
                       0xC0031500u, 16u, 1u, 1u, 0xB079u,
                       0xC0017600u, 0x0216u, 0xAAAAu,
                       0xC0017600u, 0x217u, 0xBBBBu});
    }
    // AMBIGUOUS: C.2 says failures in steps 3-6 only skip that packet and the result is NULL when
    // step 1 failed; it does not say the function stops after a step-1 failure. We read that it
    // carries on, so the 3-dword CU-mask packet that fits is still written.
    SECTION("first step fails -> NULL; later packets that fit are still written") {
        put(desc, 0x2A, 2, 2);
        Buf b(3); // SET_SH_REG of 2 regs needs 4; user data needs 4; masks need 3 each
        CHECK(agc::agcCbFillMemory(&b.cb, 0x1000, pattern, 0x10) == nullptr);
        CHECK(b.used() == 3);
        expect_dwords(b.at(0), {0xC0017600u, 0x216u, 0x0003FCFFu, kSentinel});
    }
}

// =================================================================================================
// A.3 / B.3 / C.3 DCB builders
// =================================================================================================

TEST_CASE("Dcb single-register and indirect register loads", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    Buf b;
    const agc::RegPair r{0x12345, 0xCAFE};
    CHECK(agc::sceAgcDcbSetCxRegisterDirect(&b.cb, r) == b.at(0));
    CHECK(agc::sceAgcDcbSetCfRegisterDirect(&b.cb, r) == b.at(3));
    CHECK(agc::sceAgcDcbSetUcRegisterDirect(&b.cb, r) == b.at(6));
    CHECK(agc::sceAgcDcbSetShRegisterDirect(&b.cb, r) == b.at(9));
    CHECK(agc::sceAgcDcbSetCxRegistersIndirect(&b.cb, 0x123456789ABCDEF7ull, 0x12345) == b.at(12));
    CHECK(agc::sceAgcDcbSetShRegistersIndirect(&b.cb, 0x123456789ABCDEF7ull, 0x12345) == b.at(17));
    CHECK(agc::sceAgcDcbSetUcRegistersIndirect(&b.cb, 0x123456789ABCDEF7ull, 0x12345) == b.at(22));
    CHECK(b.used() == 27);
    expect_dwords(b.at(0),
                  {0xC0016900u, 0x2345u, 0xCAFEu, 0xC0016800u, 0x2345u, 0xCAFEu, 0xC0017900u,
                   0x2345u, 0xCAFEu, 0xC0017600u, 0x2345u, 0xCAFEu,
                   0xC0039F00u, 0x9ABCDEF4u, 0x12345678u, 0x80000000u, 0x2345u,
                   0xC0036300u, 0x9ABCDEF4u, 0x12345678u, 0x80000000u, 0x2345u,
                   0xC0036400u, 0x9ABCDEF4u, 0x12345678u, 0x80000000u, 0x2345u, kSentinel});
    SECTION("UCONFIG indirect uses opcode 0x68 on SoC 0x840F00 only") {
        Buf c;
        tst::set_soc_id(0x840F1Fu);
        CHECK(agc::sceAgcDcbSetUcRegistersIndirect(&c.cb, 0x1000, 1) == c.at(0));
        tst::set_soc_id(0x840FC0u);
        CHECK(agc::sceAgcDcbSetUcRegistersIndirect(&c.cb, 0x1000, 1) == c.at(5));
        expect_dwords(c.at(0),
                      {0xC0036800u, 0x1000u, 0u, 0x80000000u, 1u, 0xC0036400u, 0x1000u, 0u,
                       0x80000000u, 1u});
    }
}

TEST_CASE("DcbAcquireMem: packet, whole memory mode, workaround variants", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("plain") {
        Buf b;
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 1, 0x02001FC0u, 0x4000, 0x0000AB1234567880ull,
                                          0x100, 0x100);
        expect_packet(b, p,
                      {0xC0065800u, 0x82001FC0u, 2u, 0u, 0x12345678u, 0xABu, 0x10u, 0xC000u});
    }
    SECTION("coherControl masked to 0x06007FC0, engine 0") {
        Buf b;
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 0, 0xF9FF803Fu, 0, 0, 0, 0xFFFFFFFFu);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0xFFFFu, 0u});
    }
    SECTION("whole memory, gcr bit1 and bit12 set") {
        Buf b;
        // g 0x100A: g' = (g & ~0xB) | 1 = 0x1001, bit12 -> & 0xFFFFEFF7 -> 1
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 0, 0x04000000u, 0x100A, 0x5000, 0x10, 0);
        expect_packet(b, p,
                      {0xC0065800u, 0x04004000u, 0xFFFFFFFEu, 0xFFu, 1u, 0u, 0u, 1u});
    }
    SECTION("whole memory, gcr bit1 clear") {
        Buf b;
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 1, 0x04000000u, 0x18, 0x5000, 0x10, 0);
        expect_packet(b, p,
                      {0xC0065800u, 0x84004000u, 0xFFFFFFFEu, 0xFFu, 1u, 0u, 0u, 0x10u});
    }
    SECTION("W = 2 bit2/3 clear, then whole memory") {
        tst::set_workaround_mask(2);
        Buf b;
        // 0x10E -> 0x102 -> & ~8 = 0x102, bit1 -> (0x102 & 0xFFFFFFF4) | 1 = 0x101
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 0, 0x04000000u, 0x10E, 0, 0, 0);
        expect_packet(b, p,
                      {0xC0065800u, 0x04004000u, 0xFFFFFFFEu, 0xFFu, 1u, 0u, 0u, 0x101u});
    }
    SECTION("W = 1 no extra packet") {
        tst::set_workaround_mask(1);
        Buf b;
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 0, 0, 0x15F, 0, 0, 0);
        expect_packet(b, p, {0xC0065800u, 0u, 0u, 0u, 0u, 0u, 0u, 0x153u});
    }
    SECTION("W = 1 extra packet; main has coher 0 and skips whole-memory") {
        tst::set_workaround_mask(1);
        Buf b;
        u32 *p = agc::sceAgcDcbAcquireMem(&b.cb, 1, 0x04000040u, 0x1A8, 0x0000AB1234567880ull,
                                          0x100, 0x40);
        expect_packet(b, p,
                      {0xC0065800u, 0x84000040u, 2u, 0u, 0x12345678u, 0xABu, 4u, 0x100u,
                       0xC0065800u, 0x80000000u, 2u, 0u, 0x12345678u, 0xABu, 4u, 0xA8u});
    }
    SECTION("W = 1 extra fits but main does not -> NULL") {
        tst::set_workaround_mask(1);
        Buf b(15);
        CHECK(agc::sceAgcDcbAcquireMem(&b.cb, 0, 0, 0x1A8, 0, 0, 0) == nullptr);
        CHECK(b.used() == 8);
    }
}

TEST_CASE("DcbAtomicMem / ClearState / CondExec / Jump / CopyData", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("AtomicMem engine bit 30") {
        Buf b;
        u32 *p = agc::sceAgcDcbAtomicMem(&b.cb, 1, 0xFF, 0x1F, 0xFE, 0x1122334455667788ull,
                                         0xAAAABBBBCCCCDDDDull, 0x0102030405060708ull, 0x12345);
        expect_packet(b, p,
                      {0xC0071E00u, 0x44000F7Fu, 0x55667788u, 0x11223344u, 0xCCCCDDDDu,
                       0xAAAABBBBu, 0x05060708u, 0x01020304u, 0x48Du});
    }
    SECTION("ClearState op & 0xF") {
        Buf b;
        u32 *p = agc::sceAgcDcbClearState(&b.cb, 0x13);
        expect_packet(b, p, {0xC0001200u, 3u});
    }
    SECTION("CondExec") {
        Buf b;
        u32 *p = agc::sceAgcDcbCondExec(&b.cb, 0x123456789ABCDEF7ull, 0x12345);
        expect_packet(b, p, {0xC0032200u, 0x9ABCDEF4u, 0x12345678u, 0u, 0x2345u});
    }
    SECTION("Jump chain/policy") {
        Buf b;
        CHECK(agc::sceAgcDcbJump(&b.cb, 1, 2, 0x123456789ABCDEF3ull, 0x123456) == b.at(0));
        CHECK(agc::sceAgcDcbJump(&b.cb, 0, 0, 0x1000, 8) == b.at(4));
        CHECK(agc::sceAgcDcbJump(&b.cb, 3, 0xFF, 0x1000, 8) == b.at(8));
        expect_dwords(b.at(0),
                      {0xC0023F00u, 0x9ABCDEF0u, 0x12345678u, 0x2F323456u, 0xC0023F00u, 0x1000u,
                       0u, 0x0F200008u, 0xC0023F00u, 0x1000u, 0u, 0x3F300008u});
    }
    SECTION("CopyData encoded selectors") {
        Buf b;
        u32 *p = agc::sceAgcDcbCopyData(&b.cb, 0x1F, 3, 0x1111222233334444ull, 0x0B, 2,
                                        0x5555666677778888ull, 1, 1);
        expect_packet(b, p,
                      {0xC0044000u, 0x46114F05u, 0x77778888u, 0x55556666u, 0x33334444u,
                       0x11112222u});
    }
}

TEST_CASE("DcbDmaData: engine, cpSync and special sources", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("fields") {
        Buf b;
        u32 *p = agc::sceAgcDcbDmaData(&b.cb, 1, 5, 2, 0x1000, 0x0A, 1, 0x2000, 0x04000010u, 1, 1, 1);
        expect_packet(b, p, {0xC0055000u, 0xC4102001u, 0x2000u, 0u, 0x1000u, 0u, 0xD8000010u});
    }
    SECTION("selector bits 2/3") {
        Buf b;
        u32 *p = agc::sceAgcDcbDmaData(&b.cb, 0, 8, 1, 0x1111222233334444ull, 4, 3,
                                       0x5555666677778888ull, 0x100, 0, 0, 0);
        expect_packet(b, p,
                      {0xC0055000u, 0x02006000u, 0x77778888u, 0x55556666u, 0x33334444u,
                       0x11112222u, 0x24000100u});
    }
    // AMBIGUOUS: as for the ACB variant, we read that the selector bits of dw1/dw6 still come
    // from the caller's srcSel (100 = 0x64: & 3 = 0, bit2 set).
    SECTION("special sources depend on the engine") {
        Buf b;
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 0, 0, 0, 0, 100, 0, 0x9999, 4, 0, 0, 0) == b.at(0));
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 1, 0, 0, 0, 100, 0, 0x9999, 4, 0, 0, 0) == b.at(7));
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 0, 0, 0, 0, 0x24, 0, 0x9999, 4, 0, 0, 0) == b.at(14));
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 1, 0, 0, 0, 0x24, 0, 0x9999, 4, 0, 0, 0) == b.at(21));
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 0, 0, 0, 0, 0x14, 0, 0x9999, 4, 0, 0, 0) == b.at(28));
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 1, 0, 0, 0, 0x14, 0, 0x9999, 4, 0, 0, 0) == b.at(35));
        // 0x25 is special on the ACB only
        CHECK(agc::sceAgcDcbDmaData(&b.cb, 0, 0, 0, 0, 0x25, 0, 0x9999, 4, 0, 0, 0) == b.at(42));
        expect_dwords(b.at(0),
                      {0xC0055000u, 0u, 0x30184u, 0u, 0u, 0u, 0x04000004u,
                       0xC0055000u, 1u, 0x30158u, 0u, 0u, 0u, 0x04000004u,
                       0xC0055000u, 0u, 0x3017Cu, 0u, 0u, 0u, 0x04000004u,
                       0xC0055000u, 1u, 0x30150u, 0u, 0u, 0u, 0x04000004u,
                       0xC0055000u, 0u, 0x30174u, 0u, 0u, 0u, 0x04000004u,
                       0xC0055000u, 1u, 0x30148u, 0u, 0u, 0u, 0x04000004u,
                       0xC0055000u, 0x20000000u, 0x9999u, 0u, 0u, 0u, 0x04000004u});
    }
}

TEST_CASE("DcbWriteData and DcbSetCfRegisterRangeDirect", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("WriteData encoded selector, address & ~3") {
        Buf b;
        const u32 data[2] = {0xA, 0xB};
        u32 *p = agc::sceAgcDcbWriteData(&b.cb, 0x0B, 2, 0x1122334455667787ull, data, 2, 1, 1);
        expect_packet(b, p, {0xC0043700u, 0x44110500u, 0x55667784u, 0x11223344u, 0xAu, 0xBu});
    }
    SECTION("WriteData selector with (uint8) 0 drops confirm") {
        Buf b;
        const u32 data[1] = {0x5};
        u32 *p = agc::sceAgcDcbWriteData(&b.cb, 0x100, 0, 0x1000, data, 1, 0, 1);
        expect_packet(b, p, {0xC0033700u, 0u, 0x1000u, 0u, 5u});
    }
    // AMBIGUOUS: truncation only reachable through u32 wrap of n + 4 (see the ACB test).
    SECTION("WriteData truncated") {
        Buf b;
        const u32 data[1] = {0x5};
        u32 *p = agc::sceAgcDcbWriteData(&b.cb, 0x0A, 0, 0x1000, data, 0xFFFFFFFDu, 0, 0);
        REQUIRE(p == b.at(0));
        CHECK(b.used() == 5);
        expect_dwords(b.at(0), {0xFFFF3700u, 0x500u, 0x1000u, 0u, 5u, kSentinel});
    }
    SECTION("SetCfRegisterRangeDirect") {
        Buf b;
        const u32 values[3] = {1, 2, 3};
        u32 *p = agc::sceAgcDcbSetCfRegisterRangeDirect(&b.cb, 0x12345, values, 3);
        expect_packet(b, p, {0xC0036800u, 0x2345u, 1u, 2u, 3u});
    }
    SECTION("SetCfRegisterRangeDirect one value") {
        Buf b;
        const u32 values[1] = {9};
        u32 *p = agc::sceAgcDcbSetCfRegisterRangeDirect(&b.cb, 0x20, values, 1);
        expect_packet(b, p, {0xC0016800u, 0x20u, 9u});
    }
    // AMBIGUOUS: as WriteData, the "copy fails -> header still returned" path needs the u32 wrap
    // of count + 2 (count 0xFFFFFFFE -> ReserveSoft(0)); header count field is count << 16.
    SECTION("SetCfRegisterRangeDirect truncated") {
        Buf b;
        const u32 values[1] = {9};
        u32 *p = agc::sceAgcDcbSetCfRegisterRangeDirect(&b.cb, 0x20, values, 0xFFFFFFFEu);
        REQUIRE(p == b.at(0));
        CHECK(b.used() == 3);
        CHECK(b.oos.last_required == 0xFFFFFFFDu);
        expect_dwords(b.at(0), {0xFFFE6800u, 0x20u, 9u, kSentinel});
    }
}

TEST_CASE("Dcb direct draws and dispatch: initiator bit-5 rule and trace masks",
          "[agc][builders][dcb][draw]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("DispatchIndirect") {
        tst::set_trace_initiator(10, 0x04000000u);
        Buf b;
        u32 *p = agc::sceAgcDcbDispatchIndirect(&b.cb, 0x40, 0x8008);
        expect_packet(b, p, {0xC0011600u, 0x40u, 0x04008049u});
    }
    SECTION("DrawIndexAuto: bit 8 -> 0x20 unless bit 32") {
        tst::set_trace_initiator(2, 0x80000000u);
        Buf b;
        CHECK(agc::sceAgcDcbDrawIndexAuto(&b.cb, 100, 0x100) == b.at(0));
        CHECK(agc::sceAgcDcbDrawIndexAuto(&b.cb, 100, 0x100000100ull) == b.at(3));
        CHECK(agc::sceAgcDcbDrawIndexAuto(&b.cb, 0, 0) == b.at(6));
        expect_dwords(b.at(0),
                      {0xC0012D00u, 100u, 0x80000022u, 0xC0012D00u, 100u, 0x80000002u,
                       0xC0012D00u, 0u, 0x80000002u});
    }
    SECTION("DrawIndex: 0 count becomes 1 in dw1 only") {
        tst::set_trace_initiator(1, 0x00010000u);
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndex(&b.cb, 0, 0x123456789ABCDEF0ull, 0x100);
        expect_packet(b, p,
                      {0xC0042700u, 1u, 0x9ABCDEF0u, 0x12345678u, 0u, 0x00010020u});
    }
    SECTION("DrawIndexOffset") {
        tst::set_trace_initiator(3, 0x00020000u);
        Buf b;
        CHECK(agc::sceAgcDcbDrawIndexOffset(&b.cb, 0x10, 5, 0) == b.at(0));
        CHECK(agc::sceAgcDcbDrawIndexOffset(&b.cb, 0x10, 0, 0x100) == b.at(5));
        expect_dwords(b.at(0),
                      {0xC0033500u, 5u, 0x10u, 5u, 0x00020000u, 0xC0033500u, 1u, 0x10u, 0u,
                       0x00020020u});
    }
    SECTION("each draw reads its own trace mask") {
        for (u32 i = 1; i <= 10; ++i) {
            tst::set_trace_initiator(i, 1u << (i + 15));
        }
        Buf b;
        agc::sceAgcDcbDrawIndex(&b.cb, 1, 0, 0);       // [1] -> bit 16
        agc::sceAgcDcbDrawIndexAuto(&b.cb, 1, 0);      // [2] -> bit 17
        agc::sceAgcDcbDrawIndexOffset(&b.cb, 0, 1, 0); // [3] -> bit 18
        agc::sceAgcDcbDrawIndexIndirect(&b.cb, 0, 0);  // [4] -> bit 19
        agc::sceAgcDcbDrawIndirect(&b.cb, 0, 0);       // [7] -> bit 22
        CHECK(Hex{b.mem[5]} == Hex{0x00010000u});
        CHECK(Hex{b.mem[8]} == Hex{0x00020002u});
        CHECK(Hex{b.mem[13]} == Hex{0x00040000u});
        CHECK(Hex{b.mem[18]} == Hex{0x00080000u});
        CHECK(Hex{b.mem[23]} == Hex{0x00400002u});
    }
}

TEST_CASE("Dcb indirect draws: user-data locations from the modifier",
          "[agc][builders][dcb][draw]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("DrawIndirect, stage 0: base 0x8C + slot") {
        tst::set_trace_initiator(7, 0x00400000u);
        Buf b;
        // bit0 slot 5, bit2 slot 7
        u32 *p = agc::sceAgcDcbDrawIndirect(&b.cb, 0x20, 0x380A05ull);
        expect_packet(b, p, {0xC0032400u, 0x20u, 0x91u, 0x93u, 0x00400002u});
    }
    SECTION("DrawIndirect, stage 3 -> 0x10C; absent start instance -> 0x280; bit 8") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndirect(&b.cb, 0, 0x60193F01ull);
        expect_packet(b, p, {0xC0032400u, 0u, 0x12Bu, 0x280u, 0x22u});
    }
    SECTION("DrawIndirect, stage 5 -> 0x10C") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndirect(&b.cb, 0, 0xA0000405ull);
        expect_packet(b, p, {0xC0032400u, 0u, 0x10Eu, 0x10Cu, 2u});
    }
    SECTION("DrawIndirect, stage 7 -> 0x8C; bit 32 suppresses bit 5") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndirect(&b.cb, 0, 0x1E0000301ull);
        expect_packet(b, p, {0xC0032400u, 0u, 0x8Du, 0x280u, 2u});
    }
    SECTION("DrawIndirect, nothing present") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndirect(&b.cb, 0, 0);
        expect_packet(b, p, {0xC0032400u, 0u, 0x280u, 0x280u, 2u});
    }
    SECTION("DrawIndexIndirect, all present, stage 3") {
        tst::set_trace_initiator(4, 0x00080000u);
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndexIndirect(&b.cb, 0x30, 0x60418807ull);
        expect_packet(b, p, {0xC0032500u, 0x30u, 0x01120110u, 0x10000114u, 0x00080000u});
    }
    SECTION("DrawIndexIndirect, nothing present") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndexIndirect(&b.cb, 0, 0x100);
        expect_packet(b, p, {0xC0032500u, 0u, 0x280u, 0x280u, 0x20u});
    }
    SECTION("DrawIndexIndirect, only draw index (slot 0, stage 0)") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndexIndirect(&b.cb, 0, 2);
        expect_packet(b, p, {0xC0032500u, 0u, 0x008C0280u, 0x10000280u, 0u});
    }
}

TEST_CASE("Dcb multi draws with driver markers", "[agc][builders][dcb][draw]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("DrawIndirectMulti") {
        tst::set_trace_initiator(8, 0x00800000u);
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndirectMulti(&b.cb, 0x40, 1, 7, 0x0000000500000013ull, 0x20,
                                                 0x0310031Dull);
        expect_packet(b, p,
                      cat({ud3(0xC6000008u, 0),
                           {0xC0082C00u, 0x40u, 0x8Du, 0x8Eu, 0xC800008Fu, 7u, 0x10u, 5u, 0x20u,
                            0x00800022u},
                           ud3(0xC6000000u, 0)}));
    }
    SECTION("DrawIndirectMulti, empty modifier: draw-id location 0x280") {
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndirectMulti(&b.cb, 0, 0, 1, 0, 16, 0);
        expect_packet(b, p,
                      cat({ud3(0xC6000008u, 0),
                           {0xC0082C00u, 0u, 0x280u, 0x280u, 0x280u, 1u, 0u, 0u, 16u, 2u},
                           ud3(0xC6000000u, 0)}));
    }
    SECTION("DrawIndexIndirectMulti, stage 5, all present") {
        tst::set_trace_initiator(5, 0x40u);
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndexIndirectMulti(&b.cb, 0x40, 0, 3, 0x2000, 0x14,
                                                      0xA418821Full);
        expect_packet(b, p,
                      cat({ud3(0xC6000005u, 0),
                           {0xC0083800u, 0x40u, 0x010E010Du, 0x10Fu, 0x98000110u, 3u, 0x2000u, 0u,
                            0x14u, 0x40u},
                           ud3(0xC6000000u, 0)}));
    }
    SECTION("DrawIndexMultiInstanced") {
        tst::set_trace_initiator(6, 0x00200000u);
        Buf b;
        u32 *p = agc::sceAgcDcbDrawIndexMultiInstanced(&b.cb, 0x77, 0x1111222233334444ull,
                                                       0x5555666677778888ull, 0, 0x100);
        expect_packet(b, p,
                      cat({ud3(0xC6000006u, 0),
                           {0xC0073A00u, 0x77u, 0x33334444u, 0x11112222u, 1u, 0x77778888u,
                            0x55556666u, 0u, 0x002000A0u},
                           ud3(0xC6000000u, 0)}));
    }
}

TEST_CASE("Dcb event, LOD stats, base, index and misc packets", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("EventWrite") {
        Buf b;
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 7, 0) == b.at(0));
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 15, 0) == b.at(2));
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 16, 0) == b.at(4));
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 0x38, 0x123456789ABCDEFFull) == b.at(6));
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 0x39, 0x1000) == b.at(10));
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 0x2E, 0x1000) == b.at(14));
        CHECK(agc::sceAgcDcbEventWrite(&b.cb, 0x4E, 0x1000) == b.at(16));
        CHECK(b.used() == 18);
        expect_dwords(b.at(0),
                      {0xC0004600u, 0x407u, 0xC0004600u, 0x40Fu, 0xC0004600u, 0x410u,
                       0xC0024600u, 0x138u, 0x9ABCDEF8u, 0x12345678u,
                       0xC0024600u, 0x139u, 0x1000u, 0u,
                       0xC0004600u, 0x2Eu, 0xC0004600u, 0x0Eu});
    }
    SECTION("GetLodStats") {
        Buf b;
        u32 *p = agc::sceAgcDcbGetLodStats(&b.cb, 3, 0x123456789ABCDEFFull, 0xAB, 0x1FF, 1, 1, 0x3C);
        expect_packet(b, p, {0xC0038E00u, 0xABu, 0x9ABCDEC0u, 0x12345678u, 0x300FFCF0u});
    }
    SECTION("SetBaseIndirectArgs: compute selects the shader-type bit") {
        Buf b;
        CHECK(agc::sceAgcDcbSetBaseIndirectArgs(&b.cb, 1, 0x123456789ABCDEFFull) == b.at(0));
        CHECK(agc::sceAgcDcbSetBaseIndirectArgs(&b.cb, 0, 0x1000) == b.at(4));
        expect_dwords(b.at(0),
                      {0xC0021102u, 1u, 0x9ABCDEF8u, 0x12345678u, 0xC0021100u, 1u, 0x1000u, 0u});
    }
    SECTION("SetIndexSize and the extended variant") {
        Buf b;
        CHECK(agc::sceAgcDcbSetIndexSize(&b.cb, 0xFF, 3) == b.at(0));
        CHECK(agc::sceAgcDcbSetIndexSize(&b.cb, 1, 5) == b.at(3));
        CHECK(agc::agcDcbSetIndexSizeEx(&b.cb, 2, 1, 3) == b.at(6));
        CHECK(agc::agcDcbSetIndexSizeEx(&b.cb, 2, 1, 0) == b.at(9));
        expect_dwords(b.at(0),
                      {0xC0017A00u, 0x20000243u, 0x4C3u, 0xC0017A00u, 0x20000243u, 0x441u,
                       0xC0017A00u, 0x20000243u, 0x4442u, 0xC0017A00u, 0x20000243u, 0x442u});
    }
    SECTION("SetIndexBuffer / SetIndexCount / SetNumInstances / Stall") {
        Buf b;
        CHECK(agc::sceAgcDcbSetIndexBuffer(&b.cb, 0x123456789ABCDEFFull) == b.at(0));
        CHECK(agc::sceAgcDcbSetIndexCount(&b.cb, 0) == b.at(3));
        CHECK(agc::sceAgcDcbSetIndexCount(&b.cb, 0xFFFFFFFFu) == b.at(5));
        CHECK(agc::sceAgcDcbSetNumInstances(&b.cb, 0) == b.at(7));
        CHECK(agc::sceAgcDcbStallCommandBufferParser(&b.cb) == b.at(9));
        CHECK(b.used() == 11);
        expect_dwords(b.at(0),
                      {0xC0012600u, 0x9ABCDEFEu, 0x12345678u, 0xC0001300u, 1u, 0xC0001300u,
                       0xFFFFFFFFu, 0xC0002F00u, 0u, 0xC0004200u, 0u});
    }
    SECTION("Rewind / PrimeUtcl2 / SetIndexIndirectArgs / SetPredication") {
        Buf b;
        CHECK(agc::sceAgcDcbRewind(&b.cb, 1) == b.at(0));
        CHECK(agc::sceAgcDcbRewind(&b.cb, 0) == b.at(2));
        CHECK(agc::sceAgcDcbPrimeUtcl2(&b.cb, 0xFF, 3, 0x123456789ABCDEFFull, 0x12345) == b.at(4));
        CHECK(agc::sceAgcDcbSetIndexIndirectArgs(&b.cb, 0x123456789ABCDEFFull, 0x12345) == b.at(9));
        CHECK(agc::sceAgcDcbSetPredication(&b.cb, 3, 0xF, 1, 0x123456789ABCDEFFull) == b.at(13));
        CHECK(b.used() == 17);
        expect_dwords(b.at(0),
                      {0xC0005900u, 0x80000000u, 0xC0005900u, 0u,
                       0xC0035D00u, 0x4000000Fu, 0x9ABCC000u, 0x12345678u, 0x2345u,
                       0xC0029100u, 0x9ABCDEF0u, 0x12345678u, 0x2345u,
                       0xC0022000u, 0x00071100u, 0x9ABCDEF0u, 0x12345678u});
    }
}

TEST_CASE("DcbWaitRegMem: engine/op bit mapping differs between sizes", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SECTION("size 0, engineAndOp 0xF") {
        Buf b;
        u32 *p = agc::sceAgcDcbWaitRegMem(&b.cb, 0, 3, 0xF, 1, 0x0001ABCD12345677ull,
                                          0xFFFFFFFF00000005ull, 0x00000000FFFF0000ull, 0x1234);
        expect_packet(b, p,
                      cat({ud4(0xC801ABCDu, 0, 0x12345677u),
                           {0xC0053C00u, 0x020003D3u, 0x12345674u, 0x0001ABCDu, 5u, 0xFFFF0000u,
                            0x123u},
                           ud3(0xC8000000u, 0)}));
    }
    SECTION("size 0, engineAndOp 5") {
        Buf b;
        u32 *p = agc::sceAgcDcbWaitRegMem(&b.cb, 0, 3, 5, 0, 0x1000, 1, 2, 0);
        expect_packet(b, p,
                      cat({ud4(0xC8010000u, 0, 0x1000u),
                           {0xC0053C00u, 0x153u, 0x1000u, 0u, 1u, 2u, 0u},
                           ud3(0xC8000000u, 0)}));
    }
    SECTION("size 1, engineAndOp 7") {
        Buf b;
        u32 *p = agc::sceAgcDcbWaitRegMem(&b.cb, 1, 3, 7, 1, 0x0001ABCD12345677ull,
                                          0xFFFFFFFF00000005ull, 0x00000000FFFF0000ull, 0x200000);
        expect_packet(b, p,
                      cat({ud4(0xC802ABCDu, 0, 0x12345677u),
                           {0xC0079300u, 0x020001D3u, 0x12345670u, 0x0001ABCDu, 5u, 0xFFFFFFFFu,
                            0xFFFF0000u, 0u, 0xFFFFu},
                           ud3(0xC8000000u, 0)}));
    }
    SECTION("size 1, engineAndOp 5") {
        Buf b;
        u32 *p = agc::sceAgcDcbWaitRegMem(&b.cb, 1, 3, 5, 0, 0x1008, 0, 0, 0);
        expect_packet(b, p,
                      cat({ud4(0xC8020000u, 0, 0x1008u),
                           {0xC0079300u, 0x193u, 0x1008u, 0u, 0u, 0u, 0u, 0u, 0u},
                           ud3(0xC8000000u, 0)}));
    }
    SECTION("bad size -> NULL") {
        Buf b;
        CHECK(agc::sceAgcDcbWaitRegMem(&b.cb, 2, 0, 0, 0, 0x1000, 0, 0, 0) == nullptr);
        CHECK(agc::sceAgcDcbWaitRegMem(&b.cb, -5, 0, 0, 0, 0x1000, 0, 0, 0) == nullptr);
        CHECK(g_fake.ud.empty());
        expect_untouched(b);
    }
}

TEST_CASE("DcbAtomicGds and the 8-bit-opcode variant", "[agc][builders][dcb]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    Buf b;
    CHECK(agc::sceAgcDcbAtomicGds(&b.cb, 1, 0x27F, 1, 3, 0xFF, 0x5678, 0xABCD, 0xFFFFFFFFu,
                                  0xCAFEBABEu, 0x1111222233334444ull, 0x5555666677778888ull) ==
          b.at(0));
    CHECK(agc::agcDcbAtomicGdsOp8(&b.cb, 1, 0x2FF, 0, 0, 0, 1, 2, 0, 0, 0, 0) == b.at(11));
    CHECK(agc::sceAgcDcbAtomicGds(&b.cb, 0, 0x05, 1, 0, 0, 0, 0, 0, 0, 0, 0) == b.at(22));
    CHECK(b.used() == 33);
    expect_dwords(b.at(0),
                  {0xC0091D00u, 0x4015007Fu, 0x13Fu, 0x5678u, 0xABCDu, 0x00FF00FFu, 0xCAFEBABEu,
                   0x33334444u, 0x11112222u, 0x77778888u, 0x55556666u,
                   0xC0091D00u, 0x401500FFu, 0u, 1u, 2u, 0u, 0u, 0u, 0u, 0u, 0u,
                   0xC0091D00u, 0x00020005u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u, 0u});
}

TEST_CASE("DcbResetQueue: flag combinations", "[agc][builders][dcb][reset]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    REQUIRE(agc::agcSetTrustedRange(0, ~u64{0}) == 0); // untrusted caller -> id bit 22
    tst::set_sync_label(kLabel);
    SlotFixture s;
    SlotFixture s1;
    const std::vector<u32> nop1 = {0xFFFF1000u};

    SECTION("bits 0, 1: CX and SH default loads") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0003, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400003u, 0, 0x0Bu), s.h10(),
                           {0xC0036300u, lo4(s.sh.data()), hi(s.sh.data()), 0x80000000u, 0x45u},
                           ud3(0xCEC00000u, 0)}));
        REQUIRE(g_fake.ud.size() == 2);
        CHECK(g_fake.ud[0].pipe == 0);
    }
    SECTION("bits 2 + 11: whole UCONFIG table; bit 7 flush; untrusted slot") {
        tst::set_slot(0, s.view(0x0B, false, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0884, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE600884u, 0, 0x0Bu), {0xC0004600u, 0x407u},
                           {0xC0036400u, lo4(s.uc.data()), hi(s.uc.data()), 0x80000000u, 20u},
                           ud3(0xCEE00000u, 0)}));
    }
    SECTION("bit 2 only: table without the special tail; SoC 0x840F00 opcode 0x68") {
        tst::set_soc_id(0x840F00u);
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0004, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400004u, 0, 0x0Bu),
                           {0xC0036800u, lo4(s.uc.data()), hi(s.uc.data()), 0x80000000u, 12u},
                           ud3(0xCEC00000u, 0)}));
    }
    SECTION("bit 11 only: the special tail") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0800, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400800u, 0, 0x0Bu),
                           {0xC0036400u, lo4(&s.uc[12]), hi(&s.uc[12]), 0x80000000u, 8u},
                           ud3(0xCEC00000u, 0)}));
    }
    SECTION("bits 3, 4, 8: instances, index defaults, flush index 4 event 0x10") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0118, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400118u, 0, 0x0Bu), {0xC0004600u, 0x410u},
                           {0xC0002F00u, 1u},
                           {0xC0017A00u, 0x20000243u, 0x480u, 0xC0012600u, 0u, 0u, 0xC0001300u,
                            0xFFFFFFFFu},
                           ud3(0xCEC00000u, 0)}));
    }
    SECTION("bits 5, 6, 9: indirect bases, whole-memory acquire, events") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0260, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400260u, 0, 0x0Bu),
                           {0xC0021102u, 1u, 0u, 0u, 0xC0021100u, 1u, 0u, 0u},
                           {0xC0065800u, 0x86007FC0u, 0xFFFFFFFEu, 0xFFu, 1u, 0u, 0x19u, 0xC3E1u},
                           {0xC0004600u, 0x2Eu, 0xC0004600u, 0x2Cu},
                           {0xC0024600u, 0x138u, 0x07FFFC00u, 0u},
                           ud3(0xCEC00000u, 0)}));
    }
    SECTION("bit 10: conditional clear state") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0400, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400400u, 0, 0x0Bu), h9(), ud3(0xCEC00000u, 0)}));
    }
    SECTION("bit 0 with g_useClearStateForCx: CLEAR_STATE 0 instead of the table") {
        tst::set_use_clear_state_for_cx(1);
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x0001, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE400001u, 0, 0x0Bu), {0xC0001200u, 0u},
                           ud3(0xCEC00000u, 0)}));
    }
    SECTION("bit 15: active slot, queueSlot ignored") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        tst::set_slot(1, s1.view(0x0C, false, 24));
        tst::set_active_slot(1, true);
        Buf b;
        u32 *p = agc::sceAgcDcbResetQueue(&b.cb, 0x8001, 0);
        expect_packet(b, p,
                      cat({nop1, ud4(0xCE608001u, 0, 0x0Cu), s1.h10(), ud3(0xCEE00000u, 0)}));
    }
    SECTION("leading NOP does not fit -> NULL, nothing written") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b(0);
        CHECK(agc::sceAgcDcbResetQueue(&b.cb, 0, 0) == nullptr);
        CHECK(g_fake.ud.empty());
    }
    SECTION("end marker does not fit -> NULL, earlier packets stay") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b(6);
        CHECK(agc::sceAgcDcbResetQueue(&b.cb, 0, 0) == nullptr);
        CHECK(b.used() == 5);
        CHECK(b.oos.last_required == 3u);
        expect_dwords(b.at(0), cat({nop1, ud4(0xCE400000u, 0, 0x0Bu), {kSentinel}}));
    }
}

TEST_CASE("agcDcbResetActiveQueue: flags 0x0BFF on the active slot", "[agc][builders][dcb][reset]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    REQUIRE(agc::agcSetTrustedRange(0, ~u64{0}) == 0);
    SlotFixture s;
    SECTION("suspend not ready -> NULL") {
        tst::set_slot(0, s.view(0x0B, true, 24));
        Buf b;
        CHECK(agc::agcDcbResetActiveQueue(&b.cb) == nullptr);
        expect_untouched(b);
    }
    SECTION("full sequence") {
        tst::set_slot(1, s.view(0x0B, true, 24));
        tst::set_active_slot(1, true);
        Buf b;
        u32 *p = agc::agcDcbResetActiveQueue(&b.cb);
        expect_packet(b, p,
                      cat({{0xFFFF1000u}, ud4(0xCE400BFFu, 0, 0x0Bu),
                           {0xC0004600u, 0x407u, 0xC0004600u, 0x410u},
                           s.h10(),
                           {0xC0036300u, lo4(s.sh.data()), hi(s.sh.data()), 0x80000000u, 0x45u},
                           {0xC0036400u, lo4(s.uc.data()), hi(s.uc.data()), 0x80000000u, 20u},
                           {0xC0002F00u, 1u},
                           {0xC0017A00u, 0x20000243u, 0x480u, 0xC0012600u, 0u, 0u, 0xC0001300u,
                            0xFFFFFFFFu},
                           {0xC0021102u, 1u, 0u, 0u, 0xC0021100u, 1u, 0u, 0u},
                           {0xC0065800u, 0x86007FC0u, 0xFFFFFFFEu, 0xFFu, 1u, 0u, 0x19u, 0xC3E1u},
                           {0xC0004600u, 0x2Eu, 0xC0004600u, 0x2Cu},
                           {0xC0024600u, 0x138u, 0x07FFFC00u, 0u},
                           ud3(0xCEC00000u, 0)}));
        CHECK(b.used() == 61);
    }
}

TEST_CASE("DcbContextStateOp: all ops", "[agc][builders][dcb][ctx]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    SlotFixture s;
    tst::set_slot(0, s.view(0x0B, true, 24));
    tst::set_active_slot(0, true);
    SECTION("op 0: load CX defaults of the active slot") {
        Buf b;
        u32 *p = agc::sceAgcDcbContextStateOp(&b.cb, 0);
        expect_packet(b, p, s.h10());
    }
    SECTION("op 1") {
        Buf b;
        u32 *p = agc::sceAgcDcbContextStateOp(&b.cb, 1);
        expect_packet(b, p, {0xC0012800u, 0u, 0x80018001u, 0xC0001200u, 1u});
    }
    SECTION("op 2") {
        Buf b;
        u32 *p = agc::sceAgcDcbContextStateOp(&b.cb, 2);
        expect_packet(b, p, {0xC0012800u, 0u, 0x80018003u, 0xC0001200u, 2u});
    }
    SECTION("op 3 without g_useClearStateForCx: CLEAR_STATE 1 + table load") {
        Buf b;
        u32 *p = agc::sceAgcDcbContextStateOp(&b.cb, 3);
        expect_packet(b, p, cat({{0xC0012800u, 0u, 0x80018001u, 0xC0001200u, 1u}, s.h10()}));
    }
    SECTION("op 3 with g_useClearStateForCx: CLEAR_STATE 3 only") {
        tst::set_use_clear_state_for_cx(1);
        Buf b;
        u32 *p = agc::sceAgcDcbContextStateOp(&b.cb, 3);
        expect_packet(b, p, {0xC0012800u, 0u, 0x80018001u, 0xC0001200u, 3u});
    }
    SECTION("other ops: CLEAR_STATE op & 0xF, returns NULL") {
        Buf b;
        CHECK(agc::sceAgcDcbContextStateOp(&b.cb, 4) == nullptr);
        CHECK(agc::sceAgcDcbContextStateOp(&b.cb, 0x13) == nullptr);
        CHECK(b.used() == 4);
        expect_dwords(b.at(0), {0xC0001200u, 4u, 0xC0001200u, 3u, kSentinel});
    }
    SECTION("reservation failure -> NULL") {
        Buf b(4);
        CHECK(agc::sceAgcDcbContextStateOp(&b.cb, 1) == nullptr);
    }
    SECTION("op 3: table load failing -> NULL") {
        Buf b(9);
        CHECK(agc::sceAgcDcbContextStateOp(&b.cb, 3) == nullptr);
    }
}

TEST_CASE("agcDcbContextStateOpNotify: H8 sequences around the context roll",
          "[agc][builders][dcb][ctx]") {
    tst::reset();
    tst::clear_imports();
    install_fakes();
    tst::set_sync_label(kLabel);
    SlotFixture s;
    tst::set_slot(0, s.view(0x0B, true, 24));
    tst::set_active_slot(0, true);
    SECTION("op 1") {
        Buf b;
        u32 *p = agc::agcDcbContextStateOpNotify(&b.cb, 1);
        expect_packet(b, p,
                      cat({h8(1, true), {0xC0012800u, 0u, 0x80018001u}, {0xC0001200u, 1u}}));
    }
    SECTION("only the low 32 bits of op are used") {
        Buf b;
        u32 *p = agc::agcDcbContextStateOpNotify(&b.cb, 0x100000001ull);
        expect_packet(b, p,
                      cat({h8(1, true), {0xC0012800u, 0u, 0x80018001u}, {0xC0001200u, 1u}}));
    }
    SECTION("op 2: CONTEXT_CONTROL first, label + 4, returns CONTEXT_CONTROL") {
        Buf b;
        u32 *p = agc::agcDcbContextStateOpNotify(&b.cb, 2);
        expect_packet(b, p,
                      cat({{0xC0012800u, 0u, 0x80018003u}, h8(2, false), {0xC0001200u, 2u}}));
    }
    SECTION("op 3 without g_useClearStateForCx") {
        Buf b;
        u32 *p = agc::agcDcbContextStateOpNotify(&b.cb, 3);
        expect_packet(b, p,
                      cat({h8(3, true), {0xC0012800u, 0u, 0x80018001u}, {0xC0001200u, 1u},
                           s.h10()}));
    }
    SECTION("op 3 with g_useClearStateForCx") {
        tst::set_use_clear_state_for_cx(1);
        Buf b;
        u32 *p = agc::agcDcbContextStateOpNotify(&b.cb, 3);
        expect_packet(b, p,
                      cat({h8(3, true), {0xC0012800u, 0u, 0x80018001u}, {0xC0001200u, 3u}}));
    }
    SECTION("op 0: only the table load") {
        Buf b;
        u32 *p = agc::agcDcbContextStateOpNotify(&b.cb, 0);
        expect_packet(b, p, s.h10());
    }
    SECTION("other op: CLEAR_STATE only, NULL") {
        Buf b;
        CHECK(agc::agcDcbContextStateOpNotify(&b.cb, 5) == nullptr);
        CHECK(b.used() == 2);
        expect_dwords(b.at(0), {0xC0001200u, 5u, kSentinel});
    }
    SECTION("H8 needs 22 free dwords: 21 -> NULL, nothing written") {
        Buf b(21);
        CHECK(agc::agcDcbContextStateOpNotify(&b.cb, 1) == nullptr);
        CHECK(b.oos.calls >= 1);
        CHECK(b.oos.last_required == 22u);
        expect_untouched(b);
    }
    SECTION("op 2 with room for CONTEXT_CONTROL only: NULL after it") {
        Buf b(24);
        CHECK(agc::agcDcbContextStateOpNotify(&b.cb, 2) == nullptr);
        CHECK(b.used() == 3);
        expect_dwords(b.at(0), {0xC0012800u, 0u, 0x80018003u, kSentinel});
    }
}
