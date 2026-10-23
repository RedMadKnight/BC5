#!/usr/bin/env bash
# BC5 (2026-10-23, the maintainer said yes): compress the emulator's capture journals once a day.
# Every play run writes ~/bc5-data/captures/play-<date>-<time>/ (PLAY_CAPTURE=1), with gc/direct.log
# and guest-printf.txt often 1-5 GB each. They filled the box's DRAM-less NVMe to 94 %, where writes
# fell to 14.5 MB/s and loads slowed down (experiment 0227). This compresses every file over 10 MB that
# is older than two days with zstd -3 (lossless, ~20-35x on these logs; `zstd -d` restores it), tests
# each archive before removing its original, and stops on the first failure. It skips the day when the
# box is busy (a BOX-LOCK line or a running emulator) and stops if an emulator starts meanwhile.
# Installed as the systemd user timer bc5-compress-captures.timer (daily, Persistent=true).
set -u
CAP=${BC5_CAPTURES:-$HOME/bc5-data/captures}
LOG=${BC5_COMPRESS_LOG:-$HOME/bc5-work/compress-captures.log}
LOCK=$HOME/bc5-work/BOX-LOCK
TAG="bc5-compress-captures | daily capture compression (zstd -3, nice/ionice)"
stamp() { date '+%F %T'; }
if [ -s "$LOCK" ] || pgrep '^kyty_emulator' >/dev/null; then
  echo "$(stamp) box busy, skipped" >> "$LOG"; exit 0
fi
echo "$TAG | start $(date +%H:%M)" > "$LOCK"
trap 'grep -q "^bc5-compress-captures |" "$LOCK" 2>/dev/null && rm -f "$LOCK"' EXIT
LIST=$(mktemp)
find "$CAP" -mindepth 2 -type f -size +10M ! -name '*.zst' -mmin +2880 -printf '%s %p\n' 2>/dev/null | sort -nr > "$LIST"
echo "$(stamp) start: $(wc -l < "$LIST") files; avail $(df -h --output=avail "$CAP" | tail -1)" >> "$LOG"
n=0; in=0; out=0
while read -r sz f; do
  if pgrep '^kyty_emulator' >/dev/null; then echo "$(stamp) emulator started, stopping" >> "$LOG"; break; fi
  if nice -n19 ionice -c3 zstd -q -3 -T2 "$f" -o "$f.zst" && zstd -q -t "$f.zst"; then
    zs=$(stat -c %s "$f.zst"); rm -f -- "$f"
    n=$((n + 1)); in=$((in + sz)); out=$((out + zs))
  else
    echo "$(stamp) FAIL $f (original kept)" >> "$LOG"; rm -f -- "$f.zst"; break
  fi
done < "$LIST"
rm -f "$LIST"
echo "$(stamp) done: $n files, $((in / 1048576)) MiB -> $((out / 1048576)) MiB; avail $(df -h --output=avail "$CAP" | tail -1)" >> "$LOG"
