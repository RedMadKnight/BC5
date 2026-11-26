#!/usr/bin/env bash
# BC5 exp 0376: the 09:48:26 GFX ring timeout of the maintainer's play (capture play-20261029-0944), read on the box,
# read only, no GPU work: the devcoredump's CP and GRBM registers (against the resident sampler's five samples), and
# the host's timeout probe in the session journal (as exp 0371's hang0371.sh). Prints register lines, probe lines
# (offsets, program addresses, grids, labels) and line counts only; nothing of the title leaves the box beyond them.
# usage: ssh bc250 'bash -s' < hang0376.sh > raw/box-read.txt
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: not read"; exit 1; }
D=$HOME/bc5-data/captures/devcoredump/20261029-094827-devcd1.txt
J=$HOME/bc5-data/captures/play-20261029-0944/gc/direct.log
echo "== devcoredump $(stat -c '%s bytes' "$D")"
grep -a -n -i -E "^\*\*\*\*|kernel|process|ring|time:|GRBM_STATUS|CP_PFP_INSTR_PNTR|CP_ME_INSTR_PNTR|CP_IB1_BUFSZ|CP_IB1_CMD_BUFSZ|CP_IB1_BASE|CP_IB2|CP_STAT|CP_STALLED|CP_BUSY|CP_CPF|CP_CPC|HEADER_DUMP|SPI_CSQ|VM_L2_PROTECTION|faulty|IB " "$D" | cut -c1-200 | head -120
echo "== the journal: $(wc -l < "$J") lines, $(stat -c '%s' "$J") bytes"
echo "== probe and TIMEOUT lines: $(nice -n 19 grep -a -c "timeout probe\|TIMEOUT" "$J")"
nice -n 19 grep -a -n "timeout probe\|TIMEOUT" "$J" | cut -c1-260 | grep -v "state before op\|gs user data\|V# base\|TF ring" | head -400
echo "== lines naming the timed-out buffers"
nice -n 19 grep -a -n "#183691\|#183692" "$J" | cut -c1-260 | head -40
echo "== the journal's last 30 lines"
tail -n 30 "$J" | cut -c1-260
