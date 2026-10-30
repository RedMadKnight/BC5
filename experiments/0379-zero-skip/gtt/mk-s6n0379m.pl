#!/usr/bin/perl
# exp 0379, GTT growth: s6n0379m.sh from raw/s6n0379.sh, the same A/B runner (arm shared or private, the S6N route, RT on,
# private wd and save copy, live saves compared only) for up to 1,500 s instead of 900, with gtt/sample0379m.sh (the
# emulator's GTT per DRM client from fdinfo) in place of raw/sample0379.sh.
# usage: perl mk-s6n0379m.pl experiments/0379-zero-skip/raw/s6n0379.sh experiments/0379-zero-skip/gtt/s6n0379m.sh
use strict; use warnings;
my ($in, $out) = @ARGV;
open my $fh, '<', $in or die "$in: $!\n"; local $/; my $s = <$fh>; close $fh;
sub rep { my ($from, $to, $n) = @_; my $c = () = $s =~ /\Q$from\E/g; die "[$from] occurs $c times, want $n\n" unless $c == $n; $s =~ s/\Q$from\E/$to/g; }
rep('[ "$SECS" -le 900 ] || { echo "at most 900 s"; exit 1; }', '[ "$SECS" -le 1500 ] || { echo "at most 1500 s"; exit 1; }', 1);
rep('"$E/in/raw/sample0379.sh"', '"$E/in/gtt/sample0379m.sh"', 2);
rep('o2-continue.cmd, sample0379.sh or', 'o2-continue.cmd, sample0379m.sh or', 1);
# Codex review (REVIEW-02): each DRM client's identity, once at 120 s: every drm- key of every fd, by fd number and the
# fd's target (so the direct path's render-node client and RADV's can be told apart by size and fd).
rep('FDINFO=1; {', 'FDINFO=1; for f in /proc/$EP/fdinfo/*; do grep -a "^drm-" "$f" 2> /dev/null | sed "s#^#fd $(basename "$f") $(readlink "/proc/$EP/fd/$(basename "$f")") #"; done > "$R/$TAG-fdinfo-full.txt"; {', 1);
# The moving route (G3/G4): BC5_0379_ROUTE=<input script> replaces o2-continue.cmd (default: the S6N route as before).
rep('cp "$W/exp0203/o2-continue.cmd" "$E/in-$TAG.cmd"', 'cp "${BC5_0379_ROUTE:-$W/exp0203/o2-continue.cmd}" "$E/in-$TAG.cmd"  # exp 0379 G3/G4: BC5_0379_ROUTE', 1);
rep('[ -f "$W/exp0203/o2-continue.cmd" ]', '[ -f "${BC5_0379_ROUTE:-$W/exp0203/o2-continue.cmd}" ]', 1);
# The route diagnosis (2026-10-30, the top session's leave): BC5_0379_SHOTS="<s> <s> ..." takes full-screen shots
# (spectacle in the Plasma session, exp 0380's way) at those seconds after the emulator's start, into the private
# ~/bc5-data/captures/exp0379/shots/ (never the repo); unset, no shots.
rep("T0=\$(date +%s)\n", "T0=\$(date +%s)\n" .
  'if [ -n "${BC5_0379_SHOTS:-}" ]; then SHOTS=$HOME/bc5-data/captures/exp0379/shots; mkdir -p "$SHOTS"; chmod 700 "$HOME/bc5-data/captures/exp0379"   # exp 0379: route shots, private' . "\n" .
  '( for s in $BC5_0379_SHOTS; do while awk -v n="$(date +%s.%N)" -v t0="$T0" -v s="$s" \'BEGIN {exit !(n - t0 < s)}\'; do sleep 0.2; done' . "\n" .
  '    pgrep -x kyty_emulator > /dev/null || break' . "\n" .
  '    XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 spectacle -b -n -f -o "$SHOTS/$TAG-$s.png" > /dev/null 2>&1' . "\n" .
  '    echo "$(date \'+%T.%3N\') shot $s s: $(stat -c %s "$SHOTS/$TAG-$s.png" 2> /dev/null || echo none)" >> "$R/$TAG-shots.txt"; done ) < /dev/null > /dev/null 2>&1 &' . "\n" .
  "fi\n", 1);
# The route diagnosis D2 (2026-10-30): BC5_0379_SAVES=<dir> replaces the route saves (a PPSA03671-shaped directory,
# copied into the private wd as before; default exp 0196's S6N saves).
rep('SAVES=$W/exp0196/saves-before-152617', 'SAVES=${BC5_0379_SAVES:-$W/exp0196/saves-before-152617}', 1);
rep('(exp 0379: zero-skip A/B)', '(exp 0379: GTT growth A/B, 20 min, route ${BC5_0379_ROUTE:-o2-continue.cmd})', 1);
my $head = "#!/usr/bin/env bash\n# BC5 experiment 0379, GTT growth (raw/s6n0379.sh, made by gtt/mk-s6n0379m.pl): the zero-skip A/B runner for up to 1,500 s,\n# with the per-client GTT sampler gtt/sample0379m.sh.\n";
$s =~ s/\A#!\/usr\/bin\/env bash\n/$head/ or die "no shebang\n";
open my $o, '>', $out or die "$out: $!\n"; binmode $o; print {$o} $s; close $o or die "$out: $!\n";
print "ok\n";
