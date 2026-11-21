#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""BC5 experiment 0438: pf438.py against synthetic marks, perf lines in perf 7.0.14's real forms (both modes, as
printed on the box on 2026-11-21) and a maps file.
Frames: 300 of 16.7 ms then every 10th 50 ms; cpu samples: 10 per short frame in libc, 40 per long frame of which 30 in a
guest anon mapping; faults: 1 per short frame, 20 per long frame into an anon region. Checks pf438's per-class counts.
Usage: python -I test_pf438.py PF438.py"""
import os
import subprocess
import sys
import tempfile

pf = sys.argv[1]
d = tempfile.mkdtemp()
t = 1_000_000_000_000
marks, frames = [], []
for i in range(300):
    ms = 50.0 if i % 10 == 9 else 16.7
    marks.append(t)
    frames.append((t, ms))
    t += int(ms * 1e6)
marks.append(t)
open(os.path.join(d, 'm.txt'), 'w').write(''.join(f'{m}\n' for m in marks))
open(os.path.join(d, 'maps.txt'), 'w').write('T 12.3\n7f0000000000-7f0000100000 r-xp 00000000 00:1f 123 /usr/lib64/libc.so.6\n'
                                              '200000000-280000000 rw-p 00000000 00:00 0 \n')
cpu, flt = [], []
for (t0, ms) in frames:
    long = ms > 40
    n = 40 if long else 10
    for k in range(n):
        ts = (t0 + int(k * ms * 1e6 / n) + 1000) / 1e9
        if long and k < 30:
            cpu.append(f'4242 {ts:.9f}:      20000{k:04x} [unknown] ([unknown])')
        else:
            cpu.append(f'4242 {ts:.9f}:      7f0000001234 memcpy (/usr/lib64/libc.so.6)')
    for k in range(20 if long else 1):
        ts = (t0 + int(k * ms * 1e6 / 20) + 2000) / 1e9
        flt.append(f'4242 {ts:.9f}:     2{k:02x}001000 [unknown] ' + ('(/memfd:KytyDirectMemory (deleted))' if k % 2 else '(//anon)') + '     7f0000005678 memset+0x8 (/usr/lib64/libc.so.6)')  # perf 7.0.14's fault forms, a nested dso too
open(os.path.join(d, 'cpu.txt'), 'w').write('\n'.join(cpu) + '\n')
open(os.path.join(d, 'flt.txt'), 'w').write('\n'.join(flt) + '\n')
fails = 0


def run(*a):
    return subprocess.run([sys.executable, '-I', pf, *a], capture_output=True, text=True).stdout


o = run(os.path.join(d, 'm.txt'), os.path.join(d, 'cpu.txt'), os.path.join(d, 'maps.txt'))
print(o)
for want in ('1 vblank: 270 frames', '10.00 samples', '3+ vblank: 30 frames', '40.00 samples', '[anon rw-p 2048 MiB @200000000] 75.0%'):
    if want not in o:
        print('FAIL: missing', want)
        fails += 1
o = run(os.path.join(d, 'm.txt'), os.path.join(d, 'flt.txt'), os.path.join(d, 'maps.txt'), 'a=0-2', 'b=2-9')
print(o)
for want in ('faults', '20.00 faults per frame', '1.00 faults per frame', 'by mapping of the faulting address: [anon rw-p 2048 MiB @200000000] 100.0%', 'a phase [0, 2)'):
    if want not in o:
        print('FAIL: missing', want)
        fails += 1
print('PASS' if fails == 0 else f'FAIL ({fails})')
sys.exit(0 if fails == 0 else 1)
