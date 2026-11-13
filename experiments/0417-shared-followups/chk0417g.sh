#!/usr/bin/env bash
# BC5 exp 0417, after the maintainer's answer of 2026-11-13 ("Tak": he pressed a pad button at the start screen in the
# runs d4p, f4p and f8ctl, so those three are void as memory measurements). One chain, one lock line:
#   g1ctl   the SHARED normal build fe0933c0, the second title's walk to G+240 (the control). It must stay on the
#           start screen until the runner's own cross and have NO pad key before it; otherwise the chain stops.
#   g4p     candidate B (27b6416f), the same walk
#   g6pcut  candidate B, the cutscene arm (exp 0412's snapshot of 2026-11-13, slot 4, no input, 240 s)
#   g7p     candidate B lean, 120 s
#   then    save0417.sh <list> (the ASTRO BOT save-memory counts), under the same lock line
# New here: during every second-title run evtest records the key events of every joystick under /dev/input/by-id
# (the runner's own keys do not pass through evdev, so every line is a human's or a device's), and the flip log is
# read for the lowest flips/s between 50 s and 84 s (the start screen holds ~30 or more until the runner's cross).
# usage (on the box, detached): chk0417g.sh [save list]
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() { padstop; chain_release; }
chain_claim "exp 0417: control on the shared build, candidate B walk + cutscene arm + lean, then ASTRO BOT save counts" 90 || { echo "chk0417g ended $(date +%T): NOT STARTED"; exit 1; }
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
second g1ctl "$SN" "$MS"
[ "$OK" = 1 ] && [ "$PADN" = 0 ] && [ "${LOWF%% *}" != none ] && [ "${LOWF%% *}" -ge 20 ] || { echo "chk0417g STOP: the control is not the morning's (clean $OK, pad keys $PADN, lowest flips $LOWF)"; echo "chk0417g ended $(date +%T): STOPPED at the control"; exit 1; }
echo "control: as the morning's (start screen held to the runner's cross, no pad key, clean to G+240)"
second g4p "$BN" "$MN"
[ "$OK" = 1 ] && second g6pcut "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1
if [ "$OK" = 1 ]; then
    line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh g7p lean 120 | grep "^g7p ")
    echo "$line"
    case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0; echo "g7p: the lean start was not clean" ;; esac
    case "$line" in *"kernel lines 0"*) ;; *) KERN=1 ;; esac
fi
echo "second title: $([ "$OK" = 1 ] && echo "all clean" || echo "NOT all clean")"
[ "$KERN" = 0 ] || { echo "chk0417g ended $(date +%T): STOPPED (a kernel line or a fault record)"; exit 1; }
[ -n "${1:-}" ] && bash ./save0417.sh "$1"
echo "chk0417g ended $(date +%T)"
