#!/usr/bin/env python3
"""BC5 experiment 0417: the swap script for candidate B (27b6416f). B changes NO backend file, so this is the
integration's int0416.sh with the pins, the patch names and the marks changed, each replacement asserted.
The swap itself is put to the maintainer by the top session; this script is only prepared and dry-run
(dryswap0417b.sh, on the laptop, with stand-ins).

  int0417b.sh  patch 0001 4651d1d3 (0001-new9.patch) -> S_NEW (0001-new14.patch, tree14.md5) in ~/src/KytyPlus;
               both shared emulators rebuilt in place; the archive 75e30335 must stay.
               New against int0416.sh: the binaries must hold candidate B's words and must NOT hold BC5_GUARD_K1R
               or the set-buffer test hook's word.
usage: mkswap0417b.py <repo root> <out dir>"""
import sys

root, out = sys.argv[1:3]
s = open(root + "/experiments/0416-emufive-switches/integration/int0416.sh", encoding="utf-8", newline="").read()
assert "\r" not in s


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:70], s.count(old), n)
    s = s.replace(old, new)


rep("# BC5 integration of 2026-11-13 (the maintainer through the top session:",
    "# BC5 exp 0417, candidate B: patch 0001 4651d1d3 -> S_NEW (0001-new14.patch), no backend change. Made from the\n"
    "# integration's swap script by mkswap0417b.py. NOT to be run on a general release: the top session puts this swap to\n"
    "# the maintainer first. usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0417b.sh\n"
    "# BC5 integration of 2026-11-13 (the maintainer through the top session:")
rep("PIN_NORMAL=ce0e3b928b6d1d1d47fc035c13e8cee3; PIN_LEAN=35ec3341be46ffd7013db8ffa9a4b2f5; PIN_ARCHIVE=75e30335; PIN_OLD=01abfc0c",
    "PIN_NORMAL=fe0933c0ad7c0d9a86194bc0a7598a06; PIN_LEAN=711d6c0d33d171bcb4749903bd607aa2; PIN_ARCHIVE=75e30335; PIN_OLD=4651d1d3")
rep('0001-new9', '0001-NEW', 8)
rep('0001-new7', '0001-new9', 7)
rep('0001-NEW', '0001-new14', 8)
rep("tree9.md5", "tree14.md5", 6)
rep("before-0416", "before-0417b", 10)
rep("-0416.out", "-0417b.out", 2)
rep("after-0416.txt", "after-0417b.txt")
rep("int0416", "int0417b", 7)
rep('claim "integration 0416+0415+0412: patch 0001 $S_NEW into the shared normal and lean, CPU only" 40',
    'claim "exp 0417 candidate B: patch 0001 $S_NEW into the shared normal and lean, CPU only" 40')
rep("KYTY_BC5_APR_POSIX BC5_GUARD_MAP_RULE", "KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_DIRECT_RESET_LABELS_ADD BC5_GUARD_MAP_RULE")
rep('        grep -aqF -- "$s" "$b" || restore "$b lacks [$s]"\n    done\n',
    '        grep -aqF -- "$s" "$b" || restore "$b lacks [$s]"\n    done\n'
    '    for s in BC5_GUARD_K1R KYTY_BC5_AMM_SETBUFFER_TEST; do   # candidate B has no K1r; the hook\'s gate is 0\n'
    '        grep -aqF -- "$s" "$b" && restore "$b holds [$s]"\n'
    '    done\n')
rep("undo: both binaries from $I/*.before-0417b, the tree by reversing 0001-new14 and applying 0001-new9 (then rebuild)",
    "undo: both binaries from $I/*.before-0417b, the tree by reversing 0001-new14 and applying 0001-new9 (then rebuild); the launchers are not touched")
open(out + "/int0417b.sh", "w", encoding="utf-8", newline="\n").write(s)
print("int0417b.sh ok")
