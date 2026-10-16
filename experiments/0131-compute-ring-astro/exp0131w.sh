#!/usr/bin/env bash
# Experiment 0131, water: ASTRO BOT into the Sky Garden water as run 410 (input318.cmd), 200 s, with or
# without the compute ring; job timestamps from 140 to 155 s. Maintainer present, hang watcher on.
# Usage: exp0131w.sh <run> <label> [ENV=VALUE ...]
cd ~/bc5-work || exit 1
R=$1; LABEL=$2; shift 2
EXTRA=""
for kv in "$@"; do EXTRA="$EXTRA $kv"; done
sed -e "s/^# BC5 run 410 (unattended).*/# BC5 run $R (ASTRO BOT into the water, $LABEL; experiment 0131)/" \
    -e "s/_SaveData-test410/_SaveData-test$R/" \
    -e "s|^exec ~/bc5-work/lle-cycle.sh 150 1|export BC5_DIRECT_JOB_TS=140:155$EXTRA\nexec ~/bc5-work/lle-cycle.sh 200 1|" run410.sh > run$R.sh
chmod +x run$R.sh
grep -q "lle-cycle.sh 200" run$R.sh || { echo "template mismatch"; exit 1; }
[ -d _SaveData-test410 ] && rm -rf _SaveData-test$R && cp -a _SaveData-test410 _SaveData-test$R
sync
(nohup sudo -n /usr/local/bin/bc5-gpu-hang-watch > /dev/null 2>&1 &)
sleep $((61 - $(date +%S | sed "s/^0//")))
pkill -9 -x steam 2>/dev/null
distrobox enter ubuntu -- fusermount3 -uz "${BC5_TITLE_MNT:?the title mountpoint under ~/bc5-data/mnt}" 2>/dev/null
t0=$(date "+%Y-%m-%d %H:%M:%S")
for t in 100 140 170; do (SHOTS=0131 ./shot.sh water$R-$t $t > /dev/null 2>&1 &); done
distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$R.sh > run$R.out 2>&1
sync
c=$(ls -td ~/bc5-data/captures/kytyplus-* | head -1); d=$c/gc/direct.log
printf "run %s (%s) capture %s timeouts=%s faults=%s given-up=%s cycles=%s\n" "$R" "$LABEL" "$(basename $c)" "$(grep -c TIMEOUT $d)" \
  "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")" "$(grep -c "GIVEN UP" $d)" "$(grep -c CYCLE $d)"
for w in "60 100" "100 140" "140 170" "170 200"; do set -- $w; printf "  t%s-%s %s\n" $1 $2 "$(python3 frameprof.py $d $1 $2 | head -1 | grep -o "fps [0-9.]*")"; done
grep "frame profile" $d | awk -F"game thread inside the host " '{split($2,a," "); s+=a[1]; n++} END{printf "  game thread inside the host: mean %.2f ms\n", s/n}'
grep -E "pieces full:" $d | tail -1
python3 jtrings.py $d 2>/dev/null | head -4
journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -iE "amdgpu.*(timeout|reset|fault)" | head -5
