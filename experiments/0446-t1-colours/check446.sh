#!/usr/bin/env bash
# BC5 exp 0446: bake 2's check runs, one per title, from ONE build (lean or normal), all into play on save copies.
#   check446.sh <tag> lean|normal <emulator binary> <md5 prefix>
#   1. The first title from its image (play-t1.sh through exp0446/ab446.sh: fresh save, ✕ at 58 s and 63 s, 180 s)
#   2. the second title from its NAS package (nas446.sh drv: exp 0412's named snapshot copy, slot 1, 600 s)
#   3. the third title from its NAS package (nas446.sh drv: a copy of exp 0439's save snapshot, its route, 600 s)
# Per run: per-second io / memory / GTT / Shmem samples, shots, MangoHud frame log (folder made first; lean: the
# figure from the log after 150 s), kernel lines before/after; the guard 1,200 MiB (the first title, third title), 600 MiB
# (second title). Stops at the first run that ends by itself or leaves a GPU line (R55/R60): no run after it on
# that boot. Needs: an empty BOX-LOCK and no emulator (each runner takes its own lock line), the NAS mounted.
# Saves: copies only; his live folders are checked unchanged at the end.
set -u
export LC_ALL=C
TAG=${1:?tag}; KIND=${2:?lean|normal}; BIN=${3:?binary}; PIN=${4:?md5 prefix}
W=$HOME/bc5-work; X=$W/exp0446; R=$X/raw; NAS=/var/mnt/nas-bc5
P2=$NAS/game.pkg
P3="$NAS/TITLE3.pkg"
S2=$W/exp0412/night/saves-named/TITLE2            # sum 1151e79071c72b17 (C locale)
S3=${CHECK_S3:-}                                     # exp 0439's third-title save snapshot dir (TITLE3): set by the caller
ROUTE3=${CHECK_ROUTE3:-}                             # exp 0439's input file for the third title's route: set by the caller
say() { echo "$(date +%T) check $TAG: $*" | tee -a "$R/$TAG-check.txt"; }
kcount() { sudo -n dmesg 2> /dev/null | grep -E 'amdgpu [0-9a-f]{4}:' | grep -v TMZ | grep -ciE 'timeout|reset|page fault|wedged'; }
livesum() { (cd "$1" 2> /dev/null && find . -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || { echo "binary is not $PIN"; exit 1; }
[ -r "$P2" ] && [ -r "$P3" ] || { echo "NAS packages not readable (mount /var/mnt/nas-bc5)"; exit 1; }
[ "$(kcount)" = 0 ] || { echo "GPU lines on this boot: no run (R55/R60)"; exit 1; }
[ -n "$S3" ] && [ -d "$S3" ] && [ -n "$ROUTE3" ] && [ -r "$ROUTE3" ] || { echo "CHECK_S3 / CHECK_ROUTE3 not set: the third title's save copy and route come from exp 0439"; exit 1; }
L2=$(livesum "$W/_SaveData-pkg-play"); L1=$(livesum "$W/_SaveData")
say "start: $KIND $BIN ($PIN), boot $(uptime -s); live saves: _SaveData $L1, _SaveData-pkg-play $L2"
LEANW=0; [ "$KIND" = lean ] && LEANW=1
# 1. The first title
( cd "$X" && AB_PIN_C=94a6513c AB_PIN_O=ef76f031 AB_PIN_N=94e0e462 AB_KIND=t1 AB_LEAN=$LEANW AB_SECS=180 AB_SHOT_S=10 \
  AB_GUARD_MB=1200 AB_ROUNDS=1 AB_ARMS="K" AB_ARM_K="$BIN|$PIN|KYTY_BC5_INPUT_CMD=$X/press446.cmd KYTY_BC5_MENU_DIR=$X/menu-full" \
  bash ./ab446.sh "${TAG}a" 2>&1 | grep -E "PASS|ENDED|GUARD|STOP" | tee -a "$R/$TAG-check.txt" )
grep -q "PASS" "$R/${TAG}aK1-end.txt" 2> /dev/null || { say "the first title did not pass: stop"; exit 2; }
[ "$(kcount)" = 0 ] || { say "GPU line after the first title: stop"; exit 2; }
# 2. and 3. the NAS titles through a derived play-pkg.sh (4 lines: lean log, mount log, save-memory dir, cd)
mkdrv() { # $1 run tag, $2 save dir to copy (title dir), $3 title id
    local wd=$X/wd/$1
    [ -e "$wd" ] && { echo "$wd exists"; return 1; }
    mkdir -p "$wd/_SaveData" "$wd/_SaveData-pkg-play" && find "$X/wda-links" -mindepth 1 -maxdepth 1 -type l -exec cp -P -t "$wd" {} + && cp -a "$2" "$wd/_SaveData/$3" || return 1
    sed -e "s#^  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log#  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=$R/$1-play-pkg-lean.log  \# exp 0446#" \
        -e "s#^LOG=~/bc5-work/play-pkg-last.log#LOG=$R/$1-play-pkg.log  \# exp 0446#" \
        -e "s#^MLOG=~/bc5-work/play-pkg-mount.log#MLOG=$R/$1-play-pkg-mount.log  \# exp 0446#" \
        -e "s#^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play\$#export KYTY_BC5_SAVEDATA_DIR=$wd/_SaveData-pkg-play  \# exp 0446#" \
        -e "s#^cd ~/bc5-work\$#cd $wd  \# exp 0446#" "$W/play-pkg.sh" > "$X/play-pkg-446.sh" && bash -n "$X/play-pkg-446.sh" && chmod +x "$X/play-pkg-446.sh"
    [ "$(diff "$W/play-pkg.sh" "$X/play-pkg-446.sh" | grep -c '^>')" = 5 ] || { echo "derived launcher is not 5 lines changed"; return 1; }
}
mkdrv "${TAG}s2" "$S2" TITLE2 || { say "second title setup failed"; exit 1; }
X446_GUARD=600 X446_MH=1 X446_ENV="KYTY_BC5_INPUT_CMD=$X/route2.cmd KYTY_BC5_MANGOHUD=0 BC5_EMU=$BIN" bash "$X/nas446.sh" "${TAG}s2" drv "$P2" 600
grep -q "ended by itself" "$R/${TAG}s2-nas.txt" && { say "second title ended by itself: stop"; exit 2; }
[ "$(kcount)" = 0 ] || { say "GPU line after the second title: stop"; exit 2; }
mkdrv "${TAG}s3" "$S3" TITLE3 || { say "third title setup failed"; exit 1; }
X446_GUARD=1200 X446_MH=1 X446_ENV="KYTY_BC5_INPUT_CMD=$ROUTE3 KYTY_BC5_MANGOHUD=0 BC5_EMU=$BIN" bash "$X/nas446.sh" "${TAG}s3" drv "$P3" 600
say "third title: $(grep -E 'ended by itself|stop: SIGTERM|GUARD' "$R/${TAG}s3-nas.txt" | tr '\n' ' ')"
[ "$(livesum "$W/_SaveData")" = "$L1" ] && [ "$(livesum "$W/_SaveData-pkg-play")" = "$L2" ] && say "live saves unchanged" || say "LIVE SAVES CHANGED: report at once"
say "kernel lines now $(kcount)"
