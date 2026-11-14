#!/usr/bin/env python3
"""BC5 experiment 0419, the test build T: a diagnostic way to run WITHOUT one forced default.
Since candidate E the rows of kFixes and kDefaults are forced at process start (setenv with overwrite), so an arm
"T without KYTY_BC5_APR_POSIX=direct" cannot be run: the word in the environment is overwritten. This adds
  KYTY_BC5_DIAG_UNFORCE=<NAME>[,<NAME>...]
For each listed name that is a row of kFixes or kDefaults the row is NOT applied: the environment's own value stands
(unset stays unset), and one line on stderr says so. Unset or empty: every row is forced, as before. It is a test
build's diagnostic, not a setting: no launcher or shortcut may carry it.
  the arm: KYTY_BC5_DIAG_UNFORCE=KYTY_BC5_APR_POSIX KYTY_BC5_APR_POSIX=0   (the old fread path of APR reads)
usage: mkdiag0419.py <src/bc5/switch_defaults.hpp>"""
import sys
from ed0419g import File

f = File(sys.argv[1])
f.gone("KYTY_BC5_DIAG_UNFORCE")
f.sub("inline void Apply() {\n",
      r'''// exp 0419 (test build T): KYTY_BC5_DIAG_UNFORCE=<NAME>[,<NAME>...]: a diagnostic. A listed row of kFixes or kDefaults is
// not applied, so the environment's own value of that word stands. Whole names between commas; unset or empty: none.
inline bool Unforced(const char* name) {
	const char* e = std::getenv("KYTY_BC5_DIAG_UNFORCE");
	if (e == nullptr || e[0] == 0) return false;
	const size_t n = std::strlen(name);
	for (const char* p = e; *p != 0;) {
		const char*  c   = std::strchr(p, ',');
		const size_t len = c != nullptr ? static_cast<size_t>(c - p) : std::strlen(p);
		if (len == n && std::strncmp(p, name, n) == 0) {
			const char* v = std::getenv(name);
			std::fprintf(stderr, "[bc5] exp 0419: DIAGNOSTIC: the forced default %s is NOT applied (KYTY_BC5_DIAG_UNFORCE); its value is %s\n", name,
			             v != nullptr ? v : "unset");
			return true;
		}
		if (c == nullptr) break;
		p = c + 1;
	}
	return false;
}

inline void Apply() {
''')
f.sub("\tfor (const Default* d = kFixes; d->name != nullptr; d++) {\n\t\tsetenv(d->name, d->value, 1);\n",
      "\tfor (const Default* d = kFixes; d->name != nullptr; d++) {\n\t\tif (Unforced(d->name)) continue;\n\t\tsetenv(d->name, d->value, 1);\n")
f.sub("\tfor (const Default* d = kDefaults; d->name != nullptr; d++) {\n\t\tsetenv(d->name, d->value, 1);\n",
      "\tfor (const Default* d = kDefaults; d->name != nullptr; d++) {\n\t\tif (Unforced(d->name)) continue;\n\t\tsetenv(d->name, d->value, 1);\n")
f.save()
