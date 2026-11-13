#!/usr/bin/env python3
"""BC5 experiment 0419, step 5: the launchers without the words that moved into the code. Makes NEW files beside
copies of the box's launchers; nothing is installed (a launcher or shortcut changes only on the maintainer's word).
  play-pkg.sh   (47426d8e): every exported word that is now in the title's table or in kDefaults is taken out of its
                export line (a line left with no word goes, its comment stays as a comment); the loop of the twenty
                library words goes; BC5_DIRECT_AMM_PRT's line goes (BC5_DIRECT_AMM_PRT=0 is "off" in the code now);
                BC5_DIRECT_LEARNED (read by nothing) and BC5_DIRECT_SOFT_WAIT_MS=8 (the code's default) go.
  play-astro.sh: BC5_DIRECT_CHAIN (general now) and KYTY_BC5_APR_READAHEAD=4 (the code's default) go.
The table is read from `test0419defs table`, so the launcher loses exactly what the compiled header has.
These launchers need the cleanup candidate's binary: on today's shared builds they would run without the fixes.
usage: mklaunch0419.py <table text> <title id> <play-pkg.sh in> <play-pkg.sh out> <play-astro.sh in> <play-astro.sh out>"""
import re
import sys

table, title, pkg_in, pkg_out, astro_in, astro_out = sys.argv[1:7]
gen, per = set(), set()
for line in open(table, encoding="utf-8"):
    t, n, _ = line.rstrip("\n").split(" ", 2)
    (gen if t == "*" else per).add(n) if t in ("*", title) else None
ASSIGN = re.compile(r"((?:KYTY_)?BC5_[A-Z0-9_]+)=(\"[^\"]*\"|\S*)")


def strip_exports(text, gone, marker):
    out, removed = [], []
    for line in text.split("\n"):
        if not line.startswith("export "):
            out.append(line)
            continue
        code, sep, comment = line.partition("  #")
        keep = []
        for m in ASSIGN.finditer(code):
            (removed if m.group(1) in gone else keep).append(m.group(0))
        if len(keep) == len(ASSIGN.findall(code)):
            out.append(line)
        elif keep:
            out.append("export " + " ".join(keep) + (sep + comment if sep else ""))
        elif sep:
            out.append("#" + comment + "  [" + marker + "]")
    return "\n".join(out), removed


# play-pkg.sh
s = open(pkg_in, encoding="utf-8", newline="").read()
assert "\r" not in s
a = s.index("# exp 0413: this title's switches that are not defaults in the emulator")
b = s.index("done\n", a) + len("done\n")
assert s[a:b].count("for w in") == 1 and s[a:b].count("KYTY_BC5_") == 20, "the loop of the twenty words is not as expected"
s = s[:a] + "# exp 0419: this title's twenty library words are in the emulator's own table for this title (src/bc5/switch_defaults.hpp)\n" + s[b:]
old = 'if [ "${BC5_DIRECT_AMM_PRT-1}" = 0 ]; then unset BC5_DIRECT_AMM_PRT; else export BC5_DIRECT_AMM_PRT=${BC5_DIRECT_AMM_PRT:-1}; fi\n'
assert s.count(old) == 1
s = s.replace(old, "# exp 0419: BC5_DIRECT_AMM_PRT is in the title's table; BC5_DIRECT_AMM_PRT=0 in the environment turns it off\n")
# exp 0418 (candidate F): its three start-state words are read by nothing any more, so they leave the launcher too
s, removed = strip_exports(s, gen | per | {"BC5_DIRECT_LEARNED", "BC5_DIRECT_SOFT_WAIT_MS", "BC5_DIRECT_CP_COHER_START_DELAY", "BC5_DIRECT_GC_TF_RING", "BC5_DIRECT_GC_HS_OFFCHIP"}, "exp 0419: now in the emulator's table or read by nothing")
names = sorted(set(x.split("=")[0] for x in removed))
left = [n for n in sorted(gen | per) if re.search(r"^export .*\b%s=" % n, s, re.M)]
assert not left, left
open(pkg_out, "w", encoding="utf-8", newline="\n").write(s)
print("play-pkg.sh: %d words out of the export lines (+ the loop's 20 and AMM_PRT): %s" % (len(names), " ".join(names)))

# play-astro.sh
s = open(astro_in, encoding="utf-8", newline="").read()
assert "\r" not in s
s, removed = strip_exports(s, {"BC5_DIRECT_CHAIN", "KYTY_BC5_APR_READAHEAD"}, "exp 0419: the emulator's own default")
assert sorted(x.split("=")[0] for x in removed) == ["BC5_DIRECT_CHAIN", "KYTY_BC5_APR_READAHEAD"], removed
open(astro_out, "w", encoding="utf-8", newline="\n").write(s)
print("play-astro.sh: BC5_DIRECT_CHAIN and KYTY_BC5_APR_READAHEAD out")
