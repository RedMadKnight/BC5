#!/usr/bin/env python3
"""BC5 experiment 0430, F5 + F6 in the shared form, 2026-11-17 (after the shared control h430C4 hung at 11:59).
    mkf6.py <tree root>
src/libs/bc5LleAgc.cpp of the shared tree as the 07:10 swap left it (md5 b8afba59) edited in place:
  1. its ho430 block (ho430.b8.cpp beside this script, the deployed text) replaced by ho430.cpp beside this script
     (F5: BC5_DIRECT_XQ_PRECISE; F6: BC5_DIRECT_XQ_KEEP; each on unless "0");
  2. one hook: submit_split's keep test also keeps a wait ho430::keep_cross() names (a satisfied wait on a cross-queue
     label with no writer in flight goes to the GPU, as the console decides it when its queue reaches the packet).
Every anchor must match exactly once, or nothing is written."""
import hashlib
import os
import sys

BASE_MD5 = "b8afba59"
U = "src/libs/bc5LleAgc.cpp"
KEEP_OLD = ("\t\t\t\t\tif (!wait_satisfied(p, op == 0x93) && ring_will_satisfy(p, op == 0x93, job_ring(kind))) {\n"
            "\t\t\t\t\t\tstatic std::atomic<uint64_t> n_kept {0};\n")
CIS_OLD = "struct ChainInSubmit {\n\tChainSlot* s = nullptr;\n"
CIS_NEW = ("// exp 0430 (tag ho430): the title's submit calls (Direct::submit, not the queue consumer's ring buffers) in progress\n"
           "// and begun, for F7's hold record (was a dcb's submit call already running when the acb was taken?)\n"
           "static std::atomic<int>      g_xq_in_submit {0};\n"
           "static std::atomic<uint64_t> g_xq_submit_entries {0};\n"
           "struct XqSubmitCount {\n"
           "\tbool on = false;\n"
           "\texplicit XqSubmitCount(const char* kind) : on(kind != nullptr && std::strcmp(kind, \"ring\") != 0 && std::strncmp(kind, \"acb\", 3) != 0) {\n"
           "\t\tif (!on) return;\n\t\tg_xq_in_submit++;\n\t\tg_xq_submit_entries++;\n\t}\n"
           "\t~XqSubmitCount() {\n\t\tif (on) g_xq_in_submit--;\n\t}\n};\n" + CIS_OLD)
SUB_OLD = "\tconst ChainInSubmit in_submit(chain_cross()); // ADR 0010 section B\n"
SUB_NEW = SUB_OLD + "\tconst XqSubmitCount xq_count(kind); // exp 0430 (tag ho430)\n"
APP_OLD = "static void chain_append(const uint32_t* pre, uint32_t pre_n, const uint32_t* ib, uint32_t n, const char* kind, bool host_built) {\n\tChainSlot& s       = g_chain_tl;\n"
APP_NEW = ("// exp 0430 F9 (BC5_DIRECT_XQ_FLUSH, on unless \"0\"; the top session's root fix, 2026-11-17 19:45): a chain held across the\n"
           "// title's submit calls (ADR 0010 section B) let bc5-ring take an acb before the dcb whose release it waits for (h430Z1:\n"
           "// with BC5_DIRECT_CHAIN=1, F7 held 0 against 330). A chain that carries a GPU memory write another queue could wait on\n"
           "// (RELEASE_MEM or EVENT_WRITE_EOP with data, WRITE_DATA to memory) is submitted at the end of the call, as mode 1 does;\n"
           "// a chain without one is held as before. No label set, nothing learned.\n"
           "static bool f9_on() {\n\tstatic const bool v = [] {\n\t\tconst char* e = std::getenv(\"BC5_DIRECT_XQ_FLUSH\");\n\t\treturn e == nullptr || !(e[0] == '0' && e[1] == 0);\n\t}();\n\treturn v;\n}\n"
           "static bool f10_on() {\n\tstatic const bool v = [] {\n\t\tconst char* e = std::getenv(\"BC5_DIRECT_XQ_TARGET\");\n\t\treturn e == nullptr || !(e[0] == '0' && e[1] == 0);\n\t}();\n\treturn v;\n}\n"
           "static std::atomic<uint64_t> g_f10_owner {0}; // exp 0430 F10: chains their owner flushed at its call's end because an acb waited\n"
           "static void f10_note(std::vector<uint64_t>& out, const uint32_t* ib, uint32_t n) { // exp 0430 F10: the write addresses of ib\n"
           "\tfor (uint32_t q = 0; q < n;) {\n"
           "\t\tconst uint32_t h = ib[q], type = h >> 30u;\n"
           "\t\tuint32_t       len = 1;\n"
           "\t\tif (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }\n"
           "\t\tif (q + len > n) break;\n"
           "\t\tif (type == 3) {\n"
           "\t\t\tconst uint32_t* w = ib + q;\n"
           "\t\t\tconst uint32_t op = (h >> 8u) & 0xffu;\n"
           "\t\t\tauto addr = [w](int lo, int hi) { return (static_cast<uint64_t>(w[lo]) & ~3ull) | (static_cast<uint64_t>(w[hi] & 0xffffu) << 32u); };\n"
           "\t\t\tuint64_t a = 0;\n"
           "\t\t\tif (op == 0x49 && len >= 8 && (w[2] >> 29u) != 0) a = addr(3, 4);\n"
           "\t\t\telse if (op == 0x47 && len >= 6 && (w[3] >> 29u) != 0) a = addr(2, 3);\n"
           "\t\t\telse if (op == 0x37 && len >= 5) { const uint32_t d = (w[1] >> 8u) & 0xfu; if (d == 1 || d == 2 || d == 5) a = addr(2, 3); }\n"
           "\t\t\tif (a != 0 && std::find(out.begin(), out.end(), a) == out.end()) out.push_back(a);\n"
           "\t\t}\n"
           "\t\tq += len;\n"
           "\t}\n"
           "}\n"
           "static thread_local bool     t_f9_write = false; // this thread's open chain carries such a write\n"
           "static std::atomic<uint64_t> g_f9_flushed {0}, g_f9_held {0}, g_f9_ended {0};\n"
           "static bool f9_writes(const uint32_t* ib, uint32_t n) {\n"
           "\tfor (uint32_t q = 0; q < n;) {\n"
           "\t\tconst uint32_t h = ib[q], type = h >> 30u;\n"
           "\t\tuint32_t       len = 1;\n"
           "\t\tif (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }\n"
           "\t\tif (q + len > n) break;\n"
           "\t\tif (type == 3) {\n"
           "\t\t\tconst uint32_t op = (h >> 8u) & 0xffu;\n"
           "\t\t\tif (op == 0x49 && len >= 8 && (ib[q + 2] >> 29u) != 0) return true;\n"
           "\t\t\tif (op == 0x47 && len >= 6 && (ib[q + 3] >> 29u) != 0) return true;\n"
           "\t\t\tif (op == 0x37 && len >= 5) { const uint32_t d = (ib[q + 1] >> 8u) & 0xfu; if (d == 1 || d == 2 || d == 5) return true; }\n"
           "\t\t}\n"
           "\t\tq += len;\n"
           "\t}\n"
           "\treturn false;\n"
           "}\n" + APP_OLD.replace("\tChainSlot& s       = g_chain_tl;\n", "") +
           "\tif (f9_on() && !t_f9_write && ib != nullptr && std::strncmp(kind, \"acb\", 3) != 0 && f9_writes(ib, n)) t_f9_write = true; // exp 0430 F9\n"
           "\tChainSlot& s       = g_chain_tl;\n")
END_OLD = "\t\t\tover = !s.c.segs.empty() && s.hold.empty() && SoftCp::now_ns() >= s.open_ns + chain_hold_ns();\n\t\t\tif (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);\n\t\t}\n\t\tif (over) chain_flush(10);\n"
END_NEW = ("\t\t\tover = !s.c.segs.empty() && s.hold.empty() && SoftCp::now_ns() >= s.open_ns + chain_hold_ns();\n"
           "\t\t\tif (s.c.segs.empty()) t_f9_write = false; // exp 0430 F9: submitted meanwhile (the watchdog, an observe point)\n"
           "\t\t\telse if (f9_on() || f10_on()) {\n"
           "\t\t\t\tg_f9_ended++;\n"
           "\t\t\t\tif (!over && t_f9_write && s.hold.empty()) { over = true; g_f9_flushed++; }\n"
           "\t\t\t\tif (!over && s.f10_wanted && s.hold.empty()) { over = true; g_f10_owner++; } // exp 0430 F10\n"
           "\t\t\t\telse if (!over) g_f9_held++;\n"
           "\t\t\t}\n"
           "\t\t\tif (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);\n\t\t}\n"
           "\t\tif (over) {\n\t\t\tchain_flush(10);\n\t\t\tt_f9_write = false;\n\t\t}\n")
SLOT_OLD = "\tstd::vector<uint64_t>        hold_writes; // ADR 0013: the labels the held chain's segments write\n"
SLOT_NEW = SLOT_OLD + ("\tstd::vector<uint64_t>        f10_writes; // exp 0430 F10: the memory addresses the open chain's packets write (RELEASE_MEM/EOP data, WRITE_DATA)\n"
                       "\tstd::vector<uint64_t>        f10_flight; // exp 0430 F10: the write set of the chain being submitted now (its writes not registered yet)\n"
                       "\tbool                         f10_wanted = false; // exp 0430 F10: an acb waits on one of them; the owner flushes at its call's end\n")
SWAP_OLD = "\t\ts.hold_writes.clear(); // ADR 0013\n"
SWAP_NEW = SWAP_OLD + "\t\ts.f10_flight.swap(s.f10_writes); // exp 0430 F10: in flight until submit_now has registered its writes\n\t\ts.f10_writes.clear();\n\t\ts.f10_wanted = false;\n"
SUBN_OLD = "\tsubmit_now(mine.buf.data(), static_cast<uint32_t>(mine.buf.size()), mine.compute ? \"acb\" : \"dcb\", mine.ring, &mine);\n"
SUBN_NEW = SUBN_OLD + "\t{ // exp 0430 F10: its writes are registered now\n\t\tstd::lock_guard lk(s.mu);\n\t\ts.f10_flight.clear();\n\t}\n"
NOTE_OLD = "\t\t\t\tif (!s.hold.empty()) hold_note_writes(s, ib, n); // ADR 0013\n"
NOTE_NEW = NOTE_OLD + "\t\t\t\tif (f10_on() && !compute) f10_note(s.f10_writes, ib, n); // exp 0430 F10\n"
KEEP_NEW = ("\t\t\t\t\tif ((!wait_satisfied(p, op == 0x93) && ring_will_satisfy(p, op == 0x93, job_ring(kind))) ||\n"
            "\t\t\t\t\t    ho430::keep_cross(p, op == 0x93, label, kind, job_ring(kind), i)) { // exp 0430 (tag ho430): F6\n"
            "\t\t\t\t\t\tstatic std::atomic<uint64_t> n_kept {0};\n")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: mkf6.py <tree root>")
        return 2
    path = os.path.join(sys.argv[1], U)
    data = open(path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()[:8]
    if md5 != BASE_MD5:
        print(f"mkf6: {path} is {md5}, not the base {BASE_MD5}")
        return 1
    text = data.decode("utf-8", "surrogateescape")
    here = os.path.dirname(os.path.abspath(__file__))
    old = open(os.path.join(here, "ho430.b8.cpp"), encoding="utf-8").read()
    new = open(os.path.join(here, "ho430.cpp"), encoding="utf-8").read()
    if hashlib.md5(old.encode()).hexdigest()[:8] != "c7dbe70b":
        print("mkf6: ho430.b8.cpp is not the deployed c7dbe70b")
        return 1
    for what, n in (("the deployed ho430 block", text.count(old)), ("the keep test", text.count(KEEP_OLD)), ("ChainInSubmit", text.count(CIS_OLD)), ("submit's ChainInSubmit", text.count(SUB_OLD)), ("chain_append", text.count(APP_OLD)), ("chain_end's hold test", text.count(END_OLD)), ("ChainSlot's hold_writes", text.count(SLOT_OLD)), ("chain_submit's swap", text.count(SWAP_OLD)), ("chain_append's hold note", text.count(NOTE_OLD)), ("chain_submit's submit_now", text.count(SUBN_OLD))):
        if n != 1:
            print(f"mkf6: {what} is found {n} times, not once")
            return 1
    if "BC5_DIRECT_XQ_PRECISE" not in new or "keep_cross" not in new or "BC5_DIRECT_XQ_KEEP" not in new or "BC5_DIRECT_XQ_KEEP_ALL" not in new:
        print("mkf6: ho430.cpp has no F5 or no F6")
        return 1
    text = text.replace(old, new).replace(KEEP_OLD, KEEP_NEW).replace(CIS_OLD, CIS_NEW).replace(SUB_OLD, SUB_NEW).replace(APP_OLD, APP_NEW).replace(END_OLD, END_NEW).replace(SLOT_OLD, SLOT_NEW).replace(SWAP_OLD, SWAP_NEW).replace(NOTE_OLD, NOTE_NEW).replace(SUBN_OLD, SUBN_NEW)
    out = text.encode("utf-8", "surrogateescape")
    open(path, "wb").write(out)
    print(f"mkf6: {BASE_MD5} -> {hashlib.md5(out).hexdigest()[:8]} (ho430 {hashlib.md5(new.encode()).hexdigest()[:8]}, 9 hooks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
