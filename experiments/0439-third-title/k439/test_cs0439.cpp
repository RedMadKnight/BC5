// BC5 exp 0439 (tag cs439): the state stack with BC5_0439_PUSH_NO_CLEAR (stand-in, no GPU). Build beside the patched
// state_stack.cpp; run twice: `test_cs0439 0` (switch unset) and `test_cs0439 1` (the test sets it before the first read).
#include "bc5/policy.hpp"
#include "bc5/state_stack.hpp"
#include <cstdio>
#include <cstdlib>
#include <vector>
using namespace bc5;
static int fails = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); fails++; } } while (0)
int main(int argc, char **argv) {
    const int want = argc > 1 ? std::atoi(argv[1]) : 0;
#ifdef _WIN32
    if (want == 1) _putenv("BC5_0439_PUSH_NO_CLEAR=1");
    if (want == 2) _putenv("BC5_0439_COND_POP_NOP=1");
#else
    if (want == 1) setenv("BC5_0439_PUSH_NO_CLEAR", "1", 1);
    if (want == 2) setenv("BC5_0439_COND_POP_NOP", "1", 1);
#endif
    // SET_CONTEXT_REG 0x5 = 1; push; SET_CONTEXT_REG 0x5 = 2; pop
    const std::vector<std::uint32_t> src = {0xC0016900u, 5, 1, 0xC0001200u, 1, 0xC0016900u, 5, 2, 0xC0001200u, 2};
    std::vector<std::uint32_t> filt = src;
    filt[4] = 0; filt[9] = 0; // the policy filter's cmd 0
    for (int mode = want == 1 ? 1 : 0; want != 2 && mode == (want == 1 ? 1 : 0); ++mode) {
        state_stack::Tracker t;
        state_stack::Stats st;
        auto rd = [](std::uint64_t, std::uint64_t) { return false; };
        std::vector<std::uint32_t> io = filt;
        t.apply_in_place(src, io, rd, st);
        CHECK(st.pushes == 1 && st.pops == 1 && st.unmatched_pops == 0);
        if (mode == 1) { CHECK(io[3] == policy::kNop && io[4] == policy::kNop); }
        else { CHECK(io[3] == 0xC0001200u && io[4] == 0); }
        // the pop is NOP-ed and followed by SET_CONTEXT_REG 0x5 = 1
        bool restored = false;
        for (std::size_t i = 0; i + 2 < io.size(); ++i) restored = restored || (io[i] == 0xC0016900u && io[i + 1] == 5 && io[i + 2] == 1 && i >= 8);
        CHECK(restored);
        CHECK(t.context().valid.test(5) && t.context().value[5] == 1);
    }
    // a pop with no push: unmatched, left as the filter's clear
    {
        state_stack::Tracker t; state_stack::Stats st;
        std::vector<std::uint32_t> s2 = {0xC0001200u, 2}, io = {0xC0001200u, 0};
        t.apply_in_place(s2, io, [](std::uint64_t, std::uint64_t) { return false; }, st);
        CHECK(st.unmatched_pops == 1 && io[1] == 0);
    }
    if (want == 2) { // BC5_0439_COND_POP_NOP: a pop inside COND_EXEC is NOP-ed
        state_stack::Tracker t; state_stack::Stats st;
        std::vector<std::uint32_t> s3 = {0xC0032200u, 0, 0, 0, 2, 0xC0001200u, 2}, io = s3;
        io[6] = 0;
        t.apply_in_place(s3, io, [](std::uint64_t, std::uint64_t) { return false; }, st);
        CHECK(st.conditional == 1 && io[5] == policy::kNop && io[6] == policy::kNop);
    }
    std::printf(fails ? "test_cs0439: %d failures\n" : "test_cs0439: ok\n", fails);
    return fails != 0;
}
