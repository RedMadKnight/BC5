// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/lake_probe.hpp"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <utility>

namespace bc5::lake_probe {
namespace {

constexpr std::uint32_t kAcquireMem = 0xC0065800u;  // PKT3(ACQUIRE_MEM, 6, 0), indirect_check.cpp's form
constexpr std::uint32_t kEventWrite = 0xC0004600u;  // PKT3(EVENT_WRITE, 0, 0)
constexpr std::uint32_t kEventWrite2 = 0xC0024600u; // PKT3(EVENT_WRITE, 2, 0), with an address
constexpr std::uint32_t kPfpSyncMe = 0xC0004200u;   // PKT3(PFP_SYNC_ME, 0, 0)
constexpr std::uint32_t kSetContextReg = 0xC0016900u; // PKT3(SET_CONTEXT_REG, 1, 0)

// tools/bc5-agc/regdb/gfx10.json, EVENT_TYPE values; EVENT_INDEX as Mesa emits them.
constexpr std::uint32_t kCsPartialFlush = 7u | (4u << 8);
constexpr std::uint32_t kPsPartialFlush = 16u | (4u << 8);
constexpr std::uint32_t kDbMeta = 44u;
constexpr std::uint32_t kZpassDone = 21u | (1u << 8);

// Context offsets from 0xa000: the regdb's byte addresses / 4. SH offsets from 0x2c00.
constexpr std::uint32_t kDbCountControl = 0x001, kDbRenderOverride = 0x003, kDbZWriteBase = 0x014;
constexpr std::uint32_t kDbDepthControl = 0x200;
constexpr std::uint32_t kShPgmLoPs = 0x008, kShPgmHiPs = 0x009, kShComputePgmLo = 0x20c, kShComputePgmHi = 0x20d;

// GCR_CNTL, tools/bc5-agc/regdb/pkt3.json.
constexpr std::uint32_t kGl2Wb = 1u << 15, kGl2Inv = 1u << 14, kGl1Inv = 1u << 9, kGlvInv = 1u << 8;
constexpr std::uint32_t kGlkInv = 1u << 7, kGlmInv = 1u << 5, kGlmWb = 1u << 4, kGliInv = 1u; // GLI_INV ALL
// DB_COUNT_CONTROL: PERFECT_ZPASS_COUNTS, DISABLE_CONSERVATIVE_ZPASS_COUNTS, ZPASS_ENABLE(1),
// SLICE_EVEN_ENABLE(1), SLICE_ODD_ENABLE(1); one sample, F484.
constexpr std::uint32_t kCountOn = (1u << 1) | (1u << 2) | (1u << 8) | (1u << 24) | (1u << 28);
constexpr std::uint32_t kCountOff = 1u; // ZPASS_INCREMENT_DISABLE, RADV's idle value below GFX11
// DB_RENDER_OVERRIDE: FORCE_HIZ_ENABLE, FORCE_HIS_ENABLE0 and 1 = FORCE_DISABLE (2).
constexpr std::uint32_t kNoHizMask = 0x3fu, kNoHiz = 2u | (2u << 2) | (2u << 4);

constexpr std::uint8_t kOpNestedIb = 0x3f, kOpCondExec = 0x22, kOpSetPredication = 0x20;
constexpr std::uint8_t kOpDispatchDirect = 0x15, kOpDispatchIndirect = 0x16;

bool is_graphics_draw(std::uint8_t op) { // full_state.hpp's list without the dispatches
    return op == 0x24 || op == 0x25 || op == 0x27 || op == 0x2c || op == 0x2d || op == 0x35 || op == 0x38;
}
bool is_indirect_draw(std::uint8_t op) { return op == 0x24 || op == 0x25 || op == 0x2c || op == 0x38; }

std::uint32_t gcr_of(Cache c) {
    switch (c) {
    case Cache::wb: return kGl2Wb;
    case Cache::inv: return kGl2Inv | kGl1Inv | kGlvInv;
    case Cache::wbinv: return kGl2Wb | kGl2Inv | kGl1Inv | kGlvInv;
    case Cache::all: return kGl2Wb | kGl2Inv | kGl1Inv | kGlvInv | kGlkInv | kGlmInv | kGlmWb | kGliInv;
    default: return 0;
    }
}

void acquire(std::vector<std::uint32_t> &w, std::uint32_t gcr) {
    w.insert(w.end(), {kAcquireMem, 0u, 0xffffffffu, 0xffffffu, 0u, 0u, 0x0000000Au, gcr});
}
void event(std::vector<std::uint32_t> &w, std::uint32_t type) { w.insert(w.end(), {kEventWrite, type}); }
void context(std::vector<std::uint32_t> &w, std::uint32_t off, std::uint32_t value) {
    w.insert(w.end(), {kSetContextReg, off, value});
}
void zpass_done(std::vector<std::uint32_t> &w, std::uint64_t va) {
    w.insert(w.end(), {kEventWrite2, kZpassDone, static_cast<std::uint32_t>(va), static_cast<std::uint32_t>(va >> 32)});
}
std::uint64_t program(const full_state::Tracker &t, std::uint32_t lo_off, std::uint32_t hi_off) {
    std::uint32_t lo = 0, hi = 0;
    if (!t.get(full_state::Sh, lo_off, lo)) return 0;
    t.get(full_state::Sh, hi_off, hi);
    return (static_cast<std::uint64_t>(hi) << 40) | (static_cast<std::uint64_t>(lo) << 8);
}

} // namespace

bool parse(std::string_view text, Switches &out, std::string &bad) {
    Switches s;
    out = Switches{};
    bad.clear();
    std::size_t i = 0;
    while (i < text.size()) {
        std::size_t e = text.find_first_of(" \t\r\n", i);
        if (e == std::string_view::npos) e = text.size();
        const std::string_view tok = text.substr(i, e - i);
        i = e + 1;
        if (tok.empty()) continue;
        if (tok.front() == '#') {
            const std::size_t nl = text.find('\n', e);
            if (nl == std::string_view::npos) break;
            i = nl + 1;
            continue;
        }
        const auto flag = [&](std::string_view name, bool &f) {
            if (tok == std::string(name) + "=1") f = true;
            else if (tok == std::string(name) + "=0") f = false;
            else return false;
            return true;
        };
        if (tok == "cache=off") s.cache = Cache::off;
        else if (tok == "cache=wb") s.cache = Cache::wb;
        else if (tok == "cache=inv") s.cache = Cache::inv;
        else if (tok == "cache=wbinv") s.cache = Cache::wbinv;
        else if (tok == "cache=all") s.cache = Cache::all;
        else if (tok == "cache_at=first") s.cache_each = false;
        else if (tok == "cache_at=each") s.cache_each = true;
        else if (!flag("cull", s.cull) && !flag("pfp", s.pfp) && !flag("dbmeta", s.dbmeta) && !flag("idle", s.idle) &&
                 !flag("nohiz", s.nohiz) && !flag("trackercf", s.trackercf) && !flag("census", s.census) &&
                 !flag("zpass", s.zpass)) {
            bad = std::string(tok);
            return false;
        }
    }
    out = s;
    return true;
}

std::string describe(const Switches &s) {
    static const char *const kCache[] = {"off", "wb", "inv", "wbinv", "all"};
    std::string o = std::string("cache=") + kCache[static_cast<int>(s.cache)] + (s.cache_each ? " cache_at=each" : " cache_at=first");
    const auto add = [&o](const char *n, bool on) { o += std::string(" ") + n + (on ? "=1" : "=0"); };
    add("cull", s.cull);
    add("pfp", s.pfp);
    add("dbmeta", s.dbmeta);
    add("idle", s.idle);
    add("nohiz", s.nohiz);
    add("trackercf", s.trackercf);
    add("census", s.census);
    add("zpass", s.zpass);
    return o;
}

namespace {
double now_ms() {
    using namespace std::chrono;
    return duration<double, std::milli>(steady_clock::now().time_since_epoch()).count();
}
} // namespace

Session::Session(std::string ctl, std::string out) : ctl_(std::move(ctl)), out_(std::move(out)) {}

void Session::attach(std::uint64_t va, void *cpu, std::uint32_t bytes) {
    z_.va = va;
    z_.capacity = bytes / kRecordBytes;
    cpu_ = cpu;
}

void Session::read_ctl() {
    std::string text;
    if (std::FILE *f = std::fopen(ctl_.c_str(), "r"); f != nullptr) {
        char buf[512];
        const std::size_t n = std::fread(buf, 1, sizeof buf, f);
        std::fclose(f);
        text.assign(buf, n);
    }
    if (text == text_) return;
    text_ = text;
    const std::uint64_t chains = full_state::chain_stops();
    std::fprintf(stderr, "bc5-direct: experiment 0385 period: jobs %llu writers %llu in_cond %llu inserted_words %llu refused %llu cull_barriers %llu htile_fills %llu chain_stops %llu cond_exec %llu predication %llu nested_ibs %llu\n",
                 static_cast<unsigned long long>(period_.jobs), static_cast<unsigned long long>(period_.writers), static_cast<unsigned long long>(period_.in_cond),
                 static_cast<unsigned long long>(period_.words), static_cast<unsigned long long>(period_.refused), static_cast<unsigned long long>(period_.cull),
                 static_cast<unsigned long long>(period_.htile), static_cast<unsigned long long>(chains - chain_at_), static_cast<unsigned long long>(period_.cond),
                 static_cast<unsigned long long>(period_.pred), static_cast<unsigned long long>(period_.nested));
    period_ = Period{};
    chain_at_ = chains;
    std::string bad;
    if (!parse(text, sw_, bad)) std::fprintf(stderr, "bc5-direct: experiment 0385 bad switch \"%s\": all off\n", bad.c_str());
    full_state::set_chain_stop(sw_.trackercf);
    std::fprintf(stderr, "bc5-direct: experiment 0385 at %.3f ms: %s\n", now_ms(), describe(sw_).c_str());
}

void Session::dump() {
    dumped_ = true;
    std::FILE *f = std::fopen(out_.c_str(), "wb");
    bool ok = f != nullptr && std::fwrite(cpu_, kRecordBytes, z_.used, f) == z_.used;
    if (f != nullptr && std::fclose(f) != 0) ok = false;
    const std::string meta = out_ + ".meta";
    std::FILE *g = std::fopen(meta.c_str(), "w");
    ok = ok && g != nullptr && std::fwrite(meta_.data(), 1, meta_.size(), g) == meta_.size();
    if (g != nullptr && std::fclose(g) != 0) ok = false;
    std::fprintf(stderr, "bc5-direct: experiment 0385 zpass: %u records to %s: %s\n", z_.used, out_.c_str(), ok ? "ok" : "FAILED");
}

void Session::step(std::vector<std::uint32_t> &ib, const full_state::Tracker::Reader &read) {
    if ((jobs_++ & 31) == 0) read_ctl();
    Result res = plan(ib, t_, read, sw_, cfg_, cpu_ != nullptr ? &z_ : nullptr);
    period_.jobs++;
    period_.writers += res.writers.size();
    for (const Writer &w : res.writers) period_.in_cond += w.in_cond ? 1u : 0u;
    for (const indirect_check::Insert &in : res.inserts) period_.words += in.words.size();
    period_.cull += res.cull_barriers;
    period_.htile += res.htile_fills;
    period_.cond += res.cond_exec;
    period_.pred += res.predication;
    period_.nested += res.nested_ibs;
    if (sw_.census && !res.writers.empty() && census_lines_ < 2000) {
        census_lines_++;
        std::size_t in_cond = 0;
        for (const Writer &w : res.writers) in_cond += w.in_cond ? 1 : 0;
        std::fprintf(stderr, "bc5-direct: experiment 0385 census job %llu: %zu lake writers, %zu inside a COND_EXEC; %llu COND_EXEC, %llu predication, %llu nested IBs\n",
                     static_cast<unsigned long long>(jobs_), res.writers.size(), in_cond, static_cast<unsigned long long>(res.cond_exec),
                     static_cast<unsigned long long>(res.predication), static_cast<unsigned long long>(res.nested_ibs));
    }
    char line[96];
    for (const Writer &w : res.writers) {
        if (w.record < 0) continue;
        const int n = std::snprintf(line, sizeof line, "%lld %llu 0x%llx 0x%02x %d %.3f\n", static_cast<long long>(w.record),
                                    static_cast<unsigned long long>(jobs_), static_cast<unsigned long long>(w.ps), w.op, w.in_cond ? 1 : 0, now_ms());
        meta_.append(line, static_cast<std::size_t>(n));
    }
    if (!res.inserts.empty() && !indirect_check::insert_before(ib, res.inserts)) {
        refused_++;
        period_.refused++;
    }
    if (cpu_ != nullptr && z_.used != 0 && !dumped_ && (!sw_.zpass || z_.used >= z_.capacity)) {
        if (++since_end_ >= 200) dump();
    }
}

Result plan(std::span<const std::uint32_t> ib, full_state::Tracker &t, const full_state::Tracker::Reader &read,
            const Switches &s, const Config &c, Zpass *z) {
    Result r;
    full_state::Stats st;
    const auto add = [&r](std::size_t at, std::vector<std::uint32_t> words) {
        if (!words.empty()) r.inserts.push_back({at, std::move(words)});
    };
    const std::uint32_t gcr = gcr_of(s.cache);
    const bool wrap = z != nullptr && s.zpass;
    std::size_t from = 0, cond_end = 0;
    bool first_writer = true, overridden = false, counting = false;
    std::uint32_t saved_override = 0, saved_count = kCountOff;
    // Puts back what the writers' inserts changed, before the first draw that is not a lake writer.
    const auto restore = [&](std::vector<std::uint32_t> &w) {
        if (overridden) context(w, kDbRenderOverride, saved_override);
        if (counting) context(w, kDbCountControl, saved_count);
        overridden = counting = false;
    };
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        const std::uint32_t type = h >> 30;
        std::size_t len = 1;
        if (type == 3 || type == 0) {
            const std::uint32_t n = (h >> 16) & 0x3fffu;
            len = n == 0x3fffu ? 1 : n + 2;
        }
        if (i + len > ib.size()) break;
        const auto op = static_cast<std::uint8_t>((h >> 8) & 0xffu);
        if (type != 3) {
            i += len;
            continue;
        }
        if (op == kOpCondExec) {
            r.cond_exec++;
            if (len == 5) cond_end = std::max(cond_end, i + len + (ib[i + 4] & 0x3fffu));
            if (s.pfp) add(i, {kPfpSyncMe, 0u});
        } else if (op == kOpSetPredication) {
            r.predication++;
        } else if (op == kOpNestedIb) {
            r.nested_ibs++;
        } else if (is_graphics_draw(op)) {
            t.apply(ib.subspan(from, i - from), read, st);
            from = i;
            std::uint32_t base = 0, depth = 0;
            const bool writer = t.get(full_state::Context, kDbZWriteBase, base) && base == c.depth_base &&
                                t.get(full_state::Context, kDbDepthControl, depth) && (depth & 6u) == 6u;
            std::vector<std::uint32_t> before;
            if (!writer) {
                restore(before);
                add(i, std::move(before));
            } else {
                Writer w;
                w.at = i;
                w.op = op;
                w.in_cond = i < cond_end;
                w.ps = program(t, kShPgmLoPs, kShPgmHiPs);
                if (s.idle && first_writer) {
                    event(before, kCsPartialFlush);
                    event(before, kPsPartialFlush);
                }
                if (gcr != 0 && (first_writer || s.cache_each)) acquire(before, gcr);
                if (s.pfp && is_indirect_draw(op)) before.insert(before.end(), {kPfpSyncMe, 0u});
                if (s.nohiz && !overridden) {
                    std::uint32_t v = 0;
                    t.get(full_state::Context, kDbRenderOverride, v);
                    saved_override = v;
                    context(before, kDbRenderOverride, (v & ~kNoHizMask) | kNoHiz);
                    overridden = true;
                }
                if (wrap && z->used < z->capacity) {
                    w.record = z->used++;
                    if (!counting) {
                        std::uint32_t v = kCountOff;
                        t.get(full_state::Context, kDbCountControl, v);
                        saved_count = v;
                        context(before, kDbCountControl, kCountOn);
                        counting = true;
                    }
                    const std::uint64_t va = z->va + static_cast<std::uint64_t>(w.record) * kRecordBytes;
                    zpass_done(before, va);
                    add(i, std::move(before));
                    std::vector<std::uint32_t> after;
                    zpass_done(after, va + 8);
                    add(i + len, std::move(after));
                } else {
                    add(i, std::move(before));
                }
                r.writers.push_back(w);
                first_writer = false;
            }
        } else if (op == kOpDispatchDirect || op == kOpDispatchIndirect) {
            t.apply(ib.subspan(from, i - from), read, st);
            from = i;
            const std::uint64_t pgm = program(t, kShComputePgmLo, kShComputePgmHi);
            std::vector<std::uint32_t> before, after;
            restore(before);
            add(i, std::move(before));
            if (s.cull && std::find(c.cull.begin(), c.cull.end(), pgm) != c.cull.end()) {
                event(after, kCsPartialFlush);
                acquire(after, kGl2Wb | kGl2Inv);
                r.cull_barriers++;
            }
            if (s.dbmeta && pgm == c.htile_fill) {
                event(after, kCsPartialFlush);
                acquire(after, kGl2Wb | kGl2Inv);
                event(after, kDbMeta);
                r.htile_fills++;
            }
            add(i + len, std::move(after));
        }
        i += len;
    }
    t.apply(ib.subspan(from), read, st);
    std::vector<std::uint32_t> tail;
    restore(tail);
    add(ib.size(), std::move(tail));
    std::stable_sort(r.inserts.begin(), r.inserts.end(),
                     [](const indirect_check::Insert &a, const indirect_check::Insert &b) { return a.at < b.at; });
    return r;
}

} // namespace bc5::lake_probe
