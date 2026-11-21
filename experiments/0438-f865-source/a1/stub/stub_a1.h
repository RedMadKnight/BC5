// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0438 A1 (tag a1438): the few host names the extracted range code needs, for test_a1438.cpp only.
#pragma once
#include <algorithm>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iterator>
#include <map>
#include <memory>
#include <mutex>
#include <utility>
#include <vector>

#include "bc5/map_records.hpp" // copied unchanged from KytyPlus+BC5 src/bc5/map_records.hpp (md5 39e4c2dd...)

#define EXIT_IF(x)                                                     \
	do {                                                               \
		if (x) {                                                       \
			std::fprintf(stderr, "EXIT_IF(%s) %s:%d\n", #x, __FILE__, __LINE__); \
			std::abort();                                              \
		}                                                              \
	} while (0)
// assumed: the environment's value, or the fixed default when unset (exp 0412's QuerySpan switch then defaults on)
#define BC5_FIXED_ENV(name, def) (std::getenv(name) != nullptr ? std::getenv(name) : (def))

namespace Common {
using Mutex     = std::recursive_mutex;
using LockGuard = std::lock_guard<std::recursive_mutex>;
} // namespace Common

namespace Libs::LibKernel::Memory {
constexpr uint32_t KERNEL_MAXIMUM_NAME_LENGTH = 32; // memory.h
} // namespace Libs::LibKernel::Memory
