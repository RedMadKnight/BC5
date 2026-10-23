#!/usr/bin/env bash
# BC5 experiment 0243: vendor vgmstream's ATRAC9 decoder into ~/src/KytyPlus, apply port0243.py, rebuild both shared
# builds, under a BOX-LOCK line of the top session. Backups of the edited files and both binaries in before/.
set -u
E=$HOME/bc5-work/exp0243; K=$HOME/src/KytyPlus; LOCK=$HOME/bc5-work/BOX-LOCK; V=$K/3rdparty/vgmstream-atrac9
S=$HOME/bc5-work/exp0241/vgmstream
mkdir -p "$E/before" "$E/raw"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs"; exit 1; }
echo "top session | exp 0243 ATRAC9 vibration decoder into KytyPlus + rebuild of both shared builds (no emulator) | start $(date +%H:%M) | until ~$(date -d +20min +%H:%M)" > "$LOCK"
{
  echo "== $(date +%T) backups"
  cp "$K/src/libs/ajm/atrac9_decoder.h" "$E/before/atrac9_decoder.h"
  cp "$K/3rdparty/CMakeLists.txt" "$E/before/3rdparty-CMakeLists.txt"
  cp "$K/src/CMakeLists.txt" "$E/before/src-CMakeLists.txt"
  cp -p "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" "$E/before/kyty_emulator.normal"
  cp -p "$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator" "$E/before/kyty_emulator.lean"
  md5sum "$E"/before/* | cut -c1-12,33-
  echo "== vendor"
  mkdir -p "$V/src/coding/libs" "$V/src/util"
  cp "$S"/src/coding/libs/atrac9_dec.c "$S"/src/coding/libs/atrac9_dec.h "$S"/src/coding/libs/atrac9_internal.c \
     "$S"/src/coding/libs/atrac9_internal.h "$S"/src/coding/libs/atrac9_internal_data.h "$V/src/coding/libs/"
  cp "$S/src/util/bitstream_msb.h" "$V/src/util/"
  cp "$S/COPYING" "$V/COPYING"
  cat > "$V/README.BC5" << 'R'
vgmstream's ATRAC9 decoder, vendored by BC5 (experiment 0243, HANDOFF F300) for the ATRAC9 vibration channel
configurations 6 and 7, which LibAtrac9 does not know.
Source: https://github.com/vgmstream/vgmstream, commit 7c520e8f9b078dfde2f84f1b5bcbad0c6c415806 (2026-10-10),
files src/coding/libs/atrac9_dec.{c,h}, atrac9_internal.{c,h}, atrac9_internal_data.h and src/util/bitstream_msb.h,
unchanged. Licence: ISC, see COPYING (vgmstream's own). The directory layout is kept so the relative include of
bitstream_msb.h resolves.
R
  find "$V" -type f | sort
  echo "== edit"
  python3 -I "$E/port0243.py" || exit 1
  echo "== $(date +%T) build normal"
  distrobox enter ubuntu -- nice -n 10 cmake --build "$HOME/bc5-work/kytyplus-build" --target kyty_emulator -j8 2>&1 | tail -25
  echo "rc ${PIPESTATUS[0]}"
  echo "== $(date +%T) build lean"
  distrobox enter ubuntu -- nice -n 10 cmake --build "$HOME/bc5-work/kytyplus-build-lean" --target kyty_emulator -j8 2>&1 | tail -15
  echo "rc ${PIPESTATUS[0]}"
  ls -la --time-style=+%H:%M:%S "$HOME/bc5-work/kytyplus-build/src/kyty_emulator" "$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator"
  for b in kytyplus-build kytyplus-build-lean; do nm -C "$HOME/bc5-work/$b/src/kyty_emulator" 2>/dev/null | grep -c " T atrac9_init"; done
  echo "== $(date +%T) done"
} > "$E/raw/port.out" 2>&1
grep -q "^top session | exp 0243" "$LOCK" 2> /dev/null && rm -f "$LOCK"
