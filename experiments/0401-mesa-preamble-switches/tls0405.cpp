// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, KYTY_BC5_TLS_FIXES (mktls0405.py; exp 0405 KL01, KL02): the CPU test of the patched TLS
// loads in src/loader/runtimeLinker.cpp. It writes the TLS handler's code and patches synthetic code buffers through the
// unit's own functions (Loader::Bc5Tls0405WriteTlsHandler and Loader::Bc5Tls0405PatchTlsLoads, which SetupTlsHandler and
// PatchProgram call; declared below, there is no header), in mmap'd pages of 0xCC bytes, and runs the results on this
// CPU. Run three times on the box, in the build container, each in a fresh directory:
//   KYTY_BC5_TLS_FIXES=1 tls0405        (on: kl01 and kl02)
//   KYTY_BC5_TLS_FIXES=0 tls0405        (off)
//   tls0405                             (unset: off)
// A comma list (KYTY_BC5_TLS_FIXES=kl02) turns on only those items; every case follows the item it tests. The program
// prints one line per case, then exactly "tls0405: on N of N; end" (any item on) or "tls0405: off N of N; end", and
// exits 0 only then. A watchdog ends a hang after 20 s with a FAIL line (exit 3); a fault in the generated code prints a
// FAIL line naming the case (exit 4). The unit prints "[bc5] exp 0405: tls fixes on (items: ...)" or "... off" on
// stderr once. It needs no game, GPU, window, sound device or network, and writes no file.
// Cases:
//    1 the switch: the unit's reading (Bc5Tls0405Items) equals this test's
//    2 this test's "today" sequences equal loader/jit.h's own structs (Jit::SafeCall, Jit::TlsRegStub, Jit::Call9)
//   (a) the stubs, written by Bc5Tls0405WriteTlsHandler into a page of 0xCC bytes:
//    3 SafeCall's 0x90 bytes. kl01 on: KytyPS5 dfec14a jit.h:74-117 (lea rsp,[rsp-0x80]; nop ... lea rsp,[rsp+0x80];
//      ret at 0x4b); off: loader/jit.h's (sub rsp,0x80 ... add rsp,0x80; ret at 0x4a). The handler's address at 0x22.
//    4 the six TlsRegStubs (rcx rdx rbx rbp rsi rdi) at Jit::TlsRegStub::GetOffset(reg): the bytes as in 3 (KytyPS5
//      jit.h:43-72 / loader/jit.h:89-117), rel32 to the SafeCall, the output register
//    5 no other byte of the page changed
//   (b) the stubs run on this CPU (the asm sets RFLAGS with popfq, calls the stub, reads RFLAGS with pushfq):
//    6 rax through SafeCall, CF PF AF ZF SF OF all set;  7 the same, all clear
//    8 rbx through its TlsRegStub (which calls SafeCall), all set (rax must survive);  9 the same, all clear
//      kl01 on: the six flags must survive and the register get the handler's value. Off: the value is checked and
//      the flags today's stubs return are printed, measured and not asserted (expected: those of `add rsp,0x80`).
//   (c) the TLS scan, Bc5Tls0405PatchTlsLoads, over synthetic code in a page of 0xCC bytes; the whole two-page region
//       (handler and code) is compared with the expected one, so a byte changed outside the instruction fails. kl02
//       on: KytyPS5's bytes (48 E8 rel32 48 89 C0 at the 0x64 byte, the 0x66 bytes kept); off: today's (E8 rel32
//       48 89 C0 90 at the first counted 0x66, then a nop per 0x66). Then the patched code runs, where its bytes can:
//   10 3C 66 | 64 48 8B 04 25 00000000 | C3: a 0x66 that ends `cmp al,0x66`. Off: recorded, today's call overwrites
//      it (not run)
//   11 66 66 66 | 64 48 8B 1C 25 00000000 | C3: rbx, three 0x66 (the static linker's TLS local-dynamic to local-exec
//      form; TODO(verify): which linker relaxations emit it)
//   12 66 | 64 48 8B 04 25 00000000 | C3: one 0x66 (on: 66 48 E8 runs, a 64-bit call with REX.W)
//   13 64 48 8B 04 25 00000000 | C3: no 0x66
//   14 66 66 66 66 | 64 48 8B 04 25 00000000 | C3: four 0x66; the scan counts three. Off: recorded, today's leaves
//      66 E8 (a 16-bit call on AMD; not run)
//   15 two loads in a row, rax then rbx | C3
//   16 a 9-byte segment that is exactly the load (the C3 after it is outside the segment)
//   17 an 8-byte segment holding the first 8 bytes of a load (the ninth follows outside it): nothing written either way
//   18 a 5-byte segment, the same
//   19 no match: mov rax,fs:[0x28], mov rax,gs:[0], mov rax,fs:[rsp+8], mov eax,fs:[0], mov r8,fs:[0]: nothing written
// Build (box0401's build0401.py, series e5): compiled with src/loader/runtimeLinker.cpp's compile command
// (--gate tls0405.cpp <out> --like src/loader/runtimeLinker.cpp) and linked with every emulator object but main.cpp.o,
// the private runtimeLinker.cpp.o (mktls0405.py's output, src/loader/runtimeLinker.cpp=<it>) in place of the shared one.
// RFLAGS bit positions: CF 0, PF 2, AF 4, ZF 6, SF 7, DF 10, OF 11 (obliteration 2a53d5c lib/x86-64/src/lib.rs:10-40,
// MIT/Apache-2.0, after the AMD64 APM vol. 2 RFLAGS section).

#include "common/abi.h"
#include "common/logging/log.h"

#include <new>

#include "loader/jit.h"

#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cpuid.h>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <initializer_list>
#include <string>
#include <thread>
#include <vector>

#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>

// The unit's functions (src/loader/runtimeLinker.cpp, mktls0405.py's block); there is no header for them.
namespace Loader {
uint32_t Bc5Tls0405Items();
void     Bc5Tls0405PatchTlsLoads(uint64_t address, uint64_t size, uint64_t handler_vaddr);
void     Bc5Tls0405WriteTlsHandler(uint64_t handler_vaddr, Jit::SafeCall::func_t func);
} // namespace Loader

namespace {

namespace Jit = Loader::Jit;

constexpr int      kWatchdogSeconds = 20;
constexpr uint32_t kKl01            = 1u;
constexpr uint32_t kKl02            = 2u;
constexpr size_t   kPage            = 4096;
constexpr size_t   kCodeAt          = kPage + 0x100;          // the code buffers: in the second page
constexpr uint64_t kTcb             = 0x00007a5a1234c0deull;  // what the test's TLS function returns
constexpr uint64_t kRaxIn           = 0x1111222233334444ull;  // rax and rbx before a run
constexpr uint64_t kRbxIn           = 0x5555666677778888ull;
constexpr uint64_t kCF = 1ull << 0, kPF = 1ull << 2, kAF = 1ull << 4, kZF = 1ull << 6, kSF = 1ull << 7;
constexpr uint64_t kDF = 1ull << 10, kOF = 1ull << 11;
constexpr uint64_t kSix = kCF | kPF | kAF | kZF | kSF | kOF;

bool                     g_kl01 = false;
bool                     g_kl02 = false;
uint64_t                 g_flags_base = 0; // this thread's RFLAGS with the six and DF clear
std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
std::atomic<bool>        g_finished {false};
uint8_t                  g_altstack[64 * 1024];

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[4096];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

std::string Hex(const uint8_t* p, size_t n) {
	std::string s;
	for (size_t i = 0; i < n; i++) {
		char b[16];
		std::snprintf(b, sizeof(b), i == 0 ? "%02x" : " %02x", static_cast<unsigned>(p[i]));
		s += b;
	}
	return s;
}

std::string FlagsText(uint64_t f) {
	return Fmt("CF=%d PF=%d AF=%d ZF=%d SF=%d OF=%d", (f & kCF) != 0 ? 1 : 0, (f & kPF) != 0 ? 1 : 0,
	           (f & kAF) != 0 ? 1 : 0, (f & kZF) != 0 ? 1 : 0, (f & kSF) != 0 ? 1 : 0, (f & kOF) != 0 ? 1 : 0);
}

void Report(const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tls0405: case %d %s: %s (%s)\n", g_cases.load(), name, ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const char* what) {
	std::printf("tls0405: FAIL setup: %s\n", what);
	std::fflush(stdout);
	_exit(2);
}

void Watchdog() {
	const auto start = std::chrono::steady_clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (std::chrono::steady_clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("tls0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %s, %d of %d cases passed "
			            "before it\n",
			            g_case.load(), kWatchdogSeconds, g_kl01 || g_kl02 ? "on" : "off", g_passed.load(), g_cases.load());
			std::fflush(stdout);
			_exit(3);
		}
	}
}

// A fault in generated code (a wrong call target, a 16-bit call, a stub that loses the stack): one line, exit 4. Only
// async-signal-safe calls; it runs on its own stack.
void PutText(char* buf, size_t* n, size_t cap, const char* s) {
	while (*s != '\0' && *n + 1 < cap) {
		buf[(*n)++] = *s++;
	}
}

void OnFault(int sig) {
	char   buf[512];
	size_t n = 0;
	PutText(buf, &n, sizeof(buf), "tls0405: FAIL fault: signal ");
	char digits[12];
	int  d = 0;
	int  v = sig;
	do {
		digits[d++] = static_cast<char>('0' + v % 10);
		v /= 10;
	} while (v > 0 && d < 11);
	while (d > 0 && n + 1 < sizeof(buf)) {
		buf[n++] = digits[--d];
	}
	PutText(buf, &n, sizeof(buf), " in case \"");
	PutText(buf, &n, sizeof(buf), g_case.load());
	PutText(buf, &n, sizeof(buf), "\" (the generated code faulted)\n");
	if (write(STDOUT_FILENO, buf, n) < 0) {
		_exit(5);
	}
	_exit(4);
}

void InstallFaultHandlers() {
	stack_t ss {};
	ss.ss_sp    = g_altstack;
	ss.ss_size  = sizeof(g_altstack);
	ss.ss_flags = 0;
	if (sigaltstack(&ss, nullptr) != 0) {
		SetupFail("sigaltstack");
	}
	struct sigaction sa {};
	sa.sa_handler = OnFault;
	sigemptyset(&sa.sa_mask);
	sa.sa_flags = SA_ONSTACK;
	for (int sig: {SIGSEGV, SIGBUS, SIGILL, SIGTRAP, SIGFPE}) {
		if (sigaction(sig, &sa, nullptr) != 0) {
			SetupFail("sigaction");
		}
	}
}

// The unit's reading of KYTY_BC5_TLS_FIXES (mktls0405.py, Bc5TlsFixesParse), repeated.
uint32_t Parse(const char* e) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    items = 0;
	const char* p     = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		if (n == 4 && std::strncmp(p, "kl01", n) == 0) {
			items |= kKl01;
		} else if (n == 4 && std::strncmp(p, "kl02", n) == 0) {
			items |= kKl02;
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return items != 0 ? items : (kKl01 | kKl02);
}

// The TLS function SafeCall calls (an MS-ABI function, as TlsMainGetAddr).
KYTY_MS_ABI uint8_t* TestTlsAddr() {
	return reinterpret_cast<uint8_t*>(kTcb);
}

uint64_t FuncBits(Jit::SafeCall::func_t f) {
	static_assert(sizeof(f) == sizeof(uint64_t));
	uint64_t v = 0;
	std::memcpy(&v, &f, sizeof(v));
	return v;
}

// RW pages filled with 0xCC (int3), made read+execute before a run.
class Pages {
public:
	explicit Pages(size_t pages): m_size(pages * kPage) {
		void* m = mmap(nullptr, m_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
		if (m == MAP_FAILED) {
			SetupFail("mmap of read-write pages");
		}
		m_p = static_cast<uint8_t*>(m);
		std::memset(m_p, 0xCC, m_size);
	}
	~Pages() { munmap(m_p, m_size); }
	Pages(const Pages&)            = delete;
	Pages& operator=(const Pages&) = delete;

	uint8_t*             At(size_t off) { return m_p + off; }
	[[nodiscard]] uint64_t Addr(size_t off) const { return reinterpret_cast<uint64_t>(m_p + off); }
	[[nodiscard]] std::vector<uint8_t> Copy() const { return {m_p, m_p + m_size}; }
	void                 MakeExecutable() {
		if (mprotect(m_p, m_size, PROT_READ | PROT_EXEC) != 0) {
			SetupFail("mprotect to read+execute");
		}
		__builtin___clear_cache(reinterpret_cast<char*>(m_p), reinterpret_cast<char*>(m_p + m_size));
	}

private:
	uint8_t* m_p    = nullptr;
	size_t   m_size = 0;
};

// RFLAGS of this thread (below the red zone: pushfq writes under rsp).
uint64_t ReadFlags() {
	uint64_t f = 0;
	asm volatile("lea -128(%%rsp), %%rsp\n\t"
	             "pushfq\n\t"
	             "pop %0\n\t"
	             "lea 128(%%rsp), %%rsp"
	             : "=r"(f)
	             :
	             : "memory");
	return f;
}

struct Regs {
	uint64_t rax;
	uint64_t rbx;
	uint64_t flags;
};

// Sets RFLAGS, rax and rbx, calls target, and returns rax, rbx and RFLAGS right after the call. The red zone of this
// function is stepped over with lea (no flag written); every other caller-saved register counts as clobbered.
__attribute__((noinline)) Regs CallAt(uint64_t target, uint64_t flags_in, uint64_t rax_in, uint64_t rbx_in) {
	uint64_t rax       = rax_in;
	uint64_t rbx       = rbx_in;
	uint64_t flags_out = 0;
	asm volatile("lea -128(%%rsp), %%rsp\n\t"
	             "push %[fin]\n\t"
	             "popfq\n\t"
	             "call *%[tgt]\n\t"
	             "pushfq\n\t"
	             "pop %[fout]\n\t"
	             "lea 128(%%rsp), %%rsp"
	             : [fout] "=&r"(flags_out), "+a"(rax), "+b"(rbx)
	             : [fin] "r"(flags_in), [tgt] "r"(target)
	             : "memory", "cc", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11", "xmm0", "xmm1", "xmm2", "xmm3",
	               "xmm4", "xmm5");
	return {rax, rbx, flags_out};
}

// ---- expected bytes ----------------------------------------------------------------------------------------------------
// SafeCall 0x07-0x42, the same today (loader/jit.h:128-156) and with KL01 (KytyPS5 dfec14a jit.h:83-112).
const uint8_t kSafeMid[] = {0x9c, 0x51, 0x52, 0x41, 0x50, 0x41, 0x51, 0x41, 0x52, 0x41, 0x53, 0x53, 0x57, 0x56,
                            0x48, 0x89, 0xe3, 0x48, 0x83, 0xe4, 0xf0, 0x48, 0x83, 0xec, 0x20, 0x48, 0xb9,
                            0x88, 0x77, 0x66, 0x55, 0x44, 0x33, 0x22, 0x11, 0xff, 0xd1, 0x48, 0x89, 0xc1,
                            0x48, 0x89, 0xdc, 0x48, 0x89, 0xc8, 0x5e, 0x5f, 0x5b, 0x41, 0x5b, 0x41, 0x5a,
                            0x41, 0x59, 0x41, 0x58, 0x5a, 0x59, 0x9d};
static_assert(sizeof(kSafeMid) == 0x43 - 0x07);
const uint8_t kSubRsp[]  = {0x48, 0x81, 0xEC, 0x80, 0x00, 0x00, 0x00};       // sub rsp,0x80 (today)
const uint8_t kAddRsp[]  = {0x48, 0x81, 0xC4, 0x80, 0x00, 0x00, 0x00};       // add rsp,0x80 (today)
const uint8_t kLeaDown[] = {0x48, 0x8D, 0x64, 0x24, 0x80, 0x66, 0x90};       // lea rsp,[rsp-0x80]; nop (KL01)
const uint8_t kLeaUp[]   = {0x48, 0x8D, 0xA4, 0x24, 0x80, 0x00, 0x00, 0x00}; // lea rsp,[rsp+0x80] (KL01)

void Append(std::vector<uint8_t>* v, const uint8_t* p, size_t n) {
	v->insert(v->end(), p, p + n);
}

void PutU32(uint8_t* at, uint64_t value) {
	const auto v = static_cast<uint32_t>(value & 0xffffffffu);
	std::memcpy(at, &v, sizeof(v));
}

std::vector<uint8_t> ExpectSafeCall(bool kl01, uint64_t func) {
	std::vector<uint8_t> v;
	Append(&v, kl01 ? kLeaDown : kSubRsp, 7);
	Append(&v, kSafeMid, sizeof(kSafeMid));
	if (kl01) {
		Append(&v, kLeaUp, sizeof(kLeaUp));
	} else {
		Append(&v, kAddRsp, sizeof(kAddRsp));
	}
	v.push_back(0xC3);
	std::memcpy(v.data() + 0x22, &func, sizeof(func));
	v.resize(0x90, 0x00);
	return v;
}

// rel: the call's rel32 (to SafeCall from code[13]); reg: the output register.
std::vector<uint8_t> ExpectTlsRegStub(bool kl01, uint64_t rel, uint8_t reg) {
	std::vector<uint8_t> v;
	Append(&v, kl01 ? kLeaDown : kSubRsp, 7);
	v.push_back(0x50); // push rax
	v.push_back(0xE8); // call
	v.resize(v.size() + 4);
	PutU32(v.data() + 9, rel);
	v.push_back(0x48); // mov <reg>,rax
	v.push_back(0x89);
	v.push_back(static_cast<uint8_t>(0xC0u | (reg & 7u)));
	v.push_back(0x58); // pop rax
	if (kl01) {
		Append(&v, kLeaUp, sizeof(kLeaUp));
	} else {
		Append(&v, kAddRsp, sizeof(kAddRsp));
	}
	v.push_back(0xC3);
	v.resize(32, 0x90);
	return v;
}

// The patched load at site (an offset in v, whose first byte is at address base): KL02's 48 E8 rel32 48 89 C0, or
// today's E8 rel32 48 89 C0 90.
void PutCall9(std::vector<uint8_t>* v, uint64_t base, size_t site, uint64_t target, bool kl02) {
	uint8_t* p = v->data() + site;
	if (kl02) {
		p[0] = 0x48;
		p[1] = 0xE8;
		PutU32(p + 2, target - (base + site + 6));
		p[6] = 0x48;
		p[7] = 0x89;
		p[8] = 0xC0;
	} else {
		p[0] = 0xE8;
		PutU32(p + 1, target - (base + site + 5));
		p[5] = 0x48;
		p[6] = 0x89;
		p[7] = 0xC0;
		p[8] = 0x90;
	}
}

struct Load {
	size_t  at;       // the 0x64 byte, from the start of the code
	size_t  prefixes; // the 0x66 bytes the scan counts before it (at most 3)
	uint8_t reg;      // the output register (0 rax, 3 rbx)
};

// The region as the scan should leave it: KL02 writes at the 0x64 byte and nothing else; today's scan writes at the
// first counted 0x66 and puts a nop in place of each counted 0x66 after its 9 bytes.
std::vector<uint8_t> ExpectScan(std::vector<uint8_t> v, uint64_t base, size_t code_at, uint64_t handler,
                                const std::vector<Load>& loads, bool kl02) {
	for (const Load& l: loads) {
		const uint64_t target = handler + (l.reg == 0 ? 0 : Jit::TlsRegStub::GetOffset(l.reg));
		if (kl02) {
			PutCall9(&v, base, code_at + l.at, target, true);
		} else {
			const size_t site = code_at + l.at - l.prefixes;
			PutCall9(&v, base, site, target, false);
			for (size_t k = 0; k < l.prefixes; k++) {
				v[site + 9 + k] = 0x90;
			}
		}
	}
	return v;
}

// "" when equal, else where they first differ.
std::string FirstDiff(const std::vector<uint8_t>& got, const std::vector<uint8_t>& want, size_t from, size_t to) {
	if (got.size() != want.size()) {
		return Fmt("sizes %zu and %zu", got.size(), want.size());
	}
	for (size_t i = from; i < to && i < got.size(); i++) {
		if (got[i] != want[i]) {
			return Fmt("first difference at offset 0x%zx: 0x%02x, expected 0x%02x", i, static_cast<unsigned>(got[i]),
			           static_cast<unsigned>(want[i]));
		}
	}
	return "";
}

// ---- the cases ---------------------------------------------------------------------------------------------------------

void CaseSwitch(uint32_t items) {
	g_case               = "switch";
	const uint32_t unit = Loader::Bc5Tls0405Items();
	Report("the unit reads KYTY_BC5_TLS_FIXES as this test does", unit == items,
	       Fmt("unit: kl01 %s, kl02 %s; test: kl01 %s, kl02 %s", (unit & kKl01) != 0 ? "on" : "off",
	           (unit & kKl02) != 0 ? "on" : "off", (items & kKl01) != 0 ? "on" : "off",
	           (items & kKl02) != 0 ? "on" : "off"));
}

void CaseTodayIsJitH() {
	g_case = "today's sequences";
	const Jit::SafeCall    sc {};
	const Jit::TlsRegStub  st {};
	const Jit::Call9       c9 {};
	const auto             want_sc = ExpectSafeCall(false, 0x1122334455667788ull);
	const auto             want_st = ExpectTlsRegStub(false, 0, 0);
	std::vector<uint8_t>   want_c9(9, 0x00);
	PutCall9(&want_c9, 0, 0, 5, false); // rel32 0
	const bool sc_ok = sizeof(sc.code) == want_sc.size() && std::memcmp(sc.code, want_sc.data(), want_sc.size()) == 0;
	const bool st_ok = sizeof(st.code) == want_st.size() && std::memcmp(st.code, want_st.data(), want_st.size()) == 0;
	const bool c9_ok = sizeof(c9.code) == want_c9.size() && std::memcmp(c9.code, want_c9.data(), want_c9.size()) == 0;
	Report("this test's today's bytes are loader/jit.h's", sc_ok && st_ok && c9_ok,
	       Fmt("SafeCall %s, TlsRegStub %s, Call9 %s", sc_ok ? "same" : "DIFFERENT", st_ok ? "same" : "DIFFERENT",
	           c9_ok ? "same" : "DIFFERENT"));
}

// (a) and (b): one page with the handler's code.
void CasesHandler() {
	g_case = "the handler's bytes";
	Pages page(1);
	Loader::Bc5Tls0405WriteTlsHandler(page.Addr(0), TestTlsAddr);
	const std::vector<uint8_t> got = page.Copy();

	std::vector<uint8_t> want(kPage, 0xCC);
	const auto           sc = ExpectSafeCall(g_kl01, FuncBits(TestTlsAddr));
	std::memcpy(want.data(), sc.data(), sc.size());
	std::string stubs_where;
	for (uint8_t reg = 1; reg < 8; reg++) {
		if (reg == 4) {
			continue;
		}
		const uint64_t off = Jit::TlsRegStub::GetOffset(reg);
		const auto     st  = ExpectTlsRegStub(g_kl01, page.Addr(0) - (page.Addr(off) + 13), reg);
		std::memcpy(want.data() + off, st.data(), st.size());
		stubs_where += Fmt("%s0x%" PRIx64, stubs_where.empty() ? "" : " ", off);
	}
	const char* kind = g_kl01 ? "KytyPS5's lea form" : "today's sub/add form";

	const std::string d3 = FirstDiff(got, want, 0, 0x90);
	Report("SafeCall's 0x90 bytes", d3.empty(),
	       d3.empty() ? Fmt("%s; 0x00-0x07: %s; 0x43-0x4c: %s", kind, Hex(got.data(), 7).c_str(),
	                        Hex(got.data() + 0x43, 9).c_str())
	                  : d3);

	std::string d4;
	for (uint8_t reg = 1; reg < 8 && d4.empty(); reg++) {
		if (reg != 4) {
			const uint64_t off = Jit::TlsRegStub::GetOffset(reg);
			d4                 = FirstDiff(got, want, off, off + 32);
		}
	}
	Report("the six TlsRegStubs", d4.empty(),
	       d4.empty() ? Fmt("%s, at %s; rbx's: %s", kind, stubs_where.c_str(),
	                        Hex(got.data() + Jit::TlsRegStub::GetOffset(3), 32).c_str())
	                  : d4);

	const std::string d5 = FirstDiff(got, want, 0, kPage);
	Report("no other byte of the handler's page changed", d5.empty(), d5.empty() ? "the rest is 0xCC" : d5);

	page.MakeExecutable();
	struct Run {
		const char* name;
		bool        rbx;
		uint64_t    pattern;
	};
	const Run runs[] = {{"rax through SafeCall, six flags set", false, kSix},
	                    {"rax through SafeCall, six flags clear", false, 0},
	                    {"rbx through its TlsRegStub, six flags set", true, kSix},
	                    {"rbx through its TlsRegStub, six flags clear", true, 0}};
	for (const Run& r: runs) {
		g_case                = r.name;
		const uint64_t target = r.rbx ? page.Addr(Jit::TlsRegStub::GetOffset(3)) : page.Addr(0);
		const uint64_t in     = g_flags_base | r.pattern;
		const Regs     out    = CallAt(target, in, kRaxIn, kRbxIn);
		const bool     value  = r.rbx ? (out.rbx == kTcb && out.rax == kRaxIn) : (out.rax == kTcb && out.rbx == kRbxIn);
		const bool     kept   = ((out.flags ^ in) & kSix) == 0;
		const bool     four_clear = (out.flags & (kCF | kZF | kSF | kOF)) == 0;
		std::string    info =
		    Fmt("rax=0x%016" PRIx64 " rbx=0x%016" PRIx64 " (%s); flags in: %s; out: %s", out.rax, out.rbx,
		        value ? "the handler's value, the other register kept" : "WRONG", FlagsText(in).c_str(),
		        FlagsText(out.flags).c_str());
		if (g_kl01) {
			info += kept ? "; kept (kl01)" : "; CHANGED (kl01 on: they must survive)";
		} else {
			info += Fmt("; today's stubs, measured: the six %s; CF ZF SF OF all clear, as `add rsp,0x80` leaves them: %s",
			            kept ? "kept" : "changed", four_clear ? "yes" : "no");
		}
		Report(r.name, value && (!g_kl01 || kept), info);
	}
}

struct ScanCase {
	const char*          name;
	std::vector<uint8_t> code;       // written at kCodeAt
	size_t               size;       // the segment given to the scan (may end before the code does)
	std::vector<Load>    loads;      // the loads the scan must patch
	bool                 run_rax;    // after the run, rax holds the handler's value
	bool                 run_rbx;    // after the run, rbx does
	bool                 today_runs; // today's bytes may run (false: today's patch breaks the code)
	const char*          today_note; // what today's bytes do, for the line with the switch off
};

void RunScanCase(const ScanCase& c) {
	g_case = c.name;
	Pages region(2);
	Loader::Bc5Tls0405WriteTlsHandler(region.Addr(0), TestTlsAddr);
	std::memcpy(region.At(kCodeAt), c.code.data(), c.code.size());
	const std::vector<uint8_t> before = region.Copy();
	const std::vector<uint8_t> want   = ExpectScan(before, region.Addr(0), kCodeAt, region.Addr(0), c.loads, g_kl02);
	Loader::Bc5Tls0405PatchTlsLoads(region.Addr(kCodeAt), c.size, region.Addr(0));
	const std::vector<uint8_t> got = region.Copy();

	const std::string d       = FirstDiff(got, want, 0, got.size());
	size_t            changed = 0;
	for (size_t i = 0; i < got.size(); i++) {
		changed += got[i] != before[i] ? 1 : 0;
	}
	std::string info = Fmt("%s; %zu byte(s) changed; now: %s", d.empty() ? (g_kl02 ? "KytyPS5's bytes" : "today's bytes")
	                                                                     : d.c_str(),
	                       changed, Hex(got.data() + kCodeAt, c.code.size()).c_str());
	bool run_ok = true;
	if (d.empty() && (c.run_rax || c.run_rbx)) {
		if (g_kl02 || c.today_runs) {
			region.MakeExecutable();
			const Regs out = CallAt(region.Addr(kCodeAt), g_flags_base, kRaxIn, kRbxIn);
			run_ok         = out.rax == (c.run_rax ? kTcb : kRaxIn) && out.rbx == (c.run_rbx ? kTcb : kRbxIn);
			info += Fmt("; ran: rax=0x%016" PRIx64 " rbx=0x%016" PRIx64 " (%s)", out.rax, out.rbx,
			            run_ok ? "as expected" : "WRONG");
		} else {
			info += "; not run";
		}
	}
	if (!g_kl02 && c.today_note != nullptr) {
		info += Fmt("; today: %s (recorded)", c.today_note);
	}
	Report(c.name, d.empty() && run_ok, info);
}

void CasesScan() {
	const std::vector<uint8_t> load_rax = {0x64, 0x48, 0x8B, 0x04, 0x25, 0x00, 0x00, 0x00, 0x00}; // mov rax,fs:[0]
	const std::vector<uint8_t> load_rbx = {0x64, 0x48, 0x8B, 0x1C, 0x25, 0x00, 0x00, 0x00, 0x00}; // mov rbx,fs:[0]
	auto cat = [](std::initializer_list<std::vector<uint8_t>> parts) {
		std::vector<uint8_t> v;
		for (const auto& p: parts) {
			v.insert(v.end(), p.begin(), p.end());
		}
		return v;
	};
	const std::vector<uint8_t> ret = {0xC3};
	const std::vector<uint8_t> no_match =
	    cat({{0x64, 0x48, 0x8B, 0x04, 0x25, 0x28, 0x00, 0x00, 0x00},   // mov rax,fs:[0x28]
	         {0x65, 0x48, 0x8B, 0x04, 0x25, 0x00, 0x00, 0x00, 0x00},   // mov rax,gs:[0]
	         {0x64, 0x48, 0x8B, 0x44, 0x24, 0x08},                     // mov rax,fs:[rsp+8]
	         {0x64, 0x8B, 0x04, 0x25, 0x00, 0x00, 0x00, 0x00},         // mov eax,fs:[0]
	         {0x64, 0x4C, 0x8B, 0x04, 0x25, 0x00, 0x00, 0x00, 0x00}}); // mov r8,fs:[0]

	const ScanCase cases[] = {
	    {"3C 66 | mov rax,fs:[0] | C3 (a 0x66 that ends cmp al,0x66)", cat({{0x3C, 0x66}, load_rax, ret}), 12,
	     {{2, 1, 0}}, true, false, false, "the call is written at byte 1, over cmp's operand 0x66"},
	    {"66 66 66 | mov rbx,fs:[0] | C3 (three 0x66)", cat({{0x66, 0x66, 0x66}, load_rbx, ret}), 13, {{3, 3, 3}},
	     false, true, true, nullptr},
	    {"66 | mov rax,fs:[0] | C3 (one 0x66)", cat({{0x66}, load_rax, ret}), 11, {{1, 1, 0}}, true, false, true,
	     nullptr},
	    {"mov rax,fs:[0] | C3 (no 0x66)", cat({load_rax, ret}), 10, {{0, 0, 0}}, true, false, true, nullptr},
	    {"66 66 66 66 | mov rax,fs:[0] | C3 (four 0x66)", cat({{0x66, 0x66, 0x66, 0x66}, load_rax, ret}), 14,
	     {{4, 3, 0}}, true, false, false,
	     "one 0x66 stays before a plain E8 call (66 E8: a 16-bit call on AMD)"},
	    {"mov rax,fs:[0] | mov rbx,fs:[0] | C3 (two in a row)", cat({load_rax, load_rbx, ret}), 19,
	     {{0, 0, 0}, {9, 0, 3}}, true, true, true, nullptr},
	    {"a 9-byte segment that is the load (C3 outside it)", cat({load_rax, ret}), 9, {{0, 0, 0}}, true, false, true,
	     nullptr},
	    {"an 8-byte segment with a load's first 8 bytes (the 9th outside)", cat({load_rax, ret}), 8, {}, false, false,
	     true, "start + 8 - 9 lies before the start; its loop does not run, nothing written"},
	    {"a 5-byte segment with a load's first 5 bytes", cat({load_rax, ret}), 5, {}, false, false, true,
	     "start + 5 - 9 lies before the start; its loop does not run, nothing written"},
	    {"no match: fs:[0x28], gs:[0], fs:[rsp+8], eax,fs:[0], r8,fs:[0]", cat({no_match, ret}), no_match.size(), {},
	     false, false, true, nullptr},
	};
	for (const ScanCase& c: cases) {
		RunScanCase(c);
	}
}

} // namespace

int main() {
	const char*    e     = std::getenv("KYTY_BC5_TLS_FIXES");
	const uint32_t items = Parse(e);
	g_kl01               = (items & kKl01) != 0;
	g_kl02               = (items & kKl02) != 0;
	Log::Bc5SetLogging(false); // the scan's LOGF lines stay off stdout
	InstallFaultHandlers();
	std::thread(Watchdog).detach();

	unsigned a = 0, b = 0, c = 0, d = 0;
	char     vendor[13] = {};
	unsigned family = 0, model = 0;
	if (__get_cpuid(0, &a, &b, &c, &d) != 0) {
		std::memcpy(vendor, &b, 4);
		std::memcpy(vendor + 4, &d, 4);
		std::memcpy(vendor + 8, &c, 4);
	}
	if (__get_cpuid(1, &a, &b, &c, &d) != 0) {
		family = ((a >> 8u) & 0xfu) + (((a >> 8u) & 0xfu) == 0xfu ? ((a >> 20u) & 0xffu) : 0u);
		model  = ((a >> 4u) & 0xfu) | ((a >> 12u) & 0xf0u);
	}
	std::printf("tls0405: KYTY_BC5_TLS_FIXES=%s, so %s (kl01 %s, kl02 %s); CPU %s family 0x%x model 0x%x\n",
	            e != nullptr ? e : "(unset)", items != 0 ? "on" : "off", g_kl01 ? "on" : "off", g_kl02 ? "on" : "off",
	            vendor, family, model);
	std::fflush(stdout);
	g_flags_base = ReadFlags() & ~(kSix | kDF);

	CaseSwitch(items);
	CaseTodayIsJitH();
	CasesHandler();
	CasesScan();

	g_finished  = true;
	const int n = g_cases.load();
	const int p = g_passed.load();
	if (p != n) {
		std::printf("tls0405: %s %d of %d passed; FAIL\n", items != 0 ? "on" : "off", p, n);
		std::fflush(stdout);
		_exit(1);
	}
	std::printf("tls0405: %s %d of %d; end\n", items != 0 ? "on" : "off", p, n);
	std::fflush(stdout);
	_exit(0);
}
