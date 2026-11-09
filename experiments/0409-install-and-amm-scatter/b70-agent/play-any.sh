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
#
# Installed games: if ~/bc5-data/games/<TITLE_ID>/.bc5-install.json exists for the chosen image,
# the game runs from that directory (BC5_GAME_DIR=...) instead of mounting.
# BC5_DRY=1 prints what would be run without executing.
set -u
EMU=~/bc5-work/kytyplus-build/src/kyty_emulator
ENVF=${BC5_RUN_ENV:-$HOME/bc5-work/bc5-run.env}
export KYTY_BC5_MENU_DIR=${KYTY_BC5_MENU_DIR:-$HOME/bc5-work/menu}
LOG=~/bc5-work/play-menu-last.log
# Experiment 0177: BC5_LEAN=1 (the "BC5 emulator (lean)" shortcut) runs the emulator built with
# KYTY_BC5_LEAN in ~/bc5-work/kytyplus-build-lean: no tracing, journal, counters, recorder or
# samplers, inside or outside; its own log file. The title scripts take the same switch.
if [ "${BC5_LEAN:-0}" = 1 ]; then
  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-menu-lean-last.log
fi
# 2026-10-25 (exp 0324, the maintainer): with BC5_LEAN=1 this script writes no log at all; BC5_LOGS=1 keeps
# its logs. The normal shortcut logs as before.
DIRLOG=~/bc5-work/play-dir-last.log
if [ "${BC5_LEAN:-0}" = 1 ] && [ "${BC5_LOGS:-0}" != 1 ]; then LOG=/dev/null DIRLOG=/dev/null; fi
PKG_SCRIPT=~/bc5-work/play-pkg.sh
IMAGE_SCRIPT=~/bc5-work/play-astro.sh
GAMES_DIR=$HOME/bc5-data/games
BM=${BC5_BC5_MOUNT:-~/bc5-work/bc5-tools-ubuntu/release/bc5-mount}

say() { echo "$*"; command -v notify-send >/dev/null 2>&1 && notify-send "BC5" "$*" 2>/dev/null; }

if pgrep -x kyty_emulator >/dev/null; then say "The emulator is already running."; exit 1; fi
[ -x "$EMU" ] || { say "No emulator build at $EMU"; exit 1; }
[ -r "$ENVF" ] || { say "No settings file at $ENVF"; exit 1; }
mkdir -p "$KYTY_BC5_MENU_DIR"

# ---- TITLE_ID helpers ----

# Extract TITLE_ID from a .pkg file (from content_id, e.g. PPSA21567 from EP9000-PPSA21567_00-ASTROBOT00000000).
pkg_title_id() {
  local pkg=$1
  # Read the first 4 bytes to check if it's a package.
  local head
  head=$(dd if="$pkg" bs=1 count=4 2>/dev/null | od -A n -t x1 | tr -d ' \n')
  # .pkg files start with specific magic; fall back to bc5-mount inspect.
  if command -v "$BM" >/dev/null 2>&1; then
    "$BM" inspect "$pkg" 2>/dev/null | grep '^title id:' | awk '{print $3}'
  fi
}

# Extract TITLE_ID from a container/ffpfsc image (from sce_sys/param.json).
container_title_id() {
  local img=$1
  if command -v "$BM" >/dev/null 2>&1; then
    "$BM" inspect "$img" 2>/dev/null | grep '^title id:' | awk '{print $3}'
  fi
}

# Get the installed game directory for a TITLE_ID, or empty string.
installed_game_dir() {
  local title_id=$1
  if [ -n "$title_id" ] && [ -d "$GAMES_DIR/$title_id" ] && [ -f "$GAMES_DIR/$title_id/.bc5-install.json" ]; then
    echo "$GAMES_DIR/$title_id"
  fi
}

# List installed games (one per line: TITLE_ID path).
list_installed_games() {
  if [ -d "$GAMES_DIR" ]; then
    for game_dir in "$GAMES_DIR"/*/; do
      [ -d "$game_dir" ] || continue
      local tid
      tid=$(basename "$game_dir")
      if [ -f "$game_dir/.bc5-install.json" ]; then
        echo "$tid $game_dir"
      fi
    done
  fi
}

# Regenerate $KYTY_BC5_MENU_DIR/installed.txt in full: one image path, a tab, the install dir, per installed game.
write_installed_list() {
  [ -n "${KYTY_BC5_MENU_DIR:-}" ] || return 0
  local game_dir img tmp="$KYTY_BC5_MENU_DIR/installed.txt.tmp"
  : > "$tmp"
  if [ -d "$GAMES_DIR" ]; then
    for game_dir in "$GAMES_DIR"/*/; do
      [ -f "$game_dir/.bc5-install.json" ] || continue
      img=$(sed -n 's/.*"image": *"\([^"]*\)".*/\1/p' "$game_dir/.bc5-install.json" | head -n1)
      printf '%s\t%s\n' "$img" "${game_dir%/}" >> "$tmp"
    done
  fi
  mv -f "$tmp" "$KYTY_BC5_MENU_DIR/installed.txt"
}

# ---- Run helpers ----

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
    run_game_dir "$path"
  elif [ "${lower%.pkg}" != "$lower" ]; then
    run_game_pkg "$path"
  elif [ "${lower%.ffpfsc}" != "$lower" ]; then
    run_game_image "$path"
  else
    say "Not a game: $path (a .pkg, a .ffpfsc or a directory)"
    return 78
  fi
}

# Run a game from an installed directory (BC5_GAME_DIR).
run_game_dir() {
  local dir=$1
  if [ "${BC5_DRY:-0}" = 1 ]; then
    echo "[dry-run] run_game_dir $dir"
    return 0
  fi
  (
    while IFS= read -r line; do
      case "$line" in ''|'#'*) continue ;; esac
      key=${line%%=*}; val=${line#*=}
      if [ "$key" = PLAY_ARGS ]; then args=$val; else export "$key=$val"; fi
    done < "$ENVF"
    [ -d "$dir/fakelib" ] && export SHADPS4_SYSMODULES_PACK_DIR=$dir/fakelib
    export XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0} DISPLAY=${DISPLAY:-:0}
    cd ~/bc5-work
    while :; do
      # shellcheck disable=SC2086
      "$EMU" --game "$dir" --printf-direction Silent --shader-log-direction Silent --command-buffer-dump false ${args:-} >> "$DIRLOG" 2>&1
      rc=$?; [ "$rc" = 75 ] || exit $rc
    done
  )
}

# Run a .pkg game: check for installed version first, otherwise mount.
run_game_pkg() {
  local pkg=$1
  local title_id
  title_id=$(pkg_title_id "$pkg")
  local inst_dir
  inst_dir=$(installed_game_dir "$title_id")

  if [ -n "$inst_dir" ]; then
    # Installed version exists — run from it.
    if [ "${BC5_DRY:-0}" = 1 ]; then
      echo "[dry-run] run_game_pkg: installed at $inst_dir (TITLE_ID=$title_id)"
      return 0
    fi
    BC5_GAME_DIR="$inst_dir" "$PKG_SCRIPT"
  else
    # No installed version — mount as before.
    if [ "${BC5_DRY:-0}" = 1 ]; then
      echo "[dry-run] run_game_pkg: mount $pkg (TITLE_ID=$title_id)"
      return 0
    fi
    BC5_PKG=$pkg "$PKG_SCRIPT"
  fi
}

# Run a .ffpfsc game: check for installed version first, otherwise mount.
run_game_image() {
  local img=$1
  local title_id
  title_id=$(container_title_id "$img")
  local inst_dir
  inst_dir=$(installed_game_dir "$title_id")

  if [ -n "$inst_dir" ]; then
    # Installed version exists — run from it.
    if [ "${BC5_DRY:-0}" = 1 ]; then
      echo "[dry-run] run_game_image: installed at $inst_dir (TITLE_ID=$title_id)"
      return 0
    fi
    local name mnt
    name=$(basename "$img"); name=${name%% *}; name=${name%.ffpfsc}
    mnt=~/bc5-data/mnt/$name
    if [ "$name" = PPSA21567 ]; then
      BC5_GAME_DIR="$inst_dir" BC5_FFPFSC=$img BC5_FFPFSC_MOUNT=$mnt "$IMAGE_SCRIPT"
    else
      BC5_GAME_DIR="$inst_dir" BC5_FFPFSC=$img BC5_FFPFSC_MOUNT=$mnt BC5_SYSMODULES_PACK_DIR=$inst_dir/fakelib "$IMAGE_SCRIPT"
    fi
  else
    # No installed version — mount as before.
    if [ "${BC5_DRY:-0}" = 1 ]; then
      echo "[dry-run] run_game_image: mount $img (TITLE_ID=$title_id)"
      return 0
    fi
    local name mnt
    name=$(basename "$img"); name=${name%% *}; name=${name%.ffpfsc}
    mnt=~/bc5-data/mnt/$name
    if [ "$name" = PPSA21567 ]; then
      BC5_FFPFSC=$img BC5_FFPFSC_MOUNT=$mnt "$IMAGE_SCRIPT"
    else
      BC5_FFPFSC=$img BC5_FFPFSC_MOUNT=$mnt BC5_SYSMODULES_PACK_DIR=$mnt/fakelib "$IMAGE_SCRIPT"
    fi
  fi
}

# ---- Menu with installed games list ----

# Show the menu, listing installed games if no image is provided.
run_menu_with_installed() {
  # Write installed.txt for the menu to read.
  write_installed_list

  if [ "${BC5_DRY:-0}" = 1 ]; then
    echo "[dry-run] run_menu_with_installed"
    echo "[dry-run] installed games:"
    list_installed_games | while read -r tid path; do
      echo "  $tid -> $path"
    done
    return 0
  fi

  run_menu
}

PATH_TO_OPEN=${1:-}
while :; do
  if [ -z "$PATH_TO_OPEN" ]; then
    run_menu_with_installed; RC=$?
  else
    [ -e "$PATH_TO_OPEN" ] || { say "No such file: $PATH_TO_OPEN"; PATH_TO_OPEN=""; continue; }
    run_game "$PATH_TO_OPEN"; RC=$?
  fi
  case $RC in
    76) PATH_TO_OPEN=$(head -n1 "$KYTY_BC5_MENU_DIR/choice.txt" 2>/dev/null) ;;
    78)
      # Code 78: could be "close session" or "install game" (from host menu).
      # Check action.txt: if it says "install", run bc5-mount install.
      ACTION=$(head -n1 "$KYTY_BC5_MENU_DIR/action.txt" 2>/dev/null || true)
      if [ "$ACTION" = "install" ]; then
        IMAGE=$(head -n1 "$KYTY_BC5_MENU_DIR/choice.txt" 2>/dev/null || true)
        if [ -z "$IMAGE" ]; then
          say "No image path in choice.txt"; PATH_TO_OPEN=""
        else
          # Extract TITLE_ID from bc5-mount inspect (Fix 8: not basename).
          local_title_id=""
          lower=$(printf '%s' "$IMAGE" | tr '[:upper:]' '[:lower:]')
          if [ "${lower%.pkg}" != "$lower" ]; then
            local_title_id=$(pkg_title_id "$IMAGE")
          else
            local_title_id=$(container_title_id "$IMAGE")
          fi
          # Fallback to basename if inspect failed.
          if [ -z "$local_title_id" ]; then
            local_title_id=$(basename "$IMAGE" | sed 's/\.[^.]*$//')
          fi
          local_dest="$GAMES_DIR/$local_title_id"
          if [ "${BC5_DRY:-0}" = 1 ]; then
            echo "[dry-run] bc5-mount install --verify $IMAGE $local_dest"
            # Fix 13: clean up action.txt after reading.
            rm -f "$KYTY_BC5_MENU_DIR/action.txt"
            PATH_TO_OPEN=""
          else
            say "Installing $IMAGE to $local_dest ..."
            INSTALL_LOG=$HOME/bc5-work/install-last.log
            # Fix 11: kdialog progress bar if available.
            KDLG_PID=""
            if command -v kdialog >/dev/null 2>&1; then
              kdialog --msgbox "Installing $IMAGE to $local_dest..." 2>/dev/null &
              KDLG_PID=$!
            fi
            if "$BM" install --verify "$IMAGE" "$local_dest" > "$INSTALL_LOG" 2>&1; then
              say "Install complete"
              # Fix 10: write installed.txt with image path + install dir (tab-separated, one per line).
              write_installed_list
              if [ -n "$KDLG_PID" ]; then kill "$KDLG_PID" 2>/dev/null; fi
              command -v kdialog >/dev/null 2>&1 && kdialog --passivepopup "Installed: $local_title_id" 8 2>/dev/null
            else
              say "Install failed (see $INSTALL_LOG)"
              # Show last 20 log lines on failure.
              LAST_LINES=$(tail -n 20 "$INSTALL_LOG")
              if [ -n "$LAST_LINES" ]; then
                say "Install failed: $LAST_LINES"
              fi
              if command -v kdialog >/dev/null 2>&1; then
                kdialog --error "$LAST_LINES" 2>/dev/null
                if [ -n "$KDLG_PID" ]; then kill "$KDLG_PID" 2>/dev/null; fi
              fi
            fi
            # Fix 13: delete action.txt after reading.
            rm -f "$KYTY_BC5_MENU_DIR/action.txt"
          fi
        fi
      else
        # Not an install action — treat as close session.
        PATH_TO_OPEN=""
      fi
      ;;
    77) PATH_TO_OPEN="" ;;
    *) exit $RC ;;
  esac
  sleep 1 # let the previous window go before the next one opens
done
