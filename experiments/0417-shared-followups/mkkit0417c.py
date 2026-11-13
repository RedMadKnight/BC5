#!/usr/bin/env python3
"""BC5 experiment 0417, the K1r fold (candidate patch 0001 26ef195c): the box scripts for the PRIVATE build.
  p0417c.sh   from p0417b.sh (this directory) by exact replacements: the private tree goes from 0001-new11 (c55174b1)
              to 0001-new12 (P_NEW12). New: a PRIVATE backend. exp 0412's K1r and probe need two backend files changed
              (include/bc5/direct.hpp a9fcb26b -> 2497a4ce, src/direct.cpp 51279eae -> b183516e), so the shared source
              ~/bc5-work/d19/export/backend is copied to exp0413/p/backend-src, the two files are put in, the archive
              is built in exp0413/p/backend-build as exp 0412's mk0412zb.sh builds its own (same cmake options), the
              backend's own tests are built and run on that copy when the container can build them, and both emulator
              builds are configured again against the private paths. The shared source and the shared archive
              (75e30335) are only read.
  cpu0417c.sh from cpu0417.sh: exp 0412's five CPU tests added.
usage: mkkit0417c.py <this directory> <out dir>"""
import sys

here, out = sys.argv[1:3]


def derive(src, dst, changes):
    s = open(here + "/" + src, encoding="utf-8", newline="").read()
    assert "\r" not in s
    for old, new, n in changes:
        assert s.count(old) == n, (src, old[:70], s.count(old), n)
        s = s.replace(old, new)
    open(out + "/" + dst, "w", encoding="utf-8", newline="\n").write(s)
    print(dst, "ok")


BACKEND = r'''# exp 0417 (the K1r fold): the PRIVATE backend. The shared source copied, exp 0412's two files put in, its own build dir.
PB=$P/backend-src; BB=$P/backend-build; BT=$P/backend-test
[ "$(m "$BSRC/include/bc5/direct.hpp")" = a9fcb26b ] && [ "$(m "$BSRC/src/direct.cpp")" = 51279eae ] || die "the shared backend source is not a9fcb26b / 51279eae"
[ "$(m "$HERE/backend-direct.hpp")" = 2497a4ce ] && [ "$(m "$HERE/backend-direct.cpp")" = b183516e ] || die "the kit's backend files are not 2497a4ce / b183516e"
rm -rf "$PB" "$BB" "$BT" && cp -a "$BSRC" "$PB" || die "cannot copy the backend source"
cp "$HERE/backend-direct.hpp" "$PB/include/bc5/direct.hpp" && cp "$HERE/backend-direct.cpp" "$PB/src/direct.cpp" || die "cannot put the two backend files in"
[ "$(diff -rq "$BSRC" "$PB" | grep -c .)" = 2 ] || die "the private backend differs from the shared one by more than direct.hpp and direct.cpp: $(diff -rq "$BSRC" "$PB" | head -4 | tr '\n' ' ')"
# The recipe checked first (exp 0412's author: it was never shown that these options reproduce the shared archive):
# the UNTOUCHED shared source built the same way, its archive compared with the shared one. Informational.
BR=$P/backend-ref
rm -rf "$BR"
if distrobox enter ubuntu -- cmake -S "$BSRC" -B "$BR" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
       -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF < /dev/null > "$BR.configure.log" 2>&1 &&
   distrobox enter ubuntu -- sh -c "cd '$BR' && nice -n 19 ninja" < /dev/null > "$BR.build.log" 2>&1 && [ -f "$BR/libbc5_backend.a" ]; then
    echo "recipe check: the untouched shared backend source built with these options gives $(m "$BR/libbc5_backend.a"); the shared archive is $(m "$ARCH") ($([ "$(m "$BR/libbc5_backend.a")" = "$(m "$ARCH")" ] && echo "the SAME: a rebuild reproduces it" || echo "DIFFERENT: a rollback must restore the kept archive file, not rebuild"))"
else
    echo "recipe check: the untouched shared backend source did not build with these options ($(grep -m1 -i error "$BR.configure.log" "$BR.build.log" 2> /dev/null | cut -c1-160))"
fi
echo "== $(date +%T) backend"
distrobox enter ubuntu -- cmake -S "$PB" -B "$BB" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
    -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=OFF < /dev/null > "$BB.configure.log" 2>&1 || die "backend configure: $(tail -3 "$BB.configure.log" | tr '\n' ' ' | cut -c1-300)"
distrobox enter ubuntu -- sh -c "cd '$BB' && nice -n 19 ninja" < /dev/null > "$BB.build.log" 2>&1 || { grep -m6 -E "error:" "$BB.build.log" | cut -c1-240; die "the backend build failed"; }
[ -f "$BB/libbc5_backend.a" ] || die "no private backend archive"
echo "private backend archive $(md5sum < "$BB/libbc5_backend.a" | cut -d' ' -f1) (the shared one $(m "$ARCH") untouched; exp 0412's private one was ed63df2f)"
# the backend's own tests on the private copy (CPU only; they never submit: CLAUDE.md hard rule 5). A container that
# cannot build them is reported, not fatal.
if distrobox enter ubuntu -- cmake -S "$PB" -B "$BT" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++ \
       -DBC5_WITH_AMDGPU=ON -DBC5_BUILD_TESTS=ON < /dev/null > "$BT.configure.log" 2>&1 &&
   distrobox enter ubuntu -- sh -c "cd '$BT' && nice -n 19 ninja" < /dev/null > "$BT.build.log" 2>&1; then
    if distrobox enter ubuntu -- sh -c "cd '$BT' && ctest --output-on-failure" < /dev/null > "$BT.ctest.log" 2>&1; then echo "backend tests: PASS: $(grep -m1 'tests passed' "$BT.ctest.log" | cut -c1-120)"
    else echo "backend tests: FAILED: $(grep -m3 -i 'failed\|\*\*\*' "$BT.ctest.log" | tr '\n' ' ' | cut -c1-300)"; die "the backend's tests failed on the private copy"; fi
else
    echo "backend tests: NOT RUN (the test build did not configure or compile here: $(grep -m2 -i 'error' "$BT.configure.log" "$BT.build.log" 2> /dev/null | tr '\n' ' ' | cut -c1-240))"
fi
BSRC=$PB; BBLD=$BB   # both emulator builds are configured against the private backend below
'''

derive("p0417b.sh", "p0417c.sh", (
    ("# p0417b (exp 0417, the next patch change):",
     "# p0417c (exp 0417, the K1r fold): the private tree goes from 0001-new11 (c55174b1) to 0001-new12 (P_NEW12); a PRIVATE\n"
     "# backend archive is built from a copy of the shared source with exp 0412's two files, and both emulator builds are\n"
     "# configured against it. usage: P_NEW12=<patch md5> bash p0417c.sh\n"
     "# p0417b (exp 0417, the next patch change):", 1),
    ('[ "$(m "$HERE/0001-new10.patch")" = 33bddfa1 ] && [ "$(m "$HERE/0001-new11.patch")" = "${P_NEW11:?the new patch md5}" ]',
     '[ "$(m "$HERE/0001-new11.patch")" = c55174b1 ] && [ "$(m "$HERE/0001-new12.patch")" = "${P_NEW12:?the new patch md5}" ]', 1),
    ('claim "exp 0417: private rebuild of the next patch change under exp0413/p, CPU only" 40',
     'claim "exp 0417: private rebuild of the K1r fold (tree and a private backend) under exp0413/p, CPU only" 40', 1),
    ('done < "$HERE/tree10.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not 33bddfa1\'s (the hook\'s gate must be 0)"',
     'done < "$HERE/tree11.md5"\n[ "$bad" = 0 ] || die "$bad files of the private tree are not c55174b1\'s"', 1),
    ('git apply -R --whitespace=nowarn "$HERE/0001-new10.patch" && git apply --whitespace=nowarn "$HERE/0001-new11.patch"',
     'git apply -R --whitespace=nowarn "$HERE/0001-new11.patch" && git apply --whitespace=nowarn "$HERE/0001-new12.patch"', 1),
    ('done < "$HERE/tree11.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"',
     'done < "$HERE/tree12.md5"\n[ "$bad" = 0 ] || die "$bad files differ from the laptop\'s tree"', 1),
    ('echo "tree: $(wc -l < "$HERE/tree11.md5") patched files match the laptop\'s (0001-new11)"\n',
     'echo "tree: $(wc -l < "$HERE/tree12.md5") patched files match the laptop\'s (0001-new12)"\n' + BACKEND, 1),
    ('    [ -f "$d/build.ninja" ] || die "no build dir $d (run p0413.sh first)"\n',
     '    [ -f "$d/build.ninja" ] || die "no build dir $d (run p0413.sh first)"\n'
     '    cfg "$d" "$x" || die "configure $v against the private backend: $(tail -2 "$d.configure.log" | tr \'\\n\' \' \' | cut -c1-240)"\n', 1),
    ("KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT", "KYTY_BC5_ANON_SYNC BC5_DIRECT_HEAP_GUARDS BC5_GUARD_K1_STAT BC5_GUARD_K1R BC5_FAULT_RECORD BC5_R3_EOP_STAT BC5_DIRECT_RESET_LABELS_ADD", 1),
))

derive("cpu0417.sh", "cpu0417c.sh", (
    ("# BC5 exp 0417, the next patch change (made from the integration's cpu0416.sh by mkkit0417b.py):",
     "# BC5 exp 0417, the K1r fold (cpu0417.sh plus exp 0412's five tests: firstfail, rlabels, k1r, saveguard; maprule was there).\n"
     "# BC5 exp 0417, the next patch change (made from the integration's cpu0416.sh by mkkit0417b.py):", 1),
    ('gxx maprule0412 -Werror -I "$HERE" && run maprule0412 "$T/maprule0412"\n',
     'gxx maprule0412 -Werror -I "$HERE" && run maprule0412 "$T/maprule0412"\n'
     'gxx firstfail0412 -Werror -I "$HERE" && run firstfail0412 "$T/firstfail0412"\n'
     'gxx rlabels0412 -Werror -I "$HERE" && run rlabels0412 "$T/rlabels0412"\n'
     'gxx k1r0412 -Werror -I "$HERE" && run k1r0412 "$T/k1r0412"\n'
     'mkdir -p "$T/sgdir" && gxx saveguard0412 -Werror -pthread -I "$HERE" && run saveguard0412 "$T/saveguard0412" "$T/sgdir"\n', 1),
    ('"test0415anon:31 of 31" "maprule0412:15281 of 15281"; do',
     '"test0415anon:31 of 31" "maprule0412:15281 of 15281" "firstfail0412:101506 of 101506" "rlabels0412:4970 of 4970" "k1r0412:17742 of 17742" "saveguard0412:178 of 178"; do', 1),
    ('echo "cpu0417: $fails failed"', 'echo "cpu0417c: $fails failed"', 1),
))
