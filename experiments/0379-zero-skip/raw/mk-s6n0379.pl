#!/usr/bin/perl
# exp 0379: s6n0379.sh from exp 0372's s6n0372.sh — arm shared (the shared normal build, pinned) or private (this
# experiment's build), exp0379 paths, the top session's lock, exp 0379's sampler (mount reads, PSI io), the zero lines.
# usage: perl mk-s6n0379.pl experiments/0372-pad-haptics-replug/raw/s6n0372.sh experiments/0379-zero-skip/raw/s6n0379.sh
use strict; use warnings;
my ($in, $out) = @ARGV;
open my $fh, '<', $in or die "$in: $!\n"; local $/; my $s = <$fh>; close $fh;
sub rep { my ($from, $to, $n) = @_; my $c = () = $s =~ /\Q$from\E/g; die "[$from] occurs $c times, want $n\n" unless $c == $n; $s =~ s/\Q$from\E/$to/g; }
# the launcher reference of exp 0372's integration stays exp 0372's
rep('"$W/exp0372/integration/new-md5.env"', '"$W/EXP0372KEEP/integration/new-md5.env"', 1);
rep('BIN=$W/exp0372/kyty_emulator; WANT=$(cat "$W/exp0372/binary.md5" 2> /dev/null)   # exp 0372: the private pad-route build (build0372.sh)',
    'ARM=${BC5_0379_ARM:-}  # exp 0379: shared = the shared normal build (pinned), private = build0379.sh\'s binary' . "\n" .
    'case "$ARM" in' . "\n" .
    '  shared) BIN=$W/kytyplus-build/src/kyty_emulator; WANT=${EXPECT_NORMAL:-58c4a627} ;;' . "\n" .
    '  private) BIN=$W/exp0379/kyty_emulator; WANT=$(cat "$W/exp0379/binary.md5" 2> /dev/null) ;;' . "\n" .
    '  *) echo "BC5_0379_ARM is shared or private"; exit 1 ;;' . "\n" .
    'esac', 1);
rep('the private pad-route build $WANT (exp 0372: software replug test, replug0372.sh)', 'the $ARM build $WANT (exp 0379: zero-skip A/B)', 1);
rep('top exp 0372 |', 'top exp 0379 |', 4);
rep('exp0372', 'exp0379', 9);
rep('EXP0372KEEP', 'exp0372', 1);
rep('[ -x "$E30/sample0330.sh" ]', '[ -f "$E/in/raw/sample0379.sh" ]', 1);
rep('"$E30/sample0330.sh" "$R/$TAG-mem.txt"', 'bash "$E/in/raw/sample0379.sh" "$R/$TAG-mem.txt"', 1);
rep('no $SAVES, $LAUNCH_SRC, o2-continue.cmd, sample0330.sh or $LEARN_SRC', 'no $SAVES, $LAUNCH_SRC, o2-continue.cmd, sample0379.sh or $LEARN_SRC', 1);
rep('  nice -n 19 grep -a "^direct: .* MiB pinned" "$J" | tail -1 > "$R/$TAG-pinned.txt"',
    '  nice -n 19 grep -a "^direct: .* MiB pinned" "$J" | tail -1 > "$R/$TAG-pinned.txt"' . "\n" .
    '  nice -n 19 grep -a "^zero skip\|^zero scan" "$J" > "$R/$TAG-zero.txt"  # exp 0379' . "\n" .
    '  nice -n 19 grep -a "^direct: .* MiB pinned" "$J" | awk \'NR % 20 == 1\' > "$R/$TAG-pinned-every20.txt"  # exp 0379: the pinned size as it grows', 1);
my $head = "#!/usr/bin/env bash\n# BC5 experiment 0379 (exp 0372's s6n0372.sh, made by mk-s6n0379.pl): the S6N route RT on, arm shared (the\n# shared normal build) or private (~/bc5-work/exp0379/kyty_emulator, binary.md5), with exp 0379's sampler; switches\n# through BC5_0368_SWITCHES (e.g. the zero scan, the zero skip). Everything else as s6n0368.sh: private wd and save copy,\n# live saves compared only.\n# usage: BC5_0379_ARM=shared|private [BC5_0368_SWITCHES=...] s6n0379.sh <live-saves sum> <tag> [secs] on\n";
$s =~ s/\A#!\/usr\/bin\/env bash\n/$head/ or die "no shebang\n";
open my $o, '>', $out or die "$out: $!\n"; print {$o} $s; close $o or die "$out: $!\n";
print "ok\n";
