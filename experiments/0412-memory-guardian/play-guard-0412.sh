#!/usr/bin/env bash
# BC5 exp 0412: one play of the second title on the guardian's build, by arm. On the host, as ~/bc5-work/exp0412/play-guard-0412.sh.
# play-e11-0411.sh's pattern: exp 0412's launcher play-pkg-0412.sh in the ubuntu distrobox, with the "e11 unpacked" shortcut's
# 70 words (RT on, the saves, the settings and the learned file are the launcher's) plus the arm's words.
# Arms (the second build, g412b, 2026-11-10 night; the first four are the first build's):
#   base     no guardian word: the binary must behave as e11's (the control)
#   ledger   BC5_GUARD_LEDGER=1: log only
#   low      ledger + MLOCK=pinned + FILE=random,dontneed (PSI 10) + APPLY_MIN_MS=50 + PIN_CAP=11600 (log only)
#   guest    low with MLOCK=guest: the title's CPU heaps are locked too. Can end in an OOM kill instead of a slow game.
#   orphans  ledger + BC5_DIRECT_LAZY_RELEASE=10,eager (exp 0401 e7's release, live for the first time: a pinned chunk under
#            no view for 10 s is unpinned) + the fuse
#   cap      orphans + BC5_GUARD_PIN_CAP=11600 + BC5_GUARD_CAP_ACT=1: over 11,600 MiB pinned, new AMM and by-data chunks are
#            put off and read as zeros on the GPU (missing textures or geometry) until room comes back
#   amm      cap + BC5_GUARD_AMM_BY_USE=1 (the launcher drops AMM from the eager heaps: its chunks are pinned when they hold
#            data, not when mapped). F403's class of risk: a GPU access to an AMM page no CPU wrote faults (14 s). No shortcut.
# The fuse (every arm but base, low and guest; fuse0412.sh): memory.max 12,400 MiB (the night of 11-10/11: 12,000 is too tight, 1 flip/s) and memory.swap.max 2,048 MiB on the container's cgroup
# while the emulator runs; past them the kernel kills the emulator instead of the box dying. BC5_0412_FUSE=0 leaves it out,
# BC5_0412_FUSE="<RAM MiB> <swap MiB>" sets other limits (any arm).
# MLOCK needs an unlimited memlock limit inside the container; the wrapper asks for it and the guardian journals what it
# got ("memlock limit unlimited" or "limited": then nothing is locked and the arm is the same without MLOCK).
# Beside it, on the host: the read-only sampler sampler0412b.sh, one line every 5 s into
# ~/bc5-work/exp0412/sampler/play-<time>-<arm>.txt. It waits up to 300 s for the emulator and ends when the emulator's
# process ends (or after 4 h). If the sampler or the fuse script is not the installed one the play goes on without it.
# A second word "dry" checks the pins and prints what would run; it starts nothing (the stand-in check).
# The launcher (play-pkg-0412.sh, exp 0411's) sets ulimit -c 0.
# usage: play-guard-0412.sh base|ledger|low|guest|orphans|cap|amm [dry]
set -u
E=$HOME/bc5-work/exp0412
BIN=$E/bin/kyty_emulator; L=$E/play-pkg-0412.sh; GAME=/home/kjaniszewski/bc5-data/games/PPSA03671
m() { md5sum < "$1" 2> /dev/null | cut -d' ' -f1; }
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send "BC5" "$*" 2> /dev/null; }
# The pins: mk0412b.sh writes built.md5 (the binary and the launcher), install0412b.sh writes tools.md5 (sampler, fuse).
pinned() { [ -s "$2" ] && grep -qxF "$(m "$E/$1")  $1" "$2"; }
pinned bin/kyty_emulator "$E/built.md5" || { say "0412: $BIN is not the build in built.md5; not started"; exit 1; }
pinned play-pkg-0412.sh "$E/built.md5" || { say "0412: $L is not the launcher in built.md5; not started"; exit 1; }
grep -aqF BC5_GUARD_CAP_ACT "$BIN" || { say "0412: $BIN is not the second build (g412b); not started"; exit 1; }
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
ORPH=(BC5_GUARD_LEDGER=1 BC5_DIRECT_LAZY_RELEASE=10,eager BC5_GUARD_SPLIT=1)   # SPLIT since the third build (g412c): without it nothing is cut while BC5_DIRECT_ALIASES is set
CAP=("${ORPH[@]}" BC5_GUARD_PIN_CAP=11600 BC5_GUARD_CAP_ACT=1)
FUSE=""; ZL=$E/zero-list-0412.txt   # the zero list of the z arms (a copy of the night's scan, put in place by hand)
case "${1:-}" in zsk | zo | zoc | zof) [ -s "$ZL" ] || { say "0412: no zero list at $ZL; not started"; exit 1; } ;; esac
case "${1:-}" in
  base)    ;;
  ledger)  WORDS+=(BC5_GUARD_LEDGER=1); FUSE="12400 2048" ;;   # the fuse since the night of 11-10/11: without a limit this arm took the box down (21:47)
  low)     WORDS+=("${LOW[@]}" BC5_GUARD_MLOCK=pinned) ;;
  guest)   WORDS+=("${LOW[@]}" BC5_GUARD_MLOCK=guest) ;;
  orphans) WORDS+=("${ORPH[@]}"); FUSE="12400 2048" ;;
  cap)     WORDS+=("${CAP[@]}"); FUSE="12400 2048" ;;
  amm)     WORDS+=("${CAP[@]}" BC5_GUARD_AMM_BY_USE=1); FUSE="12400 2048" ;;
  # The night's arms (2026-11-11): exp 0379's zero skip with a list scanned at the maintainer's current save.
  zscan)   WORDS+=("${ORPH[@]}" BC5_DIRECT_ZEROSCAN_AT=140,170,200,230,260 "BC5_DIRECT_ZEROSCAN_OUT=$E/night/zero-list-scan.txt"); FUSE="12400 2048" ;;
  zsk)     WORDS+=(BC5_GUARD_LEDGER=1 "BC5_DIRECT_ZERO_SKIP=$ZL"); FUSE="12400 2048" ;;
  zo)      WORDS+=("${ORPH[@]}" "BC5_DIRECT_ZERO_SKIP=$ZL"); FUSE="12400 2048" ;;
  zoc)     WORDS+=("${CAP[@]}" "BC5_DIRECT_ZERO_SKIP=$ZL"); FUSE="12400 2048" ;;
  zof)     WORDS+=("${ORPH[@]}" BC5_GUARD_FORGET=20 "BC5_DIRECT_ZERO_SKIP=$ZL"); FUSE="12400 2048" ;;   # the fourth build (g412d)
  of)      WORDS+=("${ORPH[@]}" BC5_GUARD_FORGET=20); FUSE="12400 2048" ;;
  *) say "0412: usage: play-guard-0412.sh base|ledger|low|guest|orphans|cap|amm|zscan|zsk|zo|zoc|zof|of [dry]; not started"; exit 1 ;;
esac
ARM=$1; DRY=${2:-}
# "words": the arm's environment words, one per line, for the night runner (run0412n.sh); nothing is started.
if [ "$DRY" = words ]; then printf '%s\n' "${WORDS[@]}"; exit 0; fi
[ -z "$DRY" ] || [ "$DRY" = dry ] || { say "0412: unknown second word $DRY; not started"; exit 1; }
case "${BC5_0412_FUSE-unset}" in unset) ;; 0 | "") FUSE="" ;; *) FUSE=$BC5_0412_FUSE ;; esac
S=$E/sampler0412b.sh; F=$E/fuse0412.sh; STAMP=$(date +%Y%m%d-%H%M%S); SOUT=$E/sampler/play-$STAMP-$ARM.txt; FLOG=$E/fuse.log
SOK=0; pinned sampler0412b.sh "$E/tools.md5" && SOK=1
FOK=0; pinned fuse0412.sh "$E/tools.md5" && FOK=1
if [ -n "$DRY" ]; then
  echo "dry: arm $ARM, ${#WORDS[@]} words; the arm's words: $(printf '%s\n' "${WORDS[@]}" | grep -E '^(BC5_GUARD_|BC5_DIRECT_LAZY_RELEASE|BC5_DIRECT_ZERO)' | tr '\n' ' ')"
  echo "dry: RT word in the words: $(printf '%s\n' "${WORDS[@]}" | grep -ci 'KYTY_BC5_RT\|RAYTRAC') (0 = the launcher's settings decide, as in e11 unpacked)"
  echo "dry: sampler $([ "$SOK" = 1 ] && echo "pinned, would write $SOUT" || echo "NOT the installed copy: the play would run without it")"
  echo "dry: fuse $([ -z "$FUSE" ] && echo "none for this arm" || { [ "$FOK" = 1 ] && echo "pinned, would set memory.max and memory.swap.max to $FUSE MiB" || echo "NOT the installed copy: the play would run without it"; })"
  echo "dry: would run: /usr/bin/distrobox enter ubuntu -- /usr/bin/bash -c 'ulimit -l unlimited 2> /dev/null; exec /usr/bin/env \"\$@\"' guard0412 <${#WORDS[@]} words> $L"
  echo "dry: nothing started"
  exit 0
fi
pgrep '^kyty_emulator' > /dev/null && { say "0412: an emulator runs already; not started"; exit 1; }
[ "$FOK" = 1 ] && /usr/bin/bash "$F" restore "$FLOG"
if [ "$SOK" = 1 ]; then
  mkdir -p "$E/sampler"
  nohup /usr/bin/bash "$S" "$SOUT" 300 14400 > /dev/null 2>&1 < /dev/null &
else
  say "0412: the sampler $S is not the installed one; playing without it"
fi
if [ -n "$FUSE" ]; then
  if [ "$FOK" = 1 ]; then
    # shellcheck disable=SC2086
    nohup /usr/bin/bash "$F" set $FUSE "$FLOG" > /dev/null 2>&1 < /dev/null &
  else
    say "0412: the fuse $F is not the installed one; playing without it"
  fi
fi
# The memlock limit is raised inside the container, where the emulator starts; a refusal is not an error here.
/usr/bin/distrobox enter ubuntu -- /usr/bin/bash -c 'ulimit -l unlimited 2> /dev/null; exec /usr/bin/env "$@"' guard0412 "${WORDS[@]}" "$L"
