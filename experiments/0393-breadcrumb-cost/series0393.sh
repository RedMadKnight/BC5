#!/usr/bin/env bash
# BC5 exp 0393 from the laptop: the cost test's runs, one go0393.sh at a time, under one deadline of 85 min. O is
# breadcrumbs off, L level 1, T level 2; the order mixes the arms against drift. Any stop ends the series, no retry.
# usage: series0393.sh [tags]     Exit: 0 every run passed; 1 the series stopped; the lines are in raw/series.txt
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
LIMIT=5100; RUN_NEED=720   # run0393.sh keeps kill, reap and release inside RUN_NEED
GO=$HERE/go0393.sh
case "${D19_RUN_FAKE:-}" in *d19-test-*) . "$D19_RUN_FAKE" ;; esac
DL=${E0393_DL:-$(($(date +%s) + LIMIT))}  # the top session's deadline counts from the first claim, the build's
OUT=$HERE/raw/series.txt
mkdir -p "$HERE/raw"
say() { echo "$*" | tee -a "$OUT"; }
for tag in ${*:-O1 L1 T1 O2 L2 T2 O3 L3}; do
    [ $((DL - $(date +%s))) -ge "$RUN_NEED" ] || { say "series: under $RUN_NEED s left at $tag"; exit 1; }
    out=$(bash "$GO" "$tag" "$DL" 2>&1); rc=$?
    say "$out"
    [ "$rc" = 0 ] || { say "series: $tag stopped, rc $rc"; exit 1; }
    case "$(printf '%s\n' "$out" | grep '^RESULT ' | tail -1)" in
        *" verdict pass") ;;
        *) say "series: $tag did not pass"; exit 1 ;;
    esac
done
say "series: every run passed"
