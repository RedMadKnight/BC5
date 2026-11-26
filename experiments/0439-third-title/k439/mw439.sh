#!/usr/bin/env bash
# BC5 exp 0439 (tag mw439, the top session's order of 11-24 05:02): the memory wall. One scripted run of the third title
# on the arm-c launcher's words (t3-test.sh.ms: PIECE_WAITS=1 SERIAL=c), a fresh KYTY_BC5_SAVEDATA_DIR (never the
# maintainer's save folder), no pad input (the start runs into the opening scene by itself, as every slot run), left
# there until the bound. Records:
#   - memsample439.sh: 1-s MemAvailable, SwapFree, Dirty, GTT and VRAM in use, emulator RssAnon/RssShmem/CPU maps;
#   - BC5_GUARD_LEDGER=1: every 10 s the guard line (pinned direct, views, gtt, rss, swap, guest views) and its heaps;
#   (11-24 07:50: BC5_DIRECT_BREAKDOWN=1 is out: its SEEK_DATA walk held the game thread 16-769 s at each 512 MiB of
#   growth, 2,420 of run a's 2,600 s)
#   - MW_ROUTE=1: mwroute439.sh, t3s.sh's screen route of 11-22 (dialog, difficulty, experience, graphics Performance,
#     then a cross every 20 s), through KYTY_BC5_INPUT_CMD;
#   - a screenshot every 60 s (private).
# TEST GUARD (a diagnostic stop in this script only, never in a shortcut): when MemAvailable < 500 MiB or swap used
# > 3 GiB, /proc/meminfo and the emulator's status, smaps_rollup and map count are copied, then the emulator is ended
# (SIGTERM, SIGKILL after 10 s). Same for a new GPU kernel line (R55: the run stops, nothing more on this boot).
#   mw439.sh <arm a|b> <bound s>
#     a  the live launcher's binary 3939f323 and words
#     b  the priv30 build (it carries nm439 and va439) with the same words + BC5_0439_NO_MERGE=1 BC5_0439_VA_DEFER=1
set -u
E=$HOME/bc5-work/exp0439; K=$E/k439; DIR=$HOME/bc5-data/games/TITLE3; LOCK=$HOME/bc5-work/BOX-LOCK
ARM=${1:?a or b}; BOUND=${2:?bound s}
case "$ARM" in a) PIN=3939f323 ;; b) PIN=${MW_PIN_B:?MW_PIN_B} ;; *) echo "arm a or b"; exit 2 ;; esac
BIN=$K/normal/kyty_emulator.$PIN
# 11-24 night (vz439k, the lean A/B of R74): MW_LEAN=1 runs the pinned lean copy k439/lean/kyty_emulator.<PIN> with BC5_LEAN=1;
# MW_MH_DIR=<dir> adds MangoHud's per-frame log there (fps_only, from the start, for the bound minus 10 s)
[ "${MW_LEAN:-0}" = 1 ] && BIN=$K/lean/kyty_emulator.$PIN
tag=mw439$ARM-$(date +%m%d-%H%M); SH=$HOME/bc5-data/priv/t3-screens/$tag; mkdir -p "$SH"; chmod 700 "$SH"
G=$HOME/bc5-data/captures/memsample/$tag-guard; mkdir -p "$G"; chmod 700 "$G"
EXTRA="BC5_SYSMODULES_PACK_DIR=$DIR/fakelib BC5_DIRECT_DCC_PRESENT=2 BC5_DIRECT_EAGER_GPU_WRITE=1 BC5_DIRECT_IB_CHAIN=1 BC5_DIRECT_IB_CHAIN_FLAT=1
BC5_DIRECT_AGC_EOP_IDENT=1 BC5_DIRECT_FLAT_APERTURE=1 BC5_DIRECT_FLAT_APERTURE_PIECES=1 BC5_DIRECT_TIMEOUT_PROBE=1 BC5_DIRECT_UMR_ON_TIMEOUT=1
BC5_0439_PIECE_WAITS=1 BC5_0439_SERIAL=c
BC5_RUN_ENV=$E/run-log.env BC5_0439_FRAME_DUMP=$HOME/bc5-data/priv/frames BC5_GUARD_LEDGER=1"
[ "$ARM" = b ] && EXTRA="$EXTRA BC5_0439_NO_MERGE=1 BC5_0439_VA_DEFER=1"
# 11-24 ~14:45 (ADR 0015, the top session): the emulator runs on the host under the user manager; MW_DISTROBOX=1 keeps the
# old distrobox hop.
# 11-24 12:20 (edge test, the top session's GO 12:30-13:30): MW_DROP='WORD|WORD' removes those words, MW_ADD appends words,
# MW_TAGX names the arm in the tag, MW_SAVE_SRC is copied into the fresh save folder (the snapshot itself never written),
# MW_SHOT_S the launcher's own shot interval (default 60 s), MW_SHOT_FROM the first shot's second (default 30).
[ -n "${MW_DROP:-}" ] && EXTRA=$(echo $EXTRA | tr ' ' '\n' | grep -v -E "^(${MW_DROP})=" | tr '\n' ' ')
[ -n "${MW_ADD:-}" ] && EXTRA="$EXTRA $MW_ADD"
[ -n "${MW_MH_DIR:-}" ] && EXTRA="$EXTRA MANGOHUD=1 MANGOHUD_CONFIG=fps_only=1,alpha=0,background_alpha=0,autostart_log=1,log_interval=0,output_folder=$MW_MH_DIR,log_duration=$((BOUND - 10))"
[ -n "${MW_TAGX:-}" ] && { tag=$tag-$MW_TAGX; SH=$HOME/bc5-data/priv/t3-screens/$tag; mkdir -p "$SH"; chmod 700 "$SH"; G=$HOME/bc5-data/captures/memsample/$tag-guard; mkdir -p "$G"; chmod 700 "$G"; }
CMDF=$E/in-$tag.cmd; : > "$CMDF"; [ "${MW_ROUTE:-0}" = 1 ] && EXTRA="$EXTRA KYTY_BC5_INPUT_CMD=$CMDF"
# 11-24 night (vz439d): MW_CMD="<pad lines, | between>" is written to the input file once the emulator runs (no route)
[ "${MW_ROUTE:-0}" != 1 ] && [ -n "${MW_CMD:-}" ] && EXTRA="$EXTRA KYTY_BC5_INPUT_CMD=$CMDF"
wl=$(ls -1 "/run/user/$(id -u)/" 2> /dev/null | grep -m1 -E '^wayland-[0-9]+$'); wl=${wl:-wayland-0}
stop() { echo "mw439 STOP: $*"; exit 1; }
shot() { flock "$SH/.shot.lock" env XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=$wl DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus timeout 10 spectacle -b -n -f -o "$SH/$1.png" > /dev/null 2>&1; }
gpu_lines() { journalctl -k -b --no-pager 2> /dev/null | grep -c -E 'amdgpu.*(timeout|reset|fault|hang)|ring .* timeout|GPU reset'; }
[ "$(md5sum < "$BIN" | cut -c1-8)" = "$PIN" ] || stop "$BIN is not $PIN"
cd "$E" || exit 1
pgrep "^kyty_emulator" > /dev/null && stop "an emulator runs"
[ -s "$LOCK" ] && stop "BOX-LOCK holds: $(cat "$LOCK")"
bash "$K/gate439.sh" > /dev/null 2>&1 || stop "gate439 refuses"
bash e0439.sh lock "exp0439 mw439$ARM: memory-wall run, bound $BOUND s, until ${MW_UNTIL:-13:30}" > /dev/null 2>&1
grep -q '^exp0439 ' "$LOCK" || stop "could not take BOX-LOCK"
bash "$K/memsample439.sh" "$tag" > /dev/null 2>&1 & MS=$!
trap 'kill "$MS" 2> /dev/null; bash "$E/run0439.sh" collect normal "$tag" > /dev/null 2>&1; bash "$E/e0439.sh" unlock > /dev/null 2>&1' EXIT
g0=$(gpu_lines); SAVE=$E/save-$tag; mkdir -p "$SAVE" "$E/runs/$tag"
[ -n "${MW_SAVE_SRC:-}" ] && { cp -a "$MW_SAVE_SRC"/. "$SAVE"/ && chmod -R u+w "$SAVE" || stop "save copy failed"; }
SF=$K/.binary-words.txt; strings -n 6 "$BIN" > "$SF"
missing=$(for w in $(echo $EXTRA | tr ' ' '
' | grep -o '^\(KYTY_\)\?BC5_[A-Z0-9_]*'); do grep -qxF "$w" "$SF" || echo -n "$w "; done)
echo "mw439: words the binary does not carry: ${missing:-none}"
{ echo "tag $tag mode normal secs $BOUND start $(date '+%F %T')"; echo "binary $BIN $(md5sum < "$BIN" | cut -d' ' -f1)"; echo "kernel $(uname -r); WAYLAND_DISPLAY=$wl; extra: $(echo $EXTRA) KYTY_BC5_SAVEDATA_DIR=$SAVE"; echo "mw439: memory-wall run, no pad input, test guard MemAvailable < 500 MiB or swap used > 3 GiB"; echo "words the binary does not carry: ${missing:-none}"; } > "$E/runs/$tag/meta.txt"
# shellcheck disable=SC2086
systemd-run --user --collect --unit="bc5-0439-$tag" ${MW_SDRUN_P:+-p "$MW_SDRUN_P"} --setenv=MW_DISTROBOX="${MW_DISTROBOX:-0}" --setenv=WAYLAND_DISPLAY="$wl" --setenv=XDG_RUNTIME_DIR="/run/user/$(id -u)" \
    /usr/bin/bash -c 'ulimit -c 0; l=$1; d=$2; shift 2; if [ "${MW_DISTROBOX:-0}" = 1 ]; then exec distrobox enter ubuntu -- env "$@" "$l" "$d"; else exec env "$@" "$l" "$d"; fi' \
    _ "$K/play439.sh" "$DIR" BC5_GAME_DIR="$DIR" P439_BIN="$BIN" BC5_LEAN="${MW_LEAN:-0}" BC5_LOGS="${MW_LOGS:-1}" PLAY_CAPTURE="${MW_CAPTURE:-1}" WAYLAND_DISPLAY="$wl" KYTY_BC5_SAVEDATA_DIR="$SAVE" $EXTRA > /dev/null 2>&1
t=0; while ! pgrep "^kyty_emulator" > /dev/null && [ $t -lt 600 ]; do sleep 0.1; t=$((t + 1)); done
pgrep "^kyty_emulator" > /dev/null || stop "no emulator within 60 s"
[ "${MW_ROUTE:-0}" != 1 ] && [ -n "${MW_CMD:-}" ] && echo "$MW_CMD" | tr "|" "
" > "$CMDF"
if [ "${MW_ROUTE:-0}" = 1 ]; then
    R=$HOME/bc5-data/priv/t3-screens
    SH="$SH" O="$E/runs/$tag/route" CMDF="$CMDF" BOUND="$BOUND" T3S_ROUTE="${MW_RT:-wait45 cross need=difficulty cross need=experience cross need=graphics right check cross play}" \
        T3S_SCREEN_REFS=$R/ref-route T3S_REF_DIR=$R/ref-gm T3S_WANT=${MW_WANT:-performance} T3S_NEED_S=${MW_NEED_S:-180} bash "$K/mwroute439.sh" > /dev/null 2>&1 &
fi
t0=$(date +%s); why="bound $BOUND s"; minav=99999999; maxsw=0; nshot=${MW_SHOT_FROM:-30}; ngpu=30
while :; do
    now=$(date +%s); el=$((now - t0))
    pid=$(pgrep -o "^kyty_emulator") || { why="the emulator ended by itself at $el s"; break; }
    [ "$el" -ge "$BOUND" ] && break
    ma=$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo); st=$(awk '/^SwapTotal:/ {print $2}' /proc/meminfo); sf=$(awk '/^SwapFree:/ {print $2}' /proc/meminfo)
    su=$((st - sf)); [ "$ma" -lt "$minav" ] && minav=$ma; [ "$su" -gt "$maxsw" ] && maxsw=$su
    # 11-25 (tag fr439): MW_GUARD_MB (default 500) the MemAvailable floor, MW_GUARD_IO the IO PSI "full" avg10 limit while MemAvailable is under MW_GUARD_IO_MB (2000) (off unless set; GS reached IO full 11.9 at a load with memory to spare):
    # the 19:01 freeze came at 1.42 GB available with IO full rising 0.95 -> 2.56 -> 4.77 in its last 3 s
    io=$(awk '/^full/ {split($2, a, "="); print a[2]}' /proc/pressure/io)
    if [ "$ma" -lt $(( ${MW_GUARD_MB:-500} * 1024 )) ] || [ "$su" -gt 3145728 ] || { [ -n "${MW_GUARD_IO:-}" ] && [ "$ma" -lt $(( ${MW_GUARD_IO_MB:-2000} * 1024 )) ] && awk -v x="$io" -v l="$MW_GUARD_IO" 'BEGIN {exit !(x > l)}'; }; then
        why="TEST GUARD at $el s: MemAvailable $ma kB, swap used $su kB, IO full avg10 $io"
        cp /proc/meminfo "$G/meminfo.txt"; cp "/proc/$pid/status" "$G/status.txt" 2> /dev/null; cp "/proc/$pid/smaps_rollup" "$G/smaps_rollup.txt" 2> /dev/null
        wc -l < "/proc/$pid/maps" > "$G/maps-count.txt" 2> /dev/null; cat /sys/class/drm/card*/device/mem_info_gtt_used > "$G/gtt_used.txt" 2> /dev/null
        cat /proc/pressure/memory > "$G/psi.txt" 2> /dev/null; sync "$G"/*
        break
    fi
    [ "$el" -ge "$nshot" ] && { shot "t${el}s"; nshot=$((nshot + ${MW_SHOT_S:-60})); }
    [ "$el" -ge "$ngpu" ] && ngpu=$((ngpu + 30)) && if [ "$(gpu_lines)" != "$g0" ]; then why="a GPU kernel line at $el s ($g0 -> $(gpu_lines))"; break; fi
    sleep 1
done
echo "mw439: end: $why (min MemAvailable $minav kB, max swap used $maxsw kB)"
pgrep "^kyty_emulator" > /dev/null && pkill -TERM "^kyty_emulator"
t=0; while pgrep "^kyty_emulator" > /dev/null && [ $t -lt 100 ]; do sleep 0.1; t=$((t + 1)); done
pgrep "^kyty_emulator" > /dev/null && pkill -KILL "^kyty_emulator" && echo "needed SIGKILL"
sleep 3
echo "mw439: $tag, ran $(( $(date +%s) - t0 )) s, GPU kernel lines $g0 -> $(gpu_lines), shots in $SH, sampler $HOME/bc5-data/captures/memsample/$tag.txt"
