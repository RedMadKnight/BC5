// BC5 experiment 0385: the small part of Catch2's macros the backend's tests use, for a laptop compile of
// lake_probe_test.cpp with no Catch2 installed. On the box the real Catch2 builds the same file.
#pragma once

#include <cstdio>
#include <functional>
#include <string>
#include <vector>

namespace shim {
struct Case {
    const char *name;
    void (*fn)();
};
inline std::vector<Case> &cases() {
    static std::vector<Case> c;
    return c;
}
inline int &fails() {
    static int f = 0;
    return f;
}
struct Add {
    Add(const char *n, void (*f)()) { cases().push_back({n, f}); }
};
struct Stop {};
inline void note(const char *what, const char *file, int line) {
    std::printf("  FAILED %s at %s:%d\n", what, file, line);
    fails()++;
}
} // namespace shim

#define SHIM_CAT2(a, b) a##b
#define SHIM_CAT(a, b) SHIM_CAT2(a, b)
#define TEST_CASE(name, tags)                                                                                          \
    static void SHIM_CAT(shim_fn_, __LINE__)();                                                                        \
    static shim::Add SHIM_CAT(shim_add_, __LINE__)(name, SHIM_CAT(shim_fn_, __LINE__));                                \
    static void SHIM_CAT(shim_fn_, __LINE__)()
#define CHECK(...)                                                                                                     \
    do {                                                                                                               \
        if (!(__VA_ARGS__)) shim::note(#__VA_ARGS__, __FILE__, __LINE__);                                              \
    } while (0)
#define CHECK_FALSE(...) CHECK(!(__VA_ARGS__))
#define REQUIRE(...)                                                                                                   \
    do {                                                                                                               \
        if (!(__VA_ARGS__)) {                                                                                          \
            shim::note(#__VA_ARGS__, __FILE__, __LINE__);                                                              \
            throw shim::Stop{};                                                                                        \
        }                                                                                                              \
    } while (0)
