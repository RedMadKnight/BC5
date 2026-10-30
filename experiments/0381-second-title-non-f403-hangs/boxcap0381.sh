#!/usr/bin/env bash
# BC5 exp 0381: the box-side cap the on-3 incident called for. Started by a start script with setsid, so a dropped ssh
# cannot end it. It waits for the emulator at <exe> to appear, then sends TERM at <cap> seconds of emulator time, and
# KILL if it has not gone 20 s later. It only ever signals a process whose executable is <exe>, and it ends as soon as
# the emulator is gone, or after <wait> s if none appears. The laptop's stop (first gfx timeout, 120 s) stays first;
# this is the backstop, so <cap> is above 120. It logs one line to <log>.
# <exe> is the end of the path ("/exp0381/kyty_emulator"): /home here is a link to /var/home.
# usage: boxcap0381.sh <exe> <cap_s> <log> [wait_s]
EXE=$1; CAP=$2; LOG=$3; WAIT=${4:-60}; TICK=${BOXCAP_TICK:-2}
find_emu() {
    local p
    for p in $(pgrep -x kyty_emulator); do
        case "$(readlink "/proc/$p/exe")" in *"$EXE") echo "$p"; return 0 ;; esac
    done
    return 1
}
waited=0
P=$(find_emu)
while [ -z "$P" ]; do
    [ "$waited" -ge "$WAIT" ] && { echo "$(date '+%F %T') boxcap: no emulator in $WAIT s" >> "$LOG"; exit 0; }
    sleep "$TICK"; waited=$((waited + TICK)); P=$(find_emu)
done
while kill -0 "$P" 2> /dev/null; do
    e=$(ps -o etimes= -p "$P" | tr -d ' ')
    if [ -n "$e" ] && [ "$e" -ge "$CAP" ]; then
        case "$(readlink "/proc/$P/exe")" in *"$EXE") ;; *) exit 0 ;; esac
        echo "$(date '+%F %T') boxcap: TERM to $P at $e s (cap $CAP)" >> "$LOG"
        kill -TERM "$P"
        for _ in $(seq 1 20); do
            kill -0 "$P" 2> /dev/null || exit 0
            sleep 1
        done
        echo "$(date '+%F %T') boxcap: KILL to $P" >> "$LOG"
        kill -KILL "$P"
        exit 0
    fi
    sleep "$TICK"
done
