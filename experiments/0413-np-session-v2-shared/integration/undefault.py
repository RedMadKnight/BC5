"""Exp 0413: take audit rows out of the defaults table (one commit each), after ASTRO BOT's start crashed with them on."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defaults as d  # noqa: E402

TREE, REPO, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
d.TREE, d.REPO, d.WORK = TREE, REPO, WORK
d.PATCH = os.path.join(REPO, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
d.HDR = os.path.join(TREE, "src", "bc5", "switch_defaults.hpp")
OUT = ["A15", "A16", "A17", "A21", "A22"]
WHY = ("ASTRO BOT's start crashed 5-6 s in (a guest write through a null out-pointer at eboot+0x48f, the same address every time)"
       " whenever four or more of A15, A16, A17, A21, A22 were on, and passed 120 s with all five off (exp 0413 runs a1astro,"
       " b1-b9, c1-c6, d1). These ports were tested only with the second title; its launcher keeps them on.")
removed = []
for row in OUT:
    removed.append(row)
    keep = [it for it in d.ITEMS if it[0] not in removed]
    saved = d.ITEMS
    d.ITEMS = keep
    d.write_header(len(keep))
    d.ITEMS = saved
    names = ", ".join(n for r, _, sw, _ in saved if r == row for n, _ in sw)
    d.commit(f"int(0413): audit {row} back to default off (second title's launcher only)\n\n{names}\n{WHY}")
    print(row, "removed")
