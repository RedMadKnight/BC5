#!/usr/bin/perl
# BC5 experiment 0367: derives run0367.sh, go0367.sh and chain0367.sh from exp 0360's scripts: exp 0367's work directory
# (~/bc5-work/exp0367), lock prefix ("exp 0367 | s6n run"), switch names (BC5_0367_SWITCHES, BC5_0367_INPUT_CONFIG),
# launcher copy (play-pkg-0367.sh) and summary file (-0367.txt); the binaries' own BC5_0360_METER/PROF switches stay.
# The fight route's files stay in ~/bc5-work/exp0360 (fight1450-*.cmd). Occurrence counts are checked.
# usage: mk-0367.pl <exp 0360 dir> <out dir>
use strict; use warnings;
my ($in, $out) = @ARGV;
sub derive {
	my ($name, $new, @pairs) = @_;
	open(my $h, "<", "$in/$name") or die "$in/$name: $!\n"; my $s = do { local $/; <$h> }; close $h;
	while (@pairs) { my ($o, $n, $want) = splice(@pairs, 0, 3); my $c = () = $s =~ /\Q$o\E/g; die "$name: [$o] $c times, expected $want\n" unless $c == $want; $s =~ s/\Q$o\E/$n/g; }
	open(my $w, ">", "$out/$new") or die; print $w $s; close $w; print "$new from $name\n";
}
derive("run0360.sh", "run0367.sh",
	'E=$HOME/bc5-work/exp0360;', 'E=$HOME/bc5-work/exp0367;', 1,
	'BC5_0360_SWITCHES', 'BC5_0367_SWITCHES', 1,
	'BC5_0360_INPUT_CONFIG', 'BC5_0367_INPUT_CONFIG', 4,
	'exp0360/', 'exp0367/', 7,
	'play-pkg-0360', 'play-pkg-0367', 4,
	'"^exp 0360 |"', '"^exp 0367 |"', 1,
	'echo "exp 0360 | s6n run', 'echo "exp 0367 | s6n run', 1,
	'"^exp 0360 | s6n run"', '"^exp 0367 | s6n run"', 2,
	'(exp 0360: ${REPRO_WHAT:-the CPU meter})', '(exp 0367: ${REPRO_WHAT:-a candidate})', 1,
	'exp 0360 frame profiles', 'exp 0367 frame profiles', 1,
	'$TAG-0360.txt', '$TAG-0367.txt', 2);
derive("go0360.sh", "go0367.sh",
	'exp 0360 laptop helper', 'exp 0367 laptop helper (from exp 0360\'s go0360.sh)', 1,
	'"^exp 0360 | s6n run"', '"^exp 0367 | s6n run"', 1,
	'("exp 0360 | s6n run")', '("exp 0367 | s6n run")', 1,
	'cd $W/exp0360', 'cd $W/exp0367', 1,
	'./run0360.sh', './run0367.sh', 1);
derive("chain0360.sh", "chain0367.sh",
	'# BC5 experiment 0360, laptop side', '# BC5 experiment 0367 (from exp 0360\'s chain0360.sh), laptop side', 1,
	'cand (~/bc5-work/exp0360/<build>/kyty_emulator)', 'pfx (~/bc5-work/exp0367/<build>/kyty_emulator; meter2 from exp 0360)', 1,
	'*) BIN=\'$W/exp0360/\'"$BUILD"\'/kyty_emulator\' ;;', 'meter2) BIN=\'$W/exp0360/meter2/kyty_emulator\' ;; *) BIN=\'$W/exp0367/\'"$BUILD"\'/kyty_emulator\' ;;', 1,
	'BC5_0360_SWITCHES', 'BC5_0367_SWITCHES', 2,
	'go0360.sh', 'go0367.sh', 2);
