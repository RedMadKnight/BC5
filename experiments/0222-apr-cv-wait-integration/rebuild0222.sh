#!/usr/bin/env bash
# BC5 experiment 0222: put exp 0216's condition-variable wait for the APR read-ahead readers (patch_0216.diff, tested in
# exps 0216 and 0220, F276 and F280) into ~/src/KytyPlus and rebuild both shared builds: kytyplus-build (every shortcut
# but "lean") and kytyplus-build-lean. exp 0214's rebuild0214.sh with this patch. Only after the user's approval and the
# top session's Go; inside chain0222.sh the chain's lock line is reused.
# Before: no emulator, no other session's lock, the tree's libAmpr.cpp is the pre-0216 file (md5 387bc07c..., patch
# 0001's blob 323e90b) or already the patched one, no other source file newer than the shared binaries. The old
# binaries and libAmpr.cpp are kept in ~/bc5-work/exp0222 (*.before-0216). A failed step puts libAmpr.cpp (with a new
# mtime, so that ninja recompiles it next time) and both binaries back.
# usage: rebuild0222.sh   (on the box)
set -u
E=$HOME/bc5-work/exp0222; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK; K=$HOME/src/KytyPlus
N=$HOME/bc5-work/kytyplus-build/src/kyty_emulator
L=$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator
P=$HOME/bc5-work/exp0216/patch_0216.diff
NEW=$HOME/bc5-work/exp0216/src/libAmpr.cv-wait.cpp   # md5 eaef1da1..., the source of the tested binary
OLD_MD5=387bc07c44b51026049e67089e08b96f
mkdir -p "$R" "$E/src"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running: not started"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q "^exp 0222 |" "$LOCK"; then echo "the box is locked: $(cat "$LOCK")"; exit 1; fi
OWN=0
[ -s "$LOCK" ] || { OWN=1; echo "exp 0222 | rebuild of both shared builds with patch_0216 (approved) | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$LOCK"; }
release() { [ "$OWN" = 1 ] && grep -q "^exp 0222 | rebuild " "$LOCK" 2> /dev/null && rm -f "$LOCK"; }
fail() {
  echo "FAILED: $*"
  cp "$E/src/libAmpr.before-0216.cpp" "$K/src/libs/libAmpr.cpp"  # not -p: a new mtime makes ninja recompile it
  cp -p "$E/kyty_emulator.before-0216" "$N"
  cp -p "$E/kyty_emulator-lean.before-0216" "$L"
  sync
  echo "libAmpr.cpp and both binaries put back: $(md5sum "$N" "$L" "$K/src/libs/libAmpr.cpp" | cut -c1-12 | tr '\n' ' ')"
  release
  exit 1
}
cd "$K" || { release; exit 1; }
# Other sources changed since the shared builds would come in with this rebuild: stop.
OTHER=$(find src -newer "$L" -type f ! -path src/libs/libAmpr.cpp | head -5)
[ -z "$OTHER" ] || { echo "sources newer than the lean binary besides libAmpr.cpp: $OTHER: stop"; release; exit 1; }
APPLY=1
if cmp -s src/libs/libAmpr.cpp "$NEW"; then
  [ -s "$E/src/libAmpr.before-0216.cpp" ] || { echo "the patch is in, but there is no pre-patch copy: stop"; release; exit 1; }
  echo "patch_0216 is already in the tree; the pre-patch libAmpr.cpp is src/libAmpr.before-0216.cpp"
  APPLY=0
else
  [ "$(md5sum < src/libs/libAmpr.cpp | cut -c1-32)" = "$OLD_MD5" ] || { echo "the tree's libAmpr.cpp is neither the pre-0216 file nor the patched one: stop"; release; exit 1; }
  git apply --check "$P" || { echo "the patch does not apply: nothing changed"; release; exit 1; }
fi
for p in "$N:$E/kyty_emulator.before-0216" "$L:$E/kyty_emulator-lean.before-0216"; do  # a second run keeps the first copies
  [ -e "${p#*:}" ] || cp -p "${p%%:*}" "${p#*:}" || { echo "backup failed: nothing changed"; release; exit 1; }
done
if [ "$APPLY" = 1 ] && [ ! -e "$E/src/libAmpr.before-0216.cpp" ]; then
  cp -p src/libs/libAmpr.cpp "$E/src/libAmpr.before-0216.cpp" || { echo "backup failed: nothing changed"; release; exit 1; }
fi
echo "== $(date +%T) before:"; md5sum "$N" "$L" src/libs/libAmpr.cpp
[ "$APPLY" = 1 ] && { git apply "$P" || fail "git apply"; }
cmp -s src/libs/libAmpr.cpp "$NEW" || fail "the patched libAmpr.cpp differs from exp 0216's tested source"
git diff f266548 -- src/libs/libAmpr.cpp > "$R/git-diff-f266548-after.txt"
for B in kytyplus-build kytyplus-build-lean; do
  S=$(date +%s)
  distrobox enter ubuntu -- nice -n 10 cmake --build "$HOME/bc5-work/$B" --target kyty_emulator -j8 > "$R/build-$B.txt" 2>&1
  rc=$?
  echo "== $(date +%T) $B: build rc $rc after $(($(date +%s) - S)) s, $(grep -c "Building CXX object" "$R/build-$B.txt") units compiled: $(grep -o "[^ ]*\.cpp\.o" "$R/build-$B.txt" | sort -u | tr '\n' ' ')"
  sed 's/\x1b\[[0-9;]*m//g' "$R/build-$B.txt" | grep -E "error|warning:" | cut -c1-200 | head -6
  [ $rc = 0 ] || fail "$B build (log $R/build-$B.txt)"
done
grep -q "bc5-apr-r%zu-%zu" <(strings "$N") || fail "the normal binary has no read-ahead"
grep -q "bc5-apr-r%zu-%zu" <(strings "$L") || fail "the lean binary has no read-ahead"
sync
echo "== $(date +%T) after (synced):"; md5sum "$N" "$L" src/libs/libAmpr.cpp; ls -la --time-style=+%T "$N" "$L" | awk '{print $6, $7}'
release
