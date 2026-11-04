#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, port agent "eq": exp 0405's equeue, timer, kevent and mmap items, in
src/kernel/eventQueue.cpp and in the libkernel shims of src/libs/bc5LleAgc.cpp (the kevent/equeue/timer shims, the mmap
shim and the shims' registration line of sceKernelAddTimerEvent; nothing else of that unit is touched).
Items (exp 0405 README top-32 rows 1, 2, 3, 7, 13; reports raw/r2-kyty-sharpemu.md section 5, raw/r3-gpu-memory.md
"e4-now port specs"), each ported in adapted form with its source named in the inserted comments:
  KYTY_BC5_EQUEUE_FIXES     kk02  R2 KK02 + SK01  a level event is delivered once per wait, not into every slot
                                                  (KytyPS5 dfec14a kernel/eventQueue.cpp:120-127, GPL-2.0; sharpemu
                                                  514d766 KernelEventQueueCompatExports.cs:1940-1960, GPL-2.0-or-later)
                            sk03  R2 SK03         sceKernelWaitEqueue accepts out == NULL (sharpemu 514d766 :783-976)
                            g1    R3 G1           kevent honours its timespec (FreeBSD kevent(2); AnyPS5 4f41f4c37
                                                  core/libs/prx/libkernel/Equeue/src/Kqueue.cpp:545-551, 669-678, for the
                                                  semantics; GPL-2.0-only)
                            kk01  R2 KK01         sceKernelAddTimerEvent takes microseconds by value and makes a periodic
                                                  EVFILT_TIMER with EV_CLEAR, data = expirations since the last read
                                                  (KytyPS5 dfec14a kernel/eventQueue.cpp:142-154, 210-234, 525-539); the
                                                  period lives in a side table of the queue (no header change);
                                                  sceKernelDeleteTimerEvent (YWQFUyXIVdU, AnyPS5 Equeue.cpp:841-843) is
                                                  registered with it
  KYTY_BC5_MMAP_SHIM_FIXES  hint  R3 M2 (a)       an anonymous mmap's address without MAP_FIXED is a hint; device
                                                  mappings (fd >= 0: Sony's driver at 0xfe0200000) keep today's path
                            prot  R3 M2 (b)       prot 0 stays no-access; no memset without CPU write (shadPS4 60c42b9
                                                  src/core/libraries/kernel/memory.cpp:753-816; AnyPS5 PosixMemory.cpp
                                                  :145-249; sharpemu KernelMemoryCompatExports.Mmap.cs:10-42; all GPL)
Each switch: unset, empty or "0" is off (today's path exactly); any other value turns all its items on, unless it names
items (comma-separated): then only those. Read once; one stderr line each: "[bc5] exp 0405: equeue fixes on (items: ...)"
or "... off", "[bc5] exp 0405: mmap shim fixes on (items: ...)" or "... off".
Inputs: the e5 input tree (KytyPlus f266548 + patch 0001 + e4's private units); each input's md5 is asserted. --chain drops
the pin of src/libs/bc5LleAgc.cpp only (for the integrator, who may apply the "gpu" agent's edit of that unit first): all
anchors still assert exactly once and an input that has this edit already is still refused. Every NID this edit and
eq0405.cpp (when it sits beside this script) use is checked against its name with exp 0327's calculator.
The edited bc5LleAgc.cpp calls two functions the edited eventQueue.cpp defines (Bc5EqueueFixes0405,
Bc5KernelAddTimerEvent0405): link the two private objects together.
Prints one line per output: "<relpath> <md5>".
usage: mkeq0405.py <tree root in> <out dir> [--chain]"""
import hashlib
import os
import re
import sys

EQ_REL = "src/kernel/eventQueue.cpp"
LLE_REL = "src/libs/bc5LleAgc.cpp"
PINS = {
    EQ_REL: "c45e6a72c8e419d98059c3477a9373cc",   # base tree's (e4 did not change it)
    LLE_REL: "df12bb2de3e90b8c82a234eedf0babb5",  # e4's unit with exp 0404's switches
}
MARKS = (b"eq0405", b"KYTY_BC5_EQUEUE_FIXES", b"KYTY_BC5_MMAP_SHIM_FIXES", b"Bc5EqueueFixes0405")

SALT = bytes.fromhex("518d64a635ded8c1e6b039b1c3e55230")
CODES = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+-"


def nid(name):
    """exp 0327's calculator (nid0401.py's): SHA-1 of the name and the salt, first 8 bytes little-endian, 64 symbols."""
    digest = int.from_bytes(hashlib.sha1(name.encode() + SALT).digest()[:8], "little")
    return "".join(CODES[(digest >> (58 - i * 6)) & 63] for i in range(10)) + CODES[(digest & 15) * 4]


NIDS = {
    "BPE9s9vQQXo": "mmap",
    "RW-GEfpnsqg": "kevent",
    "57ZK+ODEXWY": "sceKernelAddTimerEvent",
    "YWQFUyXIVdU": "sceKernelDeleteTimerEvent",
    "fzyMKs9kim0": "sceKernelWaitEqueue",
}


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


# =====================================================================================================================
# src/kernel/eventQueue.cpp
# =====================================================================================================================
EQ_INC_OLD = T("#include <cstdlib>\n#include \"common/stringUtils.h\"\n")
EQ_INC_NEW = T("#include <cstdlib>\n#include <cstring> // exp 0401 series e5 (eq0405): std::strcmp, strchr, strncmp, strlen\n"
               "#include \"common/stringUtils.h\"\n")

EQ_BLOCK_ANCHOR = T("class KernelEqueuePrivate {\npublic:\n")
EQ_BLOCK = T(r"""// ---- exp 0401 series e5 (eq0405): exp 0405's equeue fixes, KYTY_BC5_EQUEUE_FIXES ------------------------------------
// Ported in adapted form (no line copied); each source's copyright stays with its authors; GPL-2.0 as this file.
// - "kk02" (exp 0405 R2 KK02 + SK01): a level event, one that is still triggered after its reset function or EV_CLEAR step
//   and has no pending copy, is delivered once per wait instead of into every slot of the caller's array. KytyPS5 dfec14a
//   kernel/eventQueue.cpp:120-127 (`else break;` after the pending pop; GPL-2.0); sharpemu 514d766
//   SharpEmu.Libs/Kernel/KernelEventQueueCompatExports.cs:1940-1960 (each entry once per wait, a level entry queued
//   again; commit 816ec4a; GPL-2.0-or-later). Events that their reset clears (the GPU EOP events of
//   graphics/host_gpu/renderer/sync.cpp, the VideoOut flip events, EV_CLEAR user events) and events with pending copies
//   (EOP, AMPR) are delivered exactly as before. Exp 0188 had the same rule as KYTY_BC5_EQUEUE_LEVEL_ONCE (removed with the
//   unused levers on 2026-11-01); the second title showed no repeated level event then (F247, run M2).
// - "sk03" (R2 SK03): sceKernelWaitEqueue with out == NULL waits as usual and writes no count; today the host EXITs.
//   sharpemu 514d766 KernelEventQueueCompatExports.cs:783-976 (the out checks at 813 and 937; GPL-2.0-or-later).
// - "kk01" (R2 KK01, F246): sceKernelAddTimerEvent(eq, id, usec, udata) (bc5LleAgc.cpp's shim) adds a periodic
//   EVFILT_TIMER (-7) with EV_CLEAR: `data` counts the periods that ran out since the last read, the deadline moves on by
//   whole periods, a re-add first counts the periods already run out. KytyPS5 dfec14a kernel/eventQueue.cpp:142-154,
//   210-234 and 525-539 (GPL-2.0); its eventQueue.h:55 interval_ns field is a side table of the queue here
//   (m_bc5_timer_period_ns, ident -> period), so no header changes. sceKernelDeleteTimerEvent (YWQFUyXIVdU; AnyPS5
//   4f41f4c37 core/libs/prx/libkernel/Equeue/Equeue.cpp:841-843, GPL-2.0-only) is registered with it in bc5LleAgc.cpp.
// - "g1" (R3 G1): kevent honours its timespec (bc5LleAgc.cpp); the switch is read here so that one line names all four.
// KYTY_BC5_EQUEUE_FIXES: unset, empty or "0" is off (today's path exactly); any other value turns all four on, unless it
// names items (comma-separated "kk02", "sk03", "g1", "kk01"): then only those. Read once; one stderr line at the first use
// (bc5LleAgc.cpp's registration reads it at init).
static constexpr uint32_t BC5_EQ_FIX_KK02 = 1u;
static constexpr uint32_t BC5_EQ_FIX_SK03 = 2u;
static constexpr uint32_t BC5_EQ_FIX_G1   = 4u; // bc5LleAgc.cpp's BC5_EQ_FIX_G1_0405 has the same value
static constexpr uint32_t BC5_EQ_FIX_KK01 = 8u; // bc5LleAgc.cpp's BC5_EQ_FIX_KK01_0405 has the same value
static constexpr uint32_t BC5_EQ_FIX_ALL  = BC5_EQ_FIX_KK02 | BC5_EQ_FIX_SK03 | BC5_EQ_FIX_G1 | BC5_EQ_FIX_KK01;

// No header may change: bc5LleAgc.cpp and the CPU test eq0405.cpp declare these themselves.
uint32_t          Bc5EqueueFixesParse0405(const char* value);
uint32_t          Bc5EqueueFixes0405();
int KYTY_SYSV_ABI Bc5KernelAddTimerEvent0405(KernelEqueue eq, int id, KernelUseconds usec, void* udata);

uint32_t Bc5EqueueFixesParse0405(const char* value) {
»if (value == nullptr || value[0] == '\0' || std::strcmp(value, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = value;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 4 && std::strncmp(p, "kk02", n) == 0) {
»»»items |= BC5_EQ_FIX_KK02;
»»} else if (n == 4 && std::strncmp(p, "sk03", n) == 0) {
»»»items |= BC5_EQ_FIX_SK03;
»»} else if (n == 2 && std::strncmp(p, "g1", n) == 0) {
»»»items |= BC5_EQ_FIX_G1;
»»} else if (n == 4 && std::strncmp(p, "kk01", n) == 0) {
»»»items |= BC5_EQ_FIX_KK01;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return items != 0 ? items : BC5_EQ_FIX_ALL;
}

// The items of KYTY_BC5_EQUEUE_FIXES that are on (0: off), read once.
uint32_t Bc5EqueueFixes0405() {
»static const uint32_t items = [] {
»»const uint32_t v = Bc5EqueueFixesParse0405(std::getenv("KYTY_BC5_EQUEUE_FIXES"));
»»if (v == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: equeue fixes off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: equeue fixes on (items:%s%s%s%s)\n", (v & BC5_EQ_FIX_KK02) != 0 ? " kk02" : "",
»»»             (v & BC5_EQ_FIX_SK03) != 0 ? " sk03" : "", (v & BC5_EQ_FIX_G1) != 0 ? " g1" : "",
»»»             (v & BC5_EQ_FIX_KK01) != 0 ? " kk01" : "");
»»}
»»std::fflush(stderr);
»»return v;
»}();
»return items;
}

static bool Bc5EqFix(uint32_t item) {
»return (Bc5EqueueFixes0405() & item) != 0;
}
// ---- end of exp 0401 series e5 (eq0405)'s block ----------------------------------------------------------------------

""")

EQ_PUB_OLD = T("»int  GetTriggeredEvents(KernelEvent* ev, int num);\n")
EQ_PUB_NEW = T("»int  GetTriggeredEvents(KernelEvent* ev, int num);\n"
               "»int  Bc5AddPeriodicTimer(const KernelEqueueEvent& event, uint64_t period_ns); // exp 0401 series e5 (eq0405) kk01\n")

EQ_PRIV_OLD = T("»bool GetNextTimerWaitMicros(uint64_t now_ns, uint32_t* wait_micros) const;\n")
EQ_PRIV_NEW = T("»bool GetNextTimerWaitMicros(uint64_t now_ns, uint32_t* wait_micros) const;\n"
                "»void Bc5TriggerExpiredPeriodicTimers(uint64_t now_ns); // exp 0401 series e5 (eq0405) kk01\n")

EQ_MEMBER_OLD = T("»bool                         m_closed = false;\n};\n")
EQ_MEMBER_NEW = T("""»bool                         m_closed = false;
»// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk01): the period of each periodic EVFILT_TIMER event, by ident
»// (KytyPS5 keeps it in KernelEqueueEvent::interval_ns, a header field). Filled only with the switch on.
»std::unordered_map<uintptr_t, uint64_t> m_bc5_timer_period_ns;
};
""")

EQ_GET_OLD = T("»TriggerExpiredTimers(MonotonicTimeNs());\n\n»int ret = 0;\n")
EQ_GET_NEW = T("»TriggerExpiredTimers(MonotonicTimeNs());\n\n»int ret = 0;\n"
               "»const bool bc5_level_once = Bc5EqFix(BC5_EQ_FIX_KK02); // exp 0401 series e5 (eq0405) kk02\n")

EQ_PENDING_OLD = T("""»»»if (!event.pending_events.empty()) {
»»»»event.event = event.pending_events.front();
»»»»event.pending_events.pop_front();
»»»»event.triggered = true;
»»»}
""")
EQ_PENDING_NEW = T("""»»»if (!event.pending_events.empty()) {
»»»»event.event = event.pending_events.front();
»»»»event.pending_events.pop_front();
»»»»event.triggered = true;
»»»} else if (bc5_level_once) {
»»»»// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk02; KytyPS5 dfec14a eventQueue.cpp:124-127): a level event
»»»»// is delivered again by the next wait, not into the other slots of this one
»»»»break;
»»»}
""")

EQ_TIMERS_OLD = T("void KernelEqueuePrivate::TriggerExpiredTimers(uint64_t now_ns) {\n»for (auto& event: m_events) {\n")
EQ_TIMERS_NEW = T("""void KernelEqueuePrivate::TriggerExpiredTimers(uint64_t now_ns) {
»if (!m_bc5_timer_period_ns.empty() && Bc5EqFix(BC5_EQ_FIX_KK01)) {
»»Bc5TriggerExpiredPeriodicTimers(now_ns); // exp 0401 series e5 (eq0405) kk01: before the one-shot rule below
»}
»for (auto& event: m_events) {
""")

EQ_PERIODIC_ANCHOR = T("bool KernelEqueuePrivate::GetNextTimerWaitMicros(uint64_t now_ns, uint32_t* wait_micros) const {\n")
EQ_PERIODIC = T(r"""// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk01; KytyPS5 dfec14a kernel/eventQueue.cpp:142-154): a periodic
// timer whose deadline has passed adds every period that ran out to `data` (also while it is unread) and moves its
// deadline on by those periods; EV_CLEAR on delivery sets `data` back to 0. Only events in the side table are touched.
void KernelEqueuePrivate::Bc5TriggerExpiredPeriodicTimers(uint64_t now_ns) {
»for (auto& event: m_events) {
»»if (event.event.filter != KERNEL_EVFILT_TIMER || event.deadline_ns == 0 || event.deadline_ns > now_ns) {
»»»continue;
»»}
»»const auto period = m_bc5_timer_period_ns.find(event.event.ident);
»»if (period == m_bc5_timer_period_ns.end() || period->second == 0) {
»»»continue;
»»}
»»const uint64_t count = 1 + (now_ns - event.deadline_ns) / period->second;
»»event.event.data += static_cast<intptr_t>(count);
»»event.deadline_ns = count <= (UINT64_MAX - event.deadline_ns) / period->second
»»                        ? event.deadline_ns + count * period->second
»»                        : UINT64_MAX;
»»event.triggered   = true;
»}
}

""")

EQ_ADDP_ANCHOR = T("int KernelEqueuePrivate::TriggerEvent(uintptr_t ident, int16_t filter, void* trigger_data) {\n")
EQ_ADDP = T(r"""// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk01; KytyPS5 dfec14a kernel/eventQueue.cpp:210-234): AddEvent for a
// periodic timer. A re-add of a live timer first counts the periods that ran out under its old setting, then takes the
// new deadline, period and udata; the period goes to the side table.
int KernelEqueuePrivate::Bc5AddPeriodicTimer(const KernelEqueueEvent& event, uint64_t period_ns) {
»Common::LockGuard lock(m_mutex);

»if (m_closed) {
»»return KERNEL_ERROR_EBADF;
»}
»auto it = std::find_if(m_events.begin(), m_events.end(),
»                       [ident = event.event.ident, filter = event.event.filter](const auto& e) {
»»                       return e.event.ident == ident && e.event.filter == filter;
»                       });
»if (it != m_events.end()) {
»»TriggerExpiredTimers(MonotonicTimeNs());
»»it->deadline_ns = event.deadline_ns;
»»it->event.udata = event.event.udata;
»»for (auto& pending: it->pending_events) {
»»»pending.udata = event.event.udata;
»»}
»} else {
»»m_events.push_back(event);
»}
»m_bc5_timer_period_ns[event.event.ident] = period_ns;

»m_cond_var.Signal();
»return OK;
}

""")

EQ_DEL_OLD = T("»»m_events.erase(it);\n\n»»return OK;\n")
EQ_DEL_NEW = T("""»»if (filter == KERNEL_EVFILT_TIMER && !m_bc5_timer_period_ns.empty()) {
»»»m_bc5_timer_period_ns.erase(ident); // exp 0401 series e5 (eq0405) kk01: the timer's period goes with it
»»}
»»m_events.erase(it);

»»return OK;
""")

EQ_WAIT_OLD = T("»EXIT_NOT_IMPLEMENTED(out == nullptr);\n\n»if (timo == nullptr) {\n")
EQ_WAIT_NEW = T("""»// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES sk03; sharpemu 514d766 KernelEventQueueCompatExports.cs:813, 937):
»// a NULL out waits as usual and gets no count written; off, today's EXIT.
»int bc5_count = 0;
»if (out == nullptr && Bc5EqFix(BC5_EQ_FIX_SK03)) {
»»out = &bc5_count;
»}
»EXIT_NOT_IMPLEMENTED(out == nullptr);

»if (timo == nullptr) {
""")

EQ_ADDT_OLD = T("int KYTY_SYSV_ABI KernelDeleteHRTimerEvent(KernelEqueue eq, int id) {\n"
                "»return KernelDeleteEvent(eq, static_cast<uintptr_t>(id), KERNEL_EVFILT_HRTIMER);\n}\n")
EQ_ADDT_NEW = EQ_ADDT_OLD + T(r"""
// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk01): sceKernelAddTimerEvent's body, called by bc5LleAgc.cpp's shim
// with the switch on. KytyPS5 dfec14a kernel/eventQueue.cpp:525-539 (AddTimerEvent, KernelAddTimerEvent; GPL-2.0) and
// AnyPS5 4f41f4c37 Equeue.cpp:829-839 (GPL-2.0-only): ident id, filter EVFILT_TIMER, EV_ADD | EV_CLEAR, the first deadline
// one period from now. A period of 0 is taken as 1 us (FreeBSD's EVFILT_TIMER takes a 0 period as 1 unit unless
// EV_ONESHOT; TODO(verify): sys/kern/kern_event.c was not read tonight, and the console's rule is not measured).
int KYTY_SYSV_ABI Bc5KernelAddTimerEvent0405(KernelEqueue eq, int id, KernelUseconds usec, void* udata) {
»LOGF("\t timer event add: eq = 0x%016" PRIx64 ", id = %d, usec = %u, udata = 0x%016" PRIx64 "\n",
»     static_cast<uint64_t>(eq), id, static_cast<unsigned>(usec), reinterpret_cast<uint64_t>(udata));

»auto owner = KernelPinEqueue(eq);
»if (!owner) {
»»return KERNEL_ERROR_EBADF;
»}
»const uint64_t period_ns = static_cast<uint64_t>(usec != 0 ? usec : 1u) * 1000u;

»KernelEqueueEvent event {};
»event.deadline_ns  = MonotonicTimeNs() + period_ns;
»event.event.ident  = static_cast<uintptr_t>(id);
»event.event.filter = KERNEL_EVFILT_TIMER;
»event.event.flags  = EV_ADD | EV_CLEAR;
»event.event.fflags = 0;
»event.event.data   = 0;
»event.event.udata  = udata;
»return owner->Bc5AddPeriodicTimer(event, period_ns);
}
""")


def edit_eventqueue(s, eol):
    assert b"#include <cstring>" not in s, "eventQueue.cpp includes <cstring> already: look again"
    s = once(s, EQ_INC_OLD, EQ_INC_NEW, "the includes", eol)
    s = once(s, EQ_GET_OLD, EQ_GET_NEW, "GetTriggeredEvents' start", eol)
    s = once(s, EQ_PENDING_OLD, EQ_PENDING_NEW, "GetTriggeredEvents' pending pop", eol)
    s = once(s, EQ_TIMERS_OLD, EQ_TIMERS_NEW, "TriggerExpiredTimers", eol)
    s = once(s, EQ_PERIODIC_ANCHOR, EQ_PERIODIC + EQ_PERIODIC_ANCHOR, "GetNextTimerWaitMicros (definition)", eol)
    s = once(s, EQ_ADDP_ANCHOR, EQ_ADDP + EQ_ADDP_ANCHOR, "TriggerEvent (definition)", eol)
    s = once(s, EQ_DEL_OLD, EQ_DEL_NEW, "DeleteEvent's erase", eol)
    s = once(s, EQ_WAIT_OLD, EQ_WAIT_NEW, "KernelWaitEqueue's out check", eol)
    s = once(s, EQ_ADDT_OLD, EQ_ADDT_NEW, "KernelDeleteHRTimerEvent", eol)
    s = once(s, EQ_PUB_OLD, EQ_PUB_NEW, "the class's public part", eol)
    s = once(s, EQ_PRIV_OLD, EQ_PRIV_NEW, "the class's private part", eol)
    s = once(s, EQ_MEMBER_OLD, EQ_MEMBER_NEW, "the class's members", eol)
    s = once(s, EQ_BLOCK_ANCHOR, EQ_BLOCK + EQ_BLOCK_ANCHOR, "class KernelEqueuePrivate", eol)
    # the block comes before the class and every use; each switch read is where it should be
    assert s.index(b"static bool Bc5EqFix(uint32_t item)") < s.index(b"class KernelEqueuePrivate {")
    assert s.index(b"class KernelEqueuePrivate {") < s.index(b"Bc5EqFix(BC5_EQ_FIX_KK02)")
    for item, n in ((b"KK02", 1), (b"SK03", 1), (b"KK01", 1)):
        assert s.count(b"Bc5EqFix(BC5_EQ_FIX_" + item + b")") == n, item
    assert s.count(b"m_bc5_timer_period_ns") == 8, s.count(b"m_bc5_timer_period_ns")
    return s


# =====================================================================================================================
# src/libs/bc5LleAgc.cpp: only the libkernel shims (mmap, kevent, sceKernelAddTimerEvent) and AddTimerEvent's
# registration line. The block goes after Ioctl's closing brace, right before the mmap shim's comment.
# =====================================================================================================================
LLE_BLOCK_ANCHOR = T("// mmap(addr, len, prot, flags, fd, offset). The driver maps the gc device at a fixed guest address\n")
LLE_BLOCK = T(r"""// ---- exp 0401 series e5 (eq0405): exp 0405's fixes of the libkernel mmap, kevent and timer shims ------------------
} // namespace Bc5LleKernel (eq0405 closes it here for two declarations and opens it again below)

namespace LibKernel::EventQueue {
// Defined in src/kernel/eventQueue.cpp by the same edit (mkeq0405.py); no header declares them (no header may change), so
// a build that pairs this unit with an unedited eventQueue.cpp.o fails at the link.
uint32_t          Bc5EqueueFixes0405();
int KYTY_SYSV_ABI Bc5KernelAddTimerEvent0405(KernelEqueue eq, int id, KernelUseconds usec, void* udata);
} // namespace LibKernel::EventQueue

namespace Bc5LleKernel {

// The bits of EQ::Bc5EqueueFixes0405() (KYTY_BC5_EQUEUE_FIXES, read and journalled in eventQueue.cpp) used here.
static constexpr uint32_t BC5_EQ_FIX_G1_0405   = 4u; // "g1": kevent honours its timespec (exp 0405 R3 G1)
static constexpr uint32_t BC5_EQ_FIX_KK01_0405 = 8u; // "kk01": sceKernelAddTimerEvent is periodic (exp 0405 R2 KK01)

// KYTY_BC5_MMAP_SHIM_FIXES (exp 0405 R3 M2), the mmap shim below:
// - "hint": an anonymous mapping (fd < 0) whose flags lack MAP_FIXED (0x10) takes its address as a hint, the start of the
//   search for free space, and no longer replaces what is mapped there. shadPS4 60c42b9
//   src/core/libraries/kernel/memory.cpp:753-816 (posix_mmap passes the flags on; its MapMemory replaces only with
//   Fixed), AnyPS5 4f41f4c37 core/libs/prx/libkernel/DirectMemory/PosixMemory.cpp:145-249, sharpemu 514d766
//   KernelMemoryCompatExports.Mmap.cs:10-42 (all GPL; behaviour only, no line copied). A device mapping (fd >= 0) keeps
//   today's path, fixed at its address: Sony's driver maps the gc page at 0xfe0200000 (exp 0011), and its flags were
//   logged as MAP_SHARED without saying whether MAP_FIXED is set (TODO(verify) in a run's "[bc5-gc] mmap" line).
//   MAP_FIXED keeps today's path (it replaces, as POSIX says).
// - "prot": prot 0 stays no-access (today it becomes 0x33), and a mapping without CPU write is not cleared with memset
//   (it would fault; flexible memory is zeroed when mapped, memory.cpp FlexibleMemory::Map's ZeroBacking).
// Unset, empty or "0" is off (today's path exactly); any other value turns both on, unless it names items
// (comma-separated "hint", "prot"): then only those. Read once; one stderr line at the first mmap.
static constexpr uint32_t BC5_MMAP_FIX_HINT = 1u;
static constexpr uint32_t BC5_MMAP_FIX_PROT = 2u;

// Not static: the CPU test eq0405.cpp declares them.
uint32_t Bc5MmapShimFixesParse0405(const char* value);
uint32_t Bc5MmapShimFixes0405();

uint32_t Bc5MmapShimFixesParse0405(const char* value) {
»if (value == nullptr || value[0] == '\0' || std::strcmp(value, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = value;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 4 && std::strncmp(p, "hint", n) == 0) {
»»»items |= BC5_MMAP_FIX_HINT;
»»} else if (n == 4 && std::strncmp(p, "prot", n) == 0) {
»»»items |= BC5_MMAP_FIX_PROT;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return items != 0 ? items : (BC5_MMAP_FIX_HINT | BC5_MMAP_FIX_PROT);
}

// The items of KYTY_BC5_MMAP_SHIM_FIXES that are on (0: off), read once.
uint32_t Bc5MmapShimFixes0405() {
»static const uint32_t items = [] {
»»const uint32_t v = Bc5MmapShimFixesParse0405(std::getenv("KYTY_BC5_MMAP_SHIM_FIXES"));
»»if (v == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: mmap shim fixes off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: mmap shim fixes on (items:%s%s)\n", (v & BC5_MMAP_FIX_HINT) != 0 ? " hint" : "",
»»»             (v & BC5_MMAP_FIX_PROT) != 0 ? " prot" : "");
»»}
»»std::fflush(stderr);
»»return v;
»}();
»return items;
}

// "hint" catcher: an anonymous hint that was not free; the first 8 go to stderr.
static void Bc5MmapHintMoved0405(const void* hint, const void* got, size_t len) {
»static std::atomic<uint32_t> told {0};
»const uint32_t                n = told.fetch_add(1, std::memory_order_relaxed);
»if (n < 8) {
»»std::fprintf(stderr, "[bc5] exp 0405: mmap hint %p len 0x%zx is not free: mapped at %p (#%u)\n", hint, len, got,
»»             static_cast<unsigned>(n + 1));
»»std::fflush(stderr);
»}
}

// "g1" (exp 0405 R3 G1): kevent's wait with a timespec (FreeBSD amd64 struct timespec, LibKernel::KernelTimespec's
// layout). FreeBSD kevent(2): a zero timespec polls; when the time runs out, 0 is returned; a timespec with tv_sec < 0,
// tv_nsec < 0 or tv_nsec >= 1e9 is EINVAL. AnyPS5 4f41f4c37 core/libs/prx/libkernel/Equeue/src/Kqueue.cpp:545-551 and
// 669-678 (GPL-2.0-only; read for the semantics only) does the same and waits without a deadline when tv_sec > INT32_MAX.
// TODO(verify): FreeBSD's sys/kern/kern_event.c (kqueue_scan) was not read tonight (no network). Rounded up to whole
// microseconds; waited in parts of 1000 s because KernelWaitEqueue takes 32-bit microseconds. -1 sets no errno, like this
// shim's other failures. The first 8 calls go to stderr (whether the graphics driver's waits carry a timeout is not known).
static int Bc5KeventTimed0405(EQ::KernelEqueue eq, EQ::KernelEvent* events, int nevents, const void* timeout) {
»static std::atomic<uint32_t> told {0};
»LibKernel::KernelTimespec    ts {};
»std::memcpy(&ts, timeout, sizeof(ts));
»int result = 0;
»if (ts.tv_sec < 0 || ts.tv_nsec < 0 || ts.tv_nsec >= 1000000000) {
»»result = -1;
»} else if (ts.tv_sec > INT32_MAX) {
»»int       out = 0;
»»const int r   = EQ::KernelWaitEqueue(eq, events, nevents, &out, nullptr);
»»result        = r == 0 ? out : -1;
»} else {
»»constexpr uint64_t kPartUs = 1000000000ull;
»»uint64_t           left_us = static_cast<uint64_t>(ts.tv_sec) * 1000000ull +
»»                            (static_cast<uint64_t>(ts.tv_nsec) + 999ull) / 1000ull;
»»for (;;) {
»»»const auto part = static_cast<LibKernel::KernelUseconds>(std::min(left_us, kPartUs));
»»»int        out  = 0;
»»»const int  r    = EQ::KernelWaitEqueue(eq, events, nevents, &out, &part);
»»»if (r == 0) {
»»»»result = out;
»»»»break;
»»»}
»»»if (r != LibKernel::KERNEL_ERROR_ETIMEDOUT) {
»»»»result = -1;
»»»»break;
»»»}
»»»if (left_us <= part) {
»»»»result = 0;
»»»»break;
»»»}
»»»left_us -= part;
»»}
»}
»const uint32_t n = told.fetch_add(1, std::memory_order_relaxed);
»if (n < 8) {
»»std::fprintf(stderr, "[bc5] exp 0405: kevent eq %d timeout {%lld s, %lld ns} nevents %d -> %d (#%u)\n",
»»             static_cast<int>(eq), static_cast<long long>(ts.tv_sec), static_cast<long long>(ts.tv_nsec), nevents,
»»             result, static_cast<unsigned>(n + 1));
»»std::fflush(stderr);
»}
»return result;
}

// "kk01": sceKernelDeleteTimerEvent (YWQFUyXIVdU), registered only with the switch on (AnyPS5 4f41f4c37
// core/libs/prx/libkernel/Equeue/Equeue.cpp:841-843, GPL-2.0-only; adapted).
static KYTY_SYSV_ABI int Bc5DeleteTimerEvent0405(EQ::KernelEqueue eq, int id) {
»PRINT_NAME();
»return EQ::KernelDeleteEvent(eq, static_cast<uintptr_t>(id), EQ::KERNEL_EVFILT_TIMER);
}
// ---- end of exp 0401 series e5 (eq0405)'s block ----------------------------------------------------------------------

""")

LLE_MMAP_OLD = T("""»if (prot == 0) {
»»prot = 0x33;
»}
»void* out = addr;
»int   r   = Mem::KernelMapNamedFlexibleMemory(&out, len, prot,
»                                              addr != nullptr ? Bc5Gc::GUEST_MAP_FIXED : 0,
""")
LLE_MMAP_NEW = T("""»// exp 0401 series e5 (eq0405, KYTY_BC5_MMAP_SHIM_FIXES): "prot" keeps prot 0 no-access; "hint" makes an anonymous
»// mapping's address without MAP_FIXED a hint. Off: today's path.
»const uint32_t bc5_mmap_fixes = Bc5MmapShimFixes0405();
»const bool     bc5_hint_only  = (bc5_mmap_fixes & BC5_MMAP_FIX_HINT) != 0 && fd < 0 &&
»                           (static_cast<uint32_t>(flags) & Bc5Gc::GUEST_MAP_FIXED) == 0;
»if (prot == 0 && (bc5_mmap_fixes & BC5_MMAP_FIX_PROT) == 0) {
»»prot = 0x33;
»}
»void* out = addr;
»int   r   = Mem::KernelMapNamedFlexibleMemory(&out, len, prot,
»                                              (addr != nullptr && !bc5_hint_only) ? Bc5Gc::GUEST_MAP_FIXED : 0,
""")

LLE_MEMSET_OLD = T("»std::memset(out, 0, len);\n»return out;\n}\n")
LLE_MEMSET_NEW = T("""»if (bc5_hint_only && addr != nullptr && out != addr) {
»»Bc5MmapHintMoved0405(addr, out, len); // exp 0401 series e5 (eq0405) "hint": the catcher
»}
»if ((bc5_mmap_fixes & BC5_MMAP_FIX_PROT) == 0 || (prot & 0x02) != 0) { // eq0405 "prot": no memset without CPU write
»»std::memset(out, 0, len);
»}
»return out;
}
""")

LLE_KEVENT_OLD = T("""»»const uint64_t t_eq = Bc5Gc::SoftCp::now_ns();
»»int r   = EQ::KernelWaitEqueue(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents,
""")
LLE_KEVENT_NEW = T("""»»const uint64_t t_eq = Bc5Gc::SoftCp::now_ns();
»»if (timeout != nullptr && (EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_G1_0405) != 0) {
»»»// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES g1): the timespec is honoured; off, today's wait below
»»»const int n = Bc5KeventTimed0405(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents, timeout);
»»»Bc5Gc::Direct::frame_profile_eqwait(static_cast<double>(Bc5Gc::SoftCp::now_ns() - t_eq) / 1e6);
»»»return n;
»»}
»»int r   = EQ::KernelWaitEqueue(eq, reinterpret_cast<EQ::KernelEvent*>(events), nevents,
""")

LLE_TIMER_OLD = T("""»PRINT_NAME();
»return EQ::KernelAddHRTimerEvent(eq, id, static_cast<const LibKernel::KernelTimespec*>(ts),
""")
LLE_TIMER_NEW = T("""»PRINT_NAME();
»if ((EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_KK01_0405) != 0) {
»»// exp 0401 series e5 (eq0405, KYTY_BC5_EQUEUE_FIXES kk01; exp 0405 R2 KK01, F246): the third argument is the period
»»// in microseconds, a 32-bit SceKernelUseconds passed by value (KytyPS5 dfec14a kernel/eventQueue.cpp:537-539, AnyPS5
»»// 4f41f4c37 Equeue.cpp:829; the upper half of the register is not part of it); a periodic EVFILT_TIMER.
»»return EQ::Bc5KernelAddTimerEvent0405(
»»    eq, id, static_cast<LibKernel::KernelUseconds>(reinterpret_cast<uintptr_t>(ts)), udata);
»}
»return EQ::KernelAddHRTimerEvent(eq, id, static_cast<const LibKernel::KernelTimespec*>(ts),
""")

LLE_REG_OLD = T("»LIB_FUNC(\"57ZK+ODEXWY\", AddTimerEvent);\n")
LLE_REG_NEW = T("""»LIB_FUNC("57ZK+ODEXWY", AddTimerEvent);
»if ((EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_KK01_0405) != 0) { // exp 0401 series e5 (eq0405) kk01
»»LIB_FUNC("YWQFUyXIVdU", Bc5DeleteTimerEvent0405); // sceKernelDeleteTimerEvent
»}
""")


def edit_lle(s, eol):
    # the regions this edit owns: they must be today's text (another agent's edit elsewhere in the unit is fine)
    assert s.count(b"static KYTY_SYSV_ABI void* Mmap(") == 1 and s.count(b"static KYTY_SYSV_ABI int Kevent(") == 1
    assert s.count(b"static KYTY_SYSV_ABI int AddTimerEvent(") == 1
    assert b"YWQFUyXIVdU" not in s, "bc5LleAgc.cpp registers sceKernelDeleteTimerEvent already: look again"
    s = once(s, LLE_MMAP_OLD, LLE_MMAP_NEW, "the mmap shim's map call", eol)
    s = once(s, LLE_MEMSET_OLD, LLE_MEMSET_NEW, "the mmap shim's memset", eol)
    s = once(s, LLE_KEVENT_OLD, LLE_KEVENT_NEW, "the kevent shim's wait", eol)
    s = once(s, LLE_TIMER_OLD, LLE_TIMER_NEW, "the AddTimerEvent shim", eol)
    s = once(s, LLE_REG_OLD, LLE_REG_NEW, "AddTimerEvent's registration", eol)
    s = once(s, LLE_BLOCK_ANCHOR, LLE_BLOCK + LLE_BLOCK_ANCHOR, "the mmap shim's comment", eol)
    # every insertion sits inside the libkernel shims' namespace, between Ioctl and the registration's end
    lo = s.index(b"namespace Bc5LleKernel {\n".replace(b"\n", eol))
    hi = s.index(b"} // namespace Bc5LleKernel" + eol)
    for m in re.finditer(rb"eq0405", s):
        assert lo < m.start() < hi, ("an eq0405 line outside the libkernel shims", m.start())
    # the block (helpers, declarations) comes before every use
    first_use = min(s.index(b"bc5_mmap_fixes = Bc5MmapShimFixes0405()"),
                    s.index(b"EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_G1_0405"),
                    s.index(b"EQ::Bc5EqueueFixes0405() & BC5_EQ_FIX_KK01_0405"))
    assert s.index(b"uint32_t Bc5MmapShimFixes0405() {") < first_use
    assert s.index(b"static int Bc5KeventTimed0405(") < s.index(b"const int n = Bc5KeventTimed0405(")
    assert s.count(b"EQ::Bc5EqueueFixes0405()") == 4  # the comment, kevent, AddTimerEvent, the registration
    return s


# =====================================================================================================================
def eol_of(s):
    crlf, lf = s.count(b"\r\n"), s.count(b"\n")
    assert crlf == 0 or crlf == lf, ("mixed line endings", crlf, lf)
    return b"\r\n" if crlf else b"\n"


def once(s, old, new, what, eol):
    old, new = old.replace(b"\n", eol), new.replace(b"\n", eol)
    assert s.count(old) == 1, (what, old[:100], s.count(old))
    return s.replace(old, new)


def balance(b):
    return tuple(b.count(c) for c in b"{}()[]")


def check_nids(script_dir):
    for n, name in NIDS.items():
        assert nid(name) == n, (n, name, nid(name))
    test = os.path.join(script_dir, "eq0405.cpp")
    if os.path.exists(test):
        with open(test, "rb") as f:
            t = f.read().decode("utf-8")
        found = re.findall(r'\{"([A-Za-z0-9+\-]{11})", "([A-Za-z_][A-Za-z0-9_]*)"\}', t)
        assert found, "eq0405.cpp has no {NID, name} pairs"
        for n, name in found:
            assert nid(name) == n, ("eq0405.cpp", n, name, nid(name))


def main():
    args = sys.argv[1:]
    chain = "--chain" in args
    args = [a for a in args if a != "--chain"]
    assert len(args) == 2, __doc__
    root, out = args
    check_nids(os.path.dirname(os.path.abspath(__file__)))
    for rel, fn in ((EQ_REL, edit_eventqueue), (LLE_REL, edit_lle)):
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, f"{rel} has this edit already ({m.decode()})"
        md5 = hashlib.md5(s).hexdigest()
        if not (chain and rel == LLE_REL):
            assert md5 == PINS[rel], f"{rel}: md5 {md5}, not the pinned {PINS[rel]} (--chain drops only {LLE_REL}'s pin)"
        elif md5 != PINS[rel]:
            print(f"mkeq0405: --chain: {rel} md5 {md5} (not the pinned {PINS[rel]}); the anchors decide", file=sys.stderr)
        eol = eol_of(s)
        o = fn(s, eol)
        assert eol_of(o) == eol
        # the inserted text is ASCII (T() encodes it so); the edit keeps each bracket kind balanced against the input's
        # own counts (the units do not balance on their own: #if alternatives, strings)
        delta = tuple(x - y for x, y in zip(balance(o), balance(s)))
        assert delta[0] == delta[1] and delta[2] == delta[3] and delta[4] == delta[5], (rel, "brackets", delta)
        assert len(o.decode("utf-8")) - len(s.decode("utf-8")) == len(o) - len(s), (rel, "non-ASCII text was added")
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(o)
        print(f"{rel} {hashlib.md5(o).hexdigest()}")


if __name__ == "__main__":
    main()
