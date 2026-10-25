#!/usr/bin/perl
# Experiment 0318: in runtimeLinker.cpp, lines FIRST..LAST (the exception handler's terminal block), LOGF( and
# LOGF_COLOR(Log::Color::Red, become Bc5CrashLog(. usage: swap.pl FIRST LAST in out
use strict;
use warnings;
my ($first, $last, $in, $out) = @ARGV;
open(my $fi, '<:raw', $in) or die "open $in: $!";
open(my $fo, '>:raw', $out) or die "open $out: $!";
my ($n, $plain, $color) = (0, 0, 0);
while (my $line = <$fi>) {
    $n++;
    if ($n >= $first && $n <= $last) {
        $color += ($line =~ s/\bLOGF_COLOR\(Log::Color::Red,\s*/Bc5CrashLog(/g);
        $plain += ($line =~ s/\bLOGF\(/Bc5CrashLog(/g);
    }
    print $fo $line;
}
close($fo) or die "close $out: $!";
print "replaced LOGF( $plain, LOGF_COLOR( $color, in lines $first..$last of $n\n";
