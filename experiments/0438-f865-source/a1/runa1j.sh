#!/usr/bin/env bash
# BC5 exp 0438 (tags a1, a1b, a1p, a2): the recording run. ASTRO BOT (or the title given) for 180 s unless
# given, on the A1 normal test build (the binary boxa1.sh last wrote, its binary.md5) with KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 BC5_DIRECT_0438_A2_CHECK=1, the A1J range-edit
# journal to $R/$TAG-a1j.bin, BC5_FAULT_RECORD=1. Through exp 0413's start0413g.sh (its own BOX-LOCK claim; it ends the
# run at once on an amdgpu timeout / reset / fault line in dmesg). Beside it a watcher ends the emulator on the first A2
# compare-only MISMATCH line. The reset count is written before and after. GPU-risk: the first run of A1/A1P/A2 on a
# real title. Diagnosis only.
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
echo "$(date '+%F %T') $TAG: resets before $(resets), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), binary $WANT" > "$S"
( while sleep 2; do
    if grep -aq 'exp 0438 (tag a2): MISMATCH' "$N/$TITLE-last.log" 2> /dev/null; then
      echo "$(date +%T) A2 MISMATCH seen: the emulator is ended" >> "$S"; pkill -TERM -o -x kyty_emulator; break
    fi
  done ) &
WP=$!
cd "$N" && P_BIN=$BIN P_WANT=$WANT bash ./start0413g.sh "$TAG" "$TITLE" "$SECS" KYTY_BC5_0438_A1=1 KYTY_BC5_0438_A1P=1 BC5_DIRECT_0438_A2=1 \
  BC5_DIRECT_0438_A2_CHECK=1 "KYTY_BC5_0438_A1J=$J" BC5_FAULT_RECORD=1 > "$R/$TAG-runner.txt" 2>&1
rc=$?
kill "$WP" 2> /dev/null
{ echo "$(date '+%F %T') runner exit $rc: $(tail -1 "$R/$TAG-runner.txt")"
  echo "resets after $(resets)"
  echo "journal $(stat -c %s "$J" 2> /dev/null || echo none) bytes"
  echo "counter lines: a1c438 $(grep -ac 'tag a1c438' "$R/$TAG-play.log" 2> /dev/null), a2c438 $(grep -ac 'tag a2c438' "$R/$TAG-play.log" 2> /dev/null); last:"
  grep -a 'tag a1c438' "$R/$TAG-play.log" 2> /dev/null | tail -1; grep -a 'tag a2c438' "$R/$TAG-play.log" 2> /dev/null | tail -1
  echo "A2 lines: $(grep -ac 'exp 0438 (tag a2)' "$R/$TAG-play.log" 2> /dev/null), MISMATCH $(grep -ac 'tag a2): MISMATCH' "$R/$TAG-play.log" 2> /dev/null); A1 lines $(grep -a 'tag a1438' "$R/$TAG-play.log" 2> /dev/null | head -2 | tr '\n' ' ')"; } >> "$S"
cat "$S"
