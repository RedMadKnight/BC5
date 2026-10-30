#!/usr/bin/env python3
# exp 0381: Codex review REVIEW-06: prefixes on F671/F672 and rows F674-F675 after F673.
# usage: python handoff0381d.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
pre = {
    "F671": "*Qualified by F674 (Codex review REVIEW-06): the host's CS and draw prefixes replay `USER_DATA_0` from the CPU-side tracker, so \"the host never writes it\" is not shown; the emitted IB decides.* ",
    "F672": "*Extended by F675 (Codex review REVIEW-06): a third reading, the words were index-like at the poll, the guard skipped those draws and the stall is elsewhere.* ",
}
for k, v in pre.items():
    s, n = re.subn(r"^(\| %s \| )" % k, lambda m, v=v: m.group(1) + v, s, count=1, flags=re.M)
    assert n == 1, k
rows = (
    "| F674 | **Codex review REVIEW-06: a host replay path for 16:25's `USER_DATA_0`. Both the compute-state prefix "
    "(`BC5_DIRECT_CS_PREFIX=1` in `play-pkg.sh`, SH 0x204–0x3ff, F321) and the full draw prefix (the dcb draws twice) "
    "replay SH registers, `USER_DATA_0` among them, from the tracker, which applies `LOAD_SH_REG_INDEX` tables from the "
    "CPU's view at submit (`full_state.cpp:185-193`).** Codex's run of the real `full_state.cpp` on a synthetic table "
    "emits 0x860 while the later table holds 0x11. On the CP, the dcb's own table load at dword 8 runs after any "
    "prefix. If its table names SH 0x240, the bad value is the table's or the fetch's; if not, a replayed 0x860 is a "
    "host bug. Decided by `head0381.py` over the emitted IB of devcoredump `20261029-162542-devcd1.txt`; the first "
    "guarded read found an emulator running and read nothing. | experiment 0381 (README §7); Codex review REVIEW-06 | "
    "Plausible on the code; unread |\n"
    "| F675 | **Codex review REVIEW-06: F672 has a third reading. The 18:08 slots may have held the index-like words "
    "at the poll, so the guard correctly skipped those draws and the stall came from other work; the verified guards "
    "show that a draw ran only with sane polls, not that any of them ran.** | experiment 0381 (README §7); Codex "
    "review REVIEW-06 | High |\n"
)
m = re.search(r"^\| F673 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + rows + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
