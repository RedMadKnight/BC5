#!/usr/bin/env python3
"""BC5 exp 0412: prof0412.sh's samples taken with PROF_SRC=1 on build g412i (line tables in the main unit), as shares
of the thread's samples by source line. For every sample that is not a wait it prints two tables per phase:
  - "where": the innermost frame that has a line of the main unit (bc5LleAgc.cpp), as function:line, with the leaf
    function the sample was really in (a backend or libc function called from that line);
  - "from": the line of submit_now / chain_submit / sync_mappings (the outermost of them in the stack) the sample
    hangs under, so the big function's own parts can be told apart.
usage: prof0412src.py <prof file> [<load at s> default 104] [<rows> default 14]"""
import collections
import re
import sys

WAITS = ("futex", "syscall_cancel", "epoll", "nanosleep", "poll", "cond_wait", "cond_clockwait", "cond_timedwait", "sem_wait", "__atomic_wait", "atomic_semaphore")
FRAME = re.compile(r"^#\d+\s+0x[0-9a-f]+\s*(.*)$")
SRC = re.compile(r"^\s+(\S+?):(\d+)(?::\d+)?\s*$")
ROOTS = ("submit_now", "chain_submit", "sync_mappings")


def short(fn):
    fn = re.sub(r"\(.*$", "", fn.strip())
    return fn.replace("Libs::Bc5Gc::Direct::", "").replace("bc5::direct::", "d::")[:60] or "?"


def load(path):
    out, cur = [], None
    for ln in open(path, errors="replace"):
        if ln.startswith("== t"):
            m = re.search(r" rel (\d+) ", ln)
            cur = dict(rel=int(m.group(1)), frames=[]) if m else None
            if cur:
                out.append(cur)
            continue
        if cur is None:
            continue
        m = FRAME.match(ln)
        if m:
            cur["frames"].append([m.group(1), None, None])
            continue
        m = SRC.match(ln)
        if m and cur["frames"]:
            cur["frames"][-1][1], cur["frames"][-1][2] = m.group(1).rsplit("/", 1)[-1], int(m.group(2))
    return out


def main():
    path = sys.argv[1]
    load_at = int(sys.argv[2]) if len(sys.argv) > 2 else 104
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 14
    samples = load(path)
    phases = (("scene load", 33, 62), ("save load", load_at, load_at + 28), ("play", load_at + 28, 10 ** 6))
    for name, lo, hi in phases:
        ss = [s for s in samples if lo <= s["rel"] < hi and s["frames"]]
        if not ss:
            continue
        where, under, kinds = collections.Counter(), collections.Counter(), collections.Counter()
        for s in ss:
            fr = s["frames"]
            leaf = fr[0][0]
            if any(w in f[0] for f in fr[:4] for w in WAITS):
                kinds["wait"] += 1
                continue
            if not leaf.strip():
                kinds["guest code"] += 1
                continue
            kinds["host"] += 1
            first = next((f for f in fr if f[1] == "bc5LleAgc.cpp"), None)
            where[(f"{short(first[0])}:{first[2]}" if first else "(no main-unit line)", short(leaf))] += 1
            root = None
            for f in fr:
                if f[1] == "bc5LleAgc.cpp" and any(r in f[0] for r in ROOTS):
                    root = f
            under[f"{short(root[0])}:{root[2]}" if root else "(not under the submit path)"] += 1
        n = len(ss)
        print(f" -- {name}: {n} samples; " + ", ".join(f"{k} {100 * v // n} %" for k, v in kinds.most_common()))
        print("    where (main-unit line <- leaf function), share of all samples:")
        for (w, leaf), c in where.most_common(rows):
            print(f"      {100 * c / n:5.1f} %  {w}  <-  {leaf}")
        print("    from (line inside submit_now / chain_submit / sync_mappings):")
        for w, c in under.most_common(rows):
            print(f"      {100 * c / n:5.1f} %  {w}")


if __name__ == "__main__":
    main()
