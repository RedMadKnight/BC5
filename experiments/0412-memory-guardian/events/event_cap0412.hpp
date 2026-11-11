// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0412 (the ASTRO BOT host leak, README section 10; tag ev412): a bound on an event's pending queue.
// The host's event queue keeps, for an event that is triggered again before the title has read it, one more entry in
// KernelEqueueEvent::pending_events, a std::deque without a bound (EopEventTriggerFunc in
// src/graphics/host_gpu/renderer/sync.cpp, AmprEventTriggerFunc in src/kernel/eventQueue.cpp). An event the title reads
// more slowly than it is triggered, or never reads, grows by one entry per trigger for ever.
//   KYTY_BC5_EVENT_PENDING_CAP=<n>   1..65536: an event's pending queue holds at most n entries; a trigger past that
//                                    replaces the newest entry (the triggers are coalesced, the latest data is kept).
//   KYTY_BC5_EVENT_PENDING_LOG=1     one line when an event's queue first reaches 64 entries and each time it doubles, and
//                                    with the cap one line at the 1st, 2nd, 4th, ... coalesced trigger: which event it is.
// Unset, empty and "0" are off (F767); with both off the queue is used exactly as before. No system call here: this file
// is what evcap0412.cpp tests on the laptop.
#pragma once
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace bc5::evcap {

struct Cfg {
    size_t cap = 0;     // 0: no bound
    bool   log = false;
    bool   bad = false; // a value that was not understood (the switch stays off)
    bool   on() const { return cap != 0 || log; }
};

inline bool env_on(const char* e) {
    return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0);
}

inline Cfg parse(const char* cap, const char* log) {
    Cfg c;
    if (env_on(cap)) {
        char*                    end = nullptr;
        const unsigned long long v = std::strtoull(cap, &end, 10);
        if (end != cap && *end == 0 && v >= 1 && v <= 65536 && cap[0] >= '0' && cap[0] <= '9') c.cap = static_cast<size_t>(v);
        else c.bad = true;
    }
    if (env_on(log)) {
        if (std::strcmp(log, "1") == 0) c.log = true;
        else c.bad = true;
    }
    return c;
}

// Puts e at the end of q, or over q's newest entry when q already holds cap entries (cap 0: no bound).
// True when the queue grew, false when the trigger was coalesced.
template <class Q, class E> bool push(Q& q, const E& e, size_t cap) {
    if (cap != 0 && q.size() >= cap) {
        q.back() = e;
        return false;
    }
    q.push_back(e);
    return true;
}

// What is remembered of one event (by ident and filter) for the log lines.
struct Seen {
    uint64_t longest = 0, coalesced = 0, next_len = 64, next_coalesced = 1;
};

// After a push that left the queue `len` long: whether a "longest queue" line is due (at 64 entries, then at each doubling).
inline bool due_len(Seen& s, uint64_t len) {
    if (len > s.longest) s.longest = len;
    if (len < s.next_len) return false;
    while (s.next_len <= len) s.next_len *= 2;
    return true;
}

// After a coalesced trigger: whether a line is due (the 1st, 2nd, 4th, ... one).
inline bool due_coalesced(Seen& s) {
    s.coalesced++;
    if (s.coalesced < s.next_coalesced) return false;
    s.next_coalesced *= 2;
    return true;
}

} // namespace bc5::evcap
