#!/usr/bin/env python3
# BC5 experiment 0380 (F595): the flight recorder's part A as a private copy of the shared tree's src/libs/bc5LleAgc.cpp,
# made by literal, counted edits only:
# 1. <ctime>, <dirent.h> and <sys/uio.h> next to the direct path's <sys/stat.h>;
# 2. rec0380.inc (the recorder, BC5_0380_REC=1, default off) in front of timeout_probe;
# 3. a call after each of the two timeout_probe calls: on a timeout, and the one-time self-test on a completed dcb.
# Nothing else changes; every exp 0380 fix switch lives in the backend archive, which this build takes as shared.
# usage: python3 mk-rec0380.py <shared bc5LleAgc.cpp> <rec0380.inc> <private bc5LleAgc.cpp>
import sys

src, inc, out = sys.argv[1:4]
t = open(src, encoding="utf-8").read()
rec = open(inc, encoding="utf-8").read()


def rep(old, new):
    global t
    assert t.count(old) == 1, f"anchor found {t.count(old)} times: {old[:80]!r}"
    t = t.replace(old, new)


rep("#include <sys/stat.h>\n", "#include <sys/stat.h>\n#include <ctime>     // experiment 0380: the recorder\n#include <dirent.h>  // experiment 0380\n#include <sys/uio.h> // experiment 0380\n")
rep("// Experiment 0160: BC5_DIRECT_TIMEOUT_PROBE=1 — after a fence timeout, the buffer the GPU ran (prefix",
    rec + "// Experiment 0160: BC5_DIRECT_TIMEOUT_PROBE=1 — after a fence timeout, the buffer the GPU ran (prefix")
old_a = ("\t\t\tif (r.timed_out && !j.ib_copy.empty()) timeout_probe(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), "
         "j.kind, j.n, &j.ran_copy, &j.ge_probe); // experiment 0160\n")
rep(old_a, old_a +
    "\t\t\tif (!j.ib_copy.empty() && BC5_DIAG_ENV(\"BC5_0380_REC\") != nullptr) { // experiment 0380: the flight recorder's part A\n"
    "\t\t\t\tif (r.timed_out) rec0380(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, false);\n"
    "\t\t\t\telse if (r.ok && rec0380_selftest_due(j.kind) && rec0380(j.ib_copy.data(), static_cast<uint32_t>(j.ib_copy.size()), j.kind, j.n, true)) g_rec0380_selftest_done = true;\n"
    "\t\t\t}\n")
old_s = "\tif (r.timed_out) timeout_probe(sub_ib, sub_n, kind, g_submits.load(), &r.executed_offsets); // experiment 0160\n"
rep(old_s, old_s +
    "\tif (BC5_DIAG_ENV(\"BC5_0380_REC\") != nullptr && BC5_DIAG_ENV(\"BC5_DIRECT_TIMEOUT_PROBE\") != nullptr) { // experiment 0380: the flight recorder's part A\n"
    "\t\tif (r.timed_out) rec0380(sub_ib, sub_n, kind, g_submits.load(), false);\n"
    "\t\telse if (r.ok && rec0380_selftest_due(kind) && rec0380(sub_ib, sub_n, kind, g_submits.load(), true)) g_rec0380_selftest_done = true;\n"
    "\t}\n")
assert t.count("rec0380(") == 5, t.count("rec0380(")
open(out, "w", encoding="utf-8", newline="\n").write(t)
print(f"{out} written")
