use strict; use warnings;
# s6n0352.sh from exp 0350's s6n0350.sh (the integrated launcher's S6N run): the private build, this experiment's
# directory, switches and lock line, the lock left as an empty file, a frame-profile metrics block (exp 0352)
my ($in, $out) = @ARGV;
open(my $h, '<', $in) or die; binmode $h; local $/; my $s = <$h>; close $h;
sub rep { my ($old, $new, $what, $min) = @_; my $n = () = $s =~ /\Q$old\E/g; die "$what: $n occurrences" unless $n >= ($min // 1); $s =~ s/\Q$old\E/$new/g; }
rep('BIN=$W/kytyplus-build/src/kyty_emulator; WANT=$(sed -n \'s/^normal=\([0-9a-f]*\) .*/\1/p\' "$E/integration/new-md5.env" 2> /dev/null)   # int0350.sh writes it',
    'BIN=$E/kyty_emulator; WANT=$(cat "$E/binary.md5" 2> /dev/null)   # build0352.sh writes it', 'bin');
rep('"$E/integration/new-md5.env"', '"$W/exp0350/integration/new-md5.env"', 'md5 env');
rep('exp0350', 'exp0352', 'dir');
rep('play-pkg-0350', 'play-pkg-0352', 'launcher');
rep('BC5_0350_SWITCHES', 'BC5_0352_SWITCHES', 'switches');
rep('BC5_0350_INPUT_CONFIG', 'BC5_0352_INPUT_CONFIG', 'input');
rep('exp 0350 | s6n run', 'bvh exp 0352 | s6n run', 'lock line', 3);
rep('[ -s "$LOCK" ] && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }', '[ -s "$LOCK" ] && ! grep -q "^bvh exp 0352 |" "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }', 'lock check');
rep('rm -f "$LOCK"', ': > "$LOCK"', 'lock release', 2);
rep('(int0350.sh first)', '(build0352.sh first)', 'hint');
rep('the integrated shared normal build $WANT', 'the private build $WANT (exp 0352: the batched CP check on main 9bd60be)', 'lock text');
rep('experiment 0346 at close\|experiment 0349\|cs refused', 'experiment 0346 at close\|experiment 0349\|experiment 0352\|cs refused', 'grep');
my $anchor = '  echo "journal $J $(stat -c \'%y %s\' "$J")" > "$R/$TAG-journal.txt"' . "\n";
my $block = '  grep -a "^frame profile" "$J" | awk \'{g=0;fl=0;p=0;s=0; for(i=1;i<=NF;i++){ if($i=="busy") g=$(i+1); if($i=="filter") fl=$(i+1); if($i=="prepare" && $(i+1)!="=") p=$(i+1); if($i=="ms" && $(i+1)=="since") s=$(i-1)} G+=g; FL+=fl; P+=p; S+=s; n++} END {if (n>0) printf "exp 0352 frame profiles %d: per frame GPU busy %.2f ms, host prepare %.2f ms (filter %.2f), %.1f ms between flips\n", n, G/n, P/n, FL/n, S/n}\' > "$R/$TAG-0352.txt"' . "\n";
my $n = () = $s =~ /\Q$anchor\E/g; die "journal anchor: $n" unless $n == 1;
$s =~ s/\Q$anchor\E/$anchor$block/;
open(my $o, '>', $out) or die; binmode $o; print $o $s; close $o; print "$out written\n";
