# BC5 experiment 0062: where the game threads spend wall time. Samples /proc/<pid>/task/*/stat
# every 1 ms for N seconds: per thread the share of samples in state R (running or runnable) and
# the CPU time (utime+stime) gained. Read-only, no ptrace.
import os, sys, time, collections
pid = int(sys.argv[1]); secs = float(sys.argv[2]); hz = os.sysconf("SC_CLK_TCK")
tasks = os.listdir("/proc/%d/task" % pid)
def rd(t):
    try:
        s = open("/proc/%d/task/%s/stat" % (pid, t)).read()
        name = s[s.index("(") + 1:s.rindex(")")]; f = s[s.rindex(")") + 2:].split()
        return name, f[0], int(f[11]) + int(f[12])
    except OSError: return None
first = {t: rd(t) for t in tasks}
states = collections.defaultdict(collections.Counter); n = 0; end = time.time() + secs
while time.time() < end:
    for t in tasks:
        r = rd(t)
        if r: states[t][r[1]] += 1
    n += 1; time.sleep(0.001)
last = {t: rd(t) for t in tasks}
rows = []
for t in tasks:
    if not first[t] or not last[t]: continue
    cpu = (last[t][2] - first[t][2]) / hz / secs
    rows.append((cpu, t, last[t][0], states[t]["R"] / max(n, 1)))
rows.sort(reverse=True)
print("samples %d over %.1f s" % (n, secs))
print("%-8s %-16s %6s %6s" % ("tid", "name", "cpu", "R"))
for cpu, t, name, r in rows[:25]: print("%-8s %-16s %5.0f%% %5.0f%%" % (t, name, cpu * 100, r * 100))
