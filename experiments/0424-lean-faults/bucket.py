import sys,collections
walk, layout = sys.argv[1], sys.argv[2]
views=[]
for l in open(layout):
    if l.startswith('#'): continue
    p=l.split(None,5)
    if len(p)<6: continue
    views.append((int(p[1],16),int(p[2],16),p[5].strip(),p[4]))
maps=[]
for l in open(layout.replace('layout-views','layout-mappings')):
    if l.startswith('0x'):
        a,s=l.split()[:2]; maps.append((int(a,16),int(s,16)))
def view(x):
    for a,s,n,f in views:
        if a<=x<a+s: return "%s [%s]"%(n,f)
    return "NO VIEW"
def mapped(x): return any(a<=x<a+s for a,s in maps)
c=collections.Counter(); ex={}
for l in open(walk):
    if 'pgm 0x909939900' not in l: continue
    f=l.split(); x=0x1100000000|int(f[9],16)
    k=(view(x), mapped(x)); c[k]+=1; ex.setdefault(k,[]).append(x)
for k,n in c.most_common(): print(n, k, 'e.g. %x..%x'%(min(ex[k]),max(ex[k])))
vb=collections.Counter()
for l in open(walk):
    if 'pgm 0x909939900' in l:
        f=l.split(); b=int(f[5],16)|((int(f[6],16)&0xffff)<<32); vb[(view(b),mapped(b))]+=1
print('V# base:',vb)
