p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == 1, (a[:80], s.count(a))
    s = s.replace(a, b)


# 1. the job remembers the hash of its buffers
rep("""	std::vector<uint64_t>    watch_args; // experiment 0050: indirect arguments of the watched program
	uint64_t                 watch_ud = 0;
};""", """	std::vector<uint64_t>    watch_args; // experiment 0050: indirect arguments of the watched program
	uint64_t                 watch_ud = 0;
	// Experiment 0063 (BC5_DIRECT_IB_STABLE_CHECK=1): the buffer and its nested buffers, hashed at
	// submission and again once the job is done; a change means the game rewrote a buffer the GPU
	// had not finished, and the host could not filter it later than now.
	uint64_t                                    ib_hash = 0;
	std::vector<std::pair<const uint32_t*, uint32_t>> hashed;
};
static uint64_t ib_hash(const std::vector<std::pair<const uint32_t*, uint32_t>>& bufs) {
	uint64_t h = 0xcbf29ce484222325ull;
	for (const auto& [p, n]: bufs) {
		const auto* v = reinterpret_cast<const volatile uint32_t*>(p);
		for (uint32_t i = 0; i < n; i++) h = (h ^ v[i]) * 0x100000001b3ull;
		h = (h ^ n) * 0x100000001b3ull;
	}
	return h;
}
static const bool g_stable_check = std::getenv("BC5_DIRECT_IB_STABLE_CHECK") != nullptr;""")

# 2. hash at submission (async jobs only, where the completion thread sees them again)
rep("""		it.job.watch_ud = t_watch_ud;
		t_watch_ud      = 0;
		frame_profile_job(t_cq == 0, r.prepare_ms, r.list_ms, r.cs_ms);""", """		it.job.watch_ud = t_watch_ud;
		t_watch_ud      = 0;
		if (g_stable_check) { // experiment 0063
			it.job.hashed.emplace_back(ib, num_dwords);
			for (const auto& nb: r.nested) it.job.hashed.emplace_back(reinterpret_cast<const uint32_t*>(nb.cpu_addr), nb.num_dwords);
			it.job.ib_hash = ib_hash(it.job.hashed);
		}
		frame_profile_job(t_cq == 0, r.prepare_ms, r.list_ms, r.cs_ms);""")

# 3. compare at completion
rep("""			forget_label_writes(j.seq, r.timed_out || r.rc == -125); // experiment 0055""", """			forget_label_writes(j.seq, r.timed_out || r.rc == -125); // experiment 0055
			if (g_stable_check && !j.hashed.empty() && r.ok) { // experiment 0063
				static std::atomic<uint64_t> jobs {0}, changed {0}, dwords {0}, changed_dwords {0};
				uint64_t n_dw = 0;
				for (const auto& b: j.hashed) n_dw += b.second;
				dwords += n_dw;
				if (ib_hash(j.hashed) != j.ib_hash) {
					const uint64_t c = changed++;
					changed_dwords += n_dw;
					if (c < 40) {
						journal("ib stable check: #%" PRIu64 " %s %u dwords (+%zu nested) CHANGED before its job was done, %.2f ms after submission\\n", j.n, j.kind,
						        j.num_dwords, j.hashed.size() - 1, static_cast<double>(SoftCp::now_ns() - j.queued_ns) / 1e6);
					}
				}
				if ((++jobs & 0x3fffu) == 0) {
					journal("ib stable check: %" PRIu64 " jobs (%" PRIu64 " dwords), %" PRIu64 " changed before done (%" PRIu64 " dwords)\\n", jobs.load(), dwords.load(), changed.load(),
					        changed_dwords.load());
				}
			}""")
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
