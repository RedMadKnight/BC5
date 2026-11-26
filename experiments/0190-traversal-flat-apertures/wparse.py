#!/usr/bin/env python3
# Parse a umr halt_waves dump (-wa) into per-wave records: PC, EXEC, SGPRs, VGPRs (64 lanes).
import re, sys, json
def parse(path):
    waves = []; cur = None
    for line in open(path, errors="replace"):
        if line.startswith("se") and ".wave" in line:
            cur = {"id": line.strip(), "sgpr": {}, "vgpr": {}}; waves.append(cur); continue
        if cur is None: continue
        for k, v in re.findall(r"ixSQ_WAVE_(\w+): ([0-9a-f]+)", line):
            cur[k] = int(v, 16)
        m = re.match(r">SGPRS\[(\d+)\.\.(\d+)\] = \{ (.*) \}", line)
        if m:
            for i, x in enumerate(m.group(3).split(",")): cur["sgpr"][int(m.group(1)) + i] = int(x, 16)
        m = re.match(r"\s+\[\s*(\d+)\] = \{ (.*) \}", line)
        if m:
            vals = [int(x, 16) for x in m.group(2).split()]
            cur["vgpr"].setdefault(int(m.group(1)), []).extend(vals)
    for w in waves:
        w["pc"] = (w.get("PC_HI", 0) << 32) | w.get("PC_LO", 0)
        w["exec"] = (w.get("EXEC_HI", 0) << 32) | w.get("EXEC_LO", 0)
    return waves
if __name__ == "__main__":
    ws = parse(sys.argv[1])
    print(len(ws), "waves")
    for w in ws[:3]: print(w["id"], hex(w["pc"]), hex(w["exec"]), len(w["vgpr"]), {k: len(v) for k, v in list(w["vgpr"].items())[:3]})
