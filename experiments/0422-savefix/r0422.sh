#!/usr/bin/env bash
# BC5 exp 0422: the laptop's driver (the top session's GO of 2026-11-15).
#   r0422.sh kit                  checks "no emulator", sends the kit to ~/bc5-work/exp0422 (no other write)
#   PIN_OLD=<8 hex> r0422.sh run   streams the kernel log to raw/kern-0422.txt, runs chain0422.sh there detached,
#                                 prints its output when it ends
#   r0422.sh patch <laptop path>  copies the new patch back
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
box() { timeout 60 ssh -o ConnectTimeout=10 bc250 "$@"; }
case "${1:-}" in
kit)
    box 'pgrep "^kyty_emulator" > /dev/null && { echo "an emulator runs"; exit 1; }; [ -e ~/bc5-work/exp0422/swap ] && { echo "exp0422/swap exists"; exit 1; }; mkdir -p ~/bc5-work/exp0422' || exit 1
    scp -q "$HERE/mk0422.py" "$HERE/int0422.sh" "$HERE/undo0422.sh" "$HERE/chk0422.sh" "$HERE/chain0422.sh" "$HERE/../0419-switch-cleanup/ed0419g.py" bc250:bc5-work/exp0422/ || exit 1
    box 'cd ~/bc5-work/exp0422 && md5sum mk0422.py int0422.sh undo0422.sh chk0422.sh chain0422.sh ed0419g.py | cut -c1-8,33- && for f in *.sh; do bash -n $f || exit 1; done && echo kit ok'
    ;;
run)
    : "${PIN_OLD:?}"
    mkdir -p "$HERE/raw"
    (timeout 3600 ssh -o ConnectTimeout=10 bc250 'timeout 3500 journalctl -k -f -n 0 -o short-precise' > "$HERE/raw/kern-0422.txt" 2>&1 &)
    box "cd ~/bc5-work/exp0422 && (PIN_OLD=$PIN_OLD setsid nohup bash chain0422.sh > chain0422.out 2>&1 < /dev/null &); sleep 5; head -4 chain0422.out | cut -c1-240" || exit 1
    for _ in $(seq 1 400); do
        o=$(box 'tail -1 ~/bc5-work/exp0422/chain0422.out; pgrep -f "bash [c]hain0422.sh" > /dev/null && echo RUNNING' 2> /dev/null)
        case "$o" in *RUNNING*) sleep 15 ;; *) [ -n "$o" ] && break; sleep 15 ;; esac
    done
    box 'cut -c1-400 ~/bc5-work/exp0422/chain0422.out'
    ;;
patch)
    out=${2:?a laptop path for the patch}
    scp -q bc250:bc5-work/exp0422/swap/0001-new0422.patch "$out" && md5sum < "$out" | cut -c1-8
    ;;
*)
    sed -n '2,6p' "$0"
    ;;
esac
