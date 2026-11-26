#!/usr/bin/env bash
# BC5 exp 0439 (tag st439, 11-22 ~23:00, the top session's order): one scripted start of a pinned diagnosis build to the
# first menu (no pad input), to see that it runs and what the frame-dump catcher costs while idle. The shortcut's
# environment plus BC5_0439_FRAME_DUMP=$HOME/bc5-data/priv/frames, a fresh save root, bounded 120 s (SIGTERM), shots at
# 15, 45, 90 and 115 s after the emulator's process appears, the logs collected to runs/<tag> (run0439.sh collect).
# BOX-LOCK through e0439.sh; gate439.sh before; any new GPU kernel line is reported.
#   st439.sh <md5-8 of the pinned copy k439/normal/kyty_emulator.<md5-8>>
# 11-22 ~23:20 (tag sc439, the scripted capture): ST_CMD=<lines for KYTY_BC5_INPUT_CMD, "|" between lines> (e.g. the
# L3 + R3 hold that arms sr439b), ST_BOUND=<s> (default 120), ST_SHOTS="<s> <s> ..." (default 15 45 90 115).
set -u
E=$HOME/bc5-work/exp0439; K=$E/k439; DIR=$HOME/bc5-data/games/TITLE3; LOCK=$HOME/bc5-work/BOX-LOCK
PIN=${1:?md5-8}; BIN=$K/normal/kyty_emulator.$PIN; BOUND=${ST_BOUND:-120}
tag=st439-$(date +%m%d-%H%M); SH=$HOME/bc5-data/priv/t3-screens/$tag; mkdir -p "$SH"; chmod 700 "$SH"
FD=$HOME/bc5-data/priv/frames; mkdir -p "$FD"; chmod 700 "$FD"
EXTRA="BC5_SYSMODULES_PACK_DIR=$DIR/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_IB_CHAIN_FLAT=1
BC5_DIRECT_AGC_EOP_IDENT=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_FLAT_APERTURE_PIECES=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_UMR_ON_TIMEOUT=1
BC5_0439_PIECE_DUMP=1 BC5_0439_IMPORT_PIECES=1 BC5_0439_XQ_COUNT=1 BC5_0439_ACB_DEEP=1 BC5_0439_ACB_REFUSE=1 BC5_0439_SEMA_TRACE=1
BC5_0439_THREAD_LOG=1 BC5_0439_AUDIO_CATCH=1 BC5_0439_ARGS_PROBE=1 BC5_0439_PREFIX_CHAINS=1 BC5_0439_PIECE_WAITS=1 BC5_0439_GAP_MS=1000
BC5_0439_COPY_LAYOUT=1 BC5_0439_WAIT_MS=12000 BC5_RUN_ENV=$E/run-log.env BC5_0439_FRAME_DUMP=$FD"
EXTRA="$EXTRA ${ST_MORE:-}" # ST_MORE: extra words for one run (e.g. KYTY_BC5_INPUT_TRACE=1)
if [ -n "${ST_CMD:-}" ]; then CMDF=$E/in-$tag.cmd; : > "$CMDF"; EXTRA="$EXTRA KYTY_BC5_INPUT_CMD=$CMDF"; fi
wl=$(ls -1 "/run/user/$(id -u)/" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
stop() { echo "st439 STOP: $*"; exit 1; }
shot() { env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$wl DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1; }
gpu_lines() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || stop "$BIN is not $PIN"
cd "$E" || exit 1
pgrep "^kyty_emulator" > /dev/null && stop "an emulator runs"
[ -s "$LOCK" ] && stop "BOX-LOCK holds: $(cat "$LOCK")"
bash "$K/gate439.sh" > /dev/null 2>&1 || stop "gate439 refuses"
bash e0439.sh lock "exp0439 st439: one 120-s start of $PIN to the first menu" > /dev/null 2>&1
grep -q '^exp0439 ' "$LOCK" || stop "could not take BOX-LOCK"
trap 'bash "$E/run0439.sh" collect normal "$tag" > /dev/null 2>&1; bash "$E/e0439.sh" unlock > /dev/null 2>&1' EXIT
g0=$(gpu_lines); SAVE=$E/save-$tag; mkdir -p "$SAVE" "$E/runs/$tag"
# exp 0439 (11-23, the top session's order): a switch word the binary does not carry is reported (BC5_0439_PIECE_WAITS=1
# was a silent no-op in 7277b404); a word only a script or the title reads may show up here too, so it is a report, not a stop
SF=$HOME/bc5-work/exp0439/k439/.binary-words.txt; strings -n 6 "$BIN" > "$SF" # one pass, overwritten by each start
missing=$(for w in $(echo $EXTRA | tr ' ' '
' | grep -o '^\(KYTY_\)\?BC5_[A-Z0-9_]*'); do grep -qxF "$w" "$SF" || echo -n "$w "; done)
[ -n "$missing" ] && echo "st439: words the binary does not carry: $missing"
{ echo "tag $tag mode normal secs $BOUND start $(date '+%F %T')"; echo "binary $BIN $(md5sum < "$BIN" | cut -d' ' -f1)"; echo "kernel $(uname -r); WAYLAND_DISPLAY=$wl; extra: $(echo $EXTRA) KYTY_BC5_SAVEDATA_DIR=$SAVE"; echo "st439: one start to the first menu, no pad input"; echo "words the binary does not carry: ${missing:-none}"; } > "$E/runs/$tag/meta.txt"
# shellcheck disable=SC2086
systemd-run --user --collect --unit="bc5-0439-$tag" --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; l=$1; d=$2; shift 2; exec distrobox enter ubuntu -- env "$@" "$l" "$d"' \
    _ "$K/play439.sh" "$DIR" BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN=0 BC5_LOGS=1 PLAY_CAPTURE=1 WAYLAND_DISPLAY="$wl" KYTY_BC5_SAVEDATA_DIR="$SAVE" $EXTRA > /dev/null 2>&1
t=0; while ! pgrep "^kyty_emulator" > /dev/null && [ $t -lt 600 ]; do sleep 0.1; t=$((t + 1)); done
pgrep "^kyty_emulator" > /dev/null || stop "no emulator within 60 s"
t0=$(date +%s)
[ -n "${ST_CMD:-}" ] && echo "$ST_CMD" | tr "|" "
" > "$CMDF" # the pad script, from the emulator's start
for at in ${ST_SHOTS:-15 45 90 115}; do
    sleep $((t0 + at - $(date +%s))) 2> /dev/null
    pgrep "^kyty_emulator" > /dev/null || { echo "the emulator ended before $at s"; break; }
    shot "t${at}s"
done
sleep $((t0 + BOUND - $(date +%s))) 2> /dev/null
pgrep "^kyty_emulator" > /dev/null && pkill -TERM "^kyty_emulator"
t=0; while pgrep "^kyty_emulator" > /dev/null && [ $t -lt 100 ]; do sleep 0.1; t=$((t + 1)); done
pgrep "^kyty_emulator" > /dev/null && pkill -KILL "^kyty_emulator" && echo "needed SIGKILL"
sleep 3
echo "st439: $tag, pad script [${ST_CMD:-none}], ran $(( $(date +%s) - t0 )) s, GPU kernel lines $g0 -> $(gpu_lines), frames dir: $(ls "$FD" | wc -l) entries, shots in $SH"
