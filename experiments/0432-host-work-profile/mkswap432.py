#!/usr/bin/env python3
"""BC5 experiment 0432: the swap form of the test build's host unit.
    mkswap432.py <tree>/src/libs/bc5LleAgc.cpp      (after mkt432.py and mkx432.py; the unit must be 019d826f)

The code that ran in the test build stays as it is. What changes is how the lean build (BC5_LEAN, exp 0419's rule: every
diagnostic switch and counter is compiled out with its code) sees it:
  - items D, W, R, M: on, no word read (BC5_LEAN_OR(true, ...)); the normal build reads the word as before ("0" = off)
  - items A, V, X: off, no word read (BC5_LEAN_OR(false / 0, ...)), so their branches are dead code in the lean build
  - the counters are a type without storage in the lean build, and the 10-second line is not compiled
The normal build's behaviour is unchanged: the same defaults (D, W, R, M on; A, V, X off), the same words, the same line.
"""
import hashlib, sys

p = sys.argv[1]
b = open(p, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "019d826f", "the unit is not mkx432.py's 019d826f"
s = b.decode("utf-8")


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


for word in ("BC5_DIRECT_UNMAP_NOWAIT", "BC5_DIRECT_ANON_THREAD", "BC5_DIRECT_REFUSED_ENDS", "BC5_DIRECT_MAPS_FAST"):
    sub("\tstatic const bool v = word_on(\"%s\");\n" % word, "\tstatic const bool v = BC5_LEAN_OR(true, word_on(\"%s\"));\n" % word)
for word in ("BC5_DIRECT_ANON_EVENTS", "BC5_DIRECT_VIEWS_KEPT"):
    sub("\tstatic const bool v = [] {\n"
        "\t\tconst char* e = std::getenv(\"%s\");\n"
        "\t\treturn e != nullptr && e[0] == '1' && e[1] == 0;\n"
        "\t}();\n" % word,
        "\tstatic const bool v = BC5_LEAN_OR(false, ([] {\n"
        "\t\tconst char* e = std::getenv(\"%s\");\n"
        "\t\treturn e != nullptr && e[0] == '1' && e[1] == 0;\n"
        "\t}()));\n" % word)
sub("\tstatic const int v = [] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_DIRECT_MAPS_DIFF\");\n"
    "\t\tif (e == nullptr) return 0;\n"
    "\t\tif (std::strcmp(e, \"verify\") == 0) return 2;\n"
    "\t\treturn e[0] == '1' && e[1] == 0 ? 1 : 0;\n"
    "\t}();\n",
    "\tstatic const int v = BC5_LEAN_OR(0, ([] {\n"
    "\t\tconst char* e = std::getenv(\"BC5_DIRECT_MAPS_DIFF\");\n"
    "\t\tif (e == nullptr) return 0;\n"
    "\t\tif (std::strcmp(e, \"verify\") == 0) return 2;\n"
    "\t\treturn e[0] == '1' && e[1] == 0 ? 1 : 0;\n"
    "\t}()));\n")

# the counters: no storage and no code in the lean build
sub("inline bool word_on(const char* name) {\n",
    "#ifdef BC5_LEAN\n"
    "struct Cnt { // the lean build: a counter that is nothing\n"
    "\tconstexpr Cnt() = default;\n"
    "\texplicit constexpr Cnt(int) {}\n"
    "\tvoid     operator++(int) const {}\n"
    "\tvoid     operator+=(uint64_t) const {}\n"
    "\tvoid     operator=(uint64_t) const {}\n"
    "\tuint64_t load() const { return 0; }\n"
    "};\n"
    "#else\n"
    "using Cnt = std::atomic<uint64_t>;\n"
    "#endif\n"
    "inline bool word_on(const char* name) {\n")
sub("inline std::atomic<uint64_t> g_maps_fast {0}, g_maps_sorted {0};\n", "inline Cnt g_maps_fast {0}, g_maps_sorted {0};\n")
sub("inline std::atomic<uint64_t> g_x_diff {0}, g_x_full {0}, g_x_views {0}, g_x_mismatch {0};\n", "inline Cnt g_x_diff {0}, g_x_full {0}, g_x_views {0}, g_x_mismatch {0};\n")
sub("inline std::atomic<uint64_t> g_x_why[11]; //", "inline Cnt g_x_why[11]; //")
sub("inline std::atomic<uint64_t> g_rebuilds {0}, g_busy {0},", "inline Cnt g_rebuilds {0}, g_busy {0},")
sub("inline void maxed(std::atomic<uint64_t>& m, uint64_t v) {\n"
    "\tuint64_t was = m.load(std::memory_order_relaxed);\n"
    "\twhile (v > was && !m.compare_exchange_weak(was, v, std::memory_order_relaxed)) {\n"
    "\t}\n"
    "}\n",
    "#ifdef BC5_LEAN\n"
    "inline void maxed(const Cnt&, uint64_t) {}\n"
    "#else\n"
    "inline void maxed(std::atomic<uint64_t>& m, uint64_t v) {\n"
    "\tuint64_t was = m.load(std::memory_order_relaxed);\n"
    "\twhile (v > was && !m.compare_exchange_weak(was, v, std::memory_order_relaxed)) {\n"
    "\t}\n"
    "}\n"
    "#endif\n")

# the 10-second line: not in the lean build
a = s.index("\t{ // exp 0432: the sync + hints part of every submission (\"prepare\" here), and the counters at most every 10 s\n")
e = s.index("\t\t\tjournal(\"%s\\n\", line);\n\t\t}\n\t}\n", a) + len("\t\t\tjournal(\"%s\\n\", line);\n\t\t}\n\t}\n")
assert e - a < 6000
s = s[:a] + "#ifndef BC5_LEAN\n" + s[a:e] + "#endif\n" + s[e:]

open(p, "w", encoding="utf-8", newline="\n").write(s)
print("edited", p, "(the swap form)")
