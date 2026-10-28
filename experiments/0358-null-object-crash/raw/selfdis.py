# BC5 experiment 0358: disassemble a range of a fake-signed SELF's executable segment (stdout only, nothing kept).
# The SELF (PS4/PS5 "fake-signed" form): a header with an entry table (each entry: properties, file offset, file size,
# memory size; the properties' bits 20-31 name the ELF program header the entry carries), then the ELF header and its
# program headers. The executable PT_LOAD's bytes lie at its entry's file offset; a title offset X (as the host's
# "eboot.bin +X" prints it, the load base 0x900000000 subtracted) is at entry.offset + (X - p_vaddr).
# usage: python3 -I selfdis.py <self> <start hex> <stop hex>   (objdump needed; prints the mapping, then the listing)
import struct, subprocess, sys, tempfile, os
path, start, stop = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
with open(path, "rb") as f:
    head = f.read(0x1000)
    magic = head[:4]
    if magic not in (b"\x4f\x15\x3d\x1d", b"\x54\x14\xf5\xee"):  # the PS4 and PS5 SELF magics
        print("not a fake-signed SELF: magic", magic.hex()); sys.exit(1)
    num_entries = struct.unpack_from("<H", head, 0x18)[0]
    entries = [struct.unpack_from("<QQQQ", head, 0x20 + 32 * i) for i in range(num_entries)]
    elf_off = 0x20 + 32 * num_entries
    if head[elf_off:elf_off + 4] != b"\x7fELF":
        print("no ELF header at", hex(elf_off)); sys.exit(1)
    e_phoff = struct.unpack_from("<Q", head, elf_off + 0x20)[0]
    e_phentsize, e_phnum = struct.unpack_from("<HH", head, elf_off + 0x36)
    f.seek(elf_off + e_phoff)
    ph = f.read(e_phentsize * e_phnum)
    phdrs = [struct.unpack_from("<IIQQQQQ", ph, i * e_phentsize) for i in range(e_phnum)]
    # the executable PT_LOAD covering the range, and the entry that carries it
    found = None
    for props, off, filesz, memsz in entries:
        idx = (props >> 20) & 0xfff
        if idx >= len(phdrs): continue
        p_type, p_flags, p_off, p_va, p_pa, p_filesz, p_memsz = phdrs[idx]
        if p_type == 1 and (p_flags & 1) and p_va <= start and stop <= p_va + p_filesz:
            found = (idx, off, filesz, p_va, p_filesz)
            break
    if found is None:
        print("no executable PT_LOAD covers", hex(start), hex(stop)); sys.exit(1)
    idx, off, filesz, p_va, p_filesz = found
    print("segment phdr %d: p_vaddr 0x%x p_filesz 0x%x, SELF entry offset 0x%x size 0x%x; range 0x%x..0x%x" % (idx, p_va, p_filesz, off, filesz, start, stop))
    f.seek(off + (start - p_va))
    data = f.read(stop - start)
tmp = tempfile.NamedTemporaryFile(prefix="bc5-dis-", suffix=".bin", delete=False)
tmp.write(data); tmp.close()
try:
    out = subprocess.run(["objdump", "-D", "-b", "binary", "-m", "i386:x86-64", "-M", "intel", "--no-show-raw-insn",
                          "--adjust-vma=0x%x" % start, tmp.name], capture_output=True, text=True)
    lines = out.stdout.splitlines()
    for line in lines[7:]:
        print(line)
    if out.returncode != 0: print(out.stderr)
finally:
    os.unlink(tmp.name)
