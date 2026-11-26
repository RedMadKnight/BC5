// BC5 exp 0439 (tag cs439 ccg): the guarded CONTEXT_CONTROL rule (stand-in, no GPU).
#include "bc5/cs0439.hpp"
#include <cstdio>
#include <vector>
static int fails = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %d %s\n", __LINE__, #c); fails++; } } while (0)
int main() {
    using namespace bc5::cs439;
    // CONTEXT_CONTROL, LOAD_CONTEXT_REG at 0xfe0008000 (offset 1, 960 regs), LOAD_SH_REG at 0xfe0010000 (offset 0, 641)
    const std::vector<std::uint32_t> ib = {0xC0012800u, 0x91018003u, 0x80018003u, 0xC0036100u, 0xe0008000u, 0xfu, 1, 960,
                                           0xC0035F00u, 0xe0010000u, 0xfu, 0, 641};
    auto all = [](std::uint64_t, std::uint64_t) { return true; };
    auto none_sh = [](std::uint64_t a, std::uint64_t) { return a != 0xfe0010000ull; };
    CHECK(cc_loads_ok(ib.data(), ib.size(), all));
    CHECK(!cc_loads_ok(ib.data(), ib.size(), none_sh));
    CHECK(!cc_loads_ok(ib.data(), 3, all)); // CONTEXT_CONTROL with no LOAD: forced
    CHECK(g_ccg_pass == 1 && g_ccg_unmapped == 1 && g_ccg_noload == 1);
    // the extent asked of `mapped`: (1 + 960) * 4 bytes for the context table
    std::uint64_t seen = 0;
    cc_loads_ok(ib.data(), 8, [&](std::uint64_t, std::uint64_t n) { seen = n; return true; });
    CHECK(seen == (1 + 960) * 4);
    std::printf(fails ? "test_cs0439c: %d failures\n" : "test_cs0439c: ok\n", fails);
    return fails != 0;
}
