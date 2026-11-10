#!/usr/bin/env bash
# BC5 exp 0401 e11: what the maintainer's shortcut "BC5 emulator (e11 unpacked)" runs (his "zrób mi skrót", 2026-11-10, after
# the e11 menu series). On the host, installed as ~/bc5-work/exp0411/play-e11-0411.sh by shortcut0411.sh.
# - The game: exp 0411's launcher play-pkg-0411.sh (exp 0409's launcher e4253b93 with only its binary, e11's 70df5cb1, and its
#   log, ~/bc5-work/exp0411/play-last.log, changed) in the ubuntu distrobox, with the "e10 unpacked" shortcut's 66 words plus
#   e11's four switches on (the x11MB arms' words without the runner's). It starts the game directly; saves, settings (RT on)
#   and the learned file are the launcher's, as with "e10 unpacked".
# - Beside it, in the same container, the read-only stall catcher stall0409.sh on that log: once the frames have stopped for
#   60 s while the emulator lives, one dump of every thread's name, state and wchan into ~/bc5-work/exp0411/stall/, plus
#   every thread's stack by the container's eu-stack (elfutils 0.194, installed on his "Tak, zainstaluj", 2026-11-10; the
#   host's eu-stack is refused the container's processes). DEBUGINFOD_URLS is unset for it: the container inherits the
#   host's Fedora debuginfod server, and eu-stack would send it the build ids it cannot resolve. A long window pause can
#   also make one dump. When the launcher ends the catcher is told to stop; it finishes a dump it has begun.
set -u
E=$HOME/bc5-work/exp0411
BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0411.sh; C=$HOME/bc5-work/exp0401t/stall0409.sh
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
[ "$(m "$BIN")" = 70df5cb1f43cf276011037aaf7793a30 ] || { say "e11: $BIN is not e11's build; not started"; exit 1; }
[ "$(m "$L")" = 3e758fdfac5718c82ff6ac108a85ec13 ] || { say "e11: $L is not e11's launcher; not started"; exit 1; }
WORDS=(BC5_GAME_DIR=/home/kjaniszewski/bc5-data/games/PPSA03671 BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0
  BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0
  BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=0 KYTY_BC5_PTHREAD_FIXES=1
  KYTY_BC5_SAVEDATA_FIXES=1 KYTY_BC5_SAVEDATA_EVENT_CB=1 KYTY_BC5_SAVEDATA_SORT=1 KYTY_BC5_AUDIO_FIXES=set,room
  KYTY_BC5_VIDEOOUT_STATUS=1 KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 KYTY_BC5_AMPR_WAITS=1 KYTY_BC5_EQUEUE_FIXES=1
  KYTY_BC5_MMAP_SHIM_FIXES=1 BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 BC5_R3_SUBMIT_EOP_EVENT=1
  BC5_R3_COND_WRITE=1 BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 KYTY_BC5_TLS_FIXES=1 KYTY_BC5_THREAD_SYNC_FIXES=1
  KYTY_BC5_SEMA_FIXES=1 BC5_R3_MPROTECT_GAPS=1 BC5_R3_NULL_ARGS=1 BC5_R3_RELEASE_HOLES=1 BC5_R3_MUNMAP_HOLES=1
  BC5_R3_FLEX_HINT=1 BC5_R3_DMQ_END=1 BC5_R3_EXEC_EINVAL=1 BC5_R3_QUERY_SIZE=1 KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1
  KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1
  KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1
  KYTY_BC5_SYSTEMSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1
  KYTY_BC5_NGS2_RACK_FIX=1 KYTY_BC5_FW_NET=1 KYTY_BC5_FW_PAD=1 KYTY_BC5_FW_AUDIO=1 KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1
  KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1 KYTY_BC5_LOAD_NPMANAGER=1
  KYTY_BC5_LOAD_NPTROPHY=1 BC5_DIRECT_JOURNAL_QUIET=1
  BC5_DIRECT_RESET_REPLAY_ACB=1 BC5_DIRECT_RESET_LABELS=1 BC5_DIRECT_LEARN_GUEST_ONLY=1 BC5_DIRECT_RESET_LABEL_JOURNAL=1)
[ "${#WORDS[@]}" = 70 ] || { say "e11: the shortcut's words are not 70; not started"; exit 1; }
SP=""; STOP=""
if [ "$(m "$C")" = 49db07c8c84e0332dab1e340c7461ce8 ]; then
  mkdir -p "$E/stall"; STOP=$E/stall/stop-$$; rm -f "$STOP"
  nohup /usr/bin/distrobox enter ubuntu -- /usr/bin/env -u DEBUGINFOD_URLS bash "$C" "$E/play-last.log" "$E/stall" "$(($(date +%s) + 86400))" "$STOP" \
    > "$E/stall/catcher-$(date +%Y%m%d-%H%M%S).out" 2>&1 < /dev/null &
  SP=$!
else
  say "e11: the stall catcher $C is not the pinned one; playing without it"
fi
/usr/bin/distrobox enter ubuntu -- /usr/bin/env "${WORDS[@]}" "$L"
RC=$?
if [ -n "$SP" ]; then
  touch "$STOP"
  ( for _ in $(seq 1 40); do kill -0 "$SP" 2> /dev/null || break; sleep 5; done; rm -f "$STOP" ) > /dev/null 2>&1 < /dev/null &
fi
exit $RC
