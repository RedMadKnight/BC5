#!/usr/bin/env python3
"""BC5: power-cycle the BC-250 through its Tuya smart plug, from the laptop, when the box is down.

After a machine-down (a failed GPU reset, MODE1) the box stops answering and needs its power switched off and on;
the board starts by itself when power returns, and tools/scripts/autologin-setup/ logs the maintainer straight into
Plasma, so the launchers work again without anyone at the box.

The plug is driven locally with tinytuya (python -m pip install tinytuya). Its id, LAN address, local key and
protocol version come from ~/.config/bc5/tuya.json (never committed):
    {"id": "<device id>", "ip": "<LAN address>", "key": "<local key>", "version": 3.4}
tinytuya's wizard (python -m tinytuya wizard, with the maintainer's Tuya IoT project) lists the id and the key.

By default it refuses to cut the power while the box still answers ssh: a box that answers is shut down or
rebooted, not unplugged.

usage: bc5-power-cycle.py [--status] [--force] [--off-seconds N] [--wait N] [--host bc250]
"""
import argparse
import json
import os
import subprocess
import sys
import time

CFG = os.path.expanduser("~/.config/bc5/tuya.json")


def ssh_alive(host: str) -> bool:
    for _ in range(2):
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=8", "-o", "BatchMode=yes", host, "true"],
                           capture_output=True)
        if r.returncode == 0:
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="power-cycle the BC-250 through its Tuya plug")
    ap.add_argument("--host", default="bc250")
    ap.add_argument("--status", action="store_true", help="print the plug's state and exit")
    ap.add_argument("--force", action="store_true", help="cut the power even though ssh answers")
    ap.add_argument("--off-seconds", type=int, default=15, help="how long the power stays off (default 15)")
    ap.add_argument("--wait", type=int, default=300, help="seconds to wait for ssh after power-on (default 300)")
    a = ap.parse_args()
    try:
        import tinytuya
    except ImportError:
        sys.exit("needs tinytuya: python -m pip install tinytuya")
    try:
        cfg = json.load(open(CFG, encoding="utf-8"))
    except OSError:
        sys.exit(f"no plug configuration at {CFG}")
    plug = tinytuya.OutletDevice(cfg["id"], cfg["ip"], cfg["key"])
    plug.set_version(float(cfg.get("version", 3.3)))
    if a.status:
        print(plug.status())
        return
    if ssh_alive(a.host) and not a.force:
        sys.exit(f"{a.host} answers ssh: not cutting its power (--force only if it is hung with ssh still up)")
    print(f"{time.strftime('%H:%M:%S')} power off")
    plug.turn_off()
    time.sleep(a.off_seconds)
    print(f"{time.strftime('%H:%M:%S')} power on")
    plug.turn_on()
    t0 = time.time()
    while time.time() - t0 < a.wait:
        time.sleep(10)
        if ssh_alive(a.host):
            print(f"{time.strftime('%H:%M:%S')} {a.host} answers ssh again ({time.time() - t0:.0f} s after power-on)")
            return
    sys.exit(f"{a.host} not back {a.wait} s after power-on")


if __name__ == "__main__":
    main()
