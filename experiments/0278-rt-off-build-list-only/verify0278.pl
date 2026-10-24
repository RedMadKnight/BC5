#!/usr/bin/perl
# Offline check of patch0278.py's anchors against the committed patch 0001 (each file reconstructed
# from its '+' and ' ' lines; the box's shared tree may differ — patch0278.py checks again there).
# usage: verify0278.pl <backend/kytyplus-patches/0001-bc5-lle-agc.patch> <patch0278.py>
use strict;
use warnings;
my ($patch, $py) = @ARGV;
open(my $fh, '<', $patch) or die "open $patch: $!";
my (%files, $cur);
while (my $line = <$fh>) {
    if ($line =~ m{^diff --git a/(\S+)}) { $cur = $1; $files{$cur} = ''; next; }
    next unless defined $cur;
    next if $line =~ m{^\+\+\+ } or $line =~ m{^--- };
    if ($line =~ m{^[+ ]}) { substr($line, 0, 1) = ''; $files{$cur} .= $line; }
}
close $fh;
open(my $ph, '<', $py) or die "open $py: $!";
my $src = do { local $/; <$ph> };
close $ph;
my $ok = 1;
my $bs = chr(92);
while ($src =~ m{^    '([^']+)': \[\n(.*?)\n    \],}msg) {
    my ($rel, $body) = ($1, $2);
    die "no $rel in the patch" unless exists $files{$rel};
    my $text = $files{$rel};
    while ($body =~ m{\('''(.*?)''', (\d+), '''}sg) {
        my ($anchor, $n) = ($1, $2);
        $anchor =~ s{\Q$bs$bs\E}{$bs}g;    # Python's '\\' is one backslash; the anchors use no other escape
        my $count = 0;
        my $pos   = 0;
        while (($pos = index($text, $anchor, $pos)) >= 0) { $count++; $pos += length($anchor); }
        my @lines = split("\n", $anchor);
        my $first = substr($lines[0], 0, 45);
        printf "%-72s expected %d found %d%s\n", "$rel: $first", $n, $count, ($count == $n ? '' : '   <-- MISMATCH');
        $ok = 0 if $count != $n;
    }
}
print $ok ? "all anchors match patch 0001\n" : "anchor mismatch\n";
exit($ok ? 0 : 1);
