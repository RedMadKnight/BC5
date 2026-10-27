#!/usr/bin/perl
# BC5 experiment 0343: the soft CP's label polls made visible and, in a replay, bounded (src/libs/bc5LleAgc.cpp in
# ~/src/KytyPlus, the host tree of patch 0001 as main has it after exp 0342). Exp 0341's 22-s hold (F415) was eleven
# WAIT_REG_MEM polls of SoftCp::wait_reg_mem running to their 2-s deadline inside the soft-CP replays on the game thread's
# completion queue (bc5-cq0), while drain() held the game thread at the flip; the timeout line was an LOGF, silent under
# --printf-direction Silent, so nothing recorded it. Seven edits, each on an anchor that must occur exactly once:
#   E1  Direct's forward block: timing_now() declared for the soft CP's lines
#   E2  SoftCp: the poll bound of this thread (t_wait_bound_ns), the buffer being executed (t_cur_*), the counters
#   E3  SoftCp::soft_wait_done(): a poll not satisfied at the first look is counted and, over 50 ms or timed out,
#       journaled through Direct::journal (label, function, reference, value, buffer kind / pointer / offset, marks empty
#       or set); wait_reg_mem() takes its deadline from the thread's bound and calls it
#   E4  SoftCp::submit(): names the buffer for the lines
#   E5  completion_thread(): a replay on cq0 polls with BC5_DIRECT_SOFT_WAIT_MS (default 8 ms; 0 keeps 2 s), on cq1
#       with BC5_DIRECT_SOFT_WAIT_RING_MS (default 0: unchanged); a post over 100 ms is journaled ("slow post")
#   E6  the frame profile line: ", waits polled N (x ms, M timed out)" after "soft-CP passes"
# usage: patch0343.pl <src root of the tree>   (perl on the box or the laptop; LF, tab-indented; idempotence refused)
use strict;
use warnings;

my $root = shift or die "usage: patch0343.pl <src root>\n";
my $f = "$root/src/libs/bc5LleAgc.cpp";
open my $in, '<', $f or die "$f: $!\n";
my $s = do { local $/; <$in> };
close $in;
die "$f already carries experiment 0343\n" if $s =~ /experiment 0343/;

my $edits = 0;
sub rep {
	my ($old, $new, $what) = @_;
	my $n = () = $s =~ /\Q$old\E/g;
	die "$what: the anchor occurs $n times, expected once: nothing written\n" unless $n == 1;
	my $at = index($s, $old);
	substr($s, $at, length $old) = $new;
	$edits++;
}

# ---- E1: timing_now() for the soft CP (defined in Direct after SoftCp; both are compiled whatever the build)
rep(<<'OLD', <<'NEW', 'E1 forward block');
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
// Experiment 0024 (BC5_DIRECT_ASYNC=1): what has to follow a buffer's execution on the GPU — the
OLD
static void journal(const char* fmt, ...) __attribute__((format(printf, 1, 2)));
static double timing_now(); // experiment 0343: the journal's time base, for the soft CP's lines
// Experiment 0024 (BC5_DIRECT_ASYNC=1): what has to follow a buffer's execution on the GPU — the
NEW

# ---- E2: the thread's bound, the buffer being executed, the counters
rep(<<'OLD', <<'NEW', 'E2 SoftCp state');
static std::atomic<uint64_t>        g_waits_timed_out {0};
OLD
static std::atomic<uint64_t>        g_waits_timed_out {0};
// Experiment 0343: the soft CP's label polls journaled and, in a replay, bounded. t_wait_bound_ns is
// the deadline of a WAIT_REG_MEM poll on this thread (0: the 2-s deadline of the standalone soft CP
// and of the ring thread's own pass; the completion threads set BC5_DIRECT_SOFT_WAIT_MS around the
// replays they run). t_cur_* name the buffer submit() is executing, for the lines. The counters feed
// the frame profile (polls not satisfied at the first look, their time, those that ran to the deadline).
static thread_local uint64_t        t_wait_bound_ns = 0;
static thread_local const uint32_t* t_cur_buf  = nullptr;
static thread_local uint32_t        t_cur_n    = 0;
static thread_local const char*     t_cur_kind = "?";
static std::atomic<uint64_t>        g_soft_polls {0}, g_soft_poll_ns {0}, g_soft_timeouts {0}, g_soft_lines {0};
NEW

# ---- E3: the poll's record, and wait_reg_mem() on the thread's bound
rep(<<'OLD', <<'NEW', 'E3a soft_wait_done');
static void wait_reg_mem(const uint32_t* p, bool is64) {
OLD
// Experiment 0343: a poll that was not satisfied at the first look. Counted for the frame profile;
// journaled through Direct::journal (which the session's printf direction does not silence) when it
// lasted over 50 ms or ran to its deadline: the label, function, reference and value, the buffer
// (kind, pointer; the packet's offset in it, or its address when it lies in an INDIRECT_BUFFER target)
// and whether the marks were empty (then every packet counts as not run by the GPU). Exp 0341's 22-s
// hold (F415) was eleven such polls at 2 s each inside bc5-cq0's replays, with no line anywhere.
static void soft_wait_done(const uint32_t* p, bool is64, uint64_t a, uint32_t function, uint64_t t0, bool timed_out) {
	const uint64_t held = now_ns() - t0;
	g_soft_polls++;
	g_soft_poll_ns += held;
	if (timed_out) g_soft_timeouts++;
	if (held < 50'000'000ull && !timed_out) return;
	if (g_soft_lines++ >= 2000) return; // the counters go on, the lines stop
	const uint64_t  ref   = is64 ? (p[4] | (static_cast<uint64_t>(p[5]) << 32u)) : p[4];
	const uint64_t  value = is64 ? *reinterpret_cast<volatile uint64_t*>(a) : *reinterpret_cast<volatile uint32_t*>(a);
	const bool      in    = t_cur_buf != nullptr && p >= t_cur_buf && p < t_cur_buf + t_cur_n;
	const long long where = in ? static_cast<long long>(p - t_cur_buf) : -1;
	Direct::journal("soft-cp wait: t %.3f s WAIT_REG_MEM%s on 0x%" PRIx64 " %s after %.1f ms (bound %" PRIu64 " ms): fn %u ref 0x%" PRIx64 " value 0x%" PRIx64 "; %s %u dwords at %p, packet at %p (offset %lld); marks %s\n",
	                Direct::timing_now(), is64 ? "64" : "", a, timed_out ? "TIMED OUT" : "satisfied", static_cast<double>(held) / 1e6,
	                (t_wait_bound_ns != 0 ? t_wait_bound_ns : 2'000'000'000ull) / 1'000'000ull, function, ref, value, t_cur_kind, t_cur_n,
	                static_cast<const void*>(t_cur_buf), static_cast<const void*>(p), where, t_gpu_done.empty() ? "empty" : "set");
}

static void wait_reg_mem(const uint32_t* p, bool is64) {
NEW

rep(<<'OLD', <<'NEW', 'E3b deadline');
	const uint64_t deadline = now_ns() + 2'000'000'000ull;
	for (;;) {
OLD
	const uint64_t t0       = now_ns();
	const uint64_t deadline = t0 + (t_wait_bound_ns != 0 ? t_wait_bound_ns : 2'000'000'000ull); // experiment 0343
	bool           polled   = false; // experiment 0343: not satisfied at the first look
	for (;;) {
NEW

rep(<<'OLD', <<'NEW', 'E3c satisfied / timed out');
		if (ok) {
			return;
		}
		if (now_ns() > deadline) {
			g_waits_timed_out++;
OLD
		if (ok) {
			if (polled) soft_wait_done(p, is64, a, function, t0, false); // experiment 0343
			return;
		}
		polled = true;
		if (now_ns() > deadline) {
			g_waits_timed_out++;
			soft_wait_done(p, is64, a, function, t0, true); // experiment 0343
NEW

# ---- E4: the buffer's name for the lines (and for the completion thread's slow-post line)
rep(<<'OLD', <<'NEW', 'E4 submit');
	const uint64_t n = g_submits.fetch_add(1);
	execute(buf, num_dwords, 0);
OLD
	const uint64_t n = g_submits.fetch_add(1);
	t_cur_buf  = buf; // experiment 0343: for the soft-cp wait lines
	t_cur_n    = num_dwords;
	t_cur_kind = kind;
	execute(buf, num_dwords, 0);
NEW

# ---- E5: the replays' bound and the slow-post line
rep(<<'OLD', <<'NEW', 'E5a soft_wait_ns');
static void completion_thread(int index) {
OLD
// Experiment 0343: the bound of a WAIT_REG_MEM poll inside a replay run by the game thread's completion
// queue (BC5_DIRECT_SOFT_WAIT_MS, default 8, like the game thread's DCB waits; 0 keeps the soft CP's
// 2-s deadline) and by the ring thread's (BC5_DIRECT_SOFT_WAIT_RING_MS, default 0: unchanged — a compute
// buffer may legitimately end in a wait for the next frame's label there, run 110). A replay runs after
// the job's fence: a label still unwritten then can only be written by work the title has not submitted,
// and while drain() holds the game thread at the flip that work cannot come (exp 0341's 22-s hold, F415:
// eleven polls at 2 s). The packets after the wait run as before, only sooner.
static uint64_t soft_wait_ns() {
	static const uint64_t v = (std::getenv("BC5_DIRECT_SOFT_WAIT_MS") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_SOFT_WAIT_MS"), nullptr, 10) : 8ull) * 1'000'000ull;
	return v;
}
static uint64_t soft_wait_ring_ns() {
	static const uint64_t v = (std::getenv("BC5_DIRECT_SOFT_WAIT_RING_MS") != nullptr ? std::strtoull(std::getenv("BC5_DIRECT_SOFT_WAIT_RING_MS"), nullptr, 10) : 0ull) * 1'000'000ull;
	return v;
}
static void completion_thread(int index) {
NEW

rep(<<'OLD', <<'NEW', 'E5b post');
			const uint64_t t_post = SoftCp::now_ns();
			it.post(failed);
			if (index == 0) frame_profile_post(static_cast<double>(SoftCp::now_ns() - t_post) / 1e6);
OLD
			const uint64_t t_post = SoftCp::now_ns();
			SoftCp::t_wait_bound_ns = index == 0 ? soft_wait_ns() : soft_wait_ring_ns(); // experiment 0343
			it.post(failed);
			SoftCp::t_wait_bound_ns = 0;
			const double post_ms = static_cast<double>(SoftCp::now_ns() - t_post) / 1e6;
			if (index == 0) frame_profile_post(post_ms);
			if (post_ms >= 100.0) { // experiment 0343: exp 0341's hold was posts of 2 s on cq0, with no line
				static std::atomic<uint32_t> n_slow {0};
				if (n_slow++ < 1000) journal("slow post: t %.3f s cq%d %.1f ms; last replayed %s %u dwords at %p; soft-cp polls so far %" PRIu64 " (%.1f ms), timed out %" PRIu64 "\n",
				                             timing_now(), index, post_ms, SoftCp::t_cur_kind, SoftCp::t_cur_n, static_cast<const void*>(SoftCp::t_cur_buf),
				                             SoftCp::g_soft_polls.load(), static_cast<double>(SoftCp::g_soft_poll_ns.load()) / 1e6, SoftCp::g_soft_timeouts.load());
			}
NEW

# ---- E6: the frame profile line
rep(<<'OLD', <<'NEW', 'E6a counters at the flip');
	const double now = timing_now();
	if (g_fp.t_last_flip != 0) {
		const double interval = (now - g_fp.t_last_flip) * 1e3;
OLD
	const double now = timing_now();
	// Experiment 0343: the soft CP's polls since the last flip (its counters are global: both completion threads and
	// the ring thread's own pass; the lines say which).
	static uint64_t sp0 = 0, st0 = 0, sn0 = 0;
	const uint64_t  sp = SoftCp::g_soft_polls.load(), st = SoftCp::g_soft_timeouts.load(), sn = SoftCp::g_soft_poll_ns.load();
	if (g_fp.t_last_flip != 0) {
		const double interval = (now - g_fp.t_last_flip) * 1e3;
NEW

rep('; soft-CP passes %.1f ms in %" PRIu64 "; prepare = filter', '; soft-CP passes %.1f ms in %" PRIu64 ", waits polled %" PRIu64 " (%.1f ms, %" PRIu64 " timed out); prepare = filter', 'E6b format');
rep('g_fp.post_ms, g_fp.posts, g_fp.pf_ms,', 'g_fp.post_ms, g_fp.posts, sp - sp0, static_cast<double>(sn - sn0) / 1e6, st - st0, g_fp.pf_ms,', 'E6c arguments');
rep(<<'OLD', <<'NEW', 'E6d reset');
	g_fp.jobs = g_fp.ring_jobs = g_fp.gpu_busy_ns = g_fp.posts = 0;
OLD
	g_fp.jobs = g_fp.ring_jobs = g_fp.gpu_busy_ns = g_fp.posts = 0;
	sp0 = sp; // experiment 0343
	st0 = st;
	sn0 = sn;
NEW

open my $out, '>', $f or die "$f: $!\n";
print {$out} $s;
close $out or die "$f: $!\n";
my $marks = () = $s =~ /experiment 0343/g;
print "patched $f: $edits edits, $marks 'experiment 0343' marks\n";
