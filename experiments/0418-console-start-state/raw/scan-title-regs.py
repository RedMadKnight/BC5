#!/usr/bin/env python3
"""Static audit: every register a captured command buffer sets. Read-only, on the box. Prints numbers only.
usage: scan-title-regs.py  (run from ~/bc5-data/captures)"""
import glob, json, os, re, struct, sys, collections

SETS = {0x68: "config", 0x69: "context", 0x6a: "context", 0x76: "sh", 0x77: "sh", 0x9b: "sh", 0x79: "uconfig", 0x7a: "uconfig"}
LOADS = {0x5e: "load_uconfig", 0x5f: "load_sh", 0x60: "load_config", 0x61: "load_context", 0x63: "load_sh_index", 0x9f: "load_context_index"}


def walk(w):
    i, n, bad = 0, len(w), 0
    while i < n:
        h = w[i]
        t = h >> 30
        if t == 3:
            if h == 0xffff1000:
                i += 1
                continue
            c = (h >> 16) & 0x3fff
            yield i, (h >> 8) & 0xff, w[i + 1:i + 2 + c]
            i += c + 2
        elif t == 2 or h == 0:
            i += 1
        else:
            yield i, -1, []
            return


def src(path):
    if "ibdump-" in path:
        return path.split("/")[1]
    return "timeout"


def main():
    files = glob.glob("ibdump-*/ib-*.bin") + glob.glob("play-*/gc/ib-timeout-*.bin")
    files = [f for f in files if not f.endswith(".tfring.bin")]
    regs = {}
    ops = collections.Counter()
    loads = collections.Counter()
    wr = collections.Counter()
    per = collections.Counter()
    bad = 0
    for f in files:
        kind = re.search(r"-(dcb|acb|hib|ccb)-", f)
        kind = kind.group(1) if kind else "?"
        s = src(f)
        per[(s, kind)] += 1
        with open(f, "rb") as fp:
            raw = fp.read()
        w = struct.unpack(f"<{len(raw) // 4}I", raw[:len(raw) // 4 * 4])
        for at, op, b in walk(w):
            if op == -1:
                bad += 1
                break
            ops[op] += 1
            if op in SETS and b:
                sp = SETS[op]
                start = b[0] & 0xffff
                for k, v in enumerate(b[1:]):
                    e = regs.setdefault((sp, start + k), {"n": 0, "vals": collections.Counter(), "src": set(), "kind": set()})
                    e["n"] += 1
                    if len(e["vals"]) < 400:
                        e["vals"][v] += 1
                    e["src"].add(s)
                    e["kind"].add(kind)
            elif op in LOADS and len(b) >= 3:
                loads[(LOADS[op], kind, len(b), b[-1] & 0x3fff if op in (0x63, 0x9f) else b[-1] & 0x3fff)] += 1
            elif op == 0x37 and b and ((b[0] >> 8) & 0xf) == 0:
                wr[("write_data", b[1] & 0xffff, kind)] += 1
            elif op == 0x40 and b and (b[0] & 0xf00) == 0:
                wr[("copy_data", b[3] & 0xffff if len(b) > 3 else -1, kind)] += 1
    out = {"files": {f"{a}/{b}": c for (a, b), c in sorted(per.items())}, "bad": bad,
           "ops": {hex(k): v for k, v in ops.most_common()},
           "loads": [[*k, v] for k, v in loads.most_common(30)],
           "reg_writes": [[*k, v] for k, v in wr.most_common(30)],
           "regs": []}
    for (sp, off), e in sorted(regs.items()):
        out["regs"].append({"sp": sp, "off": off, "n": e["n"], "vals": [[v, c] for v, c in e["vals"].most_common(6)],
                            "nvals": len(e["vals"]), "src": sorted(e["src"]), "kind": sorted(e["kind"])})
    json.dump(out, sys.stdout)


main()
