#!/usr/bin/env python3
# BC5 experiment 0236: does the async APR path's parked AMM-only submission occur? Reads KytyPlus AMM-trace lines
# (KYTY_BC5_AMM_TRACE=1) from play logs, or exp 0200's filtered APR traces (the same lines without the
# "amm trace: " prefix, other kinds folded into "counts" lines), and counts, per file:
#  - submissions by kind (with reads / AMM-only: maps and no reads / neither) and how many carried a WaitOnAddress
#    recorded on their command buffer since its previous submit;
#  - for AMM-only submissions with a wait: whether the wait was already met when it was recorded
#    (op 4 "reached": now - value < 2^63, the only op the titles use, libAmpr.cpp AprWaitSatisfied);
#  - the wait-on-address lines in all, and those left unpaired (no later submit of that command buffer);
#  - the host's own lines for the path: "waits at command" (async mode: only an AMM-only submission
#    that stopped at a wait on the submitting thread), "resumed submission" (the wait thread's pump
#    finished a buffer), "queued behind a waiting one" (sync mode only), "finished on worker".
# usage: parked0236.py <log> [<log> ...]   Read-only; run with nice/ionice on the box.
import re
import sys

SUB = re.compile(rb"submit 0x([0-9a-f]+): (\d+) reads, (\d+) maps")
WAIT = re.compile(rb"wait-on-address cb 0x([0-9a-f]+) addr 0x([0-9a-f]+) value 0x([0-9a-f]+) a3 (\d+) a4 (\d+) \(now 0x([0-9a-f]+)\)")
MONO = re.compile(rb"^mono ([0-9.]+) ")
COUNTS = re.compile(rb"^counts [0-9.]+ (.*)$")
KEYS = (b"waits at command", b"resumed submission", b"queued behind a waiting one", b"finished on worker")
SIGN = 1 << 63


def met(op, now, value):
    if op == 0:
        return now == value
    if op == 1:
        return now > value
    if op == 2:
        return now < value
    if op == 3:
        return now != value
    if op == 5:
        return (now ^ SIGN) > (value ^ SIGN)
    if op == 6:
        return (now ^ SIGN) < (value ^ SIGN)
    return (now - value) % (1 << 64) < SIGN


for path in sys.argv[1:]:
    pending = {}  # cb -> list of (addr, value, op, now) recorded since its last submit
    n = {"reads": 0, "reads+wait": 0, "amm": 0, "amm+wait": 0, "amm+wait unmet at record": 0, "other": 0, "other+wait": 0}
    keys = {k: 0 for k in KEYS}
    folded = {}  # exp 0200's "counts" lines: kind -> total
    waits = 0
    examples = []
    lines = 0
    t_first = t_last = None  # the trace's "mono <s>" stamps (CLOCK_MONOTONIC)
    with open(path, "rb") as f:
        for line in f:
            if b"amm trace:" not in line and not line.startswith((b"mono ", b"counts ")):
                continue
            lines += 1
            ts = MONO.search(line)
            if ts:
                t_last = float(ts.group(1))
                t_first = t_last if t_first is None else t_first
            m = COUNTS.match(line.rstrip())
            if m:
                for kv in m.group(1).split():
                    k, _, v = kv.partition(b"=")
                    folded[k] = folded.get(k, 0) + int(v or 0)
                continue
            m = WAIT.search(line)
            if m:
                waits += 1
                cb = m.group(1)
                pending.setdefault(cb, []).append((int(m.group(2), 16), int(m.group(3), 16), int(m.group(4)), int(m.group(6), 16)))
                continue
            m = SUB.search(line)
            if m:
                cb, reads, maps = m.group(1), int(m.group(2)), int(m.group(3))
                w = pending.pop(cb, [])
                if reads > 0:
                    n["reads"] += 1
                    n["reads+wait"] += 1 if w else 0
                elif maps > 0:
                    n["amm"] += 1
                    if w:
                        n["amm+wait"] += 1
                        if any(not met(op, now, value) for _, value, op, now in w):
                            n["amm+wait unmet at record"] += 1
                        if len(examples) < 5:
                            examples.append(line.strip()[:160].decode(errors="replace"))
                else:
                    n["other"] += 1
                    n["other+wait"] += 1 if w else 0
                continue
            for k in KEYS:
                if k in line:
                    keys[k] += 1
                    if k in (b"waits at command", b"resumed submission") and len(examples) < 10:
                        examples.append(line.strip()[:160].decode(errors="replace"))
    span = f", mono {t_first:.1f}-{t_last:.1f} ({t_last - t_first:.0f} s)" if t_first is not None else ""
    print(f"== {path}: {lines} trace lines{span}")
    print("   submissions: " + ", ".join(f"{k} {v}" for k, v in n.items()))
    print(f"   wait-on-address lines {waits}, left unpaired {sum(len(v) for v in pending.values())}")
    print("   host lines: " + ", ".join(f'"{k.decode()}" {v}' for k, v in keys.items()))
    if folded:
        print("   folded counts: " + ", ".join(f"{k.decode()} {v}" for k, v in sorted(folded.items())))
    for e in examples:
        print("   e.g. " + e)
