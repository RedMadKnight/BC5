#!/usr/bin/env bash
# BC5 exp 0412 (README section 24): perf runs on arm fast2 with the gap classifier, repeated until one run has 40 s of
# the play phase or more (the top session's order), at most <n> runs. Each: perfgap0412.sh on Render Thread and
# game-main (in the container), run0412n.sh <tag> fast2 60 BC5_GUARD_GAP_STAT=100 (sampler, fuse, watchdog as always).
# A run that the watchdog ends early is kept and the next one starts. A file night/STOP ends the chain between runs.
# usage (on the box, under setsid nohup): ab0412p.sh <first number> <n>
set -u
X=$HOME/bc5-work/exp0412; N=$X/night
K=${1:?first number}; MAX=${2:?how many at most}
calm() { for _ in $(seq 1 60); do pgrep '^kyty_emulator' > /dev/null || pgrep -f perfgap0412.sh > /dev/null || [ -s "$HOME/bc5-work/BOX-LOCK" ] || return 0; sleep 5; done; return 1; }
for i in $(seq 1 "$MAX"); do
  tag="w$((K + i - 1))perf"
  [ -e "$N/STOP" ] && { echo "$(date +%T) chain: STOP before $tag"; exit 0; }
  calm || { echo "$(date +%T) chain: the box is not calm before $tag"; exit 1; }
  sleep 10
  (setsid nohup distrobox enter ubuntu -- bash "$X/perfgap0412.sh" "$N/raw/$tag-perf" 200 "Render Thread" game-main > /dev/null 2>&1 < /dev/null &)
  bash "$X/run0412n.sh" "$tag" fast2 60 BC5_GUARD_GAP_STAT=100 > "$N/run-$tag.log" 2>&1
  J=$(ls -td "$HOME"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log
  grep -a 'gap (exp 0412' "$J" | sed 's/^.*gap (exp 0412/gap (exp 0412/' > "$N/raw/$tag-gaps.txt"
  last=$(tail -1 "$N/raw/$tag-frames.txt" 2> /dev/null | cut -d' ' -f1 | cut -d. -f1)
  echo "$(date +%T) chain: $tag: $(cut -c1-120 "$N/raw/$tag-summary.txt" 2> /dev/null); last frame at ${last:-?} s"
  if [ "${last:-0}" -ge 172 ]; then echo "$(date +%T) chain: $tag has its play phase; end"; exit 0; fi
done
echo "$(date +%T) chain: end, no run reached 172 s"
