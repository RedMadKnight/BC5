#!/usr/bin/perl
# BC5 experiment 0324 (the maintainer, 2026-10-25: "pozbądź się wszystkich dzienników … abym na wersji lean grał
# naprawdę bez żadnego logowania … uwzględnij też skrypty na maszynie, aby nic nie pisały - możesz zrobić im
# włączenie na parametr"): with BC5_LEAN=1 the launchers write no log at all unless BC5_LOGS=1.
#   play-any.sh, play-pkg.sh, play-astro.sh: the play log, the pad-volume lines, the menu and directory logs and the
#     mount logs go to /dev/null when BC5_LEAN=1 and BC5_LOGS is not 1 (the lean binary itself has no journal,
#     counters, recorder or samplers: exp 0177). The normal shortcut is unchanged.
#   compress-old-captures.sh: writes nothing while the box is busy (it already did no work then).
# Literal edits with \Q, each anchor counted; a file that already carries "exp 0324" is refused; backups go to
# <backup dir>/<name>.before-0324 and every md5 is printed.
# usage: quiet0324.pl <backup dir> <file>...   (on the box, by the top session; the file names decide the edits)
use strict; use warnings;
use Digest::MD5 qw(md5_hex);
my ($bak, @files) = @ARGV;
die "usage: quiet0324.pl <backup dir> <file>...\n" unless defined $bak && @files;
-d $bak or die "no backup dir $bak\n";

sub rep {
	my ($t, $old, $new, $want, $what, $f) = @_;
	my $n = () = $$t =~ /\Q$old\E/g;
	die "$f: $what: found $n times, expected $want\n" unless $n == $want;
	$$t =~ s/\Q$old\E/$new/g;
}

my $note = "# 2026-10-25 (exp 0324, the maintainer): with BC5_LEAN=1 this script writes no log at all; BC5_LOGS=1 keeps\n"
         . "# its logs. The normal shortcut logs as before.\n";

my %edit = (
	'play-any.sh' => sub {
		my ($t, $f) = @_;
		my $lean = "  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-menu-lean-last.log\nfi\n";
		rep($t, $lean, $lean . $note
			. "DIRLOG=~/bc5-work/play-dir-last.log\n"
			. "if [ \"\${BC5_LEAN:-0}\" = 1 ] && [ \"\${BC5_LOGS:-0}\" != 1 ]; then LOG=/dev/null DIRLOG=/dev/null; fi\n",
			1, 'lean block', $f);
		rep($t, '>> ~/bc5-work/play-dir-last.log 2>&1', '>> "$DIRLOG" 2>&1', 1, 'directory log', $f);
	},
	'play-pkg.sh' => sub {
		my ($t, $f) = @_;
		my $lean = "  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-pkg-lean-last.log\nfi\n";
		rep($t, $lean, $lean . $note
			. "MLOG=~/bc5-work/play-pkg-mount.log\n"
			. "if [ \"\${BC5_LEAN:-0}\" = 1 ] && [ \"\${BC5_LOGS:-0}\" != 1 ]; then LOG=/dev/null MLOG=/dev/null; fi\n",
			1, 'lean block', $f);
		rep($t, '(see ~/bc5-work/play-pkg-mount.log)', '(see $MLOG; with BC5_LEAN=1 run with BC5_LOGS=1 to keep it)', 1, 'mount message', $f);
		rep($t, '> ~/bc5-work/play-pkg-mount.log 2>&1 &', '> "$MLOG" 2>&1 &', 1, 'mount log', $f);
		rep($t, '2>> ~/bc5-work/play-pkg-mount.log', '2>> "$MLOG"', 2, 'unmount stderr', $f);
		rep($t, '>> ~/bc5-work/play-pkg-mount.log', '>> "$MLOG"', 2, 'unmount lines', $f);
	},
	'play-astro.sh' => sub {
		my ($t, $f) = @_;
		my $lean = "  EMU=~/bc5-work/kytyplus-build-lean/src/kyty_emulator LOG=~/bc5-work/play-lean-last.log\nfi\n";
		rep($t, $lean, $lean . $note
			. "ALOG=~/bc5-work/play-mount.log MLOG=~/bc5-work/play-pkg-mount.log\n"
			. "if [ \"\${BC5_LEAN:-0}\" = 1 ] && [ \"\${BC5_LOGS:-0}\" != 1 ]; then LOG=/dev/null ALOG=/dev/null MLOG=/dev/null; fi\n",
			1, 'lean block', $f);
		rep($t, '(see ~/bc5-work/play-mount.log)', '(see $ALOG; with BC5_LEAN=1 run with BC5_LOGS=1 to keep it)', 1, 'mount message', $f);
		rep($t, '> ~/bc5-work/play-mount.log 2>&1 &', '> "$ALOG" 2>&1 &', 1, 'mount log', $f);
		rep($t, '2>> ~/bc5-work/play-pkg-mount.log', '2>> "$MLOG"', 2, 'unmount stderr', $f);
		rep($t, '>> ~/bc5-work/play-pkg-mount.log', '>> "$MLOG"', 2, 'unmount lines', $f);
	},
	'compress-old-captures.sh' => sub {
		my ($t, $f) = @_;
		rep($t, '  echo "$(stamp) box busy, skipped" >> "$LOG"; exit 0',
			'  exit 0  # 2026-10-25 (exp 0324, the maintainer): nothing is written while the box is busy', 1, 'busy skip', $f);
		rep($t, 'then echo "$(stamp) emulator started, stopping" >> "$LOG"; break; fi',
			'then break; fi  # exp 0324: silent when an emulator starts', 1, 'emulator stop', $f);
	},
);

for my $f (@files) {
	my ($name) = $f =~ m{([^/]+)$};
	my $e = $edit{$name} or die "$f: no edits known for $name\n";
	open(my $h, '<', $f) or die "$f: $!\n"; my $t = do { local $/; <$h> }; close $h;
	my $before = substr(md5_hex($t), 0, 8);
	die "$f: already carries exp 0324 (md5 $before): nothing done\n" if $t =~ /exp 0324/;
	my $new = $t;
	$e->(\$new, $f);
	open(my $b, '>', "$bak/$name.before-0324") or die "$bak/$name.before-0324: $!\n"; print $b $t; close $b;
	open(my $o, '>', $f) or die "$f: $!\n"; print $o $new; close $o;
	printf "%s: md5 %s -> %s (backup %s/%s.before-0324)\n", $f, $before, substr(md5_hex($new), 0, 8), $bak, $name;
}
