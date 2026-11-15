#!/usr/bin/env bash
# BC5 exp 0420: the laptop's driver for the shared swap to W with the games menu. Each stage only on the top's GO,
# after the night series (n15), in this order:
#   round0420w.sh race          (a) the race fix in the shared launcher: install-race0420.sh (dry, conditions, apply)
#   round0420w.sh pad           is the DualSense there (a joystick and its ALSA card in PipeWire)? needed by (b)
#   round0420w.sh replug <tag>  (b) ONE software replug (go0391.sh, pulls) on the private W+menu normal build 10e3ef15
#                               (W changes audio.cpp, controller.cpp, hostInput.cpp, libAudio*.cpp: rule R53/13.11)
#   round0420w.sh kit           sends the swap kit to ~/bc5-work/exp0420/swapW
#   round0420w.sh swapdry       (c, first half) swap0420w.sh dry on the box: every check and diff, nothing changed
#   round0420w.sh swap          (c) swap0420w.sh apply
#   round0420w.sh smoke         (d) smoke0420w.sh: the menu normal and lean, the second title from the list (private saves)
#   round0420w.sh undo          swap0420w.sh undo (everything back from the .before-W copies)
# KIT= the directory with 0001-B.patch, 0001-W-menu.patch and tree-W-menu.md5 (the laptop's replay; default the
# session's scratchpad copy).
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
RP=$HERE/../0413-np-session-v2-shared/integration/replug
KIT=${KIT:-/c/Users/kjani/AppData/Local/Temp/claude/7e70d624f1bff3f5/43cd6eac-dc2c-49c1-b603-e5283be4d569/scratchpad/w420/kit}
box() { ssh -o ConnectTimeout=10 bc250 "$@"; }
noemu() { box 'pgrep "^kyty_emulator" > /dev/null && { echo "an emulator runs"; exit 1; }; [ -s ~/bc5-work/BOX-LOCK ] && { echo "the lock is held: $(cat ~/bc5-work/BOX-LOCK)"; exit 1; }; exit 0'; }
case "${1:-}" in
race)
    noemu || exit 1
    box 'mkdir -p ~/bc5-work/exp0420/race-107e307a' || exit 1
    scp -q "$HERE/fix-lean-race.sh" "$HERE/install-race0420.sh" "$HERE/../0412-memory-guardian/lean-session.sh" bc250:bc5-work/exp0420/race-107e307a/ || exit 1
    box 'cd ~/bc5-work/exp0420/race-107e307a && md5sum fix-lean-race.sh lean-session.sh | cut -c1-8,33- && bash install-race0420.sh 2>&1 | tee install.out | cut -c1-300'
    ;;
pad)
    box 'export XDG_RUNTIME_DIR=/run/user/$(id -u); echo "joysticks: $(ls /dev/input/by-id/ 2> /dev/null | grep -c -- "-event-joystick"); PipeWire: $(pw-dump 2> /dev/null | python3 ~/bc5-work/exp0413r/s/streams0391.py device 2> /dev/null | head -3 | tr "\n" " ")"'
    ;;
replug)
    tag=${2:?a replug tag not used before, e.g. R13}
    noemu || exit 1
    md5=$(box 'md5sum < ~/bc5-work/exp0413/p/build-normal/src/kyty_emulator | cut -c1-8') || exit 1
    [ "$md5" = 10e3ef15 ] || { echo "the private normal build is $md5, not W+menu 10e3ef15: not run"; exit 1; }
    cp "$RP/pins0391.env" "$RP/pins0391.env.before-0420w" || exit 1
    printf '%s\n' '# exp 0420, W + the games menu: the PRIVATE normal build, the shared launcher 47426d8e.' 'BUILD=$HOME/bc5-work/exp0413/p/build-normal' "NORMAL8=$md5" 'LAUNCHER=47426d8e3aec711a5e95937490e810cf' 'RUN_ENV=e5030475c208c557ac9147f0f8dd2429' > "$RP/pins0391.env"
    (cd "$RP" && bash go0391.sh "$tag" pulls 2>&1 | tail -12 | cut -c1-300)
    cp "$RP/pins0391.env" "$RP/pins0391-W-menu-private.env"; mv "$RP/pins0391.env.before-0420w" "$RP/pins0391.env"
    cat "$RP/raw/$tag-check.txt" 2> /dev/null | cut -c1-400
    ;;
kit)
    for f in 0001-B.patch 0001-W-menu.patch tree-W-menu.md5; do [ -f "$KIT/$f" ] || { echo "no $KIT/$f"; exit 1; }; done
    box 'mkdir -p ~/bc5-work/exp0420/swapW' || exit 1
    scp -q "$KIT/0001-B.patch" "$KIT/0001-W-menu.patch" "$KIT/tree-W-menu.md5" "$HERE/swap0420w.sh" "$HERE/smoke0420w.sh" "$HERE/play-any.sh" "$HERE/play-astro.sh" "$HERE/../0412-memory-guardian/lean-session.sh" bc250:bc5-work/exp0420/swapW/ || exit 1
    box 'cd ~/bc5-work/exp0420/swapW && md5sum * | cut -c1-8,33-'
    ;;
swapdry) box 'cd ~/bc5-work/exp0420/swapW && bash swap0420w.sh dry 2>&1 | tee dry.out | cut -c1-300' ;;
swap)
    noemu || exit 1
    box 'cd ~/bc5-work/exp0420/swapW && (setsid nohup bash swap0420w.sh apply > apply.out 2>&1 < /dev/null &); sleep 5; head -3 apply.out | cut -c1-200' || exit 1
    for _ in $(seq 1 300); do
        o=$(box 'tail -2 ~/bc5-work/exp0420/swapW/apply.out' 2> /dev/null)
        case "$o" in *"undo: bash"*|*"STOP"*|*"restored and read back"*|*"INCOMPLETE"*) break ;; esac
        sleep 10
    done
    box 'cut -c1-300 ~/bc5-work/exp0420/swapW/apply.out | grep -v "^ *$" | tail -30'
    ;;
smoke) noemu || exit 1; box 'cd ~/bc5-work/exp0420/swapW && bash smoke0420w.sh all 2>&1 | tee smoke.out | cut -c1-300' ;;
undo) noemu || exit 1; box 'cd ~/bc5-work/exp0420/swapW && bash swap0420w.sh undo 2>&1 | tee undo.out | cut -c1-300' ;;
*) sed -n '2,15p' "$0"; exit 1 ;;
esac
