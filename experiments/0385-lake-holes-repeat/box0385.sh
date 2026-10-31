#!/usr/bin/env bash
# BC5 experiment 0385: every box step of the lake series, one subcommand each. The README has the order.
#   claim                  over stdin, before anything else of ours is on the box: the lock, then the pins under it
#   setup <token>          checks the sent kit; private launcher, wd, input and learned copies; starts the watchdog
#   build <token>          the private test binary from testbuild.tar: its tests, then the shared link command with the
#                          private archive. Nothing shared is written. CPU only, no emulator
#   kstream <token>        the kernel log for the laptop; ends with our lock line or the deadline
#   run <token> <tag>      one attempt: K4, K5, K6, in that order
#   bench <token> <tag>    the route and the shots, started by run
#   status <token>         read only
#   stop <token>           stops what is ours; no further runs
#   release <token>        stops what is ours, then takes our lock line out; every other line stays
#   watch <token>          the watchdog, started by setup in its own session; tick <token> is one pass of it
# run exits 0 for a run that passed its gates, 10 for a failed route (the attempt is used, evidence kept), 1 for a stop.
# Ownership: one lock line with one token, no per-run line. Distrobox starts the launcher through podman, so it and the
# emulator are in no process group of ours: a process is ours only if its exec environment holds the token. Marked
# host children (bench, poller, shots) carry a second mark, and the launch chain's host side carries none, so a
# conmon or pause process started on our behalf can never be taken for ours. The series has one deadline.
# Claim and marks follow D19's reviewed d19box.sh (sha256 2cf2a0f1) and archive-d19.sh (c892c407); the launcher
# derivation and the wd layout follow s6n-d19.sh (d7cf6e33).
set -u
export LC_ALL=C LANGUAGE=C

W=$HOME/bc5-work; DATA=$HOME/bc5-data; TESTING=0
# Stand-ins load only if the root and the stand-in file both sit under a 0385-test- path. Otherwise nothing overrides.
case "${BC5_0385_ROOT:-}" in *0385-test-*) case "${BC5_0385_FAKE:-}" in *0385-test-*) TESTING=1 ;; esac ;; esac
[ "$TESTING" = 0 ] || { W=$BC5_0385_ROOT/bc5-work; DATA=$BC5_0385_ROOT/bc5-data; }
E=$W/exp0385; WD=$E/wd; PRIV=$DATA/priv/exp0385; EV=$PRIV/evidence; LOCK=$W/BOX-LOCK; QUEUE=$W/BOX-QUEUE; ST=$E/state
LAKE=$W/saves-lake-1153; SELF=$E/box0385.sh; TB=$E/tb; TB_BIN=$TB/kyty_emulator

BIN_MD5=78f251729b06001d67d642ff06773758; ARCHIVE_MD5=3292bdaf0aca16ca9922a7f732386aa8
LAUNCHER_MD5=55531ab6277d6816c0603a7a6c6d62b4; RUN_ENV_MD5=cb8ad5fcfd6eac2a5cafac2a501b3eba
LIVE_SAVES=""   # no fixed pin, the maintainer's play moves it: read under the claim, then held in $E/live.sum (C locale)
SERIES_S=2700; GRACE=120; RUN_S=780; EMU_S=560; BENCH_S=500; ANA_S=150; BUILD_S=420; EMU_WAIT=60
REAP_TERM=15; REAP_KILL=10; REAP_WAIT=40; WATCH_NAP=3; WATCH_WAIT=25
SERIES=53; STEP=5; SLOTWAIT=5; LOADWAIT=60; KEYWAIT=120; TAGS="K4 K5 K6"; DISK_MAX=80; DISK_STOP=90
KPAT='amdgpu.*(fault|timeout|reset)|gpu reset|ring .* timeout'

# What a test may replace. Each stays a plain box command here.
DBX=(distrobox enter ubuntu --); PY=(python3 -I); KS=(journalctl -k -f -n 0 -o short-precise)
now() { printf '%(%s)T
' -1; }
nap() { sleep "$1"; }
private_dir() { mkdir -m 700 "$@"; }
hook() { :; }
session() { setsid "$@"; }
boot_id() { cat /proc/sys/kernel/random/boot_id; }
dmesg_read() { sudo -n dmesg; }
compress_idle() { [ "$(systemctl --user is-active bc5-compress-captures.service 2> /dev/null)" = inactive ]; }
atime_ok() { case " $(findmnt -no OPTIONS -T "$E" 2> /dev/null | tr ',' ' ') " in *" noatime "*) return 1 ;; esac; }
save_read_since() { find "$1" -type f -newerat "@$2" 2> /dev/null | grep -q .; }
disk_pct() { df --output=pcent "$W" | tail -1 | tr -dc 0-9; }
shot() { XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 timeout -k 3 12 spectacle -b -n -f -o "$1" > /dev/null 2>&1; }
in_box() { local n=$1; shift; cap "$n" "${DBX[@]}" "$@"; }
poller() { env "$HMARK" "${PY[@]}" "$E/pl0385.py" "$@"; }
bundle() { tar cf "$1" "${@:2}"; }

TOKEN=""; LOCKLINE=""; DEADLINE=0; MARK=""; HMARK=""; WHY=""; TAG=""; COMM=""; PSTATE=""; START=""; EP=""; ES=""

die() { echo "0385 STOP: $*"; exit 1; }
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
rd() { local x=""; { IFS= read -r x < "$1"; } 2> /dev/null; printf '%s\n' "$x"; }   # the first line of a small file
# Atomic, checked write of one small file.
try_put() {
    local f=$1 t=$1.tmp.$$; shift
    printf '%s\n' "$*" > "$t" 2> /dev/null && mv -fT "$t" "$f" 2> /dev/null && [ "$(cat "$f" 2> /dev/null)" = "$*" ]
}
put() { try_put "$@" || die "write failed: $1"; }
marks() { MARK=BC5_0385_OWNER=$TOKEN; HMARK=BC5_0385_HOST=$TOKEN; }
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
    LIVE_SAVES=$(rd "$E/live.sum")
    [ -n "$LIVE_SAVES" ] || die "no live saves sum in $E"
    marks
}
state() { rd "$ST"; }
# stopped and released are final, but for stopped to released.
set_state() {
    case "$(state):$1" in released:* | stopped:setup | stopped:ready | stopped:running | stopped:done) return 1 ;; esac
    put "$ST" "$1"
}
series_stop() {
    [ "$(state)" = released ] || try_put "$ST" stopped
    printf '%s %s\n' "$(date '+%F %T')" "$1" >> "$E/stop.log" 2> /dev/null
    return 0
}
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
    local c=$LOCK.0385-claim t=$LOCK.0385-$$.new a=$LOCK.0385-$$.aside
    mkdir "$c" 2> /dev/null || die "another 0385 claim runs, or $c was left behind"
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
    local t=$LOCK.0385-$$.new a=$LOCK.0385-$$.aside n
    [ -f "$LOCK" ] && [ ! -L "$LOCK" ] || { WHY="$LOCK is not a plain file"; return 1; }
    grep -qxF -- "$LOCKLINE" "$LOCK" || { WHY="no line of ours in $LOCK"; return 1; }
    mv -T "$LOCK" "$a" 2> /dev/null || { WHY="the lock moved under us"; return 1; }
    hook after-release-aside
    grep -vxF -- "$LOCKLINE" "$a" > "$t"
    [ $? -le 1 ] || { WHY="cannot read $a; the lock lines are there"; return 1; }
    if ! ln "$t" "$LOCK" 2> /dev/null; then
        cat "$t" >> "$LOCK" || { WHY="cannot keep the lines of $a"; return 1; }
    fi
    hook after-release-link
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

# Processes, read from /proc alone: the same functions on the box and in the tests.
stat_of() {   # pid; sets COMM, PSTATE, START (the kernel's start time); 1 if there is no such process
    local l
    { IFS= read -r l < "/proc/$1/stat"; } 2> /dev/null || return 1
    COMM=${l#*\(}; COMM=${COMM%\)*}; l=${l##*\) }
    # shellcheck disable=SC2086
    set -- $l
    PSTATE=${1:-}; START=${20:-}
    [ -n "$START" ]
}
has_mark() {   # pid, entries: is one of them in its exec environment
    local p=$1 e x y; shift
    { mapfile -d '' -t e < "/proc/$p/environ"; } 2> /dev/null || return 1
    for x in "${e[@]}"; do for y in "$@"; do [ "$x" = "$y" ] && return 0; done; done
    return 1
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
own_pids() { local l; while IFS= read -r l; do if has_mark "${l%%:*}" "$MARK" "$HMARK"; then echo "$l"; fi; done < <(live_pids); return 0; }
own_emus() { local l; while IFS= read -r l; do case ${l#*:} in kyty_emulator*) if has_mark "${l%%:*}" "$MARK"; then echo "${l%%:*}"; fi ;; esac; done < <(live_pids); return 0; }
own_stuck() { local l; while IFS= read -r l; do case ${l#*:} in bc5-mount*) ;; *) echo "${l%%:*}" ;; esac; done < <(own_pids); return 0; }
foreign_emus() { local l; while IFS= read -r l; do case ${l#*:} in kyty_emulator*) if ! has_mark "${l%%:*}" "$MARK"; then echo "${l%%:*}"; fi ;; esac; done < <(live_pids); return 0; }
work_free() {   # no emulator or build of anyone
    local l
    while IFS= read -r l; do
        case ${l#*:} in kyty_emulator* | ninja | cmake) WHY="work runs on the box: $l"; return 1 ;; esac
    done < <(live_pids)
    return 0
}
signal_own() {   # signal, pids; each one is checked again right before its signal
    local s=$1 n; shift
    for n in "$@"; do if has_mark "$n" "$MARK" "$HMARK"; then kill "-$s" "$n" 2> /dev/null; fi; done
    return 0
}
# The emulator first: the launcher's EXIT trap then unmounts, as after any run. bc5-mount is never killed; it leaves after
# its unmount (exp 0288). Returns 0 only when nothing of ours is left. Nothing without our mark is ever signalled.
reap() {
    local i p
    for i in $(seq 1 $((REAP_TERM + REAP_KILL))); do
        p=$(own_emus)
        [ -n "$p" ] || break
        # shellcheck disable=SC2086
        if [ "$i" -le "$REAP_TERM" ]; then signal_own TERM $p; else signal_own KILL $p; fi
        nap 1
    done
    [ -z "$(own_emus)" ] || return 1
    for i in $(seq 1 "$REAP_WAIT"); do [ -n "$(own_pids)" ] || return 0; nap 1; done
    for i in $(seq 1 $((REAP_TERM + REAP_KILL))); do
        p=$(own_stuck)
        [ -n "$p" ] || break
        # shellcheck disable=SC2086
        if [ "$i" -le "$REAP_TERM" ]; then signal_own TERM $p; else signal_own KILL $p; fi
        nap 1
    done
    [ -z "$(own_pids)" ]
}
emu_alive() { stat_of "$EP" && [ "$PSTATE" != Z ] && [ "$START" = "$ES" ] && has_mark "$EP" "$MARK"; }
id_alive() {   # file with "pid start"
    local p s
    read -r p s < "$1" 2> /dev/null || return 1
    stat_of "$p" && [ "$PSTATE" != Z ] && [ "$START" = "$s" ]
}
stop_run() {
    local p s
    read -r p s < "$E/run.id" 2> /dev/null || return 0
    if [ "$p" != "$$" ] && id_alive "$E/run.id"; then kill -TERM "$p" 2> /dev/null; fi
    return 0
}

# The two identities the review asks for: the live saves (compared, never restored) and the source lake save.
saves_sum() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
lake_sum() { (cd "$LAKE" && find . -type f -exec md5sum {} + | sort -k2 | md5sum | cut -d' ' -f1); }
pins_why() {   # prints the first pin that does not hold
    [ "$(m "$W/kytyplus-build/src/kyty_emulator")" = "$BIN_MD5" ] || { echo "the binary is not $BIN_MD5"; return; }
    [ "$(m "$W/backend-ubuntu/libbc5_backend.a")" = "$ARCHIVE_MD5" ] || { echo "the archive is not $ARCHIVE_MD5"; return; }
    [ "$(m "$W/play-pkg.sh")" = "$LAUNCHER_MD5" ] || { echo "the launcher is not $LAUNCHER_MD5"; return; }
    [ "$(m "$W/bc5-run.env")" = "$RUN_ENV_MD5" ] || { echo "bc5-run.env is not $RUN_ENV_MD5"; return; }
    local s; s=$(saves_sum)
    [ -n "$s" ] || { echo "the live saves cannot be read"; return; }
    [ -z "$LIVE_SAVES" ] || [ "$s" = "$LIVE_SAVES" ] || { echo "live saves $s, not $LIVE_SAVES: ask the top session"; return; }
    [ -d "$LAKE" ] && [ ! -L "$LAKE" ] || { echo "$LAKE is not a plain directory"; return; }
    [ -z "$(find "$LAKE" -type l -print -quit 2> /dev/null)" ] || { echo "$LAKE holds a link"; return; }
    compress_idle || { echo "the capture compression runs"; return; }
    [ "$(disk_pct)" -lt "$DISK_MAX" ] || { echo "the disk is at $DISK_MAX % or more"; return; }
    dmesg_read > /dev/null 2>&1 || { echo "no dmesg access, the kernel gate would be empty"; return; }
    [ -d "$DATA/captures/devcoredump" ] || { echo "no devcoredump directory, that gate would be empty"; return; }
}

cmd_claim() {
    local why line
    [ ! -e "$E" ] && [ ! -L "$E" ] || die "$E exists: nothing touched"
    [ ! -e "$PRIV" ] && [ ! -L "$PRIV" ] || die "$PRIV exists: nothing touched"
    work_free || die "$WHY"
    hook before-claim
    TOKEN=$(date +%Y%m%d%H%M%S)$$; marks
    DEADLINE=$(($(now) + SERIES_S))
    LOCKLINE="water exp 0385 | K4-K6 lake bench, RT on, build ${BIN_MD5:0:8}, token $TOKEN | until $(date -d "@$DEADLINE" '+%F %T')"
    claim
    own
    why=$(pins_why)
    [ -z "$why" ] || unclaim "$why"
    work_free || unclaim "$WHY"
    hook after-pins
    mkdir "$E" 2> /dev/null || unclaim "$E appeared"
    mkdir -p "$DATA/priv" 2> /dev/null && private_dir "$PRIV" "$EV" 2> /dev/null || unclaim "cannot make $PRIV"
    try_put "$E/token" "$TOKEN" || unclaim "write failed: token"
    try_put "$E/lock.line" "$LOCKLINE" || unclaim "write failed: lock.line"
    try_put "$E/deadline" "$DEADLINE" || unclaim "write failed: deadline"
    try_put "$E/lake.sum" "$(lake_sum)" || unclaim "write failed: lake.sum"
    LIVE_SAVES=$(saves_sum)                     # under the lock, nothing of ours has run: the series holds this one
    [ -n "$LIVE_SAVES" ] && try_put "$E/live.sum" "$LIVE_SAVES" || unclaim "write failed: live.sum"
    try_put "$E/boot.id" "$(boot_id)" || unclaim "write failed: boot.id"
    line="water exp 0385 | claimed: K4-K6 lake bench, RT on, build ${BIN_MD5:0:8}, token $TOKEN, until the deadline $DEADLINE | $(date '+%F %T')"
    queue_try "$line" || unclaim "queue write failed"
    try_put "$ST" claimed || unclaim "write failed: state"
    hook claimed
    echo "TOKEN=$TOKEN"
    echo "kernel $(uname -r); live saves $LIVE_SAVES (C locale); lake save $(cat "$E/lake.sum"); until $(date -d "@$DEADLINE" '+%F %T')"
}

# play-pkg.sh by the exact pin, with its own logs, working directory, save directory and learned copy, and one hook for
# the input configuration. Nothing is taken from older derivatives.
derive_launcher() {
    local src=$W/play-pkg.sh L=$E/play-pkg-0385.sh a
    [ "$(m "$src")" = "$LAUNCHER_MD5" ] || die "the launcher is not $LAUNCHER_MD5"
    cp "$src" "$L" || die "cannot copy the launcher"
    for a in 'done < "$ENVF"' 'LOG=~/bc5-work/play-pkg-last.log' \
        '  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log' \
        'MLOG=~/bc5-work/play-pkg-mount.log' 'cd ~/bc5-work' \
        'export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/_SaveData-pkg-play' \
        'export BC5_DIRECT_LEARNED=$HOME/bc5-work/direct-learned-pkg.txt'; do
        [ "$(grep -cxF -- "$a" "$L")" = 1 ] || die "anchor [$a] is not there exactly once"
    done
    sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0385/play-last.log  \# exp 0385: own log#' \
        -e 's#^\(  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator\) LOG=~/bc5-work/play-pkg-lean-last\.log$#\1 LOG=~/bc5-work/exp0385/play-last.log  \# the same own log#' \
        -e 's#^MLOG=~/bc5-work/play-pkg-mount\.log$#MLOG=~/bc5-work/exp0385/play-pkg-mount.log  \# exp 0385: own mount log#' \
        -e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0385/wd  \# exp 0385: own working directory (its own _SaveData)#' \
        -e 's#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$#export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0385/wd/_SaveData-pkg-play  \# exp 0385: private#' \
        -e 's#^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/direct-learned-pkg\.txt$#export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0385/direct-learned-pkg.txt  \# exp 0385: a private copy#' "$L" || die "sed failed"
    sed -i '/^done < "\$ENVF"$/a [ -n "${BC5_0385_INPUT_CONFIG:-}" ] \&\& export KYTY_BC5_INPUT_CONFIG=$BC5_0385_INPUT_CONFIG  # exp 0385' "$L" || die "sed failed"
    diff -u "$src" "$L" > "$E/play-pkg-0385.diff"
    [ "$(grep -c '^[-+][^-+]' "$E/play-pkg-0385.diff")" = 13 ] || die "the launcher's diff is not 6 lines changed + 1 added"
    for a in '^LOG=~/bc5-work/exp0385/play-last\.log' '^MLOG=~/bc5-work/exp0385/' '^cd ~/bc5-work/exp0385/wd' \
        '^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/exp0385/wd/' '^export BC5_DIRECT_LEARNED=\$HOME/bc5-work/exp0385/' 'BC5_0385_INPUT_CONFIG'; do
        grep -q -- "$a" "$L" || die "the derived launcher lacks $a"
    done
    ! grep -Eq 'LOG=~/bc5-work/play-pkg(-lean|-mount)?(-last)?\.log' "$L" || die "a log of the launcher is still shared"
    bash -n "$L" || die "the derived launcher does not parse"
    chmod +x "$L" || die "chmod failed"
}
# s6n-d19.sh's layout: exp 0330's links copied as they are, and two new, empty save directories. Links are only read: the
# one thing ever deleted under here is own_rm's save copy, and every link must point into the work directory.
make_wd() {
    local src=$W/exp0330/wd
    [ -d "$src" ] && [ ! -L "$src" ] || die "no $src to take the layout from"
    [ ! -e "$WD" ] && [ ! -L "$WD" ] || die "$WD exists"
    [ -z "$(find "$src" -mindepth 1 -maxdepth 1 ! -type l ! -name _SaveData ! -name _SaveData-pkg-play)" ] || die "$src has entries that are not links"
    mkdir "$WD" "$WD/_SaveData" "$WD/_SaveData-pkg-play" || die "cannot make $WD"
    find "$src" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play -exec cp -P -t "$WD" {} + || die "the links could not be copied"
    [ "$(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l)" = "$(find "$src" -mindepth 1 -maxdepth 1 -type l ! -name _SaveData ! -name _SaveData-pkg-play | wc -l)" ] || die "the wd link count differs from $src"
    [ -z "$(find "$WD" -mindepth 1 -maxdepth 1 -type l ! -lname "$W/*" -print -quit)" ] || die "a wd link points outside $W"
    find "$WD" -mindepth 1 -maxdepth 1 -type l -printf '%f %l\n' | sort | sha256sum | cut -d' ' -f1 > "$E/wd-links.sha256" || die "write failed"
}
cmd_setup() {
    load "${1:-}"
    [ "$(state)" = claimed ] || die "state is $(state), want claimed"
    own; budget "$GRACE"
    [ -z "$(foreign_emus)" ] || die "an emulator that is not ours runs"
    hook before-setup
    (cd "$E" && sha256sum -c --quiet kit.sha256) > "$E/kit.check" 2>&1 || die "the kit is not what was sent: $(cut -c1-120 "$E/kit.check")"
    derive_launcher
    make_wd
    grep -qxF 'RayTracing.PPSA03671=on' "$E/input-0385.cfg" && grep -qxF 'MangoHud.PPSA03671=off' "$E/input-0385.cfg" || die "input-0385.cfg is not RT on, MangoHud off"
    cp -p "$W/direct-learned-pkg.txt" "$E/direct-learned-pkg.txt" || die "cannot copy the learned file"
    m "$W/direct-learned-pkg.txt" > "$E/learned.md5"
    { echo "kernel $(uname -r)"; echo "bc5-mount $(m "$W/bc5-tools-ubuntu/release/bc5-mount")"; echo "learned $(cat "$E/learned.md5")"
      echo "wd links $(cat "$E/wd-links.sha256")"; echo "lake save $(cat "$E/lake.sum")"; } > "$E/inputs.txt" || die "write failed"
    atime_ok || die "noatime: the route save read cannot be shown"
    in_box 60 python3 -I "$E/tz0385.py" --selftest "$E/swz0248-z4.json" > "$E/selftest.txt" 2>&1 || die "tz0385.py's self-test failed"
    own
    hook before-watch
    session bash "$SELF" watch "$TOKEN" < /dev/null >> "$E/watch.log" 2>&1 &
    local i
    for i in $(seq 1 "$WATCH_WAIT"); do id_alive "$E/watch.id" && break; nap 0.2; done
    id_alive "$E/watch.id" || die "the watchdog did not start"
    own
    set_state setup || die "state is $(state)"
    echo "set up: launcher $(m "$E/play-pkg-0385.sh"), wd $(find "$WD" -mindepth 1 -maxdepth 1 -type l | wc -l) links, watchdog running"
}
# The private backend with this experiment's switches, its Catch2 tests, then the shared normal build's link command with
# the private archive in place of the shared one (relink0385.py). No host unit changes and the backend's public headers keep
# their ABI, so nothing else is compiled. The shared objects, archive and binary are only read.
cmd_build() {
    load "${1:-}"
    [ "$(state)" = setup ] || die "state is $(state), want setup"
    own; budget $((BUILD_S + GRACE))
    work_free || die "$WHY"
    (cd "$E" && sha256sum -c --quiet tb.sha256) > "$E/tb.check" 2>&1 || die "testbuild.tar is not what was sent"
    mkdir "$TB" "$TB/in" "$TB/raw" 2> /dev/null || die "cannot make $TB"
    tar xf "$E/testbuild.tar" -C "$TB/in" || die "cannot unpack testbuild.tar"
    hook before-build
    local catch arg="" bcache=$W/backend-ubuntu/CMakeCache.txt bt cxx
    catch=$(find "$W" -maxdepth 4 -type d -path '*/backend-build/_deps/catch2-src' -print -quit 2> /dev/null)
    [ -z "$catch" ] || arg="-DFETCHCONTENT_SOURCE_DIR_CATCH2=$catch"
    bt=$(sed -n 's/^CMAKE_BUILD_TYPE:[A-Z]*=//p' "$bcache" 2> /dev/null); cxx=$(sed -n 's/^CMAKE_CXX_COMPILER:[A-Z]*=//p' "$bcache" 2> /dev/null)
    [ -n "$bt" ] && [ -n "$cxx" ] || die "cannot read the shared archive's configuration"
    in_box "$BUILD_S" sh -c "nice -n 19 cmake -S '$TB/in' -B '$TB/build' -G Ninja -DCMAKE_BUILD_TYPE=$bt -DCMAKE_CXX_COMPILER=$cxx -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON $arg && nice -n 19 cmake --build '$TB/build' -j8" > "$TB/raw/backend-build.out" 2>&1 || die "the private backend did not build: $(grep -m3 'error:' "$TB/raw/backend-build.out" | cut -c1-160 | tr '\n' ' ')"
    in_box 120 sh -c "cd '$TB/build' && nice -n 19 ./bc5_backend_tests" > "$TB/raw/backend-tests.out" 2>&1 || die "the backend's tests failed: no emulator linked"
    own
    in_box 60 sh -c "cd '$W/kytyplus-build' && ninja -t compdb -x" > "$TB/compdb.json" 2> "$TB/raw/compdb.err" || die "no compile database"
    in_box 300 python3 -I "$E/relink0385.py" "$TB/compdb.json" "$W/kytyplus-build" "$W/backend-ubuntu/libbc5_backend.a" "$TB/build/libbc5_backend.a" "$TB_BIN" > "$TB/raw/link.out" 2>&1 || die "the private link failed"
    [ -x "$TB_BIN" ] || die "no private binary"
    grep -aq BC5_DIRECT_LAKE_CTL "$TB_BIN" || die "the private binary has no lake switches"
    local why; why=$(pins_why)
    [ -z "$why" ] || die "$why"
    try_put "$E/tb.md5" "$(m "$TB_BIN")" || die "write failed: tb.md5"
    own
    set_state ready || die "state is $(state)"
    echo "built: private binary $(rd "$E/tb.md5"), tb/ $(du -sh "$TB" | cut -f1), shared binary and archive unchanged"
}

# Only these three trees are ever deleted, each only if it is what it says: a plain directory of ours, at its canonical
# place under a plain root, with no link and no foreign file inside, on one file system.
own_rm() {
    local p=$1 root rel base
    case "$p" in
        "$WD/_SaveData/PPSA03671") base=$E; rel=wd/_SaveData/PPSA03671 ;;
        "$E"/r-K[0-9]/shots) base=$E; rel=${p#"$E"/} ;;
        "$PRIV"/K[0-9]) base=$PRIV; rel=${p#"$PRIV"/} ;;
        *) WHY="refusing to delete $p"; return 1 ;;
    esac
    [ -d "$base" ] && [ ! -L "$base" ] || { WHY="$base is not a plain directory"; return 1; }
    root=$(readlink -f "$base")
    [ -d "$p" ] && [ ! -L "$p" ] || { WHY="$p is not a plain directory"; return 1; }
    [ "$(readlink -f "$p")" = "$root/$rel" ] || { WHY="$p leaves $root"; return 1; }
    [ "$(stat -c %u "$p")" = "$(id -u)" ] || { WHY="$p is not ours"; return 1; }
    [ -z "$(find "$p" -xdev \( -type l -o ! -uid "$(id -u)" \) -print -quit 2> /dev/null)" ] || { WHY="$p holds a link or a foreign file"; return 1; }
    rm -rf --one-file-system -- "$p" || { WHY="cannot delete $p"; return 1; }
    [ ! -e "$p" ] || { WHY="$p is still there"; return 1; }
}
reset_saves() {
    local d=$WD/_SaveData/PPSA03671
    if [ -e "$d" ] || [ -L "$d" ]; then own_rm "$d" || return 1; fi
    cp -a "$LAKE" "$d" 2> /dev/null && diff -rq "$LAKE" "$d" > /dev/null 2>&1 || { WHY="the lake save could not be put into $d"; return 1; }
    # the route proof: a read after the start moves these
    find "$d" -type f -exec touch -a -d '2020-01-01 00:00:00' {} + || { WHY="cannot set the access times in $d"; return 1; }
}

halt() {   # the series stops here. Nothing is deleted; the lock stays for release
    echo "0385 STOP: $*"
    series_stop "$TAG: $*"
    reap || echo "0385 STOP: processes of ours remain: $(own_pids | tr '\n' ' ')"
    exit 1
}
on_exit() {
    local rc=$?
    trap - EXIT
    if [ "$(state)" = running ]; then
        echo "0385 STOP: the run ended unfinished, exit $rc"
        series_stop "$TAG: the run ended unfinished, exit $rc"
        reap
    fi
    exit "$rc"
}
next_tag() {
    local t
    for t in $TAGS; do [ -e "$E/r-$t" ] || { echo "$t"; return; }; done
}
kernel_new() {   # dmesg line count at the start; 1 if the log cannot be read
    local all
    all=$(dmesg_read) || return 1
    printf '%s\n' "$all" | tail -n +"$(($1 + 1))" | grep -iE "$KPAT"
    return 0
}
count() { local n; n=$(grep -ac -- "$1" "$2"); [ $? -le 1 ] && echo "$n"; }
# The journal of this run: the directory in this emulator's own environment, not the newest one on the box.
journal_facts() {
    local tag=$1 t0=$2 d j
    d=$(tr '\0' '\n' < "$EV/$tag-environ.bin" 2> /dev/null | sed -n 's/^BC5_GC_DUMP_DIR=//p' | head -1)
    j=$d/direct.log
    {
        echo "path $j"
        case "$(readlink -f "$d" 2> /dev/null)" in
            "$(readlink -f "$DATA/captures")"/play-*/gc) ;;
            *) echo "why the journal directory is not this run's capture directory"; return ;;
        esac
        if [ ! -f "$j" ] || [ -L "$j" ] || [ ! -r "$j" ]; then echo "why no readable journal"; return; fi
        [ "$(stat -c %Y "$j")" -ge "$t0" ] || { echo "why a stale journal"; return; }
        echo "rtoff $(count 'ray tracing off:' "$j")"
        echo "skip $(count 'skip pgm' "$j")"
        echo "timeouts $(count TIMEOUT "$j")"
        echo "flips $(count 'VideoOutSubmitFlip took' "$j")"
        echo "bytes $(stat -c %s "$j")"
    } > "$E/$tag.journal.txt"
}
analyse() {   # every step's status counts
    local t=$1 c; c=$PRIV/$t
    [ -s "$c/events.txt" ] && [ -s "$c/snaps.txt" ] || { echo "no poll log"; return 1; }
    bash "$E/bt0362.sh" "$c/events.txt" > "$E/$t.bursts.txt" || { echo "bt0362.sh failed"; return 1; }
    [ -s "$E/$t.bursts.txt" ] || { echo "no bursts"; return 1; }
    in_box "$ANA_S" python3 -I "$E/sn0385.py" reads "$c" "$E/swz0248-z4.json" "$E/$t.reads.json" > "$E/$t.reads.txt" 2>&1 || { echo "sn0385.py failed"; return 1; }
    [ -s "$E/$t.reads.json" ] || { echo "no reads.json"; return 1; }
    in_box "$ANA_S" python3 -I "$E/tz0385.py" "$c" "$E/$t.reads.json" "$E/swz0248-z4.json" > "$E/$t.tz.txt" 2>&1 || { echo "tz0385.py failed"; return 1; }
    gzip -c "$c/events.txt" > "$E/$t.events.txt.gz" || { echo "gzip failed"; return 1; }
    cp "$c/snaps.txt" "$E/$t.snaps.txt" || { echo "cp failed"; return 1; }
}
files_of() {
    local t=$1
    echo "$t.out $t.pl.txt $t.start.txt $t.manifest.txt $t.journal.txt $t.kernel.txt $t.saves.txt $t.route.txt $t.dmesg.txt"
    echo "$t.patch.txt $t.bursts.txt $t.reads.txt $t.reads.json $t.tz.txt $t.events.txt.gz $t.snaps.txt $t.gates.txt"
    echo "$t.arms.txt $t.armlog.txt $t.switches.txt $t.zp.txt"
    echo "play-pkg-0385.diff input-0385.cfg inputs.txt arms0385.txt tb.md5"
}
pack() {   # strict: every file, or no pass and no cleanup
    local t=$1 f n
    (
        cd "$E" || exit 1
        # shellcheck disable=SC2046
        bundle "$t.raw.tar" $(files_of "$t") || exit 1
        n=$(tar tf "$t.raw.tar" | wc -l)
        [ "$n" = "$(files_of "$t" | wc -w)" ] || exit 1
    ) 2> "$E/$t.pack.err" || return 1
    sha256sum "$E/$t.raw.tar" | cut -d' ' -f1 > "$E/$t.raw.sha256"
    [ -s "$E/$t.raw.sha256" ]
}

cmd_run() {
    load "${1:-}"
    local tag=${2:-} next why R C T0 N BP PP brc=0 prc=0 end kern="" lost=0 foreign=0 died=0 capped=0 full=0 read_ok=1 s qual rc=0 ana=0 i p
    TAG=$tag
    next=$(next_tag)
    [ -n "$next" ] || die "no attempts left"
    [ "$tag" = "$next" ] || die "the next tag is $next, not $tag"
    [ "$(state)" = ready ] || die "state is $(state), want ready"
    own
    budget $((RUN_S + GRACE))
    id_alive "$E/watch.id" || die "the watchdog is gone"
    [ -z "$(own_pids)" ] || die "processes of ours run: $(own_pids | tr '\n' ' ')"
    work_free || die "$WHY"
    why=$(pins_why)
    [ -z "$why" ] || die "$why"
    [ "$(lake_sum)" = "$(cat "$E/lake.sum")" ] || die "the lake save changed"
    local tb; tb=$(rd "$E/tb.md5")
    [ -n "$tb" ] && [ "$(m "$TB_BIN")" = "$tb" ] || die "the private binary is not the one built"
    N=$(dmesg_read | wc -l)
    R=$E/r-$tag; C=$PRIV/$tag
    mkdir "$R" 2> /dev/null || die "$R exists"    # the attempt is used from here on
    mkdir "$R/shots" && private_dir "$C" || die "cannot make the run directories"
    # in this order: the watchdog reads running as "the process in run.id is alive"
    put "$E/run.id" "$$ $(stat_of $$; echo "$START")"
    set_state running || die "state is $(state)"
    trap '' HUP PIPE    # a dropped ssh or a dead reader must not end the run or its clean-up
    trap on_exit EXIT
    trap 'halt "a signal during the run"' INT TERM
    exec > >(tee -p "$E/$tag.run.log") 2>&1
    echo "== $tag $(date +%T), $(left) s to the deadline"
    hook before-reset
    own_q || halt "the lock is not ours"
    reset_saves || halt "$WHY"
    printf 'wait 90000\npress cross\n' > "$R/input.cmd"
    hook before-launch
    own_q || halt "the lock is not ours"
    T0=$(now); put "$R/t0" "$T0"
    end=$((T0 + EMU_S)); [ "$end" -le $((DEADLINE - GRACE)) ] || end=$((DEADLINE - GRACE))
    put "$E/run.end" "$end"
    session bash -c '"$@"; echo "launcher exit $?"' _ "${DBX[@]}" env "$MARK" "KYTY_BC5_INPUT_CMD=$R/input.cmd" \
        "BC5_0385_INPUT_CONFIG=$E/input-0385.cfg" "BC5_EMU=$TB_BIN" "BC5_DIRECT_LAKE_CTL=$R/lake.ctl" \
        "BC5_DIRECT_LAKE_OUT=$C/zpass.dat" "$E/play-pkg-0385.sh" < /dev/null > "$R/launcher.out" 2>&1 &
    for i in $(seq 1 "$EMU_WAIT"); do
        p=$(own_emus)
        [ -z "$p" ] || break
        nap 1
    done
    [ -n "$p" ] || halt "no emulator of ours started"
    [ "$(echo "$p" | wc -l)" = 1 ] || halt "more than one emulator of ours: $(echo "$p" | tr '\n' ' ')"
    EP=$p; stat_of "$EP" || halt "the emulator is gone"
    ES=$START
    put "$R/emu.id" "$EP $ES"
    [ "$(md5sum < "/proc/$EP/exe" | cut -d' ' -f1)" = "$tb" ] || halt "the emulator is not the private binary $tb"
    [ "$(readlink -f "/proc/$EP/cwd")" = "$(readlink -f "$WD")" ] || halt "the emulator's working directory is not $WD"
    (umask 077; set -C; cat "/proc/$EP/environ" > "$EV/$tag-environ.bin") || halt "the emulator's environment could not be saved"
    {
        echo "arm $tag, token $TOKEN, t0 $T0, boot $(boot_id | cut -c1-8)"
        echo "emulator pid $EP start $ES exe $(readlink "/proc/$EP/exe") cwd $(readlink "/proc/$EP/cwd")"
        echo "environ capture bytes $(stat -c %s "$EV/$tag-environ.bin") sha256 $(sha256sum < "$EV/$tag-environ.bin" | cut -d' ' -f1)"
    } > "$E/$tag.start.txt"
    "${PY[@]}" "$E/gates0385.py" manifest "$EV/$tag-environ.bin" "$TOKEN" "$tag" > "$E/$tag.manifest.txt" 2>&1 \
        || halt "the effective options are not the plan's: $(grep -v '^[A-Za-z_0-9]*=' "$E/$tag.manifest.txt" | head -3 | cut -c1-160 | tr '\n' ' ')"
    hook after-manifest
    env "$HMARK" bash "$SELF" bench "$TOKEN" "$tag" > "$E/$tag.out" 2>&1 &
    BP=$!
    poller "$tag" 85 "$C" 212 2.0 6 "$EP" "$ES" "$E/lock.line" > "$E/$tag.pl.txt" 2>&1 &
    PP=$!
    while :; do
        kill -0 "$BP" 2> /dev/null || break
        if ! s=$(kernel_new "$N"); then kern="the kernel log cannot be read"; break; fi
        [ -z "$s" ] || { kern=$s; break; }
        own_q || { lost=1; break; }
        [ -z "$(foreign_emus)" ] || { foreign=1; break; }
        [ "$(disk_pct)" -lt "$DISK_STOP" ] || { full=1; break; }
        [ "$(now)" -lt "$end" ] || { capped=1; break; }
        # the watchdog stops it at the same limit: gone at that time is the limit, not a crash
        if ! emu_alive; then
            if [ "$(now)" -ge "$end" ]; then capped=1; else died=1; fi
            break
        fi
        nap 3
    done
    hook after-watch-loop
    [ -z "$kern" ] || echo "$tag: kernel lines, stopping the run: $(echo "$kern" | head -3 | cut -c1-160)"
    put "$E/run.end" 0
    cp "$E/play-last.log" "$R/emu.log" 2> /dev/null
    reap || halt "processes of ours remain: $(own_pids | tr '\n' ' ')"
    cp "$E/play-last.log" "$R/emu.log" 2> /dev/null
    wait "$BP"; brc=$?
    wait "$PP"; prc=$?
    echo "bench exit $brc, poller exit $prc $(date +%T)"
    grep -a "fps counter" "$R/emu.log" 2> /dev/null | tail -1 | cut -c1-90 >> "$E/$tag.out"
    [ -z "$kern" ] || halt "kernel lines: no analysis, nothing deleted"
    [ "$lost" = 0 ] || halt "the lock stopped being ours during the run"
    [ "$foreign" = 0 ] || halt "an emulator that is not ours appeared during the run"
    [ "$full" = 0 ] || halt "the disk reached $DISK_STOP %: nothing deleted"
    [ "$died" = 0 ] || halt "the emulator ended by itself"
    s=$(kernel_new "$N") || halt "the kernel log cannot be read at the end"
    [ -z "$s" ] || halt "kernel lines at the end: nothing deleted"
    { dmesg_read | tail -n +"$((N + 1))"; } > "$E/$tag.dmesg.txt" 2> /dev/null
    {
        echo "lines 0"
        echo "devcoredumps $(find "$DATA/captures/devcoredump" -maxdepth 1 -type f -newermt "@$T0" 2> /dev/null | wc -l)"
    } > "$E/$tag.kernel.txt"
    {
        s=$(saves_sum); echo "live $s want $LIVE_SAVES"
        s=$(lake_sum); echo "lake $s want $(cat "$E/lake.sum")"
        echo "learned $(m "$W/direct-learned-pkg.txt") want $(cat "$E/learned.md5")"
    } > "$E/$tag.saves.txt"
    journal_facts "$tag" "$T0"
    save_read_since "$WD/_SaveData/PPSA03671" "$T0" || read_ok=0
    { echo "bench_rc $brc"; echo "poller_rc $prc"; echo "save_read $read_ok"; echo "capped $capped"; } > "$E/$tag.route.txt"
    "${PY[@]}" "$E/gates0385.py" check "$E" "$tag" pre > "$E/$tag.gates.txt" 2>&1; rc=$?
    case "$rc" in
        0) ;;
        10) echo "RESULT $tag: route failure, the attempt is used, evidence kept"; tail -1 "$E/$tag.gates.txt"
            set_state "$( [ -n "$(next_tag)" ] && echo ready || echo done )" || true
            exit 10 ;;
        *) halt "$(tail -1 "$E/$tag.gates.txt" | cut -c1-200)" ;;
    esac
    # shellcheck disable=SC2086
    in_box 60 python3 "$E/patch0385.py" "$R"/shots/*-ts*.png > "$E/$tag.patch.raw" 2>&1 || ana=1
    sed "s|$R/shots/||" "$E/$tag.patch.raw" > "$E/$tag.patch.txt"
    if [ "$ana" = 0 ]; then analyse "$tag" > "$E/$tag.ana.log" 2>&1 || ana=1; fi
    echo "ana_rc $ana" >> "$E/$tag.route.txt"
    hook before-gates
    "${PY[@]}" "$E/gates0385.py" check "$E" "$tag" post > "$E/$tag.gates.txt" 2>&1; rc=$?
    tail -2 "$E/$tag.gates.txt" | cut -c1-200
    case "$rc" in
        0) ;;
        10) echo "RESULT $tag: route failure, the attempt is used, evidence kept"
            set_state "$( [ -n "$(next_tag)" ] && echo ready || echo done )" || true
            exit 10 ;;
        *) halt "the gates: $(tail -1 "$E/$tag.gates.txt" | cut -c1-200)" ;;
    esac
    # the arms and the catcher: what they say is the result, but a failed summary loses nothing else
    grep -a 'experiment 0385' "$R/emu.log" > "$E/$tag.switches.txt" 2> /dev/null || echo "no switch lines" > "$E/$tag.switches.txt"
    "${PY[@]}" "$E/gates0385.py" arms "$E/$tag.patch.txt" "$E/arms0385.txt" "$E/$tag.switches.txt" > "$E/$tag.arms.txt" 2>&1 || echo "no arm table" >> "$E/$tag.arms.txt"
    cp "$R/arms.log" "$E/$tag.armlog.txt" 2> /dev/null || : > "$E/$tag.armlog.txt"
    if [ -s "$C/zpass.dat" ]; then
        "${PY[@]}" "$E/zp0385.py" "$C/zpass.dat" "$C/zpass.dat.meta" > "$E/$tag.zp.txt" 2>&1 || echo "zp0385.py failed" >> "$E/$tag.zp.txt"
    else
        echo "no zpass records" > "$E/$tag.zp.txt"
    fi
    hook before-pack
    pack "$tag" || halt "the summaries could not be packed: nothing deleted"
    hook before-clean
    own_q || halt "the lock stopped being ours: nothing deleted"
    du -sh "$C" "$R/shots" 2> /dev/null | cut -f1 | tr '\n' ' '; ls "$R/shots" | wc -l
    own_rm "$C" || halt "$WHY"
    own_rm "$R/shots" || halt "$WHY"
    echo "deleted snapshots and shots (unviewed)"
    qual=$(sed -n 's/^.* qualify \(yes\|no\)$/\1/p' "$E/$tag.gates.txt" | tail -1)
    if [ "$qual" = yes ] || [ -z "$(next_tag)" ]; then set_state done || true; else set_state ready || true; fi
    hook run-done
    echo "RESULT $tag: $(tail -1 "$E/$tag.gates.txt" | cut -c1-120), raw sha256 $(cat "$E/$tag.raw.sha256"), state $(state), $(left) s left"
}

# The route of exps 0194 and 0293 and the shots. No process is looked up and none is stopped here. Exit 0 only with every
# shot taken.
cmd_bench() {
    load "${1:-}"
    local tag=${2:-} R n k T0 a b
    local -A arm=()
    R=$E/r-$tag
    while IFS='|' read -r a b; do
        case $a in "" | \#*) ;; *) arm[$a]=$b ;; esac
    done < "$E/arms0385.txt"
    read -r EP ES < "$R/emu.id" || die "no emulator id"
    T0=$(rd "$R/t0"); [ -n "$T0" ] || die "no start time"
    gone() { emu_alive && [ $(($(now) - T0)) -lt "$BENCH_S" ] && return 1; echo "== $tag: the emulator ended or the time ran out at $(date +%T)"; return 0; }
    done_n() { local x; x=$(rd "$R/input.cmd.done"); echo "${x:-0}"; }
    step() {   # append lines, wait until all are done
        gone && return 1
        local c add; c=$(done_n)
        printf "$1" >> "$R/input.cmd"
        add=$(printf "$1" | grep -c "")
        for _ in $(seq 1 120); do [ "$(done_n)" -ge $((c + add)) ] && return 0; gone && return 1; nap 0.5; done
        echo "step timed out: $1"; return 1
    }
    snap() { local t; printf -v t '%(%H%M%S)T' -1; shot "$R/shots/$t-$1.png"; }
    route() {
        for _ in $(seq 1 "$KEYWAIT"); do [ "$(done_n)" -ge 2 ] && break; gone && return 1; nap 2; done
        [ "$(done_n)" -ge 2 ] || { echo "the first keys were not taken"; return 1; }
        for _ in $(seq 1 "$SLOTWAIT"); do gone && return 1; nap 1; done
        step "press down\nwait 700\npress down\nwait 900\n" || return 1
        snap slot
        step "press cross\nwait 3500\n" || return 1
        step "press down\nwait 800\npress cross\nwait 1500\n" || return 1
        for _ in $(seq 1 "$LOADWAIT"); do gone && return 1; nap 1; done
        snap game
        step "press options\nwait 1300\npress down\nwait 400\npress down\nwait 400\npress down\nwait 400\npress down\nwait 600\npress cross\nwait 3000\npress triangle\nwait 1500\n" || return 1
        step "stick r 0 128 1600\nwait 300\ntrigger r2 255 1500\nwait 300\nstick r 128 255 350\nwait 900\n" || return 1
        # a switch goes in one step before its shot, so the shot shows its effect
        for k in $(seq -w 0 $((SERIES - 1))); do
            gone && return 1
            n=$((10#$k))
            if [ -n "${arm[$n]+x}" ]; then
                try_put "$R/lake.ctl" "${arm[$n]}" || { echo "cannot write the switches"; return 1; }
                echo "$n $(now) ${arm[$n]}" >> "$R/arms.log"
            fi
            nap $((STEP - 1))
            snap "ts$k"
        done
    }
    route; n=$?
    echo "== $tag route exit $n, shots done $(date +%T)"
    [ "$n" = 0 ] || exit 3
    n=$(find "$R/shots" -maxdepth 1 -type f -name '*-ts*.png' -size +0 | wc -l)
    [ "$n" = "$SERIES" ] || { echo "$n of $SERIES shots"; exit 3; }
}

watch_tick() {   # 1 when the watchdog is done
    local s n e
    s=$(state)
    hook tick-read
    [ "$s" != released ] || return 1
    n=$(now)
    if ! own_q; then
        series_stop "watchdog: the lock is not ours"
        stop_run; reap
        return 1
    fi
    if [ "$n" -ge "$DEADLINE" ]; then
        series_stop "watchdog: the deadline"
        do_release "the watchdog at the deadline"
        return 1
    fi
    if [ "$n" -ge $((DEADLINE - GRACE)) ]; then
        series_stop "watchdog: the deadline is near"
        stop_run; reap
        return 0
    fi
    if [ "$s" = running ]; then
        if ! id_alive "$E/run.id"; then
            # it may just have ended: a run sets its state before it exits
            [ "$(state)" = running ] || return 0
            series_stop "watchdog: the run is gone"
            reap
            return 0
        fi
        e=$(rd "$E/run.end")
        case "$e" in "" | 0 | *[!0-9]*) ;; *) if [ "$n" -ge "$e" ]; then echo "watchdog: stopping the emulator at $(date +%T)"; reap; fi ;; esac
    fi
    return 0
}
cmd_watch() {
    load "${1:-}"
    put "$E/watch.id" "$$ $(stat_of $$; echo "$START")"
    while watch_tick; do nap "$WATCH_NAP"; done
    echo "watchdog ends $(date +%T), state $(state)"
}
do_release() {
    local line sum
    [ "$(state)" != released ] || { echo "released already"; return 0; }
    mkdir "$E/release.claim" 2> /dev/null || { echo "a release runs, or $E/release.claim was left behind"; return 1; }
    series_stop "release: $1"
    stop_run
    if ! reap; then
        rmdir "$E/release.claim"
        echo "our processes do not stop, the lock stays: $(own_pids | tr '\n' ' ')"
        return 1
    fi
    if [ -L "$LOCK" ] || [ ! -f "$LOCK" ] || ! grep -qxF -- "$LOCKLINE" "$LOCK"; then
        rmdir "$E/release.claim"
        echo "no line of ours in $LOCK, left as it is: $(cat "$LOCK" 2> /dev/null)"
        return 1
    fi
    sum=$(saves_sum)
    line="water exp 0385 | released: $1, live saves ${sum:-unreadable} (C locale), token $TOKEN | $(date '+%F %T')"
    hook before-release-queue
    if ! queue_try "$line"; then rmdir "$E/release.claim"; echo "queue write failed, the lock stays"; return 1; fi
    if ! lock_remove; then rmdir "$E/release.claim"; echo "$WHY"; return 1; fi
    try_put "$ST" released
    rmdir "$E/release.claim"
    echo "released, live saves ${sum:-unreadable}"
}
cmd_kstream() {
    load "${1:-}"
    local jp
    timeout "$(left)" "${KS[@]}" & jp=$!
    while [ "$(left)" -gt 0 ] && grep -qxF -- "$LOCKLINE" "$LOCK" 2> /dev/null; do nap 5; done
    nap 5
    kill "$jp" 2> /dev/null
    wait "$jp" 2> /dev/null
    return 0
}
cmd_status() {
    load "${1:-}"
    echo "state $(state); $(left) s to the deadline; next tag $(next_tag); lock ours $(own_q && echo yes || echo no)"
    echo "own: $(own_pids | tr '\n' ' ')"; echo "other emulators: $(foreign_emus | tr '\n' ' ')"
    echo "watchdog $(id_alive "$E/watch.id" && echo alive || echo gone); stop log: $(tail -1 "$E/stop.log" 2> /dev/null)"
    echo "--- BOX-LOCK:"; cat "$LOCK" 2> /dev/null
}

[ "$TESTING" = 0 ] || . "$BC5_0385_FAKE"
case "${1:-}" in
    claim) cmd_claim ;;
    setup) cmd_setup "${2:-}" ;;
    build) cmd_build "${2:-}" ;;
    run) cmd_run "${2:-}" "${3:-}" ;;
    bench) cmd_bench "${2:-}" "${3:-}" ;;
    kstream) cmd_kstream "${2:-}" ;;
    status) cmd_status "${2:-}" ;;
    stop) load "${2:-}"; series_stop "the stop command"; stop_run; reap || die "processes of ours remain: $(own_pids | tr '\n' ' ')"; echo "stopped" ;;
    release) load "${2:-}"; do_release "${3:-the release command}" ;;
    watch) cmd_watch "${2:-}" ;;
    tick) load "${2:-}"; watch_tick; echo "tick $?, state $(state)" ;;
    # one real function by name, for the tests only
    call) [ "$TESTING" = 1 ] || { echo "call is for the tests"; exit 2; }
        load "${2:-}"; f=${3:-}; shift 3; "$f" "$@"; rc=$?; echo "WHY=$WHY"; exit "$rc" ;;
    *) echo "usage: box0385.sh claim|setup|run|bench|kstream|status|stop|release|watch|tick ..."; exit 2 ;;
esac
