#!/usr/bin/env bash
# BC5 experiment 0345: READ-ONLY reads after R1's machine-down (2026-10-27 13:29, RT off, the private build 495f8795,
# BC5_DIRECT_GFX_BASE1=learn): which dispatches the GfxBase rebased, what base-1 the host carried for them, and what
# sat at the CP's fetch point. Reads the run's play log, the timeout dumps and the journal of play-20261027-1327, and
# writes text into ~/bc5-work/exp0345/raw/h3-* only — offsets, counts, opcodes, headers, program and argument
# addresses; no dword of a buffer is copied. Guard: no emulator, an empty BOX-LOCK, its own line while it runs,
# ionice -c3 nice -n 19. usage: probe0345.sh   (on the box, with ../exp0344's ibmap0344.pl and known0344.txt, or
#        BC5_0345_IBMAP=<dir> naming where they are)
set -u
E=$HOME/bc5-work/exp0345; R=$E/raw; LOCK=$HOME/bc5-work/BOX-LOCK
CAP=${BC5_0345_CAPTURE:-$HOME/bc5-data/captures/play-20261027-1327}
DCB=$CAP/gc/ib-timeout-00081041-dcb-98099.bin; ACB=$CAP/gc/ib-timeout-00081042-acb-1318.bin; J=$CAP/gc/direct.log
PLAY=$E/play-last.log; DEVCD=$HOME/bc5-data/captures/devcoredump/20261027-132921-devcd1.txt
CS_SIZE=${BC5_0345_CS_SIZE:-162176}; BUFSZ=${BC5_0345_BUFSZ:-87424}
IBMAP=${BC5_0345_IBMAP:-$HOME/bc5-work/exp0344}
N="ionice -c3 nice -n 19"
pgrep '^kyty_emulator' > /dev/null && { echo "an emulator runs: stop"; exit 1; }
[ -e "$LOCK" ] || touch "$LOCK"
[ -s "$LOCK" ] && { echo "box locked: $(cat "$LOCK")"; exit 1; }
for f in "$DCB" "$J" "$IBMAP/ibmap0344.pl" "$IBMAP/known0344.txt"; do [ -r "$f" ] || { echo "not readable: $f"; exit 1; }; done
echo "bvh exp 0345 | read-only: R1's dumps, journal and play log read (perl + grep, ionice idle, nice 19; no emulator) | start $(date +%H:%M) | until ~$(date -d +5min +%H:%M)" > "$LOCK"
trap 'grep -q "^bvh exp 0345 | read-only" "$LOCK" 2> /dev/null && : > "$LOCK"' EXIT
mkdir -p "$R"
cat > "$E/setbase0345.pl" <<'PL'
# the SET_BASE index-1 packets of a dump (offset, header, lo, hi: the host's conversions carry header 0xc0021102, the
# shader-type bit), and every GFX-form DISPATCH_INDIRECT before the first of them (offset, data offset): what the
# experiment rebased relied on a base from an earlier job
use strict; use warnings; no warnings "portable";
open(F, "<", $ARGV[0]) or die; binmode F; local $/; my @ib = unpack("V*", <F>);
my ($first, $nb, $nd, $printed) = (-1, 0, 0, 0);
for (my $q = 0; $q < @ib;) {
	my $h = $ib[$q]; my $t = $h >> 30; my $l = 1;
	if ($t == 3 || $t == 0) { my $c = ($h >> 16) & 0x3fff; $l = $c == 0x3fff ? 1 : $c + 2; }
	my $op = $t == 3 ? ($h >> 8) & 0xff : -1;
	if ($op == 0x11 && $l >= 4 && ($ib[$q + 1] & 0xf) == 1) {
		$first = $q if $first < 0; $nb++;
		printf "SET_BASE at %u header 0x%08x lo 0x%x hi 0x%x%s\n", $q, $h, $ib[$q + 2], $ib[$q + 3], ($h & 2) ? " (shader type compute: a host conversion)" : "" if $nb <= 12 || $q > @ib - 400;
	}
	if ($op == 0x16 && $l == 3 && $first < 0) { $nd++; printf "dispatch before any SET_BASE at %u: header 0x%08x (%s type), data offset 0x%x, initiator 0x%x\n", $q, $h, ($h & 2) ? "compute" : "gfx", $ib[$q + 1], $ib[$q + 2] if $printed++ < 20; }
	$q += $l;
}
printf "%u SET_BASE index-1 packets (first at %d); %u GFX-form dispatches before the first\n", $nb, $first, $nd;
PL
{
  echo "== $(date '+%F %T') exp 0345 R1 reads; kernel $(uname -r)"
  for f in "$DCB" "$ACB" "$J" "$PLAY" "$DEVCD"; do [ -r "$f" ] && echo "$f $(stat -c '%s bytes, %y' "$f") md5 $(md5sum < "$f" | cut -c1-8)" || echo "missing: $f"; done
} > "$R/h3-inputs.txt"; cat "$R/h3-inputs.txt"
echo "== 1. the experiment's own lines in the play log (the switch, one line per program, the close summary)"
[ -r "$PLAY" ] && { grep -a "experiment 0345\|experiment 0341 switches\|experiment 0341 at close\|experiment 0341 periodic" "$PLAY" | tail -30 | cut -c1-300 | tee "$R/h3-play-0345-lines.txt"; echo "rebase lines: $(grep -a -c 'experiment 0345 rebase' "$PLAY")"; grep -a -n "fps counter\|Access violation\|Segmentation\|TIMEOUT\|timed out" "$PLAY" | tail -8 | cut -c1-200 > "$R/h3-play-tail.txt"; } || echo "no play log at $PLAY"
echo "== 2. the dcb dump mapped (ibmap0344.pl; a chain: the size will not replay, the fetch point is early or not)"
$N perl "$IBMAP/ibmap0344.pl" "$DCB" "$CS_SIZE" "$BUFSZ" "$IBMAP/known0344.txt" > "$R/h3-ibmap-dcb.txt" 2>&1; sed -n '1,8p' "$R/h3-ibmap-dcb.txt" | cut -c1-220; sed -n '/^fetch point/,$p' "$R/h3-ibmap-dcb.txt" | cut -c1-200 | head -40
echo "== 3. the dcb's SET_BASE packets (title vs host conversions) and the dispatches before the first"
$N perl "$E/setbase0345.pl" "$DCB" | tee "$R/h3-dcb-setbase.txt" | tail -40
[ -r "$ACB" ] && { echo "== 3b. the acb dump"; $N perl "$E/setbase0345.pl" "$ACB" | tail -6 | tee "$R/h3-acb-setbase.txt"; }
echo "== 4. the journal: marks, the 30 lines before the submit, the probe's dispatch lines near the fetch point and the largest grid, the host's carried-base lines, write lines at the fault page"
L=$($N grep -a -n "submit #8104[12] \|timeout probe: dcb 98099\|timeout probe: dcb #81041 \|timeout probe: acb #81042 " "$J" | head -8); echo "$L" | cut -c1-200 | tee "$R/h3-journal-marks.txt"
S=$(echo "$L" | grep "submit #81041 dcb" | head -1 | cut -d: -f1); A=$(echo "$L" | grep "timeout probe: dcb 98099" | head -1 | cut -d: -f1); B=$(echo "$L" | grep "timeout probe: dcb #81041 " | head -1 | cut -d: -f1)
[ -n "$S" ] && $N sed -n "$((S > 30 ? S - 30 : 1)),$((S + 4))p" "$J" | cut -c1-220 > "$R/h3-journal-before-submit.txt" && echo "before the submit: $(wc -l < "$R/h3-journal-before-submit.txt") lines"
if [ -n "$A" ] && [ -n "$B" ] && [ "$B" -gt "$A" ]; then
  $N sed -n "${A},${B}p" "$J" > "$R/h3-journal-dcb-probe.txt"
  echo "dcb probe section lines $A-$B: $(wc -l < "$R/h3-journal-dcb-probe.txt"); dispatch lines $(grep -c 'dispatch op' "$R/h3-journal-dcb-probe.txt"), wait $(grep -c 'wait op' "$R/h3-journal-dcb-probe.txt"), write $(grep -c 'write op' "$R/h3-journal-dcb-probe.txt")"
  tail -1 "$R/h3-journal-dcb-probe.txt" | cut -c1-300
  grep -a "dispatch op 16 at 9590[0-9]:\|dispatch op 1[56] at 9[45][0-9][0-9][0-9]:" "$R/h3-journal-dcb-probe.txt" | head -12 | cut -c1-240 | tee "$R/h3-journal-largest.txt"
  grep -a "0x11da0e2\|11da0e2" "$R/h3-journal-dcb-probe.txt" | head -8 | cut -c1-240 | tee "$R/h3-journal-faultpage.txt"
  grep -o '^  #[0-9]*: [0-9]* ->' "$R/h3-ibmap-dcb.txt" | awk '{print $2}' | tr -d ':' | sort -un | while read -r q; do grep -a "dispatch op 1[56] at ${q}:" "$R/h3-journal-dcb-probe.txt"; done | cut -c1-240 | tee "$R/h3-journal-at-fetch.txt"
fi
$N grep -a -n "  indirect op 16 at\|not mapped, DROPPED\|gpu check: " "$J" | tail -12 | cut -c1-220 | tee "$R/h3-journal-host-base-lines.txt"
echo "== 5. the devcoredump's registers (read-only)"
[ -r "$DEVCD" ] && grep -a -i "CP_PFP_HEADER_DUMP\|CP_ME_HEADER_DUMP\|CP_IB1_BASE\|CP_IB1_BUFSZ\|CP_IB1_CMD_BUFSZ\|CP_IB2\|GCVM_L2_PROTECTION_FAULT_STATUS\|GCVM_L2_PROTECTION_FAULT_ADDR\|GRBM_STATUS\b\|GRBM_STATUS_SE\|CP_PFP_INSTR_PNTR\|CP_ME_INSTR_PNTR\|CP_STALLED\|CP_BUSY_STAT\|^thread\|^process\|^fault" "$DEVCD" | head -40 | cut -c1-200 | tee "$R/h3-devcd-registers.txt"
echo "== $(date +%T) done; text in $R/h3-*; lock released on exit"
