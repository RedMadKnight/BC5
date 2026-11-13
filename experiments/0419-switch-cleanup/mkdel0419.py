#!/usr/bin/env python3
"""BC5 experiment 0419, step 1, PHASE 1: the options of refuted, superseded or answered switches are removed.
Each read of the environment becomes the constant the switch had when unset, so the word can no longer be turned on
and the compiler drops what it guarded. The code behind each constant is still in the source (phase 2 removes it,
with the compiler's help, once this candidate has run); its journal texts still name the old words.
Which words, and on whose verdict: README section "DELETE". NOT touched: KYTY_BC5_ANON_SYNC(+_MS) (exp 0415: keep),
BC5_GUARD_FORGET (exp 0412: keep), BC5_GUARD_MAP_RULE / _PRT_BG / _LEARN_LOG (exp 0412's, read through env_digit;
the fast9 shortcut checks the binary for the text BC5_GUARD_LEARN_LOG), BC5_DIRECT_SPI_REQ_CTRL_PS (exp 0418 plans it).
alias_learn (exp 0056: a GPU fault at a tagged address added an alias window for every later run, a learned window
by another name) is no longer called.
Edits candidate B's tree in place; every anchor must occur the stated number of times.
usage: mkdel0419.py <tree root>"""
import sys

root = sys.argv[1]
X = " /* exp 0419: option removed */"
EDITS = {
    "src/libs/bc5LleAgc.cpp": [
        # the soft-CP catchers that answered (audit A10)
        ('v.rewind     = take("BC5_R3_REWIND_CATCH");', "v.rewind     = false;" + X, 1),
        ('v.drop       = take("BC5_R3_DROP_CATCH");', "v.drop       = false;" + X, 1),
        # exp 0415: no effect in 5 runs (its README section 10)
        ('static const int               mode = bc5::sync_fast::mode_of(std::getenv("KYTY_BC5_NAMES_FAST"));', "static const int               mode = 0;" + X, 1),
        ('static const int vma_fast = bc5::sync_fast::mode_of(std::getenv("KYTY_BC5_VMA_FAST"));', "static const int vma_fast = 0;" + X, 1),
        # the acb inherit catcher and its caps (audit B4), the acb CS prefix (audit B3: 3 guest CPU crashes)
        ('\t\tconst char* e = std::getenv("BC5_DIRECT_ACB_INHERIT");\n', "\t\tconst char* e = nullptr;" + X + "\n", 1),
        ('bc5::env_on(std::getenv("BC5_DIRECT_ACB_CS_PREFIX"))', "false" + X, 2),
        ('cap_parse(std::getenv("BC5_DIRECT_INHERIT_PROG_CAP"), kInhProgCapDefault)', "cap_parse(nullptr, kInhProgCapDefault)" + X, 1),
        ('cap_parse(std::getenv("BC5_DIRECT_INHERIT_CENSUS_CAP"), kInhCensusCapDefault)', "cap_parse(nullptr, kInhCensusCapDefault)" + X, 1),
        # the draw-class catchers (audit B8, B11)
        ('e = std::getenv("BC5_DIRECT_FL_SKIP_ES");', "e = nullptr;" + X, 1),
        ('smp_parse(std::getenv("BC5_DIRECT_FL_MESHLET_SAMPLE"), &bad)', "smp_parse(nullptr, &bad)" + X, 1),
        # the zero skip (F818: unsound by design) and its poll
        ('static const bool on = std::getenv("BC5_DIRECT_ZERO_SKIP") != nullptr;', "static const bool on = false;" + X, 1),
        ('static const char* p = bc5::env_on(std::getenv("BC5_DIRECT_ZERO_SKIP")) ? std::getenv("BC5_DIRECT_ZERO_SKIP") : nullptr;', "static const char* p = nullptr;" + X, 1),
        ('e = std::getenv("BC5_DIRECT_ZERO_NAMES");', "e = nullptr;" + X, 2),
        ('\t\tconst char* e = std::getenv("BC5_GUARD_ZSKIP_POLL_SUBMIT");\n', "\t\tconst char* e = nullptr;" + X + "\n", 1),
        # the recovery after a GPU reset (F821 and the maintainer's rule of 2026-11-13: no recovery as a fix)
        ("bc5::env_on(std::getenv(kM11Names[0]))", "false", 1),
        ("bc5::env_on(std::getenv(kM11Names[1]))", "false", 1),
        ("bc5::env_on(std::getenv(kM11Names[2]))", "false", 1),
        ("bc5::env_on(std::getenv(kM11Names[3]))", "false" + X, 1),
        ('\t\tconst char* e = std::getenv("BC5_DIRECT_RESET_LABELS_ADD");\n', "\t\tconst char* e = nullptr;" + X + "\n", 1),
        # exp 0412's page-cache advice, pressure loop and learned_apply throttle (its owner: never moved the wall / dead)
        ('std::getenv("BC5_GUARD_FILE"), std::getenv("BC5_GUARD_FILE_ROOT"),', "nullptr, nullptr," + X, 1),
        ('std::getenv("BC5_GUARD_PSI"),', "nullptr,", 1),
        ('std::getenv("BC5_GUARD_APPLY_MIN_MS"),', "nullptr," + X, 1),
        # alias_learn: no window is learned from a fault any more
        ("\t\tif (r.fault_addr != 0 && (r.fault_addr >> 40u) != 0 && aliases_on()) alias_learn(r.fault_addr); // experiment 0056\n",
         "\t\t// exp 0419: alias_learn (experiment 0056) is no longer called: no window is learned from a GPU fault\n", 1),
        ("static void alias_learn(uint64_t fault_addr) {\n", "[[maybe_unused]] static void alias_learn(uint64_t fault_addr) { // exp 0419: not called\n", 1),
    ],
    "src/kernel/memory.cpp": [
        ('\t\tconst char* e = std::getenv("KYTY_BC5_MEMORY_FROM_PARAM");\n', "\t\tconst char* e = nullptr;" + X + "\n", 1),  # audit A25: failed in play
    ],
    "src/graphics/presentation/videoOut.cpp": [
        ('\t\tconst char* e = std::getenv("KYTY_BC5_MIN_FLIP_RATE");\n', "\t\tconst char* e = nullptr;" + X + "\n", 1),  # F247: the cutscenes are at 1.00x without it
    ],
    "src/bc5/load_stat.hpp": [
        # exp 0415's probe and tuning words (its owner, 2026-11-13: no effect on the loads; 200 stays in the code)
        ('\t\t\tconst char* e = std::getenv("KYTY_BC5_LOAD_DELAY");\n', "\t\t\tconst char* e = nullptr;" + X + "\n", 1),
        ('const uint64_t x = env_num("KYTY_BC5_RING_POLL_US", 200, 20\'000);', "const uint64_t x = 200;" + X, 1),
        ('static const uint64_t v = env_num("KYTY_BC5_RING_SPIN_US", 0, 5\'000) * 1000ull;', "static const uint64_t v = 0;" + X, 1),
        ('static const uint64_t v = env_num("KYTY_BC5_MUTEX_SPIN_US", 0, 1\'000) * 1000ull;', "static const uint64_t v = 0;" + X, 1),
        ('const uint64_t ns = env_num("KYTY_BC5_TIMERSLACK_NS", 0, 50\'000);', "const uint64_t ns = 0;" + X, 1),
    ],
}
GONE = ["BC5_R3_REWIND_CATCH", "BC5_R3_DROP_CATCH", "KYTY_BC5_NAMES_FAST", "KYTY_BC5_VMA_FAST", "BC5_DIRECT_ACB_INHERIT", "BC5_DIRECT_ACB_CS_PREFIX",
        "BC5_DIRECT_INHERIT_PROG_CAP", "BC5_DIRECT_INHERIT_CENSUS_CAP", "BC5_DIRECT_FL_SKIP_ES", "BC5_DIRECT_FL_MESHLET_SAMPLE", "BC5_DIRECT_ZERO_SKIP",
        "BC5_DIRECT_ZERO_NAMES", "BC5_GUARD_ZSKIP_POLL_SUBMIT", "BC5_DIRECT_RESET_LABELS_ADD", "BC5_GUARD_FILE", "BC5_GUARD_FILE_ROOT", "BC5_GUARD_PSI",
        "BC5_GUARD_APPLY_MIN_MS", "KYTY_BC5_MEMORY_FROM_PARAM", "KYTY_BC5_MIN_FLIP_RATE", "KYTY_BC5_LOAD_DELAY", "KYTY_BC5_RING_POLL_US",
        "KYTY_BC5_RING_SPIN_US", "KYTY_BC5_MUTEX_SPIN_US", "KYTY_BC5_TIMERSLACK_NS"]
n = 0
texts = {}
for rel, edits in EDITS.items():
    p = root + "/" + rel
    s = open(p, encoding="utf-8", newline="").read()
    assert "exp 0419: option removed" not in s, rel
    for old, new, cnt in edits:
        assert s.count(old) == cnt, (rel, old[:70], s.count(old), cnt)
        s = s.replace(old, new)
        n += cnt
    # exp 0412's K1r (when the unit has it) refused to run beside the zero skip: that half of its check goes with the word
    k = 'std::getenv("BC5_DIRECT_ZERO_SKIP") != nullptr || std::getenv("BC5_GUARD_PIN_CAP") != nullptr'
    assert s.count(k) in (0, 1), rel
    if k in s:
        s = s.replace(k, 'std::getenv("BC5_GUARD_PIN_CAP") != nullptr' + X)
        n += 1
    open(p, "w", encoding="utf-8", newline="").write(s)
    texts[rel] = s
left = []
for name in GONE:
    for rel, s in texts.items():
        for tag in ('getenv("%s")' % name, 'take("%s")' % name, 'env_num("%s"' % name):
            if tag in s:
                left.append((name, rel))
assert not left, left
print("delete, phase 1: %d read sites made constant; %d words can no longer be set (+ the four recovery words read through kM11Names)" % (n, len(GONE)))
