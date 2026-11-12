// BC5 experiment 0412 (tag mr412, DESIGN-learned-windows.md, README sections 51-53): the learned windows replaced by a
// rule. Three switches, each off when unset or 0 (one test of a constant where it is asked):
//   BC5_GUARD_MAP_RULE=1|2   R1: every 2 MiB chunk under a view of direct memory is imported when the view exists, with
//                            no name list and no "has data" test (1: the direct-memory file; 2: the private file too).
//   BC5_GUARD_PRT_BG=1       R2: one PRT mapping (reads 0, writes dropped, no memory) under the guest's address span
//                            [kBgLo, kBgHi) at device open; real mappings replace it. It acts ONLY with MAP_RULE on:
//                            with the "by data" import a PRT page under an unimported view would turn a loud miss
//                            (a GPU fault) into a silent one (the top session's point 3). scratch_fill does nothing
//                            inside the span then.
//   BC5_GUARD_LEARN_LOG=1|2  the catcher: a GPU fault that would be learned is journaled with what lay at its address
//                            (classify below), and nothing is written to the learned file or the alias file.
//                            1: the window still joins this run's list in memory, so the same place does not fault
//                            again in this run; 2: nothing is added at all.
// The span: 4 GiB (above libdrm's 32-bit range, where the device keeps its argument slot) to the end of the title's
// AMM window (0x9000000000); the device's own addresses are at 16 TiB and its code page at 0xFE00000000
// (backend/include/bc5/direct.hpp kCodeVa, backend/src/direct.cpp kScratchVa), outside it.
// This text is included by the main unit and by the CPU test maprule0412.cpp.
namespace mr412 {
static constexpr uint64_t kBgLo = 0x100000000ull, kBgHi = 0x9000000000ull;
inline int env_digit(const char* name, int max) {
	const char* e = std::getenv(name);
	if (e == nullptr || e[0] < '0' || e[0] > '9' || e[1] != 0) return 0;
	const int v = e[0] - '0';
	return v > max ? 0 : v;
}
inline int rule() {
	static const int v = env_digit("BC5_GUARD_MAP_RULE", 2);
	return v;
}
inline bool rule_for(int kind) { return rule() == 2 || (rule() == 1 && kind == 0); } // kind: 0 direct memory, 1 private memory
inline bool prt_bg() {
	static const bool v = env_digit("BC5_GUARD_PRT_BG", 1) == 1 && rule() != 0;
	return v;
}
inline int learn_log() {
	static const int v = env_digit("BC5_GUARD_LEARN_LOG", 2);
	return v;
}
// Is [lo, hi) wholly inside the background span? (scratch_fill's question; a piece that straddles an end is left to it.)
inline bool in_bg(uint64_t lo, uint64_t hi) { return lo >= kBgLo && hi <= kBgHi && lo < hi; }
// The chunks of the file a view [off, off + size) touches, as the eager loop walks them.
inline void view_chunks(uint64_t off, uint64_t size, uint64_t chunk, std::vector<uint64_t>& out) {
	if (size == 0) return;
	for (uint64_t c = off & ~(chunk - 1); c < off + size; c += chunk) out.push_back(c);
}
// What lay at a faulting address, for the catcher's line. The order is the order of the questions that matter:
// was it a guest address at all, did the guest have a range there, did we hold its memory, had the GPU a mapping.
inline const char* classify(bool junk_bits, bool guest_range, bool under_view, bool view_lazy, bool view_eager, bool chunk_imported, bool gpu_mapped) {
	if (junk_bits) return "K4 junk address (a bit above 40 set)";
	if (!guest_range && !under_view) return "K3 no guest range (a hole)";
	if (under_view && !chunk_imported) return view_lazy ? "K1 under a LAZY view, chunk not imported" : (view_eager ? "K1 under an EAGER view, chunk not imported (import failed or late)" : "K1 under a BY-DATA view, chunk never written by the CPU");
	if (under_view && !gpu_mapped) return "K5 imported but not GPU-mapped at the fault (timing or a dropped mapping)";
	if (under_view) return "K6 imported and GPU-mapped (a protection fault or a stale report)";
	return gpu_mapped ? "K6 guest range outside direct memory, GPU-mapped" : "K2 guest range outside direct memory (anonymous), not GPU-mapped";
}
} // namespace mr412
