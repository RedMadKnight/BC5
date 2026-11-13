#!/usr/bin/env bash
# BC5 exp 0419: candidate F on the PRIVATE builds (exp0413/p; build it first with p0419f.sh). One chain, one lock line;
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
# usage (on the box, detached): long0419f.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() { padstop; chain_release; }
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419 candidate F, private: the long walk to G+560 again, $# arm(s), stop at the first that is not clean" $(($# * 12 + 3)) || { echo "long0419f ended $(date +%T): NOT STARTED"; exit 1; }
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
grep -aqF BC5_GUARD_WRITERS "$BN" && grep -aqF BC5_DIRECT_START_STATE_SKIP "$BN" || { echo "long0419f ended $(date +%T): NOT STARTED, the private build is not candidate F"; exit 1; }
[ "$#" -ge 1 ] || { echo "long0419f: arms, please"; exit 1; }
for arm in "$@"; do
    tag=${arm%%,*}; rest=${arm#"$tag"}; rest=${rest#,}
    IFS=, read -r -a ws <<< "$rest"
    t0=$(date +%s)
    PLAYS=560 second "$tag" "$BN" "$MN" "${ws[@]}"
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag words: ${rest:-none: the defaults of F}; last memory line: $(grep -a '^memory (exp 0401)' "$J" 2> /dev/null | tail -1 | cut -c1-170)"
    echo "$tag frame-profile lines over 500 ms: $(grep -a 'frame profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | wc -l); fault records since it began: $(recs "$t0")"
    if [ "$OK" != 1 ] || [ "$KERN" != 0 ]; then echo "long0419f STOP at $tag: not clean (OK $OK, kernel $KERN); the arms after it were NOT run"; break; fi
done
echo "long0419f ended $(date +%T)"
