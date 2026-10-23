#!/usr/bin/env python3
# BC5 experiment 0236: the wait-on-address lines parked0236.py leaves unpaired (no later submit of that command
# buffer). For one AMM-trace log: per unpaired command buffer, its waits (count, first/last mono time), whether the
# buffer was ever submitted, with what kinds (reads / AMM-only / other), and the trace's last stamp; so it shows
# whether they are buffers recorded at the end of the run or buffers submitted under another address.
# usage: unpaired0236.py <log>   Read-only.
import re
import sys

SUB = re.compile(rb"submit 0x([0-9a-f]+): (\d+) reads, (\d+) maps")
WAIT = re.compile(rb"wait-on-address cb 0x([0-9a-f]+) addr 0x([0-9a-f]+) value 0x([0-9a-f]+) a3 (\d+)")
MONO = re.compile(rb"^mono ([0-9.]+) ")

pending = {}  # cb -> [(t, addr)]
kinds = {}    # cb -> {"reads", "amm", "other"} ever submitted
addrs = {}    # wait address -> [paired, unpaired]
t = 0.0
with open(sys.argv[1], "rb") as f:
    for line in f:
        ts = MONO.search(line)
        if ts:
            t = float(ts.group(1))
        m = WAIT.search(line)
        if m:
            pending.setdefault(m.group(1), []).append((t, m.group(2)))
            continue
        m = SUB.search(line)
        if m:
            cb, reads, maps = m.group(1), int(m.group(2)), int(m.group(3))
            kinds.setdefault(cb, set()).add("reads" if reads else "amm" if maps else "other")
            for _, a in pending.pop(cb, []):
                addrs.setdefault(a, [0, 0])[0] += 1
for cb, w in pending.items():
    for _, a in w:
        addrs.setdefault(a, [0, 0])[1] += 1
print(f"last stamp {t:.1f}; unpaired buffers {len(pending)}, waits {sum(len(w) for w in pending.values())}")
for cb, w in sorted(pending.items(), key=lambda kv: kv[1][0][0]):
    print(f"  cb 0x{cb.decode()}: {len(w)} waits at {w[0][0]:.1f}-{w[-1][0]:.1f} (end - {t - w[-1][0]:.1f} s), "
          f"submitted before as: {','.join(sorted(kinds.get(cb, []))) or 'never'}")
print("wait addresses: paired / unpaired")
for a, (p, u) in sorted(addrs.items(), key=lambda kv: -sum(kv[1])):
    print(f"  0x{a.decode()}: {p} / {u}")
