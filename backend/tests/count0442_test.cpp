// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0442 (count while guarding): the two count modes' pure parts (HOST_INDIRECT's is gone with the word, tag nl442). Built in the Catch2 suite, and also
// standalone (-DBC5_STANDALONE, a minimal harness below) so a laptop without the Linux toolchain can run it.
#include "bc5/indirect_check.hpp"
#include "bc5/shadow_labels.hpp"

#include <cstdint>
#include <vector>

#ifdef BC5_STANDALONE
#include <cstdio>
namespace {
struct Case {
    const char *name;
    void (*fn)();
};
std::vector<Case> &cases() {
    static std::vector<Case> c;
    return c;
}
int g_fail = 0, g_pass = 0;
struct Reg {
    Reg(const char *n, void (*f)()) { cases().push_back({n, f}); }
};
} // namespace
#define BC5_CAT2(a, b) a##b
#define BC5_CAT(a, b) BC5_CAT2(a, b)
#define TEST_CASE(name, tags)                                                                                  \
    static void BC5_CAT(t_, __LINE__)();                                                                       \
    static Reg BC5_CAT(r_, __LINE__)(name, &BC5_CAT(t_, __LINE__));                                           \
    static void BC5_CAT(t_, __LINE__)()
#define CHECK(x)                                                                                               \
    do {                                                                                                       \
        if (x) {                                                                                               \
            g_pass++;                                                                                          \
        } else {                                                                                               \
            g_fail++;                                                                                          \
            std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #x);                                          \
        }                                                                                                      \
    } while (0)
#define REQUIRE(x) CHECK(x)
#else
#include <catch2/catch_test_macros.hpp>
#endif

using namespace bc5;

namespace {
constexpr std::uint32_t kMax[3] = {1u << 20, 1u << 10, 1u << 10};
constexpr std::uint32_t kDrawMax[2] = {1u << 22, 1024};
constexpr std::uint32_t kDispatchIndirect = 0xC0011600u; // PKT3(DISPATCH_INDIRECT, 1, 0)
constexpr std::uint32_t kCondWrite = 0xC0074500u;        // PKT3(COND_WRITE, 7, 0)
constexpr std::uint32_t kCondExec = 0xC0032200u;         // PKT3(COND_EXEC, 3, 0)
// SET_BASE index 1 = 0x12_3456_7000, then DISPATCH_INDIRECT offset 0x40, initiator 0x41 (indirect_check_test.cpp's IB)
const std::vector<std::uint32_t> kIb = {0xC0021100u, 1u, 0x34567000u, 0x12u, kDispatchIndirect, 0x40u, 0x41u};
} // namespace

TEST_CASE("exp 0442: BC5_DIRECT_GPU_CHECK_PRODUCT with and without count", "[count0442]") {
    indirect_check::ProductLimit p;
    CHECK(!indirect_check::parse_product(nullptr, p));
    CHECK(!indirect_check::parse_product("0", p));
    CHECK(!indirect_check::parse_product("", p));
    REQUIRE(indirect_check::parse_product("1", p));
    CHECK((p.x_limit == (1u << 16) && p.yz_min == 1 && !p.count));
    REQUIRE(indirect_check::parse_product("100000:2", p));
    CHECK((p.x_limit == 100000u && p.yz_min == 2 && !p.count));
    REQUIRE(indirect_check::parse_product("count", p));
    CHECK((p.x_limit == (1u << 16) && p.yz_min == 1 && p.count));
    REQUIRE(indirect_check::parse_product("count:4096:3", p));
    CHECK((p.x_limit == 4096u && p.yz_min == 3 && p.count));
}

TEST_CASE("exp 0442: the staircase without count is unchanged, with count it marks the would word", "[count0442]") {
    // without count: exp 0341's size and its COND_EXEC over 9 dwords
    indirect_check::ProductLimit plain{1u << 16, 1};
    std::vector<std::size_t> refs;
    indirect_check::Stats st;
    auto out = indirect_check::apply(kIb, 0, kMax, kDrawMax, refs, st, false, &plain);
    REQUIRE(out.size() == kIb.size() + indirect_check::kCheckDwords + indirect_check::kProductDwords);
    REQUIRE(refs.size() == 12);
    // with count: 9 more dwords, one more flag reference, the COND_EXEC over 18, the second COND_WRITE writes 1 at +28
    indirect_check::ProductLimit counted{1u << 16, 1, true};
    std::vector<std::size_t> refs2;
    indirect_check::Stats st2;
    auto out2 = indirect_check::apply(kIb, 0, kMax, kDrawMax, refs2, st2, false, &counted);
    REQUIRE(out2.size() == out.size() + indirect_check::kProductCountDwords);
    REQUIRE(refs2.size() == refs.size() + 1);
    CHECK(st2.product_checked == 1);
    const std::uint64_t flag_va = 0x1000'0000'2000ull;
    indirect_check::patch(out2, refs2, flag_va);
    indirect_check::patch(out, refs, flag_va);
    // find the staircase's COND_EXEC (on flag2 = flag + 8)
    std::size_t ce = 0, ce_plain = 0;
    for (std::size_t i = 0; i + 4 < out2.size(); ++i)
        if (out2[i] == kCondExec && out2[i + 1] == 0x2008u) ce = i;
    for (std::size_t i = 0; i + 4 < out.size(); ++i)
        if (out[i] == kCondExec && out[i + 1] == 0x2008u) ce_plain = i;
    REQUIRE(ce != 0);
    REQUIRE(ce_plain != 0);
    CHECK(out[ce_plain + 4] == 9u);
    CHECK(out2[ce + 4] == 18u);
    // the two COND_WRITEs it covers: flag = 0, then would = 1
    const std::size_t a = ce + 5, b = ce + 14;
    CHECK(out2[a] == kCondWrite);
    CHECK(out2[a + 4] == (1u << 16));
    CHECK(out2[a + 6] == 0x2000u);
    CHECK(out2[a + 8] == 0u);
    CHECK(out2[b] == kCondWrite);
    CHECK(out2[b + 4] == (1u << 16));
    CHECK(out2[b + 6] == static_cast<std::uint32_t>(flag_va + indirect_check::kWouldByte));
    CHECK(out2[b + 7] == 0x1000u);
    CHECK(out2[b + 8] == 1u);
    // everything outside the added 9 dwords is the plain staircase (same offsets before, shifted after)
    bool same = true;
    for (std::size_t i = 0; i < b; ++i)
        if (i != ce + 4 && out2[i] != out[i]) same = false;
    for (std::size_t i = b; i < out.size(); ++i)
        if (out2[i + indirect_check::kProductCountDwords] != out[i]) same = false;
    CHECK(same);
    CHECK(indirect_check::kWouldByte == 28u); // the flag area's 8th dword: zeroed per job (direct.cpp), unused before
}

TEST_CASE("exp 0442: a shadowed label compared after the job", "[count0442]") {
    using shadow_labels::Match;
    CHECK(shadow_labels::classify(1, 1) == Match::Equal);
    CHECK(shadow_labels::classify(0x1234'5678'0000'0001ull, 1) == Match::Equal); // a 32-bit label: low word only
    CHECK(shadow_labels::classify(0x1234'5678'0000'0000ull, 1) == Match::TitleZero);
    CHECK(shadow_labels::classify(0x44069b70u, 1) == Match::Other); // F360's float 538.4 over a label of 1
    CHECK(shadow_labels::classify(0x2'0000'0001ull, 0x1'0000'0001ull) == Match::Other); // a 64-bit label: all of it
    CHECK(shadow_labels::classify(0x1'0000'0001ull, 0x1'0000'0001ull) == Match::Equal);
}

TEST_CASE("exp 0442: shadow_labels::apply gives the labels in slot order", "[count0442]") {
    const std::vector<std::uint32_t> wr1 = {0xC0033700u, 5u << 8, 0xe0b975e0u, 0x11u, 0u};
    const std::vector<std::uint32_t> wt1 = {0xC0053C00u, 0x13u, 0xe0b975e0u, 0x11u, 1u, 0xffffffffu, 4u};
    const std::vector<std::uint32_t> wr2 = {0xC0033700u, 5u << 8, 0x00001000u, 0x22u, 0u};
    const std::vector<std::uint32_t> wt2 = {0xC0053C00u, 0x13u, 0x00001000u, 0x22u, 1u, 0xffffffffu, 4u};
    std::vector<std::uint32_t> ib;
    for (const auto *p : {&wr1, &wr2, &wt2, &wt1}) ib.insert(ib.end(), p->begin(), p->end()); // label 2 waited first
    shadow_labels::Stats st;
    std::vector<std::uint64_t> labels;
    REQUIRE(shadow_labels::apply(ib, 64, st, &labels));
    REQUIRE(labels.size() == 2);
    CHECK(labels[0] == 0x22'0000'1000ull); // slot 0: the first label waited on
    CHECK(labels[1] == 0x11'e0b9'75e0ull);
    std::vector<std::uint32_t> ib2;
    for (const auto *p : {&wr1, &wt1}) ib2.insert(ib2.end(), p->begin(), p->end());
    shadow_labels::Stats st2;
    REQUIRE(shadow_labels::apply(ib2, 64, st2)); // no labels_out: as before
    CHECK(st2.labels == 1);
}

#ifdef BC5_STANDALONE
int main() {
    for (const Case &c : cases()) {
        const int before = g_fail;
        c.fn();
        std::printf("%s %s\n", g_fail == before ? "ok  " : "FAIL", c.name);
    }
    std::printf("== count0442: %d checks passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
#endif
