#!/usr/bin/env bash
# BC5 exp 0439 (tag vz439k, step 1c): one function run of the second title on a private build that carries the
# flip-label fix (vlon439), to show the universal change breaks no other title. Its package from the NAS, RT on (the
# Ray tracing switch is always on since 11-22), the launcher's own words, no keys. ~/bc5-work/play-pkg.sh hard-sets the
# save folder to ~/bc5-work/_SaveData-pkg-play, so a derived copy (k439/play-pkg-vz.sh) differs in that one line: the
# saves go to a fresh copy of the 11-17 play snapshot. BOX-LOCK through e0439.sh, ulimit -c 0, shots at 60/120/240 s
# (private), SIGTERM at the bound, the kernel's GPU lines before and after.
#   vz2t439.sh <tag> <binary md5-8> [bound s, default 300]
set -u
E=$HOME/bc5-work/exp0439; K=$E/k439; W=$HOME/bc5-work; T=${1:?tag}; PIN=${2:?md5-8}; B=${3:-300}
BIN=$K/normal/kyty_emulator.$PIN; L=$K/play-pkg-vz.sh; SAVE=$E/save-$T; SH=$HOME/bc5-data/priv/second-screens/$T
stop() { echo "vz2t439 STOP: $*"; exit 1; }
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || stop "$BIN is not $PIN"
pgrep "^kyty_emulator" > /dev/null && stop "an emulator runs"
[ -s "$W/BOX-LOCK" ] && stop "BOX-LOCK: $(cat "$W/BOX-LOCK")"
mountpoint -q /var/mnt/nas-bc5 && [ -r /var/mnt/nas-bc5/game.pkg ] || stop "the NAS package is not there"
sed "s#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play\$#export KYTY_BC5_SAVEDATA_DIR=\${VZ_SAVE:?} \# exp 0439 vz2t439: a private save copy#" "$W/play-pkg.sh" > "$L"
[ "$(diff "$W/play-pkg.sh" "$L" | grep -c '^>')" = 1 ] || stop "the derived launcher is not 1 line changed"
mkdir -p "$SAVE" "$SH" && chmod 700 "$SH" && cp -a "$HOME/bc5-data/saves/TITLE2-20261117-0946-play/." "$SAVE/" && chmod -R u+w "$SAVE" || stop "save copy"
g0=$(gl); cd "$E" || exit 1
bash e0439.sh lock "exp0439 vz2t439 $T: the second title, function run $B s" > /dev/null 2>&1
trap 'bash "$E/e0439.sh" unlock > /dev/null 2>&1' EXIT
wl=$(ls -1 "/run/user/$(id -u)/" | grep -m1 -E '^wayland-[0-9]+$')
shot() { env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$wl DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1; }
echo "$(date '+%F %T') $T: binary $PIN, launcher $(md5sum < "$L" | cut -c1-8) (play-pkg.sh $(md5sum < "$W/play-pkg.sh" | cut -c1-8)), save $SAVE, GPU lines $g0"
systemd-run --user --collect --unit="bc5-0439-vz2t-$T" --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; exec env "$@"' _ VZ_SAVE="$SAVE" BC5_EMU="$BIN" BC5_PKG=/var/mnt/nas-bc5/game.pkg WAYLAND_DISPLAY="$wl" bash "$L" > /dev/null 2>&1
t=0; while ! pgrep "^kyty_emulator" > /dev/null && [ $t -lt 900 ]; do sleep 0.1; t=$((t + 1)); done
pgrep "^kyty_emulator" > /dev/null || stop "no emulator within 90 s"
t0=$(date +%s); why="bound $B s"
for at in 60 120 240; do
    while [ $(( $(date +%s) - t0 )) -lt $at ]; do pgrep "^kyty_emulator" > /dev/null || break 2; [ "$(gl)" = "$g0" ] || break 2; sleep 1; done
    shot "t${at}s"
done
while [ $(( $(date +%s) - t0 )) -lt "$B" ]; do
    pgrep "^kyty_emulator" > /dev/null || { why="the emulator ended by itself at $(( $(date +%s) - t0 )) s"; break; }
    [ "$(gl)" = "$g0" ] || { why="a GPU kernel line"; break; }
    sleep 1
done
pgrep "^kyty_emulator" > /dev/null && pkill -TERM "^kyty_emulator"
for k in $(seq 1 100); do pgrep "^kyty_emulator" > /dev/null || break; sleep 0.1; done
pgrep "^kyty_emulator" > /dev/null && pkill -KILL "^kyty_emulator"
sleep 3
echo "$(date '+%F %T') $T: end: $why; GPU lines $g0 -> $(gl); shots in $SH; the launcher's log ~/bc5-work/play-pkg-last.log"
