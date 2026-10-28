use strict; use warnings;
# s6n0349.sh from exp 0343's s6n0343.sh: the experiment directory, the switches (0343 + 0346 + the 0349 cut forced at
# 65,536 dwords so the bench exercises it), the lock kept as an empty file, and a 0349 result block
my ($in, $out) = @ARGV;
open(my $h, '<', $in) or die; binmode $h; local $/; my $s = <$h>; close $h;
sub rep { my ($old, $new, $what) = @_; my $n = () = $s =~ /\Q$old\E/g; die "$what: $n occurrences" unless $n >= 1; $s =~ s/\Q$old\E/$new/g; }
rep('exp0343', 'exp0349', 'dir');
rep('play-pkg-0343', 'play-pkg-0349', 'launcher');
rep('BC5_0343_SWITCHES-BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8', 'BC5_0349_SWITCHES-BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8 BC5_DIRECT_IB_MAX_DW=65536', 'switches');
rep('bvh exp 0343 |', 'bvh exp 0349 |', 'lock');
rep('s6n0343.sh', 's6n0349.sh', 'usage');
rep('build0343.sh', 'build0349.sh', 'build');
rep('0343 + 0346: $SWITCHES', '0343 + 0346 + 0349 (the IB cut forced at 65,536 dwords): $SWITCHES', 'lockline');
rep('rm -f "$LOCK"', ': > "$LOCK"', 'lock release');
my $anchor = '# experiment 0343: the soft CP';
my $block = <<'B';
# experiment 0349: the IB cut (jobs over BC5_DIRECT_IB_MAX_DW cut into up to four IBs) and any refused submit
{ echo "0349 switch: $(grep -a -c 'experiment 0349: a job' "$R/$TAG-play.log"); split lines: $(grep -a -c 'experiment 0349 split' "$R/$TAG-play.log"); cannot-cut lines: $(grep -a -c 'cannot be cut' "$R/$TAG-play.log"); cs refused lines: $(grep -a -c 'cs refused rc' "$R/$TAG-play.log")"
  grep -a 'experiment 0349: a job\|experiment 0349 split\|cannot be cut\|cs refused rc' "$R/$TAG-play.log" | tail -6 | cut -c1-400
  echo "journal: rc -22 submits $(grep -a -c 'rc -22' "$J" 2> /dev/null), dcbs over 65,536 dwords $(grep -a '^submit #.* dcb ' "$J" 2> /dev/null | awk '$4+0 > 65536' | wc -l), largest dcb $(grep -a '^submit #.* dcb ' "$J" 2> /dev/null | awk '{print $4}' | sort -n | tail -1) dwords"; } > "$R/$TAG-0349.txt"
B
my $n = () = $s =~ /\Q$anchor\E/g; die "0343 anchor: $n" unless $n == 1;
$s =~ s/\Q$anchor\E/$block$anchor/;
rep('cat "$R/$TAG-summary.txt" "$R/$TAG-0343.txt" "$R/$TAG-verdict.txt"', 'cat "$R/$TAG-summary.txt" "$R/$TAG-0343.txt" "$R/$TAG-0349.txt" "$R/$TAG-verdict.txt"', 'cat');
open(my $o, '>', $out) or die; binmode $o; print $o $s; close $o; print "$out written\n";
