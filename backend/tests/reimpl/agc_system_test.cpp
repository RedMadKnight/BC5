// SPDX-License-Identifier: GPL-2.0-only
// Tests of the libSceAgc re-creation's module functions: load, init with fake imports and a
// synthetic module image (every table here is made up by the test, never real data), register
// defaults, static area, semaphores, suspend, CU-mask lists and the export/import tables.
#include "bc5/reimpl/agc.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstring>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace agc = bc5::reimpl::agc;
namespace tst = bc5::reimpl::agc::testing;
using u32 = std::uint32_t;
using u64 = std::uint64_t;

namespace {

// ---- synthetic module image ---------------------------------------------------------------------

class FakeImage : public bc5::reimpl::FirmwareData {
  public:
    void put(u64 vaddr, const void *data, std::size_t size) {
        auto &v = blocks_[vaddr];
        v.assign(static_cast<const std::uint8_t *>(data),
                 static_cast<const std::uint8_t *>(data) + size);
    }
    void put_pairs(u64 vaddr, const std::vector<agc::RegPair> &pairs) {
        put(vaddr, pairs.data(), pairs.size() * sizeof(agc::RegPair));
    }
    const std::uint8_t *get(const char *module, u64 vaddr, u64 size) override {
        if (std::string(module) != "libSceAgc") {
            return nullptr;
        }
        for (auto &[base, bytes] : blocks_) {
            if (vaddr >= base && vaddr + size <= base + bytes.size()) {
                return bytes.data() + (vaddr - base);
            }
        }
        return nullptr;
    }

  private:
    std::map<u64, std::vector<std::uint8_t>> blocks_;
};

std::vector<agc::RegPair> range_pairs(u32 first, u32 count, u32 value_base) {
    std::vector<agc::RegPair> v;
    for (u32 i = 0; i < count; ++i) {
        v.push_back({first + i, value_base + i});
    }
    return v;
}

// A synthetic internal-shader header blob: header, two SH pairs (program address LO/HI), the
// 5-qword sub-block, user-data count 3 at sub-block + 0x2A.
std::vector<std::uint8_t> make_shader_blob() {
    std::vector<std::uint8_t> blob(0xA0, 0);
    agc::Shader h{};
    h.magic = 0x34333231u;
    h.version = 0x18u;
    h.extra = 0x70 - 0x08;
    h.sh_regs = 0x60 - 0x20;
    h.info = 0x60 - 0x28; // info read only for the dispatch initiator (+0x10 = pair 2)
    h.header_bytes = 0xA0;
    h.code_bytes = 0x40;
    h.stage = 0;
    h.num_sh_regs = 2;
    std::memcpy(blob.data(), &h, sizeof h);
    const agc::RegPair regs[2] = {{0x20c, 0}, {0x20d, 0}};
    std::memcpy(blob.data() + 0x60, regs, sizeof regs);
    const std::uint16_t user = 3;
    std::memcpy(blob.data() + 0x70 + 0x2A, &user, 2);
    return blob;
}

FakeImage &image() {
    static FakeImage img;
    static bool built = false;
    if (!built) {
        built = true;
        // SoC 0x840F00 tables: public cx 0x20B pairs (offsets 0..0x20A), sh 0xA1 (0x80..0xFF and
        // 0x208..0x228), uc 0x2B (0x240..0x26A); internal cx 1 (0x300), sh 12.
        img.put_pairs(0x34120, range_pairs(0, 0x20B, 0x100000));
        auto sh = range_pairs(0x80, 0x80, 0x20000);
        auto sh2 = range_pairs(0x208, 0x21, 0x30000);
        sh.insert(sh.end(), sh2.begin(), sh2.end());
        img.put_pairs(0x35178, sh);
        img.put_pairs(0x35680, range_pairs(0x240, 0x2B, 0x40000));
        img.put_pairs(0x34018, {{0x300, 0x55}});
        std::vector<agc::RegPair> ish = {{0x216, 1}, {0x217, 2}, {0x100, 0x00ABCDEF}, {0x081, 4}};
        auto ish2 = range_pairs(0x300, 8, 0x50000);
        ish.insert(ish.end(), ish2.begin(), ish2.end());
        img.put_pairs(0x34020, ish);
        // CU override rows: 6 x 10 pairs, values 0x1000 + row * 16 + col.
        std::vector<agc::RegPair> rows;
        const u32 cols[10] = {0x216, 0x217, 0x219, 0x21A, 0x107, 0x087, 0x007, 0x101, 0x081, 0x001};
        for (u32 r = 0; r < 6; ++r) {
            for (u32 c = 0; c < 10; ++c) {
                rows.push_back({cols[c], 0x1000 + r * 16 + c});
            }
        }
        img.put_pairs(0x1BDB0, rows);
        u32 prim[18];
        for (u32 i = 0; i < 18; ++i) {
            prim[i] = (i + 1) % 5;
        }
        img.put(0x23f1c, prim, sizeof prim);
        const auto blob = make_shader_blob();
        const u64 headers[10] = {0x2c000, 0x2c130, 0x2c260, 0x2c390, 0x2c4c0,
                                 0x2c5f0, 0x2c720, 0x2c850, 0x2c980, 0x2cab0};
        const u64 code[10] = {0x30000, 0x30100, 0x30b00, 0x31400, 0x31600,
                              0x31a00, 0x31d00, 0x32300, 0x32900, 0x32b00};
        std::vector<std::uint8_t> code_bytes(0x40, 0xCC);
        for (int i = 0; i < 10; ++i) {
            img.put(headers[i], blob.data(), blob.size());
            img.put(code[i], code_bytes.data(), code_bytes.size());
        }
    }
    return img;
}

// ---- fake imports ----------------------------------------------------------------------------------

struct Record {
    std::vector<std::uint8_t> dmem;
    int notify_calls = 0;
    u32 n_cx = 0, n_sh = 0, n_uc = 0;
    std::vector<u64> pass_info;
    int suspend_calls = 0;
    agc::CbDescriptor last_desc{};
    u32 last_suspend_arg = 0;
    u32 *last_status = nullptr;
    int submit_acb_calls = 0;
    u32 first_queue = 0, last_queue = 0;
    int reset_cb_calls = 0;
    int kernel_flag_calls = 0;
    int kernel_flag_arg = -1;
    int lock_calls = 0, unlock_calls = 0, init_calls = 0, destroy_calls = 0;
    int raise_calls = 0;
    int raise_kind = 0;
    int tmp_init_calls = 0;
    int regmgr_a = 0, regmgr_b = 0;
};
Record g_rec;

u32 ud_size(u32 bytes) { return bytes == 0 ? 3u : (bytes <= 4 ? 4u : (bytes + 3) / 4 + 7u); }
u32 ud_write(u32 *dst, int pipe, u32 header, const void *payload, u32 bytes) {
    const u32 n = ud_size(bytes);
    dst[0] = (n == 3 ? 0xC0017900u : 0xC0027900u) | (pipe == 0 ? 4u : 0u);
    dst[1] = 0x342;
    dst[2] = header;
    for (u32 i = 3; i < n; ++i) {
        dst[i] = 0;
    }
    if (payload != nullptr && bytes != 0 && n == 4) {
        std::memcpy(&dst[3], payload, 4);
    }
    return n;
}
int trace_initiator(u32 i) { return static_cast<int>(i << 8); }
int tmp_init(u32 *, u32) {
    ++g_rec.tmp_init_calls;
    return 0;
}
int notify(const u32 *, const u32 *, const u32 *, u32 a, u32 b, u32 c) {
    ++g_rec.notify_calls;
    g_rec.n_cx = a;
    g_rec.n_sh = b;
    g_rec.n_uc = c;
    return 0;
}
int pass_info(const u64 *entries, u32 count) {
    g_rec.pass_info.assign(entries, entries + 2 * count);
    return 0;
}
int suspend_submit(const agc::CbDescriptor *desc, u32 *status, u32 arg) {
    ++g_rec.suspend_calls;
    g_rec.last_desc = *desc;
    g_rec.last_status = status;
    g_rec.last_suspend_arg = arg;
    return 0;
}
int submit_acb(u32 q, const agc::CbDescriptor *) {
    if (g_rec.submit_acb_calls++ == 0) {
        g_rec.first_queue = q;
    }
    g_rec.last_queue = q;
    return 0;
}
int reset_callbacks(const void *) {
    ++g_rec.reset_cb_calls;
    return 0;
}
int kernel_flag(int enable) {
    ++g_rec.kernel_flag_calls;
    g_rec.kernel_flag_arg = enable;
    return 0x77;
}
std::uint8_t not_esvm() { return 0; }
int raise(int kind, u64) {
    ++g_rec.raise_calls;
    g_rec.raise_kind = kind;
    return static_cast<int>(0x8A6D0003u);
}
int pa_debug_off() { return 0; }
int reserved_dmem(u64 *addr, u32 *size) {
    *addr = reinterpret_cast<u64>(g_rec.dmem.data());
    *size = static_cast<u32>(g_rec.dmem.size());
    return 0;
}
u32 soc_a() { return 0x840F00u; }
int m_init(void **, const void *, const char *) {
    ++g_rec.init_calls;
    return 0;
}
int m_lock(void **) {
    ++g_rec.lock_calls;
    return 0;
}
int m_unlock(void **) {
    ++g_rec.unlock_calls;
    return 0;
}
int m_destroy(void **) {
    ++g_rec.destroy_calls;
    return 0;
}
int kernel_query_one() { return 1; }
int regmgr(u64 key, int, int *out) {
    *out = key == 0x33236083918938B1ull ? g_rec.regmgr_a : g_rec.regmgr_b;
    return 0;
}

template <typename F> void install(const char *nid, F *f) {
    REQUIRE(tst::set_import(nid, reinterpret_cast<void *>(f)));
}

void install_all() {
    install("VhLnEiTuuWo", &ud_size);
    install("-vc-xL+G8u0", &ud_write);
    install("xDPdCurOujQ", &trace_initiator);
    install("UM8rn9hRWrY", &tmp_init);
    install("nR6xhiFsOoc", &notify);
    install("aCfbPzyjU90", &pass_info);
    install("kAPt2J4U3v8", &suspend_submit);
    install("gSRnr79F8tQ", &submit_acb);
    install("KtIXf8La96k", &reset_callbacks);
    install("oFb2hMcoJa4", &kernel_flag);
    install("SFB48L57OKQ", &not_esvm);
    install("yuO+lNrj+Do", &raise);
    install("HMnVBVUyajk", &pa_debug_off);
    install("Um-jkyDy9rI", &reserved_dmem);
    install("0vTn5IDMU9A", &soc_a);
    install("cmo1RIYva9o", &m_init);
    install("9UK1vLZQft4", &m_lock);
    install("tn3VlD0hG60", &m_unlock);
    install("2Of0f+3mhhE", &m_destroy);
}

struct Env {
    Env() {
        tst::reset();
        tst::clear_imports();
        g_rec = Record{};
        g_rec.dmem.assign(4u << 20, 0);
        bc5::reimpl::set_firmware_data(&image());
        install_all();
        // The static area lands at the start of the fake DMEM (already 4-aligned).
        tst::set_expected_static_area(reinterpret_cast<u64>(g_rec.dmem.data()));
    }
    ~Env() {
        bc5::reimpl::set_firmware_data(nullptr);
        tst::clear_imports();
        tst::reset();
    }
};

} // namespace

TEST_CASE("module_load carves the static area and the DMEM allocator", "[agc][system]") {
    Env env;
    REQUIRE(agc::module_load() == 0);
    CHECK(g_rec.init_calls == 1);
    CHECK(tst::static_area() == reinterpret_cast<u64>(g_rec.dmem.data()));
    REQUIRE(g_rec.pass_info.size() == 2);
    CHECK(g_rec.pass_info[0] == 10);
    CHECK(g_rec.pass_info[1] == 0);
    agc::module_unload();
    CHECK(g_rec.destroy_calls == 1);
}

TEST_CASE("module_load without DMEM leaves the static area unset", "[agc][system]") {
    Env env;
    tst::set_import("Um-jkyDy9rI", nullptr);
    REQUIRE(agc::module_load() == 0);
    CHECK(tst::static_area() == 0);
    const u64 entry[2] = {1, 2};
    CHECK(agc::sceAgcSetStaticBuffer(0, entry) == agc::kErrNotInitialised);
}

TEST_CASE("sceAgcInit builds the slot, notifies the driver and sets up suspend", "[agc][system]") {
    Env env;
    REQUIRE(agc::module_load() == 0);
    REQUIRE(agc::sceAgcInit(12) == 0);

    CHECK(g_rec.lock_calls == 1);
    CHECK(g_rec.unlock_calls == 1);
    CHECK(g_rec.tmp_init_calls == 1);
    CHECK(g_rec.kernel_flag_calls == 1);
    CHECK(g_rec.kernel_flag_arg == 0); // version 12 >= 6

    const auto s = tst::slot(0);
    CHECK(s.version == 12);
    CHECK(s.trusted);
    CHECK(s.cx_count == 0x20C); // offsets 0..0x20A plus internal 0x300
    for (u32 i = 1; i < s.cx_count; ++i) {
        CHECK(s.cx[i - 1].offset < s.cx[i].offset);
    }
    // Version >= 11: the flag is set, context register 0x201 gets bit 16.
    CHECK(s.cx[0x201].offset == 0x201);
    CHECK(s.cx[0x201].value == (0x100201u | 0x10000u));
    CHECK(s.cx[0x20B].offset == 0x300);
    CHECK(s.sh_count == 0xA1 + 12);
    CHECK(s.uc_count == 0x2B);
    CHECK(s.uc_special_count == 0);
    // CU-override patch: variant 0, row 0; SH 0x216 / 0x217 values from the row.
    bool saw216 = false;
    for (u32 i = 0; i < s.sh_count; ++i) {
        if (s.sh[i].offset == 0x216) {
            CHECK(s.sh[i].value == 0x1000u);
            saw216 = true;
        }
        if (s.sh[i].offset == 0x217) {
            CHECK(s.sh[i].value == 0x1001u);
        }
    }
    CHECK(saw216);
    // Prebuilt SH stream: first run 0x208..0x216 (15 registers).
    REQUIRE(s.sh_stream != nullptr);
    CHECK(s.sh_stream_bytes > 0);
    CHECK(s.sh_stream_bytes < 0x180);
    CHECK(s.sh_stream[0] == 0xC00F7600u);
    CHECK(s.sh_stream[1] == 0x208u);

    // Flat images handed to the driver: unique offsets per space.
    CHECK(g_rec.notify_calls == 1);
    CHECK(g_rec.n_cx == 0x20C);
    CHECK(g_rec.n_sh == 0xA1 + 9);
    CHECK(g_rec.n_uc == 0x2B);

    // Info passed downward: 8 {key, value} pairs.
    REQUIRE(g_rec.pass_info.size() == 16);
    CHECK(g_rec.pass_info[0] == 0);
    CHECK(g_rec.pass_info[1] == 12);
    CHECK(g_rec.pass_info[3] == reinterpret_cast<u64>(agc::sceAgcGetRegisterDefaults2(12)));
    CHECK(g_rec.pass_info[5] ==
          reinterpret_cast<u64>(agc::sceAgcGetRegisterDefaults2Internal(12)));
    CHECK(g_rec.pass_info[7] == 0); // slot 1 unused
    CHECK(g_rec.pass_info[12] == 6);
    CHECK(g_rec.pass_info[13] == tst::sync_label());
    CHECK(g_rec.pass_info[14] == 9);
    CHECK(g_rec.pass_info[15] == 0); // slot 0 trusted

    // Sync label {0, 1} in DMEM.
    REQUIRE(tst::sync_label() != 0);
    const auto *label = reinterpret_cast<const u32 *>(tst::sync_label());
    CHECK(label[0] == 0);
    CHECK(label[1] == 1);

    // Resume DCB: starts with the conditional roll notification (COND_EXEC).
    REQUIRE(s.resume_dcb != nullptr);
    CHECK(s.resume_dcb[0] == 0xC0032200u);
    CHECK(s.resume_dwords > 22);
    // Suspend set up: resume DCB submitted, then the SH stream on every compute queue.
    CHECK(g_rec.suspend_calls == 1);
    CHECK(g_rec.last_desc.address == reinterpret_cast<u64>(s.resume_dcb));
    CHECK(g_rec.last_desc.size_dwords == s.resume_dwords);
    CHECK(g_rec.last_suspend_arg == 1);
    CHECK(g_rec.submit_acb_calls == 0x3F);
    CHECK(g_rec.first_queue == 0x20);
    CHECK(g_rec.last_queue == 0x5E);
    CHECK(g_rec.reset_cb_calls == 1);

    // Trace initiators from the driver.
    agc::CommandBuffer cb{};
    std::vector<u32> buf(64, 0);
    agc::init_command_buffer(&cb, buf.data(), buf.size() * 4, nullptr, nullptr);
    u32 *p = agc::sceAgcCbDispatch(&cb, 1, 1, 1, 0);
    REQUIRE(p != nullptr);
    CHECK(p[4] == (0x41u | (9u << 8)));

    // Register descriptors resolved from the tables.
    const agc::RegPair *pgm = tst::descriptor(0x45c90);
    REQUIRE(pgm != nullptr);
    CHECK(pgm[0].offset == 0x20c);
    CHECK(pgm[0].value == 0x30004u);
    CHECK(pgm[1].offset == 0x20d);
    CHECK(tst::descriptor(0x45f28)->value == 0x00ABCDEFu); // internal SH 0x100
    CHECK(tst::descriptor(0x45db8)->offset == 0x191);
    CHECK(tst::descriptor(0x45a58)->offset == 0x242);
    CHECK(tst::descriptor(0x45f30)->offset == 0x081);
    CHECK(tst::descriptor(0x45f08)->offset == 0x260u); // internal uc list empty: described value

    // Internal shaders created; the fill shader got its program address patched.
    const agc::Shader *fill = tst::fill_shader();
    REQUIRE(fill != nullptr);
    CHECK(fill->code_address != 0);
    const auto *fill_regs = reinterpret_cast<const agc::RegPair *>(fill->sh_regs);
    CHECK(fill_regs[0].value == static_cast<u32>(fill->code_address >> 8));
    u64 entry[2] = {};
    REQUIRE(agc::sceAgcGetStaticBuffer(0, entry) == 0);
    CHECK(entry[1] == 0x80);
    CHECK(reinterpret_cast<const u64 *>(entry[0])[0] == fill->code_address);

    // Active state is usable now.
    CHECK(agc::sceAgcGetRegisterDefaults() == agc::agcGetRegisterDefaultsForVersion(12));
    CHECK(agc::sceAgcGetRegisterDefaultsInternal() ==
          agc::agcGetRegisterDefaultsInternalForVersion(12));
    std::vector<u32> sh_copy(128, 0);
    agc::init_command_buffer(&cb, sh_copy.data(), sh_copy.size() * 4, nullptr, nullptr);
    u32 *stream = agc::agcAcbCopyActiveShDefaults(&cb);
    REQUIRE(stream != nullptr);
    CHECK(stream[0] == 0xC00F7600u);

    // Fill memory with the internal shader.
    std::vector<u32> fill_buf(128, 0);
    agc::init_command_buffer(&cb, fill_buf.data(), fill_buf.size() * 4, nullptr, nullptr);
    const u64 pattern[2] = {0x1111111122222222ull, 0x3333333344444444ull};
    u32 *f = agc::agcCbFillMemory(&cb, 0x123400000000ull, pattern, 0x20000);
    REQUIRE(f != nullptr);
    CHECK(f[0] == 0xC0027600u); // two SH pairs in one run
    CHECK(f[1] == 0x20cu);
    CHECK(f[4] == 0xC0037600u); // 3 user-data dwords
    CHECK(f[5] == 0x240u);
    CHECK(f[6] == 0u);
    CHECK(f[7] == (0x00100000u | 0x1234u));
    CHECK(f[8] == 0x2000u);
    CHECK(f[9] == 0xC0017600u);
    CHECK(f[10] == 0x216u);
    CHECK(f[11] == 0x0003FCFFu);
    // Restore of the internal defaults (0x216 = 0x1000 after the CU patch).
    CHECK(f[20] == 0xC0017600u);
    CHECK(f[21] == 0x216u);
    CHECK(f[22] == 0x1000u);
}

TEST_CASE("sceAgcInit reuses and allocates slots", "[agc][system]") {
    Env env;
    REQUIRE(agc::module_load() == 0);
    REQUIRE(agc::sceAgcInit(12) == 0);
    const int notify_before = g_rec.notify_calls;
    CHECK(agc::agcInitWithVersion(0xDEAD, 12) == 0); // existing slot
    CHECK(g_rec.notify_calls == notify_before);
    CHECK(agc::sceAgcInit(11) == 0); // second slot (an empty defaults set)
    CHECK(tst::slot(1).version == 11);
    CHECK(g_rec.notify_calls == notify_before + 1);
    CHECK(agc::sceAgcInit(5) == agc::kErrNoFreeSlot);
}

TEST_CASE("sceAgcInit from an untrusted caller skips suspend", "[agc][system]") {
    Env env;
    REQUIRE(agc::module_load() == 0);
    agc::agcSetTrustedRange(0, ~0ull); // every caller inside the range
    REQUIRE(agc::sceAgcInit(12) == 0);
    CHECK(g_rec.suspend_calls == 0);
    CHECK(g_rec.kernel_flag_calls == 0);
    CHECK(!tst::slot(0).trusted);
    CHECK(g_rec.pass_info[15] == 1);
    CHECK(agc::sceAgcSuspendPoint() == agc::kErrNotInitialised);
    CHECK(agc::sceAgcGetRegisterDefaults() == nullptr);
    CHECK(agc::sceAgcGetRegisterDefaultsInternal() == nullptr);
}

TEST_CASE("sceAgcInit fails cleanly without DMEM or without driver imports", "[agc][system]") {
    {
        Env env;
        tst::set_import("Um-jkyDy9rI", nullptr);
        REQUIRE(agc::module_load() == 0);
        CHECK(agc::sceAgcInit(12) == agc::kErrInternal);
    }
    {
        Env env;
        REQUIRE(agc::module_load() == 0);
        tst::set_import("UM8rn9hRWrY", nullptr);
        CHECK(agc::sceAgcInit(12) == agc::kErrInternal);
    }
}

TEST_CASE("suspend points and the suspend configuration", "[agc][system]") {
    Env env;
    CHECK(agc::sceAgcSuspendPoint() == agc::kErrNotInitialised);
    CHECK(agc::sceAgcSuspendPointAndCheckStatus(0) == agc::kErrNotInitialised);
    REQUIRE(agc::module_load() == 0);
    REQUIRE(agc::sceAgcInit(12) == 0);
    const int before = g_rec.suspend_calls;
    CHECK(agc::sceAgcSuspendPoint() == 0);
    CHECK(g_rec.suspend_calls == before + 1);
    CHECK(g_rec.last_status == nullptr);
    CHECK(g_rec.last_suspend_arg == 1);
    // Negative configuration with bit 0: flags 3 -> mode 0x1F; flags stored in the static area.
    CHECK(agc::agcSetSuspendConfig(0x80000001u) == 0);
    u32 status = 0;
    CHECK(agc::sceAgcSuspendPointAndCheckStatus(reinterpret_cast<u64>(&status)) == 0);
    CHECK(g_rec.last_status == &status);
    CHECK(g_rec.last_suspend_arg == 0x1F);
    u64 word = 0;
    CHECK(agc::agcGetStaticWord(0, &word) == 0);
    CHECK(word == 3);
    CHECK(agc::agcSetSuspendConfig(1) == 0);
    CHECK(agc::sceAgcSuspendPoint() == 0);
    CHECK(g_rec.last_suspend_arg == 5);
    CHECK(agc::agcGetSuspendConfig() == 1);
    CHECK(agc::agcSetStaticWord(2, 0xABCDull) == 0);
    CHECK(agc::agcGetStaticWord(2, &word) == 0);
    CHECK(word == 0xABCDull);
}

TEST_CASE("static buffer bounds and round trip", "[agc][system]") {
    Env env;
    const u64 entry[2] = {0x1111, 0x2222};
    u64 out[2] = {};
    CHECK(agc::sceAgcSetStaticBuffer(0, entry) == agc::kErrNotInitialised);
    CHECK(agc::sceAgcGetStaticBuffer(0, out) == agc::kErrNotInitialised);
    REQUIRE(agc::module_load() == 0);
    CHECK(agc::sceAgcSetStaticBuffer(6, entry) == agc::kErrRange);
    CHECK(agc::sceAgcGetStaticBuffer(6, out) == agc::kErrRange);
    CHECK(agc::sceAgcSetStaticBuffer(5, entry) == 0);
    CHECK(agc::sceAgcGetStaticBuffer(5, out) == 0);
    CHECK(out[0] == 0x1111);
    CHECK(out[1] == 0x2222);
    // The area must be at the fixed address.
    tst::set_expected_static_area(0xFE0040000ull);
    CHECK(agc::sceAgcSetStaticBuffer(5, entry) == agc::kErrNotInitialised);
}

TEST_CASE("semaphore memory registration and labels", "[agc][system]") {
    Env env;
    std::vector<std::uint8_t> mem(0x10000, 0xAA);
    auto base = (reinterpret_cast<u64>(mem.data()) + 0x3FFF) & ~0x3FFFull;
    std::uint64_t label = 0;
    CHECK(agc::sceAgcGetSemaphoreLabel(0, &label) == agc::kErrSemaphoreNotSet);
    CHECK(agc::sceAgcSetAmmSemaphoreMemory(base + 4, 0x4000) == agc::kErrAlign);
    CHECK(agc::sceAgcSetAmmSemaphoreMemory(base, 0x100) == agc::kErrAlign);
    REQUIRE(agc::sceAgcSetAmmSemaphoreMemory(base, 0x4000) == 0);
    REQUIRE(g_rec.pass_info.size() == 6);
    CHECK(g_rec.pass_info[0] == 7);
    CHECK(g_rec.pass_info[1] == base);
    CHECK(g_rec.pass_info[2] == 8);
    CHECK(g_rec.pass_info[3] == 0x4000);
    CHECK(g_rec.pass_info[4] == 0xB);
    CHECK(g_rec.pass_info[5] == 0);
    CHECK(reinterpret_cast<const std::uint8_t *>(base)[0x3FFF] == 0);
    CHECK(agc::sceAgcSetAmmSemaphoreMemory(base, 0x4000) == agc::kErrSemaphoreSet);
    CHECK(agc::agcSetSemaphoreMemoryLimited(base, 0x4000) == agc::kErrSemaphoreSet);
    CHECK(agc::sceAgcGetSemaphoreLabel(511, &label) == 0);
    CHECK(label == base + 511 * 32);
    CHECK(agc::sceAgcGetSemaphoreLabel(512, &label) == agc::kErrRange);
}

TEST_CASE("limited semaphore memory variant", "[agc][system]") {
    Env env;
    CHECK(agc::agcSetSemaphoreMemoryLimited(0x4000, 0x100) == agc::kErrAlign);
    CHECK(agc::agcSetSemaphoreMemoryLimited(0x4000, 0x40004000ull) == agc::kErrRange);
    CHECK(agc::agcSetSemaphoreMemoryLimited(0x4004, 0x4000) == agc::kErrAlign);
    std::vector<std::uint8_t> mem(0x10000, 0xAA);
    auto base = (reinterpret_cast<u64>(mem.data()) + 0x3FFF) & ~0x3FFFull;
    REQUIRE(agc::agcSetSemaphoreMemoryLimited(base, 0x4000) == 0);
    CHECK(g_rec.pass_info[5] == 1);
    CHECK(tst::semaphore_base() == base);
    CHECK(tst::semaphore_size() == 0x4000);
}

TEST_CASE("default context state flattening", "[agc][system]") {
    Env env;
    std::vector<agc::RegPair> cx = {{2, 20}, {3, 30}, {7, 70}, {0xFFFFFFFFu, 0}};
    tst::SlotView v{};
    v.cx = cx.data();
    v.cx_count = 3;
    v.version = 1;
    tst::set_slot(1, v);
    std::vector<u32> out(8, 0xEEEEEEEEu);
    CHECK(agc::sceAgcGetDefaultCxStateFlat(out.data(), 1, 9, 1) == 0);
    CHECK(out[0] == 0);  // reg 1
    CHECK(out[1] == 20); // reg 2
    CHECK(out[2] == 30);
    CHECK(out[3] == 0);
    CHECK(out[6] == 70); // reg 7
    CHECK(out[7] == 0); // reg 8: scan reaches the padding entry
    CHECK(agc::sceAgcGetDefaultCxStateFlat(out.data(), 1, 9, 2) == agc::kErrRange);
}

TEST_CASE("register default selectors", "[agc][system]") {
    Env env;
    tst::set_soc_id(0x840F00u);
    const agc::RegisterDefaults *d = agc::sceAgcGetRegisterDefaults2(3);
    REQUIRE(d != nullptr);
    CHECK(d->cx_count == 0x20B);
    CHECK(d->sh_count == 0xA1);
    CHECK(d->uc_count == 0x2B);
    REQUIRE(*d->cx != nullptr);
    CHECK((*d->cx)[0x201].value == 0x100201u); // version < 11, workaround bit 2 clear
    tst::set_workaround_mask(4);
    agc::sceAgcGetRegisterDefaults2(3);
    CHECK((*d->cx)[0x201].value == 0x110201u);
    const agc::RegisterDefaults *old = agc::agcGetRegisterDefaultsForVersion(3);
    CHECK(old != d);
    CHECK(*old->cx == *d->cx); // same table, distinct descriptor
    const agc::RegisterDefaults *in = agc::sceAgcGetRegisterDefaults2Internal(3);
    CHECK(in->cx_count == 1);
    CHECK(in->sh_count == 12);
    CHECK(in->uc_count == 0);
    CHECK(agc::agcGetRegisterDefaultsInternalForVersion(3)->sh_count == 12);
    // Another SoC: version groups this re-creation cannot locate give an empty set.
    tst::set_soc_id(0);
    const agc::RegisterDefaults *e = agc::sceAgcGetRegisterDefaults2(5);
    REQUIRE(e != nullptr);
    CHECK(e->cx_count == 0);
    CHECK(e->name_table == nullptr);
}

TEST_CASE("CU-mask override lists", "[agc][system]") {
    Env env;
    const agc::RegPair *pairs = nullptr;
    const u32 *masks = nullptr;
    u32 count = 0;
    CHECK(agc::agcGetCuMaskOverrides(nullptr, &masks, &count) == agc::kErrNullPointer);
    CHECK(agc::agcGetCuMaskOverridesForVersion(&pairs, nullptr, &count, 1) ==
          agc::kErrNullPointer);
    CHECK(agc::agcGetComputeThreadMaskOverrides(&pairs, &masks, nullptr) == agc::kErrNullPointer);
    REQUIRE(agc::agcGetCuMaskOverrides(&pairs, &masks, &count) == 0);
    CHECK(count == 10);
    CHECK(pairs[0].offset == 0x216);
    CHECK(pairs[0].value == 0x1000u);
    CHECK(masks[4] == 0xFFFF0000u);
    CHECK(masks[9] == 0x0000FFFFu);
    tst::set_soc_id(0x840FC0u); // variant 1
    REQUIRE(agc::agcGetCuMaskOverridesForVersion(&pairs, &masks, &count, 13) == 0);
    CHECK(pairs[0].value == 0x1000u + 4 * 16); // row 1 + 3
    REQUIRE(agc::agcGetComputeThreadMaskOverrides(&pairs, &masks, &count) == 0);
    CHECK(count == 2);
    CHECK(pairs[0].value == 0x00FF00FFu);
    CHECK(masks[1] == 0xFFFFFFFFu);
    tst::set_soc_id(0);
    REQUIRE(agc::agcGetComputeThreadMaskOverrides(&pairs, &masks, &count) == 0);
    CHECK(pairs[1].offset == 0x217);
    CHECK(pairs[1].value == 0x0003FCFFu);
    bc5::reimpl::set_firmware_data(nullptr);
}

TEST_CASE("driver pass-throughs and the kernel flag", "[agc][system]") {
    Env env;
    CHECK(agc::sceAgcSetSubmitMode(1) == 0x77);
    CHECK(g_rec.kernel_flag_arg == 1);
    CHECK(agc::sceAgcDebugRaiseException(1, 0) == static_cast<int>(0x8A6D0003u));
    CHECK(g_rec.raise_kind == 1);
    std::uint8_t flag = 9;
    CHECK(agc::agcQueryKernelFlag(&flag) == 0);
    CHECK(flag == 0);
    install("tU5e3f9gSiU", &kernel_query_one);
    CHECK(agc::agcQueryKernelFlag(&flag) == 1);
    CHECK(flag == 1);
    tst::clear_imports();
    CHECK(agc::sceAgcSetSubmitMode(1) == agc::kErrInternal);
    CHECK(agc::sceAgcDebugRaiseException(1, 0) == agc::kErrInternal);
}

TEST_CASE("registry-backed suspend configuration on the transcoding SoC", "[agc][system]") {
    Env env;
    install("0vTn5IDMU9A", +[]() -> u32 { return 0x840FC5u; });
    install("39iV5E1HoCk", +[](u32) -> int { return 0; });
    install("dKeshzt29G4", &regmgr);
    REQUIRE(agc::module_load() == 0);
    g_rec.regmgr_a = 1;
    g_rec.regmgr_b = 1;
    CHECK(agc::agcGetSuspendConfig() == 0x80000001u);
    g_rec.regmgr_a = 0;
    CHECK(agc::agcGetSuspendConfig() == 0x80000000u);
}

TEST_CASE("export and import tables", "[agc][system]") {
    const auto ex = agc::exports();
    REQUIRE(ex.size() == 249);
    std::set<std::string> nids;
    int objects = 0;
    for (const auto &e : ex) {
        CHECK(e.address != nullptr);
        CHECK(std::string(e.library) == "libSceAgc");
        nids.insert(e.nid);
        if (e.is_object) {
            ++objects;
            CHECK(std::string(e.nid) == "bi4pcLifd1k");
        }
    }
    CHECK(nids.size() == 249);
    CHECK(objects == 1);
    bool found_init = false;
    for (const auto &e : ex) {
        if (std::string(e.nid) == "kW3GLb7QfPg") {
            found_init = true;
            CHECK(std::string(e.name) == "sceAgcInit");
            CHECK(e.address == reinterpret_cast<void *>(&agc::sceAgcInit));
        }
        if (std::string(e.nid) == "qj7QZpgr9Uw") {
            CHECK(std::string(e.name).empty());
            CHECK(e.address == reinterpret_cast<void *>(&agc::agcDcbContextStateOpNotify));
        }
    }
    CHECK(found_init);
    const auto im = agc::imports();
    std::set<std::string> import_nids;
    for (const auto &i : im) {
        CHECK(i.slot != nullptr);
        import_nids.insert(i.nid);
    }
    CHECK(import_nids.size() == im.size());
    CHECK(import_nids.count("kAPt2J4U3v8") == 1);
    CHECK(!tst::set_import("not-an-import", nullptr));
}

TEST_CASE("branch patch helpers retarget then/else sides", "[agc][patch]") {
    tst::reset();
    tst::clear_imports();
    std::vector<u32> buf(32, 0);
    agc::CommandBuffer cb{};
    agc::init_command_buffer(&cb, buf.data(), buf.size() * 4, nullptr, nullptr);
    u32 *p = agc::sceAgcCbBranch(&cb, 1, 3, 0x1000, 0, 0, 2, 0x2000, 0x10, 1, 0x3000, 0x20);
    REQUIRE(p != nullptr);
    CHECK(p[10] == 0x20000010u);
    CHECK(p[13] == 0x10000020u);
    CHECK(agc::sceAgcBranchPatchSetThenTarget(p, 0x1234567898ull, 0x55) == 0);
    CHECK(p[8] == 0x34567898u);
    CHECK(p[9] == 0x12u);
    CHECK(p[10] == 0x20000055u); // policy bits kept
    CHECK(agc::agcBranchPatchSetThenTargetEx(p, 3, 0xABCD0004ull, 0xFFFFF) == 0);
    CHECK(p[8] == 0xABCD0004u);
    CHECK(p[9] == 0u);
    CHECK(p[10] == 0x300FFFFFu);
    CHECK(agc::sceAgcBranchPatchSetElseTarget(p, 0x500000008ull, 7) == 0);
    CHECK(p[11] == 8u);
    CHECK(p[12] == 5u);
    CHECK(p[13] == 0x10000007u);
    CHECK(agc::agcBranchPatchSetElseTargetEx(p, 0, 0x10, 1) == 0);
    CHECK(p[11] == 0x10u);
    CHECK(p[12] == 0u);
    CHECK(p[13] == 0x00000001u);
    std::vector<u32> nop(14, 0);
    nop[0] = 0xC00C1000u;
    CHECK(agc::sceAgcBranchPatchSetThenTarget(nop.data(), 0x1000, 1) == agc::kErrWrongPacket);
    CHECK(agc::sceAgcBranchPatchSetElseTarget(nop.data(), 0x1000, 1) == agc::kErrWrongPacket);
    CHECK(agc::agcBranchPatchSetThenTargetEx(nop.data(), 1, 0x1000, 1) == agc::kErrWrongPacket);
    CHECK(agc::agcBranchPatchSetElseTargetEx(nop.data(), 1, 0x1000, 1) == agc::kErrWrongPacket);
    CHECK(nop[8] == 0u);
    CHECK(nop[13] == 0u);
}
