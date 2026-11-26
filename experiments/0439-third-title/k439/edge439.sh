#!/usr/bin/env bash
# BC5 exp 0439 (tag eg439, the top session's GO of 11-24 12:20, slot 12:30-13:30): the edge-block test plus the top's
# EAGER_GPU_WRITE question. Arms in this order, each mw439.sh a <bound> from a fresh copy of the 10:46 snapshot save
# (TITLE3-20261124-x439mwu-end, read only), the kernel-line sampler (MS_KLOG=1, 0.5 s), a shot every 2 s while the
# edge script moves the sticks:
#   c   arm c as it is (3939f323, PIECE_WAITS=1 SERIAL=c)
#   cE  arm c without BC5_DIRECT_EAGER_GPU_WRITE
#   S   SERIAL=1 instead of c (no one-frame lateness)
#   D   arm c + BC5_0439_DCC_UNCOMPRESSED=1
# Stops before the next arm on any new GPU kernel line (R55) or when it is past EG_UNTIL (default 13:22).
#   edge439.sh <bound s> [arms]
set -u
K=$HOME/bc5-work/exp0439/k439; B=${1:?bound}; ARMS=${2:-c cE S D}
SRC=$HOME/bc5-data/saves/TITLE3-20261124-x439mwu-end
gl() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
g0=$(gl)
for a in $ARMS; do
    [ "$(gl)" = "$g0" ] || { echo "eg439: a GPU kernel line: no more arms"; break; }
    [ "$(date +%H%M)" -lt "$(echo "${EG_UNTIL:-13:22}" | tr -d :)" ] || { echo "eg439: past ${EG_UNTIL:-13:22}: $a not run"; break; }
    case $a in
        c) d=; ad= ;;
        cE) d=BC5_DIRECT_EAGER_GPU_WRITE; ad= ;;
        S) d=BC5_0439_SERIAL; ad=BC5_0439_SERIAL=1 ;;
        D) d=; ad=BC5_0439_DCC_UNCOMPRESSED=1 ;;
        *) echo "eg439: unknown arm $a"; continue ;;
    esac
    echo "eg439: $(date +%T) arm $a"
    MS_KLOG=1 MS_INTERVAL=0.5 MW_TAGX=eg$a MW_DROP="$d" MW_ADD="$ad" MW_SAVE_SRC=$SRC MW_SHOT_S=100000 MW_ROUTE=1 \
        MW_RT="${EG_RT:-wait40 cross wait50 cross wait60 cross wait70 cross wait80 cross wait95 cross wait110 cross wait125 edge}" \
        bash "$K/mw439.sh" a "$B" 2>&1 | tail -3
    sleep 15
done
echo "eg439: $(date +%T) done; GPU kernel lines $g0 -> $(gl)"
