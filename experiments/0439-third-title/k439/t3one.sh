#!/usr/bin/env bash
# BC5 exp 0439: the ONE clean-boot run (the top session's GO of 11-22 ~07:30): the 06:28 environment (default rings,
# FLAT_APERTURE=1, the piece dump) with the umr watchdog OFF and the indirect-argument probe on (BC5_0439_ARGS_PROBE=1,
# tag pa439: at the submit and at the timeout, the argument dwords of every compute-form DISPATCH_INDIRECT, every
# DMA_DATA and the mapping under each argument address). The Performance presses, bound 600 s. No chain: one emulator
# start; it exits at its first GPU fault (exit 86). The same script on either system image.
# Candidate fixes (tag ds439), $2 (the top session's order of 11-22 ~08:10; each only on zero kernel lines before it):
#   fixes   = D (BC5_0439_DMA_SYNC_MEC=1: a zero-byte CP_SYNC DMA_DATA before the first dispatch after an unsynced
#             DMA_DATA, on the compute rings too) + D2 (BC5_0439_DMA_SYNC_LABEL=1: the same before a label write and at
#             a buffer's end) + C (BC5_0439_ARGS_GL2WB=1: an ACQUIRE_MEM GL2_WB after it) + B (BC5_0439_DMA_DST_BYPASS=1:
#             DST_CACHE_POLICY bypass on DMA_DATA to an address through L2) + BC5_DIRECT_DMA_SYNC=1 (exp 0050's loop on
#             the GFX ring, behind the GDS DMA_DATA our filter strips of CP_SYNC);
#   f       = the same with F (BC5_0439_KEEP_GDS_SYNC=1: the title's CP_SYNC on GDS DMA_DATA kept) in place of
#             BC5_DIRECT_DMA_SYNC=1;
#   control = everything off.
#   waves   = fixes, with the umr watchdog ON: five wave scans 100 ms apart (BC5_0439_UMR_SCANS=5, tag ms439) from 0.9 s
#             into a stuck completion wait, the march-loop inputs in the timeout record (tag mi439), and switch E
#             (BC5_0439_WAVES_UNLIMITED=1: WAVES_PER_SH of COMPUTE_RESOURCE_LIMITS cleared; the top session, 11-22 ~08:55),
#             and G (BC5_0439_KEEP_XQ_WAITS=1: a satisfied cross-queue wait on a compute ring kept for the GPU; 11-22 ~09:30).
#   t3one.sh <md5-8 of the private normal build> fixes|f|control|waves
set -u
PIN=${1:?md5}
UMR=1
# The second title's kTitleDefaults rows (src/bc5/switch_defaults.hpp of patch 589ef163, lines 189-228), set by
# environment for the third title. Left out, on the maintainer's word "nothing learned, in any form" (via TOP, 11-22
# ~10:20): BC5_GUARD_SPLIT, BC5_GUARD_LEARN_LOG and BC5_DIRECT_ALIASES (the second title's learned and alias files) and
# BC5_DIRECT_HOST_INDIRECT (a window learned from SET_BASEs or the second title's constant). Kept: REMEMBER_UNMAPPED
# (pages a forced sync left unmapped in the last 2 s of this run, exp 0103: nothing from an earlier run).
# FLAT_APERTURE is on already.
T2ROWS="BC5_DIRECT_LAZY_RELEASE=30,eager BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 BC5_DIRECT_DMA_SYNC=1 BC5_DIRECT_REMEMBER_UNMAPPED=1 KYTY_BC5_APR_PARALLEL=8 BC5_DIRECT_DMA_SNAPSHOT=4096 BC5_DIRECT_AMM_PRT=1 BC5_DIRECT_SKIP_PGM=0 BC5_DIRECT_CS_PREFIX=1 BC5_DIRECT_INDIRECT_DRAWS=multi BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1"
T2LIB="KYTY_BC5_SAVEDATA_MEMORY_FIXES=1 KYTY_BC5_SAVEDATA_DELETE_BUSY=1 KYTY_BC5_SAVEDATA_ALIASES=1 KYTY_BC5_HTTP2_FIXES=1 KYTY_BC5_PAD_OPEN_EXT=1 KYTY_BC5_JSON2_FIXES=1 KYTY_BC5_ULT_FIXES=1 KYTY_BC5_USERSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_VALUES=1 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000=1 KYTY_BC5_AUDIOOUT_CHECKS=1 KYTY_BC5_AUDIOIN_CHECKS=1 KYTY_BC5_NGS2_RACK_FIX=1 KYTY_BC5_FW_PAD=1 KYTY_BC5_LOAD_ZLIB=1 KYTY_BC5_LOAD_JPEG=1 KYTY_BC5_LOAD_IME=1 KYTY_BC5_LOAD_NPCOMMON=1 KYTY_BC5_LOAD_NPMANAGER=1 KYTY_BC5_LOAD_NPTROPHY=1"
BASE="BC5_0439_DMA_SYNC_MEC=1 BC5_0439_DMA_SYNC_LABEL=1 BC5_0439_DMA_DST_BYPASS=1 BC5_0439_ARGS_GL2WB=1"
case "${2:-}" in
    fixes) FX="$BASE BC5_DIRECT_DMA_SYNC=1"; SUF=onefx ;;
    f) FX="$BASE BC5_0439_KEEP_GDS_SYNC=1"; SUF=onef ;;
    control) FX=""; SUF=onectl ;;
    waves) FX="$BASE BC5_DIRECT_DMA_SYNC=1 BC5_0439_UMR_SCANS=5 BC5_0439_WAVES_UNLIMITED=1 BC5_0439_KEEP_XQ_WAITS=1 BC5_0439_CHAIN_WRITERS=1"; SUF=onewv; UMR=0 ;;
    waves-nocw) FX="$BASE BC5_DIRECT_DMA_SYNC=1 BC5_0439_UMR_SCANS=5 BC5_0439_WAVES_UNLIMITED=1 BC5_0439_KEEP_XQ_WAITS=1"; SUF=onewv2; UMR=0 ;; # the retry without CW (TOP, 11-22 ~09:40)
    waves-nog) FX="$BASE BC5_DIRECT_DMA_SYNC=1 BC5_0439_UMR_SCANS=5 BC5_0439_WAVES_UNLIMITED=1"; SUF=onewv; UMR=0 ;; # without G (a build before kw439)
    pc) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_UMR_SCANS=4"; SUF=onepc; UMR=0 ;; # tag pc439: the system prefix (TF ring, offchip, start state, GS rings) also in front of dcbs that draw only in chained pieces
    pcpw) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=2 BC5_0439_UMR_SCANS=2"; SUF=onepcpw; UMR=0; LT=auto ;; # tag pw439: + every piece memory wait kept for the GPU and the root's offset lists off for pieces
    pcpw1) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000 BC5_0439_COPY_LAYOUT=1 BC5_0439_UMR_SCANS=2"; SUF=onepcpw1; UMR=0; LT=auto ;; # tag pw439: the root's offset lists off for pieces only
    d2) FX="BC5_0439_BLACK_CATCH=1 BC5_0439_SOFT_LINES=50000"; SUF=oned2; UMR=1; LT=; export T3S_PRIV_CHECK=0 ;; # the diagnosis build on bake 2 (d439): no old private words
    bl) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000 BC5_0439_COPY_LAYOUT=1 BC5_0439_UMR_SCANS=2 BC5_DIRECT_FLAT_APERTURE_PIECES=1 BC5_0439_BLACK_CATCH=1 BC5_0439_SOFT_LINES=50000"; SUF=onebl; UMR=0; LT=auto ;; # tag bl439: fp + the black-picture record + every timed-out soft-CP wait with what runs after it
    fp) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000 BC5_0439_COPY_LAYOUT=1 BC5_0439_UMR_SCANS=2 BC5_DIRECT_FLAT_APERTURE_PIECES=1"; SUF=onefp; UMR=0; LT=auto ;; # tag fp439: pcpw1 + the flat-aperture rewrite for programs in pieces
    early) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_UMR_AFTER_MS=400 BC5_0439_UMR_ARM_S=20 BC5_0439_UMR_SCANS=2${T3ONE_PW:+ BC5_0439_PIECE_WAITS=$T3ONE_PW}"; SUF=oneearly; UMR=0; LT=default ;; # tag lw439 case A: the watchdog at 0.4 s of job age, armed from t 20 s, on the kernel's 2-s bound
    long) FX="BC5_0439_PREFIX_CHAINS=1 BC5_0439_WAIT_MS=12000 BC5_0439_DUMP_AT_MS=3100,7100 BC5_0439_UMR_SCANS=2${T3ONE_PW:+ BC5_0439_PIECE_WAITS=$T3ONE_PW}"; SUF=onelong; UMR=0; LT=10000 ;; # tag lw439 case B: amdgpu.lockup_timeout=10000; the host waits 12 s; dumps at 0.9, 4 and 8 s of job age
    base) FX="BC5_0439_UMR_SCANS=4"; SUF=onebase; UMR=0 ;; # four scans with bc5-gpu-hang-dump after the second (tag gp439)
    t2rows) FX="$T2ROWS $T2LIB BC5_0439_DMA_SYNC_MEC=1 BC5_0439_DMA_SYNC_LABEL=1 BC5_0439_UMR_SCANS=4"; SUF=onet2; UMR=0 ;; # the second title's rows (TOP, 11-22 ~10:15)
    t2rows-nolib) FX="$T2ROWS BC5_0439_DMA_SYNC_MEC=1 BC5_0439_DMA_SYNC_LABEL=1 BC5_0439_UMR_SCANS=4"; SUF=onet2d; UMR=0 ;; # the old/new-image comparison (TOP, 11-22 ~09:45): no candidates, the probe and the five scans
    *) echo "fixes, f, control, waves, waves-nocw, waves-nog, pc, pcpw, pcpw1, fp, early, long, base, t2rows or t2rows-nolib"; exit 1 ;;
esac
FX="$FX${T3ONE_MORE:+ $T3ONE_MORE}" # exp 0439: T3ONE_MORE="NAME=value ..." adds one run's variable (the series of 11-22 evening)
SUF0=$SUF; SUF=$SUF${T3ONE_TAG:+-$T3ONE_TAG} # exp 0439: T3ONE_TAG=<tag> gives the run its own runs/ directory
cd "$HOME/bc5-work/exp0439" || exit 1
LTV=$(cat /sys/module/amdgpu/parameters/lockup_timeout 2> /dev/null); echo "== amdgpu lockup_timeout [${LTV}]" # exp 0439 (tag lw439)
case "${LT:-}" in
    10000) case "$LTV" in 10000*) ;; *) echo "REFUSED: variant long needs amdgpu.lockup_timeout=10000 (read [${LTV}])"; exit 1 ;; esac ;;
    auto) case "$LTV" in # exp 0439 (tag lw439): the kernel's bound decides the capture (top, 11-22 ~10:55)
              10000*) FX="$FX BC5_0439_WAIT_MS=12000 BC5_0439_DUMP_AT_MS=3100,7100"; echo "== capture: case B (10-s window): host wait 12000 ms, dumps at 0.9, 4 and 8 s" ;;
              "" | 2000*) FX="$FX BC5_0439_UMR_AFTER_MS=400 BC5_0439_UMR_ARM_S=20"; echo "== capture: case A (2-s bound): the watchdog at 0.4 s of job age, armed from t 20 s" ;;
              *) echo "REFUSED: amdgpu lockup_timeout [${LTV}] is neither the default nor 10000"; exit 1 ;;
          esac ;;
    default) [ -z "$LTV" ] || [ "${LTV%%,*}" = 2000 ] || { echo "REFUSED: variant early is for the default 2-s bound (read [${LTV}])"; exit 1; } ;;
esac
echo "== kernel $(uname -r), $(rpm -q mesa-vulkan-drivers libdrm | paste -sd' '), boot $(cut -c1-8 /proc/sys/kernel/random/boot_id), up $(cut -d' ' -f1 /proc/uptime) s"
bash k439/gate439.sh || exit $? # exp 0439 (tag gt439): refuses a failed or empty read and any GPU kernel line
[ "$SUF0" = oned2 ] || grep -aq BC5_0439_ARGS_PROBE k439/normal/kyty_emulator || { echo "REFUSED: no BC5_0439_ARGS_PROBE in the binary"; exit 1; }
for w in $(echo $FX | tr ' ' '\n' | sed 's/=.*//'); do # the words this variant sets must be in the binary
    grep -aq $w k439/normal/kyty_emulator || { echo "REFUSED: no $w in the binary"; exit 1; }
done
T3P6_SUFFIX=$SUF T3P6_FLAT=1 T3S_NO_UMR=${UMR:-1} T3P6_MORE="BC5_0439_ARGS_PROBE=1${FX:+ $FX}" bash k439/t3p6.sh "$PIN"
J=$(ls -d ~/bc5-data/captures/play-* | tail -1)/gc/direct.log
echo "== ds439"; grep -a "tag ds439" runs/t3s-vunset-p$SUF/play-last.log | head -3
echo "== pa439 ($J)"; grep -a "pa439" "$J" | head -140 | cut -c1-300; grep -a "tag pa439" runs/t3s-vunset-p$SUF/play-last.log | head -2
S=$SUF0; if [ "$S" = onewv ] || [ "$S" = onewv2 ] || [ "$S" = onebase ] || [ "$S" = onepc ] || [ "$S" = oneearly ] || [ "$S" = onelong ] || [ "$S" = onepcpw ] || [ "$S" = onepcpw1 ] || [ "$S" = onefp ] || [ "$S" = onebl ] || [ "$S" = oned2 ] || [ "$S" = onet2 ] || [ "$S" = onet2d ]; then # exp 0439 (tag ms439): the wave scans, with their times against the kernel's timeout lines
    W=$(ls $(dirname "$J")/umr-waves-*.txt 2> /dev/null | head -1)
    echo "== ms439 ($W)"; grep -a "^=== ms439 scan\|No active waves\|^umr\|^\[ERROR" "$W" 2> /dev/null | head -20
    echo "== waves per scan"; awk '/^=== ms439 scan/ {if (s) print s": "n" lines"; s=$0; n=0; next} {n++} END {if (s) print s": "n" lines"}' "$W" 2> /dev/null
    echo "== kernel timeout lines"; sudo -n dmesg 2> /dev/null | grep -a "timeout, signaled" | head -4
fi
