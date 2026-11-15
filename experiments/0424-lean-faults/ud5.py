import sys
L=open(sys.argv[1]).read().split('\n')
i=[k for k,l in enumerate(L) if l.startswith('IB #')][0]
n=int(L[i].split()[3]); d=[int(x,16) for x in L[i+1:i+1+n]]
p=0; sh={}; first=None; w=[]; nd=0; k=0
while p<len(d):
    h=d[p]; t=h>>30
    if t!=3: p+=1; continue
    op=(h>>8)&0xff; c=((h>>16)&0x3fff)+1; b=d[p+1:p+1+c]
    if op in (0x76,0x9b):
        o=b[0]&0xffff
        if o<=0x245<o+len(b)-1: w.append((p,b[1+0x245-o], o, len(b)-1))
    if op==0x63 or op==0x5f: w.append((p,'LOAD_SH_REG op %x'%op,b[:4],0))
    if op in (0x15,0x16):
        pg=(sh.get(0x20c,0)|(sh.get(0x20d,0)&0xff)<<32)<<8
        if pg==0x909939900 and first is None: first=p
        nd+=1
    if op==0x76:
        for kk,v in enumerate(b[1:]): sh[(b[0]&0xffff)+kk]=v
    p+=1+c
print('first refit dispatch at dword',first)
print('writes of COMPUTE_USER_DATA_5 (SH 0x245):',len(w))
for x in w[:12]: print('  at',x[0],'value',x[1] if isinstance(x[1],str) else '%08x'%x[1],'(SET_SH_REG from 0x%x, %d regs)'%(x[2],x[3]) if not isinstance(x[1],str) else x[2])
print('before the first refit:', sum(1 for x in w if x[0]<first))
pass
