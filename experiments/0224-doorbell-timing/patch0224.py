#!/usr/bin/env python3
# Experiment 0224: two journal-only additions on top of exp 0221's v3 source (bc5LleAgc.v3.cpp = the shared tree's
# bc5LleAgc.cpp, md5 b210fa8e, through exp 0221's patch0221b.py). Both are off by default.
#   1. BC5_DIRECT_DOORBELL_TRACE=1: when the title writes a queue's doorbell, and when the ring consumer
#      (queue_consumer_thread) takes those entries and its submit of them returns. A thread of its own ("bc5-dbw")
#      reads every registered queue's write pointer every ~50 us; it and the consumer record their events in a
#      ring (also the start of a queue's deferral, when its next buffer waits on another queue). For each given-up
#      wait the flip trace (BC5_DIRECT_FLIP_TRACE=1) journals the events from 50 ms before the give-up to its end.
#   2. With BC5_DIRECT_FLIP_TRACE=1: the completion thread's timestamp rescale (the ts_collect() addresses, written
#      by RELEASE_MEM / EVENT_WRITE_EOP with DATA_SEL 3, rewritten as value * ts_scale()) is journaled whenever its
#      address is a label some wait has looked at: the address, the value read and written, the scale, and which
#      thread last polled that label and when. The rewrite itself is unchanged (the value is read once, as before).
# Each anchor must occur exactly once.
# usage: patch0224.py <bc5LleAgc.v3.cpp> <out .cpp>   (the input is only read)
import sys

FWD_ANCHOR = "static void held(uint64_t label); // experiment 0221 v3: acb_ready()'s not-ready branch\n"
FWD_ADD = '''static void waited(uint64_t a); // experiment 0224: wait_satisfied()
static void ts_write(uint64_t a, uint64_t old_v, uint64_t new_v, uint64_t n, const char* kind, double k); // experiment 0224
'''

DBT = '''// Experiment 0224 (BC5_DIRECT_DOORBELL_TRACE=1, off by default; journal only): when the title writes a queue's
// doorbell, and when the consumer below takes the entries and its submit of them returns. A thread of its own
// ("bc5-dbw") reads every registered queue's write pointer every ~50 us; it and the consumer record their events
// in a ring, which the flip trace (experiment 0221) journals around each given-up wait.
namespace dbt0224 {
struct Ev {
    uint64_t ns    = 0;
    int      queue = 0;
    int      type  = 0; // 0 the write pointer changed (a, b: old, new); 1 the consumer takes b dwords at a; 2 its submit of them returned; 3 the queue is deferred (b dwords pending at a)
    uint32_t a = 0, b = 0;
};
static std::mutex ev_mutex;
static Ev         ev_ring[16384];
static uint64_t   ev_count = 0;
static bool on() {
    static const bool e = BC5_DIAG_ENV("BC5_DIRECT_DOORBELL_TRACE") != nullptr;
    return e;
}
static void record(int queue, int type, uint32_t a, uint32_t b) {
    if (!on()) return;
    const uint64_t  ns = now_ns();
    std::lock_guard lk(ev_mutex);
    ev_ring[ev_count % 16384] = {ns, queue, type, a, b};
    ev_count++;
}
static void watcher() {
    pthread_setname_np(pthread_self(), "bc5-dbw");
    std::vector<QueueReg> qs;
    std::vector<uint64_t> last;
    for (uint64_t pass = 0;; pass++) {
        if ((pass % 1000) == 0) { // the registered queues, every ~50 ms
            std::lock_guard lock(g_mutex);
            qs = g_queues;
        }
        if (last.size() < qs.size()) last.resize(qs.size(), ~0ull);
        for (size_t i = 0; i < qs.size(); i++) {
            const auto& q = qs[i];
            if (q.doorbell_page == 0) continue;
            const uint64_t w = reinterpret_cast<const volatile uint64_t*>(q.doorbell_page)[q.d == 0 ? 0 : q.d - 1];
            if (w == last[i]) continue;
            if (last[i] != ~0ull) record(static_cast<int>(i), 0, static_cast<uint32_t>(last[i]), static_cast<uint32_t>(w));
            last[i] = w;
        }
        std::this_thread::sleep_for(std::chrono::microseconds(50));
    }
}
static void start() {
    if (!on()) return;
    static std::once_flag once;
    std::call_once(once, [] { std::thread(watcher).detach(); });
}
// The events in [from, to] (now_ns), oldest first; at most the ring's last 16384.
static std::vector<Ev> between(uint64_t from, uint64_t to) {
    std::vector<Ev> out;
    std::lock_guard lk(ev_mutex);
    const uint64_t first = ev_count > 16384 ? ev_count - 16384 : 0;
    for (uint64_t k = first; k < ev_count; k++) {
        const Ev& e = ev_ring[k % 16384];
        if (e.ns >= from && e.ns <= to) out.push_back(e);
    }
    return out;
}
} // namespace dbt0224

'''

FLIP_ADD = '''// Experiment 0224: the labels the waits have looked at (wait_satisfied()), with the last poll and its thread, so a
// timestamp rewrite that lands on one can be named. Lock-free, never cleared; 512 slots.
struct Waited {
    std::atomic<uint64_t> label {0}, ns {0};
    std::atomic<int>      who {0}; // 1 the game thread, 2 another thread (the ring consumer)
};
static Waited waited_tab[512];
static void waited(uint64_t a) {
    if (!env()) return;
    a &= ~7ull;
    const size_t h = static_cast<size_t>(((a >> 3u) * 0x9E3779B97F4A7C15ull) >> 55u);
    for (size_t k = 0; k < 16; k++) {
        Waited&  w   = waited_tab[(h + k) & 511u];
        uint64_t cur = w.label.load(std::memory_order_relaxed);
        if (cur == 0 && w.label.compare_exchange_strong(cur, a)) cur = a;
        if (cur != a) continue;
        w.ns.store(SoftCp::now_ns(), std::memory_order_relaxed);
        w.who.store(on_game_thread() ? 1 : 2, std::memory_order_relaxed);
        return;
    }
}
static const Waited* waited_find(uint64_t a) {
    a &= ~7ull;
    const size_t h = static_cast<size_t>(((a >> 3u) * 0x9E3779B97F4A7C15ull) >> 55u);
    for (size_t k = 0; k < 16; k++) {
        const Waited& w = waited_tab[(h + k) & 511u];
        const uint64_t cur = w.label.load(std::memory_order_relaxed);
        if (cur == a) return &w;
        if (cur == 0) return nullptr;
    }
    return nullptr;
}
static void ts_write(uint64_t a, uint64_t old_v, uint64_t new_v, uint64_t n, const char* kind, double k) {
    if (!on()) return;
    const Waited* w   = waited_find(a);
    const bool    fix = std::find(wp_fixed().begin(), wp_fixed().end(), a & ~7ull) != wp_fixed().end();
    if (w == nullptr && !fix) return;
    const uint64_t now  = SoftCp::now_ns();
    const uint64_t last = w != nullptr ? w->ns.load(std::memory_order_relaxed) : 0;
    const uint64_t cur  = value64(a);
    journal("ts trace: job #%" PRIu64 " %s rewrote the timestamp at 0x%" PRIx64 " at t %.6f s: 0x%" PRIx64 " -> 0x%" PRIx64 " (scale %.9f), value just after 0x%" PRIx64 "; a wait label%s, last polled %.3f ms before by %s\\n",
            n, kind != nullptr ? kind : "", a, t_of(now), old_v, new_v, k, cur, fix ? " (one of the fixed compute labels)" : "",
            last != 0 && now >= last ? static_cast<double>(now - last) / 1e6 : -1.0, w == nullptr ? "-" : (w->who.load() == 1 ? "the game thread" : "another thread (the ring consumer)"));
}
'''

DUMP = '''{ // experiment 0224: the doorbell and ring-consumer events around this give-up
    const auto evs = SoftCp::dbt0224::between(it.t_give - 50'000'000ull, now);
    for (const auto& e: evs) {
        const double rel = (static_cast<double>(e.ns) - static_cast<double>(it.t_give)) / 1e6;
        if (e.type == 0) journal("doorbell trace: #%" PRIu64 " queue %d write pointer %u -> %u at t %.6f s (%+.3f ms from the give-up)\\n", it.id, e.queue, e.a, e.b, t_of(e.ns), rel);
        else if (e.type == 1) journal("doorbell trace: #%" PRIu64 " queue %d consumer takes %u dwords at %u at t %.6f s (%+.3f ms from the give-up)\\n", it.id, e.queue, e.b, e.a, t_of(e.ns), rel);
        else if (e.type == 2) journal("doorbell trace: #%" PRIu64 " queue %d consumer's submit of %u dwords at %u returned at t %.6f s (%+.3f ms from the give-up)\\n", it.id, e.queue, e.b, e.a, t_of(e.ns), rel);
        else journal("doorbell trace: #%" PRIu64 " queue %d deferred, %u dwords pending at %u, at t %.6f s (%+.3f ms from the give-up)\\n", it.id, e.queue, e.b, e.a, t_of(e.ns), rel);
    }
}'''


def once(src, anchor):
    c = src.count(anchor)
    if c != 1:
        sys.exit('anchor %r occurs %d times' % (anchor, c))
    return src.index(anchor)


def line_of(src, anchor):
    i = once(src, anchor)
    ls = src.rfind('\n', 0, i) + 1
    le = src.index('\n', i)
    line = src[ls:le]
    return ls, le, line[:len(line) - len(line.lstrip('\t '))]


def after_line(src, anchor, text):
    """Insert text (one or more lines) after the line holding anchor, with that line's indentation."""
    ls, le, indent = line_of(src, anchor)
    return src[:le + 1] + ''.join(indent + t + '\n' for t in text.split('\n')) + src[le + 1:]


def before_line(src, anchor, text):
    ls, le, indent = line_of(src, anchor)
    return src[:ls] + ''.join(indent + t + '\n' for t in text.split('\n')) + src[ls:]


def tabs(text):
    """The source indents with tabs: four leading spaces become one tab."""
    out = []
    for line in text.split('\n'):
        n = len(line) - len(line.lstrip(' '))
        out.append('\t' * (n // 4) + ' ' * (n % 4) + line[n:])
    return '\n'.join(out)


def main():
    src = open(sys.argv[1], encoding='utf-8', newline='').read()
    i = once(src, FWD_ANCHOR) + len(FWD_ANCHOR)
    src = src[:i] + FWD_ADD + src[i:]
    src = after_line(src, '\tlabel_watch(a);', 'flip0221::waited(a); // experiment 0224')
    i = once(src, 'static void queue_consumer_thread() {')
    src = src[:i] + tabs(DBT) + src[i:]
    src = after_line(src, '\tDirect::set_source(1);', 'dbt0224::start(); // experiment 0224')
    src = before_line(src, "Direct::chain_begin(); // ADR 0010: the slice's buffers as one submission", 'dbt0224::record(t_queue_idx, 1, r, take); // experiment 0224')
    # the consumer's submit returned: the line after its chain_end() is "{" before "auto marks = std::move(t_gpu_done);"
    i = once(src, '\t\t\tDirect::chain_end();\n\t\t\t{\n\t\t\t\tauto marks = std::move(t_gpu_done);')
    j = i + len('\t\t\tDirect::chain_end();\n')
    src = src[:j] + '\t\t\tdbt0224::record(t_queue_idx, 2, r, take); // experiment 0224\n' + src[j:]
    old = 'if (s.deferred_since == 0) s.deferred_since = now;'
    i = once(src, old)
    src = src[:i] + 'if (s.deferred_since == 0) { s.deferred_since = now; dbt0224::record(t_queue_idx, 3, r, pending); } // experiment 0224' + src[i + len(old):]
    # the timestamp rescale: the value read once (as before), then journaled when its address is a wait label
    old = '*v      = static_cast<uint64_t>(static_cast<double>(*v) * k);'
    ls, le, indent = line_of(src, old)
    src = (src[:ls] + indent + 'const uint64_t old_v = *v; // experiment 0224: read once, as the line it replaces did\n'
           + indent + '*v                   = static_cast<uint64_t>(static_cast<double>(old_v) * k);\n'
           + indent + 'flip0221::ts_write(a, old_v, static_cast<uint64_t>(static_cast<double>(old_v) * k), j.n, j.kind, k); // experiment 0224\n'
           + src[le + 1:])
    # the waited-label table and ts_write(), inside namespace flip0221 before last_before() (after env(), on(),
    # wp_fixed(), t_of() and value64(), which they use)
    i = once(src, 'static Last last_before(uint64_t t, uint64_t from) {')
    src = src[:i] + tabs(FLIP_ADD) + src[i:]
    src = after_line(src, 'for (auto& wl: wp_labels) wp_read(wl, it, "compute", "at the end", now);', tabs(DUMP))
    open(sys.argv[2], 'w', encoding='utf-8', newline='').write(src)


main()
