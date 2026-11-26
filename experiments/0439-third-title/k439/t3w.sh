#!/usr/bin/env bash
# BC5 exp 0439: the exploration run (the top session's step 2 of 11-21 ~22:45): t3s.sh in script mode, 600 s, the switch set
# of 21:51 with the fixed pass (CB_SHADER_MASK 0xf built in), crosses at 45 s and then every 20 s while the picture stands
# still for 15 s, screenshots every 10 s, memory every 30 s (runs/t3s-vunset-x.mem), a stall ends the run after its snapshot.
#   t3w.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
T3S_TAG=-x T3S_BOUND=600 T3S_STALL_STOP=1 T3S_EXTRA="BC5_0439_AUDIO_CATCH=1" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -40
O=runs/t3s-vunset-x; P=$O/play-last.log
echo "== presses"; cat $O.keys
echo "== memory"; cat $O.mem
echo "== stall"; cat $O/stall/when.txt 2> /dev/null || echo "none"
echo "== rate per 30 s (frame-profile lines)"
J=$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log
grep -a -o "frame profile: t [0-9.]* s" "$J" | awk '{b = int($4 / 30); n[b]++; if (b > m) m = b} END {for (b = 0; b <= m; b++) printf "%d-%ds %.1f/s\n", b * 30, b * 30 + 30, n[b] / 30}'
echo "== stub calls with the nearest earlier journal time"
awk '/ t [0-9]+\.[0-9]+ s/ {match($0, / t [0-9]+\.[0-9]+ s/); t = substr($0, RSTART + 3, RLENGTH - 5)} /Unresolved import stub called/ {match($0, /symbol=[^ ]*/); print "t~" t " " substr($0, RSTART, RLENGTH)}' "$P" | sort | uniq -c | sort -k2 | head -60
echo "== fz439 ZERO and dm439 lines"; grep -a "tag fz439): ZERO|bc5 ajm: .*DMC" "$P" | head -20 | cut -c1-220
echo "== GPU fault / timeout"; grep -a -c 'GPU FAULT' "$P"; grep -a -i 'amdgpu.*\(timeout\|reset\)' $O/klog.txt | head -4
