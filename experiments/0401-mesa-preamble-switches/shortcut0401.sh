#!/usr/bin/env bash
# BC5 experiment 0401: the maintainer's test shortcut "BC5 emulator (test 0401)" on his desktop (his words, 2026-11-03:
# "przygotuj skrót do kolejnego testu z przełącznikami bez ARGS_WB=all"). It runs the private launcher play-pkg-0401.sh
# (c6b2d7fd) with the private build 174e768e and both of this experiment's switches on, ARGS_WB set off explicitly. No
# menu: the launcher starts game.pkg. RT on comes from the shared settings, which this script only prints.
# Writes only the one .desktop file (made as a temporary file in the series' directory, then moved). Nothing else is
# written, except that mode cpacb also removes the cp shortcut it replaces; the build, the launcher and the settings are only read.
# Mode cp (the top session's GO, 2026-11-03, after "Nie da się grać" on both): "BC5 emulator (test 0401 CP)", CP_COHER_START_DELAY alone.
# Mode cpacb (the top session's GO, 2026-11-03 09:10 and 09:24): "BC5 emulator (test 0401 CP+acb)", series c's build
# (exp0401c) with CP_COHER_START_DELAY, the acb CS prefix and exp 0381's acb state restore on; it replaces the cp shortcut.
# Mode cpacb-b puts the same shortcut back on series b's build (exp0401b, no restore): the rollback.
# Since the top session's GO of 2026-11-03 13:52 (his "Tak, przebuduj"), mode cpacb runs series d (exp0401d): series c's
# three switches on exp 0379's zero skip, with the skip on as exp 0388's play0389z.sh on sets it (its list, pinned). Mode
# cpacb-c puts the same shortcut back on series c's 505b3ae3, without the skip: the rollback.
# Since the top session's GO of 2026-11-03 16:4x (his "Buduj"), mode cpacb runs series e (exp0401e): series c's binary plus
# the table catcher, the NpCppWebApi SessionManager V2 exports and the param.json memory sizing, all three on, with the acb CS
# prefix off (the top's hand edit of 2026-11-03, after the prefix-on crashes). Mode cpacb-c0 is that hand edit (series c's
# 505b3ae3, prefix off): the rollback. Mode cpacb-d is series d as mode cpacb was until then.
# Since the top session's addition of 2026-11-03 17:0x, mode cpacb runs series e2 (exp0401e2): series e plus exp 0403's
# BC5_DIRECT_ACB_INHERIT, set to journal (the catcher; wave and skip are built, not set). Mode cpacb-e is series e as it was.
# At 18:1x the top session set KYTY_BC5_MEMORY_FROM_PARAM=0 in that shortcut by hand (the AMM pool ran out with it on,
# exp0401e2/desktop-mem1.bak); mode cpacb writes it so. Mode cpacb-e3 (series e3: e2 with exp 0403's queue mode, plus the memory
# line) is built and not installed: the shortcut stays on e2 until the maintainer says otherwise. Series e3 has exp 0403's
# queue mode (addendum a423f761) in place of the per-wave slots; its first draft is set aside in exp0401e3w.
# Since the top session's GO of 2026-11-04 (the maintainer's "Tak" to "Przełączyć Twój skrót z e2 na e6?"), mode cpacb runs
# series e6 (exp0401e6, binary 7252558e): e2's switches plus every e4, e5 and e6 switch as the r6 route had them, except
# KYTY_BC5_AUDIO_FIXES=set,room (not =1: the haptics rule) and with BC5_DIRECT_FL_SKIP_ES off; FL_CRUMBS on; no G7 (not in
# e6). Mode cpacb-e2 is e2 as it was installed: the rollback. Every write keeps the file it replaces as
# <series dir>/desktop-before-<time>.bak.
# Since the top session's GO of 2026-11-05 (the maintainer's "1" to "switch the shortcut to e7 with the memory fixes,
# without catchers?"), mode cpacb runs series e8's binary (exp0401e8, dc7fb4e0, the build of the 18 F2 arms): e6's
# switches without BC5_DIRECT_FL_CRUMBS, plus the quiet journal. Without exp 0379's zero skip: his choice, on the top
# session's recommendation after both e8 F403 hangs followed a canary take-back of zero-skip run 37 (hang1954-0401.md).
# No lazy release, no F2, no FL catchers, no e7 tables. Mode cpacb-e6 is e6 as it was installed: the rollback (it writes
# the same file again, cb3fa0a8).
# usage: shortcut0401.sh [both|cp|cpacb|cpacb-e6|cpacb-e2|cpacb-e3|cpacb-e|cpacb-c0|cpacb-c|cpacb-d|cpacb-b]   (on the box; both is the default)
set -u
DESK=$(xdg-user-dir DESKTOP 2> /dev/null); DESK=${DESK:-$HOME/Pulpit}
OLD=""; ZL=""; WANT_LIST=""
case ${1:-both} in
both)  S=""; WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
       NAME="BC5 emulator (test 0401)"; WHAT="CP_COHER_START_DELAY 0x20 and SPI_SHADER_REQ_CTRL_PS 0x7 (Mesa's preamble values)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=1 BC5_DIRECT_ARGS_WB=0" ;;
cp)    S=""; WANT_BIN=174e768ec3a68c34be879ad57067819c; WANT_LAUNCHER=c6b2d7fdba882a1817224c9bf6d07ff2
       NAME="BC5 emulator (test 0401 CP)"; WHAT="CP_COHER_START_DELAY 0x20 only (Mesa's preamble value)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0" ;;
cpacb) S=e8; WANT_BIN=dc7fb4e051f0a2f5db1abe7e5ec43bcf; WANT_LAUNCHER=d88543fffaa20a5053df47e8e7406caf
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="e6's switches without the fl crumbs, plus the quiet journal, as the e8 arms had them without their catchers and without the zero skip (audio fixes set,room; no lazy release, no F2, no e7 tables)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=0 KYTY_BC5_PTHREAD_FIXES=1 KYTY_BC5_SAVEDATA_FIXES=1 KYTY_BC5_SAVEDATA_EVENT_CB=1 KYTY_BC5_SAVEDATA_SORT=1 KYTY_BC5_AUDIO_FIXES=set,room KYTY_BC5_VIDEOOUT_STATUS=1 KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 KYTY_BC5_AMPR_WAITS=1 KYTY_BC5_EQUEUE_FIXES=1 KYTY_BC5_MMAP_SHIM_FIXES=1 BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_COND_WRITE=1 BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 KYTY_BC5_TLS_FIXES=1 KYTY_BC5_THREAD_SYNC_FIXES=1 KYTY_BC5_SEMA_FIXES=1 BC5_R3_MPROTECT_GAPS=1 BC5_R3_NULL_ARGS=1 BC5_R3_RELEASE_HOLES=1 BC5_R3_MUNMAP_HOLES=1 BC5_R3_FLEX_HINT=1 BC5_R3_DMQ_END=1 BC5_R3_EXEC_EINVAL=1 BC5_R3_QUERY_SIZE=1 KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1 KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1 KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1 KYTY_BC5_NGS2_RACK_FIX=1 KYTY_BC5_FW_NET=1 KYTY_BC5_FW_PAD=1 KYTY_BC5_FW_AUDIO=1 KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1 KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1 KYTY_BC5_LOAD_NPMANAGER=1 KYTY_BC5_LOAD_NPTROPHY=1 BC5_DIRECT_JOURNAL_QUIET=1"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-e6) S=e6; WANT_BIN=7252558e78d38b3bf589d8d773676a63; WANT_LAUNCHER=456e5168d2dce6a7253646918f1fc30f   # the rollback: series e6 as installed until 2026-11-05
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="e2's switches plus every e4, e5 and e6 switch as the r6 route had them (audio fixes set,room; fl crumbs on, fl skip-es off)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=0 KYTY_BC5_PTHREAD_FIXES=1 KYTY_BC5_SAVEDATA_FIXES=1 KYTY_BC5_SAVEDATA_EVENT_CB=1 KYTY_BC5_SAVEDATA_SORT=1 KYTY_BC5_AUDIO_FIXES=set,room KYTY_BC5_VIDEOOUT_STATUS=1 KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 KYTY_BC5_AMPR_WAITS=1 BC5_DIRECT_FL_CRUMBS=1 KYTY_BC5_EQUEUE_FIXES=1 KYTY_BC5_MMAP_SHIM_FIXES=1 BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_COND_WRITE=1 BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 KYTY_BC5_TLS_FIXES=1 KYTY_BC5_THREAD_SYNC_FIXES=1 KYTY_BC5_SEMA_FIXES=1 BC5_R3_MPROTECT_GAPS=1 BC5_R3_NULL_ARGS=1 BC5_R3_RELEASE_HOLES=1 BC5_R3_MUNMAP_HOLES=1 BC5_R3_FLEX_HINT=1 BC5_R3_DMQ_END=1 BC5_R3_EXEC_EINVAL=1 BC5_R3_QUERY_SIZE=1 KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1 KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1 KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1 KYTY_BC5_NGS2_RACK_FIX=1 KYTY_BC5_FW_NET=1 KYTY_BC5_FW_PAD=1 KYTY_BC5_FW_AUDIO=1 KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1 KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1 KYTY_BC5_LOAD_NPMANAGER=1 KYTY_BC5_LOAD_NPTROPHY=1"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-e2) S=e2; WANT_BIN=35ff82ebc8530e4bcc4ea66ccf43accf; WANT_LAUNCHER=f23acf2742e7cb7a4c097b0911a08adb   # the rollback: series e2 as installed until 2026-11-04
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, exp 0381's acb state restore, exp 0403's ACB_INHERIT journal (acb CS prefix off), the table catcher, NpCppWebApi SessionManager V2 and the param.json memory sizing"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-e3) S=e3; WANT_BIN=c059c71fa37c0f81db19310cb1197be4; WANT_LAUNCHER=03d29959a729ca79ba831787a03a8122   # built, not installed; the launcher as the top session edited it (log kept per run)
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, exp 0381's acb state restore, exp 0403's ACB_INHERIT journal of the queue's own state (queue and skip built, not set; acb CS prefix off), the table catcher, NpCppWebApi SessionManager V2 and the 10-s memory line"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-e) S=e; WANT_BIN=852d9b089558d4c845ba7005af888b96; WANT_LAUNCHER=b9774734b4ae9411afb768197d3f59c8   # series e as built first
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, exp 0381's acb state restore (acb CS prefix off), the table catcher, NpCppWebApi SessionManager V2 and the param.json memory sizing"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=1"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-c0) S=c; WANT_BIN=505b3ae35ac4510494e03e50fec6a43e; WANT_LAUNCHER=d17996d379eef31aab995fa9aa55600d   # the rollback: the top's hand edit
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20 and exp 0381's acb state restore (acb CS prefix off)"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-d) S=d; WANT_BIN=1545c4dee54528fc0480faf1b62df45e; WANT_LAUNCHER=7e4df66b96b3983b85733606895d2a01
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, the acb CS prefix, exp 0381's acb state restore and exp 0379's zero skip"
       ZL=$HOME/bc5-work/exp0388/m/zero-list-moving.txt; WANT_LIST=843f9fbcde4d9c2d324e8cba78cdbae5   # play0389z.sh on's list
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_ZERO_SKIP=$ZL"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-c) S=c; WANT_BIN=505b3ae35ac4510494e03e50fec6a43e; WANT_LAUNCHER=d17996d379eef31aab995fa9aa55600d   # the rollback: series c, no skip
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20, the acb CS prefix and exp 0381's acb state restore"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
cpacb-b) S=b; WANT_BIN=5b05ce9be5e4a4bf6352e270d28358d7; WANT_LAUNCHER=01312b5b995d632177745273a5adcd93   # the rollback: series b, no restore
       NAME="BC5 emulator (test 0401 CP+acb)"; WHAT="CP_COHER_START_DELAY 0x20 and the acb CS prefix"
       ENVS="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0"
       OLD="BC5 emulator (test 0401 CP)" ;;
*)     echo "usage: shortcut0401.sh [both|cp|cpacb|cpacb-e6|cpacb-e2|cpacb-e3|cpacb-e|cpacb-c0|cpacb-c|cpacb-d|cpacb-b]"; exit 1 ;;
esac
E=$HOME/bc5-work/exp0401$S; BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0401.sh
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not $WANT_BIN: stop"; exit 1; }
[ "$(m "$L")" = "$WANT_LAUNCHER" ] || { echo "$L is not $WANT_LAUNCHER: stop"; exit 1; }
[ -z "$ZL" ] || [ "$(m "$ZL")" = "$WANT_LIST" ] || { echo "the zero list $ZL is not $WANT_LIST: stop"; exit 1; }
[ -d "$DESK" ] && [ ! -L "$DESK" ] || { echo "no desktop directory $DESK: stop"; exit 1; }
D="$DESK/$NAME.desktop"
[ ! -e "$D" ] || grep -qxF "Name=$NAME" "$D" || { echo "$D exists and is not ours: stop"; exit 1; }
O=""; [ -z "$OLD" ] || O="$DESK/$OLD.desktop"
[ -z "$O" ] || [ ! -e "$O" ] || grep -qxF "Name=$OLD" "$O" || { echo "$O exists and is not ours: stop"; exit 1; }
t=$E/shortcut-0401.tmp.$$.desktop   # desktop-file-validate wants the extension; the same file system as the desktop
cat > "$t" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$NAME
Comment=BC5 test 0401: private build $WANT_BIN with $WHAT, without ARGS_WB; starts the game directly; log ~/bc5-work/exp0401$S/play-last.log
Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env $ENVS $L
Icon=applications-games
Terminal=false
Categories=Game;
StartupNotify=false
EOF
[ "$(grep -c "^Exec=/usr/bin/distrobox enter ubuntu -- /usr/bin/env $ENVS $L$" "$t")" = 1 ] || { rm -f "$t"; echo "the Exec line is not as meant: stop"; exit 1; }
if command -v desktop-file-validate > /dev/null; then desktop-file-validate "$t" || { rm -f "$t"; echo "the .desktop file is not valid: stop"; exit 1; }; fi
if [ -e "$D" ]; then   # keep the file this one replaces (the top session, 2026-11-04)
    k=$E/desktop-before-$(date +%Y%m%d-%H%M%S).bak; cp -p "$D" "$k" || { rm -f "$t"; echo "cannot keep $D as $k: stop"; exit 1; }
    echo "kept the old shortcut as $k, md5 $(m "$k")"
fi
chmod +x "$t" && mv -fT "$t" "$D" || { rm -f "$t"; echo "cannot write $D"; exit 1; }
echo "shortcut $D, md5 $(m "$D")"; grep -E '^(Name|Exec)=' "$D"
if [ -n "$O" ] && [ -e "$O" ]; then rm -f "$O" && echo "removed $O, which this one replaces"; fi
echo "RT in the shared settings: $(grep -h 'RayTracing.PPSA03671' "$HOME"/bc5-work/input*.cfg 2> /dev/null | sort -u | tr '\n' ' ')"
