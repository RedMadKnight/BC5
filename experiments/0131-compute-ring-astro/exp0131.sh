#!/usr/bin/env bash
# Experiment 0131: ASTRO BOT's start (play settings, 70 s, no input) with or without the compute ring,
# job timestamps from 40 to 55 s. Maintainer present, hang watcher on.
# Usage: exp0131.sh <run> <label> [ENV=VALUE ...]
cd ~/bc5-work || exit 1
R=$1; LABEL=$2; shift 2
EXTRA=""
for kv in "$@"; do EXTRA="$EXTRA $kv"; done
sed -e "s/^# BC5 run 526 (ASTRO BOT start at GPU clock 1850-2150 MHz; maintainer present, hang watcher on)/# BC5 run $R (ASTRO BOT start, $LABEL; experiment 0131)/" \
    -e "s|^exec |export BC5_DIRECT_JOB_TS=40:55$EXTRA\nexec |" run526.sh > run$R.sh
chmod +x run$R.sh
sync
(nohup sudo -n /usr/local/bin/bc5-gpu-hang-watch > /dev/null 2>&1 &)
sleep $((61 - $(date +%S | sed "s/^0//")))
pkill -9 -x steam 2>/dev/null
distrobox enter ubuntu -- fusermount3 -uz "${BC5_TITLE_MNT:?the title mountpoint under ~/bc5-data/mnt}" 2>/dev/null
t0=$(date "+%Y-%m-%d %H:%M:%S")
(SHOTS=0131 ./shot.sh astro$R-60 60 > /dev/null 2>&1 &)
distrobox enter ubuntu -- /home/kjaniszewski/bc5-work/run$R.sh > run$R.out 2>&1
sync
c=$(ls -td ~/bc5-data/captures/kytyplus-* | head -1); d=$c/gc/direct.log
printf "run %s (%s) capture %s timeouts=%s faults=%s given-up=%s\n" "$R" "$LABEL" "$(basename $c)" "$(grep -c TIMEOUT $d)" \
  "$(journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -c "in page starting")" "$(grep -c "GIVEN UP" $d)"
printf "  t10-30 %s | t40-65 %s\n" "$(python3 frameprof.py $d 10 30 | head -1 | grep -o "fps [0-9.]*")" "$(python3 frameprof.py $d 40 65 | head -1 | grep -o "fps [0-9.]*")"
grep "frame profile" $d | awk -F"game thread inside the host " '{split($2,a," "); s+=a[1]; n++} END{printf "  game thread inside the host: mean %.2f ms\n", s/n}'
grep -E "compute ring|stays on the GFX ring|pieces full" $d | tail -3
python3 jtrings.py $d 2>/dev/null | head -4
journalctl _TRANSPORT=kernel --since "$t0" --no-pager | grep -iE "amdgpu.*(timeout|reset|fault)" | head -5
