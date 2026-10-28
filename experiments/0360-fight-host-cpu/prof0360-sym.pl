#!/usr/bin/perl
# BC5 experiment 0360: resolves the sampler's "cpu prof top host:" buckets (offsets from the emulator's load base, in
# 16-byte steps) to function names with the private binary's `nm -n -C --defined-only` output, and sums the samples by
# function per thread group. Uses the last "cpu prof top host" line in the file (the counts are cumulative).
# usage: prof0360-sym.pl <nm output> <file with the cpu prof lines> [functions per group, default 25]
use strict;
use warnings;
my ($nmf, $file, $per) = @ARGV;
$per //= 25;
my $n;
if ($nmf =~ /\.gz$/) { open($n, "-|", "gzip", "-dc", $nmf) or die "$nmf: $!\n"; } else { open($n, "<", $nmf) or die "$nmf: $!\n"; }
my (@addr, @name);
while (my $l = <$n>) {
	next unless $l =~ /^([0-9a-f]+) ([tTwWiI]) (.+)$/;
	push @addr, hex($1);
	push @name, $3;
}
close $n;
die "no text symbols in $nmf\n" unless @addr;
sub sym {
	my ($a) = @_;
	my ($lo, $hi) = (0, $#addr);
	return "(below the first symbol)" if $a < $addr[0];
	while ($lo < $hi) {
		my $mid = int(($lo + $hi + 1) / 2);
		if ($addr[$mid] <= $a) { $lo = $mid; } else { $hi = $mid - 1; }
	}
	return $name[$lo];
}
my $h;
if ($file =~ /\.gz$/) { open($h, "-|", "gzip", "-dc", $file) or die "$file: $!\n"; } else { open($h, "<", $file) or die "$file: $!\n"; }
my $last;
while (my $l = <$h>) { $last = $l if $l =~ /^cpu prof top host /; }
close $h;
die "no 'cpu prof top host' line in $file\n" unless defined $last;
my ($total) = $last =~ /, (\d+) samples;/;
my %f;
my %g;
while ($last =~ / (\S+?):([0-9a-f]+)=(\d+)/g) {
	my ($grp, $off, $cnt) = ($1, hex($2), $3);
	my $s = sym($off);
	$s = substr($s, 0, 140) if length($s) > 140;
	$f{$grp}{$s} += $cnt;
	$g{$grp} += $cnt;
}
printf "the last cumulative host histogram: %d samples in all buckets; the listed buckets by group:\n", $total // 0;
for my $grp (sort { $g{$b} <=> $g{$a} } keys %g) {
	printf "== %s: %d samples in the listed buckets\n", $grp, $g{$grp};
	my @fs = sort { $f{$grp}{$b} <=> $f{$grp}{$a} } keys %{$f{$grp}};
	for my $s (@fs[0 .. ($#fs < $per - 1 ? $#fs : $per - 1)]) { printf "  %6d %5.1f%%  %s\n", $f{$grp}{$s}, 100.0 * $f{$grp}{$s} / $g{$grp}, $s; }
}
