#!/usr/bin/env bash
# exp 0413 private diagnostic build: the call ring (libs-ring.h) and crash walk 5 in the private tree; originals kept beside.
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; P=$W/exp0413/p; L=$W/BOX-LOCK; HERE=$(cd "$(dirname "$0")" && pwd)
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; exit 1; }
LINE="exp 0413 | private diagnostic build (call ring), CPU only | $(date '+%F %T')"
printf '%s\n' "$LINE" > "$L.0413r"
if ! ln "$L.0413r" "$L" 2> /dev/null; then [ -s "$L" ] && { rm -f "$L.0413r"; echo "locked: $(cat "$L")"; exit 1; }; mv -fT "$L.0413r" "$L"; fi
rm -f "$L.0413r"
trap '[ "$(cat "$L" 2> /dev/null)" = "$LINE" ] && : > "$L"' EXIT
[ -e "$P/libs.h.orig" ] || cp -p "$P/tree/src/libs/libs.h" "$P/libs.h.orig"
cp "$HERE/libs-ring.h" "$P/tree/src/libs/libs.h" && cp "$HERE/runtimeLinker-walk5.cpp" "$P/tree/src/loader/runtimeLinker.cpp" || exit 1
distrobox enter ubuntu -- sh -c "cd '$P/build-normal' && nice -n 19 ninja kyty_emulator" < /dev/null > "$P/ring-build.log" 2>&1 || { grep -m5 "error" "$P/ring-build.log" | cut -c1-220; exit 1; }
echo "ring: $(md5sum < "$P/build-normal/src/kyty_emulator" | cut -d' ' -f1)"
