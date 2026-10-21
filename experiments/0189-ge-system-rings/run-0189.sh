#!/usr/bin/env bash
# BC5 (experiment 0189): one idle night run of the second title (slot 1 loaded, no input after loading: the
# idle-run.sh of exp 0185-0188 without the sound recording) for SECS seconds with the switches in ENVX, then
# from the kernel log of the run: the GPU page faults (client, pages, 5-s windows, first/last time from the
# emulator's start), ring timeouts and resets; from the direct journal: fence timeouts, the timeout probe's TF
# ring / HS user-data lines, and flips per 10 s; from the emulator's output: the exp 0189 ioctl trace, register
# census and ring lines. The saves are put back to save-backup-0180-0953 before and after (the run may autosave
# slot 1).
# usage: ENVX="<switches>" run-0189.sh <tag> [secs]
TAG=$1; SECS=${2:-300}
cd ~/bc5-work
BK=save-backup-0180-0953; SD=_SaveData/PPSA03671
restore() {
  cp -a "$BK/." "$SD/"
  for d in "$SD"/*/; do d=${d%/}; [ -e "$BK/$(basename "$d")" ] || rm -r -- "$d"; done
  diff -rq "$BK" "$SD" > /dev/null && echo "saves as in $BK" || echo "SAVES DIFFER from $BK"
}
pgrep -x kyty_emulator >/dev/null && { echo busy; exit 1; }
restore
sync
O=exp0189/r-$TAG; mkdir -p "$O"
echo "${ENVX:-defaults}" > "$O/env.txt"
cp idle-cmd.txt "$O/input.cmd"
UP0=$(cut -d' ' -f1 /proc/uptime)
setsid nohup distrobox enter ubuntu -- env KYTY_BC5_INPUT_CMD=$HOME/bc5-work/$O/input.cmd ${ENVX:-} ~/bc5-work/play-pkg.sh < /dev/null > "$O/launcher.out" 2>&1 &
for _ in $(seq 1 60); do pgrep -x kyty_emulator >/dev/null && break; sleep 1; done
UPS=$(cut -d' ' -f1 /proc/uptime)
T0=$(date +%s); ENDED=""
while [ $(( $(date +%s) - T0 )) -lt "$SECS" ]; do
  pgrep -x kyty_emulator >/dev/null || { ENDED="ended by itself at $(( $(date +%s) - T0 )) s"; break; }
  sleep 2
done
J=$(ls -td ~/bc5-data/captures/play-*/gc | head -1)/direct.log
cp play-pkg-last.log "$O/emu.log"
pkill -x kyty_emulator; sleep 4; pkill -9 -x kyty_emulator; sleep 3
restore
sudo -n dmesg | awk -v up0="$UP0" '{ts = substr($0, 2, index($0, "]") - 2) + 0; if (ts >= up0) print}' > "$O/dmesg.txt"
grep -a "^frame profile: t \|TIMEOUT\|timeout probe: TF ring\|timeout probe: HS user\|tf ring" "$J" > "$O/journal-excerpt.txt" 2>/dev/null
echo "== $TAG (${ENVX:-defaults}): ${ENDED:-stopped at $SECS s}; journal $J"
awk -v ups="$UPS" '/page fault/ {ts = substr($0, 2, index($0, "]") - 2) + 0; n++; if (!f) f = ts; l = ts; w[int((ts - ups) / 5)] = 1}
  /in page starting at address/ {for (i = 1; i <= NF; i++) if ($i == "address") a[$(i + 1)]++}
  /Faulty UTCL2 client ID/ {sub(/.*client ID: /, ""); c[$0]++}
  END {printf "kernel: %d fault records in %d 5-s windows", n, length(w); if (n) printf ", first %.1f s, last %.1f s after the start", f - ups, l - ups; printf "\n";
       for (k in c) printf "   client %s: %d\n", k, c[k]; m = 0; for (k in a) {m++; if (m <= 6) printf "   page %s: %d\n", k, a[k]} if (m > 6) printf "   ... %d pages in all\n", m}' "$O/dmesg.txt"
echo "kernel: $(grep -c -i "ring .*timeout\|GPU reset\|gpu recover" "$O/dmesg.txt") ring timeout/reset lines"
echo "journal: $(grep -c -a "TIMEOUT" "$O/journal-excerpt.txt") fence timeouts"
grep -a "TIMEOUT" "$O/journal-excerpt.txt" | cut -c1-160 | head -3
grep -a "timeout probe: TF ring\|timeout probe: HS user" "$O/journal-excerpt.txt" | cut -c1-300 | head -6
grep -a "^frame profile: t " "$O/journal-excerpt.txt" | awk '{t = $4 + 0; n[int(t / 10)]++} END {for (k in n) printf "%d:%d\n", k * 10, n[k]}' | sort -n | tr '\n' ' '; echo
grep -a "default TF ring\|/dev/gc TF ring\|/dev/gc HS offchip\|\[bc5-tess\]" "$O/emu.log" | head -5
grep -a "tf ring" "$O/journal-excerpt.txt" | head -3
echo "ioctl codes traced: $(grep -a -c "^\[bc5-gc-trace\]" "$O/emu.log")"
grep -a "^reg census:" "$O/emu.log" | awk '/buffers,/ {n++} END {print "census reports: " n}'
