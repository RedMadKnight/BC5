#!/usr/bin/env python3
"""BC5 experiment 0417: the box kit for the PRIVATE build with the set-buffer test hook.
  p0417.sh    from ../0416-emufive-switches/integration/p0416c.sh by exact replacements (each asserted): the private
              tree ~/bc5-work/exp0413/p/tree goes from 0001-new9 (4651d1d3, what the shared builds are) to 0001-new10
              (P_NEW10, the candidate c61fe48b); then the hook's gate in src/bc5/setbuffer_test.hpp is set to 1 IN
              THE PRIVATE TREE ONLY, the normal build is rebuilt (libAmpr.cpp and memory.cpp recompile), and the gate
              is set back to 0 so the tree again equals the candidate. Lean is not built. Shared files are only read.
usage: mkkit0417.py <repo root> <out dir>"""
import sys

root, out = sys.argv[1:3]
s = open(root + "/experiments/0416-emufive-switches/integration/p0416c.sh", encoding="utf-8", newline="").read()
assert "\r" not in s
GATE = "$P/tree/src/bc5/setbuffer_test.hpp"
CH = (
    ("# p0416c (2026-11-13, the integration of exp 0416 + 0415 + 0412):",
     "# p0417 (exp 0417): the private tree goes from 0001-new9 (4651d1d3) to 0001-new10 (P_NEW10), the set-buffer test\n"
     "# hook's gate is set to 1 in the private tree for the build and back to 0 after it; normal only.\n"
     "# usage: P_NEW10=<patch md5> bash p0417.sh\n"
     "# p0416c (2026-11-13, the integration of exp 0416 + 0415 + 0412):", 1),
    ('= 01abfc0c ] || stop "the shared tree is not 0001 01abfc0c"', '= 4651d1d3 ] || stop "the shared tree is not 0001 4651d1d3"', 1),
    ('[ "$(m "$HERE/0001-new8.patch")" = a099e662 ] && [ "$(m "$HERE/0001-new9.patch")" = "${P_NEW9:?the new patch md5}" ]',
     '[ "$(m "$HERE/0001-new9.patch")" = 4651d1d3 ] && [ "$(m "$HERE/0001-new10.patch")" = "${P_NEW10:?the new patch md5}" ]', 1),
    ('claim "integration 0416+0415+0412: private rebuild (incremental) under exp0413/p, CPU only" 40',
     'claim "exp 0417: private rebuild with the set-buffer test hook under exp0413/p, CPU only" 25', 1),
    ('done < "$HERE/tree8.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not a099e662\'s"',
     'done < "$HERE/tree9.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 4651d1d3\'s"', 1),
    ('git apply -R --whitespace=nowarn "$HERE/0001-new8.patch" && git apply --whitespace=nowarn "$HERE/0001-new9.patch"',
     'git apply -R --whitespace=nowarn "$HERE/0001-new9.patch" && git apply --whitespace=nowarn "$HERE/0001-new10.patch"', 1),
    ('done < "$HERE/tree9.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"',
     'done < "$HERE/tree10.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"', 1),
    ('echo "tree: $(wc -l < "$HERE/tree9.md5") patched files match the laptop\'s (0001-new9)"\n',
     'echo "tree: $(wc -l < "$HERE/tree10.md5") patched files match the laptop\'s (0001-new10)"\n'
     '# exp 0417: the hook\'s gate, in the private tree only, for this build\n'
     'GATE=%s\n'
     'gate() { sed -i "s/^#define KYTY_BC5_SETBUFFER_TEST_HOOK [01]$/#define KYTY_BC5_SETBUFFER_TEST_HOOK $1/" "$GATE" && [ "$(grep -c "^#define KYTY_BC5_SETBUFFER_TEST_HOOK $1$" "$GATE")" = 1 ]; }\n'
     'gate 1 || die "the gate could not be set to 1"\n'
     'echo "gate: $(grep "^#define KYTY_BC5_SETBUFFER_TEST_HOOK" "$GATE")"\n' % GATE, 1),
    ("for v in normal lean; do", "for v in normal; do", 1),
    ("KYTY_BC5_APR_POSIX BC5_GUARD_MAP_RULE", "KYTY_BC5_APR_POSIX KYTY_BC5_AMM_SETBUFFER_TEST KYTY_BC5_AMM_SETBUFFER_TEST_VA BC5_GUARD_MAP_RULE", 1),
    ('echo "$(date \'+%F %T\') done; normal $(m "$P/build-normal/src/kyty_emulator"), lean $(m "$P/build-lean/src/kyty_emulator")"\n',
     'gate 0 && [ "$(md5sum < "$GATE" | cut -d\' \' -f1)" = "$(grep " src/bc5/setbuffer_test.hpp$" "$HERE/tree10.md5" | cut -d\' \' -f1)" ] || die "the gate could not be set back to 0"\n'
     'echo "gate back: $(grep "^#define KYTY_BC5_SETBUFFER_TEST_HOOK" "$GATE"); the private lean build is still patch 4651d1d3\'s (not rebuilt)"\n'
     'echo "$(date \'+%F %T\') done; normal $(m "$P/build-normal/src/kyty_emulator") (WITH the test hook: private only), lean not rebuilt"\n', 1),
)
for old, new, n in CH:
    assert s.count(old) == n, (old[:70], s.count(old), n)
    s = s.replace(old, new)
open(out + "/p0417.sh", "w", encoding="utf-8", newline="\n").write(s)
print("p0417.sh ok")
