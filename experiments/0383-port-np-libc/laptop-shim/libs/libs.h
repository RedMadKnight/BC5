// Laptop stand-in for the host's libs/libs.h: the same LIB_ADD body as f266548, without the logging and thread headers
// that a tree without submodules cannot compile. PRINT_NAME is off, as it is by default in the host.
#pragma once
#include "common/abi.h"
#include "common/logging/log.h"
#include "loader/symbolDatabase.h"

#define LIB_DEFINE(name) void name(Loader::SymbolDatabase* s)
#define LIB_NAME(l, m)                                                                                                 \
	static constexpr char g_library[] = l;                                                                             \
	static constexpr char g_module[]  = m;
#define LIB_VERSION(l, lv, m, mv1, mv2)                                                                                \
	LIB_NAME(l, m);                                                                                                    \
	static constexpr int g_library_version      = lv;                                                                  \
	static constexpr int g_module_version_major = mv1;                                                                 \
	static constexpr int g_module_version_minor = mv2;
#define LIB_USING(n)                                                                                                   \
	using n::g_library;                                                                                                \
	using n::g_library_version;                                                                                        \
	using n::g_module;                                                                                                 \
	using n::g_module_version_major;                                                                                   \
	using n::g_module_version_minor;
#define LIB_LOAD(name) name(s)
#define LIB_ADD(n, f, t)                                                                                               \
	{                                                                                                                  \
		Loader::SymbolResolve sr {};                                                                                   \
		sr.name                 = n;                                                                                   \
		sr.library              = g_library;                                                                           \
		sr.library_version      = g_library_version;                                                                   \
		sr.module               = g_module;                                                                            \
		sr.module_version_major = g_module_version_major;                                                              \
		sr.module_version_minor = g_module_version_minor;                                                              \
		sr.type                 = t;                                                                                   \
		auto        func        = reinterpret_cast<uint64_t>(f);                                                       \
		const char* dbg_name    = "" #f;                                                                               \
		s->Add(sr, func, dbg_name);                                                                                    \
	}
#define LIB_OBJECT(n, f) LIB_ADD(n, f, Loader::SymbolType::Object)
#define LIB_FUNC(n, f)   LIB_ADD(n, f, Loader::SymbolType::Func)
#define PRINT_NAME()
