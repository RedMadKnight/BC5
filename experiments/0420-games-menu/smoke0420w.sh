#!/usr/bin/env bash
# BC5 exp 0420: the short smoke test after the shared swap to W with the games menu (step d of the top's order). One
# lock line, RT as the shared launchers set it, no pad key sent. The maintainer's live saves are never used: the
# second title runs with a PRIVATE copy of the shared play-pkg.sh whose working directory and save directory are
# ~/bc5-work/exp0413/n/wd (exp 0413's private layout), reset from exp 0412's named snapshot (a copy, read only).
#   d1  the empty window through the shared play-any.sh, normal then lean, 20 s each, one screenshot each (the start
#       page with Open game, Install game, the Installed list); lean: the Plasma shell is active again afterwards
#   d2  the second title from the installed list: the shared play-any.sh given the installed folder, which is what the
#       menu does on a click (exit 76, choice.txt = the folder), so play-any.sh runs the title's script with
#       BC5_GAME_DIR; the script is the private copy above (BC5_PKG_SCRIPT). 120 s, a screenshot at 90 s, then quit.
# No install, no uninstall. Usage (on the box): smoke0420w.sh [d1|d2|all]
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; X=$W/exp0420/smoke; NS=$W/exp0412/night/saves-named
STEP=${1:-all}
say() { echo "smoke0420w: $*"; }
pgrep '^kyty_emulator' > /dev/null && { say "an emulator runs: NOT STARTED"; exit 1; }
[ -s "$W/lean-session.state" ] && { say "a lean session is active: NOT STARTED"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0420: smoke test of the shared W with the games menu: the menu normal and lean, the second title from the installed list on private saves, 120 s" 15 || { say "NOT STARTED"; exit 1; }
trap chain_release EXIT
mkdir -p "$X" || exit 1
WL=$(ls "/run/user/$(id -u)/" | grep -m1 '^wayland-[0-9]*$')
[ -n "$WL" ] || { say "no Wayland socket: NOT STARTED"; exit 1; }
K0=$(sudo -n dmesg 2> /dev/null | wc -l)
shot() { # file
  XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$WL DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 20 spectacle -b -n -f -o "$1" > /dev/null 2>&1
  [ -s "$1" ] && echo "$1" || echo none
}
endrun() { # launcher pid: the emulator ends (as the menu's Quit would), then the launcher
  local ep; ep=$(pgrep -o '^kyty_emulator')
  [ -n "$ep" ] && kill "$ep" 2> /dev/null
  for _ in $(seq 1 30); do pgrep '^kyty_emulator' > /dev/null || break; sleep 0.5; done
  kill "$1" 2> /dev/null; wait "$1" 2> /dev/null
}
started() { for _ in $(seq 1 60); do pgrep '^kyty_emulator' > /dev/null && return 0; sleep 0.5; done; return 1; }
if [ "$STEP" = all ] || [ "$STEP" = d1 ]; then
  for v in normal lean; do
    lean=0; [ "$v" = lean ] && lean=1
    distrobox enter ubuntu -- env WAYLAND_DISPLAY="$WL" BC5_LEAN=$lean BC5_LOGS=1 bash "$W/play-any.sh" < /dev/null > "$X/d1-$v.out" 2>&1 &
    LP=$!
    started || { say "d1 $v: no emulator after 30 s: $(tail -3 "$X/d1-$v.out" | tr '\n' ' ' | cut -c1-200)"; kill "$LP" 2> /dev/null; continue; }
    sleep 20
    s=$(shot "$X/d1-$v-$(date +%H%M%S).png")
    ps_state=""; [ "$v" = lean ] && ps_state=", the shell during the window: $(systemctl --user is-active plasma-plasmashell.service 2>&1)"
    endrun "$LP"
    if [ "$v" = lean ]; then
      for _ in $(seq 1 30); do [ "$(systemctl --user is-active plasma-plasmashell.service 2> /dev/null)" = active ] && break; sleep 1; done
      ps_state="$ps_state, after: $(systemctl --user is-active plasma-plasmashell.service 2>&1), state file $([ -s "$W/lean-session.state" ] && echo NOT-EMPTY || echo empty), owner $([ -e "$W/lean-session.state.owner" ] && echo PRESENT || echo none)"
    fi
    say "d1 $v: the menu ran 20 s, screenshot $s$ps_state; the menu log: $(tail -1 "$W/play-menu$([ "$v" = lean ] && echo -lean)-last.log" 2> /dev/null | cut -c1-120)"
    sleep 3
  done
fi
if [ "$STEP" = all ] || [ "$STEP" = d2 ]; then
  GD=""
  for d in "$HOME"/bc5-data/games/*/; do
    d=${d%/}
    [ -L "$d" ] || [ ! -f "$d/.bc5-install.json" ] && continue
    grep -q '"titleId" *: *"TITLE2"' "$d/sce_sys/param.json" 2> /dev/null && { GD=$d; break; }
  done
  [ -n "$GD" ] || { say "d2: no installed second title under ~/bc5-data/games: NOT RUN"; exit 1; }
  # the private copy of the shared play-pkg.sh: the working directory and the save directory only
  SRC=$W/play-pkg.sh; L=$X/play-pkg-smoke.sh
  cp "$SRC" "$L" || exit 1
  for a in 'cd ~/bc5-work' 'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play'; do
    [ "$(grep -cxF -- "$a" "$L")" = 1 ] || { say "d2: the anchor [$a] is not in $SRC exactly once: NOT RUN"; exit 1; }
  done
  sed -i -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0413/n/wd  \# exp 0420 smoke: the private working directory (its own _SaveData)#' \
         -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0413/n/wd/_SaveData-pkg-play  \# exp 0420 smoke: private#' "$L" || exit 1
  [ "$(diff "$SRC" "$L" | grep -c '^>')" = 2 ] && [ "$(diff "$SRC" "$L" | grep -c '^<')" = 2 ] || { say "d2: the private launcher is not 2 lines changed: NOT RUN"; exit 1; }
  grep -nE '_SaveData|SAVEDATA_DIR=' "$L" | grep -v 'exp0413/n/wd' | grep -v '^[0-9]*: *#' > "$X/d2-save-lines.txt"
  [ -s "$X/d2-save-lines.txt" ] && { say "d2: the private launcher still names another save path: $(head -2 "$X/d2-save-lines.txt" | tr '\n' ' ' | cut -c1-200): NOT RUN"; exit 1; }
  bash -n "$L" && chmod +x "$L" || exit 1
  WD=$N/wd
  [ -d "$WD/_SaveData" ] && [ ! -L "$WD/_SaveData" ] && [ -d "$NS/TITLE2" ] || { say "d2: no private working directory or no named snapshot: NOT RUN"; exit 1; }
  mkdir -p "$WD/_SaveData-pkg-play" && rm -rf "$WD/_SaveData/TITLE2" && cp -a "$NS/TITLE2" "$WD/_SaveData/TITLE2" || { say "d2: the private save copy failed: NOT RUN"; exit 1; }
  for v in normal lean; do
    lean=0; [ "$v" = lean ] && lean=1
    rm -rf "$WD/_SaveData/TITLE2" && cp -a "$NS/TITLE2" "$WD/_SaveData/TITLE2" || { say "d2 $v: the private save copy failed: NOT RUN"; exit 1; }
    distrobox enter ubuntu -- env WAYLAND_DISPLAY="$WL" BC5_LEAN=$lean BC5_LOGS=1 BC5_PKG_SCRIPT="$L" bash "$W/play-any.sh" "$GD" < /dev/null > "$X/d2-$v.out" 2>&1 &
    LP=$!
    started || { say "d2 $v: no emulator after 30 s: $(tail -3 "$X/d2-$v.out" | tr '\n' ' ' | cut -c1-200)"; kill "$LP" 2> /dev/null; continue; }
    EP=$(pgrep -o '^kyty_emulator')
    game=$(tr '\0' ' ' < "/proc/$EP/cmdline" 2> /dev/null | grep -o -- "--game [^ ]*" | head -1)
    bin=$(readlink "/proc/$EP/exe" 2> /dev/null)
    sleep 90
    s=$(shot "$X/d2-$v-$(date +%H%M%S).png")
    alive=no; [ -d "/proc/$EP" ] && alive=yes
    sleep 30
    alive2=no; [ -d "/proc/$EP" ] && alive2=yes
    endrun "$LP"
    ps_state=""
    if [ "$v" = lean ]; then
      for _ in $(seq 1 30); do [ "$(systemctl --user is-active plasma-plasmashell.service 2> /dev/null)" = active ] && break; sleep 1; done
      ps_state=", the shell after: $(systemctl --user is-active plasma-plasmashell.service 2>&1), state file $([ -s "$W/lean-session.state" ] && echo NOT-EMPTY || echo empty)"
    fi
    say "d2 $v: $GD from the list's path (play-any.sh <folder>): emulator $EP ($bin) alive at 90 s $alive, at 120 s $alive2, $game; screenshot $s$ps_state; the launcher's last line: $(tail -1 "$X/d2-$v.out" | cut -c1-160)"
    sleep 5
  done
  say "d2: saves used: $WD/_SaveData/TITLE2 (a copy of the named snapshot, reset before each run); no pad key sent, so no save is loaded into gameplay"
fi
say "kernel lines since the start: $(sudo -n dmesg 2> /dev/null | tail -n +$((K0 + 1)) | grep -c -i 'amdgpu.*\(timeout\|fault\|reset\)')"
say "done $(date +%T)"
