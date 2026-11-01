#!/usr/bin/env python3
# BC5 exp 0393: makes run0393.sh, go0393.sh, s6n0393.sh and prestart0393.sh from exp 0388's kit (0e87a5d2 of
# exp/0388-job-arena-root) by literal edits. Every edit must match exactly once; the rename 0388 -> 0393 comes first.
# usage: python mk0393.py   (from this directory, in a checkout that has that commit)
import os, subprocess, sys

REF = '0e87a5d2'
OLD = 'experiments/0388-job-arena-root/'
HERE = os.path.dirname(os.path.abspath(__file__))


def src(name):
    raw = subprocess.run(['git', 'show', f'{REF}:{OLD}{name}'], capture_output=True, check=True, cwd=HERE).stdout
    return raw.decode('utf-8').replace('0388', '0393')


def edit(text, pairs, name):
    for k, (old, new) in enumerate(pairs, 1):
        n = text.count(old)
        if n != 1:
            sys.exit(f'{name}, edit {k}: found {n} times: {old[:70]!r}')
        text = text.replace(old, new)
    return text


def span(text, a, b, new, name):
    if text.count(a) != 1:
        sys.exit(f'{name}: start found {text.count(a)} times: {a[:70]!r}')
    i = text.index(a)
    j = text.find(b, i)
    if j < 0:
        sys.exit(f'{name}: no end: {b[:70]!r}')
    return text[:i] + new + text[j + len(b):]


def write(name, text):
    with open(os.path.join(HERE, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    print(name, len(text.splitlines()), 'lines')


def s6n():
    n = 's6n0393.sh'
    t = src('s6n0388.sh')
    t = span(t, '# BC5 exp 0393: one F464 fight run', '# Exit: 0 verdict pass, 1 anything else.\n', r'''# BC5 exp 0393: one run of the S6N route, RT on, on the private breadcrumb binary, one arm of the cost test.
# Made from exp 0388's s6n0388.sh by mk0393.py. What differs:
#  - the route: exp 0196's save copy and exp 0203's o2-continue.cmd, as exps 0350-0378; no gameplay inputs, no journal gate.
#  - the first letter of the tag is the arm: O breadcrumbs off, L level 1, T level 2; the journal must show that arm.
#  - the launcher's md5 comes from run0393.sh's pins; <tag>-frames.txt keeps the frame profile lines for ana0393.py.
# Called by run0393.sh only. usage: s6n0393.sh <tag> <secs>
# Exit: 0 verdict pass, 1 anything else.
''', n)
    t = span(t, '# 0393: the first letter of the tag is the arm; the check reads the same table\n',
             'SWITCHES="KYTY_BC5_JOB_ARENA_FIX=$FIXV $ARM"\n', r'''# 0393: the first letter of the tag is the arm
case "$TAG" in
  O*) SWITCHES=""; BCLEVEL=0 ;;
  L*) SWITCHES="BC5_DIRECT_BREADCRUMBS=1"; BCLEVEL=1 ;;
  T*) SWITCHES="BC5_DIRECT_BREADCRUMBS=2"; BCLEVEL=2 ;;
  *) echo "no arm for $TAG"; exit 1 ;;
esac
''', n)
    t = span(t, '  if [ -z "$JOBS" ] && [ "$(el)" -ge "$T_JOBS" ]', 'uniq -c > "$R/$TAG-nice.txt"\n  fi\n', '', n)
    t = span(t, '  # 0393, from run0360.sh: the gameplay inputs',
             'then pause "$T_POLL_P2"; else pause "$T_POLL"; fi\n', '  pause "$T_POLL"\n', n)
    return edit(t, [
        ('SECS=${2:?secs}; FIX=${3:?on or off}; RT=on;', 'SECS=${2:?secs}; RT=on;'),
        ('case "$FIX" in on) FIXV=1 ;; off) FIXV=0 ;; *) echo "the fix is on or off"; exit 1 ;; esac\n', ''),
        ('WANT=${BC5_0380_WANT:?}; LOCKLINE=${E0393_LOCKLINE:?}', 'WANT=${BC5_0393_WANT:?}; LOCKLINE=${E0393_LOCKLINE:?}; LAUNCHER=${E0393_LAUNCHER:?}'),
        ('JOBS=""; T_JOBS=70; DISK_MAX=80; T_ROUTE=60;', 'DISK_MAX=80; T_ROUTE=120;'),
        ('T_FD=120; T_P2=88; T_P2_WAIT=30; T_POLL=5; T_POLL_P2=1; T_KERN=25;', 'T_FD=120; T_POLL=5; T_KERN=25;'),
        ('SAVES=$W/exp0358/saves-live-47aefd45; MENU=$W/exp0360/fight1450-menu.cmd; PHASE2=$W/exp0360/fight1450-play.cmd  # 0393: F464\'s route',
         'SAVES=$W/exp0196/saves-before-152617; MENU=$W/exp0203/o2-continue.cmd  # 0393: the S6N route'),
        ('kernel $(uname -r); shared normal $(md5sum < "$BIN" | cut -c1-8);', 'kernel $(uname -r); binary $(md5sum < "$BIN" | cut -c1-8);'),
        ('[ -s "$MENU" ] && [ -s "$PHASE2" ] && [ -x "$E30/sample0330.sh" ]', '[ -s "$MENU" ] && [ -x "$E30/sample0330.sh" ]'),
        ('{ echo "no $SAVES, $LAUNCH_SRC, $MENU, $PHASE2, sample0330.sh or $LEARN_SRC"; exit 1; }', '{ echo "no $SAVES, $LAUNCH_SRC, $MENU, sample0330.sh or $LEARN_SRC"; exit 1; }'),
        ("PLAY_PKG_MD5=55531ab6   # D19's pin; run0393.sh checks the full md5", 'PLAY_PKG_MD5=${LAUNCHER:0:8}   # 0393: from the pins; run0393.sh checks the full md5'),
        ('P2LOAD=""; P2DONE=""; P2GAME=0  # 0393: the fight route\'s second part\n', ''),
        # LESSONS R45, R48: a named sample and a reset private copy, identified by the copy's sum. No read of the live saves.
        ('''saves() { (cd "$W/_SaveData" && find PPSA03671 -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }  # exp 0253's ab0253.sh, C locale\nLIVE=$(saves)\n''', ''),
        ('''WANT_SAVES=$(saves)\necho "$(date '+%F %T') live saves $WANT_SAVES (comparison only)" | tee -a "$R/s6n-saves.txt"\n''', ''),
        ('''echo "$(date '+%F %T') aborted" >> "$R/s6n-saves.txt"; sync; exit 1; }''', '''echo "$(date '+%F %T') aborted" >> "$R/$TAG-aborted.txt"; sync; exit 1; }'''),
        ('''find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +\n''',
         '''find "$SROOT/PPSA03671" -type f -exec touch -a -d '2020-01-01 00:00:00' {} +\n'''
         '''(cd "$SROOT/PPSA03671" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16) > "$R/$TAG-copy.txt"  # 0393: the copy's sum, as ROUTE_SAVES\n'''),
        ('''S1=$(saves); echo "$(date '+%F %T') live saves $S1 (want $WANT_SAVES)" | tee -a "$R/s6n-saves.txt"\nsync\n''', ''),
        ('KYTY_BC5_JOB_ARENA_FIX|KYTY_BC5_0393_[A-Z_]*|BC5_GC_DUMP_DIR', 'BC5_DIRECT_BREADCRUMBS|BC5_GC_DUMP_DIR'),
        ('''{ ENDED="SETUP: the emulator's environment lacks $w"; break; }; done\n''',
         '''{ ENDED="SETUP: the emulator's environment lacks $w"; break; }; done\n'''
         '''  if [ "$BCLEVEL" = 0 ] && envof "$EP" | grep -q '^BC5_DIRECT_BREADCRUMBS='; then ENDED="SETUP: breadcrumbs are set in an off arm"; fi  # 0393\n'''),
        ('''per frame GPU busy %.2f ms, host prepare %.2f ms (filter %.2f), %.1f ms between flips\\n", n, G/n, P/n, FL/n, S/n}' > "$R/$TAG-0358.txt"\n''',
         '''per frame GPU busy %.2f ms, host prepare %.2f ms (filter %.2f), %.1f ms between flips\\n", n, G/n, P/n, FL/n, S/n}' > "$R/$TAG-0358.txt"\n'''
         '''  nice -n 19 grep -a "^frame profile" "$J" > "$R/$TAG-frames.txt"  # 0393: for ana0393.py\n'''
         '''  nice -n 19 grep -a "breadcrumbs (exp 0277)" "$J" > "$R/$TAG-bc.txt"  # 0393: the arm's proof and its health\n'''),
        ('''X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)\n''',
         '''X=$(grep -a "^launcher exit" "$R/$TAG-launch.out" | tail -1)\n'''
         '''# 0393: the journal shows the arm: no breadcrumb line with them off, their level and health lines with them on.\n'''
         '''if [ "$JOK" = 1 ]; then\n'''
         '''  if [ "$BCLEVEL" = 0 ]; then [ ! -s "$R/$TAG-bc.txt" ] || FAIL="$FAIL breadcrumb lines in an off arm;"\n'''
         '''  elif ! grep -q " inserted, " "$R/$TAG-bc.txt" || ! grep -q "level $BCLEVEL, " "$R/$TAG-bc.txt"; then FAIL="$FAIL no level $BCLEVEL breadcrumb lines;"; fi\n'''
         '''fi\n'''),
    ], n)


def run():
    n = 'run0393.sh'
    t = src('run0388.sh')
    t = span(t, '# BC5 exp 0393 on the box: the lock, the run', '# changes shared files; the runs use a private copy of a named snapshot.\n', r'''# BC5 exp 0393 on the box: the lock, the run and its cleanup for one step, the private build or one arm's run. Called by
# go0393.sh only. Made from exp 0388's run0388.sh by mk0393.py.
#   run0393.sh claim <tag> <deadline epoch>       over stdin; the atomic claim, prints TOK=
#   run0393.sh start <token> <tag> <deadline>     detaches `run` under its own time limit
#   run0393.sh run <token> <tag> <deadline>       the step; always ends by releasing its own lock
#   run0393.sh stream <token> <secs>              the kernel log, until the token's lock is gone
#   run0393.sh release <token>                    over stdin; recovery: stops this token's processes, frees its lock
# A tag build* compiles the one unit with exp 0277's edits and links it from the shared normal build's objects, nice 19, no
# emulator, no GPU. Any other tag is one s6n0393.sh run. Claim as in coordination/d19/d19box.sh: the line appears by a hard
# link, which cannot replace an existing lock. One token per step, no second claimant. Only processes with this token in
# their environment are ever signalled. Nothing here changes shared files; the runs use a private copy of a named snapshot.
''', n)
    t = span(t, '# The pins under the lock, immediately before the launch.\n', '# The copy in C and from inside it.', r'''# The pins under the lock, immediately before the launch.
inputs_ok() {
    local v
    . "$S/pins0393.env" || die "no pins"
    for v in BINARY LAUNCHER RUN_ENV ROUTE_SAVES MENU_CMD INPUT_CFG LEARNED; do
        case "${!v:-FILL}" in FILL) die "the pin $v is not filled" ;; esac
    done
    BIN=$EX/kyty_emulator  # 0393: the private test build
    [ "$(m "$BIN")" = "$BINARY" ] || die "the binary is not $BINARY"
    [ "$(m "$W/play-pkg.sh")" = "$LAUNCHER" ] || die "the launcher is not $LAUNCHER"
    [ "$(m "$W/bc5-run.env")" = "$RUN_ENV" ] || die "bc5-run.env is not $RUN_ENV"
    [ "$(m "$W/exp0203/o2-continue.cmd")" = "$MENU_CMD" ] || die "the menu script differs"
    [ "$(m "$W/input.cfg")" = "$INPUT_CFG" ] || die "input.cfg differs"
    [ "$(m "$W/direct-learned-pkg.txt")" = "$LEARNED" ] || die "the learned file differs"
    [ "$(cd "$W/exp0196" && find saves-before-152617 -type f | wc -l)" -gt 0 ] || die "no route saves"
    [ "$(route_sum)" = "$ROUTE_SAVES" ] || die "the route saves are not $ROUTE_SAVES"
}
# The private binary. The shared binary's md5 is read before and after; nothing shared is written.
do_build() {
    local K=$HOME/src/KytyPlus B=$W/kytyplus-build T s0 rc n
    T=$K/src/libs/bc5LleAgc.cpp
    [ "$(m "$T")" = "$TREE_MD5" ] || die "the tree's bc5LleAgc.cpp is not $TREE_MD5"
    s0=$(m "$B/src/kyty_emulator")
    { echo "tree bc5LleAgc.cpp $(stat -c '%y' "$T") md5 $TREE_MD5"
      echo "shared binary $(stat -c '%y %s' "$B/src/kyty_emulator") md5 $s0"
      echo "shared object $(stat -c '%y' "$B/src/CMakeFiles/kyty_emulator.dir/libs/bc5LleAgc.cpp.o")"; } > "$R/$TAG-inputs.txt"
    "${PY[@]}" "$S/patch0393.py" "$T" "$EX/src/bc5LleAgc.bc.cpp" "$R/patch_0393.diff" || die "the patch failed"
    distrobox enter ubuntu -- sh -c "cd '$B' && ninja -t compdb -x" > "$EX/compdb.json" 2> "$R/compdb.err" || die "compdb failed"
    grep -q '"command": "[^"]* @' "$EX/compdb.json" && die "the compdb still names response files"
    grep -q '"output": "src/kyty_emulator"' "$EX/compdb.json" || die "no link command in the compdb"
    ( cd "$EX" && distrobox enter ubuntu -- python3 -I "$S/build0393.py" "$EX/compdb.json" ) > "$R/$TAG-build.out" 2>&1
    rc=$?
    [ "$(m "$B/src/kyty_emulator")" = "$s0" ] || die "the shared binary changed during the build"
    [ "$rc" = 0 ] && [ -x "$EX/kyty_emulator" ] || die "the build failed, rc $rc, see $R/$TAG-build.out"
    n=$(strings "$EX/kyty_emulator" | grep -c "exp 0277")
    [ "$n" -gt 0 ] || die "no exp 0277 strings in the binary"
    echo "RESULT $TAG binary $(m "$EX/kyty_emulator") shared $s0 strings $n warnings $(grep -c "warning:" "$R/$TAG-build.out")" > "$R/$TAG-result.txt.$$" && mv -f "$R/$TAG-result.txt.$$" "$R/$TAG-result.txt" || die "the result could not be written"
}
# The copy in C and from inside it.''', n)
    t = span(t, '# The copy in C and from inside it.', '| md5sum | cut -c1-16); }\n',
             '''# The copy in C and from inside it.\nroute_sum() { (cd "$W/exp0196/saves-before-152617" && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-16); }\n''', n)
    t = span(t, '    "${PY[@]}" "$S/check0393.py" run', '|| die "the result could not be written"\n',
             '''    echo "RESULT $TAG runner $rc verdict $(head -1 "$R/$TAG-verdict.txt" 2> /dev/null)" > "$R/$TAG-result.txt.$$" && mv -f "$R/$TAG-result.txt.$$" "$R/$TAG-result.txt" || die "the result could not be written"\n''', n)
    return edit(t, [
        ('# for its own kill (30), reap (30), check and release. A run needs 390 s, plus the claim and the send.\n',
         '# for its own kill (30), reap (30) and release. A run needs 690 s, plus the claim and the send.\n'),
        ('SECS=180; RUN_MIN=430; RUN_CAP=280; KEEP=150;', 'SECS=420; RUN_MIN=720; RUN_CAP=540; KEEP=150;'),
        ('HELD=0; LOCKLINE=""; STOPWHY=""; RUNP=""\n', 'HELD=0; LOCKLINE=""; STOPWHY=""; RUNP=""\nTREE_MD5=29b3d8c602c92c84fa7731d3902fcc48  # main\'s unit at 5b22f700\n'),
        ('write_roots() { echo "$EX" "$E" "$R" "$S" "$E/wd"', 'write_roots() { echo "$EX" "$EX/src" "$EX/obj" "$E" "$R" "$S" "$E/wd"'),
        ('    local tag=$1 fix=$2 dl=$3\n', '    local tag=$1 dl=$2\n'),
        ('    case "$fix" in off) ;; *) die "every 0393 run has the fix off" ;; esac\n', ''),
        ('LOCKLINE="top exp0393 | token $TOK | $tag fix $fix, RT on, until', 'LOCKLINE="tcp exp0393 | token $TOK | $tag breadcrumb cost, RT on, until'),
        ('    for p in "$EX" "$E" "$R" "$S"; do\n', '    for p in "$EX" "$EX/src" "$EX/obj" "$E" "$R" "$S"; do\n'),
        ('queue "top exp0393 | done: $TAG token $TOK | $(date \'+%F %T\')"', 'queue "tcp exp0393 | done: $TAG token $TOK | $(date \'+%F %T\')"'),
        ('    load_tok "$1"; TAG=$2; FIX=$3; DL=$4\n', '    load_tok "$1"; TAG=$2; DL=$3\n'),
        ('    free_box\n    inputs_ok\n    hook after-inputs\n',
         '    free_box\n    case "$TAG" in build*) do_build; return ;; esac\n    inputs_ok\n    hook after-inputs\n'),
        ('    local left=$((DL - $(now) - KEEP)) cap=$RUN_CAP rc p c\n', '    local left=$((DL - $(now) - KEEP)) cap=$RUN_CAP rc p\n'),
        ('''    D19_OWNER=$TOK D19_BIN=$BIN BC5_0380_WANT=${NORMAL:0:8} E0393_LOCKLINE=$LOCKLINE \\\n''',
         '''    D19_OWNER=$TOK D19_BIN=$BIN BC5_0393_WANT=${BINARY:0:8} E0393_LAUNCHER=$LAUNCHER E0393_LOCKLINE=$LOCKLINE \\\n'''),
        ('bash "$S/s6n0393.sh" "$TAG" "$SECS" "$FIX" > "$R/$TAG-runner.out" 2>&1 &', 'bash "$S/s6n0393.sh" "$TAG" "$SECS" > "$R/$TAG-runner.out" 2>&1 &'),
        ('    claim) do_claim "${2:-}" "${3:-}" "${4:-}" ;;\n', '    claim) do_claim "${2:-}" "${3:-}" ;;\n'),
        ('        l=$(($5 - $(now) - OUTER_END))\n', '        l=$(($4 - $(now) - OUTER_END))\n'),
        ('bash "$S/run0393.sh" run "$2" "$3" "$4" "$5" < /dev/null > "$R/$3-box.out" 2>&1 &', 'bash "$S/run0393.sh" run "$2" "$3" "$4" < /dev/null > "$R/$3-box.out" 2>&1 &'),
        ('    run) do_run "$2" "$3" "$4" "$5" ;;\n', '    run) do_run "$2" "$3" "$4" ;;\n'),
        ('queue "top exp0393 | released: token $TOK', 'queue "tcp exp0393 | released: token $TOK'),
    ], n)


def go():
    n = 'go0393.sh'
    t = src('go0388.sh')
    return edit(t, [
        ('# BC5 exp 0393 from the laptop: one fight run. No retry of any step.\n# usage: go0393.sh <tag> <on|off> <deadline epoch>\n',
         '# BC5 exp 0393 from the laptop: one step, the build or one run (made from go0388.sh by mk0393.py). No retry of any step.\n# usage: go0393.sh <build|tag> <deadline epoch>\n'),
        ('TAG=${1:?tag}; FIX=${2:?on or off}; DL=${3:?deadline epoch}\n', 'TAG=${1:?tag}; DL=${2:?deadline epoch}\n'),
        ('FILES="run0393.sh s6n0393.sh prestart0393.sh check0393.py d19gates.py d19manifest.py pins0393.env"  # the private binary is pinned there\n',
         'FILES="run0393.sh s6n0393.sh prestart0393.sh patch0393.py patch0277.py build0393.py pins0393.env"  # the private binary is pinned there\n'),
        ('out=$(over claim "$TAG" "$FIX" "$DL"); rc=$?\n', 'out=$(over claim "$TAG" "$DL"); rc=$?\n'),
        ('if ! box "bash ~/$S/run0393.sh start $TOK $TAG $FIX $DL" > /dev/null;', 'if ! box "bash ~/$S/run0393.sh start $TOK $TAG $DL" > /dev/null;'),
    ], n)


def prestart():
    n = 'prestart0393.sh'
    return edit(src('prestart0388.sh'), [
        ("# The name list is d19manifest.py's FORBIDDEN; test_prestart.sh compares them.\n",
         "# The name list is exp 0388's d19manifest.py FORBIDDEN, unchanged.\n"),
    ], n)


write('s6n0393.sh', s6n())
write('run0393.sh', run())
write('go0393.sh', go())
write('prestart0393.sh', prestart())
