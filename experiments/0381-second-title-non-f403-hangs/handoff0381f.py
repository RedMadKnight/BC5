#!/usr/bin/env python3
# exp 0381: J1 (F679) after F678, and prefixes on F671/F676/F678. usage: python handoff0381f.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
pre = {
    "F671": "*Source named by F679: the `USER_DATA_0` carried from an acb on the GFX ring (0x11d00860).* ",
    "F676": "*Decided by F679: carried state from the preceding acb.* ",
    "F678": "*Run 10-30 08:14 as J1 (F679): reproduced; 3 of 4 starts from the live saves.* ",
}
for k, v in pre.items():
    s, n = re.subn(r"^(\| %s \| )" % k, lambda m, v=v: m.group(1) + v, s, count=1, flags=re.M)
    assert n == 1, k
row = (
    "| F679 | **The F443/F677 fault's `USER_DATA_0` is carried from the title's async compute: with "
    "`BC5_DIRECT_COMPUTE_RING=-1` an acb runs on the GFX ring, and its last dispatch (0x11d03a3500) sets user data 0 to "
    "0x11d00860. The next dcb opens with 0x909977100 dispatches that inherit it, and they fault at high half 0x0860, that "
    "value's low 16 bits.** J1 (exp 0379 D2's invocation plus `BC5_DIRECT_DISPATCH_JOURNAL=1`, RT on, live saves "
    "377a8d45) reproduced the event at t ≈ 60 s (TCP read faults 0x8608c654000–0x8608c65b000; ring reset succeeded). "
    "The journal holds 5 runs of 0x909977100. The 4 healthy ones sit mid-dcb after the dcb's own dispatches with "
    "`ud0` 0x11; the faulting one is the only run that starts a dcb right after an acb. The host tracker keeps acb and "
    "dcb state apart and shows 0x11. Not journaled: the dcb's table at dword 8 (it cannot name SH 0x240, or the CP "
    "would have loaded it), and the order of the earlier three events. Fix candidate (design): re-emit the dcb "
    "tracker's compute SH state (the CS prefix) in front of a dcb that follows a merged acb, or save and restore "
    "around acbs. Test: 3 starts from the live saves. The 0381 compile check passed (clang 21 + libdrm, 0 warnings, "
    "95/95) after a `-Wsign-conversion` fix in `draw_args_test.cpp`. | experiment 0381 (README §9, "
    "`raw/j1-dispatch-journal.txt`, `dj0381.py`; journal `play-20261030-0814`, devcoredump "
    "`20261030-081544-devcd3.txt` private) | High for the carried value and the order; the table's content inferred |\n"
)
m = re.search(r"^\| F678 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + row + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
