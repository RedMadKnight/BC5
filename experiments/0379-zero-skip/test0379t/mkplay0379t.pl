#!/usr/bin/perl
# BC5 experiment 0379, test shortcut (exp 0372's mkplay0372.pl; the maintainer's yes "Tak, przygotuj", 2026-10-29): the
# test launcher for two of the maintainer's play sessions, RT on, derived from the integrated play-pkg.sh (55531ab6):
# - the private build ~/bc5-work/exp0379t/kyty_emulator (exp 0379's zero skip + exp 0380's backend);
# - BC5_DIRECT_FORCE_START_000=1 always (exp 0380), BC5_DIRECT_GPU_CHECK_ZERO off;
# - the zero skip's mode chosen per start: SCAN when ~/bc5-work/exp0379t/play-lists/ holds no zero-list-*.txt (the scan
#   writes scan-<start>.txt; at the end a list with >= 3 scans becomes zero-list-<start>.txt), else SKIP on the newest
#   zero-list-*.txt, with the canary and the take-back;
# - one log and one mount log per start in ~/bc5-work/exp0379t/play/, the mode in the log's first line;
# - a memory sample once a minute (play-sample0379t.sh), started after the mount and stopped by the launcher's exit;
# - BC5_LEAN / BC5_LOGS cleared (the zero lines are journal lines of the normal build).
# usage: perl mkplay0379t.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0379t/play-pkg-0379t.sh
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mkplay0379t.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $mode = <<'EOS';
# exp 0379t (the maintainer's yes, 2026-10-29): exp 0380's FORCE_START_AT_000 on every indirect dispatch, its zero
# guard off; exp 0379's zero skip, SCAN until a list from this play exists, then SKIP on the newest list.
export BC5_DIRECT_FORCE_START_000=1
unset BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT
mkdir -p "$Z/play-lists"
ZLIST=$(ls -t "$Z"/play-lists/zero-list-*.txt 2> /dev/null | head -1)
ZSCAN=""
if [ -n "$ZLIST" ]; then
  ZMODE="SKIP $ZLIST"
  export BC5_DIRECT_ZERO_SKIP=$ZLIST
else
  ZMODE=SCAN
  ZSCAN=$Z/play-lists/scan-$ZSTAMP.txt
  export BC5_DIRECT_ZEROSCAN_AT=${BC5_0379T_SCAN_AT:-$(seq -s, 240 120 7200)} BC5_DIRECT_ZEROSCAN_OUT=$ZSCAN
fi
EOS
my $keep = <<'EOS';
# exp 0379t: a scan of this play with at least 3 scans becomes the list the next start skips
if [ -n "$ZSCAN" ] && [ -f "$ZSCAN" ]; then
  ZN=$(awk '$1 == "heap" {print $4}' "$ZSCAN" | sort -n | head -1)
  if [ "${ZN:-0}" -ge 3 ]; then
    mv "$ZSCAN" "$Z/play-lists/zero-list-$ZSTAMP.txt" && echo "== exp 0379t: the zero list of this play ($ZN scans) is $Z/play-lists/zero-list-$ZSTAMP.txt" >> "$LOG"
  else
    echo "== exp 0379t: $ZSCAN has ${ZN:-0} scans (< 3): not used" >> "$LOG"
  fi
fi
EOS
my @r = (
	["set -u\n",
	 "set -u\n" . q{unset BC5_LEAN BC5_LOGS  # exp 0379t: the normal build's journal holds the zero lines} . "\n" .
	 q{Z=~/bc5-work/exp0379t; ZSTAMP=$(date +%Y%m%d-%H%M%S)  # exp 0379t} . "\n"],
	["EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n",
	 q{EMU=~/bc5-work/exp0379t/kyty_emulator  # exp 0379t: zero skip + exp 0380's backend (build0379t.sh)} . "\n"],
	["LOG=~/bc5-work/play-pkg-last.log\n",
	 "mkdir -p ~/bc5-work/exp0379t/play\n" . q{LOG=~/bc5-work/exp0379t/play/play-$ZSTAMP.log  # exp 0379t: one log per start} . "\n"],
	["MLOG=~/bc5-work/play-pkg-mount.log\n",
	 q{MLOG=~/bc5-work/exp0379t/play/mount-$ZSTAMP.log  # exp 0379t: its own mount log} . "\n"],
	["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\n" . $mode],
	["cleanup() {\n  [ -n \"\$MP\" ] || return 0\n",
	 "cleanup() {\n  [ -n \"\${ZSP:-}\" ] && kill \"\$ZSP\" 2> /dev/null  # exp 0379t: the memory sampler\n  [ -n \"\$MP\" ] || return 0\n"],
	["trap cleanup EXIT\n",
	 "trap cleanup EXIT\n" . q{bash "$Z/play-sample0379t.sh" $$ "$Z/play/mem-$ZSTAMP.txt" < /dev/null > /dev/null 2>&1 & ZSP=$!  # exp 0379t: once a minute} . "\n"],
	["  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n",
	 q{  echo "== exp 0379t mode: $ZMODE; BC5_DIRECT_FORCE_START_000=1; binary $(md5sum < "$EMU" | cut -c1-8)"} . "\n" .
	 "  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n"],
	["echo \"== \$(date '+%F %T') exit \$RC\" >> \"\$LOG\"\n",
	 "echo \"== \$(date '+%F %T') exit \$RC\" >> \"\$LOG\"\n" . $keep],
);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
die "the launcher has no one-ring line\n" unless $t =~ /^export BC5_DIRECT_COMPUTE_RING=-1 /m;
die "the launcher has no GPU check line\n" unless $t =~ /^export BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 /m;
die "the private binary line is missing\n" unless $t =~ m{^EMU=~/bc5-work/exp0379t/kyty_emulator }m;
die "the FORCE_START line is missing\n" unless $t =~ /^export BC5_DIRECT_FORCE_START_000=1$/m;
die "a \$( was lost\n" unless $t =~ /ZSTAMP=\$\(date \+%Y%m%d-%H%M%S\)/;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
