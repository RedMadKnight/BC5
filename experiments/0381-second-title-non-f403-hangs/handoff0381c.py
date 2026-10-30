#!/usr/bin/env python3
# exp 0381: HANDOFF rows F671-F673 after F670. usage: python handoff0381c.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
rows = (
    "| F671 | **16:25's fault high half is `COMPUTE_USER_DATA_0`, which none of the IB's 890 `DISPATCH_INDIRECT`s sets: the "
    "adjacency build 0x909977100's only vector load builds its descriptor base as {`USER_DATA_0` + a carry of at most 1, "
    "`USER_DATA_3` + header[0x9c] × 32 + 0x80} (the private disassembly on the box, not committed), and `USER_DATA_0` "
    "comes from the `LOAD_SH_REG_INDEX` tables the CP fetches (0x909842dc0 at dword 8, 0x909843280 at 8418, 10 entries "
    "each) or from carried state.** So the 0x860 (and F443's 0xe380) is a wrong `USER_DATA_0`, not `USER_DATA_5` and "
    "not a pointer the shader loaded; Codex's offset counter-model (F670) is narrowed to that register (index × stride "
    "cannot reach it at the title's stride 16; TODO(verify) the V# word-1 layout). Open: the title's table content, a "
    "wrong CP table fetch, or carried state. Next: `BC5_DIRECT_DISPATCH_JOURNAL=1` at start-up (F207's table tracking) "
    "or a timeout-probe dump of the tables. | experiment 0381 (README §6; `walk0381.py`, exp 0380's `binspan0380.py`; "
    "`~/bc5-work/dis-909/dis-909977100.txt` private) | High for the dataflow and the IB; the table's content open |\n"
    "| F672 | **All 15 `DRAW_INDIRECT`s of 18:08's hung host IB carry exp 0057's CP check, verified packet for packet "
    "(polls at base 0x1193ad3900 + data offset and + 4, limits 2^20 vertices and 64 instances, the flag, confirm, "
    "`PFP_SYNC_ME` and a `COND_EXEC` over exactly the draw).** A draw ran only if its polls read ≤ 64 instances, so "
    "either the CP fetched other words than it polled (sub-class B's mismatch on the draw side) or F662's index-like "
    "words came after the polls and these draws are not shown to be the stuck work. | experiment 0381 (README §6, "
    "`raw/hang-1808-drawcheck.txt`; devcoredump `20261029-180813-devcd3.txt` private) | High |\n"
    "| F673 | **The control over the five earlier hangs (10-28 18:15, 23:36; 10-29 09:48, 12:12, 14:04; last 8 MB of each "
    "journal) is weak: none holds the 0x1193ad3900 pass, and their 8 `DRAW_INDIRECT` slots (base 0x11a5c68000) and 4 "
    "multi-draws read sane at the timeout.** The full-journal grep and the `direct.cpp` compile check were refused by "
    "the laptop's classifier; the compile check (`compile0381.sh`) is listed for the morning. | experiment 0381 "
    "(README §6, `raw/control-earlier-hangs-draws.txt`) | Medium |\n"
)
m = re.search(r"^\| F670 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + rows + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
