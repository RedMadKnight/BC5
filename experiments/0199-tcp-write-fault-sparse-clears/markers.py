#!/usr/bin/env python3
# List the debug-marker strings a PM4 dump writes (WRITE_DATA to register 0xc343, preceded by
# SET_UCONFIG_REG 0x342 push/pop words), with their dword position, and every dispatch/draw
# position, so a dispatch can be placed inside its marker.
import struct, sys

def main():
    b = open(sys.argv[1], 'rb').read()
    d = struct.unpack('<%dI' % (len(b) // 4), b[: len(b) // 4 * 4])
    i = 0
    stack = []
    pending = ''
    while i < len(d):
        h = d[i]
        if h == 0xffff1000 or h >> 30 != 3:
            i += 1
            continue
        n = ((h >> 16) & 0x3fff) + 1
        op = (h >> 8) & 0xff
        body = d[i + 1: i + 1 + n]
        if op == 0x37 and n >= 4 and body[1] == 0xc343:
            pending += b''.join(struct.pack('<I', x) for x in body[3:]).split(b'\0')[0].decode('latin1')
        elif op == 0x79 and n >= 2 and body[0] == 0x342:
            v = body[1]
            if (v >> 24) == 0xc2:  # pop
                if pending:
                    stack.append(pending); pending = ''
                print('%6d %s pop  %s' % (i, '  ' * len(stack), stack.pop() if stack else '?'))
            elif (v >> 24) == 0xc1:
                if pending:
                    stack.append(pending); print('%6d %s push %s' % (i, '  ' * (len(stack) - 1), pending))
                pending = struct.pack('<I', body[2]).split(bytes(1))[0].decode('latin1') if n >= 3 else '?'
        elif op in (0x15, 0x16, 0x2d, 0x27, 0x24, 0x25, 0x38, 0x2c):
            if pending:
                stack.append(pending); pending = ''
            print('%6d %s %s' % (i, '  ' * len(stack), {0x15: 'DISPATCH_DIRECT', 0x16: 'DISPATCH_INDIRECT'}.get(op, 'draw op%02x' % op)))
        if pending and op not in (0x37, 0x79):
            stack.append(pending)
            print('%6d %s push %s' % (i, '  ' * (len(stack) - 1), pending))
            pending = ''
        i += 1 + n

main()
