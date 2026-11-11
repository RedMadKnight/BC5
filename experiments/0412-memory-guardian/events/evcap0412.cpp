// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0412: the CPU test of event_cap0412.hpp (no host, no system call). Builds on the laptop and on the box:
//   clang++ -std=c++20 -Wall -Wextra -Werror evcap0412.cpp -o evcap0412 && ./evcap0412
// Prints "evcap0412: N of N; end" and returns 0 when every check holds.
#include <cstdio>
#include <deque>
#include <vector>

#include "event_cap0412.hpp"

static int g_n = 0, g_ok = 0;
#define CHECK(...)                                                          \
    do {                                                                    \
        g_n++;                                                              \
        if (__VA_ARGS__) g_ok++;                                            \
        else std::printf("FAIL line %d: %s\n", __LINE__, #__VA_ARGS__);     \
    } while (0)

struct Ev {
    int      ident;
    unsigned fflags;
    long     data;
    bool     operator==(const Ev& o) const { return ident == o.ident && fflags == o.fflags && data == o.data; }
};

int main() {
    using namespace bc5::evcap;
    { // switches: off forms
        for (const char* off: {static_cast<const char*>(nullptr), "", "0"}) {
            const Cfg c = parse(off, off);
            CHECK(c.cap == 0 && !c.log && !c.bad && !c.on());
        }
    }
    { // switches: on forms
        Cfg c = parse("64", "1");
        CHECK(c.cap == 64 && c.log && !c.bad && c.on());
        c = parse("1", nullptr);
        CHECK(c.cap == 1 && !c.log && c.on());
        c = parse("65536", "0");
        CHECK(c.cap == 65536 && !c.log && !c.bad);
        c = parse(nullptr, "1");
        CHECK(c.cap == 0 && c.log && c.on());
    }
    { // switches: values that are not understood stay off and are flagged
        CHECK(parse("65537", nullptr).cap == 0 && parse("65537", nullptr).bad);
        CHECK(parse("-1", nullptr).cap == 0 && parse("-1", nullptr).bad);
        CHECK(parse("64x", nullptr).cap == 0 && parse("64x", nullptr).bad);
        CHECK(parse(" 64", nullptr).cap == 0 && parse(" 64", nullptr).bad);
        CHECK(parse("on", nullptr).cap == 0 && parse("on", nullptr).bad);
        CHECK(!parse(nullptr, "yes").log && parse(nullptr, "yes").bad);
        CHECK(parse("00", nullptr).cap == 0 && parse("00", nullptr).bad); // "00" is not "0": refused, not read as off
    }
    { // no bound: the queue is used as before
        std::deque<Ev> q;
        for (int i = 0; i < 1000; i++) CHECK(push(q, Ev {7, static_cast<unsigned>(i), i}, 0));
        CHECK(q.size() == 1000 && q.front() == (Ev {7, 0, 0}) && q.back() == (Ev {7, 999, 999}));
    }
    { // a bound of 3: the fourth trigger and every later one replace the newest entry; the older ones stay in order
        std::deque<Ev> q;
        CHECK(push(q, Ev {1, 1, 10}, 3) && push(q, Ev {1, 2, 20}, 3) && push(q, Ev {1, 3, 30}, 3));
        CHECK(!push(q, Ev {1, 4, 40}, 3) && q.size() == 3 && q[0] == (Ev {1, 1, 10}) && q[1] == (Ev {1, 2, 20}) && q[2] == (Ev {1, 4, 40}));
        CHECK(!push(q, Ev {1, 5, 50}, 3) && q.size() == 3 && q[2] == (Ev {1, 5, 50}));
        q.pop_front(); // the title read one
        CHECK(push(q, Ev {1, 6, 60}, 3) && q.size() == 3 && q[0] == (Ev {1, 2, 20}) && q[1] == (Ev {1, 5, 50}) && q[2] == (Ev {1, 6, 60}));
    }
    { // a bound of 1
        std::deque<Ev> q;
        CHECK(push(q, Ev {1, 1, 1}, 1) && !push(q, Ev {1, 2, 2}, 1) && q.size() == 1 && q[0] == (Ev {1, 2, 2}));
    }
    { // a queue already over the bound (the switch cannot do that, but nothing may grow it further)
        std::vector<Ev> q(10, Ev {1, 0, 0});
        CHECK(!push(q, Ev {1, 9, 9}, 4) && q.size() == 10 && q.back() == (Ev {1, 9, 9}));
    }
    { // the log lines: at 64 entries, then at each doubling
        Seen s;
        int  lines = 0;
        for (uint64_t len = 1; len <= 1000; len++) lines += due_len(s, len) ? 1 : 0;
        CHECK(lines == 4 && s.longest == 1000 && s.next_len == 1024); // 64, 128, 256, 512
        Seen j;
        CHECK(due_len(j, 300) && j.next_len == 512 && !due_len(j, 400) && due_len(j, 512) && j.longest == 512); // a jump
        Seen d;
        CHECK(!due_len(d, 63) && due_len(d, 64) && !due_len(d, 64) && !due_len(d, 10) && d.longest == 64);
    }
    { // the log lines: the 1st, 2nd, 4th, ... coalesced trigger
        Seen s;
        int  lines = 0;
        for (int i = 0; i < 1000; i++) lines += due_coalesced(s) ? 1 : 0;
        CHECK(lines == 10 && s.coalesced == 1000); // 1, 2, 4, ..., 512
    }
    std::printf("evcap0412: %d of %d; end\n", g_ok, g_n);
    return g_ok == g_n ? 0 : 1;
}
