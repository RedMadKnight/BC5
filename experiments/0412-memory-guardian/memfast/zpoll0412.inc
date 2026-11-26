// BC5 experiment 0412 (tag zp412, README section 40 and its correction, section 45): the decision of the zero skip's
// poll before a submission. `seen` is the direct file's block count the last scan was started for; `sample` is the
// count read now, BEFORE any scan. A scan runs when they differ, and `seen` becomes that sample: never a count read
// after the scan or after the sync that follows it, because a write that lands between the scan and such a second
// read would be credited to `seen` without having been scanned, and the next submission would then skip its scan
// (the review of 2026-11-12, lesson R12: a sequence of reads is not a snapshot).
// The block count is a hint that something was written somewhere in the file; it is the scan that looks at the
// skipped chunks. A growth caused by the host's own pin after a scan costs one more scan at the next submission.
// This text is included by the main unit (through mkzpoll0412.py) and by the CPU test zpoll0412.cpp.
namespace zp412 {
inline bool look(uint64_t& seen, uint64_t sample) {
	if (sample == seen) return false;
	seen = sample;
	return true;
}
} // namespace zp412
