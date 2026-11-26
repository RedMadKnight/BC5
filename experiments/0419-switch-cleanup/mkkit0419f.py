#!/usr/bin/env python3
"""BC5 experiment 0419: the private build script of candidate F, from the generated p0419e.sh by exact replacements.
F = B (27b6416f) + exp 0412's FORM 6 (K1r with the binary-search cover, its writers catcher BC5_GUARD_WRITERS, off;
the backend files of form 4: direct.hpp e96e5c73, direct.cpp 28100ce5) + this experiment's cleanup + exp 0417's save
words + exp 0418's start-state table (its 0418-on-410273ca.diff, applied on top: always on, three title rows out).
The private tree goes from 0001-new17 (410273ca, candidate E) to 0001-new18 (P_NEW18).
usage: mkkit0419f.py <p0419e.sh as generated> <out dir>"""
import sys

src, out = sys.argv[1:3]
s = open(src, encoding="utf-8", newline="").read()
assert "\r" not in s


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:70], s.count(old), n)
    s = s.replace(old, new)


rep("# p0419e (exp 0419, candidate E):",
    "# p0419f (exp 0419, candidate F): the private tree goes from 0001-new17 (410273ca, E) to 0001-new18 (P_NEW18); the\n"
    "# private backend is made again from the same two files. usage: P_NEW18=<patch md5> bash p0419f.sh\n"
    "# p0419e (exp 0419, candidate E):")
rep('[ "$(m "$HERE/0001-new15.patch")" = 1689b7da ] && [ "$(m "$HERE/0001-new17.patch")" = "${P_NEW17:?the new patch md5}" ]',
    '[ "$(m "$HERE/0001-new17.patch")" = 410273ca ] && [ "$(m "$HERE/0001-new18.patch")" = "${P_NEW18:?the new patch md5}" ]')
rep("private rebuild of candidate E (tree and a private backend)", "private rebuild of candidate F (tree and a private backend)")
rep('done < "$HERE/tree15.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 1689b7da\'s"',
    'done < "$HERE/treeE.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 410273ca\'s"')
rep('git apply -R --whitespace=nowarn "$HERE/0001-new15.patch" && git apply --whitespace=nowarn "$HERE/0001-new17.patch"',
    'git apply -R --whitespace=nowarn "$HERE/0001-new17.patch" && git apply --whitespace=nowarn "$HERE/0001-new18.patch"')
rep("tree17.md5", "tree18.md5", 2)
rep("treeE.md5", "tree17.md5")
rep("(0001-new17)", "(0001-new18)")
rep("KYTY_BC5_TITLE_DEFAULTS KYTY_BC5_SAVEDATA_MEMORY_LOG KYTY_BC5_SAVEDATA_TRANSFER_FIX",
    "KYTY_BC5_TITLE_DEFAULTS KYTY_BC5_SAVEDATA_MEMORY_LOG KYTY_BC5_SAVEDATA_TRANSFER_FIX BC5_GUARD_WRITERS BC5_DIRECT_START_STATE_SKIP")  # BC5_GC_IOCTL_TRACE is read through BC5_DIAG_ENV: not in the lean binary
rep("for s in BC5_GUARD_K1R_PROBE KYTY_BC5_NAMES_FAST KYTY_BC5_MIN_FLIP_RATE BC5_GUARD_ZSKIP_POLL_SUBMIT; do",
    "for s in BC5_GUARD_K1R_PROBE KYTY_BC5_NAMES_FAST KYTY_BC5_MIN_FLIP_RATE BC5_GUARD_ZSKIP_POLL_SUBMIT BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_GC_HS_OFFCHIP; do")
open(out + "/p0419f.sh", "w", encoding="utf-8", newline="\n").write(s)
print("p0419f.sh ok")
