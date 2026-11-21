import sys, collections
sys.path.insert(0, sys.argv[1])
from vb0438 import load
VB=1000/60
c=collections.Counter(); gf=collections.Counter(); pat=collections.Counter()
for p in sys.argv[2:]:
    fr=[ft for s,ft in load(p) if 136<=s<416]
    v=[max(1,round(x/VB)) for x in fr]
    L=[i for i,x in enumerate(v) if x>=3]
    for a,b in zip(L,L[1:]): gf[b-a]+=1
    for i in range(0,len(v)-6,1): pat[tuple(min(x,3) for x in v[i:i+6])]+=1
print('frames between long frames:', sorted(gf.items())[:12], 'total', sum(gf.values()))
print('top 6-frame patterns (3 = 3+):', pat.most_common(8))
# autocorrelation of frame time on lag 1..12
