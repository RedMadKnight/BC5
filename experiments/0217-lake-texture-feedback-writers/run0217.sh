#!/usr/bin/env bash
# BC5 experiment 0217: one lake-bench run (exp 0212's bench0212.sh; its default binary, the exp 0194 build, whose draw
# journal flags "cp-skip" for indirect draws the host's check would drop) with the draw journal on the four
# candidate feedback writers and the water's two draws, the descriptor table dumped per shot (DUMPS=1), and, once the
# frozen view is reached, the code of the water mesh draw's programs read from the running emulator's memory into the
# private directory ~/bc5-data/priv/exp0217 (the title's code: never copied off the box). Afterwards: the descriptors of
# the journalled draws (desc0212.py) and the code's store/atomic counts (prog0212.py, llvm-mc in the ubuntu container).
# usage: run0217.sh <tag>   (on the box, from SSH, when granted)
set -u
TAG=${1:?tag}
E=$HOME/bc5-work/exp0217
PRIV=$HOME/bc5-data/priv/exp0217
PSL=11d0c13700,11d0d6c400,11d3269600,11d3269800,11d01ff900,11d01d7100
[ -e "$HOME/bc5-work/exp0194/r-$TAG" ] && { echo "tag $TAG used"; exit 1; }
mkdir -p "$PRIV" && chmod 700 "$PRIV"
before=$(sudo -n dmesg | wc -l)
( DUMPS=1 ENVX="BC5_DIRECT_DRAW_JOURNAL=150:4 BC5_DIRECT_DRAW_JOURNAL_EVERY=15 BC5_DIRECT_DRAW_JOURNAL_PS=$PSL" \
    "$HOME/bc5-work/exp0212/bench0212.sh" "$TAG" > "$E/$TAG.bench.txt" 2>&1 ) &
BP=$!
# wait for the frozen view (the first frozen-view shot), then read the water mesh draw's programs (64 KiB and 16 KiB)
for _ in $(seq 1 120); do ls "$HOME/bc5-work/exp0194/r-$TAG/shots/" 2>/dev/null | grep -q ts00 && break; sleep 3; done
EP=$(pgrep -n -x kyty_emulator)
[ -n "$EP" ] && python3 -I "$HOME/bc5-work/exp0212/mem0212.py" dump "$EP" "$PRIV/code" 11d01ff900:10000 11d0148800:4000 > "$E/$TAG.codedump.txt" 2>&1
wait $BP
for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
jd=$(cat "$HOME/bc5-work/exp0194/r-$TAG/journal-dir.txt" 2>/dev/null)
[ -n "$jd" ] && nice -n 10 python3 -I "$HOME/bc5-work/exp0212/desc0212.py" "$jd/direct.log" 11d0c13700 11d0d6c400 11d3269600 11d3269800 11d01ff900 11d01d7100 > "$E/$TAG.desc.txt" 2>&1
[ -n "$jd" ] && grep -a -c "cp-skip" "$jd/direct.log" | sed 's/^/cp-skip lines in the journal: /' >> "$E/$TAG.desc.txt"
for a in 11d01ff900 11d0148800; do
  f="$PRIV/code.$a.bin"
  n=4000; [ "$a" = 11d01ff900 ] && n=10000
  [ -f "$f" ] && distrobox enter ubuntu -- nice -n 10 python3 -I "$HOME/bc5-work/exp0212/prog0212.py" "$f" "$a" "$a" "$PRIV" "$n" 2>&1 | grep -v "^Starting\|distrobox" | tail -4
done > "$E/$TAG.code.txt"
sudo -n dmesg | tail -n +$((before + 1)) | grep -i "amdgpu\|fault\|timeout" | sed 's/^/kernel: /' >> "$E/$TAG.code.txt"
echo "$(date +%T) $TAG done"
