// SPDX-License-Identifier: GPL-2.0-only
#include "bc5/lake_probe.hpp"

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace bc5;
using lake_probe::Cache;
using lake_probe::Config;
using lake_probe::Switches;
using lake_probe::Zpass;

namespace {

using Words = std::vector<std::uint32_t>;
constexpr std::uint32_t kLake = 0x1129ec00, kOther = 0x22222200;
constexpr std::uint32_t kAcquire = 0xC0065800u, kPfp = 0xC0004200u, kEvent = 0xC0004600u, kCtx = 0xC0016900u;
const full_state::Tracker::Reader kNoRead = [](std::uint64_t, std::uint64_t) -> const std::uint32_t * { return nullptr; };

void ctx(Words &ib, std::uint32_t off, std::uint32_t v) { ib.insert(ib.end(), {kCtx, off, v}); }
void sh(Words &ib, std::uint32_t off, std::uint32_t v) { ib.insert(ib.end(), {0xC0017600u, off, v}); }
void depth(Words &ib, std::uint32_t base, std::uint32_t control) {
    ctx(ib, 0x014, base);
    ctx(ib, 0x200, control);
}
void draw(Words &ib) { ib.insert(ib.end(), {0xC0012D00u, 3u, 2u}); }              // DRAW_INDEX_AUTO
void draw_indirect(Words &ib) { ib.insert(ib.end(), {0xC0032400u, 0u, 0u, 0u, 0u}); } // DRAW_INDIRECT
void dispatch(Words &ib, std::uint64_t pgm) {
    sh(ib, 0x20c, static_cast<std::uint32_t>(pgm >> 8));
    sh(ib, 0x20d, 0);
    ib.insert(ib.end(), {0xC0031500u, 1u, 1u, 1u, 1u});
}
void nops(Words &ib, std::size_t n) { ib.insert(ib.end(), n, 0x80000000u); }

lake_probe::Result plan(const Words &ib, const Switches &s, Zpass *z = nullptr) {
    full_state::Tracker t;
    return lake_probe::plan(ib, t, kNoRead, s, Config{}, z);
}
std::size_t count(const Words &w, std::uint32_t x) { return static_cast<std::size_t>(std::count(w.begin(), w.end(), x)); }
Words applied(Words ib, const lake_probe::Result &r) {
    REQUIRE(indirect_check::insert_before(ib, r.inserts));
    return ib;
}

} // namespace

TEST_CASE("switches parse, and a bad request leaves them all off", "[lake]") {
    Switches s;
    std::string bad;
    REQUIRE(lake_probe::parse("cache=wbinv cache_at=each\ncull=1 # a note\npfp=1 zpass=1\n", s, bad));
    CHECK(s.cache == Cache::wbinv);
    CHECK(s.cache_each);
    CHECK(s.cull);
    CHECK(s.pfp);
    CHECK(s.zpass);
    CHECK_FALSE(s.nohiz);
    REQUIRE(lake_probe::parse("", s, bad));
    CHECK(s == Switches{});
    s.cull = true;
    CHECK_FALSE(lake_probe::parse("cull=1 cache=everything", s, bad));
    CHECK(bad == "cache=everything");
    CHECK(s == Switches{});
    Switches t;
    REQUIRE(lake_probe::parse(lake_probe::describe(Switches{Cache::all, true, true, false, true, false, true, false, true, true}), t, bad));
    CHECK(t.cache == Cache::all);
    CHECK(t.zpass);
}

TEST_CASE("all off inserts nothing, and the tracker still follows the job", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    ctx(ib, 0x003, 0x55);
    full_state::Tracker t;
    const auto r = lake_probe::plan(ib, t, kNoRead, Switches{}, Config{}, nullptr);
    CHECK(r.inserts.empty());
    REQUIRE(r.writers.size() == 1);
    std::uint32_t v = 0;
    CHECK(t.get(full_state::Context, 0x003, v));
    CHECK(v == 0x55);
}

TEST_CASE("only draws on the lake's depth with Z and Z write on are writers", "[lake]") {
    Words ib;
    depth(ib, kOther, 6);
    draw(ib);
    depth(ib, kLake, 2); // Z on, no write: the water draw
    draw(ib);
    depth(ib, kLake, 0); // the decompress: Z off
    draw(ib);
    depth(ib, kLake, 6);
    draw_indirect(ib);
    const auto r = plan(ib, Switches{});
    REQUIRE(r.writers.size() == 1);
    CHECK(r.writers[0].op == 0x24);
}

TEST_CASE("the cache switch goes before the first writer, or each with cache_at=each", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    draw(ib);
    draw(ib);
    Switches s;
    s.cache = Cache::wb;
    auto r = plan(ib, s);
    REQUIRE(r.inserts.size() == 1);
    CHECK(r.inserts[0].at == r.writers[0].at);
    CHECK(r.inserts[0].words[0] == kAcquire);
    CHECK(r.inserts[0].words[7] == 1u << 15);
    s.cache_each = true;
    CHECK(plan(ib, s).inserts.size() == 3);
    s.cache = Cache::all;
    CHECK(plan(ib, s).inserts[0].words[7] == 0xC3B1u);
    s.cache = Cache::inv;
    CHECK(plan(ib, s).inserts[0].words[7] == ((1u << 14) | (1u << 9) | (1u << 8)));
}

TEST_CASE("cull and dbmeta go after the named programs only", "[lake]") {
    Words ib;
    dispatch(ib, 0x11d0375600);
    dispatch(ib, 0x11d0288a00);
    dispatch(ib, 0x11d0999900);
    Switches s;
    s.cull = true;
    auto r = plan(ib, s);
    CHECK(r.cull_barriers == 1);
    REQUIRE(r.inserts.size() == 1);
    CHECK(r.inserts[0].words[0] == kEvent);
    CHECK(r.inserts[0].words[2] == kAcquire);
    s = Switches{};
    s.dbmeta = true;
    r = plan(ib, s);
    CHECK(r.htile_fills == 1);
    REQUIRE(r.inserts.size() == 1);
    CHECK(r.inserts[0].words[r.inserts[0].words.size() - 1] == 44u);
    // after the packet, so the dispatch itself keeps its place
    const Words out = applied(ib, r);
    CHECK(out.size() == ib.size() + r.inserts[0].words.size());
}

TEST_CASE("pfp goes before COND_EXEC and indirect writers, and the COND_EXEC count grows", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    ib.insert(ib.end(), {0xC0032200u, 0x1000u, 0u, 0u, 5u}); // COND_EXEC over the five dwords of the draw
    draw_indirect(ib);
    Switches s;
    s.pfp = true;
    const auto r = plan(ib, s);
    REQUIRE(r.writers.size() == 1);
    CHECK(r.writers[0].in_cond);
    CHECK(r.cond_exec == 1);
    REQUIRE(r.inserts.size() == 2);
    CHECK(r.inserts[0].words[0] == kPfp);
    const Words out = applied(ib, r);
    const auto at = static_cast<std::size_t>(std::find(out.begin(), out.end(), 0xC0032200u) - out.begin());
    CHECK((out[at + 4] & 0x3fffu) == 7u); // the sync the writer got is inside the range
}

TEST_CASE("idle flushes CS and PS once, before the first writer", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    draw(ib);
    Switches s;
    s.idle = true;
    const auto r = plan(ib, s);
    REQUIRE(r.inserts.size() == 1);
    CHECK(r.inserts[0].words == Words{kEvent, 7u | (4u << 8), kEvent, 16u | (4u << 8)});
}

TEST_CASE("nohiz forces HiZ off for the writers and restores the title's value", "[lake]") {
    Words ib;
    ctx(ib, 0x003, 0x40000000u);
    depth(ib, kLake, 6);
    draw(ib);
    draw(ib);
    depth(ib, kOther, 6);
    draw(ib);
    Switches s;
    s.nohiz = true;
    const auto r = plan(ib, s);
    REQUIRE(r.inserts.size() == 2);
    CHECK(r.inserts[0].words == Words{kCtx, 0x003u, 0x40000000u | 0x2au});
    CHECK(r.inserts[1].words == Words{kCtx, 0x003u, 0x40000000u});
    CHECK(r.inserts[1].at == r.writers[1].at + 3 + 6);
}

TEST_CASE("an override still on at the job's end is put back there", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    Switches s;
    s.nohiz = true;
    const auto r = plan(ib, s);
    REQUIRE(r.inserts.size() == 2);
    CHECK(r.inserts[1].at == ib.size());
}

TEST_CASE("zpass wraps each writer in its own record until they run out", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    draw(ib);
    draw(ib);
    Switches s;
    s.zpass = true;
    Zpass z{0x7000000, 2, 0};
    const auto r = plan(ib, s, &z);
    REQUIRE(r.writers.size() == 3);
    CHECK(r.writers[0].record == 0);
    CHECK(r.writers[1].record == 1);
    CHECK(r.writers[2].record == -1);
    CHECK(z.used == 2);
    const Words out = applied(ib, r);
    CHECK(count(out, 0xC0024600u) == 4);
    CHECK(count(out, 0x7000000u + 256u) == 1);
    CHECK(count(out, 0x7000000u + 256u + 8u) == 1);
    CHECK(count(out, 21u | (1u << 8)) == 4);
    // DB_COUNT_CONTROL on once, and back to the idle value at the end
    const std::uint32_t on = (1u << 1) | (1u << 2) | (1u << 8) | (1u << 24) | (1u << 28);
    CHECK(count(out, on) == 1);
    CHECK(out.back() == 1u);
}

TEST_CASE("zpass with the switch off or no records wraps nothing", "[lake]") {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    Zpass z{0x7000000, 8, 0};
    CHECK(plan(ib, Switches{}, &z).inserts.empty());
    CHECK(z.used == 0);
    Switches s;
    s.zpass = true;
    CHECK(plan(ib, s, nullptr).inserts.empty());
}

TEST_CASE("nested IBs and predication are counted, a truncated packet ends the walk", "[lake]") {
    Words ib;
    ib.insert(ib.end(), {0xC0023F00u, 0x1000u, 0u, 16u});
    ib.insert(ib.end(), {0xC0012000u, 0u, 0u});
    nops(ib, 2);
    ib.push_back(0xC0102D00u); // claims 18 dwords, has one
    const auto r = plan(ib, Switches{});
    CHECK(r.nested_ibs == 1);
    CHECK(r.predication == 1);
    CHECK(r.writers.empty());
}

TEST_CASE("trackercf stops the tracker at a CHAIN, and off keeps today's walk", "[lake]") {
    const Words nested = {kCtx, 0x010u, 7u};
    const full_state::Tracker::Reader read = [&nested](std::uint64_t, std::uint64_t) -> const std::uint32_t * { return nested.data(); };
    Words ib = {0xC0023F00u, 0x1000u, 0u, 3u | (1u << 20)}; // INDIRECT_BUFFER with CHAIN
    ctx(ib, 0x011, 9);                                      // the dead tail
    full_state::Stats st;
    std::uint32_t v = 0;
    full_state::Tracker today;
    today.apply(ib, read, st);
    CHECK(today.get(full_state::Context, 0x011, v));
    full_state::set_chain_stop(true);
    full_state::Tracker fixed;
    fixed.apply(ib, read, st);
    full_state::set_chain_stop(false);
    CHECK_FALSE(fixed.get(full_state::Context, 0x011, v));
    CHECK(fixed.get(full_state::Context, 0x010, v));
    CHECK(v == 7);
}

TEST_CASE("every insert is in ascending order and lands on a packet start", "[lake]") {
    Words ib;
    for (int k = 0; k < 6; ++k) {
        depth(ib, kLake, 6);
        draw(ib);
        dispatch(ib, 0x11d0375600);
        depth(ib, kOther, 6);
        draw(ib);
    }
    Switches s;
    s.cache = Cache::wbinv;
    s.cache_each = true;
    s.cull = s.pfp = s.idle = s.nohiz = s.zpass = true;
    Zpass z{0x7000000, 64, 0};
    const auto r = plan(ib, s, &z);
    CHECK(std::is_sorted(r.inserts.begin(), r.inserts.end(),
                         [](const indirect_check::Insert &a, const indirect_check::Insert &b) { return a.at < b.at; }));
    const Words out = applied(ib, r);
    CHECK(out.size() > ib.size());
    // the out buffer still parses, packet by packet, to its end
    std::size_t i = 0;
    while (i < out.size()) {
        const std::uint32_t n = (out[i] >> 16) & 0x3fffu;
        REQUIRE(out[i] >> 30 == 3);
        i += n + 2;
    }
    CHECK(i == out.size());
}

namespace {
std::string temp_path(const char *name) {
    const char *t = std::getenv("TEMP");
    return std::string(t != nullptr ? t : "/tmp") + "/" + name;
}
void write_file(const std::string &p, const std::string &text) {
    std::FILE *f = std::fopen(p.c_str(), "w");
    REQUIRE(f != nullptr);
    std::fwrite(text.data(), 1, text.size(), f);
    std::fclose(f);
}
Words writer_job() {
    Words ib;
    depth(ib, kLake, 6);
    draw(ib);
    return ib;
}
} // namespace

TEST_CASE("a session follows the control file during the run, in both directions", "[lake]") {
    const std::string ctl = temp_path("bc5-lake-test-ctl.txt");
    std::remove(ctl.c_str());
    lake_probe::Session s(ctl, "");
    Words ib = writer_job();
    s.step(ib, kNoRead); // no file: all off
    CHECK(ib == writer_job());
    write_file(ctl, "cache=wb\n");
    for (int k = 0; k < 31; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK(s.switches().cache == Cache::off); // only every 32 jobs
    ib = writer_job();
    s.step(ib, kNoRead);
    CHECK(s.switches().cache == Cache::wb);
    CHECK(count(ib, kAcquire) == 1);
    write_file(ctl, "cache=nonsense\n");
    for (int k = 0; k < 32; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK(s.switches() == Switches{}); // a bad request is all off
    CHECK(count(ib, kAcquire) == 0);
    write_file(ctl, "trackercf=1\n");
    for (int k = 0; k < 32; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK(s.switches().trackercf);
    write_file(ctl, "");
    for (int k = 0; k < 32; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK(s.switches() == Switches{});
    std::remove(ctl.c_str());
}

TEST_CASE("zpass's records reach the file once the switch goes off and every job has ended", "[lake]") {
    const std::string ctl = temp_path("bc5-lake-test-ctl2.txt"), out = temp_path("bc5-lake-test.bin");
    std::remove(out.c_str());
    write_file(ctl, "zpass=1\n");
    std::vector<std::uint32_t> mem(1024 * 256 / 4, 0);
    mem[0] = 0x1234;
    lake_probe::Session s(ctl, out);
    s.attach(0x7000000, mem.data(), 1024 * 256);
    Words ib = writer_job();
    for (int k = 0; k < 8; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK(count(ib, 0xC0024600u) == 2);
    write_file(ctl, "\n");
    for (int k = 0; k < 24; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK_FALSE(s.dumped()); // the switch is read at job 32
    for (int k = 0; k < 197; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK_FALSE(s.dumped());
    for (int k = 0; k < 8; ++k) {
        ib = writer_job();
        s.step(ib, kNoRead);
    }
    CHECK(s.dumped());
    std::FILE *f = std::fopen(out.c_str(), "rb");
    REQUIRE(f != nullptr);
    std::fseek(f, 0, SEEK_END);
    const long size = std::ftell(f);
    std::fclose(f);
    CHECK(size == 32L * 256L); // jobs 0-31 ran with the switch on
    std::FILE *g = std::fopen((out + ".meta").c_str(), "r");
    REQUIRE(g != nullptr);
    char line[96] = {};
    REQUIRE(std::fgets(line, sizeof line, g) != nullptr);
    std::fclose(g);
    CHECK(std::string(line).rfind("0 1 0x0 0x2d 0 ", 0) == 0);
    std::remove(out.c_str());
    std::remove((out + ".meta").c_str());
    std::remove(ctl.c_str());
}
