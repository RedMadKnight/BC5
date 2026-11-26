# offline apply of a multi-file patchNNNN.py (the EDITS dict) to a copy of a tree: writes each patched file under
# <out root>/<rel>, checks each anchor count, prints brace/paren balance per file. usage: apply0327.pl patch.py <tree> <out>
use strict; use warnings;
my ($py, $tree, $out) = @ARGV;
open(my $ph, '<', $py) or die; my $src = do { local $/; <$ph> }; close $ph;
my $bs = chr(92);
my $total = 0;
while ($src =~ m{^    '([^']+)': \[\n(.*?)\n    \],}msg) {
	my ($rel, $body) = ($1, $2);
	open(my $ih, '<', "$tree/$rel") or die "$tree/$rel: $!"; binmode $ih; my $text = do { local $/; <$ih> }; close $ih;
	$text =~ s/\r\n/\n/g; my $orig = $text; my $k = 0;   # as python reads the file: universal newlines
	while ($body =~ m{\('''(.*?)''', (\d+), '''(.*?)'''\),}sg) {
		my ($anchor, $n, $new) = ($1, $2, $3); $k++;
		$anchor =~ s{\Q$bs$bs\E}{$bs}g; $new =~ s{\Q$bs$bs\E}{$bs}g;
		my $count = () = $text =~ m{\Q$anchor\E}g;
		die "$rel edit $k: anchor found $count times, expected $n\n" unless $count == $n;
		$text =~ s{\Q$anchor\E}{$new}g;
		print "$rel edit $k ok (", scalar(() = $new =~ /\n/g), " lines in place of ", scalar(() = $anchor =~ /\n/g), ")\n";
	}
	my %c; for my $ch ('{', '}', '(', ')') { $c{$ch} = () = $text =~ /\Q$ch\E/g; }
	my %o; for my $ch ('{', '}', '(', ')') { $o{$ch} = () = $orig =~ /\Q$ch\E/g; }
	printf "%s: braces %d/%d -> %d/%d, parens %d/%d -> %d/%d\n", $rel, $o{'{'}, $o{'}'}, $c{'{'}, $c{'}'}, $o{'('}, $o{')'}, $c{'('}, $c{')'};
	my $dst = "$out/$rel"; (my $dir = $dst) =~ s{/[^/]+$}{}; system("mkdir -p '$dir'");
	open(my $oh, '>', $dst) or die; binmode $oh; print $oh $text; close $oh;
	my $added = () = $text =~ /\n/g; my $before = () = $orig =~ /\n/g; $total += $added - $before;
}
print "$total lines added in all\n";
