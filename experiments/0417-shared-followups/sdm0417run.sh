#!/usr/bin/env bash
# BC5 exp 0417 (tag sdm417): ASTRO BOT's first save from an empty directory, the catcher and the candidate fixes at
# once (README section 12). Candidate C's PRIVATE normal build; private test save directories only.
# One arm = a fresh empty _SaveData; 120 s with a cross at 30, 45, 60, 75 and 90 s (KYTY_BC5_INPUT_CMD) and the arm's
# words; the files; a copy kept as wda/_SaveData.<tag>; then a 30 s start on those files with the same words.
# The call log (KYTY_BC5_SAVEDATA_MEMORY_LOG=1) is on in every run; evtest records real pad keys (a key voids the arm).
# One lock line. A kernel line stops the list; a crash of the second start is a RESULT.
# usage (on the box, detached): sdm0417run.sh <list>      list lines: <tag> [KEY=VALUE ...]   (# starts a comment)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; WD=$N/wda; T=_SaveData/PPSA21564
LIST=${1:?the list file}
cd "$N" || exit 1
. "$N/chainlock0417.inc"
n=$(grep -c '^[^#]' "$LIST")
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0417 save data memory: $n ASTRO BOT arms with scripted cross presses, private test save directories" $((n * 3 + 3)) || { echo "sdm0417run ended $(date +%T): NOT STARTED"; exit 1; }
bin=$W/exp0413/p/build-normal/src/kyty_emulator; want=$(md5sum < "$bin" | cut -d' ' -f1)
grep -aqF KYTY_BC5_SAVEDATA_MEMORY_LOG "$bin" || { echo "sdm0417run ended $(date +%T): NOT STARTED, the private build has no sdm417 (build candidate C first)"; exit 1; }
echo "binary: private normal $want"
KEEP=$WD/_SaveData.before-sdm0417-$$
mv "$WD/_SaveData" "$KEEP" || exit 1
files() { (cd "$WD/$T" 2> /dev/null && for f in sce_sdmemory*/*; do [ -f "$f" ] && echo "$f $(md5sum < "$f" | cut -c1-8) $(tr -d '\000' < "$f" | wc -c)"; done | tr '\n' ';'); }
kinds() { for k in setup get set sync; do printf '%s %s, ' "$k" "$(grep -a -c "sdm417 $k:" "$1" 2> /dev/null)"; done; echo "slots $(grep -a -o 'sdm417 [a-z]*: slot [0-9]*' "$1" 2> /dev/null | awk '{print $4}' | sort -u | tr '\n' ' ')"; }
while read -r tag words; do
    case "$tag" in '' | '#'*) continue ;; esac
    rm -rf "$WD/_SaveData"; mkdir "$WD/_SaveData" || break
    CMD=$N/cmd-$tag.txt; : > "$CMD"; : > "$R/$tag-pad.txt"; PADS=()
    for d in /dev/input/by-id/*-event-joystick; do
        [ -e "$d" ] || continue
        stdbuf -oL evtest "$d" 2> /dev/null | grep --line-buffered 'EV_KEY.*value 1' >> "$R/$tag-pad.txt" &
        PADS+=($!)
    done
    (for t in 30 15 15 15 15; do sleep "$t"; printf 'press cross\n' >> "$CMD"; done) &
    KP=$!
    # shellcheck disable=SC2086
    a=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "$tag" astro 120 KYTY_BC5_INPUT_CMD="$CMD" KYTY_BC5_SAVEDATA_MEMORY_LOG=1 $words 2>&1 | tail -1)
    kill "$KP" "${PADS[@]}" 2> /dev/null; pkill -u "$USER" -x evtest 2> /dev/null
    f=$(files)
    rm -rf "$WD/_SaveData.$tag"; cp -a "$WD/_SaveData" "$WD/_SaveData.$tag"
    # shellcheck disable=SC2086
    b=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "${tag}n" astro 30 KYTY_BC5_SAVEDATA_MEMORY_LOG=1 $words 2>&1 | tail -1)
    echo "== $tag [${words:-no fix}]: real pad keys $(wc -l < "$R/$tag-pad.txt"); first run: $(echo "$a" | cut -d';' -f1 | cut -c1-80)"
    echo "$tag files: $f"
    echo "$tag first run calls: $(kinds "$R/$tag-play.log")"
    grep -a 'sdm417 setup:' "$R/$tag-play.log" | sort | uniq -c | cut -c1-230
    grep -a 'sdm417 set:.*piece' "$R/$tag-play.log" | sed 's/ fnv [0-9a-f]*//' | awk '{$1=""; print}' | sort | uniq -c | sort -rn | head -6 | cut -c1-200
    case "$b" in *"PASS: ran 30 s"*) rb=PASSES ;; *"ENDED BY ITSELF"*) rb="CRASHES ($(echo "$b" | grep -o 'ENDED BY ITSELF at [0-9]* s'))" ;; *) rb="? $(echo "$b" | cut -c1-80)" ;; esac
    echo "$tag next start: $rb; calls: $(kinds "$R/${tag}n-play.log")"
    grep -a 'sdm417' "$R/${tag}n-play.log" | tail -5 | cut -c1-230
    [ "$rb" = PASSES ] || grep -a -m2 'exception_address\|Access violation\|Segmentation' "$R/${tag}n-crash.txt" | cut -c1-160
    case "$a$b" in *"kernel lines 0"*) ;; *) echo "sdm0417run STOP: no clean kernel line in $tag"; break ;; esac
done < "$LIST"
rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"
echo "sdm0417run ended $(date +%T)"
