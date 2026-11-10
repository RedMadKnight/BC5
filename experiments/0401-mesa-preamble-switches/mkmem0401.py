#!/usr/bin/env python3
"""BC5 experiment 0401, series e, switch 3 (2026-11-03, the top session's GO on the maintainer's "Buduj"): direct and
flexible memory sized from param.json, after KytyPS5 09753bf "memory: change defaults" (src/kernel/memory.cpp,
src/loader/systemContent.cpp, src/loader/systemContent.h; GPL-2.0, as KytyPlus). Switch KYTY_BC5_MEMORY_FROM_PARAM: on when
set, non-empty and not "0" (F767's reading). Off is today's code path and today's sizes; the only change then is one
journal line at memory init and three more param.json keys read and kept (never used when off).
Edits main 029e0d6b's tree (KytyPlus f266548 + patch 0001): src/kernel/memory.cpp, src/loader/systemContent.cpp and
src/loader/systemContent.h. The header only gains a struct and one declaration; its existing declarations are unchanged,
so units that include it and are not rebuilt stay valid. Each anchor must occur exactly once; a tree that has the edit
already is refused. Prints "<md5>  <relpath>" for each output.
usage: mkmem0401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARK = b"KYTY_BC5_MEMORY_FROM_PARAM"
MARK_SC = b"SystemContentGetMemoryTables"

# ---- src/loader/systemContent.h -----------------------------------------------------------------------------------
H_ANCHOR = b"uint64_t SystemContentGetFlexibleMemorySize();\n"
H_ADD = b"""// Experiment 0401 series e (KytyPS5 09753bf, GPL-2.0): the page-table sizes a game's param.json sets, in bytes; 0 where
// it sets none. Read for KYTY_BC5_MEMORY_FROM_PARAM (kernel/memory.cpp); the declarations around it are unchanged.
struct SystemContentMemoryTables {
\tuint64_t cpu_table_memory = 0; // kernel.cpuPageTableSize
\tuint64_t gpu_table_memory = 0; // kernel.gpuPageTableSize
\tuint64_t amm_table_memory = 0; // amm.pagetableMemorySizeInMib, in bytes here
};
SystemContentMemoryTables SystemContentGetMemoryTables();
"""

# ---- src/loader/systemContent.cpp ---------------------------------------------------------------------------------
SC_EDITS = (
    # Psf's method (the class is local to this unit)
    (b"\tuint64_t GetFlexibleMemorySize();\n",
     b"\tuint64_t GetFlexibleMemorySize();\n\tSystemContentMemoryTables GetMemoryTables(); // experiment 0401 series e\n"),
    # Psf's member
    (b"\tuint64_t           m_flexible_memory_size = 0;\n",
     b"\tuint64_t           m_flexible_memory_size = 0;\n\tSystemContentMemoryTables m_memory_tables; // experiment 0401 series e\n"),
    # the param.json read: the kernel object's two table sizes beside flexibleMemorySize, then the amm object's
    (b"""\t\tif (auto it = kernel->find("flexibleMemorySize"); it != kernel->end()) {
\t\t\tm_flexible_memory_size = it->get<uint64_t>();
\t\t}
\t}
""",
     b"""\t\tif (auto it = kernel->find("flexibleMemorySize"); it != kernel->end()) {
\t\t\tm_flexible_memory_size = it->get<uint64_t>();
\t\t}
\t}
\t// Experiment 0401 series e (KytyPS5 09753bf, GPL-2.0): the page-table sizes, kept for KYTY_BC5_MEMORY_FROM_PARAM. Only
\t// non-negative integers are taken; anything else leaves 0 (none set).
\tauto read_table_size = [](const nlohmann::ordered_json& object, const char* key, uint64_t* size, uint64_t unit) {
\t\tif (auto it = object.find(key); it != object.end() && it->is_number_unsigned()) {
\t\t\t*size = it->get<uint64_t>() * unit;
\t\t}
\t};
\tif (auto kernel = param_json.find("kernel"); kernel != param_json.end() && kernel->is_object()) {
\t\tread_table_size(*kernel, "cpuPageTableSize", &m_memory_tables.cpu_table_memory, 1);
\t\tread_table_size(*kernel, "gpuPageTableSize", &m_memory_tables.gpu_table_memory, 1);
\t}
\tif (auto amm = param_json.find("amm"); amm != param_json.end() && amm->is_object()) {
\t\tread_table_size(*amm, "pagetableMemorySizeInMib", &m_memory_tables.amm_table_memory, 1024ull * 1024ull);
\t}
"""),
    # Close
    (b"\tm_flexible_memory_size = 0;\n\tm_opened               = false;\n",
     b"\tm_flexible_memory_size = 0;\n\tm_memory_tables        = {}; // experiment 0401 series e\n\tm_opened               = false;\n"),
    # Psf's getter, after GetFlexibleMemorySize's
    (b"""uint64_t Psf::GetFlexibleMemorySize() {
\tCommon::LockGuard lock(m_mutex);

\treturn m_flexible_memory_size;
}
""",
     b"""uint64_t Psf::GetFlexibleMemorySize() {
\tCommon::LockGuard lock(m_mutex);

\treturn m_flexible_memory_size;
}

SystemContentMemoryTables Psf::GetMemoryTables() { // experiment 0401 series e
\tCommon::LockGuard lock(m_mutex);

\treturn m_memory_tables;
}
"""),
    # the free function, after SystemContentGetFlexibleMemorySize's
    (b"""uint64_t SystemContentGetFlexibleMemorySize() {
\tauto* sc = Common::Singleton<SystemContent>::Instance();

\treturn sc->psf.GetFlexibleMemorySize();
}
""",
     b"""uint64_t SystemContentGetFlexibleMemorySize() {
\tauto* sc = Common::Singleton<SystemContent>::Instance();

\treturn sc->psf.GetFlexibleMemorySize();
}

SystemContentMemoryTables SystemContentGetMemoryTables() { // experiment 0401 series e
\tauto* sc = Common::Singleton<SystemContent>::Instance();

\treturn sc->psf.GetMemoryTables();
}
"""),
)

# ---- src/kernel/memory.cpp ----------------------------------------------------------------------------------------
M_INCLUDE = (b'#include "libs/libs.h"\n', b'#include "libs/libs.h"\n#include "loader/systemContent.h" // experiment 0401 series e\n')
M_GLOBALS_ANCHOR = b"static Graphics::GpuResourceManager* g_gpu_resources               = nullptr;\n"
M_GLOBALS = b"""
// Experiment 0401 series e: direct and flexible memory sized from param.json, after KytyPS5 09753bf "memory: change
// defaults" (src/kernel/memory.cpp, src/loader/systemContent.cpp; GPL-2.0). With KYTY_BC5_MEMORY_FROM_PARAM set and not
// "0", a game gets 12.5 GiB (12800 MiB): a fixed 64 MiB cache and the page-table memory past the 64 MiB included for each
// of the CPU, GPU and AMM tables (param.json kernel.cpuPageTableSize, kernel.gpuPageTableSize, amm.pagetableMemorySizeInMib)
// come off the top, and flexible memory (param.json kernel.flexibleMemorySize, set by emulator.cpp as before, or the
// default) and direct memory share the rest. KYTY_GUEST_MEMORY_MB and the host-RAM cap are not used then. Unset or "0":
// today's sizes by today's code path. Left out on purpose: 0a14091's charge of loaded modules' segments to flexible memory
// (the title sets its own flexible size, and the charge changes the runtime linker too) and 09753bf's
// KernelGetPageTableStats totals; both are outside this switch.
constexpr uint64_t BC5_GUEST_MEMORY_BUDGET   = 12800ull * 1024ull * 1024ull;
constexpr uint64_t BC5_RESERVED_CACHE_SIZE   = 64ull * 1024ull * 1024ull;
constexpr uint64_t BC5_INCLUDED_TABLE_MEMORY = 64ull * 1024ull * 1024ull;
static uint64_t    g_bc5_today_total         = 0; // what today's code gives, for the journal line

static bool Bc5MemoryFromParamOn() {
\tstatic const bool on = [] {
\t\tconst char* e = std::getenv("KYTY_BC5_MEMORY_FROM_PARAM");
\t\treturn e != nullptr && e[0] != 0 && std::strcmp(e, "0") != 0;
\t}();
\treturn on;
}

static uint64_t Bc5TableOverhead(const ::Loader::SystemContentMemoryTables& t) {
\treturn std::max(t.cpu_table_memory, BC5_INCLUDED_TABLE_MEMORY) + std::max(t.gpu_table_memory, BC5_INCLUDED_TABLE_MEMORY) +
\t       std::max(t.amm_table_memory, BC5_INCLUDED_TABLE_MEMORY) - 3 * BC5_INCLUDED_TABLE_MEMORY;
}

// The total for the switch on: called from PhysicalMemory::TotalSize()'s first call, which comes after param.json is
// loaded (emulator.cpp: SetFlexibleMemorySize right after SystemContentLoadParamSfo, else the memory subsystem's init).
static uint64_t Bc5MemoryFromParamTotal() {
\tconst uint64_t overhead = Bc5TableOverhead(::Loader::SystemContentGetMemoryTables());
\tEXIT_IF(overhead >= BC5_GUEST_MEMORY_BUDGET - BC5_RESERVED_CACHE_SIZE);
\treturn (BC5_GUEST_MEMORY_BUDGET - BC5_RESERVED_CACHE_SIZE - overhead) & ~(0x4000ull - 1ull);
}
"""
M_TOTAL_OLD = b"""\t\t\ttarget = target & ~(0x4000ull - 1ull);
\t\t\tLOGF("guest memory total = %llu MiB\\n", static_cast<unsigned long long>(target / megabyte));
"""
M_TOTAL_NEW = b"""\t\t\ttarget = target & ~(0x4000ull - 1ull);
\t\t\tg_bc5_today_total = target; // experiment 0401 series e
\t\t\tif (Bc5MemoryFromParamOn()) {
\t\t\t\ttarget = Bc5MemoryFromParamTotal();
\t\t\t}
\t\t\tLOGF("guest memory total = %llu MiB\\n", static_cast<unsigned long long>(target / megabyte));
"""
M_INIT_OLD = b"""KYTY_SUBSYSTEM_INIT(Memory) {
\tg_flexible_memory_size_frozen = true;
"""
M_INIT_NEW = b"""KYTY_SUBSYSTEM_INIT(Memory) {
\tg_flexible_memory_size_frozen = true;
\t{ // experiment 0401 series e: the sizes, with the switch on or off (flexible + table overhead must fit, as in 09753bf)
\t\tconstexpr uint64_t mib    = 1024ull * 1024ull;
\t\tconst bool         on     = Bc5MemoryFromParamOn();
\t\tconst auto         tables = ::Loader::SystemContentGetMemoryTables();
\t\tconst uint64_t     total  = PhysicalMemory::TotalSize();
\t\tEXIT_IF(g_flexible_memory_size >= total);
\t\tstd::fprintf(stderr,
\t\t             "[bc5] exp 0401: memory from param.json %s: total %" PRIu64 " MiB, flexible %" PRIu64 " MiB, direct %" PRIu64
\t\t             " MiB (param.json: flexible %" PRIu64 ", cpu table %" PRIu64 ", gpu table %" PRIu64 ", amm table %" PRIu64 " MiB)",
\t\t             on ? "on" : "off", total / mib, g_flexible_memory_size / mib, (total - g_flexible_memory_size) / mib,
\t\t             ::Loader::SystemContentGetFlexibleMemorySize() / mib, tables.cpu_table_memory / mib,
\t\t             tables.gpu_table_memory / mib, tables.amm_table_memory / mib);
\t\tif (on) {
\t\t\tstd::fprintf(stderr, "; today's total would be %" PRIu64 " MiB", g_bc5_today_total / mib);
\t\t}
\t\tstd::fprintf(stderr, "\\n");
\t}
"""


def once(s, anchor, new, what):
    assert s.count(anchor) == 1, (what, anchor[:70], s.count(anchor))
    return s.replace(anchor, new)


def edit_header(s):
    assert MARK_SC not in s, "the header has the edit already"
    return once(s, H_ANCHOR, H_ANCHOR + H_ADD, "systemContent.h")


def edit_sc(s):
    assert MARK_SC not in s, "systemContent.cpp has the edit already"
    for old, new in SC_EDITS:
        s = once(s, old, new, "systemContent.cpp")
    return s


def edit_memory(s):
    assert MARK not in s and b"Bc5MemoryFromParam" not in s, "memory.cpp has the edit already"
    assert b'#include "loader/systemContent.h"' not in s, "memory.cpp includes systemContent.h already: look again"
    s = once(s, *M_INCLUDE, "memory.cpp include")
    s = once(s, M_GLOBALS_ANCHOR, M_GLOBALS_ANCHOR + M_GLOBALS, "memory.cpp globals")
    s = once(s, M_TOTAL_OLD, M_TOTAL_NEW, "memory.cpp TotalSize")
    s = once(s, M_INIT_OLD, M_INIT_NEW, "memory.cpp init")
    return s


FILES = (("src/kernel/memory.cpp", edit_memory), ("src/loader/systemContent.cpp", edit_sc), ("src/loader/systemContent.h", edit_header))


def main():
    root, out = sys.argv[1], sys.argv[2]
    for rel, fn in FILES:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        o = fn(s)
        p = os.path.join(out, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(o)
        print(f"{hashlib.md5(o).hexdigest()}  {rel}")


if __name__ == "__main__":
    main()
