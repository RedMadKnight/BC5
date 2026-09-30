import struct,sys,os,math,collections
root=sys.argv[1]
for name in sys.argv[2:]:
    d=open(os.path.join(root,name),"rb").read()
    off=d.find(b"\x7fELF")
    if off<0: print(name,"no ELF"); continue
    e_phoff,=struct.unpack_from("<Q",d,off+0x20); e_phentsize,e_phnum=struct.unpack_from("<HH",d,off+0x36)
    segs=[]
    for i in range(e_phnum):
        p_type,p_flags,p_off,p_va,p_pa,p_filesz,p_memsz=struct.unpack_from("<IIQQQQQ",d,off+e_phoff+i*e_phentsize)
        if p_type==1: segs.append((hex(p_flags),p_filesz,p_memsz))
    body=d[off+0x1000:off+0x1000+65536]
    c=collections.Counter(body); n=len(body); H=-sum(v/n*math.log2(v/n) for v in c.values())
    print(name, "size", len(d), "elf@", hex(off), "PT_LOAD", segs, "entropy(64K@+4K)=%.2f" % H)
