#!/usr/bin/perl
# BC5 experiment 0360: per-window means of the journal's "frame profile:" lines (one line per flip, exp 0026's
# BC5_DIRECT_FRAME_PROFILE). Columns: flips/s, ms between flips, and the game thread's ms inside the host per flip with
# its parts (sync, hints, prepare, list, cs, fence, cap, label waits, event waits), at the flip, outside, GPU busy,
# jobs, ring jobs, soft-CP passes, and the parts of prepare.
# usage: fp0360.pl <extract.txt> [window seconds, default 5]
use strict;
use warnings;
my ($file, $win) = @ARGV;
$win //= 5;
open(my $h, "<", $file) or die "$file: $!\n";
my %w;
my @keys = qw(iv in sync hints prep list cs fence cap lw ew flip out gpu jobs rj soft pf pt pc pn pcopy);
while (my $l = <$h>) {
	next unless $l =~ /^frame profile: t ([\d.]+) s, ([\d.]+) ms since the last flip; game thread inside the host ([\d.]+) ms \(sync ([\d.]+), hints ([\d.]+), prepare ([\d.]+), list ([\d.]+), cs ([\d.]+), fence ([\d.]+), cap ([\d.]+), label waits ([\d.]+), event waits ([\d.]+)\), at the flip ([\d.]+), outside (-?[\d.]+); GPU busy ([\d.]+) ms in (\d+) jobs \(\+(\d+) from the ring thread\); soft-CP passes ([\d.]+) ms in \d+, waits polled \d+ \([\d.]+ ms, \d+ timed out\); prepare = filter ([\d.]+) \+ tracker ([\d.]+) \+ cu ([\d.]+) \+ nested ([\d.]+) \+ copy ([\d.]+)/;
	my $t = $1;
	my @v = ($2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24);
	my $k = int($t / $win);
	$w{$k}{n}++;
	for my $i (0 .. $#keys) { $w{$k}{$keys[$i]} += $v[$i]; }
}
close $h;
printf "%6s %5s %6s | %6s %6s %5s %6s %5s %5s %5s %5s %6s %6s | %5s %6s | %6s %5s %4s %5s | %5s %5s\n",
	"t", "fl/s", "ms/fl", "inside", "sync", "hints", "prep", "list", "cs", "fence", "cap", "lblw", "evw", "flip", "out", "gpu", "jobs", "rj", "soft", "filt", "trk";
for my $k (sort { $a <=> $b } keys %w) {
	my $n = $w{$k}{n};
	my %m = map { $_ => $w{$k}{$_} / $n } @keys;
	printf "%6d %5.1f %6.1f | %6.1f %6.1f %5.1f %6.1f %5.1f %5.1f %5.1f %5.1f %6.1f %6.1f | %5.1f %6.1f | %6.1f %5.1f %4.1f %5.1f | %5.2f %5.2f\n",
		$k * $win, $n / $win, $m{iv}, $m{in}, $m{sync}, $m{hints}, $m{prep}, $m{list}, $m{cs}, $m{fence}, $m{cap}, $m{lw}, $m{ew}, $m{flip}, $m{out}, $m{gpu}, $m{jobs}, $m{rj}, $m{soft}, $m{pf}, $m{pt};
}
