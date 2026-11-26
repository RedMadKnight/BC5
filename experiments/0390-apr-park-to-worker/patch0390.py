#!/usr/bin/env python3
"""BC5 experiment 0390: patch_0390.diff as anchored edits, for the box, which has no `patch` on its host.
Each anchor must occur exactly once, or nothing is written. box0390.sh then checks the result against patched0390.sha256.
usage: python3 -I patch0390.py <tree with src/libs/libAmpr.cpp>"""
import sys

path = sys.argv[1] + "/src/libs/libAmpr.cpp"
s = open(path, encoding="utf-8", newline="").read()

EDITS = [
    ('''static bool AprAsync() {
	static const bool sync = std::getenv("KYTY_BC5_APR_SYNC") != nullptr;
	return !sync;
}
''', '''static bool AprAsync() {
	static const bool sync = std::getenv("KYTY_BC5_APR_SYNC") != nullptr;
	return !sync;
}

// BC5 (experiment 0390): with KYTY_BC5_APR_PARK_TO_WORKER=1 (default off; 0 is off) an AMM-only submission that stopped
// at a wait goes to its priority's worker. Without it, in async mode it starts the wait thread, whose pump runs the
// front of a queue a worker owns while the worker runs it unlocked, and pops buffers the worker or a reader still
// holds (experiment 0236, F295). The second title never takes this path: its AMM-only waits are met by the buffer's
// own earlier write.
static bool AprParkToWorker() {
	static const bool on = [] {
		const char* e = std::getenv("KYTY_BC5_APR_PARK_TO_WORKER");
		return e != nullptr && std::strtol(e, nullptr, 10) != 0;
	}();
	return on;
}
'''),
    ('''static void StartAprWaitThread() {
	static std::once_flag once;
''', '''// BC5 (experiment 0156): the priority's worker and, with KYTY_BC5_APR_READAHEAD (experiment 0203), its readers.
static void StartAprWorker(size_t qi) {
	std::call_once(g_apr_worker_once[qi], [qi] {
		std::thread(AprWorkerThread, qi).detach();
		for (size_t k = 0; k < AprReadahead(); k++) {
			std::thread(AprReaderThread, qi, k).detach();
		}
	});
}

static void StartAprWaitThread() {
	static std::once_flag once;
'''),
    ('''		std::call_once(g_apr_worker_once[qi], [qi] {
			std::thread(AprWorkerThread, qi).detach();
			for (size_t k = 0; k < AprReadahead(); k++) { // BC5 (experiment 0203): KYTY_BC5_APR_READAHEAD
				std::thread(AprReaderThread, qi, k).detach();
			}
		});
		g_apr_queue_cv.notify_all();
		return OK;
''', '''		StartAprWorker(qi);
		g_apr_queue_cv.notify_all();
		return OK;
'''),
    ('''		queue.push_back({command_buffer, state, ordered, next, submission_id, result_ptr});
		StartAprWaitThread();
''', '''		queue.push_back({command_buffer, state, ordered, next, submission_id, result_ptr});
		if (AprAsync() && AprParkToWorker()) {
			StartAprWorker(qi); // experiment 0390: the amm_only notify below wakes the worker
		} else {
			StartAprWaitThread();
		}
'''),
]

for a, _ in EDITS:
    if s.count(a) != 1:
        raise SystemExit(f"anchor found {s.count(a)} times, nothing written: {a[:60]!r}")
for a, b in EDITS:
    s = s.replace(a, b)
open(path, "w", encoding="utf-8", newline="").write(s)
print(f"{len(EDITS)} edits on {path}")
