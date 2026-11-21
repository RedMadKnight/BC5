# BC5 experiment 0439 (tag kv439): the private eventQueue.cpp from the shared tree's (patch 0fede35d): every
# KernelWaitEqueue return is logged with the equeue's name, the thread, the count and each event (first 120 returns),
# so a wake of the third title's ProxySetSync on "ProxySet Cull" can be seen.
#   python mkeq439.py <dir with the original eventQueue.cpp> <out dir>
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src + '/eventQueue.cpp', encoding='utf-8', newline='').read()
a = '''	if (*out == KERNEL_ERROR_EBADF) {
		return KERNEL_ERROR_EBADF;
	}
	if (*out == 0) {
		LOGF("\\tEqueue wait timedout: %s\\n", owner->GetName().c_str());
		return KERNEL_ERROR_ETIMEDOUT;
	}

	return OK;
}'''
assert s.count(a) == 1, 'anchor'
b = '''	{ // exp 0439 (tag kv439): the wait's return, with its events
		static std::atomic<int> kv_n {0};
		if (kv_n++ < 120) {
			char tn[32] = {};
			pthread_getname_np(pthread_self(), tn, sizeof(tn));
			const int n = *out;
			std::fprintf(stderr, "[bc5] exp 0439 (tag kv439): KernelWaitEqueue returns on \\"%s\\" (thread %s, num %d, timeout %s): %d event(s), return address %p\\n", owner->GetName().c_str(), tn, num,
			             timo == nullptr ? "none" : (*timo == 0 ? "0" : "set"), n, __builtin_return_address(0));
			for (int k = 0; k < n && k < 4; k++) {
				std::fprintf(stderr, "[bc5] exp 0439 (tag kv439):   event %d: ident 0x%llx filter %d flags 0x%x fflags 0x%x data 0x%llx udata %p\\n", k, static_cast<unsigned long long>(ev[k].ident),
				             static_cast<int>(ev[k].filter), static_cast<unsigned>(ev[k].flags), static_cast<unsigned>(ev[k].fflags), static_cast<unsigned long long>(ev[k].data), ev[k].udata);
			}
		}
	}
''' + a
s = s.replace(a, b)
if '#include <pthread.h>' not in s:
    s = '#include <pthread.h> // exp 0439 (tag kv439)\n#include <atomic>\n#include <cstdio>\n' + s
open(dst + '/eventQueue.cpp', 'w', encoding='utf-8', newline='').write(s)
print('ok')
