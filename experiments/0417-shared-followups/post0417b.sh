#!/usr/bin/env bash
# BC5 exp 0417: the checks on the SHARED builds after candidate B's swap (int0417b.sh). Made from chk0417g.sh by hand.
# One chain, one lock line; every second-title run records pad keys (a foreign key voids the run).
#   h0a     ASTRO BOT 120 s on the shared normal build (a fresh private test save directory, no key)
#   h1      the second title's walk to G+240
#   h2cut   the cutscene arm (exp 0412's snapshot of 2026-11-13, slot 4, no input, 240 s)
#   h3l     the shared lean build, 120 s
#   h4eop   the walk once more with BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1 (the EOP count, never run yet)
# Then, by hand and with the maintainer at the box: the replug series (run0391.sh with pins0391 for the shared build).
# usage (on the box, detached): P_N=<expected shared normal md5> P_L=<expected shared lean md5> post0417b.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() { padstop; chain_release; }
: "${P_N:?the expected shared normal md5}" "${P_L:?the expected shared lean md5}"
chain_claim "exp 0417: checks on the shared builds after candidate B's swap (ASTRO BOT, walk, cutscene arm, lean, EOP count)" 45 || { echo "post0417b ended $(date +%T): NOT STARTED"; exit 1; }
trap fin EXIT
recs() { find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$1" 2> /dev/null | wc -l; }
BN=$W/kytyplus-build/src/kyty_emulator; BL=$W/kytyplus-build-lean/src/kyty_emulator; SN=$BN
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1); MS=$(md5sum < "$SN" | cut -d' ' -f1)
echo "shared binaries: normal $MN, lean $ML"
[ "$MN" = "$P_N" ] && [ "$ML" = "$P_L" ] || { echo "post0417b ended $(date +%T): NOT STARTED, the shared builds are not the expected ones"; exit 1; }
WD=$N/wda; KEEP=$WD/_SaveData.before-post0417b-$$; mv "$WD/_SaveData" "$KEEP" && mkdir "$WD/_SaveData" || exit 1
line=$(P_BIN=$BN P_WANT=$MN bash ./start0413g.sh h0a astro 120 2>&1 | tail -1); echo "$line"
echo "h0a save-memory file: $(md5sum < "$WD/_SaveData/PPSA21564/sce_sdmemory/memory.dat" 2> /dev/null | cut -c1-8) (1fa391a4 with no key)"
rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"
case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) echo "post0417b ended $(date +%T): STOPPED at ASTRO BOT"; exit 1 ;; esac
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
    local line; line=$(env "${envs[@]}" P_BIN="$bin" P_WANT="$want" P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip 240 KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "${words[@]}" | grep "^$tag ")
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
    case "$line" in *"ended at G+240"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "$tag: NOT a clean run" ;; esac
    sleep 5
}
second h1 "$BN" "$MN"
[ "$PADN" = 0 ] || echo "h1: VOID as a measurement, a foreign pad key"
[ "$OK" = 1 ] && second h2cut "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1
if [ "$OK" = 1 ]; then
    line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh h3l lean 120 | grep "^h3l ")
    echo "$line"
    case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "h3l: the lean start was not clean" ;; esac
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
fi
echo "second title: $([ "$OK" = 1 ] && echo "all clean" || echo "NOT all clean")"
[ "$KERN" = 0 ] || { echo "post0417b ended $(date +%T): STOPPED (a kernel line or a fault record)"; exit 1; }
if [ "$OK" = 1 ]; then
    second h4eop "$BN" "$MN" BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_EOP_STAT=1
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/h4eop-journal.txt" 2> /dev/null); echo "h4eop EOP lines: $(grep -a -i 'eop stat\|EOP_STAT' "$J" 2> /dev/null | tail -2 | cut -c1-200)"
fi
echo "post0417b ended $(date +%T)"
