#!/usr/bin/env python3
"""BC5 experiment 0412, tag rl412 (README section 62): BC5_DIRECT_RESET_LABELS_ADD=1 (default off). When two jobs time
out in one hang, the label writes kept for the reopen (exp 0401 e11, m11_keep_lost) are no longer overwritten by the
second job's call, which sees the list the first call's forget emptied. rlabels0412.inc holds the rule and
rlabels0412.cpp tests it. Input: the shared main unit (patch 4651d1d3's a81efd2c, or a later fold); one anchor, asserted
once; the script undoes its edit and checks that this gives the input back.
usage: mkrl0412.py <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    assert len(sys.argv) == 3 and sys.argv[1] != sys.argv[2], __doc__
    s = open(sys.argv[1], "rb").read()
    inc = open(os.path.join(HERE, "rlabels0412.inc"), "rb").read()
    assert b"\r" not in s and b"\r" not in inc and b"tag rl412" not in s, "refused: CRLF or already edited"
    inc.decode("ascii")
    old = (b"static void m11_keep_lost() {\n"
           b"\tif (!m11_on(1) && !m11_on(3)) return;\n"
           b"\tstd::lock_guard lk(g_plw_mutex);\n"
           b"\tg_m11_lost     = g_plw;\n"
           b"\tg_m11_lost_for = g_m11_reopens.load() + 1;\n"
           b"}\n")
    new = (inc +
           b"static void m11_keep_lost() {\n"
           b"\tif (!m11_on(1) && !m11_on(3)) return;\n"
           b"\tstd::lock_guard lk(g_plw_mutex);\n"
           b"\tconst size_t rl_before = g_m11_lost.size(); // exp 0412 (tag rl412)\n"
           b"\tconst bool   rl_same   = g_m11_lost_for == g_m11_reopens.load() + 1;\n"
           b"\trl412::keep(g_m11_lost, g_m11_lost_for, g_plw, g_m11_reopens.load() + 1, rl412::on());\n"
           b"\tif (rl_same) journal(\"e11: a second timed-out job before reopen %\" PRIu64 \": %zu label writes were kept, %zu are pending now; kept after this call %zu (BC5_DIRECT_RESET_LABELS_ADD %s; exp 0412, tag rl412)\\n\",\n"
           b"\t                    g_m11_lost_for, rl_before, g_plw.size(), g_m11_lost.size(), rl412::on() ? \"on\" : \"off: the earlier ones are dropped\");\n"
           b"}\n")
    assert s.count(old) == 1, ("the anchor does not occur exactly once", s.count(old))
    out = s.replace(old, new)
    assert out.replace(new, old) == s
    g = out.index(b"namespace rl412 {")
    for need in (b"static void journal(const char* fmt, ...) {", b"static std::vector<PendingLabelWrite> g_m11_lost;", b"g_plw_mutex"):
        assert out.index(need) < g, ("must be defined before the rule", need[:40])
    open(sys.argv[2], "wb").write(out)
    print(f"bc5LleAgc.cpp {hashlib.md5(out).hexdigest()}")


if __name__ == "__main__":
    main()
