#!/usr/bin/env python3
# BC5 exp 0381: the offsets of 0x909977100's runs in J1 and J2 (from j2shape0381.py's output, chain offsets) and the
# step between the second burst's two runs. RESTORE is the restore's size in dwords; HEAD the first dispatch's offset in
# the faulting title buffer (ACQUIRE_MEM 8 + LOAD_SH_REG_INDEX 5).
RESTORE, HEAD = 58, 13
rows = [  # run, chain dwords, offset of run A, of run B, previous dispatch before B
    ("J2-1", 47670, 186, 32772, 32657),
    ("J2-2", 47670, 186, 32772, 32657),
    ("J2-3", 77940, 30456, 63042, 62927),
    ("J2-4", 103865, 56397, 88983, 88868),
    ("J2-5", 67871, 20387, 52973, 52858),
]
print("J1: chain 88848 with run A at 56333, then chain 15083 with run B at 13")
j1 = 88848 - 56333 + HEAD
print("J1 step A to B across the chain break: %d" % j1)
for r, n, a, b, p in rows:
    print("%s chain %d: A %d B %d step %d (J1 + %d); B minus its previous dispatch %d" % (r, n, a, b, b - a, b - a - j1, b - p))
print("first burst, runs at 23864/53054 in J1: step %d; J2-1 %d, J2-2 %d (no restore between them)" % (53054 - 23864, 53024 - 23834, 53199 - 24009))
print("J2-4's chain minus J1's two chains: %d" % (103865 - (88848 + 15083)))
