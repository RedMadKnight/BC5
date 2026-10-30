#!/usr/bin/env bash
# BC5 exp 0381: test build 2 from the laptop. Each step runs only if the one before passed, and this script writes no outcome
# line: the box scripts do, after their guards. On a box slot and the maintainer's go, after Codex's review.
#   tb2run0381.sh build <out-dir>       the tree goes across, then guard, claim, build
#   tb2run0381.sh smoke <tag> <out-dir> the kernel stream, the smoke; the cap stops it at 125 s, the laptop's backstop at 140 s
# PC_REMOTE: runs a shell line on the box (default: ssh bc250); the dry run sets a stand-in.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); TOP=$(git -C "$HERE" rev-parse --show-toplevel)
REMOTE=${PC_REMOTE:-ssh bc250}
BASE=${TB2_MAIN:-d6fa368}; NP=${TB2_NP:-4968372}; E=experiments/0381-second-title-non-f403-hangs
PATCHFILE=backend/kytyplus-patches/0001-bc5-lle-agc.patch
BSSH="timeout 20 ssh -o ConnectTimeout=10 bc250"
case "${1:-}" in
build)
    OUT=$2
    X=$(mktemp -d); trap 'rm -rf "$X"' EXIT
    git -C "$TOP" -c core.autocrlf=false archive "$BASE" backend | tar -xf - -C "$X" || { echo "no such tree: nothing run"; exit 3; }
    git -C "$TOP" -c core.autocrlf=false archive HEAD "$E" | tar -xf - -C "$X" || { echo "no scripts: nothing run"; exit 3; }
    git -C "$TOP" show "$NP:$PATCHFILE" > "$X/patch0001-np.patch" || { echo "no patch: nothing run"; exit 3; }
    [ -f "$X/$E/build0381tb2.sh" ] && [ -f "$X/$E/boxcap0381.sh" ] && [ -f "$X/$E/mkpatch0381.py" ] && [ -f "$X/$E/pins0381tb2.env" ] || { echo "the scripts are not in this commit: nothing run"; exit 3; }
    echo "main $(git -C "$TOP" rev-parse "$BASE"), backend $(git -C "$TOP" rev-parse "$BASE:backend"), np $(git -C "$TOP" rev-parse "$NP"), patch $(md5sum < "$X/patch0001-np.patch" | cut -d' ' -f1), scripts $(git -C "$TOP" rev-parse HEAD)"
    CLAIM='W=$HOME/bc5-work; T="top exp 0381 | test build 2"
guard() { pgrep "^kyty_emulator" > /dev/null && { echo "GUARD: an emulator runs; lock: $(cat $W/BOX-LOCK)"; exit 3; }; [ -s $W/BOX-LOCK ] && { echo "GUARD: lock: $(cat $W/BOX-LOCK)"; exit 4; }; return 0; }
guard
[ -e $W/exp0381/in-tb2 ] && mv $W/exp0381/in-tb2 $W/exp0381/in-tb2-before-$(date +%Y%m%d-%H%M%S)
mkdir -p $W/exp0381/in-tb2 && tar -xf - -C $W/exp0381/in-tb2 || { echo "extract failed"; exit 5; }
guard
echo "$T private build, CPU only | $(date "+%F %T")" > $W/BOX-LOCK
echo "$T claim | $(date "+%F %T")" >> $W/BOX-QUEUE
echo claimed'
    tar -cf - -C "$X" backend experiments patch0001-np.patch | $REMOTE "$CLAIM"
    rcs=("${PIPESTATUS[@]}")
    [ "${rcs[0]}" = 0 ] && [ "${rcs[1]}" = 0 ] || { echo "not claimed: nothing run, nothing recorded"; exit 3; }
    timeout ${PC_TIMEOUT:-900} $REMOTE "bash \$HOME/bc5-work/exp0381/in-tb2/$E/build0381tb2.sh"
    rc=$?
    echo "build rc $rc"
    exit $rc
    ;;
smoke)
    TAG=$2; OUT=$3; K=$OUT/kern-$TAG.txt
    ssh bc250 'timeout 240 journalctl -k -f -n 0 -o short-precise' > "$K" 2>&1 &
    KP=$!
    ssh bc250 'bash -s' -- "$TAG" < "$HERE/start0381tb2.sh" > "$OUT/start-$TAG.txt" 2>&1 &
    SP=$!
    why=""
    for _ in $(seq 1 80); do
        sleep 3
        kill -0 $SP 2> /dev/null || { why="launcher ended"; break; }
        grep -q 'ring gfx_0.0.0 timeout' "$K" && { why="gfx timeout"; break; }
        e=$($BSSH 'P=$(pgrep -x kyty_emulator | head -1); [ -n "$P" ] && ps -o etimes= -p $P')
        [ -n "$e" ] && [ "$e" -ge 140 ] && { why="the laptop backstop at 140 s: the cap did NOT stop it"; break; }
    done
    echo "$TAG stop reason: ${why:-loop ended}"
    if [ "$why" != "launcher ended" ]; then
        for _ in 1 2 3 4 5; do
            $BSSH 'P=$(pgrep -x kyty_emulator | head -1); [ -z "$P" ] && { echo "no emulator"; exit 0; }; readlink /proc/$P/exe | grep -q exp0381/tb2/bin/kyty_emulator || { echo "not our emulator"; exit 5; }; echo "etimes $(ps -o etimes= -p $P)"; kill -TERM $P' && break
            sleep 3
        done
    fi
    wait $SP
    cat "$OUT/start-$TAG.txt"
    kill $KP 2> /dev/null
    $BSSH 'pgrep -f "^timeout 240 journalctl -k" | xargs -r kill'
    echo "faults $(grep -c 'in page starting' "$K"); timeouts $(grep -c 'ring gfx_0.0.0 timeout' "$K"); resets ok $(grep -c 'reset succeeded' "$K")"
    $BSSH 'TB=$HOME/bc5-work/exp0381/tb2; G=$(ls -dt $HOME/bc5-data/captures/play-* | head -1); echo "$G"; cut -c1-120 $TB/raw/'"$TAG"'-start.txt; L=$(ls -t $TB/play/play-*.log | head -1); grep -a -m1 "^== exp 0381" "$L" | cut -c1-170; grep -a "fps counter" "$L" | tail -1 | cut -c1-90; echo "restore lines $(grep -a -c "acb state restore" "$G/gc/direct.log"), zero skip lines $(grep -a -c "^zero skip" "$G/gc/direct.log"), ib-timeout files $(ls $G/gc | grep -c ib-timeout)"; grep -a -n -i -E "crash|exception|TIMEOUT" "$L" | head -5 | cut -c1-120'
    ;;
*)
    echo "usage: tb2run0381.sh build <out-dir> | smoke <tag> <out-dir>"; exit 2 ;;
esac
