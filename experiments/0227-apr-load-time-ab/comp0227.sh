#!/usr/bin/env bash
# BC5 experiment 0227: compress the files of old, uncited capture directories under ~/bc5-data/captures, to give the
# near-full NVMe room (writes ran at 14.5 MB/s with 29-31 GB free, 2026-10-23). The list (<list>, one dir name a line)
# holds only dirs dated 2026-10-20 or older whose name is cited nowhere in the repo, whose date and HHMM do not appear
# together in any repo file, and whose HHMM appears in no README (the top session's filter). Per file over 1 MiB that is
# not already .zst: zstd -19 -T2 at nice 19 / ionice idle into <file>.zst, `zstd -t` on the result, and only then the
# original is removed (safer than --rm before the test). One file at a time. It stops when an emulator runs or another
# session's BOX-LOCK appears, and on any zstd or test failure (that file's original is kept). Logs every file's
# sizes to <log>. usage: comp0227.sh <list> <log>   (on the box, only with the user's approval)
set -u
LIST=$1 LOG=$2
C=$HOME/bc5-data/captures; LOCK=$HOME/bc5-work/BOX-LOCK
busy() { pgrep '^kyty_emulator' > /dev/null && return 0; [ -s "$LOCK" ] && ! grep -q "^exp 0227 | compression" "$LOCK" && return 0; return 1; }
busy && { echo "box busy at $(date +%T): not started"; exit 1; }
echo "exp 0227 | compression of old uncited capture journals (zstd -19 -T2, nice 19, ionice idle; stops for any emulator or lock) | start $(date +%H:%M) | until ~$(date -d +60min +%H:%M)" > "$LOCK"
release() { grep -q "^exp 0227 | compression" "$LOCK" 2> /dev/null && rm -f "$LOCK"; }
trap release EXIT
echo "# comp0227 start $(date '+%F %T'); free $(df -B1M --output=avail ~ | tail -1) MiB" >> "$LOG"
B=0 A=0 N=0
while read -r d; do
  [ -n "$d" ] && [ -d "$C/$d" ] || continue
  while IFS= read -r -d '' f; do
    busy && { echo "# stopped at $(date '+%F %T'): box busy" >> "$LOG"; echo "stopped: box busy"; exit 2; }
    s0=$(stat -c %s "$f"); t0=$(date +%s)
    if nice -n 19 ionice -c3 zstd -19 -T2 -q "$f" -o "$f.zst" && nice -n 19 ionice -c3 zstd -t -q "$f.zst"; then
      s1=$(stat -c %s "$f.zst"); rm -f -- "$f"
      B=$((B + s0)); A=$((A + s1)); N=$((N + 1))
      echo "$d ${f#"$C/$d/"} $s0 $s1 $(($(date +%s) - t0))s" >> "$LOG"
    else
      rm -f -- "$f.zst"; echo "# FAILED on $f at $(date '+%F %T'): original kept, stop" >> "$LOG"; echo "FAILED on $f"; exit 3
    fi
  done < <(find "$C/$d" -type f -size +1M ! -name '*.zst' -print0)
done < "$LIST"
echo "# comp0227 end $(date '+%F %T'): $N files, $((B >> 20)) MiB -> $((A >> 20)) MiB, freed $(((B - A) >> 20)) MiB; free $(df -B1M --output=avail ~ | tail -1) MiB" >> "$LOG"
tail -1 "$LOG"
