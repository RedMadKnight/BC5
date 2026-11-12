"""Exp 0413: the set-buffer guard as a row of the defaults table (on by default), one commit."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import defaults as d  # noqa: E402

TREE, REPO, WORK = sys.argv[1], sys.argv[2], sys.argv[3]
d.TREE, d.REPO, d.WORK = TREE, REPO, WORK
d.PATCH = os.path.join(REPO, "backend", "kytyplus-patches", "0001-bc5-lle-agc.patch")
d.HDR = os.path.join(TREE, "src", "bc5", "switch_defaults.hpp")
keep = [it for it in d.ITEMS if it[0] not in ("A15", "A16", "A17", "A21", "A22")]
keep.append(("E1", "set-buffer guard: no AMM map flavour over mapped memory (exp 0413)", [("KYTY_BC5_AMM_SETBUFFER_GUARD", "1")],
             "ASTRO BOT's start crash: a zeroed page mapped over the title's heap from leftover registers"))
d.ITEMS = keep
d.write_header(len(keep))
d.commit("int(0413): default on, E1: the set-buffer guard (KYTY_BC5_AMM_SETBUFFER_GUARD=1)\n\n"
         "The fix of ASTRO BOT's start crash, on by default; KYTY_BC5_AMM_SETBUFFER_GUARD=0 gives exp 0035's old heuristic.")
print("committed")
