#!/usr/bin/env python3
"""BC5 experiment 0417, the next patch change (the top session, 2026-11-13: the candidate of exp 0417 + exp 0415's L5c
with KYTY_BC5_ANON_SYNC + exp 0412's nl412, the learned windows removed, keep-guards, + BC5_DIRECT_HEAP_GUARDS):
the box scripts for the PRIVATE build and its CPU tests, derived from the integration's by exact replacements.
  p0417b.sh   from ../0416-emufive-switches/integration/p0416c.sh: the private tree goes from 0001-new10 (33bddfa1,
              exp 0417's first candidate, the hook's gate at 0) to 0001-new11 (P_NEW11); normal and lean. The normal
              binary must NOT hold the test hook's variable name (the gate is 0).
  cpu0417.sh  from ../0416-emufive-switches/integration/cpu0416.sh: exp 0415's new counts, test0415anon added.
usage: mkkit0417b.py <repo root> <out dir>"""
import sys

root, out = sys.argv[1:3]


def derive(src, dst, changes):
    s = open(root + "/" + src, encoding="utf-8", newline="").read()
    assert "\r" not in s
    for old, new, n in changes:
        assert s.count(old) == n, (src, old[:70], s.count(old), n)
        s = s.replace(old, new)
    open(out + "/" + dst, "w", encoding="utf-8", newline="\n").write(s)
    print(dst, "ok")


derive("experiments/0416-emufive-switches/integration/p0416c.sh", "p0417b.sh", (
    ("# p0416c (2026-11-13, the integration of exp 0416 + 0415 + 0412):",
     "# p0417b (exp 0417, the next patch change): the private tree goes from 0001-new10 (33bddfa1) to 0001-new11\n"
     "# (P_NEW11); normal and lean; the set-buffer test hook must be absent. usage: P_NEW11=<patch md5> bash p0417b.sh\n"
     "# p0416c (2026-11-13, the integration of exp 0416 + 0415 + 0412):", 1),
    ('= 01abfc0c ] || stop "the shared tree is not 0001 01abfc0c"', '= 4651d1d3 ] || stop "the shared tree is not 0001 4651d1d3"', 1),
    ('[ "$(m "$HERE/0001-new8.patch")" = a099e662 ] && [ "$(m "$HERE/0001-new9.patch")" = "${P_NEW9:?the new patch md5}" ]',
     '[ "$(m "$HERE/0001-new10.patch")" = 33bddfa1 ] && [ "$(m "$HERE/0001-new11.patch")" = "${P_NEW11:?the new patch md5}" ]', 1),
    ('claim "integration 0416+0415+0412: private rebuild (incremental) under exp0413/p, CPU only" 40',
     'claim "exp 0417: private rebuild of the next patch change under exp0413/p, CPU only" 40', 1),
    ('done < "$HERE/tree8.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not a099e662\'s"',
     'done < "$HERE/tree10.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 33bddfa1\'s (the hook\'s gate must be 0)"', 1),
    ('git apply -R --whitespace=nowarn "$HERE/0001-new8.patch" && git apply --whitespace=nowarn "$HERE/0001-new9.patch"',
     'git apply -R --whitespace=nowarn "$HERE/0001-new10.patch" && git apply --whitespace=nowarn "$HERE/0001-new11.patch"', 1),
    ('done < "$HERE/tree9.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"',
     'done < "$HERE/tree11.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"', 1),
    ('echo "tree: $(wc -l < "$HERE/tree9.md5") patched files match the laptop\'s (0001-new9)"',
     'echo "tree: $(wc -l < "$HERE/tree11.md5") patched files match the laptop\'s (0001-new11)"', 1),
    ("KYTY_BC5_APR_POSIX BC5_GUARD_MAP_RULE", "KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT BC5_GUARD_MAP_RULE", 1),
    ('        grep -aqF -- "$s" "$b" || die "$v lacks [$s]"\n    done\n',
     '        grep -aqF -- "$s" "$b" || die "$v lacks [$s]"\n    done\n'
     '    grep -aqF -- "KYTY_BC5_AMM_SETBUFFER_TEST" "$b" && die "$v holds the set-buffer test hook (the gate is not 0)"\n', 1),
))

derive("experiments/0416-emufive-switches/integration/cpu0416.sh", "cpu0417.sh", (
    ("# BC5 integration of 2026-11-13: the CPU tests of the three experiments,",
     "# BC5 exp 0417, the next patch change (made from the integration's cpu0416.sh by mkkit0417b.py): exp 0415's counts\n"
     "# for L5c and its test0415anon; sb.cpp is exp 0417's plain test (the hook compiled out).\n"
     "# BC5 integration of 2026-11-13: the CPU tests of the three experiments,", 1),
    ("# usage (on the box): cpu0416.sh ", "# usage (on the box): cpu0417.sh ", 1),
    ('[ -f "$SRC/bc5/apr_posix.hpp" ] && [ -f "$SRC/bc5/map_records.hpp" ] || { echo "cpu0416: the private tree has no exp 0415 headers"; exit 1; }',
     '[ -f "$SRC/bc5/apr_posix.hpp" ] && [ -f "$SRC/bc5/anon_sync.hpp" ] || { echo "cpu0417: the private tree has no exp 0415 L5c headers"; exit 1; }', 1),
    ('gxx test0415rec -Werror -I "$SRC" && run test0415rec "$T/test0415rec"\n',
     'gxx test0415rec -Werror -I "$SRC" && run test0415rec "$T/test0415rec"\n'
     'gxx test0415anon -Werror -I "$SRC" && run test0415anon "$T/test0415anon"\n'
     '# the counts exp 0415 names for L5c: test0415 off 76, on 32; apr 33; sync 15; rec 11; anon 31\n'
     'for want in "test0415-off:76 of 76" "test0415-on:32 of 32" "test0415apr:33 of 33" "test0415sync:15 of 15" "test0415rec:11 of 11" "test0415anon:31 of 31" "maprule0412:15281 of 15281"; do\n'
     '    grep -q -- "${want#*:}; end" "$T/${want%%:*}.out" 2> /dev/null || { echo "FAIL count ${want%%:*}: want ${want#*:}, got $(tail -1 "$T/${want%%:*}.out" 2> /dev/null | cut -c1-80)"; fails=$((fails + 1)); }\n'
     'done\n', 1),
    ('echo "cpu0416: $fails failed"', 'echo "cpu0417: $fails failed"', 1),
    ('echo "cpu0416: an emulator runs: not started"', 'echo "cpu0417: an emulator runs: not started"', 1),
))
