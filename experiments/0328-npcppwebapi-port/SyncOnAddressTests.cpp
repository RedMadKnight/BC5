// BC5 experiment 0327: tests of the sync-on-address waits, after upstream KytyPlus's tests/SyncOnAddressTests.cpp
// (Coder787-source/KytyPlus, GPL-2.0; the same self-contained Check/abort style, no framework), extended with the
// 8- and 16-bit waits and the byte-address wake this experiment adds. Built and run by build0327.sh against the
// patched src/kernel/syncOnAddress.cpp and the shared build's common library; exits 0 when every check holds.
#include "kernel/syncOnAddress.h"

#include "libs/errno.h"

#include <atomic>
#include <chrono>
#include <climits>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <thread>
#include <vector>

namespace {

using Libs::LibKernel::SyncOnAddress::Wait16;
using Libs::LibKernel::SyncOnAddress::Wait32;
using Libs::LibKernel::SyncOnAddress::Wait64;
using Libs::LibKernel::SyncOnAddress::Wait8;
using Libs::LibKernel::SyncOnAddress::Wake;

int g_failed = 0;

void Check(bool value, const char* text) {
	if (!value) {
		std::fprintf(stderr, "SyncOnAddressTests: FAILED: %s\n", text);
		g_failed++;
	} else {
		std::fprintf(stderr, "SyncOnAddressTests: ok: %s\n", text);
	}
}

template <typename T>
void Store(volatile T* address, T value) {
	__atomic_store_n(address, value, __ATOMIC_RELEASE);
}

void TestInvalidAddress() {
	uint32_t timeout = 1;
	Check(Wait32(nullptr, 0, &timeout) == Libs::LibKernel::KERNEL_ERROR_EINVAL, "wait32 rejects a null address");
	Check(Wait64(nullptr, 0, &timeout) == Libs::LibKernel::KERNEL_ERROR_EINVAL, "wait64 rejects a null address");
	Check(Wait8(nullptr, 0, &timeout) == Libs::LibKernel::KERNEL_ERROR_EINVAL, "wait8 rejects a null address");
	Check(Wait16(nullptr, 0, &timeout) == Libs::LibKernel::KERNEL_ERROR_EINVAL, "wait16 rejects a null address");
	alignas(8) uint8_t bytes[8] = {};
	Check(Wait32(reinterpret_cast<volatile uint32_t*>(bytes + 1), 0, &timeout) ==
	          Libs::LibKernel::KERNEL_ERROR_EINVAL,
	      "wait32 rejects a misaligned address");
	Check(Wait16(reinterpret_cast<volatile uint16_t*>(bytes + 1), 0, &timeout) ==
	          Libs::LibKernel::KERNEL_ERROR_EINVAL,
	      "wait16 rejects a misaligned address");
	Check(Wake(nullptr, 1) == Libs::LibKernel::KERNEL_ERROR_EINVAL, "wake rejects a null address");
	Check(Wake(bytes + 1, -1) == Libs::LibKernel::KERNEL_ERROR_EINVAL, "wake rejects a negative count");
	Check(Wake(bytes + 1, 1) == 0, "wake accepts a byte address (the console does)");
}

void TestReturnsWhenValueDiffers() {
	alignas(8) volatile uint32_t w32 = 5;
	alignas(8) volatile uint64_t w64 = 5;
	alignas(4) volatile uint16_t w16 = 5;
	volatile uint8_t             w8  = 5;
	uint32_t                     timeout = 1000;
	Check(Wait32(&w32, 6, &timeout) == 0, "wait32 returns at once when the value differs");
	Check(Wait64(&w64, 6, &timeout) == 0, "wait64 returns at once when the value differs");
	Check(Wait16(&w16, 6, &timeout) == 0, "wait16 returns at once when the value differs");
	Check(Wait8(&w8, 6, &timeout) == 0, "wait8 returns at once when the value differs");
}

void TestTimeout() {
	alignas(4) volatile uint16_t w16 = 7;
	volatile uint8_t             w8  = 7;
	uint32_t                     timeout = 20000; // 20 ms
	const auto                   t0      = std::chrono::steady_clock::now();
	Check(Wait16(&w16, 7, &timeout) == Libs::LibKernel::KERNEL_ERROR_ETIMEDOUT, "wait16 times out while the value holds");
	Check(Wait8(&w8, 7, &timeout) == Libs::LibKernel::KERNEL_ERROR_ETIMEDOUT, "wait8 times out while the value holds");
	const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - t0).count();
	Check(ms >= 30 && ms < 2000, "two 20-ms timeouts take about 40 ms");
}

template <typename T>
void TestWakeByStoreAndWake(const char* what) {
	alignas(8) volatile T word  = 1;
	std::atomic<int>      rc {-100};
	std::thread           waiter([&] {
        uint32_t timeout = 2000000; // 2 s, the safety net
        rc.store(static_cast<int>(sizeof(T) == 1 ? Wait8(reinterpret_cast<volatile uint8_t*>(&word), 1, &timeout)
                                  : sizeof(T) == 2 ? Wait16(reinterpret_cast<volatile uint16_t*>(&word), 1, &timeout)
                                  : sizeof(T) == 4 ? Wait32(reinterpret_cast<volatile uint32_t*>(&word), 1, &timeout)
                                                   : Wait64(reinterpret_cast<volatile uint64_t*>(&word), 1, &timeout)));
	});
	std::this_thread::sleep_for(std::chrono::milliseconds(30));
	Store(&word, static_cast<T>(2));
	Check(Wake(&word, 1) == 0, "wake after the store");
	waiter.join();
	char text[160];
	std::snprintf(text, sizeof(text), "%s: a waiter woken by a store and a wake returns 0 (rc %d)", what, rc.load());
	Check(rc.load() == 0, text);
}

// A byte inside a word: the neighbouring bytes' waiters are not disturbed in their result (a spurious
// wake returns 0 only after a re-check of the own byte — the implementation re-checks before sleeping;
// a wake on the word may still end the sleep early, which the API allows).
void TestByteInsideWord() {
	alignas(4) volatile uint8_t bytes[4] = {1, 1, 1, 1};
	std::atomic<int>            rc0 {-100};
	std::thread                 waiter([&] {
        uint32_t timeout = 2000000;
        rc0.store(Wait8(&bytes[2], 1, &timeout));
	});
	std::this_thread::sleep_for(std::chrono::milliseconds(30));
	Store(&bytes[2], static_cast<uint8_t>(9));
	Check(Wake(&bytes[2], INT_MAX) == 0, "wake on a byte address inside a word");
	waiter.join();
	Check(rc0.load() == 0, "a byte waiter inside a word returns 0 after its byte changed");
	Check(bytes[0] == 1 && bytes[1] == 1 && bytes[3] == 1, "the neighbouring bytes are untouched");
}

void TestManyWaiters() {
	alignas(4) volatile uint16_t word = 3;
	std::atomic<int>             woken {0};
	std::vector<std::thread>     threads;
	for (int i = 0; i < 4; i++) {
		threads.emplace_back([&] {
			uint32_t timeout = 2000000;
			if (Wait16(&word, 3, &timeout) == 0) {
				woken.fetch_add(1);
			}
		});
	}
	std::this_thread::sleep_for(std::chrono::milliseconds(50));
	Store(&word, static_cast<uint16_t>(4));
	Check(Wake(&word, INT_MAX) == 0, "wake all");
	for (auto& t: threads) {
		t.join();
	}
	Check(woken.load() == 4, "four 16-bit waiters all return 0 after the store and the wake");
}

} // namespace

int main() {
	TestInvalidAddress();
	TestReturnsWhenValueDiffers();
	TestTimeout();
	TestWakeByStoreAndWake<uint8_t>("wait8");
	TestWakeByStoreAndWake<uint16_t>("wait16");
	TestWakeByStoreAndWake<uint32_t>("wait32");
	TestWakeByStoreAndWake<uint64_t>("wait64");
	TestByteInsideWord();
	TestManyWaiters();
	if (g_failed != 0) {
		std::fprintf(stderr, "SyncOnAddressTests: %d check(s) FAILED\n", g_failed);
		return 1;
	}
	std::fprintf(stderr, "SyncOnAddressTests: all checks passed\n");
	return 0;
}
