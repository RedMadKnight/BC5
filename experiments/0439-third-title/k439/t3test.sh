#!/usr/bin/env bash
# BC5 exp 0439: the launcher of the maintainer's desktop shortcut for the third title (top's order of 11-22 17:40), on
# the private test build with the candidate fixes. He plays:
# - the private normal build (pinned below, fp439 + ap439 and exp 0439's diagnosis tags), with run fp's environment
#   (as in run ap2211) minus everything scripted or intrusive: no KYTY_BC5_INPUT_CMD (no scripted pad input), no wave
#   halting (BC5_0439_UMR_WAVES, UMR_SCANS, DUMP_AT_MS out: the watchdog runs bc5-gpu-hang-dump, a register read), no
#   surface dumps; no time bound, no kill at a wall or a stall: the emulator's own exit ends it;
# - started through the user manager (systemd-run --user, rtkit), ulimit -c 0, in the ubuntu distrobox as run0439.sh;
# - BOX-LOCK taken through e0439.sh ("maintainer plays the third title"), dropped at the end; refuses with a message
#   if an emulator runs, the lock is held, or the kernel log of this boot has a GPU fault line (R55, gate439.sh);
# - the title's own save folder untouched; the capture under ~/bc5-data/captures/play-<time> (PLAY_CAPTURE=1), the
#   logs collected to runs/play-<time> at the end (run0439.sh collect).
#   t3test.sh          (DRY=1: print the command and environment, start nothing, take no lock)
set -u
E=$HOME/bc5-work/exp0439; K=$E/k439; BIN=$K/normal/kyty_emulator.7277b404; PIN=7277b404 # a pinned copy: later builds cannot replace it (11-22 20:40; 23:05 the diagnosis build with sr439b, vf439, tc439/tp439; 23:40 its program cap 0x20000; 23:45 the L3+R3 arm from a connected pad only)
DIR=$HOME/bc5-data/games/TITLE3; LOCK=$HOME/bc5-work/BOX-LOCK; NAME="BC5: the third title (test)"
say() { echo "$*"; command -v notify-send > /dev/null 2>&1 && notify-send -u critical "$NAME" "$*" 2> /dev/null; command -v kdialog > /dev/null 2>&1 && [ "${DRY:-0}" != 1 ] && kdialog --title "$NAME" --sorry "$*" 2> /dev/null; true; }
[ "$(md5sum < "$BIN" 2> /dev/null | cut -c1-8)" = "$PIN" ] || { say "The test build is not $PIN: not started."; exit 1; }
pgrep "^kyty_emulator" > /dev/null && { say "An emulator is already running: not started."; exit 1; }
[ -s "$LOCK" ] && { say "The box is busy (BOX-LOCK: $(cat "$LOCK")): not started."; exit 1; }
cd "$E" || exit 1
g=$(bash "$K/gate439.sh" 2>&1) || { say "This boot already has a GPU fault line in the kernel log (or it could not be read): reboot first. ($g)"; exit 1; }
EXTRA="BC5_SYSMODULES_PACK_DIR=$DIR/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_IB_CHAIN_FLAT=1
BC5_DIRECT_AGC_EOP_IDENT=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_FLAT_APERTURE_PIECES=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_UMR_ON_TIMEOUT=1
BC5_0439_PIECE_DUMP=1 BC5_0439_IMPORT_PIECES=1 BC5_0439_XQ_COUNT=1 BC5_0439_ACB_DEEP=1 BC5_0439_ACB_REFUSE=1 BC5_0439_SEMA_TRACE=1
BC5_0439_THREAD_LOG=1 BC5_0439_AUDIO_CATCH=1 BC5_0439_ARGS_PROBE=1 BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000
BC5_0439_COPY_LAYOUT=1 BC5_0439_WAIT_MS=12000 BC5_RUN_ENV=$E/run-log.env BC5_0439_FRAME_DUMP=$HOME/bc5-data/priv/frames"
wl=$(ls -1 "/run/user/$(id -u)/" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
tag=play-$(date +%m%d-%H%M)
# exp 0439 (11-23): a switch word the binary does not carry is reported (BC5_0439_PIECE_WAITS=1 was a silent no-op)
SF=$HOME/bc5-work/exp0439/k439/.binary-words.txt; strings -n 6 "$BIN" > "$SF" # one pass, overwritten by each start
missing=$(for w in $(echo $EXTRA | tr ' ' '
' | grep -o '^\(KYTY_\)\?BC5_[A-Z0-9_]*'); do grep -qxF "$w" "$SF" || echo -n "$w "; done)
if [ "${DRY:-0}" = 1 ]; then
    echo "DRY: binary $PIN ok, no emulator, lock free, $g"
    echo "DRY: systemd-run --user --wait --collect --unit=bc5-0439-$tag: ulimit -c 0; distrobox enter ubuntu -- env BC5_GAME_DIR=$DIR P439_BIN=$BIN BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=1 WAYLAND_DISPLAY=$wl <EXTRA> $K/play439.sh $DIR"
    echo "DRY: EXTRA = $(echo $EXTRA)"
    echo "DRY: lock text would be: maintainer plays the third title; logs to runs/$tag"
    echo "DRY: words the binary does not carry: ${missing:-none}"
    exit 0
fi
bash e0439.sh lock "maintainer plays the third title" > /dev/null 2>&1
grep -q '^exp0439 ' "$LOCK" || { say "Could not take BOX-LOCK ($(cat "$LOCK" 2> /dev/null)): not started."; exit 1; }
trap 'bash "$E/run0439.sh" collect normal "$tag" > /dev/null 2>&1; bash "$E/e0439.sh" unlock > /dev/null 2>&1' EXIT
mkdir -p "$E/runs/$tag"
{ echo "tag $tag mode normal secs none start $(date '+%F %T')"; echo "binary $BIN $(md5sum < "$BIN" | cut -d' ' -f1)"; echo "kernel $(uname -r); WAYLAND_DISPLAY=$wl; extra: $(echo $EXTRA)"; echo "the maintainer plays (t3test.sh)"; echo "words the binary does not carry: ${missing:-none}"; } > "$E/runs/$tag/meta.txt"
# shellcheck disable=SC2086
systemd-run --user --wait --collect --unit="bc5-0439-$tag" --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; l=$1; d=$2; shift 2; exec distrobox enter ubuntu -- env "$@" "$l" "$d"' \
    _ "$K/play439.sh" "$DIR" BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=1 WAYLAND_DISPLAY="$wl" $EXTRA > /dev/null 2>&1
