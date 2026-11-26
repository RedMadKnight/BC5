// SPDX-License-Identifier: GPL-2.0-only
// libScePsml re-creation: lifecycle and dispatch recording against fake imports. The fakes
// implement the libSceAgc / libSceAgcDriver builders as their clean-room descriptions state, a
// kernel that can say "PS5 Pro" or not and maps direct memory at the requested address, a file
// system serving synthetic packages built here, and synthetic firmware data (shader headers and
// code generated in this file; never Sony data).
#include <catch2/catch_test_macros.hpp>

#include "bc5/reimpl/psml_internal.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#if defined(_WIN32)
extern "C" __declspec(dllimport) void *__stdcall VirtualAlloc(void *, std::size_t, unsigned long,
                                                              unsigned long);
extern "C" __declspec(dllimport) int __stdcall VirtualFree(void *, std::size_t, unsigned long);
#else
#include <sys/mman.h>
#endif

using namespace bc5::reimpl;
using namespace bc5::reimpl::psml;
using detail::ld;
using detail::st;

namespace {

// ------------------------------------------------------------------------------------------------
// Call log.
// ------------------------------------------------------------------------------------------------
struct Call {
    std::string name;
    std::vector<std::uint64_t> a;
    std::string text;
};
std::vector<Call> g_calls;
void rec(const char *name, std::vector<std::uint64_t> a = {}, std::string text = {}) {
    g_calls.push_back({name, std::move(a), std::move(text)});
}
std::size_t count_calls(const char *name) {
    return static_cast<std::size_t>(std::count_if(g_calls.begin(), g_calls.end(),
                                                  [&](const Call &c) { return c.name == name; }));
}
std::vector<Call> calls_named(const char *name) {
    std::vector<Call> out;
    for (const Call &c : g_calls) {
        if (c.name == name) {
            out.push_back(c);
        }
    }
    return out;
}

// ------------------------------------------------------------------------------------------------
// Fake libSceAgc / libSceAgcDriver (behaviour per their clean-room descriptions).
// ------------------------------------------------------------------------------------------------
std::uint32_t free_dwords(const AgcCommandBuffer *cb) {
    const std::int64_t d = cb->limit - cb->cursor;
    const std::int64_t f = d - static_cast<std::int64_t>(cb->reserved_dwords);
    return f > 0 ? static_cast<std::uint32_t>(f) : 0u;
}
std::uint32_t *reserve(AgcCommandBuffer *cb, std::uint32_t n) {
    if (free_dwords(cb) < n) {
        if (cb->reserved_dwords > 0xffffffffu - n || cb->out_of_space == nullptr ||
            !cb->out_of_space(cb, cb->reserved_dwords + n, cb->user) || free_dwords(cb) < n) {
            return nullptr;
        }
    }
    auto *p = reinterpret_cast<std::uint32_t *>((reinterpret_cast<std::uintptr_t>(cb->cursor) + 3) &
                                                ~std::uintptr_t{3});
    cb->cursor = p + n;
    return p;
}

std::uint32_t *f_nop(AgcCommandBuffer *cb, std::uint32_t n) {
    rec("nop", {n});
    if (n == 0) {
        return nullptr;
    }
    std::uint32_t *p = reserve(cb, n);
    if (p != nullptr) {
        p[0] = 0xc0001000u | (((n - 2) & 0x3fffu) << 16);
    }
    return p;
}
std::uint32_t *f_sh_direct(AgcCommandBuffer *cb, const RegPair *regs, std::uint32_t count) {
    rec("sh_direct", {count, regs != nullptr ? regs[0].value : 0});
    if (count == 0) {
        return nullptr;
    }
    std::uint32_t *first = nullptr;
    std::uint32_t i = 0;
    while (i < count) {
        std::uint32_t j = i + 1;
        while (j < count && regs[j].offset == regs[j - 1].offset + 1) {
            ++j;
        }
        const std::uint32_t len = j - i;
        std::uint32_t *p = reserve(cb, len + 2);
        if (p != nullptr) {
            p[0] = 0xc0007600u | ((len & 0x3fffu) << 16);
            p[1] = regs[i].offset & 0xffffu;
            for (std::uint32_t k = 0; k < len; ++k) {
                p[2 + k] = regs[i + k].value;
            }
            first = first != nullptr ? first : p;
        }
        i = j;
    }
    return first;
}
std::uint32_t *f_sh_range(AgcCommandBuffer *cb, std::uint32_t start, const std::uint32_t *values,
                          std::uint32_t count) {
    rec("sh_range", {start, count});
    std::uint32_t *p = reserve(cb, count + 2);
    if (p != nullptr) {
        p[0] = 0xc0007600u | ((count & 0x3fffu) << 16);
        p[1] = start & 0xffffu;
        if (values != nullptr) {
            std::memcpy(p + 2, values, count * 4u);
        }
    }
    return p;
}
std::uint32_t *f_dispatch(AgcCommandBuffer *cb, std::uint32_t x, std::uint32_t y, std::uint32_t z,
                          std::uint32_t init) {
    rec("dispatch", {x, y, z, init});
    std::uint32_t *p = reserve(cb, 5);
    if (p != nullptr) {
        p[0] = 0xc0031500u;
        p[1] = x;
        p[2] = y;
        p[3] = z;
        p[4] = (init & 0xa038u) | 0x41u;
    }
    return p;
}
std::uint32_t *marker_packet(AgcCommandBuffer *cb, std::uint32_t word) {
    std::uint32_t *p = reserve(cb, 2);
    if (p != nullptr) {
        p[0] = 0xc0001000u;
        p[1] = word;
    }
    return p;
}
std::uint32_t *f_push_marker(AgcCommandBuffer *cb, const char *name, std::uint32_t) {
    rec("push_marker", {}, name);
    return marker_packet(cb, 0x4b52414du);
}
std::uint32_t *f_push_marker_span(AgcCommandBuffer *cb, const char *name, std::uint32_t len,
                                  std::uint32_t) {
    rec("push_marker_span", {len}, name);
    return marker_packet(cb, 0x4e415053u);
}
std::uint32_t *f_pop_marker(AgcCommandBuffer *cb) {
    rec("pop_marker");
    return marker_packet(cb, 0x504f5021u);
}
std::uint32_t *f_sh_indirect(AgcCommandBuffer *cb, std::uint64_t pairs, std::uint32_t n) {
    rec("sh_indirect", {pairs, n});
    std::uint32_t *p = reserve(cb, 5);
    if (p != nullptr) {
        p[0] = 0xc0036300u;
        p[1] = static_cast<std::uint32_t>(pairs) & ~3u;
        p[2] = static_cast<std::uint32_t>(pairs >> 32);
        p[3] = 0x80000000u;
        p[4] = n & 0x3fffu;
    }
    return p;
}
std::uint32_t *f_event_write(AgcCommandBuffer *cb, std::uint32_t ev, std::uint64_t) {
    rec("event_write", {ev});
    std::uint32_t *p = reserve(cb, 2);
    if (p != nullptr) {
        p[0] = 0xc0004600u;
        p[1] = (ev & 0xffu) | 0x400u;
    }
    return p;
}
std::uint32_t *f_acquire_mem(AgcCommandBuffer *cb, std::uint8_t engine, std::uint32_t coher,
                             std::uint32_t gcr, std::uint64_t base, std::uint64_t size,
                             std::uint32_t poll) {
    rec("acquire_mem", {engine, coher, gcr, base, size, poll});
    std::uint32_t *p = reserve(cb, 8);
    if (p != nullptr) {
        p[0] = 0xc0065800u;
        p[1] = (static_cast<std::uint32_t>(engine) << 31) | (coher & 0x06007fc0u);
        p[2] = 0xffffffffu;
        p[3] = 0xffu;
        p[4] = static_cast<std::uint32_t>(base >> 8);
        p[5] = static_cast<std::uint32_t>(base >> 40);
        p[6] = std::min(poll >> 4, 0xffffu);
        p[7] = gcr & 0x7ffffu;
    }
    return p;
}
// NID zARR5aCmkoY: 11 dwords, opcode 0x1D, per the libSceAgc description.
std::uint32_t *f_bracket(AgcCommandBuffer *cb, std::int32_t engine, std::uint32_t op,
                         std::int32_t mode, std::uint32_t flag40, std::uint32_t field32,
                         std::uint16_t gds_off, std::uint16_t gds_size, std::uint32_t f5,
                         std::uint32_t f6, std::uint64_t d0, std::uint64_t d1) {
    rec("bracket", {static_cast<std::uint64_t>(engine), op, static_cast<std::uint64_t>(mode)});
    std::uint32_t *p = reserve(cb, 11);
    if (p != nullptr) {
        p[0] = 0xc0091d00u;
        p[1] = (op & 0xffu) | ((op & 0x200u) << 7) | (static_cast<std::uint32_t>(mode) << 18) |
               (static_cast<std::uint32_t>(engine) << 30);
        p[2] = flag40 | field32;
        p[3] = gds_off;
        p[4] = gds_size;
        p[5] = f5;
        p[6] = f6;
        p[7] = static_cast<std::uint32_t>(d0);
        p[8] = static_cast<std::uint32_t>(d0 >> 32);
        p[9] = static_cast<std::uint32_t>(d1);
        p[10] = static_cast<std::uint32_t>(d1 >> 32);
    }
    return p;
}
void f_raise(std::uint32_t code, std::uint64_t arg) { rec("raise_exception", {code, arg}); }
std::int32_t f_agc_init(std::uint64_t, std::uint32_t v) {
    rec("agc_init", {v});
    return 0;
}
std::int32_t g_agc_init_result = 0;
std::int32_t f_agc_init_cfg(std::uint64_t a, std::uint32_t v) {
    f_agc_init(a, v);
    return g_agc_init_result;
}
std::int32_t f_capability(std::uint8_t *out) {
    rec("capability");
    *out = 1;
    return 1;
}
const std::uint8_t g_regdefaults[0x40] = {};
const void *f_regdefaults(std::uint32_t v) {
    rec("regdefaults", {v});
    return g_regdefaults;
}
const void *f_regdefaults_internal(std::uint32_t v) {
    rec("regdefaults_internal", {v});
    return g_regdefaults;
}
std::int32_t f_payload(void **out, const std::uint32_t *packet, std::int32_t sub) {
    if (sub != 0) {
        *out = const_cast<std::uint32_t *>(packet + 2);
    } else if (((packet[0] >> 16) & 0x3fffu) == 0x3fffu) {
        *out = nullptr;
    } else {
        *out = const_cast<std::uint32_t *>(packet + 1);
    }
    return 0;
}
// sceAgcCreateShader: magic/version, unset code pointer, self-relative fields made absolute.
std::int32_t f_create_shader(void **out, void *header, std::uint64_t code) {
    rec("create_shader", {reinterpret_cast<std::uint64_t>(header), code});
    auto *h = static_cast<std::uint8_t *>(header);
    if (ld<std::uint32_t>(h, 0) != 0x34333231u) {
        return static_cast<std::int32_t>(0x8a6c0003u);
    }
    if (ld<std::uint64_t>(h, 0x10) != 0) {
        return static_cast<std::int32_t>(0x8a6c001fu);
    }
    for (std::uint32_t f : {0x08u, 0x28u, 0x18u, 0x20u, 0x30u, 0x38u}) {
        const std::uint64_t v = ld<std::uint64_t>(h, f);
        if (v != 0) {
            st<std::uint64_t>(h, f, reinterpret_cast<std::uint64_t>(h + f) + v);
        }
    }
    auto *sub = reinterpret_cast<std::uint8_t *>(ld<std::uint64_t>(h, 0x08));
    for (std::uint32_t k = 0; k < 5; ++k) {
        const std::uint64_t v = ld<std::uint64_t>(sub, 8u * k);
        if (v != 0) {
            st<std::uint64_t>(sub, 8u * k, reinterpret_cast<std::uint64_t>(sub + 8u * k) + v);
        }
    }
    st<std::uint64_t>(h, 0x10, code);
    *out = header;
    return 0;
}
std::uint32_t f_ud_size(std::uint32_t n) {
    if (n == 0) {
        return 3;
    }
    const std::uint32_t d = (n + 3) / 4;
    return d == 1 ? 4 : d + 7;
}
std::uint32_t f_ud_write(std::uint32_t *dst, std::int32_t pipe, std::uint32_t hdr, const void *,
                         std::uint32_t) {
    rec("user_data_packet", {hdr});
    dst[0] = 0xc0017900u | (pipe == 0 ? 4u : 0u);
    dst[1] = 0x342;
    dst[2] = hdr;
    return 3;
}
std::uint32_t f_data_size(std::uint32_t n) { return (n + 3) / 4 + 2; }
std::uint32_t f_data_write(std::uint32_t *dst, std::uint32_t tag, const void *payload,
                           std::uint32_t n) {
    rec("data_packet", {tag, n});
    const std::uint32_t pbytes = (n + 3) & ~3u;
    const std::uint32_t t = pbytes / 4 + 2;
    std::memset(dst, 0, pbytes + 8);
    dst[0] = 0xc0001000u | ((t - 2) << 16);
    dst[1] = tag;
    if (payload != nullptr && n != 0) {
        std::memcpy(dst + 2, payload, n);
        return t;
    }
    return 2;
}

// ------------------------------------------------------------------------------------------------
// Fake kernel: Trinity switch, SDK version, direct memory mapped at the requested address.
// ------------------------------------------------------------------------------------------------
bool g_trinity = true;
std::uint32_t g_sdk = 0x10000000;
int g_fail_map_after = -1;
std::map<std::uint64_t, std::uint64_t> g_maps;
std::uint32_t g_videoout_first = 0;

bool host_map(std::uint64_t va, std::uint64_t len) {
#if defined(_WIN32)
    void *p = VirtualAlloc(reinterpret_cast<void *>(va), len, 0x3000 /*commit|reserve*/,
                           0x04 /*read/write*/);
    return p == reinterpret_cast<void *>(va);
#else
    void *p = mmap(reinterpret_cast<void *>(va), len, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (p != MAP_FAILED && p != reinterpret_cast<void *>(va)) {
        munmap(p, len);
        return false;
    }
    return p != MAP_FAILED;
#endif
}
void host_unmap(std::uint64_t va, std::uint64_t len) {
#if defined(_WIN32)
    (void)len;
    VirtualFree(reinterpret_cast<void *>(va), 0, 0x8000 /*release*/);
#else
    munmap(reinterpret_cast<void *>(va), len);
#endif
}
void unmap_range(std::uint64_t va, std::uint64_t len) {
    for (auto it = g_maps.begin(); it != g_maps.end();) {
        if (it->first >= va && it->first < va + len) {
            host_unmap(it->first, it->second);
            it = g_maps.erase(it);
        } else {
            ++it;
        }
    }
}
void unmap_all() { unmap_range(0, ~std::uint64_t{0}); }

std::int32_t k_mprotect(const void *a, std::uint64_t len, std::int32_t prot) {
    rec("mprotect", {reinterpret_cast<std::uint64_t>(a), len, static_cast<std::uint64_t>(prot)});
    return 0;
}
std::int32_t k_map(void **addr, std::uint64_t len, std::int32_t prot, std::int32_t flags,
                   std::int64_t off, std::uint64_t align, const char *name) {
    rec("map",
        {reinterpret_cast<std::uint64_t>(*addr), len, static_cast<std::uint64_t>(prot),
         static_cast<std::uint64_t>(flags), static_cast<std::uint64_t>(off), align},
        name);
    if (g_fail_map_after == 0) {
        return static_cast<std::int32_t>(0x80020016u);
    }
    if (g_fail_map_after > 0) {
        --g_fail_map_after;
    }
    const std::uint64_t va = reinterpret_cast<std::uint64_t>(*addr);
    if (va == 0 || !host_map(va, len)) {
        return static_cast<std::int32_t>(0x8002000cu);
    }
    g_maps[va] = len;
    return 0;
}
std::int32_t k_munmap(void *a, std::uint64_t len) {
    rec("munmap", {reinterpret_cast<std::uint64_t>(a), len});
    unmap_range(reinterpret_cast<std::uint64_t>(a), len);
    return 0;
}
std::int32_t k_batch(const BatchMapEntry *e, std::int32_t n, std::int32_t *done, std::int32_t) {
    rec("batch_map2", {static_cast<std::uint64_t>(n)});
    for (std::int32_t i = 0; i < n; ++i) {
        unmap_range(reinterpret_cast<std::uint64_t>(e[i].start), e[i].length);
    }
    *done = n;
    return 0;
}
int g_eq_dummy = 0;
std::int32_t k_create_eq(void **eq, const char *name) {
    rec("create_equeue", {}, name);
    *eq = &g_eq_dummy;
    return 0;
}
void *g_timer_udata = nullptr;
void *g_videoout_udata = nullptr;
std::int32_t k_add_user(void *, std::int32_t id) {
    rec("add_user_event", {static_cast<std::uint64_t>(id)});
    return 0;
}
std::int32_t k_add_timer(void *, std::int32_t id, std::uint64_t usec, void *udata) {
    rec("add_timer_event", {static_cast<std::uint64_t>(id), usec});
    g_timer_udata = udata;
    return 0;
}
std::int32_t k_pthread(std::uint64_t *thr, const void *, void *(*)(void *), void *,
                       const char *name) {
    rec("pthread_create", {}, name);
    *thr = 1;
    return 0;
}
std::int32_t k_usleep(std::uint32_t) { return 0; }
std::int32_t k_getpid() { return 42; }
std::int32_t k_swver(void *buf) {
    st<std::uint32_t>(buf, 0x24, 0x09000000u);
    return 0;
}
const char *k_sandbox() { return "sbx"; }
std::int32_t k_sdk(std::uint32_t *out) {
    *out = g_sdk;
    return 0;
}
std::int32_t k_trinity() { return g_trinity ? 1 : 0; }
std::int32_t k_release_tool(std::uint64_t a, std::uint64_t s) {
    rec("release_tool_memory", {a, s});
    return 0;
}
std::int32_t v_add_set_mode(void *, std::int32_t, void *udata) {
    rec("add_set_mode_event2");
    g_videoout_udata = udata;
    return 0;
}
std::int32_t v_query(void *out) {
    std::memset(out, 0, 32);
    st<std::uint32_t>(out, 0, g_videoout_first);
    return 0;
}

// ------------------------------------------------------------------------------------------------
// Fake file system (libc FILE imports).
// ------------------------------------------------------------------------------------------------
std::map<std::string, std::vector<std::uint8_t>> g_files;
struct OpenFile {
    const std::vector<std::uint8_t> *data;
    std::uint64_t pos;
};
std::int32_t c_fopen(void **fp, const char *path, const char *mode) {
    rec("fopen", {}, path);
    auto it = g_files.find(path);
    if (it == g_files.end() || std::string(mode) != "r") {
        *fp = nullptr;
        return 2;
    }
    *fp = new OpenFile{&it->second, 0};
    return 0;
}
std::int32_t c_fseek(void *fp, std::int64_t off, std::int32_t whence) {
    if (whence != 0 || off < 0) {
        return -1;
    }
    static_cast<OpenFile *>(fp)->pos = static_cast<std::uint64_t>(off);
    return 0;
}
std::uint64_t c_fread(void *dst, std::uint64_t size, std::uint64_t n, void *fp) {
    auto *f = static_cast<OpenFile *>(fp);
    const std::uint64_t want = size * n;
    const std::uint64_t have = f->pos < f->data->size() ? f->data->size() - f->pos : 0;
    const std::uint64_t got = std::min(want, have);
    std::memcpy(dst, f->data->data() + f->pos, got);
    f->pos += got;
    return size != 0 ? got / size : 0;
}
std::int32_t c_fclose(void *fp) {
    rec("fclose");
    delete static_cast<OpenFile *>(fp);
    return 0;
}

// ------------------------------------------------------------------------------------------------
// Synthetic shaders and firmware data.
// ------------------------------------------------------------------------------------------------
// A compute shader header in the layout the module reads after creation: register list at 0x70
// (10 pairs, value = tag), user-data layout block at 0x100 (kind 1 slot 0, initiator 0x21,
// count 2 at +0x2a), metadata sub-block at 0xd8.
std::vector<std::uint8_t> make_header(std::uint32_t tag, std::uint32_t code_size) {
    std::vector<std::uint8_t> h(0x130, 0);
    st<std::uint32_t>(h.data(), 0x00, 0x34333231u);
    st<std::uint32_t>(h.data(), 0x04, 0x18);
    st<std::uint64_t>(h.data(), 0x08, 0xd8 - 0x08);
    st<std::uint64_t>(h.data(), 0x20, 0x70 - 0x20);
    st<std::uint64_t>(h.data(), 0x28, 0x100 - 0x28);
    st<std::uint32_t>(h.data(), 0x40, 0x130);
    st<std::uint32_t>(h.data(), 0x44, code_size);
    st<std::uint32_t>(h.data(), 0x4c, 15);
    h[0x5a] = 0;
    h[0x5c] = 10;
    for (std::uint32_t i = 0; i < 10; ++i) {
        st<std::uint32_t>(h.data(), 0x70 + 8 * i, 0x2e00 + i);
        st<std::uint32_t>(h.data(), 0x74 + 8 * i, tag);
    }
    for (std::uint32_t k = 0; k < 8; ++k) {
        st<std::uint16_t>(h.data(), 0x100 + 2 * k, 0xffff);
    }
    st<std::uint16_t>(h.data(), 0x102, 0); // kind 1 slot start
    st<std::uint32_t>(h.data(), 0x110, 0x21);
    st<std::uint16_t>(h.data(), 0x12a, 2);
    return h;
}
std::vector<std::uint8_t> make_code(std::uint32_t size) {
    std::vector<std::uint8_t> c(size, 0x5a);
    std::memcpy(c.data() + size - 0x30, "barefoot", 8);
    return c;
}

class SyntheticFirmware : public FirmwareData {
  public:
    bool available = true;
    std::vector<std::uint64_t> header_requests;
    const std::uint8_t *get(const char *module, std::uint64_t vaddr, std::uint64_t size) override {
        if (!available || std::string(module) != "libScePsml") {
            return nullptr;
        }
        auto &blob = cache_[vaddr];
        if (vaddr == 0x6ac70) { // format table: {channel layout 1, channel type 7} for all
            blob.assign(183 * 8, 0);
            for (std::uint32_t i = 0; i < 183; ++i) {
                st<std::uint32_t>(blob.data(), 8 * i, 1);
                st<std::uint32_t>(blob.data(), 8 * i + 4, 7);
            }
        } else if (vaddr == 0x6ac00) { // keep-copy format remap by log2(bpe)
            blob.assign(0x28, 0);
            const std::uint32_t f[5] = {1, 7, 0x16, 0x3e, 0x4b};
            for (std::uint32_t i = 0; i < 5; ++i) {
                st<std::uint32_t>(blob.data(), 8 * i, f[i]);
            }
        } else if (vaddr >= 0xf4000 && vaddr < 0xfe550 && size == 0x130) {
            header_requests.push_back(vaddr);
            blob = make_header(static_cast<std::uint32_t>(vaddr), 0x100);
        } else if (vaddr >= 0x100000 && vaddr < 0x164db0) {
            blob = make_code(static_cast<std::uint32_t>(size));
        } else {
            return nullptr;
        }
        return blob.size() >= size ? blob.data() : nullptr;
    }

  private:
    std::map<std::uint64_t, std::vector<std::uint8_t>> cache_;
};

// ------------------------------------------------------------------------------------------------
// Synthetic packages.
// ------------------------------------------------------------------------------------------------
void put(std::vector<std::uint8_t> &v, std::uint64_t off, const std::vector<std::uint8_t> &d) {
    if (v.size() < off + d.size()) {
        v.resize(off + d.size(), 0);
    }
    std::memcpy(v.data() + off, d.data(), d.size());
}
std::vector<std::uint8_t> lz4_literals(const std::vector<std::uint8_t> &d) {
    std::vector<std::uint8_t> out = {0xf0};
    std::size_t rest = d.size() - 15;
    while (rest >= 255) {
        out.push_back(255);
        rest -= 255;
    }
    out.push_back(static_cast<std::uint8_t>(rest));
    out.insert(out.end(), d.begin(), d.end());
    return out;
}

// MFSR4K-style package: id, version 0x914, `entries` entries, LZ4 code.
std::vector<std::uint8_t> make_mfsr_package(std::uint16_t id, std::uint32_t entries) {
    std::vector<std::uint8_t> f(0x1000, 0);
    st<std::uint16_t>(f.data(), 4, id);
    st<std::uint16_t>(f.data(), 6, 0x914);
    st<std::uint32_t>(f.data(), 0x0c, 0x100);
    st<std::uint32_t>(f.data(), 0x10, 0x400);
    f[0x28] = 1;
    f[0x29] = 1;
    std::memcpy(f.data() + 0x400 + 0x88, "CFG-TEST", 8);
    std::uint64_t at = 0x1000;
    for (std::uint32_t i = 0; i < entries; ++i) {
        std::uint8_t *e = f.data() + 0x100 + 0x40 * i;
        std::memcpy(e, "P11_60", 6);
        const auto hdr = make_header(0xabc00 + i, 0x100);
        const auto code = lz4_literals(make_code(0x100));
        const std::vector<std::uint8_t> weights(0x100, 0x11);
        const std::vector<std::uint8_t> extra(0x10, 0x22);
        std::vector<std::uint8_t> halves(54, 0);
        st<std::uint16_t>(halves.data(), 0, 0x3c00); // 1.0
        st<std::uint32_t>(e, 0x10, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(e, 0x14, static_cast<std::uint32_t>(hdr.size()));
        put(f, at, hdr);
        at += 0x200;
        e = f.data() + 0x100 + 0x40 * i;
        st<std::uint32_t>(e, 0x18, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(e, 0x1c, static_cast<std::uint32_t>(code.size()));
        st<std::uint32_t>(e, 0x38, 0x100);
        put(f, at, code);
        at += 0x200;
        e = f.data() + 0x100 + 0x40 * i;
        st<std::uint32_t>(e, 0x20, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(e, 0x24, 0x100);
        put(f, at, weights);
        at += 0x100;
        e = f.data() + 0x100 + 0x40 * i;
        st<std::uint32_t>(e, 0x28, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(e, 0x2c, 0x10);
        put(f, at, extra);
        at += 0x100;
        e = f.data() + 0x100 + 0x40 * i;
        st<std::uint32_t>(e, 0x30, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(e, 0x34, 54);
        put(f, at, halves);
        at += 0x100;
    }
    return f;
}

// KPN9 package: `layers` rows, mode 1 (persistent) unless mode0.
std::vector<std::uint8_t> make_kpn9(std::uint32_t layers, bool mode0, bool lz4) {
    std::vector<std::uint8_t> f(0x80 + 64 * layers, 0);
    st<std::uint16_t>(f.data(), 4, 9);
    st<std::uint32_t>(f.data(), 0x08, 0x40);
    f[0x2c] = static_cast<std::uint8_t>((lz4 ? 1 : 0) | (mode0 ? 2 : 0));
    std::memcpy(f.data() + 0x40, "KPN9-SYNTH", 10);
    f[0x50] = static_cast<std::uint8_t>(layers);
    st<std::uint32_t>(f.data(), 0x54, 0x80);
    std::uint64_t at = (f.size() + 0xff) & ~std::size_t{0xff};
    // param block
    st<std::uint32_t>(f.data(), 0x0c, static_cast<std::uint32_t>(at));
    put(f, at, std::vector<std::uint8_t>(0x400, 0x33));
    at += 0x400;
    std::vector<std::uint8_t> consts(0x448);
    for (std::size_t i = 0; i < consts.size(); ++i) {
        consts[i] = static_cast<std::uint8_t>(i);
    }
    st<std::uint32_t>(f.data(), 0x58, static_cast<std::uint32_t>(at));
    st<std::uint32_t>(f.data(), 0x5c, 0x448);
    put(f, at, consts);
    at += 0x500;
    for (std::uint32_t k = 0; k < layers; ++k) {
        const auto hdr = make_header(0x900 + k, 0x100);
        const auto code = lz4 ? lz4_literals(make_code(0x100)) : make_code(0x100);
        const std::vector<std::uint8_t> blob(0x40, static_cast<std::uint8_t>(k));
        const std::uint64_t row = 0x80 + 64ull * k;
        st<std::uint32_t>(f.data(), row + 0x10, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(f.data(), row + 0x14, 0x130);
        put(f, at, hdr);
        at += 0x200;
        st<std::uint32_t>(f.data(), row + 0x18, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(f.data(), row + 0x1c, static_cast<std::uint32_t>(code.size()));
        st<std::uint32_t>(f.data(), row + 0x28, 0x100);
        put(f, at, code);
        at += 0x200;
        st<std::uint32_t>(f.data(), row + 0x20, static_cast<std::uint32_t>(at));
        st<std::uint32_t>(f.data(), row + 0x24, 0x40);
        put(f, at, blob);
        at += 0x100;
        st<std::uint32_t>(f.data(), row + 0x2c, 0x1000 + k);
        f[row + 0x30] = static_cast<std::uint8_t>(k);
    }
    return f;
}

// ------------------------------------------------------------------------------------------------
// Test environment.
// ------------------------------------------------------------------------------------------------
struct Env {
    SyntheticFirmware fw;
    explicit Env(bool trinity = true) {
        unmap_all();
        reset_state_for_tests();
        g_calls.clear();
        g_files.clear();
        g_trinity = trinity;
        g_sdk = 0x10000000;
        g_fail_map_after = -1;
        g_agc_init_result = 0;
        g_videoout_first = 0;
        Imports &im = import_table();
        im = Imports{};
        im.kernel_mprotect = k_mprotect;
        im.kernel_map_named_direct_memory = k_map;
        im.kernel_munmap = k_munmap;
        im.kernel_batch_map2 = k_batch;
        im.kernel_create_equeue = k_create_eq;
        im.kernel_add_user_event = k_add_user;
        im.kernel_add_timer_event = k_add_timer;
        im.pthread_create = k_pthread;
        im.kernel_usleep = k_usleep;
        im.getpid = k_getpid;
        im.kernel_get_prospero_system_sw_version = k_swver;
        im.kernel_get_fs_sandbox_random_word = k_sandbox;
        im.kernel_compiled_sdk_version = k_sdk;
        im.kernel_is_trinity_mode = k_trinity;
        im.kernel_release_tool_memory = k_release_tool;
        im.videoout_sys_add_set_mode_event2 = v_add_set_mode;
        im.videoout_mode_query = v_query;
        im.libc_fopen_s = c_fopen;
        im.libc_fseek = c_fseek;
        im.libc_fread = c_fread;
        im.libc_fclose = c_fclose;
        im.agc_create_shader = f_create_shader;
        im.agc_get_register_defaults2 = f_regdefaults;
        im.agc_get_register_defaults2_internal = f_regdefaults_internal;
        im.agc_cb_set_sh_registers_direct = f_sh_direct;
        im.agc_cb_set_sh_register_range_direct = f_sh_range;
        im.agc_cb_dispatch = f_dispatch;
        im.agc_cb_nop = f_nop;
        im.agc_dcb_push_marker = f_push_marker;
        im.agc_dcb_push_marker_span = f_push_marker_span;
        im.agc_dcb_pop_marker = f_pop_marker;
        im.agc_dcb_set_sh_registers_indirect = f_sh_indirect;
        im.agc_dcb_event_write = f_event_write;
        im.agc_dcb_acquire_mem = f_acquire_mem;
        im.agc_dcb_bracket_packet = f_bracket;
        im.agc_debug_raise_exception = f_raise;
        im.agc_init_with_version = f_agc_init_cfg;
        im.agc_capability_query = f_capability;
        im.agc_get_nop_payload = f_payload;
        im.driver_user_data_get_packet_size = f_ud_size;
        im.driver_user_data_write_packet = f_ud_write;
        im.driver_data_packet_size = f_data_size;
        im.driver_write_data_packet = f_data_write;
        set_firmware_data(&fw);
    }
    ~Env() {
        unmap_all();
        set_firmware_data(nullptr);
        import_table() = Imports{};
        reset_state_for_tests();
    }
    Env(const Env &) = delete;
    Env &operator=(const Env &) = delete;
};

std::vector<PhysicalBlock> blocks(std::size_t n, std::uint64_t first = 0) {
    std::vector<PhysicalBlock> b(n);
    for (std::size_t i = 0; i < n; ++i) {
        b[i] = {(first + i) * 0x200000ull, 0};
    }
    return b;
}
std::vector<Mfsr2MemoryBlock> blocks2(std::size_t n) {
    std::vector<Mfsr2MemoryBlock> b(n);
    for (std::size_t i = 0; i < n; ++i) {
        b[i] = {i * 0x200000ull, 0x200000ull};
    }
    return b;
}

struct Tex {
    std::uint8_t d[32] = {};
    Tex(std::uint32_t w, std::uint32_t h, std::uint32_t fmt, std::uint64_t at = 0x7f0000000000ull) {
        detail::build_texture_desc(d, at, w, h, 0x00000fac00000000ull | fmt, 0);
    }
};

// Walk type-3 packets from the region start: the region must be consumed exactly.
std::size_t walk_packets(const std::uint32_t *p, std::size_t n) {
    std::size_t i = 0;
    while (i < n) {
        const std::uint32_t h = p[i];
        if ((h >> 30) != 3) {
            return static_cast<std::size_t>(-1);
        }
        const std::uint32_t c = (h >> 16) & 0x3fffu;
        i += c == 0x3fffu ? 1u : c + 2u;
    }
    return i;
}
std::size_t find_seq(const std::vector<std::uint32_t> &buf, std::size_t from,
                     const std::vector<std::uint32_t> &seq) {
    for (std::size_t i = from; i + seq.size() <= buf.size(); ++i) {
        if (std::equal(seq.begin(), seq.end(), buf.begin() + static_cast<std::ptrdiff_t>(i))) {
            return i;
        }
    }
    return static_cast<std::size_t>(-1);
}
constexpr std::size_t kNotFound = static_cast<std::size_t>(-1);

const std::vector<std::uint32_t> kBracketOpen = {0xc0091d00u, 0x40050030u, 0, 0x0000c000u, 4, 0,
                                                 0,           0,           0, 1,           0};
const std::vector<std::uint32_t> kBracketClose = {0xc0091d00u, 0x0000000du, 0, 0x0000c000u, 4, 0,
                                                  0,           0,           0, 1,           0};
} // namespace

// ================================================================================================
// Trinity gate and not-initialised paths.
// ================================================================================================
TEST_CASE("not PS5 Pro: both initialise exports fail and every entry stays uninitialised",
          "[psml]") {
    Env env(false);
    REQUIRE(psmlInitialize() == err::kNotTrinity);
    REQUIRE(sceMfsr2Initialize() == err::k2NotTrinity);
    REQUIRE(psmlInitialize() == err::kNotTrinity); // retried, still refused
    REQUIRE(count_calls("create_shader") == 0);
    // mfsr2 ran the module GPU setup before the Trinity check (its order), psml did not need to.
    REQUIRE(count_calls("mprotect") == 2);
    REQUIRE(count_calls("agc_init") == 1);

    MemoryRequirement req{};
    void *obj = nullptr;
    std::uint32_t dw = 0;
    float bias = 0;
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrCreateSharedResources(&obj, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrReleaseSharedResources(nullptr) == err::kNotInitialized);
    REQUIRE(mfsrGetSimpleInitRequirement(&req, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrGetContextAndSharedInitRequirement(&req, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrGetContextInitRequirementV1(&req, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrGetContextInitRequirementV2(&req, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrGetContextInitRequirementV3(&req, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrCreateContextSimple(&obj, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrCreateContextWithOwnSharedResources(&obj, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrCreateContextV1(&obj, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrCreateContextV2(&obj, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrCreateContextV3(&obj, nullptr) == err::kNotInitialized);
    REQUIRE(mfsrReleaseContext(nullptr) == err::kNotInitialized);
    REQUIRE(mfsrGetDispatchCommandSize(nullptr, &dw) == err::kNotInitialized);
    std::uint8_t params[0x200] = {};
    DispatchCommandRegion region{};
    REQUIRE(mfsrDispatchExplicitMatrix(nullptr, &region, params) == err::kNotInitialized);
    REQUIRE(mfsrDispatchFloatCamera(nullptr, &region, params) == err::kNotInitialized);
    REQUIRE(mfsrDispatchDoubleCamera(nullptr, &region, params) == err::kNotInitialized);
    REQUIRE(mfsrDispatchNative(nullptr, &region, params) == err::kNotInitialized);
    REQUIRE(mfsrDispatchNativeValidated(nullptr, &region, params) == err::kNotInitialized);
    REQUIRE(mfsrGetMipLodBias(nullptr, &bias, 960) == err::kNotInitialized);
    REQUIRE(mfsrRequestCapture(nullptr) == err::kNotInitialized);
    REQUIRE(mfsrContextNoOpA(nullptr) == err::kNotInitialized);
    REQUIRE(mfsrContextNoOpB(nullptr) == err::kNotInitialized);

    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&req, nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2CreateSharedResources(&obj, nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2ReleaseSharedResources(nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2CreateContext(&obj, nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2ReleaseContext(nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2GetDispatchCommandSize(nullptr, nullptr) == err::k2NotInitialized);
    REQUIRE(sceMfsr2Dispatch(nullptr, nullptr, nullptr) == err::k2NotInitialized);
}

TEST_CASE("a missing Trinity import reads as not Pro (the module's own fallback)", "[psml]") {
    Env env(true);
    import_table().kernel_is_trinity_mode = nullptr;
    REQUIRE(psmlInitialize() == err::kNotTrinity);
}

TEST_CASE("switch sub-libraries and no-submission stubs need no initialisation", "[psml]") {
    Env env(false);
    REQUIRE(scePsmlNoSubmissionStub0() == 0);
    REQUIRE(scePsmlNoSubmissionStub1() == 0);
    REQUIRE(scePsmlNoSubmissionStub2() == 0);
    REQUIRE(scePsmlEnableSpecularAA() == 0);
    REQUIRE(detail::state().sharpening_permitted == 1);
    REQUIRE(scePsmlEnableQuality8K() == 0);
    REQUIRE(detail::state().feature_bits == 1);
    REQUIRE(scePsmlEnableLightweight() == 0);
    REQUIRE(detail::state().feature_bits == 3);
}

TEST_CASE("set_mfsrversion: null, long strings and the ordering trap", "[psml]") {
    Env env(true);
    REQUIRE(scePsmlSetMfsrVersion(nullptr) == err::kInvalidParameter);
    REQUIRE(detail::state().version_override_set == 0);
    // Set before the first initialise: the system-info gather clears it.
    REQUIRE(scePsmlSetMfsrVersion("09.00") == 0);
    REQUIRE(std::string(detail::effective_version_string()) == "09.00");
    REQUIRE(psmlInitialize() == 0);
    REQUIRE(detail::effective_version_string() == nullptr);
    // Set after initialise: effective.
    REQUIRE(scePsmlSetMfsrVersion("11.60") == 0);
    REQUIRE(std::string(detail::effective_version_string()) == "11.60");
    REQUIRE(version_index(detail::effective_version_string(), 0) == 5);
    // Seven or more characters: Annex K strncpy_s leaves "" while the flag stays set.
    REQUIRE(scePsmlSetMfsrVersion("11.60.0") == 0);
    REQUIRE(detail::state().version_override_set == 1);
    REQUIRE(std::string(detail::effective_version_string()).empty());
    REQUIRE(scePsmlSetMfsrVersion("123456") == 0);
    REQUIRE(std::string(detail::effective_version_string()) == "123456");
}

// ================================================================================================
// Initialisation.
// ================================================================================================
TEST_CASE("psmlInitialize: platform setup, 59 shaders, event thread, once only", "[psml]") {
    Env env(true);
    REQUIRE(psmlInitialize() == 0);
    REQUIRE(count_calls("mprotect") == 2);
    const auto mp = calls_named("mprotect");
    REQUIRE(mp[0].a[1] == 0xa550);
    REQUIRE(mp[0].a[2] == 0x12);
    REQUIRE(mp[1].a[1] == 0x64db0);
    REQUIRE(mp[1].a[2] == 0x11);
    REQUIRE(calls_named("agc_init")[0].a[0] == 13);
    REQUIRE(calls_named("regdefaults")[0].a[0] == 13);
    REQUIRE(calls_named("regdefaults_internal")[0].a[0] == 13);
    REQUIRE(count_calls("create_shader") == 59);
    // Small shaders first, in the description's order, then the 48 kernels from 0xf58f0.
    REQUIRE(env.fw.header_requests.size() == 59);
    REQUIRE(env.fw.header_requests[0] == 0xf9320);
    REQUIRE(env.fw.header_requests[2] == 0xf4e40);
    REQUIRE(env.fw.header_requests[10] == 0xf5690);
    REQUIRE(env.fw.header_requests[11] == 0xf58f0);
    REQUIRE(env.fw.header_requests[58] == 0xf90c0);
    for (std::uint32_t slot = 0; slot < 59; ++slot) {
        REQUIRE(detail::state().group_a[slot] != nullptr);
    }
    // Variant slot pairing: kernel slot 0x16e8b8 (index 12) holds the shader of header 0xf5b50.
    const void *v12 = detail::state().group_a[detail::slot_index(0x16e8b8)];
    REQUIRE(detail::shader_regs(v12)[0].value == 0xf5b50u);
    // Event thread.
    REQUIRE(calls_named("create_equeue")[0].text == "ScePsmlEq");
    REQUIRE(calls_named("add_timer_event")[0].a == std::vector<std::uint64_t>{0x100, 100000});
    REQUIRE(calls_named("add_user_event")[0].a[0] == 1);
    REQUIRE(calls_named("pthread_create")[0].text == "ScePsmlEvent");
    REQUIRE(count_calls("add_set_mode_event2") == 1);
    REQUIRE(psmlInitialize() == err::kAlreadyInitialized);
    REQUIRE(count_calls("create_shader") == 59);
    // MFSR2 initialise now creates only its own 9 shaders.
    REQUIRE(sceMfsr2Initialize() == 0);
    REQUIRE(count_calls("create_shader") == 68);
    REQUIRE(sceMfsr2Initialize() == err::k2AlreadyInitialized);
    // Timer events advance the tick counter; the stop event ends the loop.
    KernelEvent ev{};
    ev.filter = -7;
    ev.ident = 0x100;
    ev.udata = g_timer_udata;
    REQUIRE(handle_event_for_tests(&ev));
    REQUIRE(detail::state().timer_ticks == 1);
    KernelEvent stop{};
    stop.filter = -11;
    stop.ident = 1;
    REQUIRE(!handle_event_for_tests(&stop));
}

TEST_CASE("initialise without shader data fails like a creation failure", "[psml]") {
    Env env(true);
    env.fw.available = false;
    REQUIRE(psmlInitialize() == err::kShaderOrPackage);
    REQUIRE(detail::state().initialised == 0);
    // MFSR2 ignores its own shader failures but the common set still fails.
    REQUIRE(sceMfsr2Initialize() == err::kShaderOrPackage);
}

TEST_CASE("platform setup: an Agc init failure leaves the setup state running (quirk)", "[psml]") {
    Env env(true);
    g_agc_init_result = -5;
    REQUIRE(psmlInitialize() == err::kPlatformInitFailed);
    REQUIRE(detail::state().gpu_setup_state.load() == 1);
}

// ================================================================================================
// MFSR: requirements and shared resources.
// ================================================================================================
TEST_CASE("mfsr: shared requirement per profile and feature bits", "[psml]") {
    Env env(true);
    REQUIRE(psmlInitialize() == 0);
    MemoryRequirement req{};
    SharedResourcesInitParameters sp{};
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, &sp) == 0);
    REQUIRE(req.alignment == 0x200000);
    REQUIRE(req.block_size == 0x200000);
    REQUIRE(req.block_count == 52);
    sp.profile = 1;
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, &sp) == err::kInvalidParameter);
    REQUIRE(scePsmlEnableQuality8K() == 0);
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, &sp) == 0);
    REQUIRE(req.block_count == 196);
    sp.profile = 2;
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, &sp) == err::kInvalidParameter);
    REQUIRE(scePsmlEnableLightweight() == 0);
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, &sp) == 0);
    REQUIRE(req.block_count == 148);
    sp.profile = 3;
    REQUIRE(mfsrGetSharedResourcesInitRequirement(&req, &sp) == err::kInvalidParameter);
}

TEST_CASE("mfsr: context requirements (V1/V2/V3, combined, simple) and the V1 failure quirk",
          "[psml]") {
    Env env(true);
    REQUIRE(psmlInitialize() == 0);
    Tex hist(960, 540, 0x47);
    ContextInitParametersV1 v1{};
    v1.output_width = 960;
    v1.output_height = 540;
    v1.history_keep_template = hist.d;
    MemoryRequirement r1{};
    REQUIRE(mfsrGetContextInitRequirementV1(&r1, &v1) == 0);
    REQUIRE(r1.alignment == 0x200000);
    REQUIRE(r1.block_count > 0);
    MemoryRequirement rc{};
    REQUIRE(mfsrGetContextAndSharedInitRequirement(&rc, &v1) == 0);
    REQUIRE(rc.block_count == r1.block_count + 52);
    // Same sizes through V2 (TextureSizeInfo instead of a template).
    TextureSizeInfo tsi{8, 960, 540};
    ContextInitParametersV2 v2{};
    v2.output_width = 960;
    v2.output_height = 540;
    v2.history_keep_size = &tsi;
    MemoryRequirement r2{};
    REQUIRE(mfsrGetContextInitRequirementV2(&r2, &v2) == 0);
    REQUIRE(r2.block_count == r1.block_count);
    // V2 ignores the reactive size, V3 counts it.
    v2.reactive_keep_size = &tsi;
    MemoryRequirement r2b{};
    MemoryRequirement r3{};
    REQUIRE(mfsrGetContextInitRequirementV2(&r2b, &v2) == 0);
    REQUIRE(mfsrGetContextInitRequirementV3(&r3, &v2) == 0);
    REQUIRE(r2b.block_count == r1.block_count);
    REQUIRE(r3.block_count > r2b.block_count);
    // Profile not allowed: the core zeroes out and fails, the export still adds R (quirk).
    v1.profile = 2;
    MemoryRequirement bad{};
    REQUIRE(mfsrGetContextInitRequirementV1(&bad, &v1) == err::kInvalidParameter);
    REQUIRE(bad.block_count > 0);
    REQUIRE(bad.alignment == 0);
    REQUIRE(mfsrGetContextAndSharedInitRequirement(&bad, &v1) == err::kInvalidParameter);
    // Simple: fixed 3840x2160, history keep only.
    SimpleInitParameters simple{};
    MemoryRequirement rs{};
    REQUIRE(mfsrGetSimpleInitRequirement(&rs, &simple) == 0);
    REQUIRE(rs.block_count > 52 + 32);
    simple.profile = 1;
    REQUIRE(mfsrGetSimpleInitRequirement(&rs, &simple) == err::kInvalidParameter);
    REQUIRE(detail::state().simple_history_size.width == 3840);
    REQUIRE(mfsrGetSimpleInitRequirement(nullptr, &simple) == err::kNullPointer);
}

TEST_CASE("mfsr: shared resources lifecycle, single instance, package missing is swallowed",
          "[psml]") {
    Env env(true);
    REQUIRE(psmlInitialize() == 0);
    auto b = blocks(52);
    SharedResourcesInitParameters sp{0, 0, b.data(), 52, 0};
    // Validation.
    sp.reserved = 1;
    void *srp = nullptr;
    REQUIRE(mfsrCreateSharedResources(&srp, &sp) == err::kInvalidParameter);
    sp.reserved = 0;
    sp.block_count = 51;
    REQUIRE(mfsrCreateSharedResources(&srp, &sp) == err::kInvalidParameter);
    sp.block_count = 52;
    sp.blocks = nullptr;
    REQUIRE(mfsrCreateSharedResources(&srp, &sp) == err::kInvalidParameter);
    sp.blocks = b.data();
    g_sdk = 0x11000000;
    detail::state().compiled_sdk_version = 0x11000000;
    sp.virtual_address_start = 0xfb00100000ull; // not 1 GiB aligned
    REQUIRE(mfsrCreateSharedResources(&srp, &sp) == err::kInvalidParameter);
    sp.virtual_address_start = 0;
    REQUIRE(detail::state().shared_count.load() == 0);
    // Created without a package file: still 0 (quirk of the original).
    REQUIRE(mfsrCreateSharedResources(&srp, &sp) == 0);
    REQUIRE(srp != nullptr);
    REQUIRE(reinterpret_cast<std::uint64_t>(srp) ==
            0xfb00000000ull + 0x6200000 + 0x10000000 + 0x5ffe20);
    const auto maps = calls_named("map");
    REQUIRE(maps.size() == 52);
    REQUIRE(maps[0].a[0] == 0xfb00000000ull);
    REQUIRE(maps[0].a[2] == 0x32);
    REQUIRE(maps[0].a[3] == 0x90);
    REQUIRE(maps[0].text == "ScePsmlSharedResources");
    REQUIRE(calls_named("fopen")[0].text == "/sbx/common/psml_package/MFSR4K_v070.psp");
    void *second = nullptr;
    REQUIRE(mfsrCreateSharedResources(&second, &sp) == err::kSharedExists);
    REQUIRE(mfsrReleaseSharedResources(nullptr) == err::kSharedResourcesArg);
    REQUIRE(mfsrReleaseSharedResources(srp) == 0);
    REQUIRE(detail::state().shared_count.load() == 0);
    REQUIRE(g_maps.empty());
}

TEST_CASE("mfsr: a mapping failure undoes the mapped pages with one batch call", "[psml]") {
    Env env(true);
    REQUIRE(psmlInitialize() == 0);
    auto b = blocks(52);
    SharedResourcesInitParameters sp{0, 0, b.data(), 52, 0};
    g_fail_map_after = 5;
    void *srp = nullptr;
    REQUIRE(mfsrCreateSharedResources(&srp, &sp) == static_cast<std::int32_t>(0x80020016u));
    REQUIRE(count_calls("batch_map2") == 1);
    REQUIRE(calls_named("batch_map2")[0].a[0] == 5);
    REQUIRE(g_maps.empty());
    REQUIRE(detail::state().shared_count.load() == 0);
}

// ================================================================================================
// MFSR: contexts and dispatch.
// ================================================================================================
namespace {
struct MfsrSetup {
    std::vector<PhysicalBlock> shared_blocks = blocks(52);
    void *srp = nullptr;
    Tex hist{960, 540, 0x47};
    ContextInitParametersV1 v1{};
    std::vector<PhysicalBlock> ctx_blocks;
    void *ctx = nullptr;
    std::uint64_t need = 0;
    explicit MfsrSetup(bool with_package) {
        if (with_package) {
            g_files["/sbx/common/psml_package/MFSR4K_v070.psp"] = make_mfsr_package(0xf2f4, 4);
        }
        REQUIRE(psmlInitialize() == 0);
        SharedResourcesInitParameters sp{0, 0, shared_blocks.data(), 52, 0};
        REQUIRE(mfsrCreateSharedResources(&srp, &sp) == 0);
        v1.output_width = 960;
        v1.output_height = 540;
        v1.history_keep_template = hist.d;
        v1.shared_resources = srp;
        MemoryRequirement req{};
        REQUIRE(mfsrGetContextInitRequirementV1(&req, &v1) == 0);
        need = req.block_count;
        ctx_blocks = blocks(need, 100);
        v1.blocks = ctx_blocks.data();
        v1.block_count = need;
    }
};

struct NativeParams {
    std::uint8_t p[0x158] = {};
    Tex out{960, 540, 0x24}, color{480, 270, 0x24}, mv{480, 270, 0x1d}, prev_depth{480, 270, 0x16},
        depth{480, 270, 0x16};
    NativeParams() {
        st<const void *>(p, 0x00, out.d);
        st<const void *>(p, 0x08, color.d);
        st<const void *>(p, 0x10, mv.d);
        st<const void *>(p, 0x18, prev_depth.d);
        st<const void *>(p, 0x20, depth.d);
        st<float>(p, 0x64, 1.0f);
        st<float>(p, 0x68, 1.0f);
        st<float>(p, 0xe8, 0.1f);
        st<float>(p, 0xec, 1000.0f);
        st<std::uint32_t>(p, 0xf0, 480);
        st<std::uint32_t>(p, 0xf4, 270);
        st<float>(p, 0x138, 1.0f);
        st<float>(p, 0x13c, 1.0f);
        st<float>(p, 0x140, 1.0f);
    }
};
} // namespace

TEST_CASE("mfsr: context creation checks", "[psml]") {
    Env env(true);
    MfsrSetup s(false);
    void *ctx = nullptr;
    ContextInitParametersV1 v = s.v1;
    REQUIRE(mfsrCreateContextV1(nullptr, &v) == err::kNullPointer);
    v.reserved0 = 1;
    REQUIRE(mfsrCreateContextV1(&ctx, &v) == err::kInvalidParameter);
    v = s.v1;
    v.output_width = 959;
    REQUIRE(mfsrCreateContextV1(&ctx, &v) == err::kOutputTooSmall);
    v = s.v1;
    v.shared_resources = nullptr;
    REQUIRE(mfsrCreateContextV1(&ctx, &v) == err::kSharedResourcesArg);
    v = s.v1;
    v.block_count = s.need - 1;
    REQUIRE(mfsrCreateContextV1(&ctx, &v) == err::kNotEnoughMemory);
    // V2 / V3 parameter checks.
    TextureSizeInfo tsi{8, 960, 540};
    FsrLutSize lut{0, 16};
    ContextInitParametersV2 v2{};
    v2.blocks = s.ctx_blocks.data();
    v2.block_count = s.need;
    v2.output_width = 960;
    v2.output_height = 540;
    v2.history_keep_size = &tsi;
    v2.shared_resources = s.srp;
    v2.flags = 2;
    REQUIRE(mfsrCreateContextV2(&ctx, &v2) == err::kInvalidParameter);
    v2.flags = 1;
    v2.max_size_fsr_lut_for_keep_copy = &lut;
    REQUIRE(mfsrCreateContextV2(&ctx, &v2) == err::kInvalidParameter);
    REQUIRE(mfsrCreateContextV3(&ctx, &v2) == err::kInvalidParameter);
    lut = {16, 16385};
    REQUIRE(mfsrCreateContextV3(&ctx, &v2) == err::kInvalidParameter);
    v2.flags = 0;
    lut = {16, 16};
    REQUIRE(mfsrCreateContextV3(&ctx, &v2) == err::kInvalidParameter); // LUT without kSupportFsr
    v2.max_size_fsr_lut_for_keep_copy = nullptr;
    v2.reserved_textures[1] = &tsi;
    REQUIRE(mfsrCreateContextV3(&ctx, &v2) == err::kInvalidParameter);
    v2.reserved_textures[1] = nullptr;
    v2.reserved1 = 3;
    REQUIRE(mfsrCreateContextV2(&ctx, &v2) == err::kInvalidParameter);
    REQUIRE(mfsrCreateContextV3(&ctx, &v2) == err::kInvalidParameter);
    // Simple / own-shared creators: argument checks.
    SimpleInitParameters simple{};
    REQUIRE(mfsrCreateContextSimple(&ctx, &simple) == err::kNullPointer);
    simple.blocks = s.ctx_blocks.data();
    simple.profile = 1;
    REQUIRE(mfsrCreateContextSimple(&ctx, &simple) == err::kInvalidParameter);
    simple.profile = 0;
    REQUIRE(mfsrCreateContextSimple(&ctx, &simple) == err::kSharedExists); // one already exists
    ContextInitParametersV1 own = s.v1;
    own.profile = 1;
    REQUIRE(mfsrCreateContextWithOwnSharedResources(&ctx, &own) == err::kInvalidParameter);
    own.blocks = nullptr;
    REQUIRE(mfsrCreateContextWithOwnSharedResources(&ctx, &own) == err::kNullPointer);
    REQUIRE(detail::state().context_count.load() == 0);
    REQUIRE(mfsrReleaseSharedResources(s.srp) == 0);
}

TEST_CASE("mfsr: create, dispatch (Native) records the described work, release", "[psml]") {
    Env env(true);
    MfsrSetup s(true);
    // The package loaded: network shader created from the package's header and LZ4 code.
    REQUIRE(count_calls("create_shader") == 59 + 1);
    REQUIRE(mfsrCreateContextV1(&s.ctx, &s.v1) == 0);
    void *ctx = s.ctx;
    REQUIRE(ld<std::uint32_t>(ctx, 0) == 0x9231u);
    REQUIRE(detail::state().context_count.load() == 1);
    REQUIRE(calls_named("map").back().text == "ScePsmlMfsrContextOutputRfm");
    std::uint32_t dwords = 0;
    REQUIRE(mfsrGetDispatchCommandSize(ctx, &dwords) == 0);
    REQUIRE(dwords == 0x600);
    REQUIRE(mfsrGetDispatchCommandSize(ctx, nullptr) == err::kNullPointer);
    float bias = 0;
    REQUIRE(mfsrGetMipLodBias(ctx, &bias, 480) == 0);
    REQUIRE(bias == -2.0f);
    REQUIRE(mfsrGetMipLodBias(ctx, nullptr, 480) == err::kNullPointer);
    REQUIRE(mfsrRequestCapture(ctx) == 0);
    REQUIRE(detail::state().capture_message_printed == 1);
    REQUIRE(mfsrContextNoOpA(ctx) == 0);
    REQUIRE(mfsrContextNoOpB(ctx) == 0);
    std::uint32_t bogus = 0x1234;
    REQUIRE(mfsrContextNoOpA(&bogus) == err::kBadContext);
    REQUIRE(mfsrContextNoOpB(nullptr) == err::kBadContext);

    NativeParams np;
    std::vector<std::uint32_t> buf(0x600 + 8, 0xdeadbeefu);
    DispatchCommandRegion region{buf.data(), 0x600, 0};
    g_calls.clear();
    REQUIRE(mfsrDispatchNative(ctx, &region, np.p) == 0);
    REQUIRE(ld<std::uint32_t>(ctx, 0) == 0xa9c4u);
    // The region is consumed exactly by whole packets, the guard after it untouched.
    REQUIRE(walk_packets(buf.data(), 0x600) == 0x600);
    REQUIRE(buf[0x600] == 0xdeadbeefu);
    // Raw packets in the described order.
    std::size_t at = 0;
    for (const auto &seq :
         std::vector<std::vector<std::uint32_t>>{{0xc0017904u, 0x342, 0xd2000001u},
                                                 {0x56000003u},
                                                 {0xc0007000u, 0},
                                                 {0xc0006f00u, 0x30000001u},
                                                 kBracketOpen,
                                                 {0xc0007000u, 1},
                                                 {0xc0006f00u, 0x70000002u},
                                                 kBracketClose,
                                                 {0xc0007000u, 2},
                                                 {0xc0017904u, 0x342, 0xd2000000u}}) {
        at = find_seq(buf, at, seq);
        REQUIRE(at != kNotFound);
    }
    // Calls: prepare 1x1x1, exposure 1x1x1, six kernel slices, the network 30x1x1, the copy.
    const auto d = calls_named("dispatch");
    REQUIRE(d.size() == 10);
    REQUIRE(d[0].a[0] == 1);
    REQUIRE(d[1].a[0] == 1);
    for (int i = 2; i < 8; ++i) {
        REQUIRE(d[static_cast<std::size_t>(i)].a[0] == 160); // 8 * floor((960 + 7) / 48)
        REQUIRE(d[static_cast<std::size_t>(i)].a[1] == 544);
    }
    REQUIRE(d[8].a == std::vector<std::uint64_t>{30, 1, 1, 0x21});
    REQUIRE(d[9].a[0] == 480);
    REQUIRE(d[9].a[1] == 270);
    REQUIRE(calls_named("push_marker").size() == 1);
    REQUIRE(calls_named("push_marker")[0].text == "Copy Texture");
    REQUIRE(count_calls("pop_marker") == 1);
    REQUIRE(calls_named("bracket").size() == 2);
    // Main-kernel variant: index 0 (no flags) -> slot 0x16e858 -> header 0xf58f0.
    const auto direct = calls_named("sh_direct");
    REQUIRE(std::any_of(direct.begin(), direct.end(),
                        [](const Call &c) { return c.a[1] == 0xf58f0u; }));
    // Ring index advanced.
    REQUIRE(ld<std::uint8_t>(ctx, 0x3a0) == 1);

    // Other dispatch converters on the same context.
    std::uint8_t matrix[0xd0] = {};
    std::memcpy(matrix, np.p, 0x38);
    st<std::uint32_t>(matrix, 0xa4, 480);
    st<std::uint32_t>(matrix, 0xa8, 270);
    st<float>(matrix, 0x90, 3.0f);
    st<float>(matrix, 0x94, 4.0f);
    std::fill(buf.begin(), buf.end(), 0xdeadbeefu);
    REQUIRE(mfsrDispatchExplicitMatrix(ctx, &region, matrix) == 0);
    REQUIRE(walk_packets(buf.data(), 0x600) == 0x600);
    std::uint8_t cam[0x140] = {};
    std::memcpy(cam, np.p, 0x40);
    st<float>(cam, 0x64, 1.0f);
    st<float>(cam, 0x68, 1.0f);
    st<std::uint32_t>(cam, 0xe4, 480);
    st<std::uint32_t>(cam, 0xe8, 270);
    REQUIRE(mfsrDispatchFloatCamera(ctx, &region, cam) == 0);
    std::uint8_t camd[0x148] = {};
    std::memcpy(camd, np.p, 0x40);
    st<float>(camd, 0x64, 1.0f);
    st<float>(camd, 0x68, 1.0f);
    st<std::uint32_t>(camd, 0xf0, 480);
    st<std::uint32_t>(camd, 0xf4, 270);
    REQUIRE(mfsrDispatchDoubleCamera(ctx, &region, camd) == 0);
    REQUIRE(ld<std::uint8_t>(ctx, 0x3a0) == 4);

    // Validated dispatch: a missing required texture is reported first.
    NativeParams bad;
    st<const void *>(bad.p, 0x08, nullptr);
    REQUIRE(mfsrDispatchNativeValidated(ctx, &region, bad.p) == err::kMissingTexture);
    NativeParams strict;
    st<float>(strict.p, 0x150, 1.0f);
    REQUIRE(mfsrDispatchNativeValidated(ctx, &region, strict.p) == err::kInvalidParameter);
    NativeParams good;
    REQUIRE(mfsrDispatchNativeValidated(ctx, &region, good.p) == 0);

    // A too-small region: the out-of-space handler raises the Agc exception, the raw packet fails.
    std::vector<std::uint32_t> small(40, 0);
    DispatchCommandRegion tiny{small.data(), 40, 0};
    g_calls.clear();
    const std::int32_t r = mfsrDispatchNative(ctx, &tiny, np.p);
    REQUIRE((r == err::kNoRoomForPacket || r == err::kScratchAllocFailed));
    REQUIRE(count_calls("raise_exception") >= 1);
    REQUIRE(calls_named("raise_exception")[0].a == std::vector<std::uint64_t>{1, 0});

    // Video-out gate through the registered set-mode callback.
    g_videoout_first = 1;
    KernelEvent ev{};
    ev.filter = -13;
    ev.udata = g_videoout_udata;
    REQUIRE(handle_event_for_tests(&ev));
    REQUIRE(mfsrDispatchNative(ctx, &region, np.p) == err::kVideoOutRefused);
    g_videoout_first = 0;
    REQUIRE(handle_event_for_tests(&ev));
    REQUIRE(mfsrDispatchNative(ctx, nullptr, np.p) == err::kNullPointer);
    REQUIRE(mfsrDispatchNative(nullptr, &region, np.p) == err::kBadContext);

    // Releasing the shared resources while the context lives fails but still decrements (quirk).
    REQUIRE(mfsrReleaseSharedResources(s.srp) == err::kBadContext);
    REQUIRE(detail::state().shared_count.load() == 0);
    REQUIRE(mfsrReleaseContext(ctx) == 0);
    REQUIRE(detail::state().context_count.load() == 0);
    REQUIRE(mfsrReleaseSharedResources(s.srp) == 0);
    REQUIRE(detail::state().shared_count.load() == -1);
    REQUIRE(g_maps.empty());
}

TEST_CASE("mfsr: four contexts per process, the fifth is refused before mapping", "[psml]") {
    Env env(true);
    MfsrSetup s(false);
    std::vector<void *> ctxs;
    std::vector<std::vector<PhysicalBlock>> keep;
    for (int i = 0; i < 4; ++i) {
        keep.push_back(blocks(s.need, 200 + 50 * static_cast<std::uint64_t>(i)));
        ContextInitParametersV1 v = s.v1;
        v.blocks = keep.back().data();
        void *c = nullptr;
        REQUIRE(mfsrCreateContextV1(&c, &v) == 0);
        REQUIRE(ld<std::uint8_t>(c, 4) == i);
        ctxs.push_back(c);
    }
    void *c5 = nullptr;
    const std::size_t maps_before = count_calls("map");
    REQUIRE(mfsrCreateContextV1(&c5, &s.v1) == err::kTooManyContexts);
    REQUIRE(count_calls("map") == maps_before);
    for (void *c : ctxs) {
        REQUIRE(mfsrReleaseContext(c) == 0);
    }
    REQUIRE(mfsrReleaseSharedResources(s.srp) == 0);
}

TEST_CASE("mfsr: V2/V3 creators with kSupportFsr and the own-shared creator", "[psml]") {
    Env env(true);
    MfsrSetup s(false);
    TextureSizeInfo tsi{8, 960, 540};
    FsrLutSize lut{64, 64};
    ContextInitParametersV2 v2{};
    v2.output_width = 960;
    v2.output_height = 540;
    v2.history_keep_size = &tsi;
    v2.reactive_keep_size = &tsi;
    v2.shared_resources = s.srp;
    v2.flags = 1;
    v2.max_size_fsr_lut_for_keep_copy = &lut;
    MemoryRequirement req{};
    REQUIRE(mfsrGetContextInitRequirementV3(&req, &v2) == 0);
    auto b = blocks(req.block_count, 300);
    v2.blocks = b.data();
    v2.block_count = req.block_count;
    void *c3 = nullptr;
    REQUIRE(mfsrCreateContextV3(&c3, &v2) == 0);
    REQUIRE(ld<std::uint32_t>(c3, 0x1a8c) == 1);
    REQUIRE(ld<std::uint8_t>(c3, 0x228) == (2 | 4 | 8));
    REQUIRE(mfsrReleaseContext(c3) == 0);
    MemoryRequirement req2{};
    REQUIRE(mfsrGetContextInitRequirementV2(&req2, &v2) == 0);
    auto b2 = blocks(req2.block_count, 400);
    v2.blocks = b2.data();
    v2.block_count = req2.block_count;
    void *c2 = nullptr;
    REQUIRE(mfsrCreateContextV2(&c2, &v2) == 0);
    REQUIRE(ld<std::uint8_t>(c2, 0x228) == (2 | 8));
    REQUIRE(mfsrReleaseContext(c2) == 0);
    REQUIRE(mfsrReleaseSharedResources(s.srp) == 0);
    REQUIRE(detail::state().shared_count.load() == 0);

    // Own shared resources: the context releases them, the shared count stays 1 (quirk).
    ContextInitParametersV1 own = s.v1;
    own.shared_resources = nullptr;
    MemoryRequirement rq{};
    REQUIRE(mfsrGetContextAndSharedInitRequirement(&rq, &own) == 0);
    auto ob = blocks(rq.block_count, 500);
    own.blocks = ob.data();
    own.block_count = rq.block_count;
    void *oc = nullptr;
    REQUIRE(mfsrCreateContextWithOwnSharedResources(&oc, &own) == 0);
    REQUIRE(ld<std::uint8_t>(oc, 0x368) == 1);
    REQUIRE(mfsrReleaseContext(oc) == 0);
    REQUIRE(detail::state().shared_count.load() == 1);
    REQUIRE(g_maps.empty());
    SimpleInitParameters simple{0, 0, ob.data(), ob.size()};
    void *sc = nullptr;
    REQUIRE(mfsrCreateContextSimple(&sc, &simple) == err::kSharedExists);
}

// ================================================================================================
// MFSR2.
// ================================================================================================
namespace {
struct Mfsr2Setup {
    std::vector<Mfsr2MemoryBlock> sb;
    void *shared = nullptr;
    Mfsr2ContextInitParameters cp{};
    std::vector<Mfsr2MemoryBlock> cb;
    void *ctx = nullptr;
    Mfsr2Setup(bool package, bool mode0) {
        if (package) {
            g_files["/sbx/common/psml_package/KPN9_v070.psp"] =
                make_kpn9(mode0 ? 17 : 3, mode0, true);
        }
        REQUIRE(sceMfsr2Initialize() == 0);
        Mfsr2SharedResourcesInitParameters sp{0, 0, nullptr, 0, 3840, 2160, 0};
        MemoryRequirement req{};
        REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&req, &sp) == 0);
        sb = blocks2(req.block_count);
        sp.blocks = sb.data();
        sp.block_count = req.block_count;
        REQUIRE(sceMfsr2CreateSharedResources(&shared, &sp) == 0);
        cp.shared_resources = shared;
        cp.output_color_width = 960;
        cp.output_color_height = 540;
        MemoryRequirement creq{};
        REQUIRE(sceMfsr2GetContextInitRequirement(&creq, &cp) == 0);
        cb = blocks2(creq.block_count);
        cp.blocks = cb.data();
        cp.block_count = creq.block_count;
        REQUIRE(sceMfsr2CreateContext(&ctx, &cp) == 0);
    }
};

struct M2Params {
    Mfsr2DispatchParameters p{};
    Tex out{960, 540, 0x24}, color{480, 270, 0x24}, mv{480, 270, 0x1d}, depth{480, 270, 0x16};
    M2Params() {
        p.output_color = out.d;
        p.color = color.d;
        p.motion_vectors = mv.d;
        p.depth = depth.d;
        p.pre_exposure = 1.0f;
        p.render_rect[2] = 480;
        p.render_rect[3] = 270;
        p.camera_near = 0.1f;
        p.camera_far = INFINITY;
    }
};
} // namespace

TEST_CASE("mfsr2: requirement and argument checks", "[psml]") {
    Env env(true);
    REQUIRE(sceMfsr2Initialize() == 0);
    REQUIRE(count_calls("create_shader") == 9 + 59);
    MemoryRequirement req{};
    Mfsr2SharedResourcesInitParameters sp{0, 0, nullptr, 0, 3840, 2160, 0};
    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(nullptr, &sp) == err::k2NullPointer);
    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&req, nullptr) == err::k2NullPointer);
    sp.profile = 1;
    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&req, &sp) == err::k2InvalidProfile);
    sp.profile = 0;
    sp.max_output_width = 1920;
    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&req, &sp) == err::k2InvalidParameter);
    sp.max_output_width = 3840;
    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&req, &sp) == 0);
    // object 0x430, scratch 0xD600000 at 64 KiB, the shared 3840x2160 texture, 0x400 block.
    std::uint64_t ts = 0;
    std::uint64_t ta = 0;
    detail::texture_size(3840, 2160, 0x000001ac00000084ull, &ts, &ta);
    std::uint64_t total = detail::align_up(0x10000 + 0xd600000ull, ta) + ts;
    total = detail::align_up(total, 4) + 0x400;
    REQUIRE(req.block_count == (total + 0x1fffff) >> 21);
    REQUIRE(req.alignment == 0x200000);
    // A package adds its pieces.
    g_files["/sbx/common/psml_package/KPN9_v070.psp"] = make_kpn9(3, false, false);
    MemoryRequirement withpkg{};
    REQUIRE(sceMfsr2GetSharedResourcesInitRequirement(&withpkg, &sp) == 0);
    REQUIRE(withpkg.block_count >= req.block_count);
    REQUIRE(std::string(reinterpret_cast<const char *>(detail::state().package_scratch_a)) ==
            "KPN9-SYNTH");
    // Create checks.
    void *shared = nullptr;
    sp.reserved = 1;
    REQUIRE(sceMfsr2CreateSharedResources(&shared, &sp) == err::k2InvalidParameter);
    sp.reserved = 0;
    sp.block_count = withpkg.block_count + 1;
    REQUIRE(sceMfsr2CreateSharedResources(&shared, &sp) == err::k2InvalidParameter);
    REQUIRE(sceMfsr2CreateSharedResources(nullptr, &sp) == err::k2NullPointer);
    REQUIRE(detail::state().mfsr2_shared_count.load() == 0);
    // Context parameter checks.
    Mfsr2ContextInitParameters cp{};
    REQUIRE(sceMfsr2GetContextInitRequirement(nullptr, &cp) == err::k2NullPointer);
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, nullptr) == err::k2NullPointer);
    cp.profile = 2;
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, &cp) == err::k2InvalidProfile);
    cp.profile = 0;
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, &cp) == err::k2NullSharedResources);
    std::uint8_t fake_shared[0x430] = {};
    cp.shared_resources = fake_shared;
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, &cp) == err::k2InvalidParameter); // width 0
    cp.output_color_width = 960;
    cp.output_color_height = 540;
    cp.input_color_space = 2;
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, &cp) == err::k2InvalidParameter);
    cp.input_color_space = 1;
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, &cp) == 0);
    st<std::uint32_t>(fake_shared, 0x78, 1);
    REQUIRE(sceMfsr2GetContextInitRequirement(&req, &cp) == err::k2InvalidParameter);
    void *ctx = nullptr;
    REQUIRE(sceMfsr2CreateContext(nullptr, &cp) == err::k2NullPointer);
    REQUIRE(detail::state().mfsr2_context_count.load() == 0);
    std::uint32_t size = 0;
    REQUIRE(sceMfsr2GetDispatchCommandSize(nullptr, &size) == 0);
    REQUIRE(size == 0x800);
    (void)ctx;
}

TEST_CASE("mfsr2: persistent network dispatch records markers, 0x6F and bracket packets",
          "[psml]") {
    Env env(true);
    Mfsr2Setup s(true, false);
    // Package: three layer shaders created (Trinity), mode 1.
    void *shared = s.shared;
    REQUIRE(ld<std::uint32_t>(shared, 0x80 + 0x10) == 1);
    REQUIRE(ld<std::uint64_t>(shared, 0x80 + 0x18 + 0x28) != 0);
    REQUIRE(ld<std::uint64_t>(shared, 0x380) == 0xf800000000ull);
    REQUIRE(ld<std::uint32_t>(s.ctx, 0) == 0x8a32954bu);
    // Network blocks carry the tensor table: a V# at +0x20 over the shared scratch.
    const std::uint64_t scratch = ld<std::uint64_t>(shared, 0);
    void *net0 = reinterpret_cast<void *>(ld<std::uint64_t>(s.ctx, 0x08));
    REQUIRE(ld<std::uint32_t>(net0, 0x20) == static_cast<std::uint32_t>(scratch));
    REQUIRE(ld<std::uint32_t>(net0, 0x28) == 0x1fa400u);
    REQUIRE(ld<std::uint32_t>(net0, 0x3a8 + 8) == 0x7e9000u);
    void *frame0 = reinterpret_cast<void *>(ld<std::uint64_t>(s.ctx, 0x48));
    REQUIRE(ld<float>(frame0, 0x58) == 300.0f);
    REQUIRE(ld<std::uint32_t>(frame0, 0xd0) == 0x000fcfcau);

    M2Params mp;
    std::vector<std::uint32_t> buf(0x800 + 4, 0xdeadbeefu);
    Mfsr2RawCommandSpan span{buf.data(), 0x800, 0};
    g_calls.clear();
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &mp.p) == 0);
    REQUIRE(walk_packets(buf.data(), 0x800) == 0x800);
    REQUIRE(buf[0x800] == 0xdeadbeefu);
    std::size_t at = 0;
    for (const auto &seq :
         std::vector<std::vector<std::uint32_t>>{{0xc0017904u, 0x342, 0xd2000001u},
                                                 {0x56000080u},
                                                 kBracketOpen,
                                                 {0xc0006f00u, 0x30000001u},
                                                 {0xc0006f00u, 0x70000002u},
                                                 kBracketClose,
                                                 {0xc0017904u, 0x342, 0xd2000000u}}) {
        at = find_seq(buf, at, seq);
        REQUIRE(at != kNotFound);
    }
    REQUIRE(calls_named("push_marker_span").size() == 1);
    REQUIRE(calls_named("push_marker_span")[0].text == "KPN9::zone1");
    REQUIRE(calls_named("push_marker_span")[0].a[0] == 12);
    REQUIRE(count_calls("pop_marker") == 1);
    const auto d = calls_named("dispatch");
    // Reprojection (2 parts), half resolution, network 30x1x1, post pass (2 parts).
    REQUIRE(d.size() == 6);
    REQUIRE(d[0].a[0] == 128);
    REQUIRE(d[0].a[1] == 135);
    REQUIRE(d[1].a[0] == 120);
    REQUIRE(d[2].a[0] == 60);
    REQUIRE(d[2].a[1] == 34);
    REQUIRE(d[3].a[0] == 30);
    REQUIRE(d[5].a[0] == 120);
    REQUIRE(d[5].a[1] == 68);
    // Barrier form: CS partial flush and the acquire with 0x380 / poll 400.
    const auto acq = calls_named("acquire_mem");
    REQUIRE(!acq.empty());
    REQUIRE(acq[0].a[2] == 0x380);
    REQUIRE(acq[0].a[5] == 400);
    REQUIRE(calls_named("event_write")[0].a[0] == 7);
    // Ring 1 frame constants: counter, reset forced on the first dispatch, magic switched.
    REQUIRE(ld<std::uint32_t>(s.ctx, 0x88) == 1);
    REQUIRE(ld<std::uint32_t>(s.ctx, 0) == 0xa853fccau);
    void *frame1 = reinterpret_cast<void *>(ld<std::uint64_t>(s.ctx, 0x48 + 8));
    REQUIRE(ld<std::uint32_t>(frame1, 0x60) == 1);
    REQUIRE(ld<std::uint32_t>(frame1, 0xbc) == 1);
    REQUIRE(ld<std::uint32_t>(frame1, 0x40) == 480);
    REQUIRE(ld<float>(frame1, 0x010) == 2.0f);
    REQUIRE(ld<std::uint32_t>(frame1, 0x700) == 959);
    // Persistent-network block: sizes, tile tables, blob addresses.
    void *net1 = reinterpret_cast<void *>(ld<std::uint64_t>(s.ctx, 0x08 + 8));
    REQUIRE(ld<std::uint32_t>(net1, 0x00) == 960);
    REQUIRE(ld<std::uint32_t>(net1, 0x1dc) == 50);
    std::uint32_t ta[30];
    REQUIRE(tile_table_a(ta, 480, 270 & ~3) == 0);
    REQUIRE(ld<std::uint64_t>(net1, 0x1e8) == ld<std::uint64_t>(shared, 0x80 + 0x30));

    // Second dispatch with sharpening and auto-exposure.
    mp.p.option_flags = 2 | 8;
    mp.p.sharpness = 1.0f;
    g_calls.clear();
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &mp.p) == 0);
    void *frame2 = reinterpret_cast<void *>(ld<std::uint64_t>(s.ctx, 0x48 + 16));
    REQUIRE(ld<std::uint32_t>(frame2, 0x60) == 0);
    REQUIRE(ld<float>(frame2, 0x6f0) == 1.0f);
    REQUIRE(ld<std::uint16_t>(frame2, 0x6f4) == 0x3c00);
    REQUIRE(ld<std::uint32_t>(frame2, 0x3ec) == (2u | 8u));
    REQUIRE(ld<std::uint64_t>(frame2, 0xa50) == 0x0800000000000000ull);
    REQUIRE(calls_named("dispatch").size() == 8); // + luminance and resolve passes
    REQUIRE(walk_packets(buf.data(), 0x800) == 0x800);

    // Validation errors leave the whole span one NOP.
    M2Params bad;
    bad.p.reserved1[1] = 1;
    std::fill(buf.begin(), buf.end(), 0u);
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &bad.p) == err::k2InvalidParameter);
    REQUIRE(buf[0] == (0xc0001000u | ((0x800u - 2) << 16)));
    REQUIRE(sceMfsr2Dispatch(nullptr, &span, &mp.p) == err::k2NullContext);
    REQUIRE(sceMfsr2Dispatch(s.ctx, nullptr, &mp.p) == err::k2NullPointer);
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, nullptr) == err::k2NullPointer);
    M2Params e1;
    e1.p.output_color = nullptr;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e1.p) == err::k2MissingTexture);
    M2Params e2;
    e2.p.pre_exposure = 0.0f;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e2.p) == err::k2InvalidParameter);
    M2Params e3;
    e3.p.render_rect[2] = 0;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e3.p) == err::k2RenderRectTooSmall);
    M2Params e4;
    e4.p.option_flags = 0x10;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e4.p) == err::k2InvalidParameter);
    M2Params e5;
    e5.p.sharpness = 0.5f;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e5.p) == err::k2InvalidParameter);
    M2Params e6;
    Tex wrongfmt(960, 540, 0x16);
    e6.p.output_color = wrongfmt.d;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e6.p) == err::k2BadTexture);
    M2Params e7;
    e7.p.render_rect[0] = 1;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e7.p) == err::k2BadTexture); // rect past the colour
    M2Params e8;
    e8.p.jitter[0] = NAN;
    REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &e8.p) == err::k2InvalidParameter);
    // Not enough room for the begin marker and capture record.
    std::vector<std::uint32_t> small(80, 0);
    Mfsr2RawCommandSpan tiny{small.data(), 80, 0};
    REQUIRE(sceMfsr2Dispatch(s.ctx, &tiny, &mp.p) == err::k2NoCommandSpace);
    REQUIRE(walk_packets(small.data(), 80) == 80);

    REQUIRE(sceMfsr2ReleaseContext(s.ctx) == 0);
    REQUIRE(detail::state().mfsr2_context_count.load() == 0);
    REQUIRE(ld<std::uint32_t>(shared, 0x400) == 0);
    REQUIRE(sceMfsr2ReleaseSharedResources(shared) == 0);
    REQUIRE(count_calls("release_tool_memory") == 1);
    REQUIRE(detail::state().mfsr2_shared_count.load() == 0);
    REQUIRE(g_maps.empty());
}

TEST_CASE("mfsr2: 17-pass network (mode 0) and the missing-package case", "[psml]") {
    {
        Env env(true);
        Mfsr2Setup s(true, true);
        REQUIRE(ld<std::uint32_t>(s.shared, 0x80 + 0x10) == 0);
        M2Params mp;
        std::vector<std::uint32_t> buf(0x800, 0);
        Mfsr2RawCommandSpan span{buf.data(), 0x800, 0};
        g_calls.clear();
        REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &mp.p) == 0);
        REQUIRE(walk_packets(buf.data(), 0x800) == 0x800);
        const auto d = calls_named("dispatch");
        REQUIRE(d.size() == 3 + 17 + 2);
        // Layer 0 at half resolution: x = ((960 >> 1) + 31) >> 5, y = 540 >> 1.
        REQUIRE(d[3].a[0] == 15);
        REQUIRE(d[3].a[1] == 270);
        // Layer 16: W >> 3, H >> 3.
        REQUIRE(d[19].a[0] == 120);
        REQUIRE(d[19].a[1] == 67);
        REQUIRE(count_calls("bracket") == 0);
        REQUIRE(sceMfsr2ReleaseContext(s.ctx) == 0);
        REQUIRE(sceMfsr2ReleaseSharedResources(s.shared) == 0);
    }
    {
        Env env(true);
        Mfsr2Setup s(false, false); // no package: created without a network
        M2Params mp;
        std::vector<std::uint32_t> buf(0x800, 0);
        Mfsr2RawCommandSpan span{buf.data(), 0x800, 0};
        REQUIRE(sceMfsr2Dispatch(s.ctx, &span, &mp.p) == 0);
        REQUIRE(walk_packets(buf.data(), 0x800) == 0x800);
        // Second shared object and fifth context are refused.
        void *again = nullptr;
        Mfsr2SharedResourcesInitParameters sp{0, 0, s.sb.data(), s.sb.size(), 3840, 2160, 0};
        REQUIRE(sceMfsr2CreateSharedResources(&again, &sp) == err::k2TooManyObjects);
        std::vector<void *> more;
        for (int i = 0; i < 3; ++i) {
            void *c = nullptr;
            REQUIRE(sceMfsr2CreateContext(&c, &s.cp) == 0);
            more.push_back(c);
        }
        void *fifth = nullptr;
        REQUIRE(sceMfsr2CreateContext(&fifth, &s.cp) == err::k2TooManyObjects);
        for (void *c : more) {
            REQUIRE(sceMfsr2ReleaseContext(c) == 0);
        }
        REQUIRE(sceMfsr2ReleaseContext(s.ctx) == 0);
        REQUIRE(sceMfsr2ReleaseSharedResources(s.shared) == 0);
        REQUIRE(g_maps.empty());
    }
}
