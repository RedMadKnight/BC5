#!/usr/bin/env bash
# exp 0446 (2026-11-26, the maintainer's check): one title from its NAS package through his own launchers, unchanged.
#   nas446.sh <tag> any|pkg <package> <seconds>
#     any: BC5_LEAN=1 BC5_LOGS=1 ~/bc5-work/play-any.sh <package>     (his shortcut's path)
#     pkg: BC5_LEAN=1 BC5_LOGS=1 BC5_PKG=<package> ~/bc5-work/play-pkg.sh  (what play-any.sh runs for a package it
#          finds no installed copy of; used when an installed copy would otherwise be chosen)
#   Started through the user manager. Per second: io pressure, bc5-mount rchar (NAS reads) and RSS, enp4s0 rx, MemAvailable,
#   swap; memory guard 1,200 MiB (SIGTERM to the emulator); a shot every 10 s; SIGTERM at <seconds>. Own BOX-LOCK line.
#   Nothing of his is edited; no input is sent (no gameplay: his live saves stay untouched).
set -u
export LC_ALL=C
TAG=$1; MODE=$2; PKG=$3; SECS=$4
W=$HOME/bc5-work; X=$W/exp0446; R=$X/raw; LOCK=$W/BOX-LOCK; SD=$HOME/bc5-data/priv/t1-shots/$TAG
mkdir -p "$R" "$SD"; chmod 700 "$HOME/bc5-data/priv/t1-shots"
say() { echo "$(date +%T) $TAG: $*" | tee -a "$R/$TAG-nas.txt"; }
[ -e "$R/$TAG-nas.txt" ] && { echo "tag used"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; exit 1; }
pgrep -x bc5-mount > /dev/null && { echo "a bc5-mount runs"; exit 1; }
[ -r "$PKG" ] || { echo "no package $PKG"; exit 1; }
LINE="exp 0446 (x446) | NAS check $TAG ($MODE, $SECS s), token $(date +%s)$$ | $(date '+%F %T')"
# X446_HELD (11-26, the top session: one lock line for a whole chain): when BOX-LOCK holds exactly that line, this run
# uses it and leaves it in place at its end; otherwise its own line is claimed as before
if [ -n "${X446_HELD:-}" ] && [ -f "$LOCK" ] && [ "$(cat "$LOCK")" = "$X446_HELD" ]; then
    LINE=$X446_HELD; unlock() { :; }
else
[ -e "$LOCK" ] || touch "$LOCK"; tl=$LOCK.n446-$$.new; al=$LOCK.n446-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "locked: $(cat "$LOCK")"; exit 1; fi
rm -f "$al" "$tl"
unlock() { if grep -qxF -- "$LINE" "$LOCK"; then grep -vxF -- "$LINE" "$LOCK" > "$LOCK.n446-$$.rel"; mv -fT "$LOCK.n446-$$.rel" "$LOCK"; fi; }
fi
trap unlock EXIT
kcount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -v TMZ | grep -ciE 'timeout|reset|page fault|wedged'; }
K0=$(kcount); say "start: lock taken; package $PKG ($(stat -c %s "$PKG") B), mode $MODE, lean ${X446_LEAN:-1}; amdgpu fault/reset lines before $K0; /var/home free $(df -B1M --output=avail /var/home | tail -1 | tr -d ' ') MiB"
WL=$(ls "/run/user/$(id -u)/" | grep -m1 '^wayland-[0-9]*$')
ENVS=(XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$WL BC5_LEAN=${X446_LEAN:-1} BC5_LOGS=1)
if [ "$MODE" = any ]; then CMD=("$W/play-any.sh" "$PKG")
elif [ "$MODE" = drv ]; then ENVS+=("BC5_PKG=$PKG"); CMD=("$X/play-pkg-446.sh")  # his play-pkg.sh with 3 lines changed: lean log, mount log, working directory
else ENVS+=("BC5_PKG=$PKG"); CMD=("$W/play-pkg.sh"); fi
read -r -a XE <<< "${X446_ENV:-}"; ENVS+=("${XE[@]}")
[ "${X446_MH:-0}" = 1 ] && mkdir -p "$R/$TAG-mh" && ENVS+=(MANGOHUD=1 "MANGOHUD_CONFIG=fps_only=1,alpha=0,background_alpha=0,autostart_log=1,log_interval=0,output_folder=$R/$TAG-mh,log_duration=$((SECS - 10))")
say "words added: ${XE[*]:-none}; MangoHud log ${X446_MH:-0}"
st=$(date +%s)
setsid nohup bash -c 'systemd-run --user --scope --quiet --collect /usr/bin/env "$@"; echo "launcher exit $?"' _ "${ENVS[@]}" "${CMD[@]}" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
echo "# el io_some io_full mount_rchar_MiB mount_MiBs mount_rss_MiB nas_rx_MiBs avail_MiB swap_MiB" > "$R/$TAG-io.txt"
( prx=0; pm=0; while [ $(( $(date +%s) - st )) -lt $((SECS + 40)) ]; do
    el=$(( $(date +%s) - st ))
    read -r s f < <(awk '/^some/ {split($2,a,"=")} /^full/ {split($2,b,"=")} END {print a[2], b[2]}' /proc/pressure/io)
    mp=$(pgrep -x bc5-mount | head -1); ep=$(pgrep '^kyty_emulator' | head -1); mr=0; rss=0
    [ -n "$mp" ] && { mr=$(awk '/^rchar/ {print int($2 / 1048576)}' /proc/$mp/io 2> /dev/null); rss=$(awk '/VmRSS/ {print int($2 / 1024)}' /proc/$mp/status 2> /dev/null); }
    rx=$(awk '/enp4s0:/ {print int($2 / 1048576)}' /proc/net/dev)
    a=$(awk '/MemAvailable/ {print int($2 / 1024)}' /proc/meminfo); sw=$(awk '/SwapTotal/ {t=$2} /SwapFree/ {f=$2} END {print int((t-f)/1024)}' /proc/meminfo)
    echo "$el $s $f ${mr:-0} $(( ${mr:-0} - pm )) ${rss:-0} $(( rx - prx )) $a $sw ${ep:+emu}" >> "$R/$TAG-io.txt"
    pm=${mr:-0}; prx=$rx
    if [ "$a" -lt "${X446_GUARD:-1200}" ] && [ -n "$ep" ]; then echo "GUARD at $el s: available $a MiB" >> "$R/$TAG-nas.txt"; kill "$ep"; fi
    sleep 1; done ) &
smp=$!
( sleep 10; el=10; while [ "$el" -lt "$SECS" ]; do env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$WL DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SD/t${el}s.png" > /dev/null 2>&1; sleep 9; el=$(( $(date +%s) - st )); done ) &
shp=$!
seen=0; while [ $(( $(date +%s) - st )) -lt "$SECS" ]; do
    ep=$(pgrep '^kyty_emulator' | head -1)
    if [ -n "$ep" ]; then
        [ $seen = 0 ] && { seen=1; say "emulator up at $(( $(date +%s) - st )) s: $(tr '\0' ' ' < /proc/$ep/cmdline | cut -c1-160)"; }
        if [ $seen = 1 ] && [ $(( $(date +%s) - st )) -ge 30 ]; then seen=2; mp=$(pgrep -x bc5-mount | head -1)
            say "bc5-mount at 30 s: $(tr '\0' ' ' < /proc/$mp/cmdline 2> /dev/null | cut -c1-200); open: $(ls -l /proc/$mp/fd 2> /dev/null | grep -oE '/var/mnt/nas[^ ]*|/home/[^ ]*\.pkg|/home/[^ ]*ffpfsc' | sort -u | tr '\n' ' ')"; fi
    elif [ $seen -ge 1 ]; then say "the emulator ended by itself at $(( $(date +%s) - st )) s"; break; fi
    sleep 1
done
ep=$(pgrep '^kyty_emulator' | head -1); [ -n "$ep" ] && { say "stop: SIGTERM at $(( $(date +%s) - st )) s"; kill "$ep"; }
for _ in $(seq 40); do pgrep '^kyty_emulator' > /dev/null || pgrep -x bc5-mount > /dev/null || break; sleep 1; done
kill "$shp" "$smp" 2> /dev/null; wait 2> /dev/null
say "launcher: $(tail -1 "$R/$TAG-launch.out"); leftover: $(pgrep -ax 'kyty_emulator|bc5-mount' | cut -c1-60 | tr '\n' ' ')"
for f in play-pkg-last.log play-pkg-mount.log play-menu-lean-last.log; do [ -f "$W/$f" ] && [ $(stat -c %Y "$W/$f") -ge "$st" ] && cp -p "$W/$f" "$R/$TAG-$f"; done
K1=$(kcount); say "amdgpu fault/reset lines after $K1 (before $K0); shots $(ls "$SD" | wc -l) in $SD; min available $(awk '!/^#/ {print $8}' "$R/$TAG-io.txt" | sort -n | head -1) MiB, max swap $(awk '!/^#/ {print $9}' "$R/$TAG-io.txt" | sort -n | tail -1) MiB"
