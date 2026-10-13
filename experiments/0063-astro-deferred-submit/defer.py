p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b, count=1):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == count, (a[:80], s.count(a))
    s = s.replace(a, b)


# 1. forward declarations
rep("""namespace Direct {
// Defined below; the queue consumer hands ring slices to the direct path as well.
static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header);""",
    """namespace Direct {
// Defined below; the queue consumer hands ring slices to the direct path as well.
static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header);
// Experiment 0063 (BC5_DIRECT_DEFER_SUBMIT=1): submit() of the game's threads only queues the
// buffer; submit_now() is the work itself, submit_sync() waits for the queue and then does it.
static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header);
static void submit_sync(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header);""")

# 2. soft CP: marks handed to a deferred post
rep("""static thread_local std::vector<GpuDone> t_gpu_done; // the IB and its INDIRECT_BUFFER targets""",
    """static thread_local std::vector<GpuDone> t_gpu_done; // the IB and its INDIRECT_BUFFER targets
// Experiment 0063: with the submissions deferred, the marks are made on the submitting thread and
// handed to the post that runs the soft CP's pass, which adds them to its own.
static thread_local std::vector<GpuDone> t_post_marks;""")

# 3. the old submit becomes submit_now
rep("""static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
	SoftCp::clear_gpu_executed(); // the soft CP runs this buffer next, on this thread""",
    """static void submit_now(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
	SoftCp::clear_gpu_executed(); // the soft CP runs this buffer next, on this thread""")

# 4. the deferral, ahead of post()
rep("""static void post(std::function<void(bool failed)> fn) {
	if (!g_async || (t_cq == 1 && !g_ring_async)) { // the consumer has waited for its jobs itself""",
    """// Experiment 0063 (BC5_DIRECT_DEFER_SUBMIT=1, with BC5_DIRECT_ASYNC): the game's threads hand a
// buffer to a submitting thread of its own and go on. That thread does what submit() did on the
// game's thread — the cross-queue waits served on the CPU, the mapping sync, the policy filter,
// the CS ioctl — in the order the buffers came, and the posts (soft-CP passes, deferred flips)
// go through the same queue, so their order against the jobs is the one they had. The game
// leaves a buffer's packets alone until its job is done (only NOP payloads, data the GPU writes,
// and the 3-dword CONTEXT_CONTROL of the submit header change earlier, experiment 0063); the
// small buffers are copied at once. The header IBs, whose soft-CP pass runs at once on the
// game's thread, wait for the queue and go the old way (submit_sync).
static const bool g_defer = g_async && std::getenv("BC5_DIRECT_DEFER_SUBMIT") != nullptr;
struct DeferItem {
	const uint32_t*                  ib         = nullptr;
	uint32_t                         num_dwords = 0;
	const char*                      kind       = "";
	bool                             from_header = false;
	std::vector<uint32_t>            copy;
	std::function<void(bool failed)> post;
};
static std::mutex              g_defer_mutex;
static std::condition_variable g_defer_cv, g_defer_idle_cv;
static std::deque<DeferItem>   g_defer_q;
static uint32_t                g_defer_busy = 0; // queued or running
static thread_local bool       t_defer_worker = false;
static bool defer_here() {
	return g_defer && t_cq == 0 && !t_defer_worker;
}
static void defer_thread() {
	pthread_setname_np(pthread_self(), "bc5-submit");
	t_defer_worker = true;
	static std::deque<std::vector<uint32_t>> kept; // the copies outlive their jobs a while
	for (;;) {
		DeferItem it;
		{
			std::unique_lock lk(g_defer_mutex);
			g_defer_cv.wait(lk, [] { return !g_defer_q.empty(); });
			it = std::move(g_defer_q.front());
			g_defer_q.pop_front();
		}
		if (it.post) {
			auto marks = std::move(SoftCp::t_gpu_done);
			SoftCp::t_gpu_done.clear();
			post([fn = std::move(it.post), m = std::move(marks)](bool failed) mutable {
				SoftCp::t_post_marks = std::move(m);
				fn(failed);
				SoftCp::t_post_marks.clear();
			});
		} else if (it.copy.empty()) {
			submit_now(it.ib, it.num_dwords, it.kind, it.from_header);
		} else {
			if (kept.size() >= 1024) kept.pop_front();
			kept.push_back(std::move(it.copy));
			const uint32_t* c = kept.back().data();
			submit_now(c, it.num_dwords, it.kind, it.from_header);
			for (auto& g: SoftCp::t_gpu_done) { // the soft CP looks the original up
				if (g.buf >= c && g.buf < c + it.num_dwords) g.buf = it.ib + (g.buf - c);
			}
		}
		{
			std::lock_guard lk(g_defer_mutex);
			g_defer_busy--;
		}
		g_defer_idle_cv.notify_all();
	}
}
static void defer_push(DeferItem&& it) {
	static std::once_flag started;
	std::call_once(started, [] { std::thread(defer_thread).detach(); });
	std::unique_lock lk(g_defer_mutex);
	g_defer_idle_cv.wait(lk, [] { return g_defer_busy < 64; }); // the game's threads stay at most 64 items ahead
	g_defer_busy++;
	g_defer_q.push_back(std::move(it));
	lk.unlock();
	g_defer_cv.notify_one();
}
static void flush_deferred() {
	if (!g_defer || t_defer_worker) return;
	std::unique_lock lk(g_defer_mutex);
	g_defer_idle_cv.wait(lk, [] { return g_defer_busy == 0; });
}
static void submit(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
	if (!defer_here()) {
		submit_now(ib, num_dwords, kind, from_header);
		return;
	}
	SoftCp::clear_gpu_executed();
	DeferItem it;
	it.ib          = ib;
	it.num_dwords  = num_dwords;
	it.kind        = kind;
	it.from_header = from_header;
	if (ib != nullptr && num_dwords <= 64) it.copy.assign(ib, ib + num_dwords);
	defer_push(std::move(it));
}
static void submit_sync(const uint32_t* ib, uint32_t num_dwords, const char* kind, bool from_header) {
	flush_deferred();
	submit_now(ib, num_dwords, kind, from_header);
}

static void post(std::function<void(bool failed)> fn) {
	if (defer_here()) { // experiment 0063: behind the deferred submissions
		DeferItem it;
		it.post = std::move(fn);
		defer_push(std::move(it));
		return;
	}
	if (!g_async || (t_cq == 1 && !g_ring_async)) { // the consumer has waited for its jobs itself""")

rep("""static void drain() {
	if (!g_async) return;
	while""", """static void drain() {
	if (!g_async) return;
	flush_deferred(); // experiment 0063
	while""")

# 5. stubs without the direct path
rep("""static void submit(const uint32_t*, uint32_t, const char*, bool) {}""",
    """static void submit(const uint32_t*, uint32_t, const char*, bool) {}
static void submit_now(const uint32_t*, uint32_t, const char*, bool) {}
static void submit_sync(const uint32_t*, uint32_t, const char*, bool) {}""")

# 6. header IBs: the old way
rep("""	dump_cb(kind, dcb, size);
	Direct::submit(dcb, size, kind, std::strcmp(kind, "hib") == 0);
	if (use_soft_cp()) {
		SoftCp::submit(dcb, size, kind);""", """	dump_cb(kind, dcb, size);
	Direct::submit_sync(dcb, size, kind, std::strcmp(kind, "hib") == 0); // its soft-CP pass runs here, now (experiment 0063)
	if (use_soft_cp()) {
		SoftCp::submit(dcb, size, kind);""")

# 7. submit_raw's post takes the marks of a deferred submission too
rep("""			if (failed) Direct::journal("soft-cp: %s %u dwords at %p replayed in full after a failed submission\\n", kind, num, static_cast<const void*>(dwords));
			SoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : std::move(marks);""",
    """			if (failed) Direct::journal("soft-cp: %s %u dwords at %p replayed in full after a failed submission\\n", kind, num, static_cast<const void*>(dwords));
			for (auto& g: SoftCp::t_post_marks) marks.push_back(std::move(g)); // experiment 0063
			SoftCp::t_post_marks.clear();
			SoftCp::t_gpu_done = failed ? std::vector<SoftCp::GpuDone>() : std::move(marks);""")

open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
