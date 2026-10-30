#!/usr/bin/env python3
# BC5 exp 0381: make the committed extracts from the private box reads (walk0381.py's output over the two probe dumps,
# and the read-only greps of the devcoredumps and the 18:08 journal). Keeps only packet offsets, register values, draw
# and dispatch argument dwords and fault addresses; drops the probe's memory dumps (s[..] lines, user-data dumps).
# usage: python extract0381.py <walk-1808.txt> <walk-1625.txt> <reads-rest.txt> <outdir>
import re
import sys
from pathlib import Path

w08, w25, rest, out = (Path(p) for p in sys.argv[1:5])
out.mkdir(parents=True, exist_ok=True)
lines = rest.read_text(errors="replace").splitlines()
sec = {}
cur = None
for ln in lines:
    m = re.match(r"^(==|--) (.*)", ln)
    if m:
        cur = m.group(2).strip()
        sec[cur] = []
    elif cur:
        sec[cur].append(re.sub(r"^\d+:", "", ln))

# 18:08: every indirect draw with its state and its arguments at the timeout (first 5 dwords), the dcb's dispatches
o = ["# exp 0381: dcb #127530 (18:08), the host timeout probe's indirect draws and dispatches (journal private)"]
for ln in sec["1808 probe lines"]:
    ln = ln.replace("timeout probe: ", "")
    m = re.match(r"\s*state before op (24|2c|15) at (\d+): (stages \S+).*?\| (prim \S+).*?(\| gs .*)", ln)
    if m and int(m.group(2)) >= 12000:
        o.append("  state before op %s at %s: %s %s %s" % m.groups())
        continue
    m = re.match(r"op (24|2c) at (\d+): (.*?) args \[(0x[0-9a-f]+)\] ((?:[0-9a-f]{8} ){5})", ln)
    if m:
        o.append("op %s at %s: %s args [%s] %s" % m.groups())
        continue
    if re.match(r"dispatch op 1[56] at|dcb #127530", ln):
        o.append(ln)
(out / "hang-1808-indirect-draws.txt").write_text("\n".join(o) + "\n")

o = ["# exp 0381: dcb #127530 (18:08), walk0381.py summary (opcode counts; IB-only state is unreliable: 252 LOAD_*_INDEX)"]
o += [l for l in w08.read_text().splitlines()[:3]]
(out / "hang-1808-walk-summary.txt").write_text("\n".join(o) + "\n")

# 16:25: the dispatch family's pointer registers, their histogram, the devcoredumps' registers and fault lines
o = ["# exp 0381: dcb #32979 (16:25 start 1), walk0381.py: every DISPATCH with COMPUTE_USER_DATA_3..6 as the IB sets them"]
o += [l for l in w25.read_text().splitlines()[:3]]
hist = {}
for l in w25.read_text().splitlines():
    if "DISPATCH" not in l:
        continue
    k = re.search(r"CUD5=(0x[0-9a-f]+)", l)
    hist[k.group(1) if k else "-"] = hist.get(k.group(1) if k else "-", 0) + 1
    regs = " ".join(re.findall(r"(?:CUD[3-6]|COMPUTE_PGM_LO)=0x[0-9a-f]+", l))
    o.append("%s %s" % (" ".join(l.split()[:4]), regs))
o.append("CUD5 histogram: " + " ".join("%s:%d" % kv for kv in sorted(hist.items())))
(out / "hang-1625-dispatch-pointers.txt").write_text("\n".join(o) + "\n")

o = ["# exp 0381: the 16:25 devcoredumps (private), status registers, header histories, fault lines"]
for k, v in sec.items():
    if k.startswith("20261029-1625"):
        o.append("-- " + k)
        o += [l for l in v if re.match(r"^mm(GRBM|CP_)", l) or re.search(r"Page fault|Faulty page|fault status", l)]
(out / "hang-1625-devcd-regs.txt").write_text("\n".join(o) + "\n")
print("ok")
