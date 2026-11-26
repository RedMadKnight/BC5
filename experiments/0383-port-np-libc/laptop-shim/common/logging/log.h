// Laptop stand-in for the host's common/logging/log.h.
#pragma once
#include <cstdio>
#define LOGF(...) std::fprintf(stderr, __VA_ARGS__)
