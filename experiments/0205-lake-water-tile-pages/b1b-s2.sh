#!/usr/bin/env bash
# BC5 experiment 0205: the B1 rerun on the v2 readahead binary (ab0205.sh B1b:B), then, if B1b left no kernel line, run S2
# (s2-0205.sh); granted 2026-10-22 ~18:10, one lock each. Run on the box from SSH.
B=$HOME/bc5-work/exp0205
d0=$(sudo -n dmesg | wc -l)
$B/ab0205.sh B1b:B > $B/ab-B1b.txt 2>&1; echo "ab0205 exit $?" >> $B/ab-B1b.txt
for _ in $(seq 1 12); do [ -s ~/bc5-work/BOX-LOCK ] || pgrep -x kyty_emulator >/dev/null || break; sleep 5; done
sleep 2
new=$(sudo -n dmesg | tail -n +$((d0 + 1)) | grep -i "amdgpu\|fault\|timeout")
[ -n "$new" ] && { echo "S2 NOT STARTED, kernel lines: $new" > $B/S2.run.txt; exit 1; }
$B/s2-0205.sh > $B/S2.run.txt 2>&1
