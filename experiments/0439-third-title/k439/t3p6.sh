#!/usr/bin/env bash
# BC5 exp 0439: the PERFORMANCE run (the top session's GO of 11-22 ~00:20, the maintainer's choice): crosses at 45 and 125 s
# to "Graphics mode", d-pad right ONCE at 135 s (Performance; a second right is Ray Tracing, which hangs), a check at 138 s
# against walk 2's reference shots (~/bc5-data/priv/t3-screens/ref-gm; not Performance -> stop without a confirm), cross
# at 140 s, then a cross every 20 s with shots before and after, bound 600 s, memory every 30 s, the stall stop. The DMC build.
#   t3p6.sh <md5-8 of the private normal build>
set -u
PIN=${1:?md5}
cd "$HOME/bc5-work/exp0439" || exit 1
RT="" # exp 0439 (tag rt439, 11-22 ~17:40): T3P6_ROUTE=1 walks the menus by screen (t3s.sh T3S_ROUTE) instead of fixed times
if [ "${T3P6_ROUTE:-0}" = 1 ]; then
    R=$HOME/bc5-data/priv/t3-screens/ref-route; S=$HOME/bc5-data/priv/t3-screens/t3s-vunset-ponefp-fp2211b-1723
    mkdir -p "$R" && chmod 700 "$R" || exit 1
    for x in difficulty:t050s experience:t130s loading:t040s; do [ -f "$R/${x%%:*}.png" ] || cp "$S/${x#*:}.png" "$R/${x%%:*}.png" || exit 1; done
    [ -f "$R/graphics.png" ] || cp "$HOME/bc5-data/priv/t3-screens/ref-gm/quality.png" "$R/graphics.png" || exit 1
    RT=${T3P6_RT:-"wait45 cross need=difficulty cross need=experience cross need=graphics right check cross play"}
fi
T3S_ROUTE="$RT" T3S_SCREEN_REFS=$HOME/bc5-data/priv/t3-screens/ref-route T3S_TAG=-p${T3P6_SUFFIX:-} T3S_NO_UMR=${T3S_NO_UMR:-0} T3S_BOUND=${T3P6_BOUND:-600} T3S_STALL_STOP=${T3P6_STALL_STOP:-1} T3S_REF_DIR=$HOME/bc5-data/priv/t3-screens/ref-gm T3S_WANT=performance T3S_PRESSES="45 125 135:right 138:check 140:xs 160:xs 180:xs 200:xs 220:xs 240:xs 260:xs 280:xs 300:xs 320:xs 340:xs 360:xs 380:xs 400:xs 420:xs 440:xs 460:xs 480:xs 500:xs 520:xs 540:xs 560:xs 580:xs" T3S_EXTRA="BC5_0439_AUDIO_CATCH=1 BC5_DIRECT_FLAT_APERTURE=${T3P6_FLAT:-1}${T3P6_MORE:+ $T3P6_MORE}" bash k439/t3s.sh "$PIN" unset "" script 2>&1 | tail -16
O=runs/t3s-vunset-p${T3P6_SUFFIX:-}; L=$O/play-last.log
echo "== kernel $(uname -r), $(rpm -q mesa-vulkan-drivers libdrm | paste -sd' '), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
echo "== flat aperture"; grep -a "flat aperture" $L | cut -c1-220 | head -20; J0=$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log; grep -a -c "flat aperture" "$J0"; grep -a "flat aperture" "$J0" | cut -c1-220 | head -12
echo "== presses"; cat $O.keys
echo "== memory"; cat $O.mem
echo "== stall"; cat $O/stall/when.txt 2> /dev/null || echo none
echo "== DMC and ZERO lines"; grep -a 'bc5 ajm: .*DMC\|tag fz439): ZERO' $L | head -12 | cut -c1-220
echo "== rate per 30 s"; J=$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log
grep -a -o "frame profile: t [0-9.]* s" "$J" | awk '{b = int($4 / 30); n[b]++; if (b > m) m = b} END {for (b = 0; b <= m; b++) printf "%d-%ds %.1f/s\n", b * 30, b * 30 + 30, n[b] / 30}'
echo "== stub calls"; grep -a -c "Unresolved import stub called" $L
echo "== fault"; grep -a "GPU FAULT" $L | head -2 | cut -c1-220
echo "== shots"; ls -d ~/bc5-data/priv/t3-screens/t3s-vunset-p${T3P6_SUFFIX:-}-[0-9]* | tail -1
