#!/usr/bin/perl
# BC5 experiment 0323: the three second-title launchers get the ring ordering (exps 0320-0322, F385) and run the BVH
# compaction with RT on (exp 0306/0321's setting). Literal, anchored edits with \Q, each anchor required exactly once:
#   - after `export BC5_DIRECT_COMPUTE_RING=0 BC5_DIRECT_CROSS_RING_WAITS=all`: `export BC5_DIRECT_RING_DEPS=dcb`
#     (every GFX-ring job starts after the compute rings' last jobs: exp 0129's kernel CS dependency; 0321: 2 x 600 s
#     clean where the split hung 11/11; cost about the one-ring flip rate, accepted by the maintainer on 2026-10-25);
#   - the default skip list loses 909974400 (the compaction): play-pkg.sh `${BC5_DIRECT_SKIP_PGM:-909974400}` ->
#     `${BC5_DIRECT_SKIP_PGM:-0}` (0 = nothing skipped, as the exp 0306+ chains ran), play-pkg-log.sh and
#     play-pkg-quiet.sh `${BC5_DIRECT_SKIP_PGM:-11d049aa00,11d04a6000,909974400}` -> `${...:-11d049aa00,11d04a6000}`.
#   RT off still drops the build family through KYTY_BC5_RT_BUILD_PGM (F343), compaction included.
# Each file: refused if it already has a BC5_DIRECT_RING_DEPS line; backed up to <backup dir>/<name>.before-0323 with
# its md5; the new md5 printed. Nothing else is touched.
# usage: launchers0323.pl <backup dir> <launcher>...   (on the box, by the top session)
use strict; use warnings;
my ($bak, @files) = @ARGV;
die "usage: launchers0323.pl <backup dir> <launcher>...\n" unless defined $bak && @files;
-d $bak or die "no backup dir $bak\n";
sub md5of { my ($t) = @_; require Digest::MD5; return substr(Digest::MD5::md5_hex($t), 0, 8); }
sub rep { my ($t, $old, $new, $what, $f) = @_; my $n = () = $$t =~ /\Q$old\E/g; die "$f: $what: anchor found $n times, expected 1\n" unless $n == 1; $$t =~ s/\Q$old\E/$new/; }
my $ring_anchor = "export BC5_DIRECT_COMPUTE_RING=0 BC5_DIRECT_CROSS_RING_WAITS=all\n";
my $ring_new    = $ring_anchor . "export BC5_DIRECT_RING_DEPS=dcb  # exp 0323 (F385): every GFX-ring job starts after the compute rings' last jobs - the BVH build's two-ring split hung 11/11 at ~2 min with RT on (exps 0320-0322); cost about the one-ring flip rate\n";
for my $f (@files) {
	open(my $h, '<', $f) or die "$f: $!\n"; my $t = do { local $/; <$h> }; close $h;
	my $before = md5of($t);
	die "$f: already has a BC5_DIRECT_RING_DEPS line (md5 $before): nothing done\n" if $t =~ /^export BC5_DIRECT_RING_DEPS=/m;
	my ($name) = $f =~ m{([^/]+)$};
	open(my $b, '>', "$bak/$name.before-0323") or die "$bak/$name.before-0323: $!\n"; print $b $t; close $b;
	rep(\$t, $ring_anchor, $ring_new, 'ring line', $f);
	if ($t =~ /\$\{BC5_DIRECT_SKIP_PGM:-909974400\}/) {
		rep(\$t, 'export BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-909974400}', 'export BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-0}  # exp 0323: the compaction 909974400 runs with RT on (exp 0306+); 0 = nothing skipped', 'skip default', $f);
	} elsif ($t =~ /\$\{BC5_DIRECT_SKIP_PGM:-11d049aa00,11d04a6000,909974400\}/) {
		rep(\$t, 'export BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-11d049aa00,11d04a6000,909974400}', 'export BC5_DIRECT_SKIP_PGM=${BC5_DIRECT_SKIP_PGM:-11d049aa00,11d04a6000}  # exp 0323: the compaction 909974400 runs with RT on (exp 0306+)', 'skip default', $f);
	} else {
		die "$f: no known BC5_DIRECT_SKIP_PGM default line: nothing written\n";
	}
	open(my $o, '>', $f) or die "$f: $!\n"; print $o $t; close $o;
	printf "%s: md5 %s -> %s (backup %s/%s.before-0323)\n", $f, $before, md5of($t), $bak, $name;
}
