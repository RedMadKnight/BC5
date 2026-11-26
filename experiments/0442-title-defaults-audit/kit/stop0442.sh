#!/usr/bin/env bash
# BC5 exp 0442: stop one of this experiment's box runs cleanly (the top session, 2026-11-22; lesson of the 20:34 stop).
#   usage (on the box): bash stop0442.sh <unit> [<lock token>]
# 1. systemctl --user stop <unit> (the run's own cgroup: the chain, MangoHud, perf, the samplers).
# 2. kyty_emulator processes left over: TERM, then KILL after 10 s.
# 3. bc5-mount: the title scripts start it inside the ubuntu distrobox, so it lives in the container's cgroup and
#    survives step 1; a leftover makes the next boot check say "busy yes". Every bc5-mount whose mountpoint is under
#    ~/bc5-data/mnt and that serves no emulator any more (step 2 left none) is sent TERM.
# 4. Dead FUSE mounts are visible only in the container's mount namespace ("Transport endpoint is not connected";
#    the host's /proc/mounts does not list them): each mountpoint under ~/bc5-data/mnt that the container lists but
#    cannot read is unmounted there with fusermount -u. Live mounts are left alone.
# 5. The lean session: lean-session.sh restore (idempotent: starts the units it noted, e.g. plasma-plasmashell).
# 6. BOX-LOCK: emptied only when it holds this run's token (given, or not given and the line names exp 0442);
#    a copy goes to BOX-LOCK.stale-<date>. Another session's lock is never touched.
# It prints what it did and ends with the boot check's three facts (busy, dead mounts, lock).
set -u
U=${1:?the unit to stop}; TOK=${2:-}
W=$HOME/bc5-work; MNT=$HOME/bc5-data/mnt
say() { echo "$(date +%T) stop0442: $*"; }
systemctl --user stop "$U" 2> /dev/null && say "unit $U stopped" || say "unit $U was not active"
if pgrep -x kyty_emulator > /dev/null; then
    pkill -TERM -x kyty_emulator; sleep 10
    pgrep -x kyty_emulator > /dev/null && { pkill -KILL -x kyty_emulator; say "kyty_emulator killed (KILL)"; } || say "kyty_emulator ended (TERM)"
fi
for p in $(pgrep -x bc5-mount); do
    a=$(tr '\0' ' ' < "/proc/$p/cmdline" 2> /dev/null)
    case "$a" in *" $MNT/"*) kill -TERM "$p" 2> /dev/null && say "bc5-mount $p ended: $a" ;; *) say "bc5-mount $p left alone (not under $MNT): $a" ;; esac
done
sleep 2
# shellcheck disable=SC2016
distrobox enter ubuntu -- sh -c '
    for m in $(awk -v r="$1/" "index(\$2, r) == 1 {print \$2}" /proc/mounts); do
        if ! ls "$m" > /dev/null 2>&1; then
            fusermount -u "$m" 2> /dev/null || fusermount -uz "$m" 2> /dev/null
            echo "dead mount $m: unmounted (rc $?)"
        fi
    done' _ "$MNT" < /dev/null 2>&1 | while read -r l; do say "$l"; done
[ -f "$W/lean-session.sh" ] && bash "$W/lean-session.sh" restore > /dev/null 2>&1 && say "lean-session restore done"
if [ -s "$W/BOX-LOCK" ]; then
    l=$(cat "$W/BOX-LOCK")
    if { [ -n "$TOK" ] && [[ "$l" == *"token $TOK "* ]]; } || { [ -z "$TOK" ] && [[ "$l" == "exp 0442 "* ]]; }; then
        cp -p "$W/BOX-LOCK" "$W/BOX-LOCK.stale-$(date +%Y%m%d-%H%M)" && : > "$W/BOX-LOCK" && say "lock released (copy kept)"
    else
        say "BOX-LOCK holds another line, left alone: $l"
    fi
fi
busy=$( { pgrep -x kyty_emulator || pgrep -x bc5-mount; } > /dev/null && echo yes || echo no)
dead=$(distrobox enter ubuntu -- sh -c 'n=0; for m in $(awk -v r="$1/" "index(\$2, r) == 1 {print \$2}" /proc/mounts); do ls "$m" > /dev/null 2>&1 || n=$((n+1)); done; echo $n' _ "$MNT" < /dev/null 2> /dev/null)
say "after: busy $busy, dead mounts ${dead:-?}, lock [$(cat "$W/BOX-LOCK" 2> /dev/null)]"
