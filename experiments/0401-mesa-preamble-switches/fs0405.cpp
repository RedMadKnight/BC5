// SPDX-License-Identifier: GPL-2.0-only
// BC5 experiment 0401 series e5, tag fs (exp 0405's ports; mkfs0405.py, fs0405-notes.md): the CPU test of
// src/kernel/fileSystem.cpp (KYTY_BC5_FS_FIXES) and of libkernel's registrations in src/libs/libKernel.cpp
// (KYTY_BC5_POSIX_RET_FIXES), as mkfs0405.py leaves them. It calls the host's own functions, linked from the emulator's
// objects, on real files in a fresh directory it makes under the current one (fs0405-work-<pid>): three host
// directories of it are mounted as the guest paths /temp0, /temp1 and /temp0/sub (FileSystem::Mount, the mount table
// the emulator fills with /app0, /savedata0 and the others); nothing else is mounted, so no guest path can reach a save,
// a game file or anything outside that directory. The directory is removed at the end (only the one this run made).
// Run three times on the box (build container), from a directory on the NVMe:
//   KYTY_BC5_FS_FIXES=1 KYTY_BC5_POSIX_RET_FIXES=1 ./fs0405     (on)
//   KYTY_BC5_FS_FIXES=0 KYTY_BC5_POSIX_RET_FIXES=0 ./fs0405     (off)
//   ./fs0405                                                     (both unset: off)
// The program reads both switches with the units' grammar (unset, empty or "0": off; a comma list of item names: only
// those; any other value: all items) and each case expects the setting of its own item. With an item off, the case
// expects today's behaviour; a case whose today's code EXITs the process is not run with its item off (a "not run"
// line names the EXIT; it is not counted). One line per case, then exactly "fs0405: on N of N; end" (every item on) or
// "fs0405: off N of N; end" (every item off; also for unset) or "fs0405: mixed N of N; end" (a comma list), exit 0 only
// then. A failed case: "fs0405: on|off|mixed P of N passed; FAIL", exit 1. Setup failure: exit 2. A watchdog ends a
// hang after 60 s with a FAIL line (exit 3). The units print "[bc5] exp 0405: fs fixes on|off ..." and "[bc5] exp 0405:
// posix return fixes on|off ..." on stderr once each.
// Cases (fs0405-notes.md has the reasons; [item] in each line):
//   kk04  1 rename of an open file, its descriptor follows (write, fstat, fsync) and an unlink of its new name works (on
//          only); 2 rename onto an open target: the old descriptor keeps the old file, a truncate by name reaches the
//          new one (on only); 3 rename of a directory (on: OK, an open descriptor of it still works, ENOTEMPTY,
//          an empty target replaced, ENOTDIR; off: ENOENT as today); 4 a rename onto the same file (on: OK, kept; off:
//          today's EIO with the file deleted); 5 a closed file, a missing one, a file onto a directory (EISDIR on, EIO
//          off); 6 an unlinked open file, then a new file of that name truncated by name (on: the new one; off: today's
//          code truncates the unlinked file of the open descriptor)
//   sk04  7 O_ACCMODE 3 is EINVAL (on only); 8 a directory opened for writing, O_CREAT, O_EXCL, O_TRUNC is refused
//          and no descriptor is left behind (on only); 9 a directory opened for reading (both); 10 100 opens with
//          O_TRUNC|O_RDONLY: EACCES, and the next descriptor is the same (on) or 100 higher (off, today's leak)
//   blksize 11 stat and fstat of a directory: st_blksize 0x10000 on, 512 off; files 512 in both
//   nametoolong 12 a path of 1024 bytes, 13 a component of 256 bytes (open, stat, unlink, rmdir, mkdir, rename both ways,
//          CheckReachability), 14 the limits: 1023 bytes, a 255-byte component, a 300-byte path with short components
//   kk10  15 write and pwrite on a read-only descriptor and on a directory: EBADF on; off 0 bytes / EISDIR as today
//   sk05  16 ".", "..", "//", ".." out of a mount, the longest mount point, open("/temp0", O_RDONLY)
//   posix 17 the seven registrations (InitLibKernel_1 into a SymbolDatabase): at the wrappers on, at today's functions
//          off; through them: 18 unlink, 19 munmap, 20 mprotect (-1 and errno on, SCE codes off), 21
//          pthread_rwlock_trywrlock (errno numbers on, SCE codes off), 22 scePthreadGet/Setschedparam and 23
//          scePthreadOnce (SCE codes on, errno numbers off)
// Build (box0401's build0401.py, series e5): this file compiled with src/kernel/fileSystem.cpp's compile command
// (--gate fs0405.cpp <out> --like src/kernel/fileSystem.cpp) and linked with every emulator object but main.cpp.o, the
// private fileSystem.cpp.o and libKernel.cpp.o (mkfs0405.py's outputs) in place of the shared ones. It needs only the
// tree's own headers. Linked with the shared libKernel.cpp.o it still links (no new symbol is used), but case 17 then
// fails with the switch on.
// Runtime state: Threads (the "main thread" for the constructors), Pthread (rwlocks, the posix wrappers) and
// FileSystem (the mount table and the descriptors), initialised on a helper thread that then ends (pth0401's way:
// PRINT_NAME stays off on every thread that calls the units); this thread then gets its own PthreadPrivate. Logging off
// (Log::Bc5SetLogging(false)). No read through a descriptor is made: KernelRead/KernelPread invalidate the GPU's view
// of the buffer, which needs the graphics side; the data are checked on the host and through fstat instead.

#include "common/abi.h"
#include "common/logging/log.h"
#include "common/subsystems.h"
#include "common/threads.h"
#include "kernel/fileSystem.h"
#include "kernel/memory.h"
#include "kernel/pthread.h"
#include "libs/errno.h"
#include "loader/symbolDatabase.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <system_error>
#include <thread>
#include <vector>

#include <sched.h> // struct sched_param (LK::KernelSchedParam), which kernel/pthread.h only declares
#include <unistd.h>

namespace Libs {
void InitLibKernel_1(Loader::SymbolDatabase* s); // libKernel.cpp's LIB_DEFINE(InitLibKernel_1)
} // namespace Libs

namespace {

namespace LK = Libs::LibKernel;
namespace FS = Libs::LibKernel::FileSystem;
using Clock  = std::chrono::steady_clock;

constexpr int kWatchdogSeconds = 60;

// FreeBSD's open flags, as KernelOpen reads them.
constexpr int kRdonly = 0, kWronly = 1, kRdwr = 2, kAccmode3 = 3, kCreat = 0x200, kTrunc = 0x400, kExcl = 0x800;
constexpr int kDirectory = 0x20000;

// ---- the switches, read as the units read them ------------------------------------------------------------------------
const char* const kFsItems[]    = {"kk04", "sk04", "blksize", "nametoolong", "kk10", "sk05"};
const char* const kPosixItems[] = {"unlink", "munmap", "mprotect", "trywrlock", "schedparam", "once"};

uint32_t ParseItems(const char* e, const char* const* names, int count) {
	if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
		return 0;
	}
	uint32_t    items = 0;
	const char* p     = e;
	for (;;) {
		const char*  comma = std::strchr(p, ',');
		const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
		for (int k = 0; k < count; k++) {
			if (std::strlen(names[k]) == n && std::strncmp(p, names[k], n) == 0) {
				items |= 1u << static_cast<uint32_t>(k);
			}
		}
		if (comma == nullptr) {
			break;
		}
		p = comma + 1;
	}
	return items != 0 ? items : (1u << static_cast<uint32_t>(count)) - 1u;
}

uint32_t g_fs    = 0;
uint32_t g_posix = 0;

bool On(const char* item) {
	for (int k = 0; k < 6; k++) {
		if (std::strcmp(item, kFsItems[k]) == 0) {
			return (g_fs & (1u << static_cast<uint32_t>(k))) != 0;
		}
		if (std::strcmp(item, kPosixItems[k]) == 0) {
			return (g_posix & (1u << static_cast<uint32_t>(k))) != 0;
		}
	}
	std::printf("fs0405: FAIL setup: unknown item %s\n", item);
	std::fflush(stdout);
	_exit(2);
}

// ---- reporting ----------------------------------------------------------------------------------------------------------
std::atomic<int>         g_cases {0};
std::atomic<int>         g_passed {0};
std::atomic<int>         g_not_run {0};
std::atomic<const char*> g_case {"start"};
std::atomic<bool>        g_finished {false};

std::string Fmt(const char* format, ...) __attribute__((format(printf, 1, 2)));
std::string Fmt(const char* format, ...) {
	char    buf[2048];
	va_list args;
	va_start(args, format);
	std::vsnprintf(buf, sizeof(buf), format, args);
	va_end(args);
	return buf;
}

// "posix" (case 17) covers the six items of KYTY_BC5_POSIX_RET_FIXES; each line of it names its own item's setting.
const char* ItemLabel(const char* item) {
	if (std::strcmp(item, "posix") == 0) {
		return g_posix == 0x3fu ? "on" : (g_posix == 0 ? "off" : "mixed");
	}
	return On(item) ? "on" : "off";
}

void Report(const char* item, const char* name, bool ok, const std::string& info) {
	g_cases++;
	if (ok) {
		g_passed++;
	}
	std::printf("fs0405: case %d [%s %s] %s: %s (%s)\n", g_cases.load(), item, ItemLabel(item), name, ok ? "ok" : "FAIL",
	            info.c_str());
	std::fflush(stdout);
}

void NotRun(const char* item, const char* name, const char* why) {
	g_not_run++;
	std::printf("fs0405: not run [%s off] %s: %s\n", item, name, why);
	std::fflush(stdout);
}

[[noreturn]] void SetupFail(const std::string& what) {
	std::printf("fs0405: FAIL setup: %s\n", what.c_str());
	std::fflush(stdout);
	_exit(2);
}

void Watchdog() {
	const auto start = Clock::now();
	while (!g_finished.load()) {
		std::this_thread::sleep_for(std::chrono::milliseconds(50));
		if (Clock::now() - start > std::chrono::seconds(kWatchdogSeconds)) {
			std::printf("fs0405: FAIL watchdog: case \"%s\" still running after %d s (a hang); %d of %d cases passed before it\n",
			            g_case.load(), kWatchdogSeconds, g_passed.load(), g_cases.load());
			std::fflush(stdout);
			_exit(3);
		}
	}
}

// An SCE result (or a descriptor, or a byte count) by name.
std::string K(int64_t r) {
	switch (r) {
		case LK::KERNEL_ERROR_EPERM: return "EPERM";
		case LK::KERNEL_ERROR_ENOENT: return "ENOENT";
		case LK::KERNEL_ERROR_EIO: return "EIO";
		case LK::KERNEL_ERROR_EBADF: return "EBADF";
		case LK::KERNEL_ERROR_EDEADLK: return "EDEADLK";
		case LK::KERNEL_ERROR_EACCES: return "EACCES";
		case LK::KERNEL_ERROR_EBUSY: return "EBUSY";
		case LK::KERNEL_ERROR_EEXIST: return "EEXIST";
		case LK::KERNEL_ERROR_EXDEV: return "EXDEV";
		case LK::KERNEL_ERROR_ENOTDIR: return "ENOTDIR";
		case LK::KERNEL_ERROR_EISDIR: return "EISDIR";
		case LK::KERNEL_ERROR_EINVAL: return "EINVAL";
		case LK::KERNEL_ERROR_ENAMETOOLONG: return "ENAMETOOLONG";
		case LK::KERNEL_ERROR_ENOTEMPTY: return "ENOTEMPTY";
		default: break;
	}
	if (r < 0) {
		return Fmt("0x%08x", static_cast<unsigned>(static_cast<uint32_t>(r)));
	}
	return Fmt("%lld", static_cast<long long>(r));
}

// ---- host and guest helpers ---------------------------------------------------------------------------------------------
std::filesystem::path g_work, g_mnt, g_mnt2, g_nested;

void HostWrite(const std::filesystem::path& p, const std::string& s) {
	std::ofstream f(p, std::ios::binary | std::ios::trunc);
	f << s;
	f.close();
	if (!f) {
		SetupFail("cannot write " + p.string());
	}
}

std::string HostRead(const std::filesystem::path& p) {
	std::error_code ec;
	if (!std::filesystem::is_regular_file(p, ec)) {
		return "<missing>";
	}
	std::ifstream f(p, std::ios::binary);
	return std::string((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}

bool HostExists(const std::filesystem::path& p) {
	std::error_code ec;
	return std::filesystem::exists(p, ec);
}

void HostMkdirs(const std::filesystem::path& p) {
	std::error_code ec;
	std::filesystem::create_directories(p, ec);
	if (ec) {
		SetupFail("cannot make " + p.string());
	}
}

int Open(const std::string& path, int flags) {
	return FS::KernelOpen(path.c_str(), flags, 0666);
}

int64_t Write(int fd, const std::string& s) {
	return FS::KernelWrite(fd, s.data(), s.size());
}

int64_t Pwrite(int fd, const std::string& s, int64_t offset) {
	return FS::KernelPwrite(fd, s.data(), s.size(), offset);
}

int Rename(const std::string& from, const std::string& to) {
	return FS::KernelRename(from.c_str(), to.c_str());
}

int Unlink(const std::string& path) {
	return FS::KernelUnlink(path.c_str());
}

int Mkdir(const std::string& path) {
	return FS::KernelMkdir(path.c_str(), 0777);
}

int Rmdir(const std::string& path) {
	return FS::KernelRmdir(path.c_str());
}

// The size through fstat, or the error.
int64_t FstatSize(int fd) {
	FS::FileStat sb {};
	const int    r = FS::KernelFstat(fd, &sb);
	return r == OK ? sb.st_size : r;
}

struct StatResult {
	int      r       = -1;
	uint32_t blksize = 0;
	bool     dir     = false;
};

StatResult Stat(const std::string& path) {
	FS::FileStat sb {};
	StatResult   s;
	s.r       = FS::KernelStat(path.c_str(), &sb);
	s.blksize = sb.st_blksize;
	s.dir     = (sb.st_mode & 0170000u) == 0040000u;
	return s;
}

StatResult Fstat(int fd) {
	FS::FileStat sb {};
	StatResult   s;
	s.r       = FS::KernelFstat(fd, &sb);
	s.blksize = sb.st_blksize;
	s.dir     = (sb.st_mode & 0170000u) == 0040000u;
	return s;
}

// The lowest free descriptor now: open a file and close it again.
int LowestFree() {
	const int fd = Open("/temp0/probe.txt", kRdonly);
	if (fd < 3 || FS::KernelClose(fd) != OK) {
		SetupFail(Fmt("probe open %s", K(fd).c_str()));
	}
	return fd;
}

// A guest path under /temp0 of exactly n bytes, components of at most 100 bytes, letter c.
std::string PathOfLength(size_t n, char c) {
	std::string s = "/temp0";
	while (s.size() + 101 + 2 <= n) {
		s += "/" + std::string(100, c);
	}
	s += "/" + std::string(n - s.size() - 1, c);
	if (s.size() != n) {
		SetupFail("PathOfLength");
	}
	return s;
}

// =========================================================================================================================
// kk04
// =========================================================================================================================
void Case1RenameOpenFile() {
	g_case = "rename of an open file";
	if (!On("kk04")) {
		NotRun("kk04", "rename of an open file", "today's code EXITs when either path is open (fileSystem.cpp:1456-1457)");
		return;
	}
	const int     fd = Open("/temp0/k1a.txt", kCreat | kRdwr);
	const int64_t w1 = Write(fd, "hello");
	const int     r  = Rename("/temp0/k1a.txt", "/temp0/k1b.txt");
	const int64_t w2 = Write(fd, " world");
	const int64_t sz = FstatSize(fd);
	const int     fs = FS::KernelFsync(fd); // opens the file by the descriptor's host name: the new one
	const int     c  = FS::KernelClose(fd);

	const int     fd2 = Open("/temp0/k1c.txt", kCreat | kRdwr);
	const int64_t w3  = Write(fd2, "x");
	const int     r2  = Rename("/temp0/k1c.txt", "/temp0/k1d.txt");
	const int     u   = Unlink("/temp0/k1d.txt"); // today's Unlink() of the open file would delete its first name
	const int64_t w4  = Write(fd2, "y");
	const int     c2  = FS::KernelClose(fd2);

	const std::string b  = HostRead(g_mnt / "k1b.txt");
	const bool        ok = fd >= 3 && w1 == 5 && r == OK && w2 == 6 && sz == 11 && fs == OK && c == OK && b == "hello world" &&
	                !HostExists(g_mnt / "k1a.txt") && fd2 >= 3 && w3 == 1 && r2 == OK && u == OK && w4 == 1 && c2 == OK &&
	                !HostExists(g_mnt / "k1c.txt") && !HostExists(g_mnt / "k1d.txt");
	Report("kk04", "rename of an open file", ok,
	       Fmt("open %s, write %s, rename %s, write through the descriptor %s, fstat size %s, fsync %s, close %s; host "
	           "b \"%s\", a %s; second file: rename while open %s, unlink of the new name %s, write after %s, gone %s",
	           K(fd).c_str(), K(w1).c_str(), K(r).c_str(), K(w2).c_str(), K(sz).c_str(), K(fs).c_str(), K(c).c_str(),
	           b.c_str(), HostExists(g_mnt / "k1a.txt") ? "still there" : "gone", K(r2).c_str(), K(u).c_str(),
	           K(w4).c_str(), HostExists(g_mnt / "k1d.txt") ? "no" : "yes"));
}

void Case2RenameOntoOpenTarget() {
	g_case = "rename onto an open target";
	if (!On("kk04")) {
		NotRun("kk04", "rename onto an open target", "today's code EXITs when either path is open (fileSystem.cpp:1456-1457)");
		return;
	}
	const int     ft = Open("/temp0/k2t.txt", kCreat | kRdwr);
	const int64_t w1 = Write(ft, "old");
	HostWrite(g_mnt / "k2s.txt", "new");
	const int     r   = Rename("/temp0/k2s.txt", "/temp0/k2t.txt");
	const int64_t w2  = Write(ft, "!"); // the replaced file
	const int64_t sz  = FstatSize(ft);
	const int     tr  = FS::KernelTruncate("/temp0/k2t.txt", 1); // the new file of that name, not the open one
	const int64_t sz2 = FstatSize(ft);
	const int     c   = FS::KernelClose(ft);

	const std::string t  = HostRead(g_mnt / "k2t.txt");
	const bool        ok = ft >= 3 && w1 == 3 && r == OK && w2 == 1 && sz == 4 && tr == OK && sz2 == 4 && c == OK && t == "n" &&
	                !HostExists(g_mnt / "k2s.txt");
	Report("kk04", "rename onto an open target", ok,
	       Fmt("rename %s; the old descriptor writes %s, its fstat size %s; truncate by name to 1 %s, then the old "
	           "descriptor's size %s; host t \"%s\" (want \"n\"), s %s",
	           K(r).c_str(), K(w2).c_str(), K(sz).c_str(), K(tr).c_str(), K(sz2).c_str(), t.c_str(),
	           HostExists(g_mnt / "k2s.txt") ? "still there" : "gone"));
}

void Case3RenameDirectory() {
	g_case = "rename of a directory";
	const int mk = Mkdir("/temp0/k3d");
	HostWrite(g_mnt / "k3d" / "f.txt", "f");
	if (!On("kk04")) {
		const int  r  = Rename("/temp0/k3d", "/temp0/k3e");
		const bool ok = mk == OK && r == LK::KERNEL_ERROR_ENOENT && HostRead(g_mnt / "k3d" / "f.txt") == "f" &&
		                !HostExists(g_mnt / "k3e");
		Report("kk04", "rename of a directory", ok,
		       Fmt("off, today's code: rename of a directory %s (want ENOENT), the directory unchanged %s", K(r).c_str(),
		           HostRead(g_mnt / "k3d" / "f.txt") == "f" ? "yes" : "no"));
		return;
	}
	const int        fdd = Open("/temp0/k3d", kDirectory | kRdonly);
	const int        r1  = Rename("/temp0/k3d", "/temp0/k3e");
	const StatResult fst = Fstat(fdd);
	const int        cd  = FS::KernelClose(fdd);
	const int        m2  = Mkdir("/temp0/k3full");
	HostWrite(g_mnt / "k3full" / "g.txt", "g");
	const int m3 = Mkdir("/temp0/k3empty");
	const int r2 = Rename("/temp0/k3e", "/temp0/k3full");
	const int r3 = Rename("/temp0/k3e", "/temp0/k3empty");
	HostWrite(g_mnt / "k3file.txt", "z");
	const int  r4 = Rename("/temp0/k3empty", "/temp0/k3file.txt");
	const bool ok = mk == OK && fdd >= 3 && r1 == OK && fst.r == OK && fst.dir && cd == OK && m2 == OK && m3 == OK &&
	                r2 == LK::KERNEL_ERROR_ENOTEMPTY && r3 == OK && r4 == LK::KERNEL_ERROR_ENOTDIR &&
	                HostRead(g_mnt / "k3empty" / "f.txt") == "f" && HostRead(g_mnt / "k3full" / "g.txt") == "g" &&
	                !HostExists(g_mnt / "k3d") && !HostExists(g_mnt / "k3e") && HostRead(g_mnt / "k3file.txt") == "z";
	Report("kk04", "rename of a directory", ok,
	       Fmt("rename of an open directory %s, its descriptor's fstat %s, close %s; onto a non-empty directory %s (want "
	           "ENOTEMPTY), onto an empty one %s, then onto a file %s (want ENOTDIR); contents moved %s",
	           K(r1).c_str(), K(fst.r).c_str(), K(cd).c_str(), K(r2).c_str(), K(r3).c_str(), K(r4).c_str(),
	           HostRead(g_mnt / "k3empty" / "f.txt") == "f" ? "yes" : "no"));
}

void Case4RenameOntoItself() {
	g_case = "rename onto the same file";
	HostWrite(g_mnt / "k4.txt", "keep");
	const int         r    = Rename("/temp0/k4.txt", "/temp0/k4.txt");
	const std::string left = HostRead(g_mnt / "k4.txt");
	const bool        ok   = On("kk04") ? (r == OK && left == "keep") : (r == LK::KERNEL_ERROR_EIO && left == "<missing>");
	Report("kk04", "rename onto the same file", ok,
	       Fmt("%s: rename %s, the file %s", On("kk04") ? "on, want OK and the file kept" : "off, today's code: EIO and the file deleted",
	           K(r).c_str(), left.c_str()));
}

void Case5RenameClosedFiles() {
	g_case = "rename of closed and missing files";
	HostWrite(g_mnt / "k5a.txt", "c");
	const int r1 = Rename("/temp0/k5a.txt", "/temp0/k5b.txt");
	const int r2 = Rename("/temp0/k5missing.txt", "/temp0/k5x.txt");
	HostMkdirs(g_mnt / "k5dir");
	const int  r3   = Rename("/temp0/k5b.txt", "/temp0/k5dir");
	const int  want = On("kk04") ? LK::KERNEL_ERROR_EISDIR : LK::KERNEL_ERROR_EIO;
	const bool ok   = r1 == OK && HostRead(g_mnt / "k5b.txt") == "c" && !HostExists(g_mnt / "k5a.txt") &&
	                r2 == LK::KERNEL_ERROR_ENOENT && !HostExists(g_mnt / "k5x.txt") && r3 == want &&
	                std::filesystem::is_directory(g_mnt / "k5dir");
	Report("kk04", "rename of closed and missing files", ok,
	       Fmt("a closed file %s (moved %s), a missing one %s, a file onto a directory %s (want %s), the file kept %s",
	           K(r1).c_str(), HostRead(g_mnt / "k5b.txt") == "c" ? "yes" : "no", K(r2).c_str(), K(r3).c_str(),
	           K(want).c_str(), HostRead(g_mnt / "k5b.txt") == "c" ? "yes" : "no"));
}

void Case6UnlinkOpenThenNew() {
	g_case = "unlink of an open file, then a new file of that name";
	const int     fu = Open("/temp0/k6.txt", kCreat | kRdwr);
	const int64_t w1 = Write(fu, "first");
	const int     u  = Unlink("/temp0/k6.txt");
	const bool    gone = !HostExists(g_mnt / "k6.txt");
	const int     fn = Open("/temp0/k6.txt", kCreat | kRdwr);
	const int64_t w2 = Write(fn, "fresh");
	const int     c1 = FS::KernelClose(fn);
	const int     tr = FS::KernelTruncate("/temp0/k6.txt", 2);
	const int64_t w3 = Write(fu, "x");
	const int64_t sz = FstatSize(fu);
	const int     c2 = FS::KernelClose(fu);

	const std::string now  = HostRead(g_mnt / "k6.txt");
	const std::string want = On("kk04") ? "fr" : "fresh";
	// Off, today's code truncates the first open file of that host name: the unlinked one (6 bytes after the write, 2
	// after the truncate and then the "x" at offset 5: 6 again); on, the new file.
	const bool ok = fu >= 3 && w1 == 5 && u == OK && gone && fn >= 3 && w2 == 5 && c1 == OK && tr == OK && w3 == 1 &&
	                c2 == OK && now == want && sz == 6;
	Report("kk04", "unlink of an open file, then a new file of that name", ok,
	       Fmt("unlink of the open file %s (gone %s); new file written %s; truncate by name to 2 %s: the new file \"%s\" "
	           "(want \"%s\"%s); the unlinked file's descriptor writes %s, size %s",
	           K(u).c_str(), gone ? "yes" : "no", K(w2).c_str(), K(tr).c_str(), now.c_str(), want.c_str(),
	           On("kk04") ? "" : ", today's code truncates the unlinked file", K(w3).c_str(), K(sz).c_str()));
}

// =========================================================================================================================
// sk04
// =========================================================================================================================
void Case7Accmode3() {
	g_case = "O_ACCMODE 3";
	if (!On("sk04")) {
		NotRun("sk04", "O_ACCMODE 3", "today's code EXITs on it (fileSystem.cpp:469)");
		return;
	}
	const int  base  = LowestFree();
	const int  r     = Open("/temp0/probe.txt", kAccmode3);
	const int  after = LowestFree();
	const bool ok    = r == LK::KERNEL_ERROR_EINVAL && after == base;
	Report("sk04", "O_ACCMODE 3", ok, Fmt("open %s (want EINVAL); lowest free descriptor %d before, %d after", K(r).c_str(), base, after));
}

void Case8DirectoryForWriting() {
	g_case = "a directory opened for writing";
	if (!On("sk04")) {
		NotRun("sk04", "a directory opened for writing", "today's code EXITs on these (fileSystem.cpp:472-473, 532-533)");
		return;
	}
	const std::string dir  = "/temp0/s8dir";
	const int         base = LowestFree();
	struct Try {
		const char* what;
		std::string path;
		int         flags;
		int         want;
		int         got;
	};
	std::vector<Try> tries = {
	    {"O_WRONLY", dir, kWronly, LK::KERNEL_ERROR_EISDIR, 0},
	    {"O_RDWR", dir, kRdwr, LK::KERNEL_ERROR_EISDIR, 0},
	    {"O_RDONLY|O_CREAT", dir, kRdonly | kCreat, LK::KERNEL_ERROR_EISDIR, 0},
	    {"O_RDONLY|O_CREAT|O_EXCL", dir, kRdonly | kCreat | kExcl, LK::KERNEL_ERROR_EEXIST, 0},
	    {"O_DIRECTORY|O_RDWR", dir, kDirectory | kRdwr, LK::KERNEL_ERROR_EISDIR, 0},
	    {"O_DIRECTORY|O_WRONLY|O_CREAT", dir, kDirectory | kWronly | kCreat, LK::KERNEL_ERROR_EISDIR, 0},
	    {"O_DIRECTORY|O_RDONLY|O_TRUNC", dir, kDirectory | kRdonly | kTrunc, LK::KERNEL_ERROR_EACCES, 0},
	    {"O_DIRECTORY|O_WRONLY, a file", "/temp0/probe.txt", kDirectory | kWronly, LK::KERNEL_ERROR_ENOTDIR, 0},
	    {"O_DIRECTORY|O_WRONLY, missing", "/temp0/s8missing", kDirectory | kWronly, LK::KERNEL_ERROR_ENOENT, 0},
	};
	bool        ok = true;
	std::string info;
	for (auto& t: tries) {
		t.got = Open(t.path, t.flags);
		ok    = ok && t.got == t.want;
		info += Fmt("%s%s %s%s", info.empty() ? "" : ", ", t.what, K(t.got).c_str(), t.got == t.want ? "" : Fmt(" (want %s)", K(t.want).c_str()).c_str());
		if (t.got >= 3) {
			FS::KernelClose(t.got);
		}
	}
	const int after = LowestFree();
	ok              = ok && after == base && std::filesystem::is_directory(g_mnt / "s8dir");
	Report("sk04", "a directory opened for writing", ok,
	       Fmt("%s; lowest free descriptor %d before, %d after (want the same)", info.c_str(), base, after));
}

void Case9DirectoryForReading() {
	g_case = "a directory opened for reading";
	const int  a  = Open("/temp0/s8dir", kRdonly);
	const int  ca = a >= 3 ? FS::KernelClose(a) : -1;
	const int  b  = Open("/temp0/s8dir", kDirectory | kRdonly);
	const int  cb = b >= 3 ? FS::KernelClose(b) : -1;
	const bool ok = a >= 3 && ca == OK && b >= 3 && cb == OK;
	Report("sk04", "a directory opened for reading", ok,
	       Fmt("O_RDONLY %s (close %s), O_DIRECTORY|O_RDONLY %s (close %s), the same in both settings", K(a).c_str(),
	           K(ca).c_str(), K(b).c_str(), K(cb).c_str()));
}

void Case10TruncReadOnlyLeak() {
	g_case = "O_TRUNC|O_RDONLY: EACCES and the descriptor";
	constexpr int kTries = 100;
	HostWrite(g_mnt / "s10.txt", "data");
	const int base   = LowestFree();
	int       eacces = 0;
	for (int k = 0; k < kTries; k++) {
		eacces += Open("/temp0/s10.txt", kRdonly | kTrunc) == LK::KERNEL_ERROR_EACCES ? 1 : 0;
	}
	const int  after = LowestFree();
	const int  want  = On("sk04") ? base : base + kTries;
	const bool ok    = eacces == kTries && after == want && HostRead(g_mnt / "s10.txt") == "data";
	Report("sk04", "O_TRUNC|O_RDONLY: EACCES and the descriptor", ok,
	       Fmt("%d of %d opens EACCES; lowest free descriptor %d before, %d after (want %d%s); the file kept %s", eacces,
	           kTries, base, after, want, On("sk04") ? "" : ": today's code leaves one descriptor per refusal",
	           HostRead(g_mnt / "s10.txt") == "data" ? "yes" : "no"));
}

// =========================================================================================================================
// blksize
// =========================================================================================================================
void Case11Blksize() {
	g_case = "st_blksize";
	const uint32_t   want = On("blksize") ? 0x10000u : 512u;
	const StatResult sd   = Stat("/temp0/s8dir");
	const int        fdd  = Open("/temp0/s8dir", kDirectory | kRdonly);
	const StatResult fd   = Fstat(fdd);
	const int        cd   = FS::KernelClose(fdd);
	const StatResult sf   = Stat("/temp0/probe.txt");
	const int        ff   = Open("/temp0/probe.txt", kRdonly);
	const StatResult fs   = Fstat(ff);
	const int        cf   = FS::KernelClose(ff);
	const bool ok = sd.r == OK && sd.dir && sd.blksize == want && fdd >= 3 && fd.r == OK && fd.dir && fd.blksize == want &&
	                cd == OK && sf.r == OK && !sf.dir && sf.blksize == 512 && ff >= 3 && fs.r == OK && fs.blksize == 512 &&
	                cf == OK;
	Report("blksize", "st_blksize", ok,
	       Fmt("directory: stat 0x%x, fstat 0x%x (want 0x%x); file: stat 0x%x, fstat 0x%x (want 0x200)", sd.blksize,
	           fd.blksize, want, sf.blksize, fs.blksize));
}

// =========================================================================================================================
// nametoolong
// =========================================================================================================================
struct PathCalls {
	int stat = 0, open = 0, unlink = 0, rmdir = 0, mkdir = 0, rename_from = 0, reach = 0;
};

PathCalls CallAll(const std::string& p) {
	PathCalls c;
	c.stat        = Stat(p).r;
	c.open        = Open(p, kRdonly);
	c.unlink      = Unlink(p);
	c.rmdir       = Rmdir(p);
	c.mkdir       = Mkdir(p);
	c.rename_from = Rename(p, "/temp0/n-target.txt");
	c.reach       = FS::KernelCheckReachability(p.c_str());
	if (c.open >= 3) {
		FS::KernelClose(c.open);
	}
	return c;
}

std::string Show(const PathCalls& c) {
	return Fmt("stat %s, open %s, unlink %s, rmdir %s, mkdir %s, rename from %s, CheckReachability %s", K(c.stat).c_str(),
	           K(c.open).c_str(), K(c.unlink).c_str(), K(c.rmdir).c_str(), K(c.mkdir).c_str(), K(c.rename_from).c_str(),
	           K(c.reach).c_str());
}

void Case12Path1024() {
	g_case = "a path of 1024 bytes";
	const std::string p = PathOfLength(1024, 'p');
	const PathCalls   c = CallAll(p);
	HostWrite(g_mnt / "n12src.txt", "s");
	const int  rto = Rename("/temp0/n12src.txt", p); // last: off, today's code moves the file there (the host allows it)
	const int  T   = LK::KERNEL_ERROR_ENAMETOOLONG, N = LK::KERNEL_ERROR_ENOENT;
	bool       ok  = false;
	if (On("nametoolong")) {
		ok = c.stat == T && c.open == T && c.unlink == T && c.rmdir == T && c.mkdir == T && c.rename_from == T && c.reach == T &&
		     rto == T && HostRead(g_mnt / "n12src.txt") == "s";
	} else {
		ok = c.stat == N && c.open == N && c.unlink == N && c.rmdir == N && c.mkdir == T && c.rename_from == N && c.reach == T &&
		     rto == OK && !HostExists(g_mnt / "n12src.txt");
	}
	Report("nametoolong", "a path of 1024 bytes", ok,
	       Fmt("%s; rename to it %s; %s", Show(c).c_str(), K(rto).c_str(),
	           On("nametoolong") ? "want ENAMETOOLONG everywhere"
	                             : "off, today's code: ENOENT, mkdir and CheckReachability ENAMETOOLONG (over 255), the rename to it moves the file"));
}

void Case13Component256() {
	g_case = "a component of 256 bytes";
	const std::string p = "/temp0/" + std::string(256, 'c');
	const PathCalls   c = CallAll(p);
	const int         T = LK::KERNEL_ERROR_ENAMETOOLONG, N = LK::KERNEL_ERROR_ENOENT;
	bool              ok = false;
	if (On("nametoolong")) {
		ok = c.stat == T && c.open == T && c.unlink == T && c.rmdir == T && c.mkdir == T && c.rename_from == T && c.reach == T;
	} else {
		ok = c.stat == N && c.open == N && c.unlink == N && c.rmdir == N && c.mkdir == T && c.rename_from == N && c.reach == T;
	}
	Report("nametoolong", "a component of 256 bytes", ok,
	       Fmt("%s; %s", Show(c).c_str(),
	           On("nametoolong") ? "want ENAMETOOLONG everywhere"
	                             : "off, today's code: ENOENT, mkdir and CheckReachability ENAMETOOLONG (over 255)"));
}

void Case14Limits() {
	g_case = "lengths at the limits";
	const bool        on    = On("nametoolong");
	const std::string p1023 = PathOfLength(1023, 'r');
	const int         s1023 = Stat(p1023).r;
	const std::string c255  = "/temp0/" + std::string(255, 'b');
	const int         m255  = Mkdir(c255);
	const StatResult  s255  = Stat(c255);
	const int         r255  = on ? Rmdir(c255) : OK;
	// A 300-byte path of short components: its parent (over 255 bytes) made on the host.
	std::string parent = "/temp0";
	for (int k = 0; k < 13; k++) {
		parent += "/" + std::string(21, static_cast<char>('a' + k));
	}
	HostMkdirs(g_mnt / parent.substr(std::strlen("/temp0/")));
	const std::string leaf  = parent + "/leaf";
	const int         mleaf = Mkdir(leaf);
	const int         reach = FS::KernelCheckReachability(parent.c_str());
	const int         T     = LK::KERNEL_ERROR_ENAMETOOLONG, N = LK::KERNEL_ERROR_ENOENT;
	bool              ok    = false;
	if (on) {
		ok = s1023 == N && m255 == OK && s255.r == OK && s255.dir && r255 == OK && mleaf == OK && reach == OK &&
		     std::filesystem::is_directory(g_mnt / leaf.substr(std::strlen("/temp0/")));
	} else {
		ok = s1023 == N && m255 == T && s255.r == N && mleaf == T && reach == T;
	}
	Report("nametoolong", "lengths at the limits", ok,
	       Fmt("1023 bytes: stat %s (want ENOENT); a 255-byte component: mkdir %s, stat %s%s; a %zu-byte path of short "
	           "components: mkdir %s, CheckReachability of its %zu-byte parent %s%s",
	           K(s1023).c_str(), K(m255).c_str(), K(s255.r).c_str(), on ? Fmt(", rmdir %s", K(r255).c_str()).c_str() : "",
	           leaf.size(), K(mleaf).c_str(), parent.size(), K(reach).c_str(),
	           on ? "" : "; off, today's code refuses any mkdir or CheckReachability path over 255 bytes"));
}

// =========================================================================================================================
// kk10
// =========================================================================================================================
void Case15WriteReadOnly() {
	g_case = "write on a read-only descriptor";
	const bool on = On("kk10");
	HostWrite(g_mnt / "k10.txt", "abc");
	const int     fd  = Open("/temp0/k10.txt", kRdonly);
	const int64_t w   = Write(fd, "x");
	const int64_t pw  = Pwrite(fd, "y", 0);
	const int     c   = FS::KernelClose(fd);
	const int     fdd = Open("/temp0/s8dir", kDirectory | kRdonly);
	const int64_t wd  = Write(fdd, "x");
	const int64_t pwd = Pwrite(fdd, "x", 0);
	const int     cd  = FS::KernelClose(fdd);
	const int     fw  = Open("/temp0/k10.txt", kRdwr);
	const int64_t ww  = Write(fw, "Z");
	const int     cw  = FS::KernelClose(fw);
	const int64_t want_file = on ? LK::KERNEL_ERROR_EBADF : 0;
	const int64_t want_dir  = on ? LK::KERNEL_ERROR_EBADF : LK::KERNEL_ERROR_EISDIR;
	const bool    ok = fd >= 3 && w == want_file && pw == want_file && c == OK && fdd >= 3 && wd == want_dir &&
	                pwd == want_dir && cd == OK && fw >= 3 && ww == 1 && cw == OK && HostRead(g_mnt / "k10.txt") == "Zbc";
	Report("kk10", "write on a read-only descriptor", ok,
	       Fmt("read-only file: write %s, pwrite %s (want %s); directory: write %s, pwrite %s (want %s); a read-write "
	           "descriptor writes %s; the file \"%s\" (want \"Zbc\")",
	           K(w).c_str(), K(pw).c_str(), K(want_file).c_str(), K(wd).c_str(), K(pwd).c_str(), K(want_dir).c_str(),
	           K(ww).c_str(), HostRead(g_mnt / "k10.txt").c_str()));
}

// =========================================================================================================================
// sk05
// =========================================================================================================================
void Case16Normalise() {
	g_case = "guest path normalisation";
	const bool on = On("sk05");
	HostWrite(g_mnt / "n16.txt", "a");
	HostWrite(g_work / "outside.txt", "o"); // in this run's own directory, one level above /temp0's
	HostWrite(g_mnt2 / "g.txt", "g");
	HostWrite(g_nested / "h.txt", "h");
	const int a  = Stat("/temp0/n16missing/../n16.txt").r;
	const int b  = Stat("/temp0/./n16.txt").r;
	const int c  = Stat("/temp0/../outside.txt").r;
	const int d  = Stat("/temp0/../temp1/g.txt").r;
	const int e  = Stat("/temp0/sub/h.txt").r;
	const int f  = Open("/temp0", kRdonly);
	const int cf = f >= 3 ? FS::KernelClose(f) : -1;
	const int g  = Stat("/temp0//n16.txt").r;
	const int N  = LK::KERNEL_ERROR_ENOENT;
	bool      ok = false;
	if (on) {
		ok = a == OK && b == OK && c == N && d == OK && e == OK && f >= 3 && cf == OK && g == OK;
	} else {
		ok = a == N && b == OK && c == OK && d == N && e == N && f == N && g == OK;
	}
	Report("sk05", "guest path normalisation", ok,
	       Fmt("/temp0/n16missing/../n16.txt %s, /temp0/./n16.txt %s, /temp0/../outside.txt %s, /temp0/../temp1/g.txt %s, "
	           "/temp0/sub/h.txt (mounts /temp0 then /temp0/sub) %s, open(\"/temp0\", O_RDONLY) %s, /temp0//n16.txt %s; %s",
	           K(a).c_str(), K(b).c_str(), K(c).c_str(), K(d).c_str(), K(e).c_str(), K(f).c_str(), K(g).c_str(),
	           on ? "want OK OK ENOENT OK OK fd OK"
	              : "off, today's code: ENOENT OK OK (out of the mount into this run's directory) ENOENT ENOENT (the first "
	                "mount) ENOENT OK"));
}

// =========================================================================================================================
// posix: libkernel's registrations
// =========================================================================================================================
Loader::SymbolDatabase* g_db = nullptr;

Loader::SymbolResolve Key(const char* library, const char* nid) {
	Loader::SymbolResolve r {};
	r.name                 = nid;
	r.library              = library;
	r.library_version      = 1;
	r.module               = "libkernel";
	r.module_version_major = 1;
	r.module_version_minor = 1;
	r.type                 = Loader::SymbolType::Func;
	return r;
}

struct Reg {
	const char* item;
	const char* library;
	const char* nid;
	const char* name;
	uint64_t    today;
};

const std::vector<Reg>& Regs() {
	static const std::vector<Reg> regs = {
	    {"unlink", "libkernel", "VAzswvTOCzI", "unlink", reinterpret_cast<uint64_t>(&FS::KernelUnlink)},
	    {"munmap", "Posix", "UqDGjXA5yUM", "munmap", reinterpret_cast<uint64_t>(&LK::Memory::KernelMunmap)},
	    {"mprotect", "Posix", "YQOfxL4QfeU", "mprotect", reinterpret_cast<uint64_t>(&LK::Memory::KernelMprotect)},
	    {"trywrlock", "Posix", "XhWHn6P5R7U", "pthread_rwlock_trywrlock", reinterpret_cast<uint64_t>(&LK::PthreadRwlockTrywrlock)},
	    {"schedparam", "Posix", "P41kTWUS3EI", "scePthreadGetschedparam", reinterpret_cast<uint64_t>(&Libs::Posix::pthread_getschedparam)},
	    {"schedparam", "Posix", "oIRFTjoILbg", "scePthreadSetschedparam", reinterpret_cast<uint64_t>(&Libs::Posix::pthread_setschedparam)},
	    {"once", "libkernel", "14bOACANTBo", "scePthreadOnce", reinterpret_cast<uint64_t>(&Libs::Posix::pthread_once)},
	};
	return regs;
}

uint64_t Registered(const char* library, const char* nid) {
	const Loader::SymbolRecord* rec = g_db->Find(Key(library, nid));
	return rec != nullptr ? rec->vaddr : 0;
}

void Case17Registrations() {
	g_case = "the seven registrations";
	bool        ok = true;
	std::string info;
	for (const Reg& r: Regs()) {
		const uint64_t at   = Registered(r.library, r.nid);
		const bool     good = at != 0 && (On(r.item) ? at != r.today : at == r.today);
		ok                  = ok && good;
		info += Fmt("%s%s %s (%s %s): %s%s", info.empty() ? "" : "; ", r.nid, r.name, r.item, On(r.item) ? "on" : "off",
		            at == 0 ? "MISSING" : (at == r.today ? "today's function" : "the wrapper"), good ? "" : " WRONG");
	}
	Report("posix", "the seven registrations", ok, info);
}

int& Errno() {
	return *Libs::Posix::GetErrorAddr();
}

void Case18Unlink() {
	g_case = "posix unlink";
	using Fn          = int(*)(const char*);
	const auto     fn = reinterpret_cast<Fn>(Registered("libkernel", "VAzswvTOCzI"));
	if (fn == nullptr) {
		Report("unlink", "posix unlink", false, "VAzswvTOCzI is not registered");
		return;
	}
	HostWrite(g_mnt / "p18.txt", "u");
	Errno()          = 0;
	const int r1     = fn("/temp0/p18.txt");
	const int e1     = Errno();
	Errno()          = 0;
	const int  r2    = fn("/temp0/p18missing.txt");
	const int  e2    = Errno();
	const bool on    = On("unlink");
	const bool ok    = r1 == 0 && e1 == 0 && !HostExists(g_mnt / "p18.txt") &&
	                (on ? (r2 == -1 && e2 == Libs::Posix::POSIX_ENOENT) : (r2 == LK::KERNEL_ERROR_ENOENT && e2 == 0));
	Report("unlink", "posix unlink", ok,
	       Fmt("an existing file %d (errno %d, removed %s); a missing one %s, errno %d (want %s)", r1, e1,
	           HostExists(g_mnt / "p18.txt") ? "no" : "yes", K(r2).c_str(), e2, on ? "-1, errno 2" : "ENOENT 0x80020002, errno untouched"));
}

void Case19Munmap() {
	g_case = "posix munmap";
	using Fn      = int(*)(uint64_t, size_t);
	const auto fn = reinterpret_cast<Fn>(Registered("Posix", "UqDGjXA5yUM"));
	if (fn == nullptr) {
		Report("munmap", "posix munmap", false, "UqDGjXA5yUM is not registered");
		return;
	}
	Errno()       = 0;
	const int  r  = fn(0x10000, 0); // a length of 0: EINVAL before any mapping is looked at
	const int  e  = Errno();
	const bool on = On("munmap");
	const bool ok = on ? (r == -1 && e == Libs::Posix::POSIX_EINVAL) : (r == LK::KERNEL_ERROR_EINVAL && e == 0);
	Report("munmap", "posix munmap", ok,
	       Fmt("munmap(0x10000, 0) %s, errno %d (want %s)", K(r).c_str(), e, on ? "-1, errno 22" : "EINVAL 0x80020016, errno untouched"));
}

void Case20Mprotect() {
	g_case = "posix mprotect";
	using Fn      = int(*)(const void*, size_t, int);
	const auto fn = reinterpret_cast<Fn>(Registered("Posix", "YQOfxL4QfeU"));
	if (fn == nullptr) {
		Report("mprotect", "posix mprotect", false, "YQOfxL4QfeU is not registered");
		return;
	}
	auto* const addr = reinterpret_cast<const void*>(static_cast<uintptr_t>(0x10000));
	Errno()          = 0;
	const int r0     = fn(addr, 0, 1);          // nothing to protect: OK before any mapping is looked at
	const int e0     = Errno();
	const int r      = fn(addr, 0x4000, 0x100); // no known protection bit: EINVAL before any mapping is looked at
	const int e      = Errno();
	const bool on    = On("mprotect");
	const bool ok    = r0 == 0 && e0 == 0 && (on ? (r == -1 && e == Libs::Posix::POSIX_EINVAL) : (r == LK::KERNEL_ERROR_EINVAL && e == 0));
	Report("mprotect", "posix mprotect", ok,
	       Fmt("mprotect(0x10000, 0, 1) %d; mprotect(0x10000, 0x4000, 0x100) %s, errno %d (want %s)", r0, K(r).c_str(), e,
	           on ? "-1, errno 22" : "EINVAL 0x80020016, errno untouched"));
}

void Case21Trywrlock() {
	g_case = "posix pthread_rwlock_trywrlock";
	using Fn      = int(*)(LK::PthreadRwlock*);
	const auto fn = reinterpret_cast<Fn>(Registered("Posix", "XhWHn6P5R7U"));
	if (fn == nullptr) {
		Report("trywrlock", "posix pthread_rwlock_trywrlock", false, "XhWHn6P5R7U is not registered");
		return;
	}
	LK::PthreadRwlock l = nullptr;
	if (LK::PthreadRwlockInit(&l, nullptr, "fs0405") != OK || l == nullptr) {
		SetupFail("PthreadRwlockInit");
	}
	const int   first = fn(&l);   // free: taken
	const int   again = fn(&l);   // held by this thread
	int         other = -1;
	std::thread t([&] {
		LK::PthreadInitSelfForMainThread();
		other = fn(&l); // held by another thread
	});
	t.join();
	const int  un = LK::PthreadRwlockUnlock(&l);
	const bool on = On("trywrlock");
	const bool ok = first == 0 && un == OK &&
	                (on ? (again == Libs::Posix::POSIX_EDEADLK && other == Libs::Posix::POSIX_EBUSY)
	                    : (again == LK::KERNEL_ERROR_EDEADLK && other == LK::KERNEL_ERROR_EBUSY));
	Report("trywrlock", "posix pthread_rwlock_trywrlock", ok,
	       Fmt("free %d; held by this thread %s; held by another %s (want %s); unlock %s", first, K(again).c_str(),
	           K(other).c_str(), on ? "errno numbers 11, 16" : "SCE codes EDEADLK, EBUSY", K(un).c_str()));
}

void Case22Schedparam() {
	g_case = "scePthreadGet/Setschedparam";
	using GetFn    = int(*)(LK::Pthread, int*, LK::KernelSchedParam*);
	using SetFn    = int(*)(LK::Pthread, int, const LK::KernelSchedParam*);
	const auto get = reinterpret_cast<GetFn>(Registered("Posix", "P41kTWUS3EI"));
	const auto set = reinterpret_cast<SetFn>(Registered("Posix", "oIRFTjoILbg"));
	if (get == nullptr || set == nullptr) {
		Report("schedparam", "scePthreadGet/Setschedparam", false, "P41kTWUS3EI or oIRFTjoILbg is not registered");
		return;
	}
	int                  policy = -1;
	LK::KernelSchedParam param {};
	const int            g_null = get(nullptr, &policy, &param);
	const int            g_self = get(LK::PthreadSelf(), &policy, &param);
	const int            s_null = set(nullptr, policy, &param);
	const int            s_self = set(LK::PthreadSelf(), policy, &param);
	const bool           on     = On("schedparam");
	const int            want   = on ? LK::KERNEL_ERROR_EINVAL : Libs::Posix::POSIX_EINVAL;
	const bool           ok     = g_null == want && s_null == want && g_self == 0 && s_self == 0;
	Report("schedparam", "scePthreadGet/Setschedparam", ok,
	       Fmt("get(NULL) %s, set(NULL) %s (want %s); get(self) %d (policy %d), set(self) %d", K(g_null).c_str(),
	           K(s_null).c_str(), on ? "EINVAL 0x80020016" : "22", g_self, policy, s_self));
}

std::atomic<int> g_once_calls {0};

void OnceRoutine() { // the default x86-64 ABI is the System V one, as KYTY_SYSV_ABI's
	g_once_calls++;
}

void Case23Once() {
	g_case = "scePthreadOnce";
	using Fn      = int(*)(void*, void(*)());
	const auto fn = reinterpret_cast<Fn>(Registered("libkernel", "14bOACANTBo"));
	if (fn == nullptr) {
		Report("once", "scePthreadOnce", false, "14bOACANTBo is not registered");
		return;
	}
	struct {
		int   state;
		void* mutex;
	} once {0, nullptr}; // SCE_PTHREAD_ONCE_INIT, 16 bytes
	const int  r_null = fn(nullptr, &OnceRoutine);
	const int  r1     = fn(&once, &OnceRoutine);
	const int  r2     = fn(&once, &OnceRoutine);
	const bool on     = On("once");
	const int  want   = on ? LK::KERNEL_ERROR_EINVAL : Libs::Posix::POSIX_EINVAL;
	const bool ok     = r_null == want && r1 == 0 && r2 == 0 && g_once_calls.load() == 1;
	Report("once", "scePthreadOnce", ok,
	       Fmt("NULL %s (want %s); first %d, second %d, routine called %d time(s)", K(r_null).c_str(),
	           on ? "EINVAL 0x80020016" : "22", r1, r2, g_once_calls.load()));
}

} // namespace

int main() {
	const char* fs_env    = std::getenv("KYTY_BC5_FS_FIXES");
	const char* posix_env = std::getenv("KYTY_BC5_POSIX_RET_FIXES");
	g_fs                  = ParseItems(fs_env, kFsItems, 6);
	g_posix               = ParseItems(posix_env, kPosixItems, 6);
	const char* label     = (g_fs == 0x3fu && g_posix == 0x3fu) ? "on" : ((g_fs == 0 && g_posix == 0) ? "off" : "mixed");
	std::printf("fs0405: KYTY_BC5_FS_FIXES=%s KYTY_BC5_POSIX_RET_FIXES=%s, so %s (fs items 0x%02x, posix items 0x%02x)\n",
	            fs_env != nullptr ? (fs_env[0] != '\0' ? fs_env : "(empty)") : "(unset)",
	            posix_env != nullptr ? (posix_env[0] != '\0' ? posix_env : "(empty)") : "(unset)", label, g_fs, g_posix);
	std::fflush(stdout);
	Log::Bc5SetLogging(false);
	std::thread(Watchdog).detach();

	// The subsystems, on a helper thread that is the "main thread" for their constructors (pth0401's way).
	std::thread init([] {
		Common::ThreadsSubsystem::Instance()->Init(nullptr);
		LK::PthreadSubsystem::Instance()->Init(nullptr);
		FS::FileSystemSubsystem::Instance()->Init(nullptr);
	});
	init.join();
	LK::PthreadInitSelfForMainThread();

	// A fresh directory of this run's own, and nothing but it mounted.
	std::error_code ec;
	const auto      home = std::filesystem::current_path(ec);
	g_work               = home / ("fs0405-work-" + std::to_string(::getpid()));
	if (ec || g_work.string().find("bc5-data") != std::string::npos || std::filesystem::exists(g_work, ec)) {
		SetupFail("cannot use a fresh " + g_work.string());
	}
	g_mnt    = g_work / "mnt";
	g_mnt2   = g_work / "mnt2";
	g_nested = g_work / "nested";
	HostMkdirs(g_mnt);
	HostMkdirs(g_mnt2);
	HostMkdirs(g_nested);
	HostMkdirs(g_mnt / "s8dir");
	HostWrite(g_mnt / "probe.txt", "probe");
	FS::Mount(g_mnt, "/temp0");
	FS::Mount(g_mnt2, "/temp1");
	FS::Mount(g_nested, "/temp0/sub"); // after /temp0: today's first-match search finds /temp0 first

	static Loader::SymbolDatabase db;
	Libs::InitLibKernel_1(&db); // reads KYTY_BC5_POSIX_RET_FIXES, as the emulator does when it loads libkernel
	g_db = &db;

	const auto start = Clock::now();
	Case1RenameOpenFile();
	Case2RenameOntoOpenTarget();
	Case3RenameDirectory();
	Case4RenameOntoItself();
	Case5RenameClosedFiles();
	Case6UnlinkOpenThenNew();
	Case7Accmode3();
	Case8DirectoryForWriting();
	Case9DirectoryForReading();
	Case11Blksize();
	Case12Path1024();
	Case13Component256();
	Case14Limits();
	Case15WriteReadOnly();
	Case16Normalise();
	Case10TruncReadOnlyLeak(); // last of the file cases: off, it leaves 100 descriptors behind
	Case17Registrations();
	Case18Unlink();
	Case19Munmap();
	Case20Mprotect();
	Case21Trywrlock();
	Case22Schedparam();
	Case23Once();

	g_case = "clean-up";
	std::filesystem::remove_all(g_work, ec); // only the directory this run made
	g_finished = true;
	const int n = g_cases.load();
	const int p = g_passed.load();
	const long long ms = std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - start).count();
	if (n == 0 || p != n) {
		std::printf("fs0405: %s %d of %d passed in %lld ms (%d not run); FAIL\n", label, p, n, ms, g_not_run.load());
		std::fflush(stdout);
		_exit(1);
	}
	std::printf("fs0405: %d case(s) not run (switch off, today's code EXITs); %lld ms\n", g_not_run.load(), ms);
	std::printf("fs0405: %s %d of %d; end\n", label, p, n);
	std::fflush(stdout);
	_exit(0);
}
