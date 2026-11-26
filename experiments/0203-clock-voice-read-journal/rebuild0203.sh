#!/usr/bin/env bash
# BC5 (experiment 0203): once the box is free (no BOX-LOCK, no kyty_emulator; at most an hour), take BOX-LOCK and
# rebuild ~/bc5-work/exp0203/kyty_emulator from src/libAmpr.readahead.cpp (patch_0203.diff: the APR journal plus
# KYTY_BC5_APR_READAHEAD, both off by default). The journal-only binary of 15:41 is kept as
# kyty_emulator.journal-only and its source as src/libAmpr.journal-only.cpp. CPU only; the shared tree and builds
# are not written. Run detached: setsid nohup rebuild0203.sh > raw/rebuild.out 2>&1 &
set -u
E=$HOME/bc5-work/exp0203; LOCK=$HOME/bc5-work/BOX-LOCK
for _ in $(seq 1 360); do
  [ ! -s "$LOCK" ] && ! pgrep -x kyty_emulator > /dev/null && break
  sleep 10
done
[ -s "$LOCK" ] && { echo "still locked at $(date +%T): $(cat "$LOCK")"; exit 1; }
pgrep -x kyty_emulator > /dev/null && { echo "an emulator runs at $(date +%T)"; exit 1; }
echo "exp 0203 | rebuild with KYTY_BC5_APR_READAHEAD ${SRC:-v1} (one file + link, no GPU; GRANTED) | start $(date +%H:%M) | until ~$(date -d '+3 min' +%H:%M)" > "$LOCK"
cd "$E" || exit 1
[ -f kyty_emulator.journal-only ] || cp -p kyty_emulator kyty_emulator.journal-only
[ -f src/libAmpr.journal-only.cpp ] || cp -p src/libAmpr.cpp src/libAmpr.journal-only.cpp
cp -p "src/${SRC:-libAmpr.readahead.cpp}" src/libAmpr.cpp  # SRC=<file in src/> picks another source (v2: libAmpr.readahead-v2.cpp)
distrobox enter ubuntu -- python3 -I build0203.py compdb.json > build-readahead.log 2>&1
RC=$?
grep -q "^exp 0203 | rebuild with KYTY_BC5_APR_READAHEAD" "$LOCK" && rm -f "$LOCK"
echo "build rc $RC at $(date +%T), lock released"
sed 's/\x1b\[[0-9;]*m//g' build-readahead.log | grep -E "warning:|error:" | cut -c1-200
ls -la --time-style=+%H:%M:%S kyty_emulator kyty_emulator.journal-only
md5sum kyty_emulator src/libAmpr.cpp
strings kyty_emulator | grep -c "KYTY_BC5_APR_READAHEAD"
