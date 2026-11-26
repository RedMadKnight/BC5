#!/usr/bin/env python3
"""BC5 integration of 2026-11-13 (exp 0416 + 0415 + 0412 into patch 0001): exp 0412's mkrule0412.py (tag mr412,
sha256 90b7afd2...) run on the SHARED main unit instead of g412w's.

mkrule0412.py was written for the unit after exp 0412's private steps (tags zs412, pr412, ...). Of those, the three
mr412 switches need one thing only: the view's protection bits (`DView::prot`, tag pr412), which the catcher
BC5_GUARD_LEARN_LOG prints. The shared unit has no such field and the private steps are not part of this integration,
so this script runs mkrule0412.py's own main() with four textual changes, each asserted to occur exactly once:
  1. the input check asks only that tag mr412 is not there yet (not for the tags zs412 and pr412);
  2. the catcher keeps no `prot` variable and does not read `v.prot`;
  3. its journal line has no "prot 0x.." field (no script of exp 0412 reads that field);
  4. `DView::prot` is not required to be defined.
Everything else (the eleven anchors, the undo check, the order checks, the two device-open sites, maprule0412.inc as
tested by maprule0412.cpp) is mkrule0412.py's, unchanged. BC5_GUARD_MAP_RULE and BC5_GUARD_PRT_BG do not touch prot.
usage: mkrule0416.py <mkrule0412.py> <bc5LleAgc.cpp in> <bc5LleAgc.cpp out>     (maprule0412.inc beside mkrule0412.py)"""
import hashlib
import os
import sys

src_path, unit_in, unit_out = sys.argv[1:4]
src = open(src_path, "rb").read()
assert hashlib.sha256(src).hexdigest() == "90b7afd2caad645b17d7e9bf13c95c9a167d130a66f400407272b7c439bd58b0", "not the mkrule0412.py this was written for"
CHANGES = (
    (b'assert b"tag zs412" in s and b"tag pr412" in s and b"tag mr412" not in s, "refused: not the expected input"',
     b'assert b"tag mr412" not in s, "refused: tag mr412 is already in the unit"'),
    (b"\tint         prot = 0, kind = -1;\n", b"\tint         kind = -1;\n"),
    (b"\t\t\tprot     = v.prot;\n", b""),
    (b"view %s%s%s prot 0x%x; chunk %s%s;", b"view %s%s%s; chunk %s%s;"),
    (b", static_cast<unsigned>(prot), imported ?", b", imported ?"),
    (b'b"static bool g_mr412_bg = false;", b"\\tint         prot = 0;"):', b'b"static bool g_mr412_bg = false;"):'),
)
for old, new in CHANGES:
    assert src.count(old) == 1, ("a change does not apply exactly once", old[:60], src.count(old))
    src = src.replace(old, new)
assert b"prot" not in src.split(b"CATCH = b'''", 1)[1].split(b"'''", 1)[0], "the catcher still names prot"
g = {"__name__": "mkrule0412_shared", "__file__": os.path.abspath(src_path)}
exec(compile(src, src_path, "exec"), g)
sys.argv = [src_path, unit_in, unit_out]
g["main"]()
