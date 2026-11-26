#!/usr/bin/perl
# exp 0379, test shortcut: s6n0379t.sh from raw/s6n0379.sh — the smoke run through the TEST launcher
# (~/bc5-work/exp0379t/play-pkg-0379t.sh, made by mkplay0379t.pl) instead of play-pkg.sh: exp0379t paths, the test
# launcher's own LOG line replaced by a fixed smoke log, FORCE_START required in the emulator's environment, the
# launcher's mode line and exp 0380's switch lines kept in raw/<tag>-0379t.txt.
# usage: perl mk-s6n0379t.pl experiments/0379-zero-skip/raw/s6n0379.sh experiments/0379-zero-skip/test0379t/s6n0379t.sh
use strict; use warnings;
my ($in, $out) = @ARGV;
open my $fh, '<', $in or die "$in: $!\n"; local $/; my $s = <$fh>; close $fh;
sub rep { my ($from, $to, $n) = @_; my $c = () = $s =~ /\Q$from\E/g; die "[$from] occurs $c times, want $n\n" unless $c == $n; $s =~ s/\Q$from\E/$to/g; }
rep('exp0379', 'exp0379t', 12);
rep('LAUNCH_SRC=$W/play-pkg.sh;', 'LAUNCH_SRC=$W/exp0379t/play-pkg-0379t.sh;', 1);
rep(q{chk 'LOG=~/bc5-work/play-pkg-last.log'}, q{chk 'LOG=~/bc5-work/exp0379t/play/play-$ZSTAMP.log  # exp 0379t: one log per start'}, 1);
rep(q{-e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0379t/play-last.log  \# exp 0350/0364: own log#'},
    q{-e 's#^LOG=~/bc5-work/exp0379t/play/play-\$ZSTAMP\.log  .*$#LOG=~/bc5-work/exp0379t/smoke-play.log  \# exp 0379t smoke run: its own log#'}, 1);
rep(q{'exp0379t/play-last.log'}, q{'exp0379t/smoke-play.log'}, 1);
rep('WANTENV=("BC5_DIRECT_COMPUTE_RING=-1"', 'WANTENV=("BC5_DIRECT_FORCE_START_000=1" "BC5_DIRECT_COMPUTE_RING=-1"', 1);
rep('  nice -n 19 grep -a "^zero skip\|^zero scan" "$J" > "$R/$TAG-zero.txt"  # exp 0379',
    '  nice -n 19 grep -a "^zero skip\|^zero scan" "$J" > "$R/$TAG-zero.txt"  # exp 0379' . "\n" .
    '  grep -a "^== exp 0379t\|experiment 0380" "$R/$TAG-play.log" > "$R/$TAG-0379t.txt"  # exp 0379t: the mode line, the 0380 switch and close lines', 1);
my $head = "#!/usr/bin/env bash\n# BC5 experiment 0379, test shortcut (raw/s6n0379.sh, made by mk-s6n0379t.pl): the smoke run of the test launcher\n# play-pkg-0379t.sh on the S6N route, RT on, private wd and save copy, live saves compared only.\n# usage: BC5_0379_ARM=private PLAY_PKG_MD5=<test launcher md5> [BC5_0368_SWITCHES=...] s6n0379t.sh <live-saves sum> <tag> [secs] on\n";
$s =~ s/\A#!\/usr\/bin\/env bash\n/$head/ or die "no shebang\n";
open my $o, '>', $out or die "$out: $!\n"; print {$o} $s; close $o or die "$out: $!\n";
print "ok\n";
