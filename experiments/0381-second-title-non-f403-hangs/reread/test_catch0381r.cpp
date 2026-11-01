// BC5 exp 0381: the catchers' pure parts. Compile with any C++17 compiler and run; it prints "all passed" or the failing line.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>
#include "catch0381r_pure.inc"

static int fails = 0;
#define CHECK(x) do { if (!(x)) { std::printf("FAIL line %d: %s\n", __LINE__, #x); fails++; } } while (0)

struct M {
    uint64_t va, size;
};

int main() {
    using namespace c0381r;
    CHECK(parse_vas(nullptr).empty());
    CHECK(parse_vas("").empty());
    CHECK(parse_vas("1112eae000") == std::vector<uint64_t>{0x1112eae000ull});
    CHECK((parse_vas("0x20,30") == std::vector<uint64_t>{0x20, 0x30}));
    CHECK(parse_vas("zz").empty());

    std::string p, n;
    const char* l = "1110000000-1120000000 rw-s 00000000 00:01 123   /memfd:bc5 (deleted)\n";
    CHECK(maps_line(l, 0x1112eae000ull, &p, &n));
    CHECK(p == "rw-s");
    CHECK(n == "/memfd:bc5 (deleted)");
    CHECK(!maps_line(l, 0x1120000000ull, &p, &n));
    CHECK(maps_line("7f00-8000 r--p 00000000 00:00 0 \n", 0x7f00, &p, &n));
    CHECK(p == "r--p");
    CHECK(n.empty());
    CHECK(!maps_line("garbage\n", 1, &p, &n));

    std::vector<M> have{{0x1000, 0x1000}, {0x5000, 0x2000}};
    CHECK(find_mapping(have, 0x1fff) == &have[0]);
    CHECK(find_mapping(have, 0x2000) == nullptr);
    CHECK(find_mapping(have, 0x6000) == &have[1]);

    CHECK(thread_of_note('D', "futex_do_wait"));
    CHECK(!thread_of_note('S', "futex_do_wait"));
    CHECK(!thread_of_note('R', "0"));
    CHECK(thread_of_note('S', "amdgpu_cs_wait_ioctl"));

    std::map<uint64_t, uint64_t> mem{{0x10, 5}, {0x20, 6}};
    auto read = [&mem](uint64_t a, uint64_t* v) {
        auto it = mem.find(a);
        if (it == mem.end()) return false;
        *v = it->second;
        return true;
    };
    const std::string s = label_summary({{0x10, 5}, {0x20, 7}, {0x30, 1}}, read);
    CHECK(s == "labels 3 open 1 unread 1 first 0x20 want 0x7 now 0x6");
    CHECK(label_summary({}, read) == "labels 0 open 0 unread 0");
    if (fails == 0) std::printf("all passed\n");
    return fails != 0;
}
