import sys, collections
sys.path.insert(0, sys.argv[1])
from vb0438 import load
h=collections.Counter(); per=[]
for p in sys.argv[2:]:
    fr=[(s,ft) for s,ft in load(p) if 136<=s<416]
    t0=fr[0][0]; sec=collections.Counter(int(s-t0) for s,_ in fr)
    xs=[sec[i] for i in range(0,275)]
    for x in xs: h[min(60,(x//5)*5)]+=1
    per.append(xs)
tot=sum(h.values())
print('seconds by flips in that second (bucket of 5):'); print(' '.join(f'{k}-{k+4}:{h[k]*100/tot:.1f}%' for k in sorted(h)))
# do slow seconds line up across runs (scene-locked)? correlation of run-averaged profile
import statistics
avg=[statistics.mean(r[i] for r in per) for i in range(275)]
print('run-averaged flips per 10-s block:', [round(statistics.mean(avg[i:i+10])) for i in range(0,270,10)])
# per-run correlation with mean of others
def corr(a,b):
    ma,mb=statistics.mean(a),statistics.mean(b); 
    return sum((x-ma)*(y-mb) for x,y in zip(a,b))/ (sum((x-ma)**2 for x in a)*sum((y-mb)**2 for y in b))**.5
print('corr of each run with the others mean:', [round(corr(r,[statistics.mean(o[i] for o in per if o is not r) for i in range(275)]),2) for r in per])
