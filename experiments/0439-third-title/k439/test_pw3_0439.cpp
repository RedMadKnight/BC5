// BC5 exp 0439 (tag pw439 mode 3): laptop test of pw0439.hpp. Build: clang++ -std=c++20 -I. test_pw3_0439.cpp
#include "pw0439.hpp"

#include <cstdio>
#include <vector>

using namespace bc5::pw439;
static int fails = 0;
#define CHECK(c)                                                                                                       \
    do {                                                                                                               \
        if (!(c)) {                                                                                                    \
            std::printf("FAIL line %d: %s\n", __LINE__, #c);                                                           \
            fails++;                                                                                                   \
        }                                                                                                              \
    } while (0)

static std::uint32_t h3(std::uint32_t op, std::uint32_t len) { return 0xC0000000u | ((len - 2) << 16) | (op << 8); }
static void wait(std::vector<std::uint32_t> &b, std::uint64_t a, bool mem = true, bool w64 = false) {
    b.insert(b.end(), {h3(w64 ? 0x93 : 0x3c, 7), (mem ? 1u << 4 : 0u) | 3u, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), 1, 0xffffffffu, 4});
}
static void release(std::vector<std::uint32_t> &b, std::uint64_t a) {
    b.insert(b.end(), {h3(0x49, 8), 0, 0x20000000u, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), 1, 0, 0});
}
static void write_data(std::vector<std::uint32_t> &b, std::uint64_t a, std::uint32_t dst_sel) {
    b.insert(b.end(), {h3(0x37, 5), dst_sel << 8, static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), 1});
}

int main() {
    // packet forms
    {
        std::vector<std::uint32_t> b;
        release(b, 0x2010449730);
        write_data(b, 0x20104cd1a0, 5);
        write_data(b, 0x1234, 0); // a register write: no label
        std::vector<std::uint64_t> w;
        labels_written(b, w);
        CHECK(w.size() == 2 && w[0] == 0x2010449730 && w[1] == 0x20104cd1a0);
        CHECK(packet_len(0xC0003F00u | (0x3fffu << 16)) == 1);
        CHECK(packet_len(0x80000000u) == 1);
    }
    // open waits: a wait after the same piece's own write is not open; register polls are not waits
    {
        std::vector<std::uint32_t> b;
        wait(b, 0x2010449750);       // open, offset 0
        release(b, 0x20104cd1a0);    // the piece writes cd1a0
        wait(b, 0x20104cd1a0);       // same piece
        wait(b, 0x20104cd180);       // open
        wait(b, 0x5555, false);      // register poll: ignored
        wait(b, 0x20105005e0, true, true); // 64-bit, open
        std::vector<OpenWait> o;
        std::uint64_t same = 0;
        open_waits(b, o, same);
        CHECK(same == 1);
        CHECK(o.size() == 3);
        CHECK(o.size() == 3 && o[0].off == 0 && o[0].label == 0x2010449750 && !o[0].is64);
        CHECK(o.size() == 3 && o[1].label == 0x20104cd180 && o[1].off == 7 + 8 + 7);
        CHECK(o.size() == 3 && o[2].is64);
    }
    // decide: same job dropped before the hook; hook decisions kept / dropped; bad hook values are drops
    {
        std::vector<std::uint32_t> b;
        wait(b, 0xA0); // the job writes it elsewhere
        wait(b, 0xB0); // hook: pending
        wait(b, 0xC0); // hook: met
        wait(b, 0xD0); // hook: no proof
        wait(b, 0xE0); // hook: busy
        wait(b, 0xF0); // hook: a bad value
        std::vector<std::uint64_t> job = {0xA0, 0x999};
        std::sort(job.begin(), job.end());
        std::uint64_t counts[kCount] = {};
        std::vector<std::uint32_t> keep;
        int hook_calls = 0;
        std::vector<std::pair<std::uint64_t, int>> notes;
        decide(
            b, job,
            [&](const std::uint32_t *p, bool) {
                hook_calls++;
                switch (p[2]) {
                case 0xB0: return static_cast<int>(kKeepPending);
                case 0xC0: return static_cast<int>(kKeepMet);
                case 0xE0: return static_cast<int>(kDropBusy);
                case 0xF0: return 77;
                default: return static_cast<int>(kDropNoProof);
                }
            },
            [&](std::uint64_t l, int d) { notes.push_back({l, d}); }, keep, counts);
        CHECK(hook_calls == 5);
        CHECK(counts[kDropSameJob] == 1);
        CHECK(counts[kKeepPending] == 1 && counts[kKeepMet] == 1);
        CHECK(counts[kDropNoProof] == 2 && counts[kDropBusy] == 1);
        CHECK(keep.size() == 2 && keep[0] == 7 && keep[1] == 14);
        CHECK(notes.size() == 6 && notes[0].second == kDropSameJob && notes[5].second == kDropNoProof);
    }
    // F916's shape: the GFX piece waits on a label whose only writer is the acb that waits on the piece's own later
    // write; with nothing submitted proving it, mode 3 drops it (no cycle) instead of keeping it (mode 2).
    {
        std::vector<std::uint32_t> piece;
        wait(piece, 0x2010449730);    // written by the acb only after its own wait
        release(piece, 0x2010449750); // the label the acb waits for
        std::vector<std::uint64_t> job;
        labels_written(piece, job);
        std::sort(job.begin(), job.end());
        std::uint64_t counts[kCount] = {};
        std::vector<std::uint32_t> keep;
        decide(piece, job, [](const std::uint32_t *, bool) { return static_cast<int>(kDropNoProof); }, [](std::uint64_t, int) {}, keep, counts);
        CHECK(keep.empty() && counts[kDropNoProof] == 1);
    }
    std::printf("%s (%d failures)\n", fails == 0 ? "PASS" : "FAIL", fails);
    return fails == 0 ? 0 : 1;
}
