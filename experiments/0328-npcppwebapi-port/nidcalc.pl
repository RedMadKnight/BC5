# PS5 NID calculator: NID = base64(reverse(first 8 bytes of SHA1(name . salt))) with the "+-" alphabet, no padding.
# usage: nidcalc.pl <nid list file> <candidate names file>   -> prints "NID name" for every match
use strict; use warnings;
use Digest::SHA qw(sha1);
use MIME::Base64 qw(encode_base64);
my ($nidf, $namef) = @ARGV;
my $salt = pack('H*', '518d64a635ded8c1e6b039b1c3e55230');
sub nid { my ($name) = @_; my $h = sha1($name . $salt); my $b = encode_base64(reverse(substr($h, 0, 8)), ''); $b =~ s/=+$//; $b =~ tr{/}{-}; return $b; }
# self-check on known pairs
my %known = ('sceKernelSyncOnAddressWait8' => 'dFym5b41JLU', 'getrusage' => 'hHlZQUnlxSM', 'sceKernelTruncate' => 'WlyEA-sLDf0', 'fsync' => 'juWbTNM+8hw');
for my $n (sort keys %known) { my $c = nid($n); die "self-check failed: $n -> $c, expected $known{$n}\n" unless $c eq $known{$n}; }
print STDERR "self-check ok (4 known pairs)\n";
open(my $nh, '<', $nidf) or die; my %want; while (<$nh>) { chomp; $want{(split)[0]} = 1 if length; } close $nh;
open(my $ch, '<', $namef) or die; my %seen; my $n = 0;
while (my $name = <$ch>) { chomp $name; next unless length $name; next if $seen{$name}++; $n++; my $c = nid($name); print "$c $name\n" if $want{$c}; }
print STDERR "$n candidate names hashed\n";
