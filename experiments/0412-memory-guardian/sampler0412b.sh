#!/usr/bin/env bash
# BC5 exp 0412 (g412b): sampler0411.sh with three more column groups, after the plays of 2026-11-10 (the second title's
# pin wall and ASTRO BOT's kill by host anonymous memory): the emulator's RssAnon, RssShmem and VmSwap; the same three of
# bc5-mount when one runs; and memory.current and memory.swap.current of the emulator's cgroup (the container's, where the
# launcher's fuse sets memory.max). They come before the thread list. The rest is sampler0411.sh's text:
# Waits up to <wait s> for an emulator. Then, every 5 s until that process exits, it writes one line with:
# - memory: MemAvailable, swap used, swap-ins and swap-outs per second, major faults per second (whole box), and PSI
#   memory "some" and "full" and PSI cpu "some" (avg10);
# - the emulator: minor and major faults per second, CPU % (100 = one core), and its thread count;
# - GTT used, and the GPU's current sclk and mclk levels;
# - (0412) emulator anon/shmem/swap MiB, bc5-mount anon/shmem/swap MiB ("- - -" when none), cgroup memory/swap MiB;
# - the six busiest threads of the interval (tid:name:CPU %).
# Reads /proc and /sys only: no root, no ptrace, no write outside <out file>.
# usage (on the box, host): sampler0412b.sh <out file> [wait s, default 1800] [max s, default 7200]
#        SAMPLER_NAME=<process name> picks another process (the stand-in test); SAMPLER_MOUNT=<name> another mount process.
set -u
OUT=$1 WAIT=${2:-1800} MAX=${3:-7200} NAME=${SAMPLER_NAME:-kyty_emulator}
D=/sys/class/drm/card1/device
HZ=$(getconf CLK_TCK)
t0=$(date +%s); EP=""
while :; do
  EP=$(pgrep -x "$NAME" | head -1)
  [ -n "$EP" ] && break
  [ $(($(date +%s) - t0)) -ge "$WAIT" ] && { echo "# $(date '+%F %T') no $NAME in $WAIT s" >> "$OUT"; exit 0; }
  sleep 2
done
echo "# $(date '+%F %T') $NAME $EP: $(readlink "/proc/$EP/exe" 2> /dev/null); every 5 s; HZ $HZ" >> "$OUT"
echo "# t s | avail MiB, swap used MiB, swap in/out pages/s, majflt/s (box) | psi mem some/full, cpu some | emu minflt/s majflt/s cpu% threads | gtt MiB | sclk mclk | emu anon shmem swap MiB | mount anon shmem swap MiB | cgroup mem swap MiB | top threads tid:name:cpu%" >> "$OUT"
# thread snapshot: "tid ticks name" per line (the name after the last field, spaces made _)
snap() {
  for f in /proc/"$EP"/task/*/stat; do cat "$f" 2> /dev/null; echo; done | awk '
    NF { i = index($0, "("); j = match($0, /\) [A-Za-z] /); if (!i || !j) next
         tid = substr($0, 1, i - 2); name = substr($0, i + 1, j - i - 1); gsub(/ /, "_", name)
         split(substr($0, j + 2), a, " "); print tid, a[12] + a[13], name }'
}
pstat() { awk '{ j = match($0, /\) [A-Za-z] /); split(substr($0, j + 2), a, " "); print a[8], a[10], a[12] + a[13], a[18] }' "/proc/$EP/stat" 2> /dev/null; }
vm() { awk '$1 == "pswpin" || $1 == "pswpout" || $1 == "pgmajfault" { v[$1] = $2 } END { print v["pswpin"], v["pswpout"], v["pgmajfault"] }' /proc/vmstat; }
psi() { awk '/^some/ { split($2, a, "="); s = a[2] } /^full/ { split($2, a, "="); f = a[2] } END { printf "%s/%s", s, f }' /proc/pressure/memory; }
psic() { awk '/^some/ { split($2, a, "="); print a[2] }' /proc/pressure/cpu; }
mem() { awk '/^MemAvailable:/ { a = $2 } /^SwapTotal:/ { st = $2 } /^SwapFree:/ { sf = $2 } END { printf "%d %d", a / 1024, (st - sf) / 1024 }' /proc/meminfo; }
# 0412: a process's anonymous, shmem and swapped MiB; "- - -" when it is gone.
pm() {
  if [ -r "/proc/$1/status" ]; then
    awk '/^RssAnon:/ { a = $2 } /^RssShmem:/ { s = $2 } /^VmSwap:/ { w = $2 } END { printf "%d %d %d", a / 1024, s / 1024, w / 1024 }' "/proc/$1/status" 2> /dev/null
  else
    printf '%s' '- - -'
  fi
}
mnt() { local mp; mp=$(pgrep -x "${SAMPLER_MOUNT:-bc5-mount}" | head -1); if [ -n "$mp" ]; then pm "$mp"; else printf '%s' '- - -'; fi; }
CGD=/sys/fs/cgroup$(cut -d: -f3 "/proc/$EP/cgroup" 2> /dev/null | head -1)
cg() {
  if [ -r "$CGD/memory.current" ]; then
    printf '%d %d' "$(($(cat "$CGD/memory.current") / 1048576))" "$(($(cat "$CGD/memory.swap.current" 2> /dev/null || echo 0) / 1048576))"
  else
    printf '%s' '- -'
  fi
}
lvl() { awk '/\*/ { sub(":", "", $1); printf "%s", $2 }' "$1" 2> /dev/null; }
ts=$(snap); ps0=$(pstat); vm0=$(vm); tp=$(date +%s.%N); start=$(date +%s)
while [ -d "/proc/$EP" ] && [ $(($(date +%s) - start)) -lt "$MAX" ]; do
  sleep 5
  [ -d "/proc/$EP" ] || break
  ts1=$(snap); ps1=$(pstat); vm1=$(vm); tn=$(date +%s.%N)
  dt=$(awk -v a="$tp" -v b="$tn" 'BEGIN { printf "%.3f", b - a }')
  top=$( { echo "$ts" | sed 's/^/P /'; echo "$ts1" | sed 's/^/C /'; } | awk -v dt="$dt" -v hz="$HZ" '
    $1 == "P" { p[$2] = $3; next }
    $1 == "C" { if ($2 in p) { d = $3 - p[$2]; if (d > 0) printf "%.1f %s:%s\n", 100 * d / hz / dt, $2, $4 } }' |
    sort -rn | head -6 | awk '{ printf "%s:%s ", $2, $1 }')
  line=$(awk -v dt="$dt" -v hz="$HZ" -v p0="$ps0" -v p1="$ps1" -v v0="$vm0" -v v1="$vm1" 'BEGIN {
    split(p0, a, " "); split(p1, b, " "); split(v0, c, " "); split(v1, d, " ")
    printf "%.0f %.0f %.0f | %.0f %.0f %.1f %s", (d[1] - c[1]) / dt, (d[2] - c[2]) / dt, (d[3] - c[3]) / dt,
      (b[1] - a[1]) / dt, (b[2] - a[2]) / dt, 100 * (b[3] - a[3]) / hz / dt, b[4] }')
  gtt=$(($(cat "$D/mem_info_gtt_used" 2> /dev/null || echo 0) / 1048576))
  printf '%s | %s %s | %s %s | %s | %s | %s %s | %s | %s | %s | %s\n' "$(($(date +%s) - start))" "$(mem)" "${line%% |*}" "$(psi)" "$(psic)" \
    "${line#*| }" "$gtt" "$(lvl "$D/pp_dpm_sclk")" "$(lvl "$D/pp_dpm_mclk")" "$(pm "$EP")" "$(mnt)" "$(cg)" "$top" >> "$OUT"
  ts=$ts1; ps0=$ps1; vm0=$vm1; tp=$tn
done
echo "# $(date '+%F %T') $NAME $EP ended or $MAX s reached" >> "$OUT"
