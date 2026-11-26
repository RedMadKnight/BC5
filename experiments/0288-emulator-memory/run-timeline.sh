#!/usr/bin/env bash
# exp 0288: run mem-timeline.awk over a direct-path journal (or the filtered copy of one). Usage: run-timeline.sh <direct.log>
set -eu
here=$(dirname "$0")
exec gawk -f "$here/mem-timeline.awk" "$1"
