#!/usr/bin/env python3
"""BC5 experiment 0428: derive run0428f.sh from exp 0425's run0425f.sh (md5 pinned below). Every replacement must match
exactly the stated number of times.
    mkrun0428.py <run0425f.sh> <run0428f.sh>
Changes:
  - everything written lands in ~/bc5-work/exp0428/n; exp 0425's named snapshot and the 14:50 record's gameplay are only read;
  - JobArenaFix stays as the shared input.cfg has it (exp 0425 forced it off to measure the crash); RT on as before;
  - lock and queue lines say exp 0428;
  - the exposure field: exp 0428's switch lines and its last counters line (tag w428c)."""
import hashlib, sys

src, dst = sys.argv[1], sys.argv[2]
b = open(src, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "0591b743", "run0425f.sh is not the box copy 0591b743"
s = b.decode("utf-8")
assert "\r" not in s


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


sub("N=$W/exp0425/n; R=$N/raw;", "N=$W/exp0428/n; R=$N/raw;")
sub('LINE="exp 0425 | private run $TAG ($ARM, cap $SECS s), the second title on exp0425/${WANT:0:8}, token $T"',
    'LINE="exp 0428 | private run $TAG ($ARM, cap $SECS s), the second title on exp0428/${WANT:0:8}, token $T"')
sub('printf \'%s\\n\' "exp 0425 | claimed: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"',
    'printf \'%s\\n\' "exp 0428 | claimed: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"')
sub('printf \'%s\\n\' "exp 0425 | released: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"',
    'printf \'%s\\n\' "exp 0428 | released: private run $TAG, token $T | $(date \'+%F %T\')" >> "$W/BOX-QUEUE"')
sub('{ grep -v -i "^RayTracing\\.TITLE2=\\|^JobArenaFix\\.TITLE2=" "$W/input.cfg"; echo "RayTracing.TITLE2=on"; echo "JobArenaFix.TITLE2=off"; } > "$CFG" || exit 1',
    '{ grep -v -i "^RayTracing\\.TITLE2=" "$W/input.cfg"; echo "RayTracing.TITLE2=on"; } > "$CFG" || exit 1  # exp 0428: JobArenaFix as the shared input.cfg has it')
sub("-e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0425/n/wd  \\# exp 0425: the private working directory (its own _SaveData)#'",
    "-e 's#^cd ~/bc5-work$#cd ~/bc5-work/exp0428/n/wd  \\# exp 0428: the private working directory (its own _SaveData)#'")
sub("export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0425/n/wd/_SaveData-pkg-play  \\# exp 0425: private#'",
    "export KYTY_BC5_SAVEDATA_DIR=$HOME/bc5-work/exp0428/n/wd/_SaveData-pkg-play  \\# exp 0428: private#'")
sub("export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0425/n/direct-learned-pkg.txt  \\# exp 0425: a private copy#'",
    "export BC5_DIRECT_LEARNED=$HOME/bc5-work/exp0428/n/direct-learned-pkg.txt  \\# exp 0428: a private copy#'")
sub('pgrep -f "exp0425/n/play-pkg-0425f.sh"', 'pgrep -f "exp0428/n/play-pkg-0425f.sh"')
i = s.index('EXPO="fix-off')
j = s.index("\n", i)
s = s[:i] + ('EXPO="w428-switch [$(grep -a -m1 \'tag w428)\' "$PL" | cut -c1-140)] aq424-switch [$(grep -a -m1 \'tag aq424)\' "$PL" | cut -c1-120)] '
             'w428c-last [$(grep -a \'tag w428c\' "$PL" | tail -1 | cut -c1-700)]"') + s[j:]
sub('echo "catch: $(grep -a \'exp 0425 catch\' "$PL" | tail -1 | cut -c1-300)" >> "$R/$TAG-start.txt"\n', "")
s = "#!/usr/bin/env bash\n# BC5 exp 0428: derived by mkrun0428.py from exp 0425's run0425f.sh (see mkrun0428.py for the changes).\n" + s.split("\n", 1)[1]
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("wrote", dst)
