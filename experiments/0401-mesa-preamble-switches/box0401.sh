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
    d) SER=d; EXPECT_UNIT=0f18cf30cb85843cdbe9d5df68909e3d; MKFLAG=--acb-restore ;;
    e) SER=e; EXPECT_UNIT=0d65c14d3705887717bac71dd97e05ab; MKFLAG="--acb-restore --catcher" ;;
    e2) SER=e2; EXPECT_UNIT=73e8e4e0a9d05e5deae426238a24c91d; MKFLAG="--acb-restore --catcher --inherit" ;; # e + exp 0403's ACB_INHERIT
    e4) SER=e4; EXPECT_UNIT=d3b7f9b0ab43184ee11de83e9e233ff8; MKFLAG="--acb-restore --catcher --inherit3 --memline" ;; # e3 + exp 0402 items
    e3) SER=e3; EXPECT_UNIT=d3b7f9b0ab43184ee11de83e9e233ff8; MKFLAG="--acb-restore --catcher --inherit3 --memline" ;; # e2 with exp 0403's queue mode (addendum a423f761) + the memory line
    e5) SER=e5; EXPECT_UNIT=d3b7f9b0ab43184ee11de83e9e233ff8; MKFLAG="--acb-restore --catcher --inherit3 --memline" ;; # e4 + exp 0405's ports
    *) echo "0401 STOP: unknown series ${BC5_0401_SERIES}"; exit 2 ;;
esac
# Series d (2026-11-03 13:52): series c's edit on exp 0379's zero skip, the unit and header of exp 0388's 902585e2 build
# (main's unit plus 0388's patch-z-bc5LleAgc.diff), read from exp0388/z under these pins and copied into exp0401d.
ZDIR=$W/exp0388/z/src/src; ZUNIT_MD5=3a77e0acef307865d1cd524951060422; ZHDR_MD5=b29c66c4bc9d5bccb8aac233b3843414
# Series e (2026-11-03 16:4x, the top session's GO on the maintainer's "Buduj"; exp 0402 items 1, 4, 5): series c's unit plus
# the table catcher (mkunit0401.py --catcher), and three more private units from the same tree: libNpCppWebApi.cpp with the
# ten SessionManager V2 exports (mknp0401.py), memory.cpp and systemContent.cpp with the param.json sizing (mkmem0401.py,
# whose edited systemContent.h goes first on the include path). The R32 gate (npgate0401.cpp) runs on and off after the link.
NP_IN_MD5=7c40b784e36ef45e816be07b0a3fb0a8; NP_OUT_MD5=935fcc7e4ab1108f3d2d8b33eaf65bf6
MEM_IN_MD5=f61546925dcf96ee9bbc1278b0f8ae6c; MASINC_MD5=44586b1ee0e7edf12a0cd293ff9c141f; SC_IN_MD5=7121c22ca8b893ac37fbeabde48b4a6b; SCH_IN_MD5=8890c158627f20f59ee55205e73d36c3
MEM_OUT_MD5=43713ef677ec887a8ca273f7ab5cee90; SC_OUT_MD5=4e33b30a4acf89481942cec435b76c37; SCH_OUT_MD5=2b2b21eb1faf35c2a538917049aea85e
# Series e4 (2026-11-03 22:3x, the top session's GO on the maintainer's "buduj dodatkowo 3,9,2,7,10 o ile sami tego już nie
# poprawialiśmy"): series e3's binary plus exp 0402's items that were missing here, each its own script, unit(s) and switch,
# default off. Under the maintainer's rule of 23:0x (judge ports for any title), items 7 and 10 are ported too. Each E4_EDITS row: tag, script, then
# relpath:tree md5:output md5 for every unit the script writes (under exp0401e4/x-<tag>/). Each E4_GATES row: test source,
# the unit whose compile command builds it, its switch (or a comma list, set together), the run's name, and the program's
# name when it differs (one program, built once, run per switch); it runs with the switch 1 ("on"), 0 and unset
# ("off"), each in a fresh directory of its own, with KYTY_BC5_SAVEDATA_DIR and KYTY_BC5_SAVE_TRACE unset.
E4_EDITS=(
    "sav mksav0401.py src/libs/libSaveData.cpp:d6e9c37fa099d576ce4c495dab850271:04f4c5bb05179b80fd7cf1e41832cdd9"
    "pth mkpth0401.py src/kernel/pthread.cpp:11cef59e0ff15f650eba98bb11f91bce:0363847bd540883467dee22797475031"
    "aud mkaud0401.py src/libs/libAudio2.cpp:fb44443e6f19f5d62c739cb39a7c377c:7a1914c898e62e1e6ce699807aafbc74"
    "vo mkvo0401.py src/graphics/presentation/videoOut.cpp:f848f5c6b81196e9722f3c7caf3984ec:3fa490f762fb6a9612289ef3a4018150"
    "amm mkamm0401.py src/libs/libAmpr.cpp:a0e2ff6e6fcbcae83847107243b35319:0a1762f6440f421586b56767d27d0770"
)
E4_GATES=(
    "sav0401.cpp src/libs/libSaveData.cpp KYTY_BC5_SAVEDATA_FIXES sav0401"
    "sav0401.cpp src/libs/libSaveData.cpp KYTY_BC5_SAVEDATA_EVENT_CB savcb0401 sav0401"
    "sav0401.cpp src/libs/libSaveData.cpp KYTY_BC5_SAVEDATA_SORT savsort0401 sav0401"
    "pth0401.cpp src/kernel/pthread.cpp KYTY_BC5_PTHREAD_FIXES pth0401"
    "aud0401.cpp src/libs/libAudio2.cpp KYTY_BC5_AUDIO_FIXES aud0401"
    "vo0401.cpp src/graphics/presentation/videoOut.cpp KYTY_BC5_VIDEOOUT_STATUS vo0401"
    "amm0401.cpp src/libs/libAmpr.cpp KYTY_BC5_AMM_PRT_CMDS,KYTY_BC5_AMM_EXTRA_CMDS,KYTY_BC5_AMPR_WAITS amm0401"
)
FL_UNIT_MD5=df12bb2de3e90b8c82a234eedf0babb5   # e3's unit plus exp 0404's FL_CRUMBS and FL_SKIP_ES (mkfl0401.py)
E4_STRS=(BC5_DIRECT_FL_CRUMBS BC5_DIRECT_FL_SKIP_ES 'exp 0404: fl crumbs %s' 'exp 0404: fl skip es' KYTY_BC5_SAVEDATA_FIXES 'exp 0401: savedata fixes' KYTY_BC5_SAVEDATA_EVENT_CB 'exp 0401: savedata event callback' KYTY_BC5_SAVEDATA_SORT 'exp 0401: savedata sort' KYTY_BC5_PTHREAD_FIXES 'exp 0401: pthread fixes' KYTY_BC5_AUDIO_FIXES 'exp 0401: audio fixes' KYTY_BC5_VIDEOOUT_STATUS 'exp 0401: videoout status' KYTY_BC5_AMM_PRT_CMDS KYTY_BC5_AMM_EXTRA_CMDS KYTY_BC5_AMPR_WAITS 'exp 0401 prt: zero pages')
# Series e5 (2026-11-04 01:3x, the top session's GO on the maintainer's "przetestuj też buildy z portami i przełącznikami z
# researchu"): e4 plus exp 0405's e4-now ports, each script over the unit as e4 left it (or the tree's), chained in this
# order. Each E5_EDITS row: tag, script, its option ("-" for none), then relpath:input md5:output md5 for every unit it
# writes (under exp0401e5/x5-<tag>/); the input is checked against the unit as the rows before left it. E5_GATES rows are as
# E4_GATES; e5 runs e4's gates too, over its own objects.
E5_EDITS=(
    "eq mkeq0405.py - src/kernel/eventQueue.cpp:c45e6a72c8e419d98059c3477a9373cc:d8eaa6d22e3e415ea8331dced30867c0 src/libs/bc5LleAgc.cpp:df12bb2de3e90b8c82a234eedf0babb5:09770e46272ed52107f055c6f1af2332"
    "gpu mkgpu0405.py --chain src/libs/bc5LleAgc.cpp:09770e46272ed52107f055c6f1af2332:d1cfd9bb1f1b3485bed4207a7f064d4f"
    "thr mkthr0405.py - src/kernel/pthread.cpp:0363847bd540883467dee22797475031:81ee12c4fa3e61df4f4b7239356b9f60 src/kernel/semaphore.cpp:c9c4aaf56492434eb84dc6e899260ae8:3aa9c8b441438483d124115d3961c9b0"
    "mem mkmem0405.py - src/kernel/memory.cpp:43713ef677ec887a8ca273f7ab5cee90:95d9ca880d01db26d51f0ecabcdfa7e1"
    "fs mkfs0405.py - src/kernel/fileSystem.cpp:f1b5f5288faddd78deff2dbd1b613e1f:a7201a1ab20dc60d876ad64f0dd4d086 src/libs/libKernel.cpp:3bf94a6168d176d591730bac33dff5b1:b353287342a8eb82305a4592a4021e3d"
    "svc mksvc0405.py - src/libs/libSaveData.cpp:04f4c5bb05179b80fd7cf1e41832cdd9:0e0c5d409286893e9956df9aeba845f5 src/libs/libNet.cpp:f7a26ceb10a4cf669c33ed592eb1e89d:35773d6e769b85be74012a86c0f02e89 src/libs/libPad.cpp:dbe268d7dff6134db45ad4328aace716:89a047a4f1ad39847bf76c15fa0d4c14"
    "lib mklib0405.py - src/libs/libJson2.cpp:d38d30582b49f57f9ef3fea6d84584be:85144ef10cbfe295d24ab7096710aa10 src/libs/libUlt.cpp:9198f40703960fe46e9ba066a6c58ac3:191fe8b19bf663af73f48cfc85535a5d src/libs/libUserService.cpp:4f90ba6b94167d9b857c8efa89f1cf47:e3d34e9896ac5e6568f691f7c9699a06 src/libs/libSystemService.cpp:6c2a2925078d2facd4abe9412408dd57:4aa00c539657776620a49e222f3f8fa2"
    "ao mkao0405.py - +src/bc5/pad_audio_route.hpp:51131854822a629c2b24739e3603ef5d src/libs/audio.cpp:f58ec0105874173a9f84954706a17e96:230f732dbc20b9b196b28cb007ba95ec"
    "tls mktls0405.py - +src/loader/jit.h:8b5a53504af3ca127c1ab4fe9b55ee45 src/loader/runtimeLinker.cpp:e94b25b8b37d36d97a074ea02723b733:aba94c24ad35a1c944ad3bd5843b13ef"
)
E5_GATES=(
    "eq0405.cpp src/kernel/eventQueue.cpp KYTY_BC5_EQUEUE_FIXES,KYTY_BC5_MMAP_SHIM_FIXES eq0405"
    "ao0405.cpp src/libs/audio.cpp KYTY_BC5_AUDIOOUT_CHECKS,KYTY_BC5_AUDIOIN_CHECKS,KYTY_BC5_NGS2_RACK_FIX ao0405"
    "mem0405.cpp src/kernel/memory.cpp BC5_R3_MPROTECT_GAPS,BC5_R3_NULL_ARGS,BC5_R3_RELEASE_HOLES,BC5_R3_MUNMAP_HOLES,BC5_R3_FLEX_HINT,BC5_R3_DMQ_END,BC5_R3_EXEC_EINVAL,BC5_R3_QUERY_SIZE mem0405"
    "thr0405.cpp src/kernel/pthread.cpp KYTY_BC5_THREAD_SYNC_FIXES,KYTY_BC5_SEMA_FIXES thr0405"
    "svc0405.cpp src/libs/libSaveData.cpp KYTY_BC5_SAVEDATA_MEMORY_FIXES,KYTY_BC5_SAVEDATA_DELETE_BUSY,KYTY_BC5_SAVEDATA_ALIASES,KYTY_BC5_HTTP2_FIXES,KYTY_BC5_PAD_OPEN_EXT svc0405"
    "gpu0405.cpp src/libs/bc5LleAgc.cpp BC5_R3_MEMSEM_SIGNAL,BC5_R3_REWIND_CATCH,BC5_R3_DROP_CATCH,BC5_R3_SUBMIT_EOP_EVENT,BC5_R3_COND_WRITE,BC5_R3_WAIT_IDLE,BC5_R3_TS_100MHZ gpu0405"
    "fs0405.cpp src/kernel/fileSystem.cpp KYTY_BC5_FS_FIXES,KYTY_BC5_POSIX_RET_FIXES fs0405"
    "lib0405.cpp src/libs/libJson2.cpp KYTY_BC5_JSON2_FIXES,KYTY_BC5_ULT_FIXES,KYTY_BC5_USERSERVICE_VALUES,KYTY_BC5_SYSTEMSERVICE_VALUES,KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000 lib0405"
    "tls0405.cpp src/loader/runtimeLinker.cpp KYTY_BC5_TLS_FIXES tls0405"
)
E5_STRS=(KYTY_BC5_EQUEUE_FIXES KYTY_BC5_MMAP_SHIM_FIXES KYTY_BC5_AUDIOOUT_CHECKS KYTY_BC5_AUDIOIN_CHECKS KYTY_BC5_NGS2_RACK_FIX BC5_R3_MPROTECT_GAPS BC5_R3_NULL_ARGS BC5_R3_RELEASE_HOLES BC5_R3_MUNMAP_HOLES BC5_R3_FLEX_HINT BC5_R3_DMQ_END BC5_R3_EXEC_EINVAL BC5_R3_QUERY_SIZE KYTY_BC5_THREAD_SYNC_FIXES KYTY_BC5_SEMA_FIXES KYTY_BC5_SAVEDATA_MEMORY_FIXES KYTY_BC5_SAVEDATA_DELETE_BUSY KYTY_BC5_SAVEDATA_ALIASES KYTY_BC5_HTTP2_FIXES KYTY_BC5_PAD_OPEN_EXT BC5_R3_MEMSEM_SIGNAL BC5_R3_REWIND_CATCH BC5_R3_DROP_CATCH BC5_R3_SUBMIT_EOP_EVENT BC5_R3_COND_WRITE BC5_R3_WAIT_IDLE BC5_R3_TS_100MHZ KYTY_BC5_FS_FIXES KYTY_BC5_POSIX_RET_FIXES KYTY_BC5_JSON2_FIXES KYTY_BC5_ULT_FIXES KYTY_BC5_USERSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_VALUES KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000 KYTY_BC5_TLS_FIXES)
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
    if [ "$SER" = d ]; then
        [ "$(m "$ZDIR/libs/bc5LleAgc.cpp")" = "$ZUNIT_MD5" ] || { echo "the zero-skip unit is not $ZUNIT_MD5"; return; }
        [ "$(m "$ZDIR/bc5/zero_skip.hpp")" = "$ZHDR_MD5" ] || { echo "zero_skip.hpp is not $ZHDR_MD5"; return; }
    fi
    if [ "${SER:0:1}" = e ]; then
        [ "$(m "$TREE/src/libs/libNpCppWebApi.cpp")" = "$NP_IN_MD5" ] || { echo "the tree's libNpCppWebApi.cpp is not $NP_IN_MD5"; return; }
        [ "$(m "$TREE/src/kernel/memory.cpp")" = "$MEM_IN_MD5" ] || { echo "the tree's memory.cpp is not $MEM_IN_MD5"; return; }
        [ "$(m "$TREE/src/kernel/memoryAddressSpace.inc")" = "$MASINC_MD5" ] || { echo "the tree's memoryAddressSpace.inc is not $MASINC_MD5"; return; }
        [ "$(m "$TREE/src/loader/systemContent.cpp")" = "$SC_IN_MD5" ] || { echo "the tree's systemContent.cpp is not $SC_IN_MD5"; return; }
        [ "$(m "$TREE/src/loader/systemContent.h")" = "$SCH_IN_MD5" ] || { echo "the tree's systemContent.h is not $SCH_IN_MD5"; return; }
    fi
    if [ "$SER" = e4 ] || [ "$SER" = e5 ]; then
        local row f
        for row in "${E4_EDITS[@]}"; do
            for f in ${row#* * }; do
                [ "$(m "$TREE/${f%%:*}")" = "$(echo "$f" | cut -d: -f2)" ] || { echo "the tree's ${f%%:*} is not $(echo "$f" | cut -d: -f2)"; return; }
            done
        done
    fi
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
    if [ "$SER" = d ]; then
        mkdir -p "$E/zbase" "$E/zinc/bc5" 2> /dev/null || die "cannot make the zero-skip directories"
        cp "$ZDIR/libs/bc5LleAgc.cpp" "$E/zbase/bc5LleAgc.cpp" && cp "$ZDIR/bc5/zero_skip.hpp" "$E/zinc/bc5/zero_skip.hpp" || die "cannot copy the zero-skip unit"
        [ "$(m "$E/zbase/bc5LleAgc.cpp")" = "$ZUNIT_MD5" ] && [ "$(m "$E/zinc/bc5/zero_skip.hpp")" = "$ZHDR_MD5" ] || die "the zero-skip copies are not the pins"
    fi
    put "$ST" setup
    echo "set up"
}

cmd_build() {
    load "${1:-}"
    [ "$(state)" = setup ] || die "state is $(state), want setup"
    own; budget "$GRACE"
    work_free || die "$WHY"
    local why u in=$TREE/src/libs/bc5LleAgc.cpp inc=()
    if [ "$SER" = d ]; then
        in=$E/zbase/bc5LleAgc.cpp; inc=("$E/zinc")
        [ "$(m "$in")" = "$ZUNIT_MD5" ] && [ "$(m "$E/zinc/bc5/zero_skip.hpp")" = "$ZHDR_MD5" ] || die "the zero-skip copies are not the pins"
    fi
    why=$(pins_why); [ -z "$why" ] || die "$why"
    stat_of $$ || die "no stat of this shell"
    put "$E/build.id" "$$ $START"
    put "$ST" building

    # 1. The unit, and its new function alone, from the tree that built the shared binaries (series d: the zero-skip unit).
    u=$("${PY[@]}" "$E/mkunit0401.py" "$in" "$E/src/bc5LleAgc.cpp" "$E/src/mesa_preamble_prefix.inc" $MKFLAG) || die "the unit's edit did not apply"
    [ "$u" = "$EXPECT_UNIT" ] || die "the private unit is $u, not $EXPECT_UNIT"
    [ "$(m "$E/src/bc5LleAgc.cpp")" = "$EXPECT_UNIT" ] || die "the private unit on disk is not $EXPECT_UNIT"
    if [ "$SER" = e4 ] || [ "$SER" = e5 ]; then   # exp 0404's two switches over e3's unit; fl_scan.inc goes beside it for the CPU test
        mv -f "$E/src/bc5LleAgc.cpp" "$E/src/bc5LleAgc-e3.cpp" || die "cannot keep e3's unit"
        u=$("${PY[@]}" "$E/mkfl0401.py" "$E/src/bc5LleAgc-e3.cpp" "$E/src/bc5LleAgc.cpp" "$E/src") || die "the fl edit did not apply"
        [ "$u" = "$FL_UNIT_MD5" ] && [ "$(m "$E/src/bc5LleAgc.cpp")" = "$FL_UNIT_MD5" ] || die "the fl unit is $u, not $FL_UNIT_MD5"
    fi
    if [ "${SER:0:1}" = e ]; then   # the three more units, and what build0401.py gets for them and the gate
        u=$("${PY[@]}" "$E/mknp0401.py" "$TREE/src/libs/libNpCppWebApi.cpp" "$E/src/libNpCppWebApi.cpp") || die "the NpCppWebApi edit did not apply"
        [ "$u" = "$NP_OUT_MD5" ] && [ "$(m "$E/src/libNpCppWebApi.cpp")" = "$NP_OUT_MD5" ] || die "the NpCppWebApi unit is $u, not $NP_OUT_MD5"
        rm -rf "$E/mem" && "${PY[@]}" "$E/mkmem0401.py" "$TREE" "$E/mem" > "$R/mkmem.out" 2>&1 || die "the memory edit did not apply: $(tail -1 "$R/mkmem.out" | cut -c1-160)"
        [ "$(m "$E/mem/src/kernel/memory.cpp")" = "$MEM_OUT_MD5" ] && [ "$(m "$E/mem/src/loader/systemContent.cpp")" = "$SC_OUT_MD5" ] &&
            [ "$(m "$E/mem/src/loader/systemContent.h")" = "$SCH_OUT_MD5" ] || die "the memory edit is not the pins: $(tr '\n' ' ' < "$R/mkmem.out" | cut -c1-200)"
        # memory.cpp includes this one beside itself ("memoryAddressSpace.inc"): the tree's copy goes beside the private unit
        cp "$TREE/src/kernel/memoryAddressSpace.inc" "$E/mem/src/kernel/" && [ "$(m "$E/mem/src/kernel/memoryAddressSpace.inc")" = "$MASINC_MD5" ] ||
            die "cannot place memoryAddressSpace.inc"
        inc=("$E/mem/src" "src/libs/libNpCppWebApi.cpp=$E/src/libNpCppWebApi.cpp" "src/kernel/memory.cpp=$E/mem/src/kernel/memory.cpp"
             "src/loader/systemContent.cpp=$E/mem/src/loader/systemContent.cpp" --gate "$E/npgate0401.cpp" "$R/npgate0401")
    fi
    if [ "$SER" = e4 ] || [ "$SER" = e5 ]; then   # exp 0402's items: their scripts on the tree, their units and their test programs
        local row tag script f rel
        for row in "${E4_EDITS[@]}"; do
            tag=${row%% *}; script=$(echo "$row" | cut -d' ' -f2)
            rm -rf "$E/x-$tag" && "${PY[@]}" "$E/$script" "$TREE" "$E/x-$tag" > "$R/$script.out" 2>&1 || die "$script did not apply: $(tail -1 "$R/$script.out" | cut -c1-160)"
            for f in ${row#* * }; do
                rel=${f%%:*}
                [ "$(m "$E/x-$tag/$rel")" = "${f##*:}" ] || die "$script's $rel is $(m "$E/x-$tag/$rel"), not ${f##*:}"
                inc+=("$rel=$E/x-$tag/$rel")
            done
        done
        local built=" "
        for row in "${E4_GATES[@]}"; do
            set -- $row
            case "$built" in *" ${5:-$4} "*) continue ;; esac
            inc+=(--gate "$E/$1" "$R/${5:-$4}" --like "$2"); built="$built${5:-$4} "
        done
    fi
    if [ "$SER" = e5 ]; then   # exp 0405's ports, chained over the units as e4 left them; then the unit list rebuilt
        local -A CUR=()
        local tag5 script5 opt5 f5 rel5 src5 x5 new5=() a5 d5 h5 k5
        CUR[src/libs/bc5LleAgc.cpp]=$E/src/bc5LleAgc.cpp
        for a5 in "${inc[@]}"; do case "$a5" in src/*=*) CUR[${a5%%=*}]=${a5#*=} ;; esac; done
        CUR[src/loader/systemContent.h]=$E/mem/src/loader/systemContent.h
        for row in "${E5_EDITS[@]}"; do
            set -- $row; tag5=$1; script5=$2; opt5=$3; shift 3
            rm -rf "$E/r5-$tag5" "$E/x5-$tag5" || die "cannot clear $tag5"
            for f5 in "$@"; do   # "+rel:md5" is a file the script only reads: staged, not written
                f5=${f5#+}; rel5=${f5%%:*}; src5=${CUR[$rel5]:-$TREE/$rel5}
                [ "$(m "$src5")" = "$(echo "$f5" | cut -d: -f2)" ] || die "$script5's input $rel5 is $(m "$src5"), not $(echo "$f5" | cut -d: -f2)"
                mkdir -p "$E/r5-$tag5/$(dirname "$rel5")" && cp "$src5" "$E/r5-$tag5/$rel5" || die "cannot stage $rel5 for $script5"
            done
            x5=(); [ "$opt5" = - ] || x5=("$opt5")
            "${PY[@]}" "$E/$script5" "${x5[@]}" "$E/r5-$tag5" "$E/x5-$tag5" > "$R/$script5.out" 2>&1 || die "$script5 did not apply: $(tail -1 "$R/$script5.out" | cut -c1-160)"
            for f5 in "$@"; do
                case "$f5" in +*) continue ;; esac
                rel5=${f5%%:*}
                [ "$(m "$E/x5-$tag5/$rel5")" = "${f5##*:}" ] || die "$script5's $rel5 is $(m "$E/x5-$tag5/$rel5"), not ${f5##*:}"
                CUR[$rel5]=$E/x5-$tag5/$rel5
            done
        done
        # The main unit: e5's over e4's (kept), the .inc files the scripts wrote beside it go beside it too.
        if [ "${CUR[src/libs/bc5LleAgc.cpp]}" != "$E/src/bc5LleAgc.cpp" ]; then
            d5=$(dirname "${CUR[src/libs/bc5LleAgc.cpp]}")
            cp "$E/src/bc5LleAgc.cpp" "$E/src/bc5LleAgc-e4.cpp" && cp "${CUR[src/libs/bc5LleAgc.cpp]}" "$E/src/bc5LleAgc.cpp" || die "cannot place e5's unit"
            for h5 in "$d5"/*.inc; do [ ! -f "$h5" ] || cp "$h5" "$E/src/" || die "cannot place $h5"; done
            CUR[src/libs/bc5LleAgc.cpp]=$E/src/bc5LleAgc.cpp
        fi
        # A unit that includes a file of its own directory by bare name ("memoryAddressSpace.inc") gets it beside it.
        for rel5 in "${!CUR[@]}"; do
            case "${CUR[$rel5]}" in "$E/x5-"*) ;; *) continue ;; esac
            d5=$(dirname "$rel5")
            for h5 in $(sed -n 's/^[[:space:]]*#[[:space:]]*include[[:space:]]*"\([^"/]*\)".*/\1/p' "${CUR[$rel5]}"); do
                [ -e "$(dirname "${CUR[$rel5]}")/$h5" ] && continue
                src5=${CUR[$d5/$h5]:-$TREE/$d5/$h5}
                [ ! -f "$src5" ] || cp "$src5" "$(dirname "${CUR[$rel5]}")/" || die "cannot place $h5 beside $rel5"
            done
        done
        # The unit list: every src/<rel>.cpp=... entry as CUR has it now, then e5's new units, then the gates.
        for a5 in "${inc[@]}"; do
            case "$a5" in src/*=*) new5+=("${a5%%=*}=${CUR[${a5%%=*}]}") ;; *) new5+=("$a5") ;; esac
        done
        for rel5 in "${!CUR[@]}"; do
            case "$rel5" in src/libs/bc5LleAgc.cpp | *.h | *.hpp | *.inc) continue ;; esac
            k5=0; for a5 in "${new5[@]}"; do [ "${a5%%=*}" != "$rel5" ] || k5=1; done
            [ "$k5" = 1 ] || new5+=("$rel5=${CUR[$rel5]}")
        done
        inc=("${new5[@]}")
        local built5=" "
        for row in "${E5_GATES[@]}"; do
            set -- $row
            case "$built5" in *" ${5:-$4} "*) continue ;; esac
            inc+=(--gate "$E/$1" "$R/${5:-$4}" --like "$2"); built5="$built5${5:-$4} "
        done
    fi

    # 2. The real function, every setting of the two switches.
    in_box 120 "$CXX" -std=c++20 -Wall -Wextra -Werror "-I$E/inc" "-I$E/src" "$E/unit0401.cpp" -o "$R/unit0401" > "$R/unit0401.out" 2>&1 || die "the function did not compile: $(grep -m3 'error:' "$R/unit0401.out" | cut -c1-160 | tr '\n' ' ')"
    in_box 60 python3 -I "$E/check0401.py" "$R/unit0401" > "$R/check0401.out" 2>&1 || die "the function's check failed: $(tail -1 "$R/check0401.out" | cut -c1-200)"
    grep -q '^check0401: 7 of 7 .*; end$' "$R/check0401.out" || die "no end marker from the function's check"
    if [ "$SER" = e3 ] || [ "$SER" = e4 ] || [ "$SER" = e5 ]; then   # series e3: inherit_scan's CPU test, from the text mkunit0401.py put into the unit
        [ -f "$E/src/inherit_scan.inc" ] && [ -f "$E/src/memline_parse.inc" ] && grep -qF -f <(head -1 "$E/src/inherit_scan.inc") "$E/src/bc5LleAgc.cpp" &&
            grep -qF -f <(head -1 "$E/src/memline_parse.inc") "$E/src/bc5LleAgc.cpp" || die "no inherit_scan.inc or memline_parse.inc beside the unit"
        in_box 120 "$CXX" -std=c++20 -Wall -Wextra -Werror "-I$E/src" "$E/inh0401.cpp" -o "$R/inh0401" > "$R/inh0401-build.out" 2>&1 ||
            die "the inherit test did not compile: $(grep -m3 'error:' "$R/inh0401-build.out" | cut -c1-160 | tr '\n' ' ')"
        in_box 60 "$R/inh0401" > "$R/inh0401.out" 2>&1 || die "the inherit test failed: $(grep -m3 'FAIL\|failed' "$R/inh0401.out" | cut -c1-200 | tr '\n' ' ')"
        grep -q '^inh0401: \([0-9]*\) of \1 cases; end$' "$R/inh0401.out" || die "no end marker from the inherit test"
    fi
    if [ "$SER" = e4 ] || [ "$SER" = e5 ]; then   # exp 0404's CPU test, from fl_scan.inc as mkfl0401.py put it into the unit
        in_box 120 "$CXX" -std=c++20 -Wall -Wextra -Werror "-I$E/src" "$E/fl0401.cpp" -o "$R/fl0401" > "$R/fl0401-build.out" 2>&1 ||
            die "the fl test did not compile: $(grep -m3 'error:' "$R/fl0401-build.out" | cut -c1-160 | tr '\n' ' ')"
        in_box 60 "$R/fl0401" > "$R/fl0401.out" 2>&1 || die "the fl test failed: $(grep -m3 'FAIL\|failed' "$R/fl0401.out" | cut -c1-200 | tr '\n' ' ')"
        grep -q '^fl0401: \([0-9]*\) of \1 cases; end$' "$R/fl0401.out" || die "no end marker from the fl test"
    fi
    hook after-check
    own

    # 3. The shared build's own commands. No header changes, so nothing else is compiled (series d: zero_skip.hpp is new
    # and only this unit includes it, from its own include directory, first on the path).
    in_box 60 sh -c "cd '$B' && ninja -t compdb -x" > "$E/compdb.json" 2> "$R/compdb.err" || die "no compile database"
    in_box "$BUILD_S" python3 -I "$E/build0401.py" "$E/compdb.json" "$E/src/bc5LleAgc.cpp" "$E/obj" "$B" "$BIN" "${inc[@]}" > "$R/build.out" 2>&1 || die "the private build failed: $(strip_ansi "$R/build.out" | grep -m3 -E 'error:|undefined|COMPILE FAILED' | cut -c1-160 | tr '\n' ' ')"
    [ -x "$BIN" ] || die "no private binary"
    own
    if [ "${SER:0:1}" = e ]; then   # the R32 gate: the ten NIDs through the real SymbolDatabase after InitAll, switch on, 0 and unset
        local g v
        for g in on off unset; do
            case $g in on) v=(env KYTY_BC5_NP_SESSION_V2=1) ;; off) v=(env KYTY_BC5_NP_SESSION_V2=0) ;; unset) v=(env -u KYTY_BC5_NP_SESSION_V2) ;; esac
            in_box 120 "${v[@]}" "$R/npgate0401" "${g/unset/off}" > "$R/npgate-$g.out" 2>&1 ||
                die "the NpCppWebApi gate ($g) failed: $(strip_ansi "$R/npgate-$g.out" | grep -m2 -iE 'fail|error|npgate' | cut -c1-160 | tr '\n' ' ')"
            grep -q "^npgate0401: ${g/unset/off} 10 of 10 .*; end\$" "$R/npgate-$g.out" || die "no end marker from the gate ($g)"
        done
        own
    fi
    if [ "$SER" = e4 ] || [ "$SER" = e5 ]; then   # exp 0402's CPU tests (e5: and exp 0405's): switch 1, 0 and unset, each in a fresh directory, away from any save
        local row d gates=("${E4_GATES[@]}")
        [ "$SER" != e5 ] || gates+=("${E5_GATES[@]}")
        for row in "${gates[@]}"; do
            set -- $row
            for g in on off unset; do
                v=(env); for sw in ${3//,/ }; do case $g in on) v+=("$sw=1") ;; off) v+=("$sw=0") ;; unset) v+=(-u "$sw") ;; esac; done
                d=$E/run-$4-$g; rm -rf "$d" && mkdir -p "$d" || die "cannot make $d"
                in_box 300 sh -c 'cd "$1" && shift && exec env -u KYTY_BC5_SAVEDATA_DIR -u KYTY_BC5_SAVE_TRACE "$@"' run "$d" "${v[@]}" "$R/${5:-$4}" "${g/unset/off}" > "$R/$4-$g.out" 2>&1 ||
                    die "the $4 test ($g) failed: $(strip_ansi "$R/$4-$g.out" | grep -m2 -E 'FAIL|failed|error' | cut -c1-160 | tr '\n' ' ')"
                grep -q "^${5:-$4}: ${g/unset/off} \([0-9]*\) of \1\b.*; end\$" "$R/$4-$g.out" || die "no end marker from the $4 test ($g)"
            done
            own
        done
    fi

    # 4. What the binary must hold, and what it must still hold.
    local s strs=(BC5_DIRECT_CP_COHER_START_DELAY BC5_DIRECT_SPI_REQ_CTRL_PS 'exp 0401: CP_COHER_START_DELAY %s' 'exp 0401: SPI_SHADER_REQ_CTRL_PS %s' BC5_DIRECT_ARGS_WB BC5_DIRECT_GC_HS_OFFCHIP)
    [ -z "$SER" ] || strs+=(BC5_DIRECT_ACB_CS_PREFIX 'exp 0401: acb CS prefix %s' 'acb cs prefix (exp 0401)' BC5_DIRECT_CS_PREFIX)
    case $SER in c | d | e | e2 | e3 | e4 | e5) strs+=(BC5_DIRECT_ACB_STATE_RESTORE 'exp 0401: acb state restore (exp 0381) %s' 'acb state restore (exp 0381)') ;; esac
    [ "${SER:0:1}" != e ] || strs+=(BC5_DIRECT_TABLE_CATCHER 'exp 0401: table catcher %s' 'table catcher (exp 0401)' KYTY_BC5_NP_SESSION_V2 KYTY_BC5_MEMORY_FROM_PARAM 'exp 0401: memory from param.json')
    case $SER in e2 | e3 | e4 | e5) strs+=(BC5_DIRECT_ACB_INHERIT 'exp 0403: acb inherit %s' 'acb inherit (exp 0403)' 'acb inherit census (exp 0403)') ;; esac
    case $SER in e3 | e4 | e5) ;; *) false ;; esac && strs+=("the queue's live program" 'prefixed with the queue' 'never bound in a part of its own' 'unknown, fallback ring' 'UNSEEN (not observed in this wave mode)' BC5_DIRECT_MEM_LINE 'exp 0401: memory line %s' 'memory (exp 0401)')
    [ "$SER" != d ] || strs+=(BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZERO_SLICES 'zero skip: list %s' 'job-arena fix APPLIED')
    case $SER in e4 | e5) strs+=("${E4_STRS[@]}") ;; esac
    [ "$SER" != e5 ] || strs+=("${E5_STRS[@]}")
    for s in "${strs[@]}"; do
        grep -aqF -- "$s" "$BIN" || die "the private binary lacks [$s]"
    done

    # 5. The private launcher.
    "${PY[@]}" "$E/launcher0401.py" "$W/play-pkg.sh" "$E/play-pkg-0401.sh" $SER || die "the launcher's edit did not apply"
    bash -n "$E/play-pkg-0401.sh" || die "the private launcher does not parse"
    chmod +x "$E/play-pkg-0401.sh" || die "chmod failed"
    diff -u "$W/play-pkg.sh" "$E/play-pkg-0401.sh" > "$E/play-pkg-0401.diff"
    local dl=8; case $SER in e4 | e5) dl=9 ;; esac   # e4, e5: the line that keeps each run's log
    [ "$(grep -c '^[-+][^-+]' "$E/play-pkg-0401.diff")" = "$dl" ] || die "the launcher's diff is not the lines it must change"

    why=$(pins_why); [ -z "$why" ] || die "$why"
    put "$E/bin.md5" "$(m "$BIN")"
    put "$E/launcher.md5" "$(m "$E/play-pkg-0401.sh")"
    {
        echo "binary $(rd "$E/bin.md5"): shared objects of $BIN_MD5, unit $EXPECT_UNIT, archive $ARCHIVE_MD5"
        echo "launcher $(rd "$E/launcher.md5") from play-pkg.sh $LAUNCHER_MD5"
        echo "warnings in the unit's compile: $(strip_ansi "$R/build.out" | grep -c 'warning:')"
        echo "function check: $(tail -1 "$R/check0401.out")"
        case $SER in e3 | e4 | e5) echo "inherit test: $(tail -1 "$R/inh0401.out")" ;; esac
        if [ "$SER" = e4 ] || [ "$SER" = e5 ]; then
            echo "e4 unit with exp 0404's switches: $FL_UNIT_MD5; fl test: $(tail -1 "$R/fl0401.out")"
            for row in "${E4_EDITS[@]}"; do echo "e4 $row"; done
            for row in "${E4_GATES[@]}"; do set -- $row; echo "e4 test $4: $(tail -1 "$R/$4-on.out" | cut -c1-100) / $(tail -1 "$R/$4-off.out" | cut -c1-100) / $(tail -1 "$R/$4-unset.out" | cut -c1-100)"; done
        fi
        if [ "$SER" = e5 ]; then
            echo "e5 unit: $(m "$E/src/bc5LleAgc.cpp") (e4's kept as bc5LleAgc-e4.cpp)"
            for row in "${E5_EDITS[@]}"; do echo "e5 $row"; done
            for row in "${E5_GATES[@]}"; do set -- $row; echo "e5 test $4: $(tail -1 "$R/$4-on.out" | cut -c1-100) / $(tail -1 "$R/$4-off.out" | cut -c1-100) / $(tail -1 "$R/$4-unset.out" | cut -c1-100)"; done
        fi
        [ "${SER:0:1}" != e ] || echo "units: libNpCppWebApi.cpp $NP_OUT_MD5, memory.cpp $MEM_OUT_MD5, systemContent.cpp $SC_OUT_MD5, systemContent.h $SCH_OUT_MD5; gate: $(tail -1 "$R/npgate-on.out" | cut -c1-120) / $(tail -1 "$R/npgate-off.out" | cut -c1-120)"
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
