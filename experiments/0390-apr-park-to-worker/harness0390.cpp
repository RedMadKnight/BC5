// BC5 experiment 0390: the real APR queue code of libAmpr.cpp (cut by extract0390.py) on stubs, with no emulator
// headers. It drives ExecuteAprCommandBuffer with synthetic submissions and counts how often each command ran.
// Scenarios (argv[1]):
//   none   the second title's shape: the AMM-only submission's wait is met by its own earlier write. Control.
//   busy   an AMM-only submission parks in a queue a worker owns; read buffers queue behind it and drain.
//   alone  an AMM-only submission parks at a priority that has no worker yet.
// Exit code 0: every write-address, event, map and submission result happened exactly once, in queue order.
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <condition_variable>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <limits>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

constexpr int OK = 0;
#define BC5_DIAG_ENV(name) static_cast<const char*>(nullptr)
#define LOGF(...) std::fprintf(stderr, __VA_ARGS__)

static std::mutex            g_stub_mutex;
static std::set<std::string> g_thread_names;
static std::map<uint64_t, int> g_writes;  // guest address -> writes
static std::map<int32_t, int>  g_events;  // event id -> triggers
static std::map<uint32_t, int> g_results; // submission id -> results
static std::vector<uint32_t>   g_result_order;
static std::map<uint64_t, int> g_maps;    // va -> map commands
static std::atomic<int>        g_file_reads {0};

static int pthread_self() { return 0; }
static int pthread_setname_np(int, const char* name) {
	std::scoped_lock lock(g_stub_mutex);
	g_thread_names.insert(name);
	return 0;
}
static void AmmTraceStamp() {}
static bool AprJournalOn() { return false; }
static bool AprJournalFile(uint32_t) { return false; }
static bool AprJournalFailureDue() { return false; }
static void AprJournal(const char*, ...) {}

namespace Common {
class File {
public:
	enum class Mode { Read };
	bool     Open(const std::string&, Mode) { return true; }
	uint64_t Size() { return uint64_t {1} << 40u; }
	bool     Seek(uint64_t) { return true; }
	void     Read(void* out, uint32_t n, uint32_t* got) {
		std::this_thread::sleep_for(std::chrono::microseconds(300)); // a reader's file read
		std::memset(out, 0x5a, n);
		*got = n;
	}
	void Close() {}
};
} // namespace Common

namespace Libs {
namespace LibKernel {
constexpr int KERNEL_ERROR_EINVAL = -1;
constexpr int KERNEL_ERROR_EFAULT = -2;
constexpr int KERNEL_ERROR_ENOENT = -3;
namespace EventQueue {
using KernelEqueue = uint64_t;
static int KernelTriggerAmprEvent(KernelEqueue, int32_t id, void*) {
	std::scoped_lock lock(g_stub_mutex);
	g_events[id]++;
	return OK;
}
} // namespace EventQueue
namespace Memory {
static int  KernelMunmap(uint64_t, uint64_t) { return OK; }
static void Bc5MapStatsAdd(bool, uint64_t) {}
} // namespace Memory
} // namespace LibKernel

namespace AprShared {
template <typename T>
static bool ReadGuest(uint64_t address, T* out) {
	*out = static_cast<T>(reinterpret_cast<std::atomic<uint64_t>*>(address)->load());
	return true;
}
static bool WriteGuest(uint64_t address, uint64_t value) {
	reinterpret_cast<std::atomic<uint64_t>*>(address)->store(value);
	std::scoped_lock lock(g_stub_mutex);
	g_writes[address]++;
	return true;
}
static bool TryGetHostPath(uint32_t, std::string* out) {
	*out = "stub";
	return true;
}
static bool IsValidGuestRange(uint64_t, uint64_t, bool) { return true; }
static void SetSubmissionResult(uint32_t id, int32_t, uint32_t) {
	std::scoped_lock lock(g_stub_mutex);
	g_results[id]++;
	g_result_order.push_back(id);
}
static int WriteResult(void*, int32_t, uint32_t) { return OK; }
} // namespace AprShared

namespace LibAmpr {
namespace Ampr {
static int ExecuteAprCommandBuffer(uint64_t command_buffer, int32_t* execution_result, uint32_t* error_offset, uint32_t priority = 0,
                                   uint32_t submission_id = 0, uint64_t result_ptr = 0);
constexpr uint64_t APR_HOST_READ_CHUNK_SIZE = 4 * 1024 * 1024;
#include "types.inc"

static std::unordered_map<uint64_t, CommandBufferState> g_states;
static bool TryGetCommandBufferState(uint64_t command_buffer, CommandBufferState* out) {
	std::scoped_lock lock(g_stub_mutex);
	const auto       it = g_states.find(command_buffer);
	if (it == g_states.end()) return false;
	*out = it->second;
	return true;
}
static bool AmmTrace() { return false; }
static void AmmAutoReleaseVa(uint64_t, uint64_t) {}
static int  ExecuteAmmMapCommand(const CommandBufferState::AmmMapCommand& command) {
	std::scoped_lock lock(g_stub_mutex);
	g_maps[command.va]++;
	return OK;
}

#include "queue.inc"

static int ReadHostFileToGuest(const std::string&, uint64_t, uint64_t destination, uint64_t size, uint64_t* bytes_read) {
	std::this_thread::sleep_for(std::chrono::milliseconds(2)); // the window in which a worker runs its front unlocked
	std::memset(reinterpret_cast<void*>(destination), 0x5a, size);
	*bytes_read = size;
	g_file_reads++;
	return OK;
}

// One recorded buffer, with record offsets in call order.
struct Rec {
	CommandBufferState s;
	uint64_t           off = 0;
	Rec&               read(uint32_t file, uint64_t size, void* dst) {
		s.read_file_commands.push_back({off++, file, reinterpret_cast<uint64_t>(dst), size, 0});
		return *this;
	}
	Rec& write(void* a, uint64_t v) {
		s.write_address_commands.push_back({off++, reinterpret_cast<uint64_t>(a), v});
		return *this;
	}
	Rec& wait(void* a, uint64_t v) {
		s.wait_address_commands.push_back({off++, reinterpret_cast<uint64_t>(a), v, 4});
		return *this;
	}
	Rec& event(int32_t id) {
		s.kernel_event_commands.push_back({off++, 0, id, 0});
		return *this;
	}
	Rec& map(uint64_t va) {
		CommandBufferState::AmmMapCommand m {};
		m.record_offset = off++;
		m.va            = va;
		m.size          = 0x10000;
		s.amm_map_commands.push_back(m);
		return *this;
	}
	void submit(uint64_t cb, uint32_t priority, uint32_t id) {
		s.write_offset = off;
		{
			std::scoped_lock lock(g_stub_mutex);
			g_states[cb] = s;
		}
		int32_t  r = 0;
		uint32_t e = 0;
		ExecuteAprCommandBuffer(cb, &r, &e, priority, id, 0);
	}
};

static int Run(const std::string& scenario) {
	constexpr int                N = 200;
	static std::atomic<uint64_t> counter {0}; // the title's sequence counter
	static std::atomic<uint64_t> park_done {0};
	static std::atomic<uint64_t> slots[N + 1];
	static uint8_t               dst[N + 1][256];
	const bool                   alone = scenario == "alone";
	const bool                   none  = scenario == "none";
	const uint32_t               prio  = alone ? 6 : 1;
	uint32_t                     id    = 1;
	std::vector<uint32_t>        expect_order;

	if (!alone) {
		Rec r;
		r.read(1, 64, dst[0]).write(&slots[0], 1).event(1000);
		expect_order.push_back(id);
		r.submit(0x1000, prio, id++);
	}
	const uint32_t park_id = id++;
	{
		Rec p;
		p.map(0x10);
		if (none) p.write(&counter, 1); // the second title's shape (exp 0236): its own write meets its wait
		p.wait(&counter, 1).map(0x20).write(&park_done, 1);
		p.submit(0x2000, prio, park_id);
	}
	if (!none) expect_order.push_back(park_id); // in "none" it finishes on this thread, ahead of the queue
	if (!alone) {
		for (int i = 1; i <= N; i++) {
			Rec r;
			r.read(10 + i, 64, dst[i]).write(&slots[i], 1).event(1000 + i);
			expect_order.push_back(id);
			r.submit(0x3000 + 0x100 * static_cast<uint64_t>(i), prio, id++);
		}
	}
	std::this_thread::sleep_for(std::chrono::milliseconds(20));
	if (!none) {
		Rec m; // what the title does: a later AMM-only submission moves the counter
		m.map(0x30).write(&counter, 1);
		m.submit(0x4000, prio, 0);
	}
	const size_t want = expect_order.size() + (none ? 1 : 0);
	const auto   end  = std::chrono::steady_clock::now() + std::chrono::seconds(10);
	for (;;) {
		{
			std::scoped_lock lock(g_stub_mutex);
			if (g_result_order.size() >= want) break;
		}
		if (std::chrono::steady_clock::now() > end) break;
		std::this_thread::sleep_for(std::chrono::milliseconds(5));
	}
	std::this_thread::sleep_for(std::chrono::milliseconds(100)); // late duplicates

	std::scoped_lock lock(g_stub_mutex);
	int              bad_writes = 0, bad_events = 0, bad_results = 0, lost = 0;
	if (!alone) {
		for (int i = 0; i <= N; i++) {
			const int w = g_writes[reinterpret_cast<uint64_t>(&slots[i])];
			const int e = g_events[1000 + i];
			bad_writes += w != 1;
			bad_events += e != 1;
			lost += w == 0;
		}
	}
	bad_results += g_results[park_id] != 1;
	for (const uint32_t s: expect_order) {
		bad_results += s != park_id && g_results[s] != 1;
	}
	std::vector<uint32_t> got;
	for (const uint32_t s: g_result_order) {
		if (!none || s != park_id) got.push_back(s);
	}
	const bool order_ok = got == expect_order;
	const int  parked_bad =
	    (g_maps[0x10] != 1) + (g_maps[0x20] != 1) + (g_writes[reinterpret_cast<uint64_t>(&park_done)] != 1);
	const bool wait_thread = g_thread_names.count("bc5-apr-wait") != 0;
	char       worker[16];
	std::snprintf(worker, sizeof(worker), "bc5-apr-q%u", prio);
	std::printf("%s: submissions %zu, results %zu, wrong writes %d (never ran %d), wrong events %d, wrong results %d, order %s, "
	            "parked buffer wrong %d, wait thread %s, worker %s\n",
	            scenario.c_str(), want, g_result_order.size(), bad_writes, lost, bad_events, bad_results, order_ok ? "ok" : "WRONG",
	            parked_bad, wait_thread ? "started" : "not started", g_thread_names.count(worker) != 0 ? "started" : "not started");
	std::fflush(stdout);
	return (bad_writes + bad_events + bad_results + parked_bad + (order_ok ? 0 : 1)) != 0 ? 1 : 0;
}
} // namespace Ampr
} // namespace LibAmpr
} // namespace Libs

int main(int argc, char** argv) {
	const int rc = Libs::LibAmpr::Ampr::Run(argc > 1 ? argv[1] : "busy");
	std::fflush(stdout);
	std::_Exit(rc); // the workers and readers never return
}
