// BC5 exp 0439 (tag f4p439): det test of f4p0439.hpp (arm A's piece-wait walk and F2's cycle question). Synthetic
// buffers only. Build: c++ -std=c++20 -I. test_f4p0439.cpp && ./a.out
#include "f4p0439.hpp"

#include <cstdio>
#include <map>

using namespace bc5::f4p439;

static int fails = 0;
#define CHECK(c)                                                         \
    do {                                                                 \
        if (!(c)) { std::printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } \
    } while (0)

static uint32_t hdr(uint32_t op, uint32_t len) { return 0xC0000000u | ((len - 2) << 16u) | (op << 8u); }
static void ib(std::vector<uint32_t>& v, uint64_t a, uint32_t n, bool chain) {
    v.push_back(hdr(0x3f, 4));
    v.push_back(static_cast<uint32_t>(a));
    v.push_back(static_cast<uint32_t>(a >> 32u));
    v.push_back(n | (chain ? (1u << 20) : 0u));
}
static void wait(std::vector<uint32_t>& v, uint64_t l, bool mem = true) {
    v.push_back(hdr(0x3c, 7));
    v.push_back(3u | (mem ? 0x10u : 0u)); // function ==, MEM_SPACE
    v.push_back(static_cast<uint32_t>(l));
    v.push_back(static_cast<uint32_t>(l >> 32u));
    v.push_back(1);
    v.push_back(0xffffffffu);
    v.push_back(4);
}
static void nop(std::vector<uint32_t>& v) { v.push_back(hdr(0x10, 2)); v.push_back(0); }

int main() {
    std::map<uint64_t, std::vector<uint32_t>> mem;
    const uint64_t A = 0x2010000000, B = 0x2011000000, C = 0x2012000000, D = 0x2013000000;
    const uint64_t L1 = 0x20000082e0, L2 = 0x2000008200, L3 = 0x2000008300, L4 = 0x2000008400, LR = 0x2000008000;
    // piece A (chained from the root): a wait on L1, a register wait (not memory), a call to B, a chain back to A (a loop)
    // piece B (called, depth 1): a wait on L2, a call to D (depth 2: D is unmapped)
    // piece C: only reached by a root IB packet the filter did not keep
    auto& b = mem[B];
    wait(b, L2);
    ib(b, D, 9, false);
    auto& c = mem[C];
    wait(c, L3);
    auto& a = mem[A];
    wait(a, L1);
    wait(a, 0x1234, false);
    ib(a, B, static_cast<uint32_t>(b.size()), false);
    const size_t self = a.size();
    ib(a, A, 0, true);
    a[self + 3] = static_cast<uint32_t>(a.size()) | (1u << 20); // the loop: each address once
    std::vector<uint32_t> root;
    wait(root, LR); // a root wait: not included (ho430 records those)
    nop(root);
    const uint32_t off_c = static_cast<uint32_t>(root.size());
    ib(root, C, static_cast<uint32_t>(c.size()), false);
    const uint32_t off_a = static_cast<uint32_t>(root.size());
    ib(root, A, static_cast<uint32_t>(a.size()), true);
    const std::vector<uint32_t> executed = {0, 7, off_a}; // the root wait, the NOP and the chain to A ran; the IB to C was dropped
    (void)off_c;
    const Reader read = [&mem](uint64_t ad, uint32_t n) -> const uint32_t* {
        const auto it = mem.find(ad);
        return it == mem.end() || it->second.size() < n ? nullptr : it->second.data();
    };
    const auto w = piece_waits(root.data(), static_cast<uint32_t>(root.size()), executed, read);
    CHECK(w.size() == 2);
    CHECK(std::find(w.begin(), w.end(), L1) != w.end());
    CHECK(std::find(w.begin(), w.end(), L2) != w.end());
    CHECK(std::find(w.begin(), w.end(), L3) == w.end()); // not executed
    CHECK(std::find(w.begin(), w.end(), LR) == w.end()); // the root's own
    CHECK(std::find(w.begin(), w.end(), 0x1234ull) == w.end()); // a register wait
    // depth: a call chain deeper than 3 is not followed
    {
        std::map<uint64_t, std::vector<uint32_t>> m2;
        uint64_t                                  base = 0x3000000000;
        for (int d = 0; d < 6; d++) {
            auto& p = m2[base + d * 0x1000];
            wait(p, 0x2000009000 + d * 0x20);
            if (d < 5) ib(p, base + (d + 1) * 0x1000, 0, false);
        }
        for (int d = 0; d < 5; d++) m2[base + d * 0x1000][7 + 3] = static_cast<uint32_t>(m2[base + (d + 1) * 0x1000].size());
        std::vector<uint32_t> r2;
        ib(r2, base, static_cast<uint32_t>(m2[base].size()), false); // depth 1
        const Reader rd2 = [&m2](uint64_t ad, uint32_t n) -> const uint32_t* {
            const auto it = m2.find(ad);
            return it == m2.end() || it->second.size() < n ? nullptr : it->second.data();
        };
        const auto w2 = piece_waits(r2.data(), static_cast<uint32_t>(r2.size()), {0}, rd2);
        CHECK(w2.size() == 3); // depths 1, 2, 3
    }
    // F2's question
    CHECK(cycle(w, {L1}));
    CHECK(cycle(w, {0x5555, L2}));
    CHECK(!cycle(w, {L3, L4}));
    CHECK(!cycle({}, {L1}));
    // arm C: the split point
    {
        std::vector<uint32_t> r;
        wait(r, LR);
        nop(r);
        const size_t at = r.size();
        ib(r, A, 10, true);
        CHECK(tail_chain_at(r.data(), static_cast<uint32_t>(r.size())) == static_cast<int64_t>(at));
        std::vector<uint32_t> call = r;
        call[at + 3] &= ~(1u << 20); // a call at the end, not a chain
        CHECK(tail_chain_at(call.data(), static_cast<uint32_t>(call.size())) == -1);
        std::vector<uint32_t> mid;
        ib(mid, B, 10, true); // a chain first, then more: not the tail
        nop(mid);
        CHECK(tail_chain_at(mid.data(), static_cast<uint32_t>(mid.size())) == -1);
        std::vector<uint32_t> only;
        ib(only, A, 10, true); // nothing before the chain: no head to split off
        CHECK(tail_chain_at(only.data(), static_cast<uint32_t>(only.size())) == -1);
        std::vector<uint32_t> two;
        ib(two, B, 10, false); // a call, a release-like NOP, then the tail chain: the last one
        nop(two);
        const size_t at2 = two.size();
        ib(two, A, 10, true);
        CHECK(tail_chain_at(two.data(), static_cast<uint32_t>(two.size())) == static_cast<int64_t>(at2));
        std::vector<uint32_t> cut = r;
        cut.pop_back(); // a truncated packet
        CHECK(tail_chain_at(cut.data(), static_cast<uint32_t>(cut.size())) == -1);
    }
    std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
    return fails == 0 ? 0 : 1;
}
