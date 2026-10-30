#!/usr/bin/perl
# BC5 experiment 0380, test shortcut variant "rebase" (after exp 0379's mkplay0379t.pl). PREPARED, NOT INSTALLED: it
# waits for the maintainer's yes, relayed by the top session. The test launcher, RT on, derived from the integrated
# play-pkg.sh, differs from it in exactly these ways:
# - the private build ~/bc5-work/exp0380r/kyty_emulator: the shared normal build's objects relinked with exp 0380's
#   backend archive (link0380r.py; the unchanged relink reproduces the shared binary byte for byte);
# - BC5_DIRECT_REBASE_DISPATCH=1 (exp 0380 F558-F560: the dispatch's SET_BASE index 1 again right before each checked
#   DISPATCH_INDIRECT). Every other exp 0379/0380 switch is unset: FORCE_START, the zero guard, the y/z limit, the
#   zero skip and scan. One change against the maintainer's normal play;
# - one log and one mount log per start in ~/bc5-work/exp0380r/play/, the switch and the binary's md5 in the log's
#   first line.
# usage: perl mkplay0380r.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0380r/play-pkg-0380r.sh
use strict;
use warnings;
my ($in, $out) = @ARGV;
die "usage: mkplay0380r.pl <play-pkg.sh> <out>\n" unless defined $out;
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $mode = <<'EOS';
# exp 0380r (prepared; run only with the maintainer's yes): the rebase fix candidate alone
export BC5_DIRECT_REBASE_DISPATCH=1
unset BC5_DIRECT_FORCE_START_000 BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZERO_SKIP BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT
EOS
my @r = (
	["set -u\n",
	 "set -u\n" . q{unset BC5_LEAN BC5_LOGS  # exp 0380r: the normal build's journal and timeout probe} . "\n" .
	 q{R=~/bc5-work/exp0380r; RSTAMP=$(date +%Y%m%d-%H%M%S)  # exp 0380r} . "\n"],
	["EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n",
	 q{EMU=~/bc5-work/exp0380r/kyty_emulator  # exp 0380r: shared objects + exp 0380's backend archive (link0380r.py)} . "\n"],
	["LOG=~/bc5-work/play-pkg-last.log\n",
	 "mkdir -p ~/bc5-work/exp0380r/play\n" . q{LOG=~/bc5-work/exp0380r/play/play-$RSTAMP.log  # exp 0380r: one log per start} . "\n"],
	["MLOG=~/bc5-work/play-pkg-mount.log\n",
	 q{MLOG=~/bc5-work/exp0380r/play/mount-$RSTAMP.log  # exp 0380r: its own mount log} . "\n"],
	["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\n" . $mode],
	["  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n",
	 q{  echo "== exp 0380r: BC5_DIRECT_REBASE_DISPATCH=1; binary $(md5sum < "$EMU" | cut -c1-8)"} . "\n" .
	 "  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n"],
);
for my $p (@r) {
	my ($o, $n) = @$p;
	my $c = () = $t =~ /\Q$o\E/g;
	die "anchor found $c times, expected once: $o" unless $c == 1;
	$t =~ s/\Q$o\E/$n/;
}
die "the launcher has no one-ring line\n" unless $t =~ /^export BC5_DIRECT_COMPUTE_RING=-1 /m;
die "the launcher has no GPU check line\n" unless $t =~ /^export BC5_DIRECT_MEC_INDIRECT=1 BC5_DIRECT_GPU_CHECK=1 /m;
die "the private binary line is missing\n" unless $t =~ m{^EMU=~/bc5-work/exp0380r/kyty_emulator }m;
die "the rebase line is missing\n" unless $t =~ /^export BC5_DIRECT_REBASE_DISPATCH=1$/m;
die "a \$( was lost\n" unless $t =~ /RSTAMP=\$\(date \+%Y%m%d-%H%M%S\)/;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
