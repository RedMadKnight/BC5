// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0438 A1b (tag a1b438): a1's stub (stub_a1.h, found through -I ../a1/stub) plus the names A1b's code adds.
#pragma once
#include "stub_a1.h"

#include <array>
#include <string>

// as src/bc5/env_rule.hpp: a diagnostic word is a null pointer in the lean build
#ifdef BC5_LEAN
#define BC5_DIAG_ENV(name) static_cast<const char*>(nullptr)
#else
#define BC5_DIAG_ENV(name) std::getenv(name)
#endif
