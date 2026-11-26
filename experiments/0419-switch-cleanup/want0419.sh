#!/usr/bin/env bash
# BC5 exp 0419: exp 0412's pass mark for K1r in candidate F. From the journal of each run given (its direct.log is named
# in raw/<tag>-journal.txt) the "timing split" lines with the largest "want" per full sync (want / full, full > 0): the
# three largest, the count of lines with full > 0 and how many are over 2 ms. A timing-split line carries no time of its
# own; the time printed is the "t <seconds>" of the nearest earlier journal line that has one.
# usage (on the box): want0419.sh <tag> [...]
R=$HOME/bc5-work/exp0413/n/raw
for tag in "$@"; do
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    [ -f "$J" ] || { echo "$tag: no journal"; continue; }
    grep -a -n 't [0-9][0-9.]* s\|^timing split' "$J" | awk -v tag="$tag" '
        /timing split/ {
            full = 0; want = 0
            if (match($0, /[0-9]+ full/)) full = substr($0, RSTART, RLENGTH) + 0
            if (match($0, /want [0-9.]+/)) want = substr($0, RSTART + 5, RLENGTH - 5) + 0
            n++
            if (full > 0) { k++; r = want / full; if (r > 2) over++; printf "%.3f ms per full sync (want %.1f over %d full) near t %s s\n", r, want, full, t > "/dev/stderr" }
            next
        }
        { if (match($0, /t [0-9][0-9.]* s/)) { t = substr($0, RSTART + 2, RLENGTH - 4) } }
        END { printf "%s: %d timing-split lines, %d with a full sync, %d over 2 ms per full sync\n", tag, n, k, over + 0 }' 2> "/tmp/want-$tag.$$"
    sort -rn "/tmp/want-$tag.$$" | head -3 | sed "s/^/  $tag largest: /"
    rm -f "/tmp/want-$tag.$$"
done
