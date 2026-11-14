#!/usr/bin/env python3
"""BC5 experiment 0419, candidate G, step g: the unit's two hang-hunt words of exp 0401 series e7 lose their option.
  BC5_DIRECT_FL_SERIAL     F2 fix candidate for F813's draw that never ends: 0 hangs in 8 with it, 0 in 10 without
  BC5_DIRECT_FL_VGT_FLUSH  F1 fix candidate: built, never run on the GPU
The maintainer's word of 2026-11-14, asked with F403 and F813 named as OPEN and F's GPU hang of 2026-11-13: "Usun".
With the backend's three (mkg0419_f.py <direct.cpp> all: BC5_DIRECT_ARGS_WB, _ARGS_FLUSH, _ARGS_FLUSH_DRAWS) these are
the five that candidate G first kept.
FIRST PHASE, as step f: the reads go, FlxSwitches::serial stays false and ::flush stays 0. The planner's F1/F2 code
(FlDraw::flush/serial, flx_heads, the inserts in fl_after, the seams bc5_flx0401_* that flx0401.cpp tests) is dead and
still in the source: it is woven through fl_scan and the laptop test's seams and is cut with a compiler at hand.
To get the words back: this step's reverse, or candidate F's unit (patch d9af28ca), which has them whole.
usage: mkg0419_g.py <src/libs/bc5LleAgc.cpp>"""
import sys
from ed0419g import File

f = File(sys.argv[1])
f.sub('\t\tv.serial         = bc5::env_on(std::getenv("BC5_DIRECT_FL_SERIAL"));\n',
      '\t\tv.serial         = false; /* exp 0419: option removed */\n')
KEEP = '\t\tv.crumbs_meshlet = bc5::env_on(std::getenv("BC5_DIRECT_FL_CRUMBS_MESHLET"));\n'
n = f.cut(KEEP, '"BC5_DIRECT_FL_VGT_FLUSH"), &bad);\n', KEEP + '\t\tv.flush          = 0; /* exp 0419: option removed */\n')
assert n < 220, n  # the kept line, `bool bad = false;` and the read: nothing else
f.sub('arm[v.flush], bad ? " (BC5_DIRECT_FL_VGT_FLUSH does not parse: prefix, transition or all)" : "",', 'arm[v.flush], "",')
f.sub('//   BC5_DIRECT_FL_VGT_FLUSH=prefix|transition|all  F1 fix candidate:',
      '//   (BC5_DIRECT_FL_VGT_FLUSH, option removed by exp 0419) F1 fix candidate:')
f.sub('//   BC5_DIRECT_FL_SERIAL=1                         F2 fix candidate:',
      '//   (BC5_DIRECT_FL_SERIAL, option removed by exp 0419) F2 fix candidate:')
f.gone('getenv("BC5_DIRECT_FL_SERIAL")', 'getenv("BC5_DIRECT_FL_VGT_FLUSH")', "BC5_DIRECT_FL_VGT_FLUSH does not parse")
f.save()
