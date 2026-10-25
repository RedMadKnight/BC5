#!/usr/bin/env bash
# BC5 experiment 0298, integration (the maintainer: "Tak, gra przeszła dalej. Wprowadź poprawkę PlayGo do obu
# wspólnych buildów."): edit0298.py's two edits in the shared tree, both shared builds rebuilt, and the three
# second-title launchers pointed at the module pack without libScePlayGo.sprx. Backups in exp0298/integration.
# usage: int0298.sh   (on the box, under the supervisor's BOX-LOCK, no emulator running)
set -eu
W=~/bc5-work; K=~/src/KytyPlus; E=$W/exp0298; I=$E/integration; L=$W/BOX-LOCK
m() { md5sum < "$1" | cut -c1-8; }
[ -s "$L" ] && { echo "the box is locked: $(cat "$L")"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running"; exit 1; }
SC=$K/src/loader/systemContent.cpp; PG=$K/src/libs/libPlayGo.cpp
[ "$(m "$SC")" = a3a786ff ] || { echo "systemContent.cpp is not a3a786ff"; exit 1; }
[ "$(m "$PG")" = 193cc47a ] || { echo "libPlayGo.cpp is not 193cc47a"; exit 1; }
[ "$(m $W/kytyplus-build/src/kyty_emulator)" = 893f8ab4 ] || { echo "normal is not 893f8ab4"; exit 1; }
[ "$(m $W/kytyplus-build-lean/src/kyty_emulator)" = fa8d15f5 ] || { echo "lean is not fa8d15f5"; exit 1; }
[ "$(m $W/play-pkg.sh)" = e6879ede ] && [ "$(m $W/play-pkg-log.sh)" = adde839c ] && [ "$(m $W/play-pkg-quiet.sh)" = 6f0e07ab ] || { echo "a launcher is not as read"; exit 1; }
N=$HOME/bc5-data/sysmodules-pack-hle-ampr-noplaygo
[ -f $N/libSceAgc.sprx ] && [ -f $N/libSceAgcDriver.sprx ] && [ -f $N/libScePsml.sprx ] && [ ! -e $N/libScePlayGo.sprx ] || { echo "the pack without PlayGo is not as made"; exit 1; }
echo "supervisor | exp 0298 integration: PlayGo plgx fix into both shared builds + launchers (maintainer yes); CPU only, no emulator | start $(date +%H:%M) | until ~$(date -d +15min +%H:%M)" > "$L"
trap 'grep -q "^supervisor | exp 0298 integration" "$L" 2> /dev/null && : > "$L"' EXIT
mkdir -p "$I"
cp "$SC" "$I/systemContent.cpp.before"; cp "$PG" "$I/libPlayGo.cpp.before"
cp $W/kytyplus-build/src/kyty_emulator "$I/kyty_emulator.normal-893f8ab4"
cp $W/kytyplus-build-lean/src/kyty_emulator "$I/kyty_emulator.lean-fa8d15f5"
for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do cp $W/$f "$I/$f.before-playgo"; done
python3 -I "$E/edit0298.py" "$SC" "$PG"
cmp "$SC" "$E/src/systemContent.cpp" && cmp "$PG" "$E/src/libPlayGo.cpp" && echo "tree files = the tested copies"
echo "tree systemContent.cpp $(m "$SC"), libPlayGo.cpp $(m "$PG")"
for b in kytyplus-build kytyplus-build-lean; do
  echo "== $(date +%T) build $b"
  distrobox enter ubuntu -- nice -n 10 cmake --build $W/$b --target kyty_emulator -j8 > "$I/build-$b.out" 2>&1 || { tail -30 "$I/build-$b.out"; exit 1; }
  echo "$b $(m $W/$b/src/kyty_emulator), trace strings $(strings $W/$b/src/kyty_emulator | grep -c 'bc5 playgo: ')"
done
OLD='export SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr'
NEW='export SHADPS4_SYSMODULES_PACK_DIR=$HOME/bc5-data/sysmodules-pack-hle-ampr-noplaygo  # 2026-10-25 (exp 0298, the maintainer'"'"'s yes): no libScePlayGo.sprx, the host answers PlayGo (100 chunks)'
for f in play-pkg.sh play-pkg-log.sh play-pkg-quiet.sh; do
  python3 - "$W/$f" "$OLD" "$NEW" <<'EOF'
import sys
p, old, new = sys.argv[1:]
s = open(p).read()
assert s.count(old + "\n") == 1, p
open(p, "w").write(s.replace(old + "\n", new + "\n"))
EOF
  bash -n "$W/$f"; echo "$f $(m $W/$f)"
done
echo "== $(date +%T) done"
