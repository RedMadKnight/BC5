#!/usr/bin/perl
# BC5 experiment 0358 (from exp 0356's mktest0356.pl): the maintainer's test launcher from the integrated play-pkg.sh
# (55531ab6: one ring, both 0341 guards, exp 0343's soft-wait bound, exp 0346's host-resolved indirect, exp 0349's
# IB cut are its own lines; RT on in the shared input.cfg): one log per start in ~/bc5-work/exp0358/play/, nothing else.
# The emulator comes from the shortcut's Exec (BC5_EMU=~/bc5-work/exp0358/kyty_emulator, the thread-trap build (exp 0358)).
# usage: mktest0358v4.pl <play-pkg.sh> <play-pkg-0358t.sh>   (v4: + the BC5_0358_FIX=1 line, a 5-line diff)
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mktest0358v4.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my @r = (["LOG=~/bc5-work/play-pkg-last.log\n", "# exp 0358 (the maintainer's test of the thread-trap build): one log per start, beside the experiment\nLOG=~/bc5-work/exp0358/play/play-\$(date +%Y%m%d-%H%M%S).log\n"],
         ["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\nexport KYTY_BC5_INPUT_RECORD=\$HOME/bc5-work/exp0358/play/record-\$(date +%Y%m%d-%H%M%S).txt  # exp 0358: his pad kept per start (the env file's recorder writes one shared file)\nexport BC5_0358_FIX=1  # exp 0358 (trap v4 + the fix candidate): the targeted semaphore wake ON\n"]);
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
print "$out written: a log per start in ~/bc5-work/exp0358/play/; the switches are the integrated launcher's own\n";
