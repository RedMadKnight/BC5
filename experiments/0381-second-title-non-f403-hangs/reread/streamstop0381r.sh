#!/usr/bin/env bash
# BC5 exp 0381, re-reads: on the box, ends this series' kernel stream and no other. The series' stream wrote its PID and start time
# to a file named after the token; a process is signalled only if both still match and it is that command (LESSONS R38).
# usage: ssh bc250 'bash -s' -- <token> < streamstop0381r.sh   (RR, PROC and KILL point it at stand-ins in the test)
set -u
TOKEN=${1:?token}
RR=${RR:-$HOME/bc5-work/exp0381/reread}; PROC=${PROC:-/proc}; KILL=${KILL:-kill}
F=$RR/stream-$TOKEN.pid
[ -f "$F" ] || { echo "stream: no file of this token"; exit 0; }
read -r P S < "$F"
NOW=$(sed 's/^.*) //' "$PROC/$P/stat" 2> /dev/null | awk '{ print $20 }')
if [ -n "$NOW" ] && [ "$NOW" = "$S" ] && tr '\0' ' ' < "$PROC/$P/cmdline" 2> /dev/null | grep -q '^timeout 7000 journalctl -k '; then
    $KILL "$P" || { echo "stream: $P was not signalled"; exit 1; }
    echo "stream: $P ended"
else
    echo "stream: $P is not ours any more, left alone"
fi
rm -f "$F"
