#!/usr/bin/env bash
# BC5 experiment 0260, integration: the timeout probe that syncs its dump and journal lines and journals a stuck buffer's
# waits, label writes and dispatches (patch0260.py, F317) into ~/src/KytyPlus and both shared builds. With the
# maintainer's approval of 2026-10-24 in the tcp session ("Zgoda na oba: (a) wprowadź zmianę sondy z exp 0260 do obu
# wspólnych buildów (kopie zapasowe, przebudowa jednego pliku, nowa łatka 0001, md5 dla nadzorcy) ..."), done as the box
# supervisor's int0258.sh does it: backups of the file and both binaries, the one file in, both builds' kyty_emulator
# target, md5s. Then patch 0001 is regenerated from the tree (git diff f266548, which reproduced the committed patch
# byte for byte, md5 caacbff8be0e, before). The probe acts only after a fence timeout and only with
# BC5_DIRECT_TIMEOUT_PROBE, which play-pkg.sh already sets for the normal build; in the lean build it is compiled out
# (BC5_DIAG_ENV is a null pointer there).
# usage: int0260.sh   (on the box, attended; no emulator)
set -u
E=$HOME/bc5-work/exp0260; I=$E/integration; LOCK=$HOME/bc5-work/BOX-LOCK; LOG=$I/int.out
K=$HOME/src/KytyPlus; T=$K/src/libs/bc5LleAgc.cpp; NEW=$E/src/bc5LleAgc.probe.cpp
mkdir -p "$I"
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
[ "$(md5sum < "$T" | cut -c1-8)" = 67859271 ] || { echo "the tree's bc5LleAgc.cpp is not 67859271: stop"; exit 1; }
[ "$(md5sum < "$NEW" | cut -c1-8)" = daca24cc ] || { echo "the probe file is not daca24cc: stop"; exit 1; }
[ "$(git -C "$K" diff f266548 | md5sum | cut -c1-12)" = caacbff8be0e ] || { echo "the tree no longer matches patch 0001 (caacbff8be0e): stop"; exit 1; }
echo "tcp exp 0260 integration: the timeout probe into both shared builds (no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
trap 'grep -q "^tcp exp 0260 integration" "$LOCK" 2> /dev/null && rm -f "$LOCK"' EXIT
{
  echo "== $(date +%T) backups"
  cp "$T" "$I/bc5LleAgc.cpp.before"
  cp -p "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" "$I/kyty_emulator.normal.before"
  cp -p "$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator" "$I/kyty_emulator.lean.before"
  md5sum "$I/kyty_emulator.normal.before" "$I/kyty_emulator.lean.before" | cut -c1-12
  cp "$NEW" "$T" # no -p: ninja must see a new mtime
  md5sum "$I/bc5LleAgc.cpp.before" "$T" | cut -c1-12
  for b in kytyplus-build kytyplus-build-lean; do
    echo "== $(date +%T) build $b"
    distrobox enter ubuntu -- nice -n 10 cmake --build "$HOME/bc5-work/$b" --target kyty_emulator -j8 2>&1 | grep -E "error|bc5LleAgc|Linking|FAILED" | tail -6
    echo "rc ${PIPESTATUS[0]}"
  done
  md5sum "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" "$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator" | cut -c1-12
  echo "probe formats in the normal binary: $(strings "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" | grep -c "timeout probe: wait op\|timeout probe: write op\|timeout probe: dispatch op")"
  git -C "$K" diff f266548 > "$I/0001-bc5-lle-agc.patch"
  echo "patch 0001 $(md5sum < "$I/0001-bc5-lle-agc.patch" | cut -c1-12), $(wc -c < "$I/0001-bc5-lle-agc.patch") bytes"
  echo "== $(date +%T) done"
} 2>&1 | tee -a "$LOG"
