#!/usr/bin/env python3
# exp 0381: J4 as row F685 after F684, and a pointer on F679. usage: python handoff0381l.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
s, n = re.subn(r"^(\| F679 \| )\*Fix tried in F680, not yet at its target \(F681\)\.\* ", lambda m: m.group(1) + "*Fix supported at its target, with the position forced: F685.* ", s, count=1, flags=re.M)
assert n == 1
row = (
    "| F685 | **With the F679 position forced (`BC5_DIRECT_CHAIN_BREAK_AT=12673`, a diagnostic, in both arms), the title's "
    "12,673-dword buffer at a job's head right after an acb faulted without the restore in 3 of 3 starts (F443, high half "
    "0x860, inherited 0x11d00860, resets ok) and ran clean with `BC5_DIRECT_ACB_STATE_RESTORE=1` in 3 of 3 (`USER_DATA_0` = "
    "0x11 in its own emitted prefix).** Private e72bc317, default hold, live saves 377a8d45, RT on. The rule written first "
    "says Supported. Limits: a forced position, the host's view of order and values (the faults' high half agrees), start-up "
    "only, one save, one build; nothing about play, F403 or the 18:08 stall. Incident: an ssh reset blocked the stop loop, "
    "so on-3 ran 1,919 s, unattended, with a 38 GB journal; `dmesg` shows no amdgpu event in that time, and the stop path is "
    "now bounded. Codex's `final_value` finding (a conditional IB2's write counted as Known) is fixed with a test; it did not "
    "act here, since the writer was a top-level dispatch in all 6 starts. Integration is the maintainer's decision (D19). | "
    "experiment 0381 (README §17–§18, `raw/j4.txt`, `j4check0381.py`; journals `play-20261030-1103` … `-1111` private); "
    "Codex review (J4 follow-up) | High for the counts, on a forced position |\n"
)
m = re.search(r"^\| F684 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + row + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
