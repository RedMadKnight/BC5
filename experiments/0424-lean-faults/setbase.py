# exp 0424 addendum: per DISPATCH_INDIRECT of a devcoredump IB #0 (read-only), its length, the packets since the last
# SET_BASE 1 and the high dword of SET_BASE 1 + offset. Prints counts only, no IB words.
import sys,collections
L=open(sys.argv[1]).read().split('\n')
i=[k for k,l in enumerate(L) if l.startswith('IB #')][0]
n=int(L[i].split()[3]); d=[int(x,16) for x in L[i+1:i+1+n]]
p=0; pk=[]
while p<len(d):
    h=d[p]; t=h>>30
    if t!=3: pk.append((p,None,[h])); p+=1; continue
    op=(h>>8)&0xff; ln=((h>>16)&0x3fff)+2; pk.append((p,op,d[p:p+ln])); p+=ln
# base1 per dispatch: last SET_BASE idx1 before it; how far
gap=collections.Counter(); hi=collections.Counter()
b1=None; last=None
for k,x in enumerate(pk):
    if x[1]==0x11 and (x[2][1]&0xf)==1: b1=(x[2][2]&~3)|((x[2][3]&0xffff)<<32); last=k
    if x[1]==0x16: gap[k-last if last is not None else -1]+=1; hi[((b1 or 0)+x[2][1])>>32]+=1
print('DISPATCH_INDIRECT lengths', sorted(set(len(x[2]) for x in pk if x[1]==0x16)), 'packets since SET_BASE 1',gap.most_common(5),'arg high',dict(hi))
