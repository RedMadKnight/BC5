# BC5 exp 0439: decode a dumped IB (the timeout probe's ib-timeout-*.bin): packet counts, the first 40 packets, every IB/wait/write/
# release/event/acquire packet, and the last 30. Private input; prints dwords of the title's buffer, so its output is not
# committed.   python decib0439.py <ib-timeout-*.bin>
import struct,sys
b=open(sys.argv[1],'rb').read(); d=struct.unpack('<%dI'%(len(b)//4), b)
print("dwords",len(d))
i=0; ops=[]
while i<len(d):
    h=d[i]; t=h>>30
    if t==3:
        c=(h>>16)&0x3fff; ln=1 if c==0x3fff else c+2; op=(h>>8)&0xff
    elif t==0: ln=((h>>16)&0x3fff)+2; op=-1
    else: ln=1; op=-2
    ops.append((i,op,ln)); i+=ln
from collections import Counter
print(Counter(o for _,o,_ in ops).most_common(14))
for k,(i,op,ln) in enumerate(ops[:40]):
    extra=""
    if op==0x76: extra="reg 0x%x = %s"%(d[i+1]&0xffff, " ".join("%08x"%x for x in d[i+2:i+ln][:4]))
    if op==0x3f: extra="IB 0x%x size %d chain %d"%(((d[i+2]&0xff)<<32)|(d[i+1]&~3), d[i+3]&0xfffff, (d[i+3]>>20)&1)
    if op==0x3c: extra="WAIT 0x%x ref 0x%x fn %d"%(((d[i+3]&0xffff)<<32)|(d[i+2]&~3), d[i+4], d[i+1]&7)
    print(i,hex(op) if op>=0 else op,ln,extra)
print("--- IB, waits, events, releases")
for (i,op,ln) in ops:
    if op in (0x3f,0x3c,0x49,0x46,0x37,0x58):
        s=" ".join("%08x"%x for x in d[i:i+min(ln,8)])
        print(i,hex(op),ln,s)
print("--- last 30 packets")
for (i,op,ln) in ops[-30:]:
    print(i,hex(op) if op>=0 else op,ln," ".join("%08x"%x for x in d[i:i+min(ln,6)]))
