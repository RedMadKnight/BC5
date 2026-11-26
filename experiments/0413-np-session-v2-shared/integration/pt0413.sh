#!/usr/bin/env bash
# exp 0413 private diagnostic build: the thread dump at the fault (runtimeLinker-thr.cpp only; libs.h is the original).
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; P=$W/exp0413/p; L=$W/BOX-LOCK; HERE=$(cd "$(dirname "$0")" && pwd)
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; exit 1; }
LINE="exp 0413 | private diagnostic build (thread dump), CPU only | $(date '+%F %T')"
printf '%s\n' "$LINE" > "$L.0413t"
if ! ln "$L.0413t" "$L" 2> /dev/null; then [ -s "$L" ] && { rm -f "$L.0413t"; echo "locked: $(cat "$L")"; exit 1; }; mv -fT "$L.0413t" "$L"; fi
rm -f "$L.0413t"
trap '[ "$(cat "$L" 2> /dev/null)" = "$LINE" ] && : > "$L"' EXIT
[ "$(md5sum < "$P/tree/src/libs/libs.h" | cut -c1-32)" = "$(md5sum < "$P/libs.h.orig" | cut -c1-32)" ] || { echo "libs.h is not the original"; exit 1; }
cp "$HERE/runtimeLinker-thr.cpp" "$P/tree/src/loader/runtimeLinker.cpp" || exit 1
distrobox enter ubuntu -- sh -c "cd '$P/build-normal' && nice -n 19 ninja kyty_emulator" < /dev/null > "$P/thr-build.log" 2>&1 || { grep -m6 "error" "$P/thr-build.log" | cut -c1-220; exit 1; }
echo "thr: $(md5sum < "$P/build-normal/src/kyty_emulator" | cut -d' ' -f1)"
