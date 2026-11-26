#!/usr/bin/env bash
# BC5 exp 0381: test build 2 from the laptop. Each step runs only if the one before passed, and this script writes no outcome
# line: the box scripts do, under the lock. Run on a box slot from the top session.
# One token names the series in <out-dir>/token, and one exact BOX-LOCK line goes from the claim to the release (lock0381tb2.inc).
#   tb2run0381.sh all <tag> <out-dir> [pins]    the whole cycle: pin read, build, snapshot, smoke; on a stop it gives back only its own line
#   tb2run0381.sh pins <out-dir> <pins file>    the pin read, then <out-dir>/pins-read.env: the file with its FILL pins from the box
#   tb2run0381.sh build <out-dir> [pins file]   claim first, then the tree goes across, then the build; default pins0381tb2.env (the
#                                               fallback), pins0381tb2r.env on the rebuilt shared base, with TB2_MAIN and TB2_NP set
#   tb2run0381.sh snapshot <out-dir>            the named save snapshot, under the series' line
#   tb2run0381.sh smoke <tag> <out-dir> the kernel stream, the smoke; the cap stops it at 125 s, the laptop's backstop at 140 s
#   tb2run0381.sh release <out-dir>             gives back the series' exact line, if it is still there
#   tb2run0381.sh read <out-dir>                the pin read, under its own claim and release
#   tb2run0381.sh recover <out-dir>             rollback, renames only: recover0381tb2.sh
#   tb2run0381.sh again <tag> <out-dir>         a second smoke with no rebuild: again0381tb2.sh, the smoke, the release
# PC_REMOTE: runs a shell line on the box (default: ssh bc250); the dry run sets a stand-in.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); TOP=$(git -C "$HERE" rev-parse --show-toplevel)
REMOTE=${PC_REMOTE:-ssh bc250}
BASE=${TB2_MAIN:-d6fa368}; NP=${TB2_NP:-4968372}; E=experiments/0381-second-title-non-f403-hangs
PATCHFILE=backend/kytyplus-patches/0001-bc5-lle-agc.patch
BSSH="timeout 20 ssh -o ConnectTimeout=10 bc250"
# The kernel's lines that stop the smoke, the first one seen, on any ring.
KSTOP='page fault|in page starting|ring [^ ]* timeout|GPU reset'
newtoken() { mkdir -p "$1" && echo "$(date +%Y%m%d-%H%M%S)-$$-$RANDOM" > "$1/token"; }
token() { [ -s "$1/token" ] || { echo "no token in $1: nothing run"; exit 3; }; cat "$1/token"; }
# A step sent on stdin: its helpers from this commit first, then the step, so nothing on the box has to be there yet.
sendstep() { # <token> <file>...
    local t=$1; shift
    { echo 'set -u; export LC_ALL=C'; echo "TB2_TOKEN=$t"; echo 'W=${TB2_ROOT:-$HOME}/bc5-work'; for f in "$@"; do git -C "$TOP" show "HEAD:$E/$f" || exit 3; done; } | $REMOTE 'bash -s'
}
case "${1:-}" in
all)
    TAG=$2; OUT=$3; PINS=${4:-pins0381tb2.env}
    bash "$0" pins "$OUT" "$PINS" || exit $?
    TB2_PINS_LOCAL=$OUT/pins-read.env bash "$0" build "$OUT" "$PINS" || exit $?
    rc=0
    bash "$0" snapshot "$OUT" || rc=$?
    [ "$rc" = 0 ] && { bash "$0" smoke "$TAG" "$OUT" || rc=$?; }
    # A release that did not finish is a result of its own: the line may still be there.
    bash "$0" release "$OUT" || { echo "the release did not finish: read the lock"; [ "$rc" != 0 ] || rc=6; }
    echo "transaction rc $rc"
    exit $rc
    ;;
pins)
    OUT=$2; PINS=$3
    bash "$0" read "$OUT" > "$OUT/read.txt" 2>&1 || { echo "the pin read stopped: nothing built"; cat "$OUT/read.txt"; exit 3; }
    pin() { awk -v f="$1" '{ sub(/^\*/, "", $2) } $2 == f { print substr($1, 1, 8) }' "$OUT/read.txt"; }
    PP=$(pin bc5-work/play-pkg.sh); LC=$(pin src/KytyPlus/src/libs/libC.cpp)
    printf '%s\n%s\n' "$PP" "$LC" | grep -cxE '[0-9a-f]{8}' | grep -qx 2 || { echo "the pin read gave no md5s: nothing built"; cat "$OUT/read.txt"; exit 3; }
    git -C "$TOP" show "HEAD:$E/$PINS" > "$OUT/pins-base.env" || { echo "no pins file in this commit: nothing built"; exit 3; }
    sed -e "s/^PIN_PLAY_PKG=FILL$/PIN_PLAY_PKG=$PP/" -e "s/^PIN_LIBC=FILL$/PIN_LIBC=$LC/" "$OUT/pins-base.env" > "$OUT/pins-read.env" || exit 3
    echo "pins from the box: play-pkg.sh $PP, libC.cpp $LC"
    ;;
build)
    OUT=$2; PINS=${3:-pins0381tb2.env}
    newtoken "$OUT" || { echo "no token: nothing run"; exit 3; }
    TOKEN=$(token "$OUT")
    X=$(mktemp -d); trap 'rm -rf "$X"' EXIT
    git -C "$TOP" -c core.autocrlf=false archive "$BASE" backend | tar -xf - -C "$X" || { echo "no such tree: nothing run"; exit 3; }
    git -C "$TOP" -c core.autocrlf=false archive HEAD "$E" | tar -xf - -C "$X" || { echo "no scripts: nothing run"; exit 3; }
    git -C "$TOP" show "$NP:$PATCHFILE" > "$X/patch0001-np.patch" || { echo "no patch: nothing run"; exit 3; }
    [ -f "$X/$E/build0381tb2.sh" ] && [ -f "$X/$E/boxcap0381.sh" ] && [ -f "$X/$E/mkpatch0381.py" ] && [ -f "$X/$E/lock0381tb2.inc" ] && [ -f "$X/$E/$PINS" ] || { echo "the scripts are not in this commit: nothing run"; exit 3; }
    [ -z "${TB2_PINS_LOCAL:-}" ] || cp "$TB2_PINS_LOCAL" "$X/$E/$PINS" || { echo "no pins file: nothing run"; exit 3; }
    if [ -z "${TB2_PINS_ABS:-}" ] && grep -q '=FILL$' "$X/$E/$PINS"; then echo "$PINS is not filled in: nothing run"; exit 3; fi
    echo "main $(git -C "$TOP" rev-parse "$BASE"), backend $(git -C "$TOP" rev-parse "$BASE:backend"), np $(git -C "$TOP" rev-parse "$NP"), patch $(md5sum < "$X/patch0001-np.patch" | cut -d' ' -f1), scripts $(git -C "$TOP" rev-parse HEAD)"
    # The claim comes first: nothing on the box moves before the line is ours, and it is checked again before each write.
    CLAIM="TB2_TOKEN=$TOKEN; W=\${TB2_ROOT:-\$HOME}/bc5-work
$(cat "$X/$E/lock0381tb2.inc")"'
guard() { pgrep "^kyty_emulator" > /dev/null && { echo "GUARD: an emulator runs; lock: $(cat "$TB2_LOCK")"; exit 3; }; return 0; }
trap tb2_held_release EXIT
guard
tb2_hook before-claim
tb2_claim
tb2_own
guard
tb2_hook after-claim
tb2_own
[ -e "$W/exp0381/in-tb2" ] && { mv -T -n "$W/exp0381/in-tb2" "$W/exp0381/in-tb2-before-$(date +%Y%m%d-%H%M%S)" || exit 5; }
tb2_hook before-extract
tb2_own
mkdir -p "$W/exp0381/in-tb2" && tar -xf - -C "$W/exp0381/in-tb2" || { echo "extract failed"; exit 5; }
tb2_own
tb2_queue "$TB2_LINE: private build, CPU only | $(date "+%F %T")"
TB2_HELD=0
echo claimed'
    tar -cf - -C "$X" backend experiments patch0001-np.patch | $REMOTE "$CLAIM"
    rcs=("${PIPESTATUS[@]}")
    [ "${rcs[0]}" = 0 ] && [ "${rcs[1]}" = 0 ] || { echo "not claimed: nothing run, nothing recorded"; exit 3; }
    BOXIN='${TB2_ROOT:-$HOME}/bc5-work/exp0381/in-tb2/'$E
    timeout ${PC_TIMEOUT:-900} $REMOTE "TB2_TOKEN=$TOKEN TB2_PINS=${TB2_PINS_ABS:-$BOXIN/$PINS} bash $BOXIN/build0381tb2.sh"
    rc=$?
    echo "build rc $rc"
    exit $rc
    ;;
snapshot)
    OUT=$2; TOKEN=$(token "$OUT") || exit 3
    timeout ${PC_SNAP_TIMEOUT:-300} $REMOTE "bash -s -- $TOKEN" < "$HERE/snapshot0381tb2.sh"
    ;;
release)
    OUT=$2; TOKEN=$(token "$OUT") || exit 3
    printf '%s\n' 'tb2_queue_q "$TB2_LINE: released | $(date "+%F %T")" && tb2_release || echo "TB2: nothing to release: the line is not there"' > "$OUT/release.step"
    { echo "TB2_TOKEN=$TOKEN; W=\${TB2_ROOT:-\$HOME}/bc5-work"; cat "$HERE/lock0381tb2.inc" "$OUT/release.step"; } | timeout 60 $REMOTE 'bash -s'
    ;;
read)
    OUT=$2; newtoken "$OUT" || exit 3
    sendstep "$(token "$OUT")" lock0381tb2.inc read0381tb2.sh
    ;;
again)
    TAG=$2; OUT=$3
    newtoken "$OUT" || exit 3
    sendstep "$(token "$OUT")" lock0381tb2.inc again0381tb2.sh || { echo "not claimed: nothing run"; exit 3; }
    rc=0
    bash "$0" smoke "$TAG" "$OUT" || rc=$?
    bash "$0" release "$OUT" || { echo "the release did not finish: read the lock"; [ "$rc" != 0 ] || rc=6; }
    echo "transaction rc $rc"
    exit $rc
    ;;
recover)
    OUT=$2; TOKEN=$(token "$OUT") || exit 3
    sendstep "$TOKEN" pathcheck0381tb2.inc lock0381tb2.inc recover0381tb2.sh
    ;;
smoke)
    TAG=$2; OUT=$3; K=$OUT/kern-$TAG.txt; TOKEN=$(token "$OUT") || exit 3
    ssh bc250 'timeout 240 journalctl -k -f -n 0 -o short-precise' > "$K" 2>&1 &
    KP=$!
    ssh bc250 'bash -s' -- "$TAG" "$TOKEN" < "$HERE/start0381tb2.sh" > "$OUT/start-$TAG.txt" 2>&1 &
    SP=$!
    why=""
    for _ in $(seq 1 80); do
        sleep 3
        kill -0 $SP 2> /dev/null || { why="launcher ended"; break; }
        grep -qE "$KSTOP" "$K" && { why="kernel line: $(grep -m1 -E "$KSTOP" "$K" | cut -c1-120)"; break; }
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
    src=$?
    [ "$src" != 0 ] || [ "$why" = "launcher ended" ] || src=8
    cat "$OUT/start-$TAG.txt"
    kill $KP 2> /dev/null
    $BSSH 'pgrep -f "^timeout 240 journalctl -k" | xargs -r kill'
    echo "faults $(grep -c 'in page starting' "$K"); timeouts $(grep -cE 'ring [^ ]* timeout' "$K"); resets ok $(grep -c 'reset succeeded' "$K")"
    $BSSH 'TB=$HOME/bc5-work/exp0381/tb2; G=$(ls -dt $HOME/bc5-data/captures/play-* | head -1); echo "$G"; cut -c1-120 $TB/raw/'"$TAG"'-start.txt; L=$(ls -t $TB/play/play-*.log | head -1); grep -a -m1 "^== exp 0381" "$L" | cut -c1-170; grep -a "fps counter" "$L" | tail -1 | cut -c1-90; echo "restore lines $(grep -a -c "acb state restore" "$G/gc/direct.log"), zero skip lines $(grep -a -c "^zero skip" "$G/gc/direct.log"), ib-timeout files $(ls $G/gc | grep -c ib-timeout)"; grep -a -n -i -E "crash|exception|TIMEOUT" "$L" | head -5 | cut -c1-120' || echo "the report was not read: a failed read shows nothing, not zero"
    exit $src
    ;;
*)
    echo "usage: tb2run0381.sh all <tag> <out-dir> [pins] | pins <out-dir> <pins> | build <out-dir> [pins] | snapshot <out-dir> | smoke <tag> <out-dir> | release <out-dir> | read <out-dir> | recover <out-dir>"; exit 2 ;;
esac
