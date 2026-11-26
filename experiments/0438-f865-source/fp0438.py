# SPDX-License-Identifier: GPL-2.0
# BC5 exp 0438: frame-time budget from frame-profile lines (journal lines starting "frame profile:").
# Usage: python fp0438.py LINES.txt  (the scene is taken as t >= 120 s, u436sS3; edit for another run)
import re,sys,statistics as st
R=re.compile(r't ([\d.]+) s, ([\d.]+) ms since the last flip; game thread inside the host ([\d.]+) ms \(sync ([\d.]+), hints ([\d.]+), prepare ([\d.]+), list ([\d.]+), cs ([\d.]+), fence ([\d.]+), cap ([\d.]+), label waits ([\d.]+), event waits ([\d.]+)\), at the flip ([-\d.]+), outside ([-\d.]+); GPU busy ([\d.]+) ms in (\d+) jobs \(\+(\d+) from the ring thread\)')
K='t iv inside sync hints prep list cs fence cap lw ew flip out gpu jobs rj'.split()
F=[]
for l in open(sys.argv[1],encoding='utf-8',errors='replace'):
    m=R.search(l)
    if m: F.append(dict(zip(K,map(float,m.groups()))))
print(len(F))
# per 10 s bucket
b={}
for f in F: b.setdefault(int(f['t']//10),[]).append(f)
for k in sorted(b):
    v=b[k]; print(f"{k*10:4d}s n {len(v):4d} fps {len(v)/10:5.1f} med iv {st.median([x['iv'] for x in v]):6.1f} gpu {st.median([x['gpu'] for x in v]):6.1f} flip {st.median([x['flip'] for x in v]):5.1f} in {st.median([x['inside'] for x in v]):5.1f} out {st.median([x['out'] for x in v]):5.1f}")
S=[f for f in F if f['t']>=120]
def rep(name,v):
    n=len(v); 
    if not n: print(name,0); return
    keys=['iv','gpu','flip','inside','sync','hints','prep','list','cs','fence','cap','lw','ew','out']
    m={k:sum(x[k] for x in v)/n for k in keys}
    print(f"{name}: n {n}, mean iv {m['iv']:.1f} | GPU busy {m['gpu']:.1f} ({100*m['gpu']/m['iv']:.0f}%) | at flip {m['flip']:.1f} | inside {m['inside']:.1f} [sync {m['sync']:.1f} hints {m['hints']:.1f} prep {m['prep']:.1f} list {m['list']:.1f} cs {m['cs']:.1f} fence {m['fence']:.1f} cap {m['cap']:.1f} labelw {m['lw']:.1f} eventw {m['ew']:.1f}] | outside {m['out']:.1f}; jobs {sum(x['jobs'] for x in v)/n:.1f} +ring {sum(x['rj'] for x in v)/n:.1f}")
    print(f"   shares of time: GPU-busy/iv {100*m['gpu']/m['iv']:.0f}%, flip {100*m['flip']/m['iv']:.0f}%, inside {100*m['inside']/m['iv']:.0f}% (label waits {100*m['lw']/m['iv']:.0f}%), outside {100*m['out']/m['iv']:.0f}%")
print('scene t>=120 s, frames', len(S), 'span', S[0]['t'], S[-1]['t'], 'fps', len(S)/(S[-1]['t']-S[0]['t']))
rep('all scene', S)
rep('typical (15-40 ms)', [x for x in S if 15<=x['iv']<40])
rep('40-100 ms', [x for x in S if 40<=x['iv']<100])
rep('over 100 ms', [x for x in S if x['iv']>=100])
tot=sum(x['iv'] for x in S); 
for lo,hi in [(0,40),(40,100),(100,1e9)]:
    v=[x['iv'] for x in S if lo<=x['iv']<hi]; print(f"frames {lo}-{hi}: {len(v)}, {100*sum(v)/tot:.0f}% of the time")
# GPU-bound proxy: frames where gpu busy >= 90% of interval
gb=[x for x in S if x['gpu']>=0.9*x['iv']]; print('frames with GPU busy >= 90% of the interval', len(gb), f"{100*len(gb)/len(S):.0f}%")
big=[x for x in S if x['iv']>=100]
for x in big: print(f"  t {x['t']:.2f} iv {x['iv']:.0f} gpu {x['gpu']:.0f} flip {x['flip']:.0f} in {x['inside']:.0f} (lw {x['lw']:.0f} sync {x['sync']:.0f} prep {x['prep']:.0f}) out {x['out']:.0f} jobs {x['jobs']:.0f}+{x['rj']:.0f}")
print('---- excluding the load-transition frame at 120.58')
S2=[x for x in S if x['iv']<1000]
rep('over 100 ms (21)', [x for x in S2 if x['iv']>=100])
rep('all scene w/o it', S2)
for k in ['iv','gpu','flip','inside','sync','prep','cs','out']:
    v=sorted(x[k] for x in S2 if 15<=x['iv']<40); print(k,'typical p10/p50/p90', round(v[len(v)//10],1), round(v[len(v)//2],1), round(v[9*len(v)//10],1))
