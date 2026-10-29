#!/usr/bin/env python3
# BC5 exp 0381: filter the box reads (reads0381.sh's stdout, private) into the committed extracts.
# Keeps: the walker's summary lines, every draw of the 18:08 dcb with its stage state, the dcb's last 400 dwords'
# packets, the 16:25 dispatches whose compute user data hold a low dword in the fault window, the devcoredump register
# lines, the probe/learn lines. Drops any line holding a run of letters that is not a register, packet or tool word
# (a guard against title strings), and reports how many lines it dropped.
# usage: python3 filter0381.py reads0381.out <outdir>
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]).read_text(errors="replace").splitlines()
out = Path(sys.argv[2])
WORD_OK = re.compile(r"^[A-Z0-9_]+$|^(type|op|len|max|size|addr|count|init|offset|dims|event|ctl|src|dst|n|data|stride|"
                     r"indirect|on|off|rc|lines|journal|timeout|probe|dcb|acb|dwords|waits|kept|for|the|GPU|label|writes|"
                     r"dispatches|indirect|largest|grid|groups|at|user|address|not|mapped|HS|VS|PS|GS|ib|walk|host|"
                     r"devcoredumps|status|registers|and|header|histories|only|learned|list|lazy|hint|fault|submit|pass|"
                     r"rewrite|drop|unmapped|cc|mappings|FAILED|TIMEOUT|ms|after|cpu|wait|on|program|ran|arguments|"
                     r"packets|by|opcode|state|from|memory|visible|here|end|UCONFIG|LOAD|REG|INDEX|mm\w+|ib-timeout-\S+|"
                     r"md5|devcd\d*|txt|bin|log|gc|direct|play-\S+|[0-9a-fx.:/+\-=\[\]()|,@#]+)$", re.I)

sections, cur = {}, None
for line in src:
    m = re.match(r"^== (.*)", line)
    if m:
        cur = m.group(1)
        sections[cur] = []
        continue
    if cur:
        sections[cur].append(line)


def clean(lines):
    kept, dropped = [], 0
    for ln in lines:
        words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]*", ln)
        bad = [w for w in words if not WORD_OK.match(w) and not re.match(r"^(0x)?[0-9a-f]+$", w, re.I)
               and not re.match(r"^(CUD\d+|PGM_\w+|COMPUTE_\w+|VGT_\w+|GE_\w+|SET_\w+|DRAW_\w+|DISPATCH_\w+|"
                                r"EVENT_\w+|RELEASE_MEM|ACQUIRE_MEM|NUM_INSTANCES\w*|INDEX_\w+|last_load|"
                                r"LOAD_\w+|NOP|COND_\w+|WRITE_DATA|DMA_DATA|PFP_SYNC_ME|WAIT_\w+|COPY_DATA|"
                                r"CONTEXT_CONTROL|CLEAR_STATE|STRMOUT_\w+|INDIRECT_BUFFER)$", w)]
        if bad:
            dropped += 1
        else:
            kept.append(ln)
    return kept, dropped


out.mkdir(parents=True, exist_ok=True)
report = []
for name, lines in sections.items():
    if name.startswith("walk 00127530"):
        sel = [l for l in lines if re.search(r"DRAW_|packets by opcode|LOAD_\*|UCONFIG state", l)]
        tail = [l for l in lines if re.match(r"^\s*\d+ ", l) and int(l.split()[0]) >= 14945 - 400]
        k, d = clean(sel + ["-- last 400 dwords --"] + tail)
        (out / "walk-1808-draws-and-tail.txt").write_text("\n".join(k) + "\n")
    elif name.startswith("walk 00032979"):
        sel = [l for l in lines if re.search(r"packets by opcode|LOAD_\*|UCONFIG state", l)
               or ("DISPATCH" in l and re.search(r"CUD\d+=0x8c[5-6][0-9a-f]{5}\b", l))]
        allu5 = {}
        for l in lines:
            m = re.search(r"CUD5=(0x[0-9a-f]+)", l)
            if "DISPATCH" in l and m:
                allu5[m.group(1)] = allu5.get(m.group(1), 0) + 1
        sel.append("-- CUD5 values over all dispatches: %s" % " ".join("%s:%d" % kv for kv in sorted(allu5.items())))
        k, d = clean(sel)
        (out / "walk-1625-fault-window-dispatches.txt").write_text("\n".join(k) + "\n")
    else:
        k, d = clean(lines)
        fn = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] + ".txt"
        (out / ("box-" + fn)).write_text("\n".join(k) + "\n")
    report.append("%s: kept %d, dropped %d" % (name, len(k), d))
print("\n".join(report))
