#!/usr/bin/env python3
# exp 0381: J2's prefix on F679 becomes rows F680-F681; README §12's corrections and §13.
# usage: python handoff0381h.py docs/HANDOFF.md <README.md> <readme-s13.md>
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
s, n = re.subn(r"^(\| F679 \| )\*J2 \(10-30 08:40.*?README §12\.\* ", lambda m: m.group(1) + "*Fix tried in F680, not yet at its target (F681).* ", s, count=1, flags=re.M)
assert n == 1
rows = (
    "| F680 | **`BC5_DIRECT_ACB_STATE_RESTORE=1` (private 6415be8f, J1's binary plus the switch) ran 5 starts from the live "
    "saves, 120 s each, RT on: 0 faults and 0 timeouts, but not a pass: no start put an acb right in front of the F679 "
    "buffer, so all count as no test under the rules written first.** The restore was active where counted (J2-1, J2-2: 40 "
    "registers, 58 dwords, ~11,000 dispatching buffers), and acbs wrote no compute register missing from the dcb state. "
    "Flip-line rates show no slowdown (a rough count). | experiment 0381 (README §11–§12; journals `play-20261030-0840`, "
    "`-0843`, `-0846`, `-0849`, `-0851` private) | High for the counts |\n"
    "| F681 | **The dispatch journal's `dcb N dwords` and `at` describe host chains (ADR 0010), not title buffers, so the "
    "F679 buffer never left: in all 5 J2 starts the step between the second BVH burst's two 0x909977100 runs is 32,586 "
    "dwords against J1's 32,528 across its chain break, exactly the restore's 58 dwords, while the first burst's step is "
    "unchanged (29,190).** The title's buffer stands at the same stream position with the restore in front of it, mid-"
    "chain. So J2 differs from J1 in the chain boundary, not in what the title builds (exp 0381's first reading, that the "
    "restore removes the shape, is withdrawn), and no acb could land there: J2 did not test the fix. Inferred from offsets; "
    "no journal line names a segment. Why the chain held is open: chains end on host timing, and the restore's path does "
    "not touch that directly, so timing or an indirect effect of the switch remain. Next: the chain statistics and timing "
    "lines of J1, J2 and the earlier starts, then J3a (switch off) and J3b (switch on with the boundary forced), rules in "
    "the README. | experiment 0381 (README §13, `raw/shape-j1-j2.txt`, `shape0381.py`; `bc5LleAgc.cpp` `submit_now`, "
    "`chain_append`) | High for the offsets; the cause of the chain difference open |\n"
)
m = re.search(r"^\| F679 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + rows + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")

r = Path(sys.argv[2])
t = r.read_text(encoding="utf-8")
a = "5 warnings in the host unit's\nlink step, the older ones, none in the new lines."
assert t.count(a) == 1
t = t.replace(a, "5 compiler warnings in the host\nunit, the older ones, none in the new lines.")
a = "**What the runs do show.** In J1 the second burst"
assert t.count(a) == 1
t = t.replace(a, "*Corrected by §13: the buffer below did not vanish. The journal's `dcb N dwords` and `at` describe host chains, so "
              "readings 1 and 2 and their odds are withdrawn.*\n\n" + a)
t = t.rstrip("\n") + "\n" + Path(sys.argv[3]).read_text(encoding="utf-8")
r.write_text(t, encoding="utf-8", newline="\n")
print("ok")
