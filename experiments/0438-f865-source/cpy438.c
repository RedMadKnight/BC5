// SPDX-License-Identifier: GPL-2.0
// BC5 experiment 0438 (tag cpy438): who makes the large host copies (LD_PRELOAD shim, records only, test runs only).
// Wraps memcpy, memmove, mempcpy and their _chk forms (fortified builds call those). A copy of CPY438_MIN bytes or more (default 256 KiB) adds one record to the calling thread's
// ring: CLOCK_MONOTONIC ns, size, destination, source, and up to 12 return addresses from the frame-pointer chain. The
// chain is read with process_vm_readv on our own pid, so a frame pointer that is not one (guest code) ends the walk
// instead of faulting. The hot path takes no lock and does not allocate: a thread's ring is a static slot, claimed once
// by an atomic index. A writer thread drains every ring every 2 s (and at exit) into $CPY438_OUT.<pid>.txt, one line
// per record: "t_ns tid comm size dst src f0 f1 ...", and copies /proc/self/maps to $CPY438_OUT.<pid>.maps once.
// A copy made inside libc itself (not through the PLT) is not seen.
#define _GNU_SOURCE
#include <dlfcn.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/syscall.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>

#define FRAMES 12
#define RING 4096
#define SLOTS 256

struct rec {
	uint64_t t, n, dst, src, nf;
	uint64_t fr[FRAMES];
};
struct slot {
	_Atomic uint64_t w;   // records written (by the owner)
	uint64_t         r;   // records drained (by the writer)
	int              tid;
	char             comm[16];
	struct rec       ring[RING];
};
static struct slot      g_slots[SLOTS];
static _Atomic int      g_nslots = 0;
static _Atomic uint64_t g_dropped = 0;
static __thread int     t_slot = -1;
static __thread int     t_in = 0;
static void* (*real_memcpy)(void*, const void*, size_t)  = NULL;
static void* (*real_memmove)(void*, const void*, size_t) = NULL;
static size_t g_min = 256 * 1024;
static int    g_on = 0, g_resolving = 0;
static char   g_out[512];

static void* slow_copy(void* d, const void* s, size_t n) { // before the real ones are known (dlsym's own copies)
	unsigned char* dd = d;
	const unsigned char* ss = s;
	if (dd < ss) for (size_t i = 0; i < n; i++) dd[i] = ss[i];
	else for (size_t i = n; i-- > 0;) dd[i] = ss[i];
	return d;
}
static void resolve(void) {
	if (real_memcpy && real_memmove) return;
	g_resolving = 1;
	real_memcpy  = (void* (*)(void*, const void*, size_t))dlsym(RTLD_NEXT, "memcpy");
	real_memmove = (void* (*)(void*, const void*, size_t))dlsym(RTLD_NEXT, "memmove");
	g_resolving = 0;
}
static uint64_t now_ns(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}
static int read_self(uint64_t addr, uint64_t* out2) { // two words at addr: [saved rbp, return address]
	struct iovec l = {out2, 16}, r = {(void*)(uintptr_t)addr, 16};
	return syscall(SYS_process_vm_readv, getpid(), &l, 1, &r, 1, 0) == 16;
}
static void record(void* d, const void* s, size_t n) {
	if (t_in) return;
	t_in = 1;
	if (t_slot < 0) {
		int k = atomic_fetch_add(&g_nslots, 1);
		if (k >= SLOTS) {
			atomic_fetch_add(&g_dropped, 1);
			t_in = 0;
			return;
		}
		t_slot = k;
		g_slots[k].tid = (int)syscall(SYS_gettid);
		prctl(PR_GET_NAME, g_slots[k].comm, 0, 0, 0);
		for (int c = 0; c < 16 && g_slots[k].comm[c]; c++)
			if (g_slots[k].comm[c] == ' ') g_slots[k].comm[c] = '_'; // one field in the record line
	}
	struct slot* S = &g_slots[t_slot];
	const uint64_t w = atomic_load_explicit(&S->w, memory_order_relaxed);
	if (w - S->r >= RING) { // the writer is behind: drop, count
		atomic_fetch_add(&g_dropped, 1);
		t_in = 0;
		return;
	}
	struct rec* R = &S->ring[w % RING];
	R->t   = now_ns();
	R->n   = n;
	R->dst = (uint64_t)(uintptr_t)d;
	R->src = (uint64_t)(uintptr_t)s;
	uint64_t fp = (uint64_t)(uintptr_t)__builtin_frame_address(0), nf = 0;
	for (; nf < FRAMES && fp != 0 && (fp & 7) == 0; nf++) {
		uint64_t two[2];
		if (!read_self(fp, two)) break;
		R->fr[nf] = two[1];
		if (two[0] <= fp || two[0] - fp > (64ull << 20)) { nf++; break; } // the chain must go up the stack
		fp = two[0];
	}
	R->nf = nf;
	atomic_store_explicit(&S->w, w + 1, memory_order_release);
	t_in = 0;
}
void* memcpy(void* d, const void* s, size_t n) {
	if (!real_memcpy) {
		if (g_resolving) return slow_copy(d, s, n);
		resolve();
	}
	if (g_on && n >= g_min) record(d, s, n);
	return real_memcpy(d, s, n);
}
void* memmove(void* d, const void* s, size_t n) {
	if (!real_memmove) {
		if (g_resolving) return slow_copy(d, s, n);
		resolve();
	}
	if (g_on && n >= g_min) record(d, s, n);
	return real_memmove(d, s, n);
}
// _FORTIFY_SOURCE (Ubuntu's gcc default when optimizing) turns memcpy / memmove into these
void* __memcpy_chk(void* d, const void* s, size_t n, size_t dlen) {
	(void)dlen;
	return memcpy(d, s, n);
}
void* __memmove_chk(void* d, const void* s, size_t n, size_t dlen) {
	(void)dlen;
	return memmove(d, s, n);
}
void* mempcpy(void* d, const void* s, size_t n) { return (char*)memcpy(d, s, n) + n; }
void* __mempcpy_chk(void* d, const void* s, size_t n, size_t dlen) {
	(void)dlen;
	return mempcpy(d, s, n);
}
static void drain(int fd) {
	static char line[1024];
	const int k = atomic_load(&g_nslots) < SLOTS ? atomic_load(&g_nslots) : SLOTS;
	for (int i = 0; i < k; i++) {
		struct slot*   S = &g_slots[i];
		const uint64_t w = atomic_load_explicit(&S->w, memory_order_acquire);
		for (; S->r < w; S->r++) {
			const struct rec* R = &S->ring[S->r % RING];
			int len = snprintf(line, sizeof(line), "%llu %d %s %llu %llx %llx", (unsigned long long)R->t, S->tid, S->comm, (unsigned long long)R->n,
			                   (unsigned long long)R->dst, (unsigned long long)R->src);
			for (uint64_t f = 0; f < R->nf && len < (int)sizeof(line) - 20; f++) len += snprintf(line + len, sizeof(line) - len, " %llx", (unsigned long long)R->fr[f]);
			line[len++] = '\n';
			if (write(fd, line, (size_t)len) < 0) return;
		}
	}
}
static int g_fd = -1;
static void* writer(void* arg) {
	(void)arg;
	for (;;) {
		sleep(2);
		drain(g_fd);
	}
	return NULL;
}
static void copy_maps(void) {
	char p[600];
	snprintf(p, sizeof(p), "%s.%d.maps", g_out, (int)getpid());
	int in = open("/proc/self/maps", O_RDONLY), out = open(p, O_WRONLY | O_CREAT | O_TRUNC, 0600);
	char b[65536];
	ssize_t r;
	while (in >= 0 && out >= 0 && (r = read(in, b, sizeof(b))) > 0)
		if (write(out, b, (size_t)r) < 0) break;
	if (in >= 0) close(in);
	if (out >= 0) close(out);
}
static void at_exit(void) {
	if (g_fd < 0) return;
	drain(g_fd);
	char tail[128];
	int len = snprintf(tail, sizeof(tail), "# dropped %llu, threads %d\n", (unsigned long long)atomic_load(&g_dropped), atomic_load(&g_nslots));
	if (write(g_fd, tail, (size_t)len) < 0) return;
}
__attribute__((constructor)) static void init(void) {
	resolve();
	const char* o = getenv("CPY438_OUT");
	if (!o || !*o) return;
	const char* m = getenv("CPY438_MIN");
	if (m && *m) g_min = (size_t)strtoull(m, NULL, 0);
	snprintf(g_out, sizeof(g_out), "%s", o);
	char p[600];
	snprintf(p, sizeof(p), "%s.%d.txt", g_out, (int)getpid());
	g_fd = open(p, O_WRONLY | O_CREAT | O_TRUNC | O_APPEND, 0600);
	if (g_fd < 0) return;
	atexit(at_exit);
	pthread_t th;
	if (pthread_create(&th, NULL, writer, NULL) == 0) pthread_detach(th);
	g_on = 1;
	copy_maps();
}
// the maps again once a few seconds in (the emulator maps its guest memory and modules after start)
__attribute__((destructor)) static void fini(void) { copy_maps(); }
