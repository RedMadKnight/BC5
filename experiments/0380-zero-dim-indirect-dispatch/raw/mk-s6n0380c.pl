#!/usr/bin/perl
# BC5 experiment 0380: s6n0380c.sh, the bench run of the argument copy, made from s6n0380.sh by literal edits only:
# its directory ~/bc5-work/exp0380c/run, its lock text "top exp 0380 | copy run", and the binary
# ~/bc5-work/exp0380c/kyty_emulator (the shared objects + archive bf8b8d4a, link0380r.py; no zero skip), md5 pinned.
# The switches come in through BC5_0368_SWITCHES as before.
# usage: perl mk-s6n0380c.pl s6n0380.sh s6n0380c.sh <binary md5>
use strict;
use warnings;
my ($in, $out, $md5) = @ARGV;
die "usage: mk-s6n0380c.pl <s6n0380.sh> <out> <md5>\n" unless defined $md5 && $md5 =~ /^[0-9a-f]{8}$/;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $o = q{BIN=$W/exp0380r/kyty_emulator; WANT=${BC5_0380_WANT:-7943d581}   # exp 0380: the shared objects + exp 0380's backend archive (link0380r.py)};
my $c = () = $t =~ /\Q$o\E/g;
die "the binary line occurs $c times\n" unless $c == 1;
$t =~ s/\Q$o\E/BIN=\$W\/exp0380c\/kyty_emulator; WANT=\${BC5_0380_WANT:-$md5}   # exp 0380c: the shared objects + archive bf8b8d4a (link0380r.py), no zero skip/;
my $n1 = ($t =~ s{exp0380s}{exp0380c/run}g);
my $n2 = ($t =~ s/top exp 0380 \| rebase run/top exp 0380 | copy run/g);
my $n3 = ($t =~ s/private exp0380r \$WANT/private exp0380c \$WANT/g);
print "replaced: exp0380s $n1, lock text $n2, lock detail $n3\n";
die "an exp0380s path is left\n" if $t =~ /exp0380s/;
die "the lock text was not adapted (3 places)\n" unless $n2 == 3 && $n3 == 1;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
