#!/usr/bin/env bash
# BC5 exp 0419: the private acceptance of the test build T (test-build.md), made from chk0419f.sh by sed: one walk to
# G+240 (T defaults, every new switch unset), one cutscene arm (320 s), ASTRO BOT 120 s x3 from a fresh save directory
# and 30 s on the kept bad save, lean 120 s. One chain, one lock line; RT on (the saves' setting).
# usage (on the box, detached): chk0419t.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() { padstop; chain_release; }
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419 test build T, private: ASTRO BOT x4, the second title x6 (walk, walk K1R off, cutscene arm; twice each), lean" 60 || { echo "chk0419t ended $(date +%T): NOT STARTED"; exit 1; }
trap fin EXIT
recs() { find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$1" 2> /dev/null | wc -l; }
BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; SN=$W/kytyplus-build/src/kyty_emulator
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1); MS=$(md5sum < "$SN" | cut -d' ' -f1)
echo "binaries: B normal $MN, B lean $ML, shared normal $MS"
KERN=0; OK=1
second() {  # tag, binary, its md5, then words and N_* settings; sets OK=0 when not clean, KERN=1 on a kernel line
    local tag=$1 bin=$2 want=$3 t0 d n=0; t0=$(date +%s); shift 3
    local envs=() words=() w
    for w in "$@"; do case "$w" in N_*) envs+=("$w") ;; *) words+=("$w") ;; esac; done
    : > "$R/$tag-pad.txt"
    for d in /dev/input/by-id/*-event-joystick; do
        [ -e "$d" ] || continue
        n=$((n + 1))
        stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$tag-pad.txt" &
        PADS+=($!)
    done
    local line; line=$(env "${envs[@]}" P_BIN="$bin" P_WANT="$want" P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip "${PLAYS:-240}" KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "${words[@]}" | grep "^$tag ")
    padstop; pkill -u "$USER" -x evtest 2> /dev/null
    local J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag journal: would-learn $(grep -a -c '^would learn' "$J" 2> /dev/null), timeout-fault $(grep -a -c '^timeout: fault' "$J" 2> /dev/null), fault record lines $(grep -a -c 'fault record (exp 0412' "$J" 2> /dev/null)"
    grep -a '^lazy release (exp 0401 e7): t ' "$J" 2> /dev/null | sed -n '2,3p' | sed "s/^lazy release (exp 0401 e7)/$tag import/" | cut -c1-230
    echo "$tag route: $(grep -h 'route:' "$R/$tag-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300); watchdog: $(tail -1 "$R/$tag-watchdog.txt" 2> /dev/null | cut -c21-140)"
    echo "$tag at ~104 s: $(awk -F'|' '$1+0 >= 100 {print "avail,swap,io" $2 "| psi" $3 "| gtt" $5; exit}' "$R/$tag-sampler.txt" 2> /dev/null | cut -c1-150)"
    echo "$tag at ~60 s: $(awk -F'|' '$1+0 >= 60 {print "avail,swap,io" $2 "| psi" $3 "| gtt" $5; exit}' "$R/$tag-sampler.txt" 2> /dev/null | cut -c1-150)"
    LOWF=$(awk '$1 >= 50 && $1 <= 84 { if (m == "" || $2 < m) { m = $2; t = $1 } } END { print (m == "" ? "none" : m " at " t " s") }' "$R/$tag-fps.txt" 2> /dev/null)
    PADN=$(wc -l < "$R/$tag-pad.txt")
    echo "$tag input: $n joystick(s) watched, pad key presses $PADN$( [ "$PADN" = 0 ] || awk -v t0="$t0" '{ sub(",", "", $3); printf " (first %.0f s after the run began: %s)", $3 - t0, $0; exit }' "$R/$tag-pad.txt" | cut -c1-200); lowest flips/s in 50..84 s: $LOWF"
    echo "$line"
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
    [ "$(recs "$t0")" = 0 ] || { echo "$tag: a NEW FAULT RECORD since it began: a finding, read record.txt under $FR"; OK=0; KERN=1; return; }
    case "$line" in *"ended at G+${PLAYS:-240}"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "$tag: NOT a clean run" ;; esac
    sleep 5
}
grep -aqF BC5_GUARD_WRITERS "$BN" && grep -aqF BC5_DIRECT_START_STATE_SKIP "$BN" || { echo "chk0419t ended $(date +%T): NOT STARTED, the private build is not the test build"; exit 1; }
WD=$N/wda; KEEP=$WD/_SaveData.before-chk0419t-$$; mv "$WD/_SaveData" "$KEEP" && mkdir "$WD/_SaveData" || exit 1
back() { rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"; }
astro() {  # tag, seconds, words...
    local tag=$1 secs=$2; shift 2
    line=$(P_BIN=$BN P_WANT=$MN bash ./start0413g.sh "$tag" astro "$secs" "$@" 2>&1 | tail -1); echo "$line"
    echo "$tag stderr: title line $(grep -a -c 'exp 0419: title' "$R/$tag-play.log" 2> /dev/null), sdt417 $(grep -a 'sdt417:' "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-120)"
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
}
for t in t0a t0b t0c; do
    astro "$t" 120
    case "$line" in *"PASS: ran 120 s"*"crash lines 0"*) ;; *) OK=0; break ;; esac
done
echo "ASTRO BOT start-state lines (exp 0418): $(grep -a -c -i 'start state\|start-state' "$R/t0a-play.log" 2> /dev/null); first: $(grep -a -i -m1 'start state\|start-state' "$R/t0a-play.log" 2> /dev/null | cut -c1-200)"
rm -rf "$WD/_SaveData"; cp -a "$WD/_SaveData.sm0" "$WD/_SaveData"
astro t0f 30 KYTY_BC5_SAVEDATA_TRANSFER_FIX=1
case "$line" in *"PASS: ran 30 s"*"crash lines 0"*) echo "t0f: the start PASSES with the fix" ;; *) echo "t0f: the fix does NOT cure the start"; OK=0 ;; esac
back
[ "$KERN" = 0 ] || { echo "chk0419t ended $(date +%T): STOPPED (a kernel line in an ASTRO BOT start)"; exit 1; }
after() {  # tag: the lines exp 0412 and exp 0418 read
    local tag=$1 J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag title table: $(grep -a 'exp 0419: title' "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-160)"
    echo "$tag start state: $(grep -a -i -m1 'start state\|start-state' "$J" "$R/$tag-play.log" 2> /dev/null | head -1 | cut -c1-220)"
    echo "$tag last timing split: $(grep -a '^timing split' "$J" 2> /dev/null | tail -1 | cut -c1-320)"
    echo "$tag frame-profile lines over 500 ms: $(grep -a -i 'frame profile\|frame-profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | wc -l); the largest: $(grep -a -i 'frame profile\|frame-profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | sort -k6,6 -n | tail -2 | cut -c1-200 | tr '\n' ';')"
}
for r in a; do
    [ "$KERN" = 0 ] || break
    second t1$r "$BN" "$MN"; after t1$r
    [ "$PADN" = 0 ] || echo "t1$r: VOID as a measurement, a foreign pad key"
    [ "$KERN" = 0 ] || break
    PLAYS=320 second t2cut$r "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1; after t2cut$r
done
if [ "$KERN" = 0 ]; then
    line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh t3l lean 120 | grep "^t3l ")
    echo "$line"
    case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "t3l: the lean start was not clean" ;; esac
fi
echo "test build T, private: $([ "$OK" = 1 ] && [ "$KERN" = 0 ] && echo "all runs clean (the pass marks are in the lines above)" || echo "NOT all clean (OK $OK, kernel $KERN)")"
echo "chk0419t ended $(date +%T)"
