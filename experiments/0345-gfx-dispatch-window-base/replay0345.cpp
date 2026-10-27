// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0345: indirect_check::apply() run offline over a timeout dump (the buffer the host handed to the
// backend), to see what the pass does with it — how many dispatches it checks, leaves unbased, rebases to a window or
// NOP-s — with the switch off, with the window unknown (learn, nothing seen) and with the window 0x1100000000.
// Links the experiment's private archive; touches no GPU. Prints counts and offsets only.
//   replay0345 <dump.bin>
#include "bc5/indirect_check.hpp"

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <functional>
#include <iterator>
#include <vector>

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: replay0345 <dump.bin>\n");
        return 2;
    }
    std::ifstream f(argv[1], std::ios::binary);
    std::vector<char> bytes((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    std::vector<std::uint32_t> ib(bytes.size() / 4);
    for (std::size_t i = 0; i < ib.size(); ++i)
        ib[i] = static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * i])) |
                (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * i + 1])) << 8) |
                (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * i + 2])) << 16) |
                (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * i + 3])) << 24);
    std::printf("dump %s: %zu dwords\n", argv[1], ib.size());
    const std::uint32_t max[3] = {1u << 20, 1u << 10, 1u << 10};
    const std::uint32_t draw_max[2] = {1u << 22, 1024};
    const bc5::indirect_check::ProductLimit product;
    const std::function<bool(std::uint64_t, std::uint64_t)> all_mapped = [](std::uint64_t, std::uint64_t) { return true; };
    struct Case {
        const char *name;
        const bc5::indirect_check::GfxBase *gb;
    };
    const bc5::indirect_check::GfxBase none{0, nullptr};
    const bc5::indirect_check::GfxBase window{0x11'0000'0000ull, &all_mapped};
    const Case cases[] = {{"switch off", nullptr}, {"learn, no window yet", &none}, {"window 0x1100000000, all mapped", &window}};
    for (const Case &c : cases) {
        std::vector<std::size_t> refs;
        bc5::indirect_check::Stats st;
        auto out = bc5::indirect_check::apply(ib, 0, max, draw_max, refs, st, false, &product, c.gb);
        std::printf("%s: out %zu dwords (+%u); checked %u (staircase %u), unbased %u, NOP-ed by COND_EXEC %u; rebased %u, NOP-ed unmapped %u, NOP-ed no window %u; records %zu\n",
                    c.name, out.size(), st.inserted_dwords, st.checked, st.product_checked, st.unbased, st.conditional,
                    st.rebased, st.rebased_unmapped, st.rebased_no_window, st.rebases.size());
        for (std::size_t k = 0; k < st.rebases.size() && k < 3; ++k)
            std::printf("  record %zu: at %zu program 0x%llx base 0x%llx address 0x%llx %s\n", k, st.rebases[k].at,
                        static_cast<unsigned long long>(st.rebases[k].program), static_cast<unsigned long long>(st.rebases[k].base),
                        static_cast<unsigned long long>(st.rebases[k].address), st.rebases[k].mapped ? "mapped" : "not mapped / no window");
    }
    std::printf("learn_window: 0x%llx\n", static_cast<unsigned long long>(bc5::indirect_check::learn_window(ib)));
    return 0;
}
