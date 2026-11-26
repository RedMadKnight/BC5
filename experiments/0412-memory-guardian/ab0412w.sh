#!/usr/bin/env bash
# BC5 exp 0412 (README section 47): which of the words lean drops keeps the zero skip from hanging the GPU.
# After his lean7 play hung at 107 s (2026-11-12 07:52) and arm a1lw (g412v with lean's word set) hung at G+61 s.
# Arms on g412v, the scripted route, 120 s after G, fuse 13,000, watchdog 220 MiB:
#   f7 = arm fast7 (all words); lw = arm lw7 (the six words dropped); ai = lw7 + BC5_DIRECT_ACB_INHERIT=journal;
#   tc = lw7 + BC5_DIRECT_TABLE_CATCHER=1; jr = lw7 + the four journal words.
# Waits for the box: the lock empty for 60 s and no emulator, not before NOT_BEFORE (HH:MM); starts no arm after LAST (HH:MM).
# usage (on the box): NOT_BEFORE=15:45 LAST=16:52 bash ab0412w.sh > ab0412w.out 2>&1
set -u
export LC_ALL=C
W=$HOME/bc5-work; X=$W/exp0412; LOCK=$W/BOX-LOCK; R=$X/night/raw
NB=${NOT_BEFORE:-00:00}; LAST=${LAST:-23:59}
now() { date +%H:%M; }
free_box() { [ ! -s "$LOCK" ] && ! pgrep '^kyty_emulator' > /dev/null; }
while [[ "$(now)" < "$NB" ]]; do sleep 20; done
ok=0
while [ "$ok" -lt 6 ]; do if free_box; then ok=$((ok + 1)); else ok=0; fi; sleep 10; [[ "$(now)" > "$LAST" ]] && { echo "the box did not come free before $LAST"; exit 1; }; done
echo "$(date '+%F %T') the box is free; series starts"
arm() {   # <tag> <arm> [KEY=VALUE ...]
  local tag=$1 a=$2; shift 2
  [[ "$(now)" > "$LAST" ]] && { echo "$(date +%T) $tag not started: past $LAST"; return 1; }
  [ -e "$R/$tag-start.txt" ] && { echo "$(date +%T) $tag already run: skipped"; return 0; }
  local ok=0   # wait for the box (another session may take it between arms): free for 60 s in a row
  while [ "$ok" -lt 6 ]; do if free_box; then ok=$((ok + 1)); else ok=0; fi; sleep 10; [[ "$(now)" > "$LAST" ]] && { echo "$(date +%T) $tag not started: past $LAST"; return 1; }; done
  echo "$(date +%T) $tag: rsync processes $(pgrep -c rsync), steamwebhelper $(pgrep -c steamwebhelper)"
  N_FUSE="13000 2048" N_WD_MIB=220 bash "$X/run0412n.sh" "$tag" "$a" 120 "$@" 2>&1 | tail -1
  echo "$(date +%T) $tag ended: rsync processes $(pgrep -c rsync); $(grep -c 'canary hit' "$(sed -n 's/^journal \([^ ]*\) .*/\1/p' "$R/$tag-journal.txt")" 2> /dev/null) canary hits"
}
JR=(BC5_GUARD_LEDGER=1 KYTY_BC5_EVENT_PENDING_LOG=1 BC5_DIRECT_RESET_LABEL_JOURNAL=1 BC5_DIRECT_JOURNAL_QUIET=1)
arm b1f7 fast7 || exit 0
arm b2lw lw7 || exit 0
arm b3ai lw7 BC5_DIRECT_ACB_INHERIT=journal || exit 0
arm b4tc lw7 BC5_DIRECT_TABLE_CATCHER=1 || exit 0
arm b5jr lw7 "${JR[@]}" || exit 0
arm b6f7 fast7 || exit 0
arm b7lw lw7 || exit 0
arm b8ai lw7 BC5_DIRECT_ACB_INHERIT=journal || exit 0
arm b9tc lw7 BC5_DIRECT_TABLE_CATCHER=1 || exit 0
echo "$(date '+%F %T') series done"
