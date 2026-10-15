# For chosen samples of a pc-sampler-bt14 output: the threads that are not parked in a wait,
# with their first frames (gdb "thread apply all bt" lines).
import re, sys
path = sys.argv[1]; want = set(int(x) for x in sys.argv[2].split(","))
idle = re.compile(r"futex|cond_wait|epoll_wait|poll|nanosleep|clock_nanosleep|sigtimedwait|read \(|__GI___libc_read|pthread_cond|sem_wait|select|accept|recv|_pthread_cond|syscall_cancel")
sample = None; thread = None; frames = []; out = {}
def flush():
    if sample in want and thread is not None and frames:
        top = " ".join(frames[:3])
        if not idle.search(top):
            out.setdefault(sample, []).append((thread, frames))
for line in open(path, errors="replace"):
    m = re.match(r"== sample (\d+)", line)
    if m:
        flush(); thread = None; frames = []; sample = int(m.group(1)); continue
    m = re.match(r'Thread \d+ \(.*?"([^"]*)"\)', line)
    if m:
        flush(); thread = m.group(1); frames = []; continue
    m = re.match(r"#\d+\s+(?:0x[0-9a-f]+ in )?(.*?)(?: \(.*)?$", line.strip())
    if m and thread is not None: frames.append(m.group(1)[:70])
flush()
for s in sorted(out):
    print("== sample", s)
    for t, f in out[s]: print("  %-18s %s" % (t, " | ".join(f[:7])))
