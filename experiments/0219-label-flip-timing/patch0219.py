#!/usr/bin/env python3
# Experiment 0219: the flip-timing diagnostic (BC5_DIRECT_FLIP_TRACE=1, off by default, journal only).
# Copies the shared KytyPlus source of bc5LleAgc.cpp with four insertions, each at an anchor that must
# occur exactly once:
#   1. a forward declaration of flip_trace_wait() next to wait_jobs();
#   2. the call at the cpu-wait give-up site (after "if (!ok) t_wait_given_up = true;");
#   3. the flip0219 namespace (watcher thread, completion ring) before completion_thread();
#   4. per-queue in-flight counting in cq_push() and at each completion.
# usage: patch0219.py <shared bc5LleAgc.cpp> <out .cpp>   (the shared file is only read)
import sys

FWD = '''// Experiment 0219 (BC5_DIRECT_FLIP_TRACE=1): defined before the completion queue's thread.
static void flip_trace_wait(const uint32_t* p, uint32_t len, bool is64, uint64_t label, uint64_t t0_ns, bool ok, bool game, const char* kind, uint32_t num_dwords, uint32_t at);
'''

BLOCK = '''// Experiment 0219 (BC5_DIRECT_FLIP_TRACE=1, off by default; journal only): when the label of a
// given-up wait is written, against the GPU jobs. After a cpu-wait is given up, a thread of its own
// ("bc5-flipw") reads its label every ~50 us for up to 2 s and journals each change of the value and
// the moment the wait would have been satisfied, with the jobs in flight on each completion queue
// and the last job completed by then. While a label is watched (and for 20 ms after), every job's
// completion is journaled too. A game-thread wait served after 4 ms or more gets the same summary
// at its end. Nothing waits longer and nothing more is submitted. A label a job writes flips while
// that job is in flight, just before its completion is seen; one the title's CPU code writes flips
// with no job in flight, or away from any completion.
namespace flip0219 {
struct Done {
    uint64_t ns = 0, n = 0;
    uint32_t dwords = 0;
    int      queue  = 0;
    char     kind[8] {};
};
struct Item {
    uint64_t id = 0, a = 0, t_wait0 = 0, t_give = 0, v_give = 0;
    uint32_t pkt[8] {};
    uint32_t num_dwords = 0, at = 0;
    int32_t  q0_at_give = 0, q1_at_give = 0;
    bool     is64 = false, game = false;
    char     kind[8] {};
};
struct Last {
    uint64_t between = 0; // completions in [from, t]
    double   ago_ms  = -1.0; // the last completion at or before t, this long before it (-1: none)
    uint64_t n       = 0;
    uint32_t dwords  = 0;
    int      queue   = -1;
    char     kind[8] {};
};
static std::mutex              mutex;
static std::condition_variable cv;
static std::deque<Item>        fresh;            // given up, not yet taken by the watcher
static Done                    ring[4096];       // the last completions (under mutex)
static uint64_t                done_count = 0;   // completions so far (under mutex)
static std::atomic<int32_t>    in_flight[2] {};  // jobs queued and not yet completed, per completion queue
static std::atomic<uint32_t>   watched {0};      // labels being watched
static std::atomic<uint64_t>   linger_until {0}; // journal completions until then (SoftCp::now_ns)
static std::atomic<uint64_t>   next_id {0};
static bool env() {
    static const bool e = BC5_DIAG_ENV("BC5_DIRECT_FLIP_TRACE") != nullptr;
    return e;
}
static bool on() {
    return env() && ::Log::Bc5LoggingOn();
}
static double t_of(uint64_t ns) { // the journal's t of a SoftCp::now_ns() time
    const uint64_t now = SoftCp::now_ns();
    return timing_now() - static_cast<double>(static_cast<int64_t>(now - ns)) / 1e9;
}
static uint64_t value_of(const Item& it) {
    return it.is64 ? *reinterpret_cast<const volatile uint64_t*>(it.a & ~7ull) : *reinterpret_cast<const volatile uint32_t*>(it.a);
}
static Last last_before(uint64_t t, uint64_t from) {
    Last l;
    std::lock_guard lk(mutex);
    for (uint64_t k = 0; k < 4096 && k < done_count; k++) {
        const Done& d = ring[(done_count - 1 - k) % 4096];
        if (d.ns > t) continue;
        if (l.queue < 0) {
            l.ago_ms = static_cast<double>(t - d.ns) / 1e6;
            l.n      = d.n;
            l.dwords = d.dwords;
            l.queue  = d.queue;
            std::memcpy(l.kind, d.kind, sizeof(l.kind));
        }
        if (d.ns < from) break;
        l.between++;
    }
    return l;
}
static void linger(uint64_t until) {
    uint64_t cur = linger_until.load();
    while (cur < until && !linger_until.compare_exchange_weak(cur, until)) {
    }
}
static void queued(int queue) {
    if (env()) in_flight[queue & 1]++;
}
static void done(uint64_t n, const char* kind, uint32_t dwords, int queue) {
    if (!env()) return;
    in_flight[queue & 1]--;
    const uint64_t now = SoftCp::now_ns();
    {
        std::lock_guard lk(mutex);
        Done& d  = ring[done_count % 4096];
        d.ns     = now;
        d.n      = n;
        d.dwords = dwords;
        d.queue  = queue;
        std::snprintf(d.kind, sizeof(d.kind), "%s", kind != nullptr ? kind : "");
        done_count++;
    }
    if (on() && (watched.load() != 0 || now < linger_until.load())) {
        journal("flip trace: job #%" PRIu64 " %s %u dwords done at t %.6f s (cq%d); in flight cq0 %d cq1 %d\\n", n, kind != nullptr ? kind : "", dwords, t_of(now), queue,
                in_flight[0].load(), in_flight[1].load());
    }
}
static void watcher() {
    pthread_setname_np(pthread_self(), "bc5-flipw");
    std::vector<Item>     active;
    std::vector<uint64_t> last_v;
    std::vector<uint32_t> changes;
    for (;;) {
        {
            std::unique_lock lk(mutex);
            if (active.empty()) cv.wait(lk, [] { return !fresh.empty(); });
            while (!fresh.empty()) {
                active.push_back(fresh.front());
                last_v.push_back(fresh.front().v_give);
                changes.push_back(0);
                fresh.pop_front();
            }
        }
        for (size_t k = 0; k < active.size();) {
            const Item&    it  = active[k];
            const uint64_t now = SoftCp::now_ns();
            const uint64_t v   = value_of(it);
            if (v != last_v[k]) {
                if (changes[k] < 16) {
                    journal("flip trace: #%" PRIu64 " 0x%" PRIx64 ": 0x%" PRIx64 " -> 0x%" PRIx64 " at t %.6f s, %.3f ms after the give-up; in flight cq0 %d cq1 %d\\n", it.id, it.a, last_v[k], v,
                            t_of(now), static_cast<double>(now - it.t_give) / 1e6, in_flight[0].load(), in_flight[1].load());
                }
                changes[k]++;
                last_v[k] = v;
            }
            const bool sat = wait_satisfied(it.pkt, it.is64);
            if (sat || now - it.t_give >= 2'000'000'000ull) {
                const Last l = last_before(now, it.t_give);
                journal("flip trace: #%" PRIu64 " 0x%" PRIx64 " %s %.3f ms after the give-up (%.3f ms after the wait began), t %.6f s; in flight cq0 %d cq1 %d (at the give-up %d %d); %" PRIu64
                        " jobs done since the give-up, the last %.3f ms before (#%" PRIu64 " %s %u dwords, cq%d); value 0x%" PRIx64 ", %u changes\\n",
                        it.id, it.a, sat ? "satisfied" : "NOT satisfied within 2 s", static_cast<double>(now - it.t_give) / 1e6, static_cast<double>(now - it.t_wait0) / 1e6, t_of(now),
                        in_flight[0].load(), in_flight[1].load(), it.q0_at_give, it.q1_at_give, l.between, l.ago_ms, l.n, l.kind, l.dwords, l.queue, v, changes[k]);
                linger(now + 20'000'000ull);
                active.erase(active.begin() + static_cast<std::ptrdiff_t>(k));
                last_v.erase(last_v.begin() + static_cast<std::ptrdiff_t>(k));
                changes.erase(changes.begin() + static_cast<std::ptrdiff_t>(k));
                watched--;
                continue;
            }
            k++;
        }
        std::this_thread::sleep_for(std::chrono::microseconds(20));
    }
}
} // namespace flip0219

static void flip_trace_wait(const uint32_t* p, uint32_t len, bool is64, uint64_t label, uint64_t t0_ns, bool ok, bool game, const char* kind, uint32_t num_dwords, uint32_t at) {
    if (!flip0219::on()) return;
    const uint64_t now       = SoftCp::now_ns();
    const double   waited_ms = static_cast<double>(now - t0_ns) / 1e6;
    if (ok) {
        if (!game || now - t0_ns < 4'000'000ull) return;
        const flip0219::Last l = flip0219::last_before(now, t0_ns);
        journal("flip trace: served %s %u dwords at %u on 0x%" PRIx64 " after %.3f ms, t %.6f s; in flight cq0 %d cq1 %d; %" PRIu64 " jobs done during the wait, the last %.3f ms before its end (#%" PRIu64
                " %s %u dwords, cq%d)\\n",
                kind, num_dwords, at, label, waited_ms, flip0219::t_of(now), flip0219::in_flight[0].load(), flip0219::in_flight[1].load(), l.between, l.ago_ms, l.n, l.kind, l.dwords, l.queue);
        flip0219::linger(now + 5'000'000ull);
        return;
    }
    if (flip0219::watched.load() >= 64) return;
    flip0219::Item it;
    it.id                = ++flip0219::next_id;
    const uint32_t n     = is64 ? 8u : (len < 8 ? len : 8u); // wait_satisfied() reads 8 dwords of a WAIT_REG_MEM64
    for (uint32_t k = 0; k < n; k++) it.pkt[k] = p[k];
    it.a          = (p[2] & ~3u) | (static_cast<uint64_t>(p[3] & 0xffffu) << 32u);
    it.is64       = is64;
    it.game       = game;
    it.t_wait0    = t0_ns;
    it.t_give     = now;
    it.num_dwords = num_dwords;
    it.at         = at;
    it.q0_at_give = flip0219::in_flight[0].load();
    it.q1_at_give = flip0219::in_flight[1].load();
    std::snprintf(it.kind, sizeof(it.kind), "%s", kind != nullptr ? kind : "");
    it.v_give              = flip0219::value_of(it);
    const flip0219::Last l = flip0219::last_before(now, now);
    journal("flip trace: #%" PRIu64 " given up: %s %u dwords at %u on 0x%" PRIx64 " (game thread %d) after %.3f ms, t %.6f s; value 0x%" PRIx64 "; in flight cq0 %d cq1 %d; the last job done %.3f ms before (#%" PRIu64
            " %s %u dwords, cq%d)\\n",
            it.id, it.kind, num_dwords, at, label, game ? 1 : 0, waited_ms, flip0219::t_of(now), it.v_give, it.q0_at_give, it.q1_at_give, l.ago_ms, l.n, l.kind, l.dwords, l.queue);
    {
        std::lock_guard lk(flip0219::mutex);
        flip0219::fresh.push_back(it);
        flip0219::watched++;
    }
    static std::once_flag once;
    std::call_once(once, [] { std::thread(flip0219::watcher).detach(); });
    flip0219::cv.notify_one();
}

'''


def tabs(text):
    """The source indents with tabs: four leading spaces become one tab."""
    out = []
    for line in text.split('\n'):
        n = len(line) - len(line.lstrip(' '))
        out.append('\t' * (n // 4) + ' ' * (n % 4) + line[n:])
    return '\n'.join(out)


def once(src, anchor):
    c = src.count(anchor)
    if c != 1:
        sys.exit('anchor %r occurs %d times' % (anchor, c))
    return src.index(anchor)


def after_line(src, anchor, new_line):
    """Insert new_line after the line holding anchor, with that line's indentation."""
    i = once(src, anchor)
    ls = src.rfind('\n', 0, i) + 1
    le = src.index('\n', i)
    line = src[ls:le]
    indent = line[:len(line) - len(line.lstrip('\t '))]
    return src[:le + 1] + indent + new_line + '\n' + src[le + 1:]


def main():
    src = open(sys.argv[1], encoding='utf-8', newline='').read()
    i = once(src, 'static void wait_jobs();\n') + len('static void wait_jobs();\n')
    src = src[:i] + FWD + src[i:]
    src = after_line(src, 'if (!ok) t_wait_given_up = true;',
                     'flip_trace_wait(p, len, op == 0x93, label, t0, ok, on_game_thread(), kind, num_dwords, i); // experiment 0219')
    i = once(src, 'static void completion_thread(int index) {')
    src = src[:i] + tabs(BLOCK) + src[i:]
    src = after_line(src, 'forget_label_writes(j.seq, r.ring, r.timed_out || r.rc == -125); // experiment 0055',
                     'flip0219::done(j.n, j.kind, j.num_dwords, index); // experiment 0219')
    src = after_line(src, 'if (it.fence) g_cq_fences++;', 'if (it.fence) flip0219::queued(index); // experiment 0219')
    open(sys.argv[2], 'w', encoding='utf-8', newline='').write(src)


main()
