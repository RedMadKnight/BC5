#!/usr/bin/perl
# BC5 experiment 0345 (exp 0341's mk-test.pl): the maintainer's test launcher from the integrated play-pkg.sh (5b469087:
# one ring and both 0341 guards are its own lines, RT on in the shared input.cfg): one log per start in
# ~/bc5-work/exp0345/play/, and the experiment's switch exported after the settings loop — a GFX-form DISPATCH_INDIRECT
# with base-1 0 gets the title's window as its base, learned from its SET_BASEs, 0x1100000000 until one is seen (exp 0344).
# The emulator comes from the shortcut's Exec (BC5_EMU=~/bc5-work/exp0345/kyty_emulator). Each anchor must occur once.
# usage: mktest0345.pl <play-pkg.sh> <play-pkg-0345t.sh>
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mktest0345.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my @r = (["LOG=~/bc5-work/play-pkg-last.log\n", "# exp 0345 (the maintainer's RT-on test): one log per start, beside the experiment\nLOG=~/bc5-work/exp0345/play/play-\$(date +%Y%m%d-%H%M%S).log\n"],
         ["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\nexport BC5_DIRECT_GFX_BASE1=learn:1100000000  # exp 0345: a GFX-form DISPATCH_INDIRECT with base-1 0 gets the title's window as its base (learned from its SET_BASEs; 0x1100000000 until one is seen), or a NOP when window + offset is not mapped\n"]);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
die "the launcher has no one-ring line\n" unless $t =~ /^export BC5_DIRECT_COMPUTE_RING=-1 /m;
die "the launcher has no guards line\n" unless $t =~ /^export BC5_DIRECT_GPU_CHECK_PRODUCT=1 BC5_DIRECT_SHADOW_LABELS=1/m;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
print "$out written: a log per start in ~/bc5-work/exp0345/play/, BC5_DIRECT_GFX_BASE1=learn:1100000000\n";
