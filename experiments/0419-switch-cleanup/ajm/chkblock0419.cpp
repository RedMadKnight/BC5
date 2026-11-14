// BC5 experiment 0419 (ajt): a laptop compile of the block mkajm0419.py puts into ajm.cpp, against stand-ins for the
// few names of ajm.cpp it uses (ajm.cpp itself needs the ffmpeg headers and cannot be compiled here). The block is cut
// out of the generated ajm.cpp between its two marker lines into block.inc by the command below.
//   sed -n '/^\/\/ ---- BC5 experiment 0419, tag ajt/,/^\/\/ ---- end of ajt/p' <tree>/src/libs/ajm.cpp > block.inc
//   clang++ -fsyntax-only -std=c++20 -Wall -Wextra -Werror -I. -I<tree>/src chkblock0419.cpp
#include "bc5/ajm_trail.hpp"
#include "bc5/env_rule.hpp"

#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <unordered_map>

namespace Common::Thread {
inline int GetThreadIdUnique() {
	return 1;
}
} // namespace Common::Thread
namespace Libs {
namespace LibKernel {
inline uint64_t KernelGetProcessTime() {
	return 0;
}
} // namespace LibKernel
namespace Audio::Ajm {
constexpr int OK = 0;
struct AjmBatchInfo {
	void*       buffer;
	size_t      offset;
	size_t      size;
	void*       last_good_job;
	const void* last_good_job_ra;
};
struct AjmDecodeResult {
	int32_t  result          = OK;
	int32_t  internal_result = OK;
	size_t   input_consumed  = 0;
	size_t   output_written  = 0;
	uint32_t frames          = 0;
};
#include "block.inc"
static int AjmAppendJob(AjmBatchInfo* info, size_t job_size, const char*) {
	info->offset += job_size;
	return OK;
}
// every static of the block used once, as ajm.cpp uses them
inline int Use(AjmBatchInfo* info) {
	Bc5AjmCreated(1, 0);
	Bc5AjmDestroyed(1, true);
	Bc5AjmMissing(1);
	(void)Bc5AjmLiveIdsOn();
	return Bc5AjmJob(info, 64, "decode", [] {});
}
} // namespace Audio::Ajm
} // namespace Libs
