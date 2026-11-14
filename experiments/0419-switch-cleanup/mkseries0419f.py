#!/usr/bin/env python3
"""BC5 experiment 0419: the deciding series for the GPU hang at 601 s of candidate F's long walk (README section 13),
ordered by the top session on 2026-11-13. Made from chk0419f.sh (lock, pad recorder, `second`). Five arms, each the
second title's walk to G+620 (past 601 s), a private copy of the save, the fault record on, RT on, pad keys recorded:
  sA  F (private 1a2900a0), no zero scan, no writers catcher
  sB  F with BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0
  sC  F with exp 0418's NEW rows skipped (BC5_DIRECT_START_STATE_SKIP = the five rows that candidate B's launcher did not
      already set: SPI_SHADER_REQ_CTRL_PS, GE_MIN_VTX_INDX, GE_MAX_VTX_INDX, VGT_INSTANCE_BASE_ID, VGT_GS_RINGS).
      Not all eight: CP_COHER_START_DELAY, VGT_TF_RING and VGT_HS_OFFCHIP_PARAM were on in B through launcher words that F
      no longer reads, so skipping them would take away what B had and test something else.
  sD  the control: the SHARED build B (51af1ed7), the same walk
  sE  F with the zero scan and BC5_GUARD_WRITERS=1 (the arm that hung), run again
All five run whatever the earlier ones gave: a hang is an arm's RESULT (the fault record is written, the emulator is
gone, the next arm starts clean). The series stops only when the kernel says a reset failed, or the box rebooted (then
this script is gone anyway and its lock line is stale). After each arm: its end line, the journal's memory lines at
580-620 s, and for a new fault record its "what the host saw" line and the probe's lines on the timed-out jobs.
usage: mkseries0419f.py <chk0419f.sh> <out dir>      on the box (detached): series0419f.sh"""
import sys

f, out = sys.argv[1:3]
s = open(f, encoding="utf-8", newline="").read()
assert "\r" not in s
head = s[:s.index("WD=$N/wda; KEEP=")]
a = 'exp 0419 candidate F, private: ASTRO BOT x4, the second title x6 (walk, walk K1R off, cutscene arm; twice each), lean" 60'
assert head.count(a) == 1
head = head.replace(a, 'exp 0419: the deciding series for F\'s hang at 601 s: five walks to G+620 (F, F K1R off, F without exp 0418\'s new rows, shared B, F + scan + writers); about 70 minutes" 78')
a = 'grep -aqF BC5_GUARD_WRITERS "$BN" && grep -aqF BC5_DIRECT_START_STATE_SKIP "$BN" ||'
assert head.count(a) == 1
head = head.replace(a, '[ "$MN" = 1a2900a08142311961050686395c4054 ] && [ "$MS" = 51af1ed78e84291caf5ee042ea82c46d ] ||')
head = head.replace("NOT STARTED, the private build is not candidate F", "NOT STARTED, the private build is not F's 1a2900a0 or the shared build is not B's 51af1ed7")
tail = r'''BOOT=$(cat /proc/sys/kernel/random/boot_id)
ZL=$W/exp0412/play-pkg-0412.sh; [ -f "$ZL" ] || ZL=$W/play-pkg.sh
ZN=$(sed -n 's/^export BC5_DIRECT_EAGER_NAMES="\(.*\)"$/\1/p' "$ZL" | head -1)
arm() {  # tag, binary, md5, words...
    local tag=$1 t0 J d; t0=$(date +%s); OK=1; KERN=0
    echo "== $(date +%T) $tag: $(shift 3; echo "${*:-no extra word}" | cut -c1-200)"
    PLAYS=620 second "$@"
    J=$(sed -n 's/^journal \([^ ]*\) .*$/\1/p' "$R/$tag-journal.txt" 2> /dev/null)
    echo "$tag memory at 580-620 s:"; grep -a '^memory (exp 0401): t \(5[89][0-9]\|6[01][0-9]\)\.' "$J" 2> /dev/null | cut -c1-170
    echo "$tag frame-profile lines over 500 ms: $(grep -a 'frame profile' "$J" 2> /dev/null | awk '$6 + 0 > 500' | wc -l); last flip line t: $(grep -a 'frame profile' "$J" 2> /dev/null | tail -1 | cut -c1-40)"
    for d in $(find "$FR" -mindepth 1 -maxdepth 1 -type d -newermt "@$t0" 2> /dev/null | sort); do
        echo "$tag FAULT RECORD $d"
        grep -a -m1 '^what the host saw' "$d/record.txt" | cut -c1-260
        grep -a -m1 '^when' "$d/record.txt" | cut -c1-120
        grep -a -i -m6 'timed out\|acb #\|dcb #' "$d/journal-tail.txt" | cut -c1-260
    done
    echo "$tag kernel lines: $(grep -c . "$R/$tag-dmesg-after.txt" 2> /dev/null)"; grep -i 'timeout\|reset' "$R/$tag-dmesg-after.txt" 2> /dev/null | cut -c1-160 | head -4
    # R55 / Codex 2026-11-13 20:13 and 21:13 UTC: no next arm after a kernel line, a new fault record or an unknown end,
    # also when the reset succeeded (added 2026-11-14; the runs of sections 14 and 15 were made without this line)
    [ "$KERN" = 0 ] || { echo "series0419f STOP after $tag: kernel error, new fault record, or unknown run status"; echo "series0419f ended $(date +%T): STOPPED"; exit 1; }
    if grep -qi 'reset.*fail\|fail.*reset' "$R/$tag-dmesg-after.txt" 2> /dev/null; then echo "series0419f STOP after $tag: the kernel reports a failed reset"; echo "series0419f ended $(date +%T): STOPPED"; exit 1; fi
    [ "$(cat /proc/sys/kernel/random/boot_id)" = "$BOOT" ] || { echo "series0419f STOP: the boot id changed"; exit 1; }
    sleep 10
}
arm sA "$BN" "$MN"
arm sB "$BN" "$MN" BC5_GUARD_K1R=0 BC5_GUARD_K1_FILTER=0
arm sC "$BN" "$MN" BC5_DIRECT_START_STATE_SKIP=SPI_SHADER_REQ_CTRL_PS:GE_MIN_VTX_INDX:GE_MAX_VTX_INDX:VGT_INSTANCE_BASE_ID:VGT_GS_RINGS
arm sD "$SN" "$MS"
arm sE "$BN" "$MN" BC5_DIRECT_ZEROSCAN_AT=175,295,415,535,640 BC5_GUARD_WRITERS=1 ${ZN:+"BC5_DIRECT_ZERO_NAMES=$ZN"}
echo "series0419f ended $(date +%T): all five arms ran"
'''
t = (head + tail).replace("chk0419f", "series0419f")
open(out + "/series0419f.sh", "w", encoding="utf-8", newline="\n").write(t)
print("series0419f.sh ok")
