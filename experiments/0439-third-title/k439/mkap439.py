#!/usr/bin/env python3
# BC5 exp 0439 (tag ap439): the APR result written BEFORE the submission is marked done (src/libs/libAmpr.cpp of
# patch 0001, FinishAprSubmission). The candidate cause of run fp2211's CPU crash (README item 50; exp 0441's decode:
# the title's file worker lost r12 to a zeroed saved-register slot while only host code ran).
#   Before: FinishAprSubmission called SetSubmissionResult (done = true, g_submission_cv.notify_all, which releases the
#   title's WaitCommandBufferCompletion) and only then WriteResult(b.result_ptr, result, offset), 8 bytes, zeros on
#   success. A title that waits and then leaves the frame holding its result struct can have that late write land in
#   a stack frame used by then (once in two starts, timing). The console's order (TODO(verify): AnyPS5 Apr.cpp's
#   _submitGuest completion writes the result before it signals) is the result first, then the completion.
#   KYTY_BC5_APR_RESULT_ORDER=0 gives the old order; anything else the new one.
#   Accounting (normal build only): one line at the first and every 1024th result written before a signal that the
#   old order would have written after it. exp 0441 (11-22): the title's one SubmitCommandBufferAndGetResult call
#   (eboot+0xc36a11, its file reads) passes a stack-local result, waits with WaitCommandBuffer, reads the result and
#   leaves; the result local is the slot where a later host call saved r12 (fp2211's crash).
# Usage: python mkap439.py IN.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert '\r' not in s and 'ap439' not in s


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''	if (b.submission_id != 0) {
		AprShared::SetSubmissionResult(b.submission_id, result, offset);
	}
	if (b.result_ptr != 0) {
		(void)AprShared::WriteResult(reinterpret_cast<void*>(b.result_ptr), result, offset);
	}
''', '''	static const bool ap439 = [] { // exp 0439 (tag ap439): the result before the completion
		const char* e = std::getenv("KYTY_BC5_APR_RESULT_ORDER");
		const bool  v = !(e != nullptr && std::strcmp(e, "0") == 0);
#ifndef BC5_LEAN
		std::fprintf(stderr, "[bc5] exp 0439 (tag ap439): KYTY_BC5_APR_RESULT_ORDER=%d\\n", v ? 1 : 0);
#endif
		return v;
	}();
	if (ap439 && b.result_ptr != 0) {
		(void)AprShared::WriteResult(reinterpret_cast<void*>(b.result_ptr), result, offset);
#ifndef BC5_LEAN
		if (b.submission_id != 0) { // the fix's accounting: a result that the old order wrote after the waiter's release
			static std::atomic<uint64_t> n_early {0};
			const uint64_t               k = ++n_early;
			if (k == 1 || (k & 0x3ffu) == 0) std::fprintf(stderr, "[bc5] exp 0439 (tag ap439): %" PRIu64 " APR results written before their completion signal (the old order wrote them after it)\\n", k);
		}
#endif
	}
	if (b.submission_id != 0) {
		AprShared::SetSubmissionResult(b.submission_id, result, offset);
	}
	if (!ap439 && b.result_ptr != 0) { // the old order
		(void)AprShared::WriteResult(reinterpret_cast<void*>(b.result_ptr), result, offset);
	}
''')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkap439: wrote', dst)
