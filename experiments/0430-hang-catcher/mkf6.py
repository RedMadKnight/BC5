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
    for what, n in (("the deployed ho430 block", text.count(old)), ("the keep test", text.count(KEEP_OLD)), ("ChainInSubmit", text.count(CIS_OLD)), ("submit's ChainInSubmit", text.count(SUB_OLD))):
        if n != 1:
            print(f"mkf6: {what} is found {n} times, not once")
            return 1
    if "BC5_DIRECT_XQ_PRECISE" not in new or "keep_cross" not in new or "BC5_DIRECT_XQ_KEEP" not in new or "BC5_DIRECT_XQ_KEEP_ALL" not in new:
        print("mkf6: ho430.cpp has no F5 or no F6")
        return 1
    text = text.replace(old, new).replace(KEEP_OLD, KEEP_NEW).replace(CIS_OLD, CIS_NEW).replace(SUB_OLD, SUB_NEW)
    out = text.encode("utf-8", "surrogateescape")
    open(path, "wb").write(out)
    print(f"mkf6: {BASE_MD5} -> {hashlib.md5(out).hexdigest()[:8]} (ho430 {hashlib.md5(new.encode()).hexdigest()[:8]}, 3 hooks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
