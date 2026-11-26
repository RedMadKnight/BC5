#!/usr/bin/env bash
# BC5 experiment 0205: the readahead A/B part 2 (B2, A2, A3, B3 on the v2 binary), then the S2 rerun as S2b if no kernel
# line appeared; granted 2026-10-22 18:23 by the top session, one lock per run. Run on the box from SSH.
B=$HOME/bc5-work/exp0205
d0=$(sudo -n dmesg | wc -l)
$B/ab0205.sh B2:B A2:A A3:A B3:B > $B/ab-part2.txt 2>&1; echo "ab0205 exit $?" >> $B/ab-part2.txt
for _ in $(seq 1 12); do [ -s ~/bc5-work/BOX-LOCK ] || pgrep -x kyty_emulator >/dev/null || break; sleep 5; done
sleep 2
grep -q "ab0205 exit 0" $B/ab-part2.txt || { echo "S2b NOT STARTED: part 2 did not finish" > $B/S2b.run.txt; exit 1; }
new=$(sudo -n dmesg | tail -n +$((d0 + 1)) | grep -i "amdgpu\|fault\|timeout")
[ -n "$new" ] && { echo "S2b NOT STARTED, kernel lines: $new" > $B/S2b.run.txt; exit 1; }
$B/s2-0205.sh > $B/S2b.run.txt 2>&1
