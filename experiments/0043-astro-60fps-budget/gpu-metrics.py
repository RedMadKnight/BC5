#!/usr/bin/env python3
# BC5 experiment 0043: the SMU's own clock and activity readings from gpu_metrics (read-only).
# Layout: struct gpu_metrics_v2_2 in the Linux kernel's drivers/gpu/drm/amd/include/kgd_pp_interface.h
# (format 2, content 2: header, temperatures, activity, the system clock counter, powers, average
# clocks at byte 64, current clocks at byte 76). TODO(verify): which fields the BC-250's SMU fills.
#   gpu-metrics.py            one reading
#   gpu-metrics.py OUT        a reading every 100 ms while kyty_emulator runs, with /proc/uptime
import glob
import os
import struct
import subprocess
import sys
import time

path = glob.glob("/sys/class/drm/card*/device/gpu_metrics")[0]


def read():
    d = open(path, "rb").read()
    size, fmt, cont = struct.unpack_from("<HBB", d, 0)
    if (fmt, cont) != (2, 2):
        raise SystemExit(f"gpu_metrics format {fmt}.{cont}, not 2.2")
    temp_gfx = struct.unpack_from("<H", d, 4)[0] / 100.0
    gfx_act = struct.unpack_from("<H", d, 28)[0]
    avg = struct.unpack_from("<6H", d, 64)
    cur = struct.unpack_from("<6H", d, 76)
    return temp_gfx, gfx_act, avg[0], cur[0], avg[2], cur[2]


if len(sys.argv) == 1:
    t, a, ag, cg, au, cu = read()
    print(f"gfx temp {t:.1f} C, gfx activity {a}, gfxclk avg {ag} cur {cg} MHz, uclk avg {au} cur {cu} MHz")
    sys.exit(0)

out = open(sys.argv[1], "w")
for _ in range(1200):
    if subprocess.run(["pgrep", "-x", "kyty_emulator"], capture_output=True).returncode == 0:
        break
    time.sleep(0.5)
while subprocess.run(["pgrep", "-x", "kyty_emulator"], capture_output=True).returncode == 0:
    up = open("/proc/uptime").read().split()[0]
    t, a, ag, cg, au, cu = read()
    out.write(f"{up} {t:.1f} {a} {ag} {cg} {au} {cu}\n")
    out.flush()
    time.sleep(0.1)
