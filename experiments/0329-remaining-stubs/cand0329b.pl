# exp 0329, second pass: the method token of every known libSceNpCppWebApi mangled name (the last lower-case
# <len><name> token followed by 'E', i.e. the member whose parameter list follows) swapped for every method token seen
# in the whole export set; the NIDs checked against the 11. usage: cand0329b.pl missing11.txt cand-mangled.txt ...
use strict; use warnings;
use Digest::SHA qw(sha1);
use MIME::Base64 qw(encode_base64);
my ($nidf, @namefs) = @ARGV;
my $salt = pack('H*', '518d64a635ded8c1e6b039b1c3e55230');
sub nid { my ($name) = @_; my $h = sha1($name . $salt); my $b = encode_base64(reverse(substr($h, 0, 8)), ''); $b =~ s/=+$//; $b =~ tr{/}{-}; return $b; }
my %want; open(my $nh, '<', $nidf) or die; while (<$nh>) { chomp; $want{$_} = 1 if length; } close $nh;
my %names;
for my $f (@namefs) { open(my $h, '<', $f) or die; while (<$h>) { chomp; s/\r//; $names{$_} = 1 if /^_Z.*CppWebApi/; } close $h; }
my @names = sort keys %names;
# tokens: every <len><identifier of exactly len chars>; the method = the last lower-case one followed by 'E'
sub method_of {
	my ($n) = @_; my $best;
	while ($n =~ /(\d+)/g) {
		my $len = $1; my $at = pos($n); my $id = substr($n, $at, $len);
		next unless length($id) == $len && $id =~ /^[A-Za-z_][A-Za-z0-9_]*$/;
		my $after = substr($n, $at + $len, 1);
		$best = [$at - length($len), $len, $id] if $id =~ /^[a-z]/ && $after eq 'E' && $id ne 'sce';
	}
	return $best;
}
my %meth; my @with;
for my $n (@names) { my $m = method_of($n); next unless $m; $meth{$m->[1] . $m->[2]} = 1; push @with, [$n, $m]; }
my @methods = sort keys %meth;
print scalar(@names), " names, ", scalar(@with), " with a method token, ", scalar(@methods), " distinct methods\n";
my $tried = 0; my %found;
for my $w (@with) {
	my ($n, $m) = @$w; my ($off, $len, $id) = @$m;
	my $pre = substr($n, 0, $off); my $post = substr($n, $off + length($len) + $len);
	for my $t (@methods) {
		next if $t eq $len . $id;
		my $c = $pre . $t . $post; my $x = nid($c); $tried++;
		if ($want{$x} && !$found{"$x $c"}) { $found{"$x $c"} = 1; print "MATCHM $x $c  (from $n)\n"; }
	}
}
print "tried $tried candidates, ", scalar(keys %found), " matches\n";
