#!/usr/bin/env python3
# Experiment 0226, integration: ADR 0013's held tail ON by default (BC5_DIRECT_HOLD_TAIL=0 disables it), as a one-file change of
# the shared tree's bc5LleAgc.cpp (md5 b210fa8e). The code is patch0226.py's, as tested in the A/B (F312); only the default differs.
#   - At a game-thread wait on the two-ring path whose label is unsatisfied and whose writer is not on a ring
#     (ring_will_satisfy), the title's thread no longer polls. The head has gone (ADR 0008's split and its
#     chain_flush(1)); the wait is kept for the GPU and the thread's chain (ADR 0010 section B, BC5_DIRECT_CHAIN=2)
#     is held: the rest of the buffer and the later buffers queue in it.
#   - A held chain is submitted only when each of its conditions is met: the label satisfied, or its writer on a
#     ring (the criteria the polling loop used). A holder thread ("bc5-hold") polls every ~20 us; an owner's flush
#     and the observe points (drain, chain_observe) wait for it; the chain watchdog leaves held chains alone.
#   - After BC5_DIRECT_HOLD_TAIL_MS (default 100) of a wait, its kept wait is dropped and the chain goes: today's
#     give-up, journaled. The host never writes a label.
#   - While a chain is held, a later wait on a label the held chain writes itself is kept for the GPU without a
#     condition (the chain's own order serves it).
# Not in this step: the ring consumer (ADR 0013 point 10).
# Each anchor must occur exactly once.
# usage: patch0226i.py <shared bc5LleAgc.cpp> <out .cpp>   (the input is only read)
import sys

COND = '''// ADR 0013 (experiment 0226, on by default; BC5_DIRECT_HOLD_TAIL=0 disables it): a wait a held chain carries for the GPU, released when
// its label is satisfied or its writer is on a ring.
struct HoldCond {
    uint32_t        pkt[8] {};
    const uint32_t* p     = nullptr; // the wait in the title's buffer: its kept offset is found by it
    bool            is64  = false;
    uint64_t        label = 0, t0 = 0;
};
'''

SLOT_ADD = '''std::vector<HoldCond>        hold;        // ADR 0013: the conditions the chain waits for before it may go
std::vector<uint64_t>        hold_writes; // ADR 0013: the labels the held chain's segments write'''

HOLD = '''// ADR 0013 (experiment 0226; on by default, BC5_DIRECT_HOLD_TAIL=0 disables it; F312): at a game-thread wait on the two-ring path
// whose label is unsatisfied and whose writer is not on a ring, the title's thread does not poll: the wait is kept
// for the GPU and the thread's chain is held until the label is satisfied or its writer is on a ring. The title's
// thread goes on and submits the writer itself, as on the console (F284, exp 0224). A holder thread submits the
// chain; owner flushes and the observe points wait for it; after BC5_DIRECT_HOLD_TAIL_MS (default 100) of the
// wait the kept wait is dropped (today's give-up). The host never writes a label.
static bool hold_on() { // on by default since experiment 0226's A/B (F312); BC5_DIRECT_HOLD_TAIL=0 disables it
    static const bool e = std::getenv("BC5_DIRECT_HOLD_TAIL") == nullptr || std::strcmp(std::getenv("BC5_DIRECT_HOLD_TAIL"), "0") != 0;
    return e;
}
static uint64_t hold_ns() {
    static const uint64_t v = (std::getenv("BC5_DIRECT_HOLD_TAIL_MS") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_HOLD_TAIL_MS"), nullptr, 10) : 100ull) * 1'000'000ull;
    return v;
}
static std::atomic<uint64_t>   g_hold_n {0}, g_hold_writer {0}, g_hold_sat {0}, g_hold_lost {0}, g_hold_inner {0}, g_hold_ns_sum {0}, g_hold_ns_max {0};
static std::mutex              g_hold_mu;
static std::condition_variable g_hold_cv;
static void                    chain_submit(ChainSlot& s, int why, bool foreign);
static void hold_stats(bool force) {
    static double last = 0;
    const double  now  = timing_now();
    if (!force && now - last < 10.0) return;
    last            = now;
    const uint64_t done = g_hold_writer.load() + g_hold_sat.load() + g_hold_lost.load();
    journal("hold tail: %" PRIu64 " holds; released with the writer on a ring %" PRIu64 ", satisfied %" PRIu64 ", GIVEN UP %" PRIu64 "; held %.2f ms on average, %.2f ms at most; %" PRIu64
            " waits kept inside held chains (their label written by the chain)\\n",
            g_hold_n.load(), g_hold_writer.load(), g_hold_sat.load(), g_hold_lost.load(), done != 0 ? static_cast<double>(g_hold_ns_sum.load()) / 1e6 / static_cast<double>(done) : 0.0,
            static_cast<double>(g_hold_ns_max.load()) / 1e6, g_hold_inner.load());
}
// The labels a buffer writes (WRITE_DATA, RELEASE_MEM, EVENT_WRITE_EOP and 0x1e, as acb_ready's scan reads them).
// Caller holds s.mu.
static void hold_note_writes(ChainSlot& s, const uint32_t* ib, uint32_t n) {
    for (uint32_t k = 0; k < n;) {
        const uint32_t hk = ib[k], tk = hk >> 30u;
        uint32_t       lk = 1;
        if (tk == 3 || tk == 0) {
            const uint32_t ck = (hk >> 16u) & 0x3fffu;
            lk                = ck == 0x3fffu ? 1 : ck + 2;
        }
        if (k + lk > n) break;
        if (tk == 3) {
            const uint32_t  op = (hk >> 8u) & 0xffu;
            const uint32_t* q  = ib + k;
            uint64_t        a  = 0;
            if (op == 0x37 && lk >= 4) a = (q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u);
            else if (op == 0x49 && lk >= 6) a = (q[3] & ~3u) | (static_cast<uint64_t>(q[4] & 0xffffu) << 32u);
            else if ((op == 0x47 || op == 0x1e) && lk >= 4) a = (q[2] & ~3u) | (static_cast<uint64_t>(q[3] & 0xffffu) << 32u);
            if (a != 0) s.hold_writes.push_back(a);
        }
        k += lk;
    }
}
static bool hold_chain_held() {
    ChainSlot&      s = g_chain_tl;
    std::lock_guard lk(s.mu);
    return !s.hold.empty();
}
static void hold_thread();
// Keeps a game-thread wait in the held chain: with a condition, unless the held chain writes its label itself.
// join: only if the chain is still held (the holder may have released and submitted it since the caller looked);
// false then, and the caller takes the normal path (its split sends the head first).
static bool hold_keep_wait(const uint32_t* p, uint32_t len, bool is64, uint64_t label, uint64_t t0, bool join) {
    ChainSlot& s = g_chain_tl;
    {
        std::lock_guard lk(s.mu);
        if (join && s.hold.empty()) return false;
        if (!s.hold.empty() && std::find(s.hold_writes.begin(), s.hold_writes.end(), label & ~3ull) != s.hold_writes.end()) {
            g_hold_inner++;
            return true; // the chain writes it first: the GPU's order serves it
        }
        HoldCond c;
        const uint32_t n = is64 ? 8u : (len < 8 ? len : 8u);
        for (uint32_t k = 0; k < n; k++) c.pkt[k] = p[k];
        c.p     = p;
        c.is64  = is64;
        c.label = label;
        c.t0    = t0;
        s.hold.push_back(c);
    }
    if (++g_hold_n <= 20 || (g_hold_n.load() & 0x3fu) == 0) journal("hold tail: the game thread's chain is held on 0x%" PRIx64 " at t %.6f s (%" PRIu64 " so far)\\n", label, timing_now(), g_hold_n.load());
    static std::once_flag started;
    std::call_once(started, [] { std::thread(hold_thread).detach(); });
    g_hold_cv.notify_one();
    return true;
}
// Releases the slot's conditions that are met: the label satisfied, or its writer on a ring. Past the bound the kept
// wait is dropped from its segment, or from the owner's t_keep_waits before it is appended (today's give-up). Returns
// whether nothing is held any more; block: poll until then (the bound ends it in any case).
static bool hold_release(ChainSlot& s, bool block) {
    for (;;) {
        {
            std::lock_guard lk(s.mu);
            const uint64_t now = SoftCp::now_ns();
            for (size_t k = 0; k < s.hold.size();) {
                HoldCond&  c    = s.hold[k];
                const bool sat  = wait_satisfied(c.pkt, c.is64);
                const bool wr   = !sat && ring_will_satisfy(c.pkt, c.is64, bc5::direct::kGfxRing);
                const bool lost = !sat && !wr && now - c.t0 >= hold_ns();
                if (!sat && !wr && !lost) {
                    k++;
                    continue;
                }
                const uint64_t held = now - c.t0;
                if (lost) {
                    bool dropped = false;
                    for (auto& seg: s.c.segs) {
                        if (seg.src != nullptr && c.p >= seg.src && c.p < seg.src + seg.n) {
                            std::erase(seg.keep, seg.off + seg.prefix + static_cast<uint32_t>(c.p - seg.src));
                            seg.given_up = true;
                            dropped      = true;
                        }
                    }
                    if (!dropped && &s == &g_chain_tl) {
                        std::erase(t_keep_waits, c.p);
                        t_wait_given_up = true;
                        dropped         = true;
                    }
                    if (!dropped) { // its segment is not appended yet and this is not the owner: it stays held until it is (never a kept wait without its writer)
                        k++;
                        continue;
                    }
                    journal("hold tail: the wait on 0x%" PRIx64 " GIVEN UP after %.1f ms: its kept wait dropped, the chain goes\\n", c.label, static_cast<double>(held) / 1e6);
                }
                g_hold_ns_sum += held;
                for (uint64_t m = g_hold_ns_max.load(); held > m && !g_hold_ns_max.compare_exchange_weak(m, held);) {
                }
                (sat ? g_hold_sat : (wr ? g_hold_writer : g_hold_lost))++;
                if (!lost) {
                    const uint64_t r = g_hold_writer.load() + g_hold_sat.load();
                    if (r <= 50 || (r & 0x3fu) == 0) journal("hold tail: released after %.3f ms on 0x%" PRIx64 ": %s (%" PRIu64 " released so far)\\n", static_cast<double>(held) / 1e6, c.label,
                                                             sat ? "label satisfied" : "writer on a ring", r);
                }
                s.hold.erase(s.hold.begin() + static_cast<std::ptrdiff_t>(k));
            }
            if (s.hold.empty()) return true;
        }
        if (!block) return false;
        std::this_thread::sleep_for(std::chrono::microseconds(20));
    }
}
// The holder: submits each held chain once its conditions are met (chain_submit's gate decides).
static void hold_thread() {
    pthread_setname_np(pthread_self(), "bc5-hold");
    for (;;) {
        bool any = false;
        {
            std::lock_guard lk(g_chains_mu);
            for (ChainSlot* s: g_chains) {
                bool held = false, busy = false;
                {
                    std::lock_guard sl(s->mu);
                    held = !s->hold.empty();
                    busy = s->in_submit;
                }
                if (!held) continue;
                any = true;
                if (!busy) chain_submit(*s, 11, true);
            }
        }
        hold_stats(false);
        if (any) {
            std::this_thread::sleep_for(std::chrono::microseconds(20));
            continue;
        }
        std::unique_lock lk(g_hold_mu);
        g_hold_cv.wait_for(lk, std::chrono::milliseconds(50));
    }
}
'''

HELD_BRANCH = '''// ADR 0013 (experiment 0226): the thread's chain is held already: this wait joins it, kept for the GPU (with a
// condition unless its writer is on a ring or the held chain writes its label); no split, no polling. Released in
// the meantime: the normal path below.
if (two_rings && hold_on() && chain_cross() && !wait_satisfied(p, op == 0x93) && hold_chain_held() &&
    (ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing) || hold_keep_wait(p, len, op == 0x93, label, t0, true))) {
    t_keep_waits.push_back(p);
    SoftCp::set_gpu_executed(p, len, {0});
    i += len;
    continue;
}'''

START_HOLD = '''// ADR 0013 (experiment 0226): the head has gone (or there was none); instead of polling here, the rest waits in
// the held chain and the title's thread goes on.
if (hold_on() && chain_cross() && (split || i == start) && !wait_satisfied(p, op == 0x93) && !ring_will_satisfy(p, op == 0x93, bc5::direct::kGfxRing)) {
    if (!split) chain_flush(1); // what the chain holds from earlier buffers goes first, as the split's flush does
    hold_keep_wait(p, len, op == 0x93, label, t0, false);
    t_keep_waits.push_back(p);
    SoftCp::set_gpu_executed(p, len, {0});
    i += len;
    continue;
}'''


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


def line_of(src, anchor):
    i = once(src, anchor)
    ls = src.rfind('\n', 0, i) + 1
    le = src.index('\n', i)
    line = src[ls:le]
    return ls, le, line[:len(line) - len(line.lstrip('\t '))]


def after_line(src, anchor, text):
    ls, le, indent = line_of(src, anchor)
    return src[:le + 1] + ''.join(indent + t + '\n' for t in tabs(text).split('\n')) + src[le + 1:]


def before_line(src, anchor, text):
    ls, le, indent = line_of(src, anchor)
    return src[:ls] + ''.join(indent + t + '\n' for t in tabs(text).split('\n')) + src[ls:]


def replace_once(src, old, new):
    i = once(src, old)
    return src[:i] + new + src[i + len(old):]


def main():
    src = open(sys.argv[1], encoding='utf-8', newline='').read()
    i = once(src, 'struct ChainSlot {')
    src = src[:i] + tabs(COND) + src[i:]
    src = after_line(src, "std::vector<SoftCp::GpuDone> marks; // the marks of the chains that carried the pending replays' buffers", SLOT_ADD)
    i = once(src, 'static std::atomic<uint64_t> g_chain_flushes {0}, g_chain_segments {0}')
    src = src[:i] + tabs(HOLD) + src[i:]
    # the gate: a held chain goes only when its conditions are met; owner flushes and observe points wait for that,
    # the watchdog (9) and the holder (11) do not
    old = '\t\tif (s.c.segs.empty() || (foreign && s.in_submit)) return;\n\t}\n\tstd::lock_guard order(s.flush_mu);'
    src = replace_once(src, old, '\t\tif (s.c.segs.empty() || (foreign && s.in_submit)) return;\n\t}\n'
                       '\tif (hold_on() && !hold_release(s, !(foreign && (why == 9 || why == 11)))) return; // ADR 0013 (experiment 0226)\n'
                       '\tstd::lock_guard order(s.flush_mu);')
    src = replace_once(src, '\t\tmine.gds     = c.gds;\n\t\ts.open_ns    = 0;\n',
                       '\t\tmine.gds     = c.gds;\n\t\ts.open_ns    = 0;\n\t\ts.hold_writes.clear(); // ADR 0013\n')
    # the watchdog leaves held chains to the holder
    src = replace_once(src, 'if (!s->c.segs.empty() && !s->in_submit && s->open_ns + chain_hold_ns() < deadline)',
                       'if (!s->c.segs.empty() && !s->in_submit && s->hold.empty() && s->open_ns + chain_hold_ns() < deadline)')
    src = replace_once(src, 'due = !s->c.segs.empty() && !s->in_submit && SoftCp::now_ns() >= s->open_ns + chain_hold_ns();',
                       'due = !s->c.segs.empty() && !s->in_submit && s->hold.empty() && SoftCp::now_ns() >= s->open_ns + chain_hold_ns();')
    # the owner's over-age close at chain_end leaves a held chain to the holder
    src = replace_once(src, 'over = !s.c.segs.empty() && SoftCp::now_ns() >= s.open_ns + chain_hold_ns();',
                       'over = !s.c.segs.empty() && s.hold.empty() && SoftCp::now_ns() >= s.open_ns + chain_hold_ns();')
    # the labels a held chain's segments write
    src = after_line(src, 'c.segs.push_back(std::move(seg));', 'if (!s.hold.empty()) hold_note_writes(s, ib, n); // ADR 0013')
    # the two-ring path
    src = before_line(src, 'if (two_rings && !wait_satisfied(p, op == 0x93)) {', HELD_BRANCH)
    src = before_line(src, 'static const uint64_t two_ns = (std::getenv("BC5_DIRECT_TWO_RING_WAIT_MS")', START_HOLD)
    open(sys.argv[2], 'w', encoding='utf-8', newline='').write(src)


main()
