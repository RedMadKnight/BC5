#!/usr/bin/env bash
# BC5 exp 0419: a read-only look at the second title's own code around the return addresses of its CPU fault at
# eboot+0x1b349f (audio-record-fault.md). The top session's GO of 2026-11-14: only with BOX-LOCK empty, no emulator,
# one lock line, nice 19, the disassembly stays on the box outside git (the repository gets words and offsets only).
# It reads the maintainer's own file, writes only under ~/bc5-work/exp0419/eread (mode 700) and starts nothing.
# usage (on the box): nice -n 19 bash eread0419.sh [path to eboot.bin]
set -u
export LC_ALL=C
W=$HOME/bc5-work; N=$W/exp0413/n; O=$W/exp0419/eread
pgrep '^kyty_emulator' > /dev/null && { echo "eread0419: an emulator is running: NOT STARTED"; exit 1; }
[ -s "$W/BOX-LOCK" ] && { echo "eread0419: BOX-LOCK is not empty: NOT STARTED"; cat "$W/BOX-LOCK"; exit 1; }
. "$N/chainlock0417.inc"
chain_claim "exp 0419: read-only look at the title's code at its CPU fault's return addresses (no emulator, nice 19, CPU only; about 5 minutes)" 15 || { echo "eread0419: NOT STARTED"; exit 1; }
trap chain_release EXIT
mkdir -p "$O" && chmod 700 "$O" || exit 1
EB=${1:-}
if [ -z "$EB" ]; then
    echo "candidates:"; find "$HOME/bc5-data" "$W" -maxdepth 7 -name 'eboot.bin' -size +1M 2> /dev/null | head -20
    echo "eread0419: give the path as the first argument"; exit 0
fi
[ -r "$EB" ] || { echo "eread0419: cannot read $EB"; exit 1; }
echo "file: $EB, $(stat -c %s "$EB") bytes, md5 $(md5sum < "$EB" | cut -c1-8), first bytes: $(head -c 8 "$EB" | od -An -tx1 | tr -s ' ')"
python3 - "$EB" "$O" << 'PYEOF'
import struct, sys
p, out = sys.argv[1:3]
b = open(p, "rb").read()
seg_off = {}  # program header index -> file offset of its bytes, when the file is a container
eh = 0
if b[:4] != b"\x7fELF":
    # a container: a 0x20-byte header, `n` entries of four u64 (properties, offset, file size, memory size), then the ELF
    # header. A data entry's properties hold the program header's index in bits 20..31 and "has blocks" in bit 11.
    n, = struct.unpack_from("<H", b, 0x18)
    print("container: magic %s, %d entries" % (b[:4].hex(), n))
    for i in range(n):
        props, off, fsz, msz = struct.unpack_from("<QQQQ", b, 0x20 + 0x20 * i)
        print("  entry %d: props %#x off %#x filesz %#x memsz %#x" % (i, props, off, fsz, msz))
        if props & 0x800:
            seg_off[(props >> 20) & 0xfff] = (off, fsz, msz, props)
    eh = 0x20 + 0x20 * n
    if b[eh:eh + 4] != b"\x7fELF":
        print("no ELF header after the entries: nothing extracted"); sys.exit(2)
phoff, = struct.unpack_from("<Q", b, eh + 0x20)
phentsize, phnum = struct.unpack_from("<HH", b, eh + 0x36)
print("program headers:")
for i in range(phnum):
    t, fl, off, va, pa, fsz, msz, al = struct.unpack_from("<IIQQQQQQ", b, eh + phoff + i * phentsize)
    print("  %d: type %#x flags %#x off %#x vaddr %#x filesz %#x memsz %#x" % (i, t, fl, off, va, fsz, msz))
    if t == 1 and (fl & 1) and va <= 0x1b3110 < va + fsz:
        if seg_off:
            if i not in seg_off:
                print("  no container entry for this segment"); continue
            off, cfsz, cmsz, props = seg_off[i]
            if cfsz != fsz:
                print("  the entry's size %#x is not the segment's %#x (compressed or encrypted?): not extracted" % (cfsz, fsz)); continue
        lo, hi = 0x110000, 0x1e2000
        lo = max(lo, va); hi = min(hi, va + fsz)
        open(out + "/text.bin", "wb").write(b[off + (lo - va):off + (hi - va)])
        open(out + "/text.lo", "w").write("%#x\n" % lo)
        print("  -> text.bin: vaddr %#x..%#x" % (lo, hi))
PYEOF
[ -s "$O/text.bin" ] || { echo "eread0419: no text extracted"; exit 1; }
LO=$(cat "$O/text.lo")
OD=objdump; command -v objdump > /dev/null || OD="distrobox enter ubuntu -- objdump"
$OD -D -b binary -m i386:x86-64 -M intel --adjust-vma="$LO" "$O/text.bin" > "$O/dis.txt" 2> "$O/dis.err"
chmod 600 "$O"/*
echo "disassembly: $(wc -l < "$O/dis.txt") lines in $O/dis.txt (not for git); errors: $(wc -l < "$O/dis.err")"
grep -n '^ *1b349f:\|^ *1b3110:\|^ *1b3460:\|^ *1d58a6:\|^ *1d23df:\|^ *19fe14:' "$O/dis.txt" | cut -c1-120
echo "eread0419 ended $(date +%T)"
