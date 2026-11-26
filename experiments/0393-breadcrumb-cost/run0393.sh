#!/usr/bin/env bash
# BC5 exp 0393 on the box: the lock, the run and its cleanup for one step, the private build or one arm's run. Called by
# go0393.sh only. Made from exp 0388's run0388.sh by mk0393.py.
#   run0393.sh claim <tag> <deadline epoch>       over stdin; the atomic claim, prints TOK=
#   run0393.sh start <token> <tag> <deadline>     detaches `run` under its own time limit
#   run0393.sh run <token> <tag> <deadline>       the step; always ends by releasing its own lock
#   run0393.sh stream <token> <secs>              the kernel log, until the token's lock is gone
#   run0393.sh release <token>                    over stdin; recovery: stops this token's processes, frees its lock
# A tag build* compiles the one unit with exp 0277's edits and links it from the shared normal build's objects, nice 19, no
# emulator, no GPU. Any other tag is one s6n0393.sh run. Claim as in coordination/d19/d19box.sh: the line appears by a hard
# link, which cannot replace an existing lock. One token per step, no second claimant. Only processes with this token in
# their environment are ever signalled. Nothing here changes shared files; the runs use a private copy of a named snapshot.
set -u
export LC_ALL=C
W=${D19_WORK:-$HOME/bc5-work}
EX=$W/exp0393; E=$EX/run; R=$E/raw; S=$EX/s
LOCK=$W/BOX-LOCK; QUEUE=$W/BOX-QUEUE
# The deadline is the end of everything. The outer limit ends 60 s before it, hard kill included; the run must leave 150 s
# for its own kill (30), reap (30) and release. A run needs 690 s, plus the claim and the send.
SECS=420; RUN_MIN=720; RUN_CAP=540; KEEP=150; OUTER_END=90; REAP_TERM=20; REAP_KILL=10; DISK_MAX=80
HELD=0; LOCKLINE=""; STOPWHY=""; RUNP=""
TREE_MD5=29b3d8c602c92c84fa7731d3902fcc48  # main's unit at 5b22f700
now() { date +%s; }
die() { STOPWHY=$*; echo "0393 STOP: $*"; exit 1; }
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
write_roots() { echo "$EX" "$EX/src" "$EX/obj" "$E" "$R" "$S" "$E/wd" "$E/wd/_SaveData" "$E/wd/_SaveData-pkg-play"; }
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
    local c=$LOCK.d19-claim t=$LOCK.0393-$$.new a=$LOCK.0393-$$.aside WHY=""
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
        echo "0393: the lock could not be released"
    else
        echo "0393: the lock is not ours, left as it is: $(cat "$LOCK" 2> /dev/null)"
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
    local tag=$1 dl=$2
    case "$tag" in *[!A-Za-z0-9]* | "") die "a tag is letters and digits" ;; esac
    case "$dl" in *[!0-9]* | "") die "no deadline" ;; esac
    free_box
    paths_safe
    [ $((dl - $(now))) -ge "$RUN_MIN" ] || die "under $RUN_MIN s left"
    hook before-claim
    TOK=$(date +%Y%m%d%H%M%S)$$
    LOCKLINE="tcp exp0393 | token $TOK | $tag breadcrumb cost, RT on, until $(date -d "@$dl" +%H:%M:%S) | $(date '+%F %T')"
    trap 'release' EXIT
    claim
    hook after-claim
    own
    local p
    for p in "$EX" "$EX/src" "$EX/obj" "$E" "$R" "$S"; do
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
# The pins under the lock, immediately before the launch.
inputs_ok() {
    local v
    . "$S/pins0393.env" || die "no pins"
    for v in BINARY LAUNCHER RUN_ENV ROUTE_SAVES MENU_CMD INPUT_CFG LEARNED; do
        case "${!v:-FILL}" in FILL) die "the pin $v is not filled" ;; esac
    done
    BIN=$EX/kyty_emulator  # 0393: the private test build
    [ "$(m "$BIN")" = "$BINARY" ] || die "the binary is not $BINARY"
    [ "$(m "$W/play-pkg.sh")" = "$LAUNCHER" ] || die "the launcher is not $LAUNCHER"
    [ "$(m "$W/bc5-run.env")" = "$RUN_ENV" ] || die "bc5-run.env is not $RUN_ENV"
    [ "$(m "$W/exp0203/o2-continue.cmd")" = "$MENU_CMD" ] || die "the menu script differs"
    [ "$(m "$W/input.cfg")" = "$INPUT_CFG" ] || die "input.cfg differs"
    [ "$(m "$W/direct-learned-pkg.txt")" = "$LEARNED" ] || die "the learned file differs"
    [ "$(cd "$W/exp0196" && find saves-before-152617 -type f | wc -l)" -gt 0 ] || die "no route saves"
    [ "$(route_sum)" = "$ROUTE_SAVES" ] || die "the route saves are not $ROUTE_SAVES"
}
# The private binary. The shared binary's md5 is read before and after; nothing shared is written.
do_build() {
    local K=$HOME/src/KytyPlus B=$W/kytyplus-build T s0 rc n
    T=$K/src/libs/bc5LleAgc.cpp
    [ "$(m "$T")" = "$TREE_MD5" ] || die "the tree's bc5LleAgc.cpp is not $TREE_MD5"
    s0=$(m "$B/src/kyty_emulator")
    { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$T") md5 $TREE_MD5"
      echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $s0"
      echo "shared object $(stat -c '%y' "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/$TAG-inputs.txt"
    "${PY[@]}" "$S/patch0393.py" "$T" "$EX/src/bc5LleAgc.bc.cpp" "$R/patch_0393.diff" || die "the patch failed"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$EX/compdb.json" 2> "$R/compdb.err" || die "compdb failed"
    grep -q '"command": "[^"]* @' "$EX/compdb.json" && die "the compdb still names response files"
    grep -q '"output": "src/kyty_emulator"' "$EX/compdb.json" || die "no link command in the compdb"
    ( cd "$EX" && distrobox enter ubuntu -- python3 -I "$S/build0393.py" "$EX/compdb.json" ) > "$R/$TAG-build.out" 2>&1
    rc=$?
    [ "$(m "$B/src/kyty_emulator")" = "$s0" ] || die "the shared binary changed during the build"
    [ "$rc" = 0 ] && [ -x "$EX/kyty_emulator" ] || die "the build failed, rc $rc, see $R/$TAG-build.out"
    n=$(strings "$EX/kyty_emulator" | grep -c "exp 0277")
    [ "$n" -gt 0 ] || die "no exp 0277 strings in the binary"
    echo "RESULT $TAG binary $(m "$EX/kyty_emulator") shared $s0 strings $n warnings $(grep -c "warning:" "$R/$TAG-build.out")" > "$R/$TAG-result.txt.$$" && mv -f "$R/$TAG-result.txt.$$" "$R/$TAG-result.txt" || die "the result could not be written"
}
# The copy in C and from inside it.
route_sum() { (cd "$W/exp0196/saves-before-152617" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }
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
    elif ! queue "tcp exp0393 | done: $TAG token $TOK | $(date '+%F %T')"; then rel="queue write failed: lock kept, run release"; HELD=0
    elif ! release; then rel="the release failed"
    elif [ -n "$(own_pids)" ]; then rel="a process of the token appeared"
    else rel=released; fi
    { [ -s "$R/$TAG-result.txt" ] || echo "ABORT box rc $rc: $STOPWHY"; echo "lock $rel"; } > "$R/$TAG-done.txt.$$" && mv -f "$R/$TAG-done.txt.$$" "$R/$TAG-done.txt"
    exit "$rc"
}
do_run() {
    load_tok "$1"; TAG=$2; DL=$3
    trap finish_run EXIT
    trap 'STOPWHY="stopped by a signal"; exit 143' HUP INT TERM
    HELD=1
    own
    paths_safe
    free_box
    case "$TAG" in build*) do_build; return ;; esac
    inputs_ok
    hook after-inputs
    paths_safe
    local left=$((DL - $(now) - KEEP)) cap=$RUN_CAP rc p
    [ "$left" -ge "$((SECS + 60))" ] || die "under $((SECS + 60)) s left"
    [ "$left" -ge "$cap" ] || cap=$left
    own
    D19_OWNER=$TOK D19_BIN=$BIN BC5_0393_WANT=${BINARY:0:8} E0393_LAUNCHER=$LAUNCHER E0393_LOCKLINE=$LOCKLINE \
        session timeout -k 30 "$cap" bash "$S/s6n0393.sh" "$TAG" "$SECS" > "$R/$TAG-runner.out" 2>&1 &
    p=$!; RUNP=$p
    wait "$p"; rc=$?
    RUNP=""
    reap || die "processes of the run remain"
    echo "RESULT $TAG runner $rc verdict $(head -1 "$R/$TAG-verdict.txt" 2> /dev/null)" > "$R/$TAG-result.txt.$$" && mv -f "$R/$TAG-result.txt.$$" "$R/$TAG-result.txt" || die "the result could not be written"
}
PY=(python3 -I)
case "${D19_FAKE:-}" in *d19-test-*) PY=(python) ;; esac
case "${1:-}" in
    claim) do_claim "${2:-}" "${3:-}" ;;
    start)
        load_tok "$2"
        own
        paths_safe
        l=$(($4 - $(now) - OUTER_END))
        [ "$l" -gt 0 ] || die "no time left"
        session nohup timeout -k 30 "$l" bash "$S/run0393.sh" run "$2" "$3" "$4" < /dev/null > "$R/$3-box.out" 2>&1 &
        echo started
        ;;
    run) do_run "$2" "$3" "$4" ;;
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
        queue "tcp exp0393 | released: token $TOK | $(date '+%F %T')" || die "queue write failed: lock kept"
        release || die "the release failed"
        [ -z "$(own_pids)" ] || die "a process of the token appeared"
        echo released
        ;;
    *) die "usage: claim|start|run|stream|release" ;;
esac
