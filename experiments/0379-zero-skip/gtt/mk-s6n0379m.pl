#!/usr/bin/perl
# exp 0379, GTT growth: s6n0379m.sh from raw/s6n0379.sh, the same A/B runner (arm shared or private, the S6N route, RT on,
# private wd and save copy, live saves compared only) for up to 1,500 s instead of 900, with gtt/sample0379m.sh (the
# emulator's GTT per DRM client from fdinfo) in place of raw/sample0379.sh.
# usage: perl mk-s6n0379m.pl experiments/0379-zero-skip/raw/s6n0379.sh experiments/0379-zero-skip/gtt/s6n0379m.sh
use strict; use warnings;
my ($in, $out) = @ARGV;
open my $fh, '<', $in or die "$in: $!\n"; local $/; my $s = <$fh>; close $fh;
sub rep { my ($from, $to, $n) = @_; my $c = () = $s =~ /\Q$from\E/g; die "[$from] occurs $c times, want $n\n" unless $c == $n; $s =~ s/\Q$from\E/$to/g; }
rep('[ "$SECS" -le 900 ] || { echo "at most 900 s"; exit 1; }', '[ "$SECS" -le 1500 ] || { echo "at most 1500 s"; exit 1; }', 1);
rep('"$E/in/raw/sample0379.sh"', '"$E/in/gtt/sample0379m.sh"', 2);
rep('o2-continue.cmd, sample0379.sh or', 'o2-continue.cmd, sample0379m.sh or', 1);
rep('(exp 0379: zero-skip A/B)', '(exp 0379: GTT growth A/B, 20 min)', 1);
my $head = "#!/usr/bin/env bash\n# BC5 experiment 0379, GTT growth (raw/s6n0379.sh, made by gtt/mk-s6n0379m.pl): the zero-skip A/B runner for up to 1,500 s,\n# with the per-client GTT sampler gtt/sample0379m.sh.\n";
$s =~ s/\A#!\/usr\/bin\/env bash\n/$head/ or die "no shebang\n";
open my $o, '>', $out or die "$out: $!\n"; binmode $o; print {$o} $s; close $o or die "$out: $!\n";
print "ok\n";
