// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0388: the CPU model's pure parts (bc5/cpu_model.hpp).
#include "bc5/cpu_model.hpp"

#include <catch2/catch_test_macros.hpp>

namespace {

using namespace bc5::cpu_model;

TEST_CASE("a flag is on only for 1", "[cpu_model]") {
    bool invalid = true;
    CHECK_FALSE(parse_flag(nullptr, &invalid));
    CHECK_FALSE(invalid);
    CHECK_FALSE(parse_flag("", &invalid));
    CHECK_FALSE(invalid);
    CHECK_FALSE(parse_flag("0", &invalid));
    CHECK_FALSE(invalid);
    CHECK(parse_flag("1"));
    CHECK_FALSE(parse_flag("yes", &invalid));
    CHECK(invalid);
    CHECK_FALSE(parse_flag("01", &invalid));
    CHECK(invalid);
}

TEST_CASE("the mask switch keeps the host's mask unless it is valid", "[cpu_model]") {
    bool invalid = true;
    CHECK(parse_mask(nullptr, &invalid) == 0x7f);
    CHECK_FALSE(invalid);
    CHECK(parse_mask("", &invalid) == 0x7f);
    CHECK_FALSE(invalid);
    CHECK(parse_mask("0", &invalid) == 0x7f);
    CHECK_FALSE(invalid);
    CHECK(parse_mask("1", &invalid) == 0x1fff);
    CHECK_FALSE(invalid);
    CHECK(parse_mask("0x3ff", &invalid) == 0x3ff);
    CHECK_FALSE(invalid);
    for (const char* bad : {"13", "0x0", "0x2000", "0x1fffg", "0x", "on"}) {
        invalid = false;
        CHECK(parse_mask(bad, &invalid) == 0x7f);
        CHECK(invalid);
    }
}

TEST_CASE("the spin is bounded", "[cpu_model]") {
    bool invalid = true;
    CHECK(parse_spin_us(nullptr, &invalid) == 0);
    CHECK_FALSE(invalid);
    CHECK(parse_spin_us("", &invalid) == 0);
    CHECK_FALSE(invalid);
    CHECK(parse_spin_us("0", &invalid) == 0);
    CHECK_FALSE(invalid);
    CHECK(parse_spin_us("200", &invalid) == 200);
    CHECK_FALSE(invalid);
    CHECK(parse_spin_us("500", &invalid) == 500);
    CHECK_FALSE(invalid);
    for (const char* bad : {"501", "-1", "2x", "x"}) {
        invalid = false;
        CHECK(parse_spin_us(bad, &invalid) == 0);
        CHECK(invalid);
    }
}

TEST_CASE("the bound and the nice stay inside their ranges", "[cpu_model]") {
    bool invalid = true;
    CHECK(parse_bound_us(nullptr, &invalid) == 0);
    CHECK_FALSE(invalid);
    CHECK(parse_bound_us("5000", &invalid) == 5000);
    CHECK_FALSE(invalid);
    for (const char* bad : {"5001", "-1", "1x"}) {
        invalid = false;
        CHECK(parse_bound_us(bad, &invalid) == 0);
        CHECK(invalid);
    }
    CHECK(parse_worker_nice(nullptr, &invalid) == 0);
    CHECK_FALSE(invalid);
    CHECK(parse_worker_nice("-5", &invalid) == -5);
    CHECK_FALSE(invalid);
    CHECK(parse_worker_nice("0", &invalid) == 0);
    CHECK_FALSE(invalid);
    for (const char* bad : {"-11", "1", "x"}) {
        invalid = false;
        CHECK(parse_worker_nice(bad, &invalid) == 0);
        CHECK(invalid);
    }
}

TEST_CASE("a time falls in one of five bands", "[cpu_model]") {
    CHECK(time_band(-1) == 0);
    CHECK(time_band(49) == 0);
    CHECK(time_band(50) == 1);
    CHECK(time_band(199) == 1);
    CHECK(time_band(200) == 2);
    CHECK(time_band(499) == 2);
    CHECK(time_band(500) == 3);
    CHECK(time_band(1999) == 3);
    CHECK(time_band(2000) == 4);
}

TEST_CASE("a job handle decodes as the title's code does", "[cpu_model]") {
    const JobHandle h = decode_job((0x12345678ull << 32) | (0x1fffffffull << 2) | 2u);
    CHECK(h.entry == 2);
    CHECK(h.index == 0x1fffffff);
    CHECK(h.generation == 0x12345678);
    const JobHandle bit31 = decode_job(0x80000000ull | 1u);  // bit 31 is outside the index
    CHECK(bit31.entry == 1);
    CHECK(bit31.index == 0);
    CHECK(bit31.generation == 0);
}

TEST_CASE("a host CPU maps into the thread's guest mask", "[cpu_model]") {
    CHECK(guest_cpu(0, 0x7f, 0x7f) == 0);
    CHECK(guest_cpu(6, 0x7f, 0x7f) == 6);
    CHECK(guest_cpu(7, 0x7f, 0x7f) == 0);
    CHECK(guest_cpu(15, 0x1fff, 0x1fff) == 2);
    CHECK(guest_cpu(1, 0x30, 0x1fff) == 5);
    CHECK(guest_cpu(2, 0x30, 0x1fff) == 4);
    CHECK(guest_cpu(3, 0, 0x7f) == 3);
    CHECK(guest_cpu(3, 0x2000, 0x1fff) == 3);
}

TEST_CASE("only a real restriction becomes a host mask", "[cpu_model]") {
    CHECK(host_mask(0x1fff, 0x1fff) == 0);
    CHECK(host_mask(0xffff, 0x1fff) == 0);
    CHECK(host_mask(0x7f, 0x7f) == 0);
    CHECK(host_mask(0x2000, 0x1fff) == 0);
    CHECK(host_mask(0x10, 0x1fff) == 0x10);
    CHECK(host_mask(0x7f, 0x1fff) == 0x7f);
}

} // namespace
