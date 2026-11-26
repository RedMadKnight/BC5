#!/usr/bin/env python3
"""BC5 experiment 0431: way 2 for every title, on the KytyPlus tree at patch a8717e53 (exp 0428's second swap).
    mkswap0431.py <tree root>
src/bc5/switch_defaults.hpp (554e0139): the five way-2 rows of TITLE2 (BC5_DIRECT_ACB_RINGS=4, _QUEUE_STATE=1,
_MEC_INDIRECT=1, _STATE_NO_WALK=1, _SPLIT_LATE=3) move from kTitleDefaults to kSoft, which Apply() runs for every title
before the title rows, with setenv(name, value, 0): a value in the environment still wins and NAME=0 turns one off.
The unit bc5LleAgc.cpp (0cda79b5) is not touched. Every edit must match exactly once (ed0419g.File)."""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # on the box ~/bc5-work/exp0431 holds a copy of ed0419g.py
sys.path.insert(1, os.path.join(HERE, "..", "0428-way2-rings"))
from ed0419g import File

root = sys.argv[1]
f = File(os.path.join(root, "src", "bc5", "switch_defaults.hpp"))
f.cut("""    // exp 0428 (way 2, the maintainer's consent through deployment, 2026-11-16): the title's acbs on compute rings, each
""", """    {BC5_T2, "BC5_DIRECT_ACB_SPLIT_LATE", "3"},
""")
f.gone("{BC5_T2, \"BC5_DIRECT_ACB")
f.sub("""    {"KYTY_BC5_0425_WAKE_SLICE_US", "200"},
    {nullptr, nullptr}};
""", """    {"KYTY_BC5_0425_WAKE_SLICE_US", "200"},
    // exp 0428 way 2, for every title since exp 0431 (the maintainer, 2026-11-16: it must work in any game; until then
    // TITLE2's rows): the acbs on kernel compute rings, one libdrm ring per busy guest queue; each acb part that
    // dispatches gets its own guest queue's tracked compute state in front; indirect dispatches on the MEC under the CP's
    // check (verified on real dispatches, exp 0428 step 2). BC5_DIRECT_ACB_RINGS=0 in the environment turns way 2 off.
    {"BC5_DIRECT_ACB_RINGS", "4"},
    {"BC5_DIRECT_ACB_QUEUE_STATE", "1"},
    {"BC5_DIRECT_ACB_MEC_INDIRECT", "1"},
    {"BC5_DIRECT_ACB_STATE_NO_WALK", "1"},
    // exp 0428 iteration 6: a two-ring dcb wait polls first and splits only on exp 0132's cycle or after 8 ms (18,625 -> 69
    // splits per run, w428L11). BC5_DIRECT_ACB_SPLIT_LATE=0 in the environment turns it off.
    {"BC5_DIRECT_ACB_SPLIT_LATE", "3"},
    {nullptr, nullptr}};
""")
f.save()
