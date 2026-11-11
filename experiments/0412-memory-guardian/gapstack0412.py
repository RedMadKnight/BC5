#!/usr/bin/env python3
"""BC5 exp 0412 (README section 24): the on-CPU time inside the frame gaps, by function.
Joins perfgap0412.sh's samples (perf cpu-clock at 1 kHz, user space, leaf address with symbol and DSO, on
CLOCK_MONOTONIC) with the gap classifier's lines (build g412m, "gap (exp 0412 ... mono <s>: <ms> ms"): a sample belongs
to a gap when its time lies in [end - ms, end]. One sample is one millisecond of user-space CPU time of its thread.
Per phase of the scripted run and per thread: the in-gap samples by group (guest code = an address with no host
symbol in anonymous or memfd memory; the host's groups by function name and DSO), as a share of the gaps' wall-clock
time, and the ten heaviest functions. For contrast one line with the groups outside the gaps.
usage: gapstack0412.py <journal lines with gaps> <perf script .txt.gz> <tid>=<name> [<tid>=<name> ...] [load=<s>]"""
import bisect
import collections
import gzip
import re
import sys

GAP = re.compile(r"gap \(exp 0412, tag gp412\): t ([\d.]+) s mono ([\d.]+): ([\d.]+) ms")
LINE = re.compile(r"^\s*(\d+)\s+([\d.]+):\s+([0-9a-f]+)\s+(.*?)\s+\(([^()]*(?:\([^()]*\))?[^()]*)\)\s*$")
GROUPS = (
    ("host GPU path (bc5LleAgc, backend)", ("Bc5Gc::", "bc5::", "Bc5Lle", "VideoOut")),
    ("host memory (memory.cpp, AMM)", ("LibKernel::Memory", "PhysicalMemory", "VirtualRanges", "FlexibleMemory", "GuestAddressSpace", "Amm", "MapDirect", "MapFlexible", "pm412", "VirtualQuery")),
    ("host libAmpr / APR", ("Ampr", "Apr")),
    ("host file I/O", ("FileSystem", "KernelRead", "KernelPread", "KernelOpen", "KernelLseek", "KernelStat", "File::", "Aio")),
    ("host loader / JIT / patch", ("Jit", "X5", "Loader::", "Patch", "Tls", "RuntimeLinker")),
    ("host fault / signal handlers", ("Signal", "Fault", "Exception", "sigaction", "Sigsegv")),
    ("host threads and sync (libkernel)", ("Pthread", "Mutex", "CondVar", "Semaphore", "EventQueue", "Equeue", "EventFlag", "Usleep", "Nanosleep", "Thread")),
    ("host time / misc libkernel", ("LibKernel::", "KernelGet", "Clock", "ProcessTime")),
)


def group(sym, dso):
    d = dso.rsplit("/", 1)[-1]
    if sym in ("[unknown]", "") or sym.startswith("0x"):
        if "kyty_emulator" in d:
            return "emulator, no symbol"
        if d.startswith("lib") or ".so" in d:
            return "library, no symbol: " + d
        return "guest code"
    if "kyty_emulator" in d:
        for name, pats in GROUPS:
            if any(p in sym for p in pats):
                return name
        return "emulator, other functions"
    if d.startswith("libc.") or d.startswith("libc-") or d.startswith("libm.") or d.startswith("libstdc++") or d.startswith("ld-linux"):
        return "libc / libstdc++ (memcpy, malloc, ...)"
    if "vulkan" in d or "gallium" in d or "libdrm" in d or "LLVM" in d or "mesa" in d.lower():
        return "radv / mesa / libdrm"
    if d == "[vdso]":
        return "vdso (clock reads)"
    return "other library: " + d


def main():
    args = sys.argv[1:]
    load_at = 104.0
    tids = {}
    for a in args[2:]:
        k, _, v = a.partition("=")
        if k == "load":
            load_at = float(v)
        else:
            tids[k] = v
    gaps = []
    for ln in open(args[0], errors="replace"):
        m = GAP.search(ln)
        if m:
            end, ms = float(m.group(2)), float(m.group(3))
            gaps.append((end - ms / 1000, end, float(m.group(1)), ms))
    gaps.sort()
    assert gaps, "no gap lines"
    off = sum(g[1] - g[2] for g in gaps) / len(gaps)  # monotonic minus the journal's clock
    starts = [g[0] for g in gaps]
    phases = (("scene load", 33, 62), ("save load", load_at, load_at + 28), ("play", load_at + 28, 1e9), ("whole run", 0, 1e9))
    # per (thread, phase, in gap?): group counts and symbol counts
    grp = collections.defaultdict(collections.Counter)
    sym = collections.defaultdict(collections.Counter)
    n_all = collections.Counter()
    bad = 0
    with gzip.open(args[1], "rt", errors="replace") as f:
        for ln in f:
            m = LINE.match(ln)
            if not m:
                bad += 1
                continue
            tid, t, s, dso = m.group(1), float(m.group(2)), m.group(4).strip(), m.group(5)
            name = tids.get(tid)
            if name is None:
                continue
            s = re.sub(r"\+0x[0-9a-f]+$", "", s)
            k = bisect.bisect_right(starts, t) - 1
            in_gap = k >= 0 and t <= gaps[k][1]
            tj = t - off
            g = group(s, dso)
            label = s[:90] if g != "guest code" else "(guest code)"
            for pname, lo, hi in phases:
                if lo <= tj < hi:
                    key = (name, pname, in_gap)
                    grp[key][g] += 1
                    n_all[key] += 1
                    if in_gap:
                        sym[key][(label, g)] += 1
    print(f"{len(gaps)} gaps, {sum(g[3] for g in gaps) / 1000:.1f} s; clock offset {off:.3f} s; unparsed perf lines {bad}")
    for pname, lo, hi in phases:
        gs = [g for g in gaps if lo <= g[2] < hi]
        wall = sum(g[3] for g in gs)
        if not gs:
            continue
        print(f"\n== {pname}: {len(gs)} gaps, {wall / 1000:.1f} s of gap time")
        for name in sorted(set(tids.values())):
            key = (name, pname, True)
            n = n_all[key]
            if n == 0:
                continue
            print(f"   {name}: {n} user-space samples in the gaps = {100 * n / wall:.1f} % of the gap time on the CPU in user space")
            print("      by group, % of the gap time: " + "; ".join(f"{g} {100 * c / wall:.1f}" for g, c in grp[key].most_common() if 100 * c / wall >= 0.3))
            print("      the ten heaviest functions, % of the gap time:")
            for (label, g), c in sym[key].most_common(10):
                print(f"        {100 * c / wall:5.1f}  {label}   [{g}]")
            ko = (name, pname, False)
            if n_all[ko]:
                print("      outside the gaps, % of this thread's user-space samples: " + "; ".join(f"{g} {100 * c / n_all[ko]:.0f}" for g, c in grp[ko].most_common(5)))


if __name__ == "__main__":
    main()
