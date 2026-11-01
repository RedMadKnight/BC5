#!/usr/bin/env bash
# BC5 exp 0381, re-reads: one arm of the second title on the box, RT on, no pad, under the series' lock line.
# Private paths only: test build 2 with the catchers (reread/bin) and its wd, the snapshot saves-sample reset into the private save directory, the
# private learned file, a private mount binary. The route is gated on the journal as exp 0382's s6n0382.sh (slot 4, then the walk
# of exp 0379's walk0379s4.cmd). It stops on the first kernel line and at the box cap. It writes no lock line of its own.
# usage: ssh bc250 'bash -s' -- <tag> <token> <cap_s> [NAME=value ...] < arm0381r.sh
set -u
export LC_ALL=C
TAG=${1:?tag}; TB2_TOKEN=${2:?token}; CAP=${3:?cap}; shift 3
case "$TAG" in *[!A-Za-z0-9]* | "") echo "the tag is letters and digits"; exit 2 ;; esac
for a in "$@"; do
    case "$a" in
        BC5_MOUNT_DROP_BACKING=1 | BC5_MOUNT_DIRECT_IO=1 | BC5_MOUNT_MAX_READAHEAD_KIB=[0-9]* | BC5_MOUNT_PREFETCH_KIB=[0-9]* | BC5_MOUNT_CACHE_MIB=[0-9]* | BC5_MOUNT_THREADS=[0-9]* | BC5_MOUNT_DISK_CACHE_MIB=[0-9]* | BC5_0381_DC=1) ;;
        *) echo "not a switch of this test: $a"; exit 2 ;;
    esac
done
# A bigger limit writes, so it never comes without the private cache directory: the shared cache stays as it is.
case " $* " in *" BC5_MOUNT_DISK_CACHE_MIB="*) case " $* " in *" BC5_0381_DC=1 "*) ;; *) echo "a disk cache limit needs the private directory"; exit 2 ;; esac ;; esac
ROOT=${TB2_ROOT:-$HOME}; W=$ROOT/bc5-work; E=$W/exp0381; TB=$E/tb2; RR=$E/reread; R=$RR/raw
IN=$E/in-tb2/experiments/0381-second-title-non-f403-hangs
. "$IN/lock0381tb2.inc"
. "$RR/gate0381r.inc"
tb2_own
pgrep '^kyty_emulator' > /dev/null && { echo "GUARD: an emulator runs"; exit 3; }
LAUNCH=$RR/play-pkg-0381r.sh; MB=$RR/target/release/bc5-mount; EMU=$RR/bin/kyty_emulator
[ -x "$LAUNCH" ] && [ -x "$MB" ] && [ -x "$EMU" ] && [ -f "$RR/walk0381r.cmd" ] || { echo "not set up"; exit 1; }
mkdir -p "$R" "$RR/dc"
[ -e "$R/$TAG-start.txt" ] && { echo "tag $TAG is used"; exit 6; }
grep -qx 'RayTracing.PPSA03671=on' "$E/input-rton.cfg" || { echo "the config is not RT on"; exit 8; }
ARGS=()
for a in "$@"; do
    if [ "$a" = BC5_0381_DC=1 ]; then ARGS+=("BC5_0381_DC=$RR/dc"); else ARGS+=("$a"); fi
done
SNAP=$E/saves-sample; SD=$E/wd/_SaveData
[ -d "$SNAP/PPSA03671" ] && [ ! -L "$SD" ] && [ -d "$SD" ] || { echo "no sample or private save directory"; exit 5; }
sum() { (cd "$1" && find PPSA03671 -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16); }
case "$SD" in "$E"/*) rm -rf "$SD/PPSA03671" ;; *) echo "refusing to clear $SD"; exit 5 ;; esac
cp -a "$SNAP/PPSA03671" "$SD/PPSA03671" || { echo "the save copy failed"; exit 5; }
SAMPLE=$(sum "$SNAP")
[ "$(sum "$SD")" = "$SAMPLE" ] || { echo "the save copy differs"; exit 5; }
tb2_queue "$TB2_LINE: mount reread arm $TAG, cap $CAP s, RT on, [$*] | $(date '+%F %T')"
sync; sudo -n sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2> /dev/null || echo "caches not dropped" >> "$R/$TAG-start.txt"
CMD=$RR/in-$TAG.cmd
printf 'wait 1000\n' > "$CMD"; rm -f "$CMD.done"
{ date '+%F %T'; echo "arm $TAG cap $CAP [$*], binary $(md5sum < "$EMU" | cut -c1-8), mount $(md5sum < "$MB" | cut -c1-8), launcher $(md5sum < "$LAUNCH" | cut -c1-8), sample $SAMPLE"; echo "vm swappiness $(cat /proc/sys/vm/swappiness), page-cluster $(cat /proc/sys/vm/page-cluster), vfs_cache_pressure $(cat /proc/sys/vm/vfs_cache_pressure), min_free_kbytes $(cat /proc/sys/vm/min_free_kbytes)"; } > "$R/$TAG-start.txt"
DRM=/sys/class/drm/card1/device setsid bash "$RR/sample-reread.sh" "$R/$TAG-sample.txt" $((CAP + 60)) < /dev/null > /dev/null 2>&1 &
setsid bash "$IN/boxcap0381.sh" /exp0381/reread/bin/kyty_emulator "$CAP" "$R/$TAG-start.txt" < /dev/null > /dev/null 2>&1 &
distrobox enter ubuntu -- env BC5_EMU="$EMU" BC5_0381_PAGE_CHECK=1112eae000 BC5_0381_REOPEN_TRACE=1 BC5_MOUNT_STATS=5 KYTY_BC5_INPUT_CMD="$CMD" TB2_SERIES_LINE="$TB2_LINE" "${ARGS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &
LP=$!
EP=""
for _ in $(seq 1 120); do EP=$(pgrep -o -x kyty_emulator) && break; sleep 0.5; done
[ -n "$EP" ] || { echo "SETUP: no emulator" >> "$R/$TAG-start.txt"; wait $LP; exit 1; }
T0=$(date +%s); KFROM=$(date '+%F %T'); J=""; RS=0; K=0; FASTN=0; PREV=0; LOADT=""; G=""; WHY=""
while [ -d "/proc/$EP" ]; do
    NOW=$(($(date +%s) - T0))
    if journalctl -k --since "$KFROM" 2> /dev/null | grep -qE 'page fault|in page starting|ring [^ ]* timeout|GPU reset'; then WHY="kernel line at $NOW s"; break; fi
    [ -z "$J" ] && [ "$NOW" -ge 60 ] && { J=$(ls -td "$ROOT"/bc5-data/captures/play-*/gc 2> /dev/null | head -1)/direct.log; [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ] || { WHY="no journal of this run"; break; }; }
    if [ -n "$J" ] && [ "$RS" -lt 4 ] && [ "$NOW" -ge 85 ]; then
        read -r NT FPS3 SLOW5 <<< "$(gate "$J")"
        route_step
        echo "$NOW s: stage $RS flip ${NT:-?} flips/s ${FPS3:-?} slow ${SLOW5:-?} runs $FASTN" >> "$R/$TAG-route.txt"
        [ -n "$WHY" ] && break
    fi
    sleep 1
done
[ -n "$WHY" ] && { echo "$(date '+%F %T') stopped: $WHY" >> "$R/$TAG-start.txt"; [ -d "/proc/$EP" ] && kill -TERM "$EP"; }
wait $LP
echo "launcher exit $?" >> "$R/$TAG-launch.out"
[ -n "$J" ] && for f in page-check.txt reopen-trace.txt; do [ -f "$(dirname "$J")/$f" ] && cp "$(dirname "$J")/$f" "$R/$TAG-$f"; done
echo "private disk cache $(du -sm "$RR/dc" | cut -f1) MiB" >> "$R/$TAG-start.txt"
echo "$(date '+%F %T') arm ended, gameplay at ${G:-never}, ${WHY:-the cap or the launcher}" >> "$R/$TAG-start.txt"
tb2_queue "$TB2_LINE: mount reread arm $TAG ended | $(date '+%F %T')"
[ -z "$WHY" ]
