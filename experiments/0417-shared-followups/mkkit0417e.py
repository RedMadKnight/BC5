#!/usr/bin/env python3
"""BC5 experiment 0417, candidate B (the top session, 2026-11-13, after K1r's fault on ASTRO BOT): the fold WITHOUT
exp 0412's K1r step, its probe and its address watch, so no backend file and no backend archive changes in this swap.
B = c55174b1 + exp 0412's rl412 (off), fault record (ON by default) with the save guard, first-fail catchers
+ the EOP counter; patch 0001-new14 (P_NEW14), linked against the SHARED archive 75e30335.
  p0417e.sh   from p0417b.sh: the private tree goes from 0001-new13 (05fe48b6, the K1R-off form of the K1r fold) to
              0001-new14; both emulator builds are configured again against the SHARED backend paths (the K1r fold's
              builds were configured against a private backend); the binaries must not hold BC5_GUARD_K1R.
  chk0417e.sh from chk0417d.sh: the short re-check: ASTRO BOT 120 s plain and with KYTY_BC5_SWITCH_DEFAULTS=0, the
              second title's walk to G+240 once, the cutscene arm once, lean 120 s.
usage: mkkit0417e.py <this directory> <out dir>"""
import sys

here, out = sys.argv[1:3]


def derive(src, dst, changes):
    s = open(here + "/" + src, encoding="utf-8", newline="").read()
    assert "\r" not in s
    for old, new, n in changes:
        assert s.count(old) == n, (src, old[:70], s.count(old), n)
        s = s.replace(old, new)
    open(out + "/" + dst, "w", encoding="utf-8", newline="\n").write(s)
    print(dst, "ok")


derive("p0417b.sh", "p0417e.sh", (
    ("# p0417b (exp 0417, the next patch change):",
     "# p0417e (exp 0417, candidate B: no K1r, no probe, no watch, the SHARED backend archive): the private tree goes from\n"
     "# 0001-new13 (05fe48b6) to 0001-new14 (P_NEW14); both builds are configured against the shared backend again.\n"
     "# usage: P_NEW14=<patch md5> bash p0417e.sh\n"
     "# p0417b (exp 0417, the next patch change):", 1),
    ('[ "$(m "$HERE/0001-new10.patch")" = 33bddfa1 ] && [ "$(m "$HERE/0001-new11.patch")" = "${P_NEW11:?the new patch md5}" ]',
     '[ "$(m "$HERE/0001-new13.patch")" = 05fe48b6 ] && [ "$(m "$HERE/0001-new14.patch")" = "${P_NEW14:?the new patch md5}" ]', 1),
    ('claim "exp 0417: private rebuild of the next patch change under exp0413/p, CPU only" 40',
     'claim "exp 0417: private rebuild of candidate B (no K1r, the shared backend) under exp0413/p, CPU only" 40', 1),
    ('done < "$HERE/tree10.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 33bddfa1\'s (the hook\'s gate must be 0)"',
     'done < "$HERE/tree13.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 05fe48b6\'s"', 1),
    ('git apply -R --whitespace=nowarn "$HERE/0001-new10.patch" && git apply --whitespace=nowarn "$HERE/0001-new11.patch"',
     'git apply -R --whitespace=nowarn "$HERE/0001-new13.patch" && git apply --whitespace=nowarn "$HERE/0001-new14.patch"', 1),
    ('done < "$HERE/tree11.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"',
     'done < "$HERE/tree14.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"', 1),
    ('echo "tree: $(wc -l < "$HERE/tree11.md5") patched files match the laptop\'s (0001-new11)"',
     'echo "tree: $(wc -l < "$HERE/tree14.md5") patched files match the laptop\'s (0001-new14)"', 1),
    ('    [ -f "$d/build.ninja" ] || die "no build dir $d (run p0413.sh first)"\n',
     '    [ -f "$d/build.ninja" ] || die "no build dir $d (run p0413.sh first)"\n'
     '    cfg "$d" "$x" || die "configure $v against the SHARED backend: $(tail -2 "$d.configure.log" | tr \'\\n\' \' \' | cut -c1-240)"\n'
     '    grep -q "KYTY_BC5_BACKEND_BUILD:[A-Z]*=$BBLD\\$" "$d/CMakeCache.txt" || die "$v is not configured against the shared backend build $BBLD"\n', 1),
    ("KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT", "KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_DIRECT_RESET_LABELS_ADD", 1),
    ('    grep -aqF -- "KYTY_BC5_AMM_SETBUFFER_TEST" "$b" && die "$v holds the set-buffer test hook (the gate is not 0)"\n',
     '    grep -aqF -- "KYTY_BC5_AMM_SETBUFFER_TEST" "$b" && die "$v holds the set-buffer test hook (the gate is not 0)"\n'
     '    grep -aqF -- "BC5_GUARD_K1R" "$b" && die "$v holds K1r (candidate B must not)"\n', 1),
))
derive("chk0417d.sh", "chk0417e.sh", (
    ("# chk0417d (after the reboot of 11:32):",
     "# chk0417e: candidate B (P_NEW14: no K1r, no probe, no watch, the shared backend archive), the SHORT re-check: ASTRO BOT\n"
     "# plain and DEFAULTS=0, the walk once, the cutscene arm once, lean. usage (on the box, detached): P_NEW14=<patch md5> chk0417e.sh\n"
     "# chk0417d (after the reboot of 11:32):", 1),
    ('    : "${P_NEW13:?the patch md5}"\n    (cd "$P/kit" && P_NEW13=$P_NEW13 bash ./p0417d.sh) > "$P/p0417d.log" 2>&1',
     '    : "${P_NEW14:?the patch md5}"\n    (cd "$P/kit" && P_NEW14=$P_NEW14 bash ./p0417e.sh) > "$P/p0417e.log" 2>&1', 1),
    ('"$P/p0417d.log"', '"$P/p0417e.log"', 4),
    ("chk0417d", "chk0417e", 7),
    ('chain_claim "exp 0417 fold with K1R default off: private build,', 'chain_claim "exp 0417 candidate B (no K1r, shared backend): private build,', 1),
    ("})\" 85 ||", "})\" 50 ||", 1),
    ("astro d1${X}a\nastro d2${X}a\nastro d3${X}d KYTY_BC5_SWITCH_DEFAULTS=0\n", "astro e1${X}a\nastro e3${X}d KYTY_BC5_SWITCH_DEFAULTS=0\n", 1),
    ("second d4${X}\nsecond d5${X}\nsecond d6${X}cut ", "second e4${X}\nsecond e6${X}cut ", 1),
    ('bash ./start0413l.sh d7${X} lean 120 | grep "^d7${X} ")', 'bash ./start0413l.sh e7${X} lean 120 | grep "^e7${X} ")', 1),
    ("second d9${X}eop BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1\n", "", 1),
))
