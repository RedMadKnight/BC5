#!/usr/bin/env python3
# BC5 exp 0439 (tag vl439): the flip label (sceVideoOutGetBufferLabelAddress) for frames whose label packets sit in a
# chained piece (README item 52: the fifth "chained frame treated as top level" defect). In the private unit after
# mkpa439/mkqc444/mkfp439/mkbl439. Two candidates, each behind its own word (the fixes-first rule), both off by default:
#   (a) BC5_0439_FLIP_LABEL_GPU=1: GetBufferLabelAddress hands the title 64 labels in guest flexible memory mapped for
#       the GPU (KernelMapNamedFlexibleMemory, cpu rw / gpu rw, as the 0xc008811b submit area), so the frame's
#       RELEASE_MEM and the next frame's WAIT_REG_MEM(64) pass the filter and run on the GPU as on the console; our
#       VideoOut's flip path clears the label as before. RISK: exp 0071 left this wait to the GPU and the ring hung
#       twice (run 312, two machine resets): with the flip deferred behind the GPU's jobs a GPU-side wait on it can be
#       a cycle. Only with a fresh boot and the stall catcher.
#   (b) BC5_0439_FLIP_LABEL_PIECES=1: the label stays on the host page; a flip-label wait inside a chained or called
#       piece is served on the CPU before the submit exactly as the top-level one (wait while that buffer's flip is
#       queued, at most 100 ms, then clear a label still set), and the filter drops the packet as before.
# Journal (normal build): every 1024th piece wait served (b), and with (a) at every 1024th flip clear whether the
# label was set (written by the GPU) when VideoOut cleared it.
# Usage: python mkvl439.py IN.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '\r' not in s and 'vl439' not in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


# the labels become a pointer (the host page by default) so (a) can swap in guest memory before the title's first use
rep('''static uint64_t (&g_labels)[64] = *reinterpret_cast<uint64_t (*)[64]>(
    ::mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));''',
    '''static uint64_t* g_labels = reinterpret_cast<uint64_t*>( // exp 0439 (tag vl439): a pointer, (a) may move it to guest memory
    ::mmap(nullptr, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0));
static constexpr uint64_t kLabelsBytes = 64 * sizeof(uint64_t); // exp 0439 (tag vl439): the labels array size, used where the range is checked''')
for _ in range(2):
    rep('''						if (label >= l0 && label < l0 + sizeof(g_labels) && !wait_satisfied(p, op == 0x93)) {
							// Experiment 0069''' if _ == 0 else '''						if (label >= l0 && label < l0 + sizeof(g_labels) && !wait_satisfied(p, op == 0x93)) {
							*reinterpret_cast''',
        '''						if (label >= l0 && label < l0 + kLabelsBytes && !wait_satisfied(p, op == 0x93)) {
							// Experiment 0069''' if _ == 0 else '''						if (label >= l0 && label < l0 + kLabelsBytes && !wait_satisfied(p, op == 0x93)) {
							*reinterpret_cast''')
assert 'sizeof(g_labels)' not in s, 'a sizeof(g_labels) left'
# (a): the allocation at the title's request
rep('''	*out = Bc5Gc::g_labels;
''', '''	{ // exp 0439 (tag vl439 a, BC5_0439_FLIP_LABEL_GPU=1): the labels in guest memory the GPU sees, once, before the title's first use
		static const bool on = [] {
			const char* e = std::getenv("BC5_0439_FLIP_LABEL_GPU");
			return e != nullptr && e[0] == '1' && e[1] == 0;
		}();
		static std::once_flag once;
		if (on)
			std::call_once(once, [] {
				void*     addr = nullptr;
				const int r    = LibKernel::Memory::KernelMapNamedFlexibleMemory(&addr, 0x4000, 0x33 /* cpu rw, gpu rw */, 0, "bc5-flip-labels");
				if (r == 0 && addr != nullptr) {
					std::memset(addr, 0, 0x4000);
					std::memcpy(addr, Bc5Gc::g_labels, Bc5Gc::kLabelsBytes);
					Bc5Gc::g_labels = static_cast<uint64_t*>(addr);
				}
				std::fprintf(stderr, "[bc5] exp 0439 (tag vl439): flip labels %s 0x%" PRIx64 " (KernelMapNamedFlexibleMemory %d)\\n", r == 0 ? "in guest GPU-visible memory at" : "ALLOCATION FAILED, still host",
				             reinterpret_cast<uint64_t>(Bc5Gc::g_labels), r);
			});
	}
	*out = Bc5Gc::g_labels;
''')
# (b): the pieces' flip-label waits served as the top-level one, in the fp439 walk's place (before the submit)
rep('''			bc5::fp439::Stats     ss;
''', '''			bc5::fp439::Stats     ss;
			{ // exp 0439 (tag vl439 b, BC5_0439_FLIP_LABEL_PIECES=1): a flip-label wait in a chained or called piece is
			  // served on the CPU as the top-level one (experiment 0069's rule: wait while that buffer's flip is queued, at
			  // most 100 ms, then clear a label still set); the filter drops the packet as before
				static const bool vlb = [] {
					const char* e = std::getenv("BC5_0439_FLIP_LABEL_PIECES");
					return e != nullptr && e[0] == '1' && e[1] == 0;
				}();
				const auto l0 = reinterpret_cast<uint64_t>(&g_labels[0]);
				for (size_t k = 1; vlb && k < cr.pieces.size(); k++) {
					const uint32_t* w = cr.pieces[k].src;
					const uint32_t  n = static_cast<uint32_t>(cr.pieces[k].n);
					bc5::fp439::flip_label_waits(w, n, l0, kLabelsBytes, [&](const uint32_t* p, bool is64, uint64_t label) {
						const size_t   idx = static_cast<size_t>((label - l0) / sizeof(uint64_t));
						const uint64_t tw  = SoftCp::now_ns();
						while (g_flip_pending[idx].load() > 0 && !wait_satisfied(p, is64) && SoftCp::now_ns() - tw < 100'000'000ull)
							std::this_thread::sleep_for(std::chrono::microseconds(50));
						const bool still = !wait_satisfied(p, is64);
						if (still) *reinterpret_cast<volatile uint64_t*>(label & ~7ull) = 0;
#ifndef BC5_LEAN
						static std::atomic<uint64_t> n_vl {0}, n_clr {0};
						if (still) n_clr++;
						if ((n_vl++ & 0x3ffu) == 0)
							journal("vl439: flip label 0x%" PRIx64 " wait in piece %zu served on the CPU: %.2f ms (%" PRIu64 " so far, %" PRIu64 " cleared still set)\\n", label, k,
							        static_cast<double>(SoftCp::now_ns() - tw) / 1e6, n_vl.load(), n_clr.load());
#endif
					});
				}
			}
''')
# (a)'s accounting at the flip path's clear by index
rep('''			Bc5Gc::g_labels[index] = 0;
''', '''#ifndef BC5_LEAN
			{ // exp 0439 (tag vl439): was the label set (by the frame's RELEASE_MEM) when VideoOut cleared it
				static std::atomic<uint64_t> n_clear {0}, n_set {0};
				if (Bc5Gc::g_labels[index] != 0) n_set++;
				if ((n_clear++ & 0x3ffu) == 0)
					std::fprintf(stderr, "[bc5] exp 0439 (tag vl439): flip clears %" PRIu64 ", label set at the clear %" PRIu64 " (labels at 0x%" PRIx64 ")\\n", n_clear.load(), n_set.load(), reinterpret_cast<uint64_t>(Bc5Gc::g_labels));
			}
#endif
			Bc5Gc::g_labels[index] = 0;
''')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkvl439: wrote', dst)
