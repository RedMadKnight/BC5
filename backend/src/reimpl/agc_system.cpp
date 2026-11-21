// SPDX-License-Identifier: GPL-2.0-only
// Clean-room re-creation of libSceAgc (see src/reimpl/PROVENANCE.md): module state, load, init
// (default register state per SDK version), register-default selection, the static area,
// semaphore memory, suspend/resume and the CU-mask override lists.
//
// Behaviour is per the original module (clean-room description, see src/reimpl/PROVENANCE.md).
#include "bc5/reimpl/agc_internal.hpp"
#include "bc5/reimpl/agc_tables.hpp"
#include "bc5/reimpl/data_source.hpp"

#include <algorithm>
#include <map>
#include <vector>

namespace bc5::reimpl::agc {

using namespace detail;

namespace detail {

namespace {
State g_state;
} // namespace

State &state() { return g_state; }

void reset_state() {
    g_state = State{};
    g_state.suspend_not_ready = 1;
    g_state.active_slot = -1;
    g_state.expected_static_area = kStaticAreaAddress;
    g_state.restore_a = RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    g_state.restore_b = RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    g_state.fourth_a = RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    g_state.fourth_b = RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    for (RegPair &p : g_state.fourth_c) {
        p = RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
    }
    // The first register of the slot's special UCONFIG block (descriptor 0x45C40 of the original).
    // The description leaves the value open ("may be updated by part-2 code"); a capture of the
    // slot the title's own copy of the module builds (run rmplF1bb, 2026-11-21, BC5's private
    // capture of the LOAD_*_REG_INDEX lists) shows the block starts at UCONFIG 0x35: its first
    // UCONFIG load carries 49 of the 57 pairs, the eight 0x35..0x3C last. Interop fact, observed.
    g_state.uc_special_offset = 0x35u;
}

namespace {
// Module-load initial values (static initialisation of the globals).
const bool g_state_initialised = [] {
    reset_state();
    return true;
}();
} // namespace

void mutex_lock() {
    if (g_imports.mutex_lock == nullptr) {
        return;
    }
    if (const int rc = g_imports.mutex_lock(&g_state.mutex); rc != 0) {
        log(kModule, "SceAgcMutex lock failed 0x%08x", static_cast<unsigned>(rc));
    }
}

void mutex_unlock() {
    if (g_imports.mutex_unlock == nullptr) {
        return;
    }
    if (const int rc = g_imports.mutex_unlock(&g_state.mutex); rc != 0) {
        log(kModule, "SceAgcMutex unlock failed 0x%08x", static_cast<unsigned>(rc));
    }
}

bool is_trusted_caller(std::uint64_t ra) {
    const bool outside = ra < g_state.trusted_lo || ra >= g_state.trusted_hi;
    return outside && (ra >= 0x840000000ull || ra < 0x800000000ull);
}

QueueSlot *slot_for_queue(std::uint32_t index) {
    if (index >= 2) {
        return nullptr; // deviation: UB in the original (no bounds check)
    }
    return &g_state.slots[index];
}

QueueSlot *active_slot() {
    if (g_state.suspend_not_ready != 0 || g_state.active_slot < 0 || g_state.active_slot > 1) {
        return nullptr;
    }
    return &g_state.slots[g_state.active_slot];
}

std::uint64_t dmem_peek(std::uint64_t size, std::uint64_t align) {
    if (align == 0) {
        align = 1;
    }
    const std::uint64_t p = (g_state.dmem_cursor + align - 1) / align * align;
    if (g_state.dmem_cursor == 0 || p > g_state.dmem_end || g_state.dmem_end - p < size) {
        return 0;
    }
    return p;
}

std::uint64_t dmem_alloc(std::uint64_t size, std::uint64_t align) {
    const std::uint64_t p = dmem_peek(size, align);
    if (p != 0) {
        g_state.dmem_cursor = p + size;
    }
    return p;
}

int transcode_query() {
    return g_imports.transcode_query != nullptr ? g_imports.transcode_query() : 0;
}

std::uint32_t suspend_mode(std::uint32_t flags) {
    return (flags & 2u) != 0 ? 0x1Fu : ((flags & 1u) != 0 ? 5u : 1u);
}

namespace {
// Registry keys read by the suspend helpers (per the original module's behaviour).
constexpr std::uint64_t kRegKeyA = 0x33236083918938B1ull;
constexpr std::uint64_t kRegKeyB = 0x508D69BDE3D3A6ACull;

bool registry_positive(std::uint64_t key) {
    if (!g_state.regmgr_available || g_imports.regmgr_get_int == nullptr) {
        return false;
    }
    int out = -1;
    // TODO(verify): "read succeeds" taken as a zero result.
    return g_imports.regmgr_get_int(key, 0, &out) == 0 && out > 0;
}
} // namespace

std::uint32_t get_suspend_flags() {
    const std::uint32_t cfg = g_state.suspend_config;
    std::uint32_t v = static_cast<std::int32_t>(cfg) < 0 ? (cfg & 1u) + 2u : (cfg & 1u);
    if (g_state.regmgr_available) {
        if (registry_positive(kRegKeyA)) {
            v |= 1u;
        }
        if (registry_positive(kRegKeyB)) {
            v |= 2u;
        }
    }
    if (g_state.static_area != 0) { // deviation: the original writes the fixed address blindly
        *ptr<std::uint64_t>(g_state.static_area + 0x10) = v;
    }
    return v;
}

} // namespace detail

// ---- register-default selection ---------------------------------------------------------------

namespace {

// A pair table, keyed by the address the original image stores it at, copied once into private,
// writable memory (the original patches its tables in place on every selection). The source is
// our own table (agc_tables.cpp) unless BC5_REIMPL_FW_DATA asks for the module file's copy.
struct Table {
    std::vector<RegPair> pairs;
    bool loaded = false;
};
std::map<std::uint64_t, Table> g_tables;

std::vector<std::uint32_t> as_words(std::span<const RegPair> pairs) {
    std::vector<std::uint32_t> w;
    w.reserve(2 * pairs.size());
    for (const RegPair &p : pairs) {
        w.push_back(p.offset);
        w.push_back(p.value);
    }
    return w;
}

// Diagnostic only (BC5_REIMPL_FW_COMPARE): our pairs against the module file's.
void compare_pairs(const char *name, std::uint64_t vaddr, std::span<const RegPair> ours) {
    if (!data_switches().fw_compare) {
        return;
    }
    const std::vector<std::uint32_t> w = as_words(ours);
    compare_table_with_firmware(kModule, name, vaddr, w.data(), ours.size(), 2);
}

RegPair *load_table(std::uint64_t vaddr, std::uint32_t count) {
    if (vaddr == 0 || count == 0) {
        return nullptr;
    }
    Table &t = g_tables[vaddr];
    if (!t.loaded) {
        tables::TableId id{};
        const bool known = tables::table_at_image_address(vaddr, id);
        const std::span<const RegPair> own = known ? tables::table(id) : std::span<const RegPair>{};
        if (known) {
            compare_pairs(tables::table_name(id), vaddr, own);
        }
        FirmwareData *fw = firmware_data_for_use();
        const std::uint8_t *src = fw != nullptr ? fw->get(kModule, vaddr, 8ull * count) : nullptr;
        if (src != nullptr) {
            t.pairs.resize(count);
            std::memcpy(t.pairs.data(), src, 8ull * count);
        } else if (own.size() == count) {
            t.pairs.assign(own.begin(), own.end());
        } else {
            log(kModule, "no register-default table for image address 0x%llx (%u pairs)",
                static_cast<unsigned long long>(vaddr), count);
            return nullptr;
        }
        t.loaded = true;
    }
    return t.pairs.data();
}

// Diagnostic only (BC5_REIMPL_FW_COMPARE): the four list counts of a descriptor (+0x20 .. +0x2C)
// against the module file's.
void compare_counts(std::uint64_t desc_vaddr, const std::uint32_t (&counts)[4]) {
    if (data_switches().fw_compare) {
        compare_table_with_firmware(kModule, "descriptor counts", desc_vaddr + 0x20, counts, 4, 1);
    }
}

// The 10 descriptor groups of the module, in the order of their descriptors: group i has its base
// at 0x28000 + 0x100 * i; base + 0x00 = old-API internal, + 0x40 = new-API internal, + 0x80 =
// old-API public, + 0xC0 = new-API public (tables2.md, "Descriptor layout"). The old- and new-API
// descriptor of a pair share every list (they differ only in the name table).
enum class Group { Soc, Other, V0_3, V4, V5_6, V7, V8, V9, V10_12, V11 };
constexpr std::uint64_t kDescriptorBase = 0x28000;

// The lists of one descriptor kind: table per list (TableId::Count = no list) and the counts at
// +0x20 .. +0x2C, both from tables2.md "All 40 descriptors".
struct Lists {
    tables::TableId id[4];
    std::uint32_t count[4];
};
struct GroupDef {
    Lists pub; // list 3 is null in every public descriptor
    Lists internal;
};

using Tid = tables::TableId;
constexpr Tid kNone = Tid::Count;
constexpr GroupDef kGroups[] = {
    // SOC
    {{{Tid::CxSoc, Tid::ShSoc, Tid::UcSoc, kNone}, {523, 161, 43, 0}},
     {{Tid::IntSocA, Tid::IntSocB, kNone, Tid::FourthSoc}, {1, 12, 0, 4}}},
    // OTHER
    {{{Tid::CxOther, Tid::ShOther, Tid::UcOther, kNone}, {488, 162, 56, 0}},
     {{Tid::IntOtherCx, Tid::IntOtherSh, Tid::IntOtherUc, Tid::FourthOther}, {8, 12, 1, 6}}},
    // V0_3
    {{{Tid::CxV0_3, Tid::ShV0_3, Tid::UcV0_3, kNone}, {523, 161, 43, 0}},
     {{Tid::IntV0_3Cx, Tid::IntV0_3Sh, kNone, Tid::FourthV0_3}, {1, 12, 0, 4}}},
    // V4
    {{{Tid::CxV4, Tid::ShV4, Tid::UcV4, kNone}, {488, 158, 43, 0}},
     {{Tid::IntV4Cx, Tid::IntV4Sh, kNone, Tid::FourthV4}, {2, 15, 0, 4}}},
    // V5_6
    {{{Tid::CxV5_6, Tid::ShV5_6, Tid::UcV5_6, kNone}, {491, 159, 75, 0}},
     {{Tid::IntV5_6Cx, Tid::IntV5_6Sh, kNone, Tid::FourthV5_6}, {3, 15, 0, 6}}},
    // V7
    {{{Tid::CxV7, Tid::ShV7, Tid::UcV7, kNone}, {489, 159, 55, 0}},
     {{Tid::IntV7Cx, Tid::IntV7Sh, kNone, Tid::FourthV7}, {4, 15, 0, 6}}},
    // V8
    {{{Tid::CxV8, Tid::ShV8, Tid::UcV8, kNone}, {489, 159, 55, 0}},
     {{Tid::IntV8Cx, Tid::IntV8Sh, kNone, Tid::FourthV8}, {4, 15, 0, 6}}},
    // V9
    {{{Tid::CxV9, Tid::ShV9, Tid::UcV9, kNone}, {489, 160, 55, 0}},
     {{Tid::IntV9Cx, Tid::IntV9Sh, Tid::IntV9Uc, Tid::FourthV9}, {4, 14, 1, 6}}},
    // V10_12
    {{{Tid::CxV10_12, Tid::ShV10_12, Tid::UcV10_12, kNone}, {482, 159, 55, 0}},
     {{Tid::IntV10_12Cx, Tid::IntV10_12Sh, Tid::IntV10_12Uc, Tid::FourthV10_12}, {9, 15, 1, 6}}},
    // V11
    {{{Tid::CxV11, Tid::ShV11, Tid::UcV11, kNone}, {486, 162, 56, 0}},
     {{Tid::IntV11_1, Tid::IntV11_2, Tid::IntV11_3, Tid::FourthV11}, {9, 12, 1, 6}}},
};
static_assert(sizeof(kGroups) / sizeof(kGroups[0]) == static_cast<std::size_t>(Group::V11) + 1);

// The descriptor address of the original image (interop fact, used for the FW_COMPARE counts).
std::uint64_t descriptor_vaddr(Group g, bool old_api, bool internal) {
    return kDescriptorBase + 0x100u * static_cast<std::uint64_t>(g) + (internal ? 0u : 0x80u) +
           (old_api ? 0u : 0x40u);
}

// The group a selector picks (tables2.md, "The four selectors" and the decision table).
Group select_group(bool old_api, std::uint32_t version) {
    // The new API sends 11 and 13 and above by the transcoder flag alone, for every SoC.
    if (!old_api && (version == 11 || version >= 13)) {
        return transcode_query() != 0 ? Group::V11 : Group::Other;
    }
    if (soc_class() == kSocA) {
        return Group::Soc;
    }
    if (version <= 3) {
        return Group::V0_3;
    }
    switch (version) {
    case 4:
        return Group::V4;
    case 5:
    case 6:
        return Group::V5_6;
    case 7:
        return Group::V7;
    case 8:
        return Group::V8;
    case 9:
        return Group::V9;
    case 10:
        return Group::V10_12;
    case 12:
        // New API: V10_12; the old API sends 12 to OTHER like every version above 10.
        return old_api ? Group::Other : Group::V10_12;
    default:
        return Group::Other; // old API, 11 and above
    }
}

struct Holder {
    RegisterDefaults desc{};
    RegPair *cells[4] = {};
};
std::map<int, Holder> g_holders;

struct Selector {
    std::uint32_t version;
    std::uint32_t variant;
    bool flag;
};

std::uint32_t selector_variant() {
    for (int i = 0; i < 3; ++i) {
        if (transcode_query() != 0) {
            return 2;
        }
    }
    return soc_class() == kSocB ? 1u : 0u;
}

// CU-enable override rows (6 rows x 10 pairs): our own table (agc_tables.cpp), or the copy at
// image address 0x1BDB0 of the module file with BC5_REIMPL_FW_DATA. Copied once, read-only.
std::vector<RegPair> g_cu_rows;
const RegPair *cu_rows() {
    std::vector<RegPair> &rows = g_cu_rows;
    if (rows.empty()) {
        const std::span<const RegPair> own = tables::cu_rows();
        compare_pairs("CU-ROWS", tables::kCuRowsImageAddress, own);
        FirmwareData *fw = firmware_data_for_use();
        const std::uint8_t *src =
            fw != nullptr ? fw->get(kModule, tables::kCuRowsImageAddress, own.size_bytes())
                          : nullptr;
        if (src != nullptr) {
            rows.resize(own.size());
            std::memcpy(rows.data(), src, own.size_bytes());
        } else {
            rows.assign(own.begin(), own.end());
        }
    }
    return rows.data();
}
constexpr std::uint32_t kCuColumns[10] = {0x216, 0x217, 0x219, 0x21A, 0x107,
                                          0x087, 0x007, 0x101, 0x081, 0x001};

void patch_defaults(const Selector &sel, RegPair *cx, std::uint32_t cx_n, RegPair *sh,
                    std::uint32_t sh_n) {
    const RegPair *rows = cu_rows();
    const std::uint32_t row = sel.variant + (sel.version > 12 ? 3u : 0u);
    if (rows != nullptr && row < 6 && sh != nullptr) {
        for (std::uint32_t i = 0; i < sh_n; ++i) {
            for (std::uint32_t c = 0; c < 10; ++c) {
                if (sh[i].offset == kCuColumns[c]) {
                    sh[i].value = rows[row * 10 + c].value;
                }
            }
        }
    }
    if (sel.flag && cx != nullptr) {
        for (std::uint32_t i = 0; i < cx_n; ++i) {
            if (cx[i].offset == 0x201) {
                cx[i].value |= 1u << 16;
            }
        }
    }
}

const RegisterDefaults *select_defaults(bool old_api, bool internal, std::uint32_t version) {
    Selector sel{version, selector_variant(), true};
    const std::uint32_t wa_bit = (state().workaround_mask >> 2) & 1u;
    if (version <= 10) {
        sel.flag = wa_bit != 0;
    }
    const Group g = select_group(old_api, version);
    const int key = (old_api ? 1 : 0) | (internal ? 2 : 0) | (static_cast<int>(g) << 2);
    Holder &h = g_holders[key];
    // Host layout: every list field points at its cell (the slot-0 pointer of the original's slot
    // array); an absent list has a null cell where the original has a null list field.
    h.desc.cx = &h.cells[0];
    h.desc.sh = &h.cells[1];
    h.desc.uc = &h.cells[2];
    h.desc.fourth = &h.cells[3];
    const Lists &lists = internal ? kGroups[static_cast<int>(g)].internal
                                  : kGroups[static_cast<int>(g)].pub;
    compare_counts(descriptor_vaddr(g, old_api, internal), lists.count);
    std::uint32_t *const counts[4] = {&h.desc.cx_count, &h.desc.sh_count, &h.desc.uc_count,
                                      &h.desc.fourth_count};
    for (int l = 0; l < 4; ++l) {
        const bool present = lists.id[l] != kNone;
        h.cells[l] = present ? load_table(tables::table_image_address(lists.id[l]), lists.count[l])
                             : nullptr;
        *counts[l] = h.cells[l] != nullptr ? lists.count[l] : 0u;
    }
    // The name table (hashes) is not part of the description: register names are resolved by
    // offset (resolve_descriptors), so the field stays null.
    patch_defaults(sel, h.cells[0], h.desc.cx_count, h.cells[1], h.desc.sh_count);
    return &h.desc;
}

} // namespace

namespace detail {
void reset_defaults_cache() {
    g_tables.clear();
    g_holders.clear();
    g_cu_rows.clear();
}
} // namespace detail

// Diagnostic (BC5): the first call of a few start-up entry points, with arguments and result.
#define BC5_AGC_FIRST_CALL(...)                                                                        do {                                                                                                   static bool logged_ = false;                                                                       if (!logged_) {                                                                                        logged_ = true;                                                                                    log(kModule, __VA_ARGS__);                                                                     }                                                                                              } while (false)

const RegisterDefaults *sceAgcGetRegisterDefaults2(std::uint32_t sdk_version) {
    const RegisterDefaults *d = select_defaults(false, false, sdk_version);
    BC5_AGC_FIRST_CALL("first sceAgcGetRegisterDefaults2(0x%x) -> cx %u sh %u uc %u", sdk_version,
                       d != nullptr ? d->cx_count : 0u, d != nullptr ? d->sh_count : 0u,
                       d != nullptr ? d->uc_count : 0u);
    return d;
}
const RegisterDefaults *sceAgcGetRegisterDefaults2Internal(std::uint32_t sdk_version) {
    const RegisterDefaults *d = select_defaults(false, true, sdk_version);
    BC5_AGC_FIRST_CALL("first sceAgcGetRegisterDefaults2Internal(0x%x) -> cx %u sh %u uc %u",
                       sdk_version, d != nullptr ? d->cx_count : 0u,
                       d != nullptr ? d->sh_count : 0u, d != nullptr ? d->uc_count : 0u);
    return d;
}
const RegisterDefaults *agcGetRegisterDefaultsForVersion(std::uint32_t sdk_version) {
    return select_defaults(true, false, sdk_version);
}
const RegisterDefaults *agcGetRegisterDefaultsInternalForVersion(std::uint32_t sdk_version) {
    return select_defaults(true, true, sdk_version);
}
const RegisterDefaults *sceAgcGetRegisterDefaults() {
    if (state().suspend_not_ready != 0 || active_slot() == nullptr) {
        return nullptr;
    }
    return agcGetRegisterDefaultsForVersion(active_slot()->version);
}
const RegisterDefaults *sceAgcGetRegisterDefaultsInternal() {
    if (state().suspend_not_ready != 0 || active_slot() == nullptr) {
        return nullptr;
    }
    return agcGetRegisterDefaultsInternalForVersion(active_slot()->version);
}

// ---- CU-mask override lists -------------------------------------------------------------------

namespace {
// INTEROP TABLE (description): one mask per override pair.
constexpr std::uint32_t kCuMasks[10] = {0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu,
                                        0xFFFF0000u, 0x0000FFFFu, 0x0000FFFFu, 0x0000FFFFu,
                                        0x0000FFFFu, 0x0000FFFFu};
// INTEROP TABLES (description): compute static thread-management masks (SH 0x216 / 0x217).
constexpr RegPair kThreadMasksA[2] = {{0x216, 0x0003FCFFu}, {0x217, 0x0003FCFFu}};
constexpr RegPair kThreadMasksB[2] = {{0x216, 0x00FF00FFu}, {0x217, 0x00FF00FFu}};
constexpr std::uint32_t kThreadMaskMasks[2] = {0xFFFFFFFFu, 0xFFFFFFFFu};

std::int32_t cu_overrides(const RegPair **pairs_out, const std::uint32_t **masks_out,
                          std::uint32_t *count_out, std::uint32_t row_offset) {
    if (pairs_out == nullptr || masks_out == nullptr || count_out == nullptr) {
        return kErrNullPointer;
    }
    const RegPair *rows = cu_rows();
    if (rows == nullptr) {
        return kErrInternal; // not reached: the own-source rows always exist
    }
    *masks_out = kCuMasks;
    *pairs_out = rows + (selector_variant() + row_offset) * 10u;
    *count_out = 10;
    return kOk;
}
} // namespace

std::int32_t agcGetCuMaskOverridesForVersion(const RegPair **pairs_out,
                                             const std::uint32_t **masks_out,
                                             std::uint32_t *count_out, std::uint32_t sdk_version) {
    return cu_overrides(pairs_out, masks_out, count_out, sdk_version > 12 ? 3u : 0u);
}

std::int32_t agcGetCuMaskOverrides(const RegPair **pairs_out, const std::uint32_t **masks_out,
                                   std::uint32_t *count_out) {
    return cu_overrides(pairs_out, masks_out, count_out, 0);
}

std::int32_t agcGetComputeThreadMaskOverrides(const RegPair **pairs_out,
                                              const std::uint32_t **masks_out,
                                              std::uint32_t *count_out) {
    if (pairs_out == nullptr || masks_out == nullptr || count_out == nullptr) {
        return kErrNullPointer;
    }
    *pairs_out = soc_class() == kSocB ? kThreadMasksB : kThreadMasksA;
    *masks_out = kThreadMaskMasks;
    *count_out = 2;
    return kOk;
}

// ---- static area ----------------------------------------------------------------------------------

std::int32_t sceAgcSetStaticBuffer(std::uint32_t index, const std::uint64_t *entry) {
    if (index >= 6) {
        return kErrRange;
    }
    if (state().static_area != state().expected_static_area || state().static_area == 0) {
        return kErrNotInitialised;
    }
    auto *dst = ptr<std::uint64_t>(state().static_area + 16ull * index);
    dst[0] = entry[0];
    dst[1] = entry[1];
    return kOk;
}

std::int32_t sceAgcGetStaticBuffer(std::uint32_t index, std::uint64_t *entry_out) {
    if (index >= 6) {
        return kErrRange;
    }
    // Static buffer 0 is the internal shaders' code table. BC5's own table has only the fill
    // shader; the original's other four shaders are not re-created (never executed on BC5 so far).
    // A title that reads it shows here at once.
    if (index == 0 && state().internal_own && !state().internal_own_read_logged) {
        state().internal_own_read_logged = true;
        log(kModule, "STATIC-BUFFER-0 READ: the internal shader code table was read; BC5 provides "
                     "only the fill shader (slot 0), slots 1-4 are empty (PROVENANCE.md)");
    }
    if (state().static_area != state().expected_static_area || state().static_area == 0) {
        return kErrNotInitialised;
    }
    const auto *src = ptr<const std::uint64_t>(state().static_area + 16ull * index);
    entry_out[0] = src[0];
    entry_out[1] = src[1];
    return kOk;
}

std::int32_t agcSetStaticWord(std::uint32_t index, std::uint64_t value) {
    if (state().static_area != 0) { // deviation: the original writes the fixed address blindly
        *ptr<std::uint64_t>(state().static_area + 0x10 + 8ull * index) = value;
    }
    return kOk;
}

std::int32_t agcGetStaticWord(std::uint32_t index, std::uint64_t *out) {
    // deviation: without a static area the original reads unmapped memory; 0 is returned here.
    *out = state().static_area != 0 ? *ptr<const std::uint64_t>(state().static_area + 0x10 + 8ull * index)
                                    : 0u;
    return kOk;
}

// ---- suspend configuration -----------------------------------------------------------------------

std::int32_t agcSetSuspendConfig(std::uint32_t config) {
    state().suspend_config = config;
    return kOk;
}

std::uint32_t agcGetSuspendConfig() {
    std::uint32_t v = state().suspend_config;
    if (state().regmgr_available) {
        if (registry_positive(kRegKeyA)) {
            v |= 1u;
        }
        if (registry_positive(kRegKeyB)) {
            v |= 0x80000000u;
        }
    }
    return v;
}

std::int32_t agcSetTrustedRange(std::uint64_t range_lo, std::uint64_t range_hi) {
    state().trusted_lo = range_lo;
    state().trusted_hi = range_hi;
    return kOk;
}

// ---- semaphore memory ---------------------------------------------------------------------------

namespace {
std::int32_t register_semaphore_memory(std::uint64_t address, std::uint64_t size, std::uint64_t flag) {
    if (g_imports.pass_info_downward == nullptr) {
        return kErrInternal;
    }
    const std::uint64_t info[6] = {7, address, 8, size, 0xB, flag};
    const int rc = g_imports.pass_info_downward(info, 3);
    if (rc == 0) {
        state().sem_base = address;
        state().sem_size = size;
        fill_bytes(ptr<void>(address), 0, size);
    }
    return rc;
}
} // namespace

std::int32_t sceAgcSetAmmSemaphoreMemory(std::uint64_t address, std::uint64_t size_bytes) {
    if (state().sem_size != 0) {
        return kErrSemaphoreSet;
    }
    if ((size_bytes & 0x3FFFu) != 0 || (address & 0x3FFFu) != 0) {
        return kErrAlign;
    }
    if (const int r = transcode_query(); r != 0) {
        return r;
    }
    return register_semaphore_memory(address, size_bytes, 0);
}

std::int32_t agcSetSemaphoreMemoryLimited(std::uint64_t address, std::uint64_t size_bytes) {
    if (state().sem_size != 0) {
        return kErrSemaphoreSet;
    }
    if ((size_bytes & 0x3FFFu) != 0) {
        return kErrAlign;
    }
    if (size_bytes > 0x40000000u) {
        return kErrRange;
    }
    if ((address & 0x3FFFu) != 0) {
        return kErrAlign;
    }
    if (((address + size_bytes) >> 40) < 0xF && (address >> 43) != 0) {
        if (const int r = transcode_query(); r != 0) {
            return r;
        }
    }
    return register_semaphore_memory(address, size_bytes, 1);
}

std::int32_t sceAgcGetSemaphoreLabel(std::uint32_t index, std::uint64_t *address_out) {
    if (state().sem_size == 0) {
        return kErrSemaphoreNotSet;
    }
    if (static_cast<std::uint64_t>(index) * 32u + 32u > state().sem_size) {
        return kErrRange;
    }
    *address_out = state().sem_base + static_cast<std::uint64_t>(index) * 32u;
    return kOk;
}

std::int32_t sceAgcGetDefaultCxStateFlat(std::uint32_t *out, std::uint32_t first_reg,
                                         std::uint32_t end_reg, std::uint32_t slot_index) {
    if (slot_index >= 2) {
        return kErrRange; // deviation: UB in the original (no range check)
    }
    const QueueSlot &s = state().slots[slot_index];
    std::uint32_t j = 0;
    for (std::uint32_t reg = first_reg; reg < end_reg; ++reg) {
        if (j >= s.cx_count) {
            return kOk;
        }
        // The original scans unbounded (the table is padded with all-ones offsets).
        while (j < s.cx_count && s.cx[j].offset < reg) {
            ++j;
        }
        out[reg - first_reg] = (j < s.cx_count && s.cx[j].offset == reg) ? s.cx[j].value : 0u;
    }
    return kOk;
}

// ---- suspend / resume -------------------------------------------------------------------------------

namespace {

std::int32_t submit_resume(const QueueSlot &slot, std::uint32_t *status) {
    if (g_imports.suspend_submit == nullptr) {
        return kErrInternal;
    }
    const CbDescriptor desc{addr(slot.resume_dcb), slot.resume_dwords, 0, {}};
    return g_imports.suspend_submit(&desc, status, suspend_mode(get_suspend_flags()));
}

std::int32_t submit_resume_and_streams(const QueueSlot &slot) {
    std::int32_t rc = submit_resume(slot, nullptr);
    if (rc != 0) {
        return rc;
    }
    if (g_imports.submit_acb == nullptr) {
        return kErrInternal;
    }
    const CbDescriptor desc{addr(slot.sh_stream), slot.sh_stream_bytes / 4u, 0, {}};
    for (std::uint32_t q = 0x20; q <= 0x5E; ++q) {
        rc = g_imports.submit_acb(q, &desc);
        if (rc != 0) {
            break;
        }
    }
    return rc;
}

bool reset_cb_a() { return true; }
int reset_cb_b() { return 0; }
int gpu_reset_handler() {
    if (state().sync_label != 0) {
        auto *label = ptr<std::uint32_t>(state().sync_label);
        label[0] = 0;
        label[1] = 1;
    }
    // The trace-flush step only concerns the shader-replacement capture, never enabled here.
    if (const QueueSlot *slot = active_slot(); slot != nullptr) {
        submit_resume(*slot, nullptr);
    }
    return 0;
}

// Callback table handed to the driver. TODO(verify): layout beyond the three entries.
void *const g_reset_callbacks[8] = {reinterpret_cast<void *>(&reset_cb_a),
                                    reinterpret_cast<void *>(&reset_cb_b),
                                    reinterpret_cast<void *>(&gpu_reset_handler),
                                    nullptr, nullptr, nullptr, nullptr, nullptr};

} // namespace

std::int32_t sceAgcSuspendPoint() {
    if (state().suspend_not_ready != 0) {
        static bool logged = false; // diagnostic (BC5): the first refusal only
        if (!logged) {
            logged = true;
            log(kModule, "sceAgcSuspendPoint refused: suspend not ready (no trusted init completed)");
        }
        return kErrNotInitialised;
    }
    const QueueSlot *slot = active_slot();
    if (slot == nullptr) {
        return kErrNotInitialised;
    }
    return submit_resume(*slot, nullptr);
}

std::int32_t sceAgcSuspendPointAndCheckStatus(std::uint64_t status_arg) {
    if (state().suspend_not_ready != 0) {
        return kErrNotInitialised;
    }
    const QueueSlot *slot = active_slot();
    if (slot == nullptr) {
        return kErrNotInitialised;
    }
    return submit_resume(*slot, ptr<std::uint32_t>(status_arg));
}

std::int32_t sceAgcSetSubmitMode(std::uint32_t mode) {
    if (g_imports.set_kernel_submit_flag == nullptr) {
        return kErrInternal;
    }
    return g_imports.set_kernel_submit_flag(static_cast<int>(mode));
}

std::int32_t sceAgcDebugRaiseException(std::uint32_t code, std::uint64_t arg) {
    if (g_imports.raise_exception == nullptr) {
        return kErrInternal;
    }
    return g_imports.raise_exception(static_cast<int>(code), arg);
}

std::int32_t agcQueryKernelFlag(std::uint8_t *out) {
    const int r = g_imports.query_kernel_flag != nullptr ? g_imports.query_kernel_flag() : 0;
    if (out != nullptr) {
        *out = static_cast<std::uint8_t>(r);
    }
    return r;
}

// ---- init -------------------------------------------------------------------------------------------

namespace {

bool by_offset(const RegPair &a, const RegPair &b) { return a.offset < b.offset; }

std::uint32_t workaround_mask_from_title() {
    if (g_imports.query_app_type == nullptr || g_imports.get_app_info == nullptr ||
        g_imports.getpid == nullptr || g_imports.title_workaround_is_enabled == nullptr) {
        return 0;
    }
    std::uint8_t buf[64] = {}; // TODO(verify) size; only byte 3 is used
    if (g_imports.query_app_type(buf) != 0) {
        return 0;
    }
    alignas(8) std::uint8_t info[512] = {}; // TODO(verify) size of the app-info record
    if (g_imports.get_app_info(g_imports.getpid(), info) < 0) {
        return 0;
    }
    int a = 0;
    int b = 0;
    int c = 0;
    if (g_imports.title_workaround_is_enabled(info, 0x52, &a) != 0 ||
        g_imports.title_workaround_is_enabled(info, 0x53, &b) != 0 ||
        g_imports.title_workaround_is_enabled(info, 0x70, &c) != 0) {
        return 0;
    }
    std::uint32_t w = a == 1 ? 2u : 1u;
    if (b == 1) {
        w = 0;
    }
    if (buf[3] != 4) {
        w = 0;
    }
    w += (c == 1 ? 1u : 0u) * 4u;
    return w;
}

std::int32_t build_sh_stream(QueueSlot &slot, const RegisterDefaults *const dbs[2]) {
    std::vector<RegPair> regs;
    for (int i = 0; i < 2; ++i) {
        const RegPair *sh = dbs[i]->sh != nullptr ? *dbs[i]->sh : nullptr;
        for (std::uint32_t k = 0; sh != nullptr && k < dbs[i]->sh_count; ++k) {
            if (sh[k].offset > 0x200) {
                regs.push_back(sh[k]);
            }
        }
    }
    std::stable_sort(regs.begin(), regs.end(), by_offset);
    std::uint32_t size = 0;
    for (std::size_t i = 0; i < regs.size(); ++i) {
        size += 4;
        if (i == 0 || regs[i].offset != regs[i - 1].offset + 1u) {
            size += 8;
        }
    }
    if (size >= 0x180) {
        return kErrInternal;
    }
    const std::uint64_t mem = dmem_alloc(0x180, 4);
    if (mem == 0) {
        return kErrInternal;
    }
    CommandBuffer cb{};
    init_command_buffer(&cb, ptr<void>(mem), 0x180, nullptr, nullptr);
    if (!regs.empty()) {
        sceAgcCbSetShRegistersDirect(&cb, regs.data(), static_cast<std::uint32_t>(regs.size()));
    }
    if (const std::uint32_t rest = (0x180u - size) / 4u; rest != 0) {
        sceAgcCbNop(&cb, rest);
    }
    slot.sh_stream = ptr<std::uint32_t>(mem);
    slot.sh_stream_bytes = size;
    return kOk;
}

bool build_resume_dcb(QueueSlot &slot) {
    const std::uint64_t mem = dmem_alloc(0x200, 4);
    if (mem == 0) {
        return false;
    }
    CommandBuffer cb{};
    init_command_buffer(&cb, ptr<void>(mem), 0x200, nullptr, nullptr);
    conditional_roll_notify(&cb, 1, false);
    std::uint32_t *r = dcb_reset_queue_body(&cb, 0x7FF, &slot, slot.trusted != 0);
    if (g_imports.is_esvm == nullptr || g_imports.is_esvm() == 0) {
        // Copy the suspend-flags word of the static area (fixed GPU addresses).
        sceAgcDcbCopyData(&cb, 5, 0, 0xFE0040018ull, 5, 2, 0xFE0040010ull, 1, 1);
    }
    slot.resume_dcb = ptr<std::uint32_t>(mem);
    slot.resume_dwords = static_cast<std::uint32_t>(cb.cursor - cb.begin);
    return r != nullptr;
}

std::int32_t notify_default_states() {
    const std::uint64_t scratch = dmem_peek(0xC000, 8);
    if (scratch == 0) {
        return kErrInternal;
    }
    fill_bytes(ptr<void>(scratch), 0xFF, 0xC000);
    RegPair *img[3] = {ptr<RegPair>(scratch), ptr<RegPair>(scratch + 0x4000),
                       ptr<RegPair>(scratch + 0x8000)};
    for (const QueueSlot &s : state().slots) {
        if (s.version == 0) {
            continue;
        }
        const RegPair *lists[3] = {s.cx, s.sh, s.uc};
        const std::uint32_t counts[3] = {s.cx_count, s.sh_count, s.uc_count};
        for (int l = 0; l < 3; ++l) {
            for (std::uint32_t k = 0; lists[l] != nullptr && k < counts[l]; ++k) {
                if (lists[l][k].offset < 0x800) { // deviation: the original writes past the image
                    img[l][lists[l][k].offset] = lists[l][k];
                }
            }
        }
    }
    std::uint32_t n[3] = {};
    for (int l = 0; l < 3; ++l) {
        std::stable_sort(img[l], img[l] + 0x800, by_offset);
        while (n[l] < 0x800 &&
               !(img[l][n[l]].offset == 0xFFFFFFFFu && img[l][n[l]].value == 0xFFFFFFFFu)) {
            ++n[l];
        }
    }
    if (g_imports.notify_default_states == nullptr) {
        return kErrInternal;
    }
    return g_imports.notify_default_states(
        reinterpret_cast<const std::uint32_t *>(img[0]), reinterpret_cast<const std::uint32_t *>(img[1]),
        reinterpret_cast<const std::uint32_t *>(img[2]), n[0], n[1], n[2]);
}

std::int32_t build_new_slot(QueueSlot &slot, std::uint32_t version, bool trusted) {
    slot = QueueSlot{};
    slot.version = version;
    slot.trusted = trusted ? 1 : 0;
    slot.cx_count = 0x400;
    const std::uint64_t cx_mem = dmem_alloc(0x2000, 4);
    if (cx_mem == 0) {
        return kErrInternal;
    }
    slot.cx = ptr<RegPair>(cx_mem);
    for (std::uint32_t i = 0; i < 0x400; ++i) {
        slot.cx[i] = RegPair{0xFFFFFFFFu, 0};
    }
    if (g_imports.tmp_init_idhs == nullptr) {
        return kErrInternal;
    }
    if (const int rc = g_imports.tmp_init_idhs(reinterpret_cast<std::uint32_t *>(slot.cx), 0x400);
        rc != 0) {
        return rc;
    }
    const RegisterDefaults *const dbs[2] = {sceAgcGetRegisterDefaults2(version),
                                            sceAgcGetRegisterDefaults2Internal(version)};
    if (state().use_clear_state_for_cx != 0 && g_imports.patch_clear_state != nullptr &&
        *dbs[0]->cx != nullptr) {
        if (const int rc = g_imports.patch_clear_state(
                reinterpret_cast<const std::uint32_t *>(*dbs[0]->cx), dbs[0]->cx_count);
            rc != 0) {
            return rc;
        }
    }
    for (const RegisterDefaults *db : dbs) {
        const RegPair *cx = *db->cx;
        for (std::uint32_t k = 0; cx != nullptr && k < db->cx_count; ++k) {
            if (cx[k].offset >= 0x400) {
                log(kModule, "illegal context register 0x%x in the default state", cx[k].offset);
                return kErrInternal;
            }
            slot.cx[cx[k].offset] = cx[k];
        }
    }
    std::stable_sort(slot.cx, slot.cx + 0x400, by_offset);
    std::uint32_t n = 0;
    while (n < 0x400 && slot.cx[n].offset != 0xFFFFFFFFu) {
        ++n;
    }
    slot.cx_count = n;
    if ((version == 12 || version < 11) && transcode_query() != 0) {
        RegPair *p = std::find_if(slot.cx, slot.cx + n, [](const RegPair &r) {
            return r.offset == 0x212;
        });
        if (p != slot.cx + n) {
            p->value = 0x2400;
        } else {
            log(kModule, "default state incomplete (context register 0x212 missing)");
        }
    }
    const std::uint32_t sh_n = dbs[0]->sh_count + dbs[1]->sh_count;
    const std::uint32_t uc_n = dbs[0]->uc_count + dbs[1]->uc_count;
    const std::uint64_t sh_mem = dmem_alloc(8ull * sh_n, 4);
    const std::uint64_t uc_mem = dmem_alloc(8ull * uc_n, 4);
    if (sh_mem == 0 || uc_mem == 0) {
        return kErrInternal;
    }
    slot.sh = ptr<RegPair>(sh_mem);
    slot.uc = ptr<RegPair>(uc_mem);
    for (const RegisterDefaults *db : dbs) {
        if (*db->sh != nullptr) {
            copy_bytes(slot.sh + slot.sh_count, *db->sh, 8ull * db->sh_count);
            slot.sh_count += db->sh_count;
        }
        if (*db->uc != nullptr) {
            copy_bytes(slot.uc + slot.uc_count, *db->uc, 8ull * db->uc_count);
            slot.uc_count += db->uc_count;
        }
    }
    for (std::uint32_t i = 0; i < slot.uc_count; ++i) {
        if (slot.uc[i].offset == state().uc_special_offset) {
            if (i + 8u <= slot.uc_count) { // deviation: the original does not check the bound
                for (std::uint32_t k = 0; k < 8; ++k) {
                    std::swap(slot.uc[i + k], slot.uc[slot.uc_count - 1u - k]);
                }
                slot.uc_special_count = 8;
            }
            break;
        }
    }
    if (const std::int32_t rc = build_sh_stream(slot, dbs); rc != kOk) {
        return rc;
    }
    std::stable_sort(slot.sh, slot.sh + slot.sh_count, by_offset);
    std::stable_sort(slot.uc, slot.uc + (slot.uc_count - slot.uc_special_count), by_offset);
    if (const std::int32_t rc = notify_default_states(); rc != kOk) {
        return rc;
    }
    if (!build_resume_dcb(slot)) {
        return kErrInternal;
    }
    return kOk;
}

std::int32_t init_locked(std::uint32_t version, bool trusted) {
    State &st = state();
    st.workaround_mask = workaround_mask_from_title();
    if (st.sync_label == 0) {
        if (const std::uint64_t p = dmem_alloc(8, 8); p != 0) {
            ptr<std::uint32_t>(p)[0] = 0;
            ptr<std::uint32_t>(p)[1] = 1;
            st.sync_label = p;
        }
    }
    if (trusted && g_imports.set_kernel_submit_flag != nullptr) {
        g_imports.set_kernel_submit_flag(version < 6 ? 1 : 0);
    }
    int index = -1;
    bool fresh = false;
    if (st.slots[0].version == version) {
        index = 0;
    } else if (st.slots[1].version == version) {
        index = 1;
    }
    if (index >= 0) {
        if (trusted) {
            st.slots[index].trusted = 1;
        }
    } else if (st.slots[0].version == 0) {
        index = 0;
        fresh = true;
    } else if (st.slots[1].version == 0) {
        index = 1;
        fresh = true;
    } else {
        return kErrNoFreeSlot;
    }
    if (const std::int32_t rc = resolve_descriptors(version); rc != kOk) {
        return rc;
    }
    for (std::uint32_t i = 1; i <= 10; ++i) {
        st.trace_initiator[i] = g_imports.get_trace_initiator != nullptr
                                    ? static_cast<std::uint32_t>(g_imports.get_trace_initiator(i))
                                    : 0u;
    }
    QueueSlot &slot = st.slots[index];
    if (fresh) {
        if (const std::int32_t rc = build_new_slot(slot, version, trusted); rc != kOk) {
            if (rc == kErrInternal || rc == kErrNoFreeSlot) {
                // keep the slot marked used as the original does (its version is already set)
            }
            return rc;
        }
    }
    if (g_imports.pass_info_downward == nullptr) {
        return kErrInternal;
    }
    auto defaults_addr = [](const QueueSlot &s, bool internal) -> std::uint64_t {
        if (s.version == 0) {
            return 0;
        }
        return addr(internal ? sceAgcGetRegisterDefaults2Internal(s.version)
                             : sceAgcGetRegisterDefaults2(s.version));
    };
    const std::uint64_t info[16] = {0, st.slots[0].version,
                                    1, defaults_addr(st.slots[0], false),
                                    2, defaults_addr(st.slots[0], true),
                                    3, st.slots[1].version,
                                    4, defaults_addr(st.slots[1], false),
                                    5, defaults_addr(st.slots[1], true),
                                    6, st.sync_label,
                                    9, st.slots[0].trusted != 0 ? 0u : 1u};
    if (const int rc = g_imports.pass_info_downward(info, 8); rc != 0) {
        return rc;
    }
    if (!st.internal_shaders_created) {
        if (const std::int32_t rc = create_internal_shaders(); rc != kOk) {
            return rc;
        }
        st.internal_shaders_created = true;
    }
    std::int32_t result = kOk;
    if (trusted && st.suspend_not_ready != 0) {
        result = submit_resume_and_streams(slot);
        if (g_imports.register_gpu_reset_callbacks != nullptr) {
            g_imports.register_gpu_reset_callbacks(g_reset_callbacks);
        }
        st.active_slot = index;
        st.suspend_not_ready = 0;
    }
    return result;
}

std::int32_t init_body(std::uint32_t version, bool trusted) {
    mutex_lock();
    const std::int32_t rc = init_locked(version, trusted);
    mutex_unlock();
    // Diagnostic (BC5): one line per init, so a title's start-up failure shows in the log.
    log(kModule, "init(version %u, %s caller) -> 0x%08x; suspend %s", version,
        trusted ? "trusted" : "untrusted", static_cast<std::uint32_t>(rc),
        state().suspend_not_ready != 0 ? "NOT ready" : "ready");
    return rc;
}

} // namespace

std::int32_t sceAgcInit(std::uint32_t sdk_version) {
    const std::uint64_t ra = BC5_AGC_RETURN_ADDRESS();
    const bool trusted = is_trusted_caller(ra);
    BC5_AGC_FIRST_CALL("first sceAgcInit(0x%x) from 0x%llx", sdk_version,
                       static_cast<unsigned long long>(ra));
    return init_body(sdk_version, trusted);
}

std::int32_t agcInitWithVersion(std::uint64_t first, std::uint32_t sdk_version) {
    const std::uint64_t ra = BC5_AGC_RETURN_ADDRESS();
    const bool trusted = is_trusted_caller(ra);
    BC5_AGC_FIRST_CALL("first init(0x%llx, 0x%x) [23LRUSvYu1M] from 0x%llx",
                       static_cast<unsigned long long>(first), sdk_version,
                       static_cast<unsigned long long>(ra));
    return init_body(sdk_version, trusted);
}

// ---- module load / unload ------------------------------------------------------------------------

std::int32_t module_load() {
    State &st = state();
    st.soc_id = g_imports.get_main_soc_id != nullptr ? g_imports.get_main_soc_id() : 0u;
    std::uint8_t flag = 0;
    agcQueryKernelFlag(&flag);
    st.kernel_flag = flag != 0;
    if (g_imports.mutex_init != nullptr) {
        if (const int rc = g_imports.mutex_init(&st.mutex, nullptr, "SceAgcMutex"); rc != 0) {
            log(kModule, "SceAgcMutex init failed 0x%08x", static_cast<unsigned>(rc));
            return rc;
        }
    }
    std::uint64_t base = 0;
    std::uint32_t size = 0;
    if (g_imports.get_reserved_dmem == nullptr || g_imports.get_reserved_dmem(&base, &size) != 0 ||
        base == 0 || size == 0) {
        log(kModule, "unable to get Dmem");
    } else {
        st.dmem_end = base + size;
        const std::uint64_t p = (base + 3) & ~3ull;
        fill_bytes(ptr<void>(p), 0, 0x60);
        st.static_area = p;
        st.dmem_cursor = p + 0x60;
        if (p != st.expected_static_area) {
            log(kModule, "FS table offset shifted (0x%llx)", static_cast<unsigned long long>(p));
        }
    }
    // GPU-transcoding decision. The dipsw query has no host equivalent and reads as 0.
    if (soc_class() == kSocB && g_imports.sysmodule_load_internal != nullptr) {
        st.regmgr_available = g_imports.sysmodule_load_internal(0x8000001Fu) == 0;
        if (st.regmgr_available) {
            int category = 0;
            const bool app_ok = g_imports.get_app_category_type != nullptr &&
                                g_imports.getpid != nullptr &&
                                g_imports.get_app_category_type(g_imports.getpid(), &category) == 0;
            if (!(app_ok && category == 0x10000) && registry_positive(0x34ae6c7a451600dbull)) {
                // deviation: the shader-replacement arena is not re-created.
                log(kModule, "GPU transcoding for workarounds requested; not supported here");
            }
        }
    }
    if (g_imports.pass_info_downward != nullptr) {
        const std::uint64_t info[2] = {10, 0};
        g_imports.pass_info_downward(info, 1);
    }
    return kOk;
}

void module_unload() {
    if (g_imports.mutex_destroy != nullptr) {
        if (const int rc = g_imports.mutex_destroy(&state().mutex); rc != 0) {
            log(kModule, "SceAgcMutex destroy failed 0x%08x", static_cast<unsigned>(rc));
        }
    }
}

// ---- test support -----------------------------------------------------------------------------------

namespace testing {

void reset() {
    reset_state();
    reset_descriptors();
    reset_defaults_cache();
    g_exported_word = 0;
}
void set_expected_static_area(std::uint64_t address) { state().expected_static_area = address; }
void set_internal_own(bool value) { state().internal_own = value; }
void set_soc_id(std::uint32_t soc_id) { state().soc_id = soc_id; }
void set_workaround_mask(std::uint32_t mask) { state().workaround_mask = mask; }
void set_trace_initiator(std::uint32_t index_1_to_10, std::uint32_t value) {
    if (index_1_to_10 >= 1 && index_1_to_10 <= 10) {
        state().trace_initiator[index_1_to_10] = value;
    }
}
void set_use_clear_state_for_cx(std::uint32_t value) { state().use_clear_state_for_cx = value; }
void set_kernel_flag(bool value) { state().kernel_flag = value; }
void set_dmem(std::uint64_t cursor, std::uint64_t end) {
    state().dmem_cursor = cursor;
    state().dmem_end = end;
}
void set_sync_label(std::uint64_t address) { state().sync_label = address; }

SlotView slot(std::uint32_t index) {
    const QueueSlot &s = state().slots[index & 1u];
    return SlotView{s.cx,         s.sh,         s.uc,          s.cx_count,     s.sh_count,
                    s.uc_count,   s.uc_special_count,          s.sh_stream,    s.sh_stream_bytes,
                    s.resume_dcb, s.resume_dwords, s.version,  s.trusted != 0};
}
void set_slot(std::uint32_t index, const SlotView &v) {
    QueueSlot &s = state().slots[index & 1u];
    s.cx = v.cx;
    s.sh = v.sh;
    s.uc = v.uc;
    s.cx_count = v.cx_count;
    s.sh_count = v.sh_count;
    s.uc_count = v.uc_count;
    s.uc_special_count = v.uc_special_count;
    s.sh_stream = v.sh_stream;
    s.sh_stream_bytes = v.sh_stream_bytes;
    s.resume_dcb = v.resume_dcb;
    s.resume_dwords = v.resume_dwords;
    s.version = v.version;
    s.trusted = v.trusted ? 1 : 0;
}
void set_active_slot(std::int32_t index, bool suspend_ready) {
    state().active_slot = index;
    state().suspend_not_ready = suspend_ready ? 0 : 1;
}
std::uint64_t static_area() { return state().static_area; }
std::uint64_t sync_label() { return state().sync_label; }
std::uint32_t workaround_mask() { return state().workaround_mask; }
std::uint64_t semaphore_base() { return state().sem_base; }
std::uint64_t semaphore_size() { return state().sem_size; }
const Shader *fill_shader() { return state().fill_shader; }
void set_fill_shader(const Shader *shader) { state().fill_shader = shader; }
void set_restore_pairs(RegPair a, RegPair b) {
    state().restore_a = a;
    state().restore_b = b;
}
RegPair *descriptor(std::uint64_t vaddr) { return descriptor_by_vaddr(vaddr); }
RegPair fourth_cache(std::uint32_t index) {
    const State &st = state();
    if (index == 0) {
        return st.fourth_a;
    }
    if (index == 1) {
        return st.fourth_b;
    }
    return index <= 4 ? st.fourth_c[index - 2] : RegPair{0xFFFFFFFFu, 0xFFFFFFFFu};
}

} // namespace testing

} // namespace bc5::reimpl::agc
