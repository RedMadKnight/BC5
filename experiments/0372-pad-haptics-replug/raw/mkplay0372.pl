#!/usr/bin/perl
# BC5 experiment 0372 (from exp 0359's mktest0359.pl): the replug test's launcher, derived from the integrated
# play-pkg.sh (55531ab6 on 2026-10-28; its switches are its own lines): the private build
# ~/bc5-work/exp0372/kyty_emulator, the normal build's traces with KYTY_BC5_AUDIO_TRACE=1 and KYTY_BC5_MEASURE=1 set
# explicitly (one "audio trace:" line per port and second, the "pad route:" lines, the "AudioOut (exp 0372)" lines),
# one log and one mount log per start in ~/bc5-work/exp0372/play/, BC5_LEAN cleared. Nothing else changes.
# usage: perl mkplay0372.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0372/play-pkg-0372t.sh
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mkplay0372.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $stamp = q{$(date +%Y%m%d-%H%M%S)};
my @r = (
	["set -u\n",
	 "set -u\n" . q{unset BC5_LEAN BC5_LOGS  # exp 0372: the normal build's traces are the record} . "\n"],
	["EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n",
	 q{EMU=~/bc5-work/exp0372/kyty_emulator  # exp 0372: the pad-route build (build0372.sh)} . "\n"],
	["LOG=~/bc5-work/play-pkg-last.log\n",
	 "mkdir -p ~/bc5-work/exp0372/play\n" . q{LOG=~/bc5-work/exp0372/play/play-} . $stamp . q{.log  # exp 0372: one log per start} . "\n"],
	["MLOG=~/bc5-work/play-pkg-mount.log\n",
	 q{MLOG=~/bc5-work/exp0372/play/mount-} . $stamp . q{.log  # exp 0372: its own mount log} . "\n"],
	["done < \"\$ENVF\"\n",
	 "done < \"\$ENVF\"\n" . q{export KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1  # exp 0372: the audio trace and the pad route lines, logging on or off} . "\n"],
);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
die "the launcher has no audio trace line\n" unless $t =~ /KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1  # exp 0372/;
die "the launcher has no one-ring line\n" unless $t =~ /^export BC5_DIRECT_COMPUTE_RING=-1 /m;
die "the launcher has no pad-volume line\n" unless $t =~ m{~/bc5-work/pad-volume\.sh --watch \$\$};
die "the private binary line is missing\n" unless $t =~ m{^EMU=~/bc5-work/exp0372/kyty_emulator }m;
die "a \$( was lost\n" unless $t =~ /play-\$\(date \+%Y%m%d-%H%M%S\)\.log/;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written: the private build, a log and a mount log per start in ~/bc5-work/exp0372/play/\n";
