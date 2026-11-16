import sys
L=open(sys.argv[1],errors="replace").read().split("\n")
i=[k for k,l in enumerate(L) if l.startswith("IB #")][0]
n=int(L[i].split()[3]); d=[int(x,16) for x in L[i+1:i+1+n]]
stop=int(sys.argv[2]); p=0; sh={}; last={}; base1=None
while p<len(d) and p<stop:
    h=d[p]; t=h>>30
    if t==3:
        c=(h>>16)&0x3fff; ln=1 if c==0x3fff else c+2; op=(h>>8)&0xff
    else: ln=1; op=-1
    b=d[p+1:p+ln]
    if op in (0x76,0x9b) and b:
        o=b[0]&0xffff
        for k,v in enumerate(b[1:]): sh[o+k]=v; last[o+k]=p
    if op==0x11 and b and (b[0]&0xf)==1: base1=(b[1]&~3)|((b[2]&0xffff)<<32); bp=p
    if op in (0x63,0x5f,0x9f,0x64): print("load-type op %02x at %d: %s"%(op,p," ".join("%08x"%x for x in d[p:p+ln])))
    p+=ln
pg=(sh.get(0x20c,0)|(sh.get(0x20d,0)&0xff)<<32)<<8
print("at %d: pgm 0x%x (set at %s), rsrc1/2 %08x %08x, dims-reg 0x207-9 %s"%(stop,pg,last.get(0x20c),sh.get(0x212,0),sh.get(0x213,0)," ".join("%x"%sh.get(0x207+k,0) for k in range(3))))
print("ud0-15:", " ".join("%08x"%sh.get(0x240+k,0) for k in range(16)))
print("ud set at:", " ".join(str(last.get(0x240+k)) for k in range(16)))
print("SET_BASE 1:", hex(base1) if base1 is not None else None)
