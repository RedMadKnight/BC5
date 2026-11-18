#!/usr/bin/env bash
# BC5 exp 0429: the check of candidate R before any set (the top session, 2026-11-17 11:0x): one short run of arm G on
# the private build (play 40 s after G, about 150 s in all), and at G+25 s every thread of the emulator with its policy
# and RR priority (ps cls/rtprio). PASS: every 'Job Hi' thread is RR, the main thread is not, and R's log shows promotions.
# The demotion of spinners is reported (dropped lines, and the RR threads at the end); MainThread's pause loop is the
# expected one. One BOX-LOCK line (chainlock0417.inc). usage (on the box): bash ~/bc5-work/exp0429/check0429r.sh <tag>
set -u
ulimit -c 0
W=$HOME/bc5-work; HERE=$W/exp0429; T=${1:?a tag}
V=normal; [ "${CHECK_LEAN:-0}" = 1 ] && V=lean  # lean: R logs nothing, so the check is the ps picture alone
BIN=$W/exp0429/$V/kyty_emulator; WORDS=$W/exp0413/n/words0413nz.txt
WANT=$(cat "$W/exp0429/$V/binary.md5")
. "$W/exp0413/n/chainlock0417.inc"
chain_claim "exp 0429: R check $T ($V, RR=${RRMODE:-1}, one short run, arm G, about 3 min)" 6 || { echo "no lock"; exit 1; }
trap chain_release EXIT
T0=$(date "+%F %T")
N_WALK_AFTER=1 N_SLOT=4 P_BIN=$BIN P_WANT=$WANT P_WORDS=$WORDS bash "$HERE/run0429f.sh" "$T" G 40 \
  KYTY_BC5_0429_TRACE=1 KYTY_BC5_0429_WAITS=1 BC5_0430_G=0 KYTY_BC5_0429_GUEST_CPUS=1 KYTY_BC5_0429_RR=${RRMODE:-1} KYTY_BC5_0429_RESERVE=${RESERVE:-4} > "$HERE/check-$T.run" 2>&1 &
RP=$!
sleep 133
P=$(pgrep -n '^kyty_emulator')
if [ -n "$P" ]; then
  ps -L -o tid,cls,rtprio,ni,comm -p "$P" > "$HERE/check-$T.ps"
fi
wait $RP
L=$HERE/n/raw/$T-play.log; [ -s "$L" ] || L=$HERE/n/play-last.log
hi=$(grep -c ' Job Hi' "$HERE/check-$T.ps" 2> /dev/null); hirr=$(grep ' Job Hi' "$HERE/check-$T.ps" 2> /dev/null | grep -c ' RR ')
prom=$(grep -ac 'exp 0429 R: promoted' "$L"); ref=$(grep -ac 'exp 0429 R: rtkit refused' "$L"); drop=$(grep -ac 'exp 0429 R: dropped' "$L")
echo "check $T: Job Hi threads $hi, of them RR $hirr; promoted $prom, refused $ref, dropped $drop; RR threads at G+25: $(grep -c ' RR ' "$HERE/check-$T.ps" 2> /dev/null)"
grep ' RR \|MainThread' "$HERE/check-$T.ps" 2> /dev/null | head -20
grep -a 'exp 0429 R: dropped\|exp 0429 R: rtkit refused\|rtkit.s reason' "$L" | head -8
tail -1 "$HERE/check-$T.run" | cut -c1-200
grep -a "exp 0429 R count\|exp 0429: R (RR" "$L" | tail -4 | cut -c1-260
mainrr=$(grep -E " (game-main|MainThread)$" "$HERE/check-$T.ps" 2> /dev/null | grep -c " RR ")
echo "check $T: the main thread RR: $mainrr (must be 0); rtkit refusals $ref (reported only: rtkit has a per-user limit)"
echo "check $T: threads with nice < 0 (rtkit high priority; build 13): $(awk 'NR > 1 && $4 ~ /^-[0-9]/ {print $5" "$6" "$7"("$4")"}' "$HERE/check-$T.ps" | sort | uniq -c | tr '\n' ';')"
LOGF=$L
# build 14: rtkit's refusals during the run that were not R's (the emulator's own audio/SDL/input threads, or another
# process of the user): any one fails the check (the top session, 2026-11-18: audio is the user-visible cost)
rk=$(journalctl -u rtkit-daemon --since "$T0" --no-pager 2> /dev/null | grep -c 'maximum concurrent threads'); rk=${rk:-0}
rref=$(grep -a 'exp 0429 R count' "$LOGF" 2> /dev/null | tail -1 | sed -E 's/.* R ([0-9]+) C .*/\1/'); [ -n "$rref" ] || rref=0
own=$((rk - rref)); [ "$own" -lt 0 ] && own=0
echo "check $T: rtkit refusals in the run $rk, of them R's $rref, others' $own (must be 0); the emulator's own threads not high priority: $(awk 'NR > 1 && $4 !~ /^-/ && ($5 ~ /^SDLAudio|^HIDAPI/ || $5 ~ /^AK::AudioOutThr|^AK::JobWrkr-Acm/) {print $5" "$6"("$4")"}' "$HERE/check-$T.ps" | sort | uniq -c | tr '\n' ';')"
akrr=$(grep ' AK::' "$HERE/check-$T.ps" 2> /dev/null | grep -c ' RR '); akrr=${akrr:-0}  # build 13: mode 3 keeps lone threads (audio) out
echo "check $T: AK threads RR at the snapshot: $akrr (mode 3: must be 0)"
[ "$rk" = 0 ] && { [ "${RRMODE:-1}" != 3 ] || [ "$akrr" = 0 ]; } && { [ "$prom" -ge 1 ] || [ $V = lean ]; } && [ "$hi" -ge 1 ] && [ "$hi" = "$hirr" ] && [ "$mainrr" = 0 ] && echo "check $T: PASS" || echo "check $T: FAIL"
