#!/usr/bin/env bash
# BC5 exp 0391 on the box: the lock, the run and its cleanup for one software replug run (s6n0391.sh + replug0391.sh)
# on the SHARED normal build. Derived from exp 0390's run0390.sh (dba7e514) by mk0391.py; "0391:" marks what differs:
# the second argument is the replug mode (pulls|late), not a fix switch; the pins are the shared binary (first 8 hex, as
# the top session named it), the launcher and bc5-run.env; the replug script runs beside the S6N run with the same
# token; check0391.py classifies. Called by go0391.sh only.
#   run0391.sh claim <tag> <pulls|late> <deadline epoch>       over stdin; the atomic claim, prints TOK=
#   run0391.sh start <token> <tag> <pulls|late> <deadline>     detaches `run` under its own time limit
#   run0391.sh run <token> <tag> <pulls|late> <deadline>       the run; always ends by releasing its own lock
#   run0391.sh stream <token> <secs>                       the kernel log, until the token's lock is gone
#   run0391.sh release <token>                             over stdin; recovery: stops this token's processes, frees its lock
# Claim as in coordination/d19/d19box.sh: the line appears by a hard link, which cannot replace an existing lock. One
# token per run, no second claimant. Only processes with this token in their environment are ever signalled. Nothing here
# changes shared files; the runs use a private copy of a named snapshot.
set -u
export LC_ALL=C
W=${D19_WORK:-$HOME/bc5-work}
EX=$W/exp0413r; E=$EX/run; R=$E/raw; S=$EX/s; B=${E0391_BUILD:-$W/kytyplus-build}  # integration 2026-11-13: the SHARED normal build again (exp 0413 ran its private one here)
LOCK=$W/BOX-LOCK; QUEUE=$W/BOX-QUEUE
# The deadline is the end of everything. The outer limit ends 90 s before it, hard kill included; the run must leave 150 s
# for its own kill (30), reap (30), check and release. A run needs 420 s of play plus ~90 s of setup and end, so the
# runner is capped at 600 s and a claim needs 840 s to the deadline (0391: SECS 420, exp 0372's P1 length).
SECS=420; RUN_MIN=840; RUN_CAP=600; KEEP=150; OUTER_END=90; REAP_TERM=20; REAP_KILL=10; DISK_MAX=90
HELD=0; LOCKLINE=""; STOPWHY=""; RUNP=""; REPLUGP=""
now() { date +%s; }
die() { STOPWHY=$*; echo "0391 STOP: $*"; exit 1; }
emu_pids() { pgrep '^kyty_emulator'; return 0; }
work_pids() { pgrep -x 'ninja|cmake'; return 0; }
compress_state() { systemctl --user is-active bc5-compress-captures.service; }
disk_pct() { df --output=pcent "$HOME" | tail -1 | tr -dc 0-9; }
session() { setsid "$@"; }
kstream() { exec timeout "$1" journalctl -k -f -n 0 -o short-precise; }
clear_lock() { : > "$LOCK"; }
# Every process with this token in its environment. /proc only, as d19box.sh's own_pids.
own_pids() {
    local p n
    for p in /proc/[0-9]*; do
        n=${p#/proc/}
        [ "$n" != "$$" ] || continue
        grep -qzxF "D19_OWNER=$TOK" "$p/environ" 2> /dev/null && echo "$n"
    done
    return 0
}
hook() { :; }
# Stand-ins load only from a d19-test- path; they replace the functions above, nothing else.
case "${D19_FAKE:-}" in *d19-test-*) . "$D19_FAKE" ;; esac

m() { md5sum < "$1" | cut -d' ' -f1; }
own_q() { [ -n "$LOCKLINE" ] && [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }
own() { own_q || die "the lock is not ours: $(cat "$LOCK" 2> /dev/null)"; }
queue() { { printf '%s\n' "$1" >> "$QUEUE"; } 2> /dev/null && grep -qxF -- "$1" "$QUEUE" 2> /dev/null; }
# Every directory this experiment writes, checked before the first write, on links and on where it really is. The wd's
# own read-only asset links are not write targets and are not here.
write_roots() { echo "$EX" "$E" "$R" "$S" "$E/wd" "$E/wd/_SaveData" "$E/wd/_SaveData-pkg-play"; }
paths_safe() {
    local p rw
    rw=$(readlink -f "$W") && [ -d "$rw" ] || die "$W is not a directory"
    for p in $(write_roots); do
        [ ! -L "$p" ] || die "$p is a link"
        if [ -e "$p" ]; then
            [ -d "$p" ] || die "$p is not a directory"
            [ "$(readlink -f "$p")" = "$rw${p#"$W"}" ] || die "$p is really elsewhere"
        fi
    done
}
free_box() {
    [ -z "$(emu_pids)" ] || die "an emulator runs"
    [ -z "$(work_pids)" ] || die "a build runs"
    [ "$(compress_state)" = inactive ] || die "the compression job runs"
    [ "$(disk_pct)" -lt "$DISK_MAX" ] || die "the disk is at $(disk_pct) %"
}
# d19box.sh's claim.
claim_inner() {
    local t=$1 a=$2
    printf '%s\n' "$LOCKLINE" > "$t" 2> /dev/null || { WHY="cannot write $t"; return 1; }
    if [ -e "$LOCK" ] || [ -L "$LOCK" ]; then
        if [ -L "$LOCK" ] || [ ! -f "$LOCK" ]; then WHY="$LOCK is not a plain file"; return 1; fi
        if [ -s "$LOCK" ]; then WHY="foreign lock: $(cat "$LOCK")"; return 1; fi
        mv -T "$LOCK" "$a" 2> /dev/null || { WHY="the lock moved under us"; return 1; }
        hook after-aside
    fi
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        WHY="lost the claim to: $(cat "$LOCK" 2> /dev/null)"
        [ -s "$a" ] || rm -f "$a"
        return 1
    fi
    if [ -s "$a" ]; then
        WHY="a foreign lock arrived during the claim: $(cat "$a")"
        mv -fT "$a" "$LOCK" 2> /dev/null || WHY="$WHY; restore it from $a"
        return 1
    fi
    rm -f "$a"
    [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ] || { WHY="the lock does not read back as ours"; return 1; }
}
claim() {
    local c=$LOCK.d19-claim t=$LOCK.0391-$$.new a=$LOCK.0391-$$.aside WHY=""
    mkdir "$c" 2> /dev/null || die "another claim runs, or $c was left behind"
    if ! claim_inner "$t" "$a"; then
        rm -f "$t"; rmdir "$c"
        die "$WHY"
    fi
    HELD=1
    rm -f "$t"
    rmdir "$c" || die "cannot remove $c"
}
release() {
    [ "$HELD" = 1 ] || return 0
    HELD=0
    if own_q; then
        clear_lock 2> /dev/null && [ ! -s "$LOCK" ] && return 0
        echo "0391: the lock could not be released"
    else
        echo "0391: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
    fi
    return 1
}
reap() {
    local i p
    for i in $(seq 1 $((REAP_TERM + REAP_KILL))); do
        p=$(own_pids)
        [ -n "$p" ] || return 0
        # shellcheck disable=SC2086
        if [ "$i" -gt 5 ] && [ "$i" -le "$REAP_TERM" ]; then kill -TERM $p 2> /dev/null; elif [ "$i" -gt "$REAP_TERM" ]; then kill -KILL $p 2> /dev/null; fi
        sleep 1
    done
    [ -z "$(own_pids)" ]
}
do_claim() {
    local tag=$1 fix=$2 dl=$3
    case "$tag" in *[!A-Za-z0-9]* | "") die "a tag is letters and digits" ;; esac
    case "$fix" in pulls | late) ;; *) die "the mode is pulls or late" ;; esac  # 0391
    case "$dl" in *[!0-9]* | "") die "no deadline" ;; esac
    free_box
    paths_safe
    [ $((dl - $(now))) -ge "$RUN_MIN" ] || die "under $RUN_MIN s left"
    hook before-claim
    TOK=$(date +%Y%m%d%H%M%S)$$
    LOCKLINE="anyps5-ports exp0413r | token $TOK | $tag software replug ($fix), the build its pins name (shared, or a private one before a swap; see <tag>-pins.txt), RT on, until $(date -d "@$dl" +%H:%M:%S) | $(date '+%F %T')"
    trap 'release' EXIT
    claim
    hook after-claim
    own
    local p
    for p in "$EX" "$E" "$R" "$S"; do
        paths_safe
        [ -d "$p" ] || mkdir "$p" || die "cannot make $p"
    done
    paths_safe
    [ ! -e "$R/$tag-start.txt" ] && [ ! -e "$R/$tag-done.txt" ] || die "tag $tag was used"
    { printf '%s\n' "$LOCKLINE" > "$EX/lock-$TOK.line"; } 2> /dev/null || die "cannot write the token"
    own
    queue "$LOCKLINE" || die "queue write failed"
    own
    trap - EXIT
    HELD=0
    echo "TOK=$TOK"
}
load_tok() {
    TOK=${1:?token}
    case "$TOK" in *[!0-9]*) die "a token is digits" ;; esac
    LOCKLINE=$(cat "$EX/lock-$TOK.line" 2> /dev/null)
    [ -n "$LOCKLINE" ] || die "no such token"
}
# The pins under the lock, immediately before the launch. 0391: the shared normal build by its first 8 hex (the top session
# named 78f25172; the full md5 is recorded in -start.txt), the launcher and bc5-run.env in full; input.cfg and the learned
# file are recorded, not gated (s6n0391.sh copies both privately and forces RT on).
inputs_ok() {
    local v
    . "$S/pins0391.env" || die "no pins"
    [ -n "${BUILD:-}" ] && B=$BUILD  # exp 0417: the pins may name a PRIVATE build directory (a check before a swap); without it the shared build
    for v in NORMAL8 LAUNCHER RUN_ENV; do
        case "${!v:-FILL}" in FILL) die "the pin $v is not filled" ;; esac
    done
    BIN=$B/src/kyty_emulator  # 0391: the SHARED normal build, read only
    [ -f "$BIN" ] && [ ! -L "$BIN" ] || die "no shared binary at $BIN"
    [ "$(m "$BIN" | cut -c1-8)" = "$NORMAL8" ] || die "the shared binary is $(m "$BIN" | cut -c1-8), not $NORMAL8"
    [ "$(m "$W/play-pkg.sh")" = "$LAUNCHER" ] || die "the launcher is not $LAUNCHER"
    [ "$(m "$W/bc5-run.env")" = "$RUN_ENV" ] || die "bc5-run.env is not $RUN_ENV"
    [ -d "$W/exp0196/saves-before-152617" ] || die "no route saves (exp 0196)"
    [ -x "$S/replug0391.sh" ] && [ -f "$S/streams0391.py" ] || die "no replug script"
    echo "pins: shared $(m "$BIN"), launcher $LAUNCHER, bc5-run.env $RUN_ENV; input.cfg $(m "$W/input.cfg"), learned $(m "$W/direct-learned-pkg.txt")" > "$R/$TAG-pins.txt"
}
finish_run() {
    local rc=$?
    trap - EXIT HUP INT TERM
    set +e
    # A stop signal reaches here too: this token's processes end first, the lock goes last.
    local rel
    [ -z "$RUNP" ] || kill -TERM "$RUNP" 2> /dev/null
    # "released" only after this: no process of the token, the queue line read back, our exact line gone from the lock.
    if ! reap; then rel="processes remain: lock kept, run release"; HELD=0
    elif [ "$HELD" != 1 ]; then rel="not held"
    elif ! own_q; then rel="lost: the lock is not ours"; HELD=0
    elif ! queue "anyps5-ports exp0413r | done: $TAG token $TOK | $(date '+%F %T')"; then rel="queue write failed: lock kept, run release"; HELD=0
    elif ! release; then rel="the release failed"
    elif [ -n "$(own_pids)" ]; then rel="a process of the token appeared"
    else rel=released; fi
    { [ -s "$R/$TAG-result.txt" ] || echo "ABORT box rc $rc: $STOPWHY"; echo "lock $rel"; } > "$R/$TAG-done.txt.$$" && mv -f "$R/$TAG-done.txt.$$" "$R/$TAG-done.txt"
    exit "$rc"
}
do_run() {
    load_tok "$1"; TAG=$2; FIX=$3; DL=$4
    trap finish_run EXIT
    trap 'STOPWHY="stopped by a signal"; exit 143' HUP INT TERM
    HELD=1
    own
    paths_safe
    free_box
    inputs_ok
    hook after-inputs
    paths_safe
    local left=$((DL - $(now) - KEEP)) cap=$RUN_CAP rc p c
    [ "$left" -ge "$((SECS + 60))" ] || die "under $((SECS + 60)) s left"
    [ "$left" -ge "$cap" ] || cap=$left
    own
    # 0391: the replug script first (it waits for the run, up to 3 min), then the run; both carry the token
    D19_OWNER=$TOK E0391_LOCKLINE=$LOCKLINE \
        session timeout -k 30 "$cap" bash "$S/replug0391.sh" "$TAG" "$FIX" > "$R/$TAG-replug.out" 2>&1 &
    REPLUGP=$!
    D19_OWNER=$TOK D19_BIN=$BIN BC5_0380_WANT=$NORMAL8 E0391_LOCKLINE=$LOCKLINE PLAY_PKG_MD5=${LAUNCHER:0:8} \
        session timeout -k 30 "$cap" bash "$S/s6n0391.sh" "$TAG" "$SECS" > "$R/$TAG-runner.out" 2>&1 &
    p=$!; RUNP=$p
    wait "$p"; rc=$?
    RUNP=""
    wait "$REPLUGP" 2> /dev/null; echo "replug rc $?" >> "$R/$TAG-replug.out"
    reap || die "processes of the run remain"
    "${PY[@]}" "$S/check0391.py" run "$TAG" "$FIX" "$rc" "$R" > "$R/$TAG-check.txt" 2>&1; c=$?
    local cl; cl=$(tail -1 "$R/$TAG-check.txt")
    case "$cl" in "CLASS "*) ;; *) cl="CLASS INVALID mode $FIX pulls 0" ;; esac
    echo "RESULT $TAG runner $rc check $c $cl" > "$R/$TAG-result.txt.$$" && mv -f "$R/$TAG-result.txt.$$" "$R/$TAG-result.txt" || die "the result could not be written"
}
PY=(python3 -I)
case "${D19_FAKE:-}" in *d19-test-*) PY=(python) ;; esac
case "${1:-}" in
    claim) do_claim "${2:-}" "${3:-}" "${4:-}" ;;
    start)
        load_tok "$2"
        own
        paths_safe
        l=$(($5 - $(now) - OUTER_END))
        [ "$l" -gt 0 ] || die "no time left"
        session nohup timeout -k 30 "$l" bash "$S/run0391.sh" run "$2" "$3" "$4" "$5" < /dev/null > "$R/$3-box.out" 2>&1 &
        echo started
        ;;
    run) do_run "$2" "$3" "$4" "$5" ;;
    stream)
        load_tok "$2"
        kstream "$3" & J=$!
        while own_q && kill -0 "$J" 2> /dev/null; do sleep 5; done
        sleep 10
        kill "$J" 2> /dev/null
        ;;
    release)
        load_tok "$2"
        own
        HELD=1
        reap || { HELD=0; die "processes of token $TOK remain: lock kept"; }
        own
        queue "anyps5-ports exp0413r | released: token $TOK | $(date '+%F %T')" || die "queue write failed: lock kept"
        release || die "the release failed"
        [ -z "$(own_pids)" ] || die "a process of the token appeared"
        echo released
        ;;
    *) die "usage: claim|start|run|stream|release" ;;
esac
