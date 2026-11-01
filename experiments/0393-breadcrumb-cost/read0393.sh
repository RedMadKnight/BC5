#!/usr/bin/env bash
# BC5 exp 0393: the read before the build and before the series. It only reads; nothing on the box is written.
# usage: ssh bc250 'bash -s' < read0393.sh
export LC_ALL=C LANGUAGE=C
W=$HOME/bc5-work
m() { md5sum < "$1" | cut -d' ' -f1; }
echo "lock [$(cat "$W/BOX-LOCK" 2> /dev/null)]"
tail -n 3 "$W/BOX-QUEUE" 2> /dev/null
pgrep -a '^kyty_emulator' || echo "no emulator"
echo "compression job $(systemctl --user is-active bc5-compress-captures.service)"
systemctl --user list-timers --all --no-pager 2> /dev/null | grep -i compress
echo "disk $(df --output=pcent "$HOME" | tail -1 | tr -dc 0-9) %; kernel $(uname -r); up since $(uptime -s)"
echo "TREE=$(m "$HOME/src/KytyPlus/src/libs/bc5LleAgc.cpp")"
echo "SHARED=$(m "$W/kytyplus-build/src/kyty_emulator")"
echo "LAUNCHER=$(m "$W/play-pkg.sh")"
echo "RUN_ENV=$(m "$W/bc5-run.env")"
echo "ROUTE_SAVES=$(cd "$W/exp0196/saves-before-152617" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16)"
echo "MENU_CMD=$(m "$W/exp0203/o2-continue.cmd")"
echo "INPUT_CFG=$(m "$W/input.cfg")"
echo "LEARNED=$(m "$W/direct-learned-pkg.txt")"
echo "wd entries $(ls -A "$W/exp0330/wd" | wc -l); sampler $(ls "$W/exp0330/sample0330.sh")"
ls -d "$W/exp0393" 2> /dev/null || echo "no exp0393 directory yet"
