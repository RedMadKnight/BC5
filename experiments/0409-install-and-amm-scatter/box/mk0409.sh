#!/bin/bash
set -eu
W=$HOME/bc5-work; X=$W/exp0409; E8=$W/exp0401e8; D=$HOME/Pulpit
# 1. launchers
sed -e "s|^EMU=.*|EMU=$X/bin/kyty_emulator  # exp 0409: the private build|" \
    -e "s|^LOG=.*|LOG=$X/play-last.log  # exp 0409: own log|" \
    -e "s|^MLOG=.*|MLOG=$X/play-pkg-mount.log|" \
    -e "s|^BM=.*|BM=$X/tools-target/release/bc5-mount|" "$E8/play-pkg-0401-dir.sh" > "$X/play-pkg-0409.sh"
sed -e "s|^EMU=.*|EMU=$X/bin/kyty_emulator|" \
    -e "s|^LOG=~/bc5-work/play-menu-last.log|LOG=$X/play-menu-last.log|" \
    -e "s|^PKG_SCRIPT=.*|PKG_SCRIPT=$X/play-pkg-0409.sh|" \
    -e "s|^BM=.*|BM=$X/tools-target/release/bc5-mount|" "$X/task2/play-any.sh" > "$X/play-any-0409.sh"
chmod +x "$X/play-pkg-0409.sh" "$X/play-any-0409.sh"; bash -n "$X/play-pkg-0409.sh"; bash -n "$X/play-any-0409.sh"
grep -n "^EMU=\|^PKG_SCRIPT=\|^BM=\|^LOG=" "$X/play-pkg-0409.sh" "$X/play-any-0409.sh" | cut -c1-150
# 2. the install record for the hand-unpacked second title
G=$HOME/bc5-data/games/PPSA03671
[ -f "$G/.bc5-install.json" ] || cat > "$G/.bc5-install.json" <<EOF
{
  "image": "/var/mnt/nas-bc5/game.pkg",
  "image_size": 101814213551,
  "file_count": 309,
  "total_bytes": 196702588158,
  "date": "2026-11-08",
  "note": "adopted by hand: files copied with cp from the package mounted by bc5-mount (copy rc=0, 309 files, 196702588158 bytes); not hash-verified"
}
EOF
# 3. shortcuts, next to the existing unpacked one
SRC="$D/BC5 emulator (test 0401 unpacked).desktop"
mkd() { # name, extra env, run-env file or "", launcher
  out="$D/BC5 emulator ($1).desktop"; cp -p "$SRC" "$out"
  sed -i "s/^Name=.*/Name=BC5 emulator ($1)/; s/^Comment=/Comment=[$1, top 2026-11-09] e10: e8 + AMM scatter + install menu. /" "$out"
  sed -i "s|$E8/play-pkg-0401-dir.sh|$4|" "$out"
  sed -i "s|/usr/bin/env |/usr/bin/env $2 |" "$out"
  [ -n "$3" ] && sed -i "s|/usr/bin/env |/usr/bin/env BC5_RUN_ENV=$3 |" "$out"
  desktop-file-validate "$out" 2>&1 | grep -v hint | head -2 || true
  echo "== $1"; grep -o "play-[a-z0-9-]*\.sh\|KYTY_BC5_AMM_SCATTER=[a-z]*\|BC5_RUN_ENV=[^ ]*\|BC5_GAME_DIR=[^ ]*" "$out" | sort -u | tr "\n" " "; echo
}
mkd "e10 unpacked" "KYTY_BC5_AMM_SCATTER=rescue" "" "$X/play-pkg-0409.sh"
mkd "e10 mem 12800" "KYTY_BC5_AMM_SCATTER=rescue" "$E8/run-mem12800.env" "$X/play-pkg-0409.sh"
# the menu shortcut: no BC5_GAME_DIR (the menu opens or installs games), its own launcher
out="$D/BC5 emulator (e10 menu).desktop"; cp -p "$D/BC5 emulator (e10 unpacked).desktop" "$out"
sed -i "s/^Name=.*/Name=BC5 emulator (e10 menu)/; s|BC5_GAME_DIR=[^ ]* ||; s|$X/play-pkg-0409.sh|$X/play-any-0409.sh|" "$out"
echo "== e10 menu"; grep -o "play-[a-z0-9-]*\.sh\|BC5_GAME_DIR=[^ ]*" "$out" | sort -u | tr "\n" " "; echo
ls "$D"
