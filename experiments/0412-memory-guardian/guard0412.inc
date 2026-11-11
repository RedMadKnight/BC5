// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0412 (tag g412, mkguard0412.py): the memory guardian. The first build's six switches and, since the second
// build (g412b, after the plays of 2026-11-10), BC5_GUARD_CAP_ACT and BC5_GUARD_CAP_NAMES. All default off; unset, empty
// and "0" are off (bc5::env_on, F767), each read once.
//   BC5_GUARD_LEDGER=1             log only: every 10 s what is pinned, per heap name, and what no view covers ("orphans").
//   BC5_GUARD_MLOCK=pinned|guest   pinned: every imported file range is mapped once more, read-only, and mlock()ed, so the
//                                  kernel takes its pages off the reclaim lists (they cannot be freed anyway).
//                                  guest: that, plus mlock2(MLOCK_ONFAULT) on the direct-memory views that are not eager
//                                  (the title's CPU heaps): the guest is not swapped. Needs "ulimit -l unlimited".
//   BC5_GUARD_FILE=random,dontneed with BC5_GUARD_FILE_ROOT=<the game's directory>: open files under it get
//                                  POSIX_FADV_RANDOM (no read-ahead); dontneed drops their page cache under pressure.
//   BC5_GUARD_PSI=<percent>        the pressure threshold (PSI memory "some", avg10) for dontneed and the pressure line;
//                                  10 when dontneed is on and this is unset.
//   BC5_GUARD_PIN_CAP=<MiB>        the cap on what both files have pinned. Alone it only logs: one line each time the pinned
//                                  total passes the cap by 64 MiB more.
//   BC5_GUARD_CAP_ACT=1            the cap acts (needs BC5_GUARD_PIN_CAP): a chunk a sync would import over the cap is put
//                                  off when it is "soft", and every view over it gets the 2 MiB zero buffer instead (the GPU
//                                  reads zeros, its writes are lost), so no access faults. Soft: wanted only for holding data
//                                  or by an eager view whose name is in BC5_GUARD_CAP_NAMES, and not forced by a hint or a
//                                  learned window. Every other chunk is imported as before, cap or not. A put-off chunk is
//                                  imported as soon as the total allows (each full sync asks again).
//   BC5_GUARD_CAP_NAMES=a,b        the eager heaps whose chunks are soft; "AMM" when unset. "-" names none.
//   BC5_GUARD_SPLIT=1              (the third build, g412c) the lazy release (BC5_DIRECT_LAZY_RELEASE, exp 0401 e7) may cut
//                                  orphan chunks out of a BO that keeps other chunks although BC5_DIRECT_ALIASES is set.
//                                  Without it such a BO only goes whole, and with BOs merged up to 1 GiB that is almost
//                                  never (night arm a2orphans: 194 MiB of orphans idle, 0 cut, "3 not split (aliases)").
//                                  The reason for the rule was that freeing the old BO drops its alias mappings until the
//                                  next aliases_apply (at most once a second); with this switch the sync that made cuts
//                                  ends with aliases_apply(true), before any submission can use them.
//   BC5_GUARD_APPLY_MIN_MS=<ms>    learned_apply runs at most once per <ms> (1..1000) while the layout keeps changing; the
//                                  first call after a device reopen is never put off.
//   BC5_GUARD_FORGET=<s>           (the fourth build, g412d) a chunk that a hint or a learned window forced and that has been
//                                  under no view for <s> seconds (1..3600) leaves the forced set, so the lazy release can
//                                  cut it. Night arm z1zscan: 264 MiB "forced and under no view" after 300 s and rising,
//                                  the larger part of the orphans. A chunk under no view has no GPU mapping. A learned
//                                  window forces its chunks again at the next learned_apply once a view is back; a hint
//                                  window does not (it is mapped once), so a view of a heap that is not eager, back at the
//                                  same file range and written only by the GPU, would fault once and be learned.
// With all of them off nothing here runs: no thread, one config read, one early return per import and per submission.
// The text between G412_PURE_BEGIN and G412_PURE_END has no system call and is what test0412.cpp runs on the laptop.
// G412_PURE_BEGIN
namespace g412 {

struct Cfg {
    bool        ledger = false;
    int         mlock = 0; // 0 off, 1 pinned, 2 guest (and pinned)
    bool        f_random = false, f_dontneed = false;
    std::string root;
    double      psi = 0.0;      // percent; 0 = off
    uint64_t    cap = 0;        // bytes; 0 = off
    uint64_t    apply_ns = 0;   // 0 = off
    bool        cap_act = false; // the cap puts soft chunks off
    std::vector<std::string> cap_names; // eager heaps whose chunks are soft
    std::string bad;            // switches whose value was not understood (they stay off)
    bool worker() const { return ledger || mlock != 0 || f_random || f_dontneed || psi > 0.0 || cap != 0; }
};

static Cfg parse(const char* ledger, const char* mlock, const char* file, const char* root, const char* psi, const char* cap, const char* apply,
                 const char* cap_act = nullptr, const char* cap_names = nullptr) {
    Cfg c;
    c.ledger = bc5::env_on(ledger);
    if (bc5::env_on(mlock)) {
        const std::string v = mlock;
        if (v == "pinned" || v == "1") c.mlock = 1;
        else if (v == "guest") c.mlock = 2;
        else c.bad += " BC5_GUARD_MLOCK";
    }
    if (bc5::env_on(file)) {
        std::string v = file;
        bool        ok = true;
        size_t      at = 0;
        while (at <= v.size()) {
            const size_t      e = std::min(v.find(',', at), v.size());
            const std::string w = v.substr(at, e - at);
            if (w == "random") c.f_random = true;
            else if (w == "dontneed") c.f_dontneed = true;
            else ok = false;
            at = e + 1;
        }
        if (root == nullptr || root[0] != '/' || root[1] == 0) ok = false; // a root is required, and "/" is refused
        if (!ok) {
            c.f_random = c.f_dontneed = false;
            c.bad += " BC5_GUARD_FILE";
        } else {
            c.root = root;
            if (c.root.back() != '/') c.root += '/';
        }
    }
    if (bc5::env_on(psi)) {
        char*        end = nullptr;
        const double v = std::strtod(psi, &end);
        if (end != psi && *end == 0 && v > 0.0 && v <= 100.0) c.psi = v;
        else c.bad += " BC5_GUARD_PSI";
    }
    if (c.f_dontneed && c.psi == 0.0) c.psi = 10.0;
    if (bc5::env_on(cap)) {
        char*                    end = nullptr;
        const unsigned long long v = std::strtoull(cap, &end, 10);
        if (end != cap && *end == 0 && v >= 1024 && v <= 65536) c.cap = static_cast<uint64_t>(v) << 20u;
        else c.bad += " BC5_GUARD_PIN_CAP";
    }
    if (bc5::env_on(apply)) {
        char*                    end = nullptr;
        const unsigned long long v = std::strtoull(apply, &end, 10);
        if (end != apply && *end == 0 && v >= 1 && v <= 1000) c.apply_ns = static_cast<uint64_t>(v) * 1'000'000ull;
        else c.bad += " BC5_GUARD_APPLY_MIN_MS";
    }
    if (bc5::env_on(cap_act)) {
        if (c.cap != 0 && std::strcmp(cap_act, "1") == 0) c.cap_act = true;
        else c.bad += " BC5_GUARD_CAP_ACT";
    }
    if (c.cap_act) {
        const std::string v = bc5::env_on(cap_names) ? cap_names : "AMM";
        size_t            at = 0;
        while (at <= v.size()) {
            const size_t      e = std::min(v.find(',', at), v.size());
            const std::string w = v.substr(at, e - at);
            if (!w.empty() && w != "-") c.cap_names.push_back(w);
            at = e + 1;
        }
    }
    return c;
}

static bool cap_name(const Cfg& c, const std::string& name) {
    return std::find(c.cap_names.begin(), c.cap_names.end(), name) != c.cap_names.end();
}

// BC5_GUARD_CAP_ACT: which of the chunks a sync wants are imported. need: the chunk offsets, sorted and unique; soft[i]
// says whether need[i] may be put off; pinned: the bytes both files have pinned now. A hard chunk is always kept. Soft
// chunks are kept in order while the total, with every hard chunk counted first, stays within the cap.
struct CapPlan {
    std::vector<uint64_t> keep, off; // both sorted
    uint64_t              hard = 0;  // hard chunks kept
};
static CapPlan cap_plan(const std::vector<uint64_t>& need, const std::vector<char>& soft, uint64_t pinned, uint64_t cap, uint64_t chunk) {
    CapPlan  p;
    uint64_t total = pinned;
    for (size_t i = 0; i < need.size(); i++) {
        if (i >= soft.size() || soft[i] == 0) total += chunk, p.hard++;
    }
    for (size_t i = 0; i < need.size(); i++) {
        const bool s = i < soft.size() && soft[i] != 0;
        if (!s) {
            p.keep.push_back(need[i]);
        } else if (total + chunk <= cap) {
            total += chunk;
            p.keep.push_back(need[i]);
        } else {
            p.off.push_back(need[i]);
        }
    }
    return p;
}

// A set of disjoint [lo, hi) ranges; touching ranges are joined.
struct Ranges {
    std::map<uint64_t, uint64_t> m;
    uint64_t                     bytes = 0;
    // Adds [lo, hi) and returns the parts that were not in the set yet.
    std::vector<std::pair<uint64_t, uint64_t>> add(uint64_t lo, uint64_t hi) {
        std::vector<std::pair<uint64_t, uint64_t>> fresh;
        if (lo >= hi) return fresh;
        auto it = m.upper_bound(lo);
        if (it != m.begin()) {
            auto p = std::prev(it);
            if (p->second >= lo) it = p;
        }
        uint64_t cur = lo, nlo = lo, nhi = hi;
        while (it != m.end() && it->first <= hi) {
            if (it->first > cur) fresh.emplace_back(cur, it->first);
            cur = std::max(cur, it->second);
            nlo = std::min(nlo, it->first);
            nhi = std::max(nhi, it->second);
            it  = m.erase(it);
        }
        if (cur < hi) fresh.emplace_back(cur, hi);
        m[nlo] = nhi;
        for (const auto& f: fresh) bytes += f.second - f.first;
        return fresh;
    }
    uint64_t overlap(uint64_t lo, uint64_t hi) const {
        uint64_t n = 0;
        auto     it = m.upper_bound(lo);
        if (it != m.begin()) --it;
        for (; it != m.end() && it->first < hi; ++it) {
            const uint64_t a = std::max(lo, it->first), b = std::min(hi, it->second);
            if (b > a) n += b - a;
        }
        return n;
    }
};

struct VIn {
    uint64_t           off, size;
    const std::string* name;
    bool               eager, lazy;
};
struct Row {
    std::string name;
    char        cls = 'D'; // E eager, L lazy, D by data
    uint64_t    reserved = 0, pinned = 0;
    uint32_t    views = 0;
};
struct Ledger {
    std::vector<Row> rows; // by pinned bytes, largest first; views of one name may share file ranges, so rows can sum past the total
    uint64_t         pinned = 0, reserved_union = 0, pinned_under = 0, orphans = 0;
    size_t           views = 0;
};

static Ledger ledger(const std::vector<VIn>& v, const Ranges& pinned) {
    Ledger                                     L;
    std::map<std::string, size_t>              idx;
    std::vector<std::pair<uint64_t, uint64_t>> spans;
    spans.reserve(v.size());
    for (const auto& x: v) {
        if (x.size == 0) continue;
        const char  cls = x.eager ? 'E' : x.lazy ? 'L' : 'D';
        std::string key = *x.name;
        key += cls;
        auto [it, fresh] = idx.try_emplace(key, L.rows.size());
        if (fresh) {
            L.rows.emplace_back();
            L.rows.back().name = x.name->empty() ? "(unnamed)" : *x.name;
            L.rows.back().cls  = cls;
        }
        Row& r = L.rows[it->second];
        r.reserved += x.size;
        r.pinned += pinned.overlap(x.off, x.off + x.size);
        r.views++;
        spans.emplace_back(x.off, x.off + x.size);
        L.views++;
    }
    std::sort(spans.begin(), spans.end());
    uint64_t lo = 0, hi = 0;
    bool     have = false;
    auto     flush = [&] {
        if (!have) return;
        L.reserved_union += hi - lo;
        L.pinned_under += pinned.overlap(lo, hi);
    };
    for (const auto& s: spans) {
        if (have && s.first <= hi) {
            hi = std::max(hi, s.second);
            continue;
        }
        flush();
        lo = s.first, hi = s.second, have = true;
    }
    flush();
    L.pinned  = pinned.bytes;
    L.orphans = L.pinned - L.pinned_under;
    std::stable_sort(L.rows.begin(), L.rows.end(), [](const Row& a, const Row& b) { return a.pinned > b.pinned; });
    return L;
}

// "name[E] pinned/reserved" in whole MiB for the first `top` rows, then the rest as one entry. At most `room` characters.
static std::string heaps_text(const Ledger& L, size_t top, size_t room) {
    std::string out;
    uint64_t    rp = 0, rr = 0;
    size_t      rest = 0;
    for (size_t i = 0; i < L.rows.size(); i++) {
        const Row& r = L.rows[i];
        char       b[96];
        std::snprintf(b, sizeof(b), "%s%.28s[%c] %" PRIu64 "/%" PRIu64, out.empty() ? "" : ", ", r.name.c_str(), r.cls, r.pinned >> 20u, r.reserved >> 20u);
        if (i < top && out.size() + std::strlen(b) + 40 <= room) {
            out += b;
        } else {
            rp += r.pinned, rr += r.reserved, rest++;
        }
    }
    if (rest != 0) {
        char b[96];
        std::snprintf(b, sizeof(b), "%s%zu more %" PRIu64 "/%" PRIu64, out.empty() ? "" : ", ", rest, rp >> 20u, rr >> 20u);
        out += b;
    }
    return out;
}

// /proc/pressure/memory: "some avg10=1.23 ..." and "full avg10=0.45 ...". False when either is missing.
static bool psi_parse(const char* text, double* some10, double* full10) {
    if (text == nullptr) return false;
    const char* s = std::strstr(text, "some avg10=");
    const char* f = std::strstr(text, "full avg10=");
    if (s == nullptr || f == nullptr) return false;
    char*        e1 = nullptr;
    char*        e2 = nullptr;
    const double a = std::strtod(s + 11, &e1), b = std::strtod(f + 11, &e2);
    if (e1 == s + 11 || e2 == f + 11) return false;
    *some10 = a, *full10 = b;
    return true;
}

// "Key:   123 kB" at a line start -> MiB; -1 when the key is missing or has no number (never 0 for "unknown").
static long kv_mib(const char* text, const char* key) {
    if (text == nullptr) return -1;
    const size_t n = std::strlen(key);
    for (const char* p = text; p != nullptr && *p != 0;) {
        if (std::strncmp(p, key, n) == 0 && p[n] == ':') {
            char*           end = nullptr;
            const long long v = std::strtoll(p + n + 1, &end, 10);
            if (end == p + n + 1 || v < 0) return -1;
            return static_cast<long>(v >> 10);
        }
        p = std::strchr(p, '\n');
        if (p != nullptr) p++;
    }
    return -1;
}

// /proc/self/stat: the faults so far (fields 10 and 12, counted after the last ')').
static bool stat_faults(const char* text, unsigned long long* minflt, unsigned long long* majflt) {
    if (text == nullptr) return false;
    const char* p = std::strrchr(text, ')');
    if (p == nullptr) return false;
    p++;
    unsigned long long v[10] = {};
    int                k = 0;
    while (k < 10) { // v[0] is field 3 (the state), v[7] field 10, v[9] field 12
        while (*p == ' ') p++;
        if (*p == 0) return false;
        char* end = nullptr;
        v[k]      = k == 0 ? 0 : std::strtoull(p, &end, 10);
        if (k == 0) {
            while (*p != 0 && *p != ' ') p++;
        } else {
            if (end == p) return false;
            p = end;
        }
        k++;
    }
    *minflt = v[7], *majflt = v[9];
    return true;
}

// BC5_GUARD_FORGET: the forced chunks under no view of `cov` for idle_ns leave `forced`; `since` remembers when each was
// first seen so. Returns how many left.
static size_t forget_step(std::set<uint64_t>& forced, const Ranges& cov, std::map<uint64_t, uint64_t>& since, uint64_t now, uint64_t idle_ns, uint64_t chunk) {
    size_t n = 0;
    for (auto it = forced.begin(); it != forced.end();) {
        const uint64_t c = *it;
        if (cov.overlap(c, c + chunk) != 0) {
            since.erase(c);
            ++it;
            continue;
        }
        const auto s = since.try_emplace(c, now).first;
        if (now - s->second >= idle_ns) {
            since.erase(s);
            it = forced.erase(it);
            n++;
        } else {
            ++it;
        }
    }
    for (auto it = since.begin(); it != since.end();) { // chunks that left the forced set some other way
        if (forced.count(it->first) == 0) it = since.erase(it);
        else ++it;
    }
    return n;
}

// BC5_GUARD_APPLY_MIN_MS: true when this learned_apply call is put off.
struct Defer {
    uint64_t last_gen = 0, last_ns = 0, last_reopens = 0, deferred = 0;
    bool     seen = false;
};
static bool defer(Defer& d, uint64_t min_ns, uint64_t gen, uint64_t now, uint64_t reopens) {
    if (min_ns == 0) return false;
    if (d.seen && gen == d.last_gen && reopens == d.last_reopens) return false; // learned_apply returns at once by itself
    if (!d.seen || reopens != d.last_reopens || now - d.last_ns >= min_ns) {
        d.seen = true, d.last_gen = gen, d.last_ns = now, d.last_reopens = reopens;
        return false;
    }
    d.deferred++;
    return true;
}

} // namespace g412
// G412_PURE_END

#if !defined(GUARD0412_TEST)
namespace g412 {

static const Cfg& cfg() {
    static const Cfg c = parse(std::getenv("BC5_GUARD_LEDGER"), std::getenv("BC5_GUARD_MLOCK"), std::getenv("BC5_GUARD_FILE"), std::getenv("BC5_GUARD_FILE_ROOT"),
                               std::getenv("BC5_GUARD_PSI"), std::getenv("BC5_GUARD_PIN_CAP"), std::getenv("BC5_GUARD_APPLY_MIN_MS"),
                               std::getenv("BC5_GUARD_CAP_ACT"), std::getenv("BC5_GUARD_CAP_NAMES"));
    return c;
}

struct Req {
    int      kind, fd;
    uint64_t lo, hi;
};
struct State {
    std::mutex            m; // pinned and q
    Ranges                pinned[2];
    std::deque<Req>       q;
    std::atomic<bool>     started {false};
    std::atomic<uint64_t> deferred {0};
    std::mutex            dm; // d
    Defer                 d;
    // What the last full sync left imported (guard0412_synced): the direct file's BOs, and each file's bytes. The lazy
    // release (exp 0401 e7) cuts chunks out again, so `pinned` above, which only grows, is not the pinned set.
    std::vector<std::pair<uint64_t, uint64_t>> bos0; // under m: off and size
    bool                  bos0_seen = false;         // under m
    std::atomic<uint64_t> bytes[2] {};
    std::atomic<uint64_t> cap_off {0}, cap_off_max {0}, cap_changes {0}, cap_hard {0}; // bytes put off now and at most; changes of the set; hard chunks imported over the cap
};
static State& st() {
    static State s;
    return s;
}

static uint64_t mono_ns() {
    return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());
}

static bool slurp(const char* path, char* buf, size_t cap) {
    FILE* f = std::fopen(path, "r");
    if (f == nullptr) return false;
    const size_t n = std::fread(buf, 1, cap - 1, f);
    std::fclose(f);
    buf[n] = 0;
    return n != 0;
}

struct Worker {
    const Cfg& c = cfg();
    bool       lock_ok = false; // RLIMIT_MEMLOCK is unlimited
    bool       lock_dead = false;
    uint64_t   locked = 0, lock_calls = 0, guest_calls = 0, guest_fail = 0;
    const void* guest_seen = nullptr; // the views snapshot the guest pass last worked on
    std::map<int, uint64_t> fd_ino;   // fds under the root that have their advice
    uint64_t   advised = 0, dropped = 0, drops = 0, last_drop_ns = 0, last_psi_line_ns = 0, cap_step = 0;
    unsigned long long minflt0 = 0, majflt0 = 0;
    bool       flt_seen = false;
    uint64_t   t0 = mono_ns();

    void lock_ranges() {
        std::deque<Req> q;
        {
            std::lock_guard l(st().m);
            q.swap(st().q);
        }
        if (c.mlock == 0 || !lock_ok || lock_dead) return;
        for (const Req& r: q) {
            static constexpr uint64_t step = 64ull << 20u; // one mlock call at a time, so no long hold of the address space
            for (uint64_t lo = r.lo; lo < r.hi && !lock_dead; lo += step) {
                const uint64_t n = std::min(step, r.hi - lo);
                void*          p = ::mmap(nullptr, n, PROT_READ, MAP_SHARED, r.fd, static_cast<off_t>(lo));
                if (p == MAP_FAILED) {
                    lock_dead = true;
                    journal("guard: mmap of %s 0x%" PRIx64 "+0x%" PRIx64 " failed (errno %d); BC5_GUARD_MLOCK stops\n", r.kind == 0 ? "direct" : "private", lo, n, errno);
                    break;
                }
                if (::mlock(p, n) != 0) {
                    const int e = errno;
                    ::munmap(p, n);
                    lock_dead = true;
                    journal("guard: mlock of %s 0x%" PRIx64 "+0x%" PRIx64 " failed (errno %d); BC5_GUARD_MLOCK stops, %.1f MiB stay locked\n", r.kind == 0 ? "direct" : "private",
                            lo, n, e, static_cast<double>(locked) / 1048576.0);
                    break;
                }
                locked += n;
                lock_calls++;
            }
        }
    }

    // BC5_GUARD_MLOCK=guest: the direct-memory views that are not eager are locked as their pages come (MLOCK_ONFAULT).
    void lock_guest() {
        if (c.mlock != 2 || !lock_ok || lock_dead) return;
        const auto views = direct_views(g_d[0]);
        if (views.get() == guest_seen) return;
        guest_seen = views.get();
        uint32_t calls = 0;
        for (const auto& v: views->v) {
            if (v.eager || v.size == 0) continue;
            if (calls++ >= 4096) break;
            guest_calls++;
            if (::mlock2(reinterpret_cast<void*>(v.va), v.size, MLOCK_ONFAULT) != 0) guest_fail++; // ENOMEM: the title unmapped it meanwhile
        }
    }

    // The open files under the root: advice once per file, and the list for a drop.
    void files(bool drop, double some10) {
        if (!c.f_random && !c.f_dontneed) return;
        std::vector<int> under;
        for (int fd = 3; fd < 4096; fd++) {
            char link[40], path[512];
            std::snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
            const ssize_t n = ::readlink(link, path, sizeof(path) - 1);
            if (n <= 0) continue;
            path[n] = 0;
            if (std::strncmp(path, c.root.c_str(), c.root.size()) != 0) continue;
            struct stat sb {};
            if (::fstat(fd, &sb) != 0 || !S_ISREG(sb.st_mode)) continue;
            under.push_back(fd);
            if (!c.f_random) continue;
            auto it = fd_ino.find(fd);
            if (it != fd_ino.end() && it->second == static_cast<uint64_t>(sb.st_ino)) continue;
            if (::posix_fadvise(fd, 0, 0, POSIX_FADV_RANDOM) == 0) advised++;
            fd_ino[fd] = static_cast<uint64_t>(sb.st_ino);
        }
        if (!drop || !c.f_dontneed) return;
        uint32_t n = 0;
        for (const int fd: under) {
            if (::posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED) == 0) n++;
        }
        dropped += n;
        drops++;
        journal("guard: psi some %.1f >= %.1f: the page cache of %u open game files dropped (drop %" PRIu64 ")\n", some10, c.psi, n, drops);
    }

    void line(bool psi_ok, double some10, double full10) {
        Ranges pin0;
        uint64_t pin1 = 0;
        {
            std::lock_guard l(st().m);
            if (st().bos0_seen) {
                for (const auto& b: st().bos0) pin0.add(b.first, b.first + b.second);
                pin1 = st().bytes[1].load();
            } else {
                pin0 = st().pinned[0];
                pin1 = st().pinned[1].bytes;
            }
        }
        const auto       views = direct_views(g_d[0]);
        std::vector<VIn> in;
        in.reserve(views->v.size());
        for (const auto& v: views->v) in.push_back({v.off, v.size, &v.name, v.eager, v.lazy});
        const Ledger L = ledger(in, pin0);
        char status[4096], pstat[1024], mem[8192], cg[64];
        const bool   cg_ok = slurp("/sys/fs/cgroup/memory.current", cg, sizeof(cg));
        const bool   s_ok = slurp("/proc/self/status", status, sizeof(status));
        const bool   m_ok = slurp("/proc/meminfo", mem, sizeof(mem));
        unsigned long long mn = 0, mj = 0;
        const bool   f_ok = slurp("/proc/self/stat", pstat, sizeof(pstat)) && stat_faults(pstat, &mn, &mj);
        if (f_ok && !flt_seen) minflt0 = mn, majflt0 = mj, flt_seen = true;
        const double mib = 1048576.0;
        const long   swt = m_ok ? kv_mib(mem, "SwapTotal") : -1, swf = m_ok ? kv_mib(mem, "SwapFree") : -1;
        journal("guard: t %.0f s: pinned direct %.1f MiB, private %.1f; under a view %.1f, orphans %.1f; views %zu over %.1f MiB; gtt %.1f; rss %ld shmem %ld swap %ld MiB; "
                "faults minor %lld major %lld; avail %ld unevictable %ld mlocked %ld swap used %ld MiB; psi some %.1f full %.1f%s; guard locked %.1f MiB, guest views %" PRIu64
                " (%" PRIu64 " refused); files advised %" PRIu64 ", drops %" PRIu64 "; apply put off %" PRIu64 "; rss anon %ld; cgroup %ld MiB; cap put off %.1f MiB (max %.1f, %" PRIu64
                " changes, %" PRIu64 " hard chunks over)\n",
                static_cast<double>(mono_ns() - t0) / 1e9, static_cast<double>(L.pinned) / mib, static_cast<double>(pin1) / mib, static_cast<double>(L.pinned_under) / mib,
                static_cast<double>(L.orphans) / mib, L.views, static_cast<double>(L.reserved_union) / mib, static_cast<double>(direct_gtt("mem_info_gtt_used")) / mib,
                s_ok ? kv_mib(status, "VmRSS") : -1, s_ok ? kv_mib(status, "RssShmem") : -1, s_ok ? kv_mib(status, "VmSwap") : -1,
                f_ok ? static_cast<long long>(mn - minflt0) : -1ll, f_ok ? static_cast<long long>(mj - majflt0) : -1ll, m_ok ? kv_mib(mem, "MemAvailable") : -1,
                m_ok ? kv_mib(mem, "Unevictable") : -1, m_ok ? kv_mib(mem, "Mlocked") : -1, swt >= 0 && swf >= 0 ? swt - swf : -1, psi_ok ? some10 : -1.0, psi_ok ? full10 : -1.0,
                psi_ok ? "" : " (unread)", static_cast<double>(locked) / mib, guest_calls, guest_fail, advised, drops, st().deferred.load(), s_ok ? kv_mib(status, "RssAnon") : -1,
                cg_ok ? static_cast<long>(std::strtoll(cg, nullptr, 10) >> 20) : -1, static_cast<double>(st().cap_off.load()) / mib, static_cast<double>(st().cap_off_max.load()) / mib,
                st().cap_changes.load(), st().cap_hard.load());
        journal("guard heaps (pinned/reserved MiB; E eager, L lazy, D by data): %s\n", heaps_text(L, 12, 760).c_str());
    }

    void run() {
        pthread_setname_np(pthread_self(), "bc5-guard");
        (void)::setpriority(PRIO_PROCESS, static_cast<id_t>(::gettid()), 10);
        struct rlimit rl {};
        const bool    rl_ok = ::getrlimit(RLIMIT_MEMLOCK, &rl) == 0;
        lock_ok = rl_ok && rl.rlim_cur == RLIM_INFINITY;
        journal("guard: switches: LEDGER %s, MLOCK %s, FILE %s%s%s%s, PSI %.1f, PIN_CAP %" PRIu64 " MiB (%s), APPLY_MIN_MS %" PRIu64 "%s%s; memlock limit %s (exp 0412, tag g412b)\n",
                c.ledger ? "on" : "off", c.mlock == 2 ? "guest" : c.mlock == 1 ? "pinned" : "off", c.f_random ? "random" : "", c.f_random && c.f_dontneed ? "," : "",
                c.f_dontneed ? "dontneed" : "", c.f_random || c.f_dontneed ? "" : "off", c.psi, c.cap >> 20u, c.cap_act ? "acts" : "log only", static_cast<uint64_t>(c.apply_ns / 1'000'000ull), c.bad.empty() ? "" : "; not understood, off:",
                c.bad.c_str(), !rl_ok ? "unread" : lock_ok ? "unlimited" : "limited");
        if (c.mlock != 0 && !lock_ok) journal("guard: BC5_GUARD_MLOCK needs \"ulimit -l unlimited\" in the launcher; nothing is locked in this run\n");
        for (uint64_t tick = 1;; tick++) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            lock_ranges();
            char         ps[512];
            double       some10 = 0.0, full10 = 0.0;
            const bool   want_psi = c.psi > 0.0 || (c.ledger && tick % 10 == 0);
            const bool   psi_ok = want_psi && slurp("/proc/pressure/memory", ps, sizeof(ps)) && psi_parse(ps, &some10, &full10);
            const uint64_t now = mono_ns();
            const bool   over = c.psi > 0.0 && psi_ok && some10 >= c.psi;
            const bool   drop = over && c.f_dontneed && now - last_drop_ns >= 5'000'000'000ull;
            if (drop) last_drop_ns = now;
            if (drop || tick % 5 == 0) files(drop, some10);
            if (over && !c.f_dontneed && now - last_psi_line_ns >= 10'000'000'000ull) {
                last_psi_line_ns = now;
                journal("guard: psi some %.1f >= %.1f (full %.1f)\n", some10, c.psi, full10);
            }
            if (tick % 10 != 0) continue;
            lock_guest();
            if (c.ledger) line(psi_ok, some10, full10);
            if (c.cap != 0) {
                uint64_t pinned = st().bytes[0].load() + st().bytes[1].load();
                if (pinned == 0) {
                    std::lock_guard l(st().m);
                    pinned = st().pinned[0].bytes + st().pinned[1].bytes;
                }
                const uint64_t step = pinned > c.cap ? (pinned - c.cap) / (64ull << 20u) + 1 : 0;
                if (step > cap_step) journal("guard: pinned %.1f MiB is over BC5_GUARD_PIN_CAP %" PRIu64 " MiB (%s)\n", static_cast<double>(pinned) / 1048576.0, c.cap >> 20u,
                                             c.cap_act ? "soft chunks are put off; the rest is hard" : "log only");
                cap_step = step;
            }
        }
    }
};

} // namespace g412

// The import loop's hook: [off, off + size) of the file behind `kind` (0 direct, 1 private) is imported, so pinned.
static void guard0412_imported(int kind, int fd, uint64_t off, uint64_t size) {
    const g412::Cfg& c = g412::cfg();
    if (!c.worker() || kind < 0 || kind > 1 || fd < 0 || size == 0) return;
    g412::State& s = g412::st();
    {
        std::lock_guard l(s.m);
        for (const auto& f: s.pinned[kind].add(off, off + size)) {
            if (c.mlock != 0) s.q.push_back({kind, fd, f.first, f.second});
        }
    }
    if (!s.started.exchange(true)) {
        std::thread([] {
            static g412::Worker w;
            w.run();
        }).detach();
    }
}

// The submission path's hook: true when learned_apply is put off (BC5_GUARD_APPLY_MIN_MS).
static bool guard0412_defer_apply() {
    const g412::Cfg& c = g412::cfg();
    if (c.apply_ns == 0) return false;
    g412::State&    s = g412::st();
    static std::atomic<bool> said {false};
    if (!said.exchange(true)) journal("guard: BC5_GUARD_APPLY_MIN_MS %" PRIu64 ": learned_apply at most once per that while the layout changes (exp 0412, tag g412)\n", static_cast<uint64_t>(c.apply_ns / 1'000'000ull));
    std::lock_guard l(s.dm);
    const bool      put_off = g412::defer(s.d, c.apply_ns, static_cast<uint64_t>(g_layout_gen), g412::mono_ns(), g_m11_reopens.load());
    if (put_off) s.deferred++;
    return put_off;
}

// BC5_GUARD_SPLIT (g412c).
static bool guard0412_split() {
    static const bool on = bc5::env_on(std::getenv("BC5_GUARD_SPLIT"));
    return on;
}
// The end of a sync whose lazy release made cuts: the aliases of the retired BOs are gone (Device::free_shared drops
// them), so they are mapped again now and not at the next submission's rate-limited aliases_apply.
static void guard0412_after_cuts(size_t cuts) {
    if (cuts == 0 || !guard0412_split()) return;
    aliases_apply(true);
    static std::atomic<uint64_t> n {0};
    if (const uint64_t k = n++; k < 8 || (k & 255u) == 0) journal("guard split: %zu BOs cut in this sync; aliases mapped again at once (%" PRIu64 " such syncs)\n", cuts, k + 1);
}

// BC5_GUARD_FORGET (g412d): at the start of a full sync of the direct file, at most every 2 s.
static void guard0412_forget(DState& S, const std::vector<DView>& views, uint64_t sig, uint64_t now) {
    static const uint64_t idle = []() -> uint64_t {
        const char* e = std::getenv("BC5_GUARD_FORGET");
        if (!bc5::env_on(e)) return uint64_t {0};
        char*                    end = nullptr;
        const unsigned long long v = std::strtoull(e, &end, 10);
        return end != e && *end == 0 && v >= 1 && v <= 3600 ? static_cast<uint64_t>(v) * 1'000'000'000ull : uint64_t {0};
    }();
    if (idle == 0 || S.kind != 0 || S.forced.empty()) return;
    static uint64_t last = 0;
    if (now - last < 2'000'000'000ull) return;
    last = now;
    static g412::Ranges cov;
    static uint64_t     cov_sig = 0;
    static bool         cov_ok = false;
    if (!cov_ok || cov_sig != sig) {
        cov = g412::Ranges {};
        for (const auto& v: views) cov.add(v.off, v.off + v.size);
        cov_sig = sig;
        cov_ok = true;
    }
    static std::map<uint64_t, uint64_t> since;
    static uint64_t                     total = 0, lines = 0;
    const size_t                        n = g412::forget_step(S.forced, cov, since, now, idle, kDChunk);
    if (n == 0) return;
    S.forced_seen = S.forced.size();
    total += n;
    if (lines++ < 16 || (lines & 63u) == 0) {
        journal("guard forget: %zu forced chunks under no view for %" PRIu64 " s left the forced set (%" PRIu64 " so far, %zu still forced, %zu waiting)\n", n,
                idle / 1'000'000'000ull, total, S.forced.size(), since.size());
    }
}

// BC5_GUARD_CAP_ACT. The chunks of the direct file the cap has put off, sorted; the sync thread's own.
static std::vector<uint64_t> g_g412_off;
static bool                  g_g412_off_changed = false;

// After the import loop's list is made: takes the soft chunks out of `need` that do not fit under the cap.
static void guard0412_cap(DState& S, const std::vector<DView>& views, std::vector<uint64_t>& need) {
    const g412::Cfg& c = g412::cfg();
    if (!c.cap_act || S.kind != 0) return;
    std::vector<char> soft(need.size(), 1);
    if (!need.empty()) {
        for (size_t i = 0; i < need.size(); i++) {
            if (S.forced.count(need[i]) != 0) soft[i] = 0;
        }
        for (const auto& v: views) {
            if (!v.eager || v.size == 0 || g412::cap_name(c, v.name)) continue; // a hard heap: its chunks are never put off
            auto it = std::lower_bound(need.begin(), need.end(), v.off & ~(kDChunk - 1));
            for (; it != need.end() && *it < v.off + v.size; ++it) soft[static_cast<size_t>(it - need.begin())] = 0;
        }
    }
    const uint64_t pinned = g_d[0].bytes + g_d[1].bytes;
    g412::CapPlan  p = g412::cap_plan(need, soft, pinned, c.cap, kDChunk);
    g412::State&   s = g412::st();
    if (p.hard != 0 && pinned + p.hard * kDChunk > c.cap) s.cap_hard += p.hard;
    if (p.off != g_g412_off) {
        g_g412_off_changed = true;
        const uint64_t bytes = p.off.size() * kDChunk, n = s.cap_changes++;
        s.cap_off = bytes;
        if (bytes > s.cap_off_max.load()) s.cap_off_max = bytes;
        if (n < 16 || (n & 63u) == 0) {
            journal("guard cap: %.1f MiB pinned, cap %" PRIu64 " MiB: %zu chunks (%.1f MiB) put off, the zero buffer under their views; %" PRIu64 " hard chunks imported "
                    "now (change %" PRIu64 ")\n",
                    static_cast<double>(pinned) / 1048576.0, c.cap >> 20u, p.off.size(), static_cast<double>(bytes) / 1048576.0, p.hard, n + 1);
        }
        g_g412_off.swap(p.off);
    }
    need.swap(p.keep);
}

// True when the put-off set changed since the mappings were last built: the GPU is drained and the mappings rebuilt.
static bool guard0412_cap_changed(const DState& S) {
    return S.kind == 0 && g_g412_off_changed;
}

// The mapping rebuild's hook: every (view, put-off chunk) intersection is one mapping of the zero buffer.
static void guard0412_want(const DState& S, const std::vector<DView>& views, std::vector<DMap>& want) {
    if (S.kind != 0) return;
    g_g412_off_changed = false;
    if (g_g412_off.empty()) return;
    const uint32_t id = scratch_bo();
    if (id == 0) {
        static bool said = false;
        if (!said) journal("guard cap: no zero buffer: the put-off chunks have no mapping (an access faults)\n");
        said = true;
        return;
    }
    for (const auto& v: views) {
        const uint64_t vend = v.off + v.size;
        auto           it = std::lower_bound(g_g412_off.begin(), g_g412_off.end(), v.off & ~(kDChunk - 1));
        for (; it != g_g412_off.end() && *it < vend; ++it) {
            const uint64_t lo = *it > v.off ? *it : v.off;
            const uint64_t hi = *it + kDChunk < vend ? *it + kDChunk : vend;
            if (lo < hi) want.push_back({v.va + (lo - v.off), hi - lo, lo - *it, id});
        }
    }
}

// The end of a full sync: what is imported now, for the ledger and the cap's log line.
static void guard0412_synced(const DState& S) {
    const g412::Cfg& c = g412::cfg();
    if (!c.worker() || S.kind < 0 || S.kind > 1) return;
    g412::State& s = g412::st();
    s.bytes[S.kind] = S.bytes;
    if (S.kind != 0 || !c.ledger) return;
    std::lock_guard l(s.m);
    s.bos0.clear();
    s.bos0.reserve(S.bos.size());
    for (const auto& b: S.bos) s.bos0.emplace_back(b.off, b.size);
    s.bos0_seen = true;
}
#endif // !GUARD0412_TEST
