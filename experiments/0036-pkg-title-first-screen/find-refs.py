import struct, sys
# Find rel32 calls/jmps to a target and absolute 8-byte pointers to it in a raw memory dump.
path, base, target = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
d = open(path, "rb").read()
t = struct.pack("<Q", target)
i = d.find(t)
while i != -1:
    print(f"pointer at {base + i:#x}")
    i = d.find(t, i + 1)
for op in (b"\xe8", b"\xe9"):
    i = d.find(op)
    while i != -1 and i + 5 <= len(d):
        rel = struct.unpack_from("<i", d, i + 1)[0]
        if base + i + 5 + rel == target:
            print(f"{'call' if op == b'\xe8' else 'jmp'} at {base + i:#x}")
        i = d.find(op, i + 1)
