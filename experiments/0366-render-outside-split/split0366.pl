#!/usr/bin/perl
# BC5 experiment 0366: where a thread group's time goes in a window of an exp 0360 meter run, offline from the journal's
# "cpu meter:" and "cpu prof:" lines (exp 0360's meter0360.pl / prof0360.pl).
#  1. Per group, per second: on a CPU, runnable waiting, and off a CPU (the rest of the second: asleep or blocked),
#     from the meter; and the kernel time (stime) of the Render Thread and game-main from the meter's top list.
#  2. Per group, the sampler's classes over the window: title code (the guest's memory), the emulator's own code,
#     a syscall return (the timer expired in the kernel inside a syscall), the other libraries.
#  3. The emulator's code during the window alone: the difference of the cumulative "cpu prof top host" dumps
#     (every 10 s; their top 60 buckets) before and at the end of the window, resolved with the build's nm output.
#  4. The same for the title's code ("cpu prof top title", top 40 buckets), as eboot.bin offsets (base 0x900000000,
#     the play log's fault print); numbers only.
# usage: split0366.pl <meter lines(.gz)> <nm output(.gz)> <t from> <t to> [group, default Render]
use strict;
use warnings;
no warnings "portable"; # the 64-bit eboot base
my ($file, $nmf, $t0, $t1, $want) = @ARGV;
die "usage: split0366.pl <meter lines> <nm> <t from> <t to> [group]\n" unless defined $t1;
$want //= "Render";
sub zopen { my ($f) = @_; my $h; if ($f =~ /\.gz$/) { open($h, "-|", "gzip", "-dc", $f) or die "$f: $!\n"; } else { open($h, "<", $f) or die "$f: $!\n"; } return $h; }
# nm
my (@addr, @name);
my $n = zopen($nmf);
while (my $l = <$n>) { next unless $l =~ /^([0-9a-f]+) ([tTwWiI]) (.+)$/; push @addr, hex($1); push @name, $3; }
close $n;
sub sym { my ($a) = @_; return "(below the first symbol)" if !@addr || $a < $addr[0]; my ($lo, $hi) = (0, $#addr); while ($lo < $hi) { my $mid = int(($lo + $hi + 1) / 2); if ($addr[$mid] <= $a) { $lo = $mid; } else { $hi = $mid - 1; } } my $s = $name[$lo]; $s =~ s/\(.*$//; return $s; }
my $h = zopen($file);
my (%m, $nm_lines, %p, $last_t, @host_dumps, @title_dumps);
my %gmap = (Hi => 0, Lo => 1, Bk => 2, "game-main" => 3, Render => 4);
while (my $l = <$h>) {
	if ($l =~ /^cpu meter: t ([\d.]+) s, ([\d.]+) ms; box busy (-?[\d.]+) %.*?CPU ms \(on a CPU\/runnable waiting\): title ([\d.]+)\/([\d.]+), host ([\d.]+)\/([\d.]+), bc5-mount (-?[\d.]+), rest of the box (-?[\d.]+); Hi ([\d.]+)\/([\d.]+) \(max wait [\d.]+\), Lo ([\d.]+)\/([\d.]+), Bk ([\d.]+)\/([\d.]+), game-main ([\d.]+)\/([\d.]+), Render ([\d.]+)\/([\d.]+);.*submits \(n, jobs, sync\/hints\/prepare\/list\/cs ms\): title (\d+) (\d+) ([\d.\/]+),.*top by CPU \(cpu\/wait\/sys ms\):(.*); cost/) {
		$last_t = $1;
		next if $1 < $t0 || $1 > $t1;
		my $s = $2 / 1000;
		$nm_lines++;
		$m{busy} += $3;
		$m{"title c"} += $4 / $s; $m{"title w"} += $5 / $s; $m{"host c"} += $6 / $s; $m{"host w"} += $7 / $s;
		$m{"Hi c"} += $10 / $s; $m{"Hi w"} += $11 / $s; $m{"Lo c"} += $12 / $s; $m{"Lo w"} += $13 / $s; $m{"Bk c"} += $14 / $s; $m{"Bk w"} += $15 / $s;
		$m{"game-main c"} += $16 / $s; $m{"game-main w"} += $17 / $s; $m{"Render c"} += $18 / $s; $m{"Render w"} += $19 / $s;
		my @q = split /\//, $22;
		$m{"direct ms (title-class threads)"} += ($q[0] + $q[1] + $q[2] + $q[3] + $q[4]) / $s;
		$m{"direct submits"} += $20 / $s;
		my $top = $23;
		$m{"Render sys"} += $1 / $s if $top =~ / Render_Thread\(.\)[\d.]+\/[\d.]+\/([\d.]+)/;
		$m{"game-main sys"} += $1 / $s if $top =~ / game-main\(.\)[\d.]+\/[\d.]+\/([\d.]+)/;
	} elsif ($l =~ /^cpu prof: t ([\d.]+) s; per group samples and % title code \/ emulator \/ in the kernel \/ libraries:(.*?) \d+ threads attached/) {
		$last_t = $1;
		next if $1 < $t0 || $1 > $t1;
		my $groups = $2;
		while ($groups =~ /\G ?(\S+) (\d+): title ([\d.]+) host ([\d.]+) sys ([\d.]+) lib ([\d.]+) \(most (-?\d+)\);/g) {
			my ($g, $c) = ($1, $2);
			$p{$g}{n} += $c; $p{$g}{title} += $3 * $c / 100; $p{$g}{host} += $4 * $c / 100; $p{$g}{sys} += $5 * $c / 100; $p{$g}{lib} += $6 * $c / 100;
			$p{$g}{most}{$7}++ if $c > 0;
		}
	} elsif ($l =~ /^cpu prof top (host|title) /) {
		push @{$1 eq "host" ? \@host_dumps : \@title_dumps}, [$last_t // 0, $l];
	}
}
close $h;
die "no meter lines in the window\n" unless $nm_lines;
printf "window t %s-%s s: %d meter lines; box busy %.0f %%\n", $t0, $t1, $nm_lines, $m{busy} / $nm_lines;
printf "per second (ms): %s\n", join("; ", map { sprintf("%s %.0f", $_, $m{$_} / $nm_lines) } ("title c", "title w", "host c", "host w", "Hi c", "Hi w", "Lo c", "Lo w", "Bk c", "Bk w", "game-main c", "game-main w", "game-main sys", "Render c", "Render w", "Render sys", "direct submits", "direct ms (title-class threads)"));
for my $g ("game-main", "Render") {
	my $c = $m{"$g c"} / $nm_lines; my $w = $m{"$g w"} / $nm_lines;
	printf "%s: on a CPU %.0f, waiting %.0f, off a CPU %.0f ms/s\n", $g, $c, $w, 1000 - $c - $w;
}
for my $g (sort keys %p) {
	my $q = $p{$g};
	next unless $q->{n};
	printf "sampler %-9s %6d samples: title %4.1f %%, emulator %4.1f %%, syscall %4.1f %%, libraries %4.1f %% (most often library %s)\n", $g, $q->{n},
		100 * $q->{title} / $q->{n}, 100 * $q->{host} / $q->{n}, 100 * $q->{sys} / $q->{n}, 100 * $q->{lib} / $q->{n},
		join(",", map { "${_}x$q->{most}{$_}" } sort { $q->{most}{$b} <=> $q->{most}{$a} } keys %{$q->{most}});
}
# 3./4. the window's part of the cumulative histograms
sub parse_dump { my ($l) = @_; my %c; while ($l =~ / (\S+?):([0-9a-f]+)=(\d+)/g) { $c{"$1 $2"} = $3; } return \%c; }
for my $kind (["host", \@host_dumps, 16], ["title", \@title_dumps, 256]) {
	my ($what, $dumps, $mul) = @$kind;
	my ($before, $end);
	for my $d (@$dumps) { $before = $d if $d->[0] <= $t0; $end = $d if $d->[0] <= $t1 + 1; }
	next unless $before && $end && $end->[0] > $before->[0];
	my ($c0, $c1) = (parse_dump($before->[1]), parse_dump($end->[1]));
	my %by;
	for my $k (keys %$c1) {
		my ($g, $hex) = split / /, $k;
		next unless $g eq $want || $want eq "all";
		my $d = $c1->{$k} - ($c0->{$k} // 0);
		next if $d <= 0;
		my $key = $what eq "host" ? sym(hex($hex)) : sprintf("eboot.bin+0x%x", hex($hex) - 0x900000000);
		$by{$key} += $d;
	}
	my $tot = 0; $tot += $_ for values %by;
	printf "%s code of %s between the dumps at t %.0f and %.0f s (the top buckets only): %d samples\n", $what, $want, $before->[0], $end->[0], $tot;
	for my $k ((sort { $by{$b} <=> $by{$a} } keys %by)[0 .. 14]) { next unless defined $k; printf "  %6d %5.1f %%  %s\n", $by{$k}, 100 * $by{$k} / ($tot || 1), substr($k, 0, 110); }
}
