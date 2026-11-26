#!/usr/bin/env python3
r"""BC5 experiment 0425: run0425f.sh, one fight run, from exp 0413's run0413p.sh (md5 fc4fe47c; the copy exp 0423 read
on the box on 2026-11-15 and used for its walks the same day, kept here as run0413p.orig.sh).
    mk0425.py <run0413p.orig.sh> <run0425f.sh>
Each edit must match exactly once. What changes:
  1. Everything written lands in ~/bc5-work/exp0425/n (log, launcher, working directory, raw); lock and queue lines say
     exp 0425. Exp 0412's launcher, tools and words, exp 0358's save copy and exp 0360's record are only read.
  2. The save: ONE named snapshot ~/bc5-work/exp0425/saves-named/TITLE2, made once by MODE=name from exp 0358's
     private copy saves-live-47aefd45 (F464's route save; its sum by exp 0388's recipe must read 9347496fbaf30f25).
     The live saves are not read (R45). Each run resets its private copy from the snapshot.
  3. input.cfg's private copy: RT on, JobArenaFix OFF (the question is the host fix with the workaround off).
  4. At gameplay G: exp 0360's 14:50 record's gameplay part (fight1450-play.cmd, md5 b0f9ad5c, exp 0388's pin) is
     queued instead of exp 0379's walk; slot 4 comes from N_SLOT=4 (the chain sets it).
  5. The Wayland socket is looked for in $XDG_RUNTIME_DIR (CLAUDE.md), /run/user/<uid> when it is unset.
  6. The summary gets a CLASS (TARGET: the access violation reading 0xc at eboot+0x3d7eca0; CRASH_OTHER; KERNEL;
     WALL; NOT_ROUTED; SETUP; NO_CRASH: G+PLAY reached) and the exposure counts of exp 0425's lines.
Everything else (the claim, the route gate on the journal, the kernel-line stop, the sampler, the fuse and the watchdog,
ulimit -c 0 through the launcher) is run0413p.sh's own."""
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert hashlib.md5(b).hexdigest() == "fc4fe47c09671667c0037535c1e84bea", "run0413p.sh is not the one exp 0423 read on 2026-11-15"
s = b.decode("utf-8")
assert "\r" not in s


def sub(old, new, n=1):
    global s
    assert s.count(old) == n, "%d matches of %r" % (s.count(old), old[:80])
    s = s.replace(old, new)


# 1. own paths and lines
sub("W=$HOME/bc5-work; X=$W/exp0412; N=$W/exp0413/n; R=$N/raw; LOCK=$W/BOX-LOCK; NS=$X/night/saves-named; NSF=$X/night/saves-named.sum",
    "W=$HOME/bc5-work; X=$W/exp0412; N=$W/exp0425/n; R=$N/raw; LOCK=$W/BOX-LOCK; NS=$W/exp0425/saves-named; NSF=$W/exp0425/saves-named.sum  # exp 0425")
s = s.replace("exp0413/n", "exp0425/n").replace("play-pkg-0413n", "play-pkg-0425f")
sub('LINE="exp 0413 | private run $TAG', 'LINE="exp 0425 | private run $TAG')
sub("on exp0413/${WANT:0:8}", "on exp0425/${WANT:0:8}")
sub('"exp 0413 | claimed: private run', '"exp 0425 | claimed: private run')
sub('"exp 0413 | released: private run', '"exp 0425 | released: private run')
sub('LOG=$N/play-last.log  # exp 0413: own log', 'LOG=$N/play-last.log  # exp 0425: own log')
sub("# exp 0413: the private working directory (its own _SaveData)", "# exp 0425: the private working directory (its own _SaveData)")
sub("# exp 0413: private#", "# exp 0425: private#")
sub("# exp 0413: a private copy#", "# exp 0425: a private copy#")

# 2. the named snapshot from exp 0358's copy
sub('''if [ "${MODE:-}" = name ]; then echo "exp 0413: no MODE=name here (exp 0412 owns the snapshot)"; exit 1
fi
if false; then
  [ ! -e "$NS" ] || { echo "$NS exists ($(cat "$N/saves-named.sum" 2> /dev/null)): not made again"; exit 0; }
  [ -d "$W/_SaveData/TITLE2" ] || { echo "no live saves"; exit 1; }
  mkdir -p "$NS" && cp -a "$W/_SaveData/TITLE2" "$NS/TITLE2" || { rm -rf "$NS"; echo "the copy failed"; exit 1; }
  sumof "$NS" > "$N/saves-named.sum"
''', '''if [ "${MODE:-}" = name ]; then  # exp 0425: the named snapshot of F464's route save, made once from exp 0358's copy
  RS0=$W/exp0425/inputs/saves-live-47aefd45  # exp 0358's copy, restored from the NAS archive of 2026-11-08
  [ ! -e "$NS" ] || { echo "$NS exists ($(cat "$NSF" 2> /dev/null)): not made again"; exit 0; }
  [ -d "$RS0" ] && [ ! -L "$RS0" ] || { echo "no $RS0"; exit 1; }
  r0=$(cd "$RS0" && find . -type f -exec md5sum {} + | sort -k2 | md5sum | cut -c1-16)
  [ "$r0" = 9347496fbaf30f25 ] || { echo "$RS0 reads $r0, not exp 0388's 9347496fbaf30f25: not made"; exit 1; }
  mkdir -p "$NS" && cp -a "$RS0" "$NS/TITLE2" && chmod -R a-w "$NS/TITLE2" || { rm -rf "$NS"; echo "the copy failed"; exit 1; }
  sumof "$NS" > "$NSF"
''')

# 3. JobArenaFix off in the private input configuration
sub('''# 1. The private input configuration (RT on, JobArenaFix on) and the private learned file.
CFG=$N/input-$TAG.cfg
{ grep -v -i "^RayTracing\\.TITLE2=\\|^JobArenaFix\\.TITLE2=" "$W/input.cfg"; echo "RayTracing.TITLE2=on"; echo "JobArenaFix.TITLE2=on"; } > "$CFG" || exit 1''',
    '''# 1. The private input configuration (RT on, JobArenaFix OFF: exp 0425) and the private learned file.
CFG=$N/input-$TAG.cfg
{ grep -v -i "^RayTracing\\.TITLE2=\\|^JobArenaFix\\.TITLE2=" "$W/input.cfg"; echo "RayTracing.TITLE2=on"; echo "JobArenaFix.TITLE2=off"; } > "$CFG" || exit 1''')

# 4. the fight record instead of the walk
sub('''[ "$(cat "$LOCK")" = "$LINE" ] || { echo "the lock does not read back as ours: not started"; exit 1; }''',
    '''[ "$(cat "$LOCK")" = "$LINE" ] || { echo "the lock does not read back as ours: not started"; exit 1; }
PLAYCMD=$W/exp0425/inputs/fight1450-play.cmd  # exp 0425: F464's gameplay part of the 14:50 record (exp 0388's pin; exp 0360's copy, from the NAS archive of 2026-11-12)
[ "$(m "$PLAYCMD")" = b0f9ad5c017a8b43295b3d96a6e78c39 ] || { echo "$PLAYCMD is not exp 0388's b0f9ad5c: not started"; exit 1; }''')
sub('''  if [ -n "$G" ] && [ "$WALKED" = 0 ]; then WALKED=1; echo "route: walk of $(wk) cycles ($PLAY s) queued at $NOW s" >> "$R/$TAG-start.txt"; fi''',
    '''  if [ -n "$G" ] && [ "$WALKED" = 0 ]; then WALKED=1; cat "$PLAYCMD" >> "$CMD"; echo "route: the 14:50 record's gameplay ($(grep -c . "$PLAYCMD") lines) queued at $NOW s" >> "$R/$TAG-start.txt"; fi  # exp 0425''')

# 5. the Wayland socket's directory
sub('''WL=$(ls "/run/user/$(id -u)/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$')
[ -n "$WL" ] || { echo "no Wayland socket in /run/user/$(id -u): not started"; exit 1; }''',
    '''RUND=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}  # exp 0425: the session's directory (CLAUDE.md)
WL=$(ls "$RUND/" 2> /dev/null | grep -m1 '^wayland-[0-9]*$')
[ -n "$WL" ] || { echo "no Wayland socket in $RUND: not started"; exit 1; }''')

# 6. the class and the exposure
sub('''echo "$(cat "$R/$TAG-end.txt"); $FPSL; kernel lines''',
    '''PL=$R/$TAG-play.log  # exp 0425: the class, by the rule fixed before the runs
SITE=0; grep -aqF 'Access violation: Read [000000000000000c]' "$PL" && grep -aqE 'off=0000000003d7eca0, module=eboot\\.bin|kyty_exception_handler: 0000000903d7eca0' "$PL" && SITE=1
if [ "${ENDED#GPU HANG}" != "$ENDED" ] || { grep -i amdgpu "$R/$TAG-dmesg-after.txt" 2> /dev/null | grep -v -E '[A-Za-z_][A-Za-z0-9_.]*\\+0x[0-9a-f]+/0x[0-9a-f]+' | grep -qi "timeout\\|reset\\|fault"; }; then CLASS=KERNEL
elif [ "${ENDED#SETUP}" != "$ENDED" ]; then CLASS=SETUP
elif [ "$SITE" = 1 ]; then CLASS=TARGET
elif [ -s "$R/$TAG-crash.txt" ]; then CLASS=CRASH_OTHER
elif [ -n "$WHY" ]; then CLASS=WALL
elif [ -z "$G" ]; then CLASS=NOT_ROUTED
elif [ -z "$ENDED" ]; then CLASS=NO_CRASH
else CLASS=OTHER; fi
X5() { grep -ac -- "$1" "$PL" 2> /dev/null; }
EXPO="fix-off $(X5 'job-arena fix OFF for TITLE2') pass-through $(X5 'PASS-THROUGH for exp 0425') catcher-on $(X5 'exp 0425: catcher ON') C1-on $(X5 'C1 wake slice ON') C1-set-ok $(grep -a 'exp 0425 slice:' "$PL" | grep -c 'set rc 0 ') C1-hi-ok $(grep -a "exp 0425 slice: .*'Job Hi" "$PL" | grep -c 'set rc 0 ') C2-on $(X5 'C2 handoff ON') C2-lines $(X5 'exp 0425 handoff:') C3-on $(X5 'C3 direct wake ON') P1-on $(X5 'P1 locus SLOW ON') P1-calls $(X5 'exp 0425 playgo: PlayGoGetLocus call') P2-on $(X5 'P2 prefetch delay ON') P2-calls $(X5 'exp 0425 playgo: PlayGoPrefetch call') P3-on $(X5 'P3 call cost ON') pg-calls $(X5 'exp 0425 playgo:') crash-type-taken $(X5 'exp 0425 catch: owner takes crash-type')"
echo "catch: $(grep -a 'exp 0425 catch' "$PL" | tail -1 | cut -c1-300)" >> "$R/$TAG-start.txt"
echo "$(cat "$R/$TAG-end.txt"); $FPSL; kernel lines''')
sub('''ledger lines $(grep -c '^guard: t' "$R/$TAG-guard.txt")" > "$R/$TAG-summary.txt"''',
    '''ledger lines $(grep -c '^guard: t' "$R/$TAG-guard.txt"); CLASS $CLASS; exposure $EXPO" > "$R/$TAG-summary.txt"''')

s = s.replace("# BC5 exp 0412: one unattended arm", "# BC5 exp 0425 (derived by mk0425.py from exp 0413's run0413p.sh; see that script for every change): one fight run.\n# Its origin, BC5 exp 0412: one unattended arm", 1)
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("run0425f.sh written, md5", hashlib.md5(s.encode()).hexdigest())
