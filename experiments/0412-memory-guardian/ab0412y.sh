#!/usr/bin/env bash
# BC5 exp 0412 (README section 50, DESIGN-memory-architecture.md option A, on the maintainer's "Tak, wariant A"):
# what does Plasma's shell cost at the wall? The scripted route on fast8's words (g412v in place, no zero skip), 120 s
# after G, fuse 13,000, watchdog 220 MiB, with snap0412.sh's whole-box snapshots (meminfo, processes, cgroups, the GPU
# clients by fdinfo) at 25, 60, 130, 165 and 225 s. Arms in the order shell, bare, bare, shell:
#   shell = the desktop as it is;  bare = plasmashell stopped for the run and started again after it (also on any exit).
# kwin, the session and everything else stay. Nothing is installed or configured; no system setting is changed.
# Before every arm: the lock empty and no emulator for 60 s in a row. Starts no arm after LAST (HH:MM).
# usage (on the box): LAST=22:30 bash ab0412y.sh > ab0412y.out 2>&1
set -u
export LC_ALL=C
export XDG_RUNTIME_DIR=/run/user/$(id -u)
W=$HOME/bc5-work; X=$W/exp0412; LOCK=$W/BOX-LOCK; R=$X/night/raw
LAST=${LAST:-23:59}
UNIT=plasma-plasmashell.service
now() { date +%H:%M; }
free_box() { [ ! -s "$LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null; }
shell_up() { pgrep -x plasmashell > /dev/null; }
STOPPED=0
shell_stop() {
  shell_up || { echo "$(date +%T) plasmashell is not running: nothing to stop"; return 1; }
  systemctl --user is-active -q "$UNIT" || { echo "$(date +%T) $UNIT is not active (plasmashell runs another way): bare arm skipped"; return 1; }
  STOPPED=1
  systemctl --user stop "$UNIT"; sleep 3
  if shell_up; then echo "$(date +%T) plasmashell still runs after the stop"; shell_start; return 1; fi
  echo "$(date +%T) plasmashell stopped"
}
shell_start() {
  [ "$STOPPED" = 1 ] || return 0
  systemctl --user start "$UNIT"; sleep 5
  if shell_up; then STOPPED=0; echo "$(date +%T) plasmashell started again"; else echo "$(date +%T) PLASMASHELL DID NOT START: run 'systemctl --user start $UNIT' by hand"; fi
}
trap shell_start EXIT
arm() {   # <tag> shell|bare
  local tag=$1 kind=$2
  [ -e "$R/$tag-start.txt" ] && { echo "$(date +%T) $tag already run: skipped"; return 0; }
  local ok=0
  while [ "$ok" -lt 6 ]; do if free_box; then ok=$((ok + 1)); else ok=0; fi; sleep 10; [[ "$(now)" > "$LAST" ]] && { echo "$(date +%T) $tag not started: past $LAST"; return 1; }; done
  if [ "$kind" = bare ]; then shell_stop || return 0; fi
  echo "$(date +%T) $tag ($kind): plasmashell $(pgrep -cx plasmashell), rsync processes $(pgrep -c rsync), steamwebhelper $(pgrep -c steamwebhelper)"
  bash "$X/snap0412.sh" "$R/$tag-snap.txt" 25 60 130 165 225 &
  local sp=$!
  N_FUSE="13000 2048" N_WD_MIB=220 bash "$X/run0412n.sh" "$tag" fast8 120 2>&1 | tail -1
  wait "$sp" 2> /dev/null
  [ "$kind" = bare ] && shell_start
  echo "$(date +%T) $tag ended: $(grep -o 'lowest available [0-9]* MiB' "$R/$tag-watchdog.txt" 2> /dev/null); snapshots $(grep -c '^######## snapshot' "$R/$tag-snap.txt" 2> /dev/null)"
}
arm y1sh shell || exit 0
arm y2ba bare || exit 0
arm y3ba bare || exit 0
arm y4sh shell || exit 0
echo "$(date '+%F %T') series done"
