#!/usr/bin/env bash
# BC5 experiment 0442 (tag tg442): ONE step of the clean-boot plan for the private build of the move (box0442.sh). One
# step per invocation, each under its own named user unit (LESSONS R73), started by the top session:
#   s1   the first title on the PRIVATE lean, 200 s, everything on (no switch word set: the build's defaults)
#   s2   only if s1 failed WITHOUT a kernel line: the same with G6+G7 off by their five off-words
#   s3   only if s2 failed WITHOUT a kernel line: the same with the twenty library words off (G6+G7 on)
#   ab   only after s1 passed: the lean A/B at 1920x1080 against the SHARED lean, exp 0438's ab438o.sh (d93139fd) as it
#        is, with AB_CB/AB_OB/AB_NB, pins, a warm-up and five pairs, then one private-normal run (diagnosis only)
# A kernel line ends the boot's plan (LESSONS R55/R60): no further step on that boot, the box is restarted first. So s2
# and s3 narrow a failure to a group only when it was a crash, an exit or a non-start without a kernel line.
# Each run step: no emulator, no foreign lock line (one chain_claim line for the step), the R60 gate with the fixed read
# (a failed or empty dmesg read refuses, LESSONS R60/R43), the R72 display check (display438.inc 5c6003f7), no dead first title
# mount, pad keys counted (reported, they do not void a caught fault), the binary read from /proc/<pid>/exe (R66),
# ulimit -c 0. Through exp 0413's start0413g.sh (2389300e; its derived first-title launcher, a private _SaveData).
# DRY=1: the checks and the plan only; no lock, no run (STANDIN_DMESG tests the R60 gate on a stand-in log).
# usage (on the box): systemd-run --user --unit=exp0442-s1 --collect -p RuntimeMaxSec=900 \
#            bash -c 'bash ~/bc5-work/exp0442/kit/run0442.sh s1 > ~/bc5-work/exp0442/s1.out 2>&1'
#   ab:      systemd-run --user --unit=exp0442-ab --collect -p RuntimeMaxSec=7200 \
#            bash -c 'bash ~/bc5-work/exp0442/kit/run0442.sh ab > ~/bc5-work/exp0442/ab.out 2>&1'
set -u
ulimit -c 0
export LC_ALL=C
STEP=${1:?s1, s2, s3 or ab}; DRY=${DRY:-0}
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; E=$W/exp0442/priv4
PL=$E/lean/kyty_emulator; PN=$E/normal/kyty_emulator; SL=$W/kytyplus-build-lean/src/kyty_emulator
PIN_PL=${PIN_PL:-eca99879}; PIN_PN=${PIN_PN:-fabfdc1c}; PIN_SL=${PIN_SL:-05fd749d}  # box0442b.sh bake 1a 2026-11-22 (archive 17fb5b25; bake 1: lean 60c31981, normal e43e111a in priv2); shared lean 589ef163
G67="BC5_DIRECT_GPU_CHECK=0 BC5_DIRECT_DMA_SNAPSHOT=0 BC5_DIRECT_CS_PREFIX=0 BC5_DIRECT_INDIRECT_DRAWS=0 BC5_DIRECT_LAZY_RELEASE=0"
LIB="KYTY_BC5_SAVEDATA_MEMORY_FIXES=0 KYTY_BC5_SAVEDATA_DELETE_BUSY=0 KYTY_BC5_SAVEDATA_ALIASES=0 KYTY_BC5_HTTP2_FIXES=0
KYTY_BC5_PAD_OPEN_EXT=0 KYTY_BC5_JSON2_FIXES=0 KYTY_BC5_ULT_FIXES=0 KYTY_BC5_USERSERVICE_VALUES=0 KYTY_BC5_SYSTEMSERVICE_VALUES=0
KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=0 KYTY_BC5_AUDIOOUT_CHECKS=0 KYTY_BC5_AUDIOIN_CHECKS=0 KYTY_BC5_NGS2_RACK_FIX=0 KYTY_BC5_FW_PAD=0
KYTY_BC5_LOAD_ZLIB=0 KYTY_BC5_LOAD_JPEG=0 KYTY_BC5_LOAD_IME=0 KYTY_BC5_LOAD_NPCOMMON=0 KYTY_BC5_LOAD_NPMANAGER=0 KYTY_BC5_LOAD_NPTROPHY=0"
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$(date +%T) run0442 $STEP: $*"; }
case "$STEP" in s1) WORDS="" ;; s2) WORDS=$G67 ;; s3) WORDS=$LIB ;; ab) WORDS="" ;; *) echo "s1, s2, s3 or ab"; exit 1 ;; esac
TAG=t442${STEP}$(date +%H%M)
ML=$(m "$PL"); MN=$(m "$PN"); MS=$(m "$SL")
[ "${ML:0:8}" = "$PIN_PL" ] && [ "${MN:0:8}" = "$PIN_PN" ] && [ "${MS:0:8}" = "$PIN_SL" ] \
    || { say "NOT STARTED: binaries private lean ${ML:0:8} (want $PIN_PL), private normal ${MN:0:8} (want $PIN_PN), shared lean ${MS:0:8} (want $PIN_SL)"; exit 1; }
for v in $(echo $G67 $LIB | tr ' ' '\n' | cut -d= -f1); do
    [ -z "${!v+x}" ] || { say "NOT STARTED: $v is set in this environment (${!v}): the steps set their own words"; exit 1; }
done
if [ "$STEP" = ab ]; then # exp 0438's A/B as it is; its own boot check, display check, lock and stop rules
    AB=$W/exp0438/r438okit/ab438o.sh
    [ "$(m "$AB" | cut -c1-8)" = d93139fd ] || { say "NOT STARTED: ab438o.sh is not d93139fd"; exit 1; }
    say "the A/B: control = shared lean ${MS:0:8}, O = private lean ${ML:0:8}, N = private normal ${MN:0:8}; a warm-up W0 and 5 pairs, 180 s each, then N1"
    DRY=$DRY AB_CB=$SL AB_OB=$PL AB_NB=$PN AB_PIN_C=${MS:0:8} AB_PIN_O=${ML:0:8} AB_PIN_N=${MN:0:8} AB_WARMUP=1 AB_NPAIRS=5 \
        bash "$AB" "q442$(date +%H%M)"
    exit $?
fi
cd "$N" || exit 1
[ -e "$R/$TAG-start.txt" ] && { say "NOT STARTED: tag $TAG used"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { say "NOT STARTED: an emulator runs"; exit 1; }
# DRY=1 STANDIN_DMESG=<file|FAIL>: a stand-in kernel log for the gate test only (refused without DRY=1)
kmsg() { if [ -n "${STANDIN_DMESG:-}" ]; then [ "$DRY" = 1 ] || return 9; [ "$STANDIN_DMESG" = FAIL ] && return 1; cat "$STANDIN_DMESG"; else sudo -n dmesg; fi; }
resets() { local o; o=$(kmsg 2> /dev/null) && [ -n "$o" ] || { echo unread; return 2; }; printf '%s\n' "$o" | grep -E 'amdgpu [0-9a-f]{4}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; return 0; }
r60gate() { local n; n=$(resets); case "$n" in 0) return 0 ;; unread) echo "R60/R43 $1: the kernel log could not be read: unknown boot: refused"; return 3 ;; *) echo "R60 $1: this boot has $n GPU reset or timeout lines: refused"; return 4 ;; esac; }
deadmnt() { distrobox enter ubuntu -- sh -c 'M=$HOME/bc5-data/mnt/TITLE1; if mountpoint -q "$M" && ! head -c1 "$M/sce_sys/param.json" > /dev/null 2>&1; then echo dead; fi' 2> /dev/null < /dev/null | grep -q dead; }
g=$(r60gate "before $TAG"); grc=$?; [ "$grc" = 0 ] || { say "NOT STARTED: $g"; exit "$grc"; }
. "$W/exp0438/display438.inc" || { say "NOT STARTED: no display438.inc"; exit 1; }
[ "$(m "$W/exp0438/display438.inc" | cut -c1-8)" = 5c6003f7 ] || { say "NOT STARTED: display438.inc is not 5c6003f7"; exit 1; }
display_check || { say "NOT STARTED: $DISP (LESSONS R72)"; exit 1; }
deadmnt && { say "NOT STARTED: a dead first-title mount inside the container"; exit 1; }
read -r -a WA <<< "$(echo $WORDS)"
say "boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), kernel $(uname -r), resets 0, $DISP; private lean ${ML:0:8}; words: ${WA[*]:-none, the build defaults}"
if [ "$DRY" = 1 ]; then say "DRY: would run $TAG: the first title 200 s on the private lean; lock now [$(cat "$W/BOX-LOCK")]"; exit 0; fi
. "$N/chainlock0417.inc"
chain_claim "exp 0442: $TAG, the first title 200 s on the private lean of the title-defaults move ($STEP)" 8 || { say "NOT STARTED: no lock"; exit 1; }
PADS=()
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; pkill -u "$USER" -x evtest 2> /dev/null; chain_release; }
trap fin EXIT
: > "$R/$TAG-pad.txt"
for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$TAG-pad.txt" & PADS+=($!); done
( for _ in $(seq 1 240); do p=$(pgrep -n '^kyty_emulator') && break; sleep 1; done
  if [ -n "${p:-}" ]; then x=$(readlink "/proc/$p/exe"); echo "pid $p exe $x md5 $(md5sum < "$x" | cut -d' ' -f1)"; else echo "no emulator within 240 s"; fi ) > "$R/$TAG-exe.txt" 2>&1 & XP=$!
# flips/s as a smoke figure: MangoHud's own per-frame log (ab438o.sh's settings; the Plasma shell is NOT stopped, so
# the figure is not an A/B number)
mkdir -p "$R/$TAG-mh"
MH=(MANGOHUD=1 "MANGOHUD_CONFIG=fps_only=1,alpha=0,background_alpha=0,autostart_log=1,log_interval=0,output_folder=$R/$TAG-mh,log_duration=190")
line=$(P_BIN=$PL P_WANT=$ML bash ./start0413g.sh "$TAG" t1 200 "${WA[@]}" "${MH[@]}" 2>&1 | tail -1)
wait "$XP" 2> /dev/null
say "$line; real pad keys $(wc -l < "$R/$TAG-pad.txt"); exe [$(cat "$R/$TAG-exe.txt")]"
mhf=$(ls -t "$R/$TAG-mh"/*.csv 2> /dev/null | grep -v summary | head -1)
if [ -n "$mhf" ]; then
    say "flips (MangoHud, from 30 s): $(awk -F, 'h == 0 && /^fps,/ {for (i = 1; i <= NF; i++) {if ($i == "frametime") ft = i; if ($i == "elapsed") el = i}; h = 1; next}
      h == 1 && ft > 0 && el > 0 {t = $el / 1e9; if (t < 30) next; if (t0 == "") t0 = t; t1 = t; n++; if ($ft > 50) o++}
      END {if (n < 2) {print "too few frames"; exit}; printf "%d frames in %.1f s, flips/s %.2f, over 50 ms %d", n, t1 - t0, (n - 1) / (t1 - t0), o + 0}' "$mhf")"
else say "flips: no MangoHud log"; fi
OK=1
grep -q " md5 $ML\$" "$R/$TAG-exe.txt" || { say "ANOTHER BINARY RAN"; OK=0; }
case "$line" in *"PASS: ran 200 s"*"kernel lines 0, crash lines 0"*) ;; *) OK=0 ;; esac
g=$(r60gate "after $TAG") || { say "$g: the boot's plan ends here (restart before any further step)"; OK=0; }
say "the library words' start lines: $(grep -ac 'exp 0405: .* on (items' "$R/$TAG-play.log" 2> /dev/null) on, $(grep -ac 'exp 0405: .* off$' "$R/$TAG-play.log" 2> /dev/null) off"
say "$([ "$OK" = 1 ] && echo PASS || echo "NOT A PASS")"
[ "$OK" = 1 ]
