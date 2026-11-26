#!/usr/bin/env bash
# Passive watch of bc250 for the machine-down question (TCP session, agreed with the box supervisor):
# the kernel log and the current play journal's timeout/fault lines, streamed onto the laptop until
# END (HH:MM, today). Reconnects after a reboot, so the next boot's first lines land too.
# Nothing is written on the box. usage: watch-local.sh <out-dir> [END]
OUT=$1; END=${2:-20:30}
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
left() { echo $(( $(date -d "today $END" +%s) - $(date +%s) )); }
SSH="ssh -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 -o BatchMode=yes bc250"
kern() {
  while [ "$(left)" -gt 0 ]; do
    timeout "$(left)" $SSH 'echo "# $(date "+%F %T") boot $(cat /proc/sys/kernel/random/boot_id) up $(cut -d" " -f1 /proc/uptime) s"; journalctl -k -f -n 0 -o short-precise' >> "$OUT/kernel.txt" 2>&1
    echo "# kernel stream ended $(date '+%F %T') (laptop clock)" >> "$OUT/kernel.txt"
    sleep 15
  done
}
jour() {
  while [ "$(left)" -gt 0 ]; do
    timeout "$(left)" $SSH 'bash -s' < "$HERE/remote-journal.sh" >> "$OUT/journal.txt" 2>&1
    echo "# journal stream ended $(date '+%F %T') (laptop clock)" >> "$OUT/journal.txt"
    sleep 15
  done
}
echo "# watch start $(date '+%F %T'), until $END" | tee -a "$OUT/kernel.txt" >> "$OUT/journal.txt"
kern & jour & wait
echo "watch ended $(date '+%F %T')"
