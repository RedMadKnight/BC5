#!/usr/bin/env python3
"""BC5 experiment 0419: the private build script of candidate G, from the generated p0419f.sh by exact replacements.
The test build T = G (mklibs0419g.py, mkg0419_a.py .. mkg0419_e.py, mkg0419_g.py, ajm/mkajm0419.py on F d9af28ca) + exp 0412's six steps (test-build.md), and mkg0419_f.py (with `all`) on the backend's
direct.cpp (28100ce5 -> aeec4c09; direct.hpp e96e5c73 as in F). The private tree goes from 0001-new18 (F) to
0001-new23 (P_NEW23). Made on the laptop on 2026-11-14 without a build: this script's run on the box is G's FIRST
compile (the main unit cannot be compiled on the laptop), so a compile error there is an expected kind of result.
usage: mkkit0419g.py <p0419f.sh as generated> <out dir>"""
import sys

src, out = sys.argv[1:3]
s = open(src, encoding="utf-8", newline="").read()
assert "\r" not in s


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:70], s.count(old), n)
    s = s.replace(old, new)


rep("# p0419f (exp 0419, candidate F):",
    "# p0419g (exp 0419, candidate G): the private tree goes from 0001-new18 (d9af28ca, F) to 0001-new23 (P_NEW23); the\n"
    "# private backend gets direct.cpp aeec4c09 (seven option reads gone). usage: P_NEW23=<patch md5> bash p0419g.sh\n"
    "# p0419f (exp 0419, candidate F):")
rep('[ "$(m "$HERE/0001-new17.patch")" = 410273ca ] && [ "$(m "$HERE/0001-new18.patch")" = "${P_NEW18:?the new patch md5}" ]',
    '[ "$(m "$HERE/0001-new18.patch")" = d9af28ca ] && [ "$(m "$HERE/0001-new23.patch")" = "${P_NEW23:?the new patch md5}" ]')
rep("private rebuild of candidate F (tree and a private backend)", "private rebuild of candidate G (tree and a private backend)")
rep('done < "$HERE/tree17.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 410273ca\'s"',
    'done < "$HERE/treeF.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not d9af28ca\'s"')
rep('git apply -R --whitespace=nowarn "$HERE/0001-new17.patch" && git apply --whitespace=nowarn "$HERE/0001-new18.patch"',
    'git apply -R --whitespace=nowarn "$HERE/0001-new18.patch" && git apply --whitespace=nowarn "$HERE/0001-new23.patch"')
rep("tree18.md5", "tree23.md5", 2)
rep("treeF.md5", "tree18.md5")
rep("(0001-new18)", "(0001-new23)")
rep('[ "$(m "$HERE/backend-direct-noprobe.hpp")" = e96e5c73 ] && [ "$(m "$HERE/backend-direct-noprobe.cpp")" = 28100ce5 ] || die "the kit\'s backend files are not e96e5c73 / 28100ce5"',
    '[ "$(m "$HERE/backend-direct-noprobe.hpp")" = e96e5c73 ] && [ "$(m "$HERE/backend-direct-g.cpp")" = aeec4c09 ] || die "the kit\'s backend files are not e96e5c73 / aeec4c09"')
rep('cp "$HERE/backend-direct-noprobe.cpp" "$PB/src/direct.cpp"', 'cp "$HERE/backend-direct-g.cpp" "$PB/src/direct.cpp"')
# the marks: what G's binaries must hold and must not hold
rep(" KYTY_BC5_EVENT_COALESCE_SAME KYTY_BC5_SEMA_TARGETED_WAKE KYTY_BC5_EVENT_PENDING_CAP", " KYTY_BC5_EVENT_PENDING_CAP")
rep(" KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT", " KYTY_BC5_ANON_SYNC BC5_GUARD_K1_STAT")
rep(" BC5_R3_EOP_STAT BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG", " BC5_R3_EOP_STAT BC5_GUARD_LEARN_LOG")
rep("BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_GC_HS_OFFCHIP; do",
    "BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_GC_HS_OFFCHIP KYTY_BC5_EVENT_COALESCE_SAME KYTY_BC5_SEMA_TARGETED_WAKE BC5_DIRECT_TF_DEFAULT "
    "BC5_DIRECT_CROSS_RING_WAITS BC5_DIRECT_RING_DEPS BC5_DIRECT_TWO_RING_WAIT_MS BC5_DIRECT_PIECES_NO_CLEAR KYTY_BC5_RING_SPIN_US "
    "KYTY_BC5_MUTEX_SPIN_US KYTY_BC5_TIMERSLACK_NS BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_WB BC5_DIRECT_ARGS_FLUSH BC5_DIRECT_FL_SERIAL BC5_DIRECT_FL_VGT_FLUSH; do")
open(out + "/p0419g.sh", "w", encoding="utf-8", newline="\n").write(s)
print("p0419g.sh ok")
