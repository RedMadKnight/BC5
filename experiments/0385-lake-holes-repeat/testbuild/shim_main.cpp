// BC5 experiment 0385: main() for the laptop compile of the backend's lake tests (see laptop-shim).
#include <catch2/catch_test_macros.hpp>

int main() {
    int bad = 0;
    for (const shim::Case &c : shim::cases()) {
        const int before = shim::fails();
        try {
            c.fn();
        } catch (const shim::Stop &) {
        }
        const bool ok = shim::fails() == before;
        bad += ok ? 0 : 1;
        std::printf("%s %s\n", ok ? "PASS" : "FAIL", c.name);
    }
    std::printf("%zu cases, %d failed\n", shim::cases().size(), bad);
    return bad == 0 ? 0 : 1;
}
