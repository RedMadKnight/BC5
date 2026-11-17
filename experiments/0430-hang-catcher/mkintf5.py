#!/usr/bin/env python3
"""BC5 exp 0430: derives int0430f5.sh (the swap of F5, the precise form) from int0430.sh. Every replacement must match
exactly once. usage: mkintf5.py int0430.sh int0430f5.sh"""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()


def r(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a)
    s = s.replace(a, b)


r(s[s.index("# BC5 exp 0430, the swap of the hang fix"):s.index("set -u\n")],
  "# BC5 exp 0430, the swap of F5, the precise form (int0430.sh adapted by mkintf5.py, 2026-11-17): BC5_DIRECT_XQ_PRECISE\n"
  "# (on unless \"0\") on top of the shared tree as it is when it runs (the hang fix F3 + F4 swapped at 07:10, then exps 0431\n"
  "# and 0429). Only src/libs/bc5LleAgc.cpp changes (b8afba59 -> 574301e4, mkf5.py); the backend is not touched. The top\n"
  "# session's gate of 2026-11-17 10:50 (P: no GPU hang or fault in any run, mean >= S's mean - 1 flips/s).\n"
  "#   1. checks: no emulator; the shared tree's diff, normal and lean are the pins given (read just before); units pinned\n"
  "#   2. the lock (chain_claim, one line); copies under ~/bc5-work/exp0430/swapf5 (*.before-0430), read back; pins file\n"
  "#   3. mkf5.py on ~/src/KytyPlus; the new patch = git diff f266548; checks on it (exp 0372 lines and every guarded count\n"
  "#      as before, the pad_audio_route header, the same file list)\n"
  "#   4. normal and lean rebuilt in place (ninja kyty_emulator, nice 19); the backend archive must stay the same\n"
  "#   5. strings: both builds gain exactly BC5_DIRECT_XQ_PRECISE and lose none\n"
  "# Any failure after step 2 runs undo0430.sh with X=swapf5 (units, binaries, backend files and archive back, by md5).\n"
  "# usage (on the box, in ~/bc5-work/exp0430): PIN_PIN=<tree diff md5> NORMAL_PIN=<md5> LEAN_PIN=<md5> U2_PIN=<md5> bash int0430f5.sh\n")
r("X=$W/exp0430/swap\n", "X=$W/exp0430/swapf5\n")
r("# F4 (the kernel orders the waiter): the shared backend source gets this experiment's two files (be/), the shared\n"
  "# archive is rebuilt from it in backend-ubuntu, and both KytyPlus builds relink with it\n", "# the backend: only copied and checked, never rebuilt (F4's archive since 07:10)\n")
r("U3_OLD=aeec4c09; U4_OLD=e96e5c73; ARCH_OLD=9aab722c", "U3_OLD=5016c2a4; U4_OLD=24988c4e; ARCH_OLD=1423af83")
r("PIN_OLD=a8717e53; NORMAL_OLD=dae7bf0b; LEAN_OLD=819f3b05; U1_OLD=0cda79b5;",
  "PIN_OLD=${PIN_PIN:?PIN_PIN: the shared tree diff md5, read before}; NORMAL_OLD=${NORMAL_PIN:?NORMAL_PIN}; LEAN_OLD=${LEAN_PIN:?LEAN_PIN}; U1_OLD=b8afba59;")
r("U1_NEW=b8afba59; U2_NEW=$U2_OLD", "U1_NEW=574301e4; U2_NEW=$U2_OLD")
r('NEW="BC5_DIRECT_XQ_ACQUIRE BC5_DIRECT_XQ_FENCE BC5_DIRECT_XQ_PENDING"', 'NEW="BC5_DIRECT_XQ_PRECISE"')
r('undo() { echo "int0430: FAILED: $*; undoing"; UNDO_IN_INT=1 bash "$HERE/undo0430.sh"; exit 1; }',
  'undo() { echo "int0430f5: FAILED: $*; undoing"; UNDO_IN_INT=1 X=$X bash "$HERE/undo0430.sh"; exit 1; }')
r('stop() { echo "int0430 STOP: $*"; exit 1; }', 'stop() { echo "int0430f5 STOP: $*"; exit 1; }')
r("for f in mkswap0430.py ho430.cpp undo0430.sh be/direct.cpp be/direct.hpp; do",
  "for f in mkf5.py ho430.cpp ho430.b8.cpp undo0430.sh; do")
r('chain_claim "exp 0430: shared swap, the hang fix (ho430: F3 + F4, F2 fallback; the backend archive rebuilt), patch $PIN_OLD + 0430; normal and lean rebuilt (CPU only, no emulator)" 40',
  'chain_claim "exp 0430: shared swap of F5 (the precise form, BC5_DIRECT_XQ_PRECISE), patch $PIN_OLD + F5; normal and lean rebuilt (CPU only, no emulator)" 30')
r('python3 -I "$HERE/mkswap0430.py" "$K" || undo "mkswap0430.py refused"', 'python3 -I "$HERE/mkf5.py" "$K" || undo "mkf5.py refused"')
r("""[ "$(grep -c 'exp 0372' "$P")" = 5 ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$P"), not 5\"""",
  """[ "$(grep -c 'exp 0372' "$P")" = "$(grep -c 'exp 0372' "$O")" ] || undo "exp 0372 lines: $(grep -c 'exp 0372' "$O") -> $(grep -c 'exp 0372' "$P")\"""")
r("ch=$(diff \"$O\" \"$P\" | grep -c '^[<>]'); echo \"the patch: $(m8 \"$O\") -> $(m8 \"$P\"), $ch lines differ, exp 0372 lines 5, pad_audio_route header in\"",
  "ch=$(diff \"$O\" \"$P\" | grep -c '^[<>]'); echo \"the patch: $(m8 \"$O\") -> $(m8 \"$P\"), $ch lines differ, exp 0372 lines $(grep -c 'exp 0372' \"$P\"), pad_audio_route header in\"")
a = s.index("# 4a: the backend")
b = s.index("# 4b\n")
s = s[:a] + s[b:]
r("# 5\nfor v in normal lean; do\n", "[ \"$(m8 \"$ARCH\")\" = \"$ARCH_OLD\" ] || undo \"the archive changed: $(m8 \"$ARCH\")\"\n# 5\nfor v in normal lean; do\n")
r("'ho430 F3': $(nice -n 19 strings \"$b\" | grep -c 'ho430 F3')", "'ho430 F5': $(nice -n 19 strings \"$b\" | grep -c 'ho430 F5')")
r('echo "int0430 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: bash $HERE/undo0430.sh (then exp 0428\'s undo0428b.sh); rollback without a build: BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_PENDING=0"',
  'echo "int0430f5 done $(date +%T): patch $(m8 "$P"), normal $(m8 "$NB"), lean $(m8 "$LB"); undo: X=$X bash $HERE/undo0430.sh; rollback without a build: BC5_DIRECT_XQ_PRECISE=0"')
assert "mkswap0430" not in s and "be/direct" not in s and "ninja bc5_backend" not in s
open(dst, "w", encoding="utf-8", newline="\n").write(s)
print("written", dst)
