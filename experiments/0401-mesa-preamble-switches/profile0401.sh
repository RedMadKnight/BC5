#!/usr/bin/env bash
# BC5 experiment 0401 series e9 (the top session's order of 2026-11-05 on the maintainer's "Ok, zbuduj od razu wersję lean
# i normal"; his yes in the water session): two launch profiles of the one e9 binary, written as two small scripts in
# ~/bc5-work/exp0401e9 (nothing else is written; his desktop shortcut is not touched):
#   play-e9-normal.sh  his e8 shortcut's 65 words (e6's switches without the fl crumbs, the quiet journal, no zero skip),
#                      every e9 switch off;
#   play-e9-lean.sh    normal without exp 0406's catcher drops (ACB_INHERIT journal, R3_REWIND_CATCH, R3_DROP_CATCH,
#                      AMM_PRT_CMDS, AMM_EXTRA_CMDS, TABLE_CATCHER), with LEARNED_PRUNE=eager and the late-producer wait
#                      (250 ms), and the launcher's own FRAME_PROFILE, AUDIO_TRACE, MEASURE and GPU_CHECK_PRODUCT taken
#                      back (BC5_0401_LATE_UNSET; unset, not =0: the shared archive may still read =0 as on, F767).
# Each runs the e9 launcher in the ubuntu distrobox, as the shortcut does. The binary and the launcher are checked by md5.
# usage (on the box): profile0401.sh <e9 binary md5> <e9 launcher md5>
set -u
WANT_BIN=${1:?the e9 binary md5}; WANT_L=${2:?the e9 launcher md5}
E=$HOME/bc5-work/exp0401e9; BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0401.sh
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
[ "$(m "$BIN")" = "$WANT_BIN" ] || { echo "$BIN is not $WANT_BIN: stop"; exit 1; }
[ "$(m "$L")" = "$WANT_L" ] || { echo "$L is not $WANT_L: stop"; exit 1; }
grep -qF 'BC5_0401_LATE_UNSET' "$L" || { echo "$L has no BC5_0401_LATE_UNSET line: stop"; exit 1; }
NORMAL="BC5_DIRECT_CP_COHER_START_DELAY=1 BC5_DIRECT_ACB_CS_PREFIX=0 BC5_DIRECT_ACB_INHERIT=journal BC5_DIRECT_ACB_STATE_RESTORE=1 BC5_DIRECT_SPI_REQ_CTRL_PS=0 BC5_DIRECT_ARGS_WB=0 BC5_DIRECT_TABLE_CATCHER=1 KYTY_BC5_NP_SESSION_V2=1 KYTY_BC5_MEMORY_FROM_PARAM=0 KYTY_BC5_PTHREAD_FIXES=1 KYTY_BC5_SAVEDATA_FIXES=1 KYTY_BC5_SAVEDATA_EVENT_CB=1 KYTY_BC5_SAVEDATA_SORT=1 KYTY_BC5_AUDIO_FIXES=set,room KYTY_BC5_VIDEOOUT_STATUS=1 KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 KYTY_BC5_AMPR_WAITS=1 KYTY_BC5_EQUEUE_FIXES=1 KYTY_BC5_MMAP_SHIM_FIXES=1 BC5_R3_MEMSEM_SIGNAL=1 BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 BC5_R3_SUBMIT_EOP_EVENT=1 BC5_R3_COND_WRITE=1 BC5_R3_WAIT_IDLE=1 BC5_R3_TS_100MHZ=1 KYTY_BC5_TLS_FIXES=1 KYTY_BC5_THREAD_SYNC_FIXES=1 KYTY_BC5_SEMA_FIXES=1 BC5_R3_MPROTECT_GAPS=1 BC5_R3_NULL_ARGS=1 BC5_R3_RELEASE_HOLES=1 BC5_R3_MUNMAP_HOLES=1 BC5_R3_FLEX_HINT=1 BC5_R3_DMQ_END=1 BC5_R3_EXEC_EINVAL=1 BC5_R3_QUERY_SIZE=1 KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1 KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1 KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1 KYTY_BC5_NGS2_RACK_FIX=1 KYTY_BC5_FW_NET=1 KYTY_BC5_FW_PAD=1 KYTY_BC5_FW_AUDIO=1 KYTY_BC5_JIT_SHM=1 KYTY_BC5_FW_KERNEL=1 KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1 KYTY_BC5_LOAD_NPMANAGER=1 KYTY_BC5_LOAD_NPTROPHY=1 BC5_DIRECT_JOURNAL_QUIET=1"
DROP=" BC5_DIRECT_ACB_INHERIT=journal BC5_R3_REWIND_CATCH=1 BC5_R3_DROP_CATCH=1 KYTY_BC5_AMM_PRT_CMDS=1 KYTY_BC5_AMM_EXTRA_CMDS=1 BC5_DIRECT_TABLE_CATCHER=1 "
LEAN=""; for w in $NORMAL; do case "$DROP" in *" $w "*) ;; *) LEAN="$LEAN $w" ;; esac; done
LEAN="${LEAN# } BC5_0406_LEARNED_PRUNE=eager BC5_DIRECT_WAIT_LATE_PRODUCER_MS=250 BC5_0401_LATE_UNSET=BC5_DIRECT_FRAME_PROFILE,KYTY_BC5_AUDIO_TRACE,KYTY_BC5_MEASURE,BC5_DIRECT_GPU_CHECK_PRODUCT"
[ "$(echo $NORMAL | wc -w)" = 65 ] && [ "$(echo $LEAN | wc -w)" = 62 ] || { echo "the word counts are not 65 and 62: stop"; exit 1; }
for p in normal lean; do
    if [ $p = normal ]; then WORDS=$NORMAL; else WORDS=$LEAN; fi
    t=$E/play-e9-$p.sh.tmp.$$
    printf '%s\n' '#!/bin/bash' "# BC5 exp 0401 e9, profile $p (profile0401.sh): binary $WANT_BIN, launcher $WANT_L" \
        "exec /usr/bin/distrobox enter ubuntu -- /usr/bin/env $WORDS $L" > "$t" || { rm -f "$t"; echo "cannot write $t"; exit 1; }
    bash -n "$t" && chmod +x "$t" && mv -fT "$t" "$E/play-e9-$p.sh" || { rm -f "$t"; echo "cannot place play-e9-$p.sh"; exit 1; }
    echo "profile $p: $E/play-e9-$p.sh md5 $(m "$E/play-e9-$p.sh"), $(echo $WORDS | wc -w) words"
done
