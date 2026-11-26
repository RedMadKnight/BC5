#!/usr/bin/env python3
"""BC5 experiment 0419: of the words a tree reads (words0419g.py's list), how many can still be set from outside.
A word forced at process start (kFixes, kDefaults: setenv with overwrite) or unset at process start (kIgnored) is
read by the code but has no option.
usage: settable0419g.py <switch_defaults.hpp> <names file, one word per line>"""
import re, sys

hdr, names = sys.argv[1:3]
s = open(hdr, encoding="utf-8").read()


def tab(n):
    a = s.index(n + "[] = {")
    e = s.index("};", a)
    return re.findall(r'"((?:KYTY_)?BC5_[A-Z0-9_]+)"', s[a:e])


fix, dfl, soft, ign, title = tab("kFixes"), tab("kDefaults"), tab("kSoft"), tab("kIgnored"), tab("kTitleDefaults")
read = set(open(names, encoding="utf-8").read().split())
forced = set(fix) | set(dfl)
if "kTitleForced[] = {" in s:  # step i: title rows set with overwrite after the word is unset at start
    forced |= set(tab("kTitleForced"))
print("read %d; forced at start %d (read: %d); unset at start %d (read: %d); defaults with an option %d; one title's rows %d" % (
    len(read), len(forced), len(forced & read), len(ign), len(set(ign) & read), len(soft), len(set(title))))
print("can still be set: %d" % len(read - forced - set(ign)))
left = read - forced - set(ign)
print("of them one title's rows: %d, defaults with an option: %d, other: %d" % (
    len(left & set(title)), len(left & set(soft)), len(left - set(title) - set(soft))))
