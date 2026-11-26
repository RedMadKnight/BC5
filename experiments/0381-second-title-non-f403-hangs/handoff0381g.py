#!/usr/bin/env python3
# exp 0381: J2's result as a prefix on F679, the last number of this experiment's range. usage: python handoff0381g.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
pre = (
    "*J2 (10-30 08:40, `BC5_DIRECT_ACB_STATE_RESTORE=1`, private 6415be8f, 5 starts from the live saves, 120 s, RT on): 0 "
    "faults, 0 timeouts, and none of the 5 shows the F679 shape, so all count as no test under the rules written first: "
    "not a pass. The 15,083-dword dcb did not appear; either the restore removes the shape, or the shape varies. The "
    "separating test, the same binary with the switch off, is not run (needs the maintainer's yes). Acbs wrote no "
    "compute register missing from the dcb state in the two starts counted. README §12.* "
)
s, n = re.subn(r"^(\| F679 \| )", lambda m: m.group(1) + pre, s, count=1, flags=re.M)
assert n == 1
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
