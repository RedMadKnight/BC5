#!/usr/bin/perl
# BC5 experiment 0325 (the maintainer, 2026-10-25: "Puść najpierw 10-minutowy test RT off bez porządkowania kolejek;
# jeśli to ono kosztuje, włącz je tylko przy RT"): the second title's launchers set BC5_DIRECT_RING_DEPS=dcb only
# when the title starts with RT on. RT at start is KYTY_BC5_RT when set (0 = off), else the saved menu setting
# RayTracing.PPSA03671 in $KYTY_BC5_INPUT_CONFIG (no entry = on, the default). Literal edit with \Q: exp 0323's
# ring line must be there exactly once; a file already carrying "exp 0325" is refused; backups <name>.before-0325.
# usage: gate0325.pl <backup dir> <launcher>...   (on the box, by the top session)
use strict; use warnings;
use Digest::MD5 qw(md5_hex);
my ($bak, @files) = @ARGV;
die "usage: gate0325.pl <backup dir> <launcher>...\n" unless defined $bak && @files;
-d $bak or die "no backup dir $bak\n";
my $old = "export BC5_DIRECT_RING_DEPS=dcb  # exp 0323 (F385): every GFX-ring job starts after the compute rings' last jobs"
        . " - the BVH build's two-ring split hung 11/11 at ~2 min with RT on (exps 0320-0322); cost about the one-ring flip rate\n";
my $new = "# exp 0325 (the maintainer: \"jeśli to ono kosztuje, włącz je tylko przy RT\"): the ring ordering only when the title\n"
        . "# starts with RT on: KYTY_BC5_RT if set (0 = off), else the saved menu setting RayTracing.PPSA03671 (no entry = on).\n"
        . "# RT switched on in the menu later in the same session runs without the ordering until the next start from the\n"
        . "# shortcut (the refusal keeps such a hang recoverable, F356).\n"
        . "BC5_RT_AT_START=\${KYTY_BC5_RT:-}\n"
        . "if [ -z \"\$BC5_RT_AT_START\" ]; then\n"
        . "  if grep -q '^RayTracing\\.PPSA03671=off' \"\${KYTY_BC5_INPUT_CONFIG:-/dev/null}\" 2> /dev/null; then BC5_RT_AT_START=0; else BC5_RT_AT_START=1; fi\n"
        . "fi\n"
        . "[ \"\$BC5_RT_AT_START\" = 0 ] || export BC5_DIRECT_RING_DEPS=dcb  # exp 0323 (F385): every GFX-ring job starts after the compute rings' last jobs\n";
for my $f (@files) {
	open(my $h, '<', $f) or die "$f: $!\n"; my $t = do { local $/; <$h> }; close $h;
	my $before = substr(md5_hex($t), 0, 8);
	die "$f: already carries exp 0325 (md5 $before): nothing done\n" if $t =~ /exp 0325/;
	my $n = () = $t =~ /\Q$old\E/g;
	die "$f: exp 0323's ring line found $n times, expected 1: nothing done\n" unless $n == 1;
	(my $out = $t) =~ s/\Q$old\E/$new/;
	my ($name) = $f =~ m{([^/]+)$};
	open(my $b, '>', "$bak/$name.before-0325") or die "$bak/$name.before-0325: $!\n"; print $b $t; close $b;
	open(my $o, '>', $f) or die "$f: $!\n"; print $o $out; close $o;
	printf "%s: md5 %s -> %s (backup %s/%s.before-0325)\n", $f, $before, substr(md5_hex($out), 0, 8), $bak, $name;
}
