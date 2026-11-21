// SPDX-License-Identifier: GPL-2.0-only
// Tests of the libSceAgcDriver re-creation against its behavioural description. A fake host
// installs every import (recording ioctl requests and argument bytes, memory mappings, mutex and
// VideoOut calls) and a fake FirmwareData; no device is touched.
#include "bc5/reimpl/agc_driver.hpp"
#include "bc5/reimpl/agc_driver_tables.hpp"
#include "bc5/reimpl/data_source.hpp"

#include <catch2/catch_test_macros.hpp>

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <utility>
#include <vector>

using namespace bc5::reimpl;
using namespace bc5::reimpl::agc_driver;

namespace {

using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;

u64 addr(const void *p) { return static_cast<u64>(reinterpret_cast<std::uintptr_t>(p)); }
template <class T> T *ptr(u64 a) { return reinterpret_cast<T *>(static_cast<std::uintptr_t>(a)); }
u32 rd32(u64 a) {
    u32 v = 0;
    std::memcpy(&v, ptr<void>(a), 4);
    return v;
}
u64 rd64(u64 a) {
    u64 v = 0;
    std::memcpy(&v, ptr<void>(a), 8);
    return v;
}
u32 lo(u64 v) { return static_cast<u32>(v); }
u32 hi(u64 v) { return static_cast<u32>(v >> 32); }
u32 hi16(u64 v) { return static_cast<u32>(v >> 32) & 0xFFFFu; }

struct IoctlRec {
    u64 req;
    std::vector<u8> arg;   // argument bytes as passed in
    std::vector<u8> extra; // the array the argument points to, where there is one
    template <class T> T as() const {
        T t{};
        std::memcpy(&t, arg.data(), sizeof(T) < arg.size() ? sizeof(T) : arg.size());
        return t;
    }
    std::vector<u32> extra32() const {
        std::vector<u32> v(extra.size() / 4);
        std::memcpy(v.data(), extra.data(), v.size() * 4);
        return v;
    }
};

struct Host {
    u32 client_info = 0;
    u8 app_mode = 0;
    int open_rc = 7;
    int open_calls = 0;
    int close_rc = 0;
    int close_calls = 0;
    bool mmap_fail = false;
    std::string flex_fail;
    std::map<u64, int> ioctl_rc;
    u32 gfx_result = 0;
    std::vector<IoctlRec> ioctls;
    std::vector<std::unique_ptr<std::vector<u8>>> storage;
    std::vector<std::pair<std::string, u64>> flex;
    std::map<std::string, u64> area;
    u64 doorbell = 0;
    u64 dmem = 0;
    std::vector<u64> mmap_args;
    std::vector<u64> dmem_args;
    int dmem_prot = 0;
    std::vector<std::pair<std::string, std::vector<u64>>> props;
    std::vector<std::pair<std::string, u64>> range_names;
    std::vector<std::string> mutex_names;
    int lock_rc = 0;
    int lock_calls = 0;
    int unlock_calls = 0;
    int destroy_calls = 0;
    std::uintptr_t next_mutex = 0x1000;
    int hook_query = 0;
    // VideoOut
    int eop_rc = 0;
    u64 eop_info = 0;
    int eop_calls = 0;
    int label_rc = 0;
    int label_calls = 0;
    u64 label_base = 0x5000001000u;
    u32 bus = 0x33;
    std::vector<KernelEvent> kevents;
    int kevent_rc = 0;
    int err = 0;
    int raise_rc = 0;
    std::vector<std::pair<u32, u64>> raises;
    u32 soc = 0;
    int flex_size_rc = 0;
    int pts_rc = 0;
    int sysinfo_rc = 0;
    std::vector<std::string> log;

    u8 *alloc(u64 n) {
        storage.push_back(std::make_unique<std::vector<u8>>(n + 0x10000));
        const u64 base = addr(storage.back()->data());
        return ptr<u8>((base + 0xFFFF) & ~u64{0xFFFF});
    }
};
Host *g_host = nullptr;

// ---- fake imports ------------------------------------------------------------------------------
int f_open(const char *path, int flags, ...) {
    ++g_host->open_calls;
    CHECK(std::string(path) == "/dev/gc");
    CHECK(flags == 2);
    return g_host->open_rc;
}
int f_close(int) {
    ++g_host->close_calls;
    return g_host->close_rc;
}
int f_ioctl(int, u64 req, void *arg) {
    IoctlRec r;
    r.req = req;
    const u64 len = (req >> 16) & 0x1FFF;
    r.arg.assign(static_cast<u8 *>(arg), static_cast<u8 *>(arg) + len);
    auto copy_extra = [&](u64 at, u64 bytes) {
        r.extra.assign(ptr<u8>(at), ptr<u8>(at) + bytes);
    };
    if (req == kIoctlGfxSubmit) {
        const auto a = r.as<GfxSubmitArgs>();
        copy_extra(a.entries, u64{a.count} * 16);
    } else if (req == kIoctlDirectSubmit) {
        const auto a = r.as<DirectSubmitArgs>();
        copy_extra(a.packets, u64{a.count} * 16);
    } else if (req == kIoctlDirectSubmitTagged) {
        const auto a = r.as<DirectSubmitTaggedArgs>();
        copy_extra(a.packets, u64{a.count} * 16);
    } else if (req == kIoctlPatchClearState) {
        const auto a = r.as<PatchClearStateArgs>();
        copy_extra(a.pairs, u64{a.count} * 8);
    }
    g_host->ioctls.push_back(r);
    const auto it = g_host->ioctl_rc.find(req);
    const int rc = it == g_host->ioctl_rc.end() ? 0 : it->second;
    if (rc != 0) {
        return rc;
    }
    auto *b = static_cast<u8 *>(arg);
    auto put32 = [&](std::size_t off, u32 v) { std::memcpy(b + off, &v, 4); };
    auto put64 = [&](std::size_t off, u64 v) { std::memcpy(b + off, &v, 8); };
    switch (req) {
    case kIoctlClientInfo:
        put32(0, g_host->client_info);
        break;
    case kIoctlGfxPrologue:
        put32(0x40, g_host->gfx_result);
        break;
    case kIoctlGfxSubmit:
        put32(0x10, g_host->gfx_result);
        break;
    case kIoctlGfxSuspend:
        put32(4, g_host->gfx_result);
        break;
    case kIoctlSuspendCheck:
        put32(0, 7);
        put64(8, 0x1234);
        break;
    case kIoctlGetTfRing:
        put64(0, 0xABCD00);
        put32(8, 0x400);
        break;
    case kIoctlGetHsOffchip:
        put32(0, 0x00120034u);
        break;
    case kIoctlSysClientNumber:
        put32(0, 5);
        break;
    case kIoctlSysIsGameClosed:
        put32(0, 1);
        break;
    case kIoctlSysGfxResetStatus:
        put32(0, 9);
        break;
    case kIoctlCwsr:
        put32(4, 0x77);
        break;
    case kIoctlInitTail:
        std::memset(b, 0x11, 16);
        break;
    default:
        break;
    }
    return 0;
}
void *f_mmap(void *a, u64 len, int prot, int flags, int fd, std::int64_t off) {
    g_host->mmap_args = {addr(a), len, static_cast<u64>(prot), static_cast<u64>(flags),
                         static_cast<u64>(fd), static_cast<u64>(off)};
    if (g_host->mmap_fail) {
        return reinterpret_cast<void *>(~std::uintptr_t{0});
    }
    u8 *p = g_host->alloc(len);
    g_host->doorbell = addr(p);
    return p;
}
int f_getpid() { return 42; }
int *f_error() { return &g_host->err; }
int f_kevent(void *, const void *changes, int n, void *, int, const void *) {
    for (int i = 0; i < n; ++i) {
        KernelEvent e{};
        std::memcpy(&e, static_cast<const u8 *>(changes) + 32 * i, 32);
        g_host->kevents.push_back(e);
    }
    return g_host->kevent_rc;
}
int f_kernel_error(int e) { return static_cast<int>(0x80020000u | static_cast<u32>(e)); }
u64 f_event_data(const void *ev) { return *static_cast<const u64 *>(ev); }
u64 f_dmem_size() { return 0x10000000u; }
int f_alloc_dmem(std::int64_t start, std::int64_t end, u64 len, u64 align, int type,
                 std::int64_t *phys) {
    g_host->dmem_args = {static_cast<u64>(start), static_cast<u64>(end), len, align,
                         static_cast<u64>(type)};
    *phys = 0x4000000;
    return 0;
}
int f_map_dmem(void **a, u64 len, int prot, int, std::int64_t phys, u64, const char *name) {
    CHECK(std::string(name) == "SceAgcDriver");
    CHECK(phys == 0x4000000);
    CHECK(addr(*a) == 0xFE0000000u);
    g_host->dmem_prot = prot;
    u8 *p = g_host->alloc(len);
    std::memset(p, 0xCD, len); // the module must zero it
    g_host->dmem = addr(p);
    *a = p;
    return 0;
}
int f_map_flex(void **a, u64 len, int prot, int flags, const char *name) {
    const std::string n(name);
    if (n == g_host->flex_fail) {
        return -1;
    }
    CHECK(flags == 0);
    if (n == "SceGnmGpuInfo") {
        CHECK(addr(*a) == 0xFE0300000u);
        CHECK(prot == 3);
    } else {
        CHECK(addr(*a) == 0xF00000000u);
        CHECK(prot == 0x33);
    }
    u8 *p = g_host->alloc(len);
    std::memset(p, 0xAB, len);
    g_host->flex.emplace_back(n, len);
    g_host->area[n] = addr(p);
    *a = p;
    return 0;
}
int f_range_name(void *a, u64, const char *name) {
    g_host->range_names.emplace_back(name, addr(a));
    return 0;
}
int f_prop(const char *name, u64 a, u64 b, u64 c, u64 d) {
    g_host->props.emplace_back(name, std::vector<u64>{a, b, c, d});
    return 0;
}
int f_raise(u32 code, u64 arg) {
    g_host->raises.emplace_back(code, arg);
    return g_host->raise_rc;
}
int f_sdk(u32 *v) {
    *v = 0x5000000;
    return 0;
}
u64 f_ptc() { return 0x1000; }
int f_flex_size(u64 *v) {
    *v = 0x1234567;
    return g_host->flex_size_rc;
}
int f_pts(int *a, int *b, int *c, int *d) {
    *a = 11;
    *b = 22;
    *c = 33;
    *d = 44;
    return g_host->pts_rc;
}
u32 f_soc() { return g_host->soc; }
int f_app_info(int pid, void *out) {
    CHECK(pid == 42);
    static_cast<u8 *>(out)[0x48] = g_host->app_mode;
    return 0;
}
int f_mutex_init(ScePthreadMutex *m, const void *, const char *name) {
    *m = reinterpret_cast<void *>(g_host->next_mutex++);
    g_host->mutex_names.emplace_back(name);
    return 0;
}
int f_mutex_lock(ScePthreadMutex *) {
    ++g_host->lock_calls;
    return g_host->lock_rc;
}
int f_mutex_unlock(ScePthreadMutex *) {
    ++g_host->unlock_calls;
    return 0;
}
int f_mutex_destroy(ScePthreadMutex *) {
    ++g_host->destroy_calls;
    return 0;
}
int f_hook_query() { return g_host->hook_query; }
int f_sysinfo(void *out) {
    auto *q = static_cast<u64 *>(out);
    CHECK(q[0] == 0x38);
    for (u64 i = 1; i < 7; ++i) {
        q[i] = 0x100 + i;
    }
    return g_host->sysinfo_rc;
}
int f_eop(int, int, u32, std::int64_t, u64 *e) {
    ++g_host->eop_calls;
    *e = g_host->eop_info;
    return g_host->eop_rc;
}
int f_label(int, u64 *base) {
    ++g_host->label_calls;
    *base = g_host->label_base;
    return g_host->label_rc;
}
u32 f_bus(int) { return g_host->bus; }

template <class F> void *fp(F *f) {
    void *p = nullptr;
    std::memcpy(&p, &f, sizeof p);
    return p;
}

const std::map<std::string, void *> &fakes() {
    static const std::map<std::string, void *> m = {
        {"open", fp(&f_open)},
        {"close", fp(&f_close)},
        {"ioctl", fp(&f_ioctl)},
        {"mmap", fp(&f_mmap)},
        {"getpid", fp(&f_getpid)},
        {"__error", fp(&f_error)},
        {"kevent", fp(&f_kevent)},
        {"sceKernelError", fp(&f_kernel_error)},
        {"sceKernelGetEventData", fp(&f_event_data)},
        {"sceKernelGetDirectMemorySize", fp(&f_dmem_size)},
        {"sceKernelAllocateDirectMemory", fp(&f_alloc_dmem)},
        {"sceKernelMapNamedDirectMemory", fp(&f_map_dmem)},
        {"sceKernelMapNamedSystemFlexibleMemory", fp(&f_map_flex)},
        {"sceKernelSetVirtualRangeName", fp(&f_range_name)},
        {"sceKernelSetProcessProperty", fp(&f_prop)},
        {"sceKernelDebugRaiseException", fp(&f_raise)},
        {"sceKernelGetCompiledSdkVersion", fp(&f_sdk)},
        {"sceKernelGetProcessTimeCounter", fp(&f_ptc)},
        {"sceKernelConfiguredFlexibleMemorySize", fp(&f_flex_size)},
        {"sceKernelGetPageTableStats", fp(&f_pts)},
        {"sceKernelGetMainSocId", fp(&f_soc)},
        {"sceKernelGetAppInfo", fp(&f_app_info)},
        {"scePthreadMutexInit", fp(&f_mutex_init)},
        {"scePthreadMutexLock", fp(&f_mutex_lock)},
        {"scePthreadMutexUnlock", fp(&f_mutex_unlock)},
        {"scePthreadMutexDestroy", fp(&f_mutex_destroy)},
        {"sceKernelIsThreadSanitizerEnabled", fp(&f_hook_query)},
        {"aj7wRdAWFeM", fp(&f_sysinfo)},
        {"sceVideoOutSubmitEopFlip", fp(&f_eop)},
        {"sceVideoOutGetBufferLabelAddress", fp(&f_label)},
        {"sceVideoOutSysGetBus", fp(&f_bus)},
    };
    return m;
}

// Firmware data: a synthetic image where byte i = (i * 7 + 3) & 0xFF.
class FakeFw : public FirmwareData {
  public:
    bool present = true;
    std::vector<u8> image;
    FakeFw() : image(0x20000) {
        for (std::size_t i = 0; i < image.size(); ++i) {
            image[i] = static_cast<u8>((i * 7 + 3) & 0xFF);
        }
    }
    const u8 *get(const char *module, u64 vaddr, u64 size) override {
        CHECK(std::string(module) == "libSceAgcDriver");
        if (!present || vaddr + size > image.size()) {
            return nullptr;
        }
        return image.data() + vaddr;
    }
    u32 u32_at(u64 off) const {
        u32 v = 0;
        std::memcpy(&v, image.data() + off, 4);
        return v;
    }
};

void capture_log(const char *, const char *message) {
    if (g_host != nullptr) {
        g_host->log.emplace_back(message);
    }
}

struct Fixture {
    Host host;
    FakeFw fw;
    explicit Fixture(u32 client_info = 0, bool init = true, u8 app_mode = 0) {
        g_host = &host;
        host.client_info = client_info;
        host.app_mode = app_mode;
        reset_for_tests();
        install_all();
        set_firmware_data(&fw);
        // These tests check the module-file path with a synthetic image.
        bc5::reimpl::set_data_switches({true, false});
        set_log(&capture_log);
        if (init) {
            REQUIRE(initialize() == kOk);
        }
    }
    ~Fixture() {
        for (const ImportSlot &s : imports()) {
            *s.slot = nullptr;
        }
        set_firmware_data(nullptr);
        bc5::reimpl::reset_data_switches();
        set_log(nullptr);
        reset_for_tests();
        g_host = nullptr;
    }
    Fixture(const Fixture &) = delete;
    Fixture &operator=(const Fixture &) = delete;

    static void install_all() {
        for (const ImportSlot &s : imports()) {
            const std::string key = std::string(s.name).empty() ? s.nid : s.name;
            const auto it = fakes().find(key);
            REQUIRE(it != fakes().end());
            *s.slot = it->second;
        }
    }
    static void uninstall(const std::string &name) {
        for (const ImportSlot &s : imports()) {
            if (name == s.name || name == s.nid) {
                *s.slot = nullptr;
            }
        }
    }
    std::vector<u64> reqs() const {
        std::vector<u64> v;
        for (const auto &r : host.ioctls) {
            v.push_back(r.req);
        }
        return v;
    }
    std::vector<IoctlRec> of(u64 req) const {
        std::vector<IoctlRec> v;
        for (const auto &r : host.ioctls) {
            if (r.req == req) {
                v.push_back(r);
            }
        }
        return v;
    }
    void clear() { host.ioctls.clear(); }
    u64 area(const char *name) const { return host.area.at(name); }
    bool logged(const std::string &needle) const {
        for (const auto &l : host.log) {
            if (l.find(needle) != std::string::npos) {
                return true;
            }
        }
        return false;
    }
};

CommandBufferDesc desc(u64 a, u32 size) {
    CommandBufferDesc d{};
    d.address = a;
    d.size_dw = size;
    return d;
}

std::vector<u32> ring_dwords(u64 base, u32 first, u32 n) {
    std::vector<u32> v;
    for (u32 i = 0; i < n; ++i) {
        v.push_back(rd32(base + 4u * (first + i)));
    }
    return v;
}

} // namespace

// =================================================================================================
// Tables

TEST_CASE("agc_driver: export table has the 175 rows of the description", "[agc_driver]") {
    const auto ex = exports();
    REQUIRE(ex.size() == 175);
    std::set<std::pair<std::string, std::string>> keys;
    std::set<void *> addresses;
    std::map<std::string, int> per_lib;
    for (const ExportEntry &e : ex) {
        CHECK(e.address != nullptr);
        CHECK_FALSE(e.is_object);
        CHECK(std::strlen(e.nid) == 11);
        keys.emplace(e.nid, e.library);
        addresses.insert(e.address);
        ++per_lib[e.library];
        const std::string name(e.name);
        CHECK((name.empty() || name.rfind("sceAgcDriver", 0) == 0));
    }
    CHECK(keys.size() == 175);
    CHECK(addresses.size() == 173); // two functions are exported from two libraries each
    CHECK(per_lib["libSceAgcDriver"] == 118);
    CHECK(per_lib["libSceAgcDriverPaDebug"] == 45);
    CHECK(per_lib["libSceAgcDriverAsyncGraphicsRingEval_nosubmission"] == 1);
    CHECK(per_lib["libSceAgcDriverDebugWavefronts_nosubmission"] == 7);
    CHECK(per_lib["libSceAgcDriverDebugReset_nosubmission"] == 4);
    auto find = [&](const char *nid, const char *lib) -> const ExportEntry * {
        for (const ExportEntry &e : ex) {
            if (std::string(e.nid) == nid && std::string(e.library) == lib) {
                return &e;
            }
        }
        return nullptr;
    };
    auto as_void = [](auto f) {
        void *p = nullptr;
        std::memcpy(&p, &f, sizeof p);
        return p;
    };
    REQUIRE(find("UglJIZjGssM", "libSceAgcDriver") != nullptr);
    CHECK(find("UglJIZjGssM", "libSceAgcDriver")->address == as_void(&sceAgcDriverSubmitDcb));
    CHECK(std::string(find("UglJIZjGssM", "libSceAgcDriver")->name) == "sceAgcDriverSubmitDcb");
    REQUIRE(find("kAPt2J4U3v8", "libSceAgcDriver") != nullptr);
    CHECK(find("kAPt2J4U3v8", "libSceAgcDriver")->address == as_void(&nid_kAPt2J4U3v8));
    CHECK(std::string(find("kAPt2J4U3v8", "libSceAgcDriver")->name).empty());
    CHECK(find("Vlaj1gwmIFA", "libSceAgcDriver")->address ==
          find("Vlaj1gwmIFA", "libSceAgcDriverAsyncGraphicsRingEval_nosubmission")->address);
    CHECK(find("NhnGMuunz0Y", "libSceAgcDriver")->address ==
          find("NhnGMuunz0Y", "libSceAgcDriverPaDebug")->address);
    CHECK(find("Dg-D0+2-m8g", "libSceAgcDriverDebugReset_nosubmission")->address ==
          as_void(&nid_Dg_D0_2_m8g));
}

TEST_CASE("agc_driver: import table has unique, non-null slots", "[agc_driver]") {
    const auto im = imports();
    CHECK(im.size() == 31);
    std::set<void **> slots;
    std::set<std::string> nids;
    for (const ImportSlot &s : im) {
        CHECK(s.slot != nullptr);
        slots.insert(s.slot);
        nids.insert(s.nid);
        const std::string lib(s.library);
        CHECK((lib == "libkernel" || lib == "libSceVideoOut"));
    }
    CHECK(slots.size() == im.size());
    CHECK(nids.size() == im.size());
    CHECK(nids.count("LzoM-wVLJDE") == 1);
    CHECK(nids.count("aj7wRdAWFeM") == 1);
    CHECK(nids.count("7VSZJxxcTL8") == 1);
    CHECK(nids.count("PfccT7qURYE") == 1); // ioctl
}

// =================================================================================================
// Initialisation

TEST_CASE("agc_driver: game init opens /dev/gc, maps areas and queues in order", "[agc_driver]") {
    Fixture f;
    // ioctls: client info, trap handler, 56 queue maps, two submit-state ioctls, init tail.
    const auto r = f.reqs();
    REQUIRE(r.size() == 61);
    CHECK(r[0] == kIoctlClientInfo);
    CHECK(r[1] == kIoctlSetTrapHandler);
    for (std::size_t i = 2; i < 58; ++i) {
        CHECK(r[i] == kIoctlMapComputeQueue);
    }
    CHECK(r[58] == kIoctlGameInitReset);
    CHECK(r[59] == kIoctlSetSubmitMode);
    CHECK(r[60] == kIoctlInitTail);
    CHECK(f.host.ioctls[58].as<u32>() == 0);
    CHECK(f.host.ioctls[59].as<u32>() == 1);
    // the init-tail argument is pre-filled with 0xFF and its output lands at dmem + 0x7FF0
    for (u8 b : f.host.ioctls[60].arg) {
        CHECK(b == 0xFF);
    }
    CHECK(rd32(f.host.dmem + 0x7FF0) == 0x11111111u);

    // doorbell mapping
    REQUIRE(f.host.mmap_args.size() == 6);
    CHECK(f.host.mmap_args[0] == 0xFE0200000u);
    CHECK(f.host.mmap_args[1] == 0x4000);
    CHECK(f.host.mmap_args[2] == 0x22);
    CHECK(f.host.mmap_args[3] == 1);
    CHECK(f.host.mmap_args[4] == 7);

    // flexible memory areas in order
    const std::vector<std::pair<std::string, u64>> want = {
        {"SceGnmGpuInfo", 0x100000}, {"SceGnmTrapCode", 0x4000},   {"SceGnmTrapData", 0x4000},
        {"SceGnmDdid", 0xFC000},     {"SceGnmEopFifo", 0x3C000},   {"SceGnmShadowRegInfo", 0x4000},
        {"SceGnmCwsr", 0x1000000},   {"SceGnmMisc", 0x4000},       {"SceGnmACQRB", 0x1E0000},
    };
    CHECK(f.host.flex == want);
    CHECK(rd64(f.area("SceGnmDdid")) == 0); // zero-filled

    // direct memory
    REQUIRE(f.host.dmem_args.size() == 5);
    CHECK(f.host.dmem_args[0] == 0);
    CHECK(f.host.dmem_args[1] == 0x10000000u);
    CHECK(f.host.dmem_args[2] == 0x200000);
    CHECK(f.host.dmem_args[3] == 0x200000);
    CHECK(f.host.dmem_args[4] == 0xC);
    CHECK(f.host.dmem_prot == 0x33);

    // trap handler: code copied from the module image, resources passed to the kernel
    const u64 code = f.area("SceGnmTrapCode");
    CHECK(std::memcmp(ptr<void>(code), f.fw.image.data() + 0x1C000, 0x2400) == 0);
    const auto t = f.host.ioctls[1].as<TrapHandlerArgs>();
    CHECK(t.code_address == code);
    CHECK(t.code_size == 0x2400);
    CHECK(t.data_address == f.area("SceGnmTrapData"));
    CHECK(t.data_size == 0x4000);
    CHECK(t.cwsr_address == f.area("SceGnmCwsr"));
    CHECK(t.cwsr_size == 0x1000000);
    CHECK(t.wfdebug_address == 0xC80008000u);
    CHECK(t.wfdebug_size == 0x3BB00);
    CHECK(t.ddid_address == f.area("SceGnmDdid"));
    CHECK(t.ddid_size == 0xFC000);
    CHECK(t.handler_data_address == 0);
    CHECK(t.handler_data_size == 0);
    CHECK(t.wfdebug_handler_data_address == 0);
    CHECK(t.wfdebug_handler_data_size == 0);
    CHECK(t.wfdebug_tail_address == 0xC80008000u + 0x3BD00);
    CHECK(t.wfdebug_tail_size == 0xD00);
    CHECK(t.extra == 0);
    const u64 td = f.area("SceGnmTrapData");
    CHECK(rd64(td) == f.area("SceGnmCwsr"));
    CHECK(rd64(td + 8) == f.area("SceGnmCwsr"));
    CHECK(rd64(td + 16) == 0xC80008000u);

    // compute queue maps: first and last
    const auto m0 = f.host.ioctls[2].as<MapQueueArgs>();
    const u64 acq = f.area("SceGnmACQRB");
    const u64 eop = f.area("SceGnmEopFifo");
    CHECK(m0.me == 1);
    CHECK(m0.pipe == 0);
    CHECK(m0.queue == 0);
    CHECK(m0.vqid == 1);
    CHECK(m0.ring_base == acq);
    CHECK(m0.rptr_report == acq + 0x4000);
    CHECK(m0.doorbell_page == f.host.doorbell);
    CHECK(m0.ring_size_log2 == 12);
    CHECK(m0.extra == 0);
    CHECK(m0.eop_address == eop);
    CHECK(m0.eop_size == 0x1000);
    const auto m55 = f.host.ioctls[57].as<MapQueueArgs>();
    CHECK(m55.me == 2);
    CHECK(m55.pipe == 2);
    CHECK(m55.queue == 7);
    CHECK(m55.vqid == 56);
    CHECK(m55.ring_base == acq + 55 * 0x8000);
    CHECK(m55.eop_address == eop + 55 * 0x1000);

    // GPU info header and the per-vqid queue record
    const u64 gi = f.area("SceGnmGpuInfo");
    CHECK(rd32(gi) == 0);
    CHECK(rd32(gi + 0xB6440) == 0xE10);
    CHECK(rd32(gi + 0xB644C) == 0x40);
    CHECK(rd32(gi + 0xB72E8) == 0x8010);
    CHECK(rd32(gi + 0xB72EC) == 0x400);
    CHECK(rd32(gi + 0xBF2F8) == 0x4010);
    CHECK(rd32(gi + 0xBF2FC) == 0x200);
    CHECK(rd32(gi + 0xB6450) == 1);
    CHECK(rd32(gi + 0xB6454) == 1);
    CHECK(rd32(gi + 0xB6458) == 0);
    CHECK(rd32(gi + 0xB6460) == 12);
    CHECK(rd64(gi + 0xB6468) == acq);
    CHECK(nid_NhnGMuunz0Y() == ptr<void>(gi));

    // process properties and range names
    REQUIRE(f.host.props.size() == 4);
    CHECK(f.host.props[0].first == "Sce.Debug:Gnm");
    CHECK(f.host.props[0].second == std::vector<u64>{gi, 0x100000, 0, 0});
    CHECK(f.host.props[1].first == "Sce.Debug:Gn2");
    CHECK(f.host.props[1].second[0] == f.area("SceGnmDdid"));
    CHECK(f.host.props[1].second[2] == f.area("SceGnmCwsr") + 0xA00000);
    CHECK(f.host.props[1].second[3] == 0x32000);
    CHECK(f.host.props[2].first == "Sce.Debug:Gn3");
    CHECK(f.host.props[2].second == std::vector<u64>{f.area("SceGnmCwsr"), 0xA00000, 0, 0});
    CHECK(f.host.props[3].first == "Sce.Debug:Gn4");
    CHECK(f.host.props[3].second ==
          std::vector<u64>{f.host.dmem + 0x8000, 0x32000, f.area("SceGnmShadowRegInfo"), 0x4000});
    std::vector<std::string> names;
    for (const auto &n : f.host.range_names) {
        names.push_back(n.first);
    }
    CHECK(names == std::vector<std::string>{"SceGnmDingDong", "SceGnmDumpArea", "SceAgcRegShadow",
                                            "SceAgcGprDumpArea", "SceAgcRegShadowCopy",
                                            "SceAgcRegShadowInfo", "SceAgcDdid"});

    // register shadow info copied to the ShadowRegInfo area and returned by the getters
    RegShadowInfo gfx{}, agr{};
    REQUIRE(sceAgcDriverGetRegShadowInfo(&gfx) == kOk);
    REQUIRE(sceAgcDriverGetRegShadowInfoAgr(&agr) == kOk);
    CHECK(gfx.base == f.host.dmem + 0x8000);
    CHECK(agr.base == f.host.dmem + 0x21000);
    CHECK(gfx.size == 0x19000);
    CHECK(gfx.ctx_last == 0x3BF);
    CHECK(gfx.sh_first == 0x2000);
    CHECK(gfx.sh_last == 0x2281);
    CHECK(gfx.uc_first == 0x2400);
    CHECK(gfx.uc_last == 0x2843);
    CHECK(std::memcmp(ptr<void>(f.area("SceGnmShadowRegInfo")), &gfx, 0x28) == 0);
    CHECK(std::memcmp(ptr<void>(f.area("SceGnmShadowRegInfo") + 0x28), &agr, 0x28) == 0);
    CHECK(sceAgcDriverGetRegShadowInfo(nullptr) == kErrInvalid);
    CHECK(sceAgcDriverGetRegShadowInfoAgr(nullptr) == kErrInvalid);

    // driver memory contents: empty IB, shadow-restore CBs, zeroed shadows
    const u64 dm = f.host.dmem;
    CHECK(rd32(dm + 0x3A200) == 0xC0001000u);
    CHECK(rd32(dm + 0x3A204) == 0);
    const std::vector<u32> restore_on = ring_dwords(dm + 0x800, 0, 18);
    const u64 sg = dm + 0x8000;
    CHECK(restore_on == std::vector<u32>{0xC0036100u, lo(sg), hi(sg), 0, 0, 0xC0035F00u,
                                         lo(sg + 0x8000), hi(sg + 0x8000), 0, 0, 0xC0035E00u,
                                         lo(sg + 0x9000), hi(sg + 0x9000), 0, 0, 0xC0012800u,
                                         0x91018003u, 0x80018003u});
    const std::vector<u32> restore_off = ring_dwords(dm + 0x900, 0, 18);
    CHECK(restore_off[1] == 0xDEAD0000u);
    CHECK(restore_off[2] == 0xF);
    CHECK(restore_off[17] == 0x80000000u);
    CHECK(rd32(dm + 0x880 + 4) == lo(dm + 0x21000));
    CHECK(rd32(dm + 0x980 + 4) == 0xDEAD0000u);
    CHECK(rd64(dm + 0x8000) == 0);
    CHECK(rd64(dm + 0x21000 + 0x18FF8) == 0);

    // mutexes: two graphics handles, 56 compute handles, the workload mutex
    REQUIRE(f.host.mutex_names.size() == 59);
    CHECK(f.host.mutex_names[0] == "SceAgcSubmitMtx00\n");
    CHECK(f.host.mutex_names[1] == "SceAgcSubmitMtx04\n");
    CHECK(f.host.mutex_names[2] == "SceAgcSubmitMtx32\n");
    CHECK(f.host.mutex_names[58] == "SceAgcDriverWorkloads");
    CHECK(f.logged("submit mode 1"));

    // reserved block for libSceAgc
    u64 a = 0;
    u32 s = 0;
    CHECK(sceAgcDriverGetReservedDmemForAgc(&a, &s) == kOk);
    CHECK(a == dm + 0x40000);
    CHECK(s == 0x1B0000);
    CHECK(sceAgcDriverGetReservedDmemForAgc(nullptr, &s) == kErrInvalid);
    CHECK(sceAgcDriverGetReservedDmemForAgc(&a, nullptr) == kErrInvalid);
    CHECK(nid_SFB48L57OKQ() == 0);
}

TEST_CASE("agc_driver: init failure paths", "[agc_driver]") {
    SECTION("open fails") {
        Fixture f(0, false);
        f.host.open_rc = -1;
        CHECK(initialize() == kErrGeneric);
        CHECK(f.host.ioctls.empty());
        CHECK(f.logged("cannot initialise the GPU"));
    }
    SECTION("no open import") {
        Fixture f(0, false);
        Fixture::uninstall("open");
        CHECK(initialize() == kErrGeneric);
    }
    SECTION("doorbell mapping fails: /dev/gc is closed") {
        Fixture f(0, false);
        f.host.mmap_fail = true;
        CHECK(initialize() == kErrGeneric);
        CHECK(f.host.close_calls == 1);
        CHECK(f.reqs() == std::vector<u64>{kIoctlClientInfo});
    }
    SECTION("a flexible area fails: later areas and the trap handler are skipped") {
        Fixture f(0, false);
        f.host.flex_fail = "SceGnmCwsr";
        CHECK(initialize() == kOk);
        CHECK(f.host.flex.size() == 6);
        CHECK(f.of(kIoctlSetTrapHandler).empty());
        CHECK(f.logged("SceGnmCwsr"));
        // no UMD info: no compute queue could be mapped
        CHECK(f.of(kIoctlMapComputeQueue).empty());
        CHECK(sceAgcDriverSubmitAcb(0x20, nullptr) == kErrInvalid);
    }
    SECTION("trap handler for app modes 1, 2 and >= 4 is not installed") {
        for (u8 mode : {u8{1}, u8{2}, u8{4}}) {
            Fixture f(0, true, mode);
            CHECK(f.of(kIoctlSetTrapHandler).empty());
        }
        Fixture f3(0, true, 3);
        CHECK(f3.of(kIoctlSetTrapHandler).size() == 1);
    }
    SECTION("trap handler binary missing in the firmware data: our own handler is sent") {
        Fixture f(0, false);
        f.fw.present = false;
        CHECK(initialize() == kOk);
        CHECK(f.of(kIoctlSetTrapHandler).size() == 1);
    }
    SECTION("own data by default: our own trap handler is sent") {
        Fixture f(0, false);
        bc5::reimpl::set_data_switches({false, false});
        CHECK(initialize() == kOk);
        CHECK(f.of(kIoctlSetTrapHandler).size() == 1);
    }
    SECTION("trap handler ioctl failure only prints") {
        Fixture f(0, false);
        f.host.ioctl_rc[kIoctlSetTrapHandler] = -1;
        CHECK(initialize() == kOk);
        CHECK(f.logged("trap handler resources"));
    }
    SECTION("init-tail ioctl failure stores zeros") {
        Fixture f(0, false);
        f.host.ioctl_rc[kIoctlInitTail] = -1;
        CHECK(initialize() == kOk);
        CHECK(rd64(f.host.dmem + 0x7FF0) == 0);
        CHECK(rd64(f.host.dmem + 0x7FF8) == 0);
    }
    SECTION("optional hook module and repeated registration") {
        Fixture f(0, false);
        f.host.hook_query = 1;
        CHECK(initialize() == kOk);
        // a second initialisation finds the modules registered: only printed
        CHECK(initialize() == kOk);
        CHECK(f.logged("already loaded"));
    }
}

TEST_CASE("agc_driver: ESVM game process", "[agc_driver]") {
    Fixture f(0x10000u);
    CHECK(f.host.dmem_prot == 0x13);
    CHECK(nid_SFB48L57OKQ() == 1);
    CHECK(f.logged("register shadowing disabled"));
    // default-state CB: graphics restore address replaced, no cross-label writes
    const u32 ctx[2] = {0, 0};
    REQUIRE(sceAgcDriverNotifyDefaultStates(ctx, nullptr, nullptr, 1, 0, 0) == kOk);
    const u64 dm = f.host.dmem;
    // CLEAR_STATE 2, COND_EXEC 5, CONTEXT_CONTROL 3, loads 5 + 5 + 5 -> zero loads start at 25
    CHECK(rd32(dm + 4 * 25) == 0xC0036100u);
    CHECK(rd32(dm + 4 * 26) == 0xDEAD0000u);
    CHECK(rd32(dm + 4 * 62) == 0x80000000u); // CONTEXT_CONTROL without shadow enables
    CHECK(rd32(dm + 4 * 63) == 0xC0004A00u); // CLEAR_STATE, then the CB ends: no label write
    CHECK(rd32(dm + 4 * 65) == 0);
    // agr CB keeps its real shadow base
    CHECK(rd32(dm + 0x400 + 4 * 26) == lo(dm + 0x21000));
}

TEST_CASE("agc_driver: compositor init and submits", "[agc_driver]") {
    Fixture f(1);
    CHECK(f.reqs() == std::vector<u64>{kIoctlClientInfo, kIoctlInitTail});
    CHECK(f.host.mmap_args.empty());
    CHECK(f.host.flex.empty());
    CHECK(f.host.dmem_args[2] == 0x10000);
    REQUIRE(f.host.props.size() == 1);
    CHECK(f.host.props[0].first == "Sce.Debug:Gn2");
    CHECK(nid_NhnGMuunz0Y() == nullptr);
    CHECK(nid_LgctzJSGy7s() == 0);
    CHECK(nid__NIAY3DWpOw() == 0);
    u64 a = 0;
    u32 s = 1;
    CHECK(sceAgcDriverGetReservedDmemForAgc(&a, &s) == kOk);
    CHECK(a == f.host.dmem + 0x10000);
    CHECK(s == 0);
    RegShadowInfo info{};
    CHECK(sceAgcDriverGetRegShadowInfo(&info) == kErrNotPermitted);
    CHECK(sceAgcDriverGetRegShadowInfoAgr(&info) == kErrNotPermitted);
    CHECK(sceAgcDriverSetupRegisterShadow(0, 0, 1, 1, 1) == kErrNotPermitted);
    CHECK(nid_dwoD_LJDQy8() == kErrProcessOrMemory);
    CHECK(nid_NRO47jBXLiI() == kErrProcessOrMemory);
    CHECK(nid_oFb2hMcoJa4(1) == kErrProcessOrMemory);

    // DCB: ring select {3, 0} then a direct IB ioctl on ring 3 (the A half is empty: one packet)
    f.clear();
    const CommandBufferDesc d = desc(0x0000123456789A00u, 0x123456);
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlRingSelect, kIoctlDirectSubmit});
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().ring == 3);
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().mode == 0);
    const auto ds = f.host.ioctls[1].as<DirectSubmitArgs>();
    CHECK(ds.ring == 3);
    CHECK(ds.count == 1);
    CHECK(f.host.ioctls[1].extra32() ==
          std::vector<u32>{0xC0023F00u, 0x56789A00u, 0x1234u, 0x23456u});

    // failure of the direct ioctl
    f.host.ioctl_rc[kIoctlDirectSubmit] = -1;
    CHECK(sceAgcDriverSubmitDcb(&d) == kErrDirectSubmit);
    f.host.ioctl_rc.clear();

    // a handle whose config sets the +0x10 tag uses the tagged direct ioctl
    u8 config[0x38] = {};
    const u32 tag = 9;
    std::memcpy(config + 0x10, &tag, 4);
    const u32 id3 = 3;
    std::memcpy(config + 4, &id3, 4);
    QueueHandle *h = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(3, &h, config, 0) == kOk);
    CHECK(h->direct_tag == 9);
    f.clear();
    REQUIRE(sceAgcDriverSubmitCommandBuffer(h, &d) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlRingSelect, kIoctlDirectSubmitTagged});
    const auto dt = f.host.ioctls[1].as<DirectSubmitTaggedArgs>();
    CHECK(dt.tag == 9);
    CHECK(dt.ring == 3);
    CHECK(dt.count == 1);
    CHECK(dt.zero == 0);

    // multi: one direct ioctl with all packets
    f.clear();
    const u64 addrs[3] = {0x1000, 0x2000, 0x3000};
    const u32 sizes[3] = {4, 5, 6};
    REQUIRE(sceAgcDriverSubmitMultiCommandBuffers(h, addrs, sizes, 3) == kOk);
    CHECK(f.of(kIoctlDirectSubmitTagged).at(0).extra32().size() == 12);

    // compute queues: no UMD memory in a compositor
    QueueHandle *c = nullptr;
    CHECK(sceAgcDriverCreateQueue(0x58, &c, nullptr, 0) == kErrUmdMemoryOrUnmap);
    CHECK(sceAgcDriverCreateQueue(0x20, &c, nullptr, 0) == kErrInvalid);
    CHECK(f.logged("invalid queue index"));

    // async graphics: the submit mode is not set yet in a compositor, so the ioctl is sent
    f.clear();
    f.host.ioctl_rc[kIoctlSetSubmitMode] = -1;
    CHECK(sceAgcDriverSetupAsyncGraphics(1) == kErrProcessOrMemory);
    f.host.ioctl_rc.clear();
    CHECK(sceAgcDriverSetupAsyncGraphics(1) == kOk);
    CHECK(f.of(kIoctlSetSubmitMode).size() == 2);
    CHECK(f.of(kIoctlSetSubmitMode)[1].as<u32>() == 1);
    CHECK(sceAgcDriverSetupAsyncGraphics(0) == kOk);
    CHECK(f.of(kIoctlSetSubmitMode).size() == 2);

    // IDHS goes to ring 3 in a non-game process, counted as "other"
    f.clear();
    CHECK(sceAgcDriverIDHSSubmit(&d) == kErrIdhsSubmitted);
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().ring == 3);
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().mode == 1);
}

TEST_CASE("agc_driver: compositor closes and re-opens /dev/gc around a reset", "[agc_driver]") {
    Fixture f(1);
    QueueHandle *h = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0, &h, nullptr, 0) == kOk);
    CHECK(sceAgcDriverDestroyQueue(h) == kOk);
    CHECK(f.host.close_calls == 1);
    CHECK(f.logged("for a reset"));
    f.clear();
    REQUIRE(sceAgcDriverCreateQueue(0, &h, nullptr, 0) == kOk);
    CHECK(f.host.open_calls == 2);
    CHECK(f.reqs() == std::vector<u64>{kIoctlClientInfo});
    CHECK(f.logged("re-opened"));
    // close failure
    f.host.close_rc = -1;
    CHECK(sceAgcDriverDestroyQueue(h) == kErrMapOrClose);
    // re-open failure
    f.host.close_rc = 0;
    REQUIRE(sceAgcDriverDestroyQueue(h) == kOk);
    f.host.open_rc = -1;
    CHECK(sceAgcDriverCreateQueue(0, &h, nullptr, 0) == kErrGeneric);
}

// =================================================================================================
// Graphics submission

TEST_CASE("agc_driver: first DCB sends the prologue, later ones only the submit", "[agc_driver]") {
    Fixture f;
    f.clear();
    const CommandBufferDesc d = desc(0x0000ABCD12345600u, 0x40);
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxPrologue, kIoctlGfxSubmit});
    const auto pro = f.host.ioctls[0].as<GfxPrologueArgs>();
    CHECK(pro.ring == 0);
    const u64 empty = f.host.dmem + 0x3A200;
    const std::vector<u32> pm4(pro.pm4, pro.pm4 + 15);
    CHECK(pm4 == std::vector<u32>{0xC0012800u, 0, 0, 0xC0023F00u, 0, 0, 0, 0, 0, 0, 0, 0xC0023F00u,
                                  lo(empty), hi16(empty), 2});
    CHECK(pro.result == 1);
    CHECK(pro.extra_ib_used == 0);
    const auto sub = f.host.ioctls[1].as<GfxSubmitArgs>();
    CHECK(sub.ring == 0);
    CHECK(sub.count == 4); // empty pending pair + the user's pair
    CHECK(sub.result == 1);
    CHECK(sub.zero == 0);
    // entries: zero pending pair, then A = 0 and B = the user's buffer with the kernel flag bit
    CHECK(f.host.ioctls[1].extra32() ==
          std::vector<u32>{0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0x12345600u, 0xABCDu, 0x40u, 1u});
    f.clear();
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxSubmit});
    CHECK(f.host.ioctls[0].as<GfxSubmitArgs>().count == 2);
    // log: the GPU-info ring-0 log got two entries with increasing counters
    const u64 gi = f.area("SceGnmGpuInfo");
    CHECK(rd32(gi + 0xB72F0) == 2);
    CHECK(rd64(gi + 0xB72F8 + 8) == 1);
    CHECK(rd64(gi + 0xB72F8 + 0x20 + 8) == 2);
    CHECK(rd32(gi + 0xB72F8 + 0x10) == 4);
    // lock and unlock per submit
    CHECK(f.host.lock_calls == 2);
    CHECK(f.host.unlock_calls == 2);
}

TEST_CASE("agc_driver: graphics submit error codes", "[agc_driver]") {
    Fixture f;
    const CommandBufferDesc d = desc(0x1000, 4);
    SECTION("prologue fails, plain and with result 0x5C") {
        f.host.ioctl_rc[kIoctlGfxPrologue] = -1;
        CHECK(sceAgcDriverSubmitDcb(&d) == static_cast<std::int32_t>(0x8A6D0102u));
        f.host.ioctl_rc.clear();
        f.host.gfx_result = 0x5C;
        CHECK(sceAgcDriverSubmitDcb(&d) == static_cast<std::int32_t>(0x8A6D0103u));
    }
    SECTION("submit fails, plain and with result 0x5C") {
        REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
        f.host.gfx_result = 3;
        CHECK(sceAgcDriverSubmitDcb(&d) == static_cast<std::int32_t>(0x8A6D0100u));
        f.host.gfx_result = 0x5C;
        CHECK(sceAgcDriverSubmitDcb(&d) == static_cast<std::int32_t>(0x8A6D0101u));
        f.host.gfx_result = 0;
        f.host.ioctl_rc[kIoctlGfxSubmit] = -1;
        CHECK(sceAgcDriverSubmitDcb(&d) == kErrGfxSubmit);
    }
    SECTION("lock failures") {
        f.host.lock_rc = -1;
        CHECK(sceAgcDriverSubmitDcb(&d) == kErrQueueLock);
        CHECK(f.logged("unable to lock"));
        f.host.lock_rc = 1;
        CHECK(sceAgcDriverSubmitDcb(&d) == kErrQueueLock);
        CHECK(f.host.unlock_calls == 0);
        Fixture::uninstall("scePthreadMutexLock");
        CHECK(sceAgcDriverSubmitDcb(&d) == kErrQueueLock);
    }
    SECTION("null arguments (deviation)") {
        CHECK(sceAgcDriverSubmitDcb(nullptr) == kErrInvalid);
        CHECK(sceAgcDriverSubmitCommandBuffer(nullptr, &d) == kErrInvalid);
    }
}

TEST_CASE("agc_driver: async graphics ring", "[agc_driver]") {
    Fixture f;
    const CommandBufferDesc d = desc(0x2000, 8);
    CHECK(sceAgcDriverAgrSubmitDcb(&d) == kErrInvalid);
    const u64 addrs[1] = {0x2000};
    const u32 sizes[1] = {8};
    CHECK(sceAgcDriverAgrSubmitMultiDcbs(addrs, sizes, 1) == kErrInvalid);
    CHECK(f.logged("not enabled"));
    f.clear();
    REQUIRE(sceAgcDriverSetupAsyncGraphics(1) == kOk);
    CHECK(f.host.ioctls.empty()); // the mode was set at init
    REQUIRE(sceAgcDriverAgrSubmitDcb(&d) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxPrologue, kIoctlGfxSubmit});
    CHECK(f.host.ioctls[0].as<GfxPrologueArgs>().ring == 4);
    CHECK(f.host.ioctls[1].as<GfxSubmitArgs>().ring == 4);
    const u64 gi = f.area("SceGnmGpuInfo");
    CHECK(rd32(gi + 0xBF300) == 1); // other-ring log
    REQUIRE(sceAgcDriverAgrSubmitMultiDcbs(addrs, sizes, 1) == kOk);
    CHECK(f.host.ioctls.back().as<GfxSubmitArgs>().count == 2);
    REQUIRE(sceAgcDriverSetupAsyncGraphics(0) == kOk);
    CHECK(sceAgcDriverAgrSubmitDcb(&d) == kErrInvalid);
}

TEST_CASE("agc_driver: kernel flag toggles bit 0 of B entries", "[agc_driver]") {
    Fixture f;
    const CommandBufferDesc d = desc(0x3000, 2);
    REQUIRE(nid_oFb2hMcoJa4(0) == kOk);
    f.clear();
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    CHECK(f.of(kIoctlGfxSubmit)[0].extra32()[15] == 0);
    REQUIRE(nid_oFb2hMcoJa4(1) == kOk);
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    CHECK(f.of(kIoctlGfxSubmit)[1].extra32()[7] == 1);
    // the lock is retried until it succeeds
    f.host.lock_rc = 0;
    CHECK(nid_oFb2hMcoJa4(1) == kOk);
}

TEST_CASE("agc_driver: suspend points are queued at the head of the next submit",
          "[agc_driver]") {
    Fixture f;
    const CommandBufferDesc d = desc(0x4000, 4);
    const CommandBufferDesc sp = desc(0x0000000500006000u, 6);
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    f.clear();
    u32 status = 0;
    REQUIRE(sceAgcDriverSuspendPointSubmit(&sp, &status) == kOk);
    // ring 0 had its prologue: reset it, then the suspend check
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxSuspend, kIoctlSuspendCheck});
    CHECK(f.host.ioctls[0].as<GfxSuspendArgs>().ring == 0);
    CHECK(f.host.ioctls[0].as<GfxSuspendArgs>().result == 1);
    const auto chk = f.host.ioctls[1].as<SuspendCheckArgs>();
    CHECK(chk.status == 0);
    CHECK(chk.arg == 0);
    CHECK(chk.out == 0);
    CHECK(status == 7);
    // the next submit: prologue, then the suspend pair and the new pair
    f.clear();
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxPrologue, kIoctlGfxSubmit});
    const auto e = f.host.ioctls[1].extra32();
    REQUIRE(e.size() == 16);
    CHECK(e[4] == 0x6000u);
    CHECK(e[5] == 0x5u);
    CHECK(e[6] == 6u);
    CHECK(e[7] == 1u);
    CHECK(e[12] == 0x4000u);

    SECTION("two suspend points in a row: the first is flushed") {
        f.clear();
        REQUIRE(nid_kAPt2J4U3v8(&sp, &status, 0x55) == kOk);
        REQUIRE(nid_kAPt2J4U3v8(&sp, &status, 0x56) == kOk);
        CHECK(f.reqs() == std::vector<u64>{kIoctlGfxSuspend, kIoctlSuspendCheck, kIoctlGfxPrologue,
                                           kIoctlGfxSubmit, kIoctlGfxSuspend, kIoctlSuspendCheck});
        CHECK(f.host.ioctls[1].as<SuspendCheckArgs>().arg == 0x55);
        CHECK(f.host.ioctls[5].as<SuspendCheckArgs>().arg == 0x56);
        CHECK(f.host.ioctls[3].as<GfxSubmitArgs>().count == 2); // only the pending pair
        // flush failure is not reported by the suspend point
        f.host.gfx_result = 1;
        CHECK(nid_kAPt2J4U3v8(&sp, &status, 0) == kOk);
    }
    SECTION("suspend check failure") {
        f.host.ioctl_rc[kIoctlSuspendCheck] = -1;
        CHECK(sceAgcDriverSuspendPointSubmit(&sp, &status) == kErrSuspendCheck);
        CHECK(f.logged("suspend check failed"));
    }
    SECTION("main lock failure returns the lock error") {
        f.host.lock_rc = -1;
        CHECK(sceAgcDriverSuspendPointSubmit(&sp, &status) == kErrQueueLock);
    }
    SECTION("with async graphics enabled both rings are handled") {
        REQUIRE(sceAgcDriverSetupAsyncGraphics(1) == kOk);
        const CommandBufferDesc ad = desc(0x7000, 2);
        REQUIRE(sceAgcDriverAgrSubmitDcb(&ad) == kOk);
        f.clear();
        REQUIRE(sceAgcDriverSuspendPointSubmit(&sp, &status) == kOk);
        REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxSuspend, kIoctlGfxSuspend, kIoctlSuspendCheck});
        CHECK(f.host.ioctls[0].as<GfxSuspendArgs>().ring == 4);
        CHECK(f.host.ioctls[1].as<GfxSuspendArgs>().ring == 0);
    }
    CHECK(nid_kAPt2J4U3v8(nullptr, &status, 0) == kErrInvalid);
    CHECK(sceAgcDriverIsSuspendPointInFlight() == kErrNotPermitted);
}

TEST_CASE("agc_driver: multi DCB submit goes in batches of 128", "[agc_driver]") {
    Fixture f;
    std::vector<u64> addrs(200);
    std::vector<u32> sizes(200);
    for (u32 i = 0; i < 200; ++i) {
        addrs[i] = 0x10000u + i * 0x100u;
        sizes[i] = i + 1;
    }
    CHECK(sceAgcDriverSubmitMultiDcbs(addrs.data(), sizes.data(), 0) == kErrMultiZero);
    f.clear();
    REQUIRE(sceAgcDriverSubmitMultiDcbs(addrs.data(), sizes.data(), 200) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlGfxPrologue, kIoctlGfxSubmit, kIoctlGfxSubmit});
    CHECK(f.host.ioctls[1].as<GfxSubmitArgs>().count == 2 * 129);
    CHECK(f.host.ioctls[2].as<GfxSubmitArgs>().count == 2 * 72);
    const auto e = f.host.ioctls[2].extra32();
    CHECK(e[4 * 1 + 0] == lo(addrs[128]));
    CHECK(e[4 * 1 + 2] == 129u);
    QueueHandle *h = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0, &h, nullptr, 0) == kOk);
    CHECK(h->batch_first == 256);
    CHECK(h->batch_left == 0);
    // a failing batch stops the loop
    f.clear();
    f.host.gfx_result = 2;
    CHECK(sceAgcDriverSubmitMultiCommandBuffers(h, addrs.data(), sizes.data(), 200) ==
          kErrGfxSubmit);
    CHECK(f.reqs().size() == 1);
    CHECK(h->batch_left == 200);
    CHECK(sceAgcDriverSubmitMultiCommandBuffers(h, nullptr, sizes.data(), 2) == kErrInvalid);
    f.host.lock_rc = -1;
    CHECK(sceAgcDriverSubmitMultiCommandBuffers(h, addrs.data(), sizes.data(), 2) == kErrQueueLock);
}

TEST_CASE("agc_driver: IDHS submit reports success inverted", "[agc_driver]") {
    Fixture f;
    f.clear();
    const CommandBufferDesc d = desc(0x0000000700008000u, 0x123);
    CHECK(sceAgcDriverIDHSSubmit(&d) == kErrIdhsSubmitted);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlRingSelect, kIoctlDirectSubmit});
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().ring == 0);
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().mode == 1);
    CHECK(f.host.ioctls[1].extra32() == std::vector<u32>{0xC0023F00u, 0x8000u, 7u, 0x123u});
    f.host.ioctl_rc[kIoctlDirectSubmit] = -1;
    CHECK(sceAgcDriverIDHSSubmit(&d) == kOk);
    CHECK(sceAgcDriverIDHSSubmit(nullptr) == kErrInvalid);
}

// =================================================================================================
// Compute queues

TEST_CASE("agc_driver: ACB submit writes two IBs into the ring and rings the doorbell",
          "[agc_driver]") {
    Fixture f;
    const u64 acq = f.area("SceGnmACQRB");
    const u64 empty = f.host.dmem + 0x3A200;
    const CommandBufferDesc d = desc(0x0000001200345600u, 0x1FFFFF);
    REQUIRE(sceAgcDriverSubmitAcb(0x20, &d) == kOk);
    CHECK(ring_dwords(acq, 0, 8) == std::vector<u32>{0xC0023F00u, lo(empty), hi16(empty),
                                                     0x00800002u, 0xC0023F00u, 0x00345600u, 0x12u,
                                                     0x00800000u | 0xFFFFFu});
    CHECK(rd32(f.host.doorbell) == 8);
    // second queue: its own ring and doorbell slot
    const CommandBufferDesc z = desc(0, 77);
    REQUIRE(sceAgcDriverSubmitAcb(0x21, &z) == kOk);
    CHECK(rd32(acq + 0x8000 + 4 * 7) == 0x00800000u); // B address 0: size 0
    CHECK(rd32(f.host.doorbell + 8) == 8);
    // compute log in the GPU info area
    const u64 gi = f.area("SceGnmGpuInfo");
    CHECK(rd32(gi + 0xB6448) == 2);
    CHECK(rd32(gi + 0xB6444) == 2);
    CHECK(rd32(gi + 0xB6C50 + 8) == 1);    // vqid of queue 0x20
    CHECK(rd32(gi + 0xB6C50 + 0x10) == 8); // new write pointer
    CHECK(rd32(gi + 0xB6C50 + 0x18 + 8) == 2);
    // queue handle bookkeeping
    QueueHandle *h = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0x20, &h, nullptr, 1) == kOk); // force: re-map, wptr reset
    REQUIRE(sceAgcDriverSubmitAcb(0x20, &d) == kOk);
    REQUIRE(sceAgcDriverSubmitAcb(0x20, &d) == kOk);
    CHECK(rd32(f.host.doorbell) == 16);
    CHECK(h->submit_count == 3);
    auto *e = ptr<ComputeQueueEntry>(h->entry);
    CHECK(e->wptr_dw == 16);
    // ids outside the tables (deviation)
    CHECK(sceAgcDriverSubmitAcb(0x1F, &d) == kErrInvalid);
    CHECK(sceAgcDriverSubmitAcb(0x60, &d) == kErrInvalid);
}

TEST_CASE("agc_driver: ACB ring wraps and waits on the read pointer", "[agc_driver]") {
    Fixture f;
    QueueHandle *h = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0x22, &h, nullptr, 1) == kOk);
    auto *e = ptr<ComputeQueueEntry>(h->entry);
    const CommandBufferDesc d = desc(0x9000, 1);
    // pretend the GPU has consumed everything so far by moving the read pointer with the writes
    for (u32 i = 0; i < 520; ++i) {
        *ptr<u32>(e->rptr_report) = e->wptr_dw;
        REQUIRE(sceAgcDriverSubmitAcb(0x22, &d) == kOk);
    }
    CHECK(e->wptr_dw == (520u * 8u) % 0x1000u);
    CHECK(rd32(e->doorbell_slot) == e->wptr_dw);
}

TEST_CASE("agc_driver: tagged and multi ACB submits", "[agc_driver]") {
    Fixture f;
    const u64 acq = f.area("SceGnmACQRB");
    const CommandBufferDesc d = desc(0xA000, 3);
    QueueHandle *h = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0x23, &h, nullptr, 1) == kOk);
    REQUIRE(nid_F5ZTyyVUHTs(0x23, &d, 0xAA) == kOk);
    CHECK((h->flags & 3u) == 1u);
    CHECK(h->tag == 0xAA);
    REQUIRE(nid_Hb3p8BJm2PI(0x23, &d, 0xBB) == kOk);
    CHECK((h->flags & 3u) == 3u);
    CHECK(h->tag == 0xBB);
    REQUIRE(sceAgcDriverSubmitAcb(0x23, &d) == kOk);
    CHECK((h->flags & 3u) == 0u);
    CHECK(h->tag == 0);
    CHECK(nid_F5ZTyyVUHTs(0x10, &d, 1) == kErrInvalid);
    CHECK(nid_Hb3p8BJm2PI(0x10, &d, 1) == kErrInvalid);
    const u64 addrs[3] = {0x1000, 0x2000, 0x3000};
    const u32 sizes[3] = {1, 2, 3};
    REQUIRE(sceAgcDriverSubmitMultiAcbs(0x24, addrs, sizes, 3) == kOk);
    const u64 ring = acq + 4 * 0x8000;
    CHECK(rd32(ring + 4 * 5) == 0x1000);
    CHECK(rd32(ring + 4 * 13) == 0x2000);
    CHECK(rd32(ring + 4 * 23) == (0x00800000u | 3u));
    CHECK(rd32(f.host.doorbell + 4 * 8) == 24);
    CHECK(sceAgcDriverSubmitMultiAcbs(0x24, addrs, sizes, 0) == kErrMultiZero);
    CHECK(sceAgcDriverSubmitMultiAcbs(0x10, addrs, sizes, 1) == kErrInvalid);
}

TEST_CASE("agc_driver: CreateQueue and DestroyQueue", "[agc_driver]") {
    Fixture f;
    QueueHandle *h = nullptr;
    CHECK(sceAgcDriverCreateQueue(0x20, nullptr, nullptr, 0) == kErrInvalid);
    CHECK(sceAgcDriverCreateQueue(0x60, &h, nullptr, 0) == kErrInvalid);
    // already created without force: success, handle not written
    f.clear();
    CHECK(sceAgcDriverCreateQueue(0x25, &h, nullptr, 0) == kOk);
    CHECK(h == nullptr);
    CHECK(f.host.ioctls.empty());
    CHECK(f.logged("already created"));
    // graphics handle with and without config
    REQUIRE(sceAgcDriverCreateQueue(0, &h, nullptr, 0) == kOk);
    CHECK(h->struct_size == 0x38);
    CHECK(h->flags == kQueueKernelFlag);
    CHECK(h->entry == 0);
    u8 config[0x38] = {};
    const u32 flags = 0x5;
    std::memcpy(config + 8, &flags, 4);
    QueueHandle *g = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0, &g, config, 0) == kOk);
    CHECK(g == h);
    CHECK(g->flags == 5);
    CHECK(g->queue_id == 0); // copied from the config
    // compute with config: the id is re-written
    const u32 cfg_size = 0x40;
    std::memcpy(config, &cfg_size, 4);
    REQUIRE(sceAgcDriverCreateQueue(0x26, &h, config, 1) == kOk);
    CHECK(h->queue_id == 0x26);
    CHECK(h->struct_size == 0x40);
    CHECK(h->flags == 5);
    // map failure
    f.host.ioctl_rc[kIoctlMapComputeQueue] = -5;
    CHECK(sceAgcDriverCreateQueue(0x27, &h, nullptr, 1) == kErrMapOrClose);
    CHECK(f.logged("cannot map queue"));
    f.host.ioctl_rc.clear();
    // destroy
    REQUIRE(sceAgcDriverCreateQueue(0x28, &h, nullptr, 1) == kOk);
    f.clear();
    CHECK(sceAgcDriverDestroyQueue(nullptr) == kErrInvalid);
    REQUIRE(sceAgcDriverDestroyQueue(h) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlUnmapComputeQueue});
    const auto u = f.host.ioctls[0].as<UnmapQueueArgs>();
    CHECK(u.me == 1);
    CHECK(u.pipe == 1);
    CHECK(u.queue == 0);
    CHECK(f.host.destroy_calls == 1);
    CHECK(rd32(f.area("SceGnmGpuInfo") + 0xB6450 + 8 * 0x20) == 0); // record of vqid 9 cleared
    CHECK(sceAgcDriverSubmitAcb(0x28, nullptr) == kErrInvalid);
    // re-create initialises a fresh mutex
    const std::size_t mutexes = f.host.mutex_names.size();
    REQUIRE(sceAgcDriverCreateQueue(0x28, &h, nullptr, 0) == kOk);
    CHECK(f.host.mutex_names.size() == mutexes + 1);
    // unmap failure
    f.host.ioctl_rc[kIoctlUnmapComputeQueue] = -1;
    CHECK(sceAgcDriverDestroyQueue(h) == kErrUmdMemoryOrUnmap);
    f.host.ioctl_rc.clear();
    // a graphics handle in a game has no entry
    QueueHandle *gfx = nullptr;
    REQUIRE(sceAgcDriverCreateQueue(0, &gfx, nullptr, 0) == kOk);
    CHECK(sceAgcDriverDestroyQueue(gfx) == kErrInvalid);
    // a compute entry whose id was configured below 0x20
    u8 low[0x38] = {};
    REQUIRE(sceAgcDriverCreateQueue(0x29, &h, low, 1) == kOk);
    h->queue_id = 0x3;
    CHECK(sceAgcDriverDestroyQueue(h) == kOk);
    CHECK(f.logged("needs no destroy"));
}

TEST_CASE("agc_driver: user special queue (HDR scopes)", "[agc_driver]") {
    Fixture f;
    const CommandBufferDesc d = desc(0xB000, 5);
    CHECK(sceAgcDriverSubmitToHDRScopesACQ(&d) == kErrInvalid);
    CHECK(f.logged("first"));
    f.clear();
    REQUIRE(nid_dwoD_LJDQy8() == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlMapComputeQueue});
    const auto m = f.host.ioctls[0].as<MapQueueArgs>();
    const u64 acq = f.area("SceGnmACQRB");
    CHECK(m.me == 0xAF1E80B7u);
    CHECK(m.pipe == 0x8B4CDD90u);
    CHECK(m.queue == 0x99F68D6Cu);
    CHECK(m.vqid == 0xE5FCC174u);
    CHECK(m.ring_base == acq + 0x1C8000);
    CHECK(m.rptr_report == acq + 0x1CC000);
    CHECK(m.eop_address == f.area("SceGnmEopFifo") + 0x39000);
    CHECK(f.host.mutex_names.back() == "SceAgcSubmitMtx93\n");
    // the report dword was not zeroed by the module: the fake left 0xAB bytes; clear it
    *ptr<u32>(acq + 0x1CC000) = 0;
    const int locks = f.host.lock_calls;
    REQUIRE(sceAgcDriverSubmitToHDRScopesACQ(&d) == kOk);
    CHECK(f.host.lock_calls == locks); // no lock
    CHECK(rd32(acq + 0x1C8000 + 4 * 5) == 0xB000);
    CHECK(rd32(f.host.doorbell + 0x1E8) == 8);
    const u64 gi = f.area("SceGnmGpuInfo");
    CHECK(rd32(gi + 0xB6C50 + 8) == 0x3E);
    CHECK(nid_dwoD_LJDQy8() == kOk); // already created
    CHECK(f.logged("queue 93 already created"));
    f.clear();
    REQUIRE(nid_NRO47jBXLiI() == kOk);
    CHECK(f.host.ioctls[0].as<UnmapQueueArgs>().me == 0xAF1E80B7u);
    CHECK(sceAgcDriverSubmitToHDRScopesACQ(&d) == kErrInvalid);
    f.host.ioctl_rc[kIoctlUnmapComputeQueue] = -1;
    CHECK(nid_NRO47jBXLiI() == kErrMapOrClose);
    f.host.ioctl_rc[kIoctlMapComputeQueue] = -1;
    f.host.err = 12;
    CHECK(nid_dwoD_LJDQy8() == kErrMapOrClose);
    CHECK(f.logged("errno = 12"));
}

TEST_CASE("agc_driver: special queue without UMD memory", "[agc_driver]") {
    Fixture f(0, false);
    f.host.flex_fail = "SceGnmGpuInfo";
    REQUIRE(initialize() == kOk);
    CHECK(nid_dwoD_LJDQy8() == kErrUmdMemoryOrUnmap);
    QueueHandle *h = nullptr;
    CHECK(sceAgcDriverCreateQueue(0x20, &h, nullptr, 1) == kErrUmdMemoryOrUnmap);
    CHECK(sceAgcDriverPassInfoDownward(nullptr, 0) == kOk); // no GPU info: skipped
}

// =================================================================================================
// Register shadow, default and clear state

TEST_CASE("agc_driver: NotifyDefaultStates builds both default-state CBs", "[agc_driver]") {
    Fixture f;
    const u32 ctx[8] = {0, 0, 1, 0, 2, 0, 5, 0};
    const u32 sh[2] = {0x10, 0};
    REQUIRE(sceAgcDriverNotifyDefaultStates(ctx, sh, nullptr, 4, 1, 0) == kOk);
    const u64 dm = f.host.dmem;
    const u64 s = dm + 0x8000;
    const u64 lg = dm + 0x3E0;
    const u64 la = dm + 0x7E0;
    const std::vector<u32> cb = ring_dwords(dm, 0, 74);
    const std::vector<u32> want_head = {
        0xC0004A00u, 0,                                         // CLEAR_STATE
        0xC0032200u, lo(lg), hi(lg), 0, 42,                     // COND_EXEC
        0xC0012800u, 0x91018003u, 0x80000000u,                  // CONTEXT_CONTROL
        0xC0056100u, lo(s), hi(s), 0, 3, 5, 1,                  // LOAD_CONTEXT_REG
        0xC0055F00u, lo(s + 0x8000), hi(s + 0x8000), 0x10, 1, 0x207, 3, // LOAD_SH_REG
        0xC0035E00u, lo(s + 0x9000), hi(s + 0x9000), 0x24D, 1,  // LOAD_UCONFIG_REG
    };
    CHECK(std::vector<u32>(cb.begin(), cb.begin() + 29) == want_head);
    CHECK(cb[29] == 0xC0036100u);
    CHECK(cb[30] == lo(s));
    CHECK(cb[34] == 0xC0035F00u);
    CHECK(cb[39] == 0xC0035E00u);
    CHECK(std::vector<u32>(cb.begin() + 44, cb.begin() + 49) ==
          std::vector<u32>{0xC0033700u, 0x40000200u, lo(lg), hi(lg), 0});
    CHECK(cb[49] == 0xC0036100u);
    CHECK(std::vector<u32>(cb.begin() + 64, cb.begin() + 74) ==
          std::vector<u32>{0xC0012800u, 0x91018003u, 0x80018003u, 0xC0004A00u, 1, 0xC0033700u,
                           0x40000200u, lo(la), hi(la), 1});
    CHECK(rd32(lg) == 0);
    CHECK(rd32(la) == 0);
    // the Agr CB uses its own shadow and label and writes the graphics label
    CHECK(rd32(dm + 0x400 + 4 * 3) == lo(la));
    CHECK(rd32(dm + 0x400 + 4 * 11) == lo(dm + 0x21000));
    CHECK(rd32(dm + 0x400 + 4 * 71) == lo(lg));
    // the next prologue loads it with cache policy 3
    f.clear();
    const CommandBufferDesc d = desc(0x1000, 1);
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    const auto pro = f.host.ioctls[0].as<GfxPrologueArgs>();
    CHECK(pro.pm4[4] == lo(dm));
    CHECK(pro.pm4[5] == hi16(dm));
    CHECK(pro.pm4[6] == (74u | (3u << 28)));
    // no ranges at all: full-range defaults for context; the extra SH/uconfig ranges stay
    REQUIRE(sceAgcDriverNotifyDefaultStates(nullptr, nullptr, nullptr, 0, 0, 0) == kOk);
    CHECK(ring_dwords(dm, 10, 5) == std::vector<u32>{0xC0036100u, lo(s), hi(s), 0, 0x3C0});
    // an offset of 0xFFFFFFFF ends a list
    const u32 term[6] = {4, 0, 0xFFFFFFFFu, 0, 9, 0};
    REQUIRE(sceAgcDriverNotifyDefaultStates(term, nullptr, nullptr, 3, 0, 0) == kOk);
    CHECK(ring_dwords(dm, 10, 5) == std::vector<u32>{0xC0036100u, lo(s), hi(s), 4, 1});
}

TEST_CASE("agc_driver: NotifyDefaultStates needs driver memory (deviation)", "[agc_driver]") {
    Fixture f(2);
    CHECK(sceAgcDriverNotifyDefaultStates(nullptr, nullptr, nullptr, 0, 0, 0) ==
          kErrProcessOrMemory);
}

TEST_CASE("agc_driver: TmpInitIdhs fills defaults from the module data", "[agc_driver]") {
    Fixture f;
    std::vector<u32> pairs(0x800, 0xEEEEEEEEu);
    REQUIRE(sceAgcDriverTmpInitIdhs(pairs.data()) == kOk);
    CHECK(pairs[0] == 0);
    CHECK(pairs[1] == f.fw.u32_at(0x10520));
    CHECK(pairs[2 * 0xD6 + 1] == f.fw.u32_at(0x10520 + 4 * 0xD6));
    CHECK(pairs[2 * 0xD7] == 0xEEEEEEEEu); // not covered
    CHECK(pairs[2 * 0xD8] == 0xD8);
    CHECK(pairs[2 * 0xD8 + 1] == f.fw.u32_at(0x10B20));
    CHECK(pairs[2 * 0x1F5 + 1] == f.fw.u32_at(0x10880));
    CHECK(pairs[2 * 0x2A3 + 1] == f.fw.u32_at(0x10B10));
    CHECK(pairs[2 * 0x3BF + 1] == f.fw.u32_at(0x11070 + 4 * 0xCA));
    CHECK(pairs[2 * 0x3C0] == 0xEEEEEEEEu);
    CHECK(sceAgcDriverTmpInitIdhs(nullptr) == kErrInvalid);
    // Without the file's copy the own defaults (AMD's gfx10 clear state) are used.
    f.fw.present = false;
    std::vector<u32> own(0x800, 1u);
    CHECK(sceAgcDriverTmpInitIdhs(own.data()) == kOk);
    CHECK(own[2 * 0x1E] == 0x1E);
    CHECK(own[2 * 0x1E + 1] == bc5::reimpl::agc_driver::tables::default_context_values()[0x1E]);
    CHECK(own[2 * 0xD7 + 1] == 1u); // not covered
}

TEST_CASE("agc_driver: PatchClearState sends the registers that differ", "[agc_driver]") {
    Fixture f;
    CHECK(sceAgcDriverPatchClearState(nullptr, 0) == kOk);
    CHECK(sceAgcDriverPatchClearState(nullptr, 0x401) == kErrInvalid);
    const u32 d0 = f.fw.u32_at(0x10520);
    const u32 d1 = f.fw.u32_at(0x10524);
    const u32 in[10] = {0, d0, 1, d1 ^ 1u, 0x500, 9, 0xD7, 0, 0xD7, 5};
    // dirty the graphics shadow first
    *ptr<u32>(f.host.dmem + 0x8000) = 0x1234;
    f.clear();
    REQUIRE(sceAgcDriverPatchClearState(in, 5) == kOk);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlPatchClearState, kIoctlRingSelect, kIoctlDirectSubmit});
    CHECK(f.host.ioctls[0].as<PatchClearStateArgs>().count == 2);
    CHECK(f.host.ioctls[0].extra32() == std::vector<u32>{1, d1 ^ 1u, 0xD7, 5});
    CHECK(f.host.ioctls[1].as<RingSelectArgs>().ring == 0);
    CHECK(f.host.ioctls[1].as<RingSelectArgs>().mode == 1);
    const u64 sb2 = f.host.dmem + 0x800;
    CHECK(f.host.ioctls[2].extra32() == std::vector<u32>{0xC0023F00u, lo(sb2), hi16(sb2), 0x12});
    CHECK(rd32(f.host.dmem + 0x8000) == 0);
    f.host.ioctl_rc[kIoctlPatchClearState] = -1;
    CHECK(sceAgcDriverPatchClearState(in, 5) == kErrInvalid);
}

TEST_CASE("agc_driver: SetupRegisterShadow submits the restore CB", "[agc_driver]") {
    Fixture f;
    const u64 dm = f.host.dmem;
    *ptr<u32>(dm + 0x21000) = 0x55;
    f.clear();
    REQUIRE(sceAgcDriverSetupRegisterShadow(4, 1, 1, 1, 1) == kOk);
    CHECK(rd32(dm + 0x21000) == 0);
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlRingSelect, kIoctlDirectSubmit});
    CHECK(f.host.ioctls[0].as<RingSelectArgs>().ring == 4);
    CHECK(f.host.ioctls[1].as<DirectSubmitArgs>().ring == 4);
    CHECK(f.host.ioctls[1].extra32() ==
          std::vector<u32>{0xC0023F00u, lo(dm + 0x880), hi16(dm + 0x880), 0x12});
    f.clear();
    REQUIRE(sceAgcDriverSetupRegisterShadow(0, 0, 0, 0, 2) == kOk);
    CHECK(f.host.ioctls[1].extra32() ==
          std::vector<u32>{0xC0023F00u, lo(dm + 0x900 + 0x3C), hi16(dm + 0x900), 3});
    // 0x101: low byte 1 counts as enable
    f.clear();
    REQUIRE(sceAgcDriverSetupRegisterShadow(0, 0, 1, 0, 0x101) == kOk);
    CHECK(f.host.ioctls[1].extra32()[1] == lo(dm + 0x800));
}

// =================================================================================================
// Kernel settings, system helpers, events

TEST_CASE("agc_driver: TF ring and HS off-chip parameters", "[agc_driver]") {
    Fixture f;
    f.clear();
    REQUIRE(sceAgcDriverSetTFRing(0x123400, 0x8000) == kOk);
    auto a = f.host.ioctls.back().as<TfRingArgs>();
    CHECK(f.host.ioctls.back().req == kIoctlSetTfRing);
    CHECK(a.address == 0x123400);
    CHECK(a.size == 0x8000);
    CHECK(a.pad == 0);
    f.host.soc = 0x840F00;
    REQUIRE(sceAgcDriverSetTFRing(0x123400, 0x8000) == kOk);
    CHECK(f.host.ioctls.back().as<TfRingArgs>().size == 0x4000);
    f.clear();
    CHECK(sceAgcDriverSetTFRing(0x123401, 0x100) == kErrGeneric);
    CHECK(sceAgcDriverSetTFRing(0x123400, 0x102) == kErrGeneric);
    CHECK(f.host.ioctls.empty());
    f.host.ioctl_rc[kIoctlSetTfRing] = -1;
    CHECK(sceAgcDriverSetTFRing(0x123400, 0x100) == kErrGeneric);
    u64 ta = 0;
    u32 ts = 0;
    REQUIRE(sceAgcDriverGetTFRing(&ta, &ts) == kOk);
    CHECK(ta == 0xABCD00);
    CHECK(ts == 0x400);
    f.host.ioctl_rc[kIoctlGetTfRing] = -1;
    CHECK(sceAgcDriverGetTFRing(&ta, &ts) == kErrGeneric);

    f.clear();
    REQUIRE(sceAgcDriverSetHsOffchipParam(0x10011, 0x20022) == kOk);
    const auto hs = f.host.ioctls.back();
    CHECK(hs.req == kIoctlSetHsOffchip);
    CHECK(hs.as<u32>() == 0x00110022u); // {u16 b, u16 a}
    u16 va = 0, vb = 0;
    REQUIRE(sceAgcDriverGetHsOffchipParam(&va, &vb) == kOk);
    CHECK(va == 0x12);
    CHECK(vb == 0x34);
    f.host.ioctl_rc[kIoctlGetHsOffchip] = -1;
    f.host.ioctl_rc[kIoctlSetHsOffchip] = -1;
    CHECK(sceAgcDriverGetHsOffchipParam(&va, &vb) == kErrGeneric);
    CHECK(sceAgcDriverSetHsOffchipParam(1, 2) == kErrGeneric);
}

TEST_CASE("agc_driver: thin ioctl wrappers", "[agc_driver]") {
    Fixture f;
    f.clear();
    u32 r = 0;
    REQUIRE(sceAgcDriverCwsrSuspendAcq(&r) == kOk);
    CHECK(r == 0x77);
    CHECK(f.host.ioctls.back().as<U32PairArgs>().first == 0);
    REQUIRE(sceAgcDriverCwsrSuspendAcq(nullptr) == kOk);
    REQUIRE(sceAgcDriverCwsrResumeAcq() == kOk);
    CHECK(f.host.ioctls.back().as<U32PairArgs>().first == 1);
    CHECK(f.host.ioctls.back().as<U32PairArgs>().second == 0);
    REQUIRE(sceAgcDriverHp3dLockStart() == kOk);
    CHECK(f.host.ioctls.back().req == kIoctlHp3dLock);
    CHECK(f.host.ioctls.back().as<u32>() == 1);
    REQUIRE(sceAgcDriverHp3dLockEnd() == kOk);
    CHECK(f.host.ioctls.back().as<u32>() == 0);
    REQUIRE(nid_NQLvUnSDyBU(3, 4) == kOk);
    CHECK(f.host.ioctls.back().req == kIoctlForwardPair);
    CHECK(f.host.ioctls.back().as<U32PairArgs>().first == 3);
    CHECK(f.host.ioctls.back().as<U32PairArgs>().second == 4);
    CHECK(sceAgcDriverDebugHardwareStatus(0) == 1);
    CHECK(f.host.ioctls.back().req == kIoctlDebugHwStatus);
    CHECK(sceAgcDriverDebugHardwareStatus(1) == 0);
    CHECK(sceAgcDriverSysGetClientNumber() == 5);
    CHECK(sceAgcDriverSysIsGameClosed() == 1);
    CHECK(sceAgcDriverSysEnableSubmitDone45Exception() == kOk);
    CHECK(f.host.ioctls.back().req == kIoctlSysSubmitDone45);
    CHECK(sceAgcDriverSysGetGfxAppGpuResetStatus() == 9u);
    for (u64 req : {kIoctlCwsr, kIoctlHp3dLock, kIoctlForwardPair, kIoctlDebugHwStatus,
                    kIoctlSysClientNumber, kIoctlSysIsGameClosed, kIoctlSysSubmitDone45,
                    kIoctlSysGfxResetStatus}) {
        f.host.ioctl_rc[req] = -1;
    }
    CHECK(sceAgcDriverCwsrSuspendAcq(&r) == kErrMapOrClose);
    CHECK(sceAgcDriverCwsrResumeAcq() == kErrMapOrClose);
    CHECK(sceAgcDriverHp3dLockStart() == kErrGeneric);
    CHECK(sceAgcDriverHp3dLockEnd() == kErrGeneric);
    CHECK(nid_NQLvUnSDyBU(1, 2) == kErrGeneric);
    CHECK(sceAgcDriverDebugHardwareStatus(0) == 0);
    CHECK(sceAgcDriverSysGetClientNumber() == kErrGeneric);
    CHECK(f.logged("client count error"));
    CHECK(sceAgcDriverSysIsGameClosed() == 0);
    CHECK(sceAgcDriverSysEnableSubmitDone45Exception() == kErrGeneric);
    CHECK(sceAgcDriverSysGetGfxAppGpuResetStatus() == 0u);
    // no ioctl import at all
    Fixture::uninstall("ioctl");
    CHECK(sceAgcDriverHp3dLockStart() == kErrGeneric);
}

TEST_CASE("agc_driver: event queue wrappers", "[agc_driver]") {
    Fixture f;
    int eq_dummy = 0;
    int udata = 0;
    REQUIRE(sceAgcDriverAddEqEvent(&eq_dummy, -3, &udata) == kOk);
    REQUIRE(f.host.kevents.size() == 1);
    const KernelEvent &e = f.host.kevents[0];
    CHECK(e.ident == ~u64{2});
    CHECK(e.filter == -14);
    CHECK(e.flags == 1);
    CHECK(e.fflags == 0);
    CHECK(e.data == -3);
    CHECK(e.udata == addr(&udata));
    REQUIRE(sceAgcDriverDeleteEqEvent(&eq_dummy, 0x40) == kOk);
    CHECK(f.host.kevents[1].flags == 2);
    CHECK(f.host.kevents[1].udata == 0);
    CHECK(f.host.kevents[1].ident == 0x40);
    f.host.kevent_rc = -1;
    f.host.err = 22;
    CHECK(sceAgcDriverAddEqEvent(&eq_dummy, 1, nullptr) == static_cast<std::int32_t>(0x80020016u));
    CHECK(sceAgcDriverDeleteEqEvent(&eq_dummy, 1) == static_cast<std::int32_t>(0x80020016u));
    const u64 ev = 0x0007000000420001u;
    CHECK(sceAgcDriverGetEqEventType(&ev) == ev);
    CHECK(sceAgcDriverGetEqContextId(&ev) == (ev >> 16));
}

TEST_CASE("agc_driver: PassInfoDownward fills the GPU info area", "[agc_driver]") {
    Fixture f;
    const u64 gi = f.area("SceGnmGpuInfo");
    const u64 entries[6] = {7, 0x1111, 6, 0x2222, 9, 1};
    REQUIRE(sceAgcDriverPassInfoDownward(entries, 3) == kOk);
    CHECK(rd32(gi + 0xB7250) == 0x98);
    CHECK(rd64(gi + 0xB7258) == 0x2222);
    CHECK(rd64(gi + 0xB7260) == 8);
    CHECK(rd64(gi + 0xB7268) == 0xF);
    CHECK(rd64(gi + 0xB7270) == 0x1234567);
    CHECK(rd32(gi + 0xB7278) == 11);
    CHECK(rd32(gi + 0xB727C) == 33);
    CHECK(rd64(gi + 0xB7280) == 0x101);
    CHECK(rd64(gi + 0xB72A8) == 0x106);
    f.host.flex_size_rc = 1;
    f.host.pts_rc = 1;
    f.host.sysinfo_rc = 1;
    REQUIRE(sceAgcDriverPassInfoDownward(entries, 1) == kOk);
    CHECK(rd64(gi + 0xB7268) == 1);
    // PA-debug accessors of the same area
    CHECK(nid__NIAY3DWpOw() == 0);
    *ptr<u32>(gi) = 5;
    CHECK(nid__NIAY3DWpOw() == 1);
    *ptr<u64>(gi + 0xC8) = 0x998877;
    CHECK(nid_LgctzJSGy7s() == 0x998877);
}

TEST_CASE("agc_driver: debugger exception wrapper", "[agc_driver]") {
    Fixture f;
    CHECK(nid_yuO_lNrj_Do(0, 5) == kErrInvalid);
    CHECK(f.host.raises.empty());
    CHECK(nid_yuO_lNrj_Do(1, 0x77) == kErrInvalid); // the call "succeeded"
    REQUIRE(f.host.raises.size() == 1);
    CHECK(f.host.raises[0].first == 0xA002030Au);
    CHECK(f.host.raises[0].second == 0x77);
    f.host.raise_rc = 1;
    CHECK(nid_yuO_lNrj_Do(1, 0) == kErrProcessOrMemory);
}

// =================================================================================================
// Packets into caller command buffers

TEST_CASE("agc_driver: user data packets", "[agc_driver]") {
    CHECK(sceAgcDriverUserDataGetPacketSize(0) == 3);
    CHECK(sceAgcDriverUserDataGetPacketSize(1) == 4);
    CHECK(sceAgcDriverUserDataGetPacketSize(4) == 4);
    CHECK(sceAgcDriverUserDataGetPacketSize(5) == 9);
    CHECK(sceAgcDriverUserDataGetPacketSize(12) == 10);
    CHECK(sceAgcDriverUserDataGetPacketSize(0xFFFFFFFFu) == 0x40000000u + 7u);
    std::vector<u32> b(32, 0xEEEEEEEEu);
    CHECK(sceAgcDriverUserDataWritePacket(b.data(), 0, 0xC5000001u, nullptr, 0) == 3);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 4) ==
          std::vector<u32>{0xC0017904u, 0x342, 0xC5000001u, 0xEEEEEEEEu});
    const char abc[3] = {'a', 'b', 'c'};
    CHECK(sceAgcDriverUserDataWritePacket(b.data(), 1, 7, abc, 3) == 4);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 4) ==
          std::vector<u32>{0xC0027900u, 0x342, 7, 0x00636261u});
    CHECK(sceAgcDriverUserDataWritePacket(b.data(), 1, 7, nullptr, 9) == 3); // no payload pointer
    const u8 ten[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    CHECK(sceAgcDriverUserDataWritePacket(b.data(), 0, 7, ten, 10) == 10);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 10) ==
          std::vector<u32>{0xC0027904u, 0x342, 7, 0x04030201u, 0xC0043704u, 0x06010000u, 0xC343u,
                           0, 0x08070605u, 0x00000A09u});
    CHECK(sceAgcDriverUserDataWritePopMarker(b.data(), 1) == 3);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 3) ==
          std::vector<u32>{0xC0017900u, 0x342, 0xC2000000u});
    CHECK(sceAgcDriverUserDataWritePopMarker(b.data(), 0) == 3);
    CHECK(b[0] == 0xC0017904u);
}

TEST_CASE("agc_driver: debug markers", "[agc_driver]") {
    std::vector<u32> b(32, 0);
    CHECK(sceAgcDriverUserDataWriteSetMarker(b.data(), 1, "hello", 5, 0xFFFFFFFFu) == 9);
    CHECK(b[2] == 0xC0017FFFu);
    CHECK(b[3] == 0x6C6C6568u);
    CHECK(b[8] == 0x6Fu);
    CHECK(sceAgcDriverUserDataWritePushMarker(b.data(), 1, "hey", 3, 0x12345678u) == 4);
    CHECK(b[2] == 0xC1000000u + 0x8000u + 0x28C2u);
    CHECK(sceAgcDriverUserDataWriteSetMarker(b.data(), 1, nullptr, 0, 0) == 3);
    CHECK(b[2] == 0xC0000000u);
}

TEST_CASE("agc_driver: NOP blob", "[agc_driver]") {
    std::vector<u32> b(8, 0xEEEEEEEEu);
    CHECK(nid_gtvWv7DEKD4(0) == 2);
    CHECK(nid_gtvWv7DEKD4(5) == 4);
    const u8 p[5] = {1, 2, 3, 4, 5};
    CHECK(nid_mQfUoU5_d1g(b.data(), 0x77, p, 5) == 4);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 5) ==
          std::vector<u32>{0xC0021000u, 0x77, 0x04030201u, 0x5u, 0xEEEEEEEEu});
    CHECK(nid_mQfUoU5_d1g(b.data(), 0x78, nullptr, 5) == 2);
    CHECK(b[0] == 0xC0021000u);
    CHECK(b[2] == 0);
}

TEST_CASE("agc_driver: workload streams and packets", "[agc_driver]") {
    Fixture f;
    const u64 status = f.host.dmem + 0x3A000;
    CHECK(sceAgcDriverGetSetWorkloadsActivePacketSize() == 18);
    CHECK(sceAgcDriverGetSetWorkloadCompletePacketSize() == 12);
    CHECK(sceAgcDriverGetSetWorkloadStreamInactivePacketSize() == 9);
    char name[40] = {};
    u64 mask = 1;
    REQUIRE(sceAgcDriverRegisterWorkloadStream(3, "Title stream") == kOk);
    CHECK(sceAgcDriverRegisterWorkloadStream(3, "again") == kErrStreamId);
    CHECK(sceAgcDriverRegisterWorkloadStream(0, "zero") == kErrStreamId);
    CHECK(sceAgcDriverRegisterWorkloadStream(32, "big") == kErrStreamId);
    CHECK(sceAgcDriverRegisterWorkloadStream(4, nullptr) == kErrStreamName);
    REQUIRE(sceAgcDriverRegisterWorkloadStream(5, "a name that is longer than thirty-one bytes") ==
            kOk);
    *ptr<u64>(status + 3 * 8) = 0xF0;
    REQUIRE(sceAgcDriverGetWorkloadStreamInfo(3, name, sizeof name, &mask) == kOk);
    CHECK(std::string(name) == "Title stream");
    CHECK(mask == 0xF0);
    REQUIRE(sceAgcDriverGetWorkloadStreamInfo(3, name, 4, nullptr) == kOk);
    CHECK(std::string(name) == "Tit");
    REQUIRE(sceAgcDriverGetWorkloadStreamInfo(5, name, sizeof name, nullptr) == kOk);
    CHECK(std::strlen(name) == 31);
    CHECK(sceAgcDriverGetWorkloadStreamInfo(4, name, sizeof name, &mask) == kErrStreamNotRegistered);
    CHECK(sceAgcDriverGetWorkloadStreamInfo(0, name, sizeof name, &mask) == kErrStreamId);

    std::vector<u32> b(32, 0);
    const u32 idx[3] = {0, 5, 63};
    REQUIRE(sceAgcDriverSetWorkloadsActive(b.data(), 1, 3, idx, 3) == kOk);
    const u64 target = status + 24;
    CHECK(std::vector<u32>(b.begin(), b.begin() + 18) ==
          std::vector<u32>{0xC0027900u, 0x342, 0xCC000003u, 0x21u, 0xC0033700u, 0x06010000u,
                           0xC343u, 0, 0x80000000u, 0xC0071E00u, 0x267u, lo(target), hi(target),
                           0x21u, 0x80000000u, 0, 0, 0});
    REQUIRE(sceAgcDriverSetWorkloadsActive(b.data(), 0, 3, idx, 1) == kOk);
    CHECK(b[10] == (0x267u | 0x40000000u));
    CHECK(sceAgcDriverSetWorkloadsActive(nullptr, 1, 3, idx, 3) == kErrNullCommandBuffer);
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 0, idx, 3) == kErrStreamId);
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 32, idx, 3) == kErrStreamId);
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 4, idx, 3) == kErrStreamNotRegistered);
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 3, idx, 0) == kErrWorkloadList);
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 3, idx, 65) == kErrWorkloadList);
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 3, nullptr, 1) == kErrWorkloadList);
    const u32 big[1] = {64};
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 3, big, 1) == kErrWorkloadList);
    const u32 dup[2] = {7, 7};
    CHECK(sceAgcDriverSetWorkloadsActive(b.data(), 1, 3, dup, 2) == kErrWorkloadList);

    REQUIRE(sceAgcDriverSetWorkloadComplete(b.data(), 1, 3, 5) == kOk);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 12) ==
          std::vector<u32>{0xC0017900u, 0x342, 0xCD0000A3u, 0xC0071E00u, 0x275u, lo(target),
                           hi(target), 0xFFFFFFDFu, 0xFFFFFFFFu, 0, 0, 0});
    REQUIRE(sceAgcDriverSetWorkloadComplete(b.data(), 0, 3, 63) == kOk);
    CHECK(b[4] == (0x275u | 0x40000000u));
    CHECK(b[8] == 0x7FFFFFFFu);
    CHECK(sceAgcDriverSetWorkloadComplete(nullptr, 1, 3, 5) == kErrNullCommandBuffer);
    CHECK(sceAgcDriverSetWorkloadComplete(b.data(), 1, 40, 5) == kErrStreamId);
    CHECK(sceAgcDriverSetWorkloadComplete(b.data(), 1, 6, 5) == kErrStreamNotRegistered);
    CHECK(sceAgcDriverSetWorkloadComplete(b.data(), 1, 3, 64) == kErrWorkloadList);

    REQUIRE(sceAgcDriverSetWorkloadStreamInactive(b.data(), 1, 3) == kOk);
    CHECK(std::vector<u32>(b.begin(), b.begin() + 9) ==
          std::vector<u32>{0xC0027900u, 0x342, 0xCC000003u, 0, 0xC0033700u, 0x06010000u, 0xC343u,
                           0, 0});
    CHECK(sceAgcDriverSetWorkloadStreamInactive(nullptr, 1, 3) == kErrNullCommandBuffer);
    CHECK(sceAgcDriverSetWorkloadStreamInactive(b.data(), 1, 0) == kErrStreamId);
    CHECK(sceAgcDriverSetWorkloadStreamInactive(b.data(), 1, 9) == kErrStreamNotRegistered);

    CHECK(sceAgcDriverUnregisterWorkloadStream(0) == kErrStreamId);
    CHECK(sceAgcDriverUnregisterWorkloadStream(9) == kErrStreamNotRegistered);
    REQUIRE(sceAgcDriverUnregisterWorkloadStream(3) == kOk);
    CHECK(sceAgcDriverSetWorkloadStreamInactive(b.data(), 1, 3) == kErrStreamNotRegistered);
    REQUIRE(sceAgcDriverRegisterWorkloadStream(3, "back") == kOk);
}

TEST_CASE("agc_driver: SetFlip registers the flip and writes the EOP packets", "[agc_driver]") {
    Fixture f;
    CHECK(sceAgcDriverGetSetFlipPacketSizeInDwords() == 0x40);
    CHECK(sceAgcDriverGetWaitRenderingPacketSizeInDwords() == 0x20);
    std::vector<u32> b(0x40, 0xEEEEEEEEu);
    u32 *cur = b.data();
    f.host.eop_info = 0x08000300u;
    REQUIRE(sceAgcDriverSetFlip(&cur, 0x40, 0, 1, 2, 1, 0x1122334455667788) == kOk);
    CHECK(cur == b.data() + 0x40);
    const u64 label = f.host.label_base + 16;
    CHECK(std::vector<u32>(b.begin(), b.begin() + 19) ==
          std::vector<u32>{0xC0027904u, 0x342, 0xC7010113u, 0x33u, 0xC0043704u, 0x06010000u,
                           0xC343u, 0, 0x55667788u, 0x11223344u, 0xC0064900u, 0x06200504u,
                           0x42010000u, lo(label), hi(label), 1, 0, 0x08000300u, 0xC02C1000u});
    // pipe flag 1, buffer -1: no label, no label query
    cur = b.data();
    f.host.eop_info = 0x1234u;
    const int label_calls = f.host.label_calls;
    REQUIRE(sceAgcDriverSetFlip(&cur, 19, 1, 1, -1, 0x12, 5) == kOk);
    CHECK(f.host.label_calls == label_calls);
    CHECK(b[0] == 0xC0027900u);
    CHECK(b[2] == ((0xC7010000u + (2u << 8) + (0x1Fu << 3)) | 7u));
    CHECK(b[11] == 0x0620062Fu);
    CHECK(b[12] == 0x02010000u);
    CHECK(b[13] == 0);
    CHECK(b[15] == 0);
    CHECK(b[17] == 0x1234u);
    CHECK(b[18] == 0xFFFD1000u); // one-dword pad
    // EOP word with p != 0
    cur = b.data();
    f.host.eop_info = 0x08001000u;
    REQUIRE(sceAgcDriverSetFlip(&cur, 0x40, 1, 1, 0, 0, 0) == kOk);
    CHECK(b[2] == (0xC7011000u | 7u));
    // errors
    cur = b.data();
    CHECK(sceAgcDriverSetFlip(&cur, 0x40, 0, 1, 16, 0, 0) == kErrDisplayBufferIndex);
    CHECK(sceAgcDriverSetFlip(&cur, 0x40, 0, 1, -3, 0, 0) == kErrDisplayBufferIndex);
    CHECK(f.logged("display buffer index"));
    CHECK(sceAgcDriverSetFlip(&cur, 17, 0, 1, 0, 0, 0) == kErrInvalid); // deviation
    f.host.eop_rc = static_cast<int>(0x80290001u);
    CHECK(sceAgcDriverSetFlip(&cur, 0x40, 0, 1, 0, 0, 0) == static_cast<std::int32_t>(0x80290001u));
    f.host.eop_rc = 0;
    f.host.label_rc = static_cast<int>(0x80290002u);
    CHECK(sceAgcDriverSetFlip(&cur, 0x40, 0, 1, 0, 0, 0) == static_cast<std::int32_t>(0x80290002u));
    CHECK(cur == b.data());
    Fixture::uninstall("sceVideoOutSubmitEopFlip");
    CHECK(sceAgcDriverSetFlip(&cur, 0x40, 0, 1, 0, 0, 0) == kErrGeneric);
}

TEST_CASE("agc_driver: WaitUntilSafeForRendering", "[agc_driver]") {
    Fixture f;
    std::vector<u32> b(0x20, 0xEEEEEEEEu);
    u32 *cur = b.data();
    REQUIRE(sceAgcDriverWaitUntilSafeForRendering(&cur, 0x20, 0, 1, 3) == kOk);
    CHECK(cur == b.data() + 0x20);
    const u64 label = f.host.label_base + 24;
    CHECK(std::vector<u32>(b.begin(), b.begin() + 16) ==
          std::vector<u32>{0xC0017904u, 0x342, 0xCB000003u, 0xC0079300u, 0x06000113u, lo(label),
                           hi(label), 0, 0, 0xFFFFFFFFu, 0xFFFFFFFFu, 0x40, 0xC0017904u, 0x342,
                           0xCB000023u, 0xC00F1000u});
    std::fill(b.begin(), b.end(), 0xEEEEEEEEu);
    cur = b.data();
    REQUIRE(sceAgcDriverWaitUntilSafeForRendering(&cur, 0x20, 1, 1, -2) == kOk);
    CHECK(b[2] == 0xCB00001Eu);
    CHECK(b[3] == 0xC0071000u);
    CHECK(b[4] == 0xEEEEEEEEu); // NOP body untouched
    CHECK(b[14] == 0xCB00003Eu);
    cur = b.data();
    CHECK(sceAgcDriverWaitUntilSafeForRendering(&cur, 0x20, 1, 1, 20) == kErrDisplayBufferIndex);
    CHECK(sceAgcDriverWaitUntilSafeForRendering(&cur, 14, 1, 1, 0) == kErrInvalid); // deviation
    f.host.label_rc = -5;
    CHECK(sceAgcDriverWaitUntilSafeForRendering(&cur, 0x20, 1, 1, 0) == -5);
}

// =================================================================================================
// Stubs

TEST_CASE("agc_driver: stubs return their constants", "[agc_driver]") {
    Fixture f;
    const std::int32_t rr = kErrResourceRegistration;
    u64 sz = 5;
    CHECK(sceAgcDriverQueryResourceRegistrationUserMemoryRequirements(&sz) == rr);
    CHECK(sz == 0);
    CHECK(sceAgcDriverQueryResourceRegistrationUserMemoryRequirements(nullptr) == rr);
    for (auto fn : {&sceAgcDriverInitResourceRegistration,
                    &sceAgcDriverGetResourceRegistrationMaxNameLength, &sceAgcDriverRegisterOwner,
                    &sceAgcDriverRegisterResource, &nid_JQc0956gCf0,
                    &sceAgcDriverRegisterGdsResource, &sceAgcDriverUnregisterResource,
                    &sceAgcDriverUnregisterOwnerAndResources,
                    &sceAgcDriverUnregisterAllResourcesForOwner, &sceAgcDriverRegisterDefaultOwner,
                    &sceAgcDriverGetDefaultOwner, &sceAgcDriverFindResourcesPublic,
                    &sceAgcDriverGetResourceName, &sceAgcDriverGetResourceType,
                    &sceAgcDriverGetResourceBaseAddressAndSizeInBytes,
                    &sceAgcDriverGetResourceUserData, &sceAgcDriverSetResourceUserData,
                    &sceAgcDriverGetResourceShaderGuid, &sceAgcDriverGetOwnerName,
                    &nid_VerAUWCtrX0, &nid_IGYqP_WKCgc, &nid__CSrlr1yY_o, &nid_mxyUaQfPgb8,
                    &nid_DGN_IaHNR8o, &nid_38aK8XQj6Cg, &nid_nTwzz_6W9Jg}) {
        CHECK(fn() == rr);
    }
    for (auto fn : {&sceAgcDriverTriggerCapture, &sceAgcDriverRequestCaptureStart,
                    &sceAgcDriverRequestCaptureStop, &nid_jwKQ1B98Q0g, &nid_m9n9wJC2D_4,
                    &nid__iAOE3jCnkk, &nid_WHIOMbb_iIU, &nid_chJWZcNSzjk, &nid_ICaGtkEIXTk,
                    &sceAgcDriverSetValidationErrorOutputFrequency, &nid_sW7yp7NVlrk,
                    &nid_1QTqF_hYqQE}) {
        CHECK(fn() == kErrCaptureUnavailable);
    }
    for (auto fn : {&sceAgcDriverIsCaptureInProgress, &sceAgcDriverIsSubmitValidationEnabled,
                    &sceAgcDriverIsTraceInProgress, &sceAgcDriverIsPaDebug,
                    &sceAgcDriverRegisterGpuResetCallbacks,
                    &sceAgcDriverUnregisterGpuResetCallbacks, &sceAgcDriverGetTraceInitiator,
                    &sceAgcDriverSysSubmitFlipHandleProxy, &sceAgcDriverUserDataImmediateWrite,
                    &sceAgcDriverUserDataImmediateWritePacket, &nid_6v_D6CQHA4Y,
                    &nid__MqhSEVvAPw, &nid_o2gvlIFMF1o, &nid_tD2ECNSuTQQ, &nid_wxdcyVqXJEY,
                    &nid_1l15IdtXNWw, &nid_8CXPPlNmvIc, &nid__JFkLpCDeHM, &nid_6WO4CscVnfM}) {
        CHECK(fn() == 0);
    }
    for (auto fn : {&sceAgcDriverGetGpuPrintfWorkArea, &sceAgcDriverGetGpuRefClks,
                    &nid_Jkypw0U_HYo, &nid_V_rBNI2HzGA, &nid_kFiKcGagv5k, &nid_gpF0LZ3_19c,
                    &nid_J6S2TMmGWgA, &nid_8j6_e3dPf4c, &nid_nhzPF9s5WF0, &nid_Cia3HgY0WiY}) {
        CHECK(fn() == kErrNotPermitted);
    }
    CHECK(sceAgcDriverGetShaderDebuggingStatus() == 1);
    CHECK(nid_9rDcI6cJb_8(1) == kErrNotPermitted);
    nid_O144kUYDSBo();
    nid_NmE3PfE211o();
    // the "permission insufficient" family logs its name
    for (auto fn : {&sceAgcDriverGetPaDebugInterfaceVersion,
                    &sceAgcDriverSubmitMultiCommandBuffersDirect,
                    &sceAgcDriverSuspendPointSubmitDirect, &sceAgcDriverAcquireRazorACQ,
                    &sceAgcDriverReleaseRazorACQ, &sceAgcDriverSubmitToRazorACQ,
                    &sceAgcDriverIsSuspendPointInFlightDirect, &sceAgcDriverSetTFRingDirect,
                    &sceAgcDriverSetHsOffchipParamDirect, &sceAgcDriverSdmaCopyLinearBlocking,
                    &sceAgcDriverRegisterCaptureInterface,
                    &sceAgcDriverDeregisterCaptureInterface,
                    &sceAgcDriverSetTargetRingForDiag}) {
        CHECK(fn() == kErrNotPermitted);
    }
    CHECK(f.logged("sceAgcDriverSdmaCopyLinearBlocking(): permission insufficient"));
    CHECK(f.logged("sceAgcDriverSetTargetRingForDiag(): permission insufficient"));
    u32 out = 9;
    CHECK(nid_EqwPDQyh_Ec(&out) == kOk);
    CHECK(out == 0);
    CHECK(nid_EqwPDQyh_Ec(nullptr) == kErrInvalid);
    out = 9;
    CHECK(nid_pto0YBGGOJo(&out) == kOk);
    CHECK(out == 0);
    CHECK(nid_pto0YBGGOJo(nullptr) == kErrInvalid);
    // tool memory stubs zero 12 bytes
    u8 tm[16];
    std::memset(tm, 0xFF, sizeof tm);
    CHECK(sceAgcDriverAllocateToolMemoryForGpuReset(1, 2, 3, tm) == kErrNotPermitted);
    CHECK(tm[0] == 0);
    CHECK(tm[11] == 0);
    CHECK(tm[12] == 0xFF);
    std::memset(tm, 0xFF, sizeof tm);
    CHECK(sceAgcDriverGetAllocatedToolMemoryForGpuReset(1, tm) == kErrNotPermitted);
    CHECK(tm[11] == 0);
    CHECK(sceAgcDriverAllocateToolMemoryForGpuReset(1, 2, 3, nullptr) == kErrNotPermitted);
    CHECK(sceAgcDriverGetAllocatedToolMemoryForGpuReset(1, nullptr) == kErrNotPermitted);
    CHECK(sceAgcDriverModuleRegistration(0, nullptr) == kErrInvalid);
    CHECK(f.logged("invalid interface"));
    CHECK(sceAgcDriverModuleRegistration(0, &out) == kErrInvalid);
    CHECK(f.logged("invalid index"));
}

TEST_CASE("agc_driver: wavefront debug stubs", "[agc_driver]") {
    u32 v32 = 5;
    u64 v64 = 5;
    CHECK(nid_JvVqPfac9vE(nullptr) == kErrWfNull);
    CHECK(nid_JvVqPfac9vE(&v32) == kErrFeatureUnavailable);
    CHECK(v32 == 0);
    for (auto fn : {&nid_6fugJiMPLGQ, &nid_cRjqDvsrGkg, &nid_dN1zf573IKU}) {
        v64 = 5;
        CHECK(fn(nullptr) == kErrWfNull);
        CHECK(fn(&v64) == kErrFeatureUnavailable);
        CHECK(v64 == 0);
    }
    u32 buf[4] = {1, 2, 3, 4};
    u32 count = 7;
    CHECK(nid_CkL1hUyKZyo(nullptr, &count, 0, 4) == kErrWfNull);
    CHECK(nid_CkL1hUyKZyo(buf, nullptr, 0, 4) == kErrWfNull);
    CHECK(nid_CkL1hUyKZyo(buf, &count, 0, 3) == kErrFeatureUnavailable);
    CHECK(buf[2] == 0xFFFFFFFFu);
    CHECK(buf[3] == 4);
    CHECK(count == 0);
    for (auto fn : {&nid_IfCY5tDfgK8, &nid_RXqABdLqFFA}) {
        u8 z[4] = {1, 1, 1, 1};
        CHECK(fn(nullptr, 4) == kErrWfNull);
        CHECK(fn(z, 0) == kErrWfSizeZero);
        CHECK(fn(z, 3) == kErrFeatureUnavailable);
        CHECK(z[2] == 0);
        CHECK(z[3] == 1);
    }
}

TEST_CASE("agc_driver: reset debug stubs", "[agc_driver]") {
    Fixture f;
    CHECK(nid_Dg_D0_2_m8g() == kErrFeatureUnavailable);
    CHECK(nid_qDjJ_CgiMzs() == 0);
    CHECK(nid_4JOwdjYqMpU(1) == kErrResetMode);
    CHECK(nid_4JOwdjYqMpU(2) == kErrResetMode);
    CHECK(nid_4JOwdjYqMpU(0) == kOk);
    CHECK(nid_KKrEe_LWNG8() == 0);
}

TEST_CASE("agc_driver: every export can be called without a host", "[agc_driver]") {
    // No imports installed and no init: nothing crashes, device paths fail cleanly.
    reset_for_tests();
    set_log([](const char *, const char *) {});
    const CommandBufferDesc d = desc(0x1000, 1);
    CHECK(sceAgcDriverSubmitDcb(&d) == kErrQueueLock);
    CHECK(sceAgcDriverSubmitAcb(0x20, &d) == kOk); // never created: dropped (run rmplF1bb)
    CHECK(sceAgcDriverCwsrResumeAcq() == kErrMapOrClose);
    CHECK(sceAgcDriverGetEqEventType(&d) == 0);
    CHECK(sceAgcDriverGetEqContextId(&d) == 0);
    CHECK(sceAgcDriverAddEqEvent(nullptr, 1, nullptr) == kErrGeneric);
    QueueHandle *h = nullptr;
    CHECK(sceAgcDriverCreateQueue(0x20, &h, nullptr, 0) == kErrInvalid);
    CHECK(sceAgcDriverCreateQueue(0, &h, nullptr, 0) == kOk);
    CHECK(h->flags == kQueueKernelFlag);
    CHECK(nid_oFb2hMcoJa4(0) == kOk);
    CHECK(sceAgcDriverPassInfoDownward(nullptr, 0) == kOk);
    u64 a = 1;
    u32 s = 1;
    CHECK(sceAgcDriverGetReservedDmemForAgc(&a, &s) == kOk);
    CHECK(a == 0);
    CHECK(s == 0);
    CHECK(initialize() == kErrGeneric);
    set_log(nullptr);
    reset_for_tests();
}

// BC5_TEST_DRV_IN=<dir>: an offline compare with a capture of the title's own driver module. The dir
// holds the default-state images init hands NotifyDefaultStates (img-cx.bin, img-sh.bin,
// img-uc.bin: sorted {offset, value} pairs); the test builds BC5's own default-state CBs from them
// (own data, no module file) and writes the first 0x8000 bytes of the driver memory and its base as
// ours-drv-area.bin / ours-drv-base.txt. Nothing happens without the switch.
TEST_CASE("agc_driver: default-state CBs for an offline compare", "[agc_driver][compare]") {
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable : 4996)
#endif
    const char *dir = std::getenv("BC5_TEST_DRV_IN");
    auto open = [](const std::string &p, const char *m) { return std::fopen(p.c_str(), m); };
#ifdef _MSC_VER
#pragma warning(pop)
#endif
    if (dir == nullptr || dir[0] == 0) {
        return;
    }
    auto load = [&](const char *name) {
        std::vector<u32> v;
        if (std::FILE *fp = open(std::string(dir) + "/" + name, "rb"); fp != nullptr) {
            u32 w = 0;
            while (std::fread(&w, 4, 1, fp) == 1) {
                v.push_back(w);
            }
            std::fclose(fp);
        }
        return v;
    };
    const std::vector<u32> cx = load("img-cx.bin"), sh = load("img-sh.bin"), uc = load("img-uc.bin");
    Fixture f(0, false);
    set_firmware_data(nullptr);
    bc5::reimpl::set_data_switches({false, false}); // BC5's own data, as on the box
    REQUIRE(initialize() == kOk);
    REQUIRE(sceAgcDriverNotifyDefaultStates(cx.data(), sh.data(), uc.data(),
                                            static_cast<u32>(cx.size() / 2),
                                            static_cast<u32>(sh.size() / 2),
                                            static_cast<u32>(uc.size() / 2)) == kOk);
    const u64 dm = f.host.dmem;
    if (std::FILE *fp = open(std::string(dir) + "/ours-drv-area.bin", "wb"); fp != nullptr) {
        std::fwrite(reinterpret_cast<const void *>(static_cast<std::uintptr_t>(dm)), 1, 0x8000, fp);
        std::fclose(fp);
    }
    if (std::FILE *fp = open(std::string(dir) + "/ours-drv-base.txt", "w"); fp != nullptr) {
        std::fprintf(fp, "0x%llx\n", static_cast<unsigned long long>(dm));
        std::fclose(fp);
    }
}

// Run rmplF1bb (a capture of the title's own module, 2026-11-21): at libSceAgc's init the resume DCB
// is queued by the suspend submit (only the suspend check goes to the kernel) and its SH stream goes
// to the compute queues; a queue the title has not created takes nothing (no graphics ioctl). The
// prologue and the queued resume go out with the title's first graphics submit, after its own TF-ring
// and HS ioctls.
TEST_CASE("agc_driver: init order: resume queued, SH stream to uncreated queues dropped",
          "[agc_driver]") {
    Fixture f;
    forget_compute_queue_for_tests(0x57); // never created: a zeroed entry, handle queue id 0
    f.clear();
    const CommandBufferDesc resume = desc(0x0000000500006000u, 96);
    const CommandBufferDesc stream = desc(0x0000000500007000u, 55);
    u32 status = 0;
    REQUIRE(nid_kAPt2J4U3v8(&resume, &status, 0) == kOk);
    REQUIRE(sceAgcDriverSubmitAcb(0x57, &stream) == kOk); // never created: dropped
    CHECK(f.logged("never created"));
    REQUIRE(f.reqs() == std::vector<u64>{kIoctlSuspendCheck}); // no prologue, no graphics submit
    // the title's own ioctls come next, then its first DCB: prologue, then the resume at the head
    (void)sceAgcDriverSetHsOffchipParam(0x1FF, 0);
    const CommandBufferDesc d = desc(0x0000000600008000u, 0x40);
    REQUIRE(sceAgcDriverSubmitDcb(&d) == kOk);
    const std::vector<u64> r = f.reqs();
    REQUIRE(r.size() == 4);
    CHECK(r[0] == kIoctlSuspendCheck);
    CHECK(r[2] == kIoctlGfxPrologue);
    CHECK(r[3] == kIoctlGfxSubmit);
    CHECK(f.host.ioctls[3].as<GfxSubmitArgs>().count == 4); // the queued resume pair + the DCB
}
