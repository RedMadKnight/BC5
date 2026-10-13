# BC5 experiment 0062: unbiased PC sampling of chosen threads. Per sample: PTRACE_SEIZE one thread,
# PTRACE_INTERRUPT, read RIP, detach: only that thread stops, for microseconds. Read-only.
# usage: ripsample.py <pid> <thread-name> <samples>
import ctypes, os, sys, time, collections, struct
libc = ctypes.CDLL(None, use_errno=True)
libc.ptrace.restype = ctypes.c_long
libc.ptrace.argtypes = [ctypes.c_long, ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
PTRACE_SEIZE, PTRACE_INTERRUPT, PTRACE_DETACH, PTRACE_GETREGS = 0x4206, 0x4207, 17, 12
class Regs(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("r15 r14 r13 r12 rbp rbx r11 r10 r9 r8 rax rcx rdx rsi rdi orig_rax rip cs eflags rsp ss fs_base gs_base ds es fs gs".split())]
pid, want, n = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
tids = [t for t in os.listdir("/proc/%d/task" % pid) if open("/proc/%d/task/%s/comm" % (pid, t)).read().strip() == want]
maps = []
for l in open("/proc/%d/maps" % pid):
    f = l.split(); a, b = (int(x, 16) for x in f[0].split("-"))
    maps.append((a, b, f[5] if len(f) > 5 else "[anon %s]" % f[0]))
def where(ip):
    for a, b, name in maps:
        if a <= ip < b: return name.split("/")[-1], ip - a
    return "?", ip
rips = collections.Counter(); mods = collections.Counter(); insys = 0; got = 0
for k in range(n):
    t = int(tids[k % len(tids)])
    if libc.ptrace(PTRACE_SEIZE, t, None, None) != 0: continue
    libc.ptrace(PTRACE_INTERRUPT, t, None, None)
    os.waitpid(t, 0x40000000)  # __WALL
    r = Regs()
    if libc.ptrace(PTRACE_GETREGS, t, None, ctypes.byref(r)) == 0:
        got += 1
        if r.orig_rax != 0xffffffffffffffff: insys += 1
        else:
            m, off = where(r.rip); mods[m] += 1; rips[r.rip] += 1
    libc.ptrace(PTRACE_DETACH, t, None, None)
    time.sleep(0.002)
print("%s: %d threads, %d samples, in a syscall %d (%.0f%%)" % (want, len(tids), got, insys, 100.0 * insys / max(got, 1)))
for m, c in mods.most_common(8): print("  %5.1f%% %s" % (100.0 * c / got, m))
print("top user PCs:")
for ip, c in rips.most_common(12):
    m, off = where(ip); print("  %4d 0x%x %s+0x%x" % (c, ip, m, off))
