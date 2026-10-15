#!/usr/bin/env bash
# GPU clock test (maintainer's governor range): the second title's start screen (run A, run517.sh
# settings) and ASTRO BOT 70 s (run B), with GPU/CPU temperature and the GPU clock sampled every
# second. Usage: octest.sh <run A> <run B> <label>
cd ~/bc5-work || exit 1
A=$1; B=$2; LABEL=$3
sample() { # <out> <seconds>
  local out=$1 n=$2
  for _ in $(seq 1 "$n"); do
    printf "%s edge %s tctl %s sclk %s\n" "$(date +%T)" \
      "$(sensors 2>/dev/null | awk '/^edge:/{print $2}')" "$(sensors 2>/dev/null | awk '/^Tctl:/{print $2}')" \
      "$(grep '\*' /sys/class/drm/card1/device/pp_dpm_sclk | awk '{print $2}')" >> "$out"
    sleep 1
  done
}
sync
(nohup sudo -n /usr/local/bin/bc5-gpu-hang-watch > /dev/null 2>&1 &)
# run A: start screen
sed -e "s/run 517 (New Game once: play settings with the reflection traversal 0x11d049aa00 skipped (F113-F116); maintainer present, hang watcher on)/run $A (start screen at GPU clock $LABEL; maintainer present, hang watcher on)/" \
    -e "s/test517/test$A/" -e "s/game.pkg 240 --fullscreen/game.pkg 200 --fullscreen/" run517.sh > run$A.sh
chmod +x run$A.sh
sleep $((61 - $(date +%S | sed "s/^0//")))
pkill -9 -x steam 2>/dev/null
t0=$(date "+%Y-%m-%d %H:%M:%S")
rm -f oc-$A.txt; sample oc-$A.txt 215 & SP=$!
distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$A.sh > run$A.out 2>&1
kill $SP 2>/dev/null; sync
c=$(ls -td ~/bc5-data/captures/pkg-* | head -1); d=$c/gc/direct.log
printf "run %s (%s, start screen) timeouts=%s faults=%s: " "$A" "$LABEL" "$(grep -c TIMEOUT $d)" "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")"
for w in "85 100" "130 165" "165 200"; do set -- $w; printf "t%s-%s %s | " $1 $2 "$(python3 frameprof.py $d $1 $2 | head -1 | grep -o "fps [0-9.]*")"; done; echo
awk '{e=$3; sub(/[+°C]/,"",e); gsub(/[^0-9.]/,"",e); t=$5; gsub(/[^0-9.]/,"",t); if (e>me) me=e; if (t>mt) mt=t; f[$7]++} END{printf "  max edge %.1f C, max tctl %.1f C; sclk samples:", me, mt; for (k in f) printf " %s x%d", k, f[k]; print ""}' oc-$A.txt
# run B: ASTRO BOT
sed -e "s/run 426 (ASTRO BOT start, baseline for experiment 0114; maintainer available)/run $B (ASTRO BOT start at GPU clock $LABEL; maintainer present, hang watcher on)/" -e "s/RUN_SECONDS=60/RUN_SECONDS=70/" run426.sh > run$B.sh
chmod +x run$B.sh
sleep $((61 - $(date +%S | sed "s/^0//")))
distrobox enter ubuntu -- fusermount3 -uz ~/bc5-data/mnt/PPSA21567 2>/dev/null
t0=$(date "+%Y-%m-%d %H:%M:%S")
rm -f oc-$B.txt; sample oc-$B.txt 85 & SP=$!
distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$B.sh > run$B.out 2>&1
kill $SP 2>/dev/null; sync
c=$(ls -td ~/bc5-data/captures/kytyplus-* | head -1); d=$c/gc/direct.log
printf "run %s (%s, ASTRO BOT) timeouts=%s faults=%s: t10-30 %s | t40-65 %s\n" "$B" "$LABEL" "$(grep -c TIMEOUT $d)" "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")" \
  "$(python3 frameprof.py $d 10 30 | head -1 | grep -o "fps [0-9.]*")" "$(python3 frameprof.py $d 40 65 | head -1 | grep -o "fps [0-9.]*")"
grep "frame profile" $d | awk -F"game thread inside the host " '{split($2,a," "); s+=a[1]; n++} END{printf "  game thread inside the host: mean %.2f ms\n", s/n}'
awk '{e=$3; gsub(/[^0-9.]/,"",e); t=$5; gsub(/[^0-9.]/,"",t); if (e>me) me=e; if (t>mt) mt=t; f[$7]++} END{printf "  max edge %.1f C, max tctl %.1f C; sclk samples:", me, mt; for (k in f) printf " %s x%d", k, f[k]; print ""}' oc-$B.txt
