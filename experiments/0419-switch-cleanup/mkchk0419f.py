#!/usr/bin/env python3
"""BC5 experiment 0419: the private check chain of candidate F, made from chk0419e.sh (its lock, pad recorder, `second`
and `astro` functions stay; the list of runs is new; tags begin with m).
The top session's order of 2026-11-13 for F: the walk, the walk with K1r and its filter off, and the cutscene arm
TWICE each; pass = exp 0412's "want" step under 2 ms per full sync with K1r on, and the longest gap in the menu as on B
(no gap over about 700 ms outside the load at 98-100 s); ASTRO BOT three times; lean. Each second-title run prints
its last "timing split" line and its frame-profile lines over 500 ms (exp 0412 reads them).
usage: mkchk0419f.py <chk0419e.sh> <out dir> [NAME=VALUE ... words for one extra walk arm (exp 0418's journal)]"""
import sys

src, out, extra = sys.argv[1], sys.argv[2], sys.argv[3:]
s = open(src, encoding="utf-8", newline="").read()
assert "\r" not in s
i, j = s.index("# BC5 exp 0419: candidate E on the PRIVATE builds"), s.index("set -u\n")
k = s.index("astro k0a 120\n")
head = s[:i] + """# BC5 exp 0419: candidate F on the PRIVATE builds (exp0413/p; build it first with p0419f.sh). One chain, one lock line;
# every second-title run records pad keys (a foreign key voids the run). Private test directories only.
#   m0a m0b m0c  ASTRO BOT 120 s three times, from a fresh private save directory (the title table must NOT speak)
#   m0f          ASTRO BOT 30 s on the kept bad save with KYTY_BC5_SAVEDATA_TRANSFER_FIX=1 (must pass)
#   m1a m1b      the second title's walk to G+240, F's defaults (K1R and its filter on)
#   m1offa m1offb  the same with BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0
#   m2cuta m2cutb  the cutscene arm (exp 0412's snapshot of 2026-11-13, slot 4, no input, 320 s)
#   m3l          lean 120 s
#   m4x          (only when words are given to the generator) one more walk with them: exp 0418's journal, not comparable
# After each second-title run: the title table's line, the last "timing split" line and the frame-profile lines over
# 500 ms (field 6) of its journal. Pass marks are exp 0412's to read: "want" under 2 ms per full sync with K1r on.
# usage (on the box, detached): chk0419f.sh
""" + s[j:k]
for a, b in (("exp 0419 candidate E, private: ASTRO BOT (3 starts), the second title walk twice + cutscene arm to its end, lean, the wall walk to G+560\" 65",
              "exp 0419 candidate F, private: ASTRO BOT x4, the second title x6 (walk, walk K1R off, cutscene arm; twice each), lean\" 60"),
             ('echo "chk0419e ended $(date +%T): NOT STARTED, the private build is not candidate E"', 'echo "chk0419f ended $(date +%T): NOT STARTED, the private build is not candidate F"'),
             ('grep -aqF KYTY_BC5_TITLE_DEFAULTS "$BN" && grep -aqF KYTY_BC5_SAVEDATA_TRANSFER_FIX "$BN" ||', 'grep -aqF BC5_GUARD_WRITERS "$BN" && grep -aqF BC5_DIRECT_START_STATE_SKIP "$BN" ||')):
    assert head.count(a) == 1, a
    head = head.replace(a, b)
head = head.replace("before-chk0419e", "before-chk0419f")
words = " ".join('"%s"' % w for w in extra)
tail = r'''for t in m0a m0b m0c; do
    astro "$t" 120
    case "$line" in *"PASS: ran 120 s"*"crash lines 0"*) ;; *) OK=0; break ;; esac
done
echo "ASTRO BOT start-state lines (exp 0418): $(grep -a -c -i 'start state\|start-state' "$R/m0a-play.log" 2> /dev/null); first: $(grep -a -i -m1 'start state\|start-state' "$R/m0a-play.log" 2> /dev/null | cut -c1-200)"
rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData"
astro m0f 30 KYTY_BC5_SAVEDATA_TRANSFER_FIX=1
case "$line" in *"PASS: ran 30 s"*"crash lines 0"*) echo "m0f: the start PASSES with the fix" ;; *) echo "m0f: the fix does NOT cure the start"; OK=0 ;; esac
back
[ "$KERN" = 0 ] || { echo "chk0419f ended $(date +%T): STOPPED (a kernel line in an ASTRO BOT start)"; exit 1; }
after() {  # tag: the lines exp 0412 and exp 0418 read
    local tag=$1 J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag title table: $(grep -a 'exp 0419: title' "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-160)"
    echo "$tag start state: $(grep -a -i -m1 'start state\|start-state' "$J" "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-220)"
    echo "$tag last timing split: $(grep -a '^timing split' "$J" 2> /dev/null | tail -1 | cut -c1-320)"
    echo "$tag frame-profile lines over 500 ms: $(grep -a -i 'frame profile\|frame-profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | wc -l); the largest: $(grep -a -i 'frame profile\|frame-profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | sort -k6,6 -n | tail -2 | cut -c1-200 | tr '\n' ';')"
}
for r in a b; do
    [ "$KERN" = 0 ] || break
    second m1$r "$BN" "$MN"; after m1$r
    [ "$PADN" = 0 ] || echo "m1$r: VOID as a measurement, a foreign pad key"
    [ "$KERN" = 0 ] || break
    second m1off$r "$BN" "$MN" BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0; after m1off$r
    [ "$KERN" = 0 ] || break
    PLAYS=320 second m2cut$r "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1; after m2cut$r
done
if [ "$KERN" = 0 ]; then
    line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh m3l lean 120 | grep "^m3l ")
    echo "$line"
    case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "m3l: the lean start was not clean" ;; esac
fi
''' + ('''if [ "$KERN" = 0 ]; then   # exp 0418's one-off journal: its own arm, frame numbers not comparable
    second m4x "$BN" "$MN" ''' + words + '''; after m4x
fi
''' if extra else '') + r'''echo "candidate F, private: $([ "$OK" = 1 ] && [ "$KERN" = 0 ] && echo "all runs clean (the pass marks are in the lines above)" || echo "NOT all clean (OK $OK, kernel $KERN)")"
echo "chk0419f ended $(date +%T)"
'''
t = (head + tail).replace("chk0419e", "chk0419f")
open(out + "/chk0419f.sh", "w", encoding="utf-8", newline="\n").write(t)
print("chk0419f.sh ok")
