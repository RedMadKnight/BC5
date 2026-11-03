#!/usr/bin/env bash
# BC5 experiment 0401: one private normal build, CPU only, no emulator, no game run. The README has the order.
#   claim                  over stdin, before anything else of ours is on the box: the lock, then the pins under it
#   setup <token>          checks the sent kit
#   build <token>          the unit's real function under test, then the unit compiled with the shared build's own command and
#                          linked with the shared objects and the shared archive; then the private launcher
#   status <token>         read only
#   release <token>        takes our lock line out; every other line stays
# build exits 0 only after its last marker. Nothing shared is written: the shared binaries, the archive, ~/src/KytyPlus and
# play-pkg.sh are only read, and their pins are checked again at the end. Claim, lock and release are box0400.sh's (D19's
# reviewed d19box.sh, sha256 2cf2a0f1) with this experiment's names. There is no watchdog: nothing of ours outlives build.
set -u
export LC_ALL=C LANGUAGE=C

W=$HOME/bc5-work; TREE=$HOME/src/KytyPlus; TESTING=0
# Stand-ins load only if the root and the stand-in file both sit under a 0401-test- path. Otherwise nothing overrides.
case "${BC5_0401_ROOT:-}" in *0401-test-*) case "${BC5_0401_FAKE:-}" in *0401-test-*) TESTING=1 ;; esac ;; esac
[ "$TESTING" = 0 ] || { W=$BC5_0401_ROOT/bc5-work; TREE=$BC5_0401_ROOT/src/KytyPlus; }
# The series (2026-11-03): unset is the first build (exp0401); BC5_0401_SERIES=b is a second build in exp0401b, the same unit
# plus the acb CS prefix (mkunit0401.py --acb), so the first build stays as it was played. c (exp0401c) adds exp 0381's
# ACB_STATE_RESTORE as well (--acb-restore), so b stays as a rollback.
case "${BC5_0401_SERIES:-}" in
    "") SER=""; EXPECT_UNIT=9eec0a3856bc1857ba7956b001c93aaf; MKFLAG="" ;;
    b) SER=b; EXPECT_UNIT=b1d96c719fda2ed048876fe119e89310; MKFLAG=--acb ;;
    c) SER=c; EXPECT_UNIT=29c88be321cc81908085b1cddcc70d2e; MKFLAG=--acb-restore ;;
    *) echo "0401 STOP: unknown series ${BC5_0401_SERIES}"; exit 2 ;;
esac
E=$W/exp0401$SER; LOCK=$W/BOX-LOCK; QUEUE=$W/BOX-QUEUE; ST=$E/state; BIN=$E/bin/kyty_emulator; B=$W/kytyplus-build; R=$E/raw

BIN_MD5=4d2b1b1dd52eaea6e3195500f604e73e; LEAN_MD5=30d4be3371d7c6376b2b4425698c1c3a; ARCHIVE_MD5=75e303357610fee8d1d205bdc88c031c
LAUNCHER_MD5=97835f8850cc22ece5c4bcdbbb646912; UNIT_MD5=d18b448299a335aadac75bbd202155fd   # main 029e0d6b's patch 0001 unit
SERIES_S=2400; GRACE=120; BUILD_S=1500; DISK_MAX=80

DBX=(distrobox enter ubuntu --); PY=(python3 -I); CXX=clang++
now() { printf '%(%s)T\n' -1; }
hook() { :; }
disk_pct() { df --output=pcent "$W" | tail -1 | tr -dc 0-9; }
in_box() { local n=$1; shift; cap "$n" "${DBX[@]}" "$@" < /dev/null; }
strip_ansi() { sed -E $'s/\x1b\\[[0-9;]*[A-Za-z]//g' "$1"; }

TOKEN=""; LOCKLINE=""; DEADLINE=0; WHY=""; COMM=""; PSTATE=""; START=""

die() { echo "0401 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
rd() { local x=""; { IFS= read -r x < "$1"; } 2> /dev/null; printf '%s\n' "$x"; }   # the first line of a small file
# Atomic, checked write of one small file.
try_put() {
    local f=$1 t=$1.tmp.$$; shift
    printf '%s\n' "$*" > "$t" 2> /dev/null && mv -fT "$t" "$f" 2> /dev/null && [ "$(cat "$f" 2> /dev/null)" = "$*" ]
}
put() { try_put "$@" || die "write failed: $1"; }
load() {
    local t=${1:-}
    case "$t" in "" | *[!0-9]*) die "give the series token" ;; esac
    [ -d "$E" ] && [ ! -L "$E" ] || die "no series at $E"
    TOKEN=$(rd "$E/token")
    [ "$TOKEN" = "$t" ] || die "token $t is not this series' (${TOKEN:-none})"
    LOCKLINE=$(rd "$E/lock.line")
    [ -n "$LOCKLINE" ] || die "no lock line in $E"
    DEADLINE=$(rd "$E/deadline")
    case "$DEADLINE" in "" | *[!0-9]*) die "no valid deadline in $E" ;; esac
}
state() { rd "$ST"; }
left() { echo $((DEADLINE - $(now))); }
budget() { [ "$(left)" -gt "$1" ] || die "$1 s are not left before the deadline"; }
# A command under a time limit that never runs past the deadline less the grace.
cap() {
    local l=$((DEADLINE - GRACE - $(now))); [ "$l" -lt "$1" ] || l=$1
    shift
    [ "$l" -gt 0 ] || { echo "no time left for $1"; return 124; }
    timeout -k 10 "$l" "$@"
}

# The lock. Free means an empty BOX-LOCK, so O_EXCL alone cannot work: the empty file goes aside, then ln, which fails if
# anyone recreated it. A writer that had the old file open shows up in the aside copy.
own_q() {   # the file is exactly our one line
    [ -f "$LOCK" ] && [ ! -L "$LOCK" ] || return 1
    local l
    { mapfile -t l < "$LOCK"; } 2> /dev/null || return 1
    [ "${#l[@]}" = 1 ] && [ "${l[0]}" = "$LOCKLINE" ]
}
own() { own_q || die "the lock is not ours: $(cat "$LOCK" 2> /dev/null)"; }
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
    local c=$LOCK.0401-claim t=$LOCK.0401-$$.new a=$LOCK.0401-$$.aside
    mkdir "$c" 2> /dev/null || die "another 0401 claim runs, or $c was left behind"
    if ! claim_inner "$t" "$a"; then
        rm -f "$t"; rmdir "$c"
        die "$WHY"
    fi
    rm -f "$t"
    rmdir "$c" || die "cannot remove $c"
}
# Only our exact line goes; every other line stays, in order. The move is atomic, so a writer lands either in the aside
# copy or in a new file, and both are kept.
lock_remove() {
    local t=$LOCK.0401-$$.new a=$LOCK.0401-$$.aside n
    [ -f "$LOCK" ] && [ ! -L "$LOCK" ] || { WHY="$LOCK is not a plain file"; return 1; }
    grep -qxF -- "$LOCKLINE" "$LOCK" || { WHY="no line of ours in $LOCK"; return 1; }
    mv -T "$LOCK" "$a" 2> /dev/null || { WHY="the lock moved under us"; return 1; }
    grep -vxF -- "$LOCKLINE" "$a" > "$t"
    [ $? -le 1 ] || { WHY="cannot read $a; the lock lines are there"; return 1; }
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        cat "$t" >> "$LOCK" || { WHY="cannot keep the lines of $a"; return 1; }
    fi
    n=$(wc -l < "$t")
    grep -vxF -- "$LOCKLINE" "$a" | tail -n +$((n + 1)) >> "$LOCK" || { WHY="cannot keep late lines of $a"; return 1; }
    rm -f "$t" "$a"
}
unclaim() {
    if [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && grep -qxF -- "$LOCKLINE" "$LOCK"; then
        lock_remove || die "$1; our line could not be released: $WHY"
    fi
    die "$1; our lock line is out, nothing moved"
}
queue_try() {
    [ ! -L "$QUEUE" ] || return 1
    { printf '%s\n' "$1" >> "$QUEUE"; } 2> /dev/null && grep -qxF -- "$1" "$QUEUE" 2> /dev/null
}

# Processes, read from /proc alone.
stat_of() {   # pid; sets COMM, PSTATE, START (the kernel's start time); 1 if there is no such process
    local l
    { IFS= read -r l < "/proc/$1/stat"; } 2> /dev/null || return 1
    COMM=${l#*\(}; COMM=${COMM%\)*}; l=${l##*\) }
    # shellcheck disable=SC2086
    set -- $l
    PSTATE=${1:-}; START=${20:-}
    [ -n "$START" ]
}
id_alive() {   # file with "pid start"
    local p s
    read -r p s < "$1" 2> /dev/null || return 1
    stat_of "$p" && [ "$PSTATE" != Z ] && [ "$START" = "$s" ]
}
live_pids() {   # pid:comm of everything alive but this shell
    local p n
    for p in /proc/[0-9]*; do
        n=${p#/proc/}
        [ "$n" != "$$" ] && [ "$n" != "${BASHPID:-}" ] || continue
        if stat_of "$n" && [ "$PSTATE" != Z ]; then echo "$n:$COMM"; fi
    done
    return 0
}
work_free() {   # no emulator or build of anyone
    local l
    while IFS= read -r l; do
        case ${l#*:} in kyty_emulator* | ninja | cmake) WHY="work runs on the box: $l"; return 1 ;; esac
    done < <(live_pids)
    return 0
}
pins_why() {   # prints the first pin that does not hold
    [ "$(m "$B/src/kyty_emulator")" = "$BIN_MD5" ] || { echo "the shared normal binary is not $BIN_MD5"; return; }
    [ "$(m "$W/kytyplus-build-lean/src/kyty_emulator")" = "$LEAN_MD5" ] || { echo "the shared lean binary is not $LEAN_MD5"; return; }
    [ "$(m "$W/backend-ubuntu/libbc5_backend.a")" = "$ARCHIVE_MD5" ] || { echo "the archive is not $ARCHIVE_MD5"; return; }
    [ "$(m "$W/play-pkg.sh")" = "$LAUNCHER_MD5" ] || { echo "the launcher is not $LAUNCHER_MD5"; return; }
    [ "$(m "$TREE/src/libs/bc5LleAgc.cpp")" = "$UNIT_MD5" ] || { echo "the tree's unit is not main's, $UNIT_MD5"; return; }
    [ "$(disk_pct)" -lt "$DISK_MAX" ] || echo "the disk is at $DISK_MAX % or more"
}

cmd_claim() {
    local why line
    [ ! -e "$E" ] && [ ! -L "$E" ] || die "$E exists: nothing touched"
    work_free || die "$WHY"
    hook before-claim
    TOKEN=$(date +%Y%m%d%H%M%S)$$
    DEADLINE=$(($(now) + SERIES_S))
    LOCKLINE="water exp 0401$SER | private normal build, CPU only, no emulator, token $TOKEN | until $(date -d "@$DEADLINE" '+%F %T')"
    claim
    own
    why=$(pins_why)
    [ -z "$why" ] || unclaim "$why"
    work_free || unclaim "$WHY"
    hook after-pins
    mkdir "$E" 2> /dev/null || unclaim "$E appeared"
    try_put "$E/token" "$TOKEN" || unclaim "write failed: token"
    try_put "$E/lock.line" "$LOCKLINE" || unclaim "write failed: lock.line"
    try_put "$E/deadline" "$DEADLINE" || unclaim "write failed: deadline"
    line="water exp 0401$SER | claimed: private normal build, token $TOKEN, until the deadline $DEADLINE | $(date '+%F %T')"
    queue_try "$line" || unclaim "queue write failed"
    try_put "$ST" claimed || unclaim "write failed: state"
    echo "TOKEN=$TOKEN"
    echo "kernel $(uname -r); until $(date -d "@$DEADLINE" '+%F %T')"
}

cmd_setup() {
    load "${1:-}"
    # A kit sent again after a failed build (state building, no build alive) is checked again the same way.
    case "$(state)" in
        claimed) ;;
        building) ! id_alive "$E/build.id" || die "a build still runs" ;;
        *) die "state is $(state), want claimed" ;;
    esac
    own; budget "$GRACE"
    (cd "$E" && sha256sum -c --quiet kit.sha256) > "$E/kit.check" 2>&1 || die "the kit is not what was sent: $(cut -c1-120 "$E/kit.check")"
    mkdir -p "$R" "$E/src" "$E/inc" "$E/inc/bc5" "$E/bin" 2> /dev/null || die "cannot make the private directories"
    cp "$E/env_flag.hpp" "$E/inc/bc5/env_flag.hpp" || die "cannot place env_flag.hpp"
    put "$ST" setup
    echo "set up"
}

cmd_build() {
    load "${1:-}"
    [ "$(state)" = setup ] || die "state is $(state), want setup"
    own; budget "$GRACE"
    work_free || die "$WHY"
    local why u
    why=$(pins_why); [ -z "$why" ] || die "$why"
    stat_of $$ || die "no stat of this shell"
    put "$E/build.id" "$$ $START"
    put "$ST" building

    # 1. The unit, and its new function alone, from the tree that built the shared binaries.
    u=$("${PY[@]}" "$E/mkunit0401.py" "$TREE/src/libs/bc5LleAgc.cpp" "$E/src/bc5LleAgc.cpp" "$E/src/mesa_preamble_prefix.inc" $MKFLAG) || die "the unit's edit did not apply"
    [ "$u" = "$EXPECT_UNIT" ] || die "the private unit is $u, not $EXPECT_UNIT"
    [ "$(m "$E/src/bc5LleAgc.cpp")" = "$EXPECT_UNIT" ] || die "the private unit on disk is not $EXPECT_UNIT"

    # 2. The real function, every setting of the two switches.
    in_box 120 "$CXX" -std=c++20 -Wall -Wextra -Werror "-I$E/inc" "-I$E/src" "$E/unit0401.cpp" -o "$R/unit0401" > "$R/unit0401.out" 2>&1 || die "the function did not compile: $(grep -m3 'error:' "$R/unit0401.out" | cut -c1-160 | tr '\n' ' ')"
    in_box 60 python3 -I "$E/check0401.py" "$R/unit0401" > "$R/check0401.out" 2>&1 || die "the function's check failed: $(tail -1 "$R/check0401.out" | cut -c1-200)"
    grep -q '^check0401: 7 of 7 .*; end$' "$R/check0401.out" || die "no end marker from the function's check"
    hook after-check
    own

    # 3. The shared build's own commands. No header changes, so nothing else is compiled.
    in_box 60 sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || die "no compile database"
    in_box "$BUILD_S" python3 -I "$E/build0401.py" "$E/compdb.json" "$E/src/bc5LleAgc.cpp" "$E/obj" "$B" "$BIN" > "$R/build.out" 2>&1 || die "the private build failed: $(strip_ansi "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED' | cut -c1-160 | tr '\n' ' ')"
    [ -x "$BIN" ] || die "no private binary"
    own

    # 4. What the binary must hold, and what it must still hold.
    local s strs=(BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_SPI_REQ_CTRL_PS 'exp 0401: CP_COHER_START_DELAY %s' 'exp 0401: SPI_SHADER_REQ_CTRL_PS %s' BC5_DIRECT_ARGS_WB BC5_DIRECT_GC_HS_OFFCHIP)
    [ -z "$SER" ] || strs+=(BC5_DIRECT_ACB_CS_PREFIX 'exp 0401: acb CS prefix %s' 'acb cs prefix (exp 0401)' BC5_DIRECT_CS_PREFIX)
    [ "$SER" != c ] || strs+=(BC5_DIRECT_ACB_STATE_RESTORE 'exp 0401: acb state restore (exp 0381) %s' 'acb state restore (exp 0381)')
    for s in "${strs[@]}"; do
        grep -aqF -- "$s" "$BIN" || die "the private binary lacks [$s]"
    done

    # 5. The private launcher.
    "${PY[@]}" "$E/launcher0401.py" "$W/play-pkg.sh" "$E/play-pkg-0401.sh" $SER || die "the launcher's edit did not apply"
    bash -n "$E/play-pkg-0401.sh" || die "the private launcher does not parse"
    chmod +x "$E/play-pkg-0401.sh" || die "chmod failed"
    diff -u "$W/play-pkg.sh" "$E/play-pkg-0401.sh" > "$E/play-pkg-0401.diff"
    [ "$(grep -c '^[-+][^-+]' "$E/play-pkg-0401.diff")" = 8 ] || die "the launcher's diff is not 4 lines changed"

    why=$(pins_why); [ -z "$why" ] || die "$why"
    put "$E/bin.md5" "$(m "$BIN")"
    put "$E/launcher.md5" "$(m "$E/play-pkg-0401.sh")"
    {
        echo "binary $(rd "$E/bin.md5"): shared objects of $BIN_MD5, unit $EXPECT_UNIT, archive $ARCHIVE_MD5"
        echo "launcher $(rd "$E/launcher.md5") from play-pkg.sh $LAUNCHER_MD5"
        echo "warnings in the unit's compile: $(strip_ansi "$R/build.out" | grep -c 'warning:')"
        echo "function check: $(tail -1 "$R/check0401.out")"
        echo "kernel $(uname -r)"
    } > "$E/build.txt" || die "write failed: build.txt"
    own
    put "$ST" built
    cat "$E/build.txt"
    echo "built: shared binaries, archive, tree and launcher unchanged"
}

do_release() {
    local line
    [ "$(state)" != released ] || { echo "released already"; return 0; }
    if id_alive "$E/build.id"; then echo "the build still runs, the lock stays"; return 1; fi
    mkdir "$E/release.claim" 2> /dev/null || { echo "a release runs, or $E/release.claim was left behind"; return 1; }
    if [ -L "$LOCK" ] || [ ! -f "$LOCK" ] || ! grep -qxF -- "$LOCKLINE" "$LOCK"; then
        rmdir "$E/release.claim"
        echo "no line of ours in $LOCK, left as it is: $(cat "$LOCK" 2> /dev/null)"
        return 1
    fi
    line="water exp 0401$SER | released: $1, token $TOKEN | $(date '+%F %T')"
    if ! queue_try "$line"; then rmdir "$E/release.claim"; echo "queue write failed, the lock stays"; return 1; fi
    if ! lock_remove; then rmdir "$E/release.claim"; echo "$WHY"; return 1; fi
    try_put "$ST" released
    rmdir "$E/release.claim"
    echo "released"
}
cmd_status() {
    load "${1:-}"
    echo "state $(state); $(left) s to the deadline; lock ours $(own_q && echo yes || echo no); build $(id_alive "$E/build.id" && echo running || echo "not running")"
    echo "--- BOX-LOCK:"; cat "$LOCK" 2> /dev/null
}

[ "$TESTING" = 0 ] || . "$BC5_0401_FAKE"
case "${1:-}" in
    claim) cmd_claim ;;
    setup) cmd_setup "${2:-}" ;;
    build) cmd_build "${2:-}" ;;
    status) cmd_status "${2:-}" ;;
    release) load "${2:-}"; do_release "${3:-the release command}" ;;
    *) echo "usage: box0401.sh claim|setup|build|status|release ..."; exit 2 ;;
esac
