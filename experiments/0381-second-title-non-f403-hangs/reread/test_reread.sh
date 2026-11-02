#!/usr/bin/env bash
# BC5 exp 0381: the sampler against a stand-in /proc and the analysis against lines in the mount's own format, on the laptop.
# pgrep is a stand-in on PATH, which also sets when the mount goes away. usage: bash test_reread.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
PY=${PY:-python3}
fail=0
check() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }
P=$T/proc; mkdir -p "$P/pressure" "$P/100/task/101" "$P/200/task/201" "$T/bin" "$T/drm"
printf 'pgmajfault 5\npswpin 6\nother 1\nworkingset_refault_file 7\n' > "$P/vmstat"
printf 'MemAvailable:  100 kB\nCached:  200 kB\nActive(file):  30 kB\nMemTotal: 9 kB\n' > "$P/meminfo"
printf 'some avg10=0.00 avg60=0.00 avg300=0.00 total=11\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=22\n' > "$P/pressure/io"
printf 'rchar: 1\nwchar: 2\nread_bytes: 3\nwrite_bytes: 4\n' > "$P/100/io"
cp "$P/100/io" "$P/200/io"
# Field 12 of /proc/pid/stat is majflt, 14 and 15 are utime and stime; the name holds a space.
S='100 (bc5 mount) S 1 1 1 0 -1 0 10 0 77 0 8 9 0 0 20 0 1 0 1 1 1'
echo "$S" > "$P/100/stat"; echo "$S" > "$P/200/stat"; echo "$S" > "$P/200/task/201/stat"; echo bc5-ring > "$P/200/task/201/comm"
echo 4096 > "$T/drm/mem_info_gtt_used"
cat > "$T/bin/pgrep" <<'E'
#!/bin/sh
case "$*" in
  *bc5-mount*) n=$(cat "$COUNT" 2> /dev/null || echo 0); echo $((n + 1)) > "$COUNT"; [ "$n" -ge 2 ] && rm -rf "$PROCDIR/100"; echo 100 ;;
  *) echo 200 ;;
esac
E
chmod +x "$T/bin/pgrep"
COUNT=$T/count PROCDIR=$P PATH="$T/bin:$PATH" PROC=$P DRM=$T/drm EVERY=0.05 bash "$HERE/sample-reread.sh" "$T/s.txt" 30
L=$(grep -m1 '^T ' "$T/s.txt")
check "vmstat fields" "echo '$L' | grep -q 'pgmajfault=5' && ! echo '$L' | grep -q other"
check "memory fields" "echo '$L' | grep -q 'Active_file_=30' && ! echo '$L' | grep -q MemTotal"
check "pressure" "echo '$L' | grep -q 'io_full_us=22'"
check "mount io and stat past a spaced name" "echo '$L' | grep -q 'mount_read_bytes=3' && echo '$L' | grep -q 'mount_majflt=77' && echo '$L' | grep -q 'mount_cpu_ticks=17'"
check "emulator and gtt" "echo '$L' | grep -q 'emu_majflt=77' && echo '$L' | grep -q 'gtt=4096'"
check "threads" "grep -q '^THREADS .* bc5-ring:77' '$T/s.txt'"
check "ends when the mount is gone" "grep -q '^END ' '$T/s.txt'"
cat > "$T/m.log" <<'E'
bc5-mount: 8 read workers, decode-ahead 2048 KiB
bc5-mount stats 30.0 s: served 100 MiB (+100), decoded 10 blocks 40 MiB (+40), 0 decoded again, from disk 20 blocks 50 MiB (+50)
bc5-mount reread 30.0 s: first 90 MiB (+90), again 10 MiB (+10), age s [1.0, 4.0, 16.0, 64.0, 256.0] [1, 2, 3, 4, 0, 0] MiB, distance MiB [64, 256, 1024, 4096] [5, 5, 0, 0, 0] MiB
bc5-mount spans 30.0 s: jobs peak 9, image 30 MiB (+30), written 40 MiB (+40), block uses 500, ahead 10 used 5, queue 100 mean 200 us peak 900 us, service 100 mean 800 us peak 5000 us, disk 20 mean 100 us peak 400 us, image 10 mean 300 us peak 900 us, decode 10 mean 700 us peak 900 us
bc5-mount again 30 s: 10 MiB of 100 MiB a/b.dat
bc5-mount stats 90.0 s: served 300 MiB (+200), decoded 30 blocks 90 MiB (+50), 2 decoded again, from disk 40 blocks 150 MiB (+100)
bc5-mount reread 90.0 s: first 190 MiB (+100), again 110 MiB (+100), age s [1.0, 4.0, 16.0, 64.0, 256.0] [51, 52, 3, 4, 0, 0] MiB, distance MiB [64, 256, 1024, 4096] [55, 55, 0, 0, 0] MiB
bc5-mount spans 90.0 s: jobs peak 12, image 90 MiB (+60), written 90 MiB (+50), block uses 900, ahead 30 used 25, queue 100 mean 400 us peak 900 us, service 100 mean 1600 us peak 5000 us, disk 20 mean 100 us peak 400 us, image 10 mean 300 us peak 900 us, decode 10 mean 700 us peak 900 us
E
A=$("$PY" "$HERE/ana-reread.py" "$T/m.log" "$T/s.txt" --minute 60)
echo "$A" | sed -n '1,4p'
check "first minute" "echo \"\$A\" | grep -Eq '^  1 +100 +[0-9]+ +90 +10 +10.0 '"
check "second minute: half repeats, ahead use, peak" "echo \"\$A\" | grep -Eq '^  2 +200 +[0-9]+ +100 +100 +50.0 .* 12\$'"
check "buckets" "echo \"\$A\" | grep -q 'repeats by age' && echo \"\$A\" | grep -q '51.0, 52.0'"
[ "$fail" = 0 ] && echo "all passed"
exit $fail
