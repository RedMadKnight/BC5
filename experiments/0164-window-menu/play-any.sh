#!/usr/bin/env bash
# BC5 (ADR 0011): the emulator window with its menu bar. Run inside the ubuntu distrobox (the
# desktop shortcut does: distrobox enter ubuntu -- ~/bc5-work/play-any.sh [path]).
#
#   play-any.sh                 the empty window (kyty_emulator --menu): File > Open game image /
#                               Open package / Recent starts a game
#   play-any.sh <game.pkg>      the second title's package, through play-pkg.sh (its mount at
#                               ~/bc5-data/mnt/pkg-play, its settings, --fullscreen)
#   play-any.sh <dump.ffpfsc>   a game image, through play-astro.sh (mounted under
#                               ~/bc5-data/mnt/<first word of the file name>)
#   play-any.sh <directory>     an already mounted or extracted app0 directory, straight to --game
#
# The host never mounts anything. Its menu ends the process with an exit code and this script
# does the rest:  75 = restart the same game (the title scripts handle it themselves),
# 76 = open the path written to $KYTY_BC5_MENU_DIR/choice.txt, 77 = close the session (back to
# the empty window), anything else = quit. BC5_MENU_FULLSCREEN=1 opens the empty window
# fullscreen too (a game's fullscreen is its script's business). Output of the empty window goes
# to ~/bc5-work/play-menu-last.log; the title scripts keep their own logs.
set -u
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
export KYTY_BC5_MENU_DIR=${KYTY_BC5_MENU_DIR:-$HOME/bc5-work/menu}
LOG=~/bc5-work/play-menu-last.log
PKG_SCRIPT=~/bc5-work/play-pkg.sh
IMAGE_SCRIPT=~/bc5-work/play-astro.sh

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }

if pgrep -x kyty_emulator >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }
mkdir -p "$KYTY_BC5_MENU_DIR"

# The empty window: the settings of bc5-run.env (the input file, Fullscreen=, the video driver),
# no game, no captures.
run_menu() {
  local args="" line key val
  (
    while IFS= read -r line; do
      case "$line" in ''|'#'*) continue ;; esac
      key=${line%%=*}; val=${line#*=}
      if [ "$key" = PLAY_ARGS ]; then args=$val; else export "$key=$val"; fi
    done < "$ENVF"
    unset BC5_GC_DUMP_DIR
    [ "${BC5_MENU_FULLSCREEN:-0}" = 1 ] && args="$args --fullscreen"
    export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}
    cd ~/bc5-work
    echo "== $(date '+%F %T') menu, emulator $(stat -c '%y' "$EMU" | cut -c1-19)" > "$LOG"
    # shellcheck disable=SC2086
    exec "$EMU" --menu --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false $args >> "$LOG" 2>&1
  )
}

# A game: the title scripts do the mount, the settings and the 75 loop; their exit code is ours.
run_game() {
  local path=$1 lower
  lower=$(printf '%s' "$path" | tr '[:upper:]' '[:lower:]')
  if [ -d "$path" ]; then
    (
      while IFS= read -r line; do
        case "$line" in ''|'#'*) continue ;; esac
        key=${line%%=*}; val=${line#*=}
        if [ "$key" = PLAY_ARGS ]; then args=$val; else export "$key=$val"; fi
      done < "$ENVF"
      [ -d "$path/fakelib" ] && export SHADPS4_SYSMODULES_PACK_DIR=$path/fakelib
      export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}
      cd ~/bc5-work
      while :; do
        # shellcheck disable=SC2086
        "$EMU" --game "$path" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false ${args:-} >> ~/bc5-work/play-dir-last.log 2>&1
        rc=$?; [ "$rc" = 75 ] || exit $rc
      done
    )
  elif [ "${lower%.pkg}" != "$lower" ]; then
    BC5_PKG=$path "$PKG_SCRIPT"
  elif [ "${lower%.ffpfsc}" != "$lower" ]; then
    local name mnt
    name=$(basename "$path"); name=${name%% *}; name=${name%.ffpfsc}
    mnt=~/bc5-data/mnt/$name
    if [ "$name" = PPSA21567 ]; then
      BC5_FFPFSC=$path BC5_FFPFSC_MOUNT=$mnt "$IMAGE_SCRIPT"
    else
      BC5_FFPFSC=$path BC5_FFPFSC_MOUNT=$mnt BC5_SYSMODULES_PACK_DIR=$mnt/fakelib "$IMAGE_SCRIPT"
    fi
  else
    say "Not a game: $path (a .pkg, a .ffpfsc or a directory)"
    return 78
  fi
}

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
    77|78) PATH_TO_OPEN="" ;;
    *) exit $RC ;;
  esac
  sleep 1 # let the previous window go before the next one opens
done
