#!/usr/bin/env python3
"""BC5 experiment 0428: the shared swap's source changes on the KytyPlus tree (patch 700fd4c2).
    mkswap0428.py <tree root>
1. src/libs/bc5LleAgc.cpp: mk0428.py's edits (unit 3e847e03 -> f16eb3f3, the unit of the tested private build 9e53ae43).
2. src/bc5/switch_defaults.hpp: four rows for the second title only (kTitleDefaults, BC5_T2), applied with
   setenv(name, value, 0), so a value in the environment wins and NAME=0 turns one off with no build (the rollback):
     BC5_DIRECT_ACB_RINGS=4, BC5_DIRECT_ACB_QUEUE_STATE=1, BC5_DIRECT_ACB_MEC_INDIRECT=1, BC5_DIRECT_ACB_STATE_NO_WALK=1
   the first title gets none of them: the table's own rule (a word moves to the general tables when it has runs on both titles).
Every edit must match exactly once."""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
from ed0419g import File

root = sys.argv[1]
r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "mk0428.py"), root])
if r.returncode != 0:
    sys.exit("mk0428.py refused")
f = File(os.path.join(root, "src", "bc5", "switch_defaults.hpp"))
f.gone("exp 0428")
f.sub("""    {BC5_T2, "KYTY_BC5_LOAD_NPTROPHY", "1"},
    {nullptr, nullptr, nullptr}};
#undef BC5_T2
""", """    {BC5_T2, "KYTY_BC5_LOAD_NPTROPHY", "1"},
    // exp 0428 (way 2, the maintainer's consent through deployment, 2026-11-16): the title's acbs on compute rings, each
    // guest queue's compute state in front of its dispatching acb parts, indirect dispatches on the MEC under the CP's
    // check (verified on real dispatches, exp 0428 step 2). BC5_DIRECT_ACB_RINGS=0 in the environment is the rollback.
    {BC5_T2, "BC5_DIRECT_ACB_RINGS", "4"},
    {BC5_T2, "BC5_DIRECT_ACB_QUEUE_STATE", "1"},
    {BC5_T2, "BC5_DIRECT_ACB_MEC_INDIRECT", "1"},
    {BC5_T2, "BC5_DIRECT_ACB_STATE_NO_WALK", "1"},
    {nullptr, nullptr, nullptr}};
#undef BC5_T2
""")
f.save()
