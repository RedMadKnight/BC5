#!/usr/bin/env bash
# BC5 exp 0388 from the laptop: G1 E1 F1 E2 F2 G2 E3 F3 E4 F4 G3 E5 F5, one go0388.sh at a time, under one deadline of 75 min.
# A run that did not reach the fight gets at most one replacement in the whole series. Any stop ends the series.
# usage: series0388.sh     Exit: 0 the rule was applied; 1 the series stopped; the RESULT lines are in raw/series.txt
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LIMIT=4500; RUN_NEED=430   # 35 min for everything; run0388.sh keeps kill, reap and release inside it
GO=$HERE/go0388.sh
case "${D19_RUN_FAKE:-}" in *d19-test-*) . "$D19_RUN_FAKE" ;; esac
DL=$(($(date +%s) + LIMIT))
OUT=$HERE/raw/series.txt; ROWS=$HERE/raw/rows.txt
mkdir -p "$HERE/raw"; : > "$OUT"; : > "$ROWS"
SPARE=1
one() {  # tag, fix. Sets CL and CRASH
    local tag=$1 fix=$2 out rc line
    [ $((DL - $(date +%s))) -ge "$RUN_NEED" ] || { echo "series: under $RUN_NEED s left at $tag"; return 1; }
    out=$(bash "$GO" "$tag" "$fix" "$DL" 2>&1); rc=$?
    printf '%s\n' "$out" | tee -a "$OUT"
    [ "$rc" = 0 ] || { echo "series: $tag stopped, rc $rc"; return 1; }
    line=$(printf '%s\n' "$out" | grep '^RESULT ' | tail -1)
    case "$line" in *" saves same CLASS "*) ;; *) echo "series: $tag has no clean result: $line"; return 1 ;; esac
    CL=${line##* CLASS }; CL=${CL%% *}
    CRASH=$(printf '%s\n' "$line" | sed -n 's/.* crash \([a-z]*\) reached.*/\1/p')
    echo "$tag $fix $CL $CRASH" >> "$ROWS"
    case "$CL" in
        KERNEL | INVALID) echo "series: $tag is $CL"; return 1 ;;
    esac
    if [ "$fix" = on ] && [ "$CRASH" = target ]; then echo "series: REGRESSION at $tag"; return 1; fi
    return 0
}
for t in G1:off E1:off F1:off E2:off F2:off G2:off E3:off F3:off E4:off F4:off G3:off E5:off F5:off; do
    tag=${t%:*}; fix=${t#*:}
    one "$tag" "$fix" || exit 1
    if [ "$CL" = NOT_ROUTED ]; then
        if [ "$SPARE" = 1 ]; then SPARE=0; sed -i "/^$tag /d" "$ROWS"; one "${tag}R" "$fix" || exit 1; [ "$CL" != NOT_ROUTED ] || echo "series: $tag not routed twice"
        else echo "series: $tag not routed, no replacement left"; fi
    fi
done
python "$HERE/check0388.py" rule "$ROWS" | tee -a "$OUT"
