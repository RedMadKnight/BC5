#!/usr/bin/perl
# BC5 experiment 0380, test shortcut "BC5 emulator (test 0380 fix + 0379)" (exp 0379's mkplay0379t.pl; the maintainer's
# yes "Tak, oba", 2026-10-29). The test launcher, RT on, derived from the integrated play-pkg.sh, differs from it in:
# - the private build ~/bc5-work/exp0380f/kyty_emulator: the shared normal build's objects with exp 0379t's private
#   bc5LleAgc.cpp object (the zero skip) and exp 0380's archive 86534bb1 (the rebase fix), by link0380f.py;
# - BC5_DIRECT_REBASE_DISPATCH=1 and BC5_DIRECT_FORCE_START_000=1 (exp 0380), the zero guard and the y/z limit off;
# - exp 0379's zero skip forced to SKIP on one fixed list (the maintainer's play list of 2026-10-29 12:00). There is no
#   scan and no list rotation, and the launcher refuses to start without that list;
# - one log and one mount log per start in ~/bc5-work/exp0380f/play/. The log's first line names the mode, both
#   switches and the binary's md5;
# - a memory sample once a minute (exp 0379t's play-sample0379t.sh, copied beside it), stopped by the launcher's exit.
# usage: perl mkplay0380f.pl ~/bc5-work/play-pkg.sh ~/bc5-work/exp0380f/play-pkg-0380f.sh <zero list>
use strict;
use warnings;
my ($in, $out, $list) = @ARGV;
die "usage: mkplay0380f.pl <play-pkg.sh> <out> <zero list>\n" unless defined $list && $list =~ m{^/[^ '"\$]+$};
open(my $h, "<", $in) or die "$in: $!\n";
my $t = do { local $/; <$h> };
close $h;
my $mode = <<"EOS";
# exp 0380f (the maintainer's yes "Tak, oba", 2026-10-29): exp 0380's rebase fix with FORCE_START_AT_000, and exp 0379's
# zero skip forced to SKIP on his play list (no scan); the zero guard and the y/z limit off.
export BC5_DIRECT_REBASE_DISPATCH=1 BC5_DIRECT_FORCE_START_000=1
unset BC5_DIRECT_GPU_CHECK_ZERO BC5_DIRECT_GPU_CHECK_YZ BC5_DIRECT_ZEROSCAN_AT BC5_DIRECT_ZEROSCAN_OUT
ZLIST=$list
[ -r "\$ZLIST" ] || { say "No zero list at \$ZLIST"; exit 1; }
export BC5_DIRECT_ZERO_SKIP=\$ZLIST
ZMODE="SKIP \$ZLIST"
EOS
my @r = (
	["set -u\n",
	 "set -u\n" . q{unset BC5_LEAN BC5_LOGS  # exp 0380f: the normal build's journal holds the zero and timeout lines} . "\n" .
	 q{Z=~/bc5-work/exp0380f; ZSTAMP=$(date +%Y%m%d-%H%M%S)  # exp 0380f} . "\n"],
	["EMU=~/bc5-work/kytyplus-build/src/kyty_emulator\n",
	 q{EMU=~/bc5-work/exp0380f/kyty_emulator  # exp 0380f: shared objects + exp 0379t's zero-skip unit + exp 0380's archive (link0380f.py)} . "\n"],
	["LOG=~/bc5-work/play-pkg-last.log\n",
	 "mkdir -p ~/bc5-work/exp0380f/play\n" . q{LOG=~/bc5-work/exp0380f/play/play-$ZSTAMP.log  # exp 0380f: one log per start} . "\n"],
	["MLOG=~/bc5-work/play-pkg-mount.log\n",
	 q{MLOG=~/bc5-work/exp0380f/play/mount-$ZSTAMP.log  # exp 0380f: its own mount log} . "\n"],
	["done < \"\$ENVF\"\n", "done < \"\$ENVF\"\n" . $mode],
	["cleanup() {\n  [ -n \"\$MP\" ] || return 0\n",
	 "cleanup() {\n  [ -n \"\${ZSP:-}\" ] && kill \"\$ZSP\" 2> /dev/null  # exp 0380f: the memory sampler\n  [ -n \"\$MP\" ] || return 0\n"],
	["trap cleanup EXIT\n",
	 "trap cleanup EXIT\n" . q{bash "$Z/play-sample0379t.sh" $$ "$Z/play/mem-$ZSTAMP.txt" < /dev/null > /dev/null 2>&1 & ZSP=$!  # exp 0380f: once a minute} . "\n"],
	["  echo \"== \$(date '+%F %T') emulator \$(stat -c '%y' \"\$EMU\" | cut -c1-19)\"\n",
	 q{  echo "== exp 0380f mode: $ZMODE; BC5_DIRECT_REBASE_DISPATCH=1; BC5_DIRECT_FORCE_START_000=1; binary $(md5sum < "$EMU" | cut -c1-8)"} . "\n" .
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
die "the private binary line is missing\n" unless $t =~ m{^EMU=~/bc5-work/exp0380f/kyty_emulator }m;
die "the switch line is missing\n" unless $t =~ /^export BC5_DIRECT_REBASE_DISPATCH=1 BC5_DIRECT_FORCE_START_000=1$/m;
die "the list line is missing\n" unless $t =~ /^ZLIST=\Q$list\E$/m;
die "a \$( was lost\n" unless $t =~ /ZSTAMP=\$\(date \+%Y%m%d-%H%M%S\)/;
# the mode line must be the log's first line: it is the first echo of the block that writes "$LOG"
my $pos_mode = index($t, q{echo "== exp 0380f mode:});
my $pos_log = index($t, q{} . '} > "$LOG"');
die "the mode line is not inside the block that writes the log\n" unless $pos_mode > 0 && $pos_log > $pos_mode;
open(my $w, ">", $out) or die "$out: $!\n";
print $w $t;
close $w;
chmod 0755, $out;
print "$out written\n";
