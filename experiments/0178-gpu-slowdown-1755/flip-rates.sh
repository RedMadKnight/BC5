#!/usr/bin/env bash
# BC5 (experiment 0178): the second title's flip rate per session from the direct path journals
# (one "timing: t <s> s flip" line per flip, BC5_DIRECT_TIMING=1): the intro (t 20-33 s) and the
# start screen (t 55-82 s) of every journal written since <since>. usage: flip-rates.sh ["YYYY-MM-DD HH:MM"]
SINCE=$(date -d "${1:-today 00:00}" +%s)
for d in $(ls -d ~/bc5-data/captures/*/gc 2>/dev/null | sort -u); do
  f=$d/direct.log; [ -r "$f" ] || continue
  [ "$(stat -c %Y "$f")" -gt "$SINCE" ] || continue
  r=$(grep -a "^timing: t .* s flip" "$f" | awk '{t=$3+0; if (t>=55 && t<82) n++; if (t>=20 && t<33) m++} END{printf "%5.1f %5.1f", m/13, n/27}')
  echo "$(stat -c '%y' "$f" | cut -c1-16)  $r  $(basename "$(dirname "$d")")"
done | sort | awk 'BEGIN{print "journal end        intro start  capture"} $3>0 || $4>0'
