#!/usr/bin/env bash
# BC5 exp 0439 (tag mn439, 11-22 ~22:40, the top session's order): the intro-movie noise checks. Three short starts to
# the "presents" card, each on a FRESH save root, one screenshot 4 s after the emulator's process appears (d3r2's t004s
# was taken at about the same point), the emulator ended with SIGTERM at 6.5 s:
#   a = ce23a3eb with KYTY_BC5_0439_PAD_TOUCH=0 KYTY_BC5_0439_PAD_TIME=0;  b = 5f582a73 as it is;  c = ce23a3eb as it is.
# The shortcut's environment (t3test.sh / t3-test.sh EXTRA), the same launcher (play439.sh through the user manager,
# ulimit -c 0, the ubuntu distrobox). BOX-LOCK through e0439.sh for the whole series; gate439.sh before each start and
# the kernel log after: any GPU line stops the series. Shots to ~/bc5-data/priv/t3-screens/mn439-<time>/ (private).
#   mn439.sh            (DRY=1: print, start nothing)
set -u
E=$HOME/bc5-work/exp0439; K=$E/k439; DIR=$HOME/bc5-data/games/TITLE3; LOCK=$HOME/bc5-work/BOX-LOCK
SH=$HOME/bc5-data/priv/t3-screens/mn439-$(date +%H%M); mkdir -p "$SH"; chmod 700 "$SH"
EXTRA="BC5_SYSMODULES_PACK_DIR=$DIR/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_IB_CHAIN_FLAT=1
BC5_DIRECT_AGC_EOP_IDENT=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_FLAT_APERTURE_PIECES=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_UMR_ON_TIMEOUT=1
BC5_0439_PIECE_DUMP=1 BC5_0439_IMPORT_PIECES=1 BC5_0439_XQ_COUNT=1 BC5_0439_ACB_DEEP=1 BC5_0439_ACB_REFUSE=1 BC5_0439_SEMA_TRACE=1
BC5_0439_THREAD_LOG=1 BC5_0439_AUDIO_CATCH=1 BC5_0439_ARGS_PROBE=1 BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000
BC5_0439_COPY_LAYOUT=1 BC5_0439_WAIT_MS=12000 BC5_RUN_ENV=$E/run-log.env"
wl=$(ls -1 "/run/user/$(id -u)/" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
stop() { echo "mn439 STOP: $*"; exit 1; }
shot() { env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$wl DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1; }
gpu_lines() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
cd "$E" || exit 1
for v in a b c; do
    case $v in
        a) BIN=$K/normal/kyty_emulator.ce23a3eb; PIN=ce23a3eb; MORE="KYTY_BC5_0439_PAD_TOUCH=0 KYTY_BC5_0439_PAD_TIME=0" ;;
        b) BIN=$K/normal/kyty_emulator.5f582a73; PIN=5f582a73; MORE="" ;;
        c) BIN=$K/normal/kyty_emulator.ce23a3eb; PIN=ce23a3eb; MORE="" ;;
    esac
    [ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || stop "$BIN is not $PIN"
done
if [ "${DRY:-0}" = 1 ]; then echo "DRY: shots to $SH; wayland $wl; gpu lines now $(gpu_lines)"; exit 0; fi
pgrep "^kyty_emulator" > /dev/null && stop "an emulator runs"
[ -s "$LOCK" ] && stop "BOX-LOCK holds: $(cat "$LOCK")"
bash e0439.sh lock "exp0439 mn439: three 6-s intro starts (movie noise)" > /dev/null 2>&1
grep -q '^exp0439 ' "$LOCK" || stop "could not take BOX-LOCK"
trap 'bash "$E/e0439.sh" unlock > /dev/null 2>&1' EXIT
g0=$(gpu_lines)
for v in a b c; do
    case $v in
        a) BIN=$K/normal/kyty_emulator.ce23a3eb; MORE="KYTY_BC5_0439_PAD_TOUCH=0 KYTY_BC5_0439_PAD_TIME=0" ;;
        b) BIN=$K/normal/kyty_emulator.5f582a73; MORE="" ;;
        c) BIN=$K/normal/kyty_emulator.ce23a3eb; MORE="" ;;
    esac
    bash "$K/gate439.sh" > /dev/null 2>&1 || stop "gate439 refuses before $v"
    SAVE=$E/save-mn439-$v-$(date +%H%M%S); mkdir -p "$SAVE"
    unit=bc5-0439-mn439-$v-$(date +%H%M%S)
    # shellcheck disable=SC2086
    systemd-run --user --collect --unit="$unit" --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
        /usr/bin/bash -c 'ulimit -c 0; l=$1; d=$2; shift 2; exec distrobox enter ubuntu -- env "$@" "$l" "$d"' \
        _ "$K/play439.sh" "$DIR" BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=0 WAYLAND_DISPLAY="$wl" KYTY_BC5_SAVEDATA_DIR="$SAVE" $EXTRA $MORE > /dev/null 2>&1
    t=0; while ! pgrep "^kyty_emulator" > /dev/null && [ $t -lt 600 ]; do sleep 0.1; t=$((t + 1)); done
    pgrep "^kyty_emulator" > /dev/null || stop "$v: no emulator within 60 s"
    t0=$(date +%s.%N)
    sleep 4; shot "mn-$v-t4"
    sleep "$(awk -v a="$t0" -v b="$(date +%s.%N)" 'BEGIN { d = a + 6.5 - b; print (d > 0 ? d : 0) }')"
    pkill -TERM "^kyty_emulator"
    t=0; while pgrep "^kyty_emulator" > /dev/null && [ $t -lt 100 ]; do sleep 0.1; t=$((t + 1)); done
    pgrep "^kyty_emulator" > /dev/null && pkill -KILL "^kyty_emulator" && echo "$v: needed SIGKILL"
    sleep 2
    g=$(gpu_lines)
    echo "$v: bin $(md5sum < "$BIN" | cut -c1-8) extra [$MORE] save $SAVE shot $(ls -la "$SH/mn-$v-t4.png" 2> /dev/null | awk '{print $5}') bytes, GPU kernel lines $g0 -> $g"
    [ "$g" = "$g0" ] || stop "a GPU kernel line after $v"
done
echo "mn439: done, shots in $SH"
