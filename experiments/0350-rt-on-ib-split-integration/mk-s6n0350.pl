#!/usr/bin/perl
# derive experiments/0350-*/s6n0350.sh from experiments/0342-*/s6n0342.sh: 0342 -> 0350 except in the launcher anchors
# (their text is the integrated play-pkg.sh's, "exp 0342 (F412, F415)"), the two new switches required in the
# emulator's environment, and exp 0346/0349 lines kept in the run's -0341.txt summary.
use strict; use warnings;
my ($in, $out) = @ARGV;
open my $fh, '<', $in or die "$in: $!\n"; my @l = <$fh>; close $fh;
my ($env, $sum) = (0, 0);
for (@l) {
  next if /^chk 'export BC5_DIRECT_/;
  s/0342/0350/g;
  if (/^WANTENV=\(/) {
    s/\Q"BC5_DIRECT_SHADOW_LABELS=1"\E/"BC5_DIRECT_SHADOW_LABELS=1" "BC5_DIRECT_HOST_INDIRECT=learn:1100000000" "BC5_DIRECT_SOFT_WAIT_MS=8"/ and $env++;
  }
  if (/^\{ grep -a "experiment 0341 switches\\\|experiment 0341 at close"/) {
    s/\Q"experiment 0341 switches\|experiment 0341 at close"\E/"experiment 0341 switches\\|experiment 0341 at close\\|experiment 0346 at close\\|experiment 0349\\|cs refused"/ and $sum++;
  }
}
die "WANTENV edits $env, summary edits $sum (want 1 and 1)\n" unless $env == 1 && $sum == 1;
open my $o, '>', $out or die "$out: $!\n"; print {$o} @l; close $o or die "$out: $!\n";
print "ok\n";
