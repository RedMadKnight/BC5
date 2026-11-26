#!/usr/bin/env bash
# BC5 exp 0421: the laptop's driver for the shared swap (the top session's GO first).
#   r0421.sh kit                 checks "no emulator, no lock", sends the kit to ~/bc5-work/exp0421 (no other write)
#   PIN_OLD=<8 hex> r0421.sh run  runs int0421.sh there, detached, and prints its output when it ends
#   r0421.sh patch               copies the new patch back to the laptop (scratchpad path given as $2)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
box() { ssh -o ConnectTimeout=10 bc250 "$@"; }
case "${1:-}" in
kit)
    box 'pgrep "^kyty_emulator" > /dev/null && { echo "an emulator runs"; exit 1; }; [ -s ~/bc5-work/BOX-LOCK ] && { echo "LOCKED: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }; [ -e ~/bc5-work/exp0421/swap ] && { echo "exp0421/swap exists"; exit 1; }; mkdir -p ~/bc5-work/exp0421' || exit 1
    scp -q "$HERE/mk0421.py" "$HERE/int0421.sh" "$HERE/undo0421.sh" "$HERE/../0419-switch-cleanup/ed0419g.py" bc250:bc5-work/exp0421/ || exit 1
    box 'cd ~/bc5-work/exp0421 && md5sum mk0421.py int0421.sh undo0421.sh ed0419g.py | cut -c1-8,33- && bash -n int0421.sh && bash -n undo0421.sh && echo kit ok'
    ;;
run)
    : "${PIN_OLD:?}"
    box "cd ~/bc5-work/exp0421 && (PIN_OLD=$PIN_OLD setsid nohup bash int0421.sh > int0421.out 2>&1 < /dev/null &); sleep 5; head -3 int0421.out | cut -c1-240" || exit 1
    for _ in $(seq 1 200); do
        o=$(box 'tail -1 ~/bc5-work/exp0421/int0421.out; pgrep -f "bash int042[1].sh" > /dev/null && echo RUNNING' 2> /dev/null)
        case "$o" in *RUNNING*) sleep 10 ;; *) break ;; esac
    done
    box 'cut -c1-300 ~/bc5-work/exp0421/int0421.out'
    ;;
patch)
    out=${2:?a laptop path for the patch}
    scp -q bc250:bc5-work/exp0421/swap/0001-new0421.patch "$out" && md5sum < "$out" | cut -c1-8
    ;;
*)
    sed -n '2,5p' "$0"
    ;;
esac
