# Check that every markdown table row in a file has the same number of cells as its header row.
import re, sys
p = sys.argv[1]
hdr_n = None
bad = 0
for i, line in enumerate(open(p, encoding='utf-8'), 1):
    s = line.rstrip('\n')
    if not s.lstrip().startswith('|'):
        hdr_n = None
        continue
    t = s.strip()
    n = len(re.findall(r'(?<!\\)\|', t)) - 1
    if hdr_n is None:
        hdr_n = n
        continue
    if n != hdr_n:
        bad += 1
        print(i, n, hdr_n, t[:120])
print('bad rows', bad)
