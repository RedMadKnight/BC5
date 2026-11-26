// BC5 exp 0439 (tag cs439): cs0439.hpp's walk helpers and the one-frame dump (stand-in, no GPU).
#include "bc5/cs0439.hpp"
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
static int fails = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %d %s\n", __LINE__, #c); fails++; } } while (0)
int main(int argc, char **argv) {
    using namespace bc5::cs439;
    // push; COND_EXEC over the next 2 dwords holding a pop; pop outside; LOAD_CONTEXT_REG_INDEX pairs from a table
    static std::uint32_t table[4] = {0x10, 0x11111111u, 0x8e, 0xf};
    const std::uint64_t ta = reinterpret_cast<std::uint64_t>(table);
    std::vector<std::uint32_t> ib = {0xC0001200u, 1, 0xC0032200u, 0, 0, 0, 2, 0xC0001200u, 2, 0xC0001200u, 2,
                                     0xC0039F00u, static_cast<std::uint32_t>(ta), static_cast<std::uint32_t>(ta >> 32), 0x80000000u, 2};
    CHECK(pops_in(ib.data(), ib.size()) == 1);
    count_ib(ib.data(), ib.size(), 0);
    CHECK(g_cs[0][0][1] == 1 && g_cs[0][0][2] == 1 && g_cs[0][1][2] == 1);
    std::vector<std::uint32_t> out = ib;
    push_nops(ib.data(), out.data(), ib.size(), 0xffff1000u);
    CHECK(out[0] == 0xffff1000u && out[1] == 0xffff1000u && out[7] == 0xC0001200u);
    if (argc > 1) { // dump armed through the environment by the caller: BC5_0439_REGTAB_DUMP=<dir> BC5_0439_REGTAB_AT=0 BC5_0439_REGTAB_MIN_DW=1
        std::vector<DumpPiece> dp = {{ib.data(), ib.size()}};
        maybe_dump(dp, [](std::uint64_t, std::uint64_t) { return true; });
        maybe_dump(dp, [](std::uint64_t, std::uint64_t) { return true; }); // one arm: the second call writes nothing
    }
    std::printf(fails ? "test_cs0439b: %d failures\n" : "test_cs0439b: ok\n", fails);
    return fails != 0;
}
