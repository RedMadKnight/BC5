#!/usr/bin/env bash
# BC5 exp 0417, candidate B (27b6416f; private normal 3baa8e39, lean e11ad4de): the rest of its short re-check after
# chk0417e.sh stopped at ASTRO BOT (a bad save file in the private test directory, see the README), and the control
# the top session asked for: the SHARED normal build fe0933c0 on the same walk, on the same box state.
# One lock line for the chain. Private directories only. Stops at the first unclean run or new fault record.
#   f4p     candidate B, the second title's walk to G+240
#   f6pcut  candidate B, the cutscene arm (exp 0412's snapshot of 2026-11-13, slot 4, no input, 240 s)
#   f7p     candidate B lean, 120 s
#   f8ctl   the shared normal build fe0933c0, the walk to G+240 (the control)
# After each second-title run: the journal's import lines near 60 s and 120 s (eager / data / under no view).
# usage (on the box, detached): chk0417f.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
halt() { echo "chk0417f STOP: $*"; echo "chk0417f ended $(date +%T): STOPPED"; exit 1; }
chain_claim "exp 0417 candidate B: the second title, the cutscene arm, lean, and the shared build as a control" 40 || { echo "chk0417f ended $(date +%T): NOT STARTED"; exit 1; }
recs() { find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$1" 2> /dev/null | wc -l; }
BN=$P/build-normal/src/kyty_emulator; BL=$P/build-lean/src/kyty_emulator; SN=$W/kytyplus-build/src/kyty_emulator
MN=$(md5sum < "$BN" | cut -d' ' -f1); ML=$(md5sum < "$BL" | cut -d' ' -f1); MS=$(md5sum < "$SN" | cut -d' ' -f1)
echo "binaries: B normal $MN, B lean $ML, shared normal $MS"
second() {  # tag, binary, its md5, then words and N_* settings
    local tag=$1 bin=$2 want=$3 t0; t0=$(date +%s); shift 3
    local envs=() words=() w
    for w in "$@"; do case "$w" in N_*) envs+=("$w") ;; *) words+=("$w") ;; esac; done
    local line; line=$(env "${envs[@]}" P_BIN="$bin" P_WANT="$want" P_WORDS=$N/words0413nz.txt bash ./run0413p.sh "$tag" nozeroskip 240 KYTY_BC5_LOAD_STAT="$R/$tag-loadstat.txt" "${words[@]}" | grep "^$tag ")
    local J; J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag journal: removed-line $(grep -a -c 'learned windows: removed from this build' "$J" 2> /dev/null), would-learn $(grep -a -c '^would learn' "$J" 2> /dev/null), timeout-fault $(grep -a -c '^timeout: fault' "$J" 2> /dev/null), fault record lines $(grep -a -c 'fault record (exp 0412' "$J" 2> /dev/null)"
    grep -a '^lazy release (exp 0401 e7): t ' "$J" 2> /dev/null | sed -n '2,3p' | sed "s/^lazy release (exp 0401 e7)/$tag import/" | cut -c1-230
    echo "$tag route: $(grep -h 'route:' "$R/$tag-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300); watchdog: $(tail -1 "$R/$tag-watchdog.txt" 2> /dev/null | cut -c21-140)"
    echo "$tag at ~104 s: $(awk -F'|' '$1+0 >= 100 {print "avail,swap,io" $2 "| gtt" $5; exit}' "$R/$tag-sampler.txt" 2> /dev/null | cut -c1-120)"
    echo "$line"
    [ "$(recs "$t0")" = 0 ] || halt "a new fault record since $tag began: a finding, read record.txt under $FR"
    case "$line" in *"ended at G+240"*"kernel lines 0, crash lines 0"*) ;; *) halt "not a clean run: $(echo "$line" | cut -c1-160)" ;; esac
    sleep 5
}
second f4p "$BN" "$MN"
second f6pcut "$BN" "$MN" N_SAVES=$HOME/bc5-data/saves/PPSA03671-20261113-0914-cutscene N_SLOT=4 N_NOWALK=1
t0=$(date +%s)
line=$(P_BIN=$BL P_WANT=$ML P_WORDS=$N/words0413nz.txt bash ./start0413l.sh f7p lean 120 | grep "^f7p ")
echo "$line"
case "$line" in *"PASS: ran 120 s"*"kernel lines 0, crash lines 0"*) ;; *) halt "the lean start was not clean" ;; esac
second f8ctl "$SN" "$MS"
echo "chk0417f ended $(date +%T): all clean"
