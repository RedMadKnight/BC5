#!/usr/bin/env python3
"""BC5 experiment 0417, after K1r's first run on ASTRO BOT (2026-11-13 11:32: a GPU write into a covered chunk of a
lazy heap, a failed ring reset, the box rebooted): the top session's decision is K1R default OFF again, the fault
record default ON. This makes the pieces for that candidate.
  def     <unit after exp 0412's mkff0412.py> -> <out>: exp 0412's own flip() (mkdef0412.py) for BC5_FAULT_RECORD
          only; BC5_GUARD_K1R keeps its default (off; "1" turns it on).
  kit     p0417d.sh from p0417c.sh and chk0417d.sh from chk0417c.sh (this directory), by exact replacements: the
          private tree goes from 0001-new12 (26ef195c) to 0001-new13 (P_NEW13); the chain has no K1R=0 arm (it is
          the default again) and its tags begin with d.
usage: mkkit0417d.py def <mkdef0412.py> <unit in> <unit out>
       mkkit0417d.py kit <this directory> <out dir>"""
import hashlib
import sys

if sys.argv[1] == "def":
    gen, src, dst = sys.argv[2:5]
    g = {"__name__": "mkdef0412_part"}
    exec(compile(open(gen, "rb").read(), gen, "exec"), g)
    s = open(src, "rb").read()
    assert b"\r" not in s and b"tag fr412" in s and b"mkdef0412.py" not in s
    k1r = b"tag k1r412" in s  # candidate B (the top session, 2026-11-13) has no K1r step at all
    s = g["flip"](s, b"BC5_FAULT_RECORD")
    assert not k1r or s.count(b'std::getenv("BC5_GUARD_K1R");\n\t\treturn e != nullptr && e[0] != 0 && !(e[0] == \'0\' && e[1] == 0);\n') == 1, "K1R is not default off"
    open(dst, "wb").write(s)
    print("def -> %s (the fault record on by default, K1R off)" % hashlib.md5(s).hexdigest()[:8])
    sys.exit(0)

here, out = sys.argv[2:4]


def derive(src, dst, changes):
    s = open(here + "/" + src, encoding="utf-8", newline="").read()
    assert "\r" not in s
    for old, new, n in changes:
        assert s.count(old) == n, (src, old[:70], s.count(old), n)
        s = s.replace(old, new)
    open(out + "/" + dst, "w", encoding="utf-8", newline="\n").write(s)
    print(dst, "ok")


derive("p0417c.sh", "p0417d.sh", (
    ("# p0417c (exp 0417, the K1r fold):",
     "# p0417d (exp 0417, K1R default off again): the private tree goes from 0001-new12 (26ef195c) to 0001-new13 (P_NEW13);\n"
     "# the private backend is made again the same way. usage: P_NEW13=<patch md5> bash p0417d.sh\n"
     "# p0417c (exp 0417, the K1r fold):", 1),
    ('[ "$(m "$HERE/0001-new11.patch")" = c55174b1 ] && [ "$(m "$HERE/0001-new12.patch")" = "${P_NEW12:?the new patch md5}" ]',
     '[ "$(m "$HERE/0001-new12.patch")" = 26ef195c ] && [ "$(m "$HERE/0001-new13.patch")" = "${P_NEW13:?the new patch md5}" ]', 1),
    ('done < "$HERE/tree11.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not c55174b1\'s"',
     'done < "$HERE/tree12.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 26ef195c\'s"', 1),
    ('git apply -R --whitespace=nowarn "$HERE/0001-new11.patch" && git apply --whitespace=nowarn "$HERE/0001-new12.patch"',
     'git apply -R --whitespace=nowarn "$HERE/0001-new12.patch" && git apply --whitespace=nowarn "$HERE/0001-new13.patch"', 1),
    ('done < "$HERE/tree12.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"',
     'done < "$HERE/tree13.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"', 1),
    ('echo "tree: $(wc -l < "$HERE/tree12.md5") patched files match the laptop\'s (0001-new12)"',
     'echo "tree: $(wc -l < "$HERE/tree13.md5") patched files match the laptop\'s (0001-new13)"', 1),
))
derive("chk0417c.sh", "chk0417d.sh", (
    ("# usage (on the box, detached): P_NEW12=<patch md5> chk0417c.sh",
     "# chk0417d (after the reboot of 11:32): candidate P_NEW13 = the same fold with BC5_GUARD_K1R default OFF again; the chain\n"
     "# has no K1R=0 arm (it is the default) and no run turns K1r on. usage (on the box, detached): P_NEW13=<patch md5> chk0417d.sh\n"
     "# usage (on the box, detached): P_NEW12=<patch md5> chk0417c.sh", 1),
    ('    : "${P_NEW12:?the patch md5}"\n    (cd "$P/kit" && P_NEW12=$P_NEW12 bash ./p0417c.sh) > "$P/p0417c.log" 2>&1',
     '    : "${P_NEW13:?the patch md5}"\n    (cd "$P/kit" && P_NEW13=$P_NEW13 bash ./p0417d.sh) > "$P/p0417d.log" 2>&1', 1),
    ('"$P/p0417c.log"', '"$P/p0417d.log"', 4),
    ("chk0417c", "chk0417d", 5),
    ('chain_claim "exp 0417 K1r fold: private build,', 'chain_claim "exp 0417 fold with K1R default off: private build,', 1),
    ("astro c1${X}a\nastro c2${X}a\nastro c3${X}d KYTY_BC5_SWITCH_DEFAULTS=0\n", "astro d1${X}a\nastro d2${X}a\nastro d3${X}d KYTY_BC5_SWITCH_DEFAULTS=0\n", 1),
    ("second c4${X}\nsecond c5${X}\nsecond c6${X}cut ", "second d4${X}\nsecond d5${X}\nsecond d6${X}cut ", 1),
    ('bash ./start0413l.sh c7${X} lean 120 | grep "^c7${X} ")', 'bash ./start0413l.sh d7${X} lean 120 | grep "^d7${X} ")', 1),
    ("second c8${X}k0 BC5_GUARD_K1R=0\nsecond c9${X}eop ", "second d9${X}eop ", 1),
))
