#!/usr/bin/env bash
# BC5 (ADR 0011): the emulator window with its menu bar. Run inside the ubuntu distrobox (the
# desktop shortcut does: distrobox enter ubuntu -- ~/bc5-work/play-any.sh [path]).
#
#   play-any.sh                 the empty window (kyty_emulator --menu): File > Open game... /
#                               Installed games / Install game... / Uninstall game / Recent
#   play-any.sh <game.pkg>      a package: through play-pkg.sh (the second title's settings) or, when
#                               the title is installed, from its folder
#   play-any.sh <dump.ffpfsc>   a game image, through play-t1.sh (mounted under
#                               ~/bc5-data/mnt/<first word of the file name>), or from its folder
#                               when the title is installed
#   play-any.sh <directory>     an installed game or an unpacked app0 folder: through the title's own
#                               script with BC5_GAME_DIR (the second title: play-pkg.sh; any other:
#                               play-t1.sh), so the title keeps its settings
#
# Experiment 0420: one launcher for opening, installing and uninstalling games (it replaces exp
# 0409's play-any-0409.sh). An installed game is ~/bc5-data/games/<TITLE_ID>/ with the record
# .bc5-install.json that bc5-mount writes. The host never mounts, installs or deletes anything.
# Its menu ends the process with an exit code and this script does the rest:
#   75 = restart the same game (the title scripts handle it themselves)
#   76 = open the path written to $KYTY_BC5_MENU_DIR/choice.txt
#   77 = close the session (back to the empty window)
#   78 = action.txt says what: "install" (choice.txt = the image: bc5-mount install --verify runs
#        in the background into ~/bc5-data/games/<TITLE_ID>, its progress goes to
#        install-progress.txt, the menu comes back at once) or "uninstall" (choice.txt = the
#        folder: bc5-mount uninstall, which refuses anything but an installed game's folder);
#        the outcome is one line in result.txt, which the menu shows. No action: as 77.
#   anything else = quit.
# BC5_MENU_FULLSCREEN=1 opens the empty window fullscreen too (a game's fullscreen is its script's
# business). Output of the empty window goes to ~/bc5-work/play-menu-last.log; the title scripts
# keep their own logs. BC5_DRY=1 (tests) prints what would run instead of running it.
set -u
EMU=${BC5_EMU:-$HOME/bc5-work/kytyplus-build/src/kyty_emulator}
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
export KYTY_BC5_MENU_DIR=${KYTY_BC5_MENU_DIR:-$HOME/bc5-work/menu}
LOG=$HOME/bc5-work/play-menu-last.log
# Experiment 0177: BC5_LEAN=1 (the "BC5 emulator (lean)" shortcut) runs the emulator built with
# KYTY_BC5_LEAN in ~/bc5-work/kytyplus-build-lean: no tracing, journal, counters, recorder or
# samplers, inside or outside; its own log file. The title scripts take the same switch.
if [ "${BC5_LEAN:-0}" = 1 ]; then
  EMU=${BC5_EMU_LEAN:-$HOME/bc5-work/kytyplus-build-lean/src/kyty_emulator} LOG=$HOME/bc5-work/play-menu-lean-last.log
fi
# 2026-10-25 (exp 0324, the maintainer): with BC5_LEAN=1 this script writes no log at all; BC5_LOGS=1 keeps
# its logs. The normal shortcut logs as before.
if [ "${BC5_LEAN:-0}" = 1 ] && [ "${BC5_LOGS:-0}" != 1 ]; then LOG=/dev/null; fi
PKG_SCRIPT=${BC5_PKG_SCRIPT:-$HOME/bc5-work/play-pkg.sh}
IMAGE_SCRIPT=${BC5_IMAGE_SCRIPT:-$HOME/bc5-work/play-t1.sh}
GAMES_DIR=${BC5_GAMES_DIR:-$HOME/bc5-data/games}
BM=${BC5_MOUNT_BIN:-$HOME/bc5-work/bc5-tools-ubuntu/release/bc5-mount}
SECOND_TITLE=TITLE2

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }
result() { printf '%s\n' "$*" > "$KYTY_BC5_MENU_DIR/result.txt"; echo "$*"; }

if pgrep '^kyty_emulator' >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }
mkdir -p "$KYTY_BC5_MENU_DIR" "$GAMES_DIR"
# exp 0412 (2026-11-14, the maintainer: the lean shortcut stops the Plasma shell for the play): lean-session.sh stops
# plasma-plasmashell.service now and starts it again when this launcher is gone, whatever ended it. It comes after
# every check that can refuse the start (2026-11-15, Codex 10:07 UTC, LESSONS R56: a second click used to stop the
# shell and rewrite the state before pgrep refused it); a stop that finds a live lean session (exit 3) refuses too.
if [ "${BC5_LEAN:-0}" = 1 ] && [ -x "$HOME/bc5-work/lean-session.sh" ]; then
  /usr/bin/bash "$HOME/bc5-work/lean-session.sh" stop $$
  [ $? = 3 ] && { say "A lean session is already running."; exit 1; }
fi

# ---- titles and installed games ----

# The title id of an image or package (bc5-mount inspect), or empty.
image_title_id() { "$BM" inspect "$1" 2>/dev/null | awk '/^title id:/ {print $3; exit}'; }

# The title id of a folder (its sce_sys/param.json), or empty.
dir_title_id() { sed -n 's/.*"titleId" *: *"\([A-Za-z0-9]*\)".*/\1/p' "$1/sce_sys/param.json" 2>/dev/null | head -n1; }

# An installed game's folder for an image: one whose record names this image, else the title's
# folder when it holds a record. Empty when none.
installed_dir_for() {
  local img=$1 d rec id
  for d in "$GAMES_DIR"/*/; do
    d=${d%/}; rec=$d/.bc5-install.json
    [ -L "$d" ] || [ ! -f "$rec" ] && continue
    grep -qF "\"image\": \"$img\"" "$rec" 2>/dev/null && { echo "$d"; return 0; }
  done
  id=$(image_title_id "$img")
  [ -n "$id" ] && [ ! -L "$GAMES_DIR/$id" ] && [ -f "$GAMES_DIR/$id/.bc5-install.json" ] && echo "$GAMES_DIR/$id"
  return 0
}

# ---- the empty window and a game ----

# The empty window: the settings of bc5-run.env (the input file, Fullscreen=, the video driver),
# no game, no captures.
run_menu() {
  local args="" line key val
  if [ "${BC5_DRY:-0}" = 1 ]; then echo "[dry-run] menu"; "$EMU" --menu; return $?; fi
  (
    while IFS= read -r line; do
      case "$line" in ''|'#'*) continue ;; esac
      key=${line%%=*}; val=${line#*=}
      if [ "$key" = PLAY_ARGS ]; then args=$val; else export "$key=$val"; fi
    done < "$ENVF"
    unset BC5_GC_DUMP_DIR
    [ "${BC5_MENU_FULLSCREEN:-0}" = 1 ] && args="$args --fullscreen"
    export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}
    cd "$HOME/bc5-work"
    echo "== $(date '+%F %T') menu, emulator $(stat -c '%y' "$EMU" | cut -c1-19)" > "$LOG"
    # shellcheck disable=SC2086
    exec "$EMU" --menu --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $args >> "$LOG" 2>&1
  )
}

# A game folder through its title's script: the second title through play-pkg.sh, any other through
# play-t1.sh; both take BC5_GAME_DIR and run the title's restart loop themselves.
run_dir() {
  local dir=$1 id
  id=$(dir_title_id "$dir")
  if [ "$id" = "$SECOND_TITLE" ]; then
    [ "${BC5_DRY:-0}" = 1 ] && { echo "[dry-run] $PKG_SCRIPT BC5_GAME_DIR=$dir"; return 0; }
    BC5_GAME_DIR=$dir "$PKG_SCRIPT"
  else
    [ "${BC5_DRY:-0}" = 1 ] && { echo "[dry-run] $IMAGE_SCRIPT BC5_GAME_DIR=$dir (title ${id:-unknown})"; return 0; }
    BC5_GAME_DIR=$dir "$IMAGE_SCRIPT"
  fi
}

# A game: an installed title runs from its folder; else the title script mounts the image.
run_game() {
  local path=$1 lower inst name mnt
  lower=$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')
  if [ -d "$path" ]; then
    run_dir "$path"
  elif [ "${lower%.pkg}" != "$lower" ] || [ "${lower%.ffpfsc}" != "$lower" ]; then
    inst=$(installed_dir_for "$path")
    if [ -n "$inst" ]; then
      run_dir "$inst"
    elif [ "${lower%.pkg}" != "$lower" ]; then
      [ "${BC5_DRY:-0}" = 1 ] && { echo "[dry-run] $PKG_SCRIPT BC5_PKG=$path"; return 0; }
      BC5_PKG=$path "$PKG_SCRIPT"
    else
      name=$(basename "$path"); name=${name%% *}; name=${name%.ffpfsc}
      mnt=$HOME/bc5-data/mnt/$name
      [ "${BC5_DRY:-0}" = 1 ] && { echo "[dry-run] $IMAGE_SCRIPT BC5_FFPFSC=$path BC5_FFPFSC_MOUNT=$mnt"; return 0; }
      if [ "$name" = TITLE1 ]; then
        BC5_FFPFSC=$path BC5_FFPFSC_MOUNT=$mnt "$IMAGE_SCRIPT"
      else
        BC5_FFPFSC=$path BC5_FFPFSC_MOUNT=$mnt BC5_SYSMODULES_PACK_DIR=$mnt/fakelib "$IMAGE_SCRIPT"
      fi
    fi
  else
    say "Not a game: $path (a .pkg, a .ffpfsc or a folder)"
    return 77
  fi
}

# ---- install and uninstall ----

# The install, in the background: the menu comes back at once and shows install-progress.txt.
# One install at a time (install.lock); the record is written by --verify only when every file
# matched the image.
start_install() {
  local img=$1 id dest lockd=$KYTY_BC5_MENU_DIR/install.lock prog=$KYTY_BC5_MENU_DIR/install-progress.txt
  [ -f "$img" ] || { result "Install: no such image: $img"; return; }
  [ -x "$BM" ] || { result "Install: no bc5-mount at $BM"; return; }
  id=$(image_title_id "$img")
  [ -n "$id" ] || { result "Install: $img has no title id (bc5-mount inspect found none)"; return; }
  dest=$GAMES_DIR/$id
  [ -e "$dest" ] && { result "Install: $id is already installed at $dest (uninstall it first)"; return; }
  mkdir "$lockd" 2>/dev/null || { result "Install: another install is running"; return; }
  if [ "${BC5_DRY:-0}" = 1 ]; then
    echo "[dry-run] $BM install --verify $img $dest"
    rmdir "$lockd"; result "Installed $id (dry run)"; return
  fi
  echo "Installing $id: starting" > "$prog"
  (
    ilog=$HOME/bc5-work/install-last.log
    "$BM" install --verify "$img" "$dest" 2> >(while IFS= read -r l; do
        printf '%s\n' "$l" >> "$ilog"
        case "$l" in "[bc5-install] "*) printf 'Installing %s: %s\n' "$id" "${l#\[bc5-install\] }" > "$prog" ;; esac
      done) > "$ilog.out"
    rc=$?
    cat "$ilog.out" >> "$ilog" 2>/dev/null; rm -f "$ilog.out"
    if [ "$rc" = 0 ] && [ -f "$dest/.bc5-install.json" ]; then
      result "Installed $id at $dest"
    else
      result "Install of $id failed (exit $rc): $(tail -n 1 "$ilog" | cut -c1-200); the partly written $dest is left for --resume (see $ilog)"
    fi
    rm -f "$prog"; rmdir "$lockd" 2>/dev/null
  ) < /dev/null > /dev/null 2>&1 &
  disown 2>/dev/null || true
}

run_uninstall() {
  local dir=$1 out
  [ -d "$KYTY_BC5_MENU_DIR/install.lock" ] && { result "Uninstall: an install is running; try again when it is done"; return; }
  [ -x "$BM" ] || { result "Uninstall: no bc5-mount at $BM"; return; }
  if out=$("$BM" uninstall "$dir" --games "$GAMES_DIR" 2>&1); then
    result "$(printf '%s' "$out" | tail -n 1 | cut -c1-300)"
  else
    result "Uninstall refused or failed: $(printf '%s' "$out" | tail -n 1 | cut -c1-300)"
  fi
}

# ---- the loop ----

PATH_TO_OPEN=${1:-}
while :; do
  if [ -z "$PATH_TO_OPEN" ]; then
    run_menu; RC=$?
  else
    [ -e "$PATH_TO_OPEN" ] || { say "No such file: $PATH_TO_OPEN"; PATH_TO_OPEN=""; continue; }
    run_game "$PATH_TO_OPEN"; RC=$?
  fi
  case $RC in
    76) PATH_TO_OPEN=$(head -n1 "$KYTY_BC5_MENU_DIR/choice.txt" 2>/dev/null) ;;
    77) PATH_TO_OPEN="" ;;
    78)
      ACTION=$(head -n1 "$KYTY_BC5_MENU_DIR/action.txt" 2>/dev/null || true)
      CHOICE=$(head -n1 "$KYTY_BC5_MENU_DIR/choice.txt" 2>/dev/null || true)
      rm -f "$KYTY_BC5_MENU_DIR/action.txt"
      case "$ACTION" in
        install) start_install "$CHOICE" ;;
        uninstall) run_uninstall "$CHOICE" ;;
      esac
      PATH_TO_OPEN="" ;;
    *) exit $RC ;;
  esac
  sleep 1 # let the previous window go before the next one opens
done
