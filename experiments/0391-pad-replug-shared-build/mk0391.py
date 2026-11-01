#!/usr/bin/env python3
"""BC5 exp 0391: the box and laptop scripts, derived from reviewed sources with counted replacements (LESSONS R05, R10).
  src/s6n-d19.sh (coordination/d19, sha256 d7cf6e33…)  -> s6n0391.sh    the S6N route, RT on, on the SHARED normal build
  src/replug0372.sh (exp 0372)                         -> replug0391.sh the software replug (PipeWire card profile off/on)
  src/streams0372.py (exp 0372)                        -> streams0391.py unchanged
  src/run0390.sh, src/go0390.sh (exp 0390, dba7e514)   -> run0391.sh, go0391.sh   the token lock, the run, the stream, the release
What differs is marked "0391:" where it stands. usage: python3 -I mk0391.py <this dir>"""
import hashlib, os, sys

HERE = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
PINS = {"s6n-d19.sh": "d7cf6e33036f97eddc097133c2d6ee75fc86608c967fa8854c587a27a65d4058"}


def load(name):
    p = os.path.join(SRC, name)
    s = open(p, encoding="utf-8", newline="").read()
    if name in PINS:
        h = hashlib.sha256(s.encode("utf-8")).hexdigest()
        assert h == PINS[name], (name, h)
    assert "\r" not in s, name
    return s


def R(s, a, b, n=1):
    c = s.count(a)
    assert c == n, ("count %d, want %d" % (c, n), a[:90])
    return s.replace(a, b)


def D(s, a, n=1):
    """Delete a block that must occur n times."""
    return R(s, a, "", n)


def save(name, s):
    p = os.path.join(HERE, name)
    open(p, "w", encoding="utf-8", newline="\n").write(s)
    os.chmod(p, 0o755)
    print("%s %s %d lines" % (hashlib.md5(s.encode()).hexdigest()[:8], name, s.count("\n")))


# ---------------------------------------------------------------- s6n0391.sh
s = load("s6n-d19.sh")
HEAD = """#!/usr/bin/env bash
# BC5 exp 0391: the software replug check of exp 0372 on the SHARED normal build (78f25172, patch 0001 with exp 0372's
# pad audio route): the S6N route, RT on, the audio, measure and input traces on, while replug0391.sh turns the DualSense's
# PipeWire card profile off and on. Derived from coordination/d19/s6n-d19.sh (sha256 d7cf6e33) by mk0391.py; what differs
# (each marked "0391:" where it stands):
#  - run0391.sh owns the lock: this script only checks that BOX-LOCK is this run's exact line (E0391_LOCKLINE), at the start,
#    before the launch and at every poll; it never writes or clears the lock.
#  - no live-save sum as a gate: the live saves are snapshot by name (saves-before-HHMM) and compared at the end only.
#  - the traces: KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1 in the emulator's environment, proved there.
#  - no stall-sampler requests, no sampler gate, no menu shots (exp 0378/0380's additions, not needed here).
#  - the audio and rumble lines of the play log go to raw/<tag>-audio-lines.txt for check0391.py.
# Called by run0391.sh only. usage: s6n0391.sh <tag> [secs]   (420 s by default)
# Exit: 0 verdict pass with the live saves unchanged, 1 anything else.
"""
s = R(s, "#!/usr/bin/env bash\n", HEAD)
s = R(s, "EXPECT_SAVES=${1:?the live saves sum}; TAG=${2:?a tag}; SECS=${3:-600}; RT=${4:-on}; VARIANT=${D19_VARIANT:?}; OWNER=${D19_OWNER:?}",
      "TAG=${1:?a tag}; SECS=${2:-420}; RT=on; VARIANT=normal; OWNER=${D19_OWNER:?}; LOCKLINE=${E0391_LOCKLINE:?}  # 0391: RT on, the shared normal build, run0391.sh's lock line")
s = R(s, "E=$HOME/bc5-work/d19/run; R=$E/raw; W=$HOME/bc5-work; LOCK=$W/BOX-LOCK; E30=$W/exp0330",
      "W=${D19_WORK:-$HOME/bc5-work}; E=$W/exp0391/run; R=$E/raw; LOCK=$W/BOX-LOCK; E30=$W/exp0330  # 0391: private paths")
s = R(s, 'SWITCHES=""; [ "$VARIANT" = lean ] && SWITCHES="BC5_LEAN=1 BC5_LOGS=1"',
      'SWITCHES="KYTY_BC5_AUDIO_TRACE=1 KYTY_BC5_MEASURE=1 KYTY_BC5_INPUT_TRACE=1"  # 0391: the traces, as exp 0267\'s play-ds4.sh')
s = R(s, '[ -s "$LOCK" ] && ! grep -q "^top d19 |" "$LOCK" && { echo "the box is locked: $(cat "$LOCK")"; exit 1; }\n',
      'own_lock_q() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }  # 0391\n'
      'own_lock_q || { echo "the lock is not this run\'s: not started"; exit 1; }  # 0391: run0391.sh owns the lock\n')
s = D(s, 'FORCE=$HOME/bc5-data/captures/gpu-stall/force; NF=40; LASTF=-10   # exp 0380: no forced requests   # exp 0378: the stall sampler\'s request file\n'
         'systemctl is-active -q bc5-gpu-stall-sampler && grep -q \'^VERSION = "0377"\' /usr/local/sbin/bc5-gpu-stall-sampler && [ -w "$(dirname "$FORCE")" ] || { echo "the stall sampler 0377 is not running or its force directory is not writable: not started"; exit 1; }\n')
s = D(s, 'LIVE=$(saves)\n[ "$LIVE" = "$EXPECT_SAVES" ] || { echo "the live saves read $LIVE, not $EXPECT_SAVES: not started"; exit 1; }\n')
s = R(s, "LAUNCH=$E/play-pkg-d19s.sh", "LAUNCH=$E/play-pkg-0391.sh")
s = R(s, "play-pkg-d19s.diff", "play-pkg-0391.diff", 3)
s = R(s, "bc5-work/d19/run/", "bc5-work/exp0391/run/", 6)
s = R(s, "'d19/run/wd' 'd19/run/play-last.log' 'd19/run/direct-learned-pkg.txt'", "'exp0391/run/wd' 'exp0391/run/play-last.log' 'exp0391/run/direct-learned-pkg.txt'")
s = R(s, "# d19: d19box.sh owns the lock\n# d19: no lock trap\n", "# 0391: run0391.sh owns the lock; no lock trap\n")
s = R(s, 'setsid nohup bash -c \'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"\' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &\n',
      'own_lock_q || { echo "the lock is not this run\'s: not launched"; [ -z "$SP" ] || kill "$SP" 2> /dev/null; exit 1; }  # 0391: the last look before the launch\n'
      'setsid nohup bash -c \'distrobox enter ubuntu -- env "$@"; echo "launcher exit $?"\' _ "${ENVS[@]}" "$LAUNCH" < /dev/null > "$R/$TAG-launch.out" 2>&1 &\n')
# the menu shots (exp 0380nc) go
i = s.index('SHOTS=$HOME/bc5-data/captures/d19/shots;')
j = s.index(') < /dev/null > /dev/null 2>&1 &\n', i) + len(') < /dev/null > /dev/null 2>&1 &\n')
assert s.count('SHOTS=') == 1 and s[i:j].count("\n") == 5, s[i:j]
s = s[:i] + s[j:]
# the lock is checked at every poll
s = R(s, '  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }\n',
      '  [ -d "/proc/$EP" ] || { ENDED="ended by itself at $(($(date +%s) - T0)) s"; break; }\n'
      '  own_lock_q || { ENDED="SETUP: the lock is no longer this run\'s"; break; }  # 0391\n')
# the forced samples loop
s = D(s, '  T=$(($(date +%s) - T0))   # exp 0378: forced register samples, 20 from t 180 s and 20 from t 450 s, >= 5 s apart\n'
         '  if [ "$NF" -lt 40 ] && [ $((T - LASTF)) -ge 5 ] && { { [ "$T" -ge 180 ] && [ "$NF" -lt 20 ]; } || [ "$T" -ge 450 ]; }; then\n'
         '    echo once > "$FORCE" && NF=$((NF + 1)) && LASTF=$T && echo "$NF $(date \'+%T.%3N\') t $T" >> "$R/$TAG-forced-times.txt"\n'
         '  fi\n')
s = D(s, 'find "$(dirname "$FORCE")" -maxdepth 1 -mindepth 1 -type d -newermt "@$T0" -printf \'%f\\n\' | sort > "$R/$TAG-sampler-dirs.txt"   # exp 0378\n'
         'awk -v t="$(date -d "@$T0" \'+%FT%T\')" \'$1 >= t\' "$(dirname "$FORCE")/stalls.log" > "$R/$TAG-stalls-log.txt"\n')
s = R(s, '{ grep -a "experiment 0380 switch" "$R/$TAG-play.log"; grep -a "experiment 0380 periodic\\|experiment 0380 at close" "$R/$TAG-play.log" | tail -3; } > "$R/$TAG-0380.txt" 2> /dev/null   # exp 0380: the rebase counters\n',
      '{ grep -a "experiment 0380 switch" "$R/$TAG-play.log"; grep -a "experiment 0380 periodic\\|experiment 0380 at close" "$R/$TAG-play.log" | tail -3; } > "$R/$TAG-0380.txt" 2> /dev/null   # exp 0380: the rebase counters\n'
      'grep -a -E "AudioOut \\(exp 0372\\)|pad route:|audio trace:|input trace: rumble|rumble: pad instance|AudioOut:" "$R/$TAG-play.log" > "$R/$TAG-audio-lines.txt" 2> /dev/null   # 0391: for check0391.py\n')
assert "d19/run" not in s and "$FORCE" not in s and "EXPECT_SAVES" not in s and "SHOTS" not in s, "leftovers"
save("s6n0391.sh", s)

# ---------------------------------------------------------------- replug0391.sh
s = load("replug0372.sh")
HEAD = """#!/usr/bin/env bash
# BC5 exp 0391: exp 0372's software replug test (raw/replug0372.sh, 2026-10-29) on the shared normal build, under run0391.sh's
# token lock. While s6n0391.sh runs the second title (RT on, the S6N route), this turns the DualSense's PipeWire card profile
# off and back on: the pad's sink node goes and comes back as at a USB replug, so SDL's PipeWire backend sends the same audio
# device removal and addition (the pad's HID side stays). Test plan A's three pulls: 5 s, under 1 s, 30 s; before and after
# each, the emulator's streams and their links. The profile is set with `pw-cli set-param` without `save` (WirePlumber
# stores nothing); the original index is put back at the end, on failure too. The default sink is muted for the run and its
# mute state put back. With `late`: the profile is off before the run starts and turned on at ~170 s, then one 5-s pull.
# What differs from replug0372.sh (marked "0391:"): the run is recognised by its exact lock line (E0391_LOCKLINE) and the
# emulator by the D19_OWNER token in its environment; private paths under ~/bc5-work/exp0391/run.
# Started by run0391.sh with the token; usage: replug0391.sh <tag> [pulls|late]   (waits up to 3 min for the run)
"""
i = s.index("set -u\n")
s = HEAD + s[i:]
s = R(s, "TAG=${1:?tag}; MODE=${2:-pulls}; W=$HOME/bc5-work; E=$W/exp0372; R=$E/raw; LOCK=$W/BOX-LOCK; LOG=$E/play-last.log",
      "TAG=${1:?tag}; MODE=${2:-pulls}; W=${D19_WORK:-$HOME/bc5-work}; E=$W/exp0391/run; R=$E/raw; LOCK=$W/BOX-LOCK; LOG=$E/play-last.log\n"
      "OWNER=${D19_OWNER:?}; LOCKLINE=${E0391_LOCKLINE:?}  # 0391: the run's token and lock line")
s = R(s, 'PY=$(cd "$(dirname "$0")" && pwd)/streams0372.py', 'PY=$(cd "$(dirname "$0")" && pwd)/streams0391.py')
s = R(s, 'ours() { grep -q "^top exp 0372 | s6n run: .*, $TAG, " "$LOCK" 2> /dev/null; }',
      'ours() { [ -f "$LOCK" ] && [ ! -L "$LOCK" ] && [ "$(cat "$LOCK" 2> /dev/null)" = "$LOCKLINE" ]; }  # 0391: the exact line')
s = R(s, 'emu() { pgrep -o -x kyty_emulator; }',
      '# 0391: the emulator that carries this run\'s token; a foreign one is never ours\n'
      'emu() { local p; for p in $(pgrep -x kyty_emulator); do tr \'\\0\' \'\\n\' < "/proc/$p/environ" 2> /dev/null | grep -qxF -- "D19_OWNER=$OWNER" && { echo "$p"; return 0; }; done; return 1; }')
s = R(s, 'say "no s6n0372.sh run with tag $TAG: nothing done"', 'say "no s6n0391.sh run under this lock line: nothing done"')
assert "exp0372" not in s and "streams0372" not in s, "leftovers"
save("replug0391.sh", s)
save("streams0391.py", load("streams0372.py").replace("exp 0372", "exp 0391 (exp 0372's streams0372.py, unchanged)", 1))

# ---------------------------------------------------------------- run0391.sh
s = load("run0390.sh")
s = R(s, "#!/usr/bin/env bash\n# BC5 exp 0390 on the box: the lock, the run and its cleanup for one fight run. Called by go0390.sh only.\n",
      "#!/usr/bin/env bash\n# BC5 exp 0391 on the box: the lock, the run and its cleanup for one software replug run (s6n0391.sh + replug0391.sh)\n"
      "# on the SHARED normal build. Derived from exp 0390's run0390.sh (dba7e514) by mk0391.py; \"0391:\" marks what differs:\n"
      "# the second argument is the replug mode (pulls|late), not a fix switch; the pins are the shared binary (first 8 hex, as\n"
      "# the top session named it), the launcher and bc5-run.env; the replug script runs beside the S6N run with the same\n"
      "# token; check0391.py classifies. Called by go0391.sh only.\n")
s = s.replace("0390", "0391")
s = R(s, "Derived from exp 0391's run0391.sh (dba7e514)", "Derived from exp 0390's run0390.sh (dba7e514)")
s = R(s, "<on|off>", "<pulls|late>", 3)
s = R(s, '"top exp0391 | token $TOK | $tag fix $fix, RT on, until',
      '"anyps5-ports exp0391 | token $TOK | $tag software replug ($fix), shared 78f25172, RT on, until')
s = R(s, '    case "$fix" in on) ;; *) die "every 0391 run has the job-arena fix on" ;; esac\n',
      '    case "$fix" in pulls | late) ;; *) die "the mode is pulls or late" ;; esac  # 0391\n')
s = R(s, "top exp0391 | done:", "anyps5-ports exp0391 | done:")
s = R(s, "top exp0391 | released:", "anyps5-ports exp0391 | released:")
s = R(s, "# The deadline is the end of everything. The outer limit ends 60 s before it, hard kill included; the run must leave 150 s\n"
         "# for its own kill (30), reap (30), check and release. A run needs 390 s, plus the claim and the send.\n"
         "SECS=180; RUN_MIN=430; RUN_CAP=280; KEEP=150; OUTER_END=90; REAP_TERM=20; REAP_KILL=10; DISK_MAX=80\n",
      "# The deadline is the end of everything. The outer limit ends 90 s before it, hard kill included; the run must leave 150 s\n"
      "# for its own kill (30), reap (30), check and release. A run needs 420 s of play plus ~90 s of setup and end, so the\n"
      "# runner is capped at 600 s and a claim needs 840 s to the deadline (0391: SECS 420, exp 0372's P1 length).\n"
      "SECS=420; RUN_MIN=840; RUN_CAP=600; KEEP=150; OUTER_END=90; REAP_TERM=20; REAP_KILL=10; DISK_MAX=80\n")
s = R(s, "EX=$W/exp0391; E=$EX/run; R=$E/raw; S=$EX/s\n", "EX=$W/exp0391; E=$EX/run; R=$E/raw; S=$EX/s; B=$W/kytyplus-build  # 0391: the shared normal build\n")
OLD_INPUTS = s[s.index("# The pins under the lock, immediately before the launch.\n"):s.index("finish_run() {\n")]
NEW_INPUTS = """# The pins under the lock, immediately before the launch. 0391: the shared normal build by its first 8 hex (the top session
# named 78f25172; the full md5 is recorded in -start.txt), the launcher and bc5-run.env in full; input.cfg and the learned
# file are recorded, not gated (s6n0391.sh copies both privately and forces RT on).
inputs_ok() {
    local v
    . "$S/pins0391.env" || die "no pins"
    for v in NORMAL8 LAUNCHER RUN_ENV; do
        case "${!v:-FILL}" in FILL) die "the pin $v is not filled" ;; esac
    done
    BIN=$B/src/kyty_emulator  # 0391: the SHARED normal build, read only
    [ -f "$BIN" ] && [ ! -L "$BIN" ] || die "no shared binary at $BIN"
    [ "$(m "$BIN" | cut -c1-8)" = "$NORMAL8" ] || die "the shared binary is $(m "$BIN" | cut -c1-8), not $NORMAL8"
    [ "$(m "$W/play-pkg.sh")" = "$LAUNCHER" ] || die "the launcher is not $LAUNCHER"
    [ "$(m "$W/bc5-run.env")" = "$RUN_ENV" ] || die "bc5-run.env is not $RUN_ENV"
    [ -d "$W/exp0196/saves-before-152617" ] || die "no route saves (exp 0196)"
    [ -x "$S/replug0391.sh" ] && [ -f "$S/streams0391.py" ] || die "no replug script"
    echo "pins: shared $(m "$BIN"), launcher $LAUNCHER, bc5-run.env $RUN_ENV; input.cfg $(m "$W/input.cfg"), learned $(m "$W/direct-learned-pkg.txt")" > "$R/$TAG-pins.txt"
}
"""
s = s.replace(OLD_INPUTS, NEW_INPUTS)
s = R(s, '    D19_OWNER=$TOK D19_BIN=$BIN BC5_0380_WANT=${NORMAL:0:8} E0391_LOCKLINE=$LOCKLINE \\\n'
         '        session timeout -k 30 "$cap" bash "$S/s6n0391.sh" "$TAG" "$SECS" "$FIX" > "$R/$TAG-runner.out" 2>&1 &\n'
         '    p=$!; RUNP=$p\n'
         '    wait "$p"; rc=$?\n'
         '    RUNP=""\n',
      '    # 0391: the replug script first (it waits for the run, up to 3 min), then the run; both carry the token\n'
      '    D19_OWNER=$TOK E0391_LOCKLINE=$LOCKLINE \\\n'
      '        session timeout -k 30 "$cap" bash "$S/replug0391.sh" "$TAG" "$FIX" > "$R/$TAG-replug.out" 2>&1 &\n'
      '    REPLUGP=$!\n'
      '    D19_OWNER=$TOK D19_BIN=$BIN BC5_0380_WANT=$NORMAL8 E0391_LOCKLINE=$LOCKLINE PLAY_PKG_MD5=${LAUNCHER:0:8} \\\n'
      '        session timeout -k 30 "$cap" bash "$S/s6n0391.sh" "$TAG" "$SECS" > "$R/$TAG-runner.out" 2>&1 &\n'
      '    p=$!; RUNP=$p\n'
      '    wait "$p"; rc=$?\n'
      '    RUNP=""\n'
      '    wait "$REPLUGP" 2> /dev/null; echo "replug rc $?" >> "$R/$TAG-replug.out"\n')
s = R(s, '    "${PY[@]}" "$S/check0391.py" run "$TAG" "$FIX" "$rc" "$R" "$W/d19/raw/stubs-baseline.txt" > "$R/$TAG-check.txt" 2>&1; c=$?\n'
         '    local cl; cl=$(tail -1 "$R/$TAG-check.txt")\n'
         '    case "$cl" in "CLASS "*) ;; *) cl="CLASS INVALID fix $FIX crash none reached 0" ;; esac\n',
      '    "${PY[@]}" "$S/check0391.py" run "$TAG" "$FIX" "$rc" "$R" > "$R/$TAG-check.txt" 2>&1; c=$?\n'
      '    local cl; cl=$(tail -1 "$R/$TAG-check.txt")\n'
      '    case "$cl" in "CLASS "*) ;; *) cl="CLASS INVALID mode $FIX pulls 0" ;; esac\n')
s = R(s, 'HELD=0; LOCKLINE=""; STOPWHY=""; RUNP=""\n', 'HELD=0; LOCKLINE=""; STOPWHY=""; RUNP=""; REPLUGP=""\n')
assert "stubs-baseline" not in s and "job-arena" not in s and "exp0358" not in s and "exp0360" not in s, "leftovers"
assert s.count("D19_OWNER=$TOK") == 3
save("run0391.sh", s)

# ---------------------------------------------------------------- go0391.sh
s = load("go0390.sh")
s = R(s, "#!/usr/bin/env bash\n# BC5 exp 0390 from the laptop: one fight run. No retry of any step.\n# usage: go0390.sh <tag> <on|off> <deadline epoch>\n",
      "#!/usr/bin/env bash\n# BC5 exp 0391 from the laptop: one software replug run on the shared normal build, in a slot the top session named.\n"
      "# Derived from exp 0390's go0390.sh (dba7e514) by mk0391.py; \"0391:\" marks what differs. No retry of any step.\n"
      "# usage: go0391.sh <tag> <pulls|late> [deadline epoch; 16 min from now by default]\n")
s = s.replace("0390", "0391")
s = R(s, "Derived from exp 0391's go0391.sh (dba7e514)", "Derived from exp 0390's go0390.sh (dba7e514)")
s = R(s, 'TAG=${1:?tag}; FIX=${2:?on or off}; DL=${3:?deadline epoch}\n',
      'TAG=${1:?tag}; FIX=${2:?pulls or late}; DL=${3:-$(($(date +%s) + 960))}  # 0391: the mode; 840 s needed, 960 given\n')
s = R(s, 'FILES="run0391.sh s6n0391.sh prestart0391.sh check0391.py d19gates.py d19manifest.py pins0391.env"  # the private binary is pinned there\n',
      'FILES="run0391.sh s6n0391.sh replug0391.sh streams0391.py check0391.py pins0391.env"  # 0391: the shared binary is pinned there\n')
s = R(s, 'echo "$res"\n', 'echo "$res"\n'
      '# 0391: the run\'s text results come to raw/ (never -environ.bin, never the play log; -audio-lines.txt holds only trace lines)\n'
      'for f in summary verdict end start pins replug audio-lines check 0358 route dmesg-after devcoredump flips-per-10s runner replug.out box; do\n'
      '    case "$f" in replug.out | box) n="$TAG-$f.out"; [ "$f" = replug.out ] && n="$TAG-replug.out" ;; *) n="$TAG-$f.txt" ;; esac\n'
      '    timeout "$SHORT" "$SCP" -q "bc250:$RAW/$n" "$HERE/raw/" 2> /dev/null || echo "$TAG: no $n fetched"\n'
      'done\n')
assert "on or off" not in s and "fight" not in s, "leftovers"  # FIX stays as the variable name: it carries the mode
save("go0391.sh", s)
print("ok")
