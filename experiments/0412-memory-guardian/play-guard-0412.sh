#!/usr/bin/env bash
# BC5 exp 0412: one play of the second title on the guardian's build, by arm. On the host, as ~/bc5-work/exp0412/play-guard-0412.sh.
# play-e11-0411.sh's pattern: exp 0412's launcher play-pkg-0412.sh in the ubuntu distrobox, with the "e11 unpacked" shortcut's
# 70 words (RT on, the saves, the settings and the learned file are the launcher's) plus the arm's BC5_GUARD_* words.
# Arms:
#   base    no guardian word: the binary must behave as e11's (the control)
#   ledger  BC5_GUARD_LEDGER=1: log only
#   low     ledger + MLOCK=pinned + FILE=random,dontneed (PSI 10) + APPLY_MIN_MS=50 + PIN_CAP=11600 (log only)
#   guest   low with MLOCK=guest: the title's CPU heaps are locked too. Can end in an OOM kill instead of a slow game.
# MLOCK needs an unlimited memlock limit inside the container; the wrapper asks for it and the guardian journals what it
# got ("memlock limit unlimited" or "limited": then nothing is locked and the arm is the same without MLOCK).
# Beside it, on the host: the read-only sampler sampler0412.sh (a byte copy of exp 0401's sampler0411.sh, 9dfc33ee), one line
# every 5 s into ~/bc5-work/exp0412/sampler/play-<time>-<arm>.txt. It waits up to 300 s for the emulator and ends when the
# emulator's process ends (or after 4 h). If the copy is not the pinned one the play goes on without it.
# A second word "dry" checks the pins and prints what would run; it starts nothing (the stand-in check).
# The launcher (play-pkg-0412.sh, exp 0411's) sets ulimit -c 0.
# usage: play-guard-0412.sh base|ledger|low|guest [dry]
set -u
E=$HOME/bc5-work/exp0412
BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0412.sh; GAME=/home/kjaniszewski/bc5-data/games/PPSA03671
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
[ "$(m "$BIN")" = 70a3bbeee1afe9b1cf54a83d7982c600 ] || { say "0412: $BIN is not the guardian's build; not started"; exit 1; }
[ "$(m "$L")" = 12838195c7ae2b6cc2b37912d74e198d ] || { say "0412: $L is not exp 0412's launcher; not started"; exit 1; }
grep -q '^ulimit -c 0' "$L" || { say "0412: $L does not set ulimit -c 0; not started"; exit 1; }
WORDS=(BC5_GAME_DIR=$GAME BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0
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
[ "${#WORDS[@]}" = 70 ] || { say "0412: the shortcut's words are not 70; not started"; exit 1; }
LOW=(BC5_GUARD_LEDGER=1 BC5_GUARD_FILE=random,dontneed "BC5_GUARD_FILE_ROOT=$GAME" BC5_GUARD_PSI=10 BC5_GUARD_APPLY_MIN_MS=50 BC5_GUARD_PIN_CAP=11600)
case "${1:-}" in
  base)   ;;
  ledger) WORDS+=(BC5_GUARD_LEDGER=1) ;;
  low)    WORDS+=("${LOW[@]}" BC5_GUARD_MLOCK=pinned) ;;
  guest)  WORDS+=("${LOW[@]}" BC5_GUARD_MLOCK=guest) ;;
  *) say "0412: usage: play-guard-0412.sh base|ledger|low|guest [dry]; not started"; exit 1 ;;
esac
ARM=$1; DRY=${2:-}
[ -z "$DRY" ] || [ "$DRY" = dry ] || { say "0412: unknown second word $DRY; not started"; exit 1; }
S=$E/sampler0412.sh; SOUT=$E/sampler/play-$(date +%Y%m%d-%H%M%S)-$ARM.txt; SOK=0
[ "$(m "$S")" = 9dfc33eed6767bd65963c016f380bc44 ] && SOK=1
if [ -n "$DRY" ]; then
  echo "dry: arm $ARM, ${#WORDS[@]} words; guardian words: $(printf '%s\n' "${WORDS[@]}" | grep '^BC5_GUARD_' | tr '\n' ' ')"
  echo "dry: RT word in the words: $(printf '%s\n' "${WORDS[@]}" | grep -ci 'KYTY_BC5_RT\|RAYTRAC') (0 = the launcher's settings decide, as in e11 unpacked)"
  echo "dry: sampler $([ "$SOK" = 1 ] && echo "pinned, would write $SOUT" || echo "NOT the pinned copy: the play would run without it")"
  echo "dry: would run: /usr/bin/distrobox enter ubuntu -- /usr/bin/bash -c 'ulimit -l unlimited 2> /dev/null; exec /usr/bin/env \"\$@\"' guard0412 <${#WORDS[@]} words> $L"
  echo "dry: nothing started"
  exit 0
fi
pgrep '^kyty_emulator' > /dev/null && { say "0412: an emulator runs already; not started"; exit 1; }
if [ "$SOK" = 1 ]; then
  mkdir -p "$E/sampler"
  nohup /usr/bin/bash "$S" "$SOUT" 300 14400 > /dev/null 2>&1 < /dev/null &
else
  say "0412: the sampler $S is not the pinned one; playing without it"
fi
# The memlock limit is raised inside the container, where the emulator starts; a refusal is not an error here.
/usr/bin/distrobox enter ubuntu -- /usr/bin/bash -c 'ulimit -l unlimited 2> /dev/null; exec /usr/bin/env "$@"' guard0412 "${WORDS[@]}" "$L"
