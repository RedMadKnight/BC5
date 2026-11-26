#!/usr/bin/env python3
"""BC5 experiment 0419: the swap script for candidate F. E changes the SHARED backend archive (exp 0412's two files),
so the script is made from exp 0417's generator for such a swap, mkswap0417.py (its int0417.sh was prepared for the
first K1r fold and never run), with E's pins put in. This file rewrites that generator's text and runs it:

  int0419f.sh  patch 0001 27b6416f -> S_NEW (0001-new18.patch, tree18.md5) in ~/src/KytyPlus;
               ~/bc5-work/d19/export/backend: include/bc5/direct.hpp a9fcb26b -> e96e5c73, src/direct.cpp
               51279eae -> 28100ce5; the shared archive rebuilt in ~/bc5-work/backend-ubuntu, 75e30335 -> d4c4882e
               expected (the private build of the same source with the same options gave d4c4882e on 2026-11-13);
               then both shared emulators. Everything is kept first and read back; a failure restores the archive,
               the two source files, both binaries and the tree and checks the restore.
The swap is the top session's to put to the maintainer (one "yes": builds, archive, launchers); nothing here runs it.
usage: mkswap0419e.py <repo root (has experiments/0417-shared-followups/mkswap0417.py and exp 0416's int0416.sh)> <out dir>"""
import os
import subprocess
import sys
import tempfile

root, out = sys.argv[1:3]
g = open(root + "/experiments/0417-shared-followups/mkswap0417.py", encoding="utf-8", newline="").read()
assert "\r" not in g


def rep(a, b, n=1):
    global g
    assert g.count(a) == n, (a[:70], g.count(a), n)
    g = g.replace(a, b)


rep("PIN_NORMAL=fe0933c0ad7c0d9a86194bc0a7598a06; PIN_LEAN=711d6c0d33d171bcb4749903bd607aa2; PIN_ARCHIVE=75e30335; PIN_OLD=4651d1d3",
    "PIN_NORMAL=51af1ed78e84291caf5ee042ea82c46d; PIN_LEAN=59894428d98ed94918d09a31002c1e3b; PIN_ARCHIVE=75e30335; PIN_OLD=27b6416f")
rep("NEW_ARCHIVE=ed63df2f", "NEW_ARCHIVE=d4c4882e")
rep("H_NEW=2497a4ce; C_NEW=b183516e", "H_NEW=e96e5c73; C_NEW=28100ce5")
# the patch names: the old tree is 0001-new14 (27b6416f), the new one 0001-new18
rep("""rep('0001-new9.patch"', '0001-NEW.patch"', 5)""", """rep('0001-new9', '0001-NEW', 8)""")
rep("""rep('0001-new7.patch', '0001-new9.patch', 5)""", """rep('0001-new7', '0001-new14', 7)""")
rep("""rep('0001-NEW.patch"', '0001-new12.patch"', 5)""", """rep('0001-NEW', '0001-new18', 8)""")
rep("""rep("tree9.md5", "tree12.md5", 6)""", """rep("tree9.md5", "tree18.md5", 6)""")
rep("# BC5 exp 0417, the K1r fold: patch 0001 4651d1d3 -> S_NEW AND the shared backend archive 75e30335 -> ed63df2f (exp",
    "# BC5 exp 0419, candidate F: patch 0001 27b6416f -> S_NEW AND the shared backend archive 75e30335 -> d4c4882e (exp")
rep("Made from the integration's swap script by mkswap0417.py; see that file for the procedure.",
    "Made from the integration's swap script by mkswap0419e.py (through exp 0417's mkswap0417.py); see those files.")
rep("# usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0417.sh",
    "# usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0419f.sh")
rep("exp 0417 K1r fold: patch 0001 $S_NEW and the backend archive into the shared builds, CPU only",
    "exp 0419 candidate F: patch 0001 $S_NEW and the backend archive into the shared builds, CPU only")
rep("KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1R BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_GUARD_MAP_RULE",
    "KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1R BC5_GUARD_K1_FILTER BC5_FAULT_RECORD BC5_R3_EOP_STAT "
    "KYTY_BC5_TITLE_DEFAULTS KYTY_BC5_SAVEDATA_TRANSFER_FIX BC5_GUARD_WRITERS BC5_DIRECT_START_STATE_SKIP BC5_GUARD_MAP_RULE")
rep("the tree by reversing 0001-new12 and applying 0001-new9 (then rebuild the backend and both emulators)",
    "the tree by reversing 0001-new18 and applying 0001-new14 (then rebuild the backend and both emulators); this script touches no launcher")
rep("the tree by reversing 0001-new9 and applying 0001-new7 (then rebuild)", "the tree by reversing 0001-new18 and applying 0001-new14 (then rebuild)")  # the bare names are replaced before this line runs
g = g.replace("before-0417", "before-0419").replace("-0417.out", "-0419.out").replace("after-0417.txt", "after-0419.txt")
rep('rep("int0416", "int0417", 7)', 'rep("int0416", "int0419f", 7)')
rep('open(out + "/int0417.sh", "w"', 'open(out + "/int0419f.sh", "w"')
rep('print("int0417.sh ok")', 'print("int0419f.sh ok")')
with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "gen.py")
    open(p, "w", encoding="utf-8", newline="\n").write(g)
    subprocess.check_call([sys.executable, p, root, out])
s = open(out + "/int0419f.sh", encoding="utf-8", newline="").read()
for bad in ("before-0417", "int0417", "ed63df2f", "2497a4ce", "b183516e", "0001-new9", "0001-new12", "fe0933c0", "4651d1d3"):
    assert bad not in s, bad
for good in ("0001-new14.patch", "0001-new18.patch", "tree18.md5", "d4c4882e", "e96e5c73", "28100ce5", "PIN_OLD=27b6416f"):
    assert good in s, good
print("int0419f.sh checked: E's pins, no pin of the earlier fold left")
