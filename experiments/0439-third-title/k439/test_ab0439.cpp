// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag ab439): det tests of acb_ready's deep wait scan (BC5_0439_ACB_DEEP), on the GENERATED code: the text
// of ab439_scan and ab439_wait is cut out of the private unit by mkab0439.py into ab439_extract.inc, with stubs here for
// what it calls (wait_satisfied: the 32-bit label value against the reference, function 3 "equal"; ring_will_satisfy:
// false; timing_now). Buffers below 2^40, as an IB address has 40 bits.
//   python3 mkab0439.py <unit> ab439_extract.inc [plant] && g++ -std=c++20 -I<backend/include> test_ab0439.cpp -o t && ./t
// Cases: a call's unmet wait is found; a wait at the end of a 6-segment chain is found (the planted chain-as-depth misses
// it); an earlier write of the label in the walk hides the wait; a met wait is not held; a chain cycle ends on the budget;
// with the switch off an IB packet is not looked into; a plain wait packet is returned as itself either way.
#include "bc5/ib_chain.hpp"

#include <algorithm>
#include <atomic>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/mman.h>
#endif
#include <vector>

static bool g_switch = true;
static bool ab439_on() { return g_switch; }
static double timing_now() { return 0.0; }
static bool wait_satisfied(const uint32_t* p, bool) {
    const uint64_t a = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
    return *reinterpret_cast<const volatile uint32_t*>(a) == p[4];
}
static bool ring_will_satisfy(const uint32_t*, bool, int) { return false; }

#include "ab439_extract.inc"

static int g_fail = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); g_fail++; } } while (0)

struct Arena {
    uint32_t* base;
    size_t used = 0;
    Arena() {
#if defined(_WIN32)
        void* m = VirtualAlloc(reinterpret_cast<void*>(0x2000000000ull), 64u << 20, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
        if (m == nullptr) { std::printf("FAIL: no mapping below 2^40\n"); std::exit(2); }
#else
        void* m = mmap(reinterpret_cast<void*>(0x2000000000ull), 64u << 20, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
        if (m == MAP_FAILED) { std::printf("FAIL: no mapping below 2^40\n"); std::exit(2); }
#endif
        base = static_cast<uint32_t*>(m);
    }
    uint32_t* buf() { return base + 4096 * used++; }
};
struct B {
    uint32_t* p;
    uint32_t n = 0;
    void put(uint32_t v) { p[n++] = v; }
};
static void nop(B& b) { b.put(0xffff1000u); }
static void ib(B& b, const B& t, uint32_t tn, bool chain) {
    const uint64_t a = reinterpret_cast<uint64_t>(t.p);
    b.put(0xC0023F00u);
    b.put(static_cast<uint32_t>(a & 0xfffffffcu));
    b.put(static_cast<uint32_t>((a >> 32) & 0xffu));
    b.put(tn | (chain ? bc5::ib_chain::kChainBit : 0u));
}
static void wait_eq(B& b, uint64_t label, uint32_t ref) {
    b.put(0xC0053C00u);       // PKT3(WAIT_REG_MEM, 5)
    b.put(3u | (1u << 4));    // function 3 (equal), memory space
    b.put(static_cast<uint32_t>(label));
    b.put(static_cast<uint32_t>(label >> 32));
    b.put(ref);
    b.put(0xffffffffu);
    b.put(0x40u);
}
static void write_data(B& b, uint64_t a, uint32_t v) {
    b.put(0xC0033700u);
    b.put(2u << 8);
    b.put(static_cast<uint32_t>(a));
    b.put(static_cast<uint32_t>(a >> 32));
    b.put(v);
}
static const uint32_t* check_ib(const B& top) { // acb_ready's view: the IB packet at offset 0 of the top buffer
    std::vector<uint64_t> written;
    const uint32_t op = (top.p[0] >> 8u) & 0xffu;
    return ab439_wait(top.p, op, 4, true, written, 1);
}

int main() {
    Arena ar;
    uint32_t* labels = ar.buf(); // label memory, all 0
    const uint64_t L1 = reinterpret_cast<uint64_t>(labels + 0), L2 = reinterpret_cast<uint64_t>(labels + 16);
    { // 1. a call whose target waits on an unmet label
        B t{ar.buf()}; nop(t); wait_eq(t, L1, 1);
        B top{ar.buf()}; ib(top, t, t.n, false);
        CHECK(check_ib(top) == t.p + 1);
        std::printf("1. call with an unmet wait: %s\n", check_ib(top) == t.p + 1 ? "held" : "NOT HELD");
    }
    { // 2. a 6-segment chain from a depth-1 call, the wait in the last segment (depth 1+5 if chains were levels)
        B seg[6];
        for (auto& s : seg) s.p = ar.buf();
        wait_eq(seg[5], L2, 1);
        for (int k = 4; k >= 0; --k) { nop(seg[k]); ib(seg[k], seg[k + 1], seg[k + 1].n, true); }
        B top{ar.buf()}; ib(top, seg[0], seg[0].n, false);
        const uint32_t* r = check_ib(top);
        CHECK(r == seg[5].p);
        std::printf("2. wait at the end of a 6-segment chain: %s\n", r == seg[5].p ? "held" : "NOT HELD");
    }
    { // 3. an earlier write of the label in the walk: the writer is in the acb itself, not held
        B t{ar.buf()}; write_data(t, L1, 1); wait_eq(t, L1, 1);
        B top{ar.buf()}; ib(top, t, t.n, false);
        CHECK(check_ib(top) == nullptr);
        std::printf("3. the acb writes the label first: %s\n", check_ib(top) == nullptr ? "not held" : "HELD");
    }
    { // 4. a met wait
        labels[32] = 7;
        B t{ar.buf()}; wait_eq(t, reinterpret_cast<uint64_t>(labels + 32), 7);
        B top{ar.buf()}; ib(top, t, t.n, false);
        CHECK(check_ib(top) == nullptr);
        std::printf("4. a met wait: %s\n", check_ib(top) == nullptr ? "not held" : "HELD");
    }
    { // 5. a chain cycle: ends on the budget, nothing held, no hang
        B x{ar.buf()}, y{ar.buf()};
        nop(x); nop(y);
        ib(x, y, 5, true); ib(y, x, 5, true);
        B top{ar.buf()}; ib(top, x, x.n, false);
        CHECK(check_ib(top) == nullptr);
        std::printf("5. a chain cycle: ended on the budget, %s\n", check_ib(top) == nullptr ? "not held" : "HELD");
    }
    { // 6. switch off: an IB packet is not looked into; a plain wait is still itself
        B t{ar.buf()}; wait_eq(t, L1, 1);
        B top{ar.buf()}; ib(top, t, t.n, false);
        g_switch = false;
        CHECK(check_ib(top) == nullptr);
        std::vector<uint64_t> w;
        CHECK(ab439_wait(t.p, 0x3c, 7, true, w, 1) == t.p);
        g_switch = true;
        CHECK(ab439_wait(t.p, 0x3c, 7, true, w, 1) == t.p);
        std::printf("6. switch off: IB not looked into; a wait packet is itself on and off\n");
    }
    std::printf("%s (%d failed checks)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
