#!/usr/bin/env python3
"""BC5 experiment 0401 series e5, KYTY_BC5_TLS_FIXES (exp 0405 KL01 and KL02; README top-32 ranks 3 and 4): the patched
TLS loads of every title's main program, in src/loader/runtimeLinker.cpp. Ported from KytyPS5 (github.com/KytyPS5/KytyPS5,
GPL-2.0) dfec14a: src/loader/jit.h:21-117 and src/loader/runtimeLinker.cpp:968-1016.
  kl01  the TLS-load stubs keep RFLAGS: lea rsp,[rsp-0x80] + nop / lea rsp,[rsp+0x80] in place of sub/add rsp,0x80
        (Jit::TlsRegStub and Jit::SafeCall)
  kl02  the TLS scan writes its call at the 0x64 byte, leaves the counted 0x66 bytes alone, uses a REX.W call
        (48 E8 rel32 48 89 C0) and skips a segment under 9 bytes
src/loader/jit.h is NOT edited (no header edits; runtimeLinker.cpp is its only includer, tls0405.cpp the second): the
KytyPS5 structs go into runtimeLinker.cpp under new names and the switch chooses at run time. Off (unset, empty or "0")
writes today's bytes exactly: loader/jit.h's structs and today's scan. Any other value turns both on, unless it names
items (comma-separated "kl01", "kl02"): then only those (e4's KYTY_BC5_AUDIO_FIXES reading). Read once; one stderr line.
Today's TLS scan and today's SetupTlsHandler writes become the switch-off bodies of two functions that tls0405.cpp also
calls (Bc5Tls0405PatchTlsLoads, Bc5Tls0405WriteTlsHandler): the scan's lines stay where they were (its `if` line turns
into a plain block), and the only changed tokens are program->tls.handler_vaddr -> handler_vaddr (2 in the scan, 3 in
the writes) and TlsMainGetAddr -> func (1); the writes' lines move from SetupTlsHandler into the function just before
it, copied by this script from the asserted original, so they are today's text by construction.
Edits the e5 input tree (KytyPlus f266548 + patch 0001 + e4's units; runtimeLinker.cpp is the base tree's, LF line
endings). Every input's md5 is asserted; each anchor must occur exactly once; a tree that has the edit already is
refused; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII.
Prints "<rel> <md5>" for the written file (and the read-only jit.h's md5 on stderr).
usage: mktls0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

REL = "src/loader/runtimeLinker.cpp"
IN_MD5 = "e94b25b8b37d36d97a074ea02723b733"  # the e5 input tree's runtimeLinker.cpp (the base tree's; LF)
RO = (("src/loader/jit.h", "8b5a53504af3ca127c1ab4fe9b55ee45"),)  # read only: the structs that today's path uses
MARKS = (b"KYTY_BC5_TLS_FIXES", b"Bc5Tls0405", b"Bc5TlsCall9", b"experiment 0401 series e5")


def T(text):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    return text.replace("»", "\t").encode("ascii")


# ---- 1. the block before PatchProgram: the switch, KytyPS5's structs, KL02's scan, the two declarations ---------------
BLOCK_ANCHOR = b"static void PatchProgram(Program* program, uint64_t address, uint64_t size) {\n"
BLOCK = T(r"""// ---- experiment 0401 series e5: KYTY_BC5_TLS_FIXES, the patched TLS loads (exp 0405 KL01, KL02) -------------------
// A main program's `mov <reg>,qword ptr fs:[0]` (64 48 8B /r 25 00 00 00 00, after up to three 0x66 bytes) becomes, at
// load time, a call of the TLS handler that SetupTlsHandler writes (Jit::SafeCall, which calls TlsMainGetAddr, and a
// Jit::TlsRegStub per output register; loader/jit.h). Two defects of that patch, in every title whose main ELF has such
// a load:
// - KL01: the original instruction leaves RFLAGS alone, but the stubs step over the guest's red zone with
//   `sub rsp,0x80` ... `add rsp,0x80` around SafeCall's pushfq/popfq, so the guest gets the flags of the last `add`: a
//   compare that the compiler scheduled across the TLS load branches on them. On: `lea rsp,[rsp-0x80]` and a 2-byte
//   nop (the same 7 bytes) and `lea rsp,[rsp+0x80]` (8 bytes: the ret one byte later, one nop less); lea writes no
//   flag. The call and data offsets (TlsRegStub code[9], code[13], code[15]; SafeCall code[0x22]) do not move.
// - KL02: the byte scan counts up to three 0x66 bytes before the load and writes its 9-byte call at the first of them,
//   then nops. A 0x66 that ends the previous instruction (`cmp al,0x66` = 3C 66) is overwritten, and after four 0x66
//   bytes one is left in front of a plain E8 call. On: the call goes at the 0x64 byte itself, the counted 0x66 bytes
//   stay as they are, and the call carries REX.W (48 E8 rel32, then 48 89 C0 mov rax,rax) so that a 0x66 left in
//   front of it cannot make it a 16-bit call on AMD processors, which do not ignore 0x66 on a near branch as Intel's
//   do (Zydis, MIT, include/Zydis/Decoder.h ZYDIS_DECODER_MODE_AMD_BRANCHES, as vendored in GPCS4 88480de
//   3rdParty/zydis; TODO(verify): the AMD64 APM vol. 3 section that gives REX.W precedence over 0x66 for a near CALL;
//   experiment 0401's tls0405.cpp runs such calls on the box's Zen 2). A segment under 9 bytes is not scanned (today's
//   end pointer, start + size - 9, lies before the start, so its loop does not run).
// From KytyPS5 (github.com/KytyPS5/KytyPS5, GPL-2.0) dfec14a: src/loader/jit.h:21-117 (Call9, TlsRegStub, SafeCall)
// and src/loader/runtimeLinker.cpp:968-1016 (the scan). Adapted: the three structs live here under new names, because
// loader/jit.h stays as it is (no header edit); the stub offsets come from Jit::TlsRegStub::GetOffset on both paths;
// the switch chooses at run time. KytyPS5's copyright remains with its authors; GPL-2.0, as the rest of this file.
// KYTY_BC5_TLS_FIXES: unset, empty or "0" is off, today's bytes exactly (loader/jit.h's structs and today's scan); any
// other value turns both items on, unless it names items (comma-separated "kl01", "kl02"): then only those. Read
// once; one line on stderr at the first use. Experiment 0401's tls0405.cpp calls Bc5Tls0405Items,
// Bc5Tls0405PatchTlsLoads and Bc5Tls0405WriteTlsHandler, declaring them itself.
static constexpr uint32_t BC5_TLS_FIX_KL01 = 1u; // the stubs keep RFLAGS
static constexpr uint32_t BC5_TLS_FIX_KL02 = 2u; // the call at the 0x64 byte, with REX.W; no scan under 9 bytes

static uint32_t Bc5TlsFixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    items = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 4 && std::strncmp(p, "kl01", n) == 0) {
»»»items |= BC5_TLS_FIX_KL01;
»»} else if (n == 4 && std::strncmp(p, "kl02", n) == 0) {
»»»items |= BC5_TLS_FIX_KL02;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return items != 0 ? items : (BC5_TLS_FIX_KL01 | BC5_TLS_FIX_KL02);
}

// The items of KYTY_BC5_TLS_FIXES that are on (0: off), read once.
uint32_t Bc5Tls0405Items();
uint32_t Bc5Tls0405Items() {
»static const uint32_t items = [] {
»»const uint32_t i = Bc5TlsFixesParse(std::getenv("KYTY_BC5_TLS_FIXES"));
»»if (i == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: tls fixes off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: tls fixes on (items:%s%s)\n", (i & BC5_TLS_FIX_KL01) != 0 ? " kl01" : "",
»»»             (i & BC5_TLS_FIX_KL02) != 0 ? " kl02" : "");
»»}
»»std::fflush(stderr);
»»return i;
»}();
»return items;
}

namespace {

#pragma pack(1)

// KytyPS5 dfec14a src/loader/jit.h:21-41 (Call9): the patched TLS load with KL02 on.
struct Bc5TlsCall9 {
»void SetFunc(uint64_t func) {
»»auto func_addr = static_cast<int64_t>(func);
»»auto rip_addr  = reinterpret_cast<int64_t>(&code[6]);
»»auto offset64  = func_addr - rip_addr;
»»auto offset32  = static_cast<uint32_t>(static_cast<uint64_t>(offset64) & 0xffffffffu);

»»std::memcpy(&code[2], &offset32, sizeof(offset32));
»}

»static uint64_t GetSize() { return 9; }

»// rex.w call func
»// mov rax,rax
»uint8_t code[9] = {0x48, 0xE8, 0x00, 0x00, 0x00, 0x00, 0x48, 0x89, 0xC0};
};

// KytyPS5 dfec14a src/loader/jit.h:43-72 (TlsRegStub): with KL01 on.
struct Bc5TlsRegStub {
»void SetFunc(uint64_t func) {
»»auto func_addr = static_cast<int64_t>(func);
»»auto rip_addr  = reinterpret_cast<int64_t>(&code[13]);
»»auto offset64  = func_addr - rip_addr;
»»auto offset32  = static_cast<uint32_t>(static_cast<uint64_t>(offset64) & 0xffffffffu);

»»std::memcpy(&code[9], &offset32, sizeof(offset32));
»}

»void SetOutputReg(uint8_t reg) { code[15] = static_cast<uint8_t>(0xc0u | (reg & 7u)); }

»// lea rsp,[rsp-0x80]
»// nop
»// push rax
»// call safe_call
»// mov <reg>,rax
»// pop rax
»// lea rsp,[rsp+0x80]
»// ret
»uint8_t code[32] = {0x48, 0x8D, 0x64, 0x24, 0x80, 0x66, 0x90, 0x50, 0xE8, 0x00, 0x00,
»                    0x00, 0x00, 0x48, 0x89, 0xC0, 0x58, 0x48, 0x8D, 0xA4, 0x24, 0x80,
»                    0x00, 0x00, 0x00, 0xC3, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90};
};

// KytyPS5 dfec14a src/loader/jit.h:74-117 (SafeCall): with KL01 on.
struct Bc5TlsSafeCall {
»void SetFunc(Jit::SafeCall::func_t func) { std::memcpy(&code[0x22], &func, sizeof(func)); }

»uint8_t code[0x90] = {
»    /*00*/ 0x48, 0x8d, 0x64, 0x24, 0x80,             // lea    rsp,[rsp-0x80]
»    /*05*/ 0x66, 0x90,                               // nop
»    /*07*/ 0x9c,                                     // pushfq
»    /*08*/ 0x51,                                     // push   rcx
»    /*09*/ 0x52,                                     // push   rdx
»    /*0a*/ 0x41, 0x50,                               // push   r8
»    /*0c*/ 0x41, 0x51,                               // push   r9
»    /*0e*/ 0x41, 0x52,                               // push   r10
»    /*10*/ 0x41, 0x53,                               // push   r11
»    /*12*/ 0x53,                                     // push   rbx
»    /*13*/ 0x57,                                     // push   rdi
»    /*14*/ 0x56,                                     // push   rsi
»    /*15*/ 0x48, 0x89, 0xe3,                         // mov    rbx,rsp
»    /*18*/ 0x48, 0x83, 0xe4, 0xf0,                   // and    rsp,0xfffffffffffffff0
»    /*1c*/ 0x48, 0x83, 0xec, 0x20,                   // sub    rsp,0x20
»    /*20*/ 0x48, 0xb9, 0x88, 0x77, 0x66, 0x55, 0x44, // movabs rcx,0x1122334455667788
»    /*27*/ 0x33, 0x22, 0x11,                         // (the handler's address: SetFunc, code[0x22])
»    /*2a*/ 0xff, 0xd1,                               // call   rcx
»    /*2c*/ 0x48, 0x89, 0xc1,                         // mov    rcx,rax
»    /*2f*/ 0x48, 0x89, 0xdc,                         // mov    rsp,rbx
»    /*32*/ 0x48, 0x89, 0xc8,                         // mov    rax,rcx
»    /*35*/ 0x5e,                                     // pop    rsi
»    /*36*/ 0x5f,                                     // pop    rdi
»    /*37*/ 0x5b,                                     // pop    rbx
»    /*38*/ 0x41, 0x5b,                               // pop    r11
»    /*3a*/ 0x41, 0x5a,                               // pop    r10
»    /*3c*/ 0x41, 0x59,                               // pop    r9
»    /*3e*/ 0x41, 0x58,                               // pop    r8
»    /*40*/ 0x5a,                                     // pop    rdx
»    /*41*/ 0x59,                                     // pop    rcx
»    /*42*/ 0x9d,                                     // popfq
»    /*43*/ 0x48, 0x8d, 0xa4, 0x24, 0x80, 0x00, 0x00, // lea    rsp,[rsp+0x80]
»    /*4a*/ 0x00,                                     // (lea's last byte)
»    /*4b*/ 0xc3,                                     // ret
»};
};

#pragma pack()

static_assert(sizeof(Bc5TlsCall9) == sizeof(Jit::Call9), "KL02's call has the size of today's");
static_assert(sizeof(Bc5TlsRegStub) == sizeof(Jit::TlsRegStub), "KL01's TlsRegStub has the size of today's");
static_assert(sizeof(Bc5TlsSafeCall) == sizeof(Jit::SafeCall), "KL01's SafeCall has the size of today's");

} // namespace

// KL02 on: KytyPS5 dfec14a src/loader/runtimeLinker.cpp:968-1016, the TLS scan of PatchProgram, with Bc5TlsCall9.
static void Bc5TlsPatchTlsLoadsKl02(uint64_t address, uint64_t size, uint64_t handler_vaddr) {
»if (size < Bc5TlsCall9::GetSize()) {
»»return; // shorter than the load
»}

»const uint8_t tls_pattern[5]       = {0x64, 0x48, 0x8B, 0x00, 0x25};
»const uint8_t zero_displacement[4] = {};

»auto* start_ptr = reinterpret_cast<uint8_t*>(address);
»auto* end_ptr   = start_ptr + size - Bc5TlsCall9::GetSize();

»for (auto* ptr = start_ptr; ptr <= end_ptr; ptr++) {
»»auto*  inst_ptr     = ptr;
»»size_t prefix_count = 0;
»»while (prefix_count < 3 && inst_ptr < start_ptr + size && *inst_ptr == 0x66) {
»»»inst_ptr++;
»»»prefix_count++;
»»}

»»if (inst_ptr + Bc5TlsCall9::GetSize() > start_ptr + size) {
»»»break;
»»}

»»const uint8_t modrm = inst_ptr[3];
»»if (std::memcmp(inst_ptr, tls_pattern, 3) == 0 && (modrm & 0xc7u) == 0x04u && inst_ptr[4] == tls_pattern[4] &&
»»    std::memcmp(inst_ptr + 5, zero_displacement, sizeof(zero_displacement)) == 0) {
»»»LOGF("Patch tls at addr: [%016" PRIx64 "]\n", reinterpret_cast<uint64_t>(inst_ptr));

»»»const auto reg = (modrm >> 3u) & 7u;
»»»EXIT_NOT_IMPLEMENTED(reg == 4u);

»»»// A raw scan can meet a 0x66 of the instruction before, so the call does not overwrite one; its REX.W keeps a real
»»»// 0x66 prefix from making it a 16-bit call on AMD (KytyPS5's comment, runtimeLinker.cpp:1007-1009).
»»»auto* code = new (inst_ptr) Bc5TlsCall9;
»»»code->SetFunc(reg == 0 ? handler_vaddr
»»»                       : handler_vaddr + Jit::TlsRegStub::GetOffset(static_cast<uint8_t>(reg)));
»»»ptr += prefix_count + Bc5TlsCall9::GetSize() - 1;
»»}
»}
}

// PatchProgram's TLS scan and SetupTlsHandler's writes, each chosen by the switch: defined right after PatchProgram
// and right before SetupTlsHandler, around today's lines.
void Bc5Tls0405PatchTlsLoads(uint64_t address, uint64_t size, uint64_t handler_vaddr);
void Bc5Tls0405WriteTlsHandler(uint64_t handler_vaddr, Jit::SafeCall::func_t func);
// ---- end of experiment 0401 series e5's block ------------------------------------------------------------------------

""")

# ---- 2. today's scan: its `if` line keeps its condition in PatchProgram; the scan becomes a function's off body ------
TLS_IF_OLD = T(r"""»if (!program->elf->IsShared() && program->tls.handler_vaddr != 0) {
»»// Replace:
""")
TLS_IF_NEW = T(r"""»// Experiment 0401 series e5 (KYTY_BC5_TLS_FIXES, exp 0405 KL02): the scan that stood here is the body of
»// Bc5Tls0405PatchTlsLoads now (just below), which runs it unchanged with the switch off and KytyPS5's with it on.
»if (!program->elf->IsShared() && program->tls.handler_vaddr != 0) {
»»Bc5Tls0405PatchTlsLoads(address, size, program->tls.handler_vaddr);
»}
}

// ---- experiment 0401 series e5: PatchProgram's TLS scan, chosen by KYTY_BC5_TLS_FIXES (exp 0405 KL02) ----------------
// On: Bc5TlsPatchTlsLoadsKl02 (above PatchProgram). Off: today's scan, PatchProgram's lines as they were but for
// handler_vaddr in place of program->tls.handler_vaddr (the caller tests what the scan's `if` tested).
void Bc5Tls0405PatchTlsLoads(uint64_t address, uint64_t size, uint64_t handler_vaddr) {
»if ((Bc5Tls0405Items() & BC5_TLS_FIX_KL02) != 0) {
»»Bc5TlsPatchTlsLoadsKl02(address, size, handler_vaddr);
»»return;
»}
»// ---- end of experiment 0401 series e5's lines: today's scan follows, its `if` line now a plain block ---------------
»{
»»// Replace:
""")

SETFUNC_OLD = T(r"""»»»»code->SetFunc(reg == 0
»»»»                  ? program->tls.handler_vaddr
»»»»                  : program->tls.handler_vaddr + Jit::TlsRegStub::GetOffset(reg));
""")
SETFUNC_NEW = SETFUNC_OLD.replace(b"program->tls.handler_vaddr", b"handler_vaddr")

# ---- 3. SetupTlsHandler's writes: into Bc5Tls0405WriteTlsHandler, defined just before SetupTlsHandler ---------------
SETUP_OLD = T(r"""»auto* code = new (reinterpret_cast<void*>(program->tls.handler_vaddr)) Jit::SafeCall;

»code->SetFunc(TlsMainGetAddr);

»for (uint8_t reg = 1; reg < 8; reg++) {
»»if (reg == 4) {
»»»continue;
»»}

»»auto* stub = new (reinterpret_cast<void*>(program->tls.handler_vaddr +
»»                                          Jit::TlsRegStub::GetOffset(reg))) Jit::TlsRegStub;
»»stub->SetFunc(program->tls.handler_vaddr);
»»stub->SetOutputReg(reg);
»}
""")
SETUP_NEW = T(r"""»// Experiment 0401 series e5 (KYTY_BC5_TLS_FIXES, exp 0405 KL01): the SafeCall and TlsRegStub writes that stood here
»// are Bc5Tls0405WriteTlsHandler's now (just above), unchanged with the switch off.
»Bc5Tls0405WriteTlsHandler(program->tls.handler_vaddr, TlsMainGetAddr);
""")
SETUP_ANCHOR = b"void RuntimeLinker::SetupTlsHandler(Program* program) {\n"
SETUP_TODAY = SETUP_OLD.replace(b"program->tls.handler_vaddr", b"handler_vaddr").replace(b"TlsMainGetAddr", b"func")
HANDLER_BLOCK = T(r"""// ---- experiment 0401 series e5: SetupTlsHandler's writes of the TLS handler, chosen by KYTY_BC5_TLS_FIXES (KL01) ------
// On: KytyPS5's SafeCall and TlsRegStub bytes (Bc5TlsSafeCall, Bc5TlsRegStub, above PatchProgram), at the same places.
// Off: SetupTlsHandler's lines as they were, but for handler_vaddr and func in place of program->tls.handler_vaddr and
// TlsMainGetAddr.
void Bc5Tls0405WriteTlsHandler(uint64_t handler_vaddr, Jit::SafeCall::func_t func) {
»if ((Bc5Tls0405Items() & BC5_TLS_FIX_KL01) != 0) {
»»auto* safe_call = new (reinterpret_cast<void*>(handler_vaddr)) Bc5TlsSafeCall;
»»safe_call->SetFunc(func);
»»for (uint8_t reg = 1; reg < 8; reg++) {
»»»if (reg == 4) {
»»»»continue;
»»»}
»»»auto* stub = new (reinterpret_cast<void*>(handler_vaddr + Jit::TlsRegStub::GetOffset(reg))) Bc5TlsRegStub;
»»»stub->SetFunc(handler_vaddr);
»»»stub->SetOutputReg(reg);
»»}
»»return;
»}
»// ---- the switch off: SetupTlsHandler's lines follow, as they were ----
""") + SETUP_TODAY + T(r"""}
// ---- end of experiment 0401 series e5's block ------------------------------------------------------------------------

""")


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def once(s, old, new, what):
    assert s.count(old) == 1, (what, old[:80], s.count(old))
    assert balance(old) == balance(new), ("the edit changes the balance", what, balance(old), balance(new))
    return s.replace(old, new)


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit(s):
    for m in MARKS:
        assert m not in s, ("runtimeLinker.cpp has the edit already", m)
    assert md5(s) == IN_MD5, ("runtimeLinker.cpp is not the e5 input tree's", md5(s), IN_MD5)
    s.decode("utf-8")  # the input has a few non-ASCII bytes in comments; the inserted text is ASCII (T)
    assert b"\r\n" not in s, "runtimeLinker.cpp has CRLF line endings: not the e5 input tree's (LF)"
    for b in (BLOCK, HANDLER_BLOCK):
        assert balance(b) == (0, 0, 0), ("a block is not balanced", balance(b))
    # the substitutions take exactly the tokens they should
    assert SETFUNC_OLD.count(b"program->tls.handler_vaddr") == 2 and SETFUNC_NEW.count(b"program->") == 0
    assert SETUP_OLD.count(b"program->tls.handler_vaddr") == 3 and SETUP_OLD.count(b"TlsMainGetAddr") == 1
    assert SETUP_TODAY.count(b"program->") == 0 and SETUP_TODAY.count(b"handler_vaddr") == 3
    assert SETUP_TODAY.count(b"code->SetFunc(func);") == 1
    # 2 before 1: the scan's SetFunc lines are counted against the input, where they occur once
    out = once(s, SETFUNC_OLD, SETFUNC_NEW, "today's scan, SetFunc")
    out = once(out, TLS_IF_OLD, TLS_IF_NEW, "today's scan, its if line")
    assert out.count(BLOCK_ANCHOR) == 1, ("PatchProgram", out.count(BLOCK_ANCHOR))
    out = out.replace(BLOCK_ANCHOR, BLOCK + BLOCK_ANCHOR)
    out = once(out, SETUP_OLD, SETUP_NEW, "SetupTlsHandler's writes")
    assert out.count(SETUP_ANCHOR) == 1, ("SetupTlsHandler", out.count(SETUP_ANCHOR))
    out = out.replace(SETUP_ANCHOR, HANDLER_BLOCK + SETUP_ANCHOR)
    assert balance(out) == balance(s), ("the unit's balance changed", balance(s), balance(out))
    out.decode("utf-8")
    assert sum(c > 127 for c in out) == sum(c > 127 for c in s), "the edit changed the non-ASCII bytes"
    # order: block < PatchProgram < its call < the scan function < ... < the writes function < SetupTlsHandler < its call
    order = [b"uint32_t Bc5Tls0405Items() {", b"static void Bc5TlsPatchTlsLoadsKl02(", BLOCK_ANCHOR,
             b"\t\tBc5Tls0405PatchTlsLoads(address, size, program->tls.handler_vaddr);",
             b"void Bc5Tls0405PatchTlsLoads(uint64_t address, uint64_t size, uint64_t handler_vaddr) {",
             b"void Bc5Tls0405WriteTlsHandler(uint64_t handler_vaddr, Jit::SafeCall::func_t func) {", SETUP_ANCHOR,
             b"\tBc5Tls0405WriteTlsHandler(program->tls.handler_vaddr, TlsMainGetAddr);"]
    for o in order:
        assert out.count(o) == 1, ("must occur once", o[:70], out.count(o))
    at = [out.index(o) for o in order]
    assert at == sorted(at), ("order", at)
    # today's code is in the output as it was: the scan (from its comment to its end) and the writes
    scan_old = s[s.index(TLS_IF_OLD) + len(TLS_IF_OLD.split(b"\n")[0]) + 1:]
    scan_old = scan_old[:scan_old.index(b"\n}\n") + 3].replace(SETFUNC_OLD, SETFUNC_NEW)
    assert out.count(scan_old) == 1, "today's scan is not in the output once"
    assert out.count(SETUP_TODAY) == 1, "today's writes are not in the output once"
    assert out.count(b"Bc5Tls0405Items()") == 4  # declaration, definition, two uses
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    for rel, want in RO:
        with open(os.path.join(root, rel), "rb") as f:
            b = f.read()
        assert md5(b) == want, (rel, "is not the e5 input tree's", md5(b), want)
        print(f"# read only: {rel} {md5(b)} (not written)", file=sys.stderr)
    with open(os.path.join(root, REL), "rb") as f:
        s = f.read()
    print(f"# in: {REL} {md5(s)}", file=sys.stderr)
    out = edit(s)
    dst = os.path.join(outdir, REL)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "wb") as f:
        f.write(out)
    print(f"{REL} {md5(out)}")


if __name__ == "__main__":
    main()
