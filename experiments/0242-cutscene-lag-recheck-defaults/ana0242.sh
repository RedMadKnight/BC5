#!/usr/bin/env bash
# BC5 experiment 0242: score a run of run0242.sh (on the box, after its lock is released; refuses while another
# emulator runs). Outputs in ~/bc5-work/exp0242/raw:
#   <tag>-ana5.txt     exp 0200's ana0200.py in 5-s windows: the cinematic clock's rate, the main player's clip time,
#                      debt and rate, fps, memory and the watched threads;
#   <tag>-clock.txt    the clock time lost in t 100-250 s and over the run, and the 5-s windows under 0.95x;
#   <tag>-voice.txt    the clock voice's entry (+0x7c69535a of file 0x7cd713df): each record-to-run delay;
#   <tag>-frames.txt   long0242.py: flips, long frames, TIMEOUT/fault/given-up counts; <tag>-long-frames.txt.
# usage: ana0242.sh <tag>
set -u
TAG=${1:?tag}
E=$HOME/bc5-work/exp0242; R=$E/raw
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: no analysis now"; exit 1; }
T0=$(grep -a -m1 "bc5 clock: journal t 0 = monotonic" "$R/$TAG-play-pkg.log" | awk '{print $(NF-1)}')
[ -n "$T0" ] || { echo "no journal t0 line in $R/$TAG-play-pkg.log"; exit 1; }
nice -n 19 python3 -I "$HOME/bc5-work/exp0200/ana0200.py" "$R/$TAG-sample.txt" "$R/$TAG-play-pkg.log" - 5 > "$R/$TAG-ana5.txt" 2>&1
# The clock (float s, wraps at 10 s) unwrapped; the loss = wall time - clock time over the window.
awk -v z="$T0" -v tag="$TAG" '$1 == "c" && $3 == $3 + 0 {
    t = $2 - z; c = $3; if (n && c < pc - 5) off += 10; u = c + off; pc = c; n++
    if (!fa) {fa = 1; ta = t; ua = u}; tb = t; ub = u
    if (t >= 100 && t <= 250) {if (!f) {f = 1; t1 = t; u1 = u}; t2 = t; u2 = u}
    k = int(t / 5) * 5; if (!(k in a)) {a[k] = u; at[k] = t}; b[k] = u; bt[k] = t}
  END {printf "%s cinematic clock (journal t0 = mono %s): t 100-250 s: wall %.1f s, clock %.1f s, lost %.1f s; whole run t %.0f-%.0f s: lost %.1f s\n", tag, z, t2 - t1, u2 - u1, (t2 - t1) - (u2 - u1), ta, tb, (tb - ta) - (ub - ua)
       printf "5-s windows under 0.95x:"; for (k = 0; k <= tb; k += 5) if ((k in a) && bt[k] > at[k] + 1) {r = (b[k] - a[k]) / (bt[k] - at[k]); if (r < 0.95) printf " %d:%.2f", k, r}; print ""}' \
  "$R/$TAG-sample.txt" > "$R/$TAG-clock.txt"
awk -v z="$T0" '$7 == "record-read" && $11 == "0x7cd713df" && $12 == "+0x7c69535a" {rec = $6 - z; pend = 1}
  $7 == "run" && $10 == "read" && $12 == "0x7cd713df" && $13 == "+0x7c69535a" {
    t = $6 - z; if (pend) {d = t - rec; n++; s = s sprintf(" %.1f:%.2f", rec, d); if (d > mx) mx = d; if (d > 0.5) late++; pend = 0} else again++}
  END {printf "clock voice entry: %d record-to-run pairs, max delay %.2f s, delays over 0.5 s: %d, runs without a new record: %d\n", n, mx, late + 0, again + 0
       print "record t:delay" s}' "$R/$TAG-apr-journal.txt" > "$R/$TAG-voice.txt"
# exp 0243 (the top session, 19:44): the ATRAC9 vibration configurations 6/7 decoded by vgmstream, on by default
{ echo "ATRAC9 vibration layout lines: $(grep -a -c "bc5 ajm: ATRAC9 vibration layout" "$R/$TAG-play-pkg.log"), CODEC_ERROR lines: $(grep -a -c "CODEC_ERROR" "$R/$TAG-play-pkg.log")"
  grep -a -m3 "bc5 ajm: ATRAC9 vibration layout" "$R/$TAG-play-pkg.log" | cut -c1-200
  grep -a -m3 "CODEC_ERROR" "$R/$TAG-play-pkg.log" | cut -c1-200; } > "$R/$TAG-at9.txt"
cat "$R/$TAG-at9.txt"
J=$(cut -d' ' -f1 "$R/$TAG-journal-path.txt")
nice -n 19 python3 -I "$E/long0242.py" 15 100 "$J" "$R/$TAG-long-frames.txt" > "$R/$TAG-frames.txt" 2>&1
cat "$R/$TAG-clock.txt" "$R/$TAG-voice.txt" | cut -c1-400
cat "$R/$TAG-frames.txt" "$R/$TAG-long-frames.txt" | cut -c1-330
grep "^# player 1\|^# player [0-9a-f]* t" "$R/$TAG-ana5.txt"
