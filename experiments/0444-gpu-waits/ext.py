# exp 0444: extract a file the KytyPlus patch adds whole (python ext.py PATCH PATH OUT); unit line N = patch line N + 38006 for src/libs/bc5LleAgc.cpp in 589ef163
import sys
lines = open(sys.argv[1], encoding='utf-8', errors='surrogateescape').read().split('\n')
want = sys.argv[2]; out = sys.argv[3]
i = next(k for k, l in enumerate(lines) if l.startswith('diff --git') and l.endswith(want))
assert lines[i+1].startswith('new file'), lines[i+1]
j = i + 1
while not lines[j].startswith('@@'): j += 1
res = []
j += 1
while j < len(lines) and not lines[j].startswith('diff --git'):
    l = lines[j]
    if l.startswith('+'): res.append(l[1:])
    elif l.startswith(chr(92)): pass
    elif l.startswith('@@'): pass
    j += 1
open(out, 'w', encoding='utf-8', errors='surrogateescape', newline='\n').write('\n'.join(res) + '\n')
print(out, len(res))
