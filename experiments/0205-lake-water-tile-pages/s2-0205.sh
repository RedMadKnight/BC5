#!/usr/bin/env bash
# BC5 experiment 0205, run S2b (plan step 2): one bench run on the exp 0194 build with the water shaders' journal
# (their texture descriptors, re-read in this run) and KYTY_BC5_AMM_TRACE=2 (every AMM map, unmap and read, plus one
# line per AMM library call: does the title call AmmGetUsageStatsData / AmmSetPageTablePoolOccupancyNotificationThreshold,
# raw/review-3b.txt). Then: the log copied into exp0205, the descriptors decoded (desc0205.py), and the kernel lines
# since the start. Run on the box from SSH, only when granted; output in ~/bc5-work/exp0205/S2b.*. (S2 itself, 18:16, reused exp 0194's r-S2: raw/B1b-S2.txt.)
set -u
B=$HOME/bc5-work/exp0205
[ -s ~/bc5-work/BOX-LOCK ] && { echo "box locked: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator is running"; exit 1; }
before=$(sudo -n dmesg | wc -l)
echo "$(date +%T) S2b start, boot $(cat /proc/sys/kernel/random/boot_id), dmesg $before lines"
ENVX="BC5_DIRECT_DRAW_JOURNAL=150:4 BC5_DIRECT_DRAW_JOURNAL_EVERY=15 BC5_DIRECT_DRAW_JOURNAL_PS=11d01d7100,11d01ff900 KYTY_BC5_AMM_TRACE=2" \
  PAGES=1 PAGES_RANGES="8492504000:800000 80907c4000:200000 8001810000:800000 8001010000:200000" \
  "$B/bench0205.sh" S2b > "$B/S2b.bench.txt" 2>&1
echo "$(date +%T) bench exit $?"
for _ in $(seq 1 60); do pgrep -x kyty_emulator > /dev/null || break; sleep 5; done
for _ in $(seq 1 12); do [ -f ~/bc5-work/exp0194/r-S2b/journal-dir.txt ] && break; sleep 5; done
cp ~/bc5-work/play-pkg-last.log "$B/S2b-play-pkg.log"
J=$(cat ~/bc5-work/exp0194/r-S2b/journal-dir.txt 2>/dev/null)
echo "$(date +%T) log $(stat -c %s "$B/S2b-play-pkg.log") bytes, journal $J"
[ -n "$J" ] && nice -n 10 python3 -I "$B/desc0205.py" "$J/direct.log" > "$B/S2b-desc.txt" 2>&1
grep -a -c "AmmSetPageTablePoolOccupancyNotificationThreshold" "$B/S2b-play-pkg.log" | sed 's/^/threshold calls: /'
grep -a -c "AmmGetUsageStatsData" "$B/S2b-play-pkg.log" | sed 's/^/usage-stats calls: /'
sudo -n dmesg | tail -n +$((before + 1)) | grep -i "amdgpu\|fault\|timeout" | sed 's/^/kernel: /'
echo "$(date +%T) S2b done; lock: $(cat ~/bc5-work/BOX-LOCK 2>/dev/null)"
