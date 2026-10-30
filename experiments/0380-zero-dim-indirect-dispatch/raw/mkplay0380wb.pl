#!/usr/bin/perl
# BC5 experiment 0380, test shortcut "BC5 emulator (test 0380 wb)" (mkplay0380f.pl's pattern). PREPARED after W2/W3,
# NOT installed: the top session relays it to the maintainer. The test launcher, RT on, derived from the integrated
# play-pkg.sh, differs from it in:
# - the private build ~/bc5-work/exp0380w/kyty_emulator (the shared objects + exp 0380's archive eff535ac, link0380r.py);
# - BC5_DIRECT_ARGS_WB=first (a GL2 write-back before the check of the first indirect dispatch after an INDEX_BASE) and
#   BC5_DIRECT_FORCE_START_000=1; every other exp 0379/0380 switch unset: no copy, no rebase, no zero skip;
# - one log and one mount log per start in ~/bc5-work/exp0380wb/play/; the log's first line names both switches and
#   the binary's md5;
# - a memory sample once a minute (exp 0379t's play-sample0379t.sh, copied beside it), stopped by the launcher's exit.
# usage: perl mkplay0380wb.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0380wb/play-pkg-0380wb.sh
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mkplay0380wb.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $mode = <<'EOS';
# exp 0380wb (prepared for the maintainer's play): the GL2 write-back before the first indirect dispatch after an
# INDEX_BASE, with FORCE_START_AT_000; no copy, no rebase, no zero skip.
export BC5_DIRECT_ARGS_WB=first BC5_DIRECT_FORCE_START_000=1
unset BC5_DIRECT_ARGS_COPY BC5_DIRECT_REBASE_DISPATCH BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT
EOS
my @r = (
	["set -u\n",
	 "set -u\n" . q{unset BC5_LEAN BC5_LOGS  # exp 0380wb: the normal build's journal and timeout probe} . "\n" .
	 q{Z=~/bc5-work/exp0380wb; ZSTAMP=$(date +%Y%m%d-%H%M%S)  # exp 0380wb} . "\n"],
	["EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n",
	 q{EMU=~/bc5-work/exp0380w/kyty_emulator  # exp 0380wb: shared objects + exp 0380's archive eff535ac (link0380r.py)} . "\n"],
	["LOG=~/bc5-work/play-pkg-last.log\n",
	 "mkdir -p ~/bc5-work/exp0380wb/play\n" . q{LOG=~/bc5-work/exp0380wb/play/play-$ZSTAMP.log  # exp 0380wb: one log per start} . "\n"],
	["MLOG=~/bc5-work/play-pkg-mount.log\n",
	 q{MLOG=~/bc5-work/exp0380wb/play/mount-$ZSTAMP.log  # exp 0380wb: its own mount log} . "\n"],
	["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\n" . $mode],
	["cleanup() {\n  [ -n \"\$MP\" ] || return 0\n",
	 "cleanup() {\n  [ -n \"\${ZSP:-}\" ] && kill \"\$ZSP\" 2> /dev/null  # exp 0380wb: the memory sampler\n  [ -n \"\$MP\" ] || return 0\n"],
	["trap cleanup EXIT\n",
	 "trap cleanup EXIT\n" . q{bash "$Z/play-sample0379t.sh" $$ "$Z/play/mem-$ZSTAMP.txt" < /dev/null > /dev/null 2>&1 & ZSP=$!  # exp 0380wb: once a minute} . "\n"],
	["  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n",
	 q{  echo "== exp 0380wb: BC5_DIRECT_ARGS_WB=first; BC5_DIRECT_FORCE_START_000=1; no copy, no rebase, no zero skip; binary $(md5sum < "$EMU" | cut -c1-8)"} . "\n" .
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
die "the private binary line is missing\n" unless $t =~ m{^EMU=~/bc5-work/exp0380w/kyty_emulator }m;
die "the switch line is missing\n" unless $t =~ /^export BC5_DIRECT_ARGS_WB=first BC5_DIRECT_FORCE_START_000=1$/m;
die "a \$( was lost\n" unless $t =~ /ZSTAMP=\$\(date \+%Y%m%d-%H%M%S\)/;
my $pos_mode = index($t, q{echo "== exp 0380wb: BC5_DIRECT_ARGS_WB});
my $pos_log = index($t, q{} . '} > "$LOG"');
die "the switch line is not inside the block that writes the log\n" unless $pos_mode > 0 && $pos_log > $pos_mode;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
