// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag cs439, 11-24, the top session's order after the register census): the edge-block suspects 1 and 2
// as switches, all off by default, each testable alone (fixes-first rule), plus a dump of one frame's register tables.
//   BC5_0439_CS_COUNT=1           CLEAR_STATE cmd 0/1/2 counted by level (root, piece depth 0/1/2/3+, inside COND_EXEC)
//                                 over the guest's src, and the root tracker's push/pop/unmatched/conditional; a line on
//                                 stderr at the first 4 GFX submits and every 1000th.
//   BC5_0439_PUSH_NO_CLEAR=1      a push (CLEAR_STATE cmd 1) no longer clears: NOP-ed instead of the filter's cmd 0; the
//                                 root tracker keeps the current context valid (snapshot taken as before, pop restores
//                                 it). In pieces without PIECE_STATE_STACK only the push changes; their pops still clear.
//                                 TODO(verify): the console's cmd 1 semantics (PAL separates push 1 from push_clear 3).
//   BC5_0439_PIECE_STATE_STACK=1  the root's tracker also runs over the GFX job's pieces (chained and called IBs) in their
//                                 collected order (TODO(verify): equals execution order for chains, not for calls in the
//                                 middle of a piece); a piece's pop becomes the restore of the pushed context. Room for it
//                                 is reserved at layout (2048 dwords per pop outside COND_EXEC); the referencing
//                                 INDIRECT_BUFFER's size is set to the grown size.
//   BC5_0439_PASS_CONTEXT_CONTROL=1  the guest's CONTEXT_CONTROL passes unchanged (policy's safe_context_control off) in
//                                 the guest's stream; BC5's own prefix keeps its 0x80000000/0x80000000. Can hang if the
//                                 shadow addresses the guest set are not valid here: run it alone.
//   BC5_0439_COND_POP_NOP=1       a pop (CLEAR_STATE cmd 2) inside a COND_EXEC range is NOP-ed instead of becoming the
//                                 filter's cmd 0 (a full clear with no restore when the condition holds). N0 (11-24): one such
//                                 pop per frame at the root, after the frame's matched push/pop (stack empty then).
//   BC5_0439_REGTAB_DUMP=<dir>    with BC5_0439_REGTAB_AT=s1,s2,.. (seconds from the first GFX submit): at each time, the
//                                 next GFX submit of at least BC5_0439_REGTAB_MIN_DW dwords over all its pieces (default 2000) is written to
//                                 <dir>/rt439-<pid>-<seq>/: every piece as the guest wrote it (rt439-dcb-<seq>-piece-<k>-<n>.bin,
//                                 frame.py's naming) and tables.bin: for each LOAD_*_REG[_INDEX] packet (0x5f 0x60 0x61
//                                 0x63 0x64 0x9f) the memory it loads (u64 address, u32 bytes, u32 opcode | piece << 8,
//                                 u32 offset in the piece, then the bytes), read on the CPU at submit (no chip readback).
#pragma once
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <mutex>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <cerrno>
#include <unistd.h>
#include <vector>

namespace bc5::cs439 {

struct Env {
    bool count = false, push_no_clear = false, piece_stack = false, pass_cc = false, cond_pop_nop = false, cc_census = false, cc_guarded = false, mlock_imports = false;
    std::string dump;
    std::vector<double> at;
    std::size_t min_dw = 2000;
};

inline bool on(const char *name) {
    const char *e = std::getenv(name);
    return e != nullptr && *e != 0 && std::strcmp(e, "0") != 0;
}

inline const Env &env() {
    static const Env e = [] {
        Env v;
        v.count = on("BC5_0439_CS_COUNT");
        v.push_no_clear = on("BC5_0439_PUSH_NO_CLEAR");
        v.piece_stack = on("BC5_0439_PIECE_STATE_STACK");
        v.pass_cc = on("BC5_0439_PASS_CONTEXT_CONTROL");
        v.cond_pop_nop = on("BC5_0439_COND_POP_NOP");
        v.cc_census = on("BC5_0439_CC_CENSUS");
        v.cc_guarded = on("BC5_0439_CC_GUARDED");
        v.mlock_imports = on("BC5_0439_MLOCK_IMPORTS");
        if (const char *d = std::getenv("BC5_0439_REGTAB_DUMP"); d != nullptr && *d != 0) v.dump = d;
        if (const char *a = std::getenv("BC5_0439_REGTAB_AT"); a != nullptr) {
            const char *p = a;
            while (*p != 0) {
                char *q = nullptr;
                const double s = std::strtod(p, &q);
                if (q == p) break;
                v.at.push_back(s);
                p = *q == ',' ? q + 1 : q;
            }
        }
        if (const char *m = std::getenv("BC5_0439_REGTAB_MIN_DW"); m != nullptr && *m != 0) v.min_dw = std::strtoul(m, nullptr, 10);
        std::fprintf(stderr, "bc5-direct: exp 0439 (tag cs439): CS_COUNT %d PUSH_NO_CLEAR %d PIECE_STATE_STACK %d PASS_CONTEXT_CONTROL %d COND_POP_NOP %d CC_CENSUS %d CC_GUARDED %d MLOCK_IMPORTS %d REGTAB_DUMP %s (%zu times, min %zu dwords)\n",
                     v.count, v.push_no_clear, v.piece_stack, v.pass_cc, v.cond_pop_nop, v.cc_census, v.cc_guarded, v.mlock_imports, v.dump.empty() ? "off" : v.dump.c_str(), v.at.size(), v.min_dw);
        return v;
    }();
    return e;
}

inline std::size_t packet_len(std::uint32_t h) {
    const std::uint32_t type = h >> 30;
    if (type == 3 || type == 0) {
        const std::uint32_t c = (h >> 16) & 0x3fffu;
        return c == 0x3fffu ? 1 : c + 2;
    }
    return 1;
}

// CLEAR_STATE packets of a guest IB outside / inside COND_EXEC ranges: f(offset, cmd, conditional).
template <class F> void clear_states(const std::uint32_t *src, std::size_t n, F f) {
    std::size_t cond_end = 0;
    for (std::size_t i = 0; i < n;) {
        const std::uint32_t h = src[i];
        const std::size_t len = packet_len(h);
        if (i + len > n) break;
        if (h >> 30 == 3 && ((h >> 16) & 0x3fffu) != 0x3fffu) {
            const std::uint32_t op = (h >> 8) & 0xffu;
            if (op == 0x22 && len >= 5) cond_end = std::max(cond_end, i + len + (src[i + 4] & 0x3fffu));
            else if (op == 0x12 && len >= 2) f(i, src[i + 1] & 0xfu, i < cond_end);
        }
        i += len;
    }
}

// [level 0 root, 1..4 piece depth 0..3+][conditional][cmd 0, 1, 2, other]
inline std::atomic<std::uint64_t> g_cs[5][2][4];
inline std::atomic<std::uint64_t> g_root_push{0}, g_root_pop{0}, g_root_unmatched{0}, g_root_cond{0}, g_piece_push{0}, g_piece_pop{0},
    g_piece_unmatched{0}, g_piece_restored{0}, g_submits{0}, g_grown{0};

inline void count_ib(const std::uint32_t *src, std::size_t n, int level) {
    clear_states(src, n, [level](std::size_t, std::uint32_t cmd, bool cond) { g_cs[level][cond ? 1 : 0][cmd <= 2 ? cmd : 3]++; });
}

inline void report() {
    const std::uint64_t s = ++g_submits;
    if (s > 4 && s % 1000 != 0) return;
    std::string t;
    static const char *const lv[] = {"root", "piece d0", "piece d1", "piece d2", "piece d3+"};
    for (int l = 0; l < 5; ++l)
        for (int c = 0; c < 2; ++c) {
            const std::uint64_t a = g_cs[l][c][0], b = g_cs[l][c][1], p = g_cs[l][c][2], o = g_cs[l][c][3];
            if (a + b + p + o == 0) continue;
            char buf[160];
            std::snprintf(buf, sizeof buf, " [%s%s: cmd0 %llu cmd1 %llu cmd2 %llu other %llu]", lv[l], c ? " in COND_EXEC" : "",
                          static_cast<unsigned long long>(a), static_cast<unsigned long long>(b), static_cast<unsigned long long>(p), static_cast<unsigned long long>(o));
            t += buf;
        }
    std::fprintf(stderr, "bc5-direct: exp 0439 (tag cs439): %llu GFX submits; CLEAR_STATE%s; root tracker push %llu pop %llu unmatched %llu conditional %llu; pieces push %llu pop %llu unmatched %llu restored regs %llu, %llu pieces grown\n",
                 static_cast<unsigned long long>(s), t.empty() ? " none" : t.c_str(), static_cast<unsigned long long>(g_root_push.load()),
                 static_cast<unsigned long long>(g_root_pop.load()), static_cast<unsigned long long>(g_root_unmatched.load()), static_cast<unsigned long long>(g_root_cond.load()),
                 static_cast<unsigned long long>(g_piece_push.load()), static_cast<unsigned long long>(g_piece_pop.load()), static_cast<unsigned long long>(g_piece_unmatched.load()),
                 static_cast<unsigned long long>(g_piece_restored.load()), static_cast<unsigned long long>(g_grown.load()));
}

// Pops a piece holds outside COND_EXEC (room for their restores).
inline std::size_t pops_in(const std::uint32_t *src, std::size_t n) {
    std::size_t p = 0;
    clear_states(src, n, [&p](std::size_t, std::uint32_t cmd, bool cond) { p += (cmd == 2 && !cond) ? 1 : 0; });
    return p;
}

// PUSH_NO_CLEAR in a piece the tracker does not see: the push's dwords become NOPs (out is the filtered copy).
inline void push_nops(const std::uint32_t *src, std::uint32_t *out, std::size_t n, std::uint32_t nop) {
    clear_states(src, n, [out, nop](std::size_t i, std::uint32_t cmd, bool cond) {
        if (cmd == 1 && !cond) out[i] = out[i + 1] = nop;
    });
}

// The one-frame register-table dump. Called for every GFX submit; does nothing unless armed.
struct DumpPiece {
    const std::uint32_t *src;
    std::size_t n;
};
inline void maybe_dump(const std::vector<DumpPiece> &pieces, const std::function<bool(std::uint64_t, std::uint64_t)> &readable) {
    const Env &e = env();
    if (e.dump.empty() || e.at.empty() || pieces.empty()) return;
    using clock = std::chrono::steady_clock;
    static const clock::time_point t0 = clock::now();
    static std::atomic<std::size_t> next{0};
    static std::atomic<std::uint64_t> seq{0};
    const std::size_t k = next.load();
    if (k >= e.at.size()) return;
    const double t = std::chrono::duration<double>(clock::now() - t0).count();
    std::size_t total = 0; // all pieces: this title's frame root is small, its work is in chained pieces (N0, 11-24)
    for (const DumpPiece &q : pieces) total += q.n;
    if (t < e.at[k] || total < e.min_dw) return;
    std::size_t expect = k;
    if (!next.compare_exchange_strong(expect, k + 1)) return;
    const std::uint64_t s = ++seq;
    char dir[512];
    std::snprintf(dir, sizeof dir, "%s/rt439-%d-%llu", e.dump.c_str(), static_cast<int>(getpid()), static_cast<unsigned long long>(s));
    mkdir(e.dump.c_str(), 0700);
    mkdir(dir, 0700);
    std::size_t tables = 0, unread = 0, bytes_out = 0;
    std::FILE *tf = std::fopen((std::string(dir) + "/tables.bin").c_str(), "wb");
    for (std::size_t p = 0; p < pieces.size(); ++p) {
        char fn[640];
        std::snprintf(fn, sizeof fn, "%s/rt439-dcb-%llu-piece-%zu-%zu.bin", dir, static_cast<unsigned long long>(s), p, pieces[p].n);
        if (std::FILE *f = std::fopen(fn, "wb")) {
            std::fwrite(pieces[p].src, 4, pieces[p].n, f);
            std::fclose(f);
        }
        const std::uint32_t *src = pieces[p].src;
        for (std::size_t i = 0; i < pieces[p].n;) {
            const std::uint32_t h = src[i];
            const std::size_t len = packet_len(h);
            if (i + len > pieces[p].n) break;
            const std::uint32_t op = (h >> 8) & 0xffu;
            if (h >> 30 == 3 && len >= 5 && (op == 0x5f || op == 0x60 || op == 0x61 || op == 0x63 || op == 0x64 || op == 0x9f)) {
                const std::uint64_t a = (static_cast<std::uint64_t>(src[i + 1]) & ~3ull) | (static_cast<std::uint64_t>(src[i + 2] & 0xffffu) << 32);
                std::uint64_t nb = 0;
                if (op == 0x63 || op == 0x64 || op == 0x9f) { // _INDEX forms: count in dword 4; pairs when dword 3 bit 31
                    const std::uint64_t cnt = src[i + 4] & 0x3fffu;
                    nb = cnt * ((src[i + 3] >> 31) != 0 ? 8 : 4);
                } else { // (reg offset, count) pairs from dword 3: the table spans up to the largest offset + count
                    std::uint64_t hi = 0;
                    for (std::size_t q = 3; q + 1 < len; q += 2) hi = std::max<std::uint64_t>(hi, (static_cast<std::uint64_t>(src[i + q] & 0xffffu) + std::min<std::uint32_t>(src[i + q + 1], 4096)) * 4);
                    nb = hi;
                }
                if (a != 0 && nb != 0 && nb <= (1u << 20) && tf != nullptr && readable && readable(a, nb)) {
                    const std::uint32_t hdr[5] = {static_cast<std::uint32_t>(a), static_cast<std::uint32_t>(a >> 32), static_cast<std::uint32_t>(nb),
                                                  op | static_cast<std::uint32_t>(p << 8), static_cast<std::uint32_t>(i)};
                    std::fwrite(hdr, 4, 5, tf);
                    std::fwrite(reinterpret_cast<const void *>(a), 1, nb, tf);
                    tables++;
                    bytes_out += nb;
                } else {
                    unread++;
                }
            }
            i += len;
        }
    }
    if (tf != nullptr) std::fclose(tf);
    std::fprintf(stderr, "bc5-direct: exp 0439 (tag cs439): register tables of GFX submit at %.1f s (arm %zu of %zu) in %s: %zu pieces, %zu tables (%zu bytes), %zu not readable\n",
                 t, k + 1, e.at.size(), dir, pieces.size(), tables, bytes_out, unread);
}

// BC5_0439_CC_CENSUS=1 (11-24 15:20, after N2): what the guest's CONTEXT_CONTROL asks for and what its loads point at. Over
// the guest's pieces of every GFX submit: the distinct (load, shadow) dword pairs of CONTEXT_CONTROL (0x28) with counts, and
// for each LOAD packet (0x5f 0x60 0x61 0x63 0x64 0x9f; also SET_*_REG_INDEX-free forms are not loads) its count, how many
// of its addresses the host vouches for (readable = mapped here) and how many distinct addresses it used. A line at the
// first 4 GFX submits and every 1000th.
struct CcPair { std::uint32_t a, b; std::uint64_t n; };
inline std::vector<CcPair> &cc_pairs() { static std::vector<CcPair> v; return v; }
inline std::atomic<std::uint64_t> g_ld[256][2]; // [op][mapped]
inline std::vector<std::uint64_t> &cc_addrs() { static std::vector<std::uint64_t> v; return v; }
inline void cc_census(const std::vector<DumpPiece> &pieces, const std::function<bool(std::uint64_t, std::uint64_t)> &readable) {
    static std::mutex mu; // GFX submits may come from more than one thread
    std::lock_guard<std::mutex> lk(mu);
    static std::atomic<std::uint64_t> subs{0};
    for (const DumpPiece &pc : pieces) {
        for (std::size_t i = 0; i < pc.n;) {
            const std::uint32_t h = pc.src[i];
            const std::size_t len = packet_len(h);
            if (i + len > pc.n) break;
            const std::uint32_t op = (h >> 8) & 0xffu;
            if (h >> 30 == 3 && op == 0x28 && len >= 3) {
                bool found = false;
                for (CcPair &q : cc_pairs()) if (q.a == pc.src[i + 1] && q.b == pc.src[i + 2]) { q.n++; found = true; break; }
                if (!found && cc_pairs().size() < 32) cc_pairs().push_back({pc.src[i + 1], pc.src[i + 2], 1});
            } else if (h >> 30 == 3 && len >= 5 && (op == 0x5f || op == 0x60 || op == 0x61 || op == 0x63 || op == 0x64 || op == 0x9f)) {
                const std::uint64_t a = (static_cast<std::uint64_t>(pc.src[i + 1]) & ~3ull) | (static_cast<std::uint64_t>(pc.src[i + 2] & 0xffffu) << 32);
                const bool m = a != 0 && readable && readable(a, 4);
                g_ld[op][m ? 1 : 0]++;
                auto &v = cc_addrs();
                if (v.size() < 100000 && std::find(v.begin(), v.end(), a) == v.end()) v.push_back(a);
            }
            i += len;
        }
    }
    const std::uint64_t s = ++subs;
    if (s > 4 && s % 1000 != 0) return;
    std::string t;
    for (const CcPair &q : cc_pairs()) {
        char b[96];
        std::snprintf(b, sizeof b, " [%08x/%08x x%llu]", q.a, q.b, static_cast<unsigned long long>(q.n));
        t += b;
    }
    std::string l;
    for (int op : {0x5f, 0x60, 0x61, 0x63, 0x64, 0x9f}) {
        const std::uint64_t y = g_ld[op][1], n = g_ld[op][0];
        if (y + n == 0) continue;
        char b[96];
        std::snprintf(b, sizeof b, " [%#x: %llu mapped, %llu not]", op, static_cast<unsigned long long>(y), static_cast<unsigned long long>(n));
        l += b;
    }
    std::fprintf(stderr, "bc5-direct: exp 0439 (tag cs439 cc): %llu GFX submits; CONTEXT_CONTROL%s; loads%s; %zu distinct load addresses\n",
                 static_cast<unsigned long long>(s), t.empty() ? " none" : t.c_str(), l.empty() ? " none" : l.c_str(), cc_addrs().size());
}

// BC5_0439_CC_GUARDED=1 (11-24 16:00, the faithful form of PASS_CONTEXT_CONTROL after N2/N2r/N2d): the guest's
// CONTEXT_CONTROL passes in a GFX submit when the submit's root holds at least one LOAD_UCONFIG/SH/CONTEXT_REG (0x5e 0x5f
// 0x61, the CP's shadow and load addresses) and every one of them lies in GPU-mapped memory (the policy's `mapped`, the
// same check every memory operand gets); otherwise the old 0x80000000/0x80000000 stays and the submit is counted with
// its reason. TODO(verify): `mapped` vouches for a GPU mapping, not for GPU-write permission; BC5's direct imports are
// mapped readable+writeable (map_shared/map_userptr), N2/N2d wrote the title's areas without a fault.
inline std::atomic<std::uint64_t> g_ccg_pass{0}, g_ccg_noload{0}, g_ccg_unmapped{0};
inline bool cc_loads_ok(const std::uint32_t *src, std::size_t n, const std::function<bool(std::uint64_t, std::uint64_t)> &readable) {
    std::size_t loads = 0;
    bool ok = true;
    for (std::size_t i = 0; i < n;) {
        const std::uint32_t h = src[i];
        const std::size_t len = packet_len(h);
        if (i + len > n) break;
        const std::uint32_t op = (h >> 8) & 0xffu;
        if (h >> 30 == 3 && len >= 3 && (op == 0x5e || op == 0x5f || op == 0x61)) {
            const std::uint64_t a = (static_cast<std::uint64_t>(src[i + 1]) & ~3ull) | (static_cast<std::uint64_t>(src[i + 2] & 0xffffu) << 32);
            std::uint64_t hi = 4;
            for (std::size_t q = 3; q + 1 < len; q += 2)
                hi = std::max<std::uint64_t>(hi, (static_cast<std::uint64_t>(src[i + q] & 0xffffu) + std::min<std::uint32_t>(src[i + q + 1], 4096)) * 4);
            loads++;
            if (a == 0 || !readable || !readable(a, hi)) ok = false;
        }
        i += len;
    }
    const bool pass = loads != 0 && ok;
    (pass ? g_ccg_pass : loads == 0 ? g_ccg_noload : g_ccg_unmapped)++;
    const std::uint64_t t = g_ccg_pass + g_ccg_noload + g_ccg_unmapped;
    if (t <= 4 || t % 1000 == 0)
        std::fprintf(stderr, "bc5-direct: exp 0439 (tag cs439 ccg): %llu GFX submits: guest CONTEXT_CONTROL passed %llu; forced (no LOAD in the root) %llu; forced (a LOAD address not mapped) %llu\n",
                     static_cast<unsigned long long>(t), static_cast<unsigned long long>(g_ccg_pass.load()), static_cast<unsigned long long>(g_ccg_noload.load()),
                     static_cast<unsigned long long>(g_ccg_unmapped.load()));
    return pass;
}

// BC5_0439_MLOCK_IMPORTS=1 (11-24 16:00, after N2's freeze): every direct-memory range imported through udmabuf is also
// mapped read-only by the host and mlock()ed, so its pages sit on the unevictable LRU and reclaim stops scanning them.
// Kernel path (from the public kernel source, recalled, TODO(verify) the exact lines on 7.3): udmabuf pins the memfd's
// folios (drivers/dma-buf/udmabuf.c, memfd_pin_folios) but a pin does not make a folio unevictable; reclaim decides by
// folio_evictable() (mm/internal.h: !mapping_unevictable(mapping) && !folio_test_mlocked(folio)), so pinned shmem stays
// on the normal LRU, gets scanned and unmapped from the CPU side, and cannot be freed (N2: the emulator's resident
// shmem 5.9 -> 0.2 GB, swap +0.4 GB, pgscan_direct 0.4M -> 8.3M). An mlocked mapping marks the folio mlocked
// (mm/mlock.c, mlock_folio) for every mapping of it. Cost: no RAM (the pages are already resident and pinned), one VMA
// per import, and RLIMIT_MEMLOCK: on the box 2,199,023,616 bytes for the emulator (limits.d/memlock.conf), against
// ~10 GB pinned, so without a raised limit or CAP_IPC_LOCK the locks past ~2 GiB fail and are counted.
inline std::atomic<std::uint64_t> g_ml_bytes{0}, g_ml_ok{0}, g_ml_fail{0};
inline void lock_import(int memfd, std::uint64_t offset, std::uint64_t size, void *&p, std::uint64_t &n) {
    p = nullptr;
    n = 0;
    void *m = mmap(nullptr, size, PROT_READ, MAP_SHARED, memfd, static_cast<off_t>(offset));
    int err = 0;
    if (m == MAP_FAILED) {
        err = errno;
    } else if (mlock(m, size) != 0) {
        err = errno;
        munmap(m, size);
    } else {
        p = m;
        n = size;
        g_ml_bytes += size;
        g_ml_ok++;
    }
    if (err != 0) g_ml_fail++;
    const std::uint64_t t = g_ml_ok + g_ml_fail;
    if ((err != 0 && g_ml_fail <= 8) || t <= 4 || t % 256 == 0)
        std::fprintf(stderr, "bc5-direct: exp 0439 (tag cs439 ml): import 0x%llx+0x%llx %s%s; locked %llu ranges, %.2f GiB, %llu failed\n",
                     static_cast<unsigned long long>(offset), static_cast<unsigned long long>(size), err != 0 ? "NOT locked: " : "locked",
                     err != 0 ? std::strerror(err) : "", static_cast<unsigned long long>(g_ml_ok.load()), static_cast<double>(g_ml_bytes.load()) / 1073741824.0,
                     static_cast<unsigned long long>(g_ml_fail.load()));
}
inline void unlock_import(void *&p, std::uint64_t &n) {
    if (p == nullptr) return;
    munlock(p, n);
    munmap(p, n);
    g_ml_bytes -= n;
    p = nullptr;
    n = 0;
}

} // namespace bc5::cs439
