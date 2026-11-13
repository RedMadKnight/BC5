#!/usr/bin/env python3
"""BC5 experiment 0419: the title table against the launcher it replaces. Reads `test0419defs table` (the rows as
the compiled header has them) and a copy of the box's play-pkg.sh, and checks, word by word:
  - every constant word the launcher exports is in the title's table or in a general table, with the SAME value;
  - every row of the title's table comes from the launcher (nothing new is turned on).
Words that stay in the launcher on purpose are listed in STAY (paths, title data, diagnostics, launcher logic).
usage: cmplaunch0419.py <table text> <play-pkg.sh> <title id>"""
import re
import sys

table, launcher, title = sys.argv[1:4]
gen, per = {}, {}
for line in open(table, encoding="utf-8"):
    t, n, v = line.rstrip("\n").split(" ", 2)
    (gen if t == "*" else per.setdefault(t, {}))[n] = v
per = per.get(title, {})
STAY = {
    "BC5_DIRECT_LAZY_NAMES", "BC5_DIRECT_EAGER_NAMES", "KYTY_BC5_RT_BUILD_PGM",          # title data, long lists
    "SHADPS4_SYSMODULES_PACK_DIR", "KYTY_BC5_SAVEDATA_DIR", "BC5_MOUNT_DISK_CACHE", "BC5_GC_DUMP_DIR",  # paths
    "XDG_RUNTIME_DIR", "WAYLAND_DISPLAY", "DISPLAY",                                      # the session
    "BC5_DIRECT_TIMING", "BC5_DIRECT_FRAME_PROFILE", "BC5_DIRECT_TIMEOUT_PROBE",          # diagnostics, non-lean only
    "KYTY_BC5_FPS_COUNTER", "KYTY_BC5_AUDIO_TRACE", "KYTY_BC5_MEASURE",
    "BC5_DIRECT_LEARNED",                                                                 # read by nothing; goes from the launcher
    "BC5_DIRECT_CP_COHER_START_DELAY", "BC5_DIRECT_GC_TF_RING", "BC5_DIRECT_GC_HS_OFFCHIP",  # exp 0418: read by nothing since the start-state table is always on
    "BC5_DIRECT_SOFT_WAIT_MS",                                                            # 8 is the code's own default
}
src = open(launcher, encoding="utf-8").read()
src = re.sub(r"\\\n", " ", src)
found = {}
for line in src.split("\n"):
    code = line.split("  #")[0]
    if code.lstrip().startswith("#"):
        continue
    if "export" not in code and not code.lstrip().startswith("for w in"):
        continue
    for m in re.finditer(r"\b((?:KYTY_)?BC5_[A-Z0-9_]+|SHADPS4_[A-Z_]+|XDG_RUNTIME_DIR|WAYLAND_DISPLAY|DISPLAY)=(\"[^\"]*\"|\S*)", code):
        n, v = m.group(1), m.group(2).rstrip(';').strip('"')
        d = re.fullmatch(r"\$\{%s:-(.*)\}" % re.escape(n), v)
        if d:
            v = d.group(1)
        found.setdefault(n, v)
bad = 0
moved = 0
for n, v in sorted(found.items()):
    if n in STAY:
        continue
    have = per.get(n, gen.get(n))
    if have is None:
        print("MISSING in the tables: %s=%s" % (n, v)); bad += 1
    elif have != v:
        print("VALUE differs: %s launcher %s, table %s" % (n, v, have)); bad += 1
    else:
        moved += 1
for n in sorted(per):
    if n not in found:
        print("NOT from the launcher: %s=%s" % (n, per[n])); bad += 1
print("cmplaunch0419: %d launcher words in the tables with the same value (%d title rows, %d stay in the launcher); %d problems"
      % (moved, len(per), len([n for n in found if n in STAY]), bad))
sys.exit(1 if bad else 0)
