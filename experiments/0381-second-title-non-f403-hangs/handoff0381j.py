#!/usr/bin/env python3
# exp 0381: J3 as rows F683-F684 after F682. usage: python handoff0381j.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rows = (
    "| F683 | **J3 shows the F679 order with job and segment identity, and one direct pair: the title's 12,673-dword buffer "
    "at a job's head right after an acb gave F443 without a prefix (off-3), and no fault with `USER_DATA_0` = 0x11 in its own "
    "emitted prefix (on-5).** Binary 2e69e902, live saves 377a8d45, RT on, 120 s. The buffer is in all 16 starts; mid-chain "
    "(14 starts, either arm) it does not fault. Under the rule written first the verdict is \"Open\": evidence for the "
    "mechanism needs 2 eligible ON starts and 1 eligible OFF start with F443 at one hold, and that is not met at either hold "
    "(default: 1 and 1; 200 µs: ON starts eligible, no OFF F443). F443 overall: OFF 1 of 8, ON 0 of 8. This covers the "
    "start-up workload, one save, one build; nothing about F403 or the 18:08 stall. | experiment 0381 (README §15–§16, "
    "`raw/j3-s1.txt`, `raw/j3-s2.txt`; journals `play-20261030-0947` … `-1021`, devcoredump of 09:57 private) | High for the "
    "counts; the fix rests on one pair |\n"
    "| F684 | **Only this buffer is exposed: the existing CS prefix already carries the graphics queue's compute state in "
    "front of the other first-dispatch offsets (8, 18, 22) with the switch off, and this buffer's table sets the program "
    "first, so `cs_inherit_at` skips it.** So `BC5_DIRECT_ACB_STATE_RESTORE` closes one gap in the CS prefix's trigger at "
    "these targets. J3's rule did not separate those buffers, so its eligible counts at 200 µs say nothing about the switch "
    "(noted after the results; the verdict was not changed for it). A hold of 200 µs did not bring the buffer to a head (seg "
    "1 in 6 of 6). The buffer reached a head once in each arm at the default hold, so the switch's effect on chain position "
    "is not shown. Flip lines: no slowdown shown, none excluded below ~3 %. | experiment 0381 (README §15–§16) | High for "
    "the offsets and prefixes |\n"
)
m = re.search(r"^\| F682 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + rows + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
