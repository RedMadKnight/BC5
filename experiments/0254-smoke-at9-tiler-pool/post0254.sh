#!/usr/bin/env bash
# BC5 experiment 0254, after the GPU reset in S6N (2026-10-24 00:26:46): the second title's saves back, then the evidence,
# read-only. Run on the box once it answers again: ssh bc250 bash -s < post0254.sh
#   1. Touches nothing while an emulator runs or another session's (or the maintainer's) BOX-LOCK line is there; the
#      stale "exp 0254 | chain b" line is replaced by this script's own.
#   2. PPSA03671: S6N's ab-restore.sh had put the route saves in and kept the live ones in a new
#      exp0196/saves-before-0024*. Restored from that copy when its checksum (ab0253.sh's method: the md5 of the sorted
#      per-file md5s under PPSA03671/) is the water session's 00:11 value and it is diff -rq identical to the 00:21:08
#      copy; else from the 00:21:08 copy when that matches; else nothing is restored. What the folder held is kept in
#      exp0254/pkg-after-S6N. PPSA21564 is only compared with exp0254/astro-live-S5A.
#   3. Evidence: the previous boot's kernel log from 00:10 (if the journal persisted), S6N's run files, the play log's
#      tail and matching lines, the GPU journal's counts (jcount0254.awk), its last lines and its frames (ra0214.py).
#   4. The lock released.
set -u
W=$HOME/bc5-work; E=$W/exp0254; R=$E/raw; LOCK=$W/BOX-LOCK; SD=$W/_SaveData/PPSA03671; WANT=1a39860996fdac5c
OLD=$W/exp0196/saves-before-002108-610387381-471392
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator is running: nothing touched"; exit 1; }
if [ -s "$LOCK" ] && ! grep -q "^exp 0254 | chain b: " "$LOCK"; then echo "the box is locked: $(cat "$LOCK"): nothing touched"; exit 1; fi
echo "exp 0254 | after the GPU reset: second title's saves back, then evidence read-only (no emulator) | start $(date +%H:%M) | until ~$(date -d +10min +%H:%M)" > "$LOCK"
echo "== $(date +%T) lock taken; boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up since $(uptime -s)"
sum() {  # <dir>: ab0253.sh's checksum of a copy of PPSA03671, its paths written as PPSA03671/...
  (cd "$(dirname "$1")" && find "$(basename "$1")" -type f -exec md5sum {} + | sed "s|  $(basename "$1")/|  PPSA03671/|" | sort -k2 | md5sum | cut -c1-16)
}
NEW=$(ls -td "$W"/exp0196/saves-before-0024* 2> /dev/null | head -1)
echo "copies: new ${NEW:-none} ($(ls -d "$W"/exp0196/saves-before-0024* 2> /dev/null | wc -l) from 00:24), old $OLD"
SN=$([ -n "$NEW" ] && sum "$NEW"); SO=$(sum "$OLD"); SC=$(sum "$SD")
echo "checksums: new ${SN:-none}, old $SO, PPSA03671 now $SC (route saves $(sum "$W/exp0196/saves-before-152617")), wanted $WANT"
SRC=""
if [ -n "$NEW" ] && [ "$SN" = "$WANT" ] && diff -rq "$NEW" "$OLD" > /dev/null; then SRC=$NEW
elif [ "$SO" = "$WANT" ]; then SRC=$OLD; echo "the new copy does not match: the 00:21:08 copy is used"; fi
if [ -z "$SRC" ]; then echo "NO COPY MATCHES $WANT: PPSA03671 not touched"
elif [ "$SC" = "$WANT" ]; then echo "PPSA03671 already matches $WANT: not touched"
else
  rm -rf "$E/pkg-after-S6N" && cp -a "$SD" "$E/pkg-after-S6N" && diff -rq "$SD" "$E/pkg-after-S6N" > /dev/null \
    || { echo "PPSA03671 could not be kept aside: not touched"; SRC=""; }
  if [ -n "$SRC" ]; then
    rm -rf "$SD" && cp -a "$SRC" "$SD"
    diff -rq "$SRC" "$SD" > /dev/null && echo "PPSA03671 restored from $SRC, diff -rq identical (what it held: $E/pkg-after-S6N)"
  fi
fi
echo "PPSA03671 checksum now (ab0253.sh): $(cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)"
diff -rq "$E/astro-live-S5A" "$W/_SaveData/PPSA21564" > /dev/null && echo "PPSA21564 identical to astro-live-S5A" || echo "PPSA21564 DIFFERS from astro-live-S5A"
echo "== $(date +%T) evidence"
journalctl --list-boots --no-pager 2> /dev/null | tail -3
journalctl -k -b -1 --since "2026-10-24 00:10" -o short-precise --no-pager > "$R/S6N-kernel-prev-boot.txt" 2>&1
echo "previous boot's kernel log from 00:10: $(wc -l < "$R/S6N-kernel-prev-boot.txt") lines, last: $(tail -1 "$R/S6N-kernel-prev-boot.txt" | cut -c1-160)"
ls -l --time-style=+%T "$R"/S6N-* 2> /dev/null | cut -c30-
L=$W/play-pkg-last.log
echo "play log $(stat -c '%y %s' "$L")"
tail -c 2000000 "$L" > "$R/S6N-play-tail.log"
grep -a -n "Access violation\|Segmentation\|Aborted\|terminate called\|TIMEOUT\|[Ff]ault\|bc5 tiler scratch:\|bc5 ajm: ATRAC9\|CODEC_ERROR\|hold tail\|cs prefix\|aliases: fault" "$L" | cut -c1-300 | tail -60 > "$R/S6N-play-lines.txt"
echo "play log lines of interest: $(wc -l < "$R/S6N-play-lines.txt") (last 60 kept)"
J=$(ls -td "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
{ echo "journal $J $(stat -c '%y %s' "$J")"; nice -n 19 awk -f "$E/jcount0254.awk" "$J"; } > "$R/S6N-journal.txt" 2>&1
cat "$R/S6N-journal.txt"
tail -n 300 "$J" | cut -c1-400 > "$R/S6N-journal-tail.txt"
grep -a -n "TIMEOUT\|[Ff]ault\|GIVEN UP\|NOT served" "$J" | cut -c1-300 | tail -40 > "$R/S6N-journal-lines.txt"
echo "journal lines of interest: $(wc -l < "$R/S6N-journal-lines.txt") (last 40 kept)"
nice -n 19 python3 -I "$W/exp0214/ra0214.py" 50 100 "S6N=$J" > "$R/S6N-frames.txt" 2>&1
cat "$R/S6N-frames.txt"
grep -q "^exp 0254 | after the GPU reset" "$LOCK" && rm -f "$LOCK" && echo "== $(date +%T) BOX-LOCK released"
