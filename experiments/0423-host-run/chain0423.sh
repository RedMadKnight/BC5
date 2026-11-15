#!/usr/bin/env bash
# BC5 exp 0423: does the second title run the same or better on the Bazzite host than inside the ubuntu distrobox?
# Four walks to G+240 with run0423p.sh on the SHARED normal binary 9da2a9d5 (the lean binary writes no log, so it has
# no flip counter to compare), interleaved container / host / container / host. Everything but the place is the same:
# the binary, the words (exp0413's words0413nz.txt), the derived launcher, RT on, the private copy reset from exp 0412's
# named snapshot (R45; the live saves are not read), ulimit -c 0. One BOX-LOCK line. The chain stops at the first run
# with a kernel line or a real pad key (R55, R51).
# usage (on the box, detached, in ~/bc5-work/exp0423): bash chain0423.sh
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; HERE=$(cd "$(dirname "$0")" && pwd)
NB=$W/kytyplus-build/src/kyty_emulator; MN=$(md5sum < "$NB" | cut -d' ' -f1)
case "$MN" in 9da2a9d5*) ;; *) echo "chain0423 ended $(date +%T): NOT STARTED, the shared normal is ${MN:0:8}, not 9da2a9d5"; exit 1 ;; esac
TAGS="q423c1 q423h1 q423c2 q423h2"
for t in $TAGS; do { [ -e "$R/$t-start.txt" ] || [ -e "$R/$t-end.txt" ]; } && { echo "chain0423 ended $(date +%T): NOT STARTED, tag $t used"; exit 1; }; done
[ -e "$W/BOX-LOCK.nas" ] && { echo "chain0423 ended $(date +%T): NOT STARTED, BOX-LOCK.nas exists"; exit 1; }
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0423: the second title, host vs container, 4 walks to G+240 (C H C H) on the shared normal" 40 || { echo "chain0423 ended $(date +%T): NOT STARTED"; exit 1; }
PADS=(); PADN=0
padon() { : > "$R/$1-pad.txt"; local d; for d in /dev/input/by-id/*-event-joystick; do [ -e "$d" ] || continue; stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$1-pad.txt" & PADS+=($!); done; }
padoff() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; PADS=(); pkill -u "$USER" -x evtest 2> /dev/null; PADN=$(wc -l < "$R/$1-pad.txt"); }
fin() { [ ${#PADS[@]} = 0 ] || kill "${PADS[@]}" 2> /dev/null; chain_release; }
trap fin EXIT
echo "binary normal ${MN:0:8}; host Mesa $(rpm -q mesa-vulkan-drivers | grep x86_64); container Mesa $(distrobox enter ubuntu -- dpkg-query -W -f '${Version}' mesa-vulkan-drivers 2> /dev/null < /dev/null)"
for t in $TAGS; do
    case "$t" in *h*) host=1 ;; *) host=0 ;; esac
    padon "$t"
    line=$(P_HOST=$host P_BIN=$NB P_WANT=$MN P_WORDS=$N/words0413nz.txt bash "$HERE/run0423p.sh" "$t" nozeroskip 240 | grep "^$t ")
    padoff "$t"
    echo "$t $([ $host = 1 ] && echo HOST || echo CONTAINER): ${line:-no result line}; real pad keys $PADN"
    echo "$t $(grep -h '^exp 0423 place\|^maps at' "$R/$t-start.txt" | tr '\n' ';' | cut -c1-500)"
    echo "$t route: $(grep -h 'route:' "$R/$t-start.txt" 2> /dev/null | tr '\n' ';' | cut -c1-300)"
    [ "$PADN" = 0 ] || { echo "chain0423 STOP: a real pad key in $t (the maintainer is at the box)"; break; }
    case "$line" in *"kernel lines 0, crash lines 0"*) ;; *) echo "chain0423 STOP: a kernel or crash line (or no result) in $t"; break ;; esac
    sleep 10
done
echo "chain0423 ended $(date +%T)"
