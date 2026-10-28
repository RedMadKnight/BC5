#!/usr/bin/env python3
# BC5 experiment 0358: name the import stubs of a fake-signed PS5 SELF. For each GOT slot given (the address a stub's
# `jmp QWORD PTR [rip+...]` reads), print the symbol the JUMP_SLOT relocation binds there ("NID#lib#module" from the
# dynlibdata string table). The SELF layout follows raw/selfdis.py; the dynamic tags are KytyPlus's loader/elf.h
# (DT_OS_* = 0x610000xx), with offsets relative to the PT_OS_DYNLIBDATA segment's bytes.
# usage: selfimports.py <eboot.bin (SELF)> <got slot hex>...     (prints also the NID -> name when a table is given
#        through BC5_NID_TABLE=<file with lines "NID name">)
import os, struct, sys
path, slots = sys.argv[1], [int(a, 16) for a in sys.argv[2:]]
PT_LOAD, PT_DYNAMIC, PT_OS_DYNLIBDATA = 1, 2, 0x61000000
DT_OS_JMPREL, DT_OS_PLTRELSZ, DT_OS_STRTAB, DT_OS_STRSZ, DT_OS_SYMTAB, DT_OS_SYMTABSZ = 0x61000029, 0x6100002d, 0x61000035, 0x61000037, 0x61000039, 0x6100003f
DT_JMPREL, DT_PLTRELSZ, DT_STRTAB, DT_STRSZ, DT_SYMTAB = 0x17, 0x2, 0x5, 0xa, 0x6
with open(path, "rb") as f:
    head = f.read(0x1000)
    if head[:4] not in (b"\x4f\x15\x3d\x1d", b"\x54\x14\xf5\xee"):
        print("not a fake-signed SELF: magic", head[:4].hex()); sys.exit(1)
    num_entries = struct.unpack_from("<H", head, 0x18)[0]
    entries = [struct.unpack_from("<QQQQ", head, 0x20 + 32 * i) for i in range(num_entries)]
    elf_off = 0x20 + 32 * num_entries
    e_phoff = struct.unpack_from("<Q", head, elf_off + 0x20)[0]
    e_phentsize, e_phnum = struct.unpack_from("<HH", head, elf_off + 0x36)
    f.seek(elf_off + e_phoff)
    ph = f.read(e_phentsize * e_phnum)
    phdrs = [struct.unpack_from("<IIQQQQQ", ph, i * e_phentsize) for i in range(e_phnum)]
    def segment_bytes(p_type):
        for props, off, filesz, memsz in entries:
            if (props & 0x800) == 0:  # not a segment-carrying entry (selfdis.py's reading of the entry props)
                continue
            idx = (props >> 20) & 0xffff
            if idx < len(phdrs) and phdrs[idx][0] == p_type:
                f.seek(off)
                return phdrs[idx], f.read(filesz)
        return None, None
    dyn_ph, dyn = segment_bytes(PT_DYNAMIC)
    dl_ph, dl = segment_bytes(PT_OS_DYNLIBDATA)
    if dyn is None or dl is None:
        print("no PT_DYNAMIC / PT_OS_DYNLIBDATA segment found in the SELF entries;", [hex(p[0]) for p in phdrs]); sys.exit(1)
tags = {}
for i in range(0, len(dyn) - 15, 16):
    tag, val = struct.unpack_from("<qQ", dyn, i)
    if tag == 0: break
    tags.setdefault(tag, val)
def tag(a, b):
    return tags.get(a, tags.get(b))
jmprel, pltrelsz, strtab, strsz, symtab = tag(DT_OS_JMPREL, DT_JMPREL), tag(DT_OS_PLTRELSZ, DT_PLTRELSZ), tag(DT_OS_STRTAB, DT_STRTAB), tag(DT_OS_STRSZ, DT_STRSZ), tag(DT_OS_SYMTAB, DT_SYMTAB)
if None in (jmprel, pltrelsz, strtab, symtab):
    print("dynamic tags missing:", {hex(k): hex(v) for k, v in tags.items()}); sys.exit(1)
names = {}
nid_table = {}
tpath = os.environ.get("BC5_NID_TABLE")
if tpath:
    for line in open(tpath):
        parts = line.split()
        if len(parts) >= 2: nid_table[parts[0]] = parts[1]
for i in range(0, pltrelsz, 24):
    r_offset, r_info, r_addend = struct.unpack_from("<QQq", dl, jmprel + i)
    if (r_info & 0xffffffff) != 7: continue  # R_X86_64_JUMP_SLOT
    sym = r_info >> 32
    st_name = struct.unpack_from("<I", dl, symtab + sym * 24)[0]
    end = dl.index(b"\0", strtab + st_name)
    names[r_offset] = dl[strtab + st_name:end].decode(errors="replace")
print("jump slots:", len(names))
for s in slots:
    n = names.get(s)
    nid = n.split("#")[0] if n else ""
    print("slot %#x: %s%s" % (s, n or "(no JUMP_SLOT relocation)", (" = " + nid_table[nid]) if nid in nid_table else ""))
