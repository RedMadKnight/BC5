#!/bin/bash
# Shared settings for the bc5-mount PFSC benchmarks (experiment 0116). Private
# data is read only through bc5-mount; the file list stays in ~/bc5-data (private) and is deleted after the runs.
DUMP="$HOME/bc5-data/games/PPSA21567 - ASTRO BOT_4xx.ffpfsc"
OLD=$HOME/bc5-work/bc5-tools-ubuntu/release/bc5-mount
NEW=$HOME/bc5-work/bc5-mount-bench/pfsc/release/bc5-mount
W=$HOME/bc5-data/bench-0116  # private: holds the file list
MNT=$HOME/bc5-data/mnt/pfsc-bench
mkdir -p "$W"

if pgrep -x kyty_emulator >/dev/null || pgrep -f bc5-run >/dev/null; then
    echo "a game is running; not benchmarking" >&2
    exit 1
fi

# 8 largest files under 512 MiB, one path per line (paths may contain spaces).
pick_files() {
    [ -s "$W/list.txt" ] || "$OLD" ls "$DUMP" / -r > "$W/list.txt"
    grep '^-' "$W/list.txt" | awk '$2 <= 536870912' | sort -k2,2nr | head -${NFILES:-8} \
        | sed -E 's/^- +[0-9]+  //' > "$W/files.txt"
    awk '$2 <= 536870912' <(grep '^-' "$W/list.txt") | sort -k2,2nr | head -${NFILES:-8} \
        | awk -v n="${NFILES:-8}" '{s += $2} END {printf n " files, %.0f MiB in total\n", s / 1048576}'
}
