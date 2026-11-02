// BC5 experiment 0401: runs the unit's real mesa_preamble_prefix() outside the emulator, no GPU. The included file is the
// function as mkunit0401.py wrote it. Two calls show that the journal lines come once and the packets every time.
#include "bc5/env_flag.hpp"

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <vector>

#define journal(...) std::printf(__VA_ARGS__)
#include "mesa_preamble_prefix.inc"

int main() {
    std::vector<uint32_t> p {0xaau};
    mesa_preamble_prefix(p);
    mesa_preamble_prefix(p);
    for (const uint32_t v : p) std::printf("%08x ", v);
    std::printf("\nend\n");
    return 0;
}
