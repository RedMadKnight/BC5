import sys

src, dst = sys.argv[1], sys.argv[2]  # the 0428 experiment dir, the 0430 experiment dir
common = [('0428b', '0430'), ('exp0428/swap2', 'exp0430/swap')]


def conv(name, out, reps):
    s = open(f'{src}/{name}', encoding='utf-8').read()
    for a, b in reps:
        if a not in s and (a, b) in common:
            continue
        if a not in s:
            sys.exit(f'{name}: [{a[:70]}] not found')
        s = s.replace(a, b)
    open(f'{dst}/{out}', 'w', encoding='utf-8', newline='\n').write(s)
    print('wrote', out)


conv('int0428b.sh', 'int0430.sh', [
    ('# BC5 exp 0428, the SECOND swap (int0428.sh adapted): iteration 6\'s split fix (BC5_DIRECT_ACB_SPLIT_LATE=3, a fifth TITLE2\n# way-2 row; the unit as tested in build 185a18f8), on top of the shared patch 2c82a979 (the first swap). The\n# maintainer\'s consent through deployment (relayed by the top session, 2026-11-16) and the top session\'s GO.',
     '# BC5 exp 0430, the swap of the hang fix (exp 0428\'s int0428b.sh adapted): F3 and F2 (tag ho430, the shared form of\n# mkswap0430.py: BC5_DIRECT_XQ_ACQUIRE and BC5_DIRECT_XQ_PENDING, each on unless "0"; they act only when rings run side\n# by side), on top of the shared patch a8717e53. Only src/libs/bc5LleAgc.cpp changes. The maintainer\'s consent for way 2\n# "until full deployment" and the top session\'s night plan of 2026-11-16.'),
    ('#   1. checks: no emulator; the shared tree\'s diff is 700fd4c2; both binaries are 1be1cc1d / b7fb337f; units pinned; kit here',
     '#   1. checks: no emulator; the shared tree\'s diff is a8717e53; both binaries are dae7bf0b / 819f3b05; units pinned; kit here'),
    ('#   3. mkswap0428.py on ~/src/KytyPlus;', '#   3. mkswap0430.py on ~/src/KytyPlus;'),
    ('#   5. strings: both builds gain exactly the four exp 0428 words and lose none; normal holds "tag w428c", lean no\n#      "exp 0428" text',
     '#   5. strings: both builds gain exactly BC5_DIRECT_XQ_ACQUIRE and BC5_DIRECT_XQ_PENDING and lose none'),
    ('# Any failure after step 2 runs undo0428.sh', '# Any failure after step 2 runs undo0430.sh'),
    ('# usage (on the box, in ~/bc5-work/exp0428): bash int0428.sh', '# usage (on the box, in ~/bc5-work/exp0430): bash int0430.sh'),
    ('X=$W/exp0428/swap2; BASE=$W/exp0428/swap/bc5LleAgc.cpp.before-0428', 'X=$W/exp0430/swap'),
    ('PIN_OLD=2c82a979; NORMAL_OLD=3f22e0e1; LEAN_OLD=35a3753d; U1_OLD=f16eb3f3; U2_OLD=3b41711e; U1_NEW=0cda79b5; U2_NEW=554e0139',
     'PIN_OLD=a8717e53; NORMAL_OLD=dae7bf0b; LEAN_OLD=819f3b05; U1_OLD=0cda79b5; U2_OLD=${U2_PIN:?U2_PIN: the shared switch_defaults.hpp md5, read before}; U1_NEW=42f9f976; U2_NEW=$U2_OLD'),
    ('NEW="BC5_DIRECT_ACB_SPLIT_LATE"', 'NEW="BC5_DIRECT_XQ_ACQUIRE BC5_DIRECT_XQ_PENDING"'),
    ('for f in mkswap0428b.py mk0428.py ed0419g.py undo0428b.sh; do', 'for f in mkswap0430.py ho430.cpp undo0430.sh; do'),
    ('chain_claim "exp 0428: second shared swap, the split fix (SPLIT_LATE=3) for the second title, patch $PIN_OLD + 0428b; normal and lean rebuilt (CPU only, no emulator)" 40',
     'chain_claim "exp 0430: shared swap, the hang fix (ho430: F3 + F2), patch $PIN_OLD + 0430; normal and lean rebuilt (CPU only, no emulator)" 40'),
    ('[ "$(m8 "$BASE")" = 3e847e03 ] || undo "the base unit $BASE is not 3e847e03"\npython3 -I "$HERE/mkswap0428b.py" "$K" "$BASE" || undo "mkswap0428b.py refused"',
     'python3 -I "$HERE/mkswap0430.py" "$K" || undo "mkswap0430.py refused"'),
    ('echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr \'\\n\' \' \')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr \'\\n\' \' \')]; \'tag w428c\': $(nice -n 19 strings "$b" | grep -c \'tag w428c\'), \'exp 0428\': $(nice -n 19 strings "$b" | grep -c \'exp 0428\')"',
     'echo "$v words: +[$(comm -13 "$X/words-$v.before" "$X/words-$v.after" | tr \'\\n\' \' \')] -[$(comm -23 "$X/words-$v.before" "$X/words-$v.after" | tr \'\\n\' \' \')]; \'ho430 F3\': $(nice -n 19 strings "$b" | grep -c \'ho430 F3\')"'),
    ('[ "$(nice -n 19 strings "$LB" | grep -c \'exp 0428\')" = 0 ] || undo "lean holds exp 0428 text"\n[ "$(nice -n 19 strings "$NB" | grep -c \'tag w428c\')" -ge 1 ] || undo "normal lacks the w428c line"\n',
     ''),
    ('undo: bash $HERE/undo0428b.sh (then undo0428.sh for way 2 itself); rollback without a build: BC5_DIRECT_ACB_SPLIT_LATE=0"',
     'undo: bash $HERE/undo0430.sh (then exp 0428\'s undo0428b.sh); rollback without a build: BC5_DIRECT_XQ_ACQUIRE=0 BC5_DIRECT_XQ_PENDING=0"'),
] + common)

conv('undo0428b.sh', 'undo0430.sh', [
    ('# BC5 exp 0428: puts the shared tree\'s bc5LleAgc.cpp and switch_defaults.hpp and both shared binaries back as they were\n# before int0428b.sh (patch 2c82a979: normal 3f22e0e1, lean 35a3753d)',
     '# BC5 exp 0430: puts the shared tree\'s bc5LleAgc.cpp and switch_defaults.hpp and both shared binaries back as they were\n# before int0430.sh (patch a8717e53: normal dae7bf0b, lean 819f3b05)'),
    ('# usage (on the box): bash ~/bc5-work/exp0428/undo0428.sh', '# usage (on the box): bash ~/bc5-work/exp0430/undo0430.sh'),
    ('chain_claim "exp 0428: undo of the second swap (back to patch 2c82a979; copies only, no emulator)" 5',
     'chain_claim "exp 0430: undo of the hang-fix swap (back to patch a8717e53; copies only, no emulator)" 5'),
    ('further back: bash $W/exp0428/undo0428.sh"', 'further back: bash $W/exp0428/undo0428b.sh"'),
] + common)

conv('test_undo0428b.sh', 'test_undo0430.sh', [
    ('U=${UNDO:-$(cd "$(dirname "$0")" && pwd)/undo0428b.sh}', 'U=${UNDO:-$(cd "$(dirname "$0")" && pwd)/undo0430.sh}'),
    ('"$T/bc5-work/exp0428/swap2"', '"$T/bc5-work/exp0430/swap"'),
    ('X=$T/bc5-work/exp0428/swap2', 'X=$T/bc5-work/exp0430/swap'),
] + common)
