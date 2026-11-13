#!/usr/bin/env python3
"""BC5 integration of 2026-11-13 (exp 0416 + 0415 + 0412 into the shared builds): derives the two box scripts from
the ones that did the same job for exp 0413, by exact replacements, each asserted to occur the stated number of times.
  p0416c.sh  from experiments/0416-emufive-switches/p0416.sh: the private tree goes from 0001-new8 (a099e662) to
             0001-new9 (the folded patch); the marks checked in the binaries are the three experiments' switches.
  int0416.sh from experiments/0413-np-session-v2-shared/int0413b.sh: the swap of both shared builds from patch
             01abfc0c (normal ce0e3b92, lean 35ec3341) to 0001-new9, with the same restore (md5-checked, the lock kept
             if incomplete).
usage: mkkit0416.py <repo root> <out dir>"""
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


MARKS = ('KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_AMM_SETBUFFER_GUARD KYTY_BC5_AMM_SETBUFFER_MAP KYTY_BC5_EVENT_COALESCE_SAME '
         'KYTY_BC5_SEMA_TARGETED_WAKE KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED KYTY_BC5_FW_NET '
         'KYTY_BC5_APR_POSIX BC5_GUARD_MAP_RULE BC5_GUARD_PRT_BG BC5_GUARD_LEARN_LOG KYTY_BC5_MAP_RECORDS')

derive("experiments/0416-emufive-switches/p0416.sh", "p0416c.sh", (
    ("# p0413b (the top, 2026-11-12 12:0x): incremental:",
     "# p0416c (2026-11-13, the integration of exp 0416 + 0415 + 0412): the private tree goes from 0001-new8 (a099e662) to\n"
     "# 0001-new9 (P_NEW9); the marks are the three experiments' switches. usage: P_NEW9=<patch md5> bash p0416c.sh\n"
     "# p0413b (the top, 2026-11-12 12:0x): incremental:", 1),
    ('[ "$(m "$HERE/0001-new7.patch")" = 01abfc0c ] && [ "$(m "$HERE/0001-new8.patch")" = "${P_NEW8:?the new patch md5}" ]',
     '[ "$(m "$HERE/0001-new8.patch")" = a099e662 ] && [ "$(m "$HERE/0001-new9.patch")" = "${P_NEW9:?the new patch md5}" ]', 1),
    ('claim "exp 0416: private rebuild (incremental) of the integration under exp0413/p, CPU only" 30',
     'claim "integration 0416+0415+0412: private rebuild (incremental) under exp0413/p, CPU only" 40', 1),
    ('done < "$HERE/tree7.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 01abfc0c\'s"',
     'done < "$HERE/tree8.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not a099e662\'s"', 1),
    ('git apply -R --whitespace=nowarn "$HERE/0001-new7.patch" && git apply --whitespace=nowarn "$HERE/0001-new8.patch"',
     'git apply -R --whitespace=nowarn "$HERE/0001-new8.patch" && git apply --whitespace=nowarn "$HERE/0001-new9.patch"', 1),
    ('done < "$HERE/tree8.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"',
     'done < "$HERE/tree9.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"', 1),
    ('echo "tree: $(wc -l < "$HERE/tree8.md5") patched files match the laptop\'s (0001-new8)"',
     'echo "tree: $(wc -l < "$HERE/tree9.md5") patched files match the laptop\'s (0001-new9)"', 1),
    ('KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_AMM_SETBUFFER_GUARD KYTY_BC5_AMM_SETBUFFER_MAP KYTY_BC5_EVENT_COALESCE_SAME KYTY_BC5_SEMA_TARGETED_WAKE '
     'KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED BC5_GUARD_ZSKIP_POLL_SUBMIT KYTY_BC5_FW_NET KYTY_BC5_AMM_SCATTER',
     MARKS + ' BC5_GUARD_ZSKIP_POLL_SUBMIT KYTY_BC5_AMM_SCATTER', 1),
))

derive("experiments/0413-np-session-v2-shared/int0413b.sh", "int0416.sh", (
    ("# BC5 exp 0413, the second swap (the maintainer, 2026-11-12:",
     "# BC5 integration of 2026-11-13 (the maintainer through the top session: \"jest zgoda na scalenie wszystkiego i twoje\n"
     "# testy\"): exp 0416 + 0415 + 0412, patch 0001 01abfc0c -> S_NEW (0001-new9.patch, tree9.md5), both shared builds.\n"
     "# Made from exp 0413's second swap script by mkkit0416.py; the text below is that script's, with the pins, the patch\n"
     "# names and the marks changed. usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0416.sh\n"
     "# BC5 exp 0413, the second swap (the maintainer, 2026-11-12:", 1),
    ("PIN_NORMAL=f6445dc6b37634ddd06366bb4b30753b; PIN_LEAN=30ee854b1dff4ae436720ab78f7ba229; PIN_ARCHIVE=75e30335; PIN_OLD=2dbed49a",
     "PIN_NORMAL=ce0e3b928b6d1d1d47fc035c13e8cee3; PIN_LEAN=35ec3341be46ffd7013db8ffa9a4b2f5; PIN_ARCHIVE=75e30335; PIN_OLD=01abfc0c", 1),
    ("#      the kit (0001-old.patch 2dbed49a, 0001-new7.patch S_NEW, tree7.md5);",
     "#      the kit (0001-new7.patch 01abfc0c, 0001-new9.patch S_NEW, tree9.md5);", 1),
    ("0001-old.patch", "0001-new7.patch.OLD", 4),
    ("0001-new7.patch\"", "0001-new9.patch\"", 5),
    ("0001-new7.patch.OLD", "0001-new7.patch", 4),
    ("tree7.md5", "tree9.md5", 4),
    ("before-0413b", "before-0416", 10),
    ("-0413b.out", "-0416.out", 2),
    ("after-0413b.txt", "after-0416.txt", 1),
    ("int0413b", "int0416", 6),
    ('claim "exp 0413: the integration\'s patch 0001 $S_NEW into normal and lean, CPU only" 40',
     'claim "integration 0416+0415+0412: patch 0001 $S_NEW into the shared normal and lean, CPU only" 40', 1),
    ('KYTY_BC5_SWITCH_DEFAULTS KYTY_BC5_AMM_SETBUFFER_GUARD KYTY_BC5_EVENT_PENDING_CAP KYTY_BC5_RANGES_FAST KYTY_BC5_PHYSMAP_SORTED KYTY_BC5_FW_NET',
     MARKS, 1),
    ("undo: both binaries from $I/*.before-0416, the tree by reversing 0001-new7 and applying 0001-old (then rebuild)",
     "undo: both binaries from $I/*.before-0416, the tree by reversing 0001-new9 and applying 0001-new7 (then rebuild)", 1),
))
