// piece-check — ADR 0008 step 1 (experiment 0072): what a graphics piece would lose. Reads raw
// command buffers in submission order (the host's BC5_DIRECT_IB_DUMP files: little-endian
// dwords), follows which registers each buffer sets (SET_*_REG and the register ranges of the
// LOAD_*_REG packets; tables in memory are not read, so an indexed load in pairs format counts as
// "unknown"), and for every memory WAIT_REG_MEM[64] of the graphics buffers ("dcb" in the file
// name) reports the registers that were set before that point by EARLIER buffers and not again
// by this one: the state a piece that replays only its own buffer's packets (run 123) would miss
// once another process has run on the ring in between. Nothing here touches a GPU.
//
//   piece-check <buffer.bin>...    (in submission order)
//
// GPL-2.0.

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace {

enum Space : int { Config, Context, Sh, Uconfig, Spaces };
const char *kSpaceName[Spaces] = {"config", "context", "sh", "uconfig"};

struct Regs {
    std::set<std::uint32_t> set[Spaces]; // register offsets from the space's base
    std::uint32_t unknown_loads = 0;      // indexed loads in pairs format (registers in memory)
    std::set<std::uint8_t> packet_state;  // SET_BASE, INDEX_BASE, ... seen
};

int space_of(std::uint8_t op) {
    switch (op) {
    case 0x68: return Config;
    case 0x69: case 0x61: case 0x9f: return Context;
    case 0x76: case 0x9b: case 0x5f: case 0x63: return Sh;
    case 0x79: case 0x7a: case 0x5e: case 0x64: return Uconfig;
    default: return -1;
    }
}

// Registers a packet sets (into r); waits (memory WAIT_REG_MEM[64]) are reported by position.
void walk(const std::vector<std::uint32_t> &ib, std::size_t from, std::size_t to, Regs &r,
          std::vector<std::size_t> *waits) {
    for (std::size_t i = from; i < to;) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t c = (h >> 16) & 0x3fff;
            len = c == 0x3fff ? 1 : c + 2;
        }
        if (i + len > ib.size()) break;
        if (type == 3 && len >= 2) {
            const auto op = static_cast<std::uint8_t>((h >> 8) & 0xff);
            const std::uint32_t *p = &ib[i];
            const int sp = space_of(op);
            if (sp >= 0 && (op == 0x68 || op == 0x69 || op == 0x76 || op == 0x79 || op == 0x9b || op == 0x7a)) {
                const std::uint32_t off = p[1] & 0xffff;
                for (std::size_t k = 2; k < len; ++k) r.set[sp].insert(off + static_cast<std::uint32_t>(k - 2));
            } else if (sp >= 0 && (op == 0x61 || op == 0x5f || op == 0x5e) && len >= 5) {
                for (std::size_t k = 3; k + 1 < len; k += 2) { // (reg offset, count) pairs
                    const std::uint32_t off = p[k] & 0xffff, n = std::min<std::uint32_t>(p[k + 1], 0x1000);
                    for (std::uint32_t q = 0; q < n; ++q) r.set[sp].insert(off + q);
                }
            } else if (sp >= 0 && (op == 0x9f || op == 0x63 || op == 0x64) && len >= 5) {
                if ((p[3] >> 31) != 0) {
                    r.unknown_loads++;
                } else {
                    const std::uint32_t off = p[3] & 0xffff, n = std::min<std::uint32_t>(p[4] & 0x3fff, 0x1000);
                    for (std::uint32_t q = 0; q < n; ++q) r.set[sp].insert(off + q);
                }
            } else if (op == 0x11 || op == 0x26 || op == 0x13 || op == 0x2a || op == 0x2f || op == 0x28) {
                r.packet_state.insert(op);
            } else if ((op == 0x3c || op == 0x93) && len >= 4 && ((p[1] >> 4) & 1) != 0 && waits != nullptr) {
                waits->push_back(i);
            }
        }
        i += len;
    }
}

} // namespace

int main(int argc, char **argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: piece-check <buffer.bin>... (in submission order)\n");
        return 2;
    }
    Regs before; // registers set by the buffers so far (all kinds)
    for (int a = 1; a < argc; ++a) {
        const std::string f = argv[a];
        std::ifstream in(f, std::ios::binary);
        std::vector<char> bytes((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        std::vector<std::uint32_t> ib(bytes.size() / 4);
        for (std::size_t k = 0; k < ib.size(); ++k)
            ib[k] = static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * k])) |
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * k + 1])) << 8) |
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * k + 2])) << 16) |
                    (static_cast<std::uint32_t>(static_cast<unsigned char>(bytes[4 * k + 3])) << 24);
        std::string name = f;
        if (const auto s = name.find_last_of('/'); s != std::string::npos) name = name.substr(s + 1);
        const bool gfx = name.find("-dcb-") != std::string::npos;
        if (gfx && ib.size() >= 1000) {
            std::vector<std::size_t> waits;
            Regs whole;
            walk(ib, 0, ib.size(), whole, &waits);
            std::printf("%s: %zu dwords, %zu memory waits\n", name.c_str(), ib.size(), waits.size());
            std::size_t shown = 0;
            for (const std::size_t w : waits) {
                if (shown++ >= 6 && w != waits.back()) continue;
                Regs head;
                walk(ib, 0, w, head, nullptr);
                std::printf("  wait at %6zu:", w);
                for (int sp = 0; sp < Spaces; ++sp) {
                    std::size_t missed = 0;
                    for (const auto reg : before.set[sp])
                        if (head.set[sp].count(reg) == 0) missed++;
                    std::printf(" %s %zu set here / %zu only earlier;", kSpaceName[sp], head.set[sp].size(), missed);
                }
                std::size_t pstate_missed = 0;
                for (const auto op : before.packet_state)
                    if (head.packet_state.count(op) == 0) pstate_missed++;
                std::printf(" packet state only earlier %zu; unknown indexed loads here %u, earlier %u\n", pstate_missed,
                            head.unknown_loads, before.unknown_loads);
            }
        }
        walk(ib, 0, ib.size(), before, nullptr);
    }
    std::printf("over all buffers:");
    for (int sp = 0; sp < Spaces; ++sp) std::printf(" %s %zu registers;", kSpaceName[sp], before.set[sp].size());
    std::printf(" unknown indexed loads %u\n", before.unknown_loads);
    return 0;
}
