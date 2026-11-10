# Parse the table rows of the part files; print compact rows or dump TSV.
import re, sys, os
parts = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else 'compact'
names = ['KK', 'KL', 'KA', 'KS', 'SK', 'SS']
def split_row(line):
    # split a markdown table row on unescaped pipes outside backticks
    cells, cur, tick = [], '', False
    i = 0
    s = line.strip()
    if s.startswith('|'):
        s = s[1:]
    if s.endswith('|'):
        s = s[:-1]
    while i < len(s):
        c = s[i]
        if c == '`':
            tick = not tick
        if c == '\\' and i + 1 < len(s) and s[i+1] == '|':
            cur += '|'; i += 2; continue
        if c == '|' and not tick:
            cells.append(cur.strip()); cur = ''
        else:
            cur += c
        i += 1
    cells.append(cur.strip())
    return cells
out = []
for n in names:
    p = os.path.join(parts, n + '.md')
    for line in open(p, encoding='utf-8'):
        if re.match(r'^\|\s*\**' + n + r'\d+', line):
            c = split_row(line)
            out.append((n, c))
if mode == 'compact':
    for n, c in out:
        cid = c[0].strip('*')
        what = c[1][:110]
        eff = c[5] if len(c) > 5 else '?'
        risk = (c[6] if len(c) > 6 else '?')[:20]
        cls = (c[7] if len(c) > 7 else '?')[:40]
        print(f'{cid}\t{eff}\t{cls}\t{what}')
elif mode == 'tsv':
    for n, c in out:
        print('\t'.join(x.replace('\t', ' ') for x in c))
elif mode == 'count':
    from collections import Counter
    cnt = Counter()
    for n, c in out:
        cls = c[7] if len(c) > 7 else '?'
        k = 'e4-now' if cls.startswith('e4-now') else 'later' if cls.startswith('later') else 'skip-match' if 'already' in cls else 'skip-prov' if 'provenance' in cls else 'done' if 'done' in cls else cls
        cnt[(n, k)] += 1
    for k in sorted(cnt):
        print(k, cnt[k])
    print(len(out), 'rows')
