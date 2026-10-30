#!/usr/bin/env python3
# exp 0381: Codex review REVIEW-04 in HANDOFF: prefixes on F660-F664 and the row F670 after F669.
# usage: python handoff0381b.py docs/HANDOFF.md
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding="utf-8")
pre = {
    "F660": "*Narrowed by F670 (Codex review REVIEW-04): a distinct graphics/front-end stall signature; deadlock, \"no movement\" and \"no memory traffic\" are not shown by five register samples.* ",
    "F661": "*Limited by F670 (Codex review REVIEW-04): a signature tag for an event the stall clock caught, not a validated detector; 0/40 on the selection set gives no false-positive rate.* ",
    "F662": "*Corrected by F670 (Codex review REVIEW-04): 13 of 15 over 64 instances, 12 index-like by `draw_args::index_like` (14127 is over the limit only); dword 12640 is the first slot with suspicious later contents, not a shown fetch.* ",
    "F663": "*Narrowed by F670 (Codex review REVIEW-04): the low dwords fit the family, but offset arithmetic fits as well (0x118c65c000 + 0x84f00000000); the high dword's source and \"no real-address fault first\" are not shown.* ",
    "F664": "*Narrowed by F670: one later job is shown waiting on the killed job's label, not every one.* ",
}
for k, v in pre.items():
    s, n = re.subn(r"^(\| %s \| )" % k, lambda m, v=v: m.group(1) + v, s, count=1, flags=re.M)
    assert n == 1, k
row = (
    "| F670 | **Codex review REVIEW-04 of exp 0381, accepted: five claims narrowed (F660 a signature, not a shown "
    "deadlock; F661 a tag, not a detector; F662's two definitions, 13 over 64 instances against 12 index-like, and no "
    "named fetch; F663's high-dword source open, with offset arithmetic as the counter-model and the rate-limited first "
    "fault; F664 one waiting job), and `drawcheck0381.py` now verifies the emitted check packet for packet per draw "
    "(poll addresses, write target, confirm, `PFP_SYNC_ME`, `COND_EXEC` flag and range) instead of counting nearby "
    "packets.** `test_drawcheck0381.py`: 6 cases pass, Codex's counterexample among them. The strongest control for "
    "F662 is a healthy completed job of the same pass (F668's journal). | experiment 0381 (README §5); Codex review "
    "REVIEW-04 (the maintainer's `Documents/ChatGPT/BC5/audit/REVIEW-04.md`) | High |\n"
)
m = re.search(r"^\| F669 \|[^\n]*\n", s, re.M)
s = s[: m.end()] + row + s[m.end():]
p.write_text(s, encoding="utf-8", newline="\n")
print("ok")
