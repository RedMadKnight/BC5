# BC5 hang1954-0401.md: reads one timed-out buffer's timeout-probe block (and exp 0404's fl crumbs block) out of a
# direct.log and prints the 0404-style tables: the draws with their state and argument counts, the dispatches, the
# end-of-pipe label writes with the value read at the timeout (which write of each label completed last), and the waits.
# Two probes that print at the same time (a dcb and an acb timing out together) interleave in the journal; each probe
# walks its buffer in rising offsets, so a line goes to the buffer whose last offset is the nearest below its own.
# Prints offsets, addresses, register values and counts only: V# contents and table data are never printed.
# usage: python -I probe1954.py <direct.log> <submit number> [<other submit number printing at the same time>]
import re
import sys

OFF = re.compile(r"^timeout probe: (?:  state before |dispatch |write |wait )?op ([0-9a-f]+) at (\d+)")


def block(lines, n):
    """(first, last) line index of submit n's probe: from its 'dumped to' line to its '#n' summary line."""
    dump = next(i for i, l in enumerate(lines) if "dumped to" in l and ("-%08d-" % n) in l)
    summ = next(i for i, l in enumerate(lines) if i > dump and re.match(r"timeout probe: \w+ #%d " % n, l))
    return dump, summ


def split(lines, mine, other):
    """The line indices of probe `mine`, separated from the probe `other` printing in the same range."""
    a0, a1 = mine
    b0, b1 = other if other else (-1, -1)
    last = {"a": -1, "b": -1}
    owner_state = None
    out = []
    for i in range(min(a0, b0) if b0 >= 0 else a0, max(a1, b1) + 1):
        act = [k for k, (s, e) in (("a", mine), ("b", other or (-1, -1))) if s <= i <= e]
        if not act:
            continue
        m = OFF.match(lines[i])
        if m:
            q = int(m.group(2))
            cand = [k for k in act if last[k] <= q]
            k = max(cand, key=lambda x: last[x]) if cand else act[0]
            last[k] = q
            if "state before" in lines[i]:
                owner_state = k
        elif lines[i].startswith("timeout probe:   ") and owner_state:
            k = owner_state  # gs user data, s[..] and ud lines follow their state line
        else:
            k = act[0] if len(act) == 1 else None
        if k == "a":
            out.append(i)
    return out


def main(path, n, other):
    lines = open(path, errors="replace").read().split("\n")
    mine = block(lines, n)
    oth = block(lines, other) if other else None
    idx = split(lines, mine, oth)
    print("probe of #%d: journal lines %d..%d, %d lines of its own" % (n, mine[0] + 1, mine[1] + 1, len(idx)))
    print("  " + lines[mine[1]][:200])
    for l in lines:
        if l.startswith("fl crumbs (exp 0404): at the timeout of submit #%d " % n):
            print("  crumbs: " + l.split(": ", 1)[1][:400])
    st = {}
    draws, disp, labels, waits = [], [], {}, []
    for i in idx:
        l = lines[i]
        m = re.match(r"timeout probe:   state before op (\w+) at (\d+): stages (\w+) subgrp (\w+) onchip (\w+) payload (\w+) "
                     r"\| prim (\w+) itype (\w+) ninst (\w+) ge_cntl (\w+) .*\| gs (\w+) es (\w+) ps (\w+) cs (\w+)", l)
        if m:
            st[int(m.group(2))] = m.groups()
            continue
        m = re.match(r"timeout probe: op (24|25|2c|38|27|2d|35) at (\d+): (.*?)\s*(ran|DROPPED)?$", l)
        if m:
            q = int(m.group(2))
            s = st.get(q)
            body = m.group(3)
            a = re.search(r"args \[(0x\w+)\] (\w+) (\w+)", body)
            c = re.search(r"count (\d+) stride (\d+)", body)
            args = ("%d x %d at %s" % (int(a.group(2), 16), int(a.group(3), 16), a.group(1))) if a else body[:60]
            if c:
                args = "count %s stride %s, first %s" % (c.group(1), c.group(2), args)
            draws.append((q, m.group(1), s, args, m.group(4) or ""))
            continue
        m = re.match(r"timeout probe: dispatch op (\w+) at (\d+): program (\w+), groups (\d+) x (\d+) x (\d+)(.*?)\s*(ran|DROPPED)?$", l)
        if m:
            disp.append((int(m.group(2)), m.group(1), m.group(3), "%s x %s x %s" % m.group(4, 5, 6), m.group(8) or ""))
            continue
        m = re.match(r"timeout probe: write op (\w+) at (\d+): (0x\w+) select (\d+) value (0x\w+) .*now (0x\w+|\S+) (ran|DROPPED)", l)
        if m:
            labels.setdefault(m.group(3), []).append((int(m.group(2)), m.group(1), int(m.group(4)), m.group(5), m.group(6), m.group(7)))
            continue
        m = re.match(r"timeout probe: wait op (\w+) at (\d+): label (0x\w+) function (\d+) reference (0x\w+) mask (0x\w+) (\w+); now (\S+) \((.*?)\) (ran|DROPPED)", l)
        if m:
            waits.append(m.groups())
    print("draws (%d):" % len(draws))
    for q, op, s, args, ex in draws:
        if s:
            print("  %5d op %s %-7s stages %s prim %s ge_cntl %s onchip %s subgrp %s es %s ps %s | %s" % (
                q, op, ex, s[2], s[6][-2:], s[9][-4:], s[4], s[3][-2:], s[11][-8:], s[12][-8:], args))
        else:
            print("  %5d op %s %-7s (no state line) | %s" % (q, op, ex, args))
    if disp:
        progs = {}
        for q, op, pg, g, ex in disp:
            progs.setdefault((pg, op), []).append((q, ex))
        print("dispatches (%d), by program:" % len(disp))
        for (pg, op), v in sorted(progs.items(), key=lambda x: x[1][0][0]):
            print("  %s op %s: %d (ran %d), at %d..%d" % (pg, op, len(v), sum(e == "ran" for _, e in v), v[0][0], v[-1][0]))
    print("label writes (%d labels):" % len(labels))
    for addr, w in sorted(labels.items(), key=lambda x: x[1][0][0]):
        now = w[-1][4]
        hits = [q for q, op, sel, v, nw, ex in w if v == now]
        print("  %s: %s | now %s; written by %s" % (addr, " ".join("%d(%s%s)->%s" % (q, op, "" if ex == "ran" else " DROPPED",
              v[-5:]) for q, op, sel, v, nw, ex in w), now[-5:], ",".join(map(str, hits)) or "none of these"))
    print("waits (%d):" % len(waits))
    for op, q, lab, fn, ref, mask, eng, now, met, ex in waits:
        print("  %s op %s at %s: label %s function %s reference %s %s; now %s (%s)" % (ex, op, q, lab, fn, ref, eng, now, met))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else None)
