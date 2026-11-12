#!/usr/bin/env bash
# BC5 exp 0412 (README section 53, DESIGN-learned-windows.md): the rule against the learned windows, on build g412x
# BESIDE the one in place (bin-x/kyty_emulator, N_EMU). The scripted route, 120 s after G, arm fast8's words, RT on,
# fuse 13,000, watchdog 220 MiB, the kernel log streamed by the caller. Arms:
#   c0  control: the three switches off, the 81-window learned file (a private copy, as always)
#   c4  an EMPTY private learned file, BC5_GUARD_LEARN_LOG=1 (today's import policy without the memory of earlier runs)
#   r1  empty file, BC5_GUARD_MAP_RULE=1, LEARN_LOG=1 (R1 alone: a miss still faults)
#   r2  empty file, MAP_RULE=1, BC5_GUARD_PRT_BG=1, LEARN_LOG=1 (R1 + R2)
# Order c0 c4 r1 r2 r2 r1 c4 c0. A run rides out two recovered GPU hangs and stops at the third (N_RESETS=3); the series
# stops after any run that ended on a GPU hang without "reset succeeded", and never writes the shared learned file.
# Before every arm: the lock empty and no emulator for 60 s in a row. Starts no arm after LAST (HH:MM).
# usage (on the box): LAST=01:10 bash ab0412r.sh > night/ab0412r.out 2>&1
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; LOCK=$W/BOX-LOCK; N=$X/night; R=$N/raw; EMU=$X/bin-x/kyty_emulator
LAST=${LAST:-23:59}
EMPTY=$N/learned-empty.txt
: > "$EMPTY" || exit 1
SUM0=$(md5sum < "$W/direct-learned-pkg.txt"); ALI0=$(md5sum < "$W/direct-aliases-pkg.txt")
now() { date +%H:%M; }
free_box() { [ ! -s "$LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null; }
arm() {   # <tag> empty|file [KEY=VALUE ...]
  local tag=$1 lf=$2; shift 2
  [ -e "$R/$tag-start.txt" ] && { echo "$(date +%T) $tag already run: skipped"; return 0; }
  local ok=0
  while [ "$ok" -lt 6 ]; do if free_box; then ok=$((ok + 1)); else ok=0; fi; sleep 10; [[ "$(now)" > "$LAST" ]] && { echo "$(date +%T) $tag not started: past $LAST"; return 1; }; done
  echo "$(date +%T) $tag ($lf $*): plasmashell $(pgrep -cx plasmashell), rsync processes $(pgrep -c rsync), steamwebhelper $(pgrep -c steamwebhelper), available $(awk '/^MemAvailable/ {print int($2 / 1024)}' /proc/meminfo) MiB"
  if [ "$lf" = empty ]; then
    N_LEARN=$EMPTY N_RESETS=3 N_EMU=$EMU N_FUSE="13000 2048" N_WD_MIB=220 bash "$X/run0412n.sh" "$tag" fast8 120 "$@" 2>&1 | tail -1
  else
    N_RESETS=3 N_EMU=$EMU N_FUSE="13000 2048" N_WD_MIB=220 bash "$X/run0412n.sh" "$tag" fast8 120 "$@" 2>&1 | tail -1
  fi
  cp -p "$N/direct-learned-pkg.txt" "$R/$tag-learned.txt" 2> /dev/null
  local j; j=$(sed -n 's/^journal \([^ ]*\) .*/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
  grep -a "^would learn\|^map rule\|^timeout: fault\|^learned: fault\|^reopen\|PRT window" "$j" "$R/$tag-play.log" 2> /dev/null | cut -c1-700 > "$R/$tag-rule.txt"
  echo "$(date +%T) $tag ended: $(grep -o 'lowest available [0-9]* MiB, highest PSI full [0-9]* %' "$R/$tag-watchdog.txt" 2> /dev/null); would-learn lines $(grep -c 'would learn' "$R/$tag-rule.txt"); private learned file $(grep -c '' "$R/$tag-learned.txt" 2> /dev/null) lines; $(grep -a '^guard: t' "$R/$tag-guard.txt" 2> /dev/null | tail -1 | grep -o 'pinned direct [0-9.]* MiB')"
  grep -a 'map rule' "$R/$tag-rule.txt" | head -2 | cut -c1-300
  [ "$(md5sum < "$W/direct-learned-pkg.txt")" = "$SUM0" ] && [ "$(md5sum < "$W/direct-aliases-pkg.txt")" = "$ALI0" ] || { echo "$(date +%T) STOP: the shared learned or alias file changed"; return 1; }
  if grep -q "GPU HANG" "$R/$tag-end.txt" 2> /dev/null && ! grep -q "reset succeeded" "$R/$tag-end.txt"; then echo "$(date +%T) STOP: $tag ended on a GPU hang without a recovered reset"; return 1; fi
  return 0
}
arm c0a file || exit 0
arm c4a empty BC5_GUARD_LEARN_LOG=1 || exit 0
arm r1a empty BC5_GUARD_MAP_RULE=1 BC5_GUARD_LEARN_LOG=1 || exit 0
arm r2a empty BC5_GUARD_MAP_RULE=1 BC5_GUARD_PRT_BG=1 BC5_GUARD_LEARN_LOG=1 || exit 0
arm r2b empty BC5_GUARD_MAP_RULE=1 BC5_GUARD_PRT_BG=1 BC5_GUARD_LEARN_LOG=1 || exit 0
arm r1b empty BC5_GUARD_MAP_RULE=1 BC5_GUARD_LEARN_LOG=1 || exit 0
arm c4b empty BC5_GUARD_LEARN_LOG=1 || exit 0
arm c0b file || exit 0
echo "$(date '+%F %T') series done"
