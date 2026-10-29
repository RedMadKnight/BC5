#!/usr/bin/perl
# BC5 experiment 0380, test shortcut "BC5 emulator (test 0380 rec)" (mkplay0380wb.pl's pattern): the maintainer's play
# to catch one F403 with the flight recorder's part A (F595). The test launcher, RT on (the shared input.cfg), derived
# from the integrated play-pkg.sh, differs from it in:
# - the private build ~/bc5-work/exp0380rec/bin/kyty_emulator (the shared objects and archive, with only
#   src/libs/bc5LleAgc.cpp recompiled from mk-rec0380.py's copy; build0380x.py);
# - BC5_0380_REC=1 (part A: after a fence timeout, CPU-only reads of the title's memory, no packet added); every
#   exp 0379/0380 fix switch unset, so F403 can happen: no write-back, FORCE_START, copy, rebase or zero skip;
# - one log and one mount log per start in ~/bc5-work/exp0380rec/play/; the log's first line names the switch and
#   the binary's md5;
# - a memory sample once a minute (exp 0379t's play-sample0379t.sh, copied beside it), stopped by the launcher's exit.
# usage: perl mkplay0380rec.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0380rec/play-pkg-0380rec.sh
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mkplay0380rec.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $mode = <<'EOS';
# exp 0380rec (the maintainer's play): the flight recorder's part A after a fence timeout; no exp 0379/0380 fix switch.
export BC5_0380_REC=1
unset BC5_DIRECT_ARGS_WB BC5_DIRECT_FORCE_START_000 BC5_DIRECT_ARGS_COPY BC5_DIRECT_REBASE_DISPATCH BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT BC5_0380_REC_SELFTEST_S BC5_NO_TIMEOUT_PROBE
EOS
my @r = (
	["set -u\n",
	 "set -u\n" . q{unset BC5_LEAN BC5_LOGS  # exp 0380rec: the normal build's journal and timeout probe} . "\n" .
	 q{Z=~/bc5-work/exp0380rec; ZSTAMP=$(date +%Y%m%d-%H%M%S)  # exp 0380rec} . "\n"],
	["EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n",
	 q{EMU=~/bc5-work/exp0380rec/bin/kyty_emulator  # exp 0380rec: shared objects and archive, bc5LleAgc.cpp with the recorder (build0380x.py)} . "\n"],
	["LOG=~/bc5-work/play-pkg-last.log\n",
	 "mkdir -p ~/bc5-work/exp0380rec/play\n" . q{LOG=~/bc5-work/exp0380rec/play/play-$ZSTAMP.log  # exp 0380rec: one log per start} . "\n"],
	["MLOG=~/bc5-work/play-pkg-mount.log\n",
	 q{MLOG=~/bc5-work/exp0380rec/play/mount-$ZSTAMP.log  # exp 0380rec: its own mount log} . "\n"],
	["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\n" . $mode],
	["cleanup() {\n  [ -n \"\$MP\" ] || return 0\n",
	 "cleanup() {\n  [ -n \"\${ZSP:-}\" ] && kill \"\$ZSP\" 2> /dev/null  # exp 0380rec: the memory sampler\n  [ -n \"\$MP\" ] || return 0\n"],
	["trap cleanup EXIT\n",
	 "trap cleanup EXIT\n" . q{bash "$Z/play-sample0379t.sh" $$ "$Z/play/mem-$ZSTAMP.txt" < /dev/null > /dev/null 2>&1 & ZSP=$!  # exp 0380rec: once a minute} . "\n"],
	["  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n",
	 q{  echo "== exp 0380rec: BC5_0380_REC=1; no write-back, FORCE_START, copy, rebase or zero skip; binary $(md5sum < "$EMU" | cut -c1-8)"} . "\n" .
	 "  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n"],
);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
die "the launcher has no one-ring line\n" unless $t =~ /^export BC5_DIRECT_COMPUTE_RING=-1 /m;
die "the launcher has no GPU check line\n" unless $t =~ /^export BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 /m;
die "the private binary line is missing\n" unless $t =~ m{^EMU=~/bc5-work/exp0380rec/bin/kyty_emulator }m;
die "the switch line is missing\n" unless $t =~ /^export BC5_0380_REC=1$/m;
die "the timeout probe line is missing\n" unless $t =~ /export BC5_DIRECT_TIMEOUT_PROBE=1/;
die "a \$( was lost\n" unless $t =~ /ZSTAMP=\$\(date \+%Y%m%d-%H%M%S\)/;
my $pos_mode = index($t, q{echo "== exp 0380rec: BC5_0380_REC=1});
my $pos_log = index($t, q{} . '} > "$LOG"');
die "the switch line is not inside the block that writes the log\n" unless $pos_mode > 0 && $pos_log > $pos_mode;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
