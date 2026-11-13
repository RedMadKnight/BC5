#!/usr/bin/env python3
"""BC5 experiment 0416, the "later round" of exp 0413 in the same build (the top session, 2026-11-12):

  agc       src/libs/bc5LleAgc.cpp (md5 8f6e92b3): Codex's EOP ownership fix (its audit/eop-owned.cpp.diff and
            make_eop_owned_candidate.py, 2026-11-12; the edits below are that script's prepare(), taken as written).
            r3gpu_submit_eop no longer rotates a global ring of 4,096 packets that a deferred soft-CP replay read by raw
            address; the replay owns a copy (a shared_ptr captured with the queue entry). Unconditional: it only changes
            who owns the six dwords. BC5_R3_SUBMIT_EOP_EVENT itself stays a switch.
  ampr      src/libs/libAmpr.cpp (md5 ddf52b7b): set-buffer's map flavour is opt-in. Neither of our titles passes six
            arguments (exp 0413: 2,304 traced calls of the second title, ASTRO BOT's calls), so the flavour chosen from
            a3/a4 is taken only with KYTY_BC5_AMM_SETBUFFER_MAP=1; without it a call with the map signature on a target
            that is not mapped is the buffer flavour too, with one stderr line. The guard of exp 0413 stays in front.
  defaults  src/bc5/switch_defaults.hpp (md5 852f4d03): the pure fixes leave the behaviour table for a second table that
            KYTY_BC5_SWITCH_DEFAULTS=0 does not skip: A2 BC5_DIRECT_ACB_STATE_RESTORE (3 of 3 faults without it), C1
            KYTY_BC5_EVENT_PENDING_CAP=64 (a leak), C2 KYTY_BC5_RANGES_FAST and C3 KYTY_BC5_PHYSMAP_SORTED (same
            answers, speed only). Each is still turned off by NAME=0 in the environment.
usage: mk0416x.py agc|ampr|defaults <in> <out>"""
import hashlib
import sys


def one(s, a, b):
    assert s.count(a) == 1, a[:80]
    return s.replace(a, b)


def function(s, sig):
    start = s.index(sig)
    return s[start:s.index(b"\n}", start) + 2]


def agc(s):
    assert hashlib.md5(s).hexdigest().startswith("8f6e92b3"), hashlib.md5(s).hexdigest()
    decl = b"static void chain_soft_push(const uint32_t* dwords, uint32_t n, const char* kind);"
    s = one(s, decl, b"static void chain_soft_push_copy(const uint32_t* dwords, uint32_t n, const char* kind);\n" + decl)
    s = one(s, b"static uint32_t              g_r3gpu_eop_slots[4096][6];\nstatic std::atomic<uint32_t> g_r3gpu_eop_next {0};\n", b"")
    s = one(s, b"\t\tuint32_t* s = g_r3gpu_eop_slots[g_r3gpu_eop_next.fetch_add(1, std::memory_order_relaxed) & 4095u];",
            b"\t\tuint32_t s[6] {}; // copied into the queued replay before returning")
    s = one(s, b'Direct::chain_soft_push(s, 6, "r3eop");', b'Direct::chain_soft_push_copy(s, 6, "r3eop");')
    s = one(s, b"// lives in a ring of 4096 slots. Nothing is submitted to the GPU for it.",
            b"// owns a copy through completion of its callback. Nothing is submitted to the GPU for it.")
    s = one(s, b"struct ChainSoft {\n\tconst uint32_t* dwords;\n\tuint32_t        n;\n\tconst char*     kind;\n};",
            b"struct ChainSoft {\n\tconst uint32_t* dwords;\n\tuint32_t        n;\n\tconst char*     kind;\n"
            b"\tstd::shared_ptr<const std::vector<uint32_t>> owned {}; // host-generated replay only; captured by value with e\n};")
    old_push = function(s, b"static void chain_soft_push(const uint32_t* dwords, uint32_t n, const char* kind) {")
    copy_push = (b"// Experiment 0416 (Codex's review of exp 0413): host-generated packets must survive both the held chain and the\n"
                 b"// completion queue. Guest command-buffer replays keep their borrowed-buffer semantics.\n"
                 b"static void chain_soft_push_copy(const uint32_t* dwords, uint32_t n, const char* kind) {\n"
                 b"\tauto owned = std::make_shared<const std::vector<uint32_t>>(dwords, dwords + n);\n"
                 b"\tChainSlot& s = g_chain_tl;\n"
                 b"\tstd::lock_guard lk(s.mu);\n"
                 b"\ts.soft.push_back({owned->data(), n, kind, owned});\n"
                 b"\tif (s.c.segs.empty() && !s.in_submit) chain_post_soft_locked(s);\n"
                 b"}")
    s = one(s, old_push, old_push + b"\n" + copy_push)
    stub = b"static void chain_soft_push(const uint32_t*, uint32_t, const char*) {}"
    s = one(s, stub, stub + b"\nstatic void chain_soft_push_copy(const uint32_t*, uint32_t, const char*) {}")
    return s


def ampr(s):
    assert hashlib.md5(s).hexdigest().startswith("ddf52b7b"), hashlib.md5(s).hexdigest()
    cond = (b"\tif (SetBufferIsMapFlavour(va, a3, a4) && !Bc5SetBufferTargetMapped(reinterpret_cast<uint64_t>(command_buffer), va, size, a3, a4, a5)) { // + exp 0413\n")
    new = (b"\tif (SetBufferIsMapFlavour(va, a3, a4) && !Bc5SetBufferTargetMapped(reinterpret_cast<uint64_t>(command_buffer), va, size, a3, a4, a5) && // + exp 0413\n"
           b"\t    Bc5SetBufferMapAllowed(reinterpret_cast<uint64_t>(command_buffer), va, size, a3, a4, a5)) { // + exp 0416\n")
    s = one(s, cond, new)
    func = (b"static int KYTY_SYSV_ABI CommandBufferSetBuffer(void* command_buffer, void* buffer, uint32_t size,\n"
            b"                                                uint64_t a3, uint64_t a4, uint64_t a5) {\n")
    helper = (b"// Experiment 0416 (KYTY_BC5_AMM_SETBUFFER_MAP): the map flavour is opt-in. Neither of our two titles passes more than\n"
              b"// three arguments (exp 0413), so a3-a5 are leftovers and the flavour would be chosen by chance. Off (the default): a\n"
              b"// call with the map signature is the buffer flavour, with a line for the first 16. =1: exp 0035's map flavour, for\n"
              b"// a target that is not mapped yet (the guard above still refuses mapped ones).\n"
              b"static bool Bc5SetBufferMapAllowed(uint64_t cb, uint64_t va, uint32_t size, uint64_t a3, uint64_t a4, uint64_t a5) {\n"
              b"\tstatic const bool on = [] {\n"
              b"\t\tconst char* e = std::getenv(\"KYTY_BC5_AMM_SETBUFFER_MAP\");\n"
              b"\t\treturn e != nullptr && e[0] != '\\0' && std::strcmp(e, \"0\") != 0;\n"
              b"\t}();\n"
              b"\tif (on) {\n"
              b"\t\treturn true;\n"
              b"\t}\n"
              b"\tstatic int told = 0;\n"
              b"\tif (told < 16) {\n"
              b"\t\ttold++;\n"
              b"\t\tstd::fprintf(stderr,\n"
              b"\t\t             \"[bc5] exp 0416: set-buffer with the map signature on a target that is not mapped (cb 0x%016\" PRIx64 \" va 0x%016\" PRIx64\n"
              b"\t\t             \" len 0x%x a3 0x%\" PRIx64 \" a4 0x%\" PRIx64 \" a5 0x%\" PRIx64 \"): taken as the buffer flavour (KYTY_BC5_AMM_SETBUFFER_MAP=1 maps)\\n\",\n"
              b"\t\t             cb, va, size, a3, a4, a5);\n"
              b"\t}\n"
              b"\treturn false;\n"
              b"}\n\n")
    return one(s, func, helper + func)


def defaults(s):
    assert hashlib.md5(s).hexdigest().startswith("852f4d03"), hashlib.md5(s).hexdigest()
    rows = [(b"    // A2: acb state restore (exp 0381, 0401 series c)\n", b'    {"BC5_DIRECT_ACB_STATE_RESTORE", "1"},\n'),
            (b"    // C1: graphics event pending cap\n", b'    {"KYTY_BC5_EVENT_PENDING_CAP", "64"},\n'),
            (b"    // C2: fast AMM range query\n", b'    {"KYTY_BC5_RANGES_FAST", "1"},\n'),
            (b"    // C3: sorted physical-mapping table\n", b'    {"KYTY_BC5_PHYSMAP_SORTED", "1"},\n')]
    fixes = (b"// Experiment 0416: pure fixes (a fault, a leak, two same-answer speed-ups). They are not behaviour choices, so\n"
             b"// KYTY_BC5_SWITCH_DEFAULTS=0 does not skip them; NAME=0 in the environment still turns one off.\n"
             b"inline constexpr Default kFixes[] = {\n")
    for c, r in rows:
        s = one(s, c + r, b"")
        fixes += c + r
    fixes += b"    {nullptr, nullptr}};\n\n"
    s = one(s, b"inline constexpr Default kDefaults[] = {\n", fixes + b"inline constexpr Default kDefaults[] = {\n")
    s = one(s, b"inline void Apply() {\n", b"inline void Apply() {\n"
            b"\tfor (const Default* d = kFixes; d->name != nullptr; d++) {\n"
            b"\t\tsetenv(d->name, d->value, 0);\n"
            b"\t}\n")
    return s


if __name__ == "__main__":
    src = open(sys.argv[2], "rb").read()
    assert b"\r" not in src
    out = {"agc": agc, "ampr": ampr, "defaults": defaults}[sys.argv[1]](src)
    open(sys.argv[3], "wb").write(out)
    print(hashlib.md5(out).hexdigest())
