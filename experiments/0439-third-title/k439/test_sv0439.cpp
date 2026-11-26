// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag sv439): det test of sv0439.hpp, the system software version switch: parsing and the three forms.
//   clang++ -std=c++20 -I. test_sv0439.cpp -o t && ./t        (PASS expected)
#include "sv0439.hpp"

#include <cstdio>
#include <string>

using namespace bc5::sv439;
static int g_fail = 0;
#define CHECK(c) do { if (!(c)) { std::printf("FAIL %s:%d %s\n", __FILE__, __LINE__, #c); g_fail++; } } while (0)

int main() {
    Version v;
    std::string why;
    // unset: the host's constant, all three forms as today
    CHECK(from_switch(nullptr, "", v, why) && v.word == 0x0A600000u && std::string(v.str) == "10.60.000");
    CHECK(from_switch("", "", v, why) && v.word == 0x0A600000u);
    // explicit values and their encodings (10.60 must give the host's own constants back)
    struct E { const char *in; std::uint32_t word; const char *str; } ok[] = {
        {"10.60", 0x0A600000u, "10.60.000"}, {"11.60", 0x0B600000u, "11.60.000"}, {"9.00", 0x09000000u, "9.00.000"},
        {"12.00", 0x0C000000u, "12.00.000"}, {"11.05", 0x0B050000u, "11.05.000"}};
    for (const auto &e : ok) {
        const bool r = from_switch(e.in, "", v, why);
        CHECK(r && v.word == e.word && std::string(v.str) == e.str);
        std::printf("  %-6s -> 0x%08x \"%s\" (%s)\n", e.in, v.word, v.str, r ? "ok" : why.c_str());
    }
    // malformed: refused, never defaulted
    for (const char *bad : {"11", "11.6", "11.600", "x.60", "11.6x", "0.50", "100.00", ".60", "11..60", "eleven", "param2"}) {
        const bool r = from_switch(bad, "", v, why);
        CHECK(!r);
        std::printf("  %-7s refused: %s\n", bad, r ? "NO" : why.c_str());
    }
    // param: the title's param.json
    const std::string pj = "{ \"contentVersion\": \"01.512.000\", \"requiredSystemSoftwareVersion\": \"0x1160000000000000\", \"sdkVersion\": \"0x0000000000000000\" }";
    CHECK(from_switch("param", pj, v, why) && v.major == 11 && v.minor == 60 && v.word == 0x0B600000u && std::string(v.str) == "11.60.000");
    std::printf("  param  -> 0x%08x \"%s\" (%s)\n", v.word, v.str, v.source);
    CHECK(!from_switch("param", "", v, why));                              // param.json not read
    CHECK(!from_switch("param", "{ \"sdkVersion\": \"0x0\" }", v, why));   // no field
    std::printf("%s (%d failed checks)\n", g_fail == 0 ? "PASS" : "FAIL", g_fail);
    return g_fail == 0 ? 0 : 1;
}
