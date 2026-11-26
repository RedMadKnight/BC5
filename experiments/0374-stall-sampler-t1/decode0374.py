#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
# exp 0374: decode the hang's status registers and packet headers with the repo's own tables (laptop, no box):
# field names from Mesa's gfx10.json and opcode names from pm4-opcodes.tsv / extra-opcodes.tsv, both vendored in
# tools/bc5-agc/regdb/ (see its NOTICE.md). The values are the ones in raw/extract.txt.
# Usage, from the repo root: python experiments/0374-stall-sampler-t1/decode0374.py > experiments/0374-stall-sampler-t1/raw/decode.txt
import json
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "bc5-agc", "regdb")
db = json.load(open(os.path.join(ROOT, "gfx10.json")))
maps = {m["name"]: m for m in db["register_mappings"]}
ops = {}
for f in ("pm4-opcodes.tsv", "extra-opcodes.tsv"):
    for line in open(os.path.join(ROOT, f)):
        p = line.split()
        if len(p) >= 2 and p[0].startswith("0x"):
            ops.setdefault(int(p[0], 16), p[1])


def fields(name, v):
    m = maps.get(name)
    if not m or "type_ref" not in m:
        return "(no field table)"
    out = []
    for f in db["register_types"][m["type_ref"]]["fields"]:
        lo, hi = f["bits"]
        x = (v >> lo) & ((1 << (hi - lo + 1)) - 1)
        if x:
            out.append(f["name"] + ("=%d" % x if hi > lo else ""))
    return " ".join(out) or "-"


def header(h):
    # PM4 type-3 header: bits 31:30 type, 29:16 count, 15:8 opcode (tools/bc5-agc, docs/formats/agc.md)
    if h >> 30 != 3:
        return "type %d" % (h >> 30)
    op = (h >> 8) & 0xFF
    return "%s count %d" % (ops.get(op, "opcode 0x%02x (not in the repo's tables)" % op), (h >> 16) & 0x3FFF)


STATES = [
    ("T1 hang 2026-10-29 06:34 (devcd 20261029-063423-devcd1, the sampler's stall samples agree)", [
        ("GRBM_STATUS", 0xE5F100AC), ("GRBM_STATUS2", 0x50000008), ("GRBM_STATUS3", 0x00002000),
        ("GRBM_STATUS_SE0", 0x08000000), ("GRBM_STATUS_SE1", 0xEC400000)]),
    ("the forced scan just before it (06:34:21.305, mono 25059.726)", [("GRBM_STATUS", 0xE7F141AC)]),
    ("F403 class, F506's dump 20261028-233612-devcd1 (F490's state)", [
        ("GRBM_STATUS", 0xA0407028), ("GRBM_STATUS2", 0x52000008), ("GRBM_STATUS_SE0", 0x0A000016),
        ("GRBM_STATUS_SE1", 0x0A000016)]),
]
for title, regs in STATES:
    print("## " + title)
    for n, v in regs:
        print("%-16s 0x%08x  %s" % (n, v, fields(n, v)))
print("## T1 hang: gfx me0 pipe0 queue0 header histories (devcoredump order; the sampler's regs-1..5 identical)")
for n, hs in (("PFP", (0xC0065800, 0xC0065800, 0xFFFF1000, 0xFFFF1000, 0xFFFF1000, 0xC0053C00, 0xFFFF1000, 0xFFFF1000)),
              ("ME", (0xC0187600, 0xC0005300, 0xC0013500, 0xC0017A00, 0xC01E7600, 0xC0187600, 0xC0016400, 0xC0016300))):
    for h in hs:
        print("%-3s 0x%08x  %s" % (n, h, header(h)))
