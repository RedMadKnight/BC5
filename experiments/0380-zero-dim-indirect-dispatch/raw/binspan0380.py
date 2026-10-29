#!/usr/bin/env python3
# BC5 experiment 0380: list the packets of a TITLE IB dumped by the host's timeout probe (ib-timeout-*.bin, little-endian
# dwords as the title wrote them, before the host's filter) in a dword range. Structure only: offset, opcode, length and
# the fields that name what a packet is (register offsets, addresses, counts, wait function/reference); no other payload.
# usage: python3 binspan0380.py <ib-timeout-…-dcb-N.bin> <from> <to>
import struct
import sys

NAMES = {0x10: "NOP", 0x11: "SET_BASE", 0x13: "INDEX_BUFFER_SIZE", 0x15: "DISPATCH_DIRECT", 0x16: "DISPATCH_INDIRECT",
         0x22: "COND_EXEC", 0x26: "INDEX_BASE", 0x2f: "NUM_INSTANCES", 0x37: "WRITE_DATA", 0x3c: "WAIT_REG_MEM",
         0x3f: "INDIRECT_BUFFER", 0x40: "COPY_DATA", 0x42: "PFP_SYNC_ME", 0x46: "EVENT_WRITE", 0x49: "RELEASE_MEM",
         0x50: "DMA_DATA", 0x58: "ACQUIRE_MEM", 0x63: "LOAD_SH_REG_INDEX", 0x76: "SET_SH_REG", 0x79: "SET_UCONFIG_REG",
         0x93: "WAIT_REG_MEM64", 0x9f: "op 9f"}
data = open(sys.argv[1], "rb").read()
ib = list(struct.unpack("<%dI" % (len(data) // 4), data[: len(data) // 4 * 4]))
lo, hi = int(sys.argv[2]), int(sys.argv[3])
print(f"{sys.argv[1].split('/')[-1]}: {len(ib)} dwords")
i = 0
while i < len(ib):
    h = ib[i]
    t = h >> 30
    ln = 1
    if t in (0, 3):
        c = (h >> 16) & 0x3fff
        ln = 1 if c == 0x3fff else c + 2
    op = (h >> 8) & 0xff
    if lo <= i < hi:
        pk = ib[i:i + ln]
        f = ""
        if t == 3:
            if op in (0x76, 0x79) and ln >= 2:
                f = f"reg 0x{pk[1] & 0xffff:x} n {ln - 2}"
            elif op == 0x37 and ln >= 4:
                f = f"ctl 0x{pk[1]:x} (dst_sel {(pk[1] >> 8) & 0xf}) addr 0x{pk[2] | ((pk[3] & 0xffff) << 32):x} n {ln - 4}"
            elif op == 0x3c and ln >= 7:
                f = f"fn {pk[1] & 7} mem {(pk[1] >> 4) & 1} engine {(pk[1] >> 8) & 1} addr 0x{(pk[2] & ~3) | ((pk[3] & 0xffff) << 32):x} ref 0x{pk[4]:x} mask 0x{pk[5]:x}"
            elif op == 0x93 and ln >= 9:
                f = f"fn {pk[1] & 7} engine {(pk[1] >> 8) & 1} addr 0x{(pk[2] & ~7) | ((pk[3] & 0xffff) << 32):x} ref 0x{pk[4] | (pk[5] << 32):x}"
            elif op == 0x50 and ln >= 7:
                f = f"ctl 0x{pk[1]:x} src 0x{pk[2] | (pk[3] << 32):x} dst 0x{pk[4] | (pk[5] << 32):x} n 0x{pk[6] & 0x1fffff:x}"
            elif op == 0x58 and ln >= 8:
                f = f"coher_cntl 0x{pk[1]:x} gcr_cntl 0x{pk[7]:x}"
            elif op == 0x46 and ln >= 2:
                f = f"event {pk[1] & 0x3f} index {(pk[1] >> 8) & 0xf}"
            elif op == 0x11 and ln >= 4:
                f = f"index {pk[1] & 0xf} 0x{(pk[2] & ~3) | ((pk[3] & 0xffff) << 32):x}"
            elif op == 0x26 and ln >= 3:
                f = f"0x{(pk[1] & ~1) | ((pk[2] & 0xffff) << 32):x}"
            elif op == 0x13 and ln >= 2:
                f = f"0x{pk[1]:x}"
            elif op == 0x16 and ln >= 3:
                f = f"offset 0x{pk[1]:x} init 0x{pk[2]:x}"
            elif op == 0x49 and ln >= 6:
                f = f"event {pk[1] & 0x3f} index {(pk[1] >> 8) & 0xf} data_sel {(pk[2] >> 29) & 7} addr 0x{pk[3] | ((pk[4] & 0xffff) << 32):x}"
            elif op == 0x63 and ln >= 5:
                f = f"addr 0x{(pk[1] & ~3) | ((pk[2] & 0xffff) << 32):x} reg/fmt 0x{pk[3]:x} n {pk[4]}"
            elif op == 0x3f and ln >= 4:
                f = f"ib 0x{(pk[1] & ~3) | ((pk[2] & 0xffff) << 32):x} size {pk[3] & 0xfffff}"
        print(f"{i:6d} type {t} op 0x{op:02x} {NAMES.get(op, '') if t == 3 else ''} len {ln} {f}")
    i += ln
