#!/usr/bin/env bash
# BC5 experiment 0214: put the APR read-ahead, on by default (patch_0214.diff = exp 0203's patch_0203.diff with
# KYTY_BC5_APR_READAHEAD defaulting to 4), into ~/src/KytyPlus and rebuild both shared builds: kytyplus-build (every
# shortcut but "lean") and kytyplus-build-lean. Only after the top session's GRANTED.
# Before: no emulator, no other session's lock, the patch applies. The old binaries and libAmpr.cpp are kept in
# ~/bc5-work/exp0214 (*.before-0214). A failed step puts libAmpr.cpp and both binaries back.
# Nothing else in src/ has changed since the shared builds (10:22:48 and 10:49:49), so ninja recompiles libAmpr.cpp
# only. usage: rebuild0214.sh   (on the box, from SSH; inside chain0214.sh the chain's lock line is reused)
set -u
E=$HOME/bc5-work/exp0214; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
N=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
L=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q "^exp 0214 |" "$LOCK"; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi
OWN=0
[ -s "$LOCK" ] || { OWN=1; echo "exp 0214 | rebuild of both shared builds, APR read-ahead on by default (GRANTED by the top session) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"; }
release() { [ "$OWN" = 1 ] && grep -q "^exp 0214 | rebuild " "$LOCK" 2> /dev/null && rm -f "$LOCK"; }
fail() {
  echo "FAILED: $*"
  cp -p "$E/src/libAmpr.before-0214.cpp" "$K/src/libs/libAmpr.cpp"
  cp -p "$E/kyty_emulator.before-0214" "$N"
  cp -p "$E/kyty_emulator-lean.before-0214" "$L"
  sync
  echo "libAmpr.cpp and both binaries put back: $(md5sum "$N" "$L" "$K/src/libs/libAmpr.cpp" | cut -c1-12 | tr '\n' ' ')"
  release
  exit 1
}
cd "$K" || { release; exit 1; }
# The patch went into the tree at 19:43:46 on the top session's go (sources only); then only the build is left.
APPLY=1
if cmp -s src/libs/libAmpr.cpp "$E/src/libAmpr.default-on.cpp"; then
  [ -s "$E/src/libAmpr.before-0214.cpp" ] || { echo "the patch is in, but there is no pre-patch copy: stop"; release; exit 1; }
  echo "patch_0214 is already in the tree; the pre-patch libAmpr.cpp is src/libAmpr.before-0214.cpp"
  APPLY=0
else
  git apply --check "$E/patch_0214.diff" || { echo "the patch does not apply: nothing changed"; release; exit 1; }
fi
for p in "$N:$E/kyty_emulator.before-0214" "$L:$E/kyty_emulator-lean.before-0214"; do  # a second run keeps the first copies
  [ -e "${p#*:}" ] || cp -p "${p%%:*}" "${p#*:}" || { echo "backup failed: nothing changed"; release; exit 1; }
done
if [ "$APPLY" = 1 ] && [ ! -e "$E/src/libAmpr.before-0214.cpp" ]; then
  cp -p src/libs/libAmpr.cpp "$E/src/libAmpr.before-0214.cpp" || { echo "backup failed: nothing changed"; release; exit 1; }
fi
echo "== $(date +%T) before:"; md5sum "$N" "$L" src/libs/libAmpr.cpp
[ "$APPLY" = 1 ] && { git apply "$E/patch_0214.diff" || fail "git apply"; }
cmp -s src/libs/libAmpr.cpp "$E/src/libAmpr.default-on.cpp" || fail "the patched libAmpr.cpp differs from src/libAmpr.default-on.cpp"
for B in kytyplus-build kytyplus-build-lean; do
  S=$(date +%s)
  distrobox enter ubuntu -- nice -n 10 cmake --build "$HOME/bc5-work/$B" --target kyty_emulator -j8 > "$R/build-$B.txt" 2>&1
  rc=$?
  echo "== $(date +%T) $B: build rc $rc after $(($(date +%s) - S)) s, $(grep -c "Building CXX object" "$R/build-$B.txt") units compiled: $(grep -o "[^ ]*\.cpp\.o" "$R/build-$B.txt" | sort -u | tr '\n' ' ')"
  grep -i "error\|warning: unused" "$R/build-$B.txt" | head -5
  [ $rc = 0 ] || fail "$B build (log $R/build-$B.txt)"
done
grep -q "bc5-apr-r%zu-%zu" <(strings "$N") || fail "the normal binary has no read-ahead"
grep -q "bc5-apr-r%zu-%zu" <(strings "$L") || fail "the lean binary has no read-ahead"
sync
echo "== $(date +%T) after (synced):"; md5sum "$N" "$L" src/libs/libAmpr.cpp; ls -la --time-style=+%T "$N" "$L" | awk '{print $6, $7}'
release
