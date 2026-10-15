#!/bin/bash
# bc5-mount cat: 8 parallel readers of different files, then 4 of the same file,
# old binary vs new (and new with a 16 MiB cache), warm page cache. Prints wall, user and system seconds.
set -u
. "$(dirname "$0")/bench-common.sh"
pick_files
mapfile -t FILES < "$W/files.txt"

run_diff() { # binary
    local bin=$1
    /usr/bin/time -f "%e %U %S" bash -c '
        bin=$1; dump=$2; shift 2
        for f in "$@"; do "$bin" cat "$dump" "$f" > /dev/null & done
        wait' _ "$bin" "$DUMP" "${FILES[@]}" 2>&1 | tail -1
}

run_same() { # binary
    local bin=$1
    /usr/bin/time -f "%e %U %S" bash -c '
        bin=$1; dump=$2; f=$3
        for i in 1 2 3 4; do "$bin" cat "$dump" "$f" > /dev/null & done
        wait' _ "$bin" "$DUMP" "${FILES[0]}" 2>&1 | tail -1
}

echo "warm-up"; run_diff "$OLD" > /dev/null
for round in 1 2 3; do
    for which in OLD NEW NEW16; do
        if [ $which = NEW16 ]; then bin=$NEW; export BC5_MOUNT_CACHE_MIB=16; else bin=${!which}; unset BC5_MOUNT_CACHE_MIB; fi
        echo "round $round $which diff8 (wall user sys): $(run_diff "$bin")"
        echo "round $round $which same4 (wall user sys): $(run_same "$bin")"
    done
done
