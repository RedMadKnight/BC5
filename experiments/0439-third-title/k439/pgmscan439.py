#!/usr/bin/env python3
# BC5 exp 0439 (tag pg439, 11-25 night, the top session's step "can a CPU-side census see every GPU reference"):
# disassembles every program a frame dump caught (events.bin, sr0439b.hpp: records "E439", type 4 PGM = u64 address,
# u32 length, bytes) with the host Mesa's LLVM through its C API (LLVMCreateDisasmCPU, gfx1013), up to the first
# s_endpgm, and counts the memory instructions by how they form their address:
#   global_* / flat_*   a 64-bit address in registers, computed by the shader: data-dependent, not in any descriptor
#   scratch_*           the wave's private scratch (BC5's scratch BO)
#   buffer_* / tbuffer_* / s_buffer_*   through a buffer descriptor (V#) in SGPRs
#   image_*             through an image descriptor (T#) in SGPRs
#   s_load_*            scalar loads from a 64-bit base in SGPRs (descriptor tables, pointer chasing)
# Usage (on the box): python3 pgmscan439.py <events.bin> [--list]
import ctypes
import struct
import sys
from collections import Counter

L = ctypes.CDLL('/usr/lib64/libLLVM.so.23.1')
for f in ('LLVMInitializeAMDGPUTargetInfo', 'LLVMInitializeAMDGPUTargetMC', 'LLVMInitializeAMDGPUDisassembler'):
    getattr(L, f)()
L.LLVMCreateDisasmCPU.restype = ctypes.c_void_p
L.LLVMCreateDisasmCPU.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]
L.LLVMDisasmInstruction.restype = ctypes.c_size_t
L.LLVMDisasmInstruction.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_char_p, ctypes.c_size_t]
ctx = L.LLVMCreateDisasmCPU(b'amdgcn-amd-amdhsa', b'gfx1013', None, 0, None, None)
assert ctx, 'no disassembler'


def programs(path):
    d = open(path, 'rb').read()
    i = 0
    while i + 12 <= len(d):
        magic, typ, n = struct.unpack_from('<III', d, i)
        if magic != 0x39343345 or n < 12:
            break
        if typ == 4:
            a, ln = struct.unpack_from('<QI', d, i + 12)
            yield a, d[i + 24:i + 24 + ln]
        i += n


def disasm(code):
    buf = ctypes.create_string_buffer(bytes(code), len(code))
    out = ctypes.create_string_buffer(256)
    pc = 0
    while pc < len(code):
        k = L.LLVMDisasmInstruction(ctx, ctypes.addressof(buf) + pc, len(code) - pc, pc, out, 256)
        if k == 0:
            yield pc, '<bad>'
            pc += 4
            continue
        t = out.value.decode(errors='replace').strip()
        yield pc, t
        pc += k
        if t.startswith('s_endpgm'):
            return


def kind(m):
    for p, k in (('global_', 'global'), ('flat_', 'flat'), ('scratch_', 'scratch'), ('buffer_', 'buffer'), ('tbuffer_', 'buffer'),
                 ('s_buffer_', 's_buffer'), ('image_', 'image'), ('s_load_', 's_load'), ('s_scratch_', 'scratch')):
        if m.startswith(p):
            return k
    return None


tot = Counter()
progs = Counter()
seen = set()
listing = '--list' in sys.argv
for a, code in programs(sys.argv[1]):
    if a in seen:
        continue
    seen.add(a)
    c = Counter()
    n = bad = 0
    ended = False
    for pc, t in disasm(code):
        n += 1
        if t == '<bad>':
            bad += 1
            if bad > 16:
                break
            continue
        m = t.split()[0]
        k = kind(m)
        if k:
            c[k] += 1
        if m == 's_endpgm':
            ended = True
    for k, v in c.items():
        tot[k] += v
        progs[k] += 1
    if listing:
        print('0x%x: %d instructions%s, %s' % (a, n, '' if ended else ' (no s_endpgm)', dict(c)))
print('%d programs; instructions by kind: %s' % (len(seen), dict(tot)))
print('programs with at least one: %s' % dict(progs))
