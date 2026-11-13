#!/usr/bin/env bash
# exp 0419: candidate E's private build (tree + private backend, CPU), then chk0419e.sh, under one lock line.
set -u
ulimit -c 0
N=$HOME/bc5-work/exp0413/n; P=$HOME/bc5-work/exp0413/p
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0419 candidate F: private build (CPU), then ASTRO BOT x4, the second title x6, lean; private dirs" 80 || { echo "fchain ended $(date +%T): NOT STARTED"; exit 1; }
(cd "$P/kit" && P_NEW18=d9af28ca bash ./p0419f.sh) > "$P/p0419f.log" 2>&1 || { echo "the private build failed:"; grep -m8 "error:" "$P"/build-*.build.log "$P"/backend-build*.log 2> /dev/null | cut -c1-260; tail -6 "$P/p0419f.log" | cut -c1-300; echo "fchain ended $(date +%T): BUILD FAILED"; exit 1; }
tail -4 "$P/p0419f.log" | cut -c1-300
echo "before the runs: $(grep MemAvailable /proc/meminfo | tr -s ' '); browsers: $(pgrep -c -f 'firefox|chrom|Web Content' 2> /dev/null)"
bash ./chk0419f.sh
echo "fchain ended $(date +%T)"
