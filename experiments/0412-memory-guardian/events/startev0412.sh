#!/usr/bin/env bash
# BC5 exp 0412 (tag ev412): makes the second title's launcher for the events-cap build and checks that the unpacked
# game starts on it. On the box, no emulator running.
#   1. ev/play-pkg-ev0412.sh from exp 0412's play-pkg-0412.sh (EMU and LOG changed; BC5_GAME_DIR, ulimit -c 0 kept),
#      and its line in ev/built.md5.
#   2. The start check: the wrapper play-pkg-ev-0412.sh <arm> with a test copy of that launcher whose working directory,
#      save directory and learned file are private (the night runner's: exp0412/night/wd and its copy of the saves, so
#      the live saves and the live learned file are not touched), for <seconds> with no input, then SIGTERM. Beside
#      it the watchdog wd0412.sh; the wrapper brings the sampler and the fuse. The result line says how many seconds
#      had flips in the play log's fps counter, and the crash, kernel and event lines.
# BOX-LOCK by an atomic hard-link claim, our exact line removed at the end.
# usage (on the box): startev0412.sh <tag> cap|log|plain <seconds>
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; V=$X/ev; N=$X/night; R=$V/raw; LOCK=$W/BOX-LOCK
TAG=${1:?a tag}; ARM=${2:?an arm}; SECS=${3:?seconds}
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 1 ;; esac
case "$SECS" in *[!0-9]* | "") echo "seconds, please"; exit 1 ;; esac
[ "$SECS" -ge 60 ] && [ "$SECS" -le 900 ] || { echo "60-900 s"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
die() { echo "STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && die "an emulator runs"
[ -e "$R/$TAG-end.txt" ] && die "tag $TAG already used"
grep -qxF "$(m "$V/bin/kyty_emulator")  bin/kyty_emulator" "$V/built.md5" || die "the ev412 binary is not the one in ev/built.md5"
grep -qxF "$(m "$X/play-pkg-0412.sh")  play-pkg-0412.sh" "$X/built.md5" || die "exp 0412's launcher is not the one in built.md5"
[ -d "$N/wd/_SaveData/PPSA03671" ] && [ ! -L "$N/wd/_SaveData" ] || die "no private working directory $N/wd (the night runner makes it)"
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$'); [ -n "$WL" ] || die "no Wayland socket"
T=$(date +%Y%m%d%H%M%S)$$
LINE="guard exp 0412 | start check $TAG (the second title unpacked on ev412, $ARM, $SECS s, no input), token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || die "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0412s-$$.new; al=$LOCK.0412s-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; die "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; die "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
printf '%s\n' "guard exp 0412 | claimed: start check $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
EP=""
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.0412s-$$.rel"; mv -fT "$LOCK.0412s-$$.rel" "$LOCK"; fi
  printf '%s\n' "guard exp 0412 | released: start check $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
mkdir -p "$R" || die "mkdir"
# 1. The launcher.
SRC=$X/play-pkg-0412.sh; L=$V/play-pkg-ev0412.sh
sed -e "s|^EMU=$X/bin/kyty_emulator  # exp 0412: the private build\$|EMU=$V/bin/kyty_emulator  # exp 0412 (ev412): the private build|" \
    -e "s|^LOG=$X/play-last.log  # exp 0412: own log\$|LOG=$X/pkg-ev-last.log  # exp 0412 (ev412): own log|" "$SRC" > "$R/play-pkg-ev0412.sh" || die "launcher"
bash -n "$R/play-pkg-ev0412.sh" || die "the launcher does not parse"
[ "$(diff "$SRC" "$R/play-pkg-ev0412.sh" | grep -c '^[<>]')" = 4 ] && grep -q '^ulimit -c 0' "$R/play-pkg-ev0412.sh" &&
    [ "$(grep -c "^EMU=$V/bin/kyty_emulator  # exp 0412 (ev412)" "$R/play-pkg-ev0412.sh")" = 1 ] && [ "$(grep -c "^LOG=$X/pkg-ev-last.log" "$R/play-pkg-ev0412.sh")" = 1 ] &&
    grep -q 'if \[ -n "${BC5_GAME_DIR:-}" \]; then M=$BC5_GAME_DIR' "$R/play-pkg-ev0412.sh" || die "the launcher is not exp 0412's with EMU and LOG changed"
chmod +x "$R/play-pkg-ev0412.sh"
cp -p "$R/play-pkg-ev0412.sh" "$L.new-$$" && mv -fT "$L.new-$$" "$L" || die "cannot put the launcher in place"
grep -v '  play-pkg-ev0412.sh$' "$V/built.md5" > "$V/built.md5.new-$$"; printf '%s  play-pkg-ev0412.sh\n' "$(m "$L")" >> "$V/built.md5.new-$$"; mv -fT "$V/built.md5.new-$$" "$V/built.md5" || die "built.md5"
echo "launcher $(m "$L")"
bash "$X/play-pkg-ev-0412.sh" "$ARM" dry > "$R/$TAG-dry.txt" 2>&1 && grep -q '^dry: nothing started$' "$R/$TAG-dry.txt" && grep -q '^dry: fuse pinned' "$R/$TAG-dry.txt" || die "the wrapper's dry run failed: $(tail -1 "$R/$TAG-dry.txt")"
# 2. The test copy: the private working directory, save directory and learned file (run0412n.sh's three lines).
TL=$R/play-pkg-ev0412-test.sh
cp -p "$W/direct-learned-pkg.txt" "$V/direct-learned-test.txt" || die "learned copy"
sed -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0412/night/wd  \# exp 0412 start check: the private working directory#' \
    -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0412/night/wd/_SaveData-pkg-play  \# exp 0412 start check: private#' \
    -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0412/ev/direct-learned-test.txt  \# exp 0412 start check: a private copy#' \
    -e "s|^LOG=$X/pkg-ev-last.log  # exp 0412 (ev412): own log\$|LOG=$R/$TAG-play.log  # exp 0412 start check|" "$L" > "$TL" || die "test launcher"
[ "$(diff "$L" "$TL" | grep -c '^[<>]')" = 8 ] && bash -n "$TL" || die "the test launcher is not the launcher with four lines changed"
chmod +x "$TL"
ND=$(sudo -n dmesg 2> /dev/null | wc -l)
S0=$(md5sum < <(cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2) | cut -c1-16)
BC5_0412_LAUNCHER=$TL WAYLAND_DISPLAY=$WL setsid nohup bash "$X/play-pkg-ev-0412.sh" "$ARM" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd"); $(tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -E '^(BC5_GAME_DIR|KYTY_BC5_EVENT_PENDING|KYTY_BC5_SAVEDATA_DIR|BC5_DIRECT_LEARNED)=' | tr '\n' ' ')" > "$R/$TAG-start.txt"
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$N/wd")" ] || ENDED="SETUP: the emulator's working directory is not the private one"
  setsid nohup bash "$X/wd0412.sh" "$EP" "$R/$TAG-watchdog.txt" 300 60 > /dev/null 2>&1 < /dev/null &
  while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
    [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
    if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qi "amdgpu.*\(timeout\|reset\|fault\)"; then sleep 20; ENDED="GPU: a kernel amdgpu line at about $(($(date +%s) - T0 - 20)) s"; break; fi
    sleep 5
  done
fi
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
for _ in $(seq 1 60); do pgrep -f "play-pkg-ev0412-test.sh" > /dev/null || break; sleep 1; done
sleep 4
P=$R/$TAG-play.log
grep -a "fps counter" "$P" 2> /dev/null | sed -E 's/.*t ([0-9.]+) s: ([0-9]+) flips in ([0-9.]+) s, longest gap ([0-9.]+) ms.*/\1 \2 \3 \4/' > "$R/$TAG-fps.txt"
grep -a "exp 0412 events" "$P" 2> /dev/null | cut -c1-300 > "$R/$TAG-events.txt"
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$P" 2> /dev/null | head -60 > "$R/$TAG-crash.txt"
sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|Killed" > "$R/$TAG-dmesg-after.txt"
SF=$(ls -t "$X/sampler/"play-*-ev"$ARM".txt 2> /dev/null | head -1); [ -n "$SF" ] && cp -p "$SF" "$R/$TAG-sampler.txt"
S1=$(md5sum < <(cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2) | cut -c1-16)
FPSL=$(awk 'NF == 4 { n++; f += $2; s += $3; if ($4 > mx) mx = $4; last = $1 } END { if (s > 0) printf "%d fps lines to t %.0f s, %.1f flips/s over %d s, longest gap %.0f ms", n, last, f / s, s, mx; else printf "NO fps lines" }' "$R/$TAG-fps.txt")
echo "$TAG (the second title unpacked on ev412, $ARM) ${ENDED:-ended at $SECS s} (after $DUR s); $FPSL; crash lines $(grep -c . "$R/$TAG-crash.txt"), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), event lines $(grep -c . "$R/$TAG-events.txt"); live saves $([ "$S0" = "$S1" ] && echo untouched || echo "CHANGED $S0 -> $S1"); $(tail -1 "$R/$TAG-watchdog.txt" 2> /dev/null | cut -c21-140)" > "$R/$TAG-end.txt"
sync
cat "$R/$TAG-end.txt"
