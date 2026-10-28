#!/usr/bin/perl
# BC5 experiment 0360: window means of the journal's "cpu meter:" lines (meter0360.pl) and "cpu prof:" lines
# (prof0360.pl). Per window: the box's busy %, CPUs over 90 %, CPU ms per second (on a CPU / runnable waiting) of the
# title's and the host's threads, of the Hi, Lo, Bk workers, game-main and the Render Thread, the Hi workers' largest
# wait, bc5-mount and the rest of the box; the submit costs by class; and the sampler's shares per group.
# usage: meter0360-sum.pl <file with the lines> [window seconds, default 5] [t from] [t to]
use strict;
use warnings;
my ($file, $win, $t0, $t1) = @ARGV;
$win //= 5;
$t0  //= 0;
$t1  //= 1e9;
my $h;
if ($file =~ /\.gz$/) { open($h, "-|", "gzip", "-dc", $file) or die "$file: $!\n"; } else { open($h, "<", $file) or die "$file: $!\n"; }
my (%w, %p, %topn);
while (my $l = <$h>) {
	if ($l =~ /^cpu meter: t ([\d.]+) s, ([\d.]+) ms; box busy (-?[\d.]+) % of (\d+) CPUs, (\d+) over 90 % \[([^\]]*)\]; CPU ms \(on a CPU\/runnable waiting\): title ([\d.]+)\/([\d.]+), host ([\d.]+)\/([\d.]+), bc5-mount (-?[\d.]+), rest of the box (-?[\d.]+); Hi ([\d.]+)\/([\d.]+) \(max wait ([\d.]+)\), Lo ([\d.]+)\/([\d.]+), Bk ([\d.]+)\/([\d.]+), game-main ([\d.]+)\/([\d.]+), Render ([\d.]+)\/([\d.]+); runnable now: title (\d+), host (\d+); submits \(n, jobs, sync\/hints\/prepare\/list\/cs ms\): title (\d+) (\d+) ([\d.\/]+), ring (\d+) (\d+) ([\d.\/]+), chainwd (\d+) (\d+) ([\d.\/]+), host (\d+) (\d+) ([\d.\/]+); (\d+) threads, top by CPU \(cpu\/wait\/sys ms\):(.*); cost (\d+) us/) {
		my $t = $1;
		next if $t < $t0 || $t > $t1;
		my $k = int($t / $win);
		my $s = $2 / 1000.0; # the line's interval in seconds
		my @v = ($3, $5, $7 / $s, $8 / $s, $9 / $s, $10 / $s, $11 / $s, $12 / $s, $13 / $s, $14 / $s, $15, $16 / $s, $17 / $s, $18 / $s, $19 / $s, $20 / $s, $21 / $s, $22 / $s, $23 / $s, $24, $25, $40);
		$w{$k}{n}++;
		for my $i (0 .. $#v) { $w{$k}{v}[$i] += $v[$i]; }
		my @cls = ([$26, $27, $28], [$29, $30, $31], [$32, $33, $34], [$35, $36, $37]);
		for my $c (0 .. 3) {
			my ($n, $j, $parts) = @{$cls[$c]};
			my @q = split /\//, $parts;
			$w{$k}{c}[$c][0] += $n;
			$w{$k}{c}[$c][1] += $j;
			for my $i (0 .. 4) { $w{$k}{c}[$c][2 + $i] += $q[$i] // 0; }
		}
		for my $e (split / /, $39) {
			next unless $e =~ /^(.+)\((.)\)([\d.]+)\/([\d.]+)\/([\d.]+)$/;
			my ($name, $cpu, $wait) = ($1, $3, $4);
			$name =~ s/_\d+$//; # the workers by kind
			$topn{$k}{$name}[0] += $cpu;
			$topn{$k}{$name}[1] += $wait;
		}
	} elsif ($l =~ /^cpu prof: t ([\d.]+) s; per group samples and % title code \/ emulator \/ in the kernel \/ libraries:(.*?) \d+ threads attached/) {
		my $t = $1;
		next if $t < $t0 || $t > $t1;
		my $k = int($t / $win);
		my $groups = $2; # the loop's own matches reset $2
		while ($groups =~ /\G ?(\S+) (\d+): title ([\d.]+) host ([\d.]+) sys ([\d.]+) lib ([\d.]+) \(most (-?\d+)\);/g) {
			my ($g, $n) = ($1, $2);
			$p{$k}{$g}{n} += $n;
			$p{$k}{$g}{title} += $3 * $n / 100;
			$p{$k}{$g}{host} += $4 * $n / 100;
			$p{$k}{$g}{sys} += $5 * $n / 100;
			$p{$k}{$g}{lib} += $6 * $n / 100;
		}
	}
}
close $h;
printf "%5s %4s %3s | %11s %11s | %11s %11s %11s %11s %11s %5s | %6s %6s | %s\n", "t", "busy", ">90", "title c/w", "host c/w", "Hi c/w", "Lo c/w", "Bk c/w", "main c/w", "Render c/w", "Hi mw", "mount", "rest", "submit ms/s by class (n, sync+hints, prepare, cs)";
for my $k (sort { $a <=> $b } keys %w) {
	my $n = $w{$k}{n};
	my @m = map { $_ / $n } @{$w{$k}{v}};
	my $sub = "";
	for my $c (0 .. 3) {
		my @q = map { $_ / $n } @{$w{$k}{c}[$c]};
		$sub .= sprintf(" %s %.0f %.1f %.1f %.1f;", (qw(title ring chainwd host))[$c], $q[0], $q[2] + $q[3], $q[4], $q[6]);
	}
	printf "%5d %4.0f %3.1f | %5.0f/%-5.0f %5.0f/%-5.0f | %5.0f/%-5.0f %5.0f/%-5.0f %5.0f/%-5.0f %5.0f/%-5.0f %5.0f/%-5.0f %5.1f | %6.0f %6.0f |%s\n",
		$k * $win, $m[0], $m[1], $m[2], $m[3], $m[4], $m[5], $m[8], $m[9], $m[11], $m[12], $m[13], $m[14], $m[15], $m[16], $m[17], $m[18], $m[10], $m[6], $m[7], $sub;
	my @tn = sort { $topn{$k}{$b}[0] <=> $topn{$k}{$a}[0] } keys %{$topn{$k}};
	my $line = join(" ", map { sprintf("%s %.0f/%.0f", $_, $topn{$k}{$_}[0] / $n, $topn{$k}{$_}[1] / $n) } @tn[0 .. ($#tn < 9 ? $#tn : 9)]);
	print "      top ms/s (cpu/wait): $line\n";
	if (exists $p{$k}) {
		my $pl = "";
		for my $g (qw(game-main Render Hi Lo Bk IO)) {
			next unless exists $p{$k}{$g} && $p{$k}{$g}{n} > 0;
			my $q = $p{$k}{$g};
			$pl .= sprintf(" %s %d: title %.0f%% host %.0f%% sys %.0f%% lib %.0f%%;", $g, $q->{n}, 100 * $q->{title} / $q->{n}, 100 * $q->{host} / $q->{n}, 100 * $q->{sys} / $q->{n}, 100 * $q->{lib} / $q->{n});
		}
		print "      sampler:$pl\n";
	}
}
