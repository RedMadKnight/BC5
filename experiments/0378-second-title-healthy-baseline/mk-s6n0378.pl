#!/usr/bin/perl
# BC5 exp 0378: derive s6n0378.sh from exp 0372's s6n0372.sh (copied to s6n0378.sh first). Literal edits only.
# usage: cp ../0372-pad-haptics-replug/raw/s6n0372.sh s6n0378.sh && perl mk-s6n0378.pl s6n0378.sh
use strict; use warnings;
my $f = shift or die "file";
open my $in, '<', $f or die; local $/; my $s = <$in>; close $in;
my $n;
sub rep { my ($old, $new, $want) = @_; my $c = () = $s =~ /\Q$old\E/g; die "[$old] occurs $c times, want $want\n" unless $c == $want; $s =~ s/\Q$old\E/$new/g; }

# 1. the header
my $hdr_old = substr($s, index($s, "# BC5 experiment 0372"), index($s, "set -u\n") - index($s, "# BC5 experiment 0372"));
my $hdr_new = <<'H';
# BC5 experiment 0378 (exp 0372's s6n0372.sh, made by mk-s6n0378.pl): the healthy-frame register baseline of the
# second title. The S6N route RT on with the SHARED normal build (~/bc5-work/kytyplus-build/src/kyty_emulator, md5
# pinned) through a private copy of play-pkg.sh (own log, wd, save directory, learned-file copy; the shared file is
# only read), exp 0196's route save copy in the private wd, the live saves compared only. While the scene runs the
# script asks the installed stall sampler (0377, registers only) for forced samples: `echo once` into its force file,
# 20 samples 5 s apart from t 180 s and 20 more from t 450 s. No wave request is ever written (F520).
# Everything else as s6n0372.sh / s6n0368.sh / s6n0350.sh: exp 0330's memory sampler, fdinfo, flips, the summary.
# usage: s6n0378.sh <expected live-saves sum> <tag> [secs] [off|on]   (on the box; 600 s, RT on by default)
H
rep($hdr_old, $hdr_new, 1);
rep('SECS=${3:-600}; RT=${4:-off}', 'SECS=${3:-600}; RT=${4:-on}', 1);
# 2. paths: everything private moves to exp0378
$n = () = $s =~ /exp0372/g; print "exp0372 occurrences: $n\n";
rep('BIN=$W/exp0372/kyty_emulator; WANT=$(cat "$W/exp0372/binary.md5" 2> /dev/null)   # exp 0372: the private pad-route build (build0372.sh)',
    'BIN=$W/kytyplus-build/src/kyty_emulator; WANT=${BC5_0378_WANT:-58c4a627}   # exp 0378: the shared normal build as installed (F504)', 1);
rep('PLAY_PKG_MD5=${PLAY_PKG_MD5:-$(sed -n \'s/.* launcher=\([0-9a-f]*\).*/\1/p\' "$W/exp0372/integration/new-md5.env" 2> /dev/null)}',
    'PLAY_PKG_MD5=${PLAY_PKG_MD5:-55531ab6}   # exp 0378: play-pkg.sh as read on 2026-10-29 10:40', 1);
$s =~ s/exp0372/exp0378/g;
rep('LAUNCH=$E/play-pkg-0358.sh', 'LAUNCH=$E/play-pkg-0378.sh', 1);
rep('play-pkg-0358.diff', 'play-pkg-0378.diff', 3);
# 3. the lock
rep('grep -q "^top exp 0372 |" "$LOCK"', 'grep -q "^top exp 0378 |" "$LOCK"', 1);
my $lock_old = substr($s, index($s, 'echo "top exp 0372 | s6n run:'), index($s, "\" > \"\$LOCK\"\n") + length("\" > \"\$LOCK\"\n") - index($s, 'echo "top exp 0372 | s6n run:'));
rep($lock_old, "echo \"top exp 0378 | second-title baseline, scripted route RT \$RT, ~10 min (\$TAG, shared normal \$WANT, forced register samples only) | \$(date '+%F %T')\" > \"\$LOCK\"\n", 1);
rep('grep -q "^top exp 0372 | s6n run" "$LOCK"', 'grep -q "^top exp 0378 | second-title baseline" "$LOCK"', 2);
# 4. the sampler must be the installed 0377, running, with its force file reachable
rep("saves() {", "FORCE=\$HOME/bc5-data/captures/gpu-stall/force; NF=0; LASTF=-10   # exp 0378: the stall sampler's request file\n"
  . "systemctl is-active -q bc5-gpu-stall-sampler && grep -q '^VERSION = \"0377\"' /usr/local/sbin/bc5-gpu-stall-sampler && [ -w \"\$(dirname \"\$FORCE\")\" ] || { echo \"the stall sampler 0377 is not running or its force directory is not writable: not started\"; exit 1; }\n"
  . "saves() {", 1);
# 5. the forced samples, after the hang check of each loop pass (a hang breaks out before any further request)
rep("    break\n  fi\n  sleep 5\ndone\n",
    "    break\n  fi\n"
  . "  T=\$((\$(date +%s) - T0))   # exp 0378: forced register samples, 20 from t 180 s and 20 from t 450 s, >= 5 s apart\n"
  . "  if [ \"\$NF\" -lt 40 ] && [ \$((T - LASTF)) -ge 5 ] && { { [ \"\$T\" -ge 180 ] && [ \"\$NF\" -lt 20 ]; } || [ \"\$T\" -ge 450 ]; }; then\n"
  . "    echo once > \"\$FORCE\" && NF=\$((NF + 1)) && LASTF=\$T && echo \"\$NF \$(date '+%T.%3N') t \$T\" >> \"\$R/\$TAG-forced-times.txt\"\n"
  . "  fi\n  sleep 5\ndone\n", 1);
# 6. after the run: which sampler directories and log lines belong to it
rep("sudo -n dmesg 2> /dev/null | tail -n +\"\$((N + 1))\" | grep -i \"amdgpu\\|gpu\\|oom\\|hung\\|SQC\" > \"\$R/\$TAG-dmesg-after.txt\"\n",
    "sudo -n dmesg 2> /dev/null | tail -n +\"\$((N + 1))\" | grep -i \"amdgpu\\|gpu\\|oom\\|hung\\|SQC\" > \"\$R/\$TAG-dmesg-after.txt\"\n"
  . "find \"\$(dirname \"\$FORCE\")\" -maxdepth 1 -mindepth 1 -type d -newermt \"@\$T0\" -printf '%f\\n' | sort > \"\$R/\$TAG-sampler-dirs.txt\"   # exp 0378\n"
  . "awk -v t=\"\$(date -d \"@\$T0\" '+%FT%T')\" '\$1 >= t' \"\$(dirname \"\$FORCE\")/stalls.log\" > \"\$R/\$TAG-stalls-log.txt\"\n", 1);
open my $out, '>', $f or die; print $out $s; close $out;
print "ok\n";
