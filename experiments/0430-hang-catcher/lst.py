import sys
L=open(sys.argv[1],errors="replace").read().split("\n")
i=[k for k,l in enumerate(L) if l.startswith("IB #")][0]
n=int(L[i].split()[3]); d=[int(x,16) for x in L[i+1:i+1+n]]
lo,hi=int(sys.argv[2]),int(sys.argv[3])
p=0
while p<len(d):
    h=d[p]; t=h>>30
    if t==3:
        c=(h>>16)&0x3fff; ln=1 if c==0x3fff else c+2; op=(h>>8)&0xff
    elif t==2: ln=1; op=-1
    else:
        c=(h>>16)&0x3fff; ln=c+2; op=-2
    if lo<=p<=hi or (p<lo<p+ln):
        print("%5d t%d op %02x len %4d: %s"%(p,t,op&0xff,ln," ".join("%08x"%x for x in d[p:p+min(ln,12)])))
    p+=ln
