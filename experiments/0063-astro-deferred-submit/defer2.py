p = "/home/kjaniszewski/src/KytyPlus/src/libs/bc5LleAgc.cpp"
s = open(p, encoding="utf-8", newline="").read()
nl = "\r\n" if "\r\n" in s else "\n"


def rep(a, b, count=1):
    global s
    a = a.replace("\n", nl)
    b = b.replace("\n", nl)
    assert s.count(a) == count, (a[:80], s.count(a))
    s = s.replace(a, b)


rep("""// game's thread, wait for the queue and go the old way (submit_sync).
static const bool g_defer = g_async && std::getenv("BC5_DIRECT_DEFER_SUBMIT") != nullptr;""",
    """// game's thread, wait for the queue and go the old way (submit_sync). One queue and one thread per
// submitting thread of the game: with one queue for all, a graphics buffer's wait for a label of
// a compute buffer that another game thread submits a moment later held that buffer up behind
// it, and the wait was given up at 8 ms every frame (run 287).
static const bool g_defer = g_async && std::getenv("BC5_DIRECT_DEFER_SUBMIT") != nullptr;""")

rep("""static std::mutex              g_defer_mutex;
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
		}""", """struct DeferQueue {
	std::mutex              mutex;
	std::condition_variable cv, idle_cv;
	std::deque<DeferItem>   q;
	uint32_t                busy = 0; // queued or running
};
static std::mutex               g_defer_list_mutex;
static std::vector<DeferQueue*> g_defer_queues; // all of them, for drain()
static thread_local DeferQueue* t_defer_q      = nullptr;
static thread_local bool        t_defer_worker = false;
static bool defer_here() {
	return g_defer && t_cq == 0 && !t_defer_worker;
}
static void defer_thread(DeferQueue* dq) {
	pthread_setname_np(pthread_self(), "bc5-submit");
	t_defer_worker = true;
	std::deque<std::vector<uint32_t>> kept; // the copies outlive their jobs a while
	for (;;) {
		DeferItem it;
		{
			std::unique_lock lk(dq->mutex);
			dq->cv.wait(lk, [dq] { return !dq->q.empty(); });
			it = std::move(dq->q.front());
			dq->q.pop_front();
		}""")

rep("""		{
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
}""", """		{
			std::lock_guard lk(dq->mutex);
			dq->busy--;
		}
		dq->idle_cv.notify_all();
	}
}
static void defer_push(DeferItem&& it) {
	if (t_defer_q == nullptr) {
		t_defer_q = new DeferQueue; // lives as long as the process
		{
			std::lock_guard lk(g_defer_list_mutex);
			g_defer_queues.push_back(t_defer_q);
		}
		std::thread(defer_thread, t_defer_q).detach();
	}
	DeferQueue*      dq = t_defer_q;
	std::unique_lock lk(dq->mutex);
	dq->idle_cv.wait(lk, [dq] { return dq->busy < 64; }); // the game's thread stays at most 64 items ahead
	dq->busy++;
	dq->q.push_back(std::move(it));
	lk.unlock();
	dq->cv.notify_one();
}
static void flush_one(DeferQueue* dq) {
	std::unique_lock lk(dq->mutex);
	dq->idle_cv.wait(lk, [dq] { return dq->busy == 0; });
}
static void flush_deferred() { // this thread's queue
	if (!g_defer || t_defer_worker || t_defer_q == nullptr) return;
	flush_one(t_defer_q);
}
static void flush_all_deferred() { // every game thread's queue
	if (!g_defer || t_defer_worker) return;
	std::vector<DeferQueue*> all;
	{
		std::lock_guard lk(g_defer_list_mutex);
		all = g_defer_queues;
	}
	for (DeferQueue* dq: all) flush_one(dq);
}""")

rep("""	flush_deferred(); // experiment 0063
	while""", """	flush_all_deferred(); // experiment 0063
	while""")
open(p, "w", encoding="utf-8", newline="").write(s)
print("ok")
