#!/usr/bin/env python3
# BC5 experiment 0338: the integration candidate the maintainer chose after exps 0335-0337 ("a) Integracja do wspólnych
# buildów (D19): poprawki z 0336 oraz przepięcie tych 16 funkcji posix na istniejące wrappery"). Five shared-tree files,
# each md5-checked; CRLF files are edited as LF and written back with CRLF. The private build and its test run come first;
# the shared builds change only on the maintainer's yes (D19).
#   exp 0336's fixes, without its counting entries:
#     libs/libKernel.cpp   posix chmod (z0dtnPxYgtg) calls KernelChmod (-1/errno); it returned OK and did nothing.
#                          posix pthread_rwlock_tryrdlock (SFxTMOfuCkE) goes to its posix wrapper.
#     kernel/pthread.cpp   PthreadRwlockTryrdlock/Trywrlock create a statically initialised lock on first use;
#                          Posix::pthread_rwlock_tryrdlock (POSIX_PTHREAD_CALL).
#     libs/bc5LleAgc.cpp   sceKernelGetCompiledSdkVersion from the program's process parameter (TODO(verify) the layout).
#     loader/runtimeLinker.cpp  BC5_IMPORT_LOG=<file> (off by default): every resolved import, once per program and name.
#   the posix NIDs on posix implementations (exp 0336 R1: 16 libScePosix imports reached libkernel's sce registrations
#   through the NID fallback):
#     libs/libKernel.cpp   the Posix block registers the twelve NIDs those imports name, on the posix entry points the
#                          tree has (LibKernel::open/close/write/getpid, Posix::lseek/fstat/pthread_cond_timedwait/
#                          pthread_rwlock_rdlock/unlock, KernelUsleep) and two new thin ones (sched_yield,
#                          pthread_cond_destroy). The libkernel block's registrations of posix NIDs with sce functions
#                          move to the same posix entry points (pthread_self and usleep behave the same and stay).
#                          LibKernel::write returns -1/EBADF for a negative descriptor, as close and read do; it stopped
#                          the emulator (EXIT_NOT_IMPLEMENTED).
#     kernel/pthread.cpp   Posix::sched_yield (int 0; the NID pointed at the void PthreadYield) and
#                          Posix::pthread_cond_destroy (POSIX_PTHREAD_CALL).
#     kernel/pthread.h     their declarations (added only).
#   Not changed: -quPa4SEJUw and FXPWHNk8Of0 are scePthreadAttrGetstack and scePthreadAttrGetschedparam (sce names), so
#   libkernel's sce registrations of them are right; the Posix block's posix-wrapper registrations of them are left as
#   they are (nothing imports them from libScePosix in exp 0336 R1).
# usage: patch0338.py <tree src dir> <out dir> <out .diff>   (the tree is only read)
import difflib, hashlib, os, sys

FILES = {
    'libs/libKernel.cpp': '35b61eea1ca5f8b11f04e1e51c0016b8',
    'kernel/pthread.cpp': 'd1ab5a056ed8e3a184c5dbaa8d46e210',
    'kernel/pthread.h': 'f51b5ef1e1917f9df71c55ac2c94acaf',
    'libs/bc5LleAgc.cpp': '5bccbb808c397f3180330425917b04c6',
    'loader/runtimeLinker.cpp': 'f294dfc28ec7558552d6b3898dbde71d',
}

DECL = '''// Experiment 0336: the import log's helpers (loader/runtimeLinker.cpp)
namespace Loader {
void     Bc5DiagText(const char* line);
uint64_t Bc5ProcParam();
} // namespace Loader

'''

# (old, new) pairs; each old text must occur exactly once
REPOINT = [
    ('6XG4B33N09g', 'LibKernel::PthreadYield', 'Posix::sched_yield'),
    ('2Q0z6rnBrTE', 'LibKernel::PthreadAttrSetstacksize', 'Posix::pthread_attr_setstacksize'),
    ('iGjsr1WAtI0', 'LibKernel::PthreadRwlockRdlock', 'Posix::pthread_rwlock_rdlock'),
    ('EgmLo6EWgso', 'LibKernel::PthreadRwlockUnlock', 'Posix::pthread_rwlock_unlock'),
    ('sIlRvQqsN2Y', 'LibKernel::PthreadRwlockWrlock', 'Posix::pthread_rwlock_wrlock'),
    ('RXXqi4CtF8w', 'LibKernel::PthreadCondDestroy', 'Posix::pthread_cond_destroy'),
    ('2MOy+rUfuhQ', 'LibKernel::PthreadCondSignal', 'Posix::pthread_cond_signal'),
    ('wuCroIGjt2g', 'FileSystem::KernelOpen', 'LibKernel::open'),
    ('bY-PO6JhzhQ', 'FileSystem::KernelClose', 'LibKernel::close'),
    ('FN4gaPmuFV8', 'FileSystem::KernelWrite', 'LibKernel::write'),
]

POSIX_BLOCK = '''	LIB_FUNC("cfwBSQyr5Ys", cfwBSQyr5Ys);

	// Experiment 0338 (exps 0335, 0336): the posix NIDs the title imports from libScePosix. Without them here, the
	// import reached libkernel's registration of the NID through the NID fallback, often an sce function (SCE codes
	// instead of -1/errno).
	LIB_FUNC("wuCroIGjt2g", LibKernel::open);
	LIB_FUNC("bY-PO6JhzhQ", LibKernel::close);
	LIB_FUNC("FN4gaPmuFV8", LibKernel::write);
	LIB_FUNC("Oy6IpwgtYOk", Posix::lseek);
	LIB_FUNC("mqQMh1zPPT8", Posix::fstat);
	LIB_FUNC("HoLVWNanBBc", LibKernel::getpid);
	LIB_FUNC("QcteRwbsnV0", LibKernel::KernelUsleep); // usleep: KernelUsleep returns 0 always
	LIB_FUNC("6XG4B33N09g", Posix::sched_yield);
	LIB_FUNC("RXXqi4CtF8w", Posix::pthread_cond_destroy);
	LIB_FUNC("27bAgiJmOh0", Posix::pthread_cond_timedwait);
	LIB_FUNC("iGjsr1WAtI0", Posix::pthread_rwlock_rdlock);
	LIB_FUNC("EgmLo6EWgso", Posix::pthread_rwlock_unlock);
}

} // namespace Posix
'''

EDITS = {
    'libs/libKernel.cpp': [
        ('''static int64_t KYTY_SYSV_ABI write(int d, const char* str, int64_t size) {
	// PRINT_NAME();

	EXIT_NOT_IMPLEMENTED(d < 0);
''', '''static int64_t KYTY_SYSV_ABI write(int d, const char* str, int64_t size) {
	// PRINT_NAME();

	// Experiment 0338: -1/EBADF, as close and read; it stopped the emulator (EXIT_NOT_IMPLEMENTED). The posix write NID
	// now comes here; it went to KernelWrite, which returns EBADF.
	if (d < 0) {
		*Posix::GetErrorAddr() = Posix::POSIX_EBADF;
		return -1;
	}
'''),
        ('\tLIB_FUNC("SFxTMOfuCkE", LibKernel::PthreadRwlockTryrdlock);\n',
         '\tLIB_FUNC("SFxTMOfuCkE", Posix::pthread_rwlock_tryrdlock); // experiment 0336: it was the sce function\n'),
        ('\tLIB_FUNC("cfwBSQyr5Ys", cfwBSQyr5Ys);\n}\n\n} // namespace Posix\n', POSIX_BLOCK),
        ('int chmod(const char* path, int mode) {\n\tPRINT_NAME();\n\n\treturn OK;\n}\n',
         '''// Experiment 0336 (exp 0335's audit): posix chmod changes the file through the tree's KernelChmod (exp 0327), -1/errno;
// it returned OK and did nothing.
int chmod(const char* path, int mode) {
	PRINT_NAME();

	return POSIX_CALL(LibKernel::FileSystem::KernelChmod(path, static_cast<uint16_t>(mode)));
}
'''),
    ] + [(f'\tLIB_FUNC("{nid}", {old});\n', f'\tLIB_FUNC("{nid}", {new}); // experiment 0338: the posix entry point\n')
         for nid, old, new in REPOINT],
    'kernel/pthread.cpp': [
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
        ('''void KYTY_SYSV_ABI pthread_yield() {
	PRINT_NAME();

	LibKernel::PthreadYield();
}
''', '''void KYTY_SYSV_ABI pthread_yield() {
	PRINT_NAME();

	LibKernel::PthreadYield();
}

// Experiment 0338: posix sched_yield returns 0; its NID pointed at the void PthreadYield.
int KYTY_SYSV_ABI sched_yield() {
	LibKernel::PthreadYield();
	return 0;
}
'''),
        ('''int KYTY_SYSV_ABI pthread_cond_signal(LibKernel::PthreadCond* cond) {
	// PRINT_NAME();

	return POSIX_PTHREAD_CALL(LibKernel::PthreadCondSignal(cond));
}
''', '''int KYTY_SYSV_ABI pthread_cond_signal(LibKernel::PthreadCond* cond) {
	// PRINT_NAME();

	return POSIX_PTHREAD_CALL(LibKernel::PthreadCondSignal(cond));
}

// Experiment 0338: posix pthread_cond_destroy returns errno numbers; its NID pointed at the sce function.
int KYTY_SYSV_ABI pthread_cond_destroy(LibKernel::PthreadCond* cond) {
	return POSIX_PTHREAD_CALL(LibKernel::PthreadCondDestroy(cond));
}
'''),
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
	return POSIX_PTHREAD_CALL(LibKernel::PthreadRwlockTryrdlock(rwlock));
}
'''),
    ],
    'kernel/pthread.h': [
        ('void KYTY_SYSV_ABI               pthread_yield();\n',
         'void KYTY_SYSV_ABI               pthread_yield();\nint KYTY_SYSV_ABI                sched_yield(); // experiment 0338\n'),
        ('int KYTY_SYSV_ABI pthread_cond_signal(LibKernel::PthreadCond* cond);\n',
         'int KYTY_SYSV_ABI pthread_cond_signal(LibKernel::PthreadCond* cond);\n'
         'int KYTY_SYSV_ABI pthread_cond_destroy(LibKernel::PthreadCond* cond); // experiment 0338\n'),
        ('int KYTY_SYSV_ABI pthread_rwlock_wrlock(LibKernel::PthreadRwlock* rwlock);\n',
         'int KYTY_SYSV_ABI pthread_rwlock_wrlock(LibKernel::PthreadRwlock* rwlock);\n'
         'int KYTY_SYSV_ABI pthread_rwlock_tryrdlock(LibKernel::PthreadRwlock* rwlock); // experiment 0336\n'),
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
	// constant 0x0A000000. The header read is journaled once (BC5_IMPORT_LOG). The second title gives 0x09000040.
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
	*version = static_cast<int>(v);
	return 0;
}
'''),
    ],
    'loader/runtimeLinker.cpp': [
        ('#include <atomic>\n', '#include <atomic>\n#include <chrono> // experiment 0336\n#include <mutex>  // experiment 0336\n#include <set>    // experiment 0336\n'),
        ('void RuntimeLinker::Resolve(const std::string& name, SymbolType type, Program* program,\n',
         r'''// Experiment 0336 (BC5_IMPORT_LOG=<file>, a diagnostic, off by default): the resolved imports, once per program and
// name, and the lines other files report through Bc5DiagText. The file is opened once, line-buffered, for appending.
static FILE* bc5_import_log() {
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
static double bc5_import_now() {
	static const auto t0 = std::chrono::steady_clock::now();
	return std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
}
void Bc5DiagText(const char* line) {
	if (FILE* f = bc5_import_log(); f != nullptr) {
		static std::mutex m;
		std::lock_guard   lock(m);
		std::fprintf(f, "%.3f %s\n", bc5_import_now(), line);
	}
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
		if (bc5_import_log() == nullptr) {
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
