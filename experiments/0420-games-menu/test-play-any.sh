#!/usr/bin/env bash
# BC5 experiment 0420: tests of play-any.sh on stand-ins (no emulator, no box, no real game). A fake emulator plays
# a script of exit codes and menu files; a fake bc5-mount answers inspect, install and uninstall; the title scripts
# are fakes that record how they were called. Extends exp 0409's eight tests with install and uninstall.
# usage: bash test-play-any.sh            (exit 0 when every test passes)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LAUNCHER=$HERE/play-any.sh
PASS=0; FAIL=0
ok() { PASS=$((PASS + 1)); echo "ok   $1"; }
bad() { FAIL=$((FAIL + 1)); echo "FAIL $1"; [ -n "${2:-}" ] && printf '     %s\n' "$2"; }

setup() {  # a fresh fake HOME with the stand-ins
  T=$(mktemp -d)
  export HOME=$T BC5_RUN_ENV=$T/bc5-run.env KYTY_BC5_MENU_DIR=$T/menu BC5_GAMES_DIR=$T/games
  export BC5_EMU=$T/emu BC5_EMU_LEAN=$T/emu-lean BC5_PKG_SCRIPT=$T/play-pkg.sh BC5_IMAGE_SCRIPT=$T/play-astro.sh BC5_MOUNT_BIN=$T/bc5-mount
  mkdir -p "$T/bc5-work" "$T/menu" "$T/games" "$T/images"
  printf 'PLAY_ARGS=--fullscreen\nVIDEO_DRIVER=wayland\n' > "$BC5_RUN_ENV"
  # the emulator: each start takes the next line of emu.script: "<exit> [action|-] [choice]"
  cat > "$BC5_EMU" << 'EOF'
#!/usr/bin/env bash
n=$(cat "$HOME/emu.n" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$HOME/emu.n"
echo "emu $n $*" >> "$HOME/calls.log"
line=$(sed -n "${n}p" "$HOME/emu.script")
[ -n "$line" ] || exit 0
set -- $line
[ "${2:--}" != - ] && echo "$2" > "$KYTY_BC5_MENU_DIR/action.txt"
[ -n "${3:-}" ] && echo "$3" > "$KYTY_BC5_MENU_DIR/choice.txt"
exit "$1"
EOF
  cp "$BC5_EMU" "$BC5_EMU_LEAN"
  for s in play-pkg.sh play-astro.sh; do
    printf '#!/usr/bin/env bash\necho "%s BC5_GAME_DIR=${BC5_GAME_DIR:-} BC5_PKG=${BC5_PKG:-} BC5_FFPFSC=${BC5_FFPFSC:-}" >> "$HOME/calls.log"\nexit 77\n' "$s" > "$T/$s"
  done
  # bc5-mount: inspect prints the title id kept in <image>.id; install writes a folder with a record; uninstall
  # removes a folder with a record directly under --games and refuses the rest (exit 2), as the real one does
  cat > "$BC5_MOUNT_BIN" << 'EOF'
#!/usr/bin/env bash
echo "bc5-mount $*" >> "$HOME/calls.log"
case "$1" in
  inspect) [ -f "$2.id" ] && echo "title id:         $(cat "$2.id")"; exit 0 ;;
  install) dest=$4; [ -e "$dest" ] && { echo "exists" >&2; exit 2; }
           mkdir -p "$dest/sce_sys"; echo "{\"titleId\": \"$(basename "$dest")\"}" > "$dest/sce_sys/param.json"
           echo "[bc5-install] 1/1 files, 0.00/0.00 GiB, 1.0 MB/s (0s elapsed)" >&2
           printf '{\n  "image": "%s",\n  "file_count": 1,\n  "total_bytes": 1\n}\n' "$3" > "$dest/.bc5-install.json"
           echo "installed 1 files"; exit 0 ;;
  uninstall) d=$2; root=$4
           [ -L "$d" ] && { echo "bc5-mount: refused: $d is a symbolic link" >&2; exit 2; }
           [ "$(dirname "$(realpath "$d")")" = "$(realpath "$root")" ] || { echo "bc5-mount: refused: not directly under" >&2; exit 2; }
           [ -f "$d/.bc5-install.json" ] || { echo "bc5-mount: refused: holds no record" >&2; exit 2; }
           rm -rf "$d"; echo "uninstalled $d: 10 bytes in 3 entries freed; image missing: /x"; exit 0 ;;
esac
exit 1
EOF
  chmod +x "$BC5_EMU" "$BC5_EMU_LEAN" "$T"/play-*.sh "$BC5_MOUNT_BIN"
  : > "$T/calls.log"
}
run() { (cd "$T" && timeout 30 bash "$LAUNCHER" "$@" > "$T/out.log" 2>&1); echo $?; }
calls() { cat "$T/calls.log"; }
wait_install() { for _ in $(seq 1 50); do [ -d "$KYTY_BC5_MENU_DIR/install.lock" ] || return 0; sleep 0.1; done; }
installed() {  # a synthetic install of <id> from <image>
  mkdir -p "$BC5_GAMES_DIR/$1/sce_sys"; echo "{\"titleId\": \"$1\"}" > "$BC5_GAMES_DIR/$1/sce_sys/param.json"
  printf '{\n  "image": "%s",\n  "file_count": 1,\n  "total_bytes": 1\n}\n' "$2" > "$BC5_GAMES_DIR/$1/.bc5-install.json"
}

# 1. a package that is not installed goes to play-pkg.sh with BC5_PKG
setup; touch "$T/images/game.pkg"; echo PPSA03671 > "$T/images/game.pkg.id"; echo "0" > "$T/emu.script"
rc=$(run "$T/images/game.pkg")
calls | grep -q "play-pkg.sh BC5_GAME_DIR= BC5_PKG=$T/images/game.pkg" && ok "pkg, not installed: play-pkg.sh with BC5_PKG" || bad "pkg, not installed" "$(calls)"
# 2. an image that is not installed goes to play-astro.sh with BC5_FFPFSC
setup; touch "$T/images/PPSA21567 - ASTRO.ffpfsc"; echo "0" > "$T/emu.script"
rc=$(run "$T/images/PPSA21567 - ASTRO.ffpfsc")
calls | grep -q "play-astro.sh BC5_GAME_DIR= BC5_PKG= BC5_FFPFSC=$T/images/PPSA21567 - ASTRO.ffpfsc" && ok "ffpfsc, not installed: play-astro.sh" || bad "ffpfsc, not installed" "$(calls)"
# 3. the second title's installed folder goes to play-pkg.sh with BC5_GAME_DIR
setup; installed PPSA03671 /gone/game.pkg; echo "0" > "$T/emu.script"
rc=$(run "$BC5_GAMES_DIR/PPSA03671")
calls | grep -q "play-pkg.sh BC5_GAME_DIR=$BC5_GAMES_DIR/PPSA03671 BC5_PKG=" && ok "installed second title: play-pkg.sh with BC5_GAME_DIR" || bad "installed second title" "$(calls)"
# 4. another installed title goes to play-astro.sh with BC5_GAME_DIR
setup; installed PPSA21567 /gone/astro.ffpfsc; echo "0" > "$T/emu.script"
rc=$(run "$BC5_GAMES_DIR/PPSA21567")
calls | grep -q "play-astro.sh BC5_GAME_DIR=$BC5_GAMES_DIR/PPSA21567" && ok "installed other title: play-astro.sh with BC5_GAME_DIR" || bad "installed other title" "$(calls)"
# 5. a package whose title is installed runs from the folder, not the package
setup; touch "$T/images/game.pkg"; echo PPSA03671 > "$T/images/game.pkg.id"; installed PPSA03671 /elsewhere/game.pkg; echo "0" > "$T/emu.script"
rc=$(run "$T/images/game.pkg")
calls | grep -q "play-pkg.sh BC5_GAME_DIR=$BC5_GAMES_DIR/PPSA03671" && ok "pkg of an installed title: from the folder" || bad "pkg of an installed title" "$(calls)"
# 6. the menu's 76 opens choice.txt, then 77 comes back to the menu, then quit
setup; touch "$T/images/game.pkg"; echo PPSA03671 > "$T/images/game.pkg.id"
printf '76 - %s\n0\n' "$T/images/game.pkg" > "$T/emu.script"
rc=$(run)
[ "$(calls | grep -c '^emu ')" = 2 ] && calls | grep -q "play-pkg.sh" && [ "$rc" = 0 ] && ok "menu 76: opens choice.txt, back to the menu, quit" || bad "menu 76" "rc $rc; $(calls)"
# 7. the menu's 78 install: bc5-mount install in the background, the record appears, the result line
setup; touch "$T/images/new.ffpfsc"; echo PPSA00001 > "$T/images/new.ffpfsc.id"
printf '78 install %s\n0\n' "$T/images/new.ffpfsc" > "$T/emu.script"
rc=$(run); wait_install
[ -f "$BC5_GAMES_DIR/PPSA00001/.bc5-install.json" ] && grep -q "Installed PPSA00001" "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null && [ ! -e "$KYTY_BC5_MENU_DIR/action.txt" ] && ok "menu 78 install: installed, result written, action.txt gone" || bad "menu 78 install" "$(calls; cat "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null)"
# 8. install of a title that is already installed is refused, nothing overwritten
setup; touch "$T/images/new.ffpfsc"; echo PPSA00001 > "$T/images/new.ffpfsc.id"; installed PPSA00001 "$T/images/new.ffpfsc"; echo keep > "$BC5_GAMES_DIR/PPSA00001/keep"
printf '78 install %s\n0\n' "$T/images/new.ffpfsc" > "$T/emu.script"
rc=$(run); wait_install
grep -q "already installed" "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null && [ -f "$BC5_GAMES_DIR/PPSA00001/keep" ] && ! calls | grep -q "bc5-mount install" && ok "install of an installed title: refused" || bad "install of an installed title" "$(calls)"
# 9. install of an image without a title id is refused
setup; touch "$T/images/junk.pkg"; printf '78 install %s\n0\n' "$T/images/junk.pkg" > "$T/emu.script"
rc=$(run); wait_install
grep -q "no title id" "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null && ok "install without a title id: refused" || bad "install without a title id" "$(cat "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null)"
# 10. the menu's 78 uninstall of an installed game: bc5-mount uninstall, the folder is gone, the image stays
setup; touch "$T/images/new.ffpfsc"; installed PPSA00002 "$T/images/new.ffpfsc"
printf '78 uninstall %s\n0\n' "$BC5_GAMES_DIR/PPSA00002" > "$T/emu.script"
rc=$(run)
[ ! -e "$BC5_GAMES_DIR/PPSA00002" ] && [ -f "$T/images/new.ffpfsc" ] && grep -q "^uninstalled" "$KYTY_BC5_MENU_DIR/result.txt" && calls | grep -q "bc5-mount uninstall $BC5_GAMES_DIR/PPSA00002 --games $BC5_GAMES_DIR" && ok "menu 78 uninstall: removed through bc5-mount, the image stays" || bad "menu 78 uninstall" "$(calls)"
# 11. uninstall of something that is not an installed game is refused, nothing removed
setup; mkdir -p "$T/other/PPSA00003"; echo x > "$T/other/PPSA00003/a"
printf '78 uninstall %s\n0\n' "$T/other/PPSA00003" > "$T/emu.script"
rc=$(run)
[ -f "$T/other/PPSA00003/a" ] && grep -q "refused" "$KYTY_BC5_MENU_DIR/result.txt" && ok "uninstall outside the games root: refused" || bad "uninstall outside" "$(cat "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null)"
# 12. uninstall while an install runs is refused
setup; installed PPSA00004 /x.pkg; mkdir "$KYTY_BC5_MENU_DIR/install.lock"
printf '78 uninstall %s\n0\n' "$BC5_GAMES_DIR/PPSA00004" > "$T/emu.script"
rc=$(run)
[ -d "$BC5_GAMES_DIR/PPSA00004" ] && grep -q "install is running" "$KYTY_BC5_MENU_DIR/result.txt" && ok "uninstall during an install: refused" || bad "uninstall during an install" "$(cat "$KYTY_BC5_MENU_DIR/result.txt" 2>/dev/null)"
# 13. 78 without an action is a close: back to the menu
setup; printf '78\n0\n' > "$T/emu.script"
rc=$(run)
[ "$(calls | grep -c '^emu ')" = 2 ] && [ "$rc" = 0 ] && ok "78 without an action: back to the menu" || bad "78 without an action" "$(calls)"
# 14. BC5_LEAN=1 runs the lean emulator
setup; echo "0" > "$T/emu.script"
(cd "$T" && BC5_LEAN=1 timeout 30 bash "$LAUNCHER" > "$T/out.log" 2>&1)
[ "$(cat "$T/emu.n")" = 1 ] && grep -q "^emu 1 --menu" "$T/calls.log" && ok "BC5_LEAN=1: the lean emulator's menu" || bad "BC5_LEAN=1" "$(calls)"

echo "test-play-any: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
