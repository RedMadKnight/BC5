#!/usr/bin/env bash
# BC5 experiment 0353 (the maintainer, 2026-10-28: "Sprawdź teraz"): the night lake on the shared build integrated by
# exp 0350 (normal affa0c22, play-pkg.sh 55531ab6). Exp 0347's lake bench, unchanged but for its paths: its scripts
# (bench0347.sh, ab0347.sh, input-0347.cfg) are copied to ~/bc5-work/exp0353 with 0347 -> 0353, and the bench launcher
# play-pkg-0353.sh is today's play-pkg.sh with exactly exp 0347's five edits (its log, its mount log, the bench input
# configuration hook, exp 0299's private save directory and working directory). The diff against play-pkg.sh is
# checked to be those edits and nothing else. Writes only ~/bc5-work/exp0353.
# usage: setup0353.sh   (on the box; no emulator, nothing shared written)
set -u
W=$HOME/bc5-work; S=$W/exp0347; E=$W/exp0353; L=$W/play-pkg.sh
m() { md5sum < "$1" | cut -c1-8; }
[ "$(m "$L")" = 55531ab6 ] || { echo "$L is $(m "$L"), not 55531ab6 (exp 0350's): stop"; exit 1; }
[ "$(m "$S/play-pkg-0347.sh")" = e6f75f1b ] || { echo "play-pkg-0347.sh is not e6f75f1b: stop"; exit 1; }
[ -e "$E/bench0353.sh" ] && { echo "$E already set up: stop"; exit 1; }
mkdir -p "$E"
sed -e "s/0347/0353/g" "$S/bench0347.sh" > "$E/bench0353.sh"
sed -e "s/0347/0353/g" -e "s/water session exp 0353/top session exp 0353/g" "$S/ab0347.sh" > "$E/ab0353.sh"
cp -p "$S/input-0347.cfg" "$E/input-0353.cfg"
chmod +x "$E/bench0353.sh" "$E/ab0353.sh"
# the launcher: today's play-pkg.sh with exp 0347's five edits, by anchor
perl -e 'my ($in, $out) = @ARGV; open my $f, "<", $in or die "$in: $!\n"; my @l = <$f>; close $f; my $n = 0;
  for (@l) {
    $n += s{^LOG=~/bc5-work/play-pkg-last\.log$}{LOG=~/bc5-work/exp0353/play-last.log};
    $n += s{^MLOG=~/bc5-work/play-pkg-mount\.log$}{MLOG=~/bc5-work/exp0353/play-pkg-mount.log  # exp 0353: its own mount log};
    $n += s{^export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/_SaveData-pkg-play$}{export KYTY_BC5_SAVEDATA_DIR=\$HOME/bc5-work/exp0299/wd/_SaveData-pkg-play  # exp 0353: private (exp 0299 wd)};
    $n += s{^cd ~/bc5-work$}{cd ~/bc5-work/exp0299/wd  # exp 0353: exp 0299 private working directory (its own _SaveData)};
  }
  my $h = 0; my @o;
  for (@l) { push @o, $_; if ($_ eq "done < \"\$ENVF\"\n") { push @o, "[ -n \"\${BC5_0299_INPUT_CONFIG:-}\" ] && export KYTY_BC5_INPUT_CONFIG=\$BC5_0299_INPUT_CONFIG  # exp 0353: the bench input configuration\n"; $h++; } }
  die "edits $n (want 4), hook $h (want 1)\n" unless $n == 4 && $h == 1;
  open my $g, ">", $out or die "$out: $!\n"; print {$g} @o; close $g or die "$out: $!\n";' "$L" "$E/play-pkg-0353.sh" || { echo "launcher derivation failed: stop"; exit 1; }
chmod +x "$E/play-pkg-0353.sh"; bash -n "$E/play-pkg-0353.sh" || { echo "the launcher does not parse: stop"; exit 1; }
diff "$L" "$E/play-pkg-0353.sh" > "$E/play-pkg-0353.diff"
# the same five edits as exp 0347's launcher had against its play-pkg.sh (names 0347 -> 0353)
diff "$W/exp0350/integration/play-pkg.sh.before-0350" "$S/play-pkg-0347.sh" | grep '^[<>]' | sed 's/0347/0353/g' > "$E/want.lines"
grep '^[<>]' "$E/play-pkg-0353.diff" > "$E/got.lines"
cmp -s "$E/want.lines" "$E/got.lines" || { echo "the launcher's edits differ from exp 0347's:"; diff "$E/want.lines" "$E/got.lines"; exit 1; }
for f in bench0353.sh ab0353.sh; do bash -n "$E/$f" || { echo "$f does not parse"; exit 1; }; done
grep -q 'exp0347\|0347' "$E/bench0353.sh" "$E/ab0353.sh" && { echo "a 0347 reference is left:"; grep -n '0347' "$E/bench0353.sh" "$E/ab0353.sh"; exit 1; }
echo "set up: play-pkg-0353.sh $(m "$E/play-pkg-0353.sh") ($(grep -c '^[<>]' "$E/play-pkg-0353.diff") diff lines, as exp 0347's), bench0353.sh $(m "$E/bench0353.sh"), ab0353.sh $(m "$E/ab0353.sh"), input-0353.cfg $(m "$E/input-0353.cfg") ($(grep -c '^RayTracing.PPSA03671=off$' "$E/input-0353.cfg") RT-off line)"
