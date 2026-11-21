// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439: det cases of the acb split's state prefix (the top session's question 2 after the 17:04 hang), on the
// generated unit's own state_prefix() (cut out by mksp0439.py into sp439_extract.inc). An acb part that follows a
// CPU-held wait goes as a job of its own; state_prefix() replays the register packets of the buffer up to the split.
//   python3 mksp0439.py <bc5LleAgc.cpp> sp439_extract.inc && clang++ -std=c++20 test_sp0439.cpp -o t && ./t
// Cases:
//   1. state set in the head (SET_SH_REG of the program and of user data) before the wait is replayed in front of the
//      rest, in order, and nothing else (no wait, no dispatch);
//   2. a register write inside an IB the head calls before the wait is NOT replayed (state_prefix does not look into
//      IBs): a rest that dispatches with that state runs with whatever the ring holds. Expected today: not replayed;
//      the case documents the gap, it does not fail on it.
//   3. a register packet split across `upto` is not taken (a packet is copied whole or not at all).
#include <cstdint>
#include <cstdio>
#include <deque>
#include <vector>

#include "sp439_extract.inc"

static int g_fail = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); g_fail++; } } while (0)

static void sh(std::vector<uint32_t>& b, uint32_t reg, std::vector<uint32_t> v) {
    b.push_back(0xC0007600u | (static_cast<uint32_t>(v.size()) << 16)); // PKT3(SET_SH_REG, n): count = n regs
    b.push_back(reg);
    b.insert(b.end(), v.begin(), v.end());
}
static void wait(std::vector<uint32_t>& b) { b.insert(b.end(), {0xC0053C00u, 0x13u, 0x1000u, 0x20u, 1u, 0xffffffffu, 4u}); }
static void dispatch(std::vector<uint32_t>& b) { b.insert(b.end(), {0xC0031500u, 8u, 1u, 1u, 1u}); }

int main() {
    { // 1.
        std::vector<uint32_t> ib;
        sh(ib, 0x20c, {0x00343500u, 0x80u});              // COMPUTE_PGM_LO/HI
        sh(ib, 0x240, {1u, 2u, 3u, 4u});                  // COMPUTE_USER_DATA_0..3
        const uint32_t split = static_cast<uint32_t>(ib.size());
        wait(ib);
        dispatch(ib);
        uint32_t n = 0;
        const uint32_t* p = state_prefix(ib.data(), split, &n);
        CHECK(n == split);
        bool same = p != nullptr;
        for (uint32_t i = 0; same && i < n; i++) same = p[i] == ib[i];
        CHECK(same);
        std::printf("1. head state replayed in front of the rest: %u of %u dwords, %s\n", n, split, same ? "identical" : "DIFFERENT");
    }
    { // 2.
        std::vector<uint32_t> nested;
        sh(nested, 0x240, {9u, 9u});
        std::vector<uint32_t> ib;
        const uint64_t a = reinterpret_cast<uint64_t>(nested.data());
        ib.insert(ib.end(), {0xC0023F00u, static_cast<uint32_t>(a & ~3ull), static_cast<uint32_t>((a >> 32) & 0xffu), static_cast<uint32_t>(nested.size())});
        const uint32_t split = static_cast<uint32_t>(ib.size());
        wait(ib);
        dispatch(ib);
        uint32_t n = 0;
        state_prefix(ib.data(), split, &n);
        std::printf("2. a register write inside an IB the head calls: %u dwords replayed (%s)\n", n, n == 0 ? "NOT replayed: the documented gap" : "replayed");
    }
    { // 3.
        std::vector<uint32_t> ib;
        sh(ib, 0x240, {1u, 2u, 3u, 4u});
        uint32_t n = 0;
        state_prefix(ib.data(), 3, &n); // the 6-dword packet cut at 3
        CHECK(n == 0);
        std::printf("3. a packet cut by the split point: %u dwords taken\n", n);
    }
    std::printf("%s (%d failed checks)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
