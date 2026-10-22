#!/usr/bin/env bash
# Experiment 0199: collect the evidence for the TCP write faults of 2026-10-20 15:08 and 2026-10-22
# (10:28, 10:51, 12:01, 12:47) from the kernel journal, the direct-path journals and the timed-out
# buffers the timeout probe dumped. Read-only; writes text into ~/bc5-work/exp0199/raw.
set -u
E=~/bc5-work/exp0199
C=~/bc5-data/captures
R=$E/raw
mkdir -p "$R"

# 1. Kernel lines: every fault with GCVM_L2_PROTECTION_FAULT_STATUS 0x00?4105[01] (TCP, write), one
# block per page, from the boots of 10-20 and 10-22.
{
  for b in -4 -2; do
    echo "== boot $b"
    journalctl -k -b "$b" --no-pager -o short-precise \
      -g "page fault \(src_id|in page starting at address|PROTECTION_FAULT_STATUS|PERMISSION_FAULTS|ring .* timeout" 2>/dev/null |
      grep -A2 "page fault (src_id:0 ring:40" | grep -v "^--$" | cut -c1-170
  done
} > "$R/kernel-tcp-write-faults.txt"

# 2. Per case: the timed-out submissions, the host's fault query, the learned window, the window's
# state after the device reopen, and the timeout probe's line for the clear dispatch.
case_lines() { # dir fault-hex window-hex dispatch-dword
  local d=$1 f=$2 w=$3 op=$4
  echo "== $d"
  grep -n "TIMEOUT\|^timeout: fault\|^learned: fault\|^reopen" "$C/$d/gc/direct.log" | head -8 | cut -c1-230
  grep -n "^learned $w\|^scratch: window $w" "$C/$d/gc/direct.log" | head -4 | cut -c1-200
  [ -n "$op" ] && grep -n "state before op 15 at $op:\|op 15 at $op:" "$C/$d/gc/direct.log" | head -2 | sed -E 's/: stages .* (cs [0-9a-f]+)( .*)?$/: (program in force) \1/' | cut -c1-230
}
{
  case_lines play-20261020-1503 0x851859a000 0x8516000000 2785
  case_lines play-20261022-1026 0x84a6884000 0x84a2000000 1648
  case_lines play-20261022-1049 0x820c3a6000 0x820a000000 962
  case_lines play-20261022-1200 0x83fdaa0000 0x83fa000000 1128
  case_lines play-20261022-1244 0x1765833000 0x1762000000 ""
} > "$R/journal-lines.txt"

# 3. The clears: the packets from the ACQUIRE_MEM before each one to the marker pop after it, and
# the colour-target registers where the dump binds the same surface.
{
  for spec in "play-20261020-1503/gc/ib-timeout-01370416-dcb-4451.bin 2740 2800 0x8518598000" \
              "play-20261022-1026/gc/ib-timeout-00070590-dcb-1820.bin 1600 1700 0x84a6880000" \
              "play-20261022-1049/gc/ib-timeout-00070258-dcb-9701.bin 915 975 0x820c37f000,0x820c3a6000" \
              "play-20261022-1200/gc/ib-timeout-00071744-dcb-25968.bin 1080 1182 0x83fdaa0000"; do
    set -- $spec
    echo "== $1"
    echo "-- pointers within 64 MiB of the fault ($4):"
    python3 -I $E/ibscan.py "$C/$1" "$4" | cut -c1-200
    echo "-- markers and dispatches in [$2, $3):"
    python3 -I $E/markers.py "$C/$1" | awk -v lo="$2" -v hi="$3" '$1 >= lo && $1 < hi'
    echo "-- packets in [$2, $3):"
    python3 -I $E/ibwalk.py "$C/$1" 0 "$2" "$3" | grep -v "WRITE_DATA .*0000c343" | cut -c1-260
  done
} > "$R/clears.txt"
python3 -I - "$C" >> "$R/clears.txt" <<'EOF'
import struct, sys
C = sys.argv[1]
print('== colour targets bound at the cleared address (CB_COLORn_BASE, INFO, ATTRIB2, ATTRIB3)')
for f, va in [('play-20261022-1200/gc/ib-timeout-00071744-dcb-25968.bin', 0x83fda500),
              ('play-20261022-1049/gc/ib-timeout-00070258-dcb-9701.bin', 0x820c2400)]:
    b = open(C + '/' + f, 'rb').read()
    d = struct.unpack('<%dI' % (len(b) // 4), b)
    i = 0
    while i < len(d):
        h = d[i]
        if h == 0xffff1000 or h >> 30 != 3:
            i += 1
            continue
        n = ((h >> 16) & 0x3fff) + 1
        if (h >> 8) & 0xff == 0x69:
            base = d[i + 1] & 0xffff
            regs = {base + j: d[i + 2 + j] for j in range(n - 1)}
            for r, v in regs.items():
                if v == va and r >= 0x318 and (r - 0x318) % 15 == 0:
                    k = (r - 0x318) // 15
                    a2, a3, info = regs.get(0x3b0 + k, 0), regs.get(0x3b8 + k, 0), regs.get(r + 4, 0)
                    w, hgt = ((a2 >> 14) & 0x3fff) + 1, (a2 & 0x3fff) + 1
                    print('%s dword %d: CB%d base %08x info %08x (format %d) attrib2 %08x (%dx%d) attrib3 %08x (sw mode %d)'
                          % (f, i, k, v, info, (info >> 2) & 0x1f, a2, w, hgt, a3, (a3 >> 14) & 0x1f))
        i += 1 + n
EOF

# 4. L7: no pointer to the fault in either buffer, the passes they hold.
{
  for f in play-20261022-1244/gc/ib-timeout-00169733-dcb-19968.bin play-20261022-1244/gc/ib-timeout-00169737-acb-891.bin; do
    echo "== $f"
    python3 -I $E/ibscan.py "$C/$f" 0x1765833000 | tail -1
    python3 -I $E/markers.py "$C/$f" | grep -c "First-Use" | sed 's/^/First-Use markers: /'
    python3 -I $E/markers.py "$C/$f" | grep " push " | sed 's/^ *[0-9]* *push //' | sort | uniq -c | sort -rn | head -12
  done
  echo "== env of run L7"; cat ~/bc5-work/exp0194/r-L7-hang/env.txt
} > "$R/l7.txt"
ls -la "$R"
