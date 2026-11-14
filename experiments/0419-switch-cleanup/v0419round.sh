#!/usr/bin/env bash
# BC5 exp 0419, build V: the round's driver, run from the laptop in the slot the top session gives. Stages, in order:
#   v0419round.sh pad                 FIRST: is the DualSense there (a joystick device and its ALSA card in PipeWire)?
#                                     The software replug at the end needs it; this says so now, not after the run.
#   v0419round.sh build [step ...]    sends the kit and runs p3build0419.sh on the box (FOLD=0 in the environment
#                                     leaves the library folds out; steps: touchfn liveids, or none)
#   v0419round.sh accept              the private acceptance as for U (chk0419v.sh on the box, detached; prints its
#                                     end lines when it is over, about 25 minutes)
#   v0419round.sh replug <tag>        pins the private normal build and runs ONE software replug (go0391.sh, pulls)
#   v0419round.sh words               the binaries' md5s and word lists (strings) against words-build-V.txt
# Every stage checks "no emulator" and takes its own lock line on the box through the scripts it runs.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
RP=$HERE/../0413-np-session-v2-shared/integration/replug
box() { ssh -o ConnectTimeout=10 bc250 "$@"; }
case "${1:-}" in
pad)
    box 'export XDG_RUNTIME_DIR=/run/user/$(id -u); j=$(ls /dev/input/by-id/ 2> /dev/null | grep -c -- "-event-joystick"); r=$(pw-dump 2> /dev/null | python3 ~/bc5-work/exp0413r/s/streams0391.py device 2> /dev/null); set -- $r; if [ "$j" -ge 1 ] && [ -n "${1:-}" ] && [ "${2:-?}" != "?" ]; then echo "PAD OK: $j joystick device(s); the DualSense ALSA card is in PipeWire (device ${1}, profile ${2})"; else echo "NO PAD: joystick devices $j, DualSense ALSA card in PipeWire: ${1:-none}. The software replug cannot run: switch the DualSense on (cable or the PS button) and run this stage again BEFORE the build."; exit 3; fi'
    ;;
build)
    shift
    box 'pgrep "^kyty_emulator" > /dev/null && { echo "an emulator runs"; exit 1; }; mkdir -p ~/bc5-work/exp0419/p3' || exit 1
    scp -q "$HERE/mkfold0419.py" "$HERE/mkv0419.py" "$HERE/ed0419g.py" "$HERE/p3build0419.sh" "$HERE/fold-levels.txt" "$HERE/chk0419v.sh" bc250:bc5-work/exp0419/p3/ || exit 1
    scp -q "$HERE/tree-build-U-5b185960.md5" bc250:bc5-work/exp0419/p3/tree24.md5 || exit 1
    box "cd ~/bc5-work/exp0419/p3 && FOLD=${FOLD:-1} bash p3build0419.sh $* 2>&1 | tee p3build.out | cut -c1-260"
    ;;
accept)
    box 'cp ~/bc5-work/exp0419/p3/chk0419v.sh ~/bc5-work/exp0413/n/ && cd ~/bc5-work/exp0413/n && (setsid nohup bash chk0419v.sh > raw/chk0419v.out 2>&1 < /dev/null &); sleep 10; head -2 raw/chk0419v.out | cut -c1-200' || exit 1
    for _ in $(seq 1 400); do
        o=$(box 'tail -2 ~/bc5-work/exp0413/n/raw/chk0419v.out' 2> /dev/null)
        case "$o" in *"chk0419v ended"*) break ;; esac
        sleep 6
    done
    box 'grep -a "PASS\|FAIL\|ended at\|NOT\|all runs\|chk0419v ended\|STOP\|VOID" ~/bc5-work/exp0413/n/raw/chk0419v.out | cut -c1-300'
    ;;
replug)
    tag=${2:?a replug tag not used before, e.g. R12}
    md5=$(box 'md5sum < ~/bc5-work/exp0413/p/build-normal/src/kyty_emulator | cut -c1-8') || exit 1
    cp "$RP/pins0391.env" "$RP/pins0391.env.before-0419v" || exit 1
    printf '%s\n' '# exp 0419, build V: the PRIVATE normal build, the shared launcher 47426d8e.' 'BUILD=$HOME/bc5-work/exp0413/p/build-normal' "NORMAL8=$md5" 'LAUNCHER=47426d8e3aec711a5e95937490e810cf' 'RUN_ENV=e5030475c208c557ac9147f0f8dd2429' > "$RP/pins0391.env"
    (cd "$RP" && bash go0391.sh "$tag" pulls 2>&1 | tail -12 | cut -c1-300)
    cp "$RP/pins0391.env" "$RP/pins0391-V-private.env"; mv "$RP/pins0391.env.before-0419v" "$RP/pins0391.env"
    cat "$RP/raw/$tag-check.txt" 2> /dev/null | cut -c1-400
    ;;
words)
    scp -q "$HERE/words-build-V.txt" bc250:bc5-work/exp0419/p3/ || exit 1
    box 'set -u; W=$HOME/bc5-work; P=$W/exp0413/p; N=$W/exp0413/n; B=$W/exp0419/bin-V; pgrep "^kyty_emulator" > /dev/null && { echo EMU; exit 1; }; [ -s $W/BOX-LOCK ] && { echo LOCKED; exit 1; }; . $N/chainlock0417.inc; chain_claim "exp 0419: copy of build V binaries and their word lists (no emulator; 2 minutes)" 5 > /dev/null || exit 1; trap "chain_release > /dev/null" EXIT; mkdir -p $B/normal $B/lean && cp -p $P/build-normal/src/kyty_emulator $B/normal/ && cp -p $P/build-lean/src/kyty_emulator $B/lean/ && (cd $B && md5sum normal/kyty_emulator lean/kyty_emulator > md5.txt && cat md5.txt); for v in normal lean; do nice -n 19 strings $B/$v/kyty_emulator | grep -x "\(KYTY_\)\?BC5_[A-Z0-9_]*" | LC_ALL=C sort -u > $B/words-$v.txt; echo "$v: of the source list ($(wc -l < $W/exp0419/p3/words-build-V.txt)) missing in the binary: $(LC_ALL=C comm -23 $W/exp0419/p3/words-build-V.txt $B/words-$v.txt | wc -l)"; done'
    ;;
*)
    sed -n '2,13p' "$0"
    ;;
esac
