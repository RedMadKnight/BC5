use strict; use warnings;
# s6n0343.sh from exp 0346's s6n0346.sh: the experiment directory, the switches (both), and a 0343 result block
my ($in, $out) = @ARGV;
open(my $h, '<', $in) or die; binmode $h; local $/; my $s = <$h>; close $h;
sub rep { my ($old, $new, $what) = @_; my $n = () = $s =~ /\Q$old\E/g; die "$what: $n occurrences" unless $n >= 1; $s =~ s/\Q$old\E/$new/g; }
rep('exp0346', 'exp0343', 'dir');
rep('play-pkg-0346', 'play-pkg-0343', 'launcher');
rep('BC5_0346_SWITCHES-BC5_DIRECT_HOST_INDIRECT=learn:1100000000', 'BC5_0343_SWITCHES-BC5_DIRECT_HOST_INDIRECT=learn:1100000000 BC5_DIRECT_SOFT_WAIT_MS=8', 'switches');
rep('bvh exp 0346 |', 'bvh exp 0343 |', 'lock');
rep('s6n0346.sh', 's6n0343.sh', 'usage');
rep('build0346.sh', 'build0343.sh', 'build');
rep('(one ring, both guards, $SWITCHES)', '(one ring, both guards, 0343 + 0346: $SWITCHES)', 'lockline');
my $anchor = 'sudo -n dmesg 2> /dev/null | tail -n +"$((N + 1))" | grep -i "amdgpu\|gpu\|oom\|hung\|SQC" > "$R/$TAG-dmesg-after.txt"';
my $block = <<'B';
# experiment 0343: the soft CP's journal lines (polls over 50 ms or at the deadline, posts over 100 ms) and the profile's counters
if [ -f "$J" ] && [ "$(stat -c %Y "$J")" -ge "$T0" ]; then
  { echo "soft-cp wait lines: $(nice -n 19 grep -a -c '^soft-cp wait:' "$J") (timed out: $(nice -n 19 grep -a -c '^soft-cp wait:.*TIMED OUT' "$J")); slow post lines: $(nice -n 19 grep -a -c '^slow post:' "$J")"
    nice -n 19 grep -a '^soft-cp wait:\|^slow post:' "$J" | head -40
    echo "last frame profile: $(nice -n 19 grep -a '^frame profile' "$J" | tail -1 | grep -o 'waits polled[^;]*')"
    nice -n 19 grep -a '^frame profile' "$J" | grep -o 'waits polled [0-9]* ([0-9.]* ms, [0-9]* timed out)' | awk '{p+=$3; gsub(/\(/,"",$4); ms+=$4; t+=$6; n++; if ($3+0>mp) mp=$3+0; if ($4+0>mm) mm=$4+0} END {printf "profile lines %d: waits polled total %d (%.1f ms), timed out %d; max per frame %d polls / %.1f ms\n", n, p, ms, t, mp, mm}'; } > "$R/$TAG-0343.txt"
else echo "no journal" > "$R/$TAG-0343.txt"; fi
B
my $n = () = $s =~ /\Q$anchor\E/g; die "dmesg anchor: $n" unless $n == 1;
$s =~ s/\Q$anchor\E/$block$anchor/;
rep('cat "$R/$TAG-summary.txt" "$R/$TAG-verdict.txt"', 'cat "$R/$TAG-summary.txt" "$R/$TAG-0343.txt" "$R/$TAG-verdict.txt"', 'cat');
open(my $o, '>', $out) or die; binmode $o; print $o $s; close $o; print "$out written\n";
