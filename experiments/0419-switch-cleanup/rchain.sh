#!/usr/bin/env bash
# exp 0419, after candidate F's acceptance chain, under ONE lock line, private directories only:
#   1. F's two private binaries are kept under ~/bc5-work/exp0413/kept/
#   2. exp 0412's extra arm (outside the acceptance): wall0419f.sh, the walk to G+560 with the zero scan and the writers catcher
#   3. a private DIAGNOSTIC build, F + exp 0418's RSRC2 journal (p0419r.sh), and its two arms with BC5_DIRECT_RSRC2_JOURNAL=1:
#      r1 the second title's walk to G+240, r0a ASTRO BOT 120 s (frame numbers not comparable); the [bc5-rsrc2] lines
#      and both titles' start-state and /dev/gc lines go to raw/rsrc2-*.txt and raw/startstate-*.txt
#   4. the private tree and builds go back to F (p0419fb.sh); the binaries must read as F's again
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; P=$W/exp0413/p; R=$N/raw; KEPT=$W/exp0413/kept
FN=1a2900a08142311961050686395c4054; FL=034bf107b7d93bc3a924a416b4bb2efb
cd "$N" || exit 1
. "$N/chainlock0417.inc"
m() { md5sum < "$1" | cut -d' ' -f1; }
chain_claim "exp 0419: after F's acceptance: the wall walk (exp 0412), a diagnostic build with exp 0418's RSRC2 journal and its two arms, then back to F; private dirs" 60 || { echo "rchain ended $(date +%T): NOT STARTED"; exit 1; }
BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator
[ "$(m "$BN")" = "$FN" ] && [ "$(m "$BL")" = "$FL" ] || { echo "rchain ended $(date +%T): NOT STARTED, the private builds are not F's"; exit 1; }
mkdir -p "$KEPT" && cp -p "$BN" "$KEPT/kyty_emulator-F-d9af28ca-${FN:0:8}" && cp -p "$BL" "$KEPT/kyty_emulator-lean-F-d9af28ca-${FL:0:8}" && [ "$(m "$KEPT/kyty_emulator-F-d9af28ca-${FN:0:8}")" = "$FN" ] || { echo "rchain ended $(date +%T): the copies of F's binaries do not read back"; exit 1; }
echo "F's binaries kept: $KEPT/kyty_emulator-F-d9af28ca-${FN:0:8}, kyty_emulator-lean-F-d9af28ca-${FL:0:8}"
# the start-state lines of the acceptance runs, for exp 0418 (both titles)
for t in m0a m1a m2cuta; do
    echo "== $t"; grep -a "bc5-direct: start state (exp 0418)\|bc5-direct: /dev/gc " "$R/$t-play.log" 2> /dev/null | sort | uniq -c | cut -c1-300
done > "$R/startstate-F.txt"
echo "start-state lines of F's runs: $(grep -c . "$R/startstate-F.txt") lines in $R/startstate-F.txt"
echo "== $(date +%T) the wall walk"
bash ./wall0419f.sh 2>&1 | grep -v " import: \| journal: \| route: \| at ~" | cut -c1-300
echo "== $(date +%T) the diagnostic build"
(cd "$P/kit" && P_NEW19=e794fbe6 bash ./p0419r.sh) > "$P/p0419r.log" 2>&1 || { echo "the diagnostic build failed:"; tail -6 "$P/p0419r.log" | cut -c1-300; echo "rchain ended $(date +%T): DIAGNOSTIC BUILD FAILED (the private tree may be between F and the diagnostic build)"; exit 1; }
tail -1 "$P/p0419r.log" | cut -c1-200
DN=$(m "$BN")
line=$(P_BIN=$BN P_WANT=$DN P_WORDS=$N/words0413nz.txt bash ./run0413p.sh r1 nozeroskip 240 BC5_DIRECT_RSRC2_JOURNAL=1 | grep "^r1 ")
echo "$line (frame numbers not comparable)"
grep -a "\[bc5-rsrc2\]" "$R/r1-play.log" > "$R/rsrc2-second-title.txt" 2> /dev/null
echo "r1 [bc5-rsrc2] lines: $(wc -l < "$R/rsrc2-second-title.txt"); last totals: $(grep -a totals "$R/rsrc2-second-title.txt" | tail -1 | cut -c1-240)"
case "$line" in *"kernel lines 0"*) ;; *) echo "rchain: a kernel line in r1; the ASTRO BOT arm is skipped" ; SKIP=1 ;; esac
if [ "${SKIP:-0}" = 0 ]; then
    WD=$N/wda; KEEP=$WD/_SaveData.before-rchain-$$; mv "$WD/_SaveData" "$KEEP" && mkdir "$WD/_SaveData"
    line=$(P_BIN=$BN P_WANT=$DN bash ./start0413g.sh r0a astro 120 BC5_DIRECT_RSRC2_JOURNAL=1 2>&1 | tail -1); echo "$line (frame numbers not comparable)"
    rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"
    grep -a "\[bc5-rsrc2\]" "$R/r0a-play.log" > "$R/rsrc2-astro.txt" 2> /dev/null
    echo "r0a [bc5-rsrc2] lines: $(wc -l < "$R/rsrc2-astro.txt"); last totals: $(grep -a totals "$R/rsrc2-astro.txt" | tail -1 | cut -c1-240)"
fi
echo "== $(date +%T) back to F"
(cd "$P/kit" && P_NEW19=e794fbe6 bash ./p0419fb.sh) > "$P/p0419fb.log" 2>&1 || { echo "the build back to F failed:"; tail -6 "$P/p0419fb.log" | cut -c1-300; echo "rchain ended $(date +%T): THE PRIVATE BUILDS ARE NOT F's (F's binaries are in $KEPT)"; exit 1; }
echo "private builds now: normal $(m "$BN"), lean $(m "$BL") (F's: $FN, $FL: $([ "$(m "$BN")" = "$FN" ] && [ "$(m "$BL")" = "$FL" ] && echo "the SAME" || echo "DIFFERENT; F's binaries are in $KEPT"))"
echo "rchain ended $(date +%T)"
