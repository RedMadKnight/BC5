#!/usr/bin/env python3
# Experiment 0157, thirteenth step: a prefixed submission (the pieces' path and BC5_DIRECT_PREFIX_ALL) marks
# the GPU-executed packets on the ORIGINAL buffer too. The copy the GPU ran dies with the lambda; the soft
# CP's lookup (gpu_packet_done, by pointer range) then found nothing for the title's buffer and executed
# its packets itself, waits included, which serialised the game thread behind the GPU (runs 684-688:
# 37-38 fps against 45 without the prefix).
p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()


def rep(a, b):
    global s
    assert s.count(a) == 1, (s.count(a), a[:80])
    s = s.replace(a, b)


rep("""static void clear_gpu_executed() {
	t_gpu_done.clear();
}""",
    """static void clear_gpu_executed() {
	t_gpu_done.clear();
}
// Experiment 0157: the marks of a copy that ran on the GPU (a prefix of `skip` dwords, then `n` dwords
// of `orig`) carried over to `orig`; the copy's own entry goes, its memory is about to be reused.
static void alias_gpu_executed(const uint32_t* copy, size_t skip, const uint32_t* orig, uint32_t n) {
	for (auto it = t_gpu_done.begin(); it != t_gpu_done.end(); ++it) {
		if (it->buf != copy) continue;
		GpuDone h {orig, std::vector<uint8_t>(n, 0)};
		for (uint32_t o = 0; o < n && skip + o < it->done.size(); o++) h.done[o] = it->done[skip + o];
		t_gpu_done.erase(it);
		t_gpu_done.push_back(std::move(h));
		return;
	}
}""")

rep("""		submit_one(one.data(), static_cast<uint32_t>(one.size()), kind, false);
		std::erase_if(t_keep_waits, [&one](const uint32_t* w) { return w >= one.data() && w < one.data() + one.size(); });
	};""",
    """		submit_one(one.data(), static_cast<uint32_t>(one.size()), kind, false);
		SoftCp::alias_gpu_executed(one.data(), pre.size(), part, n); // experiment 0157
		std::erase_if(t_keep_waits, [&one](const uint32_t* w) { return w >= one.data() && w < one.data() + one.size(); });
	};""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
