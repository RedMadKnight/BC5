#!/usr/bin/env bash
# exp 0446: the second title from its NAS package with each row group of exp 0439's private build alone (priv61,
# normal), into play on a fresh copy of exp 0412's named snapshot (slot 1), 320 s each (about 3 minutes of play).
#   ser446.sh <tag prefix> <arm>...      arms: N I O F M P W T (as x446r3 on the first title)
# Each run: its own working directory and derived play-pkg.sh (5 lines: both logs, mount log, save-memory dir, cd),
# nas446.sh drv with X446_LEAN=0, BC5_EMU=priv61, the route ✕ at 80/86/92 s, guard 600 MiB. Stops at the first run
# that ends by itself or leaves a GPU line (R55/R60). His live saves are checked unchanged at the end.
set -u
export LC_ALL=C
PFX=${1:?tag prefix}; shift
W=$HOME/bc5-work; X=$W/exp0446; R=$X/raw; PKG=/var/mnt/nas-bc5/game.pkg; BIN=${SER_BIN:-$X/priv61/kyty_emulator}; PIN=${SER_PIN:-f21bfa76}  # SER_BIN/SER_PIN: hb446 halves
S2=$W/exp0412/night/saves-named/TITLE2
ALL="BC5_DIRECT_EAGER_GPU_WRITE=0 BC5_DIRECT_DCC_PRESENT=0 BC5_DIRECT_FLAT_APERTURE=0 BC5_DIRECT_IB_CHAIN=0 BC5_DIRECT_IB_CHAIN_FLAT=0 BC5_DIRECT_AGC_EOP_IDENT=0 BC5_DIRECT_DMA_SYNC=0 BC5_DIRECT_DMA_SYNC_MEC=0 BC5_DIRECT_DMA_SYNC_LABEL=0 BC5_DIRECT_PREFIX_CHAINS=0 BC5_DIRECT_CHAIN_WRITERS=0 KYTY_BC5_AT9_DMC=0"
SIX="BC5_0439_FLIP_LABEL_PIECES=0 KYTY_BC5_APR_RESULT_ORDER=0 KYTY_BC5_VD2_FILL=0 KYTY_BC5_VD2_SIZES=0 KYTY_BC5_0439_PAD_TOUCH=0 KYTY_BC5_0439_PAD_TIME=0"
# 11-26 06:15: the second title's own rows in the shared tree (switch_defaults.hpp {BC5_T2, ...}: DMA_SYNC F107,
# FLAT_APERTURE F249) are never turned off here: every arm before this line did (x446n2I ... x446hbA1Z), so those runs
# tested the title without its fixes, not priv61. The guard below refuses any arm that sets one of them to 0.
T2ROWS="BC5_DIRECT_DMA_SYNC BC5_DIRECT_FLAT_APERTURE"
for x in $T2ROWS; do ALL=${ALL/$x=0 /}; done
w() { local s=" $ALL "; for x in "$@"; do s=${s/ $x=0 / }; done; echo "$s"; }
words() { case "$1" in
    N) w ;; I) w BC5_DIRECT_IB_CHAIN BC5_DIRECT_IB_CHAIN_FLAT ;; O) w BC5_DIRECT_AGC_EOP_IDENT ;; F) w BC5_DIRECT_FLAT_APERTURE ;;
    M) w BC5_DIRECT_DMA_SYNC BC5_DIRECT_DMA_SYNC_MEC BC5_DIRECT_DMA_SYNC_LABEL ;; P) w BC5_DIRECT_PREFIX_CHAINS ;;
    W) w BC5_DIRECT_CHAIN_WRITERS ;; T) w KYTY_BC5_AT9_DMC ;;
    Z) echo "$(w) $SIX" ;;                                   # rows off and the six default-on words off (exp 0439 list, 11-26)
    L) echo "$(w) ${SIX/BC5_0439_FLIP_LABEL_PIECES=0 /}" ;;  # as Z but FLIP_LABEL_PIECES left on (its default)
    C) w BC5_DIRECT_DCC_PRESENT ;;                             # N with DCC_PRESENT at priv61's default (2)
    D) echo "${SER_EXTRA:-}" ;;                              # the build's and the title's own defaults, plus SER_EXTRA (exp 0439's sampler arm)
    *) return 1 ;; esac; }
kcount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -v TMZ | grep -ciE 'timeout|reset|page fault|wedged'; }
livesum() { (cd "$1" 2> /dev/null && find . -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
say() { echo "$(date +%T) ser $PFX: $*" | tee -a "$R/$PFX-ser.txt"; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || { echo "$BIN is not $PIN"; exit 1; }
[ -r "$PKG" ] || { echo "NAS package not readable"; exit 1; }
L1=$(livesum "$W/_SaveData"); L2=$(livesum "$W/_SaveData-pkg-play")
for a in "$@"; do
    # 11-26 10:20 (the top session): a measured run also waits for no compiler on the box; SER_WAIT seconds at most
    busy() { { [ -s "$W/BOX-LOCK" ] && ! { [ -n "${X446_HELD:-}" ] && [ "$(cat "$W/BOX-LOCK")" = "$X446_HELD" ]; }; } || pgrep "^kyty_emulator" > /dev/null || pgrep -x bc5-mount > /dev/null || [ "$(pgrep -c '^clang|^cc1plus|^ninja|^cargo|^rustc')" != 0 ]; }
    t0=$(date +%s); while busy && [ $(( $(date +%s) - t0 )) -lt "${SER_WAIT:-1800}" ]; do sleep 15; done
    busy && { say "box busy (lock, emulator or compiler) for ${SER_WAIT:-1800} s before $a: stop"; break; }
    say "before $a: 1-min load $(cut -d' ' -f1 /proc/loadavg), compilers $(pgrep -c '^clang|^cc1plus|^ninja|^cargo|^rustc')"
    [ -e "$X/STOP" ] && { say "STOP file: stop before $a"; break; }
    [ "$(kcount)" = 0 ] || { say "GPU line on this boot: stop before $a"; break; }
    t=$PFX$a; wd=$X/wd/$t
    [ -e "$wd" ] && { say "$wd exists: stop"; break; }
    mkdir -p "$wd/_SaveData" "$wd/_SaveData-pkg-play" && find "$X/wda-links" -mindepth 1 -maxdepth 1 -type l -exec cp -P -t "$wd" {} + && cp -a "$S2" "$wd/_SaveData/" || { say "setup failed: stop"; break; }
    sed -e "s#^  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log#  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=$R/$t-play-pkg-lean.log  \# exp 0446#" \
        -e "s#^LOG=~/bc5-work/play-pkg-last.log#LOG=$R/$t-play-pkg.log  \# exp 0446#" \
        -e "s#^MLOG=~/bc5-work/play-pkg-mount.log#MLOG=$R/$t-play-pkg-mount.log  \# exp 0446#" \
        -e "s#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play\$#export KYTY_BC5_SAVEDATA_DIR=$wd/_SaveData-pkg-play  \# exp 0446#" \
        -e "s#^cd ~/bc5-work\$#cd $wd  \# exp 0446#" "$W/play-pkg.sh" > "$X/play-pkg-446.sh"
    [ "$(diff "$W/play-pkg.sh" "$X/play-pkg-446.sh" | grep -c '^>')" = 5 ] && bash -n "$X/play-pkg-446.sh" || { say "derived launcher is not 5 lines changed: stop"; break; }
    for x in $T2ROWS; do case " $(words "$a") " in *" $x=0 "*) say "$t: arm $a turns off the title's row $x: stop"; exit 1 ;; esac; done
    say "$t: arm $a words [$(words "$a")]"
    X446_LEAN=${SER_LEAN:-0} X446_MH=${SER_MH:-0} X446_GUARD=600 X446_ENV="KYTY_BC5_INPUT_CMD=$X/route2.cmd BC5_EMU=$BIN $(words "$a")" bash "$X/nas446.sh" "$t" drv "$PKG" "${SER_SECS:-320}"
    say "$t: $(grep -E 'ended by itself|stop: SIGTERM|GUARD|amdgpu fault/reset lines after' "$R/$t-nas.txt" | tr '\n' ' ' | cut -c1-300)"
    [ -s "$R/$t-nas.txt" ] || { say "$t: no record (the runner refused): stop"; break; }
    # a guard cut (our own memory floor) is not the emulator's end: go on unless a GPU line came with it (the gate above)
    grep -q "ended by itself" "$R/$t-nas.txt" && ! grep -q "GUARD at" "$R/$t-nas.txt" && { say "$t ended by itself: stop"; break; }
    sleep 15
done
[ "$(livesum "$W/_SaveData")" = "$L1" ] && [ "$(livesum "$W/_SaveData-pkg-play")" = "$L2" ] && say "his live saves unchanged" || say "LIVE SAVES CHANGED"
