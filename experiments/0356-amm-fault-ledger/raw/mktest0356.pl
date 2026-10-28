#!/usr/bin/perl
# BC5 experiment 0356 (from exp 0349's mktest0349.pl): the maintainer's test launcher from the integrated play-pkg.sh
# (55531ab6: one ring, both 0341 guards, exp 0343's soft-wait bound, exp 0346's host-resolved indirect, exp 0349's
# IB cut are its own lines; RT on in the shared input.cfg): one log per start in ~/bc5-work/exp0356/play/, nothing else.
# The emulator comes from the shortcut's Exec (BC5_EMU=~/bc5-work/exp0356/kyty_emulator, the AMM fault ledger build).
# usage: mktest0356.pl <play-pkg.sh> <play-pkg-0356t.sh>
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mktest0356.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my @r = (["LOG=~/bc5-work/play-pkg-last.log\n", "# exp 0356 (the maintainer's test of the AMM fault ledger build): one log per start, beside the experiment\nLOG=~/bc5-work/exp0356/play/play-\$(date +%Y%m%d-%H%M%S).log\n"]);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
die "the launcher has no one-ring line\n" unless $t =~ /^export BC5_DIRECT_COMPUTE_RING=-1 /m;
die "the launcher has no guards line\n" unless $t =~ /^export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1/m;
die "the launcher has no host-indirect line\n" unless $t =~ /BC5_DIRECT_HOST_INDIRECT=learn:1100000000/;
die "the launcher has no soft-wait line\n" unless $t =~ /BC5_DIRECT_SOFT_WAIT_MS=8/;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
print "$out written: a log per start in ~/bc5-work/exp0356/play/; the switches are the integrated launcher's own\n";
