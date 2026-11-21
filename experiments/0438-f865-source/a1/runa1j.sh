#!/usr/bin/env bash
# BC5 exp 0438 (tags a1, a1b, a1p, a2): the recording run. ASTRO BOT (or the title given) for 180 s unless
# given, on the A1 normal test build (the binary boxa1.sh last wrote, its binary.md5) with KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 BC5_DIRECT_0438_A2_CHECK=1, the A1J range-edit
# journal to $R/$TAG-a1j.bin, BC5_FAULT_RECORD=1. Through exp 0413's start0413g.sh (its own BOX-LOCK claim; it ends the
# run at once on an amdgpu timeout / reset / fault line in dmesg). Beside it a watcher ends the emulator on the first A2
# compare-only MISMATCH line. The reset count is written before and after. GPU-risk: the first run of A1/A1P/A2 on a
# real title. Diagnosis only.
# The lock (LESSONS R68): this script claims BOX-LOCK itself (start0413g.sh's atomic hard-link claim) and passes the
# line to start0413g.sh as CHAIN_LOCKLINE, so the lock stays held until no kyty_emulator / bc5-mount is left and the
# data is on disk; a leftover emulator of our binary gets TERM, then KILL.
# usage (on the box, under the user manager): bash runa1j.sh <tag> [title, astro] [seconds, 180]
set -u
ulimit -c 0
export LC_ALL=C
TAG=${1:?tag}; TITLE=${2:-astro}; SECS=${3:-180}; N=$HOME/bc5-work/exp0413/n; R=$N/raw; BIN=$HOME/bc5-work/exp0438/a1/normal/kyty_emulator
WANT=$(md5sum < "$BIN" | cut -d' ' -f1)
[ "$WANT" = "$(cat "$(dirname "$BIN")/binary.md5")" ] || { echo "the binary is not boxa1.sh's ($(cat "$(dirname "$BIN")/binary.md5")): not started"; exit 1; }
J=$R/$TAG-a1j.bin; S=$R/$TAG-a1j-run.txt
resets() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -ciE 'ring .* timeout|reset (succeeded|failed)|GPU reset|device wedged'; }
mkdir -p "$R"
LOCK=$HOME/bc5-work/BOX-LOCK; LINE="exp 0438 | recording run $TAG ($TITLE, $SECS s) on ${WANT:0:8}, token $(date +%s)$$ | $(date '+%F %T')"
INHERIT=0 # a wrapper that holds one lock line for several steps passes it in CHAIN_LOCKLINE (as start0413g.sh)
if [ -n "${CHAIN_LOCKLINE:-}" ] && [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK")" = "$CHAIN_LOCKLINE" ]; then INHERIT=1; LINE=$CHAIN_LOCKLINE; fi
if [ "$INHERIT" = 0 ]; then
[ -e "$LOCK" ] || touch "$LOCK"
[ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ ! -s "$LOCK" ] || { echo "the box is locked: $(cat "$LOCK")"; exit 1; }
tl=$LOCK.0438r-$$.new; al=$LOCK.0438r-$$.aside
printf '%s\n' "$LINE" > "$tl" && mv -T "$LOCK" "$al" && ln "$tl" "$LOCK" || { [ -e "$LOCK" ] || mv -T "$al" "$LOCK"; rm -f "$tl"; echo "the claim failed"; exit 1; }
if [ -s "$al" ]; then mv -fT "$al" "$LOCK"; rm -f "$tl"; echo "a foreign line arrived during the claim: not started"; exit 1; fi
rm -f "$al" "$tl"
fi
release() { [ "$INHERIT" = 1 ] && return 0; if [ -f "$LOCK" ] && grep -qxF -- "$LINE" "$LOCK"; then local t=$LOCK.0438r-$$.rel; grep -vxF -- "$LINE" "$LOCK" > "$t"; mv -fT "$t" "$LOCK"; fi; }
pgrep -x kyty_emulator > /dev/null || pgrep -x bc5-mount > /dev/null && { release; echo "an emulator or bc5-mount runs: not started"; exit 1; }
echo "$(date '+%F %T') $TAG: resets before $(resets), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), binary $WANT" > "$S"
( while sleep 2; do
    if grep -aq 'exp 0438 (tag a2): MISMATCH' "$N/$TITLE-last.log" 2> /dev/null; then
      echo "$(date +%T) A2 MISMATCH seen: the emulator is ended" >> "$S"; pkill -TERM -o -x kyty_emulator; break
    fi
  done ) &
WP=$!
cd "$N" && CHAIN_LOCKLINE=$LINE P_BIN=$BIN P_WANT=$WANT bash ./start0413g.sh "$TAG" "$TITLE" "$SECS" KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 \
  BC5_DIRECT_0438_A2_CHECK=1 "KYTY_BC5_0438_A1J=$J" BC5_FAULT_RECORD=1 > "$R/$TAG-runner.txt" 2>&1
rc=$?
kill "$WP" 2> /dev/null
left() { for p in $(pgrep -x kyty_emulator) $(pgrep -x bc5-mount); do echo "$p $(tr '\0' ' ' < "/proc/$p/cmdline" | cut -c1-80)"; done; }
L1=$(left)
for p in $(pgrep -x kyty_emulator); do [ "$(md5sum < "/proc/$p/exe" | cut -d' ' -f1)" = "$WANT" ] && kill -TERM "$p"; done
[ -n "$L1" ] && sleep 6
for p in $(pgrep -x kyty_emulator); do [ "$(md5sum < "/proc/$p/exe" | cut -d' ' -f1)" = "$WANT" ] && kill -KILL "$p"; done
sleep 1; L2=$(left)
{ echo "$(date '+%F %T') runner exit $rc: $(tail -1 "$R/$TAG-runner.txt")"
  echo "left after the runner: ${L1:-none}; after the check: ${L2:-none}"
  echo "resets after $(resets)"
  echo "journal $(stat -c %s "$J" 2> /dev/null || echo none) bytes"
  echo "counter lines: a1c438 $(grep -ac 'tag a1c438' "$R/$TAG-play.log" 2> /dev/null), a2c438 $(grep -ac 'tag a2c438' "$R/$TAG-play.log" 2> /dev/null); last:"
  grep -a 'tag a1c438' "$R/$TAG-play.log" 2> /dev/null | tail -1; grep -a 'tag a2c438' "$R/$TAG-play.log" 2> /dev/null | tail -1
  echo "A2 lines: $(grep -ac 'exp 0438 (tag a2)' "$R/$TAG-play.log" 2> /dev/null), MISMATCH $(grep -ac 'tag a2): MISMATCH' "$R/$TAG-play.log" 2> /dev/null); A1 lines $(grep -a 'tag a1438' "$R/$TAG-play.log" 2> /dev/null | head -2 | tr '\n' ' ')"; } >> "$S"
sync
if [ -z "$L2" ]; then release; echo "lock released: $(cat "$LOCK" 2> /dev/null)" >> "$S"; else echo "LOCK KEPT: processes left: $L2" >> "$S"; fi
cat "$S"
