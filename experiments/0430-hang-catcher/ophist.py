import sys, collections
L=open(sys.argv[1],errors="replace").read().split("\n")
i=[k for k,l in enumerate(L) if l.startswith("IB #")][0]
n=int(L[i].split()[3]); d=[int(x,16) for x in L[i+1:i+1+n]]
c=collections.Counter(); p=0
while p<len(d):
    h=d[p]; t=h>>30
    if t==3:
        k=(h>>16)&0x3fff; ln=1 if k==0x3fff else k+2; c["%02x"%((h>>8)&0xff)]+=1
    else: ln=1; c["t%d"%t]+=1
    p+=ln
handled=set("68 69 76 9b 79 7a 61 5f 5e 9f 63 64 12 3f 11 26 13 2a 2f 28 15 16 24 25 27 2c 2d 35 38 10".split())
print(" ".join("%s:%d%s"%(k,v,"" if k in handled else "*") for k,v in sorted(c.items())))
