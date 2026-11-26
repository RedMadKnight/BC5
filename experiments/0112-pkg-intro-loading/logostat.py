# The intro's first seconds from a direct-path journal: frames per second, and the time from the
# first frame until the frame rate first stays above 40 for 2 s.
import re, sys, collections
d = sys.argv[1]
ts = [float(m[1]) for m in (re.search(r"frame profile: t ([0-9.]+)", l) for l in open(d, errors="replace")) if m]
per = collections.Counter(int(t) for t in ts)
first = ts[0] if ts else 0
print("first frame at %.1f s" % first)
print(" ".join("%d:%d" % (s, per[s]) for s in range(0, 25)))
for s in range(0, 60):
    if per[s] > 40 and per[s + 1] > 40:
        print("steady from %d s (%.1f s after the first frame)" % (s, s - first)); break
