#!/usr/bin/env bash
# BC5 exp 0417: counts for the save-memory finding (the top session, 2026-11-13: "settle it by counts"). ASTRO BOT,
# private test save directories only (~/bc5-work/exp0413/n/wda; nothing of the maintainer's saves is read or written).
# One pair = a FRESH empty _SaveData, a run of <secs> s with the given words, the save-memory file's sum and its count
# of non-zero bytes, a copy of the directory kept as wda/_SaveData.<tag>, then a 30 s default start on that file.
# One lock line for the whole list. A kernel line stops the list; a crash of the second start is the RESULT, not a stop.
# usage (on the box, detached): save0417.sh <list file>
#   list file lines:  <tag> <shared|B|path-of-binary> <secs> <astro|astrolog> [KEY=VALUE ...]      (# starts a comment)
set -u
ulimit -c 0
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; R=$N/raw; WD=$N/wda; F=_SaveData/PPSA21564/sce_sdmemory/memory.dat
LIST=${1:?the list file}
cd "$N" || exit 1
. "$N/chainlock0417.inc"
n=$(grep -c '^[^#]' "$LIST")
[ -n "${CHAIN_LOCKLINE:-}" ] || chain_claim "exp 0417 save-memory counts: $n ASTRO BOT pairs on private test save directories" $((n * 3 + 5)) || { echo "save0417 ended $(date +%T): NOT STARTED"; exit 1; }
KEEP=$WD/_SaveData.before-save0417-$$
mv "$WD/_SaveData" "$KEEP" || { echo "cannot set the current private save directory aside"; exit 1; }
back() { rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"; }
st() { if [ -f "$WD/$F" ]; then echo "$(md5sum < "$WD/$F" | cut -c1-8) $(tr -d '\000' < "$WD/$F" | wc -c)"; else echo "none 0"; fi; }
printf '%-10s %-8s %-9s %-34s | %-8s %8s | %s\n' tag build mode words file-md5 non-zero "the next default start"
while read -r tag which secs kind words; do
    case "$tag" in '' | '#'*) continue ;; esac
    case "$which" in
        shared) bin=$W/kytyplus-build/src/kyty_emulator ;;
        B) bin=$W/exp0413/p/build-normal/src/kyty_emulator ;;
        *) bin=$which ;;
    esac
    [ -x "$bin" ] || { echo "$tag: no binary $bin"; continue; }
    want=$(md5sum < "$bin" | cut -d' ' -f1)
    rm -rf "$WD/_SaveData"; mkdir "$WD/_SaveData" || break
    # shellcheck disable=SC2086
    a=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "$tag" "$kind" "$secs" $words 2>&1 | tail -1)
    s=$(st)
    rm -rf "$WD/_SaveData.$tag"; cp -a "$WD/_SaveData" "$WD/_SaveData.$tag"
    b=$(P_BIN=$bin P_WANT=$want bash ./start0413g.sh "${tag}n" astro 30 2>&1 | tail -1)
    case "$a" in *"PASS: ran $secs s"*) ra=ran ;; *) ra="FIRST RUN: $(echo "$a" | cut -c1-70)" ;; esac
    case "$b" in *"PASS: ran 30 s"*) rb="passes" ;; *"ENDED BY ITSELF"*) rb="CRASHES ($(echo "$b" | grep -o 'ENDED BY ITSELF at [0-9]* s'))" ;; *) rb="? $(echo "$b" | cut -c1-70)" ;; esac
    printf '%-10s %-8s %-9s %-34s | %-8s %8s | %s%s\n' "$tag" "${want:0:8}" "$kind/$secs" "${words:-(defaults)}" ${s% *} "${s#* }" "$rb" "$([ "$ra" = ran ] || echo "; $ra")"
    case "$a$b" in *"kernel lines 0"*"kernel lines 0"*) ;; *"kernel lines 0"*) ;; *) echo "save0417 STOP: a kernel line or no result line in $tag"; break ;; esac
done < "$LIST"
back
echo "save0417 ended $(date +%T)"
