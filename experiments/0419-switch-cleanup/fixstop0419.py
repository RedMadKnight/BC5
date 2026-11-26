#!/usr/bin/env python3
"""BC5 experiment 0419 (LESSONS R54, found by exp 0418 on 2026-11-13): the runners' kernel stopper matched a frame of
a kernel backtrace. Their test `grep -qi "amdgpu.*\\(timeout\\|reset\\|fault\\)"` on the new dmesg lines also matches
"amdgpu_gem_fault+0x95/0x100", a stack frame of an out-of-memory backtrace, and a run that the OOM killer touched was
reported as a GPU hang although there was no ring timeout, no reset and no fault record.
After this script the stopper first drops backtrace frames (name+0xOFF/0xLEN, exp 0418's kern0418.sh gpu_errors())
and then looks for timeout / reset / fault in the remaining amdgpu lines. Every file given is edited in place; a file
without the old test is left alone and named.
usage: fixstop0419.py <runner script> [...]"""
import sys

OLD = '| grep -qi "amdgpu.*\\(timeout\\|reset\\|fault\\)"'
NEW = ("| grep -i amdgpu | grep -v -E '[A-Za-z_][A-Za-z0-9_.]*\\+0x[0-9a-f]+/0x[0-9a-f]+' "
       '| grep -qi "timeout\\|reset\\|fault"')
for p in sys.argv[1:]:
    s = open(p, encoding="utf-8", newline="").read()
    n = s.count(OLD)
    if n == 0:
        print("%s: no old test (already fixed: %s)" % (p, "yes" if NEW in s else "no"))
        continue
    open(p, "w", encoding="utf-8", newline="").write(s.replace(OLD, NEW))
    print("%s: %d stopper line(s) fixed" % (p, n))
