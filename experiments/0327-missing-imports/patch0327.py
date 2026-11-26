#!/usr/bin/env python3
# BC5 experiment 0327: the second title's twelve missing imports, implemented the way the console behaves (no return-0
# stubs), in the tree ~/src/KytyPlus (f266548 + patch 0001) as the box has it. Six units are touched:
#   src/kernel/syncOnAddress.{h,cpp}  sceKernelSyncOnAddressWait8 / Wait16 (dFym5b41JLU / XgVs4jRehcY): an 8- or 16-bit
#       word waited on through the futex of its containing aligned 32-bit word (the futex compares 32 bits; the waiter
#       re-checks its own byte / half-word and returns when it differs), the portable path keyed by the exact address as
#       the 32/64-bit waits are; sceKernelSyncOnAddressWake accepts any non-null address (the console does; a byte
#       address wakes through its aligned word).
#   src/libs/libKernel.cpp           the two wrappers and their NIDs; scePthreadRwlockTryrdlock (XD3mDeybCnk),
#       scePthreadRwlockTimedrdlock (iPtZRWICjrM), scePthreadRwlockTimedwrlock (adh--6nIqTk) registered on the tree's own
#       cooperative rwlock (the functions exist, only the NIDs were missing); sceKernelTruncate (WlyEA-sLDf0),
#       sceKernelChmod (fgIsQ10xYVA), sceKernelFchmod (UtszJWHrDcA), sceKernelUtimes (0Cq8ipKr9n0); getrusage
#       (hHlZQUnlxSM) in the posix set: the host's getrusage into the FreeBSD layout, -1/errno on a bad `who` or pointer.
#   src/kernel/fileSystem.{h,cpp}     the four path functions through the mount points (GetRealFilename), the console's
#       error codes (EFAULT null path, EINVAL relative path / negative length, ENAMETOOLONG, ENOENT, EISDIR, EROFS on
#       /app0 and /system), the host operation through std::filesystem (truncate, permissions) and utimensat (times).
#       KernelTruncate follows upstream KytyPlus's (Coder787-source, GPL-2.0, src/kernel/fileSystem.cpp) on this tree's
#       path resolution.
#   src/libs/libC.cpp                 sceLibcInternalForceTlsDestructor (tB59hFLH3SA): the calling thread's thread_atexit
#       destructors registered from the given module are run (and removed), as the console's libc does when a module is
#       unloaded; the DSO handle each destructor was registered with is kept for that. sceLibcInternalFinalizeTls
#       (OQ-dzhlnM28): the calling thread's destructors are all run, the thread's TLS finalised.
#   src/loader/runtimeLinker.cpp      diagnostics off the hot path: one RawLog (stderr, no CRT) line per stubbed import at
#       link time (NID[lib][module], program) — the title's complete missing list — and one at a stub's first call.
# usage: patch0327.py <src root of the tree> <out dir>   (python3 on the box; the laptop applies it with apply0327.pl)
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
        print('usage: patch0327.py <src root> <out dir>')
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
    open(os.path.join(out, 'patch_0327.diff'), 'w', encoding='utf-8', newline='\n').write(''.join(diff))
    print(f'patch_0327.diff: {sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))} added lines')


if __name__ == '__main__':
    main()
