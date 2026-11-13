// BC5 experiment 0412: CPU test of saveguard0412.inc (tag sg412): the fault record's exit against a stand-in writer.
// The stand-in "title" saves as the title does through the host: mount, write the file in parts (each part one
// guarded call), unmount. The stand-in "exit" is close(): what stands on the disk when it returns is what a real
// exit would leave. Held callers are ended by an exception (the hook), where the real build holds them for ever.
//   A  the exit is asked for in the middle of a write: the file is complete when close() returns
//   B  the exit is asked for between two writes of one save: complete
//   C  the exit is asked for before the save's first write (mounted, clean): the file is untouched, the writer held
//   D  the exit is asked for before the mount: untouched, the writer held
//   E  the writer never finishes: close() returns at its bound and SAYS the save may be incomplete
//   F  after the close every guarded call is held, also on a mount that was being written
//   G  without a close nothing is held; slot_of's parsing; a library call that writes is refused while draining
// The file is "complete" (every part, in order), "untouched" (does not exist) or "half": A-D must never be half.
// build: g++ -std=c++20 -O1 -Wall -Wextra -Werror -pthread saveguard0412.cpp -o saveguard0412
#include <atomic>
#include <chrono>
#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <string>
#include <thread>

#include "saveguard0412.inc"

static uint64_t g_checks = 0, g_ok = 0;
static void     check(bool c, const char* what) {
	g_checks++;
	if (c) g_ok++;
	else if (g_checks - g_ok < 20) std::printf("FAIL: %s\n", what);
}

struct Held {};
static void throw_held() { throw Held{}; }

static void reset() {
	sg412::g_phase.store(sg412::kOpen);
	sg412::g_ops.store(0);
	for (auto& s: sg412::g_slot) s.store(sg412::kUnmounted);
	sg412::g_last_ms.store(-1);
	sg412::g_held.store(0);
}

static const int   kParts = 4;
static std::string g_path;

// 0 untouched, 1 complete, 2 half
static int file_state() {
	std::FILE* f = std::fopen(g_path.c_str(), "rb");
	if (f == nullptr) return 0;
	char   buf[64] = {};
	size_t n       = std::fread(buf, 1, sizeof(buf), f);
	std::fclose(f);
	return (n == static_cast<size_t>(kParts) * 4 && std::string(buf, n) == "P0;;P1;;P2;;P3;;") ? 1 : 2;
}

struct Writer {
	std::atomic<int>  stage{0};       // 1 mounted, 2 in the first part's call, 3 between parts, 9 done
	std::atomic<bool> go_mount{true}; // false: wait before the mount
	std::atomic<bool> go_write{true}; // false: wait after the mount, before the first write
	std::atomic<bool> go_rest{true};  // false: wait inside the first part's call
	std::atomic<bool> go_next{true};  // false: wait between the first and the second part
	std::atomic<bool> stuck{false};   // true: never write the rest, never unmount
	std::atomic<bool> held{false};
	std::atomic<bool> give_up{false};
	void wait(std::atomic<bool>& g) {
		while (!g.load() && !give_up.load()) std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	void run() {
		try {
			wait(go_mount);
			{
				sg412::Op op(sg412::kLib, true); // the mount call
				sg412::mounted(3);
			}
			stage.store(1);
			wait(go_write);
			std::FILE* f = nullptr;
			for (int i = 0; i < kParts; i++) {
				{
					sg412::Op op(sg412::slot_of("/savedata3/save.dat"), true);
					if (f == nullptr) f = std::fopen(g_path.c_str(), "wb");
					if (i == 0) {
						stage.store(2);
						wait(go_rest);
					}
					std::fprintf(f, "P%d;;", i);
					std::fflush(f);
				}
				if (i == 0) {
					stage.store(3);
					wait(go_next);
					if (stuck.load()) {
						while (!give_up.load()) std::this_thread::sleep_for(std::chrono::milliseconds(1));
						std::fclose(f);
						return;
					}
				}
			}
			{
				sg412::Op op(sg412::slot_of("/savedata3/save.dat"), false); // the close call
				std::fclose(f);
			}
			sg412::unmounted(3);
			stage.store(9);
		} catch (const Held&) {
			held.store(true);
		}
	}
};

static void until(const std::atomic<int>& v, int want) {
	for (int i = 0; i < 5000 && v.load() != want; i++) std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
static void until_true(const std::atomic<bool>& v) {
	for (int i = 0; i < 5000 && !v.load(); i++) std::this_thread::sleep_for(std::chrono::milliseconds(1));
}

int main(int argc, char** argv) {
	g_path             = std::string(argc > 1 ? argv[1] : ".") + "/saveguard0412-standin.dat";
	sg412::g_hold_hook = throw_held;

	for (int round = 0; round < 20; round++) {
		// A: in the middle of a write
		{
			reset();
			std::remove(g_path.c_str());
			Writer w;
			w.go_rest.store(false);
			std::thread th([&] { w.run(); });
			until(w.stage, 2);
			std::thread rel([&] {
				std::this_thread::sleep_for(std::chrono::milliseconds(20 + round));
				w.go_rest.store(true);
			});
			const sg412::Closed c = sg412::close(5000);
			const int           st = file_state();
			rel.join();
			th.join();
			check(st == 1, "A: the file is complete when close() returns");
			check(c.in_flight && c.complete && c.ops_at_request == 1 && c.dirty_at_request == 1 && c.ops_left == 0 && c.dirty_left == 0, "A: in flight at the request, complete at the end");
			check(c.waited_ms >= 15 && c.waited_ms < 4000 && !w.held.load() && w.stage.load() == 9, "A: the wait took as long as the save, the writer was not held");
		}
		// B: between two writes of one save
		{
			reset();
			std::remove(g_path.c_str());
			Writer w;
			w.go_next.store(false);
			std::thread th([&] { w.run(); });
			until(w.stage, 3);
			std::thread rel([&] {
				std::this_thread::sleep_for(std::chrono::milliseconds(15));
				w.go_next.store(true);
			});
			const sg412::Closed c = sg412::close(5000);
			const int           st = file_state();
			rel.join();
			th.join();
			check(st == 1, "B: complete");
			check(c.in_flight && c.complete && c.ops_at_request == 0 && c.dirty_at_request == 1, "B: no call in flight but a written mount: in flight, then complete");
		}
		// C: mounted, nothing written yet
		{
			reset();
			std::remove(g_path.c_str());
			Writer w;
			w.go_write.store(false);
			std::thread th([&] { w.run(); });
			until(w.stage, 1);
			const sg412::Closed c = sg412::close(5000);
			w.go_write.store(true);
			until_true(w.held);
			const int st = file_state();
			th.join();
			check(st == 0, "C: untouched");
			check(!c.in_flight && c.complete && c.waited_ms < 1000 && w.held.load(), "C: nothing in flight, no wait, the writer's first write held");
		}
		// D: before the mount
		{
			reset();
			std::remove(g_path.c_str());
			Writer w;
			w.go_mount.store(false);
			std::thread th([&] { w.run(); });
			const sg412::Closed c = sg412::close(5000);
			w.go_mount.store(true);
			until_true(w.held);
			const int st = file_state();
			th.join();
			check(st == 0 && !c.in_flight && c.complete && w.held.load() && sg412::g_slot[3].load() == sg412::kUnmounted, "D: untouched, the mount call held");
		}
	}
	// E: the writer never finishes: the bound holds and the outcome says so
	{
		reset();
		std::remove(g_path.c_str());
		Writer w;
		w.go_next.store(false);
		w.stuck.store(true);
		std::thread th([&] { w.run(); });
		until(w.stage, 3);
		w.go_next.store(true);
		const sg412::Closed c = sg412::close(300);
		check(file_state() == 2, "E: the stand-in's file is half (the writer stopped)");
		check(c.in_flight && !c.complete && c.dirty_left == 1 && c.ops_left == 0 && c.waited_ms >= 300 && c.waited_ms < 2000, "E: the bound holds; a written mount is left");
		check(std::string(sg412::verdict(c)).find("MAY BE INCOMPLETE") != std::string::npos, "E: the record's words say the save may be incomplete");
		// F: after the close every guarded call is held, also on the written mount
		bool held = false;
		try {
			sg412::Op op(3, true);
		} catch (const Held&) { held = true; }
		check(held && sg412::g_ops.load() == 0, "F: a write on the written mount is held after the close, and not counted");
		held = false;
		try {
			sg412::Op op(3, false);
		} catch (const Held&) { held = true; }
		check(held, "F: a close call is held after the close");
		w.give_up.store(true);
		th.join();
	}
	// G: no close: nothing held; parsing; the library's writer while draining
	{
		reset();
		{
			sg412::Op a(sg412::kLib, true);
			sg412::Op b(5, true);
			sg412::Op n(sg412::kNone, true);
			check(sg412::g_ops.load() == 2 && sg412::g_held.load() == 0, "G: open: two counted, the unguarded one not, none held");
		}
		check(sg412::g_ops.load() == 0, "G: the count returns to zero");
		check(sg412::g_slot[5].load() == sg412::kUnmounted, "G: a write on a slot that is not mounted does not make it dirty");
		sg412::mounted(5);
		{ sg412::Op b(5, false); }
		check(sg412::g_slot[5].load() == sg412::kClean, "G: a call that writes nothing leaves the mount clean");
		{ sg412::Op b(5, true); }
		check(sg412::g_slot[5].load() == sg412::kDirty && sg412::dirty_mounts() == 1, "G: a write makes it dirty");
		sg412::unmounted(5);
		check(sg412::dirty_mounts() == 0, "G: the unmount ends it");
		check(sg412::slot_of("/savedata0/a") == 0 && sg412::slot_of("/savedata12") == 12 && sg412::slot_of("/savedata15/x/y") == 15, "G: slot_of on save paths");
		check(sg412::slot_of("/savedata16/a") == sg412::kNone && sg412::slot_of("/savedata") == sg412::kNone && sg412::slot_of("/savedata1x/a") == sg412::kNone && sg412::slot_of("/app0/savedata0") == sg412::kNone &&
		          sg412::slot_of(nullptr) == sg412::kNone && sg412::slot_of("") == sg412::kNone,
		      "G: slot_of on other paths");
		sg412::g_phase.store(sg412::kDraining);
		sg412::mounted(6);
		sg412::mounted(7);
		sg412::g_slot[7].store(sg412::kDirty);
		check(!sg412::allowed(sg412::kLib, true) && !sg412::allowed(6, true) && sg412::allowed(7, true) && sg412::allowed(6, false) && sg412::allowed(sg412::kLib, false),
		      "G: draining: the library's writer and a first write are refused; the save being written and calls that write nothing go on");
		sg412::g_phase.store(sg412::kFinal);
		check(!sg412::allowed(7, true) && !sg412::allowed(6, false), "G: final: all refused");
		check(!sg412::g_root_set.load(), "G: no save directory before the first mount");
		sg412::note_root("_SaveData/PPSA00000/slot1");
		sg412::note_root("_SaveData/PPSA00000/slot2");
		check(sg412::g_root_set.load() && std::string(sg412::g_root) == "_SaveData/PPSA00000/slot1", "G: the first mount's directory is kept");
		sg412::Closed none;
		check(std::string(sg412::verdict(none)).find("no save") == 0, "G: the words for no save in flight");
	}
	std::remove(g_path.c_str());
	std::printf("saveguard0412: %" PRIu64 " of %" PRIu64 "; end\n", g_ok, g_checks);
	return g_ok == g_checks ? 0 : 1;
}
