#!/usr/bin/env bash
# BC5 experiment 0241, step 2: decode every stream find0241.py copied out with dec0241, one line per stream
# (copy, config, Wwise channels and samples, then the decoder's report with "|" for newlines). Run inside the ubuntu
# distrobox, from ~/bc5-work/exp0241:  bash decode0241.sh > raw/decode-all.tsv
P=$HOME/bc5-data/priv/exp0241/streams
tail -n +2 raw/index.tsv | while IFS=$'\t' read -r file off riff codec ch rate cfg cfgat samples delay dsize copy; do
  r=$(nice -n 19 ./dec0241 "$cfg" "$P/$copy" < /dev/null 2>&1 | tr '\n' '|')
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$copy" "$file" "$cfg" "$ch" "$samples" "$r"
done
