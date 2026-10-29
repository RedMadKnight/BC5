#!/usr/bin/perl
# exp 0372: s6n0372.sh from exp 0368's s6n0368.sh — the private pad-route build, exp0372 paths, the top session's lock.
use strict; use warnings;
my ($in, $out) = @ARGV;
open my $fh, '<', $in or die "$in: $!\n"; local $/; my $s = <$fh>; close $fh;
my %want;
sub rep { my ($from, $to, $n) = @_; my $c = () = $s =~ /\Q$from\E/g; die "[$from] occurs $c times, want $n\n" unless $c == $n; $s =~ s/\Q$from\E/$to/g; }
rep('BIN=$W/kytyplus-build/src/kyty_emulator; WANT=$(md5sum < "$BIN" | cut -c1-8)   # exp 0368: the SHARED normal build',
    'BIN=$W/exp0372/kyty_emulator; WANT=$(cat "$W/exp0372/binary.md5" 2> /dev/null)   # exp 0372: the private pad-route build (build0372.sh)', 1);
rep('the SHARED normal build $WANT (exp 0368: umr on timeout)', 'the private pad-route build $WANT (exp 0372: software replug test, replug0372.sh)', 1);
rep('bvh exp 0368 |', 'top exp 0372 |', 4);
rep('exp0368', 'exp0372', 9);
my $head = "#!/usr/bin/env bash\n# BC5 experiment 0372 (exp 0368's s6n0368.sh, made by mk-s6n0372.pl): the S6N route RT on with the PRIVATE pad-route\n# build ~/bc5-work/exp0372/kyty_emulator (binary.md5) through play-pkg.sh, while replug0372.sh turns the DualSense's\n# PipeWire card profile off and on. Everything else as s6n0368.sh: private wd and save copy, live saves compared only.\n";
$s =~ s/\A#!\/usr\/bin\/env bash\n/$head/ or die "no shebang\n";
open my $o, '>', $out or die "$out: $!\n"; print {$o} $s; close $o or die "$out: $!\n";
print "ok\n";
