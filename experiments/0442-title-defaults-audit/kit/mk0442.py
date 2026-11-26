#!/usr/bin/env python3
"""BC5 experiment 0442 (tag tg442): the generic rows of kTitleDefaults moved to every title (decision D26, F896).
    mk0442.py <orig dir> <out dir>
<orig dir> holds the shared tree's files at patch 589ef163: switch_defaults.hpp (48ae1cd6), bc5LleAgc.cpp (ed489aca),
and settingsOverlay.cpp (0acb8d6b). <out dir> gets the edited three plus the new header idraws0442.hpp. The backend
(direct.cpp, the count modes, HOST_INDIRECT and Device::map_alias removed) is the branch's backend/, built as it is.

switch_defaults.hpp:
  G0  the inert row BC5_GUARD_LEARN_LOG and the hook row BC5_DIRECT_SKIP_PGM=0 deleted; the table's stale comment
      corrected (exp 0413's 5-6 s end was F816, not the library words; KYTY_BC5_SWITCH_DEFAULTS is in kIgnored)
  G1-G3 the twenty library words, G4 APR_PARALLEL / REMEMBER_UNMAPPED / MEC_INDIRECT, G6 GPU_CHECK / CS_PREFIX /
      INDIRECT_DRAWS=multi / DMA_SNAPSHOT, G7 LAZY_RELEASE: deleted from TITLE2's rows and put, with the same values,
      into a NEW table kGeneric0442 applied for every title right after kSoft with setenv(name, value, 0), so NAME=0
      in the environment turns each off. A new table, not kSoft's end, so exp 0439's bake (which appends after kSoft's
      last row and inserts BC5_T3 rows after kTitleDefaults' header) applies before or after this one unchanged.
  G7  kTitleForced emptied: BC5_GUARD_SPLIT stays a TITLE2 row (G8, it goes with ALIASES) and is now a plain row.
  Left: TITLE2's DMA_SYNC and FLAT_APERTURE (G5, exp 0439), GUARD_SPLIT, AMM_PRT, ALIASES, GPU_CHECK_PRODUCT,
      SHADOW_LABELS, HOST_INDIRECT (G8).
bc5LleAgc.cpp: BC5_DIRECT_INDIRECT_DRAWS through bc5/idraws0442.hpp: unset, empty and "0" are off (today "0" let
  DRAW_INDIRECT through and turned on the drop after a given-up wait).
settingsOverlay.cpp: the first-title compare uses its run-time TITLE_ID TITLE1B (F863), not the image name TITLE1.
Stage 2 (tag nl442, the top session's decision of 2026-11-22 on the maintainer's order of 2026-11-13: nothing learned
  stays): the aliases and their file, GUARD_SPLIT, GUARD_LEARN_LOG and alias_learn, the zero skip's learned-window guard
  and its seam, the m11 learn refusal; TITLE2's rows GUARD_SPLIT, ALIASES, HOST_INDIRECT. See the stage's comment.
Bake 1a (the top session, 2026-11-22, after the lean A/B of bake 1 and D28): MK0442_KEEP="<row names>" (comma or
  space separated, each one of GENERIC's) leaves those rows exactly where they are, TITLE2 rows with their values, each
  marked "D28: cost on the first title being looked for"; they are not in kGeneric0442. MK0442_LEAN_GONE_OUT=1 compiles
  kGone0442's report and unset out of the lean build (#ifndef BC5_LEAN): in lean the gone words have no reader at all.
  With neither set the output is byte for byte bake 1's.
Every edit must match exactly once; bytes in, bytes out (LF)."""
import hashlib, os, re, sys

orig, out = sys.argv[1], sys.argv[2]
PINS = {"switch_defaults.hpp": "48ae1cd6", "bc5LleAgc.cpp": "ed489aca", "settingsOverlay.cpp": "0acb8d6b",
        "load_stat.hpp": "e4090056", "hostMenu.cpp": "34546c89", "hostInput.cpp": "83ef5bef"}
# the TITLE2 rows that become every title's, in the table's order, with their groups
GENERIC = [
    ("G7", "BC5_DIRECT_LAZY_RELEASE", "30,eager", "orphan release of unused direct-memory chunks (exps 0401, 0412; F843)"),
    ("G4", "BC5_DIRECT_MEC_INDIRECT", "1", "F91"),
    ("G6", "BC5_DIRECT_GPU_CHECK", "1", "F106"),
    ("G4", "BC5_DIRECT_REMEMBER_UNMAPPED", "1", "F163"),
    ("G4", "KYTY_BC5_APR_PARALLEL", "8", "F166"),
    ("G6", "BC5_DIRECT_DMA_SNAPSHOT", "4096", "F172"),
    ("G6", "BC5_DIRECT_CS_PREFIX", "1", "F321"),
    ("G6", "BC5_DIRECT_INDIRECT_DRAWS", "multi", "F108, F112"),
] + [("G1-G3", w, "1", "exp 0405 port (audit 0413 rows A15-A17, A21, A22)") for w in (
    "KYTY_BC5_SAVEDATA_MEMORY_FIXES", "KYTY_BC5_SAVEDATA_DELETE_BUSY", "KYTY_BC5_SAVEDATA_ALIASES", "KYTY_BC5_HTTP2_FIXES",
    "KYTY_BC5_PAD_OPEN_EXT", "KYTY_BC5_JSON2_FIXES", "KYTY_BC5_ULT_FIXES", "KYTY_BC5_USERSERVICE_VALUES",
    "KYTY_BC5_SYSTEMSERVICE_VALUES", "KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000", "KYTY_BC5_AUDIOOUT_CHECKS",
    "KYTY_BC5_AUDIOIN_CHECKS", "KYTY_BC5_NGS2_RACK_FIX", "KYTY_BC5_FW_PAD", "KYTY_BC5_LOAD_ZLIB", "KYTY_BC5_LOAD_JPEG",
    "KYTY_BC5_LOAD_IME", "KYTY_BC5_LOAD_NPCOMMON", "KYTY_BC5_LOAD_NPMANAGER", "KYTY_BC5_LOAD_NPTROPHY")]
DELETED = [("BC5_GUARD_LEARN_LOG", "2"), ("BC5_DIRECT_SKIP_PGM", "0")]
KEEP = [w for w in re.split(r"[,\s]+", os.environ.get("MK0442_KEEP", "")) if w]
assert len(set(KEEP)) == len(KEEP) and all(w in [g[1] for g in GENERIC] for w in KEEP), ("MK0442_KEEP", KEEP)
LEAN_GONE_OUT = os.environ.get("MK0442_LEAN_GONE_OUT") == "1"
RT_OUT = os.environ.get("MK0442_RT_OUT") == "1"  # bake 1d: the ray-tracing switch (exp 0273/0278) removed whole
COST_FIX = os.environ.get("MK0442_COST_FIX") == "1"  # bake 1c (D28): the unit's cost fixes, each with its off-word
KEEP_MARK = ("    // exp 0442 bake 1b (D28): temporary, moves to every title with its cost fix. Console behaviour or a host measure\n"
             "    // with a cost on the first title (exp 0442's lean A/B runs 1-3); this is the row's existing state, not a new per-title fix.\n")


def rd(name):
    b = open(os.path.join(orig, name), "rb").read()
    got = hashlib.md5(b).hexdigest()[:8]
    # MK0442_ON_0439=1: the header may be exp 0439's bake output (mkbk439.py on 48ae1cd6, marked by BC5_T3), so this
    # kit applies after exp 0439's as well as before it
    on439 = name == "switch_defaults.hpp" and os.environ.get("MK0442_ON_0439") == "1" and b"#define BC5_T3 " in b
    assert got == PINS[name] or on439, f"{name} is {got}, not {PINS[name]}"
    t = b.decode("utf-8")
    assert "\r" not in t, name + ": CRLF"
    return t


def once(t, old, new, what):
    n = t.count(old)
    assert n == 1, f"{what}: {n} matches"
    return t.replace(old, new)


# ---- switch_defaults.hpp ----
h = rd("switch_defaults.hpp")
assert "kGeneric0442" not in h
for _, w, v, _ in GENERIC + [(None, w, v, None) for w, v in DELETED]:
    rows = re.findall(r'^[ \t]*\{BC5_T2, "' + re.escape(w) + r'", "' + re.escape(v) + r'"\},[^\n]*\n', h, re.M)
    assert len(rows) == 1, (w, len(rows))
    if w in KEEP:  # bake 1a: the row stays where it is, marked
        h = h.replace(rows[0], KEEP_MARK + rows[0])
        continue
    h = h.replace(rows[0], "")
    assert f'"{w}"' not in h.split("kTitleDefaults[] = {", 1)[1].split("#undef BC5_T2", 1)[0], w + " still a title row"
h = once(h, "    // the twenty library words of audit rows A15, A16, A17, A21, A22 (launcher lines 59-67)\n", "", "library comment")
h = once(h,
         "// line, which is all this needs before any static initializer runs. KYTY_BC5_TITLE_DEFAULTS=0 skips the table, and so\n"
         "// does KYTY_BC5_SWITCH_DEFAULTS=0.\n"
         "// Why per title and not general: for 14 of the direct-path words no first-title run is on record, and four or more of the\n"
         "// twenty library words together end the first title at 5-6 s (exp 0413). A word moves up to kDefaults when it has a run on\n"
         "// both titles. The heap-name lists, the RT program list and every path stay in the launcher (title data and paths).\n",
         "// line, which is all this needs before any static initializer runs. KYTY_BC5_TITLE_DEFAULTS=0 skips the table\n"
         "// (KYTY_BC5_SWITCH_DEFAULTS is in kIgnored since exp 0419 and skips nothing).\n"
         "// exp 0442 (D26, F896: no per-title fixes): the generic rows moved to kGeneric0442 (every title). Exp 0413's\n"
         "// \"the library words end the first title at 5-6 s\" was the host's own F816 (CommandBufferSetBuffer), fixed since 2026-11-12.\n"
         "// What is left here: the G5 rows exp 0439 moves (DMA_SYNC, FLAT_APERTURE) and the G8 rows that need a general\n"
         "// replacement first (GUARD_SPLIT with ALIASES, AMM_PRT, ALIASES, GPU_CHECK_PRODUCT, SHADOW_LABELS, HOST_INDIRECT;\n"
         "// experiments/0442-title-defaults-audit). The heap-name lists, the RT program list and every path stay in the\n"
         "// launcher (title data and paths).\n", "table comment")
h = once(h, 'inline constexpr const char* kTitleForced[] = {"BC5_DIRECT_LAZY_RELEASE", "BC5_GUARD_SPLIT", nullptr};\n',
         '// exp 0442: empty. LAZY_RELEASE is every title\'s (kGeneric0442) with its off-word; GUARD_SPLIT is a plain row.\n'
         'inline constexpr const char* kTitleForced[] = {nullptr};\n', "kTitleForced")
rows = ""
for g in ("G1-G3", "G4", "G6", "G7"):
    rows += {"G1-G3": "    // G1-G3: the twenty system-library ports and fixes (every title by the port rule; the 0413 claim was F816)\n",
             "G4": "    // G4: host speed, timing only\n",
             "G6": "    // G6: submission changes (the run script can turn this group off by its off-words)\n",
             "G7": "    // G7: memory mapping (the run script can turn this group off by its off-word)\n"}[g]
    for gg, w, v, why in GENERIC:
        if gg == g and w not in KEEP:
            rows += f'    {{"{w}", "{v}"}}, // {why}\n'
table = ("// exp 0442 (tag tg442; D26, F896): the generic rows of TITLE2's kTitleDefaults, for EVERY title, with their values\n"
         "// unchanged. Applied after kSoft with setenv(name, value, 0): a value in the environment wins, NAME=0 turns one off.\n"
         "// A table of its own so exp 0439's bake (kSoft's end, kTitleDefaults' head) and this one apply in either order.\n"
         + ("// exp 0442 bake 1b (D28): kept as temporary TITLE2 rows, each moves to every title with its cost fix: "
            + ", ".join(KEEP) + ".\n" if KEEP else "")
         + "inline constexpr Default kGeneric0442[] = {\n" + rows + "    {nullptr, nullptr}};\n\n")
h = once(h, "// exp 0419: words whose option is removed and whose code default (the value when unset) is the tested behaviour.\n",
         table + "// exp 0419: words whose option is removed and whose code default (the value when unset) is the tested behaviour.\n",
         "kIgnored comment (insertion point)")
h = once(h,
         "\tfor (const Default* d = kSoft; d->name != nullptr; d++) {\n\t\tsetenv(d->name, d->value, 0);\n\t}\n",
         "\tfor (const Default* d = kSoft; d->name != nullptr; d++) {\n\t\tsetenv(d->name, d->value, 0);\n\t}\n"
         "\tfor (const Default* d = kGeneric0442; d->name != nullptr; d++) { // exp 0442: the generic rows, every title\n"
         "\t\tsetenv(d->name, d->value, 0);\n\t}\n", "the kSoft loop")

# ---- bc5LleAgc.cpp ----
u = rd("bc5LleAgc.cpp")
u = once(u, '#include "bc5/direct.hpp"\n', '#include "bc5/direct.hpp"\n#include "bc5/idraws0442.hpp" // exp 0442: BC5_DIRECT_INDIRECT_DRAWS, "0" is off\n', "include")
u = once(u,
         '\t\tconst char* idraws = std::getenv("BC5_DIRECT_INDIRECT_DRAWS");\n'
         '\t\tif (idraws == nullptr) v.insert(v.end(), {0x24, 0x2c, 0x38});\n'
         '\t\telse if (std::strcmp(idraws, "multi") != 0) v.insert(v.end(), {0x2c, 0x38});\n',
         '\t\tconst bc5::IndirectDraws idraws = bc5::indirect_draws_mode(std::getenv("BC5_DIRECT_INDIRECT_DRAWS")); // exp 0442: "0" is off\n'
         '\t\tif (idraws == bc5::IndirectDraws::off) v.insert(v.end(), {0x24, 0x2c, 0x38});\n'
         '\t\telse if (idraws == bc5::IndirectDraws::draw) v.insert(v.end(), {0x2c, 0x38});\n', "extra_drop")
u = once(u, 'chain_given_up_at(chain, q) && std::getenv("BC5_DIRECT_INDIRECT_DRAWS") != nullptr) {',
         'chain_given_up_at(chain, q) && bc5::indirect_draws_mode(std::getenv("BC5_DIRECT_INDIRECT_DRAWS")) != bc5::IndirectDraws::off) { // exp 0442',
         "given-up drop")
assert u.count('getenv("BC5_DIRECT_INDIRECT_DRAWS")') == 2

# ---- stage 2 (tag nl442, the top session's decision of 2026-11-22: nothing learned stays, in any form) ----
# bc5LleAgc.cpp: the aliases (exp 0056: the file ~/bc5-work/direct-aliases-pkg.txt, its read and mapping), BC5_GUARD_SPLIT
# (g412c) with it, BC5_GUARD_LEARN_LOG (mr412::learn_log) and the uncalled alias_learn(), the zero skip's learned-window
# scope guard (ZLearned, t_force_learned) and its seam bc5_zsk0401_hint, the m11 learn refusal (BC5_DIRECT_LEARN_GUEST_ONLY,
# m11_learn_refused, bc5_m11_0401_learn_refused), the BC5_DIRECT_LEARNED comment. switch_defaults.hpp: TITLE2's rows
# BC5_GUARD_SPLIT, BC5_DIRECT_ALIASES, BC5_DIRECT_HOST_INDIRECT. HOST_INDIRECT's code is in the backend (removed there).
u = once(u, "inline int learn_log() {\n\tstatic const int v = env_digit(\"BC5_GUARD_LEARN_LOG\", 2);\n\treturn v;\n}\n", "", "learn_log")
u = once(u, "static bool guard0412_split(); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n", "", "guard0412_split decl")
u = once(u, "\tconst bool          splits = !bc5::env_on(std::getenv(\"BC5_DIRECT_ALIASES\")) || guard0412_split(); // exp 0412 (tag g412c)\n",
         "\tconst bool          splits = true; // exp 0442: the aliases are gone, so a BO may always be split\n", "splits")
u = once(u, "// learned window is marked by a scope guard (ZLearned); ", "// learned window was marked by a scope guard (ZLearned, removed in exp 0442); ", "zskip comment")
u = once(u, "static thread_local bool t_force_learned = false; // direct_force called for a learned window (map_window)\n", "", "t_force_learned")
u = once(u, "\tif (S.kind != 0 || t_force_learned || g_zskip.empty()) return false;\n", "\tif (S.kind != 0 || g_zskip.empty()) return false;\n", "zskip_hint_back")
u = once(u, "// Experiment 0379, in map_window: direct_force for a learned window leaves skipped chunks skipped (exp 0401 e7: a scope\n"
            "// guard instead of 0379's set, call, reset around the call, so map_window's own lines stay as they are).\n"
            "struct ZLearned {\n\texplicit ZLearned(bool learned) { t_force_learned = learned; }\n\t~ZLearned() { t_force_learned = false; }\n"
            "\tZLearned(const ZLearned&)            = delete;\n\tZLearned& operator=(const ZLearned&) = delete;\n};\n", "", "ZLearned")
u = once(u, "// 15 g_zflag[a] (255: none), 16 t_force_learned on this thread,", "// 15 g_zflag[a] (255: none), 16 always 0 (exp 0442: was t_force_learned),", "case 16 comment")
u = once(u, "\tcase 16: return t_force_learned ? 1 : 0;\n", "\tcase 16: return 0; // exp 0442: no learned windows\n", "case 16")
u = once(u, "// zskip_hint_back for chunk c, as direct_force calls it for a hint window (learned 0) or, under map_window's guard, for a\n"
            "// learned window (learned 1). 1 when the chunk left the skip set.\n"
            "extern \"C\" int bc5_zsk0401_hint(int kind, uint64_t c, int learned, uint64_t* blocks) {\n"
            "\tDState S    = zsk_state(kind, *blocks);\n\tbool   back = false;\n\t{\n\t\tconst ZLearned guard(learned != 0);\n"
            "\t\tback = zskip_hint_back(S, c);\n\t}\n\t*blocks = S.blocks;\n\treturn back ? 1 : 0;\n}\n", "", "bc5_zsk0401_hint")
u = once(u, "static void guard0412_after_cuts(size_t cuts); // exp 0412 (tag g412c)\nstatic void aliases_apply(bool force);\n", "", "after_cuts/aliases decls")
a0 = "// Regions learned from GPU VM faults (BC5_DIRECT_LEARNED, default ~/bc5-work/direct-learned.txt,\n"
a1 = "// Experiment 0401 series e11 (tag m11, mkm110401.py;"
assert u.count(a0) == 1 and u.count(a1) == 1 and u.index(a0) < u.index(a1)
u = u[:u.index(a0)] + ("// exp 0442 (tag nl442): the learned windows (BC5_DIRECT_LEARNED, gone since exp 0412 nl412) and the aliases of\n"
                       "// experiment 0056 (BC5_DIRECT_ALIASES, the file ~/bc5-work/direct-aliases-pkg.txt) are removed with every reader:\n"
                       "// nothing a past run wrote is read. F110's question (the PS5 GPU and address bits 47:40) is open; a fault there is a\n"
                       "// bug with a record, fixed at its cause.\n") + u[u.index(a1):]
u = once(u, "//   BC5_DIRECT_LEARN_GUEST_ONLY     a fault whose learned window holds no guest range is not learned or saved.\n",
         "//   (the third, BC5_DIRECT_LEARN_GUEST_ONLY, removed in exp 0442 with the learned windows)\n", "m11 comment")
u = once(u, "\"BC5_DIRECT_RESET_LABELS\", \"BC5_DIRECT_LEARN_GUEST_ONLY\", \"BC5_DIRECT_RESET_LABEL_JOURNAL\"}",
         "\"BC5_DIRECT_RESET_LABELS\", \"(removed)\", \"BC5_DIRECT_RESET_LABEL_JOURNAL\"}", "kM11Names")
u = once(u, "// BC5_DIRECT_LEARN_GUEST_ONLY: true when the window [lo, lo + n) that learned_add would save for fault_addr holds no guest range.\n"
            "static bool m11_learn_refused(uint64_t fault_addr, uint64_t lo, uint64_t n) {\n\tif (!m11_on(2)) return false;\n\tm11_switch_line();\n"
            "\tif (g_m11_guest_in(lo, lo + n)) return false;\n"
            "\tjournal(\"e11: fault 0x%\" PRIx64 \": no guest range in its window 0x%\" PRIx64 \"+0x%\" PRIx64 \", not learned\\n\", fault_addr, lo, n);\n"
            "\treturn true;\n}\n", "", "m11_learn_refused")
u = once(u, "extern \"C\" int bc5_m11_0401_learn_refused(uint64_t fault_addr) {\n"
            "\tconst uint64_t lo = (fault_addr & ~0x3ffffffull) > 0x2000000ull ? (fault_addr & ~0x3ffffffull) - 0x2000000ull : 0; // learned_add's window\n"
            "\treturn m11_learn_refused(fault_addr, lo, 0x6000000ull) ? 1 : 0;\n}\n", "", "bc5_m11_0401_learn_refused")
g0 = "// BC5_GUARD_SPLIT (g412c).\nstatic bool guard0412_split() {\n"
g1 = "// BC5_GUARD_CAP_ACT. The chunks of the direct file the cap has put off, sorted; the sync thread's own.\n"
assert u.count(g0) == 1 and u.count(g1) == 1 and u.index(g0) < u.index(g1)
u = u[:u.index(g0)] + u[u.index(g1):]
u = once(u, "\tguard0412_after_cuts(lzr.done.size()); // exp 0412 (tag g412c): BC5_GUARD_SPLIT\n", "", "after_cuts call")
u = once(u, "\t\t// exp 0419: alias_learn (experiment 0056) is no longer called: no window is learned from a GPU fault\n", "", "alias_learn note")
u = once(u, "\taliases_apply(false); // experiment 0056\n", "", "aliases_apply call")
u = once(u, "// max_cuts: BOs cut per pass; splits: false when a BO may only go whole (BC5_DIRECT_ALIASES: the aliases of a BO's\n"
            "// mappings come back only at the next aliases_apply); zero_skip:",
         "// max_cuts: BOs cut per pass; splits: false when a BO may only go whole (always true since exp 0442: the aliases of\n"
         "// experiment 0056 that kept a BO whole are gone); zero_skip:", "splits comment")
g2a = "//   BC5_GUARD_SPLIT=1              (the third build, g412c) the lazy release"
g2b = "//   BC5_GUARD_APPLY_MIN_MS=<ms>"
assert u.count(g2a) == 1 and u.count(g2b) == 1 and u.index(g2a) < u.index(g2b)
u = u[:u.index(g2a)] + "//   (BC5_GUARD_SPLIT, g412c: removed in exp 0442 with the aliases it worked around)\n" + u[u.index(g2b):]
for gone in ("alias_learn", "aliases_apply", "aliases_on", "alias_path", "direct-aliases-pkg.txt\";", "learn_log", "ZLearned(", "t_force_learned ?",
             "guard0412_split", "m11_learn_refused", "bc5_zsk0401_hint", "\"BC5_DIRECT_ALIASES\"", "\"BC5_GUARD_SPLIT\"", "\"BC5_GUARD_LEARN_LOG\"",
             "\"BC5_DIRECT_LEARN_GUEST_ONLY\"", "map_alias", "unmap_aliases"):
    assert gone not in u, "bc5LleAgc.cpp still holds " + gone
# switch_defaults.hpp: the three learned rows
for w, v in (("BC5_GUARD_SPLIT", "1"), ("BC5_DIRECT_ALIASES", "1"), ("BC5_DIRECT_HOST_INDIRECT", "learn:1100000000")):
    rows = re.findall(r'^[ \t]*\{BC5_T2, "' + re.escape(w) + r'", "' + re.escape(v) + r'"\},[^\n]*\n', h, re.M)
    assert len(rows) == 1, (w, len(rows))
    h = h.replace(rows[0], "")
h = once(h, "// exp 0442: empty. LAZY_RELEASE is every title's (kGeneric0442) with its off-word; GUARD_SPLIT is a plain row.\n",
         "// exp 0442: empty. LAZY_RELEASE is every title's (kGeneric0442) with its off-word; GUARD_SPLIT is gone (tag nl442).\n", "kTitleForced comment")
h = once(h, "// replacement first (GUARD_SPLIT with ALIASES, AMM_PRT, ALIASES, GPU_CHECK_PRODUCT, SHADOW_LABELS, HOST_INDIRECT;\n"
            "// experiments/0442-title-defaults-audit).",
         "// cause or a source first (AMM_PRT, GPU_CHECK_PRODUCT, SHADOW_LABELS; experiments/0442-title-defaults-audit). The learned rows\n"
         "// (GUARD_SPLIT, ALIASES, HOST_INDIRECT, GUARD_LEARN_LOG) are gone with their code (tag nl442, the maintainer's order of 2026-11-13).",
         "table comment nl442")
h = h.replace("// What is left here: the G5 rows exp 0439 moves (DMA_SYNC, FLAT_APERTURE) and the G8 rows that need a general\n",
              "// What is left here: the G5 rows exp 0439 moves (DMA_SYNC, FLAT_APERTURE) and the G8 rows that need a\n")
for gone in ('"BC5_GUARD_SPLIT"', '"BC5_DIRECT_ALIASES"', '"BC5_DIRECT_HOST_INDIRECT"', '"BC5_GUARD_LEARN_LOG"'):
    assert gone not in h, "switch_defaults.hpp still holds " + gone
# the learned words that are gone: one line each when one is still set (a launcher or a shortcut that names it), then unset
h = once(h, "// exp 0419: words whose option is removed and whose code default (the value when unset) is the tested behaviour.\n",
         "// exp 0442 (tag nl442): the learned words, gone with their code (the maintainer's order of 2026-11-13: nothing learned\n"
         "// stays). A launcher that still sets one gets one line on stderr; the word is then taken out of the environment.\n"
         "inline constexpr const char* kGone0442[] = {\"BC5_DIRECT_ALIASES\", \"BC5_GUARD_SPLIT\", \"BC5_GUARD_LEARN_LOG\", \"BC5_DIRECT_HOST_INDIRECT\",\n"
         "                                            \"BC5_DIRECT_LEARNED\", \"BC5_DIRECT_LEARN_GUEST_ONLY\", nullptr};\n\n"
         "// exp 0419: words whose option is removed and whose code default (the value when unset) is the tested behaviour.\n",
         "kGone0442 table")
h = once(h, "\tfor (const char* const* n = kIgnored; *n != nullptr; n++) {\n\t\tunsetenv(*n);\n\t}\n",
         "\tfor (const char* const* n = kGone0442; *n != nullptr; n++) { // exp 0442 (tag nl442)\n"
         "\t\tif (const char* v = std::getenv(*n); v != nullptr) {\n"
         "\t\t\tstd::fprintf(stderr, \"[bc5] exp 0442: %s=%s is set, but the word is gone (nothing learned is read): ignored\\n\", *n, v);\n"
         "\t\t\tunsetenv(*n);\n\t\t}\n\t}\n"
         "\tfor (const char* const* n = kIgnored; *n != nullptr; n++) {\n\t\tunsetenv(*n);\n\t}\n", "kGone0442 loop")
if LEAN_GONE_OUT:  # bake 1a: in lean the gone words have no reader; the report and the unset are normal-build only
    h = once(h, "inline constexpr const char* kGone0442[] = {",
             "#ifndef BC5_LEAN // exp 0442 bake 1a: lean carries no report; nothing in lean reads these words\n"
             "inline constexpr const char* kGone0442[] = {", "kGone0442 lean open")
    h = once(h, "\"BC5_DIRECT_LEARNED\", \"BC5_DIRECT_LEARN_GUEST_ONLY\", nullptr};\n",
             "\"BC5_DIRECT_LEARNED\", \"BC5_DIRECT_LEARN_GUEST_ONLY\", nullptr};\n#endif\n", "kGone0442 lean close")
    h = once(h, "\tfor (const char* const* n = kGone0442; *n != nullptr; n++) { // exp 0442 (tag nl442)\n",
             "#ifndef BC5_LEAN\n\tfor (const char* const* n = kGone0442; *n != nullptr; n++) { // exp 0442 (tag nl442)\n", "loop open")
    h = once(h, "\t\t\tunsetenv(*n);\n\t\t}\n\t}\n\tfor (const char* const* n = kIgnored;",
             "\t\t\tunsetenv(*n);\n\t\t}\n\t}\n#endif\n\tfor (const char* const* n = kIgnored;", "loop close")

# ---- stage 3 (tag rn442, the top session's word of 2026-11-22): names that said "learned" with no learned data in them.
# Behaviour unchanged. The journal texts that change (no shared tool parses them; experiments/ scripts of exps 0231-0412
# do, as history): "learned apply: " -> "heap guards apply: ", "learned_apply took" -> "heap_guards_apply took",
# "...: learned_apply at most once per that" -> "...: heap_guards_apply at most once per that", "would learn (exp 0412,
# tag mr412)" -> "fault record (exp 0412, tag mr412)"; the load-stat names "learned", "learned_apply", "learned_changed"
# -> "heap_guards", "heap_guards_apply", "heap_guards_changed".
n_la = u.count("learned_apply")
assert n_la >= 10, n_la
u = u.replace("learned_apply", "heap_guards_apply")   # the function (exp 0037's zero guards behind the eager heaps), its calls, comments
u = once(u, 'journal("learned apply: %.1f ms', 'journal("heap guards apply: %.1f ms', "learned apply journal")
n_wl = u.count("mr412_would_learn")
assert n_wl == 4, n_wl
u = u.replace("mr412_would_learn", "mr412_fault_record")  # the GPU-fault record (his rule: a fault is a bug with a record)
u = once(u, 'journal("would learn (exp 0412, tag mr412): t %.3f s:', 'journal("fault record (exp 0412, tag mr412): t %.3f s:', "would learn journal")
u = once(u, "bc5::load_stat::kLearned); // experiment 0415 (ls415)", "bc5::load_stat::kHeapGuards); // experiment 0415 (ls415)", "kLearned use")
u = once(u, "bc5::load_stat::kLearnedApply); // experiment 0415 (ls415d)", "bc5::load_stat::kHeapGuardsApply); // experiment 0415 (ls415d)", "kLearnedApply use")
for gone in ("learned_apply", "mr412_would_learn", "would learn (", "kLearned"):
    assert gone not in u, "bc5LleAgc.cpp still holds " + gone
ls = rd("load_stat.hpp")
ls = once(ls, "\tkLearned,        // learned_apply\n", "\tkHeapGuards,     // heap_guards_apply (exp 0442: renamed; no learned data in it)\n", "enum kLearned")
ls = once(ls, "\tkLearnedApply,   // learned_apply past its \"same layout\" return: n, time\n",
          "\tkHeapGuardsApply,   // heap_guards_apply past its \"same layout\" return: n, time\n", "enum kLearnedApply")
ls = once(ls, "\tkLearnedChanged, // ... windows that mapped something: n, items = bytes\n",
          "\tkHeapGuardsChanged, // ... windows that mapped something: n, items = bytes\n", "enum kLearnedChanged")
ls = once(ls, '"anon_sync", "learned",     "apr_buffer",', '"anon_sync", "heap_guards", "apr_buffer",', "name learned")
ls = once(ls, '"fast_diff",   "learned_apply",   "learned_changed",', '"fast_diff",   "heap_guards_apply", "heap_guards_changed",', "names apply/changed")
for gone in ("kLearned", '"learned', "learned_apply"):
    assert gone not in ls, "load_stat.hpp still holds " + gone

# ---- stage 4 (tag zl442, the top session's word of 2026-11-22: B8): exp 0379's zero list removed whole. Its option has been
# removed since exp 0419 (zskip_path() returned null), F818 calls it unsound by design, and the list a run wrote was read
# by later runs (a learned artefact). Gone: the inlined zero_skip.hpp (its standard #includes kept), the section
# "experiment 0379: the zero list" with the canary, g_zskip, zskip_*, the seams bc5_zsk0401_* (exp 0401's harness
# zsk0401.cpp, history), the zero-skip poll zp412 (zpoll412_submit), lzr_zero_skip / lzr_zero_name, and every call.
# Left as it is: Lzr0401's own "zero" chunk class and plan() parameter (the lazy release's library), now always false.
import re as _re


def drop_line(t, sub, n=1, what=""):
    lines = t.split("\n")
    hits = [i for i, ln in enumerate(lines) if sub in ln]
    assert len(hits) == n, (what or sub[:60], len(hits))
    for i in reversed(hits):
        del lines[i]
    return "\n".join(lines)


def cut_between(t, start, end, new, what, include_end=True):
    assert t.count(start) == 1, (what, "start", t.count(start))
    a = t.index(start)
    b = t.index(end, a + len(start))
    b = b + len(end) if include_end else b
    return t[:a] + new + t[b:]


# Z1: the inlined header; its standard includes stay for the rest of the unit
a = "// ---- experiment 0379's backend/include/bc5/zero_skip.hpp (782ca0e9) lines 13-228, inlined by exp 0401's mkzsk0401.py ----\n"
e = _re.search(r"// ---- end of experiment 0379's zero_skip\.hpp -+\n", u)
assert u.count(a) == 1 and e is not None
blk = u[u.index(a):e.end()]
incs = "".join(ln + "\n" for ln in blk.split("\n") if ln.startswith("#include <"))
u = u[:u.index(a)] + "// exp 0442 (tag zl442): exp 0379's inlined zero_skip.hpp is gone with the zero list; its standard includes stay.\n" + incs + u[e.end():]
# Z2: the section, from its header to its end marker
a = "// ---- experiment 0379: the zero list (BC5_DIRECT_ZEROSCAN_AT/_OUT) and the skip (BC5_DIRECT_ZERO_SKIP) "
e = _re.search(r"// ---- end of experiment 0379's zero skip \(exp 0401 e7\) -+\n", u)
assert u.count(a) == 1 and e is not None and u.index(a) < e.start()
u = u[:u.index(a)] + "// exp 0442 (tag zl442): exp 0379's zero list and skip (scan, canary, take-back, seams) removed whole.\n" + u[e.end():]
# Z3: the lazy release's view of the skip
u = cut_between(u, "// Exp 0379's zero skip, read by its switch and heap names (BC5_DIRECT_ZERO_SKIP set; BC5_DIRECT_ZERO_NAMES, default\n",
                "static LzrPass lzr_pass(", "", "lzr_zero_skip/name", include_end=False)
u = once(u, "cov     = Lzr0401::covers(views, [](const DView& v) { return lzr_zero_name(v.name); });",
         "cov     = Lzr0401::covers(views, [](const DView&) { return false; }); // exp 0442: no zero list", "covers")
u = once(u, "32, splits, lzr_zero_skip());", "32, splits, false); // exp 0442: no zero list", "plan call")
# Z4: direct_sync_one
u = drop_line(u, "const bool zskip_new = zskip_sync_start(S, views);", 1, "zskip_new")
u = drop_line(u, "zskip_take_back(S, fd); // experiment 0379: CPU writes and canary hits take skipped chunks back", 1, "take back")
u = drop_line(u, "const bool zskip_on = S.kind == 0 && !g_zskip.empty();", 1, "zskip_on")
u = drop_line(u, "if (zskip_on && g_zskip.contains(c)) continue;", 2, "zskip_on continues")
u = once(u, "!k1r412::on() && g_zskip.empty() && !zskip_new &&", "!k1r412::on() &&", "x432 condition")
u = once(u, "k1r412::on(), !g_zskip.empty(), zskip_new, !x432_plain[x432_k],",
         "k1r412::on(), false, false, !x432_plain[x432_k], // exp 0442: slots 4, 5 were the zero skip's", "x432 reasons")
u = drop_line(u, "if (!g_zpieces.empty()) zskip_release(w.va, w.va + w.size);", 2, "zskip_release")
u = drop_line(u, "zskip_map(views); // experiment 0379", 1, "zskip_map")
# Z5: the hint take-back
u = drop_line(u, "if (zskip_hint_back(S, c) && S.forced.count(c) != 0) here += kDChunk;", 1, "hint back")
# Z6: K1r's refusal for the zero skip or the pin cap (both gone since exp 0419)
k0 = "\tstatic const bool refused = [] {\n\t\tconst bool r = false; /* exp 0419: BC5_DIRECT_ZERO_SKIP and BC5_GUARD_PIN_CAP are gone */\n"
assert u.count(k0) == 1
k_end = u.index("\tif (refused) return;\n", u.index(k0)) + len("\tif (refused) return;\n")
u = (u[:u.index(k0)] +
     "\tstatic const bool said = [] { // exp 0442: the refusal for the zero skip or the pin cap is gone with them\n"
     "\t\tjournal(\"k1r (exp 0412, tag k1r412): BC5_GUARD_K1R on: never-written parts of the views of direct memory are GPU-mapped read-only onto one zero buffer; nothing is pinned for them\\n\");\n"
     "\t\treturn true;\n\t}();\n\t(void)said;\n" + u[k_end:])
# Z7: the zero-skip poll before every submission (zp412)
u = cut_between(u, "// BC5 experiment 0412 (tag zp412, README section 40 and its correction, section 45): the decision of the zero skip's\n",
                "static void submit_one(const uint32_t* ib, uint32_t num_dwords, const char* kind);\n", "", "zp412 block", include_end=False)
u = drop_line(u, "zpoll412_submit(); // exp 0412 (tag zp412)", 1, "zpoll call")
# Z8: the reopen
u = drop_line(u, "zskip_disable(\"device reopen\"); // experiment 0379", 1, "zskip_disable")
# Z9: comments
u = once(u, "// view, or never seen under a view, is cut only with the \"eager\" word; a chunk of a zero-list heap (BC5_DIRECT_ZERO_SKIP,\n// exp 0379) never.",
         "// view, or never seen under a view, is cut only with the \"eager\" word (exp 0379's zero list, which kept its chunks,\n// is gone since exp 0442).", "lzr comment")
u = once(u, "; zero_skip: BC5_DIRECT_ZERO_SKIP is set. Updates st.chunks and", "; zero_skip: always false since exp 0442 (no zero list). Updates st.chunks and", "plan comment")
for gone in ("g_zskip", "zskip_", "ZERO_SKIP", "ZEROSCAN", "ZERO_NAMES", "bc5_zsk0401", "lzr_zero_skip", "lzr_zero_name", "zpoll412", "namespace zp412",
             "namespace bc5::zero_skip", "g_zpieces", "ZSKIP_POLL", "g_zcanary", "g_zstat"):
    assert gone not in u, "bc5LleAgc.cpp still holds " + gone

if "BC5_DIRECT_LAZY_RELEASE" in KEEP:  # bake 1a: the kTitleForced comment must not call it every title's
    h = once(h, "// exp 0442: empty. LAZY_RELEASE is every title's (kGeneric0442) with its off-word; GUARD_SPLIT is gone (tag nl442).\n",
             "// exp 0442: empty. LAZY_RELEASE is a TITLE2 row for now (bake 1a, D28) with its off-word; GUARD_SPLIT is gone (tag nl442).\n",
             "kTitleForced comment 1a")
CS_SKIP_BLOCK = '''// Experiment 0442 bake 1c (D28): BC5_DIRECT_0442_CS_SKIP, on unless "0". cs_inherit_at walks a graphics buffer that
// gets no other prefix up to its first dispatch, to its end when it has none, and reads every LOAD_SH_REG_INDEX pair
// table (guest memory) on the way; for a buffer with no DISPATCH_DIRECT/INDIRECT (0x15/0x16) it always returned -1. A
// header-only walk (packet headers, parsed as cs_inherit_at and ib_has_draw parse them) finds that first and skips the
// call: the same answer for every buffer, without the table reads.
static bool cs_skip0442() {
	static const bool on = [] {
		const char* e = std::getenv("BC5_DIRECT_0442_CS_SKIP");
		return !(e != nullptr && std::strcmp(e, "0") == 0);
	}();
	return on;
}
static bool ib_has_dispatch0442(const uint32_t* ib, uint32_t num_dwords) {
	for (uint32_t i = 0; i < num_dwords;) {
		const uint32_t h = ib[i], type = h >> 30u;
		uint32_t       len = 1;
		if (type == 3 || type == 0) { const uint32_t c = (h >> 16u) & 0x3fffu; len = c == 0x3fffu ? 1 : c + 2; }
		if (i + len > num_dwords) break;
		if (type == 3 && (((h >> 8u) & 0xffu) == 0x15 || ((h >> 8u) & 0xffu) == 0x16)) return true;
		i += len;
	}
	return false;
}
'''
if COST_FIX:  # bake 1c (D28), CS_SKIP: no cs_inherit_at walk (and no pair-table read) for a dcb with no dispatch
    u = once(u, '// The tracked compute registers (SH 0x204-0x3ff) as SET_SH_REG runs; *pgm = COMPUTE_PGM_LO/HI as an address.\n', CS_SKIP_BLOCK + '// The tracked compute registers (SH 0x204-0x3ff) as SET_SH_REG runs; *pgm = COMPUTE_PGM_LO/HI as an address.\n', "cs_skip decl")
    u = once(u, '\t\tconst int at = cs_inherit_at(ib, num_dwords, *g_dev->sorted_mappings());\n', '\t\tconst int at = cs_skip0442() && !ib_has_dispatch0442(ib, num_dwords) ? -1 : cs_inherit_at(ib, num_dwords, *g_dev->sorted_mappings()); // exp 0442 bake 1c (D28)\n', "cs_skip call")

if RT_OUT:  # bake 1d (the maintainer, 2026-11-22 18:05): exp 0273's ray-tracing switch out, ray tracing always on
    u = cut_between(u, "// Experiment 0273: the window's Emulation > Ray tracing switch. The pending value is taken at the next\n", '// Are every cross-queue wait of a compute IB (labels no earlier packet of it writes) satisfied?\n', "// exp 0442 bake 1d (the maintainer, 2026-11-22 18:05): exp 0273's ray-tracing switch is gone whole (the menu item, the\n// pending state, KYTY_BC5_RT, the drop of the second title's BVH build list KYTY_BC5_RT_BUILD_PGM). Ray tracing is\n// always on, as on the console; there is no off. Both words are in kGone0442.\n", "rt switch", include_end=False)
    u = cut_between(u, "\t\t\t// Experiment 0273: with the window's ray-tracing switch off, a dispatch of a program on the\n", '\t\t\tif (type == 3 && (op == 0x2c || op == 0x38) && len >= 10 && ib[q + 5] > 65536u) { // experiment 0054\n', "\t\t\t// exp 0442 bake 1d: no ray-tracing drop (exp 0273's build-list drop is gone; ray tracing is always on)\n", "rt drop", include_end=False)
    u = once(u, '\tBc5Gc::Direct::ApplyPendingRayTracing(); // experiment 0273: the switch takes effect at a frame boundary\n', "", "rt flip")
    for gone in ("g_rt_on", "g_rt_pending", "g_rt_dropped", "SetRayTracing", "GetRayTracing", "ApplyPendingRayTracing",
                 'getenv("KYTY_BC5_RT")', 'pgm_list("KYTY_BC5_RT_BUILD_PGM")'):
        assert gone not in u, "bc5LleAgc.cpp still holds " + gone
    h = once(h, '"BC5_DIRECT_LEARNED", "BC5_DIRECT_LEARN_GUEST_ONLY", nullptr};\n', '"BC5_DIRECT_LEARNED", "BC5_DIRECT_LEARN_GUEST_ONLY",\n                                            "KYTY_BC5_RT", "KYTY_BC5_RT_BUILD_PGM", nullptr}; // + bake 1d\n', "kGone0442 rt")
    hm = rd("hostMenu.cpp")
    hm = once(hm, "namespace Libs::Bc5Gc::Direct {\nvoid SetRayTracing(bool on); // bc5LleAgc.cpp, experiment 0273: the Emulation menu's switch\nbool GetRayTracing();\n} // namespace Libs::Bc5Gc::Direct\n\n", "", "hostMenu decl")
    hm = once(hm, '\t\t\t// Experiment 0273: the ray-tracing switch (default on; KYTY_BC5_RT=0 or the title\'s\n\t\t\t// RayTracing.<TITLE_ID>=off starts it off). It takes effect at the next flip and is saved per\n\t\t\t// title into the input configuration, as the Video tab saves RenderScale.<TITLE_ID>.\n\t\t\t{\n\t\t\t\tbool rt = Libs::Bc5Gc::Direct::GetRayTracing();\n\t\t\t\tif (ImGui::MenuItem("Ray tracing", nullptr, rt, !launcher)) {\n\t\t\t\t\trt = !rt;\n\t\t\t\t\tLibs::Bc5Gc::Direct::SetRayTracing(rt);\n\t\t\t\t\tSaveTitleSwitch("RayTracing", "ray tracing", rt);\n\t\t\t\t}\n\t\t\t}\n', "\t\t\t// exp 0442 bake 1d: no ray-tracing item (exp 0273's switch is gone; ray tracing is always on, as on the console)\n", "hostMenu item")
    hi = rd("hostInput.cpp")
    hi = once(hi, 'void   SetRayTracing(bool on); // bc5LleAgc.cpp, experiment 0273\n', "", "hostInput decl")
    hi = once(hi, '\t\tif (m_ray_tracing >= 0) out.emplace_back("RayTracing." + HostInputTitleId() + (m_ray_tracing == 1 ? "=on" : "=off")); // experiment 0273\n', "", "hostInput save")
    hi = once(hi, '\t[[nodiscard]] int    RayTracing() const { return m_ray_tracing; } // experiment 0273: -1 not set, 0 off, 1 on\n', "", "hostInput getter")
    hi = cut_between(hi, '\t\tif (left.size() > 11 && EqualNoCase(left.substr(0, 11), "RayTracing.")) { // experiment 0273, per title\n', '\t\tif (left.size() > 9 && EqualNoCase(left.substr(0, 9), "MangoHud.")) { // experiment 0301, per title\n', '\t\tif (left.size() > 11 && EqualNoCase(left.substr(0, 11), "RayTracing.")) { // exp 0442 bake 1d: accepted, ignored\n\t\t\t// Ray tracing is always on (exp 0273\'s switch is gone). An old RayTracing.<TITLE_ID>=... line of any title\n\t\t\t// loads, is reported once and is not written back; any value, never an error.\n\t\t\tstatic bool told = false;\n\t\t\tif (!told) {\n\t\t\t\ttold = true;\n\t\t\t\tstd::fprintf(stderr, "[bc5] exp 0442: input configuration %s: ignored (ray tracing is always on; the line is not written back)\\n",\n\t\t\t\t             std::string(line).c_str());\n\t\t\t}\n\t\t\treturn true;\n\t\t}\n\n', "hostInput parse", include_end=False)
    hi = once(hi, '\tint                  m_ray_tracing      = -1;  // experiment 0273: -1 not set (the environment decides), 0 off, 1 on\n', "", "hostInput member")
    assert hi.count('\tif (map->RayTracing() >= 0) Libs::Bc5Gc::Direct::SetRayTracing(map->RayTracing() == 1); // experiment 0273\n') == 2, "hostInput: the two SetRayTracing applies"
    hi = hi.replace('\tif (map->RayTracing() >= 0) Libs::Bc5Gc::Direct::SetRayTracing(map->RayTracing() == 1); // experiment 0273\n', "")
    for gone in ("m_ray_tracing", "SetRayTracing", "RayTracing()"):
        assert gone not in hi, "hostInput.cpp still holds " + gone
    for gone in ("SetRayTracing", "GetRayTracing", "\"Ray tracing\""):
        assert gone not in hm, "hostMenu.cpp still holds " + gone

# ---- settingsOverlay.cpp ----
s = rd("settingsOverlay.cpp")
s = once(s, '\t\tif (HostInputTitleId() != "TITLE1") {\n',
         '\t\t// exp 0442: the first title\'s run-time TITLE_ID is TITLE1B (F863); TITLE1 is its image name.\n'
         '\t\tif (HostInputTitleId() != "TITLE1B") {\n', "overlay compare")

idraws = ('// SPDX-License-Identifier: GPL-2.0-only\n'
          '// BC5 experiment 0442 (tag tg442): BC5_DIRECT_INDIRECT_DRAWS read as one mode in both of its places. Unset, empty and\n'
          '// "0" are off (the code default: DRAW_INDIRECT 0x24 and the multi-draws 0x2c/0x38 dropped, no drop after a given-up\n'
          '// wait); "multi" lets all of them through; any other value lets DRAW_INDIRECT through only (exps 0054, 0057). Before\n'
          '// exp 0442 "0" counted as set.\n'
          '#pragma once\n\n#include <cstring>\n\nnamespace bc5 {\n\n'
          'enum class IndirectDraws { off, draw, multi };\n\n'
          'inline IndirectDraws indirect_draws_mode(const char* e) {\n'
          '\tif (e == nullptr || e[0] == 0 || std::strcmp(e, "0") == 0) return IndirectDraws::off;\n'
          '\treturn std::strcmp(e, "multi") == 0 ? IndirectDraws::multi : IndirectDraws::draw;\n}\n\n'
          '} // namespace bc5\n')

os.makedirs(out, exist_ok=True)
for name, t in (("switch_defaults.hpp", h), ("bc5LleAgc.cpp", u), ("settingsOverlay.cpp", s), ("load_stat.hpp", ls),
                ("idraws0442.hpp", idraws)) + ((("hostMenu.cpp", hm), ("hostInput.cpp", hi)) if RT_OUT else ()):
    b = t.encode("utf-8")
    open(os.path.join(out, name), "wb").write(b)
    print(f"{name}: {hashlib.md5(b).hexdigest()[:8]}, braces {t.count('{') - t.count('}'):+d}")
print(f"moved rows {len(GENERIC) - len(KEEP)}, kept rows {len(KEEP)} {KEEP}, deleted rows {len(DELETED)}, lean gone-out {LEAN_GONE_OUT}, cost fix {COST_FIX}, rt out {RT_OUT}")
