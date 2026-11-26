#!/usr/bin/env bash
# exp 0288: tables from a run's raw files (laptop side, over copies): the per-heap breakdown blocks ("<label> by name (at): ..."
# followed by one line per heap name) sorted by MiB imported, and the memory samples (sample0288.sh) as min/max/last per column.
# usage: summarize0288.sh <tag>-breakdown.txt <tag>-mem.txt
set -eu
BD=$1; MEM=$2
echo "== per-heap breakdown ($BD): heap, views, MiB reserved, with data, imported (sorted by imported)"
gawk '/ by name \(/ { print "-- " $0; next }
      /^  [A-Za-z(].* views: / { line=$0; sub(/^  /, "", line); n=split(line, f, / +/); name=line; sub(/ +[0-9]+ views:.*/, "", name);
        match(line, /([0-9]+) views: +([0-9.]+) MiB reserved, +([0-9.]+) with data, +([0-9.]+) imported/, m);
        printf "%10.1f | %-30s | %4d views | %10.1f reserved | %10.1f with data\n", m[4], name, m[1], m[2], m[3] }' "$BD" | sort -t'|' -k1 -rn
echo
echo "== memory samples ($MEM): column min / max / last (MiB unless noted)"
gawk '!/^#/ && NF >= 21 { for (i = 2; i <= NF; i++) { v = $i + 0; if (!(i in mn) || v < mn[i]) mn[i] = v; if (!(i in mx) || v > mx[i]) mx[i] = v; last[i] = v }; n++ }
      END { split("avail swapfree shmem cached dirty zram_data zram_compr psi_full_us gtt_used emu_rss emu_pss_shmem emu_anon emu_swap emu_threads mount_rss mount_swap pswpin pswpout pgmajfault compact_stall", c, " ");
            printf "%d samples\n", n; for (i = 2; i <= 21; i++) printf "%-14s min %10d  max %10d  last %10d\n", c[i-1], mn[i], mx[i], last[i] }' "$MEM"
