// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0438 A1P (tag a1p438): the few host names the extracted memory-table code needs, for test_a1p438.cpp only.
#pragma once
#include <algorithm>
#include <atomic>
#include <cinttypes>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iterator>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#define EXIT_IF(x)                                                               \
	do {                                                                         \
		if (x) {                                                                 \
			std::fprintf(stderr, "EXIT_IF(%s) %s:%d\n", #x, __FILE__, __LINE__); \
			std::abort();                                                        \
		}                                                                        \
	} while (0)
#define EXIT_NOT_IMPLEMENTED(x) EXIT_IF(x)
#define KYTY_CLASS_NO_COPY(name)     \
	name(const name&)            = delete; \
	name& operator=(const name&) = delete
// TotalSize's host branches stay out: the PS5 total (12800 MiB) unless KYTY_GUEST_MEMORY_MB is set
#define KYTY_PLATFORM         0
#define KYTY_PLATFORM_WINDOWS 1
#define KYTY_PLATFORM_LINUX   2
#define LOGF(...)             ((void)0)
#define LOGF_COLOR(...)       ((void)0)
// assumed: the environment's value, or the fixed default when unset; a diagnostic switch reads the environment
#define BC5_FIXED_ENV(name, def) (std::getenv(name) != nullptr ? std::getenv(name) : (def))
#define BC5_DIAG_ENV(name)       std::getenv(name)

namespace Common {
// Kyty's Mutex has Lock/Unlock; this one also aborts on a second lock from the same thread, so the test shows that the
// A1P bodies never lock their owner's mutex again.
class Mutex {
public:
	void Lock() {
		EXIT_IF(m_owner == std::this_thread::get_id());
		m_m.lock();
		m_owner = std::this_thread::get_id();
	}
	void Unlock() {
		m_owner = std::thread::id();
		m_m.unlock();
	}
	[[nodiscard]] bool HeldHere() const { return m_owner == std::this_thread::get_id(); }

private:
	std::mutex      m_m;
	std::thread::id m_owner;
};
class LockGuard {
public:
	explicit LockGuard(Mutex& m): m_m(m) { m_m.Lock(); }
	~LockGuard() { m_m.Unlock(); }
	LockGuard(const LockGuard&)            = delete;
	LockGuard& operator=(const LockGuard&) = delete;

private:
	Mutex& m_m;
};
namespace Thread {
inline bool IsMainThread() { return true; }
} // namespace Thread
namespace VirtualMemory {
enum class Mode { NoAccess, Read, Write, ReadWrite, Execute, ExecuteRead, ExecuteWrite, ExecuteReadWrite };
} // namespace VirtualMemory
} // namespace Common

namespace Libs::LibKernel::Memory {
namespace VirtualMemory = Common::VirtualMemory;
constexpr uint32_t KERNEL_MAXIMUM_NAME_LENGTH = 32;        // memory.h
enum class GpuAccessMode { NoAccess, Read, Write, ReadWrite }; // memory.cpp
static uint64_t g_flexible_memory_size = 64ull * 1024ull * 1024ull;

// The three backing calls FlexibleMemory makes: each is logged; `fail_in` = n makes the n-th call from now fail.
class GuestAddressSpace {
public:
	bool ZeroBacking(uint64_t off, uint64_t size) { return Note('Z', off, size, 0); }
	bool MapBacking(uint64_t vaddr, uint64_t size, uint64_t off, VirtualMemory::Mode mode) {
		return Note('M', vaddr, size, off * 16 + static_cast<uint64_t>(mode));
	}
	bool UnmapBacking(uint64_t vaddr, uint64_t size) { return Note('U', vaddr, size, 0); }

	std::string log;
	int         fail_in = 0;
	bool        quiet   = false; // the bench: no log

private:
	bool Note(char c, uint64_t a, uint64_t b, uint64_t d) {
		const bool ok = !(fail_in > 0 && --fail_in == 0);
		if (!quiet) {
			char buf[96];
			std::snprintf(buf, sizeof(buf), "%c%" PRIx64 ",%" PRIx64 ",%" PRIx64 "%s;", c, a, b, d, ok ? "" : "!");
			log += buf;
		}
		return ok;
	}
};
static std::unique_ptr<GuestAddressSpace> g_guest_address_space = std::make_unique<GuestAddressSpace>();
} // namespace Libs::LibKernel::Memory
