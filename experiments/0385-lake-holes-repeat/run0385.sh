#!/usr/bin/env bash
# BC5 experiment 0385: one lake-bench run from guard to clean-up on the box, so one plain ssh carries it. Order: guard,
# ab0385.sh with the poller beside it, ana0385.sh, the summaries into <tag>.raw.tar, the snapshots and shots deleted
# unviewed. A dropped ssh does not stop it (tee -p). A kernel line or changed live saves stop it before the analysis, and
# nothing is deleted then or if the analysis failed.
# Needs our "water session exp 0385 | series" lock line, written before the first run and removed after the last.
# usage: run0385.sh <tag K4..K6> <live saves, C locale> <build, first 8 of the md5>   (on the box, attended; from the
#        laptop under timeout -k 10 540)
set -u
tag=$1; SV=$2; BUILD=$3
case $tag in K[0-9]) ;; *) echo "bad tag $tag"; exit 1;; esac
W=$HOME/bc5-work; E=$W/exp0385; C=$HOME/bc5-data/priv/exp0385/$tag
LINE="water session exp 0385 | series"
exec > >(tee -p "$E/$tag.run.log") 2>&1
echo "== $tag $(date +%T)"
cd "$W" || exit 1
grep -q "^$LINE" BOX-LOCK || { echo "our lock line is gone: stop"; exit 1; }
[ "$(grep -vc "^$LINE" BOX-LOCK)" = 0 ] || { echo "foreign lock line: stop"; cat BOX-LOCK; exit 1; }
pgrep -a '^kyty_emulator' && { echo "an emulator is running: stop"; exit 1; }
b=$(md5sum < kytyplus-build/src/kyty_emulator | cut -c1-8)
[ "$b" = "$BUILD" ] || { echo "binary $b is not the merged build $BUILD: stop"; exit 1; }
"$E/ab0385.sh" "$tag" "$SV" '' 330 > "$E/$tag.ab.txt" 2>&1 &
AB=$!
sleep 8
kill -0 "$AB" 2>/dev/null || { wait "$AB"; echo "ab ended at once, exit $?: stop"; cut -c1-160 "$E/$tag.ab.txt"; exit 1; }
python3 -I "$E/pl0385.py" "$tag" 85 "$C" 212 2.0 6 > "$E/$tag.pl.txt" 2>&1 &
PL=$!
wait "$AB"; rc=$?
for _ in $(seq 1 30); do kill -0 "$PL" 2>/dev/null || break; sleep 1; done
kill "$PL" 2>/dev/null
wait "$PL" 2>/dev/null
echo "ab exit $rc $(date +%T)"; tail -n 3 "$E/$tag.ab.txt" | cut -c1-120
[ "$rc" = 0 ] || { echo "ab exit $rc, a kernel line or a failed bench: stop at once, no analysis, nothing deleted"; exit 1; }
grep -q "LIVE SAVES CHANGED" "$E/$tag.ab.txt" && { echo "the live saves changed: stop, ask the top session, nothing deleted"; exit 1; }
cd "$E" || exit 1
pgrep -a '^kyty_emulator' && { echo "an emulator is up: no analysis, nothing deleted"; exit 1; }
ok=1
bash "ana0385.sh" "$tag" > "$tag.ana.log" 2>&1 || ok=0
[ -s "$tag.tz.txt" ] || ok=0
grep '^#' "$tag.tz.txt" 2>/dev/null | cut -c1-200
gzip -c "$C/events.txt" > "$tag.events.txt.gz" 2>/dev/null
cp "$C/snaps.txt" "$tag.snaps.txt" 2>/dev/null
cp "r-$tag/dmesg.txt" "$tag.dmesg.txt" 2>/dev/null || : > "$tag.dmesg.txt"
tar cf "$tag.raw.tar" $(ls "$tag.out" "$tag.ab.txt" "$tag.pl.txt" "$tag.ana.log" "$tag.bursts.txt" "$tag.reads.txt" "$tag.reads.json" "$tag.tz.txt" "$tag.events.txt.gz" "$tag.snaps.txt" "$tag.dmesg.txt" "$tag.cap.txt" play-pkg-0385.diff input-0385.cfg 2>/dev/null)
if [ "$ok" = 1 ]; then
  du -sh "$C" "r-$tag/shots" | cut -f1 | tr '\n' ' '; ls "r-$tag/shots" | wc -l
  rm -rf "$C" "r-$tag/shots" && echo "deleted snapshots and shots (unviewed)"
else
  echo "the analysis failed: snapshots and shots kept, nothing deleted"
fi
cat "r-$tag/journal-dir.txt" 2>/dev/null
p=$(grep -o 'png: patch *[0-9.]*' "$tag.out" | awk '{s+=$3;n++} END {if(n) printf "%.1f", s/n; else print "none"}')
echo "RESULT $tag: analysis ok $ok, mean patch $p %, $(date +%T)"
[ "$ok" = 1 ]
