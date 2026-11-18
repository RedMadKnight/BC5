#!/usr/bin/env python3
"""BC5 experiment 0430: the hang fix built in (2026-11-18 evening; the maintainer: "Wprowadzamy wszystkie 4 poprawki. Usuń
przełączniki i wybuduj w kod. Przygotuj czysta wersję lean i zwykłego buildu.").
    mkbake0430.py <tree root>
Edits src/libs/bc5LleAgc.cpp of the shared tree at patch ef2ff54f (md5 f574f460) in place:
  1. the deployed ho430 block (ho430.b8.cpp, c7dbe70b: F2/F3/F4 under BC5_DIRECT_XQ_PENDING/ACQUIRE/FENCE) and its
     HO430_SHARED define are replaced by ho430.bake.cpp: F2's pending-writer order through F4's kernel fence, F10 (with
     F11-F13's look), F16 and F18, no switch; the counting is compiled out of the lean build;
  2. the hooks the tested build (p22, unit 178d8890 = mkf6.py on f574f460) put in for F10/F16 (12 of mkf6's 15; F6's keep
     test, F7's submit counter and F18's hold_release counter are not taken, F9's flush is dropped from chain_append/end);
  3. the two call sites of what is gone (given_up: G's event ring; f3_before_submit: F3);
  4. lean only: KYTY_BC5_ANON_SYNC_KICK fixed at its default (exp 0432 Result 10's follow-up), the timeout probe's copies
     and call compiled out.
Every anchor must match exactly once, or nothing is written."""
import hashlib
import os
import sys

BASE = "f574f460"
U = "src/libs/bc5LleAgc.cpp"
HEAD_OLD = "// BC5 experiment 0430 (tag ho430, the shared form): the fix of the second title's GPU hang of 2026-11-16 21:38.\n#define HO430_SHARED 1\n"

APP_OLD = "static void chain_append(const uint32_t* pre, uint32_t pre_n, const uint32_t* ib, uint32_t n, const char* kind, bool host_built) {\n"
APP_NEW = ("// exp 0430 F10: the memory addresses ib's packets write (RELEASE_MEM / EVENT_WRITE_EOP with data, WRITE_DATA to memory)\n"
           "static void f10_note(std::vector<uint64_t>& out, const uint32_t* ib, uint32_t n) {\n"
           "\tfor (uint32_t q = 0; q < n;) {\n"
           "\t\tconst uint32_t h = ib[q], type = h >> 30u;\n"
           "\t\tuint32_t       len = 1;\n"
           "\t\tif (type == 3 || type == 0) {\n\t\t\tconst uint32_t c = (h >> 16u) & 0x3fffu;\n\t\t\tlen = c == 0x3fffu ? 1 : c + 2;\n\t\t}\n"
           "\t\tif (q + len > n) break;\n"
           "\t\tif (type == 3) {\n"
           "\t\t\tconst uint32_t* w  = ib + q;\n"
           "\t\t\tconst uint32_t  op = (h >> 8u) & 0xffu;\n"
           "\t\t\tauto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };\n"
           "\t\t\tuint64_t a = 0;\n"
           "\t\t\tif (op == 0x49 && len >= 8 && (w[2] >> 29u) != 0) a = addr(3, 4);\n"
           "\t\t\telse if (op == 0x47 && len >= 6 && (w[3] >> 29u) != 0) a = addr(2, 3);\n"
           "\t\t\telse if (op == 0x37 && len >= 5) {\n\t\t\t\tconst uint32_t d = (w[1] >> 8u) & 0xfu;\n\t\t\t\tif (d == 1 || d == 2 || d == 5) a = addr(2, 3);\n\t\t\t}\n"
           "\t\t\tif (a != 0 && std::find(out.begin(), out.end(), a) == out.end()) out.push_back(a);\n"
           "\t\t}\n"
           "\t\tq += len;\n"
           "\t}\n"
           "}\n" + APP_OLD)
END_OLD = "\t\t\tover = !s.c.segs.empty() && s.hold.empty() && SoftCp::now_ns() >= s.open_ns + chain_hold_ns();\n"
END_NEW = (END_OLD + "\t\t\tif (!over && !s.c.segs.empty() && s.f10_wanted && s.hold.empty()) over = true; // exp 0430 F10: an acb waits on one of its writes\n")
SLOT_OLD = "\tstd::vector<uint64_t>        hold_writes; // ADR 0013: the labels the held chain's segments write\n"
SLOT_NEW = SLOT_OLD + ("\tstd::vector<uint64_t>        f10_writes; // exp 0430 F10: the memory addresses the open chain's packets write (RELEASE_MEM/EOP data, WRITE_DATA)\n"
                       "\tstd::vector<uint64_t>        f10_flight; // exp 0430 F10: the write set of the chain being submitted now (its writes not registered yet)\n"
                       "\tbool                         f10_wanted = false; // exp 0430 F10: an acb waits on one of them; the owner flushes at its call's end\n"
                       "\tstd::atomic<uint64_t>        f16_done {0}; // exp 0430 F16: bumped when a submit_now of this slot's chain has returned (after its f10_flight is cleared)\n"
                       "\tstd::atomic<int>             f16_phase {0}; // exp 0430 F16: 0 idle, 1 in chain_submit before the device lock (back-pressure), 2 asking for g_dev_mutex, 3 holding it, 4 draining the GPU (wait_jobs)\n")
SWAP_OLD = "\t\ts.hold_writes.clear(); // ADR 0013\n"
SWAP_NEW = SWAP_OLD + "\t\ts.f10_flight.swap(s.f10_writes); // exp 0430 F10: in flight until submit_now has registered its writes\n\t\ts.f10_writes.clear();\n\t\ts.f10_wanted = false;\n"
SUBN_OLD = "\tsubmit_now(mine.buf.data(), static_cast<uint32_t>(mine.buf.size()), mine.compute ? \"acb\" : \"dcb\", mine.ring, &mine);\n"
SUBN_NEW = ("\tChainSlot* const f16_prev = t_f16_slot; // exp 0430 F16\n\tt_f16_slot = &s;\n\ts.f16_phase.store(1);\n" + SUBN_OLD +
            "\t{ // exp 0430 F10: its writes are registered now\n\t\tstd::lock_guard lk(s.mu);\n\t\ts.f10_flight.clear();\n\t}\n"
            "\ts.f16_phase.store(0); // exp 0430 F16: after the clear, so a waiter that saw the flight set sees the bump\n\ts.f16_done.fetch_add(1);\n\tt_f16_slot = f16_prev;\n")
DEVL_OLD = "\tconst uint64_t  fs_ask = fs415_file() != nullptr ? SoftCp::now_ns() : 0; // experiment 0415 (fs415b)\n\tstd::lock_guard lock(g_dev_mutex);\n"
DEVL_NEW = ("\tif (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(2); // exp 0430 F16: past the back-pressure, asking for the device\n" + DEVL_OLD +
            "\tif (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(3); // exp 0430 F16\n")
WJ_OLD = "static void wait_jobs() {\n\tchain_flush(5); // ADR 0010\n"
WJ_NEW = "static void wait_jobs() {\n\tif (t_f16_slot != nullptr) t_f16_slot->f16_phase.store(4); // exp 0430 F16: a submit drains the GPU: no waiter may wait on it\n\tchain_flush(5); // ADR 0010\n"
NOTE_OLD = "\t\t\t\tif (!s.hold.empty()) hold_note_writes(s, ib, n); // ADR 0013\n"
NOTE_NEW = NOTE_OLD + "\t\t\t\tf10_note(s.f10_writes, ib, n); // exp 0430 F10 (graphics and compute chains)\n"
REGD_OLD = "static std::vector<ChainSlot*> g_chains; // the registered (cross) slots, for the watchdog and the observe points\n"
REGD_NEW = REGD_OLD + ("static std::mutex              g_f10_reg_mu; // exp 0430 F10: its own registry of the slots; only chain_register and ~ChainSlot take it, nothing submits under it\n"
                       "static std::vector<ChainSlot*> g_f10_reg;\n"
                       "static thread_local ChainSlot*  t_f16_slot = nullptr; // exp 0430 F16: the slot whose chain this thread's submit_now carries\n")
REGA_OLD = "\tg_chains.push_back(&s);\n\ts.registered = true;\n"
REGA_NEW = REGA_OLD + "\t{ // exp 0430 F10\n\t\tstd::lock_guard rk(g_f10_reg_mu);\n\t\tg_f10_reg.push_back(&s);\n\t}\n"
REGE_OLD = "\tstd::lock_guard lk(g_chains_mu);\n\tstd::erase(g_chains, this);\n"
REGE_NEW = REGE_OLD + "\tstd::lock_guard rk(g_f10_reg_mu); // exp 0430 F10 holds it while it touches this slot\n\tstd::erase(g_f10_reg, this);\n"
AT_OLD = "\t\t\t\t\tho430::at_wait(p, op == 0x93, label, kind, job_ring(kind), ib, num_dwords, i); // exp 0430 (tag ho430): F2 and F3\n"
AT_NEW = "\t\t\t\t\tho430::at_wait(p, op == 0x93, label, kind, job_ring(kind), ib, num_dwords, i); // exp 0430 (tag ho430): F10, F2 + F4\n"
GU_OLD = "\t\t\t\t\tif (!ok) ho430::given_up(broken, label, kind, job_ring(kind), i); // exp 0430 (tag ho430)\n"
F3_OLD = "\tif (sub_ib == ib) ho430::f3_before_submit(ib, num_dwords, opt.drop_offsets, qring, kind, *maps_p); // exp 0430 (tag ho430): F3\n"
KICK_OLD = "\t\tstatic const bool kick = bc5::load_stat::env_num(\"KYTY_BC5_ANON_SYNC_KICK\", 1, 1) != 0;\n"
KICK_NEW = "\t\tstatic const bool kick = BC5_LEAN_OR(true, bc5::load_stat::env_num(\"KYTY_BC5_ANON_SYNC_KICK\", 1, 1) != 0); // exp 0430: a measuring knob, not in lean\n"
TPC_OLD = "\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160\n"
TPC_NEW = "#ifndef BC5_LEAN // exp 0430: the probe is a diagnostic; the lean build has none of it\n" + TPC_OLD + "#endif\n"
TPF_OLD = "static void timeout_probe(const uint32_t* sub_ib, uint32_t sub_n, const char* kind, uint64_t n, const std::vector<uint32_t>* ran, const std::vector<GeProbeSlot>* gep = nullptr) {\n"
TPF_NEW = "[[maybe_unused]] " + TPF_OLD
TPK_OLD = "\t\tif (BC5_DIAG_ENV(\"BC5_DIRECT_TIMEOUT_PROBE\") != nullptr) { if (fl_ib.empty())"
TPK_NEW = "\t\tif (BC5_LEAN_OR(false, BC5_DIAG_ENV(\"BC5_DIRECT_TIMEOUT_PROBE\") != nullptr)) { if (fl_ib.empty())"

EDITS = [("the deployed ho430 block", None, None), ("chain_append", APP_OLD, APP_NEW), ("chain_end's hold test", END_OLD, END_NEW),
         ("ChainSlot's hold_writes", SLOT_OLD, SLOT_NEW), ("chain_submit's swap", SWAP_OLD, SWAP_NEW), ("chain_append's hold note", NOTE_OLD, NOTE_NEW),
         ("chain_submit's submit_now", SUBN_OLD, SUBN_NEW), ("g_chains", REGD_OLD, REGD_NEW), ("chain_register's push", REGA_OLD, REGA_NEW),
         ("~ChainSlot's erase", REGE_OLD, REGE_NEW), ("submit_now's device lock", DEVL_OLD, DEVL_NEW), ("wait_jobs", WJ_OLD, WJ_NEW),
         ("at_wait's call", AT_OLD, AT_NEW), ("given_up's call", GU_OLD, ""), ("f3_before_submit's call", F3_OLD, ""),
         ("the anonymous sync's kick", KICK_OLD, KICK_NEW), ("the timeout probe's call", TPC_OLD, TPC_NEW), ("timeout_probe", TPF_OLD, TPF_NEW),
         ("the timeout probe's copies", TPK_OLD, TPK_NEW)]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: mkbake0430.py <tree root>")
        return 2
    path = os.path.join(sys.argv[1], U)
    data = open(path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()[:8]
    if md5 != BASE:
        print(f"mkbake0430: {path} is {md5}, not {BASE}")
        return 1
    text = data.decode("utf-8", "surrogateescape")
    here = os.path.dirname(os.path.abspath(__file__))
    old = open(os.path.join(here, "ho430.b8.cpp"), encoding="utf-8").read()
    new = open(os.path.join(here, "ho430.bake.cpp"), encoding="utf-8").read()
    if hashlib.md5(old.encode()).hexdigest()[:8] != "c7dbe70b":
        print("mkbake0430: ho430.b8.cpp is not the deployed c7dbe70b")
        return 1
    if "getenv" in new or "BC5_DIRECT_XQ" in new:
        print("mkbake0430: ho430.bake.cpp reads a switch")
        return 1
    for what, a, _ in EDITS:
        n = text.count(HEAD_OLD + old) if a is None else text.count(a)
        if n != 1:
            print(f"mkbake0430: {what} is found {n} times, not once")
            return 1
    text = text.replace(HEAD_OLD + old, new)
    for _, a, b in EDITS[1:]:
        text = text.replace(a, b)
    for w in ("BC5_DIRECT_XQ_", "HO430_SHARED", "f3_before_submit", "given_up(", "keep_cross", "f9_on", "f17_on"):
        if w in text:
            print(f"mkbake0430: {w} is still in the unit")
            return 1
    out = text.encode("utf-8", "surrogateescape")
    open(path, "wb").write(out)
    print(f"mkbake0430: {md5} -> {hashlib.md5(out).hexdigest()[:8]} (ho430 {hashlib.md5(new.encode()).hexdigest()[:8]}, {len(EDITS) - 1} edits)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
