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
# usage (on the box, detached): series0419f.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0413; N=$E/n; P=$E/p; R=$N/raw; FR=$HOME/bc5-data/captures/faults
cd "$N" || exit 1
. "$N/chainlock0417.inc"
PADS=()
padstop() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); }
fin() { padstop; chain_release; }
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419: the deciding series for F's hang at 601 s: five walks to G+620 (F, F K1R off, F without exp 0418's new rows, shared B, F + scan + writers); about 70 minutes" 78 || { echo "series0419f ended $(date +%T): NOT STARTED"; exit 1; }
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
[ "$MN" = 1a2900a08142311961050686395c4054 ] && [ "$MS" = 51af1ed78e84291caf5ee042ea82c46d ] || { echo "series0419f ended $(date +%T): NOT STARTED, the private build is not F's 1a2900a0 or the shared build is not B's 51af1ed7"; exit 1; }
BOOT=$(cat /proc/sys/kernel/random/boot_id)
ZL=$W/exp0412/play-pkg-0412.sh; [ -f "$ZL" ] || ZL=$W/play-pkg.sh
ZN=$(sed -n 's/^export BC5_DIRECT_EAGER_NAMES="\(.*\)"$/\1/p' "$ZL" | head -1)
arm() {  # tag, binary, md5, words...
    local tag=$1 t0 J d; t0=$(date +%s); OK=1; KERN=0
    echo "== $(date +%T) $tag: $(shift 3; echo "${*:-no extra word}" | cut -c1-200)"
    PLAYS=620 second "$@"
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag memory at 580-620 s:"; grep -a '^memory (exp 0401): t \(5[89][0-9]\|6[01][0-9]\)\.' "$J" 2> /dev/null | cut -c1-170
    echo "$tag frame-profile lines over 500 ms: $(grep -a 'frame profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | wc -l); last flip line t: $(grep -a 'frame profile' "$J" 2> /dev/null | tail -1 | cut -c1-40)"
    for d in $(find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$t0" 2> /dev/null | sort); do
        echo "$tag FAULT RECORD $d"
        grep -a -m1 '^what the host saw' "$d/record.txt" | cut -c1-260
        grep -a -m1 '^when' "$d/record.txt" | cut -c1-120
        grep -a -i -m6 'timed out\|acb #\|dcb #' "$d/journal-tail.txt" | cut -c1-260
    done
    echo "$tag kernel lines: $(grep -c . "$R/$tag-dmesg-after.txt" 2> /dev/null)"; grep -i 'timeout\|reset' "$R/$tag-dmesg-after.txt" 2> /dev/null | cut -c1-160 | head -4
    if grep -qi 'reset.*fail\|fail.*reset' "$R/$tag-dmesg-after.txt" 2> /dev/null; then echo "series0419f STOP after $tag: the kernel reports a failed reset"; echo "series0419f ended $(date +%T): STOPPED"; exit 1; fi
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "series0419f STOP: the boot id changed"; exit 1; }
    sleep 10
}
arm sA "$BN" "$MN"
arm sB "$BN" "$MN" BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0
arm sC "$BN" "$MN" BC5_DIRECT_START_STATE_SKIP=SPI_SHADER_REQ_CTRL_PS:GE_MIN_VTX_INDX:GE_MAX_VTX_INDX:VGT_INSTANCE_BASE_ID:VGT_GS_RINGS
arm sD "$SN" "$MS"
arm sE "$BN" "$MN" BC5_DIRECT_ZEROSCAN_AT=175,295,415,535,640 BC5_GUARD_WRITERS=1 ${ZN:+"BC5_DIRECT_ZERO_NAMES=$ZN"}
echo "series0419f ended $(date +%T): all five arms ran"
