#!/usr/bin/env python3
r"""BC5 experiment 0419, build V = U + what could be put together safely for ONE compile (prepared 2026-11-14/15 on
the laptop, no box). The library folds are mkfold0419.py's (levels file); this script holds V's other steps, each
independent and each left out by not naming it:
    mkv0419.py <tree root> [step ...]        default: touchfn lazyfs (liveids only when named)
  lazyfs   the heap "FileSystem" is never lazy for the direct path (the fault of arm n13P4, record 20261114-184017);
           BC5_DIAG_LAZY_FILESYSTEM=1 keeps the launcher's list as it is
  touchfn  the rest of KYTY_BC5_PAD_TOUCH's code in the pad's own files: ControllerTouch, GameController::Touch,
           ApplyTouch, the touch fields of the state and of the slot, and the read-out of touch points. Nothing fed
           them since phase 2 removed the forwarding, so the pad data is what it was (no touch points; the two touch
           ids keep the values upstream gave them). PAD CODE: the round runs one software replug.
  liveids  KYTY_BC5_AJM_LIVE_IDS becomes the fixed behaviour (an instance id that is alive is never given out again);
           the word goes. Named only in the variant the top session picks after the night series.
  defer    KYTY_BC5_AJM_DEFER becomes the fixed behaviour (a batch's jobs run at sceAjmBatchStart); the word goes
Every edit must match exactly once."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ed0419g import File

root = sys.argv[1]
steps = sys.argv[2:] or ["touchfn", "lazyfs"]
P = lambda *a: os.path.join(root, "src", *a)

if "touchfn" in steps:
    f = File(P("libs", "controller.cpp"))
    f.cut("\t// BC5 (experiment 0193): the touch points the guest is given (touch_num 0: none).\n",
          "\tuint8_t  touch_id[2]                           = {0, 0};\n")
    f.sub("\tvoid Touch(int id, int finger, bool down, float x, float y);\n", "")
    f.cut("\t\t// BC5 (experiment 0193): the two fingers on the touchpad, the latest sample like the motion\n",
          "\t\tuint8_t  last_finger_id = 0;\n")
    f.cut("\tvoid ApplyTouch(int index, ControllerState* state) const {\n", "\t\t}\n\t}\n\n")
    f.cut("\t// BC5 (experiment 0193): the touch points, when KYTY_BC5_PAD_TOUCH=1 forwards them (without it\n",
          "\t\t\tdata->touch_data_touch1_id = state.touch_id[1];\n\t\t}\n\t}\n")
    f.cut("void ControllerTouch(int id, int finger, bool down, float x, float y) {\n", "\t}\n}\n\n")
    f.cut("void GameController::Touch(int id, int finger, bool down, float x, float y) {\n", "\t\tstd::fflush(stderr);\n\t}\n}\n\n")
    f.sub("\tApplyMotion(index, state);\n\tApplyTouch(index, state);\n", "\tApplyMotion(index, state);\n")
    f.sub("\t\t\t\tApplyMotion(index, &states[ret_num]);\n\t\t\t\tApplyTouch(index, &states[ret_num]);\n",
          "\t\t\t\tApplyMotion(index, &states[ret_num]);\n")
    f.gone("ApplyTouch", "finger_down", "touch_num", "ControllerTouch", "::Touch(")
    f.save()
    f = File(P("libs", "controller.h"))
    f.cut("// BC5 (experiment 0193): a finger on the pad's touchpad (SDL's controller touchpad events: finger\n",
          "void ControllerTouch(int id, int finger, bool down, float x, float y);\n")
    f.gone("ControllerTouch")
    f.save()

if "liveids" in steps:
    f = File(P("libs", "ajm.cpp"))
    f.cut("static bool Bc5AjmLiveIdsOn() {\n", "\treturn on;\n}\n",
          "static bool Bc5AjmLiveIdsOn() { // exp 0419: fixed (the night series of 2026-11-14/15); the word is gone\n\treturn true;\n}\n")
    f.gone("KYTY_BC5_AJM_LIVE_IDS\"")
    f.save()

if "lazyfs" in steps:
    # The GPU read fault of arm n13P4 (fault record 20261114-184017; exp 0412 README sections 98-99 and
    # PLAN-memory-wall.md, cure 2): the title's heap "FileSystem" was on the lazy list, so its written pages were not
    # imported and a shader read two of them. The list is a launcher word (BC5_DIRECT_LAZY_NAMES); the launchers are
    # not this experiment's to change, so the name is taken out where the list is read. Cost by the guardian's
    # estimate: at most 48 MiB pinned more. BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list (to measure that cost).
    f = File(P("libs", "bc5LleAgc.cpp"))
    f.sub("\t\treturn v;\n\t}();\n\tstatic const bool by_data = [] { // exp 0412 (tag kl412): BC5_GUARD_LAZY_BY_DATA=1, no view is lazy\n",
          "\t\t// exp 0419 (build V) for exp 0412: \"FileSystem\" is never lazy (fault record 20261114-184017: a shader read two\n"
          "\t\t// of its written pages, which a lazy heap does not import). BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list.\n"
          "\t\tif (!bc5::env_on(std::getenv(\"BC5_DIAG_LAZY_FILESYSTEM\"))) {\n"
          "\t\t\tconst auto it = std::find(v.begin(), v.end(), std::string(\"FileSystem\"));\n"
          "\t\t\tif (it != v.end()) {\n"
          "\t\t\t\tv.erase(it);\n"
          "\t\t\t\tstd::fprintf(stderr, \"[bc5] exp 0419: FileSystem taken out of BC5_DIRECT_LAZY_NAMES (fault record 20261114-184017); \"\n"
          "\t\t\t\t                     \"BC5_DIAG_LAZY_FILESYSTEM=1 keeps the old list\\n\");\n"
          "\t\t\t}\n"
          "\t\t}\n"
          "\t\treturn v;\n\t}();\n\tstatic const bool by_data = [] { // exp 0412 (tag kl412): BC5_GUARD_LAZY_BY_DATA=1, no view is lazy\n")
    f.save()

if "defer" in steps:
    # KYTY_BC5_AJM_DEFER fixed on (the top session, 2026-11-15, after the night series on U: arm tJ ran with both AJM
    # switches in 28 long walks, clean, with no difference in smoothness or memory): a batch's jobs run at
    # sceAjmBatchStart, the console's order. What the series does NOT show: that this cures anything (the measured
    # defect was the id reuse, which `liveids` removes), and ASTRO BOT never ran with it before V's acceptance.
    f = File(P("libs", "ajm.cpp"))
    f.cut("static bool Bc5AjmDeferOn() {\n", "\treturn on;\n}\n",
          "static bool Bc5AjmDeferOn() { // exp 0419: fixed (the night series of 2026-11-14/15, arm tJ); the word is gone\n\treturn true;\n}\n")
    f.gone("KYTY_BC5_AJM_DEFER\"")
    f.save()
