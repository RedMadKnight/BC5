#!/usr/bin/env bash
# BC5 exp 0417: the save-memory finding against the foreign pad input. save0417.sh's seven pairs (2026-11-13 14:46-15:06)
# all wrote the small file (1fa391a4, 30,095 non-zero bytes) on both builds with the table on and off; the two large
# files (97fb2aba, 164,965 bytes) were written at 11:59 and 12:19, inside the window in which the maintainer pressed
# the pad (README section 10). Question: does the SHARED build write the large file when a cross is pressed during
# the 120 s, and does the next start then crash? One pair per build given; the runner's own keys go through
# KYTY_BC5_INPUT_CMD; evtest records real pad keys beside it. Private test save directories only.
# usage (on the box, detached): save0417k.sh <tag> <shared|B> [<tag> <shared|B> ...]
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; WD=$N/wda; F=_SaveData/PPSA21564/sce_sdmemory/memory.dat
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0417 save-memory finding: ASTRO BOT with scripted cross presses, private test save directories" $(($# * 2 + 3)) || { echo "save0417k ended $(date +%T): NOT STARTED"; exit 1; }
KEEP=$WD/_SaveData.before-save0417k-$$
mv "$WD/_SaveData" "$KEEP" || exit 1
st() { if [ -f "$WD/$F" ]; then echo "$(md5sum < "$WD/$F" | cut -c1-8) $(tr -d '\000' < "$WD/$F" | wc -c)"; else echo "none 0"; fi; }
while [ $# -ge 2 ]; do
    tag=$1; which=$2; shift 2
    case "$which" in shared) bin=$W/kytyplus-build/src/kyty_emulator ;; B) bin=$W/exp0413/p/build-normal/src/kyty_emulator ;; *) bin=$which ;; esac
    want=$(md5sum < "$bin" | cut -d' ' -f1)
    rm -rf "$WD/_SaveData"; mkdir "$WD/_SaveData" || break
    CMD=$N/cmd-$tag.txt; : > "$CMD"; : > "$R/$tag-pad.txt"; PADS=()
    for d in /dev/input/by-id/*-event-joystick; do
        [ -e "$d" ] || continue
        stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$tag-pad.txt" &
        PADS+=($!)
    done
    (for t in 30 15 15 15 15; do sleep "$t"; printf 'press cross\n' >> "$CMD"; done) &
    KP=$!
    a=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "$tag" astro 120 KYTY_BC5_INPUT_CMD="$CMD" 2>&1 | tail -1)
    kill "$KP" "${PADS[@]}" 2> /dev/null; pkill -u "$USER" -x evtest 2> /dev/null
    s=$(st)
    rm -rf "$WD/_SaveData.$tag"; cp -a "$WD/_SaveData" "$WD/_SaveData.$tag"
    b=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "${tag}n" astro 30 2>&1 | tail -1)
    echo "$tag ${want:0:8}: $(wc -l < "$CMD") cross presses sent, real pad keys $(wc -l < "$R/$tag-pad.txt"); file $s; first: $(echo "$a" | cut -c1-110)"
    echo "$tag next default start: $(echo "$b" | cut -c1-140)"
    case "$a$b" in *"kernel lines 0"*) ;; *) echo "save0417k STOP: no clean kernel line in $tag"; break ;; esac
done
rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"
echo "save0417k ended $(date +%T)"
