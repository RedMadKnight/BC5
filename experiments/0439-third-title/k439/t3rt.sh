#!/usr/bin/env bash
# BC5 exp 0439: the Ray Tracing highlight walk with BC5_DIRECT_FLAT_APERTURE=1 (the top session's GO of 11-22 06:25, the direct
# test of F893): crosses at 45 and 125 s to "Graphics mode", d-pad right at 135 s (Performance) and 150 s (Ray Tracing: walk 2
# hung 1.2 s after this highlight without the word), no confirm; shots 2 s after each, every 10 s; bound 240 s; the stall stop.
#   t3rt.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
echo "== kernel $(uname -r), $(rpm -q mesa-vulkan-drivers libdrm 2> /dev/null | tr '\n' ' '), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
T3S_TAG=-rt T3S_BOUND=240 T3S_STALL_STOP=1 T3S_PRESSES="45 125 135:right 150:right" T3S_EXTRA="BC5_0439_AUDIO_CATCH=1 BC5_DIRECT_FLAT_APERTURE=1" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -16
O=runs/t3s-vunset-rt; L=$O/play-last.log
J=$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log
echo "== flat aperture"; grep -a -c "flat aperture" "$J"; grep -a "flat aperture" "$J" | cut -c1-220 | head -12
echo "== presses"; cat $O.keys
echo "== memory"; cat $O.mem
echo "== stall"; cat $O/stall/when.txt 2> /dev/null || echo none
echo "== rate per 30 s"
grep -a -o "frame profile: t [0-9.]* s" "$J" | awk '{b = int($4 / 30); n[b]++; if (b > m) m = b} END {for (b = 0; b <= m; b++) printf "%d-%ds %.1f/s\n", b * 30, b * 30 + 30, n[b] / 30}'
echo "== stub calls"; grep -a -c "Unresolved import stub called" $L
echo "== fault"; grep -a "GPU FAULT" $L | head -2 | cut -c1-220
echo "== aperture bases in wave dumps"; grep -a -h -i "src_private_base\|src_shared_base\|SH_MEM" $O/*umr* $O/*/*umr* 2> /dev/null | sort | uniq -c | head
echo "== shots"; ls -d ~/bc5-data/priv/t3-screens/t3s-vunset-rt-[0-9]* | tail -1
