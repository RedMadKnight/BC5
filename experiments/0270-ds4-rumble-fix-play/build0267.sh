#!/usr/bin/env bash
# BC5 experiment 0267, box side, in the granted slot: a private build of the rumble-thread / pad-speaker diff,
# exp 0252's one-TU + relink pattern with two units. Copies the shared tree's audio.cpp and controller.cpp
# (read-only), applies raw/rumble-thread-and-speaker-off.diff to the copies, takes the shared normal build's
# compile database (read-only) and runs build0267.py in the ubuntu distrobox: the two objects go to
# ~/bc5-work/exp0267/obj, the link to ~/bc5-work/exp0267/kyty_emulator from the shared build's other objects.
# So the private binary is exactly today's shared normal build plus the diff. Writes only under
# ~/bc5-work/exp0267; holds one BOX-LOCK line meanwhile; CPU only, nice 10 / ionice idle.
# Every identity check stops the script: the shared binary (8c63d974), bc5LleAgc.cpp (daca24cc),
# libSaveData.cpp (cafb1a54) in ~/src/KytyPlus, the diff applying cleanly to audio.cpp and controller.cpp,
# and the shared binary's md5 unchanged afterwards.
# Run on the host: bash ~/bc5-work/exp0267/build0267.sh    (log: ~/bc5-work/exp0267/build.log)
set -u
E=~/bc5-work/exp0267
SRC=~/src/KytyPlus
SHARED=~/bc5-work/kytyplus-build
DIFF=$E/rumble-thread-and-speaker-off.diff
EXPECT_BIN=${EXPECT_BIN:-8c63d974}
exec > >(tee -a "$E/build.log") 2>&1
say() { printf '[build0267 %s] %s\n' "$(date +%H:%M:%S)" "$*"; }
stop() { say "STOP: $*"; exit 1; }
md8() { md5sum "$1" | cut -c1-8; }
cd ~/bc5-work || exit 1
pgrep '^kyty_emulator' >/dev/null && stop "an emulator runs"
[ -s BOX-LOCK ] && stop "BOX-LOCK held: $(cat BOX-LOCK)"
[ -f "$DIFF" ] || stop "missing $DIFF"
[ -f "$E/build0267.py" ] || stop "missing $E/build0267.py"
echo "anyps5-ports exp 0267 | private build of audio.cpp + controller.cpp (two TUs + relink, CPU only, nice 10) | start $(date +%H:%M) | until ~$(date -d '+10 min' +%H:%M)" > BOX-LOCK
trap 'grep -q "exp 0267 | private build" ~/bc5-work/BOX-LOCK 2>/dev/null && rm -f ~/bc5-work/BOX-LOCK' EXIT

say "identity of the shared tree and build"
BIN0=$(md8 "$SHARED/src/kyty_emulator")
say "  shared normal binary $BIN0 ($(ls -la --time-style=+%m-%d_%H:%M "$SHARED/src/kyty_emulator" | awk '{print $5, $6}'))"
[ "$BIN0" = "$EXPECT_BIN" ] || stop "shared binary is $BIN0, expected $EXPECT_BIN (EXPECT_BIN=<md5-8> to override after a rebuild)"
( cd "$SRC" && say "  tree HEAD $(git rev-parse --short HEAD), dirty files $(git status --porcelain | wc -l)" )
A=$(md8 "$SRC/src/libs/bc5LleAgc.cpp");  say "  bc5LleAgc.cpp   $A"; [ "$A" = daca24cc ] || stop "bc5LleAgc.cpp is $A, expected daca24cc"
A=$(md8 "$SRC/src/libs/libSaveData.cpp"); say "  libSaveData.cpp $A"; [ "$A" = cafb1a54 ] || stop "libSaveData.cpp is $A, expected cafb1a54"
say "  audio.cpp       $(md8 "$SRC/src/libs/audio.cpp")"
say "  controller.cpp  $(md8 "$SRC/src/libs/controller.cpp")"
[ -n "${EXPECT_AUDIO:-}" ] && { [ "$(md8 "$SRC/src/libs/audio.cpp")" = "$EXPECT_AUDIO" ] || stop "audio.cpp is not $EXPECT_AUDIO"; }
[ -n "${EXPECT_CONTROLLER:-}" ] && { [ "$(md8 "$SRC/src/libs/controller.cpp")" = "$EXPECT_CONTROLLER" ] || stop "controller.cpp is not $EXPECT_CONTROLLER"; }

say "copy the two units and apply the diff"
rm -rf "$E/src"; mkdir -p "$E/src/libs"
cp "$SRC/src/libs/audio.cpp" "$SRC/src/libs/controller.cpp" "$E/src/libs/"
# The Bazzite host has no patch(1); git apply outside a repository applies a unified diff the same way.
# controller.cpp is CRLF on the box (patch 0001 writes it so) and the diff is LF, so the diff goes on with
# --ignore-whitespace and each file is then normalised back to the line endings it had.
for f in audio.cpp controller.cpp; do
  crlf=$(grep -c $'' "$E/src/libs/$f")
  ( cd "$E" && git apply --check --ignore-whitespace --include="src/libs/$f" "$DIFF" > "$E/patch-check-$f.log" 2>&1 ) || { cat "$E/patch-check-$f.log"; stop "the diff does not apply to today's $f"; }
  ( cd "$E" && git apply --ignore-whitespace --include="src/libs/$f" "$DIFF" ) || stop "git apply failed for $f"
  if [ "$crlf" -gt 0 ]; then sed -i 's/$//; s/$//' "$E/src/libs/$f"; else sed -i 's/$//' "$E/src/libs/$f"; fi
  say "  $f: diff applied ($( [ "$crlf" -gt 0 ] && echo CRLF || echo LF ) kept)"
done
grep -q RumbleThread "$E/src/libs/controller.cpp" && grep -q pad_nb "$E/src/libs/audio.cpp" || stop "diff markers missing after patch"
say "  patched audio.cpp      $(md8 "$E/src/libs/audio.cpp")"
say "  patched controller.cpp $(md8 "$E/src/libs/controller.cpp")"

say "compile database of the shared build (read-only) and the two-unit build + relink in the ubuntu distrobox"
distrobox enter ubuntu -- sh -c "cd ~/bc5-work/kytyplus-build && nice -n 10 ninja -t compdb -x > $E/compdb.json" || stop "compdb failed"
distrobox enter ubuntu -- nice -n 10 ionice -c3 python3 -I "$E/build0267.py" "$E/compdb.json" || stop "build0267.py failed (see $E/build.log)"
[ -x "$E/kyty_emulator" ] || stop "no private binary produced"

BIN1=$(md8 "$SHARED/src/kyty_emulator")
[ "$BIN1" = "$BIN0" ] || stop "the shared binary CHANGED during the build ($BIN0 -> $BIN1): investigate before using anything"
say "done: $E/kyty_emulator md5 $(md8 "$E/kyty_emulator") ($(ls -la --time-style=+%H:%M "$E/kyty_emulator" | awk '{print $5, $6}')); shared normal binary still $BIN1"
