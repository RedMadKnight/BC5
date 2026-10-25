#!/usr/bin/env bash
# BC5 exp 0318 integration (the maintainer: "Tak, wprowadź poprawkę logu wysypań do wspólnych buildów po teście
# stabilności."): the crash handler's terminal block writes its diagnostics through RawLog to stderr, regardless of
# --printf-direction and the logging switch, and names the faulting rip as program file + offset.
set -eu
W=~/bc5-work; K=~/src/KytyPlus; E=$W/exp0318; I=$E/integration; L=$W/BOX-LOCK
F=src/loader/runtimeLinker.cpp
m() { md5sum < "$1" | cut -c1-8; }
[ -s "$L" ] && { echo "the box is locked: $(cat "$L")"; exit 1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running"; exit 1; }
[ "$(m $K/$F)" = f4bf3213 ] || { echo "$F is $(m $K/$F), not f4bf3213"; exit 1; }
[ "$(m $W/kytyplus-build/src/kyty_emulator)" = 226bcb82 ] || { echo "normal is not 226bcb82"; exit 1; }
[ "$(m $W/kytyplus-build-lean/src/kyty_emulator)" = 71ef2194 ] || { echo "lean is not 71ef2194"; exit 1; }
echo "supervisor | exp 0318 integration: crash-log diagnostics into both shared builds (maintainer yes); CPU only, no emulator | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$L"
trap 'grep -q "^supervisor | exp 0318 integration" "$L" 2> /dev/null && : > "$L"' EXIT
mkdir -p "$I"
cp "$K/$F" "$I/runtimeLinker.cpp.before"
cp $W/kytyplus-build/src/kyty_emulator "$I/kyty_emulator.normal-226bcb82"
cp $W/kytyplus-build-lean/src/kyty_emulator "$I/kyty_emulator.lean-71ef2194"
cd "$K"
git apply --check "$E/patch0001-crashlog.lf.diff"
git apply "$E/patch0001-crashlog.lf.diff"
echo "tree $F $(m $K/$F)"
for b in kytyplus-build kytyplus-build-lean; do
  echo "== $(date +%T) build $b"
  distrobox enter ubuntu -- nice -n 10 cmake --build $W/$b --target kyty_emulator -j8 > "$I/build-$b.out" 2>&1 || { tail -30 "$I/build-$b.out"; exit 1; }
  echo "$b $(m $W/$b/src/kyty_emulator), warnings in runtimeLinker: $(grep -c 'runtimeLinker.cpp.*warning' "$I/build-$b.out")"
done
echo "== $(date +%T) done"
