#!/usr/bin/env python3
"""BC5 experiment 0428, the second swap (iteration 6's split fix) on the KytyPlus tree at patch 2c82a979.
    mkswap0428b.py <tree root> <base unit>
1. src/libs/bc5LleAgc.cpp: the base unit (700fd4c2's, md5 3e847e03: the first swap's saved copy) edited by mk0428.py as it
   is now (unit 0cda79b5, the tested build 185a18f8's).
2. src/bc5/switch_defaults.hpp: one more PPSA03671 row, BC5_DIRECT_ACB_SPLIT_LATE=3 (setenv(name, value, 0): =0 in the
   environment is the rollback with no build).
Every edit must match exactly once."""
import hashlib, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "0419-switch-cleanup"))
from ed0419g import File

root, base = sys.argv[1], sys.argv[2]
assert hashlib.md5(open(base, "rb").read()).hexdigest()[:8] == "3e847e03", "the base unit is not 3e847e03"
shutil.copyfile(base, os.path.join(root, "src", "libs", "bc5LleAgc.cpp"))
r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "mk0428.py"), root])
if r.returncode != 0:
    sys.exit("mk0428.py refused")
f = File(os.path.join(root, "src", "bc5", "switch_defaults.hpp"))
f.gone("BC5_DIRECT_ACB_SPLIT_LATE")
f.sub("""    {BC5_T2, "BC5_DIRECT_ACB_STATE_NO_WALK", "1"},
""", """    {BC5_T2, "BC5_DIRECT_ACB_STATE_NO_WALK", "1"},
    // exp 0428 iteration 6: a two-ring dcb wait polls first and splits only on exp 0132's cycle or after 8 ms (18,625 -> 69
    // splits per run, w428L11). BC5_DIRECT_ACB_SPLIT_LATE=0 in the environment is the rollback.
    {BC5_T2, "BC5_DIRECT_ACB_SPLIT_LATE", "3"},
""")
f.save()
