#!/usr/bin/perl
# BC5 experiment 0380: s6n0380.sh from exp 0378's s6n0378.sh, by literal edits only:
# - its directory ~/bc5-work/exp0380s (log, wd, saves snapshot, raw/), its lock line "top exp 0380 | rebase run";
# - the private build ~/bc5-work/exp0380r/kyty_emulator (the shared objects + exp 0380's archive, link0380r.py),
#   md5 pinned through BC5_0380_WANT;
# - no forced sampler requests (the installed sampler 0377 still runs and records any stall by itself);
# - the backend's exp 0380 lines (the rebase counters) kept in raw/<tag>-0380.txt.
# The switch itself (BC5_DIRECT_REBASE_DISPATCH=1) comes in through s6n0378.sh's BC5_0368_SWITCHES, which the script
# both passes to the emulator and checks in its environment.
# usage: perl mk-s6n0380.pl s6n0378.sh s6n0380.sh <binary md5>
use strict;
use warnings;
my ($in, $out, $md5) = @ARGV;
die "usage: mk-s6n0380.pl <s6n0378.sh> <out> <md5>\n" unless defined $md5 && $md5 =~ /^[0-9a-f]{8}$/;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my @r = (
	[q{BIN=$W/kytyplus-build/src/kyty_emulator; WANT=${BC5_0378_WANT:-58c4a627}   # exp 0378: the shared normal build as installed (F504)},
	 qq{BIN=\$W/exp0380r/kyty_emulator; WANT=\${BC5_0380_WANT:-$md5}   # exp 0380: the shared objects + exp 0380's backend archive (link0380r.py)}],
	[q{FORCE=$HOME/bc5-data/captures/gpu-stall/force; NF=0; LASTF=-10},
	 q{FORCE=$HOME/bc5-data/captures/gpu-stall/force; NF=40; LASTF=-10   # exp 0380: no forced requests}],
	[q{} . '} > "$R/$TAG-0341.txt" 2> /dev/null   # exp 0341: the backend' . q{'s lines},
	 q{} . '} > "$R/$TAG-0341.txt" 2> /dev/null   # exp 0341: the backend' . q{'s lines} . "\n" .
	 q{{ grep -a "experiment 0380 switch" "$R/$TAG-play.log"; grep -a "experiment 0380 periodic\|experiment 0380 at close" "$R/$TAG-play.log" | tail -3; } > "$R/$TAG-0380.txt" 2> /dev/null   # exp 0380: the rebase counters}],
);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o\n" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
my $n1 = ($t =~ s/exp0378/exp0380s/g);
my $n2 = ($t =~ s/top exp 0378 \| second-title baseline/top exp 0380 | rebase run/g);
my $n3 = ($t =~ s/\^top exp 0378 \|/^top exp 0380 |/g);
my $n4 = ($t =~ s/play-pkg-0378\.diff/play-pkg-0380s.diff/g);
my $n5 = ($t =~ s/play-pkg-0378\.sh/play-pkg-0380s.sh/g);
my $n6 = ($t =~ s/\(\$TAG, shared normal \$WANT, forced register samples only\)/(\$TAG, private exp0380r \$WANT, \$SWITCHES)/g);
die "the lock text was not adapted\n" unless $n6 == 1;
print "replaced: exp0378 $n1, lock text $n2, lock anchors $n3, diff name $n4, launcher name $n5\n";
# comments that cite exp 0378 stay; no path, lock or file name of it may
die "an exp 0378 path or lock is left\n" if $t =~ /exp0378|top exp 0378|0378\.diff|play-pkg-0378\.sh/;
$t =~ s/^(# BC5 experiment )0378 /$1 0380 (s6n0378.sh by mk-s6n0380.pl; the rebase fix runs) /m;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
