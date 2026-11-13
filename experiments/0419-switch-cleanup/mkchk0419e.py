#!/usr/bin/env python3
"""BC5 experiment 0419: the private check chain of candidate E, made from exp 0417's chk0417g.sh (its lock, its pad
recorder and its `second` function are kept as they are; the list of runs is new).
usage: mkchk0419e.py <chk0417g.sh> <out dir>"""
import sys

src, out = sys.argv[1:3]
s = open(src, encoding="utf-8", newline="").read()
assert "\r" not in s
i, j = s.index("# BC5 exp 0417, after the maintainer"), s.index("set -u\n")
k = s.index('second g1ctl "$SN" "$MS"\n')
head = s[:i] + r'''# BC5 exp 0419: candidate E on the PRIVATE builds (exp0413/p; build it first with p0419e.sh). One chain, one lock line;
# every second-title run records pad keys (a foreign key voids the run). Private test directories only.
#   k0a     ASTRO BOT 120 s, a fresh private save directory. The title table must NOT speak (no "exp 0419: title" line).
#   k0x     ASTRO BOT 30 s on the kept bad save (wda/_SaveData.sm0), the fix off: the fault of exp 0417 section 15 is expected
#   k0f     the same with KYTY_BC5_SAVEDATA_TRANSFER_FIX=1: the start must pass and name the transfer as NOT_FOUND
#   k1      the second title's walk to G+240 with E's defaults (K1R on since the maintainer's play of 2026-11-13)
#   k1off   the same with BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0 (the comparison with B itself is B's own run: exp 0417's g1ctl / sw1)
#   k2cut   the cutscene arm (exp 0412's snapshot of 2026-11-13, slot 4, no input, 240 s), E's defaults
#   k3l     lean 120 s
# Each second-title run prints the title table's line (rows, taken, already set).
# usage (on the box, detached): chk0419e.sh
''' + s[j:k]
head = head.replace('chain_claim "exp 0417: control on the shared build, candidate B walk + cutscene arm + lean, then ASTRO BOT save counts" 90',
                    'chain_claim "exp 0419 candidate E, private: ASTRO BOT (3 starts), the second title walk twice + cutscene arm, lean" 45')
assert "exp 0419 candidate E, private" in head
tail = r'''grep -aqF KYTY_BC5_TITLE_DEFAULTS "$BN" && grep -aqF KYTY_BC5_SAVEDATA_TRANSFER_FIX "$BN" || { echo "chk0419e ended $(date +%T): NOT STARTED, the private build is not candidate E"; exit 1; }
WD=$N/wda; KEEP=$WD/_SaveData.before-chk0419e-$$; mv "$WD/_SaveData" "$KEEP" && mkdir "$WD/_SaveData" || exit 1
back() { rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"; }
astro() {  # tag, seconds, words...
    local tag=$1 secs=$2; shift 2
    line=$(P_BIN=$BN P_WANT=$MN bash ./start0413g.sh "$tag" astro "$secs" "$@" 2>&1 | tail -1); echo "$line"
    echo "$tag stderr: title line $(grep -a -c 'exp 0419: title' "$R/$tag-play.log" 2> /dev/null), sdt417 $(grep -a 'sdt417:' "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-120)"
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
}
astro k0a 120
case "$line" in *"PASS: ran 120 s"*"crash lines 0"*) ;; *) OK=0 ;; esac
rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData"
astro k0x 30
case "$line" in *"ENDED BY ITSELF"*) echo "k0x: the fault is there without the fix, as expected" ;; *) echo "k0x: UNEXPECTED, the bad save did not fault without the fix" ;; esac
rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData"
astro k0f 30 KYTY_BC5_SAVEDATA_TRANSFER_FIX=1
case "$line" in *"PASS: ran 30 s"*"crash lines 0"*) echo "k0f: the start PASSES with the fix" ;; *) echo "k0f: the fix does NOT cure the start"; OK=0 ;; esac
back
[ "$KERN" = 0 ] || { echo "chk0419e ended $(date +%T): STOPPED (a kernel line in an ASTRO BOT start)"; exit 1; }
title() { echo "$1 title table: $(grep -a 'exp 0419: title' "$R/$1-play.log" 2> /dev/null | head -1 | cut -c1-160)"; }
second k1 "$BN" "$MN"; title k1
[ "$PADN" = 0 ] || echo "k1: VOID as a measurement, a foreign pad key"
if [ "$KERN" = 0 ]; then second k1off "$BN" "$MN" BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0; title k1off; fi
if [ "$KERN" = 0 ]; then second k2cut "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1; title k2cut; fi
if [ "$KERN" = 0 ]; then
    line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh k3l lean 120 | grep "^k3l ")
    echo "$line"
    case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "k3l: the lean start was not clean" ;; esac
fi
echo "candidate E, private: $([ "$OK" = 1 ] && [ "$KERN" = 0 ] && echo "all as expected" || echo "NOT all as expected (OK $OK, kernel $KERN)")"
echo "chk0419e ended $(date +%T)"
'''
t = head + tail
t = t.replace("chk0417g", "chk0419e")
open(out + "/chk0419e.sh", "w", encoding="utf-8", newline="\n").write(t)
print("chk0419e.sh ok")
