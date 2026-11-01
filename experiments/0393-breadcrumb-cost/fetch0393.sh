#!/usr/bin/env bash
# BC5 exp 0393 from the laptop: copies the run files for the repo into raw/ and the frame profile lines (numbers only, too
# big to commit) into the given directory. It only reads the box. The journals and play logs stay there.
# usage: fetch0393.sh <directory for the frames>
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:?a directory for the frames}
mkdir -p "$OUT" "$HERE/raw"
timeout 120 ssh bc250 'cd ~/bc5-work/exp0393/run/raw && tar czf - --ignore-failed-read *-summary.txt *-0358.txt *-verdict.txt *-end.txt *-start.txt *-flips-per-10s.txt *-bc.txt *-0341.txt *-fdinfo.txt *-box-settings.txt *-result.txt *-done.txt *-route.txt *-mem.txt build*-inputs.txt patch_0393.diff play-pkg-0393.diff' | tar xzf - -C "$HERE/raw" || exit 1
timeout 300 ssh bc250 'cd ~/bc5-work/exp0393/run/raw && tar czf - *-frames.txt' | tar xzf - -C "$OUT" || exit 1
ls "$OUT" | wc -l
