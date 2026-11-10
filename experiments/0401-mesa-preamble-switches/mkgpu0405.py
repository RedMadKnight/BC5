#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, tag gpu: experiment 0405's R3 "e4-now" GPU items in src/libs/bc5LleAgc.cpp, in the
soft CP (the CPU executor of packets) and the gc ioctl handlers only. Nothing changes what is submitted to amdgpu.
  G2  BC5_R3_MEMSEM_SIGNAL     MEM_SEMAPHORE (0x39) signal in the soft CP (op 6: SIGNAL_TYPE bit 20 stores 1, else adds 1)
  G4  BC5_R3_REWIND_CATCH      catcher: REWIND (0x59) whose VALID bit 31 is clear (count + one journal line)
  G8  BC5_R3_DROP_CATCH        catcher: packets the policy table drops, per opcode; custom NOPs, per sub-code (bits 7:2)
  G6  BC5_R3_SUBMIT_EOP_EVENT  ioctl 0xc020810c raises the graphics EOP event (0x40) after the call's buffers
  G11 BC5_R3_COND_WRITE        COND_WRITE (0x45) in the soft CP
  G12 BC5_R3_WAIT_IDLE         ioctl 0xc0048117 returns once the completion queues are empty (bounded at 2 s)
  G14 BC5_R3_TS_100MHZ         the soft CP's GPU-clock timestamps (DATA_SEL 3, COPY_DATA SRC_SEL 9) as a 100-MHz count
Each switch is off by default and read once (bc5::env_on). Design, sources, tests and risks: gpu0405-notes.md; the CPU
test is gpu0405.cpp (it calls the unit through the extern "C" seams bc5_exp0405_gpu_*).
The input is the e5 input tree's unit (md5 pinned below). --chain drops that pin, for a unit another e5 agent has edited
first (tag eq edits the kevent/equeue/timer and mmap shims of the same file): every anchor still has to occur exactly
once, and a unit that has this edit already is refused either way. After the edit the script reverts it in memory and
asserts that the input comes back byte for byte. Prints "<rel> <md5>" for the output.
usage: mkgpu0405.py [--chain] <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/libs/bc5LleAgc.cpp"
IN_MD5 = "df12bb2de3e90b8c82a234eedf0babb5"  # the e5 input tree's unit (e4's)
# Present only once this edit is in (the eq agent's edit has other names): refuse such an input.
MARKS = (b"bc5_exp0405_gpu_", b"BC5_R3_MEMSEM_SIGNAL", b"r3gpu()", b"exp 0405: gpu")


def tabs(text):
    """The C++ below is written with 4-space indents; the unit indents with tabs."""
    out = []
    for line in text.split("\n"):
        body = line.lstrip(" ")
        k = len(line) - len(body)
        out.append("\t" * (k // 4) + " " * (k % 4) + body)
    return "\n".join(out).encode("ascii")


# ---------------------------------------------------------------------------------------------------------------------
# 1. The block in namespace SoftCp, before write_timestamp_or_data (it needs now_ns, addr64, compare, fire_eop, t_cur_*).
A1_OLD = tabs(r"""// Writes `value` per DATA_SEL (bits 31:29 of the data-control dword) to `address`.
static void write_timestamp_or_data(uint32_t data_sel, uint64_t address, uint32_t lo, uint32_t hi) {
""")
A1_BLOCK = tabs(r"""// ---- experiment 0405 (exp 0401 series e5, tag gpu): R3's e4-now items in the soft CP and the gc ioctls ---------------
// Experiment 0405 raw/r3-gpu-memory.md, "e4-now port specs" G2, G4, G6, G8, G11, G12 and G14. Nothing here changes what is
// submitted to amdgpu: the policy (backend/policy/pm4-policy.tsv, "default-op drop") still NOPs MEM_SEMAPHORE, COND_WRITE
// and REWIND on the GPU path. What changes is the soft CP's own execution, host events after a fence, and catchers (a
// count, and one journal line per kind). No header is touched: all state lives in this file. Each item has its own switch,
// off by default and read once, at the first use (bc5::env_on, backend/include/bc5/env_flag.hpp, F767: on when set,
// non-empty and not "0"); off, each site takes today's path. The first use prints one line on stderr:
// "[bc5] exp 0405: gpu on (items: <switches>)" or "[bc5] exp 0405: gpu off".
//   BC5_R3_MEMSEM_SIGNAL     G2   MEM_SEMAPHORE (0x39) signals run in the soft CP; waits are counted only
//   BC5_R3_REWIND_CATCH      G4   catcher: REWIND (0x59) with its VALID bit clear
//   BC5_R3_DROP_CATCH        G8   catcher: packets the policy table drops, per opcode; custom NOPs, per sub-code
//   BC5_R3_SUBMIT_EOP_EVENT  G6   ioctl 0xc020810c raises the graphics EOP event after the call's buffers
//   BC5_R3_COND_WRITE        G11  COND_WRITE (0x45) runs in the soft CP
//   BC5_R3_WAIT_IDLE         G12  ioctl 0xc0048117 returns once the completion queues are empty (at most 2 s)
//   BC5_R3_TS_100MHZ         G14  the soft CP's GPU-clock timestamps as a 100-MHz count
// Journal (Direct::journal, BC5_GC_DUMP_DIR/direct.log): the first occurrence of each kind with where it was, then only
// counts; a summary line "exp 0405 gpu: ..." at most every 10 s (from submit() below) when a count has moved.
// Upstream code is GPL (AnyPS5 4f41f4c37 GPL-2.0-only, KytyPS5 dfec14a GPL-2.0, shadPS4 60c42b9 GPL-2.0-or-later, RPCSX
// e8ae148 GPL-2.0, sharpemu 514d766 GPL-2.0-or-later): only behaviour is taken, rewritten here, and their copyrights stay
// with their authors. Mesa ab2374a (MIT) gives opcode facts only.
constexpr uint32_t IT_MEM_SEMAPHORE = 0x39; // Mesa ab2374a src/amd/common/sid.h:88
constexpr uint32_t IT_COND_WRITE    = 0x45; // sid.h:128
constexpr uint32_t IT_REWIND        = 0x59; // sid.h:206, "GFX8+ [any ring]"

struct R3Gpu {
    bool memsem = false, rewind = false, drop = false, submit_eop = false, cond_write = false, wait_idle = false, ts100 = false;
    bool any() const { return memsem || rewind || drop || submit_eop || cond_write || wait_idle || ts100; }
};
static bool r3gpu_env(const char* name) {
    const char* e = std::getenv(name);
#if defined(KYTY_BC5_DIRECT)
    return bc5::env_on(e);
#else
    return e != nullptr && e[0] != 0 && !(e[0] == '0' && e[1] == 0); // bc5::env_on's reading (its header comes with the backend)
#endif
}
static const R3Gpu& r3gpu() {
    static const R3Gpu s = [] {
        R3Gpu       v;
        std::string items;
        auto        take = [&items](const char* name) {
            const bool on = r3gpu_env(name);
            if (on) {
                if (!items.empty()) items += ", ";
                items += name;
            }
            return on;
        };
        v.memsem     = take("BC5_R3_MEMSEM_SIGNAL");
        v.rewind     = take("BC5_R3_REWIND_CATCH");
        v.drop       = take("BC5_R3_DROP_CATCH");
        v.submit_eop = take("BC5_R3_SUBMIT_EOP_EVENT");
        v.cond_write = take("BC5_R3_COND_WRITE");
        v.wait_idle  = take("BC5_R3_WAIT_IDLE");
        v.ts100      = take("BC5_R3_TS_100MHZ");
        if (v.any()) {
            std::fprintf(stderr, "[bc5] exp 0405: gpu on (items: %s)\n", items.c_str());
        } else {
            std::fprintf(stderr, "[bc5] exp 0405: gpu off\n");
        }
        return v;
    }();
    return s;
}

// The counts (the CPU test reads them by these indices through bc5_exp0405_gpu_count).
enum R3GpuCount : int {
    kR3MemsemSet,      // G2: signals with SIGNAL_TYPE 1 (the word set to 1)
    kR3MemsemAdd,      // G2: signals with SIGNAL_TYPE 0 (1 added)
    kR3MemsemWait,     // G2: waits (op 7), not held (G3 is a later port)
    kR3MemsemOther,    // G2: not executed (not 4 dwords, address 0, an op other than 6 and 7)
    kR3Rewind,         // G4: REWIND packets walked
    kR3RewindInvalid,  // G4: ... with VALID (dword 1 bit 31) clear
    kR3DropPackets,    // G8: packets whose opcode the policy table drops
    kR3NopCustom,      // G8: NOPs with header bits 7:2 not 0
    kR3EopEvents,      // G6: EOP events raised for the submit-and-write-EOP ioctl
    kR3EopChained,     // G6: ... of which handed to a held chain (BC5_DIRECT_CHAIN=2)
    kR3CondWritten,    // G11: condition true, the dword written
    kR3CondNotWritten, // G11: condition false
    kR3CondOther,      // G11: not executed (register poll or destination, function 7, not 9 dwords, address 0)
    kR3WaitIdle,       // G12: wait-idle ioctls that waited
    kR3WaitIdleGaveUp, // G12: ... that gave up at 2 s
    kR3TsWrites,       // G14: timestamps written as a 100-MHz count
    kR3CountN
};
static std::atomic<uint64_t> g_r3gpu_count[kR3CountN];
static std::atomic<uint64_t> g_r3gpu_drop_op[256]; // G8, per opcode
static std::atomic<uint64_t> g_r3gpu_nop_sub[64];  // G8, per custom-NOP sub-code
static std::atomic<uint64_t> g_r3gpu_seen[6];      // the kinds journaled once: bits 0-255 opcodes, 256-319 sub-codes, 320+ others
constexpr uint32_t           kR3SeenSub   = 256;
constexpr uint32_t           kR3SeenOther = 320;
static bool r3gpu_first(uint32_t bit) {
    const uint64_t m = 1ull << (bit & 63u);
    return (g_r3gpu_seen[bit >> 6u].fetch_or(m, std::memory_order_relaxed) & m) == 0;
}
// Where a packet was, for a journal line: its address and offset in the buffer the soft CP walks (the submitted buffer or
// an INDIRECT_BUFFER target), and the buffer submit() was handed (t_cur_*; stale on the ring thread's own passes).
static void r3gpu_where(char* out, size_t cap, const uint32_t* buf, uint32_t at) {
    std::snprintf(out, cap, "packet at %p (offset %u of the buffer at %p), in %s %u dwords at %p", static_cast<const void*>(buf + at), at,
                  static_cast<const void*>(buf), t_cur_kind, t_cur_n, static_cast<const void*>(t_cur_buf));
}

// G2 (BC5_R3_MEMSEM_SIGNAL). The console's form, 4 dwords (KytyPS5 src/graphics/guest_gpu/command_processor/
// pm4Handlers.cpp:2077-2088, header 0xc0023900; AnyPS5 core/libs/prx/libSceAgcDriver/Execution/src/Pm4.cpp:507-512, size 4;
// sharpemu src/SharpEmu.Libs/Agc/AgcExports.MemSemaphore.cs:47-58, the builder: op << 29 | type << 20 | mailbox << 16):
// dword 1 the address (bits 31:3), dword 2 its high bits, dword 3 the control: SEM_SEL bits 31:29 (6 signal, 7 wait),
// SIGNAL_TYPE bit 20, USE_MAILBOX bit 16 (the field names: shadPS4 src/video_core/amdgpu/pm4_cmds.h PM4CmdMemSemaphore, in
// the PS4's 3-dword form). The semaphore is a 64-bit word (AnyPS5 docs/dev/debt/libSceAgcDriver.md:62: inferred from the
// 8-byte alignment the builder checks, not measured). A signal with SIGNAL_TYPE 1 stores 1, with 0 adds 1, atomically
// (AnyPS5 Pm4.cpp:1130-1147; KytyPS5 src/graphics/guest_gpu/graphicsRun.cpp:277-285; shadPS4 pm4_cmds.h Signal(),
// src/video_core/amdgpu/liverpool.cpp:799-809); KytyPS5 notes a signal's mailbox never stalls. A wait (op 7, G3) is
// counted and journaled only: holding the queue is a later port. The address's high dword keeps 16 bits, as everywhere
// in this soft CP (addr64; KytyPS5 keeps 18, AnyPS5 all: the same for user addresses below 2^47). The GPU path still NOPs
// the packet (pm4-policy.tsv default-op drop).
static void r3gpu_mem_semaphore(const uint32_t* buf, uint32_t at, uint32_t len) {
    const uint32_t* p       = buf + at;
    const uint32_t  control = len == 4 ? p[3] : 0u;
    const uint32_t  sel     = control >> 29u;
    const uint64_t  a       = len == 4 ? addr64(p[1] & ~7u, p[2]) : 0;
    char            where[256];
    if (len != 4 || a == 0 || (sel != 6 && sel != 7)) {
        g_r3gpu_count[kR3MemsemOther]++;
        if (r3gpu_first(kR3SeenOther + 0)) {
            r3gpu_where(where, sizeof(where), buf, at);
            Direct::journal("exp 0405 gpu: MEM_SEMAPHORE not executed (%u dwords, control 0x%08x, address 0x%" PRIx64 "), %s; counted from here\n", len, control, a, where);
        }
        return;
    }
    if (sel == 7) {
        g_r3gpu_count[kR3MemsemWait]++;
        if (r3gpu_first(kR3SeenOther + 1)) {
            r3gpu_where(where, sizeof(where), buf, at);
            Direct::journal("exp 0405 gpu: MEM_SEMAPHORE wait on 0x%" PRIx64 " (control 0x%08x) not held (G3 is a later port), %s; counted from here\n", a, control, where);
        }
        return;
    }
    auto*      w   = reinterpret_cast<uint64_t*>(a);
    const bool set = (control & 0x100000u) != 0;
    if (set) {
        __atomic_store_n(w, uint64_t {1}, __ATOMIC_RELEASE);
    } else {
        __atomic_fetch_add(w, uint64_t {1}, __ATOMIC_ACQ_REL);
    }
    g_r3gpu_count[set ? kR3MemsemSet : kR3MemsemAdd]++;
    if (r3gpu_first(kR3SeenOther + 2)) {
        r3gpu_where(where, sizeof(where), buf, at);
        Direct::journal("exp 0405 gpu: MEM_SEMAPHORE signal (%s) on 0x%" PRIx64 " executed by the soft CP, %s; counted from here\n", set ? "set 1" : "add 1", a, where);
    }
}

// G4 (BC5_R3_REWIND_CATCH), a catcher: nothing is executed. REWIND is 2 dwords, dword 1 bit 31 VALID and bit 24
// OFFLOAD_ENABLE (AnyPS5 Execution/include/Pm4.hpp:162-163, Pm4.cpp:497-500; shadPS4 pm4_cmds.h PM4CmdRewind; KytyPS5
// pm4Handlers.cpp:1324-1333, header 0xc0005900). With VALID clear the console's parser stops there until the CPU sets the
// bit and then fetches what follows afresh (shadPS4 liverpool.cpp:815-824, KytyPS5 WaitForRewind). The GPU path NOPs it
// and runs the copy made at submission. Counted: every REWIND the soft CP walks, and those with VALID clear; the first of
// these is journaled with where it was and how many of the dwords after it in that buffer are not 0. The soft CP reads
// guest memory when it runs (after the fence when posted), when the CPU may have set the bit already: a lower bound.
static void r3gpu_rewind(const uint32_t* buf, uint32_t at, uint32_t num_dwords, uint32_t len) {
    g_r3gpu_count[kR3Rewind]++;
    if (len != 2 || (buf[at + 1] & 0x80000000u) != 0) return;
    g_r3gpu_count[kR3RewindInvalid]++;
    if (!r3gpu_first(kR3SeenOther + 3)) return;
    uint32_t nonzero = 0;
    for (uint32_t k = at + len; k < num_dwords; k++) {
        if (buf[k] != 0) nonzero++;
    }
    char where[256];
    r3gpu_where(where, sizeof(where), buf, at);
    Direct::journal("exp 0405 gpu: REWIND with VALID clear (dword 1 0x%08x), %s; %u of the %u dwords after it in that buffer are not 0; counted from here\n", buf[at + 1], where,
                    nonzero, num_dwords - at - len);
}

// G8 (BC5_R3_DROP_CATCH), a catcher on the unit's side (the backend's FilterStats has no per-opcode count, and the backend
// is not this experiment's to change): every type-3 packet the soft CP walks whose opcode the policy table gives the
// verdict Drop (bc5::policy::Policy::builtin().op(), the table the filter uses: pm4-policy.tsv's "default-op drop" line,
// and its two listed drops 0x4a PREAMBLE_CNTL and 0x8e GET_LOD_STATS, which the query cannot tell apart), per opcode; and
// every NOP (0x10) whose header bits 7:2 are not 0, per sub-code: the console's custom NOPs (KytyPS5
// src/graphics/guest_gpu/pm4.h:74-84 and command_processor/pm4Dispatch.cpp:223-229; AnyPS5 Execution/src/Pm4.cpp:223-240,
// header & 0xfc, sub-code (header >> 2) & 0x3f). The policy passes NOP and the AMD CP ignores its payload. The first packet
// of each opcode and of each sub-code is journaled. Not seen: what a COND_EXEC skipped in the soft CP, IBs nested deeper
// than 4, and the filter's own drops in code (unmapped operands and the like). Without the direct path (no
// KYTY_BC5_DIRECT) there is no policy: only the sub-codes are counted.
static void r3gpu_drop_note(const uint32_t* buf, uint32_t at, uint32_t header, uint32_t op) {
    char where[256];
    if (op == IT_NOP) {
        if ((header & 0xfcu) == 0) return;
        const uint32_t sub = (header >> 2u) & 0x3fu;
        g_r3gpu_nop_sub[sub]++;
        g_r3gpu_count[kR3NopCustom]++;
        if (r3gpu_first(kR3SeenSub + sub)) {
            r3gpu_where(where, sizeof(where), buf, at);
            Direct::journal("exp 0405 gpu: custom NOP sub-code 0x%02x (header 0x%08x), %s; counted from here\n", sub, header, where);
        }
        return;
    }
#if defined(KYTY_BC5_DIRECT)
    if (bc5::policy::Policy::builtin().op(static_cast<uint8_t>(op)) != bc5::policy::Verdict::Drop) return;
    g_r3gpu_drop_op[op & 0xffu]++;
    g_r3gpu_count[kR3DropPackets]++;
    if (r3gpu_first(op & 0xffu)) {
        r3gpu_where(where, sizeof(where), buf, at);
        Direct::journal("exp 0405 gpu: opcode 0x%02x (header 0x%08x) is NOP-ed by the policy on the GPU path, %s; counted from here\n", op, header, where);
    }
#endif
}

// G11 (BC5_R3_COND_WRITE): COND_WRITE, 9 dwords: dword 1 FUNCTION bits 2:0, POLL_SPACE bit 4 (1 memory), WRITE_SPACE bits
// 9:8 (1 memory); the poll address in dwords 2-3, the reference in 4, the mask in 5, the write address in 6-7, the data in
// 8 (AnyPS5 Execution/src/Pm4.cpp:513-520 and 736-739; RPCSX rpcsx/gpu/Pipe.cpp:1266-1300). When (*poll & mask) <function>
// (reference & mask) holds, the dword is written. RPCSX masks both sides (Pipe.cpp:66-88), as this soft CP's compare() does
// for WAIT_REG_MEM; AnyPS5 (Pm4.cpp:589-600) masks the value only: they differ only for reference bits outside the mask,
// TODO(verify). Register polls, register or scratch destinations and the reserved function 7 are counted and not executed
// (AnyPS5 refuses them, RPCSX's compare is false for 7). The GPU path still NOPs the packet.
static void r3gpu_cond_write(const uint32_t* buf, uint32_t at, uint32_t len) {
    const uint32_t* p       = buf + at;
    const uint32_t  control = len == 9 ? p[1] : 0u;
    const uint64_t  poll    = len == 9 ? addr64(p[2], p[3]) : 0;
    const uint64_t  dst     = len == 9 ? addr64(p[6], p[7]) : 0;
    char            where[256];
    if (len != 9 || (control & 7u) == 7u || ((control >> 4u) & 1u) == 0 || ((control >> 8u) & 3u) != 1u || poll == 0 || dst == 0) {
        g_r3gpu_count[kR3CondOther]++;
        if (r3gpu_first(kR3SeenOther + 4)) {
            r3gpu_where(where, sizeof(where), buf, at);
            Direct::journal("exp 0405 gpu: COND_WRITE not executed (%u dwords, control 0x%08x, poll 0x%" PRIx64 ", write 0x%" PRIx64 "), %s; counted from here\n", len, control, poll, dst,
                            where);
        }
        return;
    }
    const uint32_t value = *reinterpret_cast<volatile uint32_t*>(poll);
    const bool     hit   = compare(control & 7u, value, p[5], p[4]);
    if (hit) *reinterpret_cast<volatile uint32_t*>(dst) = p[8];
    g_r3gpu_count[hit ? kR3CondWritten : kR3CondNotWritten]++;
    if (r3gpu_first(kR3SeenOther + 5)) {
        r3gpu_where(where, sizeof(where), buf, at);
        Direct::journal("exp 0405 gpu: COND_WRITE executed by the soft CP (function %u, value 0x%08x, reference 0x%08x, mask 0x%08x: %s 0x%08x to 0x%" PRIx64 "), %s; counted from here\n",
                        control & 7u, value, p[4], p[5], hit ? "wrote" : "did not write", p[8], dst, where);
    }
}

// G6 (BC5_R3_SUBMIT_EOP_EVENT): the gc ioctl 0xc020810c "submit and write eop" raises the graphics EOP interrupt with its
// eopValue once its buffers are done. RPCSX rpcsx/iodev/gc.cpp:250-277 submits the buffers, then DeviceCtl::submitWriteEop
// (rpcsx/gpu/DeviceCtl.cpp:60-80): an EVENT_WRITE_EOP with address 0, INT_SEL 2 and DATA_SEL 2 carrying eopValue, which its
// pipe delivers as kGcEventGfxEop 0x40 (rpcsx/gpu/Pipe.cpp:20-30). Here: fire_eop(eopValue) on the graphics side (0x40,
// and ident 0 quietly, as for a RELEASE_MEM with INT_SEL), through Direct::post: after the fence of the call's buffers on
// the completion thread when submission is asynchronous (BC5_DIRECT_JOURNAL=min), at once when each job is waited for or
// there is no direct path. With the game thread's chain held across its ioctls (BC5_DIRECT_CHAIN=2) the buffers are not
// submitted yet, so RPCSX's EVENT_WRITE_EOP itself (6 dwords, the form event_write_eop below reads; address 0, so nothing
// is written) goes to the chain as a soft-CP replay, posted behind the chain's fence. The replay reads it later, so it
// lives in a ring of 4096 slots. Nothing is submitted to the GPU for it. RPCSX also waits for idle at the end of this
// ioctl (gc.cpp:271); that is not ported here (G12 is the wait-idle ioctl's).
static uint32_t              g_r3gpu_eop_slots[4096][6];
static std::atomic<uint32_t> g_r3gpu_eop_next {0};
static void r3gpu_submit_eop(uint64_t eop_value) {
    g_r3gpu_count[kR3EopEvents]++;
    const bool chained = Direct::chain_cross();
    if (chained) {
        uint32_t* s = g_r3gpu_eop_slots[g_r3gpu_eop_next.fetch_add(1, std::memory_order_relaxed) & 4095u];
        s[0]        = 0xc0044700u;                 // PKT3 EVENT_WRITE_EOP (0x47), count 4: 6 dwords
        s[1]        = 0;                           // EVENT_CNTL (RPCSX: the event type is not used)
        s[2]        = 0;                           // address lo
        s[3]        = (2u << 24u) | (2u << 29u);   // INT_SEL 2, DATA_SEL 2, address hi 0
        s[4]        = static_cast<uint32_t>(eop_value);
        s[5]        = static_cast<uint32_t>(eop_value >> 32u);
        g_r3gpu_count[kR3EopChained]++;
        Direct::chain_soft_push(s, 6, "r3eop");
    } else {
        Direct::post([eop_value](bool) { fire_eop(eop_value); });
    }
    if (r3gpu_first(kR3SeenOther + 6)) {
        Direct::journal("exp 0405 gpu: submit-and-write-EOP ioctl: the graphics EOP event (0x40) with 0x%" PRIx64 " raised after the call's buffers%s; counted from here\n", eop_value,
                        chained ? " (behind the held chain)" : "");
    }
}

// G12 (BC5_R3_WAIT_IDLE): the count and the journal of the wait in gc_ioctl (0xc0048117).
static void r3gpu_wait_idle_note(bool gave_up, double ms) {
    g_r3gpu_count[kR3WaitIdle]++;
    if (gave_up) g_r3gpu_count[kR3WaitIdleGaveUp]++;
    if (r3gpu_first(kR3SeenOther + 7)) Direct::journal("exp 0405 gpu: wait-idle ioctl waited %.1f ms for the completion queues; counted from here\n", ms);
    if (gave_up && r3gpu_first(kR3SeenOther + 8)) Direct::journal("exp 0405 gpu: wait-idle ioctl gave up after %.1f ms with the completion queues not empty; counted from here\n", ms);
}

// G14 (BC5_R3_TS_100MHZ): the soft CP's GPU-clock timestamps (RELEASE_MEM / EVENT_WRITE_EOP DATA_SEL 3, Mesa sid.h:168
// EOP_DATA_SEL_TIMESTAMP; COPY_DATA SRC_SEL 9, sid.h:107 COPY_DATA_TIMESTAMP) as a 100-MHz count. AnyPS5's debt note
// docs/dev/debt/libSceAgcDriver.md:287 measured both as one counter at 98.0 and 99.8 MHz on a PS5 (firmware 13.40), and
// AnyPS5 Execution/src/Pm4.cpp:1178-1180 writes the steady clock in 10-ns ticks. The epoch is the host's steady clock, not
// the GPU's own counter that the direct path's GPU-written timestamps carry: TODO(verify) the box's gpu_counter_freq (amdgpu
// device info) before mixing the two. DATA_SEL 4 and SRC_SEL 0xa keep nanoseconds: their console frequency is not measured.
static uint64_t r3gpu_clock() {
    g_r3gpu_count[kR3TsWrites]++;
    return now_ns() / 10u;
}

// The summary line, at most every 10 s and only when a count has moved; from submit() (any switch on).
static void r3gpu_summary() {
    static std::mutex m;
    static uint64_t   last_ns = 0, last_total = 0;
    std::unique_lock  lk(m, std::try_to_lock);
    if (!lk.owns_lock()) return;
    const uint64_t now = now_ns();
    if (last_ns != 0 && now - last_ns < 10'000'000'000ull) return;
    last_ns = now;
    uint64_t c[kR3CountN];
    uint64_t total = 0;
    for (int k = 0; k < kR3CountN; k++) {
        c[k] = g_r3gpu_count[k].load(std::memory_order_relaxed);
        total += c[k];
    }
    if (total == last_total) return;
    last_total = total;
    std::string ops, subs;
    char        b[32];
    for (uint32_t k = 0; k < 256; k++) {
        if (const uint64_t v = g_r3gpu_drop_op[k].load(std::memory_order_relaxed); v != 0) {
            std::snprintf(b, sizeof(b), " %02x:%" PRIu64, k, v);
            ops += b;
        }
    }
    for (uint32_t k = 0; k < 64; k++) {
        if (const uint64_t v = g_r3gpu_nop_sub[k].load(std::memory_order_relaxed); v != 0) {
            std::snprintf(b, sizeof(b), " %02x:%" PRIu64, k, v);
            subs += b;
        }
    }
    Direct::journal("exp 0405 gpu: t %.3f s: MEM_SEMAPHORE set %" PRIu64 " add %" PRIu64 " wait %" PRIu64 " other %" PRIu64 "; REWIND %" PRIu64 " (VALID clear %" PRIu64 "); dropped by the policy %" PRIu64
                    " (by opcode:%s); custom NOPs %" PRIu64 " (by sub-code:%s); submit-EOP events %" PRIu64 " (chained %" PRIu64 "); COND_WRITE wrote %" PRIu64 " not %" PRIu64 " other %" PRIu64
                    "; wait idle %" PRIu64 " (gave up %" PRIu64 "); 100-MHz timestamps %" PRIu64 "\n",
                    Direct::timing_now(), c[kR3MemsemSet], c[kR3MemsemAdd], c[kR3MemsemWait], c[kR3MemsemOther], c[kR3Rewind], c[kR3RewindInvalid], c[kR3DropPackets], ops.c_str(),
                    c[kR3NopCustom], subs.c_str(), c[kR3EopEvents], c[kR3EopChained], c[kR3CondWritten], c[kR3CondNotWritten], c[kR3CondOther], c[kR3WaitIdle], c[kR3WaitIdleGaveUp],
                    c[kR3TsWrites]);
}
// ---- end of experiment 0405's (tag gpu) soft-CP block ------------------------------------------------------------------

""")

# 2. G14 in write_timestamp_or_data (DATA_SEL 3).
A2_OLD = tabs(r"""        case 3:
        case 4: *reinterpret_cast<volatile uint64_t*>(address) = now_ns(); break;
""")
A2_NEW = tabs(r"""        case 3:
            if (r3gpu().ts100) { // experiment 0405 G14 (BC5_R3_TS_100MHZ): the GPU clock as a 100-MHz count; off, today's ns
                *reinterpret_cast<volatile uint64_t*>(address) = r3gpu_clock();
                break;
            }
            [[fallthrough]];
        case 4: *reinterpret_cast<volatile uint64_t*>(address) = now_ns(); break;
""")

# 3. G14 in copy_data (SRC_SEL 9). The comments are aligned with spaces in the unit.
A3_OLD = (b"\t\tcase 9:" + b" " * 62 + b"// perf counter\n"
          b"\t\tcase 0xa: value = now_ns(); break;" + b" " * 35 + b"// timestamp\n")
A3_NEW = b"\t\tcase 9:" + b" " * 62 + b"// perf counter\n" + tabs(r"""            // Experiment 0405 G14 (BC5_R3_TS_100MHZ): SRC_SEL 9 is the GPU clock (Mesa sid.h:107 COPY_DATA_TIMESTAMP),
            // as a 100-MHz count; off, today's ns.
            if (r3gpu().ts100) {
                value = r3gpu_clock();
                break;
            }
            [[fallthrough]];
""") + b"\t\tcase 0xa: value = now_ns(); break;" + b" " * 35 + b"// timestamp\n"

# 4. G8 in execute(): the catcher, before the soft CP's switch.
A4_OLD = tabs(r"""            g_packets++;
            switch (op) {
                case IT_NOP: break;
""")
A4_NEW = tabs(r"""            g_packets++;
            if (r3gpu().drop) r3gpu_drop_note(buf, i, header, op); // experiment 0405 G8 (BC5_R3_DROP_CATCH): a catcher, nothing executed
            switch (op) {
                case IT_NOP: break;
""")

# 5. G2, G11, G4 in execute(): three cases before the default. Off, each takes the default's path (g_skipped).
A5_OLD = tabs(r"""                case IT_DISPATCH_INDIRECT: record_dispatch(p, true); g_skipped[op]++; break;
                default: g_skipped[op & 0xffu]++; break;
""")
A5_NEW = tabs(r"""                case IT_DISPATCH_INDIRECT: record_dispatch(p, true); g_skipped[op]++; break;
                // Experiment 0405 (exp 0401 series e5, tag gpu): G2, G11 and G4. Off, each takes the default's path below.
                case IT_MEM_SEMAPHORE: // G2 (BC5_R3_MEMSEM_SIGNAL)
                    if (!r3gpu().memsem) {
                        g_skipped[op & 0xffu]++;
                        break;
                    }
                    if (!done) r3gpu_mem_semaphore(buf, i, len);
                    break;
                case IT_COND_WRITE: // G11 (BC5_R3_COND_WRITE)
                    if (!r3gpu().cond_write) {
                        g_skipped[op & 0xffu]++;
                        break;
                    }
                    if (!done) r3gpu_cond_write(buf, i, len);
                    break;
                case IT_REWIND: // G4 (BC5_R3_REWIND_CATCH): counted, not executed
                    if (r3gpu().rewind) r3gpu_rewind(buf, i, num_dwords, len);
                    g_skipped[op & 0xffu]++;
                    break;
                default: g_skipped[op & 0xffu]++; break;
""")

# 6. The summary, at the end of a submitted buffer's pass.
A6_OLD = tabs(r"""    execute(buf, num_dwords, 0);
    if (n < 16 || (n & 0xffu) == 0) {
""")
A6_NEW = tabs(r"""    execute(buf, num_dwords, 0);
    if (r3gpu().any()) r3gpu_summary(); // experiment 0405 (tag gpu): at most every 10 s
    if (n < 16 || (n & 0xffu) == 0) {
""")

# 7. The CPU test's seams, after submit() (they use it), before the queue consumer.
A7_OLD = tabs(r"""// Consumes the hardware-style queues the driver registered (ioctl 0xc0408121): for each queue,
""")
A7_BLOCK = tabs(r"""// ---- experiment 0405 (tag gpu): the CPU test's seams (gpu0405.cpp); always compiled in, never called by the emulator ----
// bc5_exp0405_gpu_count takes the R3GpuCount indices above.
extern "C" int bc5_exp0405_gpu_switches() {
    const R3Gpu& s = r3gpu();
    return (s.memsem ? 1 : 0) | (s.rewind ? 2 : 0) | (s.drop ? 4 : 0) | (s.submit_eop ? 8 : 0) | (s.cond_write ? 16 : 0) | (s.wait_idle ? 32 : 0) |
           (s.ts100 ? 64 : 0);
}
extern "C" void bc5_exp0405_gpu_soft_submit(const uint32_t* buf, uint32_t num_dwords) {
    submit(buf, num_dwords, "gpu0405");
}
extern "C" uint64_t bc5_exp0405_gpu_count(int which) {
    return which >= 0 && which < kR3CountN ? g_r3gpu_count[which].load() : 0;
}
extern "C" uint64_t bc5_exp0405_gpu_drop_op(uint32_t op) {
    return g_r3gpu_drop_op[op & 0xffu].load();
}
extern "C" uint64_t bc5_exp0405_gpu_nop_sub(uint32_t sub) {
    return g_r3gpu_nop_sub[sub & 0x3fu].load();
}
extern "C" int bc5_exp0405_gpu_has_policy() {
#if defined(KYTY_BC5_DIRECT)
    return 1;
#else
    return 0;
#endif
}
extern "C" void bc5_exp0405_gpu_register_eq(int64_t eq, int ident, int add) {
    register_eq(eq, ident, add != 0);
}
extern "C" void bc5_exp0405_gpu_post(void (*fn)(void*), void* arg) {
    Direct::post([fn, arg](bool) { fn(arg); });
}
extern "C" int bc5_exp0405_gpu_async() {
    return Direct::async_on() ? 1 : 0;
}
// ---- end of experiment 0405's (tag gpu) seams ------------------------------------------------------------------------

""")

# 8. G6 in gc_ioctl 0xc020810c, after today's store of the value.
A8_OLD = tabs(r"""            // TODO(bc5): where the EOP value is written on the console is not known yet (RPCSX
            // has its own submitWriteEop); the submit-done page gets it for now.
            if (g_submit_area != nullptr) {
                static_cast<uint64_t*>(g_submit_area)[0] = a->eop_value;
            }
            return 0;
""")
A8_NEW = tabs(r"""            // TODO(bc5): where the EOP value is written on the console is not known yet (RPCSX
            // has its own submitWriteEop); the submit-done page gets it for now.
            if (g_submit_area != nullptr) {
                static_cast<uint64_t*>(g_submit_area)[0] = a->eop_value;
            }
            // Experiment 0405 G6 (BC5_R3_SUBMIT_EOP_EVENT): the graphics EOP event with eop_value once the buffers above have
            // run (SoftCp::r3gpu_submit_eop; RPCSX rpcsx/iodev/gc.cpp:250-277). Off: today's, the value stored only.
            if (SoftCp::r3gpu().submit_eop) SoftCp::r3gpu_submit_eop(a->eop_value);
            return 0;
""")

# 9. G12 in gc_ioctl 0xc0048117.
A9_OLD = tabs(r"""            Direct::chain_observe(); // ADR 0010 section B: the title asks about the GPU
            return 0;
""")
A9_NEW = tabs(r"""            Direct::chain_observe(); // ADR 0010 section B: the title asks about the GPU
            // Experiment 0405 G12 (BC5_R3_WAIT_IDLE): "wait idle" blocks until the work handed over has run (RPCSX e8ae148
            // rpcsx/iodev/gc.cpp:287-293 waits for idle in 0xc0048117. Its 0xc0048116, gc.cpp:279-285, has the wait commented
            // out but no break, so it falls into the same wait: TODO(verify) whether that is meant; 0xc0048116 stays as it is
            // here, as R3's spec says). Here it returns once the completion queues are empty: every job queued so far has
            // passed its fence and every soft-CP replay posted behind one has run, the wait Direct::drain() does at the flip,
            // but without drain()'s chain flushes (chain_observe above already submitted the held chains; a flush here could
            // close another thread's chain earlier, a different submission) and bounded at 2 s (a replay's label poll can
            // hold a queue).
            // Without asynchronous submission each job was waited for when it was submitted: nothing to wait for.
            // Off: today's, at once.
            if (idle && SoftCp::r3gpu().wait_idle) {
                const uint64_t t0      = SoftCp::now_ns();
                bool           gave_up = false;
#if defined(KYTY_BC5_DIRECT)
                if (Direct::async_on()) {
                    while (Direct::g_cq_items.load() != 0) {
                        if (SoftCp::now_ns() - t0 >= 2'000'000'000ull) {
                            gave_up = true;
                            break;
                        }
                        std::this_thread::sleep_for(std::chrono::microseconds(50));
                    }
                }
#endif
                SoftCp::r3gpu_wait_idle_note(gave_up, static_cast<double>(SoftCp::now_ns() - t0) / 1e6);
            }
            return 0;
""")

# 10. The test's seam into gc_ioctl, right after it.
A10_OLD = tabs(r"""            return 0;
        }
    }
}

// /dev/dipsw: dip-switch (debug setting) queries from libSceAgc. All switches off.
""")
A10_BLOCK = tabs(r"""// Experiment 0405 (tag gpu): the CPU test's seam into gc_ioctl (gpu0405.cpp, G6 and G12); never called by the emulator.
extern "C" int bc5_exp0405_gpu_gc_ioctl(uint64_t request, void* argp) {
    return gc_ioctl(request, argp);
}

""")
A10_NEW = A10_OLD.replace(b"// /dev/dipsw:", A10_BLOCK + b"// /dev/dipsw:", 1)

# (old, new, what) in file order; each old must occur exactly once in the input.
EDITS = (
    (A1_OLD, A1_BLOCK + A1_OLD, "the soft-CP block before write_timestamp_or_data"),
    (A2_OLD, A2_NEW, "write_timestamp_or_data DATA_SEL 3 (G14)"),
    (A3_OLD, A3_NEW, "copy_data SRC_SEL 9 (G14)"),
    (A4_OLD, A4_NEW, "execute(): the G8 catcher before the switch"),
    (A5_OLD, A5_NEW, "execute(): the G2, G11 and G4 cases"),
    (A6_OLD, A6_NEW, "submit(): the summary"),
    (A7_OLD, A7_BLOCK + A7_OLD, "the seams after submit()"),
    (A8_OLD, A8_NEW, "gc_ioctl 0xc020810c (G6)"),
    (A9_OLD, A9_NEW, "gc_ioctl 0xc0048117 (G12)"),
    (A10_OLD, A10_NEW, "the gc_ioctl seam"),
)

# The regions this edit may touch (a line inside: soft CP namespace, and gc_ioctl): checked on the input.
REGIONS = ((b"namespace SoftCp {\n", b"} // namespace SoftCp\n"),
           (b"static int gc_ioctl(uint64_t request, void* argp) {\n", b"static int dipsw_ioctl(uint64_t request, void* argp) {\n"))


def eol_of(s):
    crlf, lf = s.count(b"\r\n"), s.count(b"\n")
    assert crlf == 0 or crlf == lf, ("mixed line endings", crlf, lf)
    return b"\r\n" if crlf else b"\n"


def in_regions(s, pos, n):
    for start, end in REGIONS:
        a = s.index(start)
        b = s.index(end, a)
        if a <= pos and pos + n <= b + len(end):
            return True
    return False


def edit(s):
    for m in MARKS:
        assert m not in s, f"{REL} has this edit already ({m.decode()} is in it)"
    eol = eol_of(s)
    for start, end in REGIONS:
        assert s.count(start.replace(b"\n", eol)) == 1 and s.count(end.replace(b"\n", eol)) == 1, ("region", start)
    conv = [(o.replace(b"\n", eol), n.replace(b"\n", eol), w) for o, n, w in EDITS]
    for old, _new, what in conv:
        assert s.count(old) == 1, (what, old[:100], s.count(old))
        assert in_regions(s.replace(b"\r\n", b"\n"), s.replace(b"\r\n", b"\n").index(old.replace(b"\r\n", b"\n")),
                          len(old.replace(b"\r\n", b"\n"))), ("outside this agent's regions", what)
    o = s
    for old, new, what in conv:
        o = o.replace(old, new, 1)
    # Every new text is in once; the switches and seams are where they should be.
    for _old, new, what in conv:
        assert o.count(new) == 1, ("new text", what, o.count(new))
    assert o.index(b"static const R3Gpu& r3gpu() {") < o.index(b"if (r3gpu().ts100)")
    assert o.index(b"static void submit(const uint32_t* buf") < o.index(b"extern \"C\" void bc5_exp0405_gpu_soft_submit(")
    assert o.index(b"static int gc_ioctl(uint64_t request") < o.index(b"extern \"C\" int bc5_exp0405_gpu_gc_ioctl(")
    for name in (b"BC5_R3_MEMSEM_SIGNAL", b"BC5_R3_REWIND_CATCH", b"BC5_R3_DROP_CATCH", b"BC5_R3_SUBMIT_EOP_EVENT",
                 b"BC5_R3_COND_WRITE", b"BC5_R3_WAIT_IDLE", b"BC5_R3_TS_100MHZ"):
        assert o.count(b'take("' + name + b'")') == 1, name
    assert eol_of(o) == eol
    # Reverting the edit gives the input back, byte for byte (the output minus this edit is the input).
    r = o
    for old, new, what in reversed(conv):
        assert r.count(new) == 1, ("revert", what)
        r = r.replace(new, old, 1)
    assert r == s, "the edit does not revert to the input"
    # Braces and parentheses of the inserted text balance (comments and literals included; the texts have none unbalanced).
    for _old, new, what in conv:
        assert new.count(b"{") - new.count(b"}") == _old.count(b"{") - _old.count(b"}"), ("braces", what)
        assert new.count(b"(") - new.count(b")") == _old.count(b"(") - _old.count(b")"), ("parentheses", what)
    return o


def main():
    args = sys.argv[1:]
    chain = False
    if args and args[0] == "--chain":
        chain, args = True, args[1:]
    assert len(args) == 2, __doc__
    root, out = args
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    md5 = hashlib.md5(s).hexdigest()
    if chain:
        if md5 != IN_MD5:
            print(f"mkgpu0405: --chain: {REL} is {md5}, not the e5 input ({IN_MD5}); the anchors decide", file=sys.stderr)
    else:
        assert md5 == IN_MD5, f"{REL} is {md5}, not the e5 input tree's {IN_MD5} (--chain for an edited unit)"
    o = edit(s)
    p = os.path.join(out, REL)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(o)
    print(f"{REL} {hashlib.md5(o).hexdigest()}")


if __name__ == "__main__":
    main()
