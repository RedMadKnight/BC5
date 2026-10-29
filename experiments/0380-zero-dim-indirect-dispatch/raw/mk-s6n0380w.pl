#!/usr/bin/perl
# BC5 experiment 0380: s6n0380w.sh, the ARGS_WB bench runs, made from s6n0380c.sh by literal edits only: its directory
# ~/bc5-work/exp0380w/run, its lock text "top exp 0380 | wb run", and the binary ~/bc5-work/exp0380w/kyty_emulator
# (the shared objects + archive eff535ac, link0380r.py; no zero skip), md5 pinned. Switches via BC5_0368_SWITCHES.
# usage: perl mk-s6n0380w.pl s6n0380c.sh s6n0380w.sh <binary md5>
use strict;
use warnings;
my ($in, $out, $md5) = @ARGV;
die "usage: mk-s6n0380w.pl <s6n0380c.sh> <out> <md5>\n" unless defined $md5 && $md5 =~ /^[0-9a-f]{8}$/;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $o = q{BIN=$W/exp0380c/kyty_emulator; WANT=${BC5_0380_WANT:-09345cbb}   # exp 0380c: the shared objects + archive bf8b8d4a (link0380r.py), no zero skip};
my $c = () = $t =~ /\Q$o\E/g;
die "the binary line occurs $c times\n" unless $c == 1;
$t =~ s/\Q$o\E/BIN=\$W\/exp0380w\/kyty_emulator; WANT=\${BC5_0380_WANT:-$md5}   # exp 0380w: the shared objects + archive eff535ac (link0380r.py), no zero skip/;
my $n1 = ($t =~ s{exp0380c/run}{exp0380w/run}g);
my $n2 = ($t =~ s/top exp 0380 \| copy run/top exp 0380 | wb run/g);
my $n3 = ($t =~ s/private exp0380c \$WANT/private exp0380w \$WANT/g);
print "replaced: exp0380c/run $n1, lock text $n2, lock detail $n3\n";
die "an exp0380c path is left\n" if $t =~ /exp0380c/;
die "the lock text was not adapted (3 places)\n" unless $n2 == 3 && $n3 == 1;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
