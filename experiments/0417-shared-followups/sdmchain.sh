#!/usr/bin/env bash
# exp 0417: candidate C's private build (CPU), then the five ASTRO BOT arms of sdm0417run.sh, under one lock line.
set -u
ulimit -c 0
N=$HOME/bc5-work/exp0413/n; P=$HOME/bc5-work/exp0413/p
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0417 save data memory: private build of candidate C (CPU), then five ASTRO BOT arms on private test save directories" 40 || { echo "sdmchain ended $(date +%T): NOT STARTED"; exit 1; }
(cd "$P/kit" && P_NEW15=1689b7da bash ./p0417f.sh) > "$P/p0417f.log" 2>&1 || { echo "the private build failed:"; tail -15 "$P/p0417f.log" | cut -c1-300; echo "sdmchain ended $(date +%T): BUILD FAILED"; exit 1; }
tail -2 "$P/p0417f.log" | cut -c1-300
bash ./sdm0417run.sh sdm0417-list1.txt
echo "sdmchain ended $(date +%T)"
