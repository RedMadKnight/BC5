#!/usr/bin/env bash
# BC5 exp 0420: start the new menu (the empty window) for 25 s through the private launcher and take one screenshot of
# the desktop; then end it. No game is started. One lock line. The menu's files are private
# (~/bc5-work/exp0420/menu); the games root is the real one, read only (the menu only lists it).
# usage (on the box): look0420.sh normal|lean
set -u
export LC_ALL=C
W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; X=$W/exp0420; K=$X/kit
V=${1:?normal or lean}
pgrep '^kyty_emulator' > /dev/null && { echo "look0420: an emulator runs: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0420: the new menu's empty window for 25 s, $V build, one screenshot (no game)" 3 || { echo "look0420: NOT STARTED"; exit 1; }
trap chain_release EXIT
WL=$(ls "/run/user/$(id -u)/" | grep -m1 '^wayland-[0-9]*$')
mkdir -p "$X/menu" "$X/shots"
lean=0; [ "$V" = lean ] && lean=1
distrobox enter ubuntu -- env WAYLAND_DISPLAY="$WL" KYTY_BC5_MENU_DIR="$X/menu" BC5_MOUNT_BIN="$X/bc5-tools/release/bc5-mount" \
    BC5_EMU="$P/build-normal/src/kyty_emulator" BC5_EMU_LEAN="$P/build-lean/src/kyty_emulator" BC5_LEAN=$lean BC5_LOGS=1 \
    bash "$K/play-any.sh" < /dev/null > "$X/look-$V.out" 2>&1 &
LP=$!
for _ in $(seq 1 60); do pgrep '^kyty_emulator' > /dev/null && break; sleep 0.5; done
EP=$(pgrep -o '^kyty_emulator')
sleep 12
shot=$X/shots/menu-$V-$(date +%H%M%S).png
if command -v spectacle > /dev/null; then
    XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$WL DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 20 spectacle -b -n -f -o "$shot" > /dev/null 2>&1
fi
alive=no; [ -n "$EP" ] && [ -d "/proc/$EP" ] && alive=yes
echo "menu ($V): emulator ${EP:-none}, alive after 12 s: $alive; screenshot: $([ -s "$shot" ] && echo "$shot" || echo none)"
[ -n "$EP" ] && kill "$EP" 2> /dev/null
for _ in $(seq 1 20); do pgrep '^kyty_emulator' > /dev/null || break; sleep 0.5; done
kill "$LP" 2> /dev/null; wait "$LP" 2> /dev/null
pkill -u "$USER" -f "$K/play-any.sh" 2> /dev/null
echo "the launcher's last lines:"; tail -5 "$X/look-$V.out" | cut -c1-200
echo "the menu log's last lines:"; tail -5 "$W/play-menu$([ "$V" = lean ] && echo -lean)-last.log" | cut -c1-200
echo "kernel lines since the start: $(sudo -n dmesg 2> /dev/null | tail -20 | grep -c -i 'amdgpu.*\(timeout\|fault\)')"
