#!/usr/bin/perl
# BC5 experiment 0360: the automated fight route from the maintainer's pad record of his 15:38 pass through the fight
# (~/bc5-work/exp0359/play/record-20261028-153847.txt, KYTY_BC5_INPUT_RECORD lines; it starts at his first press on
# the title screen). Splits it at the first wait over 5 s that follows the menu presses (cross / down / up only):
#   <out>-menu.cmd: `wait <title ms>` (85000, the S6N route's own: the title screen is up by then), then his menu presses
#                   as recorded (the slot list, the slot, Continue);
#   <out>-play.cmd: everything after that wait: the gameplay inputs, appended by run0360.sh (REPRO_PHASE2) once the
#                   journal shows the load and then gameplay. The long wait itself (the load) is dropped.
# usage: mk-fight0360.pl <record.txt> <out prefix> [title ms]
use strict;
use warnings;
my ($rec, $out, $title) = @ARGV;
die "usage: mk-fight0360.pl <record.txt> <out prefix> [title ms]\n" unless defined $out;
$title //= 85000;
open(my $h, "<", $rec) or die "$rec: $!\n";
my @l = <$h>;
close $h;
chomp @l;
my $cut = -1;
for my $i (0 .. $#l) {
	if ($l[$i] =~ /^wait (\d+)$/ && $1 > 5000) {
		$cut = $i;
		last;
	}
	die "line " . ($i + 1) . " is not a menu press before the load: $l[$i]\n" unless $l[$i] =~ /^(wait \d+|(hold|release) (cross|down|up))$/;
}
die "no wait over 5 s in $rec\n" if $cut < 0;
my @menu = @l[0 .. $cut - 1];
my @play = @l[$cut + 1 .. $#l];
my $presses = grep { /^hold / } @menu;
open(my $m, ">", "$out-menu.cmd") or die;
print $m "wait $title\n", map { "$_\n" } @menu;
close $m;
open(my $p, ">", "$out-play.cmd") or die;
print $p map { "$_\n" } @play;
close $p;
my $t = 0;
for (@play) { $t += $1 if /^wait (\d+)$/; }
printf "%s-menu.cmd: wait %d + %d lines (%d presses: %s); dropped the load wait of %s; %s-play.cmd: %d lines, %.1f s of play\n", $out, $title, scalar(@menu), $presses,
	join(" ", map { /^hold (\S+)/ ? $1 : () } @menu), $l[$cut], $out, scalar(@play), $t / 1000;
