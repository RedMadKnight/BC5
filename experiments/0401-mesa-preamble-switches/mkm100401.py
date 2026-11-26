#!/usr/bin/env python3
"""BC5 experiment 0401 series e10, tag m10: six switches from exp 0408's final change list (bc5-0408
experiments/0408-memory-review/README.md section G6 at 509083aa, rows 2, 4, 5 and 6; the cross-unit contract is
scratchpad e10/CONTRACT.md), as one edit of src/libs/bc5LleAgc.cpp (pinned input: MAIN_MD5, e9's final main unit).
m100401-notes.md has the design, the costs, the risks and the sources.
  BC5_DIRECT_PROT_CENSUS       log only. extern "C" Bc5ProtCensus(call, va, size, phys, prot, type, name), defined here and
                               called by memory.cpp (tag k10) and libAmpr.cpp (tag p10) at each map, mprotect, mtypeprotect,
                               AMM map, AMM remap and unmap: off, it returns at once; on, it copies the call into a list of
                               at most 65,536 (one short lock of its own, nothing else: no journal, no memory.cpp or mapper
                               lock). A thread of its own (started at the first submission) writes them each second: one
                               line per map, mprotect and mtypeprotect call (va, size, phys, prot and its CPU/GPU decode,
                               type, name, the mapper's class by the name lists), at most 1,000 in 10 s; the AMM calls,
                               the unmaps and the calls past that are counted per (call, type, protection, name) and written
                               every 10 s (at most 200 groups and one line for the rest), with the calls lost to a full
                               list. On the memory line's thread (mem_line_loop, BC5_DIRECT_MEM_LINE on), at journal time
                               120, 300, 600 s and then every 600 s: the bytes imported per GPU class (no GPU bit, GPU_READ
                               only, GPU_WRITE only, both; type 0 by its file offset against g_d[0]'s BOs, types 3-5 by
                               address against g_d[1]'s) and per state the forced chunks: under an eager view, holding data
                               (one SEEK_DATA each), neither (the pin the hints and learned windows alone cause) and of
                               those imported. The mapper's BOs and forced chunks are copied under g_dev_mutex taken with
                               try_lock (a busy lock puts the census off to the next tick); the SEEK_DATA calls come after.
  BC5_DIRECT_JOURNAL_DONTNEED  exp 0330's switch: after each flush of the journal file (journal_min_file's flush,
                               journal()'s and journal_quiet_put's per-line files, the two per-submission lines), once the
                               file has grown 8 MiB past the last start, the writeback of the new part is started
                               (sync_file_range WRITE) and the part started the time before leaves the page cache
                               (posix_fadvise DONTNEED). Nothing is written into the journal from there; a count line every
                               64 writebacks and at a new failure comes from the 10-s tick.
  BC5_DIRECT_GPU_RIGHTS        DView keeps the title's protection of a direct view (the 5th int of direct_views_build's
                               callback; -1 for the private regions, whose callback has none); a view with GPU_READ (0x10)
                               and not GPU_WRITE (0x20) is mapped R|X through Device::map_shared_rights(.., 1|4), every other
                               one R|W|X through map_shared as e9. The rights enter DMap's equality and the views' signature,
                               so a protection change remaps. A backend without map_shared_rights: map_shared, journaled.
  BC5_DIRECT_AMM_WINDOW_FIX    with BC5_DIRECT_AMM_PRT set, the PRT window goes where libAmpr's Bc5AmmWindow says the AMM
                               window is (64 KiB aligned inward), at the device's open and reopen, not at 0x8000000000. When
                               it is not reserved yet, the window waits, retried at most once a second at a submission and
                               at each Bc5AmmReserved event.
  BC5_DIRECT_AMM_NULL_BO       "rw": writable, any other on value: read-only. With BC5_DIRECT_AMM_PRT set: the PRT window as
                               above, then Device::map_null_window over each of the title's reservations inside the window
                               (libAmpr's Bc5AmmForEachReserved at the open and reopen; then extern "C" Bc5AmmReserved(va,
                               size, on), defined here, queued and applied under g_dev_mutex at the next submission's
                               direct_sync). The null pages REPLACE the PRT pages there; never the whole window. A
                               reservation given back (on=0) keeps its null pages: the backend has no call to give them
                               back. With no reservation yet, the window waits for the first one.
  BC5_DIRECT_HOLES_NULL_BO     "rw": writable, any other on value: read-only. The learned windows' holes get
                               Device::map_null_range pieces instead of the writable 2 MiB scratch BO; scratch_release gives
                               them back with unmap_null_range. A piece map_null_range refuses takes the scratch BO, as e9.
                               Null ranges have no exp 0056 aliases (map_alias covers userptr and shared mappings only): with
                               BC5_DIRECT_ALIASES each null piece also gets null ranges at its alias addresses ((byte << 40) +
                               address, sign-extended from 2^47 as map_alias does), at the fill and from aliases_apply for an
                               alias window learned later, and gives them back with the piece.
The AMM lines carry, with NULL_BO or PROT_CENSUS on, the GPU's VRAM and GTT use before and after (sysfs mem_info_vram_used,
mem_info_gtt_used of kRenderNode's device; -1 when not read). libAmpr's two functions are weak here: without them the unit
links and says so; the three new backend methods are found at compile time (a requires-expression): without them the old
call is made and journaled.
Each switch: unset, empty and "0" are off, any other value is on (bc5::env_on's reading, F767); read once; one journal line
that names its mode (PROT_CENSUS, JOURNAL_DONTNEED, GPU_RIGHTS and HOLES_NULL_BO at the first submission, from
mem_line_start; the two AMM switches at the device's open, held until the journal has its directory). With all six off the
binary does what e9's does, plus those switch lines and one "amm window" line per window map when BC5_DIRECT_AMM_PRT is set.
The edit: every anchor occurs exactly once; every edit keeps braces, parentheses and brackets balanced outside comments and
literals; the inserted text is ASCII; LF line ends; a unit that has the edit already is refused, and so is an input that is
not the pinned one. After editing, the script undoes its edits and asserts that this gives the input back byte for byte.
Prints "<relpath> <md5>".
CPU test: m100401.cpp (on, off, unset, empty, junk, rw).
usage: mkm100401.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MAIN = "src/libs/bc5LleAgc.cpp"
MAIN_MD5 = "4761c532868ce1cd5e8dc097050990bb"  # e9's final main unit: e8 (bd181169) + zcb + gvw + p406
MARKS = (b"BC5_DIRECT_PROT_CENSUS", b"BC5_DIRECT_JOURNAL_DONTNEED", b"BC5_DIRECT_AMM_NULL_BO", b"BC5_DIRECT_GPU_RIGHTS", b"BC5_DIRECT_AMM_WINDOW_FIX",
         b"BC5_DIRECT_HOLES_NULL_BO", b"Bc5ProtCensus", b"Bc5AmmReserved", b"bc5_m10_", b"tag m10", b"m10_", b"M10")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes (LF)."""
    return text.replace("»", "\t").encode("ascii")


def tabs(text):
    """C++ written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


E = []  # (name, old, new) in file order


def edit(name, old, new):
    E.append((name, old, new))


# ---- the journal: m10_journal_drop at every path that writes the journal file (BC5_DIRECT_JOURNAL_DONTNEED) ----------------
DECL1_ANCHOR = b"static FILE* journal_min_file(bool flush_now) {\n"
edit("the journal hook's declaration", DECL1_ANCHOR, T(r"""static void m10_journal_drop(FILE* f); // exp 0401 e10 (tag m10, mkm100401.py): BC5_DIRECT_JOURNAL_DONTNEED, after each flush of the journal file
""") + DECL1_ANCHOR)
edit("journal_min_file's flush", T(r"""»»if (flush_now || now - last_flush > 500'000'000ull) {
»»»std::fflush(f);
»»»last_flush = now;
»»}
"""), T(r"""»»if (flush_now || now - last_flush > 500'000'000ull) {
»»»std::fflush(f);
»»»last_flush = now;
»»»m10_journal_drop(f); // exp 0401 e10 (m10): BC5_DIRECT_JOURNAL_DONTNEED (exp 0330); off, one flag test
»»}
"""))
edit("journal_quiet_put's file", T(r"""»if (FILE* f = std::fopen(name, "a"); f != nullptr) {
»»std::fputs(s, f);
»»std::fflush(f);
»»std::fclose(f);
»}
"""), T(r"""»if (FILE* f = std::fopen(name, "a"); f != nullptr) {
»»std::fputs(s, f);
»»std::fflush(f);
»»m10_journal_drop(f); // exp 0401 e10 (m10): BC5_DIRECT_JOURNAL_DONTNEED
»»std::fclose(f);
»}
"""))
edit("journal()'s file", T(r"""»std::vfprintf(f, fmt, ap);
»va_end(ap);
»std::fflush(f);
»std::fclose(f);
}
"""), T(r"""»std::vfprintf(f, fmt, ap);
»va_end(ap);
»std::fflush(f);
»m10_journal_drop(f); // exp 0401 e10 (m10): BC5_DIRECT_JOURNAL_DONTNEED
»std::fclose(f);
}
"""))

# ---- the direct part's hooks, declared before init_once_locked ------------------------------------------------------------
DECL2_ANCHOR = b"static void init_once_locked() {\n"
DECL2_HEAD = "// exp 0401 e10 (tag m10, mkm100401.py): the hooks of its switches in the direct part, defined in its block after p406's"
edit("the direct hooks' declarations", DECL2_ANCHOR, T(DECL2_HEAD + r"""
static void     m10_amm_window(const char* when, bool hold);                                         // where e9 maps the AMM window as PRT (BC5_DIRECT_AMM_PRT)
static void     m10_amm_pending();                                                                   // init_once_locked, after dump_init: the lines held at the open
static void     m10_amm_apply();                                                                     // direct_sync: Bc5AmmReserved's queue, a waiting window
static void     m10_start(bool mem_line);                                                            // mem_line_start, once: switch lines, the census's thread
static void     m10_tick(double t);                                                                  // the memory line's 10-s tick
static unsigned m10_view_rights(int prot);                                                           // BC5_DIRECT_GPU_RIGHTS: 0 e9's R|W|X, 5 R|X
static bool     m10_map_view(uint32_t id, uint64_t bo_off, uint64_t size, uint64_t va, unsigned rights); // the rebuild's map_shared
static int      m10_hole_map(uint64_t va, uint64_t size);                                            // scratch_fill: 1 mapped, 0 refused, -1 no scratch BO
static void     m10_hole_unmap(uint64_t va);                                                         // scratch_release
static void     m10_holes_reset();                                                                   // the device's reopen
static void     m10_holes_alias_sync(const std::vector<std::tuple<uint64_t, uint64_t, uint64_t>>& wins); // aliases_apply: the holes' alias null ranges
""") + DECL2_ANCHOR)

# ---- BC5_DIRECT_AMM_WINDOW_FIX / AMM_NULL_BO: the open ----------------------------------------------------------------------
edit("the AMM window at the open", T(r"""»if (std::getenv("BC5_DIRECT_AMM_PRT") != nullptr) g_dev->map_prt_window(0x8000000000ull, 0x1000000000ull);
"""), T(r"""»m10_amm_window("open", true); // exp 0401 e10 (m10): with BC5_DIRECT_AMM_PRT set, e9's PRT window (BC5_DIRECT_AMM_WINDOW_FIX: where libAmpr has it; BC5_DIRECT_AMM_NULL_BO: null pages under the reservations)
"""))
edit("the held lines after dump_init", T(r"""»dump_init();
»journal("direct: enabled, stage all, cu mask 0x%08x, bo list with mappings\n", g_cu_mask);
"""), T(r"""»dump_init();
»journal("direct: enabled, stage all, cu mask 0x%08x, bo list with mappings\n", g_cu_mask);
»m10_amm_pending(); // exp 0401 e10 (m10): the AMM window's lines from above, now that the journal has its directory
"""))

# ---- BC5_DIRECT_GPU_RIGHTS: the protection in DView, the rights in DMap -----------------------------------------------------
edit("DView: the protection", T(r"""struct DView {
»uint64_t    va, size, off;
»std::string name;
»bool        lazy;
»bool        eager;
};
"""), T(r"""struct DView {
»uint64_t    va, size, off;
»std::string name;
»bool        lazy;
»bool        eager;
»int         prot; // exp 0401 e10 (m10): the title's protection (Bc5ForEachMappedRange's), -1 when not known (private regions); BC5_DIRECT_GPU_RIGHTS
};
"""))
edit("DMap: the rights", T(r"""struct DMap {
»uint64_t va, size, bo_off;
»uint32_t id;
»bool operator==(const DMap& o) const { return va == o.va && size == o.size && bo_off == o.bo_off && id == o.id; }
};
"""), T(r"""struct DMap {
»uint64_t va, size, bo_off;
»uint32_t id;
»unsigned rights; // exp 0401 e10 (m10) BC5_DIRECT_GPU_RIGHTS: 0 map_shared (R|W|X, e9), else map_shared_rights' rights
»bool operator==(const DMap& o) const { return va == o.va && size == o.size && bo_off == o.bo_off && id == o.id && rights == o.rights; }
};
"""))
edit("direct_views_build: direct views", T(r"""»»Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int, const char* name, void* p) {
»»»if (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", direct_lazy_name(name), direct_eager_name(name)});
"""), T(r"""»»Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &v, [](uint64_t start, uint64_t size, uint64_t offset, int type, int prot, const char* name, void* p) {
»»»if (type == 0 && size != 0) static_cast<std::vector<DView>*>(p)->push_back({start, size, offset, name != nullptr ? name : "", direct_lazy_name(name), direct_eager_name(name), prot}); // + exp 0401 e10 (m10): prot
"""))
edit("direct_views_build: private views", T(r"""»»»static_cast<std::vector<DView>*>(p)->push_back({start, size, start, n, direct_lazy_name(name) || type == 3, direct_eager_name(name)});
"""), T(r"""»»»static_cast<std::vector<DView>*>(p)->push_back({start, size, start, n, direct_lazy_name(name) || type == 3, direct_eager_name(name), -1}); // + exp 0401 e10 (m10): no protection here
"""))
edit("direct_views: the signature", T(r"""»»for (const uint64_t x: {v.va, v.size, v.off}) sig = (sig ^ x) * 1099511628211ull;
"""), T(r"""»»for (const uint64_t x: {v.va, v.size, v.off}) sig = (sig ^ x) * 1099511628211ull;
»»if (const uint64_t r = m10_view_rights(v.prot); r != 0) sig = (sig ^ r) * 1099511628211ull; // exp 0401 e10 (m10) BC5_DIRECT_GPU_RIGHTS: a rights change remaps; off, 0
"""))
edit("zsk_views", T(r"""»for (size_t i = 0; i < n; i++) v.push_back(DView {0x10000000000ull + offs[i], sizes[i], offs[i], names[i], false, eager[i] != 0});
"""), T(r"""»for (size_t i = 0; i < n; i++) v.push_back(DView {0x10000000000ull + offs[i], sizes[i], offs[i], names[i], false, eager[i] != 0, -1}); // + exp 0401 e10 (m10): prot
"""))
edit("the rebuild: the rights", T(r"""»»»»want.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id});
"""), T(r"""»»»»want.push_back({v.va + (lo - v.off), hi - lo, lo - it->off, it->id, m10_view_rights(v.prot)}); // + exp 0401 e10 (m10) BC5_DIRECT_GPU_RIGHTS
"""))
edit("the rebuild: the map", T(r"""»»»»if (g_dev->map_shared(w.id, w.bo_off, w.size, w.va)) {
"""), T(r"""»»»»if (m10_map_view(w.id, w.bo_off, w.size, w.va, w.rights)) { // exp 0401 e10 (m10): rights 0 is e9's map_shared
"""))

# ---- BC5_DIRECT_AMM_NULL_BO / WINDOW_FIX: the queue at each submission ------------------------------------------------------
edit("direct_sync: the AMM queue", T(r"""static void direct_sync(bool force) {
»for (auto& S: g_d) direct_sync_one(S, force);
}
"""), T(r"""static void direct_sync(bool force) {
»m10_amm_apply(); // exp 0401 e10 (m10): Bc5AmmReserved's events and a waiting AMM window (BC5_DIRECT_AMM_NULL_BO, _WINDOW_FIX); none: two flag tests
»for (auto& S: g_d) direct_sync_one(S, force);
}
"""))

# ---- BC5_DIRECT_HOLES_NULL_BO -------------------------------------------------------------------------------------------------
edit("aliases_apply: the holes' aliases", T(r"""»for (const auto& [t, a, n]: g_aliases) bytes += g_dev->map_alias(a, n, (t << 40u) + a);
"""), T(r"""»for (const auto& [t, a, n]: g_aliases) bytes += g_dev->map_alias(a, n, (t << 40u) + a);
»m10_holes_alias_sync(g_aliases); // exp 0401 e10 (m10) BC5_DIRECT_HOLES_NULL_BO: map_alias leaves null ranges out, so the holes' aliases are null ranges too
"""))
edit("scratch_release", T(r"""»»if (va < hi && va + n > lo) {
»»»g_dev->unmap_shared(va);
»»»g_scratch.erase(g_scratch.begin() + static_cast<std::ptrdiff_t>(i));
"""), T(r"""»»if (va < hi && va + n > lo) {
»»»m10_hole_unmap(va); // exp 0401 e10 (m10) BC5_DIRECT_HOLES_NULL_BO: unmap_null_range for a null piece; else unmap_shared as e9
»»»g_scratch.erase(g_scratch.begin() + static_cast<std::ptrdiff_t>(i));
"""))
edit("scratch_fill", T(r"""»»»const uint32_t id = scratch_bo();
»»»if (id == 0) break;
»»»if (!g_dev->map_shared(id, 0, n, pa)) {
"""), T(r"""»»»const int m10h = m10_hole_map(pa, n); // exp 0401 e10 (m10) BC5_DIRECT_HOLES_NULL_BO: null pages (map_null_range); off: scratch_bo and map_shared as e9
»»»if (m10h < 0) break;
»»»if (m10h == 0) {
"""))

# ---- the memory line: the tick, the start -------------------------------------------------------------------------------------
edit("the memory line's tick", T(r"""»»journal("%s", line);
»»if (g_journal_min) (void)journal_min_file(true);
"""), T(r"""»»journal("%s", line);
»»if (g_journal_min) (void)journal_min_file(true);
»»m10_tick(timing_now()); // exp 0401 e10 (m10): BC5_DIRECT_PROT_CENSUS's totals when due, BC5_DIRECT_JOURNAL_DONTNEED's count; off, two flag tests
"""))
edit("mem_line_start", T(r"""»»if (on) std::thread(mem_line_loop).detach();
"""), T(r"""»»if (on) std::thread(mem_line_loop).detach();
»»m10_start(on); // exp 0401 e10 (m10): four switch lines; the census's thread (PROT_CENSUS), a 10-s tick for the dontneed count without the memory line
"""))

# ---- the reopen ---------------------------------------------------------------------------------------------------------------
edit("the AMM window at the reopen", T(r"""»»if (g_dev && std::getenv("BC5_DIRECT_AMM_PRT") != nullptr) g_dev->map_prt_window(0x8000000000ull, 0x1000000000ull); // experiment 0102
"""), T(r"""»»if (g_dev) m10_amm_window("reopen", false); // experiment 0102; exp 0401 e10 (m10): with BC5_DIRECT_AMM_PRT set, e9's PRT window or the switches'
"""))
edit("the reopen: the holes", T(r"""»»g_scratch.clear();
»»g_scratch_id = 0;
"""), T(r"""»»g_scratch.clear();
»»g_scratch_id = 0;
»»m10_holes_reset(); // exp 0401 e10 (m10): the null pieces went with the old device
"""))

# ---- the two per-submission lines of the journal without "min" ----------------------------------------------------------------
edit("the per-submission line, first half", T(r"""»»»             n, kind, num_dwords, static_cast<const void*>(ib), pre.passed, pre.rewritten, pre.dropped, pre.unmapped_drops, pre.context_control_rewrites, maps_p->size());
»»»std::fflush(f);
»»»fsync(fileno(f));
»»»std::fclose(f);
"""), T(r"""»»»             n, kind, num_dwords, static_cast<const void*>(ib), pre.passed, pre.rewritten, pre.dropped, pre.unmapped_drops, pre.context_control_rewrites, maps_p->size());
»»»std::fflush(f);
»»»fsync(fileno(f));
»»»m10_journal_drop(f); // exp 0401 e10 (m10): BC5_DIRECT_JOURNAL_DONTNEED
»»»std::fclose(f);
"""))
edit("the per-submission line, second half", T(r"""»»»std::fflush(f);
»»»if (!r.ok) fsync(fileno(f));
»»»std::fclose(f);
"""), T(r"""»»»std::fflush(f);
»»»if (!r.ok) fsync(fileno(f));
»»»m10_journal_drop(f); // exp 0401 e10 (m10): BC5_DIRECT_JOURNAL_DONTNEED
»»»std::fclose(f);
"""))
edit("p406_seam_views", T(r"""»for (uint32_t k = 0; k < count; k++) v.push_back({va[k], size[k], va[k], eager[k] != 0 ? "eager" : "other", false, eager[k] != 0});
"""), T(r"""»for (uint32_t k = 0; k < count; k++) v.push_back({va[k], size[k], va[k], eager[k] != 0 ? "eager" : "other", false, eager[k] != 0, -1}); // + exp 0401 e10 (m10): prot
"""))

# ---- the block, after p406's ----------------------------------------------------------------------------------------------------
BLOCK_ANCHOR = b"// ---- end of exp 0406's (tag p406) block " + b"-" * 83 + b"\n"
PURE_MARK = b"// ---- exp 0401 e10 (tag m10): the pure part"
HOST_MARK = b"// ---- exp 0401 e10 (tag m10): the host's side"
SEAMS_MARK = b"// ---- exp 0401 e10 (tag m10): the CPU test's seams"
SEAMS_END = b"// ---- end of exp 0401 e10's (tag m10) seams"
BLOCK_END = b"// ---- end of exp 0401 e10's (tag m10) block"
BLOCK = tabs(r"""
// ---- exp 0401 series e10 (tag m10, mkm100401.py): six switches of exp 0408 G6 (the census, dontneed, GPU rights, the AMM window) --
} // namespace Bc5LleKernel (m10 closes it here for its block and opens it again below)

namespace Bc5Gc::Direct {
#if defined(KYTY_BC5_DIRECT)
// ---- exp 0401 e10 (tag m10): the pure part --------------------------------------------------------------------------------
// Exp 0408 (bc5-0408 experiments/0408-memory-review/README.md, section G6 at 509083aa; e10's contract in m100401-notes.md)
// orders the changes that bring the memory model closer to the console's. Six of them are switches here, each off by default
// (bc5::env_on's reading, F767), read once, with one journal line that names its mode:
//   BC5_DIRECT_PROT_CENSUS (row 2): log only, at the calls (Bc5ProtCensus, from memory.cpp and libAmpr.cpp) and, on the
//     memory line's thread, the bytes imported per GPU class and the forced chunks' pin. Never from direct_breakdown_one
//     (its SEEK_DATA walk held the game thread 25-80 s, exp 0288 README:25-27). The protection is the title's: memory.cpp
//     stores the int it was given (KernelMapDirectMemory, KernelMprotect, the flexible and pooled maps); only the host page
//     protection is widened (sysLinuxVirtual.cpp get_protection_flag, memoryAddressSpace.inc GetProtect).
//   BC5_DIRECT_JOURNAL_DONTNEED (row 6, exp 0330's switch, experiments/0330-host-memory/patch_0330.diff hunks 1-3).
//   BC5_DIRECT_GPU_RIGHTS (row 4): GPU_READ without GPU_WRITE maps R|X (RPCSX's prot >> 4, gpu/Device.cpp:1027, e8ae148);
//     X stays everywhere: whether the GPU fetches shader code from the title's heaps is not known here, TODO(verify).
//   BC5_DIRECT_AMM_WINDOW_FIX (row 5): the PRT window where the AMM window is (exp 0408 G7: hard-coded at 0x8000000000).
//   BC5_DIRECT_AMM_NULL_BO, BC5_DIRECT_HOLES_NULL_BO (row 5, exp 0407's N1): null pages under the title's AMM reservations
//     and under the learned windows' holes. RADV maps unbound sparse memory with an 8-MiB zero BO, read-only (Mesa ab2374a
//     src/amd/vulkan/winsys/amdgpu/radv_amdgpu_bo.c:412-437; READ_ONLY drops WRITEABLE, :40-48), because on GFX10-12 an SMEM
//     load from a NULL PRT page faults and hangs the GPU (src/amd/common/ac_gpu_info.c:437-442). TODO(verify): that the null
//     BO's page tables stay small (the kernel's fragment handling for a VRAM or GTT backing is not cited); the AMM lines
//     carry VRAM and GTT use before and after to measure it.
// KytyPlus's protection bits (patch 0001, P:20408-20411): CPU_READ 0x1, CPU_WRITE 0x2, CPU_EXEC 0x4, GPU_READ 0x10, GPU_WRITE 0x20.
extern "C" int  Bc5AmmWindow(uint64_t* va, uint64_t* size) __attribute__((weak)); // libAmpr.cpp (tag p10); weak: without it the unit links and says so
extern "C" void Bc5AmmForEachReserved(void (*cb)(uint64_t va, uint64_t size, void* ctx), void* ctx) __attribute__((weak));
constexpr int      kM10GpuRead    = 0x10;
constexpr int      kM10GpuWrite   = 0x20;
constexpr uint64_t kM10DropStep   = 8ull << 20u;     // exp 0330: every 8 MiB the journal grows
constexpr uint64_t kM10DropLine   = 64;              // the dontneed count: every 64 writebacks started (512 MiB)
constexpr uint64_t kM10AmmVa      = 0x8000000000ull; // e9's AMM window (exp 0102)
constexpr uint64_t kM10AmmSize    = 0x1000000000ull;
constexpr uint64_t kM10Align      = 0x10000ull;      // map_prt_window's and map_null_window's alignment
constexpr uint32_t kM10CallLines  = 1000;            // the census: lines one per call in 10 s
constexpr uint32_t kM10AggLines   = 200;             // the census: counted groups written per 10 s
constexpr size_t   kM10Ring       = 65536;           // the census: calls held between two writes
constexpr uint32_t kM10EventLines = 256;             // lines for Bc5AmmReserved's events
constexpr unsigned kM10RightsRX   = 1u | 4u;         // map_shared_rights: READABLE | EXECUTABLE (AMDGPU_VM_PAGE_*)
constexpr char     kM10CensusP[]  = "prot census (exp 0401 e10 m10): ";
static bool m10_parse(const char* e) { // unset, empty and "0" are off
    return bc5::env_on(e);
}
static int m10_null_parse(const char* e) { // AMM_NULL_BO and HOLES_NULL_BO: 0 off, 1 read-only, 2 writable ("rw")
    if (!m10_parse(e)) return 0;
    return std::strcmp(e, "rw") == 0 ? 2 : 1;
}
static const char* m10_off_how(const char* e) {
    return e == nullptr ? "unset" : e[0] == 0 ? "empty" : "=0";
}
static const char* const kM10Names[6] = {"BC5_DIRECT_PROT_CENSUS", "BC5_DIRECT_JOURNAL_DONTNEED", "BC5_DIRECT_AMM_NULL_BO", "BC5_DIRECT_GPU_RIGHTS",
                                         "BC5_DIRECT_AMM_WINDOW_FIX", "BC5_DIRECT_HOLES_NULL_BO"};
// The switch lines. which: 0 PROT_CENSUS, 1 JOURNAL_DONTNEED, 2 AMM_NULL_BO, 3 GPU_RIGHTS, 4 AMM_WINDOW_FIX, 5 HOLES_NULL_BO.
static void m10_switch_text(int which, int mode, const char* e, char* out, size_t cap) {
    const char* const v   = e != nullptr ? e : "";
    const bool        one = std::strcmp(v, "1") == 0;
    const char* const any = one ? "" : ", any value but unset, empty or 0 is on";
    const char* const ro  = one ? "" : ", any value but unset, empty, 0 or rw is read-only";
    if (mode == 0) {
        static const char* const what[6] = {"prot census", "journal dontneed", "amm null bo", "gpu rights", "amm window fix", "holes null bo"};
        std::snprintf(out, cap, "exp 0401 e10 (m10): %s off (%s %s): as e9\n", what[which], kM10Names[which], m10_off_how(e));
    } else if (which == 0) {
        std::snprintf(out, cap,
                      "exp 0401 e10 (m10): prot census on (BC5_DIRECT_PROT_CENSUS=%.40s%s): each map, mprotect, mtypeprotect and AMM call with the title's "
                      "protection, a line per call (AMM calls, unmaps and calls past 1000 in 10 s counted every 10 s); at journal time 120, 300 and 600 s, then "
                      "every 600 s, the bytes imported per GPU class and the forced chunks' pin\n",
                      v, any);
    } else if (which == 1) {
        std::snprintf(out, cap,
                      "exp 0401 e10 (m10): journal dontneed on (BC5_DIRECT_JOURNAL_DONTNEED=%.40s%s): each time the journal has grown 8 MiB, the writeback of "
                      "the new part is started (sync_file_range) and the part started the time before leaves the page cache (posix_fadvise DONTNEED); exp 0330's switch\n",
                      v, any);
    } else if (which == 2) {
        std::snprintf(out, cap,
                      "exp 0401 e10 (m10): amm null bo on, %s (BC5_DIRECT_AMM_NULL_BO=%.40s%s): with BC5_DIRECT_AMM_PRT set, %s null pages (map_null_window) under "
                      "the title's reservations inside the AMM window, PRT over the rest\n",
                      mode == 2 ? "writable" : "read-only", v, mode == 2 ? "" : ro, mode == 2 ? "writable" : "read-only");
    } else if (which == 3) {
        std::snprintf(out, cap,
                      "exp 0401 e10 (m10): gpu rights on (BC5_DIRECT_GPU_RIGHTS=%.40s%s): a direct view whose protection has GPU_READ and not GPU_WRITE is mapped "
                      "R|X (map_shared_rights), every other one R|W|X as e9\n",
                      v, any);
    } else if (which == 4) {
        std::snprintf(out, cap,
                      "exp 0401 e10 (m10): amm window fix on (BC5_DIRECT_AMM_WINDOW_FIX=%.40s%s): with BC5_DIRECT_AMM_PRT set, the PRT window where Bc5AmmWindow "
                      "says the AMM window is, not at 0x8000000000\n",
                      v, any);
    } else {
        std::snprintf(out, cap,
                      "exp 0401 e10 (m10): holes null bo on, %s (BC5_DIRECT_HOLES_NULL_BO=%.40s%s): the learned windows' holes get %s null pages (map_null_range) "
                      "instead of the writable 2 MiB scratch BO\n",
                      mode == 2 ? "writable" : "read-only", v, mode == 2 ? "" : ro, mode == 2 ? "writable" : "read-only");
    }
}
// -- the census's pure part
// The census times: journal time 120, 300 and 600 s, then every 600 s. The next one after t: a late tick skips the ones it missed.
static double m10_census_next(double t) {
    if (t < 120.0) return 120.0;
    if (t < 300.0) return 300.0;
    return (std::floor(t / 600.0) + 1.0) * 600.0;
}
static bool m10_census_due(double next, double t) {
    return t >= next;
}
static const char* m10_type_name(int type) { // Bc5ForEachMappedRange's types
    switch (type) {
    case 0: return "direct";
    case 1: return "flexible";
    case 2: return "pooled";
    case 3: return "stack";
    case 4: return "code";
    case 5: return "runtime";
    default: return "type?";
    }
}
// The mapper state whose memfd backs a range: 0 the direct memfd (type 0, at the range's file offset), 1 the private memfd
// (stack, code, runtime: Commit, at the guest address), -1 none the mapper views (flexible and pooled are mapped from the
// direct memfd by MapBacking, at an offset the ranges do not keep).
static int m10_state_of(int type) {
    return type == 0 ? 0 : type >= 3 && type <= 5 ? 1 : -1;
}
// The class the mapper gives a range today (direct_views_build, direct_sync_one): 0 an eager name (imported in full), 1 a lazy
// name (only what is forced), 2 thread stacks (private, lazy), 3 data (what holds data is imported), 4 no view.
static int m10_class(int type, bool eager_name, bool lazy_name) {
    if (m10_state_of(type) < 0) return 4;
    if (eager_name) return 0;
    if (type == 3) return 2;
    return lazy_name ? 1 : 3;
}
static const char* m10_class_name(int c) {
    switch (c) {
    case 0: return "eager name";
    case 1: return "lazy name";
    case 2: return "lazy stacks";
    case 3: return "data";
    default: return "no view";
    }
}
static int m10_gpu_class(int prot) { // 0 no GPU bit, 1 GPU_READ only, 2 GPU_WRITE only, 3 both
    return ((prot & kM10GpuRead) != 0 ? 1 : 0) + ((prot & kM10GpuWrite) != 0 ? 2 : 0);
}
static const char* m10_gpu_name(int g) {
    switch (g) {
    case 0: return "no gpu bit";
    case 1: return "gpu read only";
    case 2: return "gpu write only";
    default: return "gpu read and write";
    }
}
static void m10_prot_text(int prot, char* out, size_t cap) {
    std::snprintf(out, cap, "cpu %c%c%c gpu %c%c", (prot & 0x1) != 0 ? 'r' : '-', (prot & 0x2) != 0 ? 'w' : '-', (prot & 0x4) != 0 ? 'x' : '-',
                  (prot & kM10GpuRead) != 0 ? 'r' : '-', (prot & kM10GpuWrite) != 0 ? 'w' : '-');
}
static std::string m10_clean(const char* s) { // a name for the journal: printable ASCII, no quote, at most 64 bytes
    std::string o;
    for (; s != nullptr && *s != 0 && o.size() < 64; s++) o.push_back(*s >= 0x20 && *s <= 0x7e && *s != '"' ? *s : '?');
    return o;
}
static std::string m10_fmt(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static std::string m10_fmt(const char* fmt, ...) {
    char    t[1024];
    va_list ap;
    va_start(ap, fmt);
    const int n = std::vsnprintf(t, sizeof(t), fmt, ap);
    va_end(ap);
    return n < 0 ? std::string() : std::string(t, std::min(static_cast<size_t>(n), sizeof(t) - 1));
}
struct M10Bo {
    uint64_t off = 0, size = 0;
};
// The bytes of [lo, hi) inside a state's BOs (sorted by offset, disjoint).
static uint64_t m10_overlap(const std::vector<M10Bo>& bos, uint64_t lo, uint64_t hi) {
    if (hi <= lo) return 0;
    auto it = std::upper_bound(bos.begin(), bos.end(), lo, [](uint64_t o, const M10Bo& b) { return o < b.off; });
    if (it != bos.begin()) --it;
    uint64_t n = 0;
    for (; it != bos.end() && it->off < hi; ++it) {
        const uint64_t a = std::max(it->off, lo), b = std::min(it->off + it->size, hi);
        if (a < b) n += b - a;
    }
    return n;
}
struct M10Range {
    uint64_t start = 0, size = 0, offset = 0;
    int      type = 0, prot = 0;
};
struct M10Total {
    uint64_t views = 0, bytes = 0, imported = 0;
};
// The four totals per GPU class: the ranges, their bytes, the bytes imported for them.
static void m10_totals(const std::vector<M10Range>& ranges, const std::vector<M10Bo> (&bos)[2], M10Total (&tot)[4]) {
    for (const auto& r: ranges) {
        const int      s   = m10_state_of(r.type);
        const uint64_t lo  = s == 0 ? r.offset : r.start;
        const uint64_t imp = s < 0 ? 0 : m10_overlap(bos[s], lo, lo + r.size);
        M10Total&      t   = tot[m10_gpu_class(r.prot)];
        t.views++;
        t.bytes += r.size;
        t.imported += imp;
    }
}
// The chunks the hints and learned windows forced (S.forced), of one state: under an eager view, or else holding data, or else
// neither: the pin those windows alone cause; and of those, the ones imported.
struct M10Forced {
    bool     classified = true; // false: no memfd, not classified
    uint64_t total = 0, eager = 0, data = 0, neither = 0, neither_imported = 0, neither_bytes = 0, seeks = 0;
    double   ms = 0.0;
};
// forced: sorted. eager: file ranges, sorted and merged (m10_merge). has_data(c): the memfd holds data in [c, c + kDChunk);
// asked once per chunk no eager view covers, never for the others.
template <class HasData>
static M10Forced m10_forced(const std::vector<uint64_t>& forced, const std::vector<std::pair<uint64_t, uint64_t>>& eager, const std::vector<M10Bo>& bos, HasData has_data) {
    M10Forced f;
    size_t    e = 0;
    for (const uint64_t c: forced) {
        f.total++;
        while (e < eager.size() && eager[e].second <= c) e++;
        if (e < eager.size() && eager[e].first < c + kDChunk) {
            f.eager++;
            continue;
        }
        f.seeks++;
        if (has_data(c)) {
            f.data++;
            continue;
        }
        f.neither++;
        const uint64_t ov = m10_overlap(bos, c, c + kDChunk);
        if (ov != 0) {
            f.neither_imported++;
            f.neither_bytes += ov;
        }
    }
    return f;
}
static std::vector<std::pair<uint64_t, uint64_t>> m10_merge(std::vector<std::pair<uint64_t, uint64_t>> v) { // sorted, merged, empty ones out
    std::sort(v.begin(), v.end());
    std::vector<std::pair<uint64_t, uint64_t>> out;
    for (const auto& r: v) {
        if (r.second <= r.first) continue;
        if (!out.empty() && r.first <= out.back().second) {
            out.back().second = std::max(out.back().second, r.second);
        } else {
            out.push_back(r);
        }
    }
    return out;
}
struct M10Head {
    uint32_t no = 0, busy = 0;
    uint64_t ranges = 0, bos[2] = {0, 0}, bytes[2] = {0, 0}, rights = 0;
    double   hold_ms = 0.0;
};
static std::string m10_forced_line(const M10Forced& f, const char* label, double t) {
    if (!f.classified)
        return m10_fmt("%st %.0f s: forced %s: %" PRIu64 " chunks of 2 MiB the hints and learned windows asked for; no memfd, not classified\n", kM10CensusP, t, label, f.total);
    return m10_fmt("%st %.0f s: forced %s: %" PRIu64 " chunks of 2 MiB the hints and learned windows asked for: %" PRIu64 " under an eager view, %" PRIu64
                   " more hold data, %" PRIu64 " neither (the pin the windows alone cause), %" PRIu64 " of those imported (%.1f MiB); %" PRIu64 " SEEK_DATA, %.3f ms\n",
                   kM10CensusP, t, label, f.total, f.eager, f.data, f.neither, f.neither_imported, static_cast<double>(f.neither_bytes) / 1048576.0, f.seeks, f.ms);
}
// One periodic census: the header, the four totals per GPU class, the forced chunks of the direct and the private state.
static void m10_census_lines(const M10Total (&tot)[4], const M10Head& h, const M10Forced (&fc)[2], double t, std::vector<std::string>& out) {
    const double mib = 1048576.0;
    out.push_back(m10_fmt("%st %.0f s: census %u: %" PRIu64 " guest ranges; direct memfd %" PRIu64 " BOs, %.1f MiB imported; private memfd %" PRIu64
                          " BOs, %.1f MiB imported; the device lock held %.3f ms for the copy, %u ticks found it busy first; %" PRIu64
                          " views mapped R|X so far (BC5_DIRECT_GPU_RIGHTS); a page under two views counts twice\n",
                          kM10CensusP, t, h.no, h.ranges, h.bos[0], static_cast<double>(h.bytes[0]) / mib, h.bos[1], static_cast<double>(h.bytes[1]) / mib, h.hold_ms,
                          h.busy, h.rights));
    for (int k = 0; k < 4; k++)
        out.push_back(m10_fmt("%st %.0f s: total, %s: %" PRIu64 " views, %" PRIu64 " bytes (%.1f MiB), %" PRIu64 " imported (%.1f MiB)\n", kM10CensusP, t, m10_gpu_name(k),
                              tot[k].views, tot[k].bytes, static_cast<double>(tot[k].bytes) / mib, tot[k].imported, static_cast<double>(tot[k].imported) / mib));
    out.push_back(m10_forced_line(fc[0], "direct", t));
    out.push_back(m10_forced_line(fc[1], "private", t));
}
// -- the census at the calls: one call as Bc5ProtCensus got it; lines one per call, and counted groups every 10 s
struct M10Call {
    uint64_t va = 0, size = 0, phys = 0, t_ns = 0;
    int      call = 0, prot = 0, type = 0;
    char     name[40] = {};
};
static void m10_call_name(int call, char* out, size_t cap) { // CONTRACT: 1 map, 2 mprotect, 3 mtypeprotect, 4 AMM map, 5 AMM remap, 6 unmap
    static const char* const n[7] = {"", "map", "mprotect", "mtypeprotect", "amm map", "amm remap", "unmap"};
    if (call >= 1 && call <= 6) std::snprintf(out, cap, "%s", n[call]);
    else std::snprintf(out, cap, "call %d", call);
}
static bool m10_call_lined(int call) { // map, mprotect, mtypeprotect: a line each (while the 10 s allow); the rest counted
    return call >= 1 && call <= 3;
}
static std::string m10_call_line(const M10Call& c, int cls) {
    char p[32], cn[24];
    m10_prot_text(c.prot, p, sizeof(p));
    m10_call_name(c.call, cn, sizeof(cn));
    return m10_fmt("%smono %.3f s: %s va 0x%" PRIx64 " size 0x%" PRIx64 " phys 0x%" PRIx64 " prot 0x%x (%s) %s \"%s\": %s\n", kM10CensusP, static_cast<double>(c.t_ns) / 1e9, cn,
                   c.va, c.size, c.phys, static_cast<unsigned>(c.prot), p, m10_type_name(c.type), m10_clean(c.name).c_str(), m10_class_name(cls));
}
struct M10Agg {
    uint64_t calls = 0, bytes = 0;
    int      cls   = 0;
};
struct M10Window { // 10 s of calls, from the first one's time
    bool                                                     open = false;
    double                                                   lo   = 0.0;
    uint64_t                                                 calls = 0, lines = 0, counted = 0, lost = 0;
    std::map<std::tuple<int, int, int, std::string>, M10Agg> agg; // (call, type, protection, name)
};
static void m10_win_close(M10Window& w, std::vector<std::string>& out) {
    if (!w.open) return;
    std::vector<std::pair<std::tuple<int, int, int, std::string>, M10Agg>> v(w.agg.begin(), w.agg.end());
    std::stable_sort(v.begin(), v.end(), [](const auto& a, const auto& b) { return a.second.calls > b.second.calls; });
    uint64_t rest_calls = 0, rest_bytes = 0;
    for (size_t i = 0; i < v.size(); i++) {
        const auto& [k, a] = v[i];
        if (i >= kM10AggLines) {
            rest_calls += a.calls;
            rest_bytes += a.bytes;
            continue;
        }
        char p[32], cn[24];
        m10_prot_text(std::get<2>(k), p, sizeof(p));
        m10_call_name(std::get<0>(k), cn, sizeof(cn));
        out.push_back(m10_fmt("%smono %.0f to %.0f s: %s %s \"%s\" prot 0x%x (%s): %" PRIu64 " calls, %" PRIu64 " bytes; %s\n", kM10CensusP, w.lo, w.lo + 10.0, cn,
                              m10_type_name(std::get<1>(k)), m10_clean(std::get<3>(k).c_str()).c_str(), static_cast<unsigned>(std::get<2>(k)), p, a.calls, a.bytes,
                              m10_class_name(a.cls)));
    }
    if (v.size() > kM10AggLines)
        out.push_back(m10_fmt("%smono %.0f to %.0f s: ... %zu more groups: %" PRIu64 " calls, %" PRIu64 " bytes\n", kM10CensusP, w.lo, w.lo + 10.0, v.size() - kM10AggLines,
                              rest_calls, rest_bytes));
    out.push_back(m10_fmt("%smono %.0f to %.0f s: %" PRIu64 " calls: %" PRIu64 " with a line each, %" PRIu64 " counted in %zu groups, %" PRIu64
                          " lost (the census holds %zu calls between two writes)\n",
                          kM10CensusP, w.lo, w.lo + 10.0, w.calls, w.lines, w.counted, v.size(), w.lost, kM10Ring));
    w = M10Window {};
}
// One call into the window: a line of its own while the window allows it (map, mprotect, mtypeprotect), else counted.
// names(name): bit 0 an eager name, bit 1 a lazy name.
template <class Names>
static void m10_win_add(M10Window& w, const M10Call& c, Names names, std::vector<std::string>& out) {
    const double t = static_cast<double>(c.t_ns) / 1e9;
    if (w.open && t - w.lo >= 10.0) m10_win_close(w, out);
    if (!w.open) {
        w.open = true;
        w.lo   = t;
    }
    w.calls++;
    const int nm  = names(c.name);
    const int cls = m10_class(c.type, (nm & 1) != 0, (nm & 2) != 0);
    if (m10_call_lined(c.call) && w.lines < kM10CallLines) {
        w.lines++;
        out.push_back(m10_call_line(c, cls));
        return;
    }
    M10Agg& a = w.agg[std::make_tuple(c.call, c.type, c.prot, std::string(c.name))];
    a.calls++;
    a.bytes += c.size;
    a.cls = cls;
    w.counted++;
}
// -- BC5_DIRECT_JOURNAL_DONTNEED: exp 0330's journal_drop, its arithmetic unchanged. started: where the last writeback started
// ended; dropped: what has left the page cache. Once the file has grown kM10DropStep past started: [dropped, started) leaves the
// page cache (its writeback was started the time before), the writeback of [started, end) is started, started = end.
struct M10Drop {
    uint64_t started = 0, dropped = 0;
    uint64_t syncs = 0, drops = 0, sync_err = 0, drop_err = 0;
    uint64_t sync_lo = 0, sync_len = 0, drop_lo = 0, drop_len = 0; // the last calls
    int      sync_rc = 0, drop_rc = 0;                             // their results: sync_file_range's (0 or -1), posix_fadvise's (0 or an error number)
};
struct M10DropPlan {
    bool     act     = false;
    uint64_t drop_lo = 0, drop_len = 0, sync_lo = 0, sync_len = 0;
};
static M10DropPlan m10_drop_plan(const M10Drop& st, uint64_t end) {
    M10DropPlan p;
    if (end < st.started || end - st.started < kM10DropStep) return p;
    p.act = true;
    if (st.started > st.dropped) {
        p.drop_lo  = st.dropped;
        p.drop_len = st.started - st.dropped;
    }
    p.sync_lo  = st.started;
    p.sync_len = end - st.started;
    return p;
}
static bool m10_drop_tell(uint64_t told_syncs, uint64_t told_errs, uint64_t syncs, uint64_t errs) { // the count: every 64 writebacks, and a new failure
    return syncs / kM10DropLine > told_syncs / kM10DropLine || errs > told_errs;
}
static void m10_drop_text(const M10Drop& s, double t, char* out, size_t cap) {
    std::snprintf(out, cap,
                  "journal dontneed (exp 0401 e10 m10): t %.0f s: %" PRIu64 " writebacks started (sync_file_range), %" PRIu64 " ranges dropped (posix_fadvise "
                  "DONTNEED); started up to %.1f MiB, dropped up to %.1f MiB; failures %" PRIu64 " and %" PRIu64 ", the last results %d and %d\n",
                  t, s.syncs, s.drops, static_cast<double>(s.started) / 1048576.0, static_cast<double>(s.dropped) / 1048576.0, s.sync_err, s.drop_err, s.sync_rc,
                  s.drop_rc);
}
// -- BC5_DIRECT_GPU_RIGHTS: GPU_READ without GPU_WRITE is R|X; 0 is e9's map_shared (R|W|X).
static unsigned m10_rights_of(int prot) {
    return prot >= 0 && (prot & kM10GpuRead) != 0 && (prot & kM10GpuWrite) == 0 ? kM10RightsRX : 0u;
}
// -- BC5_DIRECT_AMM_NULL_BO / WINDOW_FIX: the window's layout. The PRT window over all of [w, w + wn) first (e9's call), then
// map_null_window over each reservation inside it: the backend REPLACEs the PRT pages there (nbo's contract: wholly inside one
// PRT window), and puts them back if it fails. Never over the whole window (exp 0408 G6 row 5: ~128 MiB of 4 KiB PTEs).
static uint64_t m10_up(uint64_t x) {
    return (x + kM10Align - 1) & ~(kM10Align - 1);
}
static uint64_t m10_down(uint64_t x) {
    return x & ~(kM10Align - 1);
}
struct M10Layout {
    bool                                       prt_ok = false;
    std::vector<std::pair<uint64_t, uint64_t>> nulls; // [lo, hi) mapped as null pages
    uint32_t                                   asked = 0, small = 0, whole = 0, null_failed = 0, null_absent = 0;
    uint64_t                                   null_bytes = 0;
};
// res: [lo, hi) of the reservations (any order, any alignment). mode: AMM_NULL_BO's. null(lo, n, writable): 1 mapped, 0 failed,
// -1 no map_null_window in this backend. prt(lo, n): map_prt_window.
template <class Null, class Prt>
static M10Layout m10_amm_layout(uint64_t w, uint64_t wn, const std::vector<std::pair<uint64_t, uint64_t>>& res, int mode, Null null, Prt prt) {
    M10Layout      L;
    const uint64_t we = w + wn;
    L.prt_ok          = prt(w, wn);
    if (mode == 0) return L;
    std::vector<std::pair<uint64_t, uint64_t>> rs;
    for (const auto& r: res) {
        const uint64_t lo = std::max(r.first, w), hi = std::min(r.second, we);
        if (hi <= lo) continue; // outside the window
        const uint64_t a = m10_up(lo), b = m10_down(hi);
        if (b <= a) {
            L.small++;
            continue;
        }
        rs.emplace_back(a, b);
    }
    for (const auto& [a, b]: m10_merge(std::move(rs))) {
        L.asked++;
        if (a <= m10_up(w) && b >= m10_down(we)) { // the whole window: never
            L.whole++;
            continue;
        }
        const int k = null(a, b - a, mode == 2);
        if (k == 1) {
            L.nulls.emplace_back(a, b);
            L.null_bytes += b - a;
        } else if (k < 0) {
            L.null_absent++;
        } else {
            L.null_failed++;
        }
    }
    return L;
}
// One Bc5AmmReserved event once the window is laid. Returns: 0 already under null pages, 1 null pages mapped, 2 map_null_window
// refused it (PRT stays), 3 given back: its null pages stay (the backend has no call to give them back), 4 outside the window,
// 5 under 64 KiB once aligned, 6 given back: not one of the null ranges, 7 no map_null_window in this backend (PRT stays),
// 8 the whole window (never).
template <class Null>
static int m10_amm_event(std::vector<std::pair<uint64_t, uint64_t>>& nulls, uint64_t w, uint64_t wn, uint64_t va, uint64_t size, int on, int mode, Null null) {
    const uint64_t we = w + wn, lo = std::max(va, w), hi = std::min(va + size, we);
    if (hi <= lo) return 4;
    const uint64_t a = m10_up(lo), b = m10_down(hi);
    if (b <= a) return 5;
    const bool in = std::any_of(nulls.begin(), nulls.end(), [a, b](const std::pair<uint64_t, uint64_t>& r) { return r.first <= a && b <= r.second; });
    if (on == 0) return in ? 3 : 6;
    if (in) return 0;
    if (a <= m10_up(w) && b >= m10_down(we)) return 8;
    const int k = null(a, b - a, mode == 2);
    if (k == 1) {
        nulls.emplace_back(a, b);
        std::sort(nulls.begin(), nulls.end());
        return 1;
    }
    return k < 0 ? 7 : 2;
}
static std::string m10_amm_event_text(uint64_t va, uint64_t size, int on, int code, int mode) {
    static const char* const what[9] = {"already under null pages", "", "map_null_window refused it: PRT stays",
                                        "its null pages stay (the backend has no call to give them back)", "outside the AMM window: nothing",
                                        "under 64 KiB once aligned: nothing", "not one of the null ranges: nothing", "no map_null_window in this backend: PRT stays",
                                        "the whole window: never (PRT stays)"};
    const std::string        done = mode == 2 ? "writable null pages (map_null_window)" : "read-only null pages (map_null_window)";
    return m10_fmt("amm window (exp 0401 e10 m10): reservation 0x%" PRIx64 "+0x%" PRIx64 " %s: %s\n", va, size, on != 0 ? "made" : "given back",
                   code == 1 ? done.c_str() : what[code >= 0 && code <= 8 ? code : 4]);
}
static void m10_amm_layout_text(const char* when, uint64_t w, uint64_t wn, const char* from, int mode, const M10Layout& L, double ms, bool sysfs, const int64_t (&before)[2],
                                const int64_t (&after)[2], uint64_t events, char* out, size_t cap) {
    char nul[320];
    nul[0] = 0;
    if (mode != 0)
        std::snprintf(nul, sizeof(nul), "; %s null pages under %zu of %u reservations (%.1f MiB), %u failed, %u with no map_null_window in this backend, %u refused as the whole window, %u under 64 KiB once aligned",
                      mode == 2 ? "writable" : "read-only", L.nulls.size(), L.asked, static_cast<double>(L.null_bytes) / 1048576.0, L.null_failed, L.null_absent, L.whole,
                      L.small);
    char mem[200];
    mem[0] = 0;
    if (sysfs)
        std::snprintf(mem, sizeof(mem), "; vram used %" PRId64 " -> %" PRId64 ", gtt used %" PRId64 " -> %" PRId64 " bytes (-1: not read)", before[0], after[0], before[1],
                      after[1]);
    char ev[80];
    ev[0] = 0;
    if (events != 0) std::snprintf(ev, sizeof(ev), "; %" PRIu64 " reservation events before it", events);
    std::snprintf(out, cap, "amm window (exp 0401 e10 m10): %s: window 0x%" PRIx64 "+0x%" PRIx64 " (%s): PRT: map_prt_window %s%s, %.3f ms%s%s\n", when, w, wn, from,
                  L.prt_ok ? "ok" : "FAILED", nul, ms, mem, ev);
}
// -- the three new backend methods (tag nbo), found at compile time: without them the old call, journaled
template <class D>
static constexpr bool m10_has_null_window() {
    return requires(D& x, std::uint64_t a, std::uint64_t n, bool w) { static_cast<bool>(x.map_null_window(a, n, w)); };
}
template <class D>
static constexpr bool m10_has_rights() {
    return requires(D& x, std::uint32_t i, std::uint64_t a, unsigned r) { static_cast<bool>(x.map_shared_rights(i, a, a, a, r)); };
}
template <class D>
static constexpr bool m10_has_null_range() {
    return requires(D& x, std::uint64_t a, bool w) {
        static_cast<bool>(x.map_null_range(a, a, w));
        static_cast<bool>(x.unmap_null_range(a));
    };
}
template <class D>
static int m10_null_call(D* d, uint64_t va, uint64_t size, bool writable) { // 1 mapped, 0 failed, -1 no such method in this backend
    if constexpr (m10_has_null_window<D>()) {
        return d->map_null_window(va, size, writable) ? 1 : 0;
    } else {
        (void)d;
        (void)va;
        (void)size;
        (void)writable;
        return -1;
    }
}
template <class D>
static int m10_rights_call(D* d, uint32_t id, uint64_t off, uint64_t size, uint64_t va, unsigned rights) {
    if constexpr (m10_has_rights<D>()) {
        return d->map_shared_rights(id, off, size, va, rights) ? 1 : 0;
    } else {
        (void)d;
        (void)id;
        (void)off;
        (void)size;
        (void)va;
        (void)rights;
        return -1;
    }
}
template <class D>
static int m10_nullrange_call(D* d, uint64_t va, uint64_t size, bool writable) {
    if constexpr (m10_has_null_range<D>()) {
        return d->map_null_range(va, size, writable) ? 1 : 0;
    } else {
        (void)d;
        (void)va;
        (void)size;
        (void)writable;
        return -1;
    }
}
template <class D>
static int m10_unnullrange_call(D* d, uint64_t va) {
    if constexpr (m10_has_null_range<D>()) {
        return d->unmap_null_range(va) ? 1 : 0;
    } else {
        (void)d;
        (void)va;
        return -1;
    }
}
// ---- exp 0401 e10 (tag m10): the host's side ----------------------------------------------------------------------------------
struct M10Read {
    int  mode = 0;
    char line[640] = {};
};
static M10Read m10_read_one(int which) {
    const char* e = std::getenv(kM10Names[which]);
    M10Read     r;
    r.mode = which == 2 || which == 5 ? m10_null_parse(e) : m10_parse(e) ? 1 : 0;
    m10_switch_text(which, r.mode, e, r.line, sizeof(r.line));
    std::fprintf(stderr, "[bc5] %s", r.line);
    return r;
}
static const M10Read& m10_census_read() { // BC5_DIRECT_PROT_CENSUS, read once (Bc5ProtCensus may read it first: stderr only there)
    static const M10Read r = m10_read_one(0);
    return r;
}
static const M10Read& m10_dontneed_read() { // BC5_DIRECT_JOURNAL_DONTNEED (the journal's write path may read it first: stderr only there)
    static const M10Read r = m10_read_one(1);
    return r;
}
static const M10Read& m10_null_read() { // BC5_DIRECT_AMM_NULL_BO
    static const M10Read r = m10_read_one(2);
    return r;
}
static const M10Read& m10_rights_read() { // BC5_DIRECT_GPU_RIGHTS
    static const M10Read r = m10_read_one(3);
    return r;
}
static const M10Read& m10_fix_read() { // BC5_DIRECT_AMM_WINDOW_FIX
    static const M10Read r = m10_read_one(4);
    return r;
}
static const M10Read& m10_holes_read() { // BC5_DIRECT_HOLES_NULL_BO
    static const M10Read r = m10_read_one(5);
    return r;
}
static std::mutex               g_m10_mutex;            // the capture, the held lines, the census's schedule, the once-only lines
static bool                     g_m10_capture = false;  // the CPU test's copy of every line (bc5_m10_capture); never set by the emulator
static std::vector<std::string> g_m10_captured;
static std::vector<std::string> g_m10_held;             // the AMM window's lines at the device's open, before dump_init
static bool                     g_m10_amm_told = false; // the two AMM switch lines are out
static void m10_line(const char* s) { // one journal line (s ends with a newline); never with an m10 lock held
    {
        std::lock_guard lk(g_m10_mutex);
        if (g_m10_capture) g_m10_captured.emplace_back(s);
    }
    journal("%s", s);
}
static void m10_line_or_hold(const char* s, bool hold) { // hold: at the device's open the journal may have no directory yet
    if (!hold || !g_dump_dir.empty()) {
        m10_line(s);
        return;
    }
    std::lock_guard lk(g_m10_mutex);
    if (g_m10_capture) g_m10_captured.emplace_back(s);
    if (g_m10_held.size() < 16) g_m10_held.emplace_back(s);
}
static void m10_amm_pending() {
    std::vector<std::string> v;
    {
        std::lock_guard lk(g_m10_mutex);
        v.swap(g_m10_held);
    }
    for (const auto& s: v) journal("%s", s.c_str());
}
static bool m10_once(bool& flag) { // true the first time (under g_m10_mutex)
    std::lock_guard lk(g_m10_mutex);
    const bool first = !flag;
    flag             = true;
    return first;
}
// -- BC5_DIRECT_JOURNAL_DONTNEED
static std::mutex g_m10_drop_mutex; // g_m10_drop and the count's last line
static M10Drop    g_m10_drop;
static uint64_t   g_m10_told_syncs = 0, g_m10_told_errs = 0;
// One step on a journal file (exp 0330's journal_drop; fstat for its size instead of lseek(SEEK_END), so the stream's offset is
// not touched). True when it started a writeback.
static bool m10_drop_fd(M10Drop& st, int fd) {
    struct stat sb {};
    if (fd < 0 || fstat(fd, &sb) != 0 || sb.st_size < 0) return false;
    const M10DropPlan p = m10_drop_plan(st, static_cast<uint64_t>(sb.st_size));
    if (!p.act) return false;
    if (p.drop_len != 0) {
        st.drop_rc  = posix_fadvise(fd, static_cast<off_t>(p.drop_lo), static_cast<off_t>(p.drop_len), POSIX_FADV_DONTNEED);
        st.drop_lo  = p.drop_lo;
        st.drop_len = p.drop_len;
        st.drops++;
        if (st.drop_rc != 0) st.drop_err++;
        st.dropped = st.started;
    }
    st.sync_rc  = sync_file_range(fd, static_cast<off_t>(p.sync_lo), static_cast<off_t>(p.sync_len), SYNC_FILE_RANGE_WRITE);
    st.sync_lo  = p.sync_lo;
    st.sync_len = p.sync_len;
    st.syncs++;
    if (st.sync_rc != 0) st.sync_err++;
    st.started = p.sync_lo + p.sync_len;
    return true;
}
// The journal's write paths, after their flush. It runs inside the journal's own write path, so it never journals.
static void m10_journal_drop(FILE* f) {
    if (f == nullptr || m10_dontneed_read().mode == 0) return;
    std::lock_guard lk(g_m10_drop_mutex);
    (void)m10_drop_fd(g_m10_drop, fileno(f));
}
static void m10_drop_report(double t) { // the 10-s tick: the count, every 64 writebacks and at a new failure
    if (m10_dontneed_read().mode == 0) return;
    char line[480];
    {
        std::lock_guard lk(g_m10_drop_mutex);
        const M10Drop& s    = g_m10_drop;
        const uint64_t errs = s.sync_err + s.drop_err;
        if (!m10_drop_tell(g_m10_told_syncs, g_m10_told_errs, s.syncs, errs)) return;
        g_m10_told_syncs = s.syncs;
        g_m10_told_errs  = errs;
        m10_drop_text(s, t, line, sizeof(line));
    }
    m10_line(line);
}
// -- BC5_DIRECT_PROT_CENSUS at the calls
static std::mutex            g_m10_pc_mutex; // the calls held: one copy under it, nothing else
static std::vector<M10Call>  g_m10_pc;
static uint64_t              g_m10_pc_lost = 0;
static std::atomic<bool>     g_m10_pc_hold {false}; // the CPU test writes the calls itself (bc5_m10_pc_hold)
static std::mutex            g_m10_win_mutex;       // the window being counted
static M10Window             g_m10_win;
static int m10_names(const char* n) { // the mapper's reading of a name (BC5_DIRECT_EAGER_NAMES, BC5_DIRECT_LAZY_NAMES)
    return (direct_eager_name(n) ? 1 : 0) | (direct_lazy_name(n) ? 2 : 0);
}
static void m10_pc_drain(double now) { // the census's thread, each second: the calls held into lines and the window's counts
    std::vector<M10Call> v;
    uint64_t             lost = 0;
    {
        std::lock_guard lk(g_m10_pc_mutex);
        v.swap(g_m10_pc);
        lost          = g_m10_pc_lost;
        g_m10_pc_lost = 0;
    }
    std::vector<std::string> out;
    {
        std::lock_guard lk(g_m10_win_mutex);
        for (const auto& c: v) m10_win_add(g_m10_win, c, m10_names, out);
        if (lost != 0) {
            if (!g_m10_win.open) {
                g_m10_win.open = true;
                g_m10_win.lo   = now;
            }
            g_m10_win.lost += lost;
        }
        if (g_m10_win.open && now - g_m10_win.lo >= 10.0) m10_win_close(g_m10_win, out);
    }
    for (const auto& l: out) m10_line(l.c_str());
}
// CONTRACT 1: memory.cpp (k10) and libAmpr.cpp (p10) call it at each map (1), mprotect (2), mtypeprotect (3), AMM map (4), AMM
// remap or protect (5) and unmap (6), with the protection as the title passed it. Off: returns at once. On: one copy into the
// list under its own short lock; no journal, no memory.cpp or mapper lock, nothing called back; any thread.
extern "C" void Bc5ProtCensus(int call, uint64_t va, uint64_t size, uint64_t phys, int prot, int type, const char* name) {
    if (m10_census_read().mode == 0) return;
    M10Call c;
    c.call = call;
    c.va   = va;
    c.size = size;
    c.phys = phys;
    c.prot = prot;
    c.type = type;
    c.t_ns = SoftCp::now_ns();
    for (size_t k = 0; name != nullptr && k + 1 < sizeof(c.name) && name[k] != 0; k++) c.name[k] = name[k];
    std::lock_guard lk(g_m10_pc_mutex);
    if (g_m10_pc.size() >= kM10Ring) {
        g_m10_pc_lost++;
        return;
    }
    g_m10_pc.push_back(c);
}
// -- BC5_DIRECT_PROT_CENSUS on the memory line's thread: the totals and the forced chunks
struct M10Snap {
    std::vector<M10Bo>    bos[2];
    std::vector<uint64_t> forced[2];
    uint64_t              bytes[2] = {0, 0};
    double                hold_ms  = 0.0;
};
static std::atomic<uint64_t> g_m10_rights_maps {0}; // views mapped R|X (BC5_DIRECT_GPU_RIGHTS)
// The mapper's state, copied under g_dev_mutex (submit_now, recover_after_timeout and the device's open change it under that
// lock), taken with try_lock: false when it is busy, and the census waits for the next tick instead of the memory line.
static bool m10_snapshot(M10Snap& s) {
    std::unique_lock lk(g_dev_mutex, std::try_to_lock);
    if (!lk.owns_lock()) return false;
    const uint64_t t1 = SoftCp::now_ns();
    for (int k = 0; k < 2; k++) {
        const DState& S = g_d[k];
        s.bos[k].clear();
        s.bos[k].reserve(S.bos.size());
        for (const auto& b: S.bos) s.bos[k].push_back(M10Bo {b.off, b.size});
        s.forced[k].assign(S.forced.begin(), S.forced.end());
        s.bytes[k] = S.bytes;
    }
    s.hold_ms = static_cast<double>(SoftCp::now_ns() - t1) / 1e6;
    return true;
}
static bool m10_has_data(int fd, uint64_t c) { // one SEEK_DATA: the memfd holds data in [c, c + kDChunk)
    const off_t d = lseek(fd, static_cast<off_t>(c), SEEK_DATA);
    return d >= 0 && static_cast<uint64_t>(d) < c + kDChunk;
}
static M10Forced m10_forced_of(int k, const M10Snap& s) { // off the device lock: the views (direct_views), one SEEK_DATA per chunk no eager view covers
    M10Forced f;
    if (s.forced[k].empty()) return f;
    const int fd = dstate_fd(g_d[k]);
    if (fd < 0) {
        f.classified = false;
        f.total      = s.forced[k].size();
        return f;
    }
    const auto                                 views_p = direct_views(g_d[k]);
    std::vector<std::pair<uint64_t, uint64_t>> eager;
    for (const auto& v: views_p->v)
        if (v.eager) eager.emplace_back(v.off, v.off + v.size);
    const uint64_t f0 = SoftCp::now_ns();
    f                 = m10_forced(s.forced[k], m10_merge(std::move(eager)), s.bos[k], [fd](uint64_t c) { return m10_has_data(fd, c); });
    f.ms              = static_cast<double>(SoftCp::now_ns() - f0) / 1e6;
    return f;
}
static double   g_m10_next  = 120.0; // the next census's journal time (g_m10_mutex)
static uint32_t g_m10_count = 0;     // censuses written (g_m10_mutex)
static uint32_t g_m10_busy  = 0;     // ticks the device lock was busy at, since the last census (g_m10_mutex)
static void m10_census_tick(double t) { // the memory line's thread (mem_line_loop), never the game thread
    if (m10_census_read().mode == 0) return;
    {
        std::lock_guard lk(g_m10_mutex);
        if (!m10_census_due(g_m10_next, t)) return;
    }
    M10Snap s;
    if (!m10_snapshot(s)) {
        std::lock_guard lk(g_m10_mutex);
        g_m10_busy++;
        return;
    }
    M10Head h;
    {
        std::lock_guard lk(g_m10_mutex);
        g_m10_next = m10_census_next(t);
        h.no       = ++g_m10_count;
        h.busy     = g_m10_busy;
        g_m10_busy = 0;
    }
    std::vector<M10Range> ranges;
    Libs::LibKernel::Memory::Bc5ForEachMappedRange(nullptr, &ranges, [](uint64_t start, uint64_t size, uint64_t offset, int type, int prot, const char*, void* p) {
        M10Range r;
        r.start  = start;
        r.size   = size;
        r.offset = offset;
        r.type   = type;
        r.prot   = prot;
        static_cast<std::vector<M10Range>*>(p)->push_back(r);
    });
    M10Total tot[4];
    m10_totals(ranges, s.bos, tot);
    const M10Forced fc[2] = {m10_forced_of(0, s), m10_forced_of(1, s)};
    h.ranges              = ranges.size();
    for (int k = 0; k < 2; k++) {
        h.bos[k]   = s.bos[k].size();
        h.bytes[k] = s.bytes[k];
    }
    h.hold_ms = s.hold_ms;
    h.rights  = g_m10_rights_maps.load();
    std::vector<std::string> lines;
    m10_census_lines(tot, h, fc, t, lines);
    for (const auto& l: lines) m10_line(l.c_str());
}
static void m10_tick(double t) { // the memory line's 10-s tick
    m10_drop_report(t);
    m10_census_tick(t);
}
static void m10_loop(bool mem_line) { // the census's thread: the calls each second; without the memory line, the dontneed count every 10 s
    for (uint64_t k = 1;; k++) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        if (m10_census_read().mode != 0 && !g_m10_pc_hold.load()) m10_pc_drain(static_cast<double>(SoftCp::now_ns()) / 1e9);
        if (!mem_line && k % 10 == 0) m10_drop_report(timing_now());
    }
}
static void m10_start(bool mem_line) { // mem_line_start, once (the first submission): four switch lines, the thread
    const M10Read& c = m10_census_read();
    const M10Read& d = m10_dontneed_read();
    m10_line(c.line);
    m10_line(d.line);
    m10_line(m10_rights_read().line);
    m10_line(m10_holes_read().line);
    if (c.mode != 0 || (d.mode != 0 && !mem_line)) std::thread(m10_loop, mem_line).detach();
}
// -- the device's calls, as the host makes them (the CPU test has a recording one of its own)
static void m10_reserved_cb(uint64_t va, uint64_t size, void* ctx) {
    static_cast<std::vector<std::pair<uint64_t, uint64_t>>*>(ctx)->emplace_back(va, va + size);
}
static int64_t m10_sysfs(const char* leaf) { // the render node's device (kRenderNode, as direct_gtt finds it); -1 when it cannot be read
    const std::string n    = kRenderNode;
    const size_t      cut  = n.rfind('/');
    const std::string path = "/sys/class/drm/" + (cut == std::string::npos ? n : n.substr(cut + 1)) + "/device/" + leaf;
    long long         v    = -1;
    if (FILE* f = std::fopen(path.c_str(), "r")) {
        if (std::fscanf(f, "%lld", &v) != 1) v = -1;
        std::fclose(f);
    }
    return static_cast<int64_t>(v);
}
struct M10Dev { // g_dev is open and the caller holds g_dev_mutex
    bool prt(uint64_t va, uint64_t n) { return g_dev->map_prt_window(va, n); }
    int  null(uint64_t va, uint64_t n, bool w) { return m10_null_call(g_dev.get(), va, n, w); }
    int  window(uint64_t* va, uint64_t* n) { // 1 the window, 0 not reserved yet, -1 no Bc5AmmWindow in this build
        if (&Bc5AmmWindow == nullptr) return -1;
        return Bc5AmmWindow(va, n) != 0 ? 1 : 0;
    }
    void reserved(std::vector<std::pair<uint64_t, uint64_t>>& out) {
        if (&Bc5AmmForEachReserved != nullptr) Bc5AmmForEachReserved(m10_reserved_cb, &out);
    }
    int64_t  sysfs(const char* leaf) { return m10_sysfs(leaf); }
    bool     shared(uint32_t id, uint64_t off, uint64_t n, uint64_t va) { return g_dev->map_shared(id, off, n, va); }
    int      rights(uint32_t id, uint64_t off, uint64_t n, uint64_t va, unsigned r) { return m10_rights_call(g_dev.get(), id, off, n, va, r); }
    int      null_range(uint64_t va, uint64_t n, bool w) { return m10_nullrange_call(g_dev.get(), va, n, w); }
    int      unmap_null_range(uint64_t va) { return m10_unnullrange_call(g_dev.get(), va); }
    void     unmap_shared(uint64_t va) { g_dev->unmap_shared(va); }
    uint32_t scratch() { return scratch_bo(); }
};
// -- BC5_DIRECT_GPU_RIGHTS
static bool m10_rights_told_ok = false, m10_rights_told_absent = false;
static unsigned m10_view_rights(int prot) {
    return m10_rights_read().mode != 0 ? m10_rights_of(prot) : 0u;
}
template <class Dev>
static bool m10_map_view_with(Dev& d, uint32_t id, uint64_t off, uint64_t n, uint64_t va, unsigned rights) {
    if (rights == 0) return d.shared(id, off, n, va); // e9's call
    const int r = d.rights(id, off, n, va, rights);
    if (r >= 0) {
        if (r == 1) g_m10_rights_maps++;
        if (m10_once(m10_rights_told_ok))
            m10_line(m10_fmt("gpu rights (exp 0401 e10 m10): the first view mapped with rights 0x%x (R|X): va 0x%" PRIx64 " size 0x%" PRIx64 " BO %u: %s\n", rights, va, n, id,
                             r == 1 ? "ok" : "FAILED")
                         .c_str());
        return r == 1;
    }
    if (m10_once(m10_rights_told_absent)) m10_line("gpu rights (exp 0401 e10 m10): map_shared_rights is not in this backend: every view R|W|X, as e9\n");
    return d.shared(id, off, n, va);
}
static bool m10_map_view(uint32_t id, uint64_t bo_off, uint64_t size, uint64_t va, unsigned rights) {
    M10Dev d;
    return m10_map_view_with(d, id, bo_off, size, va, rights);
}
// -- BC5_DIRECT_HOLES_NULL_BO. Device::map_alias covers userptr and shared mappings only, not null ranges, so where the scratch
// BO's pieces got their exp 0056 aliases (BC5_DIRECT_ALIASES: (byte << 40) + address, aliases_apply), each null piece gets null
// ranges at its alias addresses too, else an alias read of a hole would fault where it reads zeros today.
using M10AliasWin = std::tuple<uint64_t, uint64_t, uint64_t>; // byte, lo, size (g_aliases)
struct M10Hole {
    uint64_t              size = 0;
    std::vector<uint64_t> aliases; // the alias null ranges' addresses, as passed to map_null_range
};
static std::map<uint64_t, M10Hole> g_m10_holes; // the pieces map_null_range put in (g_dev_mutex: learned_apply and the rebuild run under it)
static bool                        m10_holes_told_ok = false, m10_holes_told_fail = false;
static uint64_t                    g_m10_hole_fallbacks = 0, g_m10_hole_alias_failed = 0;
static uint64_t m10_alias_va(uint64_t byte, uint64_t va) { // map_alias's address: sign-extended from 2^47 up (the kernel's VA hole; direct.cpp map_alias)
    uint64_t to = (byte << 40u) + va;
    if (to >= (1ull << 47u)) to |= 0xffff000000000000ull;
    return to;
}
// The alias null ranges a piece [va, va + n) needs: (alias address, size) for each alias window over it.
static std::vector<std::pair<uint64_t, uint64_t>> m10_hole_aliases(uint64_t va, uint64_t n, const std::vector<M10AliasWin>& wins) {
    std::vector<std::pair<uint64_t, uint64_t>> out;
    for (const auto& [t, a, an]: wins) {
        const uint64_t lo = std::max(va, a), hi = std::min(va + n, a + an);
        if (lo < hi) out.emplace_back(m10_alias_va(t, lo), hi - lo);
    }
    return out;
}
template <class Dev>
static void m10_hole_alias_add(Dev& d, uint64_t va, M10Hole& h, const std::vector<M10AliasWin>& wins, bool writable) {
    for (const auto& [av, an]: m10_hole_aliases(va, h.size, wins)) {
        if (std::find(h.aliases.begin(), h.aliases.end(), av) != h.aliases.end()) continue;
        if (d.null_range(av, an, writable) == 1) h.aliases.push_back(av);
        else g_m10_hole_alias_failed++;
    }
}
template <class Dev>
static int m10_hole_map_with(Dev& d, uint64_t va, uint64_t n, const std::vector<M10AliasWin>& wins) { // 1 mapped, 0 refused, -1 no scratch BO (e9's break)
    const int mode = m10_holes_read().mode;
    if (mode != 0) {
        const int r = d.null_range(va, n, mode == 2);
        if (r == 1) {
            M10Hole& h = g_m10_holes[va];
            h          = M10Hole {};
            h.size     = n;
            m10_hole_alias_add(d, va, h, wins, mode == 2);
            if (m10_once(m10_holes_told_ok))
                m10_line(m10_fmt("holes null bo (exp 0401 e10 m10): the first null range: 0x%" PRIx64 "+0x%" PRIx64 " (%s), %zu alias null ranges\n", va, n,
                                 mode == 2 ? "writable" : "read-only", h.aliases.size())
                             .c_str());
            return 1;
        }
        g_m10_hole_fallbacks++;
        if (m10_once(m10_holes_told_fail))
            m10_line(m10_fmt("holes null bo (exp 0401 e10 m10): map_null_range 0x%" PRIx64 "+0x%" PRIx64 " %s: the scratch BO there, as e9 (later ones are counted)\n", va, n,
                             r < 0 ? "is not in this backend" : "refused it")
                         .c_str());
    }
    const uint32_t id = d.scratch(); // e9's path
    if (id == 0) return -1;
    return d.shared(id, 0, n, va) ? 1 : 0;
}
template <class Dev>
static void m10_hole_unmap_with(Dev& d, uint64_t va) { // scratch_release: before the direct mapper maps there (its unmap-before-map path)
    const auto it = g_m10_holes.find(va);
    if (it == g_m10_holes.end()) {
        d.unmap_shared(va); // e9's call
        return;
    }
    for (const uint64_t av: it->second.aliases) (void)d.unmap_null_range(av);
    (void)d.unmap_null_range(va);
    g_m10_holes.erase(it);
}
template <class Dev>
static void m10_holes_alias_sync_with(Dev& d, const std::vector<M10AliasWin>& wins) { // an alias window learned after a hole was filled
    const int mode = m10_holes_read().mode;
    if (mode == 0) return;
    for (auto& kv: g_m10_holes) m10_hole_alias_add(d, kv.first, kv.second, wins, mode == 2);
}
static std::vector<M10AliasWin> m10_alias_windows() { // g_aliases (BC5_DIRECT_ALIASES), copied under g_alias_mutex
    std::vector<M10AliasWin> v;
    if (!aliases_on()) return v;
    std::lock_guard lk(g_alias_mutex);
    aliases_load();
    v = g_aliases;
    return v;
}
static int m10_hole_map(uint64_t va, uint64_t size) {
    M10Dev d;
    if (m10_holes_read().mode == 0) return m10_hole_map_with(d, va, size, std::vector<M10AliasWin>()); // e9's path; no alias lock
    return m10_hole_map_with(d, va, size, m10_alias_windows());
}
static void m10_hole_unmap(uint64_t va) {
    M10Dev d;
    m10_hole_unmap_with(d, va);
}
static void m10_holes_alias_sync(const std::vector<std::tuple<uint64_t, uint64_t, uint64_t>>& wins) { // aliases_apply holds g_alias_mutex
    M10Dev d;
    m10_holes_alias_sync_with(d, wins);
}
static void m10_holes_reset() {
    g_m10_holes.clear();
}
// -- BC5_DIRECT_AMM_WINDOW_FIX and AMM_NULL_BO
struct M10Res {
    uint64_t va = 0, size = 0;
    int      on = 0;
};
struct M10Amm { // g_dev_mutex: the device's open and reopen, direct_sync
    bool                                       laid = false, pending = false;
    uint64_t                                   w = 0, wn = 0, last_try_ns = 0;
    std::vector<std::pair<uint64_t, uint64_t>> nulls;
    uint32_t                                   event_lines = 0;
    bool                                       told_wait   = false;
};
static M10Amm              g_m10_amm;
static std::mutex          g_m10_amm_mutex; // Bc5AmmReserved's queue only
static std::vector<M10Res> g_m10_amm_queue;
static uint64_t            g_m10_amm_overflow = 0;
static std::atomic<bool>   g_m10_amm_queued {false};
// CONTRACT 2: libAmpr.cpp (p10) calls it when the title reserves a range inside the AMM window (on 1) or gives one back (on 0).
// It only queues (its own short lock): direct_sync applies the queue under g_dev_mutex at the next submission.
extern "C" void Bc5AmmReserved(uint64_t va, uint64_t size, int on) {
    if (m10_null_read().mode == 0 && m10_fix_read().mode == 0) return;
    std::lock_guard lk(g_m10_amm_mutex);
    if (g_m10_amm_queue.size() >= 4096) {
        g_m10_amm_overflow++;
    } else {
        M10Res r;
        r.va   = va;
        r.size = size;
        r.on   = on;
        g_m10_amm_queue.push_back(r);
    }
    g_m10_amm_queued = true;
}
static uint64_t m10_amm_take(std::vector<M10Res>* out) { // the queue (and its overflow) taken; returns the events
    std::lock_guard lk(g_m10_amm_mutex);
    const uint64_t  n = g_m10_amm_queue.size() + g_m10_amm_overflow;
    if (out != nullptr) out->swap(g_m10_amm_queue);
    g_m10_amm_queue.clear();
    g_m10_amm_overflow = 0;
    g_m10_amm_queued   = false;
    return n;
}
// The window's layout now, if it can be: the window (BC5_DIRECT_AMM_WINDOW_FIX: Bc5AmmWindow's) and, with NULL_BO, at least one
// reservation; otherwise it waits (pending) and one line says why.
template <class Dev>
static void m10_amm_try(Dev& d, const char* when, bool hold, uint64_t events) {
    const int   nb   = m10_null_read().mode;
    uint64_t    w    = kM10AmmVa, wn = kM10AmmSize;
    const char* from = "as e9";
    g_m10_amm.last_try_ns = SoftCp::now_ns();
    if (m10_fix_read().mode != 0) {
        const int k = d.window(&w, &wn);
        if (k == 1) {
            const uint64_t a = m10_up(w), b = m10_down(w + wn);
            w    = a;
            wn   = b > a ? b - a : 0;
            from = "from Bc5AmmWindow";
        }
        if (k != 1 || wn == 0) {
            g_m10_amm.pending = true;
            if (m10_once(g_m10_amm.told_wait))
                m10_line_or_hold(m10_fmt("amm window (exp 0401 e10 m10): %s: the AMM window is %s: its PRT window waits for it (BC5_DIRECT_AMM_WINDOW_FIX)\n", when,
                                         k < 0 ? "not in this build (no Bc5AmmWindow)" : k == 0 ? "not reserved yet" : "under 64 KiB once aligned")
                                     .c_str(),
                                 hold);
            return;
        }
    }
    std::vector<std::pair<uint64_t, uint64_t>> res;
    if (nb != 0) {
        d.reserved(res);
        res.erase(std::remove_if(res.begin(), res.end(), [w, wn](const std::pair<uint64_t, uint64_t>& r) { return r.second <= w || r.first >= w + wn; }), res.end());
        if (res.empty()) {
            g_m10_amm.pending = true;
            if (m10_once(g_m10_amm.told_wait))
                m10_line_or_hold(m10_fmt("amm window (exp 0401 e10 m10): %s: window 0x%" PRIx64 "+0x%" PRIx64 " (%s): no reservation of the title's in it yet: its PRT and null "
                                         "pages wait for the first one (BC5_DIRECT_AMM_NULL_BO)\n",
                                         when, w, wn, from)
                                     .c_str(),
                                 hold);
            return;
        }
    }
    const bool rd        = nb != 0 || m10_census_read().mode != 0;
    int64_t    before[2] = {-1, -1}, after[2] = {-1, -1};
    if (rd) {
        before[0] = d.sysfs("mem_info_vram_used");
        before[1] = d.sysfs("mem_info_gtt_used");
    }
    const uint64_t  t0 = SoftCp::now_ns();
    const M10Layout L  = m10_amm_layout(
        w, wn, res, nb, [&d](uint64_t a, uint64_t n, bool wr) { return d.null(a, n, wr); }, [&d](uint64_t a, uint64_t n) { return d.prt(a, n); });
    const double ms = static_cast<double>(SoftCp::now_ns() - t0) / 1e6;
    if (rd) {
        after[0] = d.sysfs("mem_info_vram_used");
        after[1] = d.sysfs("mem_info_gtt_used");
    }
    g_m10_amm.laid    = true;
    g_m10_amm.pending = false;
    g_m10_amm.w       = w;
    g_m10_amm.wn      = wn;
    g_m10_amm.nulls   = L.nulls;
    char line[1000];
    m10_amm_layout_text(when, w, wn, from, nb, L, ms, rd, before, after, events, line, sizeof(line));
    std::fprintf(stderr, "[bc5] %s", line);
    m10_line_or_hold(line, hold);
}
// The device's open (hold: the journal may have no directory yet) and reopen, where e9 maps its PRT window.
template <class Dev>
static void m10_amm_window_with(Dev& d, const char* when, bool hold) {
    if (m10_once(g_m10_amm_told)) {
        m10_line_or_hold(m10_null_read().line, hold);
        m10_line_or_hold(m10_fix_read().line, hold);
    }
    g_m10_amm                = M10Amm {}; // a new device: nothing of the old one's window is mapped
    const uint64_t events    = m10_amm_take(nullptr); // the open reads the reservations itself
    if (std::getenv("BC5_DIRECT_AMM_PRT") == nullptr) return; // e9: no AMM window
    m10_amm_try(d, when, hold, events);
}
static void m10_amm_window(const char* when, bool hold) {
    M10Dev d;
    m10_amm_window_with(d, when, hold);
}
// direct_sync, under g_dev_mutex: Bc5AmmReserved's events, and a window that waits (at most one try a second without an event).
template <class Dev>
static void m10_amm_apply_with(Dev& d) {
    const bool queued = g_m10_amm_queued.load();
    if (!queued && !(g_m10_amm.pending && SoftCp::now_ns() - g_m10_amm.last_try_ns >= 1'000'000'000ull)) return;
    std::vector<M10Res> ev;
    const uint64_t      n = m10_amm_take(&ev);
    if (std::getenv("BC5_DIRECT_AMM_PRT") == nullptr) return;
    if (!g_m10_amm.laid) {
        if (g_m10_amm.pending) m10_amm_try(d, "later", false, n);
        return;
    }
    const int nb = m10_null_read().mode;
    if (nb == 0) return; // the window is laid; without NULL_BO an event changes nothing
    for (const auto& e: ev) {
        const int code = m10_amm_event(g_m10_amm.nulls, g_m10_amm.w, g_m10_amm.wn, e.va, e.size, e.on, nb, [&d](uint64_t a, uint64_t s, bool wr) { return d.null(a, s, wr); });
        if (g_m10_amm.event_lines < kM10EventLines) {
            g_m10_amm.event_lines++;
            m10_line(m10_amm_event_text(e.va, e.size, e.on, code, nb).c_str());
        }
    }
}
static void m10_amm_apply() {
    if (!g_dev) return;
    M10Dev d;
    m10_amm_apply_with(d);
}
// ---- exp 0401 e10 (tag m10): the CPU test's seams (m100401.cpp); always compiled in, never called by the emulator ------------------
extern "C" int bc5_m10_parse(const char* e) {
    return m10_parse(e) ? 1 : 0;
}
extern "C" int bc5_m10_null_parse(const char* e) {
    return m10_null_parse(e);
}
extern "C" void bc5_m10_switches(int* out) { // the unit's reading: census, dontneed, null bo, rights, window fix, holes
    out[0] = m10_census_read().mode;
    out[1] = m10_dontneed_read().mode;
    out[2] = m10_null_read().mode;
    out[3] = m10_rights_read().mode;
    out[4] = m10_fix_read().mode;
    out[5] = m10_holes_read().mode;
}
extern "C" void bc5_m10_switch_line(int which, int mode, const char* e, char* out, uint32_t cap) {
    m10_switch_text(which, mode, e, out, cap);
}
extern "C" void bc5_m10_consts(uint64_t* out) {
    out[0] = kM10DropStep;
    out[1] = kM10DropLine;
    out[2] = kM10CallLines;
    out[3] = kM10AmmVa;
    out[4] = kM10AmmSize;
    out[5] = kDChunk;
    out[6] = kM10AggLines;
    out[7] = kM10Ring;
    out[8] = kM10Align;
}
extern "C" void bc5_m10_capture(int on) {
    std::lock_guard lk(g_m10_mutex);
    g_m10_capture = on != 0;
}
// The captured lines from index from on, joined into out (NUL-ended, cut at cap - 1 bytes); returns how many there are in all.
extern "C" uint64_t bc5_m10_lines(uint64_t from, char* out, uint64_t cap) {
    std::lock_guard lk(g_m10_mutex);
    std::string     all;
    for (size_t k = static_cast<size_t>(from); k < g_m10_captured.size(); k++) all += g_m10_captured[k];
    const size_t c = cap != 0 ? std::min(all.size(), static_cast<size_t>(cap) - 1) : 0;
    if (cap != 0) {
        std::memcpy(out, all.data(), c);
        out[c] = 0;
    }
    return g_m10_captured.size();
}
static void m10_seam_out(const std::string& s, char* out, uint64_t cap) {
    if (cap == 0) return;
    const size_t c = std::min(s.size(), static_cast<size_t>(cap) - 1);
    std::memcpy(out, s.data(), c);
    out[c] = 0;
}
extern "C" double bc5_m10_next(double t) {
    return m10_census_next(t);
}
extern "C" int bc5_m10_due(double next, double t) {
    return m10_census_due(next, t) ? 1 : 0;
}
extern "C" void bc5_m10_start(int mem_line) { // mem_line_start's call (the test passes 1)
    m10_start(mem_line != 0);
}
extern "C" void bc5_m10_tick(double t) { // the memory line's tick
    m10_tick(t);
}
extern "C" void bc5_m10_census_state(uint64_t* out) { // censuses written, ticks the lock was busy at since, the next census's time (ms)
    std::lock_guard lk(g_m10_mutex);
    out[0] = g_m10_count;
    out[1] = g_m10_busy;
    out[2] = static_cast<uint64_t>(g_m10_next * 1000.0);
}
extern "C" void bc5_m10_dev_lock(int take) { // the device lock, as submit_now holds it
    if (take != 0) g_dev_mutex.lock();
    else g_dev_mutex.unlock();
}
static std::vector<M10Bo> m10_seam_bos(const uint64_t* off, const uint64_t* size, uint32_t n) {
    std::vector<M10Bo> v;
    for (uint32_t k = 0; k < n; k++) v.push_back(M10Bo {off[k], size[k]});
    return v;
}
extern "C" uint64_t bc5_m10_overlap(const uint64_t* off, const uint64_t* size, uint32_t n, uint64_t lo, uint64_t hi) {
    return m10_overlap(m10_seam_bos(off, size, n), lo, hi);
}
extern "C" int bc5_m10_class(int type, int eager, int lazy) {
    return m10_class(type, eager != 0, lazy != 0);
}
extern "C" int bc5_m10_gpu_class(int prot) {
    return m10_gpu_class(prot);
}
// One periodic census's lines from ranges and BOs of the test's own (census 1, nothing forced, no lock times). Returns the lines.
extern "C" uint64_t bc5_m10_census_lines(const uint64_t* start, const uint64_t* size, const uint64_t* offset, const int* type, const int* prot, uint32_t n,
                                         const uint64_t* bo_off0, const uint64_t* bo_size0, uint32_t nb0, const uint64_t* bo_off1, const uint64_t* bo_size1, uint32_t nb1,
                                         double t, char* out, uint64_t cap) {
    std::vector<M10Range> ranges;
    for (uint32_t k = 0; k < n; k++) {
        M10Range r;
        r.start  = start[k];
        r.size   = size[k];
        r.offset = offset[k];
        r.type   = type[k];
        r.prot   = prot[k];
        ranges.push_back(r);
    }
    const std::vector<M10Bo> bos[2] = {m10_seam_bos(bo_off0, bo_size0, nb0), m10_seam_bos(bo_off1, bo_size1, nb1)};
    M10Total                 tot[4];
    m10_totals(ranges, bos, tot);
    M10Head h;
    h.no     = 1;
    h.ranges = ranges.size();
    for (int k = 0; k < 2; k++) {
        h.bos[k] = bos[k].size();
        for (const auto& b: bos[k]) h.bytes[k] += b.size;
    }
    const M10Forced          fc[2];
    std::vector<std::string> lines;
    m10_census_lines(tot, h, fc, t, lines);
    std::string all;
    for (const auto& l: lines) all += l;
    m10_seam_out(all, out, cap);
    return lines.size();
}
// The forced chunks of a "state" of the test's own: its memfd (the real SEEK_DATA), its eager file ranges (merged here, as the
// census merges the views'), its BOs. out: total, eager, data, neither, neither imported, their bytes, SEEK_DATA calls; line:
// the census's line for it (label "direct", time 120 s).
extern "C" void bc5_m10_forced(int fd, const uint64_t* forced, uint32_t nf, const uint64_t* eager_lo, const uint64_t* eager_hi, uint32_t ne, const uint64_t* bo_off,
                               const uint64_t* bo_size, uint32_t nb, uint64_t* out, char* line, uint32_t cap) {
    std::vector<uint64_t> fv(forced, forced + nf);
    std::sort(fv.begin(), fv.end());
    std::vector<std::pair<uint64_t, uint64_t>> ev;
    for (uint32_t k = 0; k < ne; k++) ev.emplace_back(eager_lo[k], eager_hi[k]);
    M10Forced f = m10_forced(fv, m10_merge(std::move(ev)), m10_seam_bos(bo_off, bo_size, nb), [fd](uint64_t c) { return m10_has_data(fd, c); });
    out[0]      = f.total;
    out[1]      = f.eager;
    out[2]      = f.data;
    out[3]      = f.neither;
    out[4]      = f.neither_imported;
    out[5]      = f.neither_bytes;
    out[6]      = f.seeks;
    f.ms        = 0.0;
    m10_seam_out(m10_forced_line(f, "direct", 120.0), line, cap);
}
// The census at the calls: the test writes the calls itself (hold 1: the census's thread leaves them), at a time of its own.
extern "C" void bc5_m10_pc_hold(int on) {
    g_m10_pc_hold = on != 0;
}
extern "C" void bc5_m10_pc_drain(double now) {
    m10_pc_drain(now);
}
extern "C" void bc5_m10_pc_state(uint64_t* out) { // calls held, calls lost since the last write
    std::lock_guard lk(g_m10_pc_mutex);
    out[0] = g_m10_pc.size();
    out[1] = g_m10_pc_lost;
}
extern "C" void bc5_m10_call_line(int call, uint64_t va, uint64_t size, uint64_t phys, int prot, int type, const char* name, char* out, uint32_t cap) { // at mono 0
    M10Call c;
    c.call = call;
    c.va   = va;
    c.size = size;
    c.phys = phys;
    c.prot = prot;
    c.type = type;
    for (size_t k = 0; name != nullptr && k + 1 < sizeof(c.name) && name[k] != 0; k++) c.name[k] = name[k];
    const int nm = m10_names(c.name);
    m10_seam_out(m10_call_line(c, m10_class(type, (nm & 1) != 0, (nm & 2) != 0)), out, cap);
}
extern "C" void bc5_m10_drop_plan(uint64_t started, uint64_t dropped, uint64_t end, uint64_t* out) { // act, drop lo, drop len, sync lo, sync len
    M10Drop st;
    st.started          = started;
    st.dropped          = dropped;
    const M10DropPlan p = m10_drop_plan(st, end);
    out[0]              = p.act ? 1 : 0;
    out[1]              = p.drop_lo;
    out[2]              = p.drop_len;
    out[3]              = p.sync_lo;
    out[4]              = p.sync_len;
}
// The real step (m10_drop_fd, the syscalls) on a file of the test's own with a state of its own: st = started, dropped, syncs,
// drops, sync lo, sync len, drop lo, drop len, sync rc, drop rc (rc as int64). Returns 1 when it started a writeback.
static void m10_seam_state_out(const M10Drop& s, uint64_t* st) {
    st[0] = s.started;
    st[1] = s.dropped;
    st[2] = s.syncs;
    st[3] = s.drops;
    st[4] = s.sync_lo;
    st[5] = s.sync_len;
    st[6] = s.drop_lo;
    st[7] = s.drop_len;
    st[8] = static_cast<uint64_t>(static_cast<int64_t>(s.sync_rc));
    st[9] = static_cast<uint64_t>(static_cast<int64_t>(s.drop_rc));
}
extern "C" int bc5_m10_drop_step(int fd, uint64_t* st) {
    M10Drop s;
    s.started   = st[0];
    s.dropped   = st[1];
    s.syncs     = st[2];
    s.drops     = st[3];
    const int r = m10_drop_fd(s, fd) ? 1 : 0;
    m10_seam_state_out(s, st);
    return r;
}
extern "C" void bc5_m10_drop_state(uint64_t* st) { // the journal's own state (g_m10_drop), as bc5_m10_drop_step's st
    std::lock_guard lk(g_m10_drop_mutex);
    m10_seam_state_out(g_m10_drop, st);
}
extern "C" int bc5_m10_drop_tell(uint64_t told_syncs, uint64_t told_errs, uint64_t syncs, uint64_t errs) {
    return m10_drop_tell(told_syncs, told_errs, syncs, errs) ? 1 : 0;
}
extern "C" void bc5_m10_drop_line(uint64_t syncs, uint64_t drops, uint64_t started, uint64_t dropped, double t, char* out, uint32_t cap) {
    M10Drop s;
    s.syncs   = syncs;
    s.drops   = drops;
    s.started = started;
    s.dropped = dropped;
    m10_drop_text(s, t, out, cap);
}
// A device that records its calls, for the AMM window, the GPU rights and the holes (the CPU test never opens a device).
struct M10FakeDev {
    std::string                                log;
    int                                        null_rc = 1, win_rc = 1, rights_rc = 1, nullrange_rc = 1;
    bool                                       prt_ok = true, shared_ok = true;
    uint64_t                                   win_va = 0, win_size = 0;
    uint32_t                                   scratch_id = 7;
    std::vector<std::pair<uint64_t, uint64_t>> res;
    const int64_t*                             sysfs_v = nullptr;
    int                                        reads   = 0;
    void add(const std::string& s) {
        log += log.empty() ? "" : ",";
        log += s;
    }
    bool prt(uint64_t va, uint64_t n) {
        add(m10_fmt("prt 0x%" PRIx64 "+0x%" PRIx64, va, n));
        return prt_ok;
    }
    int null(uint64_t va, uint64_t n, bool w) {
        add(m10_fmt("null %s 0x%" PRIx64 "+0x%" PRIx64, w ? "rw" : "ro", va, n));
        return null_rc;
    }
    int window(uint64_t* va, uint64_t* n) {
        add("window");
        if (win_rc == 1) {
            *va = win_va;
            *n  = win_size;
        }
        return win_rc;
    }
    void reserved(std::vector<std::pair<uint64_t, uint64_t>>& out) {
        add("reserved");
        out.insert(out.end(), res.begin(), res.end());
    }
    int64_t sysfs(const char* leaf) {
        add(leaf);
        return sysfs_v != nullptr ? sysfs_v[(reads++) & 3] : -1;
    }
    bool shared(uint32_t id, uint64_t off, uint64_t n, uint64_t va) {
        add(m10_fmt("shared %u 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64, id, off, n, va));
        return shared_ok;
    }
    int rights(uint32_t id, uint64_t off, uint64_t n, uint64_t va, unsigned r) {
        add(m10_fmt("rights %u 0x%" PRIx64 " 0x%" PRIx64 " 0x%" PRIx64 " %u", id, off, n, va, r));
        return rights_rc;
    }
    int null_range(uint64_t va, uint64_t n, bool w) {
        add(m10_fmt("null_range %s 0x%" PRIx64 "+0x%" PRIx64, w ? "rw" : "ro", va, n));
        return nullrange_rc;
    }
    int unmap_null_range(uint64_t va) {
        add(m10_fmt("unmap_null_range 0x%" PRIx64, va));
        return 1;
    }
    void unmap_shared(uint64_t va) { add(m10_fmt("unmap_shared 0x%" PRIx64, va)); }
    uint32_t scratch() {
        add("scratch");
        return scratch_id;
    }
};
// The fake's set-up for the AMM seams: win (rc, va, size), the reservations [lo, hi), null_rc, prt_ok, the four sysfs values.
static void m10_seam_fake(M10FakeDev& d, int win_rc, uint64_t win_va, uint64_t win_size, const uint64_t* res_lo, const uint64_t* res_hi, uint32_t nres, int null_rc, int prt_ok,
                          const int64_t* sysfs) {
    d.win_rc   = win_rc;
    d.win_va   = win_va;
    d.win_size = win_size;
    for (uint32_t k = 0; k < nres; k++) d.res.emplace_back(res_lo[k], res_hi[k]);
    d.null_rc = null_rc;
    d.prt_ok  = prt_ok != 0;
    d.sysfs_v = sysfs;
}
// The real open/reopen path (m10_amm_window_with: the switch lines, BC5_DIRECT_AMM_PRT, the window, the reservations, the layout,
// the sysfs reads, the line, the hold) with the recording device. log: its calls in order.
extern "C" void bc5_m10_amm_window(const char* when, int hold, int win_rc, uint64_t win_va, uint64_t win_size, const uint64_t* res_lo, const uint64_t* res_hi, uint32_t nres,
                                   int null_rc, int prt_ok, const int64_t* sysfs, char* log, uint32_t cap) {
    M10FakeDev d;
    m10_seam_fake(d, win_rc, win_va, win_size, res_lo, res_hi, nres, null_rc, prt_ok, sysfs);
    m10_amm_window_with(d, when, hold != 0);
    m10_seam_out(d.log, log, cap);
}
// The real direct_sync step (m10_amm_apply_with) with the recording device; force: as if the last try were a second ago.
extern "C" void bc5_m10_amm_apply(int force, int win_rc, uint64_t win_va, uint64_t win_size, const uint64_t* res_lo, const uint64_t* res_hi, uint32_t nres, int null_rc, int prt_ok,
                                  const int64_t* sysfs, char* log, uint32_t cap) {
    M10FakeDev d;
    m10_seam_fake(d, win_rc, win_va, win_size, res_lo, res_hi, nres, null_rc, prt_ok, sysfs);
    if (force != 0) g_m10_amm.last_try_ns = SoftCp::now_ns() - 2'000'000'000ull;
    m10_amm_apply_with(d);
    m10_seam_out(d.log, log, cap);
}
// The window's state: laid, pending, w, wn, null ranges (count; then ranges[2k], ranges[2k + 1] up to cap pairs), queued events.
extern "C" void bc5_m10_amm_state(uint64_t* out, uint64_t* ranges, uint32_t cap) {
    out[0] = g_m10_amm.laid ? 1 : 0;
    out[1] = g_m10_amm.pending ? 1 : 0;
    out[2] = g_m10_amm.w;
    out[3] = g_m10_amm.wn;
    out[4] = g_m10_amm.nulls.size();
    for (size_t k = 0; k < g_m10_amm.nulls.size() && k < cap; k++) {
        ranges[2 * k]     = g_m10_amm.nulls[k].first;
        ranges[2 * k + 1] = g_m10_amm.nulls[k].second;
    }
    std::lock_guard lk(g_m10_amm_mutex);
    out[5] = g_m10_amm_queue.size();
}
// The pure layout and event with recorded results: null_rc for every map_null_window, prt_ok for map_prt_window.
extern "C" void bc5_m10_amm_layout(uint64_t w, uint64_t wn, const uint64_t* res_lo, const uint64_t* res_hi, uint32_t nres, int mode, int null_rc, int prt_ok, uint64_t* out,
                                   char* log, uint32_t cap) {
    M10FakeDev d;
    m10_seam_fake(d, 1, 0, 0, res_lo, res_hi, nres, null_rc, prt_ok, nullptr);
    const M10Layout L = m10_amm_layout(
        w, wn, d.res, mode, [&d](uint64_t a, uint64_t n, bool wr) { return d.null(a, n, wr); }, [&d](uint64_t a, uint64_t n) { return d.prt(a, n); });
    out[0] = L.prt_ok ? 1 : 0;
    out[1] = L.nulls.size();
    out[2] = L.asked;
    out[3] = L.small;
    out[4] = L.whole;
    out[5] = L.null_failed;
    out[6] = L.null_absent;
    out[7] = L.null_bytes;
    m10_seam_out(d.log, log, cap);
}
extern "C" int bc5_m10_amm_event(uint64_t* nulls_lo_hi, uint32_t* n_nulls, uint32_t cap, uint64_t w, uint64_t wn, uint64_t va, uint64_t size, int on, int mode, int null_rc,
                                 char* line, uint32_t line_cap) {
    std::vector<std::pair<uint64_t, uint64_t>> nulls;
    for (uint32_t k = 0; k < *n_nulls; k++) nulls.emplace_back(nulls_lo_hi[2 * k], nulls_lo_hi[2 * k + 1]);
    M10FakeDev d;
    d.null_rc    = null_rc;
    const int r  = m10_amm_event(nulls, w, wn, va, size, on, mode, [&d](uint64_t a, uint64_t n, bool wr) { return d.null(a, n, wr); });
    *n_nulls     = static_cast<uint32_t>(nulls.size());
    for (size_t k = 0; k < nulls.size() && k < cap; k++) {
        nulls_lo_hi[2 * k]     = nulls[k].first;
        nulls_lo_hi[2 * k + 1] = nulls[k].second;
    }
    m10_seam_out(m10_amm_event_text(va, size, on, r, mode), line, line_cap);
    return r;
}
extern "C" uint64_t bc5_m10_held() {
    std::lock_guard lk(g_m10_mutex);
    return g_m10_held.size();
}
extern "C" void bc5_m10_amm_pending() {
    m10_amm_pending();
}
// The GPU rights: the pure rule, the unit's reading, the rebuild's map with the recording device.
extern "C" unsigned bc5_m10_rights_of(int prot) {
    return m10_rights_of(prot);
}
extern "C" unsigned bc5_m10_view_rights(int prot) {
    return m10_view_rights(prot);
}
extern "C" int bc5_m10_map_view(int rights_rc, int shared_ok, uint32_t id, uint64_t off, uint64_t n, uint64_t va, unsigned rights, char* log, uint32_t cap) {
    M10FakeDev d;
    d.rights_rc = rights_rc;
    d.shared_ok = shared_ok != 0;
    const bool r = m10_map_view_with(d, id, off, n, va, rights);
    m10_seam_out(d.log, log, cap);
    return r ? 1 : 0;
}
extern "C" uint64_t bc5_m10_rights_maps() {
    return g_m10_rights_maps.load();
}
// The holes: the scratch_fill and scratch_release steps and aliases_apply's hook with the recording device; the alias windows
// (byte, lo, size) are the test's own.
static std::vector<M10AliasWin> m10_seam_wins(const uint64_t* byte, const uint64_t* lo, const uint64_t* size, uint32_t n) {
    std::vector<M10AliasWin> v;
    for (uint32_t k = 0; k < n; k++) v.emplace_back(byte[k], lo[k], size[k]);
    return v;
}
extern "C" int bc5_m10_hole_map(int nullrange_rc, int shared_ok, uint32_t scratch_id, uint64_t va, uint64_t n, const uint64_t* win_byte, const uint64_t* win_lo,
                                const uint64_t* win_size, uint32_t nwin, char* log, uint32_t cap) {
    M10FakeDev d;
    d.nullrange_rc = nullrange_rc;
    d.shared_ok    = shared_ok != 0;
    d.scratch_id   = scratch_id;
    const int r    = m10_hole_map_with(d, va, n, m10_seam_wins(win_byte, win_lo, win_size, nwin));
    m10_seam_out(d.log, log, cap);
    return r;
}
extern "C" void bc5_m10_hole_unmap(uint64_t va, char* log, uint32_t cap) {
    M10FakeDev d;
    m10_hole_unmap_with(d, va);
    m10_seam_out(d.log, log, cap);
}
extern "C" void bc5_m10_holes_alias_sync(int nullrange_rc, const uint64_t* win_byte, const uint64_t* win_lo, const uint64_t* win_size, uint32_t nwin, char* log, uint32_t cap) {
    M10FakeDev d;
    d.nullrange_rc = nullrange_rc;
    m10_holes_alias_sync_with(d, m10_seam_wins(win_byte, win_lo, win_size, nwin));
    m10_seam_out(d.log, log, cap);
}
extern "C" void bc5_m10_holes_state(uint64_t* out) { // null pieces held, fallbacks to the scratch BO, alias null ranges held, alias failures
    out[0] = g_m10_holes.size();
    out[1] = g_m10_hole_fallbacks;
    uint64_t a = 0;
    for (const auto& kv: g_m10_holes) a += kv.second.aliases.size();
    out[2] = a;
    out[3] = g_m10_hole_alias_failed;
}
extern "C" void bc5_m10_holes_reset() {
    m10_holes_reset();
}
extern "C" uint64_t bc5_m10_alias_va(uint64_t byte, uint64_t va) {
    return m10_alias_va(byte, va);
}
// The backend's three methods as this build sees them (1 there, 0 not): map_null_window, map_shared_rights, map_null_range with
// unmap_null_range; and the calls on devices with and without them.
extern "C" int bc5_m10_backend_has(int which) {
    if (which == 0) return m10_has_null_window<bc5::direct::Device>() ? 1 : 0;
    if (which == 1) return m10_has_rights<bc5::direct::Device>() ? 1 : 0;
    return m10_has_null_range<bc5::direct::Device>() ? 1 : 0;
}
struct M10FakeAll { // a device with the three methods
    int  ok = 0, writable = -1;
    unsigned rights = 0;
    bool map_null_window(std::uint64_t va, std::uint64_t size, bool w) {
        writable = w ? 1 : 0;
        return ok != 0 && va == kM10AmmVa && size == kM10AmmSize;
    }
    bool map_shared_rights(std::uint32_t id, std::uint64_t off, std::uint64_t size, std::uint64_t va, unsigned r) {
        rights = r;
        return ok != 0 && id == 3 && off == 0 && size == 0x10000 && va == kM10AmmVa;
    }
    bool map_null_range(std::uint64_t va, std::uint64_t size, bool w) {
        writable = w ? 1 : 0;
        return ok != 0 && va == kM10AmmVa && size == 0x10000;
    }
    bool unmap_null_range(std::uint64_t va) { return ok != 0 && va == kM10AmmVa; }
};
struct M10FakeNone { // a device without them
    int prt = 0;
};
// which: 0 map_null_window, 1 map_shared_rights, 2 map_null_range, 3 unmap_null_range; has: the device has them; got: what it saw.
extern "C" int bc5_m10_backend_call(int which, int has, int ok, int writable, int* got) {
    if (has != 0) {
        M10FakeAll d;
        d.ok        = ok;
        const int r = which == 0   ? m10_null_call(&d, kM10AmmVa, kM10AmmSize, writable != 0)
                      : which == 1 ? m10_rights_call(&d, 3, 0, 0x10000, kM10AmmVa, kM10RightsRX)
                      : which == 2 ? m10_nullrange_call(&d, kM10AmmVa, 0x10000, writable != 0)
                                   : m10_unnullrange_call(&d, kM10AmmVa);
        *got        = which == 1 ? static_cast<int>(d.rights) : d.writable;
        return r;
    }
    M10FakeNone d;
    *got = -1;
    return which == 0 ? m10_null_call(&d, kM10AmmVa, kM10AmmSize, writable != 0)
           : which == 1 ? m10_rights_call(&d, 3, 0, 0x10000, kM10AmmVa, kM10RightsRX)
           : which == 2 ? m10_nullrange_call(&d, kM10AmmVa, 0x10000, writable != 0)
                        : m10_unnullrange_call(&d, kM10AmmVa);
}
extern "C" int64_t bc5_m10_sysfs(const char* leaf) {
    return m10_sysfs(leaf);
}
// ---- end of exp 0401 e10's (tag m10) seams --------------------------------------------------------------------------------------
#else
// Without the direct path: the journal's hook does nothing, and the two functions other units call (CONTRACT 1 and 2) exist.
static void     m10_journal_drop(FILE*) {}
extern "C" void Bc5ProtCensus(int, uint64_t, uint64_t, uint64_t, int, int, const char*) {}
extern "C" void Bc5AmmReserved(uint64_t, uint64_t, int) {}
#endif
} // namespace Bc5Gc::Direct

namespace Bc5LleKernel {
// ---- end of exp 0401 e10's (tag m10) block --------------------------------------------------------------------------------------
""")

edit("the block", BLOCK_ANCHOR, BLOCK_ANCHOR + BLOCK)


def strip_code(b):
    """The text with comments and string/char literals removed (for the balance counts)."""
    out = bytearray()
    i, n = 0, len(b)
    while i < n:
        c = b[i:i + 1]
        if b[i:i + 2] == b"//":
            j = b.find(b"\n", i)
            i = n if j < 0 else j
        elif b[i:i + 2] == b"/*":
            j = b.find(b"*/", i + 2)
            i = n if j < 0 else j + 2
        elif c in (b'"', b"'") and not (c == b"'" and i > 0 and b[i - 1:i].isalnum()):  # 500'000'000ull: a digit separator, not a literal
            j = i + 1
            while j < n and b[j:j + 1] != c:
                j += 2 if b[j:j + 1] == b"\\" else 1
            i = j + 1
        else:
            out += c
            i += 1
    return bytes(out)


def balance(b):
    s = strip_code(b)
    return (s.count(b"{") - s.count(b"}"), s.count(b"(") - s.count(b")"), s.count(b"[") - s.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def apply(s, edits, rel):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert b"\r" not in s, ("a CR in the LF unit", rel)
    done = []
    out = s
    at = -1
    for name, old, new in edits:
        assert out.count(old) == 1, ("an anchor does not occur exactly once", rel, name, out.count(old))
        assert balance(old) == balance(new), ("the edit changes the balance", rel, name, balance(old), balance(new))
        new.decode("ascii")
        assert b"\r" not in new, ("a CR in the inserted text", rel, name)
        pos = out.index(old)
        assert pos > at, ("the edits are not in file order", rel, name)
        at = pos
        out = out.replace(old, new)
        done.append((old, new, name))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    back = out
    for old, new, name in reversed(done):
        assert back.count(new) == 1, ("undo", rel, name)
        back = back.replace(new, old)
    assert back == s, ("undoing the edits does not give the input back", rel)
    assert out.startswith(b"\xef\xbb\xbf") == s.startswith(b"\xef\xbb\xbf"), ("the BOM changed", rel)
    return out


def edit_main(s):
    out = apply(s, E, MAIN)
    # The hooks: declaration, uses, definition (and the seams' names and bodies).
    counts = {h: out.count(h.encode() + b"(") for h in ("m10_journal_drop", "m10_amm_window", "m10_amm_pending", "m10_amm_apply", "m10_start", "m10_tick", "m10_view_rights",
                                                         "m10_map_view", "m10_hole_map", "m10_hole_unmap", "m10_holes_reset", "m10_holes_alias_sync")}
    want = {"m10_journal_drop": 8, "m10_amm_window": 5, "m10_amm_pending": 5, "m10_amm_apply": 4, "m10_start": 5, "m10_tick": 5, "m10_view_rights": 6, "m10_map_view": 4,
            "m10_hole_map": 4, "m10_hole_unmap": 4, "m10_holes_reset": 5, "m10_holes_alias_sync": 4}
    assert counts == want, ("the hooks' uses", counts)
    blk = out[out.index(BLOCK_ANCHOR):out.index(BLOCK_END)]
    assert blk.count(b"\n#if defined(KYTY_BC5_DIRECT)\n") == 1 and blk.count(b"\n#else\n") == 1 and blk.count(b"\n#endif\n") == 1, "the block's #if"
    assert blk.count(b"\n} // namespace Bc5LleKernel") == 1 and blk.count(b"\nnamespace Bc5LleKernel {\n") == 1, "the block's namespaces"
    assert blk.count(b"\nnamespace Bc5Gc::Direct {\n") == 1 and blk.count(b"\n} // namespace Bc5Gc::Direct\n") == 1, "the block's namespaces"
    order = [blk.index(x) for x in (PURE_MARK, HOST_MARK, SEAMS_MARK, SEAMS_END, b"\n#else\n")]
    assert order == sorted(order), ("the block's parts", order)
    # Both CONTRACT functions this unit defines exist once in each branch; e9's two PRT calls are gone and the hook's is the one left.
    for f in (b'extern "C" void Bc5ProtCensus(', b'extern "C" void Bc5AmmReserved('):
        assert blk.count(f) == 2, ("a contract function", f)
    amm = b'std::getenv("BC5_DIRECT_AMM_PRT")'
    assert out.count(b"->map_prt_window(") == 1 and s.count(b"->map_prt_window(") == 2 and out.count(amm) == s.count(amm) - 2 + 2, "the AMM calls"
    # Every DView brace-initialiser has its protection now (7 values), and DMap's has its rights (5).
    assert out.count(b"direct_eager_name(name), prot})") == 1 and out.count(b"direct_eager_name(name), -1})") == 1, "DView's initialisers"
    assert out.count(b"eager[i] != 0, -1})") == 1 and out.count(b"eager[k] != 0, -1})") == 1, "the seams' DViews"
    assert out.count(b"it->id, m10_view_rights(v.prot)})") == 1, "DMap's initialiser"
    assert out.count(b"std::fopen(name, \"a\")") == s.count(b"std::fopen(name, \"a\")"), "the journal's opens"
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    with open(os.path.join(root, MAIN), "rb") as f:
        s = f.read()
    for m in MARKS:
        assert m not in s, ("refused: the unit has the edit already", MAIN, m.decode())
    assert md5(s) == MAIN_MD5, ("refused: not the pinned input", MAIN, md5(s), MAIN_MD5)
    out = edit_main(s)
    print(f"# in:  {MAIN} {md5(s)}  ({len(s)} bytes, LF)", file=sys.stderr)
    dst = os.path.join(outdir, MAIN)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{MAIN} {md5(out)}")


if __name__ == "__main__":
    main()
