# exp 0329: candidate mangled names for the 11 unnamed NpCppWebApi NIDs, by substituting class tokens: every known
# mangled name of libSceNpCppWebApi (AnyPS5's exports + the title's resolved ones) that carries a class token of
# SessionManager::V1, TitleCloudStorage::V1 or Common is re-issued with every other class token of the same family;
# their NIDs are checked against the 11. usage: cand0329.pl missing11.txt cand-mangled.txt cppwebapi-mangled.txt
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
print scalar(@names), " names\n";
# the class tokens per family: "<len><Name>" right after the family's namespace token
my %fam = ('14SessionManager2V1' => {}, '17TitleCloudStorage2V1' => {}, '6Common' => {});
for my $n (@names) {
	for my $f (keys %fam) {
		while ($n =~ /\Q$f\E(\d+)([A-Za-z_][A-Za-z0-9_]*)/g) {
			my ($len, $rest) = ($1, $2);
			next if $len > length($rest);
			$fam{$f}{$len . substr($rest, 0, $len)} = 1;
		}
	}
}
for my $f (keys %fam) { print "$f: ", scalar(keys %{$fam{$f}}), " class tokens\n"; }
# direct check first
for my $n (@names) { my $x = nid($n); print "DIRECT $x $n\n" if $want{$x}; }
my $tried = 0; my %found;
for my $f (keys %fam) {
	my @tokens = keys %{$fam{$f}};
	for my $n (@names) {
		next unless index($n, $f) >= 0;
		my %in; while ($n =~ /\Q$f\E(\d+)([A-Za-z_][A-Za-z0-9_]*)/g) { my ($len, $rest) = ($1, $2); next if $len > length($rest); $in{$len . substr($rest, 0, $len)} = 1; }
		for my $t (keys %in) {
			for my $t2 (@tokens) {
				next if $t2 eq $t;
				my $c = $n; $c =~ s/\Q$f$t\E/$f$t2/g;
				my $x = nid($c); $tried++;
				if ($want{$x} && !$found{"$x $c"}) { $found{"$x $c"} = 1; print "MATCH $x $c  (from $n)\n"; }
			}
		}
	}
}
print "tried $tried candidates, ", scalar(keys %found), " matches\n";
