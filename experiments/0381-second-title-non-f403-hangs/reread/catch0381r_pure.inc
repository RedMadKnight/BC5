// BC5 exp 0381: the parts of the F687 and F688 catchers that touch nothing but their arguments, so that a test can compile them.
namespace c0381r {
struct Label {
    uint64_t addr = 0;
    uint64_t want = 0;
};
// "1112eae000,0x20000" to addresses; anything else ends the list.
inline std::vector<uint64_t> parse_vas(const char* s) {
    std::vector<uint64_t> out;
    while (s != nullptr && *s != '\0') {
        char*          end = nullptr;
        const uint64_t v   = std::strtoull(s, &end, 16);
        if (end == s) break;
        if (v != 0) out.push_back(v);
        if (*end != ',') break;
        s = end + 1;
    }
    return out;
}
// One line of /proc/self/maps: true when it covers va, with its permissions and the rest of the line after the inode.
inline bool maps_line(const char* line, uint64_t va, std::string* perms, std::string* name) {
    unsigned long long lo = 0, hi = 0;
    char               p[8] = {};
    int                used = 0;
    if (std::sscanf(line, "%llx-%llx %7s %*s %*s %*s %n", &lo, &hi, p, &used) < 3) return false;
    if (va < lo || va >= hi) return false;
    *perms = p;
    *name  = used > 0 ? std::string(line + used) : std::string();
    while (!name->empty() && (name->back() == '\n' || name->back() == '\r')) name->pop_back();
    return true;
}
// The mapping of `have` that covers va, or null. M has va, size.
template <class M>
inline const M* find_mapping(const std::vector<M>& have, uint64_t va) {
    for (const auto& m: have) {
        if (va >= m.va && va - m.va < m.size) return &m;
    }
    return nullptr;
}
// A thread worth a line: asleep in the kernel on something other than its usual idle waits.
inline bool thread_of_note(char state, const char* wchan) {
    if (state == 'D') return true;
    if (state == 'R') return false;
    static const char* const idle[] = {"futex_do_wait", "futex_wait_queue", "ep_poll", "do_nanosleep", "hrtimer_nanosleep", "do_sys_poll",
                                       "poll_schedule_timeout", "do_select", "pipe_read", "unix_stream_read_generic", "0", ""};
    for (const char* w: idle) {
        if (std::strcmp(w, wchan) == 0) return false;
    }
    return true;
}
// How many labels have not reached their value, and the first of them. read(addr, &v) is false when it cannot be read.
template <class R>
inline std::string label_summary(const std::vector<Label>& labels, R read) {
    size_t   open = 0, unread = 0;
    char     first[96] = "";
    for (const auto& l: labels) {
        uint64_t v = 0;
        if (!read(l.addr, &v)) {
            unread++;
            continue;
        }
        if (v == l.want) continue;
        if (open++ == 0) std::snprintf(first, sizeof(first), " first 0x%llx want 0x%llx now 0x%llx", static_cast<unsigned long long>(l.addr),
                                       static_cast<unsigned long long>(l.want), static_cast<unsigned long long>(v));
    }
    char out[160];
    std::snprintf(out, sizeof(out), "labels %zu open %zu unread %zu%s", labels.size(), open, unread, first);
    return out;
}
} // namespace c0381r
