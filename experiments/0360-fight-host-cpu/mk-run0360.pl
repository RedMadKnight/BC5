#!/usr/bin/perl
# BC5 experiment 0360: derives run0360.sh from exp 0358's raw/repro0358.sh (itself exp 0350's s6n0350.sh with the binary
# under test as REPRO_BIN). Literal replacements only, each checked to occur as often as expected:
#   exp 0360's paths, switches and lock prefix; the S6N route's saves (exp0196/saves-before-152617) as the default
#   instead of exp 0358's private copy of the live saves; the launcher check against exp 0350's recorded md5; the lock
#   cleared by its own prefix ("exp 0360 | s6n run": repro0358.sh's EXIT trap looked for "bvh exp 0358 | s6n run" while
#   its lock line said "repro"); and the journal's "cpu meter"/"cpu prof" lines kept as raw/<tag>-meter.txt.
# usage: mk-run0360.pl <repro0358.sh> <run0360.sh>
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mk-run0360.pl <repro0358.sh> <run0360.sh>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $s = do { local $/; <$h> };
close $h;
sub rep {
	my ($old, $new, $want) = @_;
	my $n = () = $s =~ /\Q$old\E/g;
	die "[$old] occurs $n times, expected $want\n" unless $n == $want;
	$s =~ s/\Q$old\E/$new/g;
}
rep('# BC5 experiment 0350 (exp 0341\'s s6n0341.sh):', '# BC5 experiment 0360 (derived by mk-run0360.pl from exp 0358\'s repro0358.sh, which is exp 0350\'s s6n0350.sh with REPRO_BIN):', 1);
rep('E=$HOME/bc5-work/exp0358;', 'E=$HOME/bc5-work/exp0360;', 1);
rep('SWITCHES=${BC5_0358_SWITCHES-}', 'SWITCHES=${BC5_0360_SWITCHES-}', 1);
rep('SAVES=${REPRO_SAVES:-$E/saves-live-47aefd45}   # exp 0358: a private copy of the live saves (never the live ones)',
    'SAVES=${REPRO_SAVES:-$W/exp0196/saves-before-152617}   # exp 0360: the S6N route\'s own saves, copied into the private wd (the live saves are compared only)', 1);
rep('[ -s "$LOCK" ] && ! grep -q "^bvh exp 0358 |" "$LOCK"', '[ -s "$LOCK" ] && ! grep -q "^exp 0360 |" "$LOCK"', 1);
rep('"$W/exp0358/integration/new-md5.env"', '"$W/exp0350/integration/new-md5.env"', 1);
rep('exp0358/', 'exp0360/', 7);
rep('BC5_0358_INPUT_CONFIG', 'BC5_0360_INPUT_CONFIG', 4);
rep('play-pkg-0358', 'play-pkg-0360', 4);
rep('echo "bvh exp 0358 | repro: the second title from a private copy of the live saves (the Continue route), RT $RT, $TAG, the private build $WANT (exp 0358: the thread trap on the shared units)',
    'echo "exp 0360 | s6n run: the second title\'s S6N route, RT $RT, $TAG, the private build $WANT (exp 0360: ${REPRO_WHAT:-the CPU meter})', 1);
rep('"^bvh exp 0358 | s6n run"', '"^exp 0360 | s6n run"', 2);
rep('exp 0358 frame profiles', 'exp 0360 frame profiles', 1);
rep('$TAG-0358.txt', '$TAG-0360.txt', 2);
rep('  nice -n 19 grep -a "compute ring:" "$J" | head -50 > "$R/$TAG-compute-ring.txt";',
    '  nice -n 19 grep -a "^cpu meter\|^cpu prof" "$J" > "$R/$TAG-meter.txt"   # exp 0360: the CPU meter and sampler lines' . "\n" .
    '  nice -n 19 grep -a "compute ring:" "$J" | head -50 > "$R/$TAG-compute-ring.txt";', 1);
my $left = () = $s =~ /0358/g;
open(my $o, ">", $out) or die "$out: $!\n";
print $o $s;
close $o;
print "mk-run0360.pl: wrote $out; '0358' left $left times (comments)\n";
