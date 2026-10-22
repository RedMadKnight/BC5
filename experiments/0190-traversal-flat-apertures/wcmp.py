#!/usr/bin/env python3
# Compare two wave dumps: same wave slots -> identical PC / SGPRs / VGPRs?
import sys; sys.path.insert(0, "/home/kjaniszewski/bc5-work/exp0190")
from wparse import parse
a = {w["id"]: w for w in parse(sys.argv[1])}; b = {w["id"]: w for w in parse(sys.argv[2])}
common = sorted(set(a) & set(b)); same_pc = same_s = same_v = 0
for k in common:
    x, y = a[k], b[k]
    same_pc += x["pc"] == y["pc"]; same_s += x["sgpr"] == y["sgpr"]; same_v += x["vgpr"] == y["vgpr"]
print(sys.argv[1].split("/")[-1], sys.argv[2].split("/")[-1], "waves", len(a), len(b), "common", len(common), "same PC", same_pc, "same SGPRs", same_s, "same VGPRs", same_v)
