#!/usr/bin/env python3
"""BC5 experiment 0417: the swap script for the K1r fold, the first swap that also changes the SHARED backend archive
(the top session's procedure of 2026-11-13; the swap itself is put to the maintainer by the top session, this script
is only prepared). Derived from the integration's int0416.sh by exact replacements, each asserted.

  int0417.sh  patch 0001 4651d1d3 -> S_NEW (0001-new12.patch, tree12.md5) in ~/src/KytyPlus;
              the shared backend source ~/bc5-work/d19/export/backend gets exp 0412's two files (include/bc5/direct.hpp
              a9fcb26b -> 2497a4ce, src/direct.cpp 51279eae -> b183516e) and the shared archive is rebuilt in its own
              build directory ~/bc5-work/backend-ubuntu (75e30335 -> ed63df2f expected: the private build of the same
              source with the same options gave ed63df2f twice); then both shared emulators are rebuilt.
              Kept before anything is touched: both binaries, the archive (in the swap directory AND beside the
              archive as libbc5_backend.a.before-0417) and the two source files, each read back by md5.
              A failure after that restores the archive, the two source files, both binaries and the tree, and CHECKS
              the restore; if it does not read back the lock is KEPT and the state is printed.
              The restore copies the kept archive back; the backend's build directory then holds newer objects, and
              a rebuild of the restored source reproduces 75e30335 (checked on 2026-11-13 in the private chain).
usage: mkswap0417.py <repo root> <out dir>"""
import sys

root, out = sys.argv[1:3]
s = open(root + "/experiments/0416-emufive-switches/integration/int0416.sh", encoding="utf-8", newline="").read()
assert "\r" not in s


def rep(old, new, n=1):
    global s
    assert s.count(old) == n, (old[:70], s.count(old), n)
    s = s.replace(old, new)


rep("# BC5 integration of 2026-11-13 (the maintainer through the top session:",
    "# BC5 exp 0417, the K1r fold: patch 0001 4651d1d3 -> S_NEW AND the shared backend archive 75e30335 -> ed63df2f (exp\n"
    "# 0412's two backend files). Made from the integration's swap script by mkswap0417.py; see that file for the procedure.\n"
    "# NOT to be run on a general release: the top session puts this swap to the maintainer first.\n"
    "# usage: S_NEW=<patch md5> S_PRIV_N=<private normal md5> S_PRIV_L=<private lean md5> int0417.sh\n"
    "# BC5 integration of 2026-11-13 (the maintainer through the top session:")
rep("PIN_NORMAL=ce0e3b928b6d1d1d47fc035c13e8cee3; PIN_LEAN=35ec3341be46ffd7013db8ffa9a4b2f5; PIN_ARCHIVE=75e30335; PIN_OLD=01abfc0c",
    "PIN_NORMAL=fe0933c0ad7c0d9a86194bc0a7598a06; PIN_LEAN=711d6c0d33d171bcb4749903bd607aa2; PIN_ARCHIVE=75e30335; PIN_OLD=4651d1d3\n"
    "PIN_ARCH_FULL=75e303357610fee8d1d205bdc88c031c; NEW_ARCHIVE=ed63df2f   # the archive before, in full; after, as the private build gave it\n"
    "BSRC=$W/d19/export/backend; BBLD=$W/backend-ubuntu; H=$BSRC/include/bc5/direct.hpp; C=$BSRC/src/direct.cpp\n"
    "H_OLD=a9fcb26b; C_OLD=51279eae; H_NEW=2497a4ce; C_NEW=b183516e; ARCH_TOUCHED=0")
rep('0001-new9.patch"', '0001-NEW.patch"', 5)
rep('0001-new7.patch', '0001-new9.patch', 5)
rep('0001-NEW.patch"', '0001-new12.patch"', 5)
rep("tree9.md5", "tree12.md5", 6)
rep("before-0416", "before-0417", 10)
rep("-0416.out", "-0417.out", 2)
rep("after-0416.txt", "after-0417.txt")
rep("int0416", "int0417", 7)
rep("    local ok=1\n",
    "    local ok=1\n"
    "    if [ \"$ARCH_TOUCHED\" = 1 ]; then   # exp 0417: the backend source and the archive first\n"
    "        cp -p \"$I/direct.hpp.before-0417\" \"$H\" || ok=0; cp -p \"$I/direct.cpp.before-0417\" \"$C\" || ok=0\n"
    "        cp -p \"$I/libbc5_backend.a.before-0417\" \"$ARCH\" || ok=0\n"
    "        [ \"$(m8 \"$H\")\" = \"$H_OLD\" ] && [ \"$(m8 \"$C\")\" = \"$C_OLD\" ] || { echo \"restore: the backend source reads $(m8 \"$H\") $(m8 \"$C\"), not $H_OLD $C_OLD\"; ok=0; }\n"
    "        [ \"$(m \"$ARCH\")\" = \"$PIN_ARCH_FULL\" ] || { echo \"restore: the archive reads $(m \"$ARCH\"), not $PIN_ARCH_FULL\"; ok=0; }\n"
    "    fi\n")
rep('[ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || stop',
    '[ "$(m "$ARCH")" = "$PIN_ARCH_FULL" ] && [ "$(m8 "$H")" = "$H_OLD" ] && [ "$(m8 "$C")" = "$C_OLD" ] || stop "the shared archive or backend source is not the pins: $(m "$ARCH") $(m8 "$H") $(m8 "$C")"\n'
    '[ "$(m8 "$HERE/backend-direct.hpp")" = "$H_NEW" ] && [ "$(m8 "$HERE/backend-direct.cpp")" = "$C_NEW" ] && [ -f "$BBLD/build.ninja" ] || stop "the kit\'s backend files are not $H_NEW / $C_NEW, or $BBLD has no build.ninja"\n'
    '[ "$(m "$NB")" = "$PIN_NORMAL" ] && [ "$(m "$LB")" = "$PIN_LEAN" ] && [ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || stop')
rep('claim "integration 0416+0415+0412: patch 0001 $S_NEW into the shared normal and lean, CPU only" 40',
    'claim "exp 0417 K1r fold: patch 0001 $S_NEW and the backend archive into the shared builds, CPU only" 45')
rep('cp -p "$NB" "$I/kyty_emulator.before-0417" && cp -p "$LB" "$I/kyty_emulator-lean.before-0417" || { release; stop "copy failed"; }\n',
    'cp -p "$NB" "$I/kyty_emulator.before-0417" && cp -p "$LB" "$I/kyty_emulator-lean.before-0417" || { release; stop "copy failed"; }\n'
    '# exp 0417: the archive (twice: in the swap directory and beside itself) and the two backend source files\n'
    'cp -p "$ARCH" "$I/libbc5_backend.a.before-0417" && cp -p "$ARCH" "$ARCH.before-0417" && cp -p "$H" "$I/direct.hpp.before-0417" && cp -p "$C" "$I/direct.cpp.before-0417" || { release; stop "copying the archive or the backend source failed"; }\n'
    '[ "$(m "$I/libbc5_backend.a.before-0417")" = "$PIN_ARCH_FULL" ] && [ "$(m "$ARCH.before-0417")" = "$PIN_ARCH_FULL" ] && [ "$(m8 "$I/direct.hpp.before-0417")" = "$H_OLD" ] && [ "$(m8 "$I/direct.cpp.before-0417")" = "$C_OLD" ] || { release; stop "the archive or source copies do not read back"; }\n')
rep('build normal "$W/kytyplus-build"\n',
    '# exp 0417: the backend first. The two files, then the archive in its own build directory.\n'
    'ARCH_TOUCHED=1\n'
    'cp "$HERE/backend-direct.hpp" "$H" && cp "$HERE/backend-direct.cpp" "$C" || restore "putting the backend files in"\n'
    '[ "$(m8 "$H")" = "$H_NEW" ] && [ "$(m8 "$C")" = "$C_NEW" ] || restore "the backend files do not read back"\n'
    'pgrep \'^kyty_emulator\' > /dev/null && restore "an emulator started before the backend build"\n'
    'echo "== $(date +%T) backend"\n'
    'distrobox enter ubuntu -- sh -c "cd \'$BBLD\' && nice -n 19 ninja" < /dev/null > "$I/build-backend-0417.out" 2>&1 || { grep -m5 "error:" "$I/build-backend-0417.out"; restore "the backend build"; }\n'
    '[ "$(m8 "$ARCH")" = "$NEW_ARCHIVE" ] || restore "the rebuilt archive is $(m8 "$ARCH"), not $NEW_ARCHIVE (the private build\'s)"\n'
    'echo "backend archive: $(m "$ARCH") (was $PIN_ARCH_FULL, kept as $ARCH.before-0417)"\n'
    'build normal "$W/kytyplus-build"\n')
rep('[ "$(m8 "$ARCH")" = "$PIN_ARCHIVE" ] || restore "the archive changed"', '[ "$(m8 "$ARCH")" = "$NEW_ARCHIVE" ] || restore "the archive changed during the emulator builds"')
rep("KYTY_BC5_APR_POSIX BC5_GUARD_MAP_RULE", "KYTY_BC5_APR_POSIX KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1R BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_GUARD_MAP_RULE")
rep("undo: both binaries from $I/*.before-0417, the tree by reversing 0001-new9 and applying 0001-new7 (then rebuild)",
    "undo: the archive from $ARCH.before-0417 and the two backend files from $I/direct.*.before-0417, both binaries from $I/*.before-0417, the tree by reversing 0001-new12 and applying 0001-new9 (then rebuild the backend and both emulators)")
open(out + "/int0417.sh", "w", encoding="utf-8", newline="\n").write(s)
print("int0417.sh ok")
