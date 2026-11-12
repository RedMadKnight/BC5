#!/usr/bin/env bash
# BC5 exp 0413 (private diagnostic): the a2ab53c7 tree built with -ftrivial-auto-var-init=<pattern|zero> into its own
# build dir under exp0413/p (the top's discriminator for an uninitialised host variable). CPU only, lock claimed by hard link.
# usage: pz0413.sh pattern|zero
set -u
ulimit -c 0
export LC_ALL=C
V=${1:?pattern or zero}; W=$HOME/bc5-work; P=$W/exp0413/p; D=$P/build-$V; L=$W/BOX-LOCK
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs"; exit 1; }
[ "$(md5sum < "$P/tree/src/loader/runtimeLinker.cpp" | cut -c1-8)" = aba94c24 ] || { echo "the tree is not a2ab53c7's"; exit 1; }
LINE="exp 0413 | private diagnostic build ($V auto-var-init), CPU only | $(date '+%F %T')"
printf '%s\n' "$LINE" > "$L.0413z"
if ! ln "$L.0413z" "$L" 2> /dev/null; then [ -s "$L" ] && { rm -f "$L.0413z"; echo "locked: $(cat "$L")"; exit 1; }; mv -fT "$L.0413z" "$L"; fi
rm -f "$L.0413z"
trap '[ "$(cat "$L" 2> /dev/null)" = "$LINE" ] && : > "$L"' EXIT
mkdir -p "$D/externals" && cp -p "$W/kytyplus-build/externals/ffmpeg-94dde08.zip" "$D/externals/"
distrobox enter ubuntu -- cmake -S "$P/tree" -B "$D" -U "*PIPEWIRE*" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang \
  -DCMAKE_CXX_COMPILER=clang++ -DKYTY_BUILD_LAUNCHER=OFF -DKYTY_BC5_BACKEND_SRC="$W/d19/export/backend" \
  -DKYTY_BC5_BACKEND_BUILD="$W/backend-ubuntu" "-DCMAKE_CXX_FLAGS=-ftrivial-auto-var-init=$V" "-DCMAKE_C_FLAGS=-ftrivial-auto-var-init=$V" \
  < /dev/null > "$D.configure.log" 2>&1 || { tail -5 "$D.configure.log"; exit 1; }
distrobox enter ubuntu -- sh -c "cd '$D' && nice -n 19 ninja kyty_emulator" < /dev/null > "$D.build.log" 2>&1 || { grep -m3 error: "$D.build.log"; exit 1; }
echo "$V: $(md5sum < "$D/src/kyty_emulator" | cut -d' ' -f1)"
