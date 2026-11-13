#!/usr/bin/env python3
"""BC5 integration of 2026-11-13: exp 0415's read fix becomes a code default (the top session, on the maintainer's
"jest zgoda na scalenie wszystkiego i twoje testy").
  defaults  src/bc5/switch_defaults.hpp (md5 4f704194): one more row in kFixes, KYTY_BC5_APR_POSIX=direct. Like the
            other rows it is applied even with KYTY_BC5_SWITCH_DEFAULTS=0, and KYTY_BC5_APR_POSIX=0 in the
            environment gives the old read path (setenv never overwrites).
  ampr      src/libs/libAmpr.cpp (md5 2852bb41, exp 0416's unit merged with exp 0415's L4): the comment over
            AprPosixMode() said "default off"; it now says where the default comes from. No code changes.
usage: mkdef0416.py defaults|ampr <in> <out>"""
import hashlib
import sys

what, src, dst = sys.argv[1:4]
s = open(src, "rb").read()
assert b"\r" not in s
md5 = hashlib.md5(s).hexdigest()


def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)


if what == "defaults":
    assert md5 == "4f7041942ee121629cd608ed40d6fc86", md5
    rep(b'''    {"KYTY_BC5_PHYSMAP_SORTED", "1"},
    {nullptr, nullptr}};
''', b'''    {"KYTY_BC5_PHYSMAP_SORTED", "1"},
    // exp 0415: APR reads by pread with POSIX_FADV_RANDOM, straight into the guest's pages (the old code let the
    // kernel read ahead 11.7 GiB for 5.1 GiB asked). KYTY_BC5_APR_POSIX=0 gives the old fread path.
    {"KYTY_BC5_APR_POSIX", "direct"},
    {nullptr, nullptr}};
''')
    rep(b"// Experiment 0416: pure fixes (a fault, a leak, two same-answer speed-ups).",
        b"// Experiment 0416: pure fixes (a fault, a leak, two same-answer speed-ups; since 2026-11-13 exp 0415's read fix).")
elif what == "ampr":
    assert md5 == "2852bb4105a14247d0b2794ea8a73042", md5
    rep(b'// Experiment 0415 (ls415b), KYTY_BC5_APR_POSIX, default off (unset, empty, "0"). Run b1 measured the cause: every APR\n',
        b'// Experiment 0415 (ls415b), KYTY_BC5_APR_POSIX; off when unset, empty or "0". Since the integration of 2026-11-13 the\n'
        b'// code defaults (bc5/switch_defaults.hpp, kFixes) set it to "direct". Run b1 measured the cause: every APR\n')
else:
    raise SystemExit(__doc__)
open(dst, "wb").write(s)
print("%s %s -> %s" % (what, md5[:8], hashlib.md5(s).hexdigest()[:8]))
