import sys
p = sys.argv[1]
s = open(p).read()
o1 = 'archive gtt_used_MiB"'
n1 = 'archive gtt_used_MiB emu_rss_MiB shmem_MiB"'
assert s.count(o1) == 1
s = s.replace(o1, n1)
o2 = '/ 1048576 ))" >> "$out"'
n2 = ('/ 1048576 )) $( [ -n "$ep" ] && awk \'/VmRSS/ {print int($2 / 1024)}\' /proc/$ep/status 2> /dev/null || echo 0)'
      ' $(awk \'/^Shmem:/ {print int($2 / 1024)}\' /proc/meminfo)" >> "$out"')
assert s.count(o2) == 1
s = s.replace(o2, n2)
open(p + ".new", "w").write(s)
print("ok")
