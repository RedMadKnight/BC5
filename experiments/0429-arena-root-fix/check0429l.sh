#!/usr/bin/env bash
# BC5 exp 0429: the lean check of candidate R. check0429r.sh cannot drive lean: run0429f.sh gates on the journal's frame
# profiles, which lean compiles out. This one runs the private lean build through exp 0428's start0428l.sh (its own
# BOX-LOCK line; RT on; input.cfg as shared) with lean0428.sh's key route by time, 200 s, words of arm G
# (GUEST_CPUS=1 RR=1, BC5_0430_G=0), and at 150 s takes every thread's policy (ps cls/rtprio). Lean logs nothing, so the
# verdict is the ps picture alone. PASS: every 'Job Hi' thread is RR, the main thread is not, the run did not crash.
# Build 11: RRMODE=2 for the pool sleepers only; the policies every 10 s and R's count lines (one a minute, lean too).
# usage (on the box, in ~/bc5-work/exp0413/n): [RRMODE=2] bash ~/bc5-work/exp0429/check0429l.sh <tag>
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; HERE=$W/exp0429; T=${1:?a tag}
BIN=$HERE/lean/kyty_emulator; WANT=$(cat "$HERE/lean/binary.md5")
[ "$(md5sum < "$BIN" | cut -d' ' -f1)" = "$WANT" ] || { echo "the lean binary is not its pin"; exit 1; }
cd "$N" || exit 1
CMD=$N/cmd-$T.txt
{ printf 'wait 90000\npress cross\nwait 10000\npress cross\nwait 8000\npress cross\nwait 62000\n'
  c=0; while [ $c -lt 8 ]; do s=255; [ $(((c / 4) % 2)) = 1 ] && s=0; printf 'stick l 128 0 15000\nstick r %d 128 1200\nwait 300\n' "$s"; c=$((c + 1)); done
  printf 'stick l 128 128\nstick r 128 128\n'; } > "$CMD"
T0=$(date "+%F %T")
P_BIN=$BIN P_WANT=$WANT P_WORDS=$N/words0413nz.txt bash "$W/exp0428/start0428l.sh" "$T" lean 200 KYTY_BC5_INPUT_CMD="$CMD" \
  BC5_0430_G=0 KYTY_BC5_0429_GUEST_CPUS=1 KYTY_BC5_0429_RR=${RRMODE:-1} KYTY_BC5_0429_RESERVE=${RESERVE:-4} > "$HERE/check-$T.run" 2>&1 &
RP=$!
: > "$HERE/check-$T.series"
for s in $(seq 10 10 190); do  # build 11: the policy of the job and audio threads every 10 s (when a Hi worker leaves RR)
  sleep 10
  P=$(pgrep -n '^kyty_emulator') || continue
  echo "$s $(ps -L -o cls,comm -p "$P" | grep -E ' (Job Hi|AK::)' | awk '{print $1}' | tr '\n' ' ')" >>"$HERE/check-$T.series"
  [ "$s" = 150 ] && ps -L -o tid,cls,rtprio,ni,comm -p "$P" > "$HERE/check-$T.ps"
done
wait $RP
hi=$(grep -c ' Job Hi' "$HERE/check-$T.ps" 2> /dev/null); hi=${hi:-0}
hirr=$(grep ' Job Hi' "$HERE/check-$T.ps" 2> /dev/null | grep -c ' RR '); hirr=${hirr:-0}
mainrr=$(grep -E " (game-main|MainThread)$" "$HERE/check-$T.ps" 2> /dev/null | grep -c " RR "); mainrr=${mainrr:-0}
end=$(grep "^$T " "$HERE/check-$T.run" | tail -1)
echo "check $T (lean $WANT): Job Hi threads $hi, of them RR $hirr; the main thread RR $mainrr; RR threads at 150 s: $(grep -c ' RR ' "$HERE/check-$T.ps" 2> /dev/null)"
grep ' RR \|game-main\|MainThread' "$HERE/check-$T.ps" 2> /dev/null | head -24
echo "$end" | cut -c1-220
echo "the Job Hi and AK policies every 10 s (Hi 0-7 first, then the AK threads):"; cat "$HERE/check-$T.series"
grep -a "exp 0429 R count\|exp 0429: R (RR" "$N/raw/$T-play.log" 2> /dev/null | cut -c1-260
echo "check $T: threads with nice < 0 (rtkit high priority; build 13): $(awk 'NR > 1 && $4 ~ /^-[0-9]/ {print $5" "$6" "$7"("$4")"}' "$HERE/check-$T.ps" | sort | uniq -c | tr '\n' ';')"
LOGF=$N/raw/$T-play.log
# build 14: rtkit's refusals during the run that were not R's (the emulator's own audio/SDL/input threads, or another
# process of the user): any one fails the check (the top session, 2026-11-18: audio is the user-visible cost)
rk=$(journalctl -u rtkit-daemon --since "$T0" --no-pager 2> /dev/null | grep -c 'maximum concurrent threads'); rk=${rk:-0}
rref=$(grep -a 'exp 0429 R count' "$LOGF" 2> /dev/null | tail -1 | sed -E 's/.* R ([0-9]+) C .*/\1/'); [ -n "$rref" ] || rref=0
own=$((rk - rref)); [ "$own" -lt 0 ] && own=0
echo "check $T: rtkit refusals in the run $rk, of them R's $rref, others' $own (must be 0); the emulator's own threads not high priority: $(awk 'NR > 1 && $4 !~ /^-/ && ($5 ~ /^SDLAudio|^HIDAPI/ || $5 ~ /^AK::AudioOutThr|^AK::JobWrkr-Acm/) {print $5" "$6"("$4")"}' "$HERE/check-$T.ps" | sort | uniq -c | tr '\n' ';')"
akrr=$(grep ' AK::' "$HERE/check-$T.ps" 2> /dev/null | grep -c ' RR '); akrr=${akrr:-0}  # build 13: mode 3 keeps lone threads (audio) out
echo "check $T: AK threads RR at the snapshot: $akrr (mode 3: must be 0)"
[ "$rk" = 0 ] && { [ "${RRMODE:-1}" != 3 ] || [ "$akrr" = 0 ]; } && [ "$hi" -ge 1 ] && [ "$hi" = "$hirr" ] && [ "$mainrr" = 0 ] && echo "$end" | grep -q 'PASS' && echo "check $T: PASS" || echo "check $T: FAIL"
