#!/usr/bin/env python3
r"""BC5 experiment 0419, build W = V + the lean build without its diagnostic switches (the maintainer, 2026-11-15:
"wersja lean ma mieć wywalone z kodu wszystkie przełączniki diagnostyczne"). The NORMAL build is not changed: every
macro below expands to the call that stood there.

In the lean build (BC5_LEAN):
  class D (diagnostics, catchers, test hooks; lean-classes.tsv) and class U (kIgnored: unset at process start)
      std::getenv("W")            ->  BC5_DIAG_ENV("W")            a null pointer
      helper("W"...)              ->  BC5_LEAN_OR(off, helper(...)) the helper's "off" value (the forms in HELPERS)
  class F (kFixes and kDefaults: forced at process start, no option)
      std::getenv("W")            ->  BC5_FIXED_ENV("W", "<v>")    the row's value as a literal
      take("W"), Bc5Exp0401Switch("W")  ->  BC5_LEAN_OR(true, ...)
  class K (configuration, one title's rows, the three defaults with an option, opt-in behaviour): untouched
In each case the word is no longer in the lean binary, and code behind a constant "off" is dropped by the compiler.
Also: a row of kFixes, kDefaults or kIgnored whose word is no longer read by name in lean is left out of the lean
build's table (so its name is not in the binary); the lean build's old unset list in main.cpp goes.
A word that is still named in another form (a table of names, a helper not in HELPERS) is NOT changed and is printed
as LEFT: it stays in the lean binary, and a forced one keeps its row, so its fix stays on.
The backend archive is one for both builds, so a word the BACKEND reads cannot be compiled out of lean here: a D word
of the backend is unset at the lean build's start (a lean-only list in switch_defaults.hpp), a U word keeps its row.
usage: mklean0419.py <tree root> <lean-classes.tsv> <the backend's direct.cpp>"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ed0419g import File

root, classes, backend_cpp = sys.argv[1:4]
SRC = os.path.join(root, "src")
cls = {}
for line in open(classes, encoding="utf-8"):
    if line.strip() and not line.startswith("#"):
        w, c = line.split()[:2]
        cls[w] = c

SD = os.path.join(SRC, "bc5", "switch_defaults.hpp")
sd = open(SD, encoding="utf-8").read()
NAME = r'((?:KYTY_)?BC5_[A-Z0-9_]+)'


def table(name):
    a = sd.index(name + "[] = {")
    return sd[a:sd.index("};", a)]


forced = dict(re.findall(r'\{"%s", "([^"]*)"\}' % NAME, table("kFixes") + table("kDefaults")))
unset = set(re.findall('"%s"' % NAME, table("kIgnored")))
keep = set(re.findall('"%s"' % NAME, table("kTitleDefaults") + table("kSoft") + table("kTitleForced")))
for w in forced:
    cls[w] = "F"
for w in unset:
    cls[w] = "U"
for w in keep:  # a title's row or a default with an option is read in lean, whatever the inventory called it
    if cls.get(w) != "F":
        cls[w] = "K"

# first: the lean build's old unset list goes, so that its names do not count as left
f = File(os.path.join(SRC, "main.cpp"))
f.cut("#ifdef BC5_LEAN\n#include <cstdlib>\n// BC5 (KYTY_BC5_LEAN, experiment 0177): the diagnostic switches of the host and the direct path,\n",
      '\tsetenv("BC5_LOGGING", "0", 1);\n}\n#endif\n',
      "// exp 0419 (build W): the lean build's unset list (exp 0177) is gone: its words are not read in the lean build at all.\n")
f.save()

GETENV = re.compile(rb'std::getenv\("' + NAME.encode() + rb'"\)')
# helper forms: (pattern with the name as group 1, the lean value for a D word, the lean value for an F word or None)
HELPERS = [
    (re.compile(rb'\benv_on\("' + NAME.encode() + rb'"\)'), b"false", None),
    (re.compile(rb'\btake\("' + NAME.encode() + rb'"\)'), b"false", b"true"),
    (re.compile(rb'\bBc5Exp0401Switch\("' + NAME.encode() + rb'"\)'), b"false", b"true"),
    (re.compile(rb'\bbc5_sdm_switch\("' + NAME.encode() + rb'", "[^"]*"\)'), b"false", None),
    (re.compile(rb'\bBc5AjmSwitch\("' + NAME.encode() + rb'", "[^"]*"\)'), b"false", None),
    (re.compile(rb'\bget\("' + NAME.encode() + rb'"\)'), b"nullptr", None),
]
ANY = re.compile(b'"' + NAME.encode() + b'"')
done, left, files = {}, {}, 0
backend_words = set(m.group(1).decode() for m in re.finditer(rb'getenv\("' + NAME.encode() + rb'"\)', open(backend_cpp, 'rb').read()))
for w in backend_words:
    if cls.get(w) in ('D', 'U', 'F'):
        left.setdefault(w, set()).add('(backend) direct.cpp')
for d, _, fs in os.walk(SRC):
    for fn in sorted(fs):
        if not fn.endswith((".cpp", ".hpp", ".h", ".inc")) or fn in ("env_rule.hpp", "switch_defaults.hpp"):
            continue
        p = os.path.join(d, fn)
        b = open(p, "rb").read()
        nl = b"\r\n" if b"\r\n" in b else b"\n"

        def rep(m):
            w = m.group(1).decode()
            c = cls.get(w)
            if c in ("D", "U"):
                done[w] = done.get(w, 0) + 1
                return b'BC5_DIAG_ENV("' + m.group(1) + b'")'
            if c == "F":
                done[w] = done.get(w, 0) + 1
                return b'BC5_FIXED_ENV("' + m.group(1) + b'", "' + forced[w].encode() + b'")'
            return m.group(0)

        t = GETENV.sub(rep, b)
        for pat, off, on in HELPERS:
            def hrep(m, off=off, on=on):
                w = m.group(1).decode()
                c = cls.get(w)
                v = off if c in ("D", "U") else (on if c == "F" else None)
                if v is None:
                    return m.group(0)
                done[w] = done.get(w, 0) + 1
                return b"BC5_LEAN_OR(" + v + b", " + m.group(0) + b")"
            t = pat.sub(hrep, t)
        for line in t.split(b"\n"):
            if line.lstrip().startswith(b"//"):
                continue
            for m in ANY.finditer(line):
                w = m.group(1).decode()
                if cls.get(w) in ("D", "U", "F") and b'ENV("' + m.group(1) + b'"' not in line and b"BC5_LEAN_OR(" not in line:
                    left.setdefault(w, set()).add(fn)
        if t != b:
            if b'#include "bc5/env_rule.hpp"' not in t:
                t = b'#include "bc5/env_rule.hpp" // exp 0419 (build W): BC5_DIAG_ENV, BC5_FIXED_ENV, BC5_LEAN_OR' + nl + t
            open(p, "wb").write(t)
            files += 1

# two more, by hand (the top session, 2026-11-15: "wytnij przy okazji, jeśli to jeden krok bez ryzyka"):
# the four reset switches' names (a table for one journal line; the switches are constant off since E) and the period
# of the ANON_SYNC thread (its default 1000 ms is env_num's own "unset" answer).
f = File(os.path.join(SRC, "libs", "bc5LleAgc.cpp"))
f.sub('static const char* const kM11Names[4] = {"BC5_DIRECT_RESET_REPLAY_ACB", "BC5_DIRECT_RESET_LABELS", "BC5_DIRECT_LEARN_GUEST_ONLY", "BC5_DIRECT_RESET_LABEL_JOURNAL"};\n',
      '#ifdef BC5_LEAN\nstatic const char* const kM11Names[4] = {"", "", "", ""}; // exp 0419 (build W): the names are not in the lean binary\n#else\n'
      'static const char* const kM11Names[4] = {"BC5_DIRECT_RESET_REPLAY_ACB", "BC5_DIRECT_RESET_LABELS", "BC5_DIRECT_LEARN_GUEST_ONLY", "BC5_DIRECT_RESET_LABEL_JOURNAL"};\n#endif\n')
f.sub('bc5::load_stat::env_num("KYTY_BC5_ANON_SYNC_MS", 1000, 60\'000)', 'BC5_LEAN_OR(1000, bc5::load_stat::env_num("KYTY_BC5_ANON_SYNC_MS", 1000, 60\'000))')
f.save()
for w in ("BC5_DIRECT_RESET_REPLAY_ACB", "BC5_DIRECT_RESET_LABELS", "BC5_DIRECT_LEARN_GUEST_ONLY", "BC5_DIRECT_RESET_LABEL_JOURNAL", "KYTY_BC5_ANON_SYNC_MS"):
    if left.get(w) == {"bc5LleAgc.cpp"}:
        del left[w]
        done[w] = done.get(w, 0) + 1

f = File(os.path.join(SRC, "bc5", "env_rule.hpp"))
f.sub("#pragma once\n",
      "#pragma once\n\n#include <cstdlib>\n\n"
      "// exp 0419 (build W): how a switch is read. In the lean build a diagnostic word is a null pointer and a forced word\n"
      "// is its value, so neither name is in the binary; in the normal build each macro is the call it replaces.\n"
      "// BC5_DIAG_ENV is defined exactly as in common/logging/log.h (exp 0177), so the two definitions may meet.\n"
      "#ifdef BC5_LEAN\n"
      "#define BC5_DIAG_ENV(name) static_cast<const char*>(nullptr)\n"
      "#else\n"
      "#define BC5_DIAG_ENV(name) std::getenv(name)\n"
      "#endif\n"
      "#ifdef BC5_LEAN\n"
      "#define BC5_FIXED_ENV(name, value) static_cast<const char*>(value)\n"
      "#define BC5_LEAN_OR(lean_value, expr) (lean_value)\n"
      "#else\n"
      "#define BC5_FIXED_ENV(name, value) std::getenv(name)\n"
      "#define BC5_LEAN_OR(lean_value, expr) (expr)\n"
      "#endif\n")
f.save()

# switch_defaults.hpp: the rows whose word lean no longer reads by name are not in the lean build's tables
gone_rows = sorted(w for w in list(forced) + sorted(unset) if w not in left)
s = sd
n_rows = 0
for w in gone_rows:
    pat = re.compile(r'^(    (?:\{"%s", "[^"]*"\}|"%s"),[^\n]*)\n' % (re.escape(w), re.escape(w)), re.M)
    m = pat.search(s)
    assert m is not None and len(pat.findall(s)) == 1, w
    s = s[:m.start()] + "#ifndef BC5_LEAN\n" + m.group(1) + "\n#endif\n" + s[m.end():]
    n_rows += 1
s = s.replace("#endif\n#ifndef BC5_LEAN\n", "")  # neighbouring rows share one guard
assert s.count('\tconst char* e = std::getenv("KYTY_BC5_DIAG_UNFORCE");\n') == 1
s = s.replace('\tconst char* e = std::getenv("KYTY_BC5_DIAG_UNFORCE");\n', '\tconst char* e = BC5_DIAG_ENV("KYTY_BC5_DIAG_UNFORCE");\n')
if '#include "bc5/env_rule.hpp"' not in s:
    assert s.count("#include <cstdio>\n") == 1
    s = s.replace("#include <cstdio>\n", '#include "bc5/env_rule.hpp" // exp 0419 (build W)\n#include <cstdio>\n')
assert s.count("#ifndef BC5_LEAN") == s.count("#endif") - sd.count("#endif")
lean_unset = sorted(w for w in backend_words if cls.get(w) == 'D')
k = "\tfor (const Default* d = kSoft; d->name != nullptr; d++) {\n"
assert s.count(k) == 1
s = s.replace(k, "#ifdef BC5_LEAN\n\t// build W: diagnostic words the BACKEND reads (one archive for both builds) are taken out of the environment\n"
              + "".join('\tunsetenv("%s");\n' % w for w in lean_unset) + "#endif\n" + k)
open(SD, "w", encoding="utf-8", newline="").write(s)


print("files changed: %d; words rewritten: %d (sites %d); rows out of the lean tables: %d of %d" % (
    files, len(done), sum(done.values()), n_rows, len(forced) + len(unset)))
print("LEFT (still named in the lean binary): %d" % len(left))
for w in sorted(left):
    print("  %s %s: %s" % (cls[w], w, " ".join(sorted(left[w]))))
