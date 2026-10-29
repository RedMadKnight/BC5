#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-only
# exp 0374: read-only extraction of the stall sampler's T1 records (2026-10-29 06:31-06:35) on the box.
# Run from the laptop:  ssh bc250 bash -s < experiments/0374-stall-sampler-t1/extract0374.sh > raw/extract.txt
# It reads files and the journal only: no GPU work, no root (sudo dmesg is not used), no writes. The devcoredumps
# stay private: only named register lines, the dump's header fields and the gfx queue's two header histories are
# printed, never its command buffers. It stops if an emulator runs (the maintainer may be playing) or if BOX-LOCK
# holds a line that is not "top exp 0374".
set -u
BOX_LC_ALL=${LC_ALL-}   # the live-save checksum sorts in the box's own locale (the reference values were made so)
export LC_ALL=C
pgrep '^kyty_emulator' >/dev/null && { echo "an emulator runs: stop (no box work during play)"; exit 1; }
lock=$(cat ~/bc5-work/BOX-LOCK 2>/dev/null || true)
if [ -n "$lock" ] && ! printf '%s\n' "$lock" | grep -q '^top exp 0374 |'; then
  echo "BOX-LOCK is someone else's: $lock"; exit 1
fi

G=~/bc5-data/captures/gpu-stall
E=$G/event-20261029-063423-gfx_0.0.0
F1=$G/forced-20261029-063308
F2=$G/forced-20261029-063421
D=~/bc5-data/captures/devcoredump/20261029-063423-devcd1.txt
D0=~/bc5-data/captures/devcoredump/20261028-233612-devcd1.txt   # F506's dump (the 23:36 F403-class hang)
P=~/bc5-data/captures/play-20261029-0633/gc/direct.log
REGS='^mm(GRBM_STATUS|GRBM_STATUS2|GRBM_STATUS3|GRBM_STATUS_SE0|GRBM_STATUS_SE1|CP_STAT|CP_STALLED_STAT1|CP_STALLED_STAT2|CP_STALLED_STAT3|CP_BUSY_STAT|CP_CPF_STATUS|CP_CPF_BUSY_STAT|CP_CPF_STALLED_STAT1|CP_ME_INSTR_PNTR|CP_PFP_INSTR_PNTR|CP_RB0_RPTR|CP_RB0_WPTR|CP_IB1_BASE_LO|CP_IB1_BASE_HI|CP_IB1_BUFSZ|CP_IB1_CMD_BUFSZ|GCVM_L2_PROTECTION_FAULT_STATUS) '

echo "# extract0374 on $(hostname) at $(date -Iseconds), kernel $(uname -r)"
echo "## stalls.log"; cat $G/stalls.log
echo "## install-check.txt: find, period and comparison"
sed -n '1,8p' $G/install-check.txt
grep -E '^# CP_(PFP|ME)_HEADER_DUMP period' $G/install-check.txt
sed -n '/^## comparison/,$p' $G/install-check.txt
for d in $F1 $F2 $E; do echo "## $(basename $d)/summary.txt"; cat $d/summary.txt; done
echo "## event kmsg.txt"; cat $E/kmsg.txt
echo "## event regs-1.txt and regs-5.txt: the header histories"
grep -h HEADER_DUMP $E/regs-1.txt; echo "(regs-5)"; grep -h HEADER_DUMP $E/regs-5.txt
echo "## event waves-1.txt (the only stall sample with kept slots)"; cat $E/waves-1.txt
for d in $F1 $F2; do
  w=$d/waves-1.txt
  echo "## $(basename $d)/waves-1.txt counts: lines $(grep -c '^se' $w), HW_ID1-mismatch $(grep -c HW_ID1-mismatch $w)," \
       "PC with beef $(grep -c 'PC=[0-9a-f]*beef' $w), mismatch naming se2/se3 $(grep -cE 'mismatch\(se[23] ' $w)," \
       "EXEC=0 $(grep -c 'EXEC=0 ' $w)"
done
echo "## event fence.txt: gfx_0.0.0 at sample 1 and at write"
grep -A2 -E '^## |gfx_0.0.0' $E/fence.txt | grep -E '^## |Last (signaled fence|emitted) ' | head -18
for d in $D $D0; do
  echo "## devcoredump $(basename $d): header fields and named registers (values only)"
  # grep -a: a dump can hold NUL bytes (20261029-063423's does), and grep then prints only a note on stderr
  sed -n '1,8p' $d | grep -aE '^(kernel|time|vmid|process_name):'
  grep -aE '^\[gfxhub\]|^Faulty page|^Protection fault status' $d
  grep -aE "$REGS" $d
  n=$(grep -an '^num_me: 1 num_pipe: 1' $d | tail -1 | cut -d: -f1)
  [ -n "$n" ] && sed -n "$((n+1)),$((n+80))p" $d | grep -aE '^me 0, pipe 0, queue 0|^mmCP_(PFP|ME)_HEADER_DUMP' | head -17
done
echo "## host direct.log: the clock line and the submits around the hang"
grep -m1 'bc5 clock' ~/bc5-work/play-last.log
tail -c 40000 $P | grep -E 't 74\.(29|3[0-9]|4[0-9])[0-9]* s|#4515[89] done|#4516[01]|GIVEN UP' | cut -c1-230
echo "## journal: boots"; journalctl --list-boots --no-pager | tail -3
echo "## journal -b -1: the sampler unit"; journalctl -b -1 -u bc5-gpu-stall-sampler --no-pager -o short-precise | cut -c1-260
echo "## journal -b -1: kernel lines from 06:34, monotonic"
journalctl -b -1 -k --no-pager -o short-monotonic --since '2026-10-29 06:34' | grep -E 'amdgpu|gpu-watch|sysrq' | cut -c1-230
echo "## journal -b -1: WARNING lines (all of the boot) and wave-read lines"
journalctl -b -1 -k --no-pager | grep -E 'WARNING:' | cut -c1-200
echo "read_wave/amdgpu_debugfs lines: $(journalctl -b -1 -k --no-pager | grep -ciE 'read_wave|amdgpu_debugfs')"
echo "## pstore records of 06:35: the panic's amdgpu, gpu-watch, sysrq and taint lines"
L=$(find ~/bc5-data/captures/pstore -newermt '2026-10-29 06:30' -name 'dmesg-*' | sort)
echo "records: $(printf '%s\n' $L | grep -c .)"
cat $L | grep -E '^<[0-9]+>\[250[0-9]{2}\.' | grep -E 'amdgpu|gpu-watch|sysrq|Kernel panic|Tainted' | sort -u | cut -c1-200
echo "## now: the service and the saves"
echo "is-enabled: $(systemctl is-enabled bc5-gpu-stall-sampler 2>&1); is-active: $(systemctl is-active bc5-gpu-stall-sampler 2>&1)"
journalctl -b 0 -u bc5-gpu-stall-sampler --no-pager -o short-precise | grep -E 'Stopp|Deactivated' | cut -c1-200
ls /usr/local/sbin/bc5-gpu-stall-sampler /etc/systemd/system/bc5-gpu-stall-sampler.service 2>&1 | sed 's/^/  /'
echo "live saves: $(cd ~/bc5-work/_SaveData && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=$BOX_LC_ALL sort -k2 | md5sum | cut -c1-16)"
echo "# extract0374 done"
