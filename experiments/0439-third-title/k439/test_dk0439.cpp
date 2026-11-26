// BC5 exp 0439 (tag dk439 arm): laptop test of dk0439.hpp. clang++ -std=c++20 -Wall -Wextra -Werror test_dk0439.cpp
#include "dk0439.hpp"

#include <cstdio>
#include <vector>

using namespace bc5::dk439;
static int fails = 0;
#define CHECK(c)                                                                                                       \
    do {                                                                                                               \
        if (!(c)) {                                                                                                    \
            std::printf("FAIL line %d: %s\n", __LINE__, #c);                                                           \
            fails++;                                                                                                   \
        }                                                                                                              \
    } while (0)

static std::uint32_t set_ctx(std::uint32_t n) { return 0xC0000000u | (n << 16) | (0x69u << 8); } // n = values + 1 - 1

int main() {
    // the G-buffer pass's registers as captured (README, the 8-px grid): MRT0 COLOR_16 UINT, MRT1 COLOR_32 UINT, DCC on
    std::vector<std::uint32_t> b;
    b.insert(b.end(), {set_ctx(5), 0x318, 0x5053890000ull >> 8 & 0xffffffffu, 0, 0, 0, 0x10050408u}); // BASE..INFO of MRT0
    b.insert(b.end(), {set_ctx(1), 0x325, 0x508de020u});                                               // MRT0 DCC_BASE
    b.insert(b.end(), {set_ctx(1), 0x31c + 0xf, 0x10050410u});                                         // MRT1 INFO alone
    b.insert(b.end(), {set_ctx(1), 0x325 + 0xf, 0x508de0e0u});                                         // MRT1 DCC_BASE
    b.insert(b.end(), {set_ctx(2), 0x3a8, 0, 0});                                                      // DCC_BASE_EXT 0, 1
    b.insert(b.end(), {set_ctx(2), 0x3b0, (3071u << 14) | 1727u, (3071u << 14) | 1727u});              // ATTRIB2 0, 1
    b.insert(b.end(), {0xC0012D00u, 3, 2});                                                            // a draw: untouched
    b.insert(b.end(), {set_ctx(1), 0x31c + 2 * 0xf, 0x00000428u});                                     // MRT2 INFO, no DCC
    Target t[8];
    const std::uint32_t c = strip(b, t);
    CHECK(c == 2);
    CHECK(b[6] == 0x00050408u && b[12] == 0x00050410u && b[b.size() - 1] == 0x00000428u);
    CHECK(t[0].stripped && t[1].stripped && !t[2].stripped);
    CHECK(dcc_base(t[0]) == 0x508de02000ull && dcc_base(t[1]) == 0x508de0e000ull);
    CHECK(key_bytes(t[0]) == 3072ull * 1728 * 2 / 256 && key_bytes(t[1]) == 3072ull * 1728 * 4 / 256);
    CHECK(b[b.size() - 6] == 0xC0012D00u && b[b.size() - 5] == 3); // the draw kept
    // a second pass over the same buffer changes nothing more
    Target u[8];
    CHECK(strip(b, u) == 0 && !u[0].stripped);
    // unknown size: no keys
    Target v;
    v.info = 0x10050410u;
    CHECK(key_bytes(v) == 0);
    std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
    return fails == 0 ? 0 : 1;
}
