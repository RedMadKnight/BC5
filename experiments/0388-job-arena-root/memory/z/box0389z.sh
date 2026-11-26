#!/usr/bin/env bash
# BC5 exp 0388, memory: the private normal build with the zero skip, from today's shared tree. Under the lock: the tree's
# bc5LleAgc.cpp must be the shared one, the private unit the laptop's; compiled with the shared build's command, linked with
# the shared objects. Writes only ~/bc5-work/exp0388/z. usage: bash box0389z.sh   (beside build0389z.py, the unit, the header)
set -u
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work; Z=$W/exp0388/z; HERE=$(cd "$(dirname "$0")" && pwd); B=$W/kytyplus-build; TREE=$HOME/src/KytyPlus
m() { md5sum < "$1" | cut -c1-8; }
stop() { echo "z STOP: $*"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && stop "an emulator runs"
[ "$(m "$B/src/kyty_emulator")" = 4d2b1b1d ] || stop "the shared normal is not 4d2b1b1d"
[ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = d18b4482 ] || stop "the tree's unit is not d18b4482"
[ "$(m "$HERE/bc5LleAgc.cpp")" = 3a77e0ac ] && [ "$(m "$HERE/zero_skip.hpp")" = b29c66c4 ] || stop "the kit is not the pins"
bash "$W/exp0388/s/box0388.sh" claim "exp 0388: private zero-skip build, CPU only" 20 || exit 1
trap 'bash "$W/exp0388/s/box0388.sh" release' EXIT
rm -rf "$Z/src" "$Z/obj"; mkdir -p "$Z/src/src/libs" "$Z/src/src/bc5"
cp "$HERE/bc5LleAgc.cpp" "$Z/src/src/libs/" && cp "$HERE/zero_skip.hpp" "$Z/src/src/bc5/" || stop "copy"
distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$Z/compdb.json" 2> "$Z/compdb.err" || stop "compdb"
distrobox enter ubuntu -- env LC_ALL=C python3 -I "$HERE/build0389z.py" "$Z/compdb.json" "$Z/src" "$Z" "$B" "$Z/kyty_emulator" > "$Z/build.out" 2>&1
rc=$?; echo "build rc $rc; errors $(grep -c 'error:' "$Z/build.out")"; grep -n "error:" "$Z/build.out" | head -12 | cut -c1-200
[ "$rc" = 0 ] && [ -x "$Z/kyty_emulator" ] || stop "build failed"
[ "$(strings "$Z/kyty_emulator" | grep -c 'BC5_DIRECT_ZERO_SKIP\|BC5_DIRECT_ZERO_SLICES')" -ge 2 ] && [ "$(strings "$Z/kyty_emulator" | grep -c 'job-arena fix APPLIED')" = 1 ] || stop "the switches or the fix are not in it"
echo "z binary $(md5sum < "$Z/kyty_emulator" | cut -d' ' -f1); shared $(m "$B/src/kyty_emulator")"
