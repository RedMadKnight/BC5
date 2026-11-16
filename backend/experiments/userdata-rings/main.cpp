// SPDX-License-Identifier: GPL-2.0-only
// userdata-rings: experiment 0427, the premise of ADR 0009's "one compute ring per guest queue"
// (way 2, exp 0426). Does a kernel compute ring keep COMPUTE_USER_DATA_4..6 that an earlier job
// set, and is that state tied to the libdrm ring index BC5 submits to, or only to the hardware
// queue the kernel's scheduler picked for the job?
//
//   userdata-rings                  dry run: build every job's IB with placeholder VAs, check them,
//                                   print the plan. No GPU, no device opened. The default.
//   userdata-rings --info           (BC5_WITH_AMDGPU) what the kernel reports; read-only
//   userdata-rings --submit         (BC5_WITH_AMDGPU) run the plan on the GPU. OFF by default.
//
// Hard rule 5 (CLAUDE.md): --submit can hang or reset the machine. It is never run by tests, CI or
// scripts, and only with the maintainer at the box.
//
// Each job is one CS with one IB and one dispatch of one 64-thread group into its own 1 KiB slot.
//   S ("set") job: the full IGT dispatch state, USER_DATA_0..3 = the slot's V#, USER_DATA_4..7 =
//                  values unique to the job.
//   P ("probe") job: the same state but USER_DATA_4..7 are NOT written; it stores what the queue
//                  holds there.
// The program stores {USER_DATA_4, USER_DATA_5, USER_DATA_6, HW_ID2} per thread, so every job also
// reports which hardware queue ran it.
//
// What the job sequence avoids (the 0427 brief): no waits on labels, no map or unmap while a job
// runs (all BOs are mapped before the first submit and unmapped after the last fence), no
// CONTEXT_CONTROL on a compute ring (F31, exp 0127).
#include "bc5/indirect_check.hpp"
#include "bc5/pm4.hpp"
#include "bc5/policy.hpp"

#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <string_view>
#include <vector>

#ifdef BC5_WITH_AMDGPU
#include <amdgpu.h>
#include <amdgpu_drm.h>
#include <fcntl.h>
#include <unistd.h>
#endif

namespace {

using bc5::pm4::Op;

// The IGT gfx10 buffer-clear program (backend/include/bc5/dispatch_min.hpp, IGT
// lib/amdgpu/amd_shaders.c:295-309 @ 9d4b6ef, MIT) with two changes, marked:
//   s_getreg_b32 s10, hwreg(HW_REG_HW_ID2, 0, 32)   ; NEW
//   v_lshl_add_u32 v4, s8, 6, v0
//   v_mov_b32 v0, s4 ; v_mov_b32 v1, s5 ; v_mov_b32 v2, s6
//   v_mov_b32 v3, s10                                ; CHANGED (was s7)
//   buffer_store_format_xyzw v[0:3], v4, s[0:3], 0 idxen
//   s_endpgm
// Encodings:
// - s_getreg_b32: SOPK, LLVM llvm/test/MC/AMDGPU/gfx10_asm_sop.s:5002-5003 (llvm-project @ 0b115ab4)
//   "s_getreg_b32 s0, hwreg(52, 8, 3) ; encoding: [0x34,0x12,0x00,0xb9]": 0xB9000000 | sdst << 16 |
//   simm16, simm16 = id | offset << 6 | (size - 1) << 11.
// - HW_REG_HW_ID2 = 24 on GFX10+ (llvm/lib/Target/AMDGPU/SIDefines.h:769,
//   Utils/AMDGPUAsmUtils.cpp:227); simm16 = 24 | 0 << 6 | 31 << 11 = 0xF818.
// - v_mov_b32 v3, s10: VOP1 as the IGT words, src0 = SGPR 10 (0x7E060207 had src0 = s7).
// s10 lies within the 16 SGPRs that RSRC1 0x000C0041 allocates (SGPRS field 1 -> 16); s8 is TGID_X
// (RSRC2 0x90: 8 user SGPRs, TGID_X_EN), as in the IGT program.
constexpr std::array<std::uint32_t, 10> kProbeCs = {
    0xB90AF818u,              // s_getreg_b32 s10, hwreg(HW_REG_HW_ID2)
    0xD7460004u, 0x04010C08u, // v_lshl_add_u32 v4, s8, 6, v0
    0x7E000204u,              // v_mov_b32 v0, s4
    0x7E020205u,              // v_mov_b32 v1, s5
    0x7E040206u,              // v_mov_b32 v2, s6
    0x7E06020Au,              // v_mov_b32 v3, s10
    0xE01C2000u, 0x80000004u, // buffer_store_format_xyzw v[0:3], v4, s[0:3], 0 idxen
    0xBF810000u,              // s_endpgm
};

constexpr std::uint32_t kRsrc1 = 0x000C0041u;  // IGT (dispatch_min.hpp kIgtRsrc1)
constexpr std::uint32_t kRsrc2 = 0x00000090u;  // IGT: 8 user SGPRs, TGID_X
constexpr std::uint32_t kVsharpW3 = 0x1104bfacu; // IGT V# word 3
constexpr std::uint32_t kThreads = 64;
constexpr std::uint32_t kSlotBytes = kThreads * 16; // one group, 16 bytes per thread
constexpr std::uint32_t kIbStride = 1024;           // bytes between IBs in the command BO

enum class Target { C0, C1, C2, Gfx };
enum class Kind { Set, Probe };

struct Step {
    Kind kind;
    Target target;
    bool wait; // wait for this job's fence before the next submit (false: pipelined)
};

struct Job {
    Step step;
    std::uint32_t id = 0;   // index in the plan
    std::uint32_t seq = 0;  // sequence number of its block
    std::array<std::uint32_t, 4> ud47{}; // S jobs: the values written; P jobs: unused
};

const char *name(Target t) {
    switch (t) {
    case Target::C0: return "comp0";
    case Target::C1: return "comp1";
    case Target::C2: return "comp2";
    case Target::Gfx: return "gfx";
    }
    return "?";
}

std::uint32_t tag(Target t) {
    switch (t) {
    case Target::C0: return 0x0;
    case Target::C1: return 0x1;
    case Target::C2: return 0x2;
    case Target::Gfx: return 0xF;
    }
    return 0xE;
}

// The plan (the 0427 brief: rings 0..2 set, ring 0 probes; a few orders; once with a GFX-ring
// compute dispatch in between; plus one pipelined block, where the scheduler keeps a busy entity on
// its hardware queue, drivers/gpu/drm/scheduler/sched_entity.c:586-602 @ v7.3).
std::vector<std::vector<Step>> plan() {
    using K = Kind;
    using T = Target;
    return {
        // A: 0, 1, 2 set; each probes.
        {{K::Set, T::C0, true}, {K::Set, T::C1, true}, {K::Set, T::C2, true},
         {K::Probe, T::C0, true}, {K::Probe, T::C1, true}, {K::Probe, T::C2, true}},
        // B: reverse order.
        {{K::Set, T::C2, true}, {K::Set, T::C1, true}, {K::Set, T::C0, true},
         {K::Probe, T::C2, true}, {K::Probe, T::C0, true}},
        // C: another order, a probe right after another ring's set.
        {{K::Set, T::C1, true}, {K::Set, T::C0, true}, {K::Set, T::C2, true},
         {K::Probe, T::C1, true}},
        // D: a GFX-ring compute dispatch between ring 0's set and its probe; the GFX ring probes too.
        {{K::Set, T::C0, true}, {K::Set, T::Gfx, true}, {K::Probe, T::C0, true},
         {K::Probe, T::Gfx, true}},
        // E: pipelined pairs, no wait inside a pair.
        {{K::Set, T::C0, false}, {K::Probe, T::C0, true}, {K::Set, T::C1, false},
         {K::Probe, T::C1, true}},
    };
}

std::vector<Job> jobs_of(const std::vector<std::vector<Step>> &blocks) {
    std::vector<Job> jobs;
    std::uint32_t seq = 0;
    for (const auto &blk : blocks) {
        for (const Step &s : blk) {
            Job j;
            j.step = s;
            j.id = static_cast<std::uint32_t>(jobs.size());
            j.seq = seq;
            const std::uint32_t low = (j.id << 8) | tag(s.target);
            j.ud47 = {0x40000000u | low, 0x50000000u | low, 0x60000000u | low, 0x70000000u | low};
            jobs.push_back(j);
        }
        ++seq;
    }
    return jobs;
}

std::uint32_t lo32(std::uint64_t v) { return static_cast<std::uint32_t>(v & 0xffffffffu); }
std::uint32_t hi32(std::uint64_t v) { return static_cast<std::uint32_t>(v >> 32); }

// The IGT dispatch sequence of bc5::dispatch_min::build_memset_ib (backend/src/dispatch_min.cpp,
// IGT amd_dispatch_helpers.c:16-185 and amd_dispatch.c:142-181 @ 9d4b6ef) for one group, with
// USER_DATA_4..7 written only for an S job. Register offsets as there (COMPUTE_USER_DATA_0 = SH
// 0x240, COMPUTE_PGM_LO = 0x20c).
std::vector<std::uint32_t> build_ib(const Job &j, std::uint64_t shader_va, std::uint64_t slot_va) {
    bc5::pm4::Builder b;
    const bool gfx = j.step.target == Target::Gfx;
    if (gfx) b.packet(Op::ContextControl, {0x80000000u, 0x80000000u}); // GFX ring only (F31)
    b.set_sh_reg(0x204, {0, 0, 0});                                  // COMPUTE_START_X/Y/Z
    b.set_sh_reg(0x218, {0});                                        // COMPUTE_TMPRING_SIZE
    b.set_sh_reg(0x22a, {0});                                        // COMPUTE_SHADER_CHKSUM
    b.set_sh_reg(0x222, {0x222, 0x222, 0x222, 0x222, 0x222, 0x222}); // as IGT, see dispatch_min.cpp
    b.packet(Op::SetUconfigReg, {0x7b, 0x20});                       // CP_COHER_START_DELAY
    b.packet(Op::SetShRegIndex, {0x30000216u, 0xffffffffu, 0xffffffffu}, true); // CU mask SE0/1
    b.packet(Op::SetShRegIndex, {0x219u, 0xffffffffu, 0xffffffffu}, true);      // CU mask SE2/3
    b.set_sh_reg(0x20c, {lo32(shader_va >> 8), lo32(shader_va >> 40)}); // COMPUTE_PGM_LO/HI
    b.set_sh_reg(0x2e12 - bc5::pm4::kShRegBase, {kRsrc1});
    b.set_sh_reg(0x2e13 - bc5::pm4::kShRegBase, {kRsrc2});
    b.set_sh_reg(0x2e07 - bc5::pm4::kShRegBase, {kThreads});
    b.set_sh_reg(0x2e08 - bc5::pm4::kShRegBase, {1});
    b.set_sh_reg(0x2e09 - bc5::pm4::kShRegBase, {1});
    b.set_sh_reg(0x228, {0}); // COMPUTE_PGM_RSRC3
    b.set_sh_reg(0x240, {lo32(slot_va), hi32(slot_va) | 0x100000u /* stride 16 */, kThreads,
                         kVsharpW3}); // USER_DATA_0..3: the slot's V#
    if (j.step.kind == Kind::Set) {
        b.set_sh_reg(0x244, {j.ud47[0], j.ud47[1], j.ud47[2], j.ud47[3]}); // USER_DATA_4..7
    }
    b.set_sh_reg(0x215, {0});                                      // COMPUTE_RESOURCE_LIMITS
    b.packet(Op::DispatchDirect, {1u, 1u, 1u, 1u}, true);          // 1 group, initiator 1 (wave64)
    b.pad_to_multiple(8);
    return b.dwords();
}

// Experiment 0428, --cp-check: the CP's indirect-count check (bc5/indirect_check.hpp, compute_ring = true, the
// FilterOptions default limits x <= 2^20, y, z <= 2^10) around a REAL compute-form DISPATCH_INDIRECT (op 0x16: address
// lo, hi, initiator) of the probe program on a compute ring. Exp 0129 verified the check's packets on the MEC with the
// dispatch replaced by a WRITE_DATA; exp 0290 then kept every indirect dispatch off the MEC after F332's machine-down.
// The triples a failed check would let through are only just over a limit: the program's V# holds 64 records
// (kThreads), so groups past the first store out of range and the hardware drops those stores (buffer bounds with
// idxen); a dispatch of 2^20 + 1 groups that should have been skipped then ends in milliseconds instead of hanging.
struct CpCase {
    std::uint32_t x, y, z;
    bool runs;
};
constexpr CpCase kCpCases[] = {
    {1, 1, 1, true},          {64, 1, 1, true},         {(1u << 20) + 1, 1, 1, false},
    {1, (1u << 10) + 1, 1, false}, {1, 1, (1u << 10) + 1, false}, {1u << 20, 1, 1, true},
};

// The IB of one case: the S-job state (USER_DATA_0..7 set), the dispatch as the compute form of DISPATCH_INDIRECT at
// args_va, through indirect_check::apply on the compute ring; flag_va receives the check's flag and confirm words.
std::vector<std::uint32_t> build_cp_ib(const Job &j, std::uint64_t shader_va, std::uint64_t slot_va, std::uint64_t args_va,
                                       std::uint64_t flag_va, bc5::indirect_check::Stats &st) {
    auto ib = build_ib(j, shader_va, slot_va);
    // replace the DISPATCH_DIRECT (header 0xC0031502, 4 payload dwords) by the compute form of DISPATCH_INDIRECT
    std::size_t at = ib.size();
    for (std::size_t i = 0; i + 4 < ib.size(); ++i)
        if (ib[i] == 0xC0031502u) at = i;
    std::vector<std::uint32_t> in(ib.begin(), ib.begin() + static_cast<std::ptrdiff_t>(at));
    in.insert(in.end(), {0xC0021602u, lo32(args_va), hi32(args_va), 1u});
    const bc5::policy::FilterOptions defaults;
    std::vector<std::size_t> refs;
    auto out = bc5::indirect_check::apply(in, 0, defaults.gpu_check_max, defaults.gpu_check_draw_max, refs, st, true);
    bc5::indirect_check::patch(out, refs, flag_va);
    while (out.size() % 8 != 0) out.push_back(bc5::pm4::kNopFiller);
    return out;
}

// Dry-run checks over one built IB.
bool check_ib(const Job &j, const std::vector<std::uint32_t> &ib) {
    bool ok = ib.size() % 8 == 0 && ib.size() * 4 <= kIbStride;
    bool has_cc = false, has_ud47 = false, has_disp = false;
    for (std::size_t i = 0; i < ib.size();) {
        const std::uint32_t h = ib[i];
        if (h == bc5::pm4::kNopFiller) {
            ++i;
            continue;
        }
        if ((h >> 30) != 3u) return false;
        const std::uint32_t op = (h >> 8) & 0xffu;
        const std::size_t len = ((h >> 16) & 0x3fffu) + 2u;
        if (op == static_cast<std::uint32_t>(Op::ContextControl)) has_cc = true;
        if (op == static_cast<std::uint32_t>(Op::DispatchDirect)) has_disp = true;
        if (op == static_cast<std::uint32_t>(Op::SetShReg) && i + 1 < ib.size()) {
            const std::uint32_t first = ib[i + 1];
            const std::uint32_t last = first + static_cast<std::uint32_t>(len) - 3u;
            if (first <= 0x247u && last >= 0x244u) has_ud47 = true;
        }
        i += len;
    }
    const bool gfx = j.step.target == Target::Gfx;
    ok = ok && has_disp && (has_cc == gfx) && (has_ud47 == (j.step.kind == Kind::Set));
    return ok;
}

int dry_run() {
    const auto jobs = jobs_of(plan());
    int bad = 0;
    std::printf("userdata-rings dry run: %zu jobs, placeholder VAs, no device\nprogram:", jobs.size());
    for (std::uint32_t w : kProbeCs) std::printf(" %08x", w);
    std::printf("\n");
    for (const Job &j : jobs) {
        const std::uint64_t shader_va = 0x0000'0001'0000'0000ull;
        const std::uint64_t slot_va = 0x0000'0001'0010'0000ull + std::uint64_t{j.id} * kSlotBytes;
        const auto ib = build_ib(j, shader_va, slot_va);
        const bool ok = check_ib(j, ib);
        bad += ok ? 0 : 1;
        std::printf("job %2u block %u %-5s %-5s %s %3zu dwords  %s", j.id, j.seq,
                    j.step.kind == Kind::Set ? "set" : "probe", name(j.step.target),
                    j.step.wait ? "wait" : "pipe", ib.size(), ok ? "ok" : "BAD");
        if (j.step.kind == Kind::Set)
            std::printf("  ud4..6 %08x %08x %08x", j.ud47[0], j.ud47[1], j.ud47[2]);
        std::printf("\n");
    }
    std::printf("dry run: %d bad IB(s)\n", bad);
    return bad == 0 ? 0 : 1;
}

// The --cp-check jobs: every case on compute ring indices 0, 1 and 2, each an S job (its own slot, args and flag).
std::vector<std::pair<Job, CpCase>> cp_jobs() {
    std::vector<std::pair<Job, CpCase>> v;
    const Target ts[] = {Target::C0, Target::C1, Target::C2};
    for (Target t: ts) {
        for (const CpCase &c: kCpCases) {
            Job j;
            j.step = {Kind::Set, t, true};
            j.id = static_cast<std::uint32_t>(v.size());
            const std::uint32_t low = (j.id << 8) | tag(t);
            j.ud47 = {0x40000000u | low, 0x50000000u | low, 0x60000000u | low, 0x70000000u | low};
            v.emplace_back(j, c);
        }
    }
    return v;
}

int cp_dry() {
    int bad = 0;
    for (const auto &[j, c]: cp_jobs()) {
        bc5::indirect_check::Stats st;
        const auto ib = build_cp_ib(j, 0x1'0000'0000ull, 0x1'0010'0000ull + std::uint64_t{j.id} * kSlotBytes,
                                    0x1'0020'0000ull + std::uint64_t{j.id} * 64, 0x1'0030'0000ull + std::uint64_t{j.id} * 64, st);
        bool cc = false;
        for (std::uint32_t w: ib) cc = cc || (w & 0xffffff00u) == 0xC0012800u;
        const bool ok = st.checked == 1 && st.conditional == 0 && !cc && ib.size() * 4 <= kIbStride;
        bad += ok ? 0 : 1;
        std::printf("cp job %2u %-5s triple %u %u %u (%s): %3zu dwords, checked %u, inserted %u  %s\n", j.id, name(j.step.target),
                    c.x, c.y, c.z, c.runs ? "runs" : "skipped", ib.size(), st.checked, st.inserted_dwords, ok ? "ok" : "BAD");
    }
    std::printf("cp-check dry run: %d bad IB(s)\n", bad);
    return bad == 0 ? 0 : 1;
}

#ifdef BC5_WITH_AMDGPU

struct Device {
    int fd = -1;
    amdgpu_device_handle dev = nullptr;
    ~Device() {
        if (dev) amdgpu_device_deinitialize(dev);
        if (fd >= 0) close(fd);
    }
};

bool open_device(const std::string &node, Device &d) {
    d.fd = open(node.c_str(), O_RDWR | O_CLOEXEC);
    if (d.fd < 0) {
        std::perror(node.c_str());
        return false;
    }
    std::uint32_t major = 0, minor = 0;
    if (amdgpu_device_initialize(d.fd, &major, &minor, &d.dev) != 0) {
        std::fprintf(stderr, "amdgpu_device_initialize failed on %s\n", node.c_str());
        return false;
    }
    return true;
}

int info(const std::string &node) {
    Device d;
    if (!open_device(node, d)) return 1;
    drm_amdgpu_info_hw_ip gfx{}, comp{};
    amdgpu_query_hw_ip_info(d.dev, AMDGPU_HW_IP_GFX, 0, &gfx);
    amdgpu_query_hw_ip_info(d.dev, AMDGPU_HW_IP_COMPUTE, 0, &comp);
    std::uint32_t count = 0;
    amdgpu_query_hw_ip_count(d.dev, AMDGPU_HW_IP_COMPUTE, &count);
    std::printf("GFX rings mask 0x%x; compute rings mask 0x%x, ip count %u, ib_start_alignment %u, "
                "ib_size_alignment %u\n",
                gfx.available_rings, comp.available_rings, count, comp.ib_start_alignment,
                comp.ib_size_alignment);
    return 0;
}

struct Bo {
    amdgpu_bo_handle bo = nullptr;
    amdgpu_va_handle va_handle = nullptr;
    std::uint64_t va = 0, size = 0;
    void *cpu = nullptr;
    ~Bo() {
        if (cpu) amdgpu_bo_cpu_unmap(bo);
        if (va) amdgpu_bo_va_op(bo, 0, size, va, 0, AMDGPU_VA_OP_UNMAP);
        if (va_handle) amdgpu_va_range_free(va_handle);
        if (bo) amdgpu_bo_free(bo);
    }
};

bool alloc(amdgpu_device_handle dev, std::uint64_t size, std::uint32_t domain, Bo &b) {
    b.size = size;
    amdgpu_bo_alloc_request req{};
    req.alloc_size = size;
    req.phys_alignment = 4096;
    req.preferred_heap = domain;
    if (amdgpu_bo_alloc(dev, &req, &b.bo) != 0) return false;
    if (amdgpu_va_range_alloc(dev, amdgpu_gpu_va_range_general, size, 4096, 0, &b.va, &b.va_handle,
                              0) != 0)
        return false;
    if (amdgpu_bo_va_op(b.bo, 0, size, b.va, 0, AMDGPU_VA_OP_MAP) != 0) return false;
    return amdgpu_bo_cpu_map(b.bo, &b.cpu) == 0;
}

struct Rec {
    std::array<std::uint32_t, 4> first{}; // thread 0: ud4, ud5, ud6, hw_id2
    std::uint32_t differing = 0;          // threads whose record differs from thread 0's
};

// HW_ID2 bits [9:0]: QUEUE_ID [3:0], PIPE_ID [5:4], ME_ID [9:8]. ME_ID's offset (8, 2 bits) is
// LLVM's (SIDefines.h:805, SIInstrInfo.cpp:2649 @ 0b115ab4). TODO(verify): QUEUE_ID and PIPE_ID
// positions, from the RDNA ISA guide's HW_ID2 table; the raw word is printed either way.
std::uint32_t queue_key(std::uint32_t hw_id2) { return hw_id2 & 0x3ffu; }

int submit(const std::string &node) {
    std::fprintf(stderr, "userdata-rings: --submit runs shaders on compute rings 0..2 and the GFX "
                         "ring. A bad submission can hang or reset the machine.\n");
    const auto jobs = jobs_of(plan());
    Device d;
    if (!open_device(node, d)) return 1;
    Bo shader, cmd, dst;
    const std::uint64_t dst_bytes = std::uint64_t{kSlotBytes} * jobs.size();
    if (!alloc(d.dev, 4096, AMDGPU_GEM_DOMAIN_VRAM, shader) ||
        !alloc(d.dev, std::uint64_t{kIbStride} * jobs.size(), AMDGPU_GEM_DOMAIN_GTT, cmd) ||
        !alloc(d.dev, (dst_bytes + 4095) / 4096 * 4096, AMDGPU_GEM_DOMAIN_GTT, dst)) {
        std::fprintf(stderr, "buffer allocation failed\n");
        return 1;
    }
    std::memset(shader.cpu, 0, 4096);
    std::memcpy(shader.cpu, kProbeCs.data(), sizeof(kProbeCs));
    std::memset(dst.cpu, 0, static_cast<std::size_t>(dst.size));
    std::memset(cmd.cpu, 0, static_cast<std::size_t>(cmd.size));

    std::vector<std::uint32_t> ib_dwords(jobs.size());
    for (const Job &j : jobs) {
        const auto ib = build_ib(j, shader.va, dst.va + std::uint64_t{j.id} * kSlotBytes);
        if (!check_ib(j, ib)) {
            std::fprintf(stderr, "job %u: IB check failed; nothing submitted\n", j.id);
            return 1;
        }
        std::memcpy(static_cast<char *>(cmd.cpu) + std::size_t{j.id} * kIbStride, ib.data(),
                    ib.size() * 4);
        ib_dwords[j.id] = static_cast<std::uint32_t>(ib.size());
    }

    amdgpu_context_handle ctx = nullptr; // one context, normal priority, as bc5::direct (direct.cpp)
    if (amdgpu_cs_ctx_create(d.dev, &ctx) != 0) return 1;
    std::vector<amdgpu_bo_handle> list_bos = {shader.bo, cmd.bo, dst.bo};
    amdgpu_bo_list_handle list = nullptr;
    if (amdgpu_bo_list_create(d.dev, 3, list_bos.data(), nullptr, &list) != 0) return 1;

    std::vector<std::uint64_t> seqno(jobs.size(), 0);
    auto ip_of = [](Target t) {
        return static_cast<std::uint32_t>(t == Target::Gfx ? AMDGPU_HW_IP_GFX : AMDGPU_HW_IP_COMPUTE);
    };
    auto ring_of = [](Target t) -> std::uint32_t {
        return t == Target::C1 ? 1u : t == Target::C2 ? 2u : 0u;
    };
    auto wait_job = [&](const Job &j) {
        amdgpu_cs_fence f{};
        f.context = ctx;
        f.ip_type = ip_of(j.step.target);
        f.ring = ring_of(j.step.target);
        f.fence = seqno[j.id];
        std::uint32_t expired = 0;
        const int rc = amdgpu_cs_query_fence_status(&f, 2'000'000'000ull, 0, &expired);
        return rc == 0 && expired != 0;
    };
    int rc = 0;
    std::size_t done = 0;
    std::vector<std::size_t> pending;
    for (const Job &j : jobs) {
        amdgpu_cs_ib_info ibi{};
        ibi.ib_mc_address = cmd.va + std::uint64_t{j.id} * kIbStride;
        ibi.size = ib_dwords[j.id];
        amdgpu_cs_request req{};
        req.ip_type = ip_of(j.step.target);
        req.ring = ring_of(j.step.target);
        req.resources = list;
        req.number_of_ibs = 1;
        req.ibs = &ibi;
        if (amdgpu_cs_submit(ctx, 0, &req, 1) != 0) {
            std::fprintf(stderr, "job %u: submit failed; stopping\n", j.id);
            rc = 1;
            break;
        }
        seqno[j.id] = req.seq_no;
        pending.push_back(j.id);
        if (j.step.wait) {
            bool all = true;
            for (std::size_t p : pending) all = wait_job(jobs[p]) && all;
            pending.clear();
            if (!all) {
                std::fprintf(stderr, "job %u: fence not signalled within 2 s; stopping\n", j.id);
                rc = 3;
                break;
            }
        }
        done = j.id + 1u;
    }
    amdgpu_bo_list_destroy(list);
    amdgpu_cs_ctx_free(ctx);

    // Read back and judge.
    const auto *out = static_cast<const std::uint32_t *>(dst.cpu);
    std::vector<Rec> recs(done);
    for (std::size_t i = 0; i < done; ++i) {
        const std::uint32_t *s = out + i * (kSlotBytes / 4);
        for (int k = 0; k < 4; ++k) recs[i].first[static_cast<std::size_t>(k)] = s[k];
        for (std::uint32_t t = 1; t < kThreads; ++t)
            if (std::memcmp(s + t * 4, s, 16) != 0) ++recs[i].differing;
    }
    int ring_pass = 0, ring_fail = 0, hwq_pass = 0, hwq_fail = 0, hwq_unknown = 0;
    for (std::size_t i = 0; i < done; ++i) {
        const Job &j = jobs[i];
        const Rec &r = recs[i];
        std::printf("job %2u blk %u %-5s %-5s hw_id2 %08x (me %u pipe %u queue %u)  "
                    "ud4..6 %08x %08x %08x  threads differing %u",
                    j.id, j.seq, j.step.kind == Kind::Set ? "set" : "probe", name(j.step.target),
                    r.first[3], (r.first[3] >> 8) & 3u, (r.first[3] >> 4) & 3u, r.first[3] & 0xfu,
                    r.first[0], r.first[1], r.first[2], r.differing);
        if (j.step.kind == Kind::Set) {
            const bool own = r.first[0] == j.ud47[0] && r.first[1] == j.ud47[1] &&
                             r.first[2] == j.ud47[2];
            std::printf("  %s\n", own ? "own values" : "WRONG own values");
            continue;
        }
        // Premise of BC5 (the libdrm ring index): the last earlier job on the same target.
        // Premise of the hardware: the last earlier job on the same hardware queue (HW_ID2).
        const Job *by_ring = nullptr;
        const Rec *by_ring_rec = nullptr;
        const Rec *by_hwq_rec = nullptr;
        for (std::size_t k = i; k-- > 0;) {
            if (!by_ring && jobs[k].step.target == j.step.target) {
                by_ring = &jobs[k];
                by_ring_rec = &recs[k];
            }
            if (!by_hwq_rec && queue_key(recs[k].first[3]) == queue_key(r.first[3]))
                by_hwq_rec = &recs[k];
        }
        auto same = [&](const Rec *o) {
            return o && o->first[0] == r.first[0] && o->first[1] == r.first[1] &&
                   o->first[2] == r.first[2];
        };
        const bool ring_ok = same(by_ring_rec);
        std::printf("  ring-premise %s (last on %s: job %d)", ring_ok ? "PASS" : "FAIL",
                    name(j.step.target), by_ring ? static_cast<int>(by_ring->id) : -1);
        (ring_ok ? ring_pass : ring_fail) += 1;
        if (!by_hwq_rec) {
            std::printf("  hwq-premise n/a (first job on this queue)\n");
            ++hwq_unknown;
        } else {
            const bool ok = same(by_hwq_rec);
            std::printf("  hwq-premise %s\n", ok ? "PASS" : "FAIL");
            (ok ? hwq_pass : hwq_fail) += 1;
        }
    }
    std::printf("summary: %zu of %zu jobs ran; probes: ring-premise %d pass %d fail; "
                "hwq-premise %d pass %d fail %d n/a\n",
                done, jobs.size(), ring_pass, ring_fail, hwq_pass, hwq_fail, hwq_unknown);
    return rc;
}

int cp_check(const std::string &node) {
    std::fprintf(stderr, "userdata-rings --cp-check: real DISPATCH_INDIRECTs under the CP check on compute rings 0..2. A bad "
                         "submission can hang or reset the machine.\n");
    const auto jobs = cp_jobs();
    Device d;
    if (!open_device(node, d)) return 1;
    Bo shader, cmd, dst, args;
    if (!alloc(d.dev, 4096, AMDGPU_GEM_DOMAIN_VRAM, shader) ||
        !alloc(d.dev, std::uint64_t{kIbStride} * jobs.size(), AMDGPU_GEM_DOMAIN_GTT, cmd) ||
        !alloc(d.dev, (std::uint64_t{kSlotBytes} * jobs.size() + 4095) / 4096 * 4096, AMDGPU_GEM_DOMAIN_GTT, dst) ||
        !alloc(d.dev, 4096 * 2, AMDGPU_GEM_DOMAIN_GTT, args)) {
        std::fprintf(stderr, "buffer allocation failed\n");
        return 1;
    }
    std::memset(shader.cpu, 0, 4096);
    std::memcpy(shader.cpu, kProbeCs.data(), sizeof(kProbeCs));
    std::memset(dst.cpu, 0, static_cast<std::size_t>(dst.size));
    std::memset(cmd.cpu, 0, static_cast<std::size_t>(cmd.size));
    auto *aw = static_cast<std::uint32_t *>(args.cpu); // per job: args at 16 dwords * id, flag at 4096 + 16 dwords * id
    for (std::size_t k = 0; k < 2048; ++k) aw[k] = 0xdeadu;
    std::vector<std::uint32_t> n_dw(jobs.size());
    for (const auto &[j, c]: jobs) {
        aw[j.id * 16 + 0] = c.x;
        aw[j.id * 16 + 1] = c.y;
        aw[j.id * 16 + 2] = c.z;
        bc5::indirect_check::Stats st;
        const auto ib = build_cp_ib(j, shader.va, dst.va + std::uint64_t{j.id} * kSlotBytes, args.va + std::uint64_t{j.id} * 64,
                                    args.va + 4096 + std::uint64_t{j.id} * 64, st);
        if (st.checked != 1 || ib.size() * 4 > kIbStride) {
            std::fprintf(stderr, "cp job %u: IB check failed; nothing submitted\n", j.id);
            return 1;
        }
        std::memcpy(static_cast<char *>(cmd.cpu) + std::size_t{j.id} * kIbStride, ib.data(), ib.size() * 4);
        n_dw[j.id] = static_cast<std::uint32_t>(ib.size());
    }
    amdgpu_context_handle ctx = nullptr;
    if (amdgpu_cs_ctx_create(d.dev, &ctx) != 0) return 1;
    std::vector<amdgpu_bo_handle> list_bos = {shader.bo, cmd.bo, dst.bo, args.bo};
    amdgpu_bo_list_handle list = nullptr;
    if (amdgpu_bo_list_create(d.dev, 4, list_bos.data(), nullptr, &list) != 0) return 1;
    int rc = 0, wrong = 0;
    std::size_t done = 0;
    for (const auto &[j, c]: jobs) {
        const std::uint32_t ring = j.step.target == Target::C1 ? 1u : j.step.target == Target::C2 ? 2u : 0u;
        amdgpu_cs_ib_info ibi{};
        ibi.ib_mc_address = cmd.va + std::uint64_t{j.id} * kIbStride;
        ibi.size = n_dw[j.id];
        amdgpu_cs_request req{};
        req.ip_type = AMDGPU_HW_IP_COMPUTE;
        req.ring = ring;
        req.resources = list;
        req.number_of_ibs = 1;
        req.ibs = &ibi;
        const auto t0 = std::chrono::steady_clock::now();
        if (amdgpu_cs_submit(ctx, 0, &req, 1) != 0) {
            std::fprintf(stderr, "cp job %u: submit failed; stopping\n", j.id);
            rc = 1;
            break;
        }
        amdgpu_cs_fence f{};
        f.context = ctx;
        f.ip_type = AMDGPU_HW_IP_COMPUTE;
        f.ring = ring;
        f.fence = req.seq_no;
        std::uint32_t expired = 0;
        if (amdgpu_cs_query_fence_status(&f, 2'000'000'000ull, 0, &expired) != 0 || expired == 0) {
            std::fprintf(stderr, "cp job %u: fence not signalled within 2 s; stopping\n", j.id);
            rc = 3;
            break;
        }
        const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        done = j.id + 1u;
        const auto *s = static_cast<const std::uint32_t *>(dst.cpu) + std::size_t{j.id} * (kSlotBytes / 4);
        const bool wrote = s[0] == j.ud47[0];
        const std::uint32_t flag = aw[1024 + j.id * 16], confirm = aw[1024 + j.id * 16 + 1];
        const bool ok = wrote == c.runs && flag == (c.runs ? 1u : 0u) && confirm == 0u;
        wrong += ok ? 0 : 1;
        std::printf("cp job %2u %-5s triple %u %u %u: expected %s; slot %s (record 0: %08x, hw_id2 %08x), flag 0x%x confirm 0x%x, "
                    "%.2f ms -> %s\n",
                    j.id, name(j.step.target), c.x, c.y, c.z, c.runs ? "runs" : "skipped", wrote ? "WRITTEN" : "untouched", s[0], s[3],
                    flag, confirm, ms, ok ? "as expected" : "WRONG");
    }
    amdgpu_bo_list_destroy(list);
    amdgpu_cs_ctx_free(ctx);
    std::printf("cp-check summary: %zu of %zu jobs ran, %d wrong\n", done, jobs.size(), wrong);
    return rc != 0 ? rc : (wrong == 0 ? 0 : 1);
}

#endif // BC5_WITH_AMDGPU

} // namespace

int main(int argc, char **argv) {
    std::string mode = "dry";
    std::string node = "/dev/dri/renderD128";
    for (int i = 1; i < argc; ++i) {
        const std::string_view a = argv[i];
        if (a == "--info") {
            mode = "info";
        } else if (a == "--submit") {
            mode = "submit";
        } else if (a == "--cp-dry") {
            mode = "cpdry";
        } else if (a == "--cp-check") {
            mode = "cpcheck";
        } else if (a == "--render-node" && i + 1 < argc) {
            node = argv[++i];
        } else {
            std::fputs("usage: userdata-rings [--info | --submit | --cp-dry | --cp-check] [--render-node PATH]\n"
                       "  (no option: dry run, no device)\n",
                       stderr);
            return 2;
        }
    }
    if (mode == "dry") return dry_run();
    if (mode == "cpdry") return cp_dry();
#ifdef BC5_WITH_AMDGPU
    if (mode == "info") return info(node);
    if (mode == "cpcheck") return cp_check(node);
    return submit(node);
#else
    (void)node;
    std::fputs("built without BC5_WITH_AMDGPU; only the dry run is available\n", stderr);
    return 2;
#endif
}
