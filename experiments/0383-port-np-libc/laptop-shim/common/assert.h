// Laptop stand-in for the host's common/assert.h: the host's EXIT stops the emulator, so does this.
#pragma once
#include <cstdio>
#include <cstdlib>
#define EXIT(...)                                                                                                      \
	do {                                                                                                               \
		std::fprintf(stderr, __VA_ARGS__);                                                                             \
		std::abort();                                                                                                  \
	} while (0)
#define EXIT_NOT_IMPLEMENTED(cond)                                                                                     \
	do {                                                                                                               \
		if (cond) EXIT("not implemented\n");                                                                           \
	} while (0)
