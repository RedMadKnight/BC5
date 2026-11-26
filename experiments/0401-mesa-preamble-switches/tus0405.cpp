// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0405 (series e7 of experiment 0401), tag tus: the CPU test of mktus0405.py's port in src/libs/libUsbd.cpp
// (the Usbd table, exp 0405 decision 4), behind KYTY_BC5_LOAD_USBD. It registers the table into its own SymbolDatabase by
// calling its LIB_DEFINE (as libs.cpp does when the switch is on; with the switch off the init still runs here, to call
// today's stubs), takes each function by NID with the exact key a title's import of libSceUsbd looks up, and calls it as a
// title would.
//   on:  61 NIDs registered, the 4 held ones absent. With KYTY_BC5_USBD_ALLOW unset (the test unsets it): AnyPS5
//        4f41f4c37's answers on a host with no USB access (see tus0405-notes.md): an empty device list, transfer
//        allocation, filling, control setup and iso packets, cancel and submit, the argument checks of every device and
//        handle call (a device or handle never handed out has no answer upstream, so today's 0 runs and nothing is
//        written), the event lock, handler and waiters, one thread and two; and libusb is never loaded (the stand-in
//        loader hook counts no symbol lookup). Then three child runs of this binary, each with its own allow-list:
//          bad   a malformed list: refused whole, libusb never loaded, no device;
//          sony  only DualShock 4 / DualSense ids: all dropped, libusb never loaded, no device;
//          fake  a list naming a vendor-class device, a HID one, an audio one, one whose configuration cannot be read,
//                one with a HID device class, plus Sony ids: the port runs over a fake libusb table injected through the
//                hook (no dlopen, no host USB): only the vendor-class device is listed and opened; the transport calls
//                (descriptors, configuration, interfaces, halt, control, bulk, interrupt, submit, cancel, completion and
//                the title's callback through event handling, iso packets, close, open by id, exit) are checked, and the
//                refused devices are never opened, claimed or detached.
//   off: all 65 registered; today's answer, 0 from every call, with every output left as it was and no wait; a child run
//        with an allow-list set shows the switch off ignores it (libusb never loaded).
// No game, GPU, window, sound device, network or host USB (nothing here loads libusb or touches a USB device); no
// subsystem is started. Prints one line per case and finally "tus0405: on|off N of N; end"; exit 0 only then (a child
// prints "tus0405: [child <name>] N of N; end" and exits 0). A watchdog ends a hang after 120 s with a FAIL line. An
// optional argument "on"/"off" must match the switch. Run it in a fresh directory: it writes ./tus0405-dump (the symbol
// dump) and removes it. The last case leaves, with the switch on, one thread inside sceUsbdHandleEvents (it waits for a
// transfer that never completes, as upstream); the test ends with _Exit.
// Build: build0401.py ... src/libs/libUsbd.cpp=<out>/src/libs/libUsbd.cpp --gate tus0405.cpp <bin> --like src/libs/libUsbd.cpp

#include "common/abi.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <vector>
#ifndef _WIN32
#include <sys/wait.h>
#endif

namespace Libs {
namespace LibUsbd {
LIB_DEFINE(InitUsbd_1);
extern void* (*bc5_usb_symbols_for_test)(const char* name); // the port's loader hook (libUsbd.cpp)
} // namespace LibUsbd
} // namespace Libs

namespace tus0405 {

constexpr int kWatchdogSeconds = 120;

std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<const char*> g_case {"start"};
char                     g_case_buf[256];
bool                     g_on = false;
std::string              g_child;  // the child run's name, or empty in the parent
std::string              g_prefix; // "" or "[child <name>] "

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[4096];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

void SetCase(const std::string& name) {
	std::snprintf(g_case_buf, sizeof(g_case_buf), "%s", name.c_str());
	g_case = g_case_buf;
}

void Report(const std::string& name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("tus0405: %scase %d %s%s: %s (%s)\n", g_prefix.c_str(), g_cases.load(), g_on ? "" : "off: ", name.c_str(),
	            ok ? "ok" : "FAIL", info.c_str());
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("tus0405: %sFAIL setup: %s\n", g_prefix.c_str(), what.c_str());
	std::fflush(stdout);
	std::_Exit(2);
}

void Watchdog() {
	std::this_thread::sleep_for(std::chrono::seconds(kWatchdogSeconds));
	std::printf("tus0405: %sFAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
	            g_prefix.c_str(), g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
	std::fflush(stdout);
	std::_Exit(3);
}

bool SwitchOn(const char* name) {
	const char* e = std::getenv(name);
	return e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
}

// ---- the table: every NID InitUsbd_1 registers, in its order, with today's symbol name (e7 sweep, sweep-nids.tsv) -------
struct Entry {
	const char* nid;
	const char* name;
};
constexpr Entry kTable[] = {
    {"0ktE1PhzGFU", "sceUsbdAllocTransfer"},
    {"BKMEGvfCPyU", "sceUsbdAttachKernelDriver"},
    {"fotb7DzeHYw", "sceUsbdBulkTransfer"},
    {"-KNh1VFIzlM", "sceUsbdCancelTransfer"},
    {"MlW6deWfPp0", "sceUsbdCheckConnected"},
    {"AE+mHBHneyk", "sceUsbdClaimInterface"},
    {"3tPPMo4QRdY", "sceUsbdClearHalt"},
    {"HarYYlaFGJY", "sceUsbdClose"},
    {"RRKFcKQ1Ka4", "sceUsbdControlTransfer"},
    {"XUWtxI31YEY", "sceUsbdControlTransferGetData"},
    {"SEdQo8CFmus", "sceUsbdControlTransferGetSetup"},
    {"Y5go+ha6eDs", "sceUsbdDetachKernelDriver"},
    {"Vw8Hg1CN028", "sceUsbdEventHandlerActive"},
    {"e7gp1xhu6RI", "sceUsbdEventHandlingOk"},
    {"Fq6+0Fm55xU", "sceUsbdExit"},
    {"oHCade-0qQ0", "sceUsbdFillBulkTransfer"},
    {"8KrqbaaPkE0", "sceUsbdFillControlSetup"},
    {"7VGfMerK6m0", "sceUsbdFillControlTransfer"},
    {"t3J5pXxhJlI", "sceUsbdFillInterruptTransfer"},
    {"xqmkjHCEOSY", "sceUsbdFillIsoTransfer"},
    {"Hvd3S--n25w", "sceUsbdFreeConfigDescriptor"},
    {"EQ6SCLMqzkM", "sceUsbdFreeDeviceList"},
    {"-sgi7EeLSO8", "sceUsbdFreeTransfer"},
    {"S1o1C6yOt5g", "sceUsbdGetActiveConfigDescriptor"},
    {"t7WE9mb1TB8", "sceUsbdGetBusNumber"},
    {"Dkm5qe8j3XE", "sceUsbdGetConfigDescriptor"},
    {"GQsAVJuy8gM", "sceUsbdGetConfigDescriptorByValue"},
    {"L7FoTZp3bZs", "sceUsbdGetConfiguration"},
    {"-JBoEtvTxvA", "sceUsbdGetDescriptor"},
    {"rsl9KQ-agyA", "sceUsbdGetDevice"},
    {"GjlCrU4GcIY", "sceUsbdGetDeviceAddress"},
    {"bhomgbiQgeo", "sceUsbdGetDeviceDescriptor"},
    {"8qB9Ar4P5nc", "sceUsbdGetDeviceList"},
    {"e1UWb8cWPJM", "sceUsbdGetDeviceSpeed"},
    {"vokkJ0aDf54", "sceUsbdGetIsoPacketBuffer"},
    {"nuIRlpbxauM", "sceUsbdGetMaxIsoPacketSize"},
    {"YJ0cMAlLuxQ", "sceUsbdGetMaxPacketSize"},
    {"g2oYm1DitDg", "sceUsbdGetStringDescriptor"},
    {"t4gUfGsjk+g", "sceUsbdGetStringDescriptorAscii"},
    {"EkqGLxWC-S0", "sceUsbdHandleEvents"},
    {"rt-WeUGibfg", "sceUsbdHandleEventsLocked"},
    {"+wU6CGuZcWk", "sceUsbdHandleEventsTimeout"},
    {"TOhg7P6kTH4", "sceUsbdInit"},
    {"rxi1nCOKWc8", "sceUsbdInterruptTransfer"},
    {"RLf56F-WjKQ", "sceUsbdKernelDriverActive"},
    {"u9yKks02-rA", "sceUsbdLockEvents"},
    {"AeGaY8JrAV4", "sceUsbdLockEventWaiters"},
    {"VJ6oMq-Di2U", "sceUsbdOpen"},
    {"vrQXYRo1Gwk", "sceUsbdOpenDeviceWithVidPid"},
    {"U1t1SoJvV-A", "sceUsbdRefDevice"},
    {"REfUTmTchMw", "sceUsbdReleaseInterface"},
    {"hvMn0QJXj5g", "sceUsbdResetDevice"},
    {"FhU9oYrbXoA", "sceUsbdSetConfiguration"},
    {"DVCQW9o+ki0", "sceUsbdSetInterfaceAltSetting"},
    {"dJxro8Nzcjk", "sceUsbdSetIsoPacketLengths"},
    {"L0EHgZZNVas", "sceUsbdSubmitTransfer"},
    {"TcXVGc-LPbQ", "sceUsbdTryLockEvents"},
    {"RA2D9rFH-Uw", "sceUsbdUnlockEvents"},
    {"1DkGvUQYFKI", "sceUsbdUnlockEventWaiters"},
    {"OULgIo1zAsA", "sceUsbdUnrefDevice"},
    {"ys2e9VRBPrY", "sceUsbdWaitForEvent"},
    {"ZfbvM+OP-1A", "Func_65F6EF33E38FFF50"},
    {"l-BWutkKrec", "Func_97F056BAD90AADE7"},
    {"xVEEozs1smQ", "Func_C55104A33B35B264"},
    {"1WtDBgcgseA", "Func_D56B43060720B1E0"},
};
constexpr int kTableSize = static_cast<int>(sizeof(kTable) / sizeof(kTable[0]));
static_assert(kTableSize == 65);

// Held: not registered when on (AnyPS5 does not have them).
constexpr const char* kHeld[] = {"Func_65F6EF33E38FFF50", "Func_97F056BAD90AADE7", "Func_C55104A33B35B264",
                                 "Func_D56B43060720B1E0"};
constexpr int kHeldCount = 4;

bool IsHeld(const char* name) {
	for (const char* h: kHeld) {
		if (std::strcmp(h, name) == 0) {
			return true;
		}
	}
	return false;
}

// ---- lookups: the exact key a title's import of libSceUsbd looks up ---------------------------------------------------
Loader::SymbolDatabase g_db;

Loader::SymbolResolve Key(const char* nid) {
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = "libSceUsbd";
	r.library_version      = 1;
	r.module               = "libSceUsbd";
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

const char* NidOf(const char* name) {
	for (const auto& e: kTable) {
		if (std::strcmp(name, e.name) == 0) {
			return e.nid;
		}
	}
	SetupFail(std::string("no NID for ") + name);
}

template <typename F>
F Fn(const char* name) {
	const char* nid = NidOf(name);
	const auto* r   = g_db.Find(Key(nid));
	if (r == nullptr || r->vaddr == 0) {
		SetupFail(Fmt("%s (%s) is not registered", name, nid));
	}
	return reinterpret_cast<F>(r->vaddr);
}

// ---- the calls, as a title makes them (the edited stubs' parameter lists; today's stubs ignore every argument) ---------
struct Tv {
	int64_t seconds;
	int64_t microseconds;
};
using I0     = int (KYTY_SYSV_ABI*)();
using IP     = int (KYTY_SYSV_ABI*)(void*);
using IPI    = int (KYTY_SYSV_ABI*)(void*, int32_t);
using IPII   = int (KYTY_SYSV_ABI*)(void*, int32_t, int32_t);
using IPP    = int (KYTY_SYSV_ABI*)(void*, void**);
using IPU8P  = int (KYTY_SYSV_ABI*)(void*, uint8_t, void**);
using IPPI   = int (KYTY_SYSV_ABI*)(void*, int32_t*);
using IPU8   = int (KYTY_SYSV_ABI*)(void*, uint8_t);
using IPPV   = int (KYTY_SYSV_ABI*)(void*, void*);
using ITv    = int (KYTY_SYSV_ABI*)(const Tv*);
using IPU32  = int (KYTY_SYSV_ABI*)(void*, uint32_t);
using QI     = uint64_t (KYTY_SYSV_ABI*)(int32_t);
using QP     = uint64_t (KYTY_SYSV_ABI*)(void*);
using QPU32  = uint64_t (KYTY_SYSV_ABI*)(void*, uint32_t);
using QU16   = uint64_t (KYTY_SYSV_ABI*)(uint16_t, uint16_t);
using LList  = int64_t (KYTY_SYSV_ABI*)(void***);
using IFree  = int (KYTY_SYSV_ABI*)(void**, int32_t);
using ISync  = int (KYTY_SYSV_ABI*)(void*, uint8_t, uint8_t*, int32_t, int32_t*, uint32_t);
using ICtl   = int (KYTY_SYSV_ABI*)(void*, uint8_t, uint8_t, uint16_t, uint16_t, uint8_t*, uint16_t, uint32_t);
using IDesc  = int (KYTY_SYSV_ABI*)(void*, uint8_t, uint8_t, uint8_t*, int32_t);
using IStr   = int (KYTY_SYSV_ABI*)(void*, uint8_t, uint16_t, uint8_t*, int32_t);
using IStrA  = int (KYTY_SYSV_ABI*)(void*, uint8_t, uint8_t*, int32_t);
using IFill  = int (KYTY_SYSV_ABI*)(void*, void*, uint8_t, uint8_t*, int32_t, void*, void*, uint32_t);
using IFillI = int (KYTY_SYSV_ABI*)(void*, void*, uint8_t, uint8_t*, int32_t, int32_t, void*, void*, uint32_t);
using ISetup = int (KYTY_SYSV_ABI*)(uint8_t*, uint8_t, uint8_t, uint16_t, uint16_t, uint16_t);
using ICtlX  = int (KYTY_SYSV_ABI*)(void*, void*, uint8_t*, void*, void*, uint32_t);

// ---- answers ----------------------------------------------------------------------------------------------------------
constexpr int kInvArg   = static_cast<int>(0x80240002u);
constexpr int kNoDevice = static_cast<int>(0x80240004u);
constexpr int kNotFound = static_cast<int>(0x80240005u);
constexpr int kTimeout  = static_cast<int>(0x80240007u);

int64_t On(int64_t v) { // the answer with the switch on; off, today's stubs answer 0
	return g_on ? v : 0;
}

struct Checks {
	int         n   = 0;
	int         bad = 0;
	std::string info;
	void Eq(const char* what, int64_t got, int64_t want) {
		n++;
		if (got != want) {
			bad++;
			info += Fmt(" [%s: 0x%llx, want 0x%llx]", what, static_cast<unsigned long long>(got),
			            static_cast<unsigned long long>(want));
		}
	}
	void True(const char* what, bool ok) {
		n++;
		if (!ok) {
			bad++;
			info += Fmt(" [%s]", what);
		}
	}
};

void Done(const std::string& name, const Checks& c) {
	Report(name, c.bad == 0, c.bad == 0 ? Fmt("%d checks", c.n) : Fmt("%d of %d checks failed:%s", c.bad, c.n, c.info.c_str()));
}

// ---- guest memory: every output a call gets is filled with 0x5A first ------------------------------------------------
constexpr uint8_t kFill = 0x5A;
alignas(16) uint8_t g_fake_device[64]; // a non-null device or handle no call ever handed out
alignas(16) uint8_t g_out[256];        // outputs: must stay 0x5A unless the port writes them
alignas(16) uint8_t g_xfer[128];       // a transfer the title owns: 60 bytes, then up to 4 packet records (12 each)
alignas(16) uint8_t g_setup[300];      // a control buffer: the setup packet, then data
alignas(16) uint8_t g_data[64];

void* Fake() {
	return g_fake_device;
}

void FillAll() {
	std::memset(g_fake_device, kFill, sizeof(g_fake_device));
	std::memset(g_out, kFill, sizeof(g_out));
	std::memset(g_xfer, kFill, sizeof(g_xfer));
	std::memset(g_setup, kFill, sizeof(g_setup));
	std::memset(g_data, kFill, sizeof(g_data));
}

bool Untouched(const uint8_t* p, size_t n) {
	for (size_t i = 0; i < n; i++) {
		if (p[i] != kFill) {
			return false;
		}
	}
	return true;
}

bool AllUntouched() {
	return Untouched(g_fake_device, sizeof(g_fake_device)) && Untouched(g_out, sizeof(g_out)) &&
	       Untouched(g_xfer, sizeof(g_xfer)) && Untouched(g_setup, sizeof(g_setup)) && Untouched(g_data, sizeof(g_data));
}

template <typename T>
T At(const void* base, size_t offset) {
	T v {};
	std::memcpy(&v, static_cast<const uint8_t*>(base) + offset, sizeof(v));
	return v;
}

template <typename T>
void Put(void* base, size_t offset, T v) {
	std::memcpy(static_cast<uint8_t*>(base) + offset, &v, sizeof(v));
}

uint64_t U(const void* p) {
	return reinterpret_cast<uint64_t>(p);
}

int64_t Ms(std::chrono::steady_clock::time_point since) {
	return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - since).count();
}

// ---- cases ------------------------------------------------------------------------------------------------------------
void CaseRegistration() {
	SetCase("registration");
	int         found  = 0;
	int         absent = 0;
	std::string bad;
	for (const auto& e: kTable) {
		const auto* r  = g_db.Find(Key(e.nid));
		const auto* rn = g_db.FindByNid(e.nid, Loader::SymbolType::Func);
		if (g_on && IsHeld(e.name)) {
			if (r == nullptr && rn == nullptr) {
				absent++;
			} else {
				bad += Fmt(" %s(registered)", e.nid);
			}
		} else if (r != nullptr && r->vaddr != 0 && rn != nullptr && rn->vaddr == r->vaddr) {
			found++;
		} else {
			bad += Fmt(" %s(missing)", e.nid);
		}
	}
	std::error_code ec;
	std::filesystem::remove_all("tus0405-dump", ec);
	g_db.DbgDump("tus0405-dump/", "symbols.txt");
	int           lines = 0;
	std::ifstream dump("tus0405-dump/symbols.txt");
	for (std::string line; std::getline(dump, line);) {
		if (!line.empty() && line != "\r") {
			lines++;
		}
	}
	dump.close();
	std::filesystem::remove_all("tus0405-dump", ec);
	const int want_found  = g_on ? kTableSize - kHeldCount : kTableSize;
	const int want_absent = g_on ? kHeldCount : 0;
	Report(g_on ? "registration: 61 NIDs by the exact key and by FindByNid, the 4 held absent, no other record"
	            : "registration: all 65 NIDs by the exact key and by FindByNid, no other record",
	       found == want_found && absent == want_absent && lines == want_found && bad.empty(),
	       Fmt("%d found, %d absent, %d records%s", found, absent, lines, bad.c_str()));
}

// With no allow-list (no host context), AnyPS5's answer of these 12 is today's 0 with nothing written, on and off; a
// non-null device or handle (none can exist) has no answer upstream, so today's 0 runs too.
void CaseMatch() {
	SetCase("no allow-list");
	FillAll();
	Checks c;
	c.Eq("Init", Fn<I0>("sceUsbdInit")(), 0);
	c.Eq("Init again", Fn<I0>("sceUsbdInit")(), 0);
	c.Eq("Exit", Fn<I0>("sceUsbdExit")(), 0);
	c.Eq("Exit", Fn<I0>("sceUsbdExit")(), 0);
	c.Eq("Exit with none left", Fn<I0>("sceUsbdExit")(), 0);
	c.Eq("FreeDeviceList(null)", Fn<IFree>("sceUsbdFreeDeviceList")(nullptr, 1), 0);
	c.Eq("FreeDeviceList(other)", Fn<IFree>("sceUsbdFreeDeviceList")(reinterpret_cast<void**>(g_out), 1), 0);
	c.Eq("FreeConfigDescriptor(null)", Fn<IP>("sceUsbdFreeConfigDescriptor")(nullptr), 0);
	c.Eq("FreeConfigDescriptor(other)", Fn<IP>("sceUsbdFreeConfigDescriptor")(g_out), 0);
	c.Eq("Close(null)", Fn<IP>("sceUsbdClose")(nullptr), 0);
	c.Eq("Close(other)", Fn<IP>("sceUsbdClose")(Fake()), 0);
	c.Eq("RefDevice(null)", static_cast<int64_t>(Fn<QP>("sceUsbdRefDevice")(nullptr)), 0);
	c.Eq("RefDevice(other)", static_cast<int64_t>(Fn<QP>("sceUsbdRefDevice")(Fake())), 0);
	c.Eq("UnrefDevice(null)", Fn<IP>("sceUsbdUnrefDevice")(nullptr), 0);
	c.Eq("UnrefDevice(other)", Fn<IP>("sceUsbdUnrefDevice")(Fake()), 0);
	c.Eq("GetDevice(null)", static_cast<int64_t>(Fn<QP>("sceUsbdGetDevice")(nullptr)), 0);
	c.Eq("GetDevice(other)", static_cast<int64_t>(Fn<QP>("sceUsbdGetDevice")(Fake())), 0);
	c.Eq("GetBusNumber(null)", Fn<IP>("sceUsbdGetBusNumber")(nullptr) & 0xFF, 0);
	c.Eq("GetBusNumber(other)", Fn<IP>("sceUsbdGetBusNumber")(Fake()) & 0xFF, 0);
	c.Eq("GetDeviceAddress(null)", Fn<IP>("sceUsbdGetDeviceAddress")(nullptr) & 0xFF, 0);
	c.Eq("GetDeviceAddress(other)", Fn<IP>("sceUsbdGetDeviceAddress")(Fake()) & 0xFF, 0);
	c.Eq("GetDeviceSpeed(null): unknown", Fn<IP>("sceUsbdGetDeviceSpeed")(nullptr), 0);
	c.Eq("GetDeviceSpeed(other)", Fn<IP>("sceUsbdGetDeviceSpeed")(Fake()), 0);
	c.Eq("OpenDeviceWithVidPid: no host device", static_cast<int64_t>(Fn<QU16>("sceUsbdOpenDeviceWithVidPid")(0x054C, 0x0CE6)),
	     0);
	c.True("nothing written", AllUntouched());
	Done("no allow-list: Init, Exit, FreeDeviceList, FreeConfigDescriptor, Close, Ref/UnrefDevice, GetDevice, GetBusNumber, "
	     "GetDeviceAddress, GetDeviceSpeed, OpenDeviceWithVidPid: 0, nothing written",
	     c);
}

void CaseDeviceList() {
	SetCase("device list");
	FillAll();
	Checks c;
	auto   list_fn = Fn<LList>("sceUsbdGetDeviceList");
	c.Eq("GetDeviceList(null)", list_fn(nullptr), On(static_cast<int64_t>(kInvArg)));
	void** list = reinterpret_cast<void**>(U(g_out));
	c.Eq("GetDeviceList: no device", list_fn(&list), 0);
	if (g_on) {
		c.True("an empty list (its first entry null)", list != reinterpret_cast<void**>(U(g_out)) && list != nullptr && list[0] == nullptr);
		void** again = nullptr;
		c.Eq("GetDeviceList again", list_fn(&again), 0);
		c.True("the same list", again == list);
	} else {
		c.True("the list pointer left as it was", list == reinterpret_cast<void**>(U(g_out)));
	}
	c.Eq("FreeDeviceList(the list)", Fn<IFree>("sceUsbdFreeDeviceList")(list, 1), 0);
	c.True("nothing else written", AllUntouched());
	Done(g_on ? "GetDeviceList: null refused (64-bit 0x80240002), else 0 and the same empty list each time; it frees"
	          : "GetDeviceList: 0, the output left as it was",
	     c);
}

void CaseAllocFree() {
	SetCase("alloc and free");
	FillAll();
	Checks c;
	auto   alloc = Fn<QI>("sceUsbdAllocTransfer");
	auto   freet = Fn<IP>("sceUsbdFreeTransfer");
	c.Eq("AllocTransfer(-1)", static_cast<int64_t>(alloc(-1)), 0);
	const uint64_t a = alloc(0);
	const uint64_t b = alloc(3);
	if (g_on) {
		c.True("AllocTransfer(0) gives a transfer", a != 0);
		c.True("AllocTransfer(3) gives another", b != 0 && b != a);
		if (a != 0 && b != 0) {
			const auto* pa   = reinterpret_cast<const uint8_t*>(a);
			const auto* pb   = reinterpret_cast<const uint8_t*>(b);
			bool        zero = true;
			for (size_t i = 0; i < 56; i++) {
				zero = zero && pa[i] == 0 && pb[i] == 0;
			}
			for (size_t i = 60; i < 60 + 3 * 12; i++) {
				zero = zero && pb[i] == 0;
			}
			c.True("zeroed", zero);
			c.Eq("packet count 0", At<int32_t>(pa, 56), 0);
			c.Eq("packet count 3", At<int32_t>(pb, 56), 3);
		}
	} else {
		c.Eq("AllocTransfer(0)", static_cast<int64_t>(a), 0);
		c.Eq("AllocTransfer(3)", static_cast<int64_t>(b), 0);
	}
	c.Eq("FreeTransfer(null)", freet(nullptr), 0);
	c.Eq("FreeTransfer(a transfer the title owns): not freed", freet(g_xfer), 0);
	if (g_on && a != 0 && b != 0) {
		c.Eq("FreeTransfer(3 packets)", freet(reinterpret_cast<void*>(b)), 0);
		c.Eq("FreeTransfer(0 packets)", freet(reinterpret_cast<void*>(a)), 0);
		c.Eq("FreeTransfer again: not freed twice", freet(reinterpret_cast<void*>(a)), 0);
	}
	c.True("nothing written", AllUntouched());
	Done(g_on ? "AllocTransfer: -1 null, else zeroed with its packet count; FreeTransfer frees only what it handed out, once"
	          : "AllocTransfer: null; FreeTransfer: 0",
	     c);
}

void CaseFill() {
	SetCase("fill");
	FillAll();
	Checks c;
	void*  cb = reinterpret_cast<void*>(uintptr_t {0x1111000});
	void*  ud = reinterpret_cast<void*>(uintptr_t {0x2222000});
	// the fields the fill writes, at their offsets; flags (+8), status (+16), actual length (+24) and the padding untouched
	auto check = [&](const char* what, uint8_t type, uint8_t endpoint, int32_t length, uint32_t timeout, const void* buffer,
	                 int32_t iso) {
		if (!g_on) {
			c.True(what, Untouched(g_xfer, sizeof(g_xfer)));
			return;
		}
		const bool ok = At<uint64_t>(g_xfer, 0) == U(Fake()) && At<uint8_t>(g_xfer, 8) == kFill &&
		                At<uint8_t>(g_xfer, 9) == endpoint && At<uint8_t>(g_xfer, 10) == type &&
		                At<uint8_t>(g_xfer, 11) == kFill && At<uint32_t>(g_xfer, 12) == timeout &&
		                At<uint32_t>(g_xfer, 16) == 0x5A5A5A5Au && At<int32_t>(g_xfer, 20) == length &&
		                At<uint32_t>(g_xfer, 24) == 0x5A5A5A5Au && At<uint32_t>(g_xfer, 28) == 0x5A5A5A5Au &&
		                At<uint64_t>(g_xfer, 32) == U(cb) && At<uint64_t>(g_xfer, 40) == U(ud) &&
		                At<uint64_t>(g_xfer, 48) == U(buffer) && At<int32_t>(g_xfer, 56) == iso &&
		                Untouched(g_xfer + 60, sizeof(g_xfer) - 60);
		c.True(what, ok);
	};
	const int32_t untouched_iso = static_cast<int32_t>(0x5A5A5A5Au);
	c.Eq("FillInterruptTransfer", Fn<IFill>("sceUsbdFillInterruptTransfer")(g_xfer, Fake(), 0x81, g_data, 64, cb, ud, 500), 0);
	check("interrupt: type 3, its fields", 3, 0x81, 64, 500, g_data, untouched_iso);
	std::memset(g_xfer, kFill, sizeof(g_xfer));
	c.Eq("FillBulkTransfer", Fn<IFill>("sceUsbdFillBulkTransfer")(g_xfer, Fake(), 0x02, g_data, 32, cb, ud, 0), 0);
	check("bulk: type 2", 2, 0x02, 32, 0, g_data, untouched_iso);
	std::memset(g_xfer, kFill, sizeof(g_xfer));
	c.Eq("FillIsoTransfer", Fn<IFillI>("sceUsbdFillIsoTransfer")(g_xfer, Fake(), 0x83, g_data, 60, 3, cb, ud, 7), 0);
	check("iso: type 1, the packet count", 1, 0x83, 60, 7, g_data, 3);
	std::memset(g_xfer, kFill, sizeof(g_xfer));
	c.Eq("FillControlSetup", Fn<ISetup>("sceUsbdFillControlSetup")(g_setup, 0xC0, 0x06, 0x0302, 0x0409, 0x00FF), 0);
	const uint8_t want_setup[8] = {0xC0, 0x06, 0x02, 0x03, 0x09, 0x04, 0xFF, 0x00};
	c.True("the setup packet", g_on ? std::memcmp(g_setup, want_setup, 8) == 0 && Untouched(g_setup + 8, sizeof(g_setup) - 8)
	                                : Untouched(g_setup, sizeof(g_setup)));
	c.Eq("FillControlTransfer", Fn<ICtlX>("sceUsbdFillControlTransfer")(g_xfer, Fake(), g_setup, cb, ud, 1000), 0);
	check("control: type 0, endpoint 0, length 8 + wLength", 0, 0, 8 + 0xFF, 1000, g_setup, untouched_iso);
	std::memset(g_xfer, kFill, sizeof(g_xfer));
	c.Eq("FillControlTransfer(no buffer)", Fn<ICtlX>("sceUsbdFillControlTransfer")(g_xfer, Fake(), nullptr, cb, ud, 1000), 0);
	check("control without a buffer: length 0", 0, 0, 0, 1000, nullptr, untouched_iso);
	std::memset(g_xfer, kFill, sizeof(g_xfer));
	// a null transfer or buffer: no answer upstream, today's 0, nothing written
	c.Eq("FillInterruptTransfer(null)", Fn<IFill>("sceUsbdFillInterruptTransfer")(nullptr, Fake(), 1, g_data, 1, cb, ud, 1), 0);
	c.Eq("FillBulkTransfer(null)", Fn<IFill>("sceUsbdFillBulkTransfer")(nullptr, Fake(), 1, g_data, 1, cb, ud, 1), 0);
	c.Eq("FillIsoTransfer(null)", Fn<IFillI>("sceUsbdFillIsoTransfer")(nullptr, Fake(), 1, g_data, 1, 1, cb, ud, 1), 0);
	c.Eq("FillControlTransfer(null)", Fn<ICtlX>("sceUsbdFillControlTransfer")(nullptr, Fake(), g_setup, cb, ud, 1), 0);
	c.Eq("FillControlSetup(null)", Fn<ISetup>("sceUsbdFillControlSetup")(nullptr, 1, 2, 3, 4, 5), 0);
	c.True("nothing else written", Untouched(g_xfer, sizeof(g_xfer)) && Untouched(g_data, sizeof(g_data)) &&
	                                   Untouched(g_out, sizeof(g_out)) && Untouched(g_fake_device, sizeof(g_fake_device)));
	Done(g_on ? "Fill{Interrupt,Bulk,Iso,Control}Transfer and FillControlSetup: the fields at their offsets; null: today's 0"
	          : "the fill calls: 0, nothing written",
	     c);
}

void CaseControlAndIso() {
	SetCase("control and iso");
	FillAll();
	Checks c;
	auto   get_data  = Fn<QP>("sceUsbdControlTransferGetData");
	auto   get_setup = Fn<QP>("sceUsbdControlTransferGetSetup");
	auto   set_len   = Fn<IPU32>("sceUsbdSetIsoPacketLengths");
	auto   iso_buf   = Fn<QPU32>("sceUsbdGetIsoPacketBuffer");
	Put<uint64_t>(g_xfer, 48, U(g_setup));
	c.Eq("ControlTransferGetData", static_cast<int64_t>(get_data(g_xfer)), On(static_cast<int64_t>(U(g_setup + 8))));
	c.Eq("ControlTransferGetSetup", static_cast<int64_t>(get_setup(g_xfer)), On(static_cast<int64_t>(U(g_setup))));
	Put<uint64_t>(g_xfer, 48, 0);
	c.Eq("ControlTransferGetData(no buffer)", static_cast<int64_t>(get_data(g_xfer)), 0);
	c.Eq("ControlTransferGetSetup(no buffer)", static_cast<int64_t>(get_setup(g_xfer)), 0);
	c.Eq("ControlTransferGetData(null)", static_cast<int64_t>(get_data(nullptr)), 0);
	c.Eq("ControlTransferGetSetup(null)", static_cast<int64_t>(get_setup(nullptr)), 0);
	// three packets of the title's own transfer, the fourth record must stay as it was
	Put<uint64_t>(g_xfer, 48, U(g_data));
	Put<int32_t>(g_xfer, 56, 3);
	c.Eq("SetIsoPacketLengths(100)", set_len(g_xfer, 100), 0);
	bool lengths = true;
	for (int i = 0; i < 3; i++) {
		lengths = lengths && At<uint32_t>(g_xfer, 60 + 12 * i) == (g_on ? 100u : 0x5A5A5A5Au) &&
		          At<uint32_t>(g_xfer, 64 + 12 * i) == 0x5A5A5A5Au && At<uint32_t>(g_xfer, 68 + 12 * i) == 0x5A5A5A5Au;
	}
	c.True("each packet's length, nothing else", lengths && Untouched(g_xfer + 96, sizeof(g_xfer) - 96));
	Put<uint32_t>(g_xfer, 60, 10);
	Put<uint32_t>(g_xfer, 72, 20);
	Put<uint32_t>(g_xfer, 84, 30);
	c.Eq("GetIsoPacketBuffer(0)", static_cast<int64_t>(iso_buf(g_xfer, 0)), On(static_cast<int64_t>(U(g_data))));
	c.Eq("GetIsoPacketBuffer(2): after 10 + 20", static_cast<int64_t>(iso_buf(g_xfer, 2)), On(static_cast<int64_t>(U(g_data + 30))));
	c.Eq("GetIsoPacketBuffer(3): past the count", static_cast<int64_t>(iso_buf(g_xfer, 3)), 0);
	Put<int32_t>(g_xfer, 56, -1);
	c.Eq("GetIsoPacketBuffer, a negative count", static_cast<int64_t>(iso_buf(g_xfer, 0)), 0);
	Put<int32_t>(g_xfer, 56, 3);
	Put<uint64_t>(g_xfer, 48, 0);
	c.Eq("GetIsoPacketBuffer, no buffer", static_cast<int64_t>(iso_buf(g_xfer, 1)), 0);
	c.Eq("GetIsoPacketBuffer(null)", static_cast<int64_t>(iso_buf(nullptr, 0)), 0);
	c.Eq("SetIsoPacketLengths(null)", set_len(nullptr, 5), 0);
	c.True("nothing else written", Untouched(g_setup, sizeof(g_setup)) && Untouched(g_data, sizeof(g_data)) &&
	                                   Untouched(g_out, sizeof(g_out)) && Untouched(g_xfer + 96, sizeof(g_xfer) - 96));
	Done(g_on ? "ControlTransferGetData/GetSetup, SetIsoPacketLengths, GetIsoPacketBuffer: the buffer arithmetic; null: today's 0"
	          : "the control and iso getters: 0, nothing written",
	     c);
}

void CaseCancelSubmit() {
	SetCase("cancel and submit");
	FillAll();
	Checks c;
	auto   cancel = Fn<IP>("sceUsbdCancelTransfer");
	auto   submit = Fn<IP>("sceUsbdSubmitTransfer");
	c.Eq("CancelTransfer: nothing in flight", cancel(g_xfer), On(kNotFound));
	c.Eq("CancelTransfer(null)", cancel(nullptr), 0);
	c.Eq("SubmitTransfer(null)", submit(nullptr), On(kInvArg));
	Put<uint64_t>(g_xfer, 0, 0);
	c.Eq("SubmitTransfer, no handle", submit(g_xfer), On(kInvArg));
	Put<uint64_t>(g_xfer, 0, U(Fake()));
	c.Eq("SubmitTransfer, a handle never opened", submit(g_xfer), 0);
	c.True("the transfer as it was", At<uint64_t>(g_xfer, 0) == U(Fake()) && Untouched(g_xfer + 8, sizeof(g_xfer) - 8));
	c.True("nothing else written", Untouched(g_out, sizeof(g_out)) && Untouched(g_fake_device, sizeof(g_fake_device)));
	Done(g_on ? "CancelTransfer: NOT_FOUND (0x80240005); SubmitTransfer: null or no handle INVALID_ARG, else today's 0"
	          : "CancelTransfer, SubmitTransfer: 0",
	     c);
}

// The handle and device calls: the refused arguments (on: their code), then a non-null handle or device, which with no
// device was never handed out: today's 0, on and off, with nothing written.
void CaseHandleCall(const char* name, const std::function<void(Checks&)>& body) {
	SetCase(name);
	FillAll();
	Checks c;
	body(c);
	c.True("nothing written", AllUntouched());
	Done(Fmt("%s: %s", name, g_on ? "the argument checks; a handle or device never handed out: today's 0" : "0"), c);
}

void CaseHandleCalls() {
	auto* out32 = reinterpret_cast<int32_t*>(g_out);
	auto* outp  = reinterpret_cast<void**>(g_out);
	for (const char* name: {"sceUsbdAttachKernelDriver", "sceUsbdClaimInterface", "sceUsbdDetachKernelDriver",
	                         "sceUsbdKernelDriverActive", "sceUsbdReleaseInterface", "sceUsbdSetConfiguration"}) {
		CaseHandleCall(name, [&](Checks& c) {
			c.Eq("null handle", Fn<IPI>(name)(nullptr, 0), On(kInvArg));
			c.Eq("a handle never opened", Fn<IPI>(name)(Fake(), 0), 0);
		});
	}
	for (const char* name: {"sceUsbdCheckConnected", "sceUsbdResetDevice"}) {
		CaseHandleCall(name, [&](Checks& c) {
			c.Eq("null handle", Fn<IP>(name)(nullptr), On(kInvArg));
			c.Eq("a handle never opened", Fn<IP>(name)(Fake()), 0);
		});
	}
	CaseHandleCall("sceUsbdSetInterfaceAltSetting", [&](Checks& c) {
		auto f = Fn<IPII>("sceUsbdSetInterfaceAltSetting");
		c.Eq("null handle", f(nullptr, 0, 0), On(kInvArg));
		c.Eq("a handle never opened (checked before the interface range)", f(Fake(), 40, 0), 0);
	});
	CaseHandleCall("sceUsbdControlTransfer", [&](Checks& c) {
		auto f = Fn<ICtl>("sceUsbdControlTransfer");
		c.Eq("null handle", f(nullptr, 0x80, 6, 0x0100, 0, g_data, 18, 100), On(kInvArg));
		c.Eq("no data for 8 bytes", f(Fake(), 0x80, 6, 0x0100, 0, nullptr, 8, 100), On(kInvArg));
		c.Eq("no data for 0 bytes", f(Fake(), 0x00, 9, 1, 0, nullptr, 0, 100), 0);
		c.Eq("a handle never opened", f(Fake(), 0x80, 6, 0x0100, 0, g_data, 18, 100), 0);
	});
	for (const char* name: {"sceUsbdBulkTransfer", "sceUsbdInterruptTransfer"}) {
		CaseHandleCall(name, [&](Checks& c) {
			auto f = Fn<ISync>(name);
			c.Eq("null handle", f(nullptr, 0x81, g_data, 4, out32, 0), On(kInvArg));
			c.Eq("no data for 4 bytes", f(Fake(), 0x81, nullptr, 4, out32, 0), On(kInvArg));
			c.Eq("no data for 0 bytes", f(Fake(), 0x81, nullptr, 0, out32, 0), 0);
			c.Eq("no transferred output", f(Fake(), 0x81, g_data, 4, nullptr, 0), 0);
			c.Eq("a handle never opened", f(Fake(), 0x81, g_data, 4, out32, 0), 0);
		});
	}
	CaseHandleCall("sceUsbdGetConfiguration", [&](Checks& c) {
		auto f = Fn<IPPI>("sceUsbdGetConfiguration");
		c.Eq("null handle", f(nullptr, out32), On(kInvArg));
		c.Eq("null output", f(Fake(), nullptr), On(kInvArg));
		c.Eq("a handle never opened", f(Fake(), out32), 0);
	});
	CaseHandleCall("sceUsbdGetDescriptor", [&](Checks& c) {
		auto f = Fn<IDesc>("sceUsbdGetDescriptor");
		c.Eq("null handle", f(nullptr, 1, 0, g_out, 18), On(kInvArg));
		c.Eq("null data", f(Fake(), 1, 0, nullptr, 18), On(kInvArg));
		c.Eq("length 0", f(Fake(), 1, 0, g_out, 0), On(kInvArg));
		c.Eq("a handle never opened", f(Fake(), 1, 0, g_out, 18), 0);
	});
	CaseHandleCall("sceUsbdGetStringDescriptor", [&](Checks& c) {
		auto f = Fn<IStr>("sceUsbdGetStringDescriptor");
		c.Eq("null handle", f(nullptr, 1, 0x0409, g_out, 64), On(kInvArg));
		c.Eq("null data", f(Fake(), 1, 0x0409, nullptr, 64), On(kInvArg));
		c.Eq("length 0", f(Fake(), 1, 0x0409, g_out, 0), On(kInvArg));
		c.Eq("a handle never opened (nothing written)", f(Fake(), 1, 0x0409, g_out, 64), 0);
	});
	CaseHandleCall("sceUsbdGetStringDescriptorAscii", [&](Checks& c) {
		auto f = Fn<IStrA>("sceUsbdGetStringDescriptorAscii");
		c.Eq("null handle", f(nullptr, 1, g_out, 64), On(kInvArg));
		c.Eq("null data", f(Fake(), 1, nullptr, 64), On(kInvArg));
		c.Eq("length -1", f(Fake(), 1, g_out, -1), On(kInvArg));
		c.Eq("a handle never opened (nothing written)", f(Fake(), 1, g_out, 64), 0);
	});
	for (const char* name: {"sceUsbdGetConfigDescriptor", "sceUsbdGetConfigDescriptorByValue"}) {
		CaseHandleCall(name, [&](Checks& c) {
			auto f = Fn<IPU8P>(name);
			c.Eq("null device", f(nullptr, 0, outp), On(kInvArg));
			c.Eq("null output", f(Fake(), 0, nullptr), On(kInvArg));
			c.Eq("a device never handed out", f(Fake(), 1, outp), 0);
		});
	}
	CaseHandleCall("sceUsbdGetDeviceDescriptor", [&](Checks& c) {
		auto f = Fn<IPPV>("sceUsbdGetDeviceDescriptor");
		c.Eq("null device", f(nullptr, g_out), On(kInvArg));
		c.Eq("null output", f(Fake(), nullptr), On(kInvArg));
		c.Eq("a device never handed out", f(Fake(), g_out), 0);
	});
	for (const char* name: {"sceUsbdGetActiveConfigDescriptor", "sceUsbdOpen"}) {
		CaseHandleCall(name, [&](Checks& c) {
			auto f = Fn<IPP>(name);
			c.Eq("null device: no answer upstream", f(nullptr, outp), 0);
			c.Eq("null output", f(Fake(), nullptr), On(kInvArg));
			c.Eq("a device never handed out", f(Fake(), outp), 0);
		});
	}
	CaseHandleCall("sceUsbdGetMaxPacketSize", [&](Checks& c) {
		auto f = Fn<IPU8>("sceUsbdGetMaxPacketSize");
		c.Eq("null device: NO_DEVICE", f(nullptr, 0x81), On(kNoDevice));
		c.Eq("a device never handed out", f(Fake(), 0x81), 0);
	});
	CaseHandleCall("sceUsbdGetMaxIsoPacketSize", [&](Checks& c) {
		auto f = Fn<IPU8>("sceUsbdGetMaxIsoPacketSize");
		c.Eq("null device: no answer upstream", f(nullptr, 0x81), 0);
		c.Eq("a device never handed out", f(Fake(), 0x81), 0);
	});
	CaseHandleCall("sceUsbdClearHalt", [&](Checks& c) {
		auto f = Fn<IPU8>("sceUsbdClearHalt");
		c.Eq("null handle: no answer upstream", f(nullptr, 0x81), 0);
		c.Eq("a handle never opened", f(Fake(), 0x81), 0);
	});
}

// One thread: the lock, the handler role, the waiters, the timeouts.
void CaseEventsOneThread() {
	SetCase("events, one thread");
	Checks c;
	auto   ok       = Fn<I0>("sceUsbdEventHandlingOk");
	auto   active   = Fn<I0>("sceUsbdEventHandlerActive");
	auto   trylock  = Fn<I0>("sceUsbdTryLockEvents");
	auto   lock     = Fn<I0>("sceUsbdLockEvents");
	auto   unlock   = Fn<I0>("sceUsbdUnlockEvents");
	auto   lockw    = Fn<I0>("sceUsbdLockEventWaiters");
	auto   unlockw  = Fn<I0>("sceUsbdUnlockEventWaiters");
	auto   wait     = Fn<ITv>("sceUsbdWaitForEvent");
	auto   hlocked  = Fn<ITv>("sceUsbdHandleEventsLocked");
	auto   htimeout = Fn<ITv>("sceUsbdHandleEventsTimeout");
	c.Eq("HandlingOk, no handler", ok(), 0);
	c.Eq("HandlerActive, no handler", active(), 0);
	c.Eq("TryLockEvents takes the lock and the handler role", trylock(), 0);
	c.Eq("HandlingOk after it", ok(), On(1));
	c.Eq("HandlerActive after it", active(), On(1));
	c.Eq("TryLockEvents again in the same thread", trylock(), On(1));
	c.Eq("UnlockEvents", unlock(), 0);
	c.Eq("HandlerActive after the unlock", active(), 0);
	c.Eq("LockEvents", lock(), 0);
	c.Eq("HandlingOk under LockEvents", ok(), On(1));
	c.Eq("LockEvents again: no answer upstream, no deadlock", lock(), 0);
	c.Eq("UnlockEvents", unlock(), 0);
	c.Eq("UnlockEvents without the lock: no answer upstream", unlock(), 0);
	c.Eq("HandlerActive", active(), 0);
	c.Eq("LockEventWaiters", lockw(), 0);
	c.Eq("HandlerActive under the waiters' lock", active(), 0);
	c.Eq("LockEventWaiters again: no answer upstream", lockw(), 0);
	c.Eq("UnlockEventWaiters", unlockw(), 0);
	c.Eq("UnlockEventWaiters again: no answer upstream", unlockw(), 0);
	const Tv ms1 {0, 1000};
	const Tv neg {-1, 0};
	c.Eq("WaitForEvent without the lock: no answer upstream", wait(&ms1), 0);
	c.Eq("WaitForEvent, a negative timeout: no answer upstream", wait(&neg), 0);
	c.Eq("HandleEventsLocked without the lock: no answer upstream", hlocked(&ms1), 0);
	const Tv usec_1e6 {0, 1000000};
	const Tv neg_usec {0, -1};
	const Tv huge {int64_t {1} << 31, 0};
	c.Eq("HandleEventsTimeout(null)", htimeout(nullptr), On(kInvArg));
	c.Eq("HandleEventsTimeout(1000000 us)", htimeout(&usec_1e6), On(kInvArg));
	c.Eq("HandleEventsTimeout(-1 s)", htimeout(&neg), On(kInvArg));
	c.Eq("HandleEventsTimeout(-1 us)", htimeout(&neg_usec), On(kInvArg));
	auto t0 = std::chrono::steady_clock::now();
	c.Eq("HandleEventsTimeout(2^31 s): no answer upstream", htimeout(&huge), 0);
	c.True("... and no wait", Ms(t0) < 1000);
	const Tv ms60 {0, 60000};
	t0 = std::chrono::steady_clock::now();
	c.Eq("HandleEventsTimeout(60 ms) as the handler", htimeout(&ms60), 0);
	const int64_t waited = Ms(t0);
	c.True(g_on ? "... sleeps its timeout (>= 55 ms)" : "... returns at once (< 55 ms)", g_on ? waited >= 55 : waited < 55);
	c.Eq("HandlerActive after it", active(), 0);
	const Tv ms40 {0, 40000};
	c.Eq("LockEvents", lock(), 0);
	t0 = std::chrono::steady_clock::now();
	c.Eq("HandleEventsLocked(40 ms) as the handler", hlocked(&ms40), 0);
	c.True(g_on ? "... sleeps its timeout (>= 35 ms)" : "... returns at once", g_on ? Ms(t0) >= 35 : Ms(t0) < 35);
	c.Eq("HandlingOk still", ok(), On(1));
	c.Eq("HandleEventsTimeout while holding the lock: no answer upstream", htimeout(&ms1), 0);
	c.Eq("UnlockEvents", unlock(), 0);
	c.Eq("LockEventWaiters", lockw(), 0);
	t0 = std::chrono::steady_clock::now();
	c.Eq("WaitForEvent(40 ms), nobody wakes it: 1", wait(&ms40), On(1));
	c.True(g_on ? "... after its timeout (>= 35 ms)" : "... at once", g_on ? Ms(t0) >= 35 : Ms(t0) < 35);
	c.Eq("HandlingOk: the waiter took over handling", ok(), On(1));
	c.Eq("UnlockEvents gives it up", unlock(), 0);
	c.Eq("HandlerActive at the end", active(), 0);
	Done(g_on ? "events, one thread: TryLock/Lock/Unlock, the waiters' lock, the handler role, timeouts (no answer: today's 0)"
	          : "events, one thread: every call 0 at once",
	     c);
}

bool WaitActive(int want) {
	auto active = Fn<I0>("sceUsbdEventHandlerActive");
	for (int i = 0; i < 400; i++) {
		if (active() == want) {
			return true;
		}
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	return false;
}

// Two threads: a handler in HandleEventsTimeout, and the main thread as a waiter.
void CaseEventsWake() {
	SetCase("events, a waiter woken by the handler's pass");
	Checks           c;
	std::atomic<int> handler_answer {-1};
	std::thread      a([&] {
		const Tv ms300 {0, 300000};
		handler_answer = Fn<ITv>("sceUsbdHandleEventsTimeout")(&ms300);
	});
	if (g_on) {
		c.True("the other thread becomes the handler", WaitActive(1));
		c.Eq("TryLockEvents: a handler exists", Fn<I0>("sceUsbdTryLockEvents")(), 1);
		c.Eq("LockEventWaiters", Fn<I0>("sceUsbdLockEventWaiters")(), 0);
		c.Eq("HandlingOk: not this thread", Fn<I0>("sceUsbdEventHandlingOk")(), 0);
		const Tv s2 {2, 0};
		auto     t0 = std::chrono::steady_clock::now();
		c.Eq("WaitForEvent(2 s): woken by the pass", Fn<ITv>("sceUsbdWaitForEvent")(&s2), 0);
		c.True("... before its timeout", Ms(t0) < 1900);
		c.Eq("HandlingOk: the handler left, this thread took over", Fn<I0>("sceUsbdEventHandlingOk")(), 1);
		c.Eq("UnlockEvents", Fn<I0>("sceUsbdUnlockEvents")(), 0);
	} else {
		c.Eq("LockEventWaiters", Fn<I0>("sceUsbdLockEventWaiters")(), 0);
		const Tv s2 {2, 0};
		auto     t0 = std::chrono::steady_clock::now();
		c.Eq("WaitForEvent(2 s)", Fn<ITv>("sceUsbdWaitForEvent")(&s2), 0);
		c.True("... at once", Ms(t0) < 100);
		c.Eq("UnlockEvents", Fn<I0>("sceUsbdUnlockEvents")(), 0);
	}
	a.join();
	c.Eq("the handler's HandleEventsTimeout(300 ms)", handler_answer.load(), 0);
	c.Eq("HandlerActive at the end", Fn<I0>("sceUsbdEventHandlerActive")(), 0);
	Done(g_on ? "events, two threads: a waiter wakes at the end of the handler's pass and takes over" : "events, two threads: 0",
	     c);
}

void CaseEventsWaiterTimeout() {
	SetCase("events, a waiter's timeout");
	Checks           c;
	std::atomic<int> handler_answer {-1};
	std::thread      a([&] {
		const Tv ms400 {0, 400000};
		handler_answer = Fn<ITv>("sceUsbdHandleEventsTimeout")(&ms400);
	});
	if (g_on) {
		c.True("the other thread becomes the handler", WaitActive(1));
	}
	c.Eq("LockEventWaiters", Fn<I0>("sceUsbdLockEventWaiters")(), 0);
	const Tv ms50 {0, 50000};
	auto     t0 = std::chrono::steady_clock::now();
	c.Eq("WaitForEvent(50 ms) during the pass", Fn<ITv>("sceUsbdWaitForEvent")(&ms50), On(1));
	const int64_t waited = Ms(t0);
	c.True(g_on ? "... after its timeout, before the pass ends" : "... at once", g_on ? waited >= 45 && waited < 350 : waited < 45);
	c.Eq("HandlingOk: the other thread still handles", Fn<I0>("sceUsbdEventHandlingOk")(), 0);
	c.Eq("UnlockEventWaiters", Fn<I0>("sceUsbdUnlockEventWaiters")(), 0);
	a.join();
	c.Eq("the handler's HandleEventsTimeout(400 ms)", handler_answer.load(), 0);
	c.Eq("HandlerActive at the end", Fn<I0>("sceUsbdEventHandlerActive")(), 0);
	Done(g_on ? "events, two threads: a waiter's WaitForEvent times out (1) while the handler sleeps" : "events, two threads: 0",
	     c);
}

void CaseEventsTimeoutAsWaiter() {
	SetCase("events, HandleEventsTimeout as a waiter");
	Checks           c;
	std::atomic<int> handler_answer {-1};
	std::thread      a([&] {
		const Tv ms400 {0, 400000};
		handler_answer = Fn<ITv>("sceUsbdHandleEventsTimeout")(&ms400);
	});
	if (g_on) {
		c.True("the other thread becomes the handler", WaitActive(1));
	}
	const Tv ms50 {0, 50000};
	auto     t0 = std::chrono::steady_clock::now();
	c.Eq("HandleEventsTimeout(50 ms) while another thread handles", Fn<ITv>("sceUsbdHandleEventsTimeout")(&ms50), On(kTimeout));
	const int64_t waited = Ms(t0);
	c.True(g_on ? "... after its timeout, before the pass ends" : "... at once", g_on ? waited >= 45 && waited < 350 : waited < 45);
	a.join();
	c.Eq("the handler's HandleEventsTimeout(400 ms)", handler_answer.load(), 0);
	c.Eq("HandlerActive at the end", Fn<I0>("sceUsbdEventHandlerActive")(), 0);
	Done(g_on ? "events, two threads: HandleEventsTimeout as a waiter times out with TIMEOUT (0x80240007)"
	          : "events, two threads: 0",
	     c);
}

void CaseEventsTryLockOther() {
	SetCase("events, TryLockEvents from another thread");
	Checks c;
	c.Eq("LockEvents", Fn<I0>("sceUsbdLockEvents")(), 0);
	int other = -1;
	std::thread([&] { other = Fn<I0>("sceUsbdTryLockEvents")(); }).join();
	c.Eq("TryLockEvents in another thread while this one holds the lock", other, On(1));
	c.Eq("UnlockEvents", Fn<I0>("sceUsbdUnlockEvents")(), 0);
	int other_try = -1;
	int other_ok  = -1;
	int other_un  = -1;
	std::thread([&] {
		other_try = Fn<I0>("sceUsbdTryLockEvents")();
		other_ok  = Fn<I0>("sceUsbdEventHandlingOk")();
		other_un  = Fn<I0>("sceUsbdUnlockEvents")();
	}).join();
	c.Eq("TryLockEvents in another thread after the unlock", other_try, 0);
	c.Eq("... which then handles", other_ok, On(1));
	c.Eq("... and unlocks", other_un, 0);
	c.Eq("HandlerActive at the end", Fn<I0>("sceUsbdEventHandlerActive")(), 0);
	Done(g_on ? "events, two threads: TryLockEvents 1 while another thread holds the lock, 0 after" : "events, two threads: 0", c);
}

void CaseHeld() {
	SetCase("held");
	Checks c;
	for (const char* name: kHeld) {
		const char* nid = NidOf(name);
		if (g_on) {
			c.True(name, g_db.Find(Key(nid)) == nullptr && g_db.FindByNid(nid, Loader::SymbolType::Func) == nullptr);
		} else {
			c.Eq(name, Fn<I0>(name)(), 0);
		}
	}
	Done(g_on ? "the 4 held (unnamed, absent upstream): not registered, the stubbed-import line shows"
	          : "the 4 held: registered, today's 0",
	     c);
}

// Last: sceUsbdHandleEvents with no timeout waits until a transfer completes, which with no device never happens. The
// thread is left inside it (on); the test ends with _Exit.
void CaseHandleEventsForever() {
	SetCase("HandleEvents");
	Checks                  c;
	static std::atomic<int> answer {-1};
	std::thread             h([] { answer = Fn<I0>("sceUsbdHandleEvents")(); });
	std::this_thread::sleep_for(std::chrono::milliseconds(300));
	if (g_on) {
		c.True("still inside after 300 ms", answer.load() == -1);
		c.Eq("HandlerActive: that thread handles", Fn<I0>("sceUsbdEventHandlerActive")(), 1);
		c.Eq("HandlingOk: not this thread", Fn<I0>("sceUsbdEventHandlingOk")(), 0);
		h.detach();
	} else {
		h.join();
		c.Eq("HandleEvents", answer.load(), 0);
	}
	Done(g_on ? "HandleEvents with no device: the handler waits for a transfer that never completes (no spin)"
	          : "HandleEvents: 0 at once",
	     c);
}

// ---- a fake libusb-1.0: the child "fake" injects it through the port's loader hook (no dlopen, no host USB) -----------
namespace fakeusb {

// libusb.h's x86-64 layouts, as the port declares them.
struct DevDesc {
	uint8_t  bLength;
	uint8_t  bDescriptorType;
	uint16_t bcdUSB;
	uint8_t  bDeviceClass;
	uint8_t  bDeviceSubClass;
	uint8_t  bDeviceProtocol;
	uint8_t  bMaxPacketSize0;
	uint16_t idVendor;
	uint16_t idProduct;
	uint16_t bcdDevice;
	uint8_t  iManufacturer;
	uint8_t  iProduct;
	uint8_t  iSerialNumber;
	uint8_t  bNumConfigurations;
};
struct Ep {
	uint8_t              bLength;
	uint8_t              bDescriptorType;
	uint8_t              bEndpointAddress;
	uint8_t              bmAttributes;
	uint16_t             wMaxPacketSize;
	uint8_t              bInterval;
	uint8_t              bRefresh;
	uint8_t              bSynchAddress;
	const unsigned char* extra;
	int                  extra_length;
};
struct Alt {
	uint8_t              bLength;
	uint8_t              bDescriptorType;
	uint8_t              bInterfaceNumber;
	uint8_t              bAlternateSetting;
	uint8_t              bNumEndpoints;
	uint8_t              bInterfaceClass;
	uint8_t              bInterfaceSubClass;
	uint8_t              bInterfaceProtocol;
	uint8_t              iInterface;
	const Ep*            endpoint;
	const unsigned char* extra;
	int                  extra_length;
};
struct Iface {
	const Alt* altsetting;
	int        num_altsetting;
};
struct Config {
	uint8_t              bLength;
	uint8_t              bDescriptorType;
	uint16_t             wTotalLength;
	uint8_t              bNumInterfaces;
	uint8_t              bConfigurationValue;
	uint8_t              iConfiguration;
	uint8_t              bmAttributes;
	uint8_t              MaxPower;
	const Iface*         interfaces;
	const unsigned char* extra;
	int                  extra_length;
};
struct Transfer {
	void*    dev_handle;
	uint8_t  flags;
	uint8_t  endpoint;
	uint8_t  type;
	uint32_t timeout;
	int32_t  status;
	int32_t  length;
	int32_t  actual_length;
	void (*callback)(Transfer*);
	void*    user_data;
	uint8_t* buffer;
	int32_t  num_iso_packets;
};
struct Timeval {
	long seconds;
	long microseconds;
};
static_assert(sizeof(DevDesc) == 18 && sizeof(Ep) == 32 && sizeof(Alt) == 40 && sizeof(Iface) == 16 && sizeof(Config) == 40);
static_assert(offsetof(Transfer, callback) == 32 && offsetof(Transfer, num_iso_packets) == 56);

struct Dev {
	uint16_t vid             = 0;
	uint16_t pid             = 0;
	uint8_t  device_class    = 0;
	uint8_t  interface_class = 0;
	bool     config_fails    = false;
	int      opens           = 0;
	int      claims          = 0;
	int      detaches        = 0;
	int      refs            = 0;
	Ep       eps[3] {};
	Alt      alt {};
	Iface    iface {};
	Config   config {};
};
struct Handle {
	Dev* dev;
};

constexpr int kDevs = 7;
Dev           g_devs[kDevs];
char          g_context_object;
int           g_lookups = 0, g_inits = 0, g_exits = 0, g_lists = 0, g_config_gets = 0, g_config_frees = 0;
int           g_open_handles = 0, g_closes = 0, g_allocs = 0, g_frees = 0, g_submits = 0, g_cancels = 0, g_resets = 0;
int           g_alt_calls = 0, g_speed = 3;
bool          g_gone = false;
struct ControlArgs {
	uint8_t  request_type;
	uint8_t  request;
	uint16_t value;
	uint16_t index;
	uint16_t length;
	unsigned timeout;
};
ControlArgs            g_control {};
std::vector<Transfer*> g_pending;
std::set<Transfer*>    g_cancelled;

// The devices: 0 a vendor-class device; 1 an interface of class HID; 2 an interface of class audio; 3 a configuration
// that cannot be read; 4 a device class HID; 5 a DualSense id; 6 an id nobody lists. Each with one configuration, one
// interface, endpoints 0x81 (interrupt, 64), 0x02 (bulk, 512) and 0x83 (iso, 0x1400: 1024 bytes, 3 per microframe).
void Setup() {
	const struct {
		uint16_t vid;
		uint16_t pid;
		uint8_t  device_class;
		uint8_t  interface_class;
		bool     config_fails;
	} spec[kDevs] = {{0x1234, 0x5678, 0, 0xFF, false}, {0x1234, 0x0003, 0, 3, false},     {0x1234, 0x0001, 0, 1, false},
	                 {0xABCD, 0xEF01, 0, 0xFF, true},  {0x1234, 0x0007, 3, 0xFF, false},  {0x054C, 0x0CE6, 0, 0xFF, false},
	                 {0x9999, 0x9999, 0, 0xFF, false}};
	const uint8_t  addresses[3] = {0x81, 0x02, 0x83};
	const uint8_t  kinds[3]     = {3, 2, 1};
	const uint16_t sizes[3]     = {64, 512, 0x1400};
	for (int i = 0; i < kDevs; i++) {
		Dev& d            = g_devs[i];
		d                 = Dev {};
		d.vid             = spec[i].vid;
		d.pid             = spec[i].pid;
		d.device_class    = spec[i].device_class;
		d.interface_class = spec[i].interface_class;
		d.config_fails    = spec[i].config_fails;
		for (int e = 0; e < 3; e++) {
			d.eps[e].bLength          = 7;
			d.eps[e].bDescriptorType  = 5;
			d.eps[e].bEndpointAddress = addresses[e];
			d.eps[e].bmAttributes     = kinds[e];
			d.eps[e].wMaxPacketSize   = sizes[e];
		}
		d.alt.bLength               = 9;
		d.alt.bDescriptorType       = 4;
		d.alt.bNumEndpoints         = 3;
		d.alt.bInterfaceClass       = d.interface_class;
		d.alt.endpoint              = d.eps;
		d.iface.altsetting          = &d.alt;
		d.iface.num_altsetting      = 1;
		d.config.bLength            = 9;
		d.config.bDescriptorType    = 2;
		d.config.bNumInterfaces     = 1;
		d.config.bConfigurationValue = 1;
		d.config.interfaces         = &d.iface;
	}
}

Dev* AsDev(void* p) {
	return static_cast<Dev*>(p);
}

int Init(void** context) {
	g_inits++;
	*context = &g_context_object;
	return 0;
}
void Exit(void* /*context*/) {
	g_exits++;
}
std::ptrdiff_t GetDeviceList(void* /*context*/, void*** list) {
	g_lists++;
	auto** l = new void*[kDevs + 1];
	for (int i = 0; i < kDevs; i++) {
		l[i] = &g_devs[i];
		g_devs[i].refs++;
	}
	l[kDevs] = nullptr;
	*list    = l;
	return kDevs;
}
void FreeDeviceList(void** list, int unref) {
	if (unref != 0) {
		for (void** p = list; *p != nullptr; p++) {
			AsDev(*p)->refs--;
		}
	}
	delete[] list;
}
void* RefDevice(void* device) {
	AsDev(device)->refs++;
	return device;
}
void UnrefDevice(void* device) {
	AsDev(device)->refs--;
}
int GetDeviceDescriptor(void* device, DevDesc* out) {
	const Dev* d = AsDev(device);
	*out         = DevDesc {};
	out->bLength            = 18;
	out->bDescriptorType    = 1;
	out->bcdUSB             = 0x0200;
	out->bDeviceClass       = d->device_class;
	out->bMaxPacketSize0    = 64;
	out->idVendor           = d->vid;
	out->idProduct          = d->pid;
	out->bNumConfigurations = 1;
	return 0;
}
int GetConfig(void* device, uint8_t index, Config** config) {
	Dev* d = AsDev(device);
	if (d->config_fails) {
		return -1; // LIBUSB_ERROR_IO
	}
	if (index != 0) {
		return -5; // LIBUSB_ERROR_NOT_FOUND
	}
	g_config_gets++;
	*config = new Config(d->config);
	return 0;
}
int GetActiveConfig(void* device, Config** config) {
	return GetConfig(device, 0, config);
}
int GetConfigByValue(void* device, uint8_t value, Config** config) {
	return value == 1 ? GetConfig(device, 0, config) : -5;
}
void FreeConfig(Config* config) {
	g_config_frees++;
	delete config;
}
uint8_t BusNumber(void* /*device*/) {
	return 3;
}
uint8_t DeviceAddress(void* /*device*/) {
	return 7;
}
int DeviceSpeed(void* /*device*/) {
	return g_speed;
}
int Open(void* device, void** handle) {
	AsDev(device)->opens++;
	g_open_handles++;
	*handle = new Handle {AsDev(device)};
	return 0;
}
void Close(void* handle) {
	g_closes++;
	g_open_handles--;
	delete static_cast<Handle*>(handle);
}
void* GetDevice(void* handle) {
	return static_cast<Handle*>(handle)->dev;
}
int GetConfiguration(void* /*handle*/, int* config) {
	if (g_gone) {
		return -4; // LIBUSB_ERROR_NO_DEVICE
	}
	*config = 1;
	return 0;
}
int SetConfiguration(void* /*handle*/, int /*config*/) {
	return 0;
}
int Claim(void* handle, int interface_number) {
	static_cast<Handle*>(handle)->dev->claims++;
	return interface_number < 0 || interface_number >= 32 ? -2 : 0;
}
int Release(void* /*handle*/, int interface_number) {
	return interface_number < 0 || interface_number >= 32 ? -2 : 0;
}
int AltSetting(void* /*handle*/, int /*interface_number*/, int /*alternate_setting*/) {
	g_alt_calls++;
	return 0;
}
int ClearHalt(void* /*handle*/, unsigned char endpoint) {
	return endpoint == 0x81 ? 0 : endpoint == 0x05 ? -5 : -9; // ok, NOT_FOUND, PIPE
}
int Reset(void* /*handle*/) {
	g_resets++;
	return 0;
}
int KernelDriverActive(void* /*handle*/, int /*interface_number*/) {
	return 1;
}
int Detach(void* handle, int /*interface_number*/) {
	static_cast<Handle*>(handle)->dev->detaches++;
	return 0;
}
int Control(void* /*handle*/, uint8_t request_type, uint8_t request, uint16_t value, uint16_t index, unsigned char* data,
            uint16_t length, unsigned int timeout) {
	g_control = {request_type, request, value, index, length, timeout};
	if (request == 6 && (value >> 8u) == 3) { // a string descriptor
		if ((value & 0xFFu) == 0) {
			const uint8_t languages[4] = {4, 3, 0x09, 0x04};
			std::memcpy(data, languages, std::min<size_t>(length, 4));
			return 4;
		}
		const uint8_t text[14] = {14, 3, 'H', 0, 'i', 0, '<', 0, '>', 0, '!', 0, 0x01, 0};
		std::memcpy(data, text, std::min<size_t>(length, 14));
		return 14;
	}
	return length;
}
int Bulk(void* /*handle*/, unsigned char /*endpoint*/, unsigned char* /*data*/, int length, int* transferred,
         unsigned int /*timeout*/) {
	*transferred = length;
	return 0;
}
int Interrupt(void* /*handle*/, unsigned char /*endpoint*/, unsigned char* /*data*/, int /*length*/, int* transferred,
              unsigned int /*timeout*/) {
	*transferred = 0;
	return -7; // LIBUSB_ERROR_TIMEOUT
}
Transfer* Alloc(int iso_packets) {
	g_allocs++;
	return static_cast<Transfer*>(std::calloc(1, 64 + 12 * static_cast<size_t>(std::max(iso_packets, 0))));
}
void Free(Transfer* transfer) {
	g_frees++;
	std::free(transfer);
}
int Submit(Transfer* transfer) {
	g_submits++;
	g_pending.push_back(transfer);
	return 0;
}
int Cancel(Transfer* transfer) {
	g_cancels++;
	g_cancelled.insert(transfer);
	return 0;
}
uint32_t IsoAt(Transfer* t, int packet, int field) {
	uint32_t v = 0;
	std::memcpy(&v, reinterpret_cast<uint8_t*>(t) + 60 + 12 * packet + 4 * field, 4);
	return v;
}
void IsoPut(Transfer* t, int packet, int field, uint32_t v) {
	std::memcpy(reinterpret_cast<uint8_t*>(t) + 60 + 12 * packet + 4 * field, &v, 4);
}
// Every pending transfer completes (cancelled: status 3), each callback runs in this thread, as libusb does.
int HandleEvents(void* /*context*/, Timeval* /*timeout*/, int* /*completed*/) {
	std::vector<Transfer*> done;
	done.swap(g_pending);
	for (Transfer* t: done) {
		const bool cancelled = g_cancelled.erase(t) != 0;
		t->status            = cancelled ? 3 : 0;
		t->actual_length     = t->length;
		for (int p = 0; p < t->num_iso_packets; p++) {
			IsoPut(t, p, 1, IsoAt(t, p, 0));
			IsoPut(t, p, 2, 0);
		}
		t->callback(t); // the port's completion: it frees t
	}
	return 0;
}

template <typename F>
void* Sym(F f) {
	return reinterpret_cast<void*>(f);
}

void* Symbols(const char* name) {
	g_lookups++;
	static const std::map<std::string, void*> table = {
	    {"libusb_init", Sym(&Init)},
	    {"libusb_exit", Sym(&Exit)},
	    {"libusb_get_device_list", Sym(&GetDeviceList)},
	    {"libusb_free_device_list", Sym(&FreeDeviceList)},
	    {"libusb_ref_device", Sym(&RefDevice)},
	    {"libusb_unref_device", Sym(&UnrefDevice)},
	    {"libusb_get_device_descriptor", Sym(&GetDeviceDescriptor)},
	    {"libusb_get_active_config_descriptor", Sym(&GetActiveConfig)},
	    {"libusb_get_config_descriptor", Sym(&GetConfig)},
	    {"libusb_get_config_descriptor_by_value", Sym(&GetConfigByValue)},
	    {"libusb_free_config_descriptor", Sym(&FreeConfig)},
	    {"libusb_get_bus_number", Sym(&BusNumber)},
	    {"libusb_get_device_address", Sym(&DeviceAddress)},
	    {"libusb_get_device_speed", Sym(&DeviceSpeed)},
	    {"libusb_open", Sym(&Open)},
	    {"libusb_close", Sym(&Close)},
	    {"libusb_get_device", Sym(&GetDevice)},
	    {"libusb_get_configuration", Sym(&GetConfiguration)},
	    {"libusb_set_configuration", Sym(&SetConfiguration)},
	    {"libusb_claim_interface", Sym(&Claim)},
	    {"libusb_release_interface", Sym(&Release)},
	    {"libusb_set_interface_alt_setting", Sym(&AltSetting)},
	    {"libusb_clear_halt", Sym(&ClearHalt)},
	    {"libusb_reset_device", Sym(&Reset)},
	    {"libusb_kernel_driver_active", Sym(&KernelDriverActive)},
	    {"libusb_detach_kernel_driver", Sym(&Detach)},
	    {"libusb_control_transfer", Sym(&Control)},
	    {"libusb_bulk_transfer", Sym(&Bulk)},
	    {"libusb_interrupt_transfer", Sym(&Interrupt)},
	    {"libusb_alloc_transfer", Sym(&Alloc)},
	    {"libusb_free_transfer", Sym(&Free)},
	    {"libusb_submit_transfer", Sym(&Submit)},
	    {"libusb_cancel_transfer", Sym(&Cancel)},
	    {"libusb_handle_events_timeout_completed", Sym(&HandleEvents)},
	};
	const auto found = table.find(name);
	return found != table.end() ? found->second : nullptr;
}

// The parent and the no-host children: any lookup at all would mean libusb was being loaded.
void* CountingSymbols(const char* /*name*/) {
	g_lookups++;
	return nullptr;
}

} // namespace fakeusb

// ---- child runs: the allow-list is read once per process, so each list gets its own run of this binary ---------------
std::string g_self;

std::string SelfPath(const char* argv0) {
	std::error_code ec;
#ifndef _WIN32
	const auto link = std::filesystem::read_symlink("/proc/self/exe", ec);
	if (!ec) {
		return link.string();
	}
#endif
	const auto path = std::filesystem::absolute(argv0, ec);
	return ec ? std::string(argv0) : path.string();
}

void SetEnv(const char* name, const char* value) {
#ifdef _WIN32
	_putenv_s(name, value);
#else
	setenv(name, value, 1);
#endif
}

void UnsetEnv(const char* name) {
#ifdef _WIN32
	_putenv_s(name, "");
#else
	unsetenv(name);
#endif
}

int RunChild(const char* name, const char* allow) {
	SetEnv("KYTY_BC5_USBD_ALLOW", allow);
	const std::string command = "\"" + g_self + "\" child " + name;
	std::fflush(stdout);
	std::fflush(stderr);
	const int status = std::system(command.c_str());
	UnsetEnv("KYTY_BC5_USBD_ALLOW");
#ifdef _WIN32
	return status;
#else
	return WIFEXITED(status) ? WEXITSTATUS(status) : 128;
#endif
}

void CaseChild(const char* name, const char* allow, const char* what) {
	SetCase(std::string("child ") + name);
	const int code = RunChild(name, allow);
	Report(Fmt("child %s (KYTY_BC5_USBD_ALLOW=\"%s\"): %s", name, allow, what), code == 0, Fmt("its exit %d", code));
}

constexpr const char* kFakeAllow = " 1234:5678, 1234:0003,1234:0001,ABCD:ef01,1234:0007,054c:0ce6,054C:05C4,,";

// The parent, after all its calls: the loader hook was never asked for a symbol.
void CaseNeverLoaded() {
	SetCase("never loaded");
	Checks c;
	c.Eq("symbol lookups through the stand-in loader hook", fakeusb::g_lookups, 0);
	Done("no allow-list: libusb never loaded (the stand-in loader hook was asked for no symbol, no device call made)", c);
}

// The children "bad", "sony" and "offlisted": no host access.
void CaseNoHost() {
	SetCase("no host");
	FillAll();
	Checks c;
	c.Eq("Init", Fn<I0>("sceUsbdInit")(), 0);
	void** list = reinterpret_cast<void**>(U(g_out));
	c.Eq("GetDeviceList", Fn<LList>("sceUsbdGetDeviceList")(&list), 0);
	c.True(g_on ? "the empty list" : "the output left as it was",
	       g_on ? list != reinterpret_cast<void**>(U(g_out)) && list != nullptr && list[0] == nullptr
	            : list == reinterpret_cast<void**>(U(g_out)));
	c.Eq("OpenDeviceWithVidPid(1234:5678)", static_cast<int64_t>(Fn<QU16>("sceUsbdOpenDeviceWithVidPid")(0x1234, 0x5678)), 0);
	c.Eq("OpenDeviceWithVidPid(054c:0ce6)", static_cast<int64_t>(Fn<QU16>("sceUsbdOpenDeviceWithVidPid")(0x054C, 0x0CE6)), 0);
	c.Eq("Exit", Fn<I0>("sceUsbdExit")(), 0);
	c.Eq("symbol lookups through the stand-in loader hook", fakeusb::g_lookups, 0);
	c.True("nothing written", AllUntouched());
	Done(Fmt("%s: libusb never loaded, no device, Init/Exit 0, nothing opened", g_child.c_str()), c);
}

// ---- the child "fake": the transport over the fake libusb ------------------------------------------------------------
constexpr int kOther = static_cast<int>(0x802400FFu);
constexpr int kBusy  = static_cast<int>(0x80240006u);

void*            g_handle = nullptr;
void**           g_list   = nullptr;
std::atomic<int> g_callbacks {0};
void*            g_callback_transfer = nullptr;
uint8_t          g_user_data;

void KYTY_SYSV_ABI GuestCallback(void* transfer) {
	g_callbacks++;
	g_callback_transfer = transfer;
}

void* D(int i) {
	return &fakeusb::g_devs[i];
}

void FakeLoader() {
	SetCase("fake: loader");
	Checks c;
	c.Eq("lookups before Init", fakeusb::g_lookups, 0);
	c.Eq("Init", Fn<I0>("sceUsbdInit")(), 0);
	c.Eq("the 34 libusb symbols, each looked up once", fakeusb::g_lookups, 34);
	c.Eq("libusb_init once", fakeusb::g_inits, 1);
	c.Eq("Init again", Fn<I0>("sceUsbdInit")(), 0);
	c.Eq("... no second context", fakeusb::g_inits, 1);
	c.Eq("... no second load", fakeusb::g_lookups, 34);
	Done("fake: the first Init loads libusb through the hook (34 symbols) and makes one context", c);
}

void FakeList() {
	SetCase("fake: device list");
	Checks        c;
	const int64_t n = Fn<LList>("sceUsbdGetDeviceList")(&g_list);
	c.Eq("GetDeviceList: one device", n, 1);
	c.True("the vendor-class 1234:5678, then null", g_list != nullptr && g_list[0] == D(0) && g_list[1] == nullptr);
	c.Eq("its one reference (the list's)", fakeusb::g_devs[0].refs, 1);
	bool others = true;
	for (int i = 1; i < fakeusb::kDevs; i++) {
		others = others && fakeusb::g_devs[i].refs == 0 && fakeusb::g_devs[i].opens == 0;
	}
	c.True("the other six: no reference kept, not opened", others);
	c.Eq("configurations read by the gate (the three listed non-HID-class devices)", fakeusb::g_config_gets, 3);
	c.Eq("... each freed", fakeusb::g_config_frees, 3);
	Done("fake: the list holds only the admitted device (not HID 1234:0003, audio 1234:0001, unreadable abcd:ef01, "
	     "HID-class 1234:0007, DualSense 054c:0ce6, unlisted 9999:9999)",
	     c);
}

void FakeQueries() {
	SetCase("fake: device queries");
	Checks  c;
	uint8_t desc[18];
	std::memset(desc, kFill, sizeof(desc));
	auto get_desc = Fn<IPPV>("sceUsbdGetDeviceDescriptor");
	c.Eq("GetDeviceDescriptor", get_desc(D(0), desc), 0);
	c.True("... its ids", At<uint16_t>(desc, 8) == 0x1234 && At<uint16_t>(desc, 10) == 0x5678);
	c.Eq("GetBusNumber", Fn<IP>("sceUsbdGetBusNumber")(D(0)), 3);
	c.Eq("GetDeviceAddress", Fn<IP>("sceUsbdGetDeviceAddress")(D(0)), 7);
	c.Eq("GetDeviceSpeed: high", Fn<IP>("sceUsbdGetDeviceSpeed")(D(0)), 3);
	fakeusb::g_speed = 5;
	c.Eq("GetDeviceSpeed: super-plus answered as super", Fn<IP>("sceUsbdGetDeviceSpeed")(D(0)), 4);
	fakeusb::g_speed = 3;
	auto max_packet = Fn<IPU8>("sceUsbdGetMaxPacketSize");
	auto max_iso    = Fn<IPU8>("sceUsbdGetMaxIsoPacketSize");
	c.Eq("GetMaxPacketSize(0x81)", max_packet(D(0), 0x81), 64);
	c.Eq("GetMaxPacketSize(0x02)", max_packet(D(0), 0x02), 512);
	c.Eq("GetMaxPacketSize(0x05): NOT_FOUND", max_packet(D(0), 0x05), kNotFound);
	c.Eq("GetMaxIsoPacketSize(0x83), high speed: 1024 x 3", max_iso(D(0), 0x83), 3072);
	fakeusb::g_speed = 2;
	c.Eq("GetMaxIsoPacketSize(0x83), full speed: as reported", max_iso(D(0), 0x83), 0x1400);
	fakeusb::g_speed = 3;
	std::memset(desc, kFill, sizeof(desc));
	c.Eq("GetDeviceDescriptor(the HID device): never handed out, today's 0", get_desc(D(1), desc), 0);
	c.True("... nothing written", Untouched(desc, sizeof(desc)));
	c.Eq("GetBusNumber(the audio device): today's 0", Fn<IP>("sceUsbdGetBusNumber")(D(2)), 0);
	c.Eq("configurations read = freed", fakeusb::g_config_gets, fakeusb::g_config_frees);
	Done("fake: descriptor, bus, address, speed (capped at super), packet sizes (iso scaled above full speed); a refused "
	     "device gets no answer",
	     c);
}

void FakeConfigs() {
	SetCase("fake: configurations");
	Checks c;
	auto   active   = Fn<IPP>("sceUsbdGetActiveConfigDescriptor");
	auto   by_index = Fn<IPU8P>("sceUsbdGetConfigDescriptor");
	auto   by_value = Fn<IPU8P>("sceUsbdGetConfigDescriptorByValue");
	auto   release  = Fn<IP>("sceUsbdFreeConfigDescriptor");
	void*  a        = nullptr;
	void*  b        = nullptr;
	void*  v        = nullptr;
	void*  none     = g_out;
	c.Eq("GetActiveConfigDescriptor", active(D(0), &a), 0);
	c.True("... the host's descriptor", a != nullptr && static_cast<fakeusb::Config*>(a)->bNumInterfaces == 1);
	c.Eq("GetConfigDescriptor(0)", by_index(D(0), 0, &b), 0);
	c.Eq("GetConfigDescriptor(1): NOT_FOUND", by_index(D(0), 1, &none), kNotFound);
	c.True("... null written", none == nullptr);
	c.Eq("GetConfigDescriptorByValue(1)", by_value(D(0), 1, &v), 0);
	const int frees = fakeusb::g_config_frees;
	c.Eq("FreeConfigDescriptor", release(a), 0);
	c.Eq("FreeConfigDescriptor", release(b), 0);
	c.Eq("FreeConfigDescriptor", release(v), 0);
	c.Eq("... three freed", fakeusb::g_config_frees - frees, 3);
	c.Eq("FreeConfigDescriptor again: no answer upstream", release(a), 0);
	c.Eq("... not freed twice", fakeusb::g_config_frees - frees, 3);
	void* refused = g_out;
	c.Eq("GetActiveConfigDescriptor(the audio device): today's 0", active(D(2), &refused), 0);
	c.True("... nothing written", refused == g_out);
	c.Eq("configurations read = freed", fakeusb::g_config_gets, fakeusb::g_config_frees);
	Done("fake: configuration descriptors handed out and freed once each", c);
}

void FakeRefs() {
	SetCase("fake: references");
	Checks c;
	c.Eq("RefDevice", static_cast<int64_t>(Fn<QP>("sceUsbdRefDevice")(D(0))), static_cast<int64_t>(U(D(0))));
	c.Eq("... two references", fakeusb::g_devs[0].refs, 2);
	c.Eq("UnrefDevice", Fn<IP>("sceUsbdUnrefDevice")(D(0)), 0);
	c.Eq("... one", fakeusb::g_devs[0].refs, 1);
	c.Eq("RefDevice(the HID device): today's 0", static_cast<int64_t>(Fn<QP>("sceUsbdRefDevice")(D(1))), 0);
	c.Eq("UnrefDevice(the HID device): today's 0", Fn<IP>("sceUsbdUnrefDevice")(D(1)), 0);
	c.Eq("... its references untouched", fakeusb::g_devs[1].refs, 0);
	Done("fake: RefDevice and UnrefDevice for the admitted device only", c);
}

void FakeHandle() {
	SetCase("fake: handle calls");
	Checks c;
	void*  h = g_out;
	c.Eq("Open", Fn<IPP>("sceUsbdOpen")(D(0), &h), 0);
	c.True("... a handle", h != nullptr && h != g_out);
	g_handle = h;
	c.Eq("... opened once", fakeusb::g_devs[0].opens, 1);
	c.Eq("GetDevice", static_cast<int64_t>(Fn<QP>("sceUsbdGetDevice")(h)), static_cast<int64_t>(U(D(0))));
	int32_t config = -1;
	c.Eq("GetConfiguration", Fn<IPPI>("sceUsbdGetConfiguration")(h, &config), 0);
	c.Eq("... 1", config, 1);
	c.Eq("SetConfiguration(1)", Fn<IPI>("sceUsbdSetConfiguration")(h, 1), 0);
	c.Eq("CheckConnected", Fn<IP>("sceUsbdCheckConnected")(h), 0);
	fakeusb::g_gone = true;
	c.Eq("CheckConnected, the device gone: NO_DEVICE", Fn<IP>("sceUsbdCheckConnected")(h), kNoDevice);
	fakeusb::g_gone = false;
	auto alt = Fn<IPII>("sceUsbdSetInterfaceAltSetting");
	c.Eq("ClaimInterface(0)", Fn<IPI>("sceUsbdClaimInterface")(h, 0), 0);
	c.Eq("SetInterfaceAltSetting(0, 1)", alt(h, 0, 1), 0);
	c.Eq("... passed to libusb", fakeusb::g_alt_calls, 1);
	c.Eq("SetInterfaceAltSetting(1, 0): not claimed", alt(h, 1, 0), kNotFound);
	c.Eq("SetInterfaceAltSetting(40, 0)", alt(h, 40, 0), kInvArg);
	c.Eq("KernelDriverActive(0)", Fn<IPI>("sceUsbdKernelDriverActive")(h, 0), 1);
	c.Eq("DetachKernelDriver(0)", Fn<IPI>("sceUsbdDetachKernelDriver")(h, 0), 0);
	c.Eq("... detached once", fakeusb::g_devs[0].detaches, 1);
	c.Eq("AttachKernelDriver(0): FreeBSD's 0", Fn<IPI>("sceUsbdAttachKernelDriver")(h, 0), 0);
	c.Eq("ReleaseInterface(0)", Fn<IPI>("sceUsbdReleaseInterface")(h, 0), 0);
	c.Eq("SetInterfaceAltSetting(0, 1) after the release: not claimed", alt(h, 0, 1), kNotFound);
	c.Eq("... libusb not asked again", fakeusb::g_alt_calls, 1);
	auto halt = Fn<IPU8>("sceUsbdClearHalt");
	c.Eq("ClearHalt(0x81)", halt(h, 0x81), 0);
	c.Eq("ClearHalt(0x05): not found answered OTHER", halt(h, 0x05), kOther);
	c.Eq("ClearHalt(0x06): a pipe error, no answer upstream", halt(h, 0x06), 0);
	c.Eq("ResetDevice", Fn<IP>("sceUsbdResetDevice")(h), 0);
	c.Eq("... reset once", fakeusb::g_resets, 1);
	c.Eq("claims of the admitted device", fakeusb::g_devs[0].claims, 1);
	Done("fake: Open, GetDevice, configuration, CheckConnected, claim/release, alternate setting, kernel driver, halt, "
	     "reset",
	     c);
}

void FakeControl() {
	SetCase("fake: control and descriptors");
	Checks c;
	void*  h = g_handle;
	c.Eq("ControlTransfer(no data)", Fn<ICtl>("sceUsbdControlTransfer")(h, 0x40, 9, 1, 0, nullptr, 0, 50), 0);
	const auto& a = fakeusb::g_control;
	c.True("... passed as given", a.request_type == 0x40 && a.request == 9 && a.value == 1 && a.index == 0 &&
	                                  a.length == 0 && a.timeout == 50);
	uint8_t buf[64];
	std::memset(buf, kFill, sizeof(buf));
	c.Eq("GetDescriptor(device, 18 bytes)", Fn<IDesc>("sceUsbdGetDescriptor")(h, 1, 0, buf, 18), 18);
	c.True("... GET_DESCRIPTOR IN, value 0x0100, index 0, 18 bytes, 1000 ms", a.request_type == 0x80 && a.request == 6 &&
	                                                                            a.value == 0x0100 && a.index == 0 &&
	                                                                            a.length == 18 && a.timeout == 1000);
	c.Eq("GetStringDescriptor(2, 0x0409, 100000 bytes)", Fn<IStr>("sceUsbdGetStringDescriptor")(h, 2, 0x0409, buf, 100000),
	     14);
	c.True("... value 0x0302, index 0x0409, the length cut to 65535", a.value == 0x0302 && a.index == 0x0409 &&
	                                                                     a.length == 65535);
	uint8_t text[16];
	std::memset(text, kFill, sizeof(text));
	auto ascii = Fn<IStrA>("sceUsbdGetStringDescriptorAscii");
	c.Eq("GetStringDescriptorAscii(2, 16)", ascii(h, 2, text, 16), 3);
	c.True("... \"Hi!\": '<', '>' and a control character dropped", std::memcmp(text, "Hi!", 4) == 0);
	c.Eq("GetStringDescriptorAscii(2, 3)", ascii(h, 2, text, 3), 2);
	c.True("... \"Hi\"", std::memcmp(text, "Hi", 3) == 0);
	Done("fake: ControlTransfer, GetDescriptor, GetStringDescriptor, GetStringDescriptorAscii", c);
}

void FakeSync() {
	SetCase("fake: bulk and interrupt");
	Checks  c;
	int32_t n = -1;
	c.Eq("BulkTransfer(8)", Fn<ISync>("sceUsbdBulkTransfer")(g_handle, 0x81, g_data, 8, &n, 100), 0);
	c.Eq("... 8 transferred", n, 8);
	c.Eq("InterruptTransfer: TIMEOUT", Fn<ISync>("sceUsbdInterruptTransfer")(g_handle, 0x81, g_data, 8, &n, 100), kTimeout);
	c.Eq("... 0 transferred", n, 0);
	Done("fake: BulkTransfer and InterruptTransfer, their counts and codes", c);
}

void FakeAsync() {
	SetCase("fake: submitted transfers");
	Checks   c;
	auto     alloc  = Fn<QI>("sceUsbdAllocTransfer");
	auto     freet  = Fn<IP>("sceUsbdFreeTransfer");
	auto     submit = Fn<IP>("sceUsbdSubmitTransfer");
	auto     cancel = Fn<IP>("sceUsbdCancelTransfer");
	auto     handle = Fn<ITv>("sceUsbdHandleEventsTimeout");
	void*    cb     = reinterpret_cast<void*>(&GuestCallback);
	const Tv ms1 {0, 1000};
	void*    t = reinterpret_cast<void*>(alloc(0));
	c.Eq("FillBulkTransfer", Fn<IFill>("sceUsbdFillBulkTransfer")(t, g_handle, 0x82, g_data, 16, cb, &g_user_data, 100), 0);
	c.Eq("SubmitTransfer", submit(t), 0);
	c.Eq("... submitted once", fakeusb::g_submits, 1);
	const fakeusb::Transfer* host = fakeusb::g_pending.empty() ? nullptr : fakeusb::g_pending[0];
	c.True("... the host copy: handle, endpoint, type, length, timeout, buffer, the title's transfer",
	       host != nullptr && host->dev_handle == g_handle && host->endpoint == 0x82 && host->type == 2 &&
	           host->length == 16 && host->timeout == 100 && host->buffer == g_data && host->user_data == t);
	const int frees = fakeusb::g_frees;
	c.Eq("SubmitTransfer again: BUSY", submit(t), kBusy);
	c.Eq("... its copy freed", fakeusb::g_frees - frees, 1);
	c.Eq("... nothing more submitted", fakeusb::g_submits, 1);
	c.Eq("FreeTransfer in flight: no answer upstream", freet(t), 0);
	c.Eq("CancelTransfer", cancel(t), 0);
	c.Eq("... cancelled once", fakeusb::g_cancels, 1);
	c.Eq("HandleEventsTimeout: it completes", handle(&ms1), 0);
	c.Eq("... the title's callback ran once", g_callbacks.load(), 1);
	c.True("... with the title's transfer", g_callback_transfer == t);
	c.Eq("... status: cancelled (3)", At<int32_t>(t, 16), 3);
	c.Eq("... actual length", At<int32_t>(t, 24), 16);
	c.Eq("CancelTransfer after it completed: NOT_FOUND", cancel(t), kNotFound);
	Put<uint8_t>(t, 8, 2); // libusb's FREE_BUFFER
	c.Eq("SubmitTransfer, flags 2: no answer upstream", submit(t), 0);
	c.Eq("... nothing submitted", fakeusb::g_submits, 1);
	Put<uint8_t>(t, 8, 1); // SHORT_NOT_OK
	c.Eq("SubmitTransfer, flags 1", submit(t), 0);
	c.Eq("HandleEvents (no timeout): returns once it completes", Fn<I0>("sceUsbdHandleEvents")(), 0);
	c.Eq("... the callback ran again", g_callbacks.load(), 2);
	c.Eq("... status: completed (0)", At<int32_t>(t, 16), 0);
	c.Eq("FreeTransfer", freet(t), 0);
	void* ti = reinterpret_cast<void*>(alloc(2));
	c.Eq("FillIsoTransfer(2 packets)", Fn<IFillI>("sceUsbdFillIsoTransfer")(ti, g_handle, 0x83, g_data, 64, 2, cb, nullptr, 0),
	     0);
	c.Eq("SetIsoPacketLengths(32)", Fn<IPU32>("sceUsbdSetIsoPacketLengths")(ti, 32), 0);
	c.Eq("SubmitTransfer(iso)", submit(ti), 0);
	fakeusb::Transfer* iso = fakeusb::g_pending.empty() ? nullptr : fakeusb::g_pending[0];
	c.True("... the host copy: type 1, two packets of 32", iso != nullptr && iso->type == 1 && iso->num_iso_packets == 2 &&
	                                                           fakeusb::IsoAt(iso, 0, 0) == 32 &&
	                                                           fakeusb::IsoAt(iso, 1, 0) == 32);
	c.Eq("HandleEventsTimeout", handle(&ms1), 0);
	c.True("... the packets' results copied back", At<uint32_t>(ti, 64) == 32 && At<uint32_t>(ti, 76) == 32 &&
	                                                   At<int32_t>(ti, 68) == 0 && At<int32_t>(ti, 80) == 0);
	c.Eq("... callbacks", g_callbacks.load(), 3);
	c.Eq("FreeTransfer(iso)", freet(ti), 0);
	c.Eq("host transfers allocated = freed", fakeusb::g_allocs, fakeusb::g_frees);
	Done("fake: submit, busy, cancel, completion through HandleEventsTimeout and HandleEvents with the title's callback, "
	     "flags, iso packets",
	     c);
}

void FakeCloseAndVidPid() {
	SetCase("fake: close and open by id");
	Checks c;
	auto   usbd_close = Fn<IP>("sceUsbdClose");
	auto   getdev = Fn<QP>("sceUsbdGetDevice");
	auto   vidpid = Fn<QU16>("sceUsbdOpenDeviceWithVidPid");
	c.Eq("Close", usbd_close(g_handle), 0);
	c.Eq("... closed once", fakeusb::g_closes, 1);
	c.Eq("GetDevice(the closed handle): today's 0", static_cast<int64_t>(getdev(g_handle)), 0);
	c.Eq("Close again: no answer upstream", usbd_close(g_handle), 0);
	c.Eq("... not closed twice", fakeusb::g_closes, 1);
	const int      lists = fakeusb::g_lists;
	const uint64_t h     = vidpid(0x1234, 0x5678);
	c.True("OpenDeviceWithVidPid(1234:5678): a handle", h != 0);
	c.Eq("... the device opened again", fakeusb::g_devs[0].opens, 2);
	c.Eq("GetDevice(it)", static_cast<int64_t>(getdev(reinterpret_cast<void*>(h))), static_cast<int64_t>(U(D(0))));
	c.Eq("OpenDeviceWithVidPid(1234:0003): the HID device is refused", static_cast<int64_t>(vidpid(0x1234, 0x0003)), 0);
	c.Eq("... not opened", fakeusb::g_devs[1].opens, 0);
	c.Eq("... two enumerations so far", fakeusb::g_lists - lists, 2);
	c.Eq("OpenDeviceWithVidPid(054c:0ce6): not listed", static_cast<int64_t>(vidpid(0x054C, 0x0CE6)), 0);
	c.Eq("OpenDeviceWithVidPid(9999:9999): not listed", static_cast<int64_t>(vidpid(0x9999, 0x9999)), 0);
	c.Eq("... no enumeration for them", fakeusb::g_lists - lists, 2);
	Done("fake: Close once; OpenDeviceWithVidPid opens the admitted id only, never a refused or unlisted one", c);
}

void FakeExit() {
	SetCase("fake: free and exit");
	Checks c;
	c.Eq("FreeDeviceList(unref)", Fn<IFree>("sceUsbdFreeDeviceList")(g_list, 1), 0);
	c.Eq("... the device's references back to 0", fakeusb::g_devs[0].refs, 0);
	auto usbd_exit = Fn<I0>("sceUsbdExit");
	c.Eq("Exit (one of two Inits)", usbd_exit(), 0);
	c.Eq("... no libusb_exit yet", fakeusb::g_exits, 0);
	c.Eq("... the open-by-id handle still open", fakeusb::g_open_handles, 1);
	c.Eq("Exit (the last)", usbd_exit(), 0);
	c.Eq("... libusb_exit once", fakeusb::g_exits, 1);
	c.Eq("... the open-by-id handle closed", fakeusb::g_open_handles, 0);
	c.Eq("Exit again", usbd_exit(), 0);
	c.Eq("... still once", fakeusb::g_exits, 1);
	void**    list  = nullptr;
	const int lists = fakeusb::g_lists;
	c.Eq("GetDeviceList after the last Exit", Fn<LList>("sceUsbdGetDeviceList")(&list), 0);
	c.True("... the empty list (no context)", list != nullptr && list[0] == nullptr);
	c.Eq("... no enumeration", fakeusb::g_lists, lists);
	Done("fake: FreeDeviceList unrefs; the last Exit closes what is open and ends the context", c);
}

void FakeNeverTouched() {
	SetCase("fake: refused devices untouched");
	Checks c;
	bool   untouched = true;
	bool   released  = true;
	for (int i = 0; i < fakeusb::kDevs; i++) {
		const auto& d = fakeusb::g_devs[i];
		if (i != 0) {
			untouched = untouched && d.opens == 0 && d.claims == 0 && d.detaches == 0;
		}
		released = released && d.refs == 0;
	}
	c.True("HID, audio, unreadable, HID-class, DualSense and unlisted: never opened, claimed or detached", untouched);
	c.True("every reference released", released);
	c.Eq("configurations read = freed", fakeusb::g_config_gets, fakeusb::g_config_frees);
	c.Eq("open handles", fakeusb::g_open_handles, 0);
	Done("fake: no refused device was ever opened, claimed or detached; nothing left held", c);
}

} // namespace tus0405

int main(int argc, char** argv) {
	using namespace tus0405;
	const bool  on   = SwitchOn("KYTY_BC5_LOAD_USBD");
	const char* mode = on ? "on" : "off";
	if (argc == 3 && std::strcmp(argv[1], "child") == 0) {
		g_child  = argv[2];
		g_prefix = "[child " + g_child + "] ";
	} else if (argc > 2 || (argc == 2 && std::strcmp(argv[1], mode) != 0)) {
		std::printf("tus0405: the argument says %s but the switch says %s\n", argc == 2 ? argv[1] : "too much", mode);
		return 2;
	}
	g_on   = on;
	g_self = SelfPath(argv[0]);
	if (!g_child.empty() && g_child != "fake" && g_child != "bad" && g_child != "sony" && g_child != "offlisted") {
		SetupFail("no child run named " + g_child);
	}
	// The loader hook: the fake libusb for the child "fake"; elsewhere a counter that must stay at 0.
	Libs::LibUsbd::bc5_usb_symbols_for_test = g_child == "fake" ? fakeusb::Symbols : fakeusb::CountingSymbols;
	if (g_child.empty()) {
		UnsetEnv("KYTY_BC5_USBD_ALLOW"); // the parent runs with no allow-list
	}
	fakeusb::Setup();
	std::printf("tus0405: %sswitch usbd %d: %s\n", g_prefix.c_str(), on ? 1 : 0, mode);
	std::fflush(stdout);
	std::thread(Watchdog).detach();

	SetCase("init: registration");
	Libs::LibUsbd::InitUsbd_1(&g_db); // prints its "[bc5] exp 0405: usbd port on|off" line (and, on, the allow-list's)

	if (g_child.empty()) {
		CaseRegistration();
		CaseMatch();
		CaseDeviceList();
		CaseAllocFree();
		CaseFill();
		CaseControlAndIso();
		CaseCancelSubmit();
		CaseHandleCalls();
		CaseEventsOneThread();
		CaseEventsWake();
		CaseEventsWaiterTimeout();
		CaseEventsTimeoutAsWaiter();
		CaseEventsTryLockOther();
		CaseHeld();
		if (g_on) {
			CaseChild("bad", "1234:5678,12345:678", "a malformed list is refused whole: no libusb, no device");
			CaseChild("sony", "054c:0ce6, 054C:05C4,054c:09cc,054c:0ba0,054c:0df2",
			          "Sony's controller ids are dropped: no libusb, no device");
			CaseChild("fake", kFakeAllow, "the transport over a fake libusb; refused devices never touched");
		} else {
			CaseChild("offlisted", "1234:5678", "the switch off ignores the list: no libusb, today's answers");
		}
		CaseNeverLoaded();
		CaseHandleEventsForever();
	} else if (g_child == "fake") {
		if (!g_on) {
			SetupFail("the child fake needs the switch on");
		}
		FakeLoader();
		FakeList();
		FakeQueries();
		FakeConfigs();
		FakeRefs();
		FakeHandle();
		FakeControl();
		FakeSync();
		FakeAsync();
		FakeCloseAndVidPid();
		FakeExit();
		FakeNeverTouched();
	} else {
		CaseNoHost();
	}

	const int   n     = g_cases.load();
	const int   p     = g_passed.load();
	const char* label = g_child.empty() ? mode : "";
	if (p != n) {
		std::printf("tus0405: %s%s%s%d of %d passed; FAIL\n", g_prefix.c_str(), label, g_child.empty() ? " " : "", p, n);
		std::fflush(stdout);
		std::_Exit(1);
	}
	std::printf("tus0405: %s%s%s%d of %d; end\n", g_prefix.c_str(), label, g_child.empty() ? " " : "", p, n);
	std::fflush(stdout);
	std::_Exit(0);
}
