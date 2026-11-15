#!/usr/bin/env bash
# BC5 exp 0419, build W: did the lean build get slower or faster? Six lean starts of the second title, 120 s each,
# interleaved V W V W V W (V's lean binary is the copy in ~/bc5-work/exp0419/bin-V/lean, W's is the private build).
# The lean build writes no journal and no flip counter, so the measure is the process's own: between 60 s and 115 s of
# each run, the emulator's CPU time (utime + stime, all threads) and its GPU time on the gfx and compute engines (the
# drm fdinfo counters of its device files), each per second of wall time. The same start, the same save, no input.
# One lock line for the chain (start0413l.sh inherits it). usage (on the box, detached): leanspeed0419.sh <tag prefix>
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; P=$W/exp0413/p
PFX=${1:?a tag prefix, letters only}
BV=$W/exp0419/bin-V/lean/kyty_emulator; BW=$P/build-lean/src/kyty_emulator
MV=$(md5sum < "$BV" | cut -d' ' -f1); MW=$(md5sum < "$BW" | cut -d' ' -f1)
[ "$MV" != "$MW" ] || { echo "leanspeed0419: V's and W's lean binaries are the same file: NOT STARTED"; exit 1; }
cd "$N" || exit 1
. "$N/chainlock0417.inc"
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0419 build W: six lean starts of the second title, V against W (CPU and GPU time per second); about 16 minutes" 25 || { echo "leanspeed0419 ended $(date +%T): NOT STARTED"; exit 1; }
trap chain_release EXIT
export CHAIN_LOCKLINE
tick() { awk '{print $14 + $15}' "/proc/$1/stat" 2> /dev/null; }
gpu() {  # ns on the gfx and compute engines, summed over the process's drm file descriptors
    local s=0 f v
    for f in /proc/"$1"/fdinfo/*; do
        v=$(awk '$1 == "drm-engine-gfx:" || $1 == "drm-engine-compute:" {s += $2} END {print s + 0}' "$f" 2> /dev/null)
        s=$((s + ${v:-0}))
    done
    echo "$s"
}
HZ=$(getconf CLK_TCK)
measure() {  # tag: waits for the emulator, samples at 60 s and 115 s of its run
    local tag=$1 ep="" c0 c1 g0 g1
    for _ in $(seq 1 240); do ep=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
    [ -n "$ep" ] || { echo "$tag speed: no emulator"; return; }
    sleep 60; c0=$(tick "$ep"); g0=$(gpu "$ep")
    sleep 55; c1=$(tick "$ep"); g1=$(gpu "$ep")
    [ -n "$c0" ] && [ -n "$c1" ] || { echo "$tag speed: the emulator ended before 115 s"; return; }
    awk -v t="$tag" -v c0="$c0" -v c1="$c1" -v g0="$g0" -v g1="$g1" -v hz="$HZ" \
        'BEGIN { printf "%s speed: CPU %.3f s/s, GPU %.1f ms/s (60..115 s)\n", t, (c1 - c0) / hz / 55, (g1 - g0) / 1e6 / 55 }'
}
for r in a b c; do
    for v in V W; do
        tag=$PFX$v$r; bin=$BV; want=$MV; [ "$v" = W ] && { bin=$BW; want=$MW; }
        measure "$tag" > "$R/$tag-speed.txt" &
        mp=$!
        line=$(P_BIN=$bin P_WANT=$want P_WORDS=$N/words0413nz.txt bash ./start0413l.sh "$tag" lean 120 | grep "^$tag ")
        wait "$mp"
        echo "$line"; cat "$R/$tag-speed.txt"
        case "$line" in *"kernel lines 0"*) ;; *) echo "leanspeed0419 STOP after $tag: a kernel line or an unknown end"; exit 1 ;; esac
        sleep 5
    done
done
echo "leanspeed0419 ended $(date +%T): six runs"
