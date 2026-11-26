#!/usr/bin/env python3
# BC5 experiment 0329: the second title's remaining 61 missing imports (exp 0328's link-time list), implemented the way
# the console behaves (no return-0 stubs), on top of exp 0327's twelve and exp 0328's NpCppWebApi port, in the tree
# ~/src/KytyPlus (f266548 + patch 0001) as the box has it. The EDITS of patch0328.py are kept as they were (the seven
# files of 0327, the libs.cpp registration of 0328) and these are added — see the README's table for the function list:
#   src/libs/libKernel.cpp             posix sleep, fsync, fcntl (variadic), shutdown; libkernel signal (the disposition
#       table), rmdir, sceKernelInternalMemoryGetModuleSegmentInfo (the main program's first segment); sceKernelFsync
#       made real; the five coredump calls (outside a handler: the console's NOT_IN_COREDUMP_HANDLER); sceKernelMlock's NID
#   src/kernel/fileSystem.{h,cpp}      KernelFsync (fflush + fsync(2) on the host file), KernelFcntl (FD_CLOEXEC, the
#       status flags, O_APPEND), a close_on_exec flag on the descriptor
#   src/kernel/memory.{h,cpp}          KernelMlock: the range checked against the virtual ranges, mlock(2) on the host
#   src/libs/libC.cpp                  sceLibcInternalBacktraceForGame: the host's backtrace of the thread on stderr
#   src/libs/network.{h,cpp}           sceHttpReadData over the request's response body (a read position per request)
#   src/libs/libNet.cpp                sceNpGetAccountLanguage2 (signed out), NpSessionSignaling Terminate / Deactivate /
#       DestroyContext (state; no context exists), NpEntitlementAccessAbortRequest (the request registry), NpWebApi2's
#       four push-event calls (no sign-in: NOT_SIGNED_IN; DeleteFilter on the filters CreateFilter handed out)
#   src/libs/libSaveData.cpp           sceSaveDataGetConvertProgress (0.0: none runs), sceSaveDataCancel (none runs)
#   src/libs/audio.{h,cpp}, libAudio.cpp   sceAcmBatchJobPriority: a job recorded in the batch as the library's others
#   src/libs/controller.{h,cpp}, libPad.cpp scePadGetAccessibilityControllerState: handle / pointer checks, state 0
#   src/graphics/presentation/videoOut.{h,cpp}, src/libs/libVideoOut.cpp   WQHD detection, VRR peg / unpeg (recorded
#       on the port), the VideoOutVrrStatus library with AddVrrStatusFlagsPrivilege
#   src/libs/libs.cpp                  the new units registered: libPngEnc.cpp (a real PNG encoder over the vendored
#       zlib), libPlayGoDialog.cpp, libNpCommerceDialog.cpp, libPlayerInvitationDialog.cpp (copied in by build0329.sh and,
#       for the integration, added to the tree beside this patch — src/CMakeLists.txt globs libs/*.cpp)
# usage: patch0329.py <src root of the tree> <out dir>   (python3 on the box; the laptop applies it with apply0327.pl)
import difflib, hashlib, os, sys

EDITS = {
    'src/kernel/syncOnAddress.h': [
        ('''int Wait32(volatile uint32_t* address, uint32_t expected, const uint32_t* timeout_micros,
           signal_poll_func_t signal_poll = nullptr);
''', 1, '''// Experiment 0327: the 8- and 16-bit waits of the PS5 (sceKernelSyncOnAddressWait8 / Wait16).
int Wait8(volatile uint8_t* address, uint8_t expected, const uint32_t* timeout_micros,
          signal_poll_func_t signal_poll = nullptr);
int Wait16(volatile uint16_t* address, uint16_t expected, const uint32_t* timeout_micros,
           signal_poll_func_t signal_poll = nullptr);
int Wait32(volatile uint32_t* address, uint32_t expected, const uint32_t* timeout_micros,
           signal_poll_func_t signal_poll = nullptr);
'''),
    ],
    'src/kernel/syncOnAddress.cpp': [
        ('''[[nodiscard]] bool IsValidWakeAddress(const volatile void* address) {
	return address != nullptr &&
	       (reinterpret_cast<uintptr_t>(address) & (alignof(uint32_t) - 1u)) == 0;
}
''', 1, '''// Experiment 0327: a wake names the address a waiter used, which may be a byte or a half-word
// (sceKernelSyncOnAddressWait8 / Wait16); the console accepts any address here.
[[nodiscard]] bool IsValidWakeAddress(const volatile void* address) {
	return address != nullptr;
}

// Experiment 0327: the futex word that covers an address: the address itself for 32- and 64-bit
// waits (the futex compares the low 32 bits), the containing aligned 32-bit word for narrower ones.
[[nodiscard]] inline volatile uint32_t* FutexWordOf(const volatile void* address) {
	return reinterpret_cast<volatile uint32_t*>(reinterpret_cast<uintptr_t>(address) & ~uintptr_t {3});
}
'''),
        ('''		long result     = 0;
		int  wait_error = 0;
		result          = syscall(SYS_futex, const_cast<T*>(address), FUTEX_WAIT_PRIVATE,
		                          static_cast<uint32_t>(expected), &timeout, nullptr, 0);
''', 1, '''		long result     = 0;
		int  wait_error = 0;
		// Experiment 0327: a narrow wait sleeps on its containing 32-bit word with that word's current
		// value as the futex's expected value; any store into the word, or a wake on any address inside
		// it, ends the sleep, and the loop re-checks the byte / half-word itself.
		uint32_t futex_expected = static_cast<uint32_t>(expected);
		if constexpr (sizeof(T) < sizeof(uint32_t)) {
			futex_expected = __atomic_load_n(FutexWordOf(address), __ATOMIC_ACQUIRE);
			if (ReadWord(address) != expected) {
				return OK;
			}
		}
		result = syscall(SYS_futex, const_cast<uint32_t*>(FutexWordOf(address)), FUTEX_WAIT_PRIVATE,
		                 futex_expected, &timeout, nullptr, 0);
'''),
        ('''	const auto result = syscall(SYS_futex, const_cast<void*>(address), FUTEX_WAKE_PRIVATE, count,
	                            nullptr, nullptr, 0);
	return result < 0 ? KERNEL_ERROR_EINVAL : OK;
''', 1, '''	// Experiment 0327: the wake goes to the aligned word the waiters of this address sleep on
	// (a 32/64-bit wait sleeps on its own address, a byte / half-word wait on the word around it).
	const auto result = syscall(SYS_futex, const_cast<uint32_t*>(FutexWordOf(address)),
	                            FUTEX_WAKE_PRIVATE, count, nullptr, nullptr, 0);
	return result < 0 ? KERNEL_ERROR_EINVAL : OK;
'''),
        ('''int Wait64(volatile uint64_t* address, uint64_t expected, const uint32_t* timeout_micros,
           signal_poll_func_t signal_poll) {
	return WaitImpl(address, expected, timeout_micros, signal_poll);
}
''', 1, '''int Wait64(volatile uint64_t* address, uint64_t expected, const uint32_t* timeout_micros,
           signal_poll_func_t signal_poll) {
	return WaitImpl(address, expected, timeout_micros, signal_poll);
}

// Experiment 0327
int Wait8(volatile uint8_t* address, uint8_t expected, const uint32_t* timeout_micros,
          signal_poll_func_t signal_poll) {
	return WaitImpl(address, expected, timeout_micros, signal_poll);
}

int Wait16(volatile uint16_t* address, uint16_t expected, const uint32_t* timeout_micros,
           signal_poll_func_t signal_poll) {
	return WaitImpl(address, expected, timeout_micros, signal_poll);
}
'''),
    ],
    'src/libs/libKernel.cpp': [
        ('''int KYTY_SYSV_ABI KernelSyncOnAddressWake(volatile void* address, int32_t count) {
	return LibKernel::SyncOnAddress::Wake(address, count);
}
''', 1, '''int KYTY_SYSV_ABI KernelSyncOnAddressWake(volatile void* address, int32_t count) {
	return LibKernel::SyncOnAddress::Wake(address, count);
}

// Experiment 0327: sceKernelSyncOnAddressWait8 / Wait16 — the second title imports both.
int KYTY_SYSV_ABI KernelSyncOnAddressWait8(volatile uint8_t* address, uint8_t expected,
                                           const uint32_t* timeout_micros) {
	static std::atomic_bool logged {false};
	LogExperimentalSyncOnAddress(logged, "sceKernelSyncOnAddressWait8");
	return LibKernel::SyncOnAddress::Wait8(address, expected, timeout_micros,
	                                       LibKernel::KernelDispatchPendingSignalForCurrentThread);
}

int KYTY_SYSV_ABI KernelSyncOnAddressWait16(volatile uint16_t* address, uint16_t expected,
                                            const uint32_t* timeout_micros) {
	static std::atomic_bool logged {false};
	LogExperimentalSyncOnAddress(logged, "sceKernelSyncOnAddressWait16");
	return LibKernel::SyncOnAddress::Wait16(address, expected, timeout_micros,
	                                        LibKernel::KernelDispatchPendingSignalForCurrentThread);
}

// Experiment 0327: getrusage (hHlZQUnlxSM), the FreeBSD layout the PS5 SDK declares: two timevals of
// two int64 each, then fourteen longs. who: RUSAGE_SELF (0), RUSAGE_CHILDREN (-1), RUSAGE_THREAD (1).
struct KernelRusage {
	LibKernel::KernelTimeval ru_utime;
	LibKernel::KernelTimeval ru_stime;
	int64_t                  ru_maxrss;
	int64_t                  ru_ixrss;
	int64_t                  ru_idrss;
	int64_t                  ru_isrss;
	int64_t                  ru_minflt;
	int64_t                  ru_majflt;
	int64_t                  ru_nswap;
	int64_t                  ru_inblock;
	int64_t                  ru_oublock;
	int64_t                  ru_msgsnd;
	int64_t                  ru_msgrcv;
	int64_t                  ru_nsignals;
	int64_t                  ru_nvcsw;
	int64_t                  ru_nivcsw;
};
static_assert(sizeof(KernelRusage) == 144);

int KYTY_SYSV_ABI getrusage(int who, KernelRusage* usage) {
	PRINT_NAME();

	if (who != 0 && who != -1 && who != 1) {
		*GetErrorAddr() = POSIX_EINVAL;
		return -1;
	}
	if (usage == nullptr) {
		*GetErrorAddr() = POSIX_EFAULT;
		return -1;
	}
	*usage = {};
	if (who == -1) { // no children on the console's process
		return 0;
	}
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	struct rusage native {};
	if (::getrusage(who == 0 ? RUSAGE_SELF : RUSAGE_THREAD, &native) != 0) {
		*GetErrorAddr() = POSIX_EINVAL;
		return -1;
	}
	usage->ru_utime.tv_sec  = static_cast<int64_t>(native.ru_utime.tv_sec);
	usage->ru_utime.tv_usec = static_cast<int64_t>(native.ru_utime.tv_usec);
	usage->ru_stime.tv_sec  = static_cast<int64_t>(native.ru_stime.tv_sec);
	usage->ru_stime.tv_usec = static_cast<int64_t>(native.ru_stime.tv_usec);
	usage->ru_maxrss        = static_cast<int64_t>(native.ru_maxrss);
	usage->ru_ixrss         = static_cast<int64_t>(native.ru_ixrss);
	usage->ru_idrss         = static_cast<int64_t>(native.ru_idrss);
	usage->ru_isrss         = static_cast<int64_t>(native.ru_isrss);
	usage->ru_minflt        = static_cast<int64_t>(native.ru_minflt);
	usage->ru_majflt        = static_cast<int64_t>(native.ru_majflt);
	usage->ru_nswap         = static_cast<int64_t>(native.ru_nswap);
	usage->ru_inblock       = static_cast<int64_t>(native.ru_inblock);
	usage->ru_oublock       = static_cast<int64_t>(native.ru_oublock);
	usage->ru_msgsnd        = static_cast<int64_t>(native.ru_msgsnd);
	usage->ru_msgrcv        = static_cast<int64_t>(native.ru_msgrcv);
	usage->ru_nsignals      = static_cast<int64_t>(native.ru_nsignals);
	usage->ru_nvcsw         = static_cast<int64_t>(native.ru_nvcsw);
	usage->ru_nivcsw        = static_cast<int64_t>(native.ru_nivcsw);
#else
	const auto cpu = std::chrono::duration_cast<std::chrono::microseconds>(
	    std::chrono::steady_clock::now().time_since_epoch());
	usage->ru_utime.tv_sec  = cpu.count() / 1000000;
	usage->ru_utime.tv_usec = cpu.count() % 1000000;
#endif
	return 0;
}
'''),
        ('''	LIB_FUNC("q2y-wDIVWZA", Posix::KernelSyncOnAddressWake);
''', 1, '''	LIB_FUNC("q2y-wDIVWZA", Posix::KernelSyncOnAddressWake);
	LIB_FUNC("dFym5b41JLU", Posix::KernelSyncOnAddressWait8);  // experiment 0327
	LIB_FUNC("XgVs4jRehcY", Posix::KernelSyncOnAddressWait16); // experiment 0327
'''),
        ('''	LIB_FUNC("yS8U2TGCe1A", nanosleep);
''', 1, '''	LIB_FUNC("yS8U2TGCe1A", nanosleep);
	LIB_FUNC("hHlZQUnlxSM", getrusage); // experiment 0327
'''),
        ('''	LIB_FUNC("bIHoZCTomsI", LibKernel::PthreadRwlockTrywrlock);
''', 1, '''	LIB_FUNC("bIHoZCTomsI", LibKernel::PthreadRwlockTrywrlock);
	LIB_FUNC("XD3mDeybCnk", LibKernel::PthreadRwlockTryrdlock);   // experiment 0327: scePthreadRwlockTryrdlock
	LIB_FUNC("iPtZRWICjrM", LibKernel::PthreadRwlockTimedrdlock); // experiment 0327
	LIB_FUNC("adh--6nIqTk", LibKernel::PthreadRwlockTimedwrlock); // experiment 0327
'''),
        ('''	LIB_FUNC("52NcYU9+lEo", FileSystem::KernelRename);
''', 1, '''	LIB_FUNC("52NcYU9+lEo", FileSystem::KernelRename);
	LIB_FUNC("WlyEA-sLDf0", FileSystem::KernelTruncate); // experiment 0327
	LIB_FUNC("fgIsQ10xYVA", FileSystem::KernelChmod);    // experiment 0327
	LIB_FUNC("UtszJWHrDcA", FileSystem::KernelFchmod);   // experiment 0327
	LIB_FUNC("0Cq8ipKr9n0", FileSystem::KernelUtimes);   // experiment 0327
'''),
        ('''#include <csignal>
#include <ucontext.h>
''', 1, '''#include <csignal>
#include <sys/resource.h> // experiment 0327: getrusage
#include <ucontext.h>
'''),
        ('''#include <cstddef>
#include <cstdio>
''', 1, '''#include <cstdarg> // experiment 0329: fcntl
#include <cstddef>
#include <cstdio>
'''),
        ('''	usage->ru_utime.tv_usec = cpu.count() % 1000000;
#endif
	return 0;
}
''', 1, '''	usage->ru_utime.tv_usec = cpu.count() % 1000000;
#endif
	return 0;
}

// Experiment 0329: sleep (0wu33hunNdE), posix: the tree's KernelSleep (signal-polled); 0 when the time has passed
// (the tree never interrupts a sleep with a signal, so no remainder is ever returned).
unsigned int KYTY_SYSV_ABI sleep(unsigned int seconds) {
	PRINT_NAME();

	LibKernel::KernelSleep(seconds);
	return 0;
}

// Experiment 0329: fsync (juWbTNM+8hw), posix: the file's writes reach the host's storage (FileSystem::KernelFsync);
// -1/errno — EINVAL on a socket, EBADF on a closed descriptor.
int KYTY_SYSV_ABI fsync(int d) {
	PRINT_NAME();

	if (d >= 0 && Network::Net::IsSocket(d)) {
		*GetErrorAddr() = POSIX_EINVAL;
		return -1;
	}
	return POSIX_CALL(LibKernel::FileSystem::KernelFsync(d));
}

// Experiment 0329: shutdown (TUuiYS2kE8s), posix: the tree's socket shutdown (Net::Shutdown), -1/errno on a failure.
int KYTY_SYSV_ABI shutdown(int s, int how) {
	PRINT_NAME();

	const int result = Network::Net::Shutdown(s, how);
	if (result < 0) {
		*GetErrorAddr() = Network::NetToPosix(result);
		return -1;
	}
	return result;
}

// Experiment 0329: fcntl (8nY19bKoiZk), posix, variadic as the SDK declares it. The commands are the FreeBSD ones
// the console runs (sys/fcntl.h): F_DUPFD 0, F_GETFD 1, F_SETFD 2, F_GETFL 3, F_SETFL 4, F_DUP2FD 10,
// F_DUPFD_CLOEXEC 17; every command but 1 and 3 takes an int. A file descriptor goes to FileSystem::KernelFcntl; a
// socket keeps its descriptor flag (FD_CLOEXEC) in a side table here and its status flags are O_RDWR plus O_NONBLOCK,
// set and cleared through the tree's socket option SO_NBIO (network.cpp: ioctl FIONBIO). The descriptor duplication
// commands have no implementation in this tree (no dup) and fail with EINVAL. -1/errno.
static std::mutex                   g_socket_fcntl_mutex;
static std::unordered_map<int, int> g_socket_fcntl_flags; // bit 0: FD_CLOEXEC, bit 1: O_NONBLOCK

int KYTY_SYSV_ABI fcntl(int d, int cmd, ...) {
	PRINT_NAME();

	constexpr int CMD_DUPFD = 0, CMD_GETFD = 1, CMD_SETFD = 2, CMD_GETFL = 3, CMD_SETFL = 4, CMD_DUP2FD = 10,
	              CMD_DUPFD_CLOEXEC = 17; // the names are macros of the host's <fcntl.h>
	constexpr int FLAG_CLOEXEC = 1, FLAG_RDWR = 2, FLAG_NONBLOCK = 4;
	constexpr int SCE_SOL_SOCKET = 0xffff, SCE_SO_NBIO = 0x1200;

	int arg = 0;
	if (cmd != CMD_GETFD && cmd != CMD_GETFL) {
#if KYTY_PLATFORM == KYTY_PLATFORM_WINDOWS
		__builtin_sysv_va_list args;
		__builtin_sysv_va_start(args, cmd);
		arg = __builtin_va_arg(args, int);
		__builtin_sysv_va_end(args);
#else
		va_list args;
		va_start(args, cmd);
		arg = va_arg(args, int);
		va_end(args);
#endif
	}

	LOGF("\\t fd = %d, cmd = %d, arg = %d\\n", d, cmd, arg);

	if (d < 0) {
		*GetErrorAddr() = POSIX_EBADF;
		return -1;
	}
	if (!Network::Net::IsSocket(d)) {
		return POSIX_N_CALL(LibKernel::FileSystem::KernelFcntl(d, cmd, arg));
	}

	std::lock_guard lock(g_socket_fcntl_mutex);
	int& flags = g_socket_fcntl_flags[d];
	switch (cmd) {
		case CMD_GETFD: return (flags & 1) != 0 ? FLAG_CLOEXEC : 0;
		case CMD_SETFD: flags = (flags & ~1) | ((arg & FLAG_CLOEXEC) != 0 ? 1 : 0); return 0;
		case CMD_GETFL: return FLAG_RDWR | ((flags & 2) != 0 ? FLAG_NONBLOCK : 0);
		case CMD_SETFL: {
			const int enabled = (arg & FLAG_NONBLOCK) != 0 ? 1 : 0;
			const int result  = Network::Net::Setsockopt(d, SCE_SOL_SOCKET, SCE_SO_NBIO, &enabled, sizeof(enabled));
			if (result < 0) {
				*GetErrorAddr() = Network::NetToPosix(result);
				return -1;
			}
			flags = (flags & ~2) | (enabled != 0 ? 2 : 0);
			return 0;
		}
		case CMD_DUPFD:
		case CMD_DUP2FD:
		case CMD_DUPFD_CLOEXEC:
		default:
			LOGF("\\t fcntl command %d on socket %d: not supported by this host\\n", cmd, d);
			*GetErrorAddr() = POSIX_EINVAL;
			return -1;
	}
}
'''),
        ('''	LIB_FUNC("hHlZQUnlxSM", getrusage); // experiment 0327
''', 1, '''	LIB_FUNC("hHlZQUnlxSM", getrusage); // experiment 0327
	LIB_FUNC("0wu33hunNdE", sleep);     // experiment 0329
	LIB_FUNC("juWbTNM+8hw", fsync);     // experiment 0329
	LIB_FUNC("8nY19bKoiZk", fcntl);     // experiment 0329
	LIB_FUNC("TUuiYS2kE8s", shutdown);  // experiment 0329
'''),
        ('''static KYTY_SYSV_ABI int sigprocmask(int /*how*/, const void* /*set*/, void* /*oset*/) {
	// PRINT_NAME();

	// LOGF("\\t how = %d\\n", how);
	// LOGF("\\t set = %016" PRIx64 "\\n", reinterpret_cast<uint64_t>(set));
	// LOGF("\\t oset = %016" PRIx64 "\\n", reinterpret_cast<uint64_t>(oset));

	return 0;
}
''', 1, '''static KYTY_SYSV_ABI int sigprocmask(int /*how*/, const void* /*set*/, void* /*oset*/) {
	// PRINT_NAME();

	// LOGF("\\t how = %d\\n", how);
	// LOGF("\\t set = %016" PRIx64 "\\n", reinterpret_cast<uint64_t>(set));
	// LOGF("\\t oset = %016" PRIx64 "\\n", reinterpret_cast<uint64_t>(oset));

	return 0;
}

// Experiment 0329: signal (VADc3MNQ3cM), libc.prx's import: the guest process's signal dispositions. The handler
// of a signal number is recorded and the previous one returned (SIG_DFL, 0, at first); SIG_ERR (-1) with errno
// EINVAL for a number outside 1..128 (FreeBSD's SIGRTMAX, the kernel the console runs) or a handler on SIGKILL (9)
// or SIGSTOP (17) — the checks of AnyPS5's System/src/Signals.cpp:480. This tree raises no host signal into a
// guest handler (its pending-signal machinery serves the cancellation of its own threads), so a disposition is
// state the title can read back through signal; nothing is installed on the host.
using KernelSignalHandler = KYTY_SYSV_ABI void (*)(int);

static std::mutex                g_signal_mutex;
static std::array<uint64_t, 129> g_signal_dispositions {};

static KYTY_SYSV_ABI KernelSignalHandler signal(int signum, KernelSignalHandler handler) {
	PRINT_NAME();

	constexpr int GUEST_SIGKILL = 9, GUEST_SIGSTOP = 17, GUEST_SIGRTMAX = 128; // FreeBSD's numbers; the names are host macros

	LOGF("\\t signum = %d, handler = 0x%016" PRIx64 "\\n", signum, reinterpret_cast<uint64_t>(handler));

	if (signum < 1 || signum > GUEST_SIGRTMAX ||
	    ((signum == GUEST_SIGKILL || signum == GUEST_SIGSTOP) && handler != nullptr)) {
		*Posix::GetErrorAddr() = Posix::POSIX_EINVAL;
		return reinterpret_cast<KernelSignalHandler>(static_cast<uintptr_t>(-1));
	}

	std::lock_guard lock(g_signal_mutex);
	const auto previous                      = g_signal_dispositions[static_cast<size_t>(signum)];
	g_signal_dispositions[static_cast<size_t>(signum)] = reinterpret_cast<uint64_t>(handler);
	return reinterpret_cast<KernelSignalHandler>(static_cast<uintptr_t>(previous));
}

// Experiment 0329: rmdir (c7ZnT7V1B98), libc.prx's import, posix: the tree's KernelRmdir, -1/errno.
static KYTY_SYSV_ABI int rmdir(const char* path) {
	PRINT_NAME();

	return POSIX_CALL(FileSystem::KernelRmdir(path));
}

// Experiment 0329: sceKernelInternalMemoryGetModuleSegmentInfo (-YTW+qXc3CQ), libc.prx's import: the console's
// libc asks libkernel where the program's first segment lies ({address, size}, AnyPS5 SceTypes.hpp:288, filled from
// the main program's first segment in Module/src/ModuleInfo.cpp:450). Here the first loadable segment of the main
// program — the one that is not a shared object, found through its process parameters — base-relocated. EINVAL
// for a null pointer, ENOENT before the main program is loaded.
struct KernelInternalSegmentInfo {
	uint64_t address;
	uint64_t size;
};
static_assert(sizeof(KernelInternalSegmentInfo) == 16);

static KYTY_SYSV_ABI int KernelInternalMemoryGetModuleSegmentInfo(KernelInternalSegmentInfo* info) {
	PRINT_NAME();

	if (info == nullptr) {
		return KERNEL_ERROR_EINVAL;
	}

	auto* rt      = Common::Singleton<Loader::RuntimeLinker>::Instance(); // NOLINT
	auto* program = rt->FindProgramByAddr(rt->GetProcParam());
	if (program == nullptr || program->elf == nullptr) {
		return KERNEL_ERROR_ENOENT;
	}
	const auto* ehdr = program->elf->GetEhdr();
	const auto* phdr = program->elf->GetPhdr();
	if (ehdr == nullptr || phdr == nullptr) {
		return KERNEL_ERROR_ENOENT;
	}
	for (Loader::Elf64_Half i = 0; i < ehdr->e_phnum; i++) {
		if (phdr[i].p_type == Loader::PT_LOAD && phdr[i].p_memsz != 0) {
			info->address = phdr[i].p_vaddr + program->base_vaddr;
			info->size    = phdr[i].p_memsz;
			LOGF("\\t segment 0 of %s: 0x%016" PRIx64 " + 0x%" PRIx64 "\\n",
			     Common::PathToString(program->file_name).c_str(), info->address, info->size);
			return OK;
		}
	}
	return KERNEL_ERROR_ENOENT;
}
'''),
        ('''	LIB_FUNC("6xVpy0Fdq+I", LibKernel::sigprocmask);
''', 1, '''	LIB_FUNC("6xVpy0Fdq+I", LibKernel::sigprocmask);
	LIB_FUNC("VADc3MNQ3cM", LibKernel::signal);                                     // experiment 0329
	LIB_FUNC("c7ZnT7V1B98", LibKernel::rmdir);                                      // experiment 0329
	LIB_FUNC("-YTW+qXc3CQ", LibKernel::KernelInternalMemoryGetModuleSegmentInfo);  // experiment 0329
'''),
        ('''static int KYTY_SYSV_ABI KernelFsync(int fd) {
	PRINT_NAME();

	LOGF("\\t fd = %d\\n", fd);

	return OK;
}
''', 1, '''// Experiment 0329: sceKernelFsync reaches the host's storage (FileSystem::KernelFsync; it was a no-op).
static int KYTY_SYSV_ABI KernelFsync(int fd) {
	PRINT_NAME();

	LOGF("\\t fd = %d\\n", fd);

	return FileSystem::KernelFsync(fd);
}
'''),
        ('''	LIB_FUNC("rVjRvHJ0X6c", Memory::KernelVirtualQuery);
''', 1, '''	LIB_FUNC("rVjRvHJ0X6c", Memory::KernelVirtualQuery);
	LIB_FUNC("3k6kx-zOOSQ", Memory::KernelMlock); // experiment 0329
'''),
        ('''int KYTY_SYSV_ABI sceCoredumpUnregisterCoredumpHandler() {
	PRINT_NAME();

	g_coredump_handler         = 0;
	g_coredump_handler_context = 0;

	return OK;
}
''', 1, '''int KYTY_SYSV_ABI sceCoredumpUnregisterCoredumpHandler() {
	PRINT_NAME();

	g_coredump_handler         = 0;
	g_coredump_handler_context = 0;

	return OK;
}

// Experiment 0329: the five coredump calls the title makes from its registered handler. The console runs the
// handler while it writes the process's core dump, and these calls only work from inside it: outside, each answers
// SCE_COREDUMP_ERROR_NOT_IN_COREDUMP_HANDLER (0x81180003), an invalid pointer or size SCE_COREDUMP_ERROR_INVALID_ARGUMENT
// (0x81180000) first — the behaviour and the values of AnyPS5's System/src/Coredump.cpp. This host never invokes the
// handler (a host crash is not turned into a guest core dump), so the in-handler flag never turns true and the
// handler-only paths are the console's answers outside a handler. The user data type is an attribute the title sets
// for its later writes; it is kept.
constexpr int COREDUMP_ERROR_INVALID_ARGUMENT        = static_cast<int>(0x81180000u);
constexpr int COREDUMP_ERROR_NOT_IN_COREDUMP_HANDLER = static_cast<int>(0x81180003u);

static thread_local bool  g_in_coredump_handler = false; // true only while a coredump handler runs on this thread
static std::atomic<int>   g_coredump_user_data_type {0};

int KYTY_SYSV_ABI sceCoredumpAttachMemoryRegion(uint32_t user_value, const void* mem, size_t size) {
	PRINT_NAME();

	LOGF("\\t user_value = %u, mem = 0x%016" PRIx64 ", size = 0x%" PRIx64 "\\n", user_value,
	     reinterpret_cast<uint64_t>(mem), static_cast<uint64_t>(size));

	if (mem == nullptr || size == 0 || size > UINTPTR_MAX - reinterpret_cast<uintptr_t>(mem)) {
		return COREDUMP_ERROR_INVALID_ARGUMENT;
	}
	if (!g_in_coredump_handler) {
		return COREDUMP_ERROR_NOT_IN_COREDUMP_HANDLER;
	}
	return OK;
}

int64_t KYTY_SYSV_ABI sceCoredumpWriteUserData(const void* data, size_t size) {
	PRINT_NAME();

	LOGF("\\t data = 0x%016" PRIx64 ", size = 0x%" PRIx64 "\\n", reinterpret_cast<uint64_t>(data),
	     static_cast<uint64_t>(size));

	if (data == nullptr || size == 0 || size > UINTPTR_MAX - reinterpret_cast<uintptr_t>(data)) {
		return COREDUMP_ERROR_INVALID_ARGUMENT;
	}
	if (!g_in_coredump_handler) {
		return COREDUMP_ERROR_NOT_IN_COREDUMP_HANDLER;
	}
	return static_cast<int64_t>(size);
}

int KYTY_SYSV_ABI sceCoredumpGetStopInfoCpu(void* info, size_t size) {
	PRINT_NAME();

	LOGF("\\t info = 0x%016" PRIx64 ", size = 0x%" PRIx64 "\\n", reinterpret_cast<uint64_t>(info),
	     static_cast<uint64_t>(size));

	if (info == nullptr || size != 16 || (reinterpret_cast<uintptr_t>(info) % alignof(uint64_t)) != 0) {
		return COREDUMP_ERROR_INVALID_ARGUMENT;
	}
	if (!g_in_coredump_handler) {
		return COREDUMP_ERROR_NOT_IN_COREDUMP_HANDLER;
	}
	return OK;
}

int KYTY_SYSV_ABI sceCoredumpGetStopInfoGpu_Agc(void* info, size_t size) {
	PRINT_NAME();

	LOGF("\\t info = 0x%016" PRIx64 ", size = 0x%" PRIx64 "\\n", reinterpret_cast<uint64_t>(info),
	     static_cast<uint64_t>(size));

	if (info == nullptr || size == 0) {
		return COREDUMP_ERROR_INVALID_ARGUMENT;
	}
	if (!g_in_coredump_handler) {
		return COREDUMP_ERROR_NOT_IN_COREDUMP_HANDLER;
	}
	return OK;
}

int KYTY_SYSV_ABI sceCoredumpSetUserDataType(int type) {
	PRINT_NAME();

	LOGF("\\t type = %d\\n", type);

	if (type < 0) {
		return COREDUMP_ERROR_INVALID_ARGUMENT;
	}
	g_coredump_user_data_type.store(type, std::memory_order_relaxed);
	return OK;
}
'''),
        ('''	LIB_FUNC("fFkhOgztiCA", Coredump::sceCoredumpUnregisterCoredumpHandler);
''', 1, '''	LIB_FUNC("fFkhOgztiCA", Coredump::sceCoredumpUnregisterCoredumpHandler);
	LIB_FUNC("+YX0z-GUSNw", Coredump::sceCoredumpAttachMemoryRegion); // experiment 0329
	LIB_FUNC("Dbbkj6YHWdo", Coredump::sceCoredumpWriteUserData);      // experiment 0329
	LIB_FUNC("kK0DUW1Ukgc", Coredump::sceCoredumpGetStopInfoCpu);     // experiment 0329
	LIB_FUNC("Jrs7UUkGOFo", Coredump::sceCoredumpGetStopInfoGpu_Agc); // experiment 0329
	LIB_FUNC("Uxqkdta7wEg", Coredump::sceCoredumpSetUserDataType);    // experiment 0329
'''),
    ],
    'src/kernel/fileSystem.h': [
        ('''int KYTY_SYSV_ABI     KernelFtruncate(int d, int64_t length);
''', 1, '''int KYTY_SYSV_ABI     KernelFtruncate(int d, int64_t length);
// Experiment 0327: sceKernelTruncate, sceKernelChmod, sceKernelFchmod, sceKernelUtimes.
int KYTY_SYSV_ABI     KernelTruncate(const char* path, int64_t length);
int KYTY_SYSV_ABI     KernelChmod(const char* path, uint16_t mode);
int KYTY_SYSV_ABI     KernelFchmod(int d, uint16_t mode);
int KYTY_SYSV_ABI     KernelUtimes(const char* path, const LibKernel::KernelTimeval* times);
'''),
        ('''int KYTY_SYSV_ABI     KernelUtimes(const char* path, const LibKernel::KernelTimeval* times);
''', 1, '''int KYTY_SYSV_ABI     KernelUtimes(const char* path, const LibKernel::KernelTimeval* times);
// Experiment 0329: sceKernelFsync / fsync to the host's storage; fcntl on a file descriptor.
int KYTY_SYSV_ABI     KernelFsync(int d);
int KYTY_SYSV_ABI     KernelFcntl(int d, int cmd, int arg);
'''),
    ],
    'src/kernel/fileSystem.cpp': [
        ('''#include "libs/network.h"
''', 1, '''#include "libs/network.h"
#include <cerrno> // experiment 0327
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <fcntl.h>    // experiment 0327: utimensat
#include <sys/stat.h> // experiment 0327
#endif
'''),
        ('''	LOGF("\\tFtruncate (size = %" PRId64 ") file: %s\\n", length,
	     Common::PathToString(file->real_name).c_str());

	return OK;
}
''', 1, '''	LOGF("\\tFtruncate (size = %" PRId64 ") file: %s\\n", length,
	     Common::PathToString(file->real_name).c_str());

	return OK;
}

// Experiment 0327: the path functions the second title imports and the tree lacked. The console's checks
// come first (a null path EFAULT, a relative path EINVAL, a component over 255 or a path over 1023 bytes
// ENAMETOOLONG, the read-only mounts EROFS), then the mount points resolve the host file and the host
// operation runs; a host error is mapped as upstream KytyPlus maps it (Coder787-source, GPL-2.0).
namespace {

int CheckGuestPath(const char* path) {
	if (path == nullptr) {
		return KERNEL_ERROR_EFAULT;
	}
	if (path[0] != '/') {
		return KERNEL_ERROR_EINVAL;
	}
	size_t component_length = 0;
	for (size_t i = 0; path[i] != '\\0'; ++i) {
		if (i >= 1023) {
			return KERNEL_ERROR_ENAMETOOLONG;
		}
		if (path[i] == '/') {
			component_length = 0;
		} else if (++component_length > 255) {
			return KERNEL_ERROR_ENAMETOOLONG;
		}
	}
	return OK;
}

bool IsReadOnlyGuestPath(const std::string& path) {
	return Common::StartsWith(path, "/app0") || Common::StartsWith(path, "/system") ||
	       Common::StartsWith(path, "/hostapp");
}

int KernelErrorFromHost(const std::error_code& error) {
	switch (static_cast<std::errc>(error.default_error_condition().value())) {
		case std::errc::no_such_file_or_directory: return KERNEL_ERROR_ENOENT;
		case std::errc::not_a_directory: return KERNEL_ERROR_ENOTDIR;
		case std::errc::is_a_directory: return KERNEL_ERROR_EISDIR;
		case std::errc::filename_too_long: return KERNEL_ERROR_ENAMETOOLONG;
		case std::errc::permission_denied: return KERNEL_ERROR_EACCES;
		case std::errc::read_only_file_system: return KERNEL_ERROR_EROFS;
		case std::errc::invalid_argument: return KERNEL_ERROR_EINVAL;
		default: return KERNEL_ERROR_EIO;
	}
}

// The host file of a guest path that exists: a regular file or a directory (is_dir says which).
int ResolveExistingGuestPath(const char* path, std::filesystem::path* real_name, bool* is_dir) {
	if (const int check = CheckGuestPath(path); check != OK) {
		return check;
	}
	const std::string path_s(path);
	auto              real_file_name = g_mount_points->GetRealFilename(path_s);
	auto              real_directory = g_mount_points->GetRealDirectory(path_s);
	const bool        dir  = Common::File::IsDirectoryExisting(real_file_name) ||
	                  Common::File::IsDirectoryExisting(real_directory);
	const bool        file = Common::File::IsFileExisting(real_file_name);
	if (!dir && !file) {
		return KERNEL_ERROR_ENOENT;
	}
	*is_dir    = dir && !file;
	*real_name = (*is_dir && !Common::File::IsDirectoryExisting(real_file_name)) ? real_directory
	                                                                              : real_file_name;
	return OK;
}

// The host permissions for a guest mode: the title's bits, with the owner's read and write kept so
// that the host (and the title through it) can still open its own files.
std::filesystem::perms HostPermsFor(uint16_t mode) {
	return static_cast<std::filesystem::perms>((mode & 0777u) | 0600u);
}

} // namespace

int KYTY_SYSV_ABI KernelTruncate(const char* path, int64_t length) {
	PRINT_NAME();

	if (const int check = CheckGuestPath(path); check != OK) {
		return check;
	}
	if (length < 0) {
		return KERNEL_ERROR_EINVAL;
	}
	if (IsReadOnlyGuestPath(path)) {
		return KERNEL_ERROR_EROFS;
	}
	std::filesystem::path real_name;
	bool                  is_dir = false;
	if (const int r = ResolveExistingGuestPath(path, &real_name, &is_dir); r != OK) {
		return r;
	}
	if (is_dir) {
		return KERNEL_ERROR_EISDIR;
	}
	if (auto* open_file = g_files->GetFile(real_name);
	    open_file != nullptr && open_file->opened && !open_file->directory) {
		Common::LockGuard lock(open_file->mutex);
		if (open_file->f.IsInvalid() || !open_file->f.Truncate(static_cast<uint64_t>(length))) {
			return KERNEL_ERROR_EIO;
		}
	} else {
		std::error_code error;
		std::filesystem::resize_file(real_name, static_cast<uint64_t>(length), error);
		if (error) {
			return KernelErrorFromHost(error);
		}
	}

	LOGF("\\tTruncate (size = %" PRId64 ") file: %s\\n", length, Common::PathToString(real_name).c_str());

	return OK;
}

int KYTY_SYSV_ABI KernelChmod(const char* path, uint16_t mode) {
	PRINT_NAME();

	if (const int check = CheckGuestPath(path); check != OK) {
		return check;
	}
	if (IsReadOnlyGuestPath(path)) {
		return KERNEL_ERROR_EROFS;
	}
	std::filesystem::path real_name;
	bool                  is_dir = false;
	if (const int r = ResolveExistingGuestPath(path, &real_name, &is_dir); r != OK) {
		return r;
	}
	std::error_code error;
	std::filesystem::permissions(real_name, HostPermsFor(mode), std::filesystem::perm_options::replace,
	                             error);
	if (error) {
		return KernelErrorFromHost(error);
	}

	LOGF("\\tChmod (mode = 0%o) %s: %s\\n", mode, is_dir ? "directory" : "file",
	     Common::PathToString(real_name).c_str());

	return OK;
}

int KYTY_SYSV_ABI KernelFchmod(int d, uint16_t mode) {
	PRINT_NAME();

	if (d < DESCRIPTOR_MIN) {
		return KERNEL_ERROR_EBADF;
	}
	if (::Libs::Network::Net::IsSocket(d)) {
		return KERNEL_ERROR_EINVAL;
	}
	auto* file = g_files->GetFile(d);
	if (file == nullptr || !file->opened) {
		return KERNEL_ERROR_EBADF;
	}
	if (file->special != SpecialFile::None) {
		return KERNEL_ERROR_EINVAL;
	}
	Common::LockGuard lock(file->mutex);
	std::error_code   error;
	std::filesystem::permissions(file->real_name, HostPermsFor(mode),
	                             std::filesystem::perm_options::replace, error);
	if (error) {
		return KernelErrorFromHost(error);
	}

	LOGF("\\tFchmod (mode = 0%o) file: %s\\n", mode, Common::PathToString(file->real_name).c_str());

	return OK;
}

int KYTY_SYSV_ABI KernelUtimes(const char* path, const LibKernel::KernelTimeval* times) {
	PRINT_NAME();

	if (const int check = CheckGuestPath(path); check != OK) {
		return check;
	}
	if (times != nullptr && (times[0].tv_usec < 0 || times[0].tv_usec >= 1000000 ||
	                         times[1].tv_usec < 0 || times[1].tv_usec >= 1000000)) {
		return KERNEL_ERROR_EINVAL;
	}
	if (IsReadOnlyGuestPath(path)) {
		return KERNEL_ERROR_EROFS;
	}
	std::filesystem::path real_name;
	bool                  is_dir = false;
	if (const int r = ResolveExistingGuestPath(path, &real_name, &is_dir); r != OK) {
		return r;
	}
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	timespec ts[2];
	if (times == nullptr) {
		ts[0].tv_sec = ts[1].tv_sec = 0;
		ts[0].tv_nsec = ts[1].tv_nsec = UTIME_NOW;
	} else {
		for (int i = 0; i < 2; i++) {
			ts[i].tv_sec  = static_cast<time_t>(times[i].tv_sec);
			ts[i].tv_nsec = static_cast<long>(times[i].tv_usec) * 1000L;
		}
	}
	if (::utimensat(AT_FDCWD, Common::PathToString(real_name).c_str(), ts, 0) != 0) {
		const std::error_code error(errno, std::generic_category());
		return KernelErrorFromHost(error);
	}
#else
	std::error_code error;
	const auto      when = (times == nullptr)
	                           ? std::filesystem::file_time_type::clock::now()
	                           : std::filesystem::file_time_type(std::chrono::seconds(times[1].tv_sec) +
	                                                             std::chrono::microseconds(times[1].tv_usec));
	std::filesystem::last_write_time(real_name, when, error);
	if (error) {
		return KernelErrorFromHost(error);
	}
#endif

	LOGF("\\tUtimes %s: %s\\n", times == nullptr ? "(now)" : "(given)", Common::PathToString(real_name).c_str());

	return OK;
}
'''),
        ('''#include <sys/stat.h> // experiment 0327
#endif
''', 1, '''#include <sys/stat.h> // experiment 0327
#include <unistd.h>   // experiment 0329: fsync
#endif
'''),
        ('''	uint64_t                            dents_offset;
};
''', 1, '''	uint64_t                            dents_offset;
	bool                                close_on_exec = false; // experiment 0329: fcntl's FD_CLOEXEC
};
'''),
        ('''	LOGF("\\tUtimes %s: %s\\n", times == nullptr ? "(now)" : "(given)", Common::PathToString(real_name).c_str());

	return OK;
}
''', 1, '''	LOGF("\\tUtimes %s: %s\\n", times == nullptr ? "(now)" : "(given)", Common::PathToString(real_name).c_str());

	return OK;
}

// Experiment 0329: sceKernelFsync / fsync — the file's buffered writes reach the host's storage: the host file's
// stream is flushed, then fsync(2) runs on a second descriptor of the same file (the host file object keeps its
// stream to itself; any descriptor of the file syncs the same inode). A descriptor opened for reading, a
// directory or a special file has nothing of ours to flush and succeeds, as on the console. EBADF for a closed
// descriptor, EINVAL for a socket, the host's error when the sync fails.
int KYTY_SYSV_ABI KernelFsync(int d) {
	PRINT_NAME();

	if (d < DESCRIPTOR_MIN) {
		return KERNEL_ERROR_EBADF;
	}
	if (::Libs::Network::Net::IsSocket(d)) {
		return KERNEL_ERROR_EINVAL;
	}
	auto* file = g_files->GetFile(d);
	if (file == nullptr || !file->opened) {
		return KERNEL_ERROR_EBADF;
	}
	if (!file->writable || file->directory || file->special != SpecialFile::None) {
		return OK;
	}
	Common::LockGuard lock(file->mutex);
	if (file->f.IsInvalid() || !file->f.Flush()) {
		return KERNEL_ERROR_EIO;
	}
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	const int host = ::open(Common::PathToString(file->real_name).c_str(), O_RDONLY | O_CLOEXEC);
	if (host < 0) {
		const std::error_code error(errno, std::generic_category());
		return KernelErrorFromHost(error);
	}
	const int synced = ::fsync(host);
	const int saved  = errno;
	::close(host);
	if (synced != 0) {
		const std::error_code error(saved, std::generic_category());
		return KernelErrorFromHost(error);
	}
#endif

	LOGF("\\tFsync file: %s\\n", Common::PathToString(file->real_name).c_str());

	return OK;
}

// Experiment 0329: fcntl on a file descriptor (the posix wrapper in libKernel.cpp sorts sockets out first). The
// FreeBSD commands and flags the console runs (sys/fcntl.h): F_GETFD (1) / F_SETFD (2) keep FD_CLOEXEC (1) on the
// descriptor; F_GETFL (3) is the access mode (O_RDONLY 0 / O_RDWR 2 — this tree opens a writable file for reading
// too) with O_APPEND (8) and O_SYNC (0x80) as the file was opened; F_SETFL (4) changes O_APPEND, and O_NONBLOCK (4)
// is accepted without effect, as on a regular file. The duplication commands (F_DUPFD 0, F_DUP2FD 10,
// F_DUPFD_CLOEXEC 17) have no implementation in this tree (no dup) and fail with EINVAL. EBADF for a closed
// descriptor, EINVAL for an unknown command; the result of F_GETFD / F_GETFL otherwise.
int KYTY_SYSV_ABI KernelFcntl(int d, int cmd, int arg) {
	PRINT_NAME();

	constexpr int CMD_GETFD = 1, CMD_SETFD = 2, CMD_GETFL = 3, CMD_SETFL = 4; // the names are macros of <fcntl.h>
	constexpr int FLAG_CLOEXEC = 1, FLAG_RDWR = 2, FLAG_APPEND = 8, FLAG_SYNC = 0x80;

	if (d < DESCRIPTOR_MIN) {
		return KERNEL_ERROR_EBADF;
	}
	auto* file = g_files->GetFile(d);
	if (file == nullptr || !file->opened) {
		return KERNEL_ERROR_EBADF;
	}

	LOGF("\\tFcntl cmd = %d, arg = 0x%x, file: %s\\n", cmd, arg, Common::PathToString(file->real_name).c_str());

	Common::LockGuard lock(file->mutex);
	switch (cmd) {
		case CMD_GETFD: return file->close_on_exec ? FLAG_CLOEXEC : 0;
		case CMD_SETFD: file->close_on_exec = ((arg & FLAG_CLOEXEC) != 0); return OK;
		case CMD_GETFL:
			return (file->writable ? FLAG_RDWR : 0) | (file->append ? FLAG_APPEND : 0) |
			       (file->sync_writes ? FLAG_SYNC : 0);
		case CMD_SETFL:
			if (file->writable) {
				file->append = ((arg & FLAG_APPEND) != 0);
			}
			return OK;
		default: LOGF("\\tFcntl command %d: not supported by this host\\n", cmd); return KERNEL_ERROR_EINVAL;
	}
}
'''),
    ],
    'src/libs/libC.cpp': [
        ('''struct ThreadAtexitDestructor {
	thread_atexit_destructor_t destructor;
	void*                      object;
};
''', 1, '''struct ThreadAtexitDestructor {
	thread_atexit_destructor_t destructor;
	void*                      object;
	void*                      module_id; // experiment 0327: the DSO handle symbol the destructor was registered with
};
'''),
        ('''int KYTY_SYSV_ABI LibcInternalExtCxaThreadAtexit(thread_atexit_destructor_t destructor,
                                                 void* object, void* /*module_id*/) {
	PRINT_NAME();

	g_thread_atexit_destructors.push_back({destructor, object});

	return 0;
}
''', 1, '''int KYTY_SYSV_ABI LibcInternalExtCxaThreadAtexit(thread_atexit_destructor_t destructor,
                                                 void* object, void* module_id) {
	PRINT_NAME();

	g_thread_atexit_destructors.push_back({destructor, object, module_id});

	return 0;
}
'''),
        ('''LIB_DEFINE(InitLibcInternalExt_1) {
	LIB_FUNC("NWtTN10cJzE", LibcInternalExt::LibcHeapGetTraceInfo);
''', 1, '''// Experiment 0327: sceLibcInternalForceTlsDestructor(handle) — the console's libc runs, on the calling
// thread, the thread_atexit destructors that a module registered, when that module is unloaded (the
// runtime linker calls it for every thread that touched the module's TLS); the destructors are removed
// as they run. A destructor's module is the one whose image holds the DSO handle symbol it was
// registered with (__cxa_thread_atexit's third argument), found through the runtime linker. Returns 0.
int KYTY_SYSV_ABI LibcInternalForceTlsDestructor(int handle) {
	PRINT_NAME();

	auto* rt  = Common::Singleton<Loader::RuntimeLinker>::Instance();
	int   run = 0;
	for (size_t i = g_thread_atexit_destructors.size(); i-- > 0;) {
		const auto d = g_thread_atexit_destructors[i];
		auto*      p = (d.module_id != nullptr)
		                   ? rt->FindProgramByAddr(reinterpret_cast<uint64_t>(d.module_id))
		                   : nullptr;
		if (p == nullptr || p->unique_id != handle) {
			continue;
		}
		g_thread_atexit_destructors.erase(g_thread_atexit_destructors.begin() + static_cast<long>(i));
		if (d.destructor != nullptr) {
			d.destructor(d.object);
			run++;
		}
	}

	LOGF("\\tsceLibcInternalForceTlsDestructor: module %d, %d destructor(s) run\\n", handle, run);

	return 0;
}

// Experiment 0327: sceLibcInternalFinalizeTls — the calling thread's TLS is finalised: every
// thread_atexit destructor it registered runs, last registered first, as at thread exit.
void KYTY_SYSV_ABI LibcInternalFinalizeTls() {
	PRINT_NAME();

	RunThreadAtexitDestructors();
}

LIB_DEFINE(InitLibcInternalExt_1) {
	LIB_FUNC("NWtTN10cJzE", LibcInternalExt::LibcHeapGetTraceInfo);
'''),
        ('''	LIB_FUNC("GMpvxPFW924", LibcInternal::vprintf);
''', 1, '''	LIB_FUNC("GMpvxPFW924", LibcInternal::vprintf);
	LIB_FUNC("tB59hFLH3SA", LibcInternalExt::LibcInternalForceTlsDestructor); // experiment 0327
	LIB_FUNC("OQ-dzhlnM28", LibcInternalExt::LibcInternalFinalizeTls);        // experiment 0327
'''),
        ('''#include <unordered_map>
#include <vector>
''', 1, '''#include <unordered_map>
#include <vector>
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <execinfo.h> // experiment 0329: sceLibcInternalBacktraceForGame
#endif
#include <cstdio> // experiment 0329
'''),
        ('''void KYTY_SYSV_ABI LibcInternalFinalizeTls() {
	PRINT_NAME();

	RunThreadAtexitDestructors();
}
''', 1, '''void KYTY_SYSV_ABI LibcInternalFinalizeTls() {
	PRINT_NAME();

	RunThreadAtexitDestructors();
}

// Experiment 0329: sceLibcInternalBacktraceForGame (EHsF2i9FXPM) — the console's libc writes the calling thread's
// backtrace to the debug output, under the name of the heap whose diagnostics asked for it (AnyPS5's
// libc/src/HeapDiagnostics.cpp:36 prints the caller). Here the host's backtrace of the calling thread (execinfo;
// the guest's frames show as bare addresses) on stderr, headed by the heap's name and the guest caller.
void KYTY_SYSV_ABI LibcInternalBacktraceForGame(const char* heap_name) {
	PRINT_NAME();

	std::fprintf(stderr, "[libc] backtrace for heap %s, requested from guest 0x%" PRIx64 "\\n",
	             heap_name != nullptr ? heap_name : "(null)",
	             reinterpret_cast<uint64_t>(__builtin_return_address(0)));
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	void*     frames[64];
	const int count = ::backtrace(frames, 64);
	::backtrace_symbols_fd(frames, count, 2);
#endif
	std::fflush(stderr);
}
'''),
        ('''	LIB_FUNC("qBS714-Jr3g", LibcInternalExt::LibcInternalExtCxaThreadAtexit);
''', 1, '''	LIB_FUNC("qBS714-Jr3g", LibcInternalExt::LibcInternalExtCxaThreadAtexit);
	LIB_FUNC("EHsF2i9FXPM", LibcInternalExt::LibcInternalBacktraceForGame); // experiment 0329
'''),
    ],
    'src/libs/libs.cpp': [
        ('''LIB_DEFINE(InitNet_1);
''', 1, '''LIB_DEFINE(InitNet_1);
namespace NpCppWebApi {
LIB_DEFINE(InitNpCppWebApi_1); // experiment 0328
} // namespace NpCppWebApi
namespace PngEnc {
LIB_DEFINE(InitPngEnc_1); // experiment 0329
} // namespace PngEnc
namespace PlayGoDialog {
LIB_DEFINE(InitPlayGoDialog_1); // experiment 0329
} // namespace PlayGoDialog
namespace NpCommerceDialog {
LIB_DEFINE(InitNpCommerceDialog_1); // experiment 0329
} // namespace NpCommerceDialog
namespace PlayerInvitationDialog {
LIB_DEFINE(InitPlayerInvitationDialog_1); // experiment 0329
} // namespace PlayerInvitationDialog
'''),
        ('''	LIB_LOAD(InitNet_1);
''', 1, '''	LIB_LOAD(InitNet_1);
	LIB_LOAD(NpCppWebApi::InitNpCppWebApi_1);                       // experiment 0328
	LIB_LOAD(PngEnc::InitPngEnc_1);                                 // experiment 0329
	LIB_LOAD(PlayGoDialog::InitPlayGoDialog_1);                     // experiment 0329
	LIB_LOAD(NpCommerceDialog::InitNpCommerceDialog_1);             // experiment 0329
	LIB_LOAD(PlayerInvitationDialog::InitPlayerInvitationDialog_1); // experiment 0329
'''),
    ],
    'src/kernel/memory.h': [
        ('''int KYTY_SYSV_ABI KernelIsStack(void* addr, void** start, void** end);
''', 1, '''int KYTY_SYSV_ABI KernelIsStack(void* addr, void** start, void** end);
int KYTY_SYSV_ABI KernelMlock(void* addr, size_t len); // experiment 0329
'''),
    ],
    'src/kernel/memory.cpp': [
        ('''#include <vector>
#include <thread>
''', 1, '''#include <vector>
#include <thread>
#include <cerrno> // experiment 0329: mlock
#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
#include <sys/mman.h> // experiment 0329: mlock
#endif
'''),
        ('''int KYTY_SYSV_ABI KernelIsStack(void* addr, void** start, void** end) {
''', 1, '''// Experiment 0329: sceKernelMlock (3k6kx-zOOSQ), libc.prx's import — the pages of a mapped range are pinned in RAM.
// Every page of the range must lie in a mapped virtual range of the process (ENOMEM otherwise, as FreeBSD's mlock
// answers an unmapped page); EINVAL for a null pointer or a length of zero. The host pins the same pages with
// mlock(2) (AnyPS5's DirectMemory/Export.cpp:717 does the same), rounded to the host's pages; the host's own
// refusal — ENOMEM at RLIMIT_MEMLOCK, EPERM — is returned as the console's error of the same name, logged once.
int KYTY_SYSV_ABI KernelMlock(void* addr, size_t len) {
	PRINT_NAME();

	std::lock_guard<std::recursive_mutex> memory_operation_lock(g_memory_operation_mutex);

	const auto vaddr = reinterpret_cast<uint64_t>(addr);

	LOGF("\\t addr = 0x%016" PRIx64 ", len = 0x%" PRIx64 "\\n", vaddr, static_cast<uint64_t>(len));

	if (addr == nullptr || len == 0 || vaddr > UINT64_MAX - len) {
		return KERNEL_ERROR_EINVAL;
	}

	const uint64_t end = vaddr + len;
	for (uint64_t pos = vaddr; pos < end;) {
		VirtualRanges::Range range {};
		if (!g_virtual_ranges->Query(pos, 0, &range) || range.type == VirtualRangeType::Reserved ||
		    pos < range.start || range.start + range.size <= pos) {
			LOGF("\\t 0x%016" PRIx64 " is not mapped: ENOMEM\\n", pos);
			return KERNEL_ERROR_ENOMEM;
		}
		pos = range.start + range.size;
	}

#if KYTY_PLATFORM == KYTY_PLATFORM_LINUX
	constexpr uint64_t host_page = 4096;
	const uint64_t     first     = vaddr & ~(host_page - 1);
	if (::mlock(reinterpret_cast<void*>(first), static_cast<size_t>(end - first)) != 0) {
		const int saved = errno;
		static std::atomic<uint32_t> logged {0};
		if (logged.fetch_add(1) < 4) {
			LOGF("\\t host mlock failed: errno %d (RLIMIT_MEMLOCK? see ulimit -l)\\n", saved);
			std::fprintf(stderr, "[bc5] sceKernelMlock: the host refused to pin 0x%" PRIx64 " bytes at 0x%016" PRIx64
			                     " (errno %d)\\n",
			             static_cast<uint64_t>(end - first), first, saved);
		}
		return saved == EPERM ? KERNEL_ERROR_EPERM : saved == ENOMEM ? KERNEL_ERROR_ENOMEM : KERNEL_ERROR_EINVAL;
	}
#endif

	return OK;
}

int KYTY_SYSV_ABI KernelIsStack(void* addr, void** start, void** end) {
'''),
    ],
    'src/libs/network.h': [
        ('''int KYTY_SYSV_ABI HttpGetStatusCode(int request_id, int* status_code);
''', 1, '''int KYTY_SYSV_ABI HttpGetStatusCode(int request_id, int* status_code);
int KYTY_SYSV_ABI HttpReadData(int request_id, void* data, size_t size); // experiment 0329
'''),
    ],
    'src/libs/network.cpp': [
        ('''	bool HttpGetRequestResponse(Id req_id, int* send_result, int* status_code, const char** headers,
	                            size_t* headers_size, uint64_t* content_length);
''', 1, '''	bool HttpGetRequestResponse(Id req_id, int* send_result, int* status_code, const char** headers,
	                            size_t* headers_size, uint64_t* content_length);
	// Experiment 0329: sceHttpReadData's read of the response body from the request's read position on.
	bool HttpReadResponseBody(Id req_id, void* data, size_t size, int* send_result, size_t* read);
'''),
        ('''		std::vector<uint8_t>  response_body;
	};
''', 1, '''		std::vector<uint8_t>  response_body;
		uint64_t              read_offset = 0; // experiment 0329: sceHttpReadData's position
	};
'''),
        ('''bool Network::HttpCompleteRequest(Id req_id, int result, int status_code, std::string&& headers,
''', 1, '''bool Network::HttpReadResponseBody(Id req_id, void* data, size_t size, int* send_result, size_t* read) {
	Common::LockGuard lock(m_mutex);
	if (req_id.GetType() != Id::Type::Request || req_id.GetId() < 0 ||
	    static_cast<size_t>(req_id.GetId()) >= m_requests.size() || !m_requests[req_id.GetId()].used) {
		return false;
	}
	auto& request = m_requests[req_id.GetId()];
	*send_result  = (request.send_attempted ? request.send_result : HTTP_ERROR_BEFORE_SEND);
	*read         = 0;
	if (*send_result != OK) {
		return true;
	}
	const uint64_t total = request.response_body.size();
	const uint64_t at    = (request.read_offset < total) ? request.read_offset : total;
	const uint64_t left  = total - at;
	const size_t   n     = static_cast<size_t>((left < size) ? left : size);
	if (n != 0) {
		std::memcpy(data, request.response_body.data() + at, n);
		request.read_offset += n;
	}
	*read = n;
	return true;
}

bool Network::HttpCompleteRequest(Id req_id, int result, int status_code, std::string&& headers,
'''),
        ('''		request.response_body    = std::move(body);
		return true;
''', 1, '''		request.response_body    = std::move(body);
		request.read_offset      = 0; // experiment 0329
		return true;
'''),
        ('''int KYTY_SYSV_ABI HttpGetAllResponseHeaders(int request_id, char** header, size_t* header_size) {
''', 1, '''// Experiment 0329: sceHttpReadData (P5pdoykPYTk) — the response body of a sent request, from the read position on,
// as many bytes as fit; 0 at the end. HTTP_ERROR_INVALID_ID for an unknown request, HTTP_ERROR_INVALID_VALUE for a
// null buffer with a size, HTTP_ERROR_BEFORE_SEND before sceHttpSendRequest, and after a failed send the send's own
// error — on this offline console the HTTP_ERROR_NETWORK of HttpFetchSync.
int KYTY_SYSV_ABI HttpReadData(int request_id, void* data, size_t size) {
	PRINT_NAME();

	LOGF("\\t request_id = %d\\n"
	     "\\t data       = 0x%016" PRIx64 "\\n"
	     "\\t size       = %" PRIu64 "\\n",
	     request_id, reinterpret_cast<uint64_t>(data), static_cast<uint64_t>(size));

	if (data == nullptr && size != 0) {
		return HTTP_ERROR_INVALID_VALUE;
	}

	EXIT_IF(g_net == nullptr);

	int    send_result = HTTP_ERROR_BEFORE_SEND;
	size_t read        = 0;
	if (!g_net->HttpReadResponseBody(Network::Id(request_id), data, size, &send_result, &read)) {
		return HTTP_ERROR_INVALID_ID;
	}
	if (send_result != OK) {
		return send_result;
	}
	return static_cast<int>(read);
}

int KYTY_SYSV_ABI HttpGetAllResponseHeaders(int request_id, char** header, size_t* header_size) {
'''),
    ],
    'src/libs/libNet.cpp': [
        ('''#include <map>
#include <mutex>
''', 1, '''#include <map>
#include <mutex>
#include <set>    // experiment 0329
#include <atomic> // experiment 0329
'''),
        ('''	LIB_FUNC("A9cVMUtEp4Y", Http::HttpInit);
''', 1, '''	LIB_FUNC("A9cVMUtEp4Y", Http::HttpInit);
	LIB_FUNC("P5pdoykPYTk", Http::HttpReadData); // experiment 0329
'''),
        ('''LIB_DEFINE(InitNet_1_NpManager) {
''', 1, '''// Experiment 0329: sceNpGetAccountLanguage2 (3Tcz5bNCfZQ): the language of the user's PSN account, through a request
// — on this console no user is signed in (NpGetState answers signed out), so the call fails with
// SCE_NP_ERROR_SIGNED_OUT (0x80550006, the value AnyPS5's libSceNpManager/Export.cpp:255 answers), the language left
// untouched; SCE_NP_ERROR_INVALID_ARGUMENT (0x80550003, shadPS4 np_error.h:11) for a null pointer or request id 0.
// The language code (SceNpLanguageCode: 6 chars + padding, shadPS4 np_manager.h:76) would come from the account.
struct NpLanguageCode {
	char code[6];
	char padding[10];
};
static_assert(sizeof(NpLanguageCode) == 16);

constexpr int NP_MANAGER_ERROR_INVALID_ARGUMENT = static_cast<int>(0x80550003u);
constexpr int NP_MANAGER_ERROR_SIGNED_OUT       = static_cast<int>(0x80550006u);

static int KYTY_SYSV_ABI NpGetAccountLanguage2(int req_id, int user_id, NpLanguageCode* language) {
	PRINT_NAME();

	LOGF("\\t req_id = %d, user_id = %d, language = 0x%016" PRIx64 "\\n", req_id, user_id,
	     reinterpret_cast<uint64_t>(language));

	if (language == nullptr || req_id <= 0) {
		return NP_MANAGER_ERROR_INVALID_ARGUMENT;
	}
	uint32_t state = 1; // signed out
	NpManager::NpGetState(user_id, &state);
	if (state == 1) {
		return NP_MANAGER_ERROR_SIGNED_OUT;
	}
	return NP_MANAGER_ERROR_SIGNED_OUT; // no account exists on this console whose language could be read
}

LIB_DEFINE(InitNet_1_NpManager) {
'''),
        ('''	LIB_FUNC("Oad3rvY-NJQ", NpManager::NpHasSignedUp);
''', 1, '''	LIB_FUNC("Oad3rvY-NJQ", NpManager::NpHasSignedUp);
	LIB_FUNC("3Tcz5bNCfZQ", NpGetAccountLanguage2); // experiment 0329
'''),
        ('''static int KYTY_SYSV_ABI NpSessionSignalingInitialize(void* param) {
	PRINT_NAME();

	LOGF("\\t param = 0x%016" PRIx64 "\\n", reinterpret_cast<uint64_t>(param));

	return 0;
}

LIB_DEFINE(InitNet_1_NpSessionSignaling) {
	LIB_FUNC("ysmw6J-P8Ak", NpSessionSignalingInitialize);
}
''', 1, '''// Experiment 0329: the library's state. Initialize records it; Terminate (CqJuNXo5yiM) clears it and fails with
// NOT_INITIALIZED before an Initialize; Deactivate (cQkBH-pXhF0) and DestroyContext (Z9Q9LzQDXf0) take a context
// id, and no context can exist — the title does not import CreateContext and this library creates none — so they
// answer INVALID_ARGUMENT (0x80553303, the value AnyPS5's libSceNpSessionSignaling/Export.cpp:8 uses for a bad
// argument). TODO(verify): NOT_INITIALIZED's value is the facility's first code by the SDK's usual numbering
// (0x80553301); no public source carries it.
constexpr int NP_SESSION_SIGNALING_ERROR_NOT_INITIALIZED  = static_cast<int>(0x80553301u);
constexpr int NP_SESSION_SIGNALING_ERROR_INVALID_ARGUMENT = static_cast<int>(0x80553303u);

static std::atomic_bool g_np_session_signaling_initialized {false};

static int KYTY_SYSV_ABI NpSessionSignalingInitialize(void* param) {
	PRINT_NAME();

	LOGF("\\t param = 0x%016" PRIx64 "\\n", reinterpret_cast<uint64_t>(param));

	g_np_session_signaling_initialized.store(true, std::memory_order_relaxed);
	return 0;
}

static int KYTY_SYSV_ABI NpSessionSignalingTerminate() {
	PRINT_NAME();

	if (!g_np_session_signaling_initialized.exchange(false, std::memory_order_relaxed)) {
		return NP_SESSION_SIGNALING_ERROR_NOT_INITIALIZED;
	}
	return 0;
}

static int KYTY_SYSV_ABI NpSessionSignalingDeactivate(uint32_t context_id) {
	PRINT_NAME();

	LOGF("\\t context_id = %u (no context exists on this console)\\n", context_id);

	return NP_SESSION_SIGNALING_ERROR_INVALID_ARGUMENT;
}

static int KYTY_SYSV_ABI NpSessionSignalingDestroyContext(uint32_t context_id) {
	PRINT_NAME();

	LOGF("\\t context_id = %u (no context exists on this console)\\n", context_id);

	return NP_SESSION_SIGNALING_ERROR_INVALID_ARGUMENT;
}

LIB_DEFINE(InitNet_1_NpSessionSignaling) {
	LIB_FUNC("ysmw6J-P8Ak", NpSessionSignalingInitialize);
	LIB_FUNC("CqJuNXo5yiM", NpSessionSignalingTerminate);      // experiment 0329
	LIB_FUNC("cQkBH-pXhF0", NpSessionSignalingDeactivate);     // experiment 0329
	LIB_FUNC("Z9Q9LzQDXf0", NpSessionSignalingDestroyContext); // experiment 0329
}
'''),
        ('''static int KYTY_SYSV_ABI NpEntitlementAccessDeleteRequest(int64_t request_id) {
	PRINT_NAME();
	std::lock_guard lock(g_bc5_ent_mutex);
	g_bc5_ent_requests.erase(request_id);
	return 0;
}
''', 1, '''static int KYTY_SYSV_ABI NpEntitlementAccessDeleteRequest(int64_t request_id) {
	PRINT_NAME();
	std::lock_guard lock(g_bc5_ent_mutex);
	g_bc5_ent_requests.erase(request_id);
	return 0;
}

// Experiment 0329: sceNpEntitlementAccessAbortRequest (HFcQl9TMcFQ): a known request is aborted — it completed at
// its creation above, so nothing runs and the request stays pollable until deleted — and an unknown one answers
// REQUEST_NOT_FOUND, as the poll does.
static int KYTY_SYSV_ABI NpEntitlementAccessAbortRequest(int64_t request_id) {
	PRINT_NAME();
	std::lock_guard lock(g_bc5_ent_mutex);
	if (g_bc5_ent_requests.find(request_id) == g_bc5_ent_requests.end()) {
		return -2122514411; // NP_ENTITLEMENT_ACCESS_ERROR_REQUEST_NOT_FOUND, 0x817D0015
	}
	LOGF("\\t request_id = %" PRId64 ": already complete, nothing to abort\\n", request_id);
	return 0;
}
'''),
        ('''	LIB_FUNC("Z0eQj8m7XA8", NpEntitlementAccessDeleteRequest);
''', 1, '''	LIB_FUNC("Z0eQj8m7XA8", NpEntitlementAccessDeleteRequest);
	LIB_FUNC("HFcQl9TMcFQ", NpEntitlementAccessAbortRequest); // experiment 0329
'''),
        ('''static int KYTY_SYSV_ABI NpWebApi2PushEventCreateFilter(int lib_ctx_id, int handle_id,
''', 1, '''// Experiment 0329: the filters CreateFilter hands out, so that DeleteFilter can tell a filter from a stranger.
static std::mutex& NpWebApi2FiltersMutex() {
	static std::mutex mutex;
	return mutex;
}

static std::set<int>& NpWebApi2Filters() {
	static std::set<int> filters;
	return filters;
}

static int KYTY_SYSV_ABI NpWebApi2PushEventCreateFilter(int lib_ctx_id, int handle_id,
'''),
        ('''	static int filter_id = 1;

	return filter_id++;
''', 1, '''	std::lock_guard lock(NpWebApi2FiltersMutex());
	static int      filter_id = 1;
	NpWebApi2Filters().insert(filter_id); // experiment 0329

	return filter_id++;
'''),
        ('''static void KYTY_SYSV_ABI NpWebApi2CheckTimeout() {
''', 1, '''// Experiment 0329: the push-context calls the title makes. A push context is the user's live connection to the
// PSN push service; without a sign-in none can be created, and the console answers NOT_SIGNED_IN (0x80553407) to
// CreatePushContext (NNVf18SlbT8) and to the two calls that take a push context — RegisterPushContextCallback
// (lxtHJMwBsaU) and StartPushContextCallback (AAj9X+4aGYA) — since the user they name has no sign-in either.
// DeleteFilter (KJdPcOGmK58) removes a filter CreateFilter handed out, INVALID_ARGUMENT for any other id.
// TODO(verify): the argument lists follow the PS4 generation's sceNpWebApi push-event calls (shadPS4 np_web_api);
// AnyPS5 declares these four without parameters.
static int KYTY_SYSV_ABI NpWebApi2PushEventCreatePushContext(int user_context_id, const char* np_service_name,
                                                              uint32_t np_service_label, void* push_context_id) {
	PRINT_NAME();
	LOGF("\\t user_context_id  = %d\\n", user_context_id);
	LOGF("\\t np_service_name  = %s\\n", np_service_name != nullptr ? np_service_name : "(null)");
	LOGF("\\t np_service_label = %" PRIu32 "\\n", np_service_label);
	if (push_context_id == nullptr) {
		return NP_WEBAPI2_ERROR_INVALID_ARGUMENT;
	}
	return NP_WEBAPI2_ERROR_NOT_SIGNED_IN;
}

static int KYTY_SYSV_ABI NpWebApi2PushEventRegisterPushContextCallback(int user_context_id, const void* push_context_id,
                                                                        int filter_id, void* callback, void* user_arg) {
	PRINT_NAME();
	LOGF("\\t user_context_id = %d\\n", user_context_id);
	LOGF("\\t push_context_id = 0x%016" PRIx64 "\\n", reinterpret_cast<uint64_t>(push_context_id));
	LOGF("\\t filter_id       = %d\\n", filter_id);
	LOGF("\\t callback        = 0x%016" PRIx64 "\\n", reinterpret_cast<uint64_t>(callback));
	LOGF("\\t user_arg        = 0x%016" PRIx64 "\\n", reinterpret_cast<uint64_t>(user_arg));
	if (push_context_id == nullptr || callback == nullptr) {
		return NP_WEBAPI2_ERROR_INVALID_ARGUMENT;
	}
	return NP_WEBAPI2_ERROR_NOT_SIGNED_IN;
}

static int KYTY_SYSV_ABI NpWebApi2PushEventStartPushContextCallback(int user_context_id, const void* push_context_id) {
	PRINT_NAME();
	LOGF("\\t user_context_id = %d\\n", user_context_id);
	LOGF("\\t push_context_id = 0x%016" PRIx64 "\\n", reinterpret_cast<uint64_t>(push_context_id));
	if (push_context_id == nullptr) {
		return NP_WEBAPI2_ERROR_INVALID_ARGUMENT;
	}
	return NP_WEBAPI2_ERROR_NOT_SIGNED_IN;
}

static int KYTY_SYSV_ABI NpWebApi2PushEventDeleteFilter(int lib_ctx_id, int filter_id) {
	PRINT_NAME();
	LOGF("\\t lib_ctx_id = %d\\n", lib_ctx_id);
	LOGF("\\t filter_id  = %d\\n", filter_id);
	std::lock_guard lock(NpWebApi2FiltersMutex());
	if (NpWebApi2Filters().erase(filter_id) == 0) {
		return NP_WEBAPI2_ERROR_INVALID_ARGUMENT;
	}
	return 0;
}

static void KYTY_SYSV_ABI NpWebApi2CheckTimeout() {
'''),
        ('''	LIB_FUNC("+o9816YQhqQ", LibNpWebApi2::NpWebApi2Initialize);
''', 1, '''	LIB_FUNC("+o9816YQhqQ", LibNpWebApi2::NpWebApi2Initialize);
	LIB_FUNC("NNVf18SlbT8", LibNpWebApi2::NpWebApi2PushEventCreatePushContext);           // experiment 0329
	LIB_FUNC("lxtHJMwBsaU", LibNpWebApi2::NpWebApi2PushEventRegisterPushContextCallback); // experiment 0329
	LIB_FUNC("AAj9X+4aGYA", LibNpWebApi2::NpWebApi2PushEventStartPushContextCallback);    // experiment 0329
	LIB_FUNC("KJdPcOGmK58", LibNpWebApi2::NpWebApi2PushEventDeleteFilter);                // experiment 0329
'''),
    ],
    'src/libs/libSaveData.cpp': [
        ('''LIB_DEFINE(InitSaveDataNative_1) {
''', 1, '''// Experiment 0329: sceSaveDataGetConvertProgress (8EA5OMIL1lQ): the progress of the save-data conversion, 0.0 to
// 1.0 — no conversion was ever started on this host (the title imports no sceSaveDataConvert), so 0.0, as AnyPS5's
// libSceSaveData.native/Export.cpp:964 reports before a conversion; SAVE_DATA_ERROR_PARAMETER for a null pointer.
static int KYTY_SYSV_ABI SaveDataGetConvertProgress(float* progress) {
	PRINT_NAME();
	if (progress == nullptr) {
		return ::Libs::SaveData::SAVE_DATA_ERROR_PARAMETER;
	}
	*progress = 0.0f;
	LOGF("\\t progress = %.2f (no conversion runs)\\n", *progress);
	return OK;
}

// Experiment 0329: sceSaveDataCancel (e6y3WMBYbiM): the save-data operation in progress is cancelled. Every
// operation of this host's library completes within its call (mount, backup, the event of 2mfSRGdshtk above), so
// there is never one to cancel and the call succeeds, as it does on the console with nothing running.
// TODO(verify): the SDK's parameter list (AnyPS5 declares the call without parameters; none is read here).
static int KYTY_SYSV_ABI SaveDataCancel() {
	PRINT_NAME();
	LOGF("\\t nothing in progress\\n");
	return OK;
}

LIB_DEFINE(InitSaveDataNative_1) {
'''),
        ('''	LIB_FUNC("2mfSRGdshtk", SaveDataNative_2mfSRGdshtk);
''', 1, '''	LIB_FUNC("2mfSRGdshtk", SaveDataNative_2mfSRGdshtk);
	LIB_FUNC("8EA5OMIL1lQ", SaveDataGetConvertProgress); // experiment 0329
	LIB_FUNC("e6y3WMBYbiM", SaveDataCancel);             // experiment 0329
'''),
    ],
    'src/libs/audio.h': [
        ('''int KYTY_SYSV_ABI AcmBatchJobNotification(AcmBatchInfo* batch_info);
''', 1, '''int KYTY_SYSV_ABI AcmBatchJobNotification(AcmBatchInfo* batch_info);
int KYTY_SYSV_ABI AcmBatchJobPriority(AcmBatchInfo* batch_info, uint32_t priority); // experiment 0329
'''),
    ],
    'src/libs/audio.cpp': [
        ('''int KYTY_SYSV_ABI AcmConvReverbSharedInput(AcmBatchInfo* batch_info, uint32_t block_count, void* in,
''', 1, '''// Experiment 0329: sceAcmBatchJobPriority (GTfJ64qFCPw): a job that sets the priority of the batch it is written
// into, recorded in the batch buffer as this library records every job (the batch is advanced by the job's size and
// nothing is executed: no audio compute runs on this host, see AcmFft above); the priority is kept per batch
// buffer for the batch's start. TODO(verify): the job's size in the batch buffer (one 16-byte command here) and
// the priority's range; AnyPS5 has no implementation.
static std::mutex                        g_acm_priority_mutex;
static std::map<const void*, uint32_t>   g_acm_batch_priorities;

int KYTY_SYSV_ABI AcmBatchJobPriority(AcmBatchInfo* batch_info, uint32_t priority) {
	PRINT_NAME();
	EXIT_NOT_IMPLEMENTED(batch_info == nullptr);
	LOGF("\\t batch buffer = 0x%016" PRIx64 ", priority = %u\\n", reinterpret_cast<uint64_t>(batch_info->buffer),
	     priority);
	{
		std::lock_guard lock(g_acm_priority_mutex);
		g_acm_batch_priorities[batch_info->buffer] = priority;
	}
	acm_advance_batch(batch_info, 16);
	return OK;
}

int KYTY_SYSV_ABI AcmConvReverbSharedInput(AcmBatchInfo* batch_info, uint32_t block_count, void* in,
'''),
    ],
    'src/libs/libAudio.cpp': [
        ('''	LIB_FUNC("r7z5YQFZo+U", Acm::AcmBatchJobNotification);
''', 1, '''	LIB_FUNC("r7z5YQFZo+U", Acm::AcmBatchJobNotification);
	LIB_FUNC("GTfJ64qFCPw", Acm::AcmBatchJobPriority); // experiment 0329
'''),
    ],
    'src/libs/controller.h': [
        ('''int KYTY_SYSV_ABI PadGetControllerInformation(int handle, PadControllerInformation* info);
''', 1, '''int KYTY_SYSV_ABI PadGetControllerInformation(int handle, PadControllerInformation* info);
int KYTY_SYSV_ABI PadGetAccessibilityControllerState(int handle, uint32_t* state); // experiment 0329
'''),
    ],
    'src/libs/controller.cpp': [
        ('''int KYTY_SYSV_ABI PadGetControllerInformation(int handle, PadControllerInformation* info) {
''', 1, '''// Experiment 0329: scePadGetAccessibilityControllerState (zBsgF0q8DIM): the state of the Access controller paired
// with the port — none is, so 0 (AnyPS5 libScePad/Export.cpp:326 answers the same); the pad errors for a bad handle
// or a null pointer, in the order of the other state queries here.
int KYTY_SYSV_ABI PadGetAccessibilityControllerState(int handle, uint32_t* state) {
	PRINT_NAME();

	EXIT_IF(g_controller == nullptr);

	if (ControllerIndexFromHandle(handle) < 0) {
		return PAD_ERROR_INVALID_HANDLE;
	}
	if (state == nullptr) {
		return PAD_ERROR_INVALID_ARG;
	}

	*state = 0;

	return OK;
}

int KYTY_SYSV_ABI PadGetControllerInformation(int handle, PadControllerInformation* info) {
'''),
    ],
    'src/libs/libPad.cpp': [
        ('''	LIB_FUNC("gjP9-KQzoUk", Controller::PadGetControllerInformation);
''', 1, '''	LIB_FUNC("gjP9-KQzoUk", Controller::PadGetControllerInformation);
	LIB_FUNC("zBsgF0q8DIM", Controller::PadGetAccessibilityControllerState); // experiment 0329
'''),
    ],
    'src/graphics/presentation/videoOut.h': [
        ('''KYTY_SYSV_ABI int VideoOutAdjustColor(int handle, const VideoOutColorSettings* settings);
''', 1, '''KYTY_SYSV_ABI int VideoOutAdjustColor(int handle, const VideoOutColorSettings* settings);
// Experiment 0329
KYTY_SYSV_ABI int VideoOutAllowOutputResolutionWqhdDetection(int handle);
KYTY_SYSV_ABI int VideoOutVrrPegToFixedRate(int handle, uint64_t arg1, uint64_t arg2);
KYTY_SYSV_ABI int VideoOutVrrUnpegFromFixedRate(int handle);
KYTY_SYSV_ABI int VideoOutAddVrrStatusFlagsPrivilege();
'''),
    ],
    'src/graphics/presentation/videoOut.cpp': [
        ('''	float                               gamma       = 1.0f;
''', 1, '''	float                               gamma       = 1.0f;
	bool                                vrr_pegged     = false; // experiment 0329: VrrPegToFixedRate
	bool                                wqhd_detection = false; // experiment 0329: AllowOutputResolutionWqhdDetection
'''),
        ('''KYTY_SYSV_ABI int VideoOutConfigureOutput(int handle, uint64_t mode,
''', 1, '''// Experiment 0329: sceVideoOutAllowOutputResolutionWqhdDetection (w7Ipp9Xl7hg) — the title allows the port to
// detect a 2560x1440 display; recorded on the port (the host's output mode is the presenter's). INVALID_HANDLE on
// a closed port (AnyPS5 libSceVideoOut/src/Output.cpp:107 checks the same).
KYTY_SYSV_ABI int VideoOutAllowOutputResolutionWqhdDetection(int handle) {
	PRINT_NAME();

	auto* ctx = DriverState().Get(handle);
	if (ctx == nullptr) {
		return VIDEO_OUT_ERROR_INVALID_HANDLE;
	}
	Common::LockGuard lock(ctx->mutex);
	ctx->wqhd_detection = true;
	return OK;
}

// Experiment 0329: sceVideoOutVrrPegToFixedRate (5tRaBjtdTzY) / VrrUnpegFromFixedRate (T4ucGB8CsnM) — with a
// variable-refresh-rate display the title pegs the output to the fixed rate and releases it; the port records the
// state (the BC-250's output is a fixed-rate one: no VRR to leave). INVALID_HANDLE on a closed port; the two
// trailing arguments of the peg are 0 in every call AnyPS5 has seen (Output.cpp:394 refuses others), INVALID_VALUE
// here for a non-zero one. TODO(verify): their meaning.
KYTY_SYSV_ABI int VideoOutVrrPegToFixedRate(int handle, uint64_t arg1, uint64_t arg2) {
	PRINT_NAME();

	LOGF("\\t arg1 = 0x%" PRIx64 ", arg2 = 0x%" PRIx64 "\\n", arg1, arg2);

	auto* ctx = DriverState().Get(handle);
	if (ctx == nullptr) {
		return VIDEO_OUT_ERROR_INVALID_HANDLE;
	}
	if (arg1 != 0 || arg2 != 0) {
		return VIDEO_OUT_ERROR_INVALID_VALUE;
	}
	Common::LockGuard lock(ctx->mutex);
	ctx->vrr_pegged = true;
	return OK;
}

KYTY_SYSV_ABI int VideoOutVrrUnpegFromFixedRate(int handle) {
	PRINT_NAME();

	auto* ctx = DriverState().Get(handle);
	if (ctx == nullptr) {
		return VIDEO_OUT_ERROR_INVALID_HANDLE;
	}
	Common::LockGuard lock(ctx->mutex);
	ctx->vrr_pegged = false;
	return OK;
}

// Experiment 0329: sceVideoOutAddVrrStatusFlagsPrivilege (kP2L8t3j-aM, the VideoOutVrrStatus library) — the process
// is granted the reading of the VRR status flags; recorded, and the flags of a fixed-rate output read as none.
// TODO(verify): the parameter list (AnyPS5 Output.cpp:406 declares it without parameters).
static std::atomic_bool g_vrr_status_privilege {false};

KYTY_SYSV_ABI int VideoOutAddVrrStatusFlagsPrivilege() {
	PRINT_NAME();

	g_vrr_status_privilege.store(true, std::memory_order_relaxed);
	return OK;
}

KYTY_SYSV_ABI int VideoOutConfigureOutput(int handle, uint64_t mode,
'''),
    ],
    'src/libs/libVideoOut.cpp': [
        ('''	LIB_FUNC("pv9CI5VC+R0", VideoOut::VideoOutAdjustColor);
}

} // namespace LibGen5

LIB_DEFINE(InitVideoOut_1) {
	LibGen5::InitVideoOut_1(s);
}
''', 1, '''	LIB_FUNC("pv9CI5VC+R0", VideoOut::VideoOutAdjustColor);
	LIB_FUNC("w7Ipp9Xl7hg", VideoOut::VideoOutAllowOutputResolutionWqhdDetection); // experiment 0329
	LIB_FUNC("5tRaBjtdTzY", VideoOut::VideoOutVrrPegToFixedRate);                  // experiment 0329
	LIB_FUNC("T4ucGB8CsnM", VideoOut::VideoOutVrrUnpegFromFixedRate);              // experiment 0329
}

} // namespace LibGen5

namespace LibVrrStatus { // experiment 0329: the title imports kP2L8t3j-aM from VideoOutVrrStatus_v1 of VideoOut_v1.1

LIB_VERSION("VideoOutVrrStatus", 1, "VideoOut", 1, 1);

LIB_DEFINE(InitVideoOut_1_VrrStatus) {
	LIB_FUNC("kP2L8t3j-aM", VideoOut::VideoOutAddVrrStatusFlagsPrivilege);
}

} // namespace LibVrrStatus

LIB_DEFINE(InitVideoOut_1) {
	LibGen5::InitVideoOut_1(s);
	LibVrrStatus::InitVideoOut_1_VrrStatus(s); // experiment 0329
}
'''),
    ],
    'src/loader/runtimeLinker.cpp': [
        ('''	g_stubbed_imports.push_back(record);
	const auto record_id                     = g_stubbed_imports.size() - 1;
	const auto thunk                         = AllocateUnresolvedImportThunk(record_id);
	g_stubbed_imports[record_id].thunk_vaddr = thunk;
	return thunk;
''', 1, '''	g_stubbed_imports.push_back(record);
	const auto record_id                     = g_stubbed_imports.size() - 1;
	const auto thunk                         = AllocateUnresolvedImportThunk(record_id);
	g_stubbed_imports[record_id].thunk_vaddr = thunk;
	{ // Experiment 0327: every stubbed import once, at link time, on stderr through RawLog (the silent
	  // console drops LOGF): the title's complete list of missing NIDs, with their library and module.
		Common::HostException::RawLog log;
		log.Append("[bc5] stubbed import #");
		log.AppendHex(record_id);
		log.Append(": ");
		log.Append(ri.name.c_str());
		log.Append(" (program ");
		log.Append(program_name.c_str());
		log.Append(")\\n");
		log.Flush();
	}
	return thunk;
'''),
        ('''	if (log_index < 1024 || first_call) {
		if (record_id < g_stubbed_imports.size()) {
			const auto& record = g_stubbed_imports[record_id];
''', 1, '''	if (first_call && record_id < g_stubbed_imports.size()) { // Experiment 0327: the first call, on stderr
		Common::HostException::RawLog log;
		log.Append("[bc5] stubbed import called: ");
		log.Append(g_stubbed_imports[record_id].name.c_str());
		log.Append(" (#");
		log.AppendHex(record_id);
		log.Append(")\\n");
		log.Flush();
	}
	if (log_index < 1024 || first_call) {
		if (record_id < g_stubbed_imports.size()) {
			const auto& record = g_stubbed_imports[record_id];
'''),
    ],
}


def main():
    if len(sys.argv) != 3:
        print('usage: patch0329.py <src root> <out dir>')
        sys.exit(2)
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    diff = []
    for rel, edits in EDITS.items():
        path = os.path.join(root, rel)
        src = open(path, encoding='utf-8').read()
        print(f'{rel}: md5 {hashlib.md5(src.encode("utf-8")).hexdigest()[:8]} in')
        dst = src
        for k, (old, n, new) in enumerate(edits, 1):
            c = dst.count(old)
            if c != n:
                print(f'{rel}: edit {k}: anchor found {c} times, expected {n}:\n{old}')
                sys.exit(1)
            dst = dst.replace(old, new)
        target = os.path.join(out, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        open(target, 'w', encoding='utf-8', newline='\n').write(dst)
        diff += difflib.unified_diff(src.splitlines(True), dst.splitlines(True), 'a/' + rel, 'b/' + rel)
        print(f'{rel}: {len(edits)} edits -> {target}, md5 {hashlib.md5(dst.encode("utf-8")).hexdigest()[:8]} out')
    open(os.path.join(out, 'patch_0329.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0329.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
