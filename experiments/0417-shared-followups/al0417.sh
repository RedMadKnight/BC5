#!/usr/bin/env bash
# exp 0417: one 30 s ASTRO BOT start on the kept bad save directory (wda/_SaveData.sm0) with the emulator's call log,
# private build C, to see the host calls before the path-split fault. Private test directories only.
set -u
ulimit -c 0
N=$HOME/bc5-work/exp0413/n; WD=$N/wda; TAG=${1:?tag}
cd "$N" || exit 1
. "$N/chainlock0417.inc"
chain_claim "exp 0417: one 30 s ASTRO BOT start with the call log on a private test save directory" 4 || { echo "al0417 ended: NOT STARTED"; exit 1; }
bin=$HOME/bc5-work/exp0413/p/build-normal/src/kyty_emulator; want=$(md5sum < "$bin" | cut -d' ' -f1)
KEEP=$WD/_SaveData.before-al0417-$$
mv "$WD/_SaveData" "$KEEP" && cp -a "$WD/_SaveData.sm0" "$WD/_SaveData" || exit 1
P_BIN=$bin P_WANT=$want bash ./start0413g.sh "$TAG" astrolog 30 KYTY_BC5_SAVEDATA_MEMORY_LOG=1 KYTY_BC5_SAVE_TRACE=1 2>&1 | tail -1
rm -rf "$WD/_SaveData"; mv "$KEEP" "$WD/_SaveData"
ls -la "$N/raw/$TAG-calls.log" 2> /dev/null
echo "al0417 ended $(date +%T)"
