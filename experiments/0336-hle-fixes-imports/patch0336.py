#!/usr/bin/env python3
# BC5 experiment 0336 (the maintainer's "B" after exp 0335's audit): three HLE fixes and a diagnostic of the title's
# imports, as one-file changes of four shared-tree files (each md5-checked; CRLF files are edited as LF and written back
# with CRLF). Everything is in the private build only; integration is a separate step (D19).
#   libs/libKernel.cpp
#     1. posix chmod (z0dtnPxYgtg) calls the tree's KernelChmod (exp 0327), -1/errno; it returned OK and did nothing.
#     2. posix pthread_rwlock_tryrdlock (SFxTMOfuCkE) goes to a posix wrapper (kernel/pthread.cpp) instead of the sce
#        function, which returns SCE codes.
#     3. counting entries for the audited NIDs: sceKernelChmod, scePthreadRwlockTryrdlock and the six posix NIDs that
#        the "libkernel" library registers with sce functions; each calls the same function as before.
#   kernel/pthread.cpp
#     4. PthreadRwlockTryrdlock and PthreadRwlockTrywrlock create a statically initialised lock on first use, as
#        PthreadRwlockRdlock does; they stopped the emulator (EXIT_NOT_IMPLEMENTED) on one.
#     5. the posix wrapper pthread_rwlock_tryrdlock (errno numbers, POSIX_PTHREAD_CALL).
#   libs/bc5LleAgc.cpp
#     6. sceKernelGetCompiledSdkVersion reads the program's process parameter (TODO(verify) the layout), with the old
#        constant as the fallback; the header it read is journaled once.
#   loader/runtimeLinker.cpp
#     7. BC5_IMPORT_LOG=<file> (off by default): every import RuntimeLinker::Resolve resolves, once per program and name,
#        with its library, module, path (hle, module, nid-fallback, unresolved) and the implementation's name; and the
#        helpers the other files use: Loader::Bc5DiagCall (a call count, journaled at 1, 2, 4, 8, ... calls),
#        Loader::Bc5DiagText and Loader::Bc5ProcParam.
# usage: patch0336.py <tree src dir> <out dir> <out .diff>   (the tree is only read)
import difflib, hashlib, os, sys

FILES = {
    'libs/libKernel.cpp': '35b61eea1ca5f8b11f04e1e51c0016b8',
    'kernel/pthread.cpp': 'd1ab5a056ed8e3a184c5dbaa8d46e210',
    'libs/bc5LleAgc.cpp': '5bccbb808c397f3180330425917b04c6',
    'loader/runtimeLinker.cpp': 'f294dfc28ec7558552d6b3898dbde71d',
}

DECL = '''// Experiment 0336: the diagnostic helpers (loader/runtimeLinker.cpp)
namespace Loader {
void     Bc5DiagCall(const char* what, std::atomic<uint64_t>* counter, int64_t value);
void     Bc5DiagText(const char* line);
uint64_t Bc5ProcParam();
} // namespace Loader

'''

KERNEL_WRAPPERS = r'''// Experiment 0336 (exp 0335's audit): counting entries for the NIDs whose implementation the audit questioned. Each
// calls the same function the NID had before and counts the call (Loader::Bc5DiagCall: journaled at 1, 2, 4, ... calls).
static std::atomic<uint64_t> g_0336_counts[8];
static const char* const      g_0336_names[8] = {
    "sceKernelChmod fgIsQ10xYVA",
    "scePthreadRwlockTryrdlock XD3mDeybCnk",
    "libkernel pthread_self EotR8a3ASf4",
    "libkernel pthread_attr_getstack -quPa4SEJUw",
    "libkernel pthread_attr_setstacksize 2Q0z6rnBrTE",
    "libkernel pthread_attr_getschedparam FXPWHNk8Of0",
    "libkernel pthread_rwlock_wrlock sIlRvQqsN2Y",
    "libkernel pthread_cond_signal 2MOy+rUfuhQ",
};
template <auto F, int K>
struct Diag0336;
template <typename R, typename... Args, R (*F)(Args...), int K>
struct Diag0336<F, K> {
	static R KYTY_SYSV_ABI call(Args... args) {
		Loader::Bc5DiagCall(g_0336_names[K], &g_0336_counts[K], 0);
		return F(args...);
	}
};

LIB_DEFINE(InitLibKernel_1_FS) {
'''

EDITS = {
    'libs/libKernel.cpp': [
        ('\nnamespace Libs {\n', '\n' + DECL + 'namespace Libs {\n'),
        ('LIB_VERSION("Posix", 1, "libkernel", 1, 1);\n',
         'LIB_VERSION("Posix", 1, "libkernel", 1, 1);\n\nint KYTY_SYSV_ABI pthread_rwlock_tryrdlock(LibKernel::PthreadRwlock* rwlock); // experiment 0336: kernel/pthread.cpp\n'),
        ('\tLIB_FUNC("SFxTMOfuCkE", LibKernel::PthreadRwlockTryrdlock);\n',
         '\tLIB_FUNC("SFxTMOfuCkE", Posix::pthread_rwlock_tryrdlock); // experiment 0336: a posix wrapper; it was the sce function\n'),
        ('int chmod(const char* path, int mode) {\n\tPRINT_NAME();\n\n\treturn OK;\n}\n',
         '''// Experiment 0336 (exp 0335's audit): posix chmod changes the file through the tree's KernelChmod (exp 0327), -1/errno;
// it returned OK and did nothing.
int chmod(const char* path, int mode) {
	PRINT_NAME();

	static std::atomic<uint64_t> calls {0};
	Loader::Bc5DiagCall("posix chmod z0dtnPxYgtg", &calls, mode);
	return POSIX_CALL(LibKernel::FileSystem::KernelChmod(path, static_cast<uint16_t>(mode)));
}
'''),
        ('LIB_DEFINE(InitLibKernel_1_FS) {\n', KERNEL_WRAPPERS),
        ('\tLIB_FUNC("fgIsQ10xYVA", FileSystem::KernelChmod);    // experiment 0327\n',
         '\tLIB_FUNC("fgIsQ10xYVA", (Diag0336<FileSystem::KernelChmod, 0>::call)); // experiment 0327; exp 0336 counts it\n'),
        ('\tLIB_FUNC("EotR8a3ASf4", LibKernel::PthreadSelf);\n',
         '\tLIB_FUNC("EotR8a3ASf4", (Diag0336<LibKernel::PthreadSelf, 2>::call)); // exp 0336 counts it\n'),
        ('\tLIB_FUNC("-quPa4SEJUw", LibKernel::PthreadAttrGetstack);\n',
         '\tLIB_FUNC("-quPa4SEJUw", (Diag0336<LibKernel::PthreadAttrGetstack, 3>::call)); // exp 0336 counts it\n'),
        ('\tLIB_FUNC("2Q0z6rnBrTE", LibKernel::PthreadAttrSetstacksize);\n',
         '\tLIB_FUNC("2Q0z6rnBrTE", (Diag0336<LibKernel::PthreadAttrSetstacksize, 4>::call)); // exp 0336 counts it\n'),
        ('\tLIB_FUNC("FXPWHNk8Of0", LibKernel::PthreadAttrGetschedparam);\n',
         '\tLIB_FUNC("FXPWHNk8Of0", (Diag0336<LibKernel::PthreadAttrGetschedparam, 5>::call)); // exp 0336 counts it\n'),
        ('\tLIB_FUNC("sIlRvQqsN2Y", LibKernel::PthreadRwlockWrlock);\n',
         '\tLIB_FUNC("sIlRvQqsN2Y", (Diag0336<LibKernel::PthreadRwlockWrlock, 6>::call)); // exp 0336 counts it\n'),
        ('\tLIB_FUNC("XD3mDeybCnk", LibKernel::PthreadRwlockTryrdlock);   // experiment 0327: scePthreadRwlockTryrdlock\n',
         '\tLIB_FUNC("XD3mDeybCnk", (Diag0336<LibKernel::PthreadRwlockTryrdlock, 1>::call)); // experiment 0327: scePthreadRwlockTryrdlock; exp 0336 counts it\n'),
        ('\tLIB_FUNC("2MOy+rUfuhQ", LibKernel::PthreadCondSignal);\n',
         '\tLIB_FUNC("2MOy+rUfuhQ", (Diag0336<LibKernel::PthreadCondSignal, 7>::call)); // exp 0336 counts it\n'),
    ],
    'kernel/pthread.cpp': [
        ('\nnamespace Libs {\n', '\n' + DECL + 'namespace Libs {\n'),
        ('''int KYTY_SYSV_ABI PthreadRwlockTryrdlock(PthreadRwlock* rwlock) {
	PRINT_NAME();

	if (rwlock == nullptr) {''', '''int KYTY_SYSV_ABI PthreadRwlockTryrdlock(PthreadRwlock* rwlock) {
	PRINT_NAME();

	// Experiment 0336: a statically initialised lock is created on first use, as PthreadRwlockRdlock does; it stopped
	// the emulator (EXIT_NOT_IMPLEMENTED) before.
	rwlock = static_cast<PthreadRwlock*>(
	    g_pthread_context->GetPthreadStaticObjects()->CreateObject(rwlock, PthreadStaticObject::Type::Rwlock));

	if (rwlock == nullptr) {'''),
        ('''int KYTY_SYSV_ABI PthreadRwlockTrywrlock(PthreadRwlock* rwlock) {
	PRINT_NAME();

	if (rwlock == nullptr) {''', '''int KYTY_SYSV_ABI PthreadRwlockTrywrlock(PthreadRwlock* rwlock) {
	PRINT_NAME();

	// Experiment 0336: a statically initialised lock is created on first use, as PthreadRwlockWrlock does.
	rwlock = static_cast<PthreadRwlock*>(
	    g_pthread_context->GetPthreadStaticObjects()->CreateObject(rwlock, PthreadStaticObject::Type::Rwlock));

	if (rwlock == nullptr) {'''),
        ('''int KYTY_SYSV_ABI pthread_rwlock_wrlock(LibKernel::PthreadRwlock* rwlock) {
	// Hot path for some PS5 titles; per-call name logging can dominate runtime.

	return POSIX_PTHREAD_CALL(LibKernel::PthreadRwlockWrlock(rwlock));
}
''', '''int KYTY_SYSV_ABI pthread_rwlock_wrlock(LibKernel::PthreadRwlock* rwlock) {
	// Hot path for some PS5 titles; per-call name logging can dominate runtime.

	return POSIX_PTHREAD_CALL(LibKernel::PthreadRwlockWrlock(rwlock));
}

// Experiment 0336 (exp 0335's audit): posix pthread_rwlock_tryrdlock (SFxTMOfuCkE) returns errno numbers (EBUSY,
// EINVAL) as the other posix wrappers do; the NID pointed at the sce function, which returns SCE codes.
int KYTY_SYSV_ABI pthread_rwlock_tryrdlock(LibKernel::PthreadRwlock* rwlock) {
	static std::atomic<uint64_t> calls {0};
	Loader::Bc5DiagCall("posix pthread_rwlock_tryrdlock SFxTMOfuCkE", &calls, 0);
	return POSIX_PTHREAD_CALL(LibKernel::PthreadRwlockTryrdlock(rwlock));
}
'''),
    ],
    'libs/bc5LleAgc.cpp': [
        ('\nnamespace Libs {\n', '\n' + DECL + 'namespace Libs {\n'),
        ('''	*version = 0x0A000000; // TODO(bc5): read from the eboot's process param
	return 0;
}
''', '''	// Experiment 0336 (exp 0335's audit): the version comes from the program's process parameter, which the host serves
	// (RuntimeLinker::GetProcParam). TODO(verify): the layout. A PS4 process parameter is {u64 size, u32 magic, u32 entry
	// count, u64 sdk version}; a PS5 title's param.json writes sdkVersion as a u64 with the version in its high half
	// ("0x0700000000000000", ps5rs crates/ps5-analysis/src/param_json.rs). So the high half of the u64 at +0x10 is taken,
	// or its low half when the high one is 0, and only a value in [0x01000000, 0x20000000) is used; otherwise the old
	// constant 0x0A000000. The header read is journaled once (BC5_IMPORT_LOG).
	static const uint32_t v = [] {
		uint32_t       out = 0x0A000000;
		const uint64_t pp  = Loader::Bc5ProcParam();
		uint64_t       size = 0, sdk = 0;
		uint32_t       magic = 0, entries = 0;
		if (pp != 0) {
			std::memcpy(&size, reinterpret_cast<const void*>(pp), 8);
			std::memcpy(&magic, reinterpret_cast<const void*>(pp + 8), 4);
			std::memcpy(&entries, reinterpret_cast<const void*>(pp + 12), 4);
			if (size >= 0x18) std::memcpy(&sdk, reinterpret_cast<const void*>(pp + 0x10), 8);
		}
		const auto hi   = static_cast<uint32_t>(sdk >> 32u);
		const auto lo   = static_cast<uint32_t>(sdk);
		const auto cand = hi != 0 ? hi : lo;
		if (cand >= 0x01000000u && cand < 0x20000000u) out = cand;
		char line[256];
		std::snprintf(line, sizeof(line), "procparam at 0x%" PRIx64 ": size 0x%" PRIx64 " magic 0x%08" PRIx32 " entries %" PRIu32 " u64@0x10 0x%016" PRIx64 " -> compiled sdk version 0x%08" PRIx32 "%s",
		              pp, size, magic, entries, sdk, out, out == 0x0A000000u ? " (the old constant)" : "");
		Loader::Bc5DiagText(line);
		return out;
	}();
	static std::atomic<uint64_t> calls {0};
	Loader::Bc5DiagCall("sceKernelGetCompiledSdkVersion WB66evu8bsU", &calls, v);
	*version = static_cast<int>(v);
	return 0;
}
'''),
    ],
    'loader/runtimeLinker.cpp': [
        ('#include <atomic>\n', '#include <atomic>\n#include <chrono> // experiment 0336\n#include <mutex>  // experiment 0336\n#include <set>    // experiment 0336\n'),
        ('void RuntimeLinker::Resolve(const std::string& name, SymbolType type, Program* program,\n',
         r'''// Experiment 0336 (BC5_IMPORT_LOG=<file>, a diagnostic, off by default): the resolved imports, once per program and
// name, and the call counts other files report. The file is opened once, line-buffered, for appending.
static FILE* bc5_0336_log() {
	static FILE* f = [] {
		const char* p = std::getenv("BC5_IMPORT_LOG");
		FILE*       x = p != nullptr && *p != 0 ? std::fopen(p, "a") : nullptr;
		if (x != nullptr) {
			std::setvbuf(x, nullptr, _IOLBF, 0);
		}
		return x;
	}();
	return f;
}
static double bc5_0336_now() {
	static const auto t0 = std::chrono::steady_clock::now();
	return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}
void Bc5DiagText(const char* line) {
	if (FILE* f = bc5_0336_log(); f != nullptr) {
		static std::mutex m;
		std::lock_guard   lock(m);
		std::fprintf(f, "%.3f %s\n", bc5_0336_now(), line);
	}
}
void Bc5DiagCall(const char* what, std::atomic<uint64_t>* counter, int64_t value) {
	const uint64_t n = counter->fetch_add(1, std::memory_order_relaxed) + 1;
	if ((n & (n - 1)) != 0 || bc5_0336_log() == nullptr) {
		return;
	}
	char line[256];
	std::snprintf(line, sizeof(line), "call %s #%" PRIu64 " value %" PRId64, what, n, value);
	Bc5DiagText(line);
}
uint64_t Bc5ProcParam() {
	return Common::Singleton<RuntimeLinker>::Instance()->GetProcParam();
}
namespace {
struct Bc5ImportNote {
	const std::string&  name;
	const Program*      program;
	const SymbolRecord* out;
	const char*         path = "unresolved";
	std::string         lib  = "-";
	std::string         mod  = "-";
	~Bc5ImportNote() {
		if (bc5_0336_log() == nullptr) {
			return;
		}
		static std::set<std::string> seen; // RuntimeLinker::Resolve holds m_mutex
		const std::string            file = program != nullptr ? program->file_name.filename().string() : "-";
		if (!seen.insert(file + "\t" + name).second) {
			return;
		}
		const std::string line = "import\t" + file + "\t" + name + "\t" + lib + "\t" + mod + "\t" + path + "\t" + out->name + "\t" + out->dbg_name + "\t" + (out->vaddr != 0 ? "bound" : "stub");
		Bc5DiagText(line.c_str());
	}
};
} // namespace

void RuntimeLinker::Resolve(const std::string& name, SymbolType type, Program* program,
'''),
        ('''	EXIT_IF(out_info == nullptr);

	auto ids = Common::Split(name, '#');
''', '''	EXIT_IF(out_info == nullptr);

	Bc5ImportNote bc5_note {name, program, out_info}; // experiment 0336

	auto ids = Common::Split(name, '#');
'''),
        ('''		const LibraryId* l = FindLibrary(*program, ids.at(1));
		const ModuleId*  m = FindModule(*program, ids.at(2));
''', '''		const LibraryId* l = FindLibrary(*program, ids.at(1));
		const ModuleId*  m = FindModule(*program, ids.at(2));
		bc5_note.lib       = l != nullptr ? l->name : "?"; // experiment 0336
		bc5_note.mod       = m != nullptr ? m->name : "?";
'''),
        ('''			if (m_symbols != nullptr) {
				rec = m_symbols->Find(sr);
			}
''', '''			if (m_symbols != nullptr) {
				rec = m_symbols->Find(sr);
			}
			if (rec != nullptr) {
				bc5_note.path = "hle"; // experiment 0336
			}
'''),
        ('''					rec = p->export_symbols->Find(sr);
''', '''					rec = p->export_symbols->Find(sr);
					if (rec != nullptr) {
						bc5_note.path = "module"; // experiment 0336
					}
'''),
        ('''					LOGF("PS5 NID fallback: %s -> %s\\n", sr.name.c_str(), out_info->name.c_str());
					return;
''', '''					LOGF("PS5 NID fallback: %s -> %s\\n", sr.name.c_str(), out_info->name.c_str());
					bc5_note.path = "nid-fallback"; // experiment 0336
					return;
'''),
        ('''				LOGF("PS5 NID fallback: %s -> %s (missing lib/module metadata)\\n",
				     ids.at(0).c_str(), out_info->name.c_str());
				return;
''', '''				LOGF("PS5 NID fallback: %s -> %s (missing lib/module metadata)\\n",
				     ids.at(0).c_str(), out_info->name.c_str());
				bc5_note.path = "nid-fallback-no-metadata"; // experiment 0336
				return;
'''),
    ],
}


def main():
    src, out_dir, diff_path = sys.argv[1:4]
    diffs = []
    for rel, want in FILES.items():
        raw = open(os.path.join(src, rel), 'rb').read()
        md5 = hashlib.md5(raw).hexdigest()
        if md5 != want:
            sys.exit(f'{rel}: md5 {md5}, expected {want}')
        crlf = b'\r\n' in raw
        text = raw.decode('utf-8').replace('\r\n', '\n')
        orig = text
        for k, (old, new) in enumerate(EDITS[rel], 1):
            n = text.count(old)
            if n != 1:
                sys.exit(f'{rel} edit {k}: anchor found {n} times')
            text = text.replace(old, new)
        out = (text.replace('\n', '\r\n') if crlf else text).encode('utf-8')
        os.makedirs(os.path.join(out_dir, os.path.dirname(rel)), exist_ok=True)
        open(os.path.join(out_dir, rel), 'wb').write(out)
        diffs += difflib.unified_diff(orig.splitlines(keepends=True), text.splitlines(keepends=True), f'a/src/{rel}', f'b/src/{rel}', n=3)
        print(f'{rel}: {len(EDITS[rel])} edits, {"CRLF" if crlf else "LF"}, md5 {hashlib.md5(out).hexdigest()}')
    open(diff_path, 'w', encoding='utf-8', newline='\n').write(''.join(diffs))


if __name__ == '__main__':
    main()
