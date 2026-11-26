#!/usr/bin/env python3
"""BC5 experiment 0419: the private build script of candidate E, made from exp 0417's generated p0417c.sh (the
script that also builds a PRIVATE backend archive) by exact replacements.
E = B (27b6416f) + exp 0412's K1r, its form 4 (no probe, no replace; K1R and its filter on by default; two backend files: direct.hpp e96e5c73,
direct.cpp 28100ce5) + this experiment's cleanup + exp 0417's save-data-memory switches and transferring-mount fix.
The private tree goes from 0001-new15 (1689b7da, exp 0417's candidate C) to 0001-new17 (P_NEW17). The shared tree,
the shared archive and the shared backend source are only read.
usage: mkkit0419e.py <p0417c.sh as generated> <out dir>"""
import sys

src, out = sys.argv[1:3]
s = open(src, encoding="utf-8", newline="").read()
assert "\r" not in s


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:70], s.count(old), n)
    s = s.replace(old, new)


rep("# p0417c (exp 0417, the K1r fold):",
    "# p0419e (exp 0419, candidate E): the private tree goes from 0001-new15 (1689b7da) to 0001-new17 (P_NEW17); the private\n"
    "# backend gets exp 0412's two files WITHOUT the probe. usage: P_NEW17=<patch md5> bash p0419e.sh\n"
    "# p0417c (exp 0417, the K1r fold):")
rep('= 4651d1d3 ] || stop "the shared tree is not 0001 4651d1d3"', '= 27b6416f ] || stop "the shared tree is not 0001 27b6416f"')
rep('[ "$(m "$HERE/0001-new11.patch")" = c55174b1 ] && [ "$(m "$HERE/0001-new12.patch")" = "${P_NEW12:?the new patch md5}" ]',
    '[ "$(m "$HERE/0001-new15.patch")" = 1689b7da ] && [ "$(m "$HERE/0001-new17.patch")" = "${P_NEW17:?the new patch md5}" ]')
rep('claim "exp 0417: private rebuild of the K1r fold (tree and a private backend) under exp0413/p, CPU only" 40',
    'claim "exp 0419: private rebuild of candidate E (tree and a private backend) under exp0413/p, CPU only" 40')
rep('done < "$HERE/tree11.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not c55174b1\'s"',
    'done < "$HERE/tree15.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 1689b7da\'s"')
rep('git apply -R --whitespace=nowarn "$HERE/0001-new11.patch" && git apply --whitespace=nowarn "$HERE/0001-new12.patch"',
    'git apply -R --whitespace=nowarn "$HERE/0001-new15.patch" && git apply --whitespace=nowarn "$HERE/0001-new17.patch"')
rep("tree12.md5", "tree17.md5", 2)
rep("(0001-new12)", "(0001-new17)")
rep('[ "$(m "$HERE/backend-direct.hpp")" = 2497a4ce ] && [ "$(m "$HERE/backend-direct.cpp")" = b183516e ] || die "the kit\'s backend files are not 2497a4ce / b183516e"',
    '[ "$(m "$HERE/backend-direct-noprobe.hpp")" = e96e5c73 ] && [ "$(m "$HERE/backend-direct-noprobe.cpp")" = 28100ce5 ] || die "the kit\'s backend files are not e96e5c73 / 28100ce5"')
rep('cp "$HERE/backend-direct.hpp" "$PB/include/bc5/direct.hpp" && cp "$HERE/backend-direct.cpp" "$PB/src/direct.cpp"',
    'cp "$HERE/backend-direct-noprobe.hpp" "$PB/include/bc5/direct.hpp" && cp "$HERE/backend-direct-noprobe.cpp" "$PB/src/direct.cpp"')
rep("exp 0412's private one was ed63df2f)", "exp 0412's with the probe was ed63df2f; this one has no probe)")
rep("BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_DIRECT_RESET_LABELS_ADD BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG KYTY_BC5_MAP_RECORDS BC5_GUARD_ZSKIP_POLL_SUBMIT KYTY_BC5_AMM_SCATTER",
    "BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG KYTY_BC5_MAP_RECORDS KYTY_BC5_AMM_SCATTER "
    "BC5_GUARD_K1_FILTER BC5_GUARD_LAZY_BY_DATA KYTY_BC5_TITLE_DEFAULTS KYTY_BC5_SAVEDATA_MEMORY_LOG KYTY_BC5_SAVEDATA_TRANSFER_FIX")
rep('    grep -aqF -- "KYTY_BC5_AMM_SETBUFFER_TEST" "$b" && die "$v holds the set-buffer test hook (the gate is not 0)"\n',
    '    grep -aqF -- "KYTY_BC5_AMM_SETBUFFER_TEST" "$b" && die "$v holds the set-buffer test hook (the gate is not 0)"\n'
    '    for s in BC5_GUARD_K1R_PROBE KYTY_BC5_NAMES_FAST KYTY_BC5_MIN_FLIP_RATE BC5_GUARD_ZSKIP_POLL_SUBMIT; do   # exp 0419: no probe; removed options\n'
    '        grep -aqF -- "$s" "$b" && die "$v holds [$s]"\n'
    '    done\n')
open(out + "/p0419e.sh", "w", encoding="utf-8", newline="\n").write(s)
print("p0419e.sh ok")
