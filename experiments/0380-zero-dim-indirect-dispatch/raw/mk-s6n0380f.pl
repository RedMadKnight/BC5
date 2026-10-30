#!/usr/bin/perl
# BC5 experiment 0380: s6n0380f.sh, the smoke run of the test shortcut "BC5 emulator (test 0380 fix + 0379)", made from
# s6n0380.sh by literal edits only:
# - its directory ~/bc5-work/exp0380t and its lock text "top exp 0380 | fix+0379 smoke run";
# - the source launcher is the shortcut's own ~/bc5-work/exp0380f/play-pkg-0380f.sh (md5 pinned), not play-pkg.sh,
#   with the same four private edits (log, wd, save directory, learned-file copy) and the input-configuration hook.
#   Its log line is the exp 0380f one, so that anchor is the one rewritten;
# - the binary ~/bc5-work/exp0380f/kyty_emulator (md5 pinned).
# usage: perl mk-s6n0380f.pl s6n0380.sh s6n0380f.sh <binary md5> <launcher md5>
use strict;
use warnings;
my ($in, $out, $md5, $lmd5) = @ARGV;
die "usage: mk-s6n0380f.pl <s6n0380.sh> <out> <binary md5> <launcher md5>\n"
  unless defined $lmd5 && $md5 =~ /^[0-9a-f]{8}$/ && $lmd5 =~ /^[0-9a-f]{8}$/;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my @r = (
	[q{BIN=$W/exp0380r/kyty_emulator; WANT=${BC5_0380_WANT:-7943d581}   # exp 0380: the shared objects + exp 0380's backend archive (link0380r.py)},
	 qq{BIN=\$W/exp0380f/kyty_emulator; WANT=\${BC5_0380_WANT:-$md5}   # exp 0380f: shared objects + exp 0379t's zero-skip unit + exp 0380's archive (link0380f.py)}],
	[q{LAUNCH_SRC=$W/play-pkg.sh; LAUNCH=$E/play-pkg-0380s.sh;},
	 q{LAUNCH_SRC=$W/exp0380f/play-pkg-0380f.sh; LAUNCH=$E/play-pkg-0380t.sh;}],
	[q{PLAY_PKG_MD5=${PLAY_PKG_MD5:-55531ab6}   # exp 0378: play-pkg.sh as read on 2026-10-29 10:40},
	 qq{PLAY_PKG_MD5=\${PLAY_PKG_MD5:-$lmd5}   # exp 0380f: the shortcut's launcher as written by mkplay0380f.pl}],
	[q{chk 'LOG=~/bc5-work/play-pkg-last.log'},
	 q{chk 'LOG=~/bc5-work/exp0380f/play/play-$ZSTAMP.log  # exp 0380f: one log per start'}],
	[q{sed -i -e 's#^LOG=~/bc5-work/play-pkg-last\.log$#LOG=~/bc5-work/exp0380s/play-last.log  \# exp 0350/0364: own log#' \\},
	 q{sed -i -e 's#^LOG=~/bc5-work/exp0380f/play/play-\$ZSTAMP\.log  \# exp 0380f: one log per start$#LOG=~/bc5-work/exp0380s/play-last.log  \# exp 0350/0364: own log#' \\}],
	[q{diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0380s.diff"}, q{diff -u "$LAUNCH_SRC" "$LAUNCH" > "$R/play-pkg-0380t.diff"}],
	[q{[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0380s.diff")" = 9 ]}, q{[ "$(grep -c '^[-+][^-+]' "$R/play-pkg-0380t.diff")" = 9 ]}],
	[q{($R/play-pkg-0380s.diff)}, q{($R/play-pkg-0380t.diff)}],
	[q{($TAG, private exp0380r $WANT, $SWITCHES)}, q{($TAG, private exp0380f $WANT, $SWITCHES)}],
);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o\n" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
my $n1 = ($t =~ s/exp0380s/exp0380t/g);
my $n2 = ($t =~ s/top exp 0380 \| rebase run/top exp 0380 | fix+0379 smoke run/g);
print "replaced: exp0380s $n1, lock text $n2\n";
die "an exp0380s path is left\n" if $t =~ /exp0380s/;
die "the lock text was not adapted (3 places)\n" unless $n2 == 3;
$t =~ s/^(# BC5 experiment  0380 )\(/$1(s6n0380f.sh: the fix+0379 shortcut's smoke run) (/m;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
