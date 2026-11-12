#!/usr/bin/env bash
# BC5 exp 0415: ASTRO BOT started on the private build for <seconds> with no input (the title stays where it starts),
# for the check "does KYTY_BC5_APR_POSIX change anything for the other title". A private launcher is derived from the
# shared ~/bc5-work/play-astro.sh (read only): the binary, both log lines and the working directory are made private
# by anchored edits; the image is mounted at a private mountpoint through the launcher's own BC5_FFPFSC_MOUNT word;
# the private working directory has an empty _SaveData (no save of the maintainer's is read or written).
# Beside it: the counter file (KYTY_BC5_LOAD_STAT), col0415.py, exp 0412's watchdog. BOX-LOCK by an atomic hard-link
# claim; only our exact line is removed. The kernel log is streamed by the laptop.
# usage (on the box): astro0415.sh <tag> <seconds> [KEY=VALUE ...]
set -u
ulimit -c 0
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; E=$W/exp0415; R=$E/raw; LOCK=$W/BOX-LOCK; HERE=$(cd "$(dirname "$0")" && pwd)
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
stop() { echo "astro0415 STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator is running"
pgrep -x bc5-mount > /dev/null && stop "a bc5-mount is running"
TAG=${1:?a tag}; SECS=${2:?seconds}; shift 2
EXTRA=("$@")
case "$TAG" in *[!A-Za-z0-9]* | "") stop "the tag is letters and digits" ;; esac
case "$SECS" in *[!0-9]* | "") stop "seconds, please" ;; esac
[ "$SECS" -ge 60 ] && [ "$SECS" -le 600 ] || stop "60-600 s"
for w in "${EXTRA[@]}"; do case "$w" in [A-Z]*=*) ;; *) stop "an extra word is NAME=VALUE: $w" ;; esac; done
[ -e "$R/$TAG-start.txt" ] && stop "tag $TAG already used"
BIN=$E/bin/kyty_emulator; WANT=$(m "$BIN"); grep -qxF "$WANT  bin/kyty_emulator" "$E/built.md5" || stop "the binary is not the one in built.md5"
LAUNCH_SRC=$W/play-astro.sh; LAUNCH=$E/play-astro-0415.sh; WD=$E/wd-astro; MNT=$E/mnt-astro/PPSA21567  # astro0415b: the game root keeps the title id as its directory name (as1off/as1on at mnt-astro fell into the host renderer at once)
[ -f "$LAUNCH_SRC" ] && [ -d "$W/exp0330/wd" ] && [ -x "$W/exp0412/wd0412.sh" ] || stop "no shared launcher, exp0330/wd or exp0412/wd0412.sh"
T=$(date +%Y%m%d%H%M%S)$$
LINE="exp 0415 | astro run $TAG ($SECS s), ASTRO BOT on exp0415/${WANT:0:8}, attended, token $T"
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || stop "the box is locked: $(cat "$LOCK")"
tl=$LOCK.0415a-$$.new; al=$LOCK.0415a-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; stop "the claim failed"; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; stop "a foreign line arrived during the claim"; fi
rm -f "$al" "$tl"
[ "$(cat "$LOCK")" = "$LINE" ] || stop "the lock does not read back as ours"
printf '%s\n' "exp 0415 | claimed: astro run $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
release() {
  if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0415a-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi
  printf '%s\n' "exp 0415 | released: astro run $TAG, token $T | $(date '+%F %T')" >> "$W/BOX-QUEUE"
}
EP=""; CP=""
cleanup() {
  if [ -n "$EP" ] && [ -d "/proc/$EP" ] && [ "$(m "/proc/$EP/exe")" = "$WANT" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
  [ -n "$CP" ] && kill "$CP" 2> /dev/null
  release
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
cp "$LAUNCH_SRC" "$LAUNCH" || stop "the launcher copy"
python3 -I - "$LAUNCH" "$E" << 'PYEOF' || stop "the launcher's edit"
import sys
p, e = sys.argv[1], sys.argv[2]
s = open(p, encoding='utf-8').read()
edits = [
    ('\nEMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n', '\nEMU=%s/bin/kyty_emulator  # exp 0415: the private build\n' % e),
    ('\nLOG=~/bc5-work/play-last.log\n', '\nLOG=%s/astro-last.log  # exp 0415: own log\n' % e),
    ('  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-lean-last.log\n',
     '  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=%s/astro-last.log  # exp 0415: own log (lean is not used here)\n' % e),
    ('\ncd ~/bc5-work\n', '\ncd %s/wd-astro  # exp 0415: the private working directory (an empty _SaveData)\n' % e),
    ('\ndone < "$ENVF"\n', '\ndone < "$ENVF"\nexport SHADPS4_SYSMODULES_PACK_DIR=$M/fakelib  # exp 0415 (astro0415c): the settings file names the shared mountpoint\n'),
]
for old, new in edits:
    if s.count(old) != 1:
        sys.exit('anchor count %d: %r' % (s.count(old), old))
    s = s.replace(old, new)
open(p, 'w', encoding='utf-8', newline='\n').write(s)
PYEOF
diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/$TAG-launcher.diff"
[ "$(grep -c '^[-+][^-+]' "$R/$TAG-launcher.diff")" = 9 ] || stop "the derived launcher's diff is not 4 lines changed + 1 added"
bash -n "$LAUNCH" || stop "the derived launcher does not parse"
grep -q 'BC5_FFPFSC_MOUNT' "$LAUNCH" || stop "the launcher has no BC5_FFPFSC_MOUNT word"
chmod +x "$LAUNCH"
if [ ! -e "$WD" ]; then
  mkdir -p "$WD" "$WD/_SaveData" || stop "the working directory"
  find "$W/exp0330/wd" -mindepth 1 -maxdepth 1 -type l ! -name '_SaveData*' -exec cp -P -t "$WD" {} + || stop "the wd links could not be copied"
fi
[ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ ! -L "$WD" ] || stop "$WD/_SaveData is not a private directory"
mkdir -p "$MNT" || stop "the mountpoint"
STAT=$R/$TAG-loadstat.txt; rm -f "$STAT"; LOG=$E/astro-last.log
WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$'); [ -n "$WL" ] || stop "no Wayland socket"
ENVS=("BC5_FFPFSC_MOUNT=$MNT" "KYTY_BC5_LOAD_STAT=$STAT" "WAYLAND_DISPLAY=$WL" "${EXTRA[@]}")
ND=$(sudo -n dmesg 2> /dev/null | wc -l)
{ date '+%F %T'; echo "astro run $TAG, $SECS s, binary $BIN md5 $WANT, launcher $(m "$LAUNCH" | cut -c1-8) from $(m "$LAUNCH_SRC" | cut -c1-8)"; echo "extra: ${EXTRA[*]:-none}"
  grep -E '^(MemAvailable|SwapFree):' /proc/meminfo | tr '\n' ' '; echo; echo "other load: rsync $(pgrep -c -x rsync)"; } > "$R/$TAG-start.txt"
setsid nohup python3 -I "$HERE/col0415.py" "$R/$TAG-col.txt" $((SECS + 60)) > "$R/$TAG-col.err" 2>&1 < /dev/null & CP=$!
setsid nohup bash -c 'distrobox enter ubuntu -- /usr/bin/bash -c '\''ulimit -c 0; exec /usr/bin/env "$@"'\'' astro0415 "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
for _ in $(seq 1 120); do EP=$(pgrep -o '^kyty_emulator') && break; sleep 0.5; done
T0=$(date +%s); ENDED=""
if [ -z "$EP" ]; then ENDED="SETUP: no emulator started"
else
  echo "emulator pid $EP exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")" >> "$R/$TAG-start.txt"
  [ "$(m "/proc/$EP/exe")" = "$WANT" ] || ENDED="SETUP: the emulator is not md5 $WANT"
  [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || ENDED="SETUP: the emulator's working directory is not $WD"
  for w in "${EXTRA[@]}" "KYTY_BC5_LOAD_STAT=$STAT"; do tr '\0' '\n' < "/proc/$EP/environ" 2> /dev/null | grep -qxF -- "$w" || { ENDED="SETUP: the emulator's environment lacks $w"; break; }; done
  setsid nohup bash "$W/exp0412/wd0412.sh" "$EP" "$R/$TAG-watchdog.txt" 300 60 > /dev/null 2>&1 < /dev/null &
fi
while [ -z "$ENDED" ] && [ $(($(date +%s) - T0)) -lt "$SECS" ]; do
  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }
  if sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -qi "amdgpu.*\(timeout\|reset\|fault\)"; then ENDED="GPU: a kernel amdgpu line at $(($(date +%s) - T0)) s"; break; fi
  sleep 2
done
DUR=$(($(date +%s) - T0))
if [ -n "$EP" ] && [ -d "/proc/$EP" ] && [ "$(m "/proc/$EP/exe")" = "$WANT" ]; then kill "$EP"; sleep 4; [ -d "/proc/$EP" ] && kill -9 "$EP" 2> /dev/null; fi
EP=""
sleep 3; [ -n "$CP" ] && kill "$CP" 2> /dev/null; CP=""
LGONE=no; for _ in $(seq 1 60); do grep -q '^launcher exit' "$R/$TAG-launch.out" 2> /dev/null && { LGONE=yes; break; }; sleep 1; done
MGONE=yes; pgrep -x bc5-mount > /dev/null && MGONE=no
if [ -f "$LOG" ] && [ "$(stat -c %Y "$LOG")" -ge "$T0" ]; then cp -p "$LOG" "$R/$TAG-play.log"; else echo "no log of this run at $LOG" > "$R/$TAG-play.log"; fi
grep -a -B2 -A12 "Access violation\|Segmentation\|Aborted\|terminate called\|exception_address\|--- Error ---" "$R/$TAG-play.log" | head -80 > "$R/$TAG-crash.txt" 2> /dev/null
sudo -n dmesg 2> /dev/null | tail -n +"$((ND + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC\|Killed" > "$R/$TAG-dmesg-after.txt"
echo "$TAG ${ENDED:-ran its $SECS s} (after $DUR s); launcher gone $LGONE, mount gone $MGONE; counter lines $(grep -c '^s ' "$STAT" 2> /dev/null), flips $(tail -1 "$STAT" 2> /dev/null | sed -n 's/.* flip=\([0-9]*\),.*/\1/p'), kernel lines $(grep -c . "$R/$TAG-dmesg-after.txt"), crash lines $(grep -c . "$R/$TAG-crash.txt")" > "$R/$TAG-summary.txt"
sync
cat "$R/$TAG-summary.txt"
