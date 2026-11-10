// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0412: a syntax check of guard0412.inc's host part on the laptop (clang++ -fsyntax-only, no Linux headers there).
// The declarations below stand in for the host unit's own (patch 0001: DView, DState, DViews, direct_views, g_d, direct_gtt,
// g_layout_gen, journal; exp 0401 e11: g_m11_reopens) and for the POSIX calls the guardian makes. Nothing here is linked or run.
//   clang++ -std=c++20 -Wall -Wextra -Werror -Wno-unused-function -fsyntax-only -I <dir of env_flag.hpp> syn0412.cpp
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <map>
#include <memory>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <vector>
#include <cerrno>

#include "env_flag.hpp"

// ---- POSIX stand-ins ----
using ssize_t = long long;
// off_t: the laptop's C library has its own
using id_t    = unsigned;
using rlim_t  = unsigned long long;
#define stat stat0412
struct stat {
    unsigned           st_mode;
    unsigned long long st_ino;
};
struct rlimit {
    rlim_t rlim_cur, rlim_max;
};
#define PROT_READ 1
#define MAP_SHARED 1
#define MAP_FAILED (reinterpret_cast<void*>(-1))
#define MLOCK_ONFAULT 1
#define POSIX_FADV_RANDOM 1
#define POSIX_FADV_DONTNEED 4
#define PRIO_PROCESS 0
#define RLIMIT_MEMLOCK 8
#define RLIM_INFINITY (~0ull)
#define S_ISREG(m) (((m) & 0170000) == 0100000)
void*   mmap(void*, size_t, int, int, int, off_t);
int     munmap(void*, size_t);
int     mlock(const void*, size_t);
int     mlock2(const void*, size_t, unsigned);
ssize_t readlink(const char*, char*, size_t);
#define fstat fstat0412
int     fstat(int, struct stat*);
int     posix_fadvise(int, off_t, off_t, int);
int     setpriority(int, id_t, int);
int     gettid();
int     getrlimit(int, struct rlimit*);
struct pthread_stand_in {};
pthread_stand_in pthread_self();
int              pthread_setname_np(pthread_stand_in, const char*);

// ---- the host unit's stand-ins (same shapes as patch 0001) ----
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static void journal(const char*, ...) {}
struct DView {
    uint64_t    va, size, off;
    std::string name;
    bool        lazy;
    bool        eager;
};
struct DState {
    int         kind;
    const char* label;
};
static DState g_d[2] = {{0, "direct"}, {1, "private"}};
struct DViews {
    std::vector<DView> v;
    uint64_t           sig = 0;
    bool               sorted = true;
};
static std::shared_ptr<const DViews> direct_views(const DState&) { return std::make_shared<DViews>(); }
static uint64_t                      direct_gtt(const char*) { return 0; }
static uint64_t                      g_layout_gen = 1;
static std::atomic<uint64_t>         g_m11_reopens {0};

#include "guard0412.inc"

int main() {
    guard0412_imported(0, 3, 0, 4096);
    return guard0412_defer_apply() ? 1 : 0;
}
