#!/usr/bin/env python3
"""BC5 experiment 0385: the zpass catcher's records, per lake writer. Standard library only.
usage: zp0385.py <zpass.dat> <zpass.dat.meta>
A record is 16 bytes per RB: begin at +0, end at +8, each with bit 63 set once written (radv_query.c:215-225, Mesa ab2374a).
Writers are keyed by pixel shader and their order within the job. For each key: how many frames ran it, how many of those
the CP skipped (begin never written, so the COND_EXEC or predication around it was not taken) and the passed samples at the
10th, 50th and 90th percentile. A writer whose count falls in some frames is the one that loses the lake's cells.
TODO(verify): gfx1013's RB count; records hold 256 bytes, so unused RBs stay zero and are ignored."""
import struct, sys

RB = 16
VALID = 1 << 63


def record(raw):
    """(passed samples, begin written, end written)."""
    total, begins, ends = 0, 0, 0
    for r in range(RB):
        b, e = struct.unpack_from("<QQ", raw, r * 16)
        begins += 1 if b & VALID else 0
        ends += 1 if e & VALID else 0
        if b & VALID and e & VALID:
            total += (e & ~VALID) - (b & ~VALID)
    return total, begins > 0, ends > 0


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def summarise(data, meta):
    jobs, keys = {}, {}
    for line in meta.splitlines():
        rec, job, ps, op, in_cond, _ms = line.split()
        rec = int(rec)
        raw = data[rec * 256:(rec + 1) * 256]
        if len(raw) != 256:
            continue
        passed, began, ended = record(raw)
        n = jobs.setdefault(job, 0)
        jobs[job] = n + 1
        k = (ps, n, op, in_cond)
        keys.setdefault(k, []).append((passed, began, ended))
    out = [f"# {len(jobs)} jobs with writers, {sum(jobs.values())} records, {len(keys)} writers by shader and order"]
    for k in sorted(keys, key=lambda x: x[1]):
        v = keys[k]
        got = [p for p, b, e in v if b and e]
        skipped = sum(1 for p, b, e in v if not b)
        line = f"{k[1]:4d} ps {k[0]} op {k[2]} in_cond {k[3]} frames {len(v)} skipped {skipped}"
        if got:
            line += f" passed {pct(got, 0.1)} {pct(got, 0.5)} {pct(got, 0.9)}"
        out.append(line)
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(newline=chr(10))
    with open(sys.argv[1], "rb") as f:
        data = f.read()
    with open(sys.argv[2], encoding="ascii") as f:
        meta = f.read()
    sys.stdout.write(summarise(data, meta))
