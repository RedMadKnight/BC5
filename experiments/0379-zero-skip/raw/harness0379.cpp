// exp 0379 stand-in harness: just enough of bc5LleAgc.cpp and Linux for a -fsyntax-only check of the zero-skip block.
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>
#include "bc5/zero_skip.hpp"
using ssize_t = long long; using id_t = unsigned;
#define PRIO_PROCESS 0
#define SYS_gettid 186
#define MFD_CLOEXEC 1u
#define MFD_ALLOW_SEALING 2u
#define F_ADD_SEALS 1033
#define F_SEAL_SHRINK 2
#define PROT_READ 1
#define MAP_SHARED 1
#define MAP_FAILED (reinterpret_cast<void*>(-1))
#define SEEK_DATA 3
int setpriority(int, id_t, int); long syscall(long, ...); int memfd_create(const char*, unsigned);
int ftruncate(int, off_t); int fcntl(int, int, ...); void* mmap(void*, size_t, int, int, int, off_t);
ssize_t pread(int, void*, size_t, off_t); off_t lseek(int, off_t, int);
#define BC5_DIAG_ENV(name) std::getenv(name)
constexpr uint64_t kDChunk = 2ull << 20u;
struct DView { uint64_t va, size, off; std::string name; bool lazy; bool eager; };
struct DState { int kind; uint64_t blocks = ~0ull; };
static int dstate_fd(const DState&) { return 3; }
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void journal(const char*, ...) {}
static double timing_now() { return 0.0; }
struct Dev { bool map_shared(uint32_t, uint64_t, uint64_t, uint64_t) { return true; } bool unmap_shared(uint64_t) { return true; } uint32_t import_memfd(int, uint64_t, uint64_t) { return 1; } };
static std::unique_ptr<Dev> g_dev;
#include "zskip_block.cpp"
int main() {
	std::vector<DView> v; DState S {0};
	zskip_resolve(v); zscan_tick(S, v); zskip_take_back(S, 3); zskip_map(v); zskip_release(0, 1); zskip_report(); zskip_disable("x");
	return t_force_learned ? 1 : 0;
}
