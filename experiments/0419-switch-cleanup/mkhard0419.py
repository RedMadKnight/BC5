#!/usr/bin/env python3
"""BC5 experiment 0419, step 4 (the maintainer, 2026-11-13: "Pozbądź się zbędnych przełączników"; bisect through git,
not through words): the options of the long-standing defaults are removed, in one place.
Runs after mkdefs0419.py on src/bc5/switch_defaults.hpp:
  - kFixes and kDefaults are FORCED at process start (setenv with overwrite): the environment can no longer change
    them, whatever a launcher, a shortcut or a shell exports;
  - kIgnored: words whose code default (the value when unset) is the tested behaviour; they are removed from the
    environment at process start, so the read site always sees "unset";
  - KYTY_BC5_SWITCH_DEFAULTS is gone (a control is now a build of the older patch, not a word);
  - kSoft: the defaults that keep their option: the quiet journal (a diagnostic choice) and the words that became
    defaults in this experiment (BC5_DIRECT_CHAIN, BC5_GC_MODE, and exp 0412's K1r set).
Phase 1 as for the deletes: the read sites and their old-path code are still in the source; nothing can reach them.
usage: mkhard0419.py <tree root> [NAME=VALUE ...]     the extra words are appended to kSoft (exp 0412's K1r defaults)"""
import hashlib
import sys

root, extra = sys.argv[1], sys.argv[2:]
p = root + "/src/bc5/switch_defaults.hpp"
s = open(p, encoding="utf-8", newline="").read()
assert "\r" not in s and "exp 0419" in s and "kIgnored" not in s


def once(old, new):
    global s
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)


soft = "".join('    {"%s", "%s"},\n' % tuple(w.split("=", 1)) for w in extra)
once('    // B16: quiet journal and inherit-map caps\n    {"BC5_DIRECT_JOURNAL_QUIET", "1"},\n'
     '    // exp 0419: the two words both titles run with every day, until now only through a launcher or bc5-run.env\n'
     '    {"BC5_DIRECT_CHAIN", "2"}, // F224\n'
     '    {"BC5_GC_MODE", "direct"},\n'
     '    {nullptr, nullptr}};\n',
     '    {nullptr, nullptr}};\n\n'
     '// exp 0419: defaults that KEEP their option (setenv without overwrite: a value in the environment wins, NAME=0 is off).\n'
     'inline constexpr Default kSoft[] = {\n'
     '    // B16: quiet journal and inherit-map caps (a diagnostic choice: a launcher may ask for the full journal)\n'
     '    {"BC5_DIRECT_JOURNAL_QUIET", "1"},\n'
     '    // the two words both titles run with every day, until now only through a launcher or bc5-run.env\n'
     '    {"BC5_DIRECT_CHAIN", "2"}, // F224\n'
     '    {"BC5_GC_MODE", "direct"},\n'
     + ('    // exp 0412: K1r and its rules, default on since the maintainer\'s play of 2026-11-13\n' + soft if soft else '')
     + '    {nullptr, nullptr}};\n\n'
     '// exp 0419: words whose option is removed and whose code default (the value when unset) is the tested behaviour.\n'
     '// They are taken out of the environment at process start, before any static initializer reads one.\n'
     'inline constexpr const char* kIgnored[] = {\n'
     '    "BC5_FAULT_RECORD",             // a GPU fault always ends the game with a record (the maintainer\'s rule, exp 0412)\n'
     '    "BC5_DIRECT_COMPUTE_RING",      // one ring (F412, F415)\n'
     '    "BC5_DIRECT_IB_MAX_DW",         // the built-in cut size\n'
     '    "BC5_DIRECT_PREFIX_ALL",        // the prefix on draws\n'
     '    "BC5_DIRECT_SOFT_WAIT_MS",      // 8 ms (F432)\n'
     '    "KYTY_BC5_AMM_SETBUFFER_GUARD", // exp 0416\n'
     '    "KYTY_BC5_APR_READAHEAD",       // 4\n'
     '    "KYTY_BC5_APR_SYNC",            // the old synchronous path\n'
     '    "KYTY_BC5_AT9_VIBRATION",\n'
     '    "KYTY_BC5_NP_SESSION_V2",       // exp 0413\n'
     '    "KYTY_BC5_PAD_PW_PROPS",\n'
     '    "KYTY_BC5_PAD_RUMBLE_FALLBACK",\n'
     '    "KYTY_BC5_SWITCH_DEFAULTS",     // removed with this change: a control is a build of the older patch\n'
     '    nullptr};\n')
a = s.index("inline void Apply() {\n")
b = s.index("\n} // namespace bc5::switch_defaults")
s = s[:a] + '''inline void Apply() {
	// exp 0419: the fixes and the long-standing defaults are forced (no option any more); see kIgnored and kSoft above.
	for (const Default* d = kFixes; d->name != nullptr; d++) {
		setenv(d->name, d->value, 1);
	}
	for (const Default* d = kDefaults; d->name != nullptr; d++) {
		setenv(d->name, d->value, 1);
	}
	for (const char* const* n = kIgnored; *n != nullptr; n++) {
		unsetenv(*n);
	}
	for (const Default* d = kSoft; d->name != nullptr; d++) {
		setenv(d->name, d->value, 0);
	}
	// the title's own rows
	const char* per = std::getenv("KYTY_BC5_TITLE_DEFAULTS");
	if (per != nullptr && std::strcmp(per, "0") == 0) return;
	const std::string title = DetectTitle();
	int               took  = 0;
	const int         rows  = title.empty() ? 0 : ApplyTitle(title, &took);
	if (rows != 0) {
		std::fprintf(stderr, "[bc5] exp 0419: title %s: %d title defaults, %d taken, %d already set in the environment\\n", title.c_str(), rows, took,
		             rows - took);
	}
}
''' + s[b:]
once("// KYTY_BC5_SWITCH_DEFAULTS=0 skips the whole table (the code then behaves as in the private builds with nothing set).\n",
     "// Since experiment 0419 the two tables below are FORCED (no option, no KYTY_BC5_SWITCH_DEFAULTS); kSoft keeps options.\n")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("switch_defaults.hpp -> %s (kSoft extra: %s)" % (hashlib.md5(s.encode()).hexdigest()[:8], " ".join(extra) or "none"))
