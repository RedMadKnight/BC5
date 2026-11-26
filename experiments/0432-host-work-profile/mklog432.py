#!/usr/bin/env python3
"""BC5 experiment 0432, after the h430H4 GPU hang of 2026-11-18 (exp 0430's run on patch 940e8f36).
    mklog432.py <tree>/src/libs/bc5LleAgc.cpp      (the unit must be the shared f574f460)

Three changes (the top session's order and the maintainer's answers of 2026-11-18):
  1. A record of the last 4096 dropped mappings and retired BOs of the direct mapper: time, address, size, BO id, and
     whether a ring was busy at that rebuild. Kept in memory, written to the journal only by the timeout probe, so a
     hang's record can be compared with the addresses of the hung buffers. Normal build only (not in BC5_LEAN).
  2. KYTY_BC5_ANON_SYNC_KICK (exp 0415's measuring knob) is no longer read in the lean build (the lean rule).
  3. TEMPORARY: BC5_DIRECT_UNMAP_NOWAIT is read in the lean build too ("0" = the old wait), the maintainer's
     yes, and removed once it is explained. To be put back to BC5_LEAN_OR(true, ...) when the hang is cleared up.
"""
import hashlib, sys

p = sys.argv[1]
b = open(p, "rb").read()
assert hashlib.md5(b).hexdigest()[:8] == "f574f460", "the unit is not the shared f574f460"
s = b.decode("utf-8")


def sub(old, new, n=1):
    global s
    got = s.count(old)
    assert got == n, "%d matches, wanted %d: %r" % (got, n, old[:80])
    s = s.replace(old, new)


# 3. the switch, readable in lean for now
sub("\tstatic const bool v = BC5_LEAN_OR(true, word_on(\"BC5_DIRECT_UNMAP_NOWAIT\"));\n",
    "\t// TEMPORARY (2026-11-18, the maintainer): read in the lean build too until the h430H4 hang is cleared up; then\n"
    "\t// back to BC5_LEAN_OR(true, word_on(...)).\n"
    "\tstatic const bool v = word_on(\"BC5_DIRECT_UNMAP_NOWAIT\");\n")

# 2. the measuring knob out of lean
sub("\t\tstatic const bool kick = bc5::load_stat::env_num(\"KYTY_BC5_ANON_SYNC_KICK\", 1, 1) != 0;\n",
    "\t\tstatic const bool kick = BC5_LEAN_OR(true, bc5::load_stat::env_num(\"KYTY_BC5_ANON_SYNC_KICK\", 1, 1) != 0);\n")

# 1. the record
sub("} // namespace d432\n",
    "// The last dropped mappings and retired BOs (after the h430H4 hang): written by the timeout probe only.\n"
    "#ifdef BC5_LEAN\n"
    "inline void drop_note(char, uint64_t, uint64_t, uint32_t, bool) {}\n"
    "inline void drops_dump() {}\n"
    "#else\n"
    "struct Drop {\n"
    "\tdouble   t;\n"
    "\tuint64_t va, size;\n"
    "\tuint32_t id;\n"
    "\tchar     what; // 'u': a mapping unmapped; 'f': a BO freed (va and size 0)\n"
    "\tbool     busy; // a ring had work in flight at this rebuild\n"
    "};\n"
    "inline constexpr size_t kDrops = 4096;\n"
    "inline std::mutex       g_drop_mu;\n"
    "inline Drop             g_drop[kDrops];\n"
    "inline uint64_t         g_drop_n = 0, g_drop_dumped = 0;\n"
    "inline void drop_note(char what, uint64_t va, uint64_t size, uint32_t id, bool busy) {\n"
    "\tconst double    t = timing_now();\n"
    "\tstd::lock_guard lk(g_drop_mu);\n"
    "\tg_drop[g_drop_n++ % kDrops] = Drop {t, va, size, id, what, busy};\n"
    "}\n"
    "inline void drops_dump() {\n"
    "\tstd::lock_guard lk(g_drop_mu);\n"
    "\tconst uint64_t  from = std::max(g_drop_dumped, g_drop_n > kDrops ? g_drop_n - kDrops : 0);\n"
    "\tjournal(\"timeout probe: exp 0432 drops: %\" PRIu64 \" in all, %\" PRIu64 \" below (t, u = mapping unmapped / f = BO freed, address+size, BO id, ring busy at that rebuild)\\n\",\n"
    "\t        g_drop_n, g_drop_n - from);\n"
    "\tfor (uint64_t i = from; i < g_drop_n; i++) {\n"
    "\t\tconst Drop& d = g_drop[i % kDrops];\n"
    "\t\tjournal(\"timeout probe: drop t %.3f s %c 0x%\" PRIx64 \"+0x%\" PRIx64 \" bo %u %s\\n\", d.t, d.what, d.va, d.size, d.id, d.busy ? \"BUSY\" : \"idle\");\n"
    "\t}\n"
    "\tg_drop_dumped = g_drop_n;\n"
    "}\n"
    "#endif\n"
    "} // namespace d432\n")
sub("\t\t\t\t} else {\n"
    "\t\t\t\t\tg_dev->unmap_shared(m.va);\n"
    "\t\t\t\t\tunmapped++;\n",
    "\t\t\t\t} else {\n"
    "\t\t\t\t\td432::drop_note('u', m.va, m.size, m.id, d432_busy);\n"
    "\t\t\t\t\tg_dev->unmap_shared(m.va);\n"
    "\t\t\t\t\tunmapped++;\n")
sub("\t\t\t\tkc412_dropped(m, want); // exp 0412 (tag kc412)\n"
    "\t\t\t\tg_dev->unmap_shared(m.va);\n",
    "\t\t\t\tkc412_dropped(m, want); // exp 0412 (tag kc412)\n"
    "\t\t\t\td432::drop_note('u', m.va, m.size, m.id, d432_busy);\n"
    "\t\t\t\tg_dev->unmap_shared(m.va);\n")
sub("\tfor (const uint32_t id: retired) g_dev->free_shared(id);\n"
    "\tguard0412_after_cuts(lzr.done.size());",
    "\tfor (const uint32_t id: retired) {\n"
    "\t\td432::drop_note('f', 0, 0, id, d432_busy);\n"
    "\t\tg_dev->free_shared(id);\n"
    "\t}\n"
    "\tguard0412_after_cuts(lzr.done.size());")
sub("\t\tjournal(\"timeout probe: %s %u dwords dumped to %s\\n\", kind, sub_n, name);\n",
    "\t\tjournal(\"timeout probe: %s %u dwords dumped to %s\\n\", kind, sub_n, name);\n"
    "\t\td432::drops_dump(); // exp 0432: what the mapper dropped before this timeout\n")

open(p, "w", encoding="utf-8", newline="\n").write(s)
print("edited", p, "(drop record, KICK out of lean, NOWAIT readable in lean)")
