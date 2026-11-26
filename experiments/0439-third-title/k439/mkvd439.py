#!/usr/bin/env python3
# BC5 exp 0439 (tag vd439): libSceVideodec2's memory answers sized from the stream, not a flat 16 MiB (README item 53;
# exp 0441's decode of the third title's movie player). The host (src/libs/libVideoDec2.cpp, FFmpeg in
# videoDec2Decoder.cpp) answered VIDEODEC2_MIN_MEMORY_SIZE = 16 MiB for every size and rejected anything smaller. The
# title sizes its movie pool's frame slots from max_frame_buffer_size: 72 MiB - 16 (compute) - 16 (cpu_gpu) leaves 2
# slots of 16 MiB where it needs at least 4, so the decoder is never created and the movie shows black with its sound.
#   KYTY_BC5_VD2_SIZES (on unless "0"):
#   - max_frame_buffer_size = the frame our decoder writes (NV12: pitch = max width rounded up to 256, luma pitch x max
#     height, chroma pitch x ceil(height / 2), as videoDec2Decoder.cpp lays it out) rounded up to 256, plus 0x4000. The
#     way the size is formed (the frame size rounded, plus a fixed tail) is the fact shadPS4 implements for the console's
#     answer (shadPS4, GPL-2.0-or-later, src/core/libraries/videodec/videodec2.cpp); this is our own code.
#   - cpu, gpu, cpu_gpu and the compute queue's cpu_gpu memory: 1 MiB each. Our decoder runs on the host CPU (FFmpeg)
#     and never touches these guest areas; the console's decoder needs them for its hardware state. TODO(verify) the
#     console's values. Smaller than before, never larger, so a title that sized its pool from the old answers still
#     fits.
#   - CreateDecoder / AllocateComputeQueue accept any size at least the new answers (was: at least 16 MiB each).
#   One trace line per call (the first 8 of each, then every 1024th) in the normal build, compiled out in lean.
# Usage: python mkvd439.py IN.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert 'vd439' not in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


rep('''constexpr size_t   VIDEODEC2_MIN_MEMORY_SIZE       = 16ull * 1024ull * 1024ull;
''', '''constexpr size_t   VIDEODEC2_MIN_MEMORY_SIZE       = 16ull * 1024ull * 1024ull;
// exp 0439 (tag vd439, KYTY_BC5_VD2_SIZES, on unless "0"): the answers sized from the stream (see Vd439FrameSize)
static bool Vd439On() {
	static const bool v = [] {
		const char* e = std::getenv("KYTY_BC5_VD2_SIZES");
		return !(e != nullptr && e[0] == '0' && e[1] == 0);
	}();
	return v;
}
constexpr size_t VD439_SMALL = 1ull * 1024ull * 1024ull; // cpu / gpu / cpu_gpu / compute: our decoder never uses them
static size_t    Vd439Min() { return Vd439On() ? VD439_SMALL : VIDEODEC2_MIN_MEMORY_SIZE; }
// The NV12 frame videoDec2Decoder.cpp writes: pitch = width rounded up to 256, luma pitch x height, chroma pitch x
// ceil(height / 2); rounded up to 256 and a 0x4000 tail (the form of the console's answer as shadPS4 implements it).
static size_t Vd439FrameSize(int32_t w, int32_t h) {
	const uint64_t pitch = (static_cast<uint64_t>(w > 0 ? w : 0) + 255u) & ~255ull;
	const uint64_t hh    = static_cast<uint64_t>(h > 0 ? h : 0);
	const uint64_t bytes = pitch * hh + pitch * ((hh + 1u) / 2u);
	return static_cast<size_t>(((bytes + 255u) & ~255ull) + 0x4000u);
}
static void Vd439Trace(const char* what, int32_t rc, size_t a = 0, size_t b = 0) {
#ifndef BC5_LEAN
	static std::atomic<uint64_t> n {0};
	const uint64_t               k = n++;
	if (k < 32 || (k & 0x3ffu) == 0)
		std::fprintf(stderr, "[bc5] exp 0439 (tag vd439): %s rc 0x%08x (%zu, %zu) (call %llu)\\n", what, static_cast<uint32_t>(rc), a, b, static_cast<unsigned long long>(k));
#else
	(void)what, (void)rc, (void)a, (void)b;
#endif
}
''')
# QueryComputeMemoryInfo
rep('''	compute_memory_info->cpu_gpu_memory_size = VIDEODEC2_MIN_MEMORY_SIZE;
	compute_memory_info->cpu_gpu_memory      = nullptr;

	return OK;''', '''	compute_memory_info->cpu_gpu_memory_size = Vd439Min();
	compute_memory_info->cpu_gpu_memory      = nullptr;

	Vd439Trace("QueryComputeMemoryInfo", OK, compute_memory_info->cpu_gpu_memory_size);
	return OK;''')
rep('''	if (compute_memory_info->cpu_gpu_memory_size < VIDEODEC2_MIN_MEMORY_SIZE) {
		return VIDEODEC2_ERROR_MEMORY_SIZE;
	}''', '''	if (compute_memory_info->cpu_gpu_memory_size < Vd439Min()) {
		Vd439Trace("AllocateComputeQueue", VIDEODEC2_ERROR_MEMORY_SIZE, compute_memory_info->cpu_gpu_memory_size);
		return VIDEODEC2_ERROR_MEMORY_SIZE;
	}''')
# QueryDecoderMemoryInfo
rep('''	memory_info->cpu_memory_size        = VIDEODEC2_MIN_MEMORY_SIZE;
	memory_info->cpu_memory             = nullptr;
	memory_info->gpu_memory_size        = VIDEODEC2_MIN_MEMORY_SIZE;
	memory_info->gpu_memory             = nullptr;
	memory_info->cpu_gpu_memory_size    = VIDEODEC2_MIN_MEMORY_SIZE;
	memory_info->cpu_gpu_memory         = nullptr;
	memory_info->max_frame_buffer_size  = VIDEODEC2_MIN_MEMORY_SIZE;
	memory_info->frame_buffer_alignment = 0x100;
	memory_info->reserved0              = 0;

	return OK;''', '''	memory_info->cpu_memory_size        = Vd439Min();
	memory_info->cpu_memory             = nullptr;
	memory_info->gpu_memory_size        = Vd439Min();
	memory_info->gpu_memory             = nullptr;
	memory_info->cpu_gpu_memory_size    = Vd439Min();
	memory_info->cpu_gpu_memory         = nullptr;
	memory_info->max_frame_buffer_size  = Vd439On() ? std::min(VIDEODEC2_MIN_MEMORY_SIZE, Vd439FrameSize(config->max_frame_width, config->max_frame_height)) : VIDEODEC2_MIN_MEMORY_SIZE;
	memory_info->frame_buffer_alignment = 0x100;
	memory_info->reserved0              = 0;

	Vd439Trace("QueryDecoderMemoryInfo", OK, static_cast<size_t>(config->max_frame_width) << 16u | static_cast<size_t>(config->max_frame_height), memory_info->max_frame_buffer_size);
	return OK;''')
# CreateDecoder
rep('''	if (memory_info->cpu_memory_size < VIDEODEC2_MIN_MEMORY_SIZE ||
	    memory_info->gpu_memory_size < VIDEODEC2_MIN_MEMORY_SIZE ||
	    memory_info->cpu_gpu_memory_size < VIDEODEC2_MIN_MEMORY_SIZE ||
	    memory_info->max_frame_buffer_size < VIDEODEC2_MIN_MEMORY_SIZE) {
		return VIDEODEC2_ERROR_MEMORY_SIZE;
	}''', '''	if (memory_info->cpu_memory_size < Vd439Min() || memory_info->gpu_memory_size < Vd439Min() ||
	    memory_info->cpu_gpu_memory_size < Vd439Min() ||
	    memory_info->max_frame_buffer_size < (Vd439On() ? std::min(VIDEODEC2_MIN_MEMORY_SIZE, Vd439FrameSize(config->max_frame_width, config->max_frame_height)) : VIDEODEC2_MIN_MEMORY_SIZE)) {
		Vd439Trace("CreateDecoder", VIDEODEC2_ERROR_MEMORY_SIZE, memory_info->max_frame_buffer_size, memory_info->cpu_gpu_memory_size);
		return VIDEODEC2_ERROR_MEMORY_SIZE;
	}''')
rep('''	*decoder = state;
	return OK;''', '''	*decoder = state;
	Vd439Trace("CreateDecoder", OK, static_cast<size_t>(config->max_frame_width) << 16u | static_cast<size_t>(config->max_frame_height), memory_info->max_frame_buffer_size);
	return OK;''')
# Decode and Flush results
rep('''	                    {frame_buffer->frame_buffer, frame_buffer->frame_buffer_size}, &decoded);
	ApplyDecodedOutput(decoded, frame_buffer, output_info);
	return MapDecoderResult(result);''', '''	                    {frame_buffer->frame_buffer, frame_buffer->frame_buffer_size}, &decoded);
	ApplyDecodedOutput(decoded, frame_buffer, output_info);
	Vd439Trace(output_info->is_valid ? "Decode: a picture" : "Decode: no picture", MapDecoderResult(result), frame_buffer->frame_buffer_size, input_data->au_size);
	return MapDecoderResult(result);''')
rep('''	    state, {frame_buffer->frame_buffer, frame_buffer->frame_buffer_size}, &decoded);
	ApplyDecodedOutput(decoded, frame_buffer, output_info);
	return MapDecoderResult(result);''', '''	    state, {frame_buffer->frame_buffer, frame_buffer->frame_buffer_size}, &decoded);
	ApplyDecodedOutput(decoded, frame_buffer, output_info);
	Vd439Trace(output_info->is_valid ? "Flush: a picture" : "Flush: no picture", MapDecoderResult(result), frame_buffer->frame_buffer_size);
	return MapDecoderResult(result);''')
if '#include <atomic>' not in s:
    i = s.index('#include')
    s = s[:i] + '#include <algorithm> // exp 0439 (tag vd439)\n#include <atomic>    // exp 0439 (tag vd439)\n#include <cstdio>    // exp 0439 (tag vd439)\n#include <cstdlib>   // exp 0439 (tag vd439)\n' + s[i:]
if crlf:
    s = s.replace('\n', '\r\n')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkvd439: wrote', dst)
