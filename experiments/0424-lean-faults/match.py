import sys,re
devcd, kern, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
pages=[int(m.group(1),16) for l in open(kern) if t0<=l[7:15]<=t1 for m in [re.search(r'address 0x([0-9a-f]+) from',l)] if m]
L=open(devcd).read().split('\n')
i=[k for k,l in enumerate(L) if l.startswith('IB #')][0]
n=int(L[i].split()[3]); d=[int(x,16) for x in L[i+1:i+1+n]]
p=0; sh={}; base1=0; disp=[]
while p<len(d):
    h=d[p]; t=h>>30
    if t!=3: p+=1; continue
    op=(h>>8)&0xff; c=((h>>16)&0x3fff)+1; b=d[p+1:p+1+c]
    if op==0x76:
        for k,v in enumerate(b[1:]): sh[(b[0]&0xffff)+k]=v
    if op==0x11 and (b[0]&0xf)==1: base1=(b[1]&~3)|((b[2]&0xffff)<<32)
    if op in (0x15,0x16):
        pg=(sh.get(0x20c,0)|(sh.get(0x20d,0)&0xff)<<32)<<8
        disp.append((p,op,pg,[sh.get(0x240+k,0) for k in range(8)],base1, b[0] if op==0x16 else None))
    p+=1+c
print('fault pages',len(pages))
for pg in pages:
    hits=[x for x in disp if (x[3][4]&~0xfff)==(pg&0xffffffff)]
    for (p,op,prog,ud,b1,off) in hits[:2]:
        print('page %x: dispatch at %d pgm %x ud4 %08x ud5 %08x | indirect base1 %x + %s -> args at %s | V# %x'%(pg,p,prog,ud[4],ud[5],b1,hex(off) if off is not None else '-', hex(b1+off) if off is not None else '-', ud[0]|((ud[1]&0xffff)<<32)))
    if not hits: print('page %x: no dispatch with that ud4 page'%pg)
# how many refit dispatches have ud4 low == indirect args low & ~0xff
r=[x for x in disp if x[2]==0x909939900 and x[5] is not None]
same=sum(1 for x in r if ((x[4]+x[5])>>8)==(((x[4]+x[5])&~0xffffffff|x[3][4])>>8) or ((x[4]+x[5])&0xffffff00)==(x[3][4]&0xffffff00))
print('refit dispatches',len(r),'with ud4 == the args address low 32 (to 256 B):',same)
print('args base hi values', sorted(set((x[4]+x[5])>>32 for x in r)))
print('ud4 - args low32 (bytes), first 10:', [hex(((x[3][4])-((x[4]+x[5])&0xffffffff))&0xffffffff) for x in r[:10]])
