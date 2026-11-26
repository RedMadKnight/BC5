#!/usr/bin/env python3
# BC5 experiment 0236: which submissions carry a WaitOnAddress, with the host's alias resolution. parked0236.py
# paired waits and submits by the literal address, but the title records commands on the command-buffer object
# (`set-buffer cb X va Y`) and submits AMM buffers by the buffer address Y, which the host resolves to X through
# g_command_buffer_aliases (libAmpr.cpp ResolveCommandBufferStateLocked: X itself if it has queued commands, else
# the alias). This script does the same from the trace:
#  - `set-buffer cb X va Y` of the buffer flavour (not SetBufferIsMapFlavour: a3 != va and a4 == 0xffffffff or ~0)
#    sets alias[Y] = X and clears X's recorded commands (the host's WriteCommandBufferPointers clears them);
#  - `write-address cb X addr A value V` and `wait-on-address cb X addr A value V a3 OP ... (now N)` are recorded on X;
#  - `submit S: R reads, M maps` takes the commands of S if S has any recorded, else of alias[S], and clears them
#    (the title records each use afresh; TODO(verify): a reset the trace does not show would be missed).
# For each submission with a wait it classifies every wait by what the host would see when it runs the buffer in
# record order: met by an earlier write-address of the same buffer to the same address ("self"), met already when
# it was recorded ("now"), or neither ("open": it parks unless the address moved on between record and run).
# It also counts, for each address some buffer waits on, the write-address commands to it by submission kind.
# usage: waits0236.py <log> [<log> ...]   Read-only; run with nice/ionice on the box.
import re
import sys

SETBUF = re.compile(rb"set-buffer cb 0x([0-9a-f]+) va 0x([0-9a-f]+) len 0x[0-9a-f]+ a3 0x([0-9a-f]+) a4 0x([0-9a-f]+)")
WRITE = re.compile(rb"write-address cb 0x([0-9a-f]+) addr 0x([0-9a-f]+) value 0x([0-9a-f]+)")
WAIT = re.compile(rb"wait-on-address cb 0x([0-9a-f]+) addr 0x([0-9a-f]+) value 0x([0-9a-f]+) a3 (\d+) a4 (\d+) \(now 0x([0-9a-f]+)\)")
SUB = re.compile(rb"submit 0x([0-9a-f]+): (\d+) reads, (\d+) maps")
MONO = re.compile(rb"^mono ([0-9.]+) ")
KEYS = (b"waits at command", b"resumed submission")
SIGN = 1 << 63
M64 = (1 << 64) - 1


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
    return ((now - value) & M64) < SIGN


for path in sys.argv[1:]:
    alias = {}  # buffer va -> command-buffer object
    rec = {}    # command-buffer object -> [("w", addr, value) | ("wait", addr, value, op, now)]
    n = {}      # (kind, wait class) -> submissions
    open_examples = []
    keys = {k: 0 for k in KEYS}
    waits_recorded = 0
    wait_addrs = set()
    writers = {}  # (submission kind, address) -> write-address commands run, for addresses some buffer waits on
    t = 0.0
    with open(path, "rb") as f:
        for line in f:
            if b"amm trace:" not in line:
                continue
            ts = MONO.search(line)
            if ts:
                t = float(ts.group(1))
            m = SETBUF.search(line)
            if m:
                va, a3, a4 = int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16)
                if not (a3 != va and a4 in (0xFFFFFFFF, M64)):
                    alias[m.group(2)] = m.group(1)
                    rec.pop(m.group(1), None)
                continue
            m = WRITE.search(line)
            if m:
                rec.setdefault(m.group(1), []).append(("w", int(m.group(2), 16), int(m.group(3), 16)))
                continue
            m = WAIT.search(line)
            if m:
                waits_recorded += 1
                rec.setdefault(m.group(1), []).append(("wait", int(m.group(2), 16), int(m.group(3), 16), int(m.group(4)), int(m.group(6), 16)))
                continue
            m = SUB.search(line)
            if m:
                s, reads, maps = m.group(1), int(m.group(2)), int(m.group(3))
                cb = s if s in rec else alias.get(s, s)
                cmds = rec.pop(cb, [])
                kind = "reads" if reads else "amm-only" if maps else "other"
                cls = []
                written = {}
                for c in cmds:
                    if c[0] == "w":
                        written[c[1]] = c[2]
                        writers[(kind, c[1])] = writers.get((kind, c[1]), 0) + 1
                        continue
                    wait_addrs.add(c[1])
                    _, a, v, op, now = c
                    if a in written and met(op, written[a], v):
                        cls.append("self")
                    elif met(op, now, v):
                        cls.append("now")
                    else:
                        cls.append("open")
                worst = "open" if "open" in cls else "now" if "now" in cls else "self" if cls else "no wait"
                n[(kind, worst)] = n.get((kind, worst), 0) + 1
                if worst == "open" and kind == "amm-only" and len(open_examples) < 5:
                    open_examples.append(f"{t:.3f} submit 0x{s.decode()} (cb 0x{cb.decode()}): {reads} reads, {maps} maps, waits {cls}")
                continue
            for k in KEYS:
                if k in line:
                    keys[k] += 1
    print(f"== {path}: wait-on-address lines {waits_recorded}, buffers still holding waits at the end "
          f"{sum(1 for c in rec.values() if any(x[0] == 'wait' for x in c))}")
    for kind in ("reads", "amm-only", "other"):
        row = ", ".join(f"{w} {n.get((kind, w), 0)}" for w in ("no wait", "self", "now", "open"))
        print(f"   {kind:9s} submissions by their waits: {row}")
    print("   host lines: " + ", ".join(f'"{k.decode()}" {v}' for k, v in keys.items()))
    for a in sorted(wait_addrs):
        row = ", ".join(f"{kind} {writers.get((kind, a), 0)}" for kind in ("reads", "amm-only", "other"))
        print(f"   writes to waited address 0x{a:016x} by submission kind: {row}")
    for e in open_examples:
        print("   open AMM-only e.g. " + e)
