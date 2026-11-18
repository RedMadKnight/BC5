#!/usr/bin/env bash
# BC5 exp 0432: the smokes of the private builds lg (normal) and lgl (lean) made by "box0432.sh buildl" on the shared
# patch ef2ff54f (2026-11-18): the drop record, KICK out of lean, NOWAIT readable in lean. Four runs, RT on:
#   1. ASTRO BOT, lgl, 200 s (exp 0431's astro0431.sh, x = XBIN, the build's defaults)
#   2. ASTRO BOT, lg, 200 s
#   3. the second title, lgl, 300 s by time (exp 0428's lean0428.sh with the binary changed; nothing else)
#   4. the second title, lg, the 09:46 scene 300 s (scene0432.sh arm T: the d432 counter lines)
# Each step takes and releases its own BOX-LOCK line. Stops at the first run that is not clean or at
# ~/bc5-work/exp0432/STOP. usage (on the box, detached): bash ~/bc5-work/exp0432/kit/smokel432.sh <n>   (tags *432L<n>)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; E=$W/exp0432; N=$W/exp0413/n; n=${1:?a run number}
LG=$E/lg/kyty_emulator; LGL=$E/lgl/kyty_emulator
[ -x "$LG" ] && [ -x "$LGL" ] || { echo "no private builds"; exit 1; }
k0() { sudo -n dmesg | grep -ci 'amdgpu.*\(timeout\|reset\)'; }
K=$(k0)
echo "== $(date +%T) smokel432: lg $(md5sum < "$LG" | cut -c1-8), lgl $(md5sum < "$LGL" | cut -c1-8); amdgpu timeout/reset lines before: $K"
for a in "a432L$n:$LGL" "a432N$n:$LG"; do
    t=${a%%:*}; b=${a#*:}
    echo "== $(date +%T) $t ASTRO BOT 200 s ($b)"
    (cd "$W/exp0431" && XBIN=$b bash astro0431.sh 200 "$t:x:D") | tee "$E/smoke-$t.out"
    grep -q "$t: PASS" "$E/smoke-$t.out" || { echo "$t not a PASS: stopped"; exit 1; }
    [ -e "$E/STOP" ] && exit 1
done
T=l432L$n
echo "== $(date +%T) $T second title lgl 300 s"
cd "$N" || exit 1
CMD=$N/cmd-$T.txt
{ printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
  c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
  printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
P_BIN=$LGL P_WANT=$(md5sum < "$LGL" | cut -d' ' -f1) P_WORDS=$N/words0413nz.txt bash "$W/exp0428/start0428l.sh" "$T" lean 300 KYTY_BC5_INPUT_CMD="$CMD" | grep "^$T " | tee "$E/smoke-$T.out"
grep -q "PASS: ran" "$E/smoke-$T.out" || { echo "$T not a PASS: stopped"; exit 1; }
[ -e "$E/STOP" ] && exit 1
echo "== $(date +%T) second title lg, the scene 300 s"
SNAP=$HOME/bc5-data/saves/PPSA03671-20261117-0946-play TBIN=$LG K0=$((39 + n)) ORDER="T" PLAY=300 bash "$E/kit/scene0432.sh" | tee "$E/smoke-scene-L$n.out"
echo "oom lines since boot: $(sudo -n dmesg | grep -c oom-killer); amdgpu timeout/reset lines: $(k0) (before: $K)"
echo "smokel432 ended $(date +%T)"
