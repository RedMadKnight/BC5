// Laptop stand-in for the host's common/common.h.
#pragma once
#include <cinttypes>
#include <cstddef>
#include <cstdint>
#include <string>
#define KYTY_CLASS_NO_COPY(name)                                                                                       \
	name(const name&)            = delete;                                                                             \
	name& operator=(const name&) = delete
