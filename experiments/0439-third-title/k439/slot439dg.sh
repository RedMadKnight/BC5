#!/usr/bin/env bash
# BC5 exp 0439 (tag dg439): the laptop side of top's 15:50 slot (11-22 15:35), in order: the 98 piece files of dcb #9544
# to the private laptop folder; the branch's k439 files to the box; the diagnosis build (dg439.sh, one box-side wait,
# bound 20 min); the R66 dry run of the run (DRY=1, no emulator, no lock). No emulator start.
#   slot439dg.sh   (laptop, Git Bash, from this directory)
set -u
K=$(cd "$(dirname "$0")" && pwd); P=$HOME/Documents/bc5-private/dcb9544-20261122-1042
mkdir -p "$P" && scp -q 'bc250:bc5-data/captures/play-20261122-1042/gc/pa439-dcb-9544-piece-*.bin' "$P/" || { echo "STOP: scp of the pieces"; exit 1; }
echo "pieces: $(ls "$P" | wc -l) files, $(cat "$P"/*.bin | wc -c) bytes in $P"
ssh bc250 'pgrep "^kyty_emulator"' && { echo "STOP: an emulator runs on the box"; exit 1; }
scp -q "$K/t3one.sh" "$K/box439.sh" "$K/dg439.sh" "$K/mkpa439.py" "$K/mkqc444.py" "$K/ud439patch.py" "$K/pa0439.hpp" bc250:bc5-work/exp0439/k439/ || { echo "STOP: copy"; exit 1; }
ssh bc250 'cd ~/bc5-work/exp0439/k439 && md5sum t3one.sh box439.sh dg439.sh mkpa439.py mkqc444.py ud439patch.py pa0439.hpp | cut -c1-8 | paste -sd" "'
ssh bc250 'systemd-run --user --unit=b439dg --wait --collect -p RuntimeMaxSec=1200 --working-directory=$HOME/bc5-work/exp0439/k439 bash -c "ulimit -c 0; bash dg439.sh > raw/dg439.txt 2>&1"; tail -32 ~/bc5-work/exp0439/k439/raw/dg439.txt'
MD=$(ssh bc250 'cut -c1-8 ~/bc5-work/exp0439/k439/normal/binary.md5')
echo "== R66 dry run on $MD"
ssh bc250 "cd ~/bc5-work/exp0439 && DRY=1 T3ONE_TAG=d2211 bash k439/t3one.sh $MD pcpw1 2>&1 | head -40"
