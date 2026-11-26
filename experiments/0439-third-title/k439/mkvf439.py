#!/usr/bin/env python3
# BC5 exp 0439 (tag vf439): the decode slot written whole (bc5/vf0439.hpp pad(): padding columns and the tail after the
# chroma neutral), for every title, KYTY_BC5_VD2_FILL on unless "0"; and (diagnosis builds only) one line per picture
# for the first 8 and every 256th: the slot's address, size, the span written and the source format, so the slot's
# mapping can be looked up against the GPU's view (the movie noise: a whole-frame colour noise with an intact luma).
# Usage: python mkvf439.py IN/videoDec2Decoder.cpp OUT.cpp (every anchor exactly once)
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, 'rb').read().decode('utf-8', 'surrogateescape')
assert 'vf439' not in s
crlf = '\r\n' in s
s = s.replace('\r\n', '\n')


def rep(a, b):
    global s
    assert s.count(a) == 1, (a[:70], s.count(a))
    s = s.replace(a, b)


INC = [ln for ln in s.split('\n') if ln.startswith('#include "libs/videoDec2Decoder.h"')]
assert len(INC) == 1, INC
rep(INC[0] + '\n', INC[0] + '\n#include "bc5/vf0439.hpp" // exp 0439 (tag vf439)\n#include <atomic>\n#include <cinttypes>\n#include <cstdio>\n#include <cstdlib>\n')
rep('''		output->valid           = true;
''', '''		{ // exp 0439 (tag vf439): the slot written whole (KYTY_BC5_VD2_FILL, on unless "0")
			static const bool fill = [] {
				const char* e = std::getenv("KYTY_BC5_VD2_FILL");
				return !(e != nullptr && e[0] == '0' && e[1] == 0);
			}();
			if (fill) bc5::vf439::pad(dst, frame_buffer.size, width, height, pitch);
#ifndef BC5_LEAN
			static std::atomic<uint64_t> n {0};
			const uint64_t               k = n++;
			if (k < 8 || (k & 255u) == 0)
				std::fprintf(stderr, "[bc5] exp 0439 (tag vf439): picture %" PRIu64 " slot %p size %zu: %ux%u pitch %u, span written %" PRIu64 " (luma %" PRIu64 "), source %s, tail %s\\n", k,
				             frame_buffer.data, frame_buffer.size, width, height, pitch, static_cast<uint64_t>(required), static_cast<uint64_t>(pitch) * height,
				             frame->format == AV_PIX_FMT_NV12 ? "NV12" : "converted", fill ? "neutral" : "as it was");
#endif
		}
		output->valid           = true;
''')
if crlf:
    s = s.replace('\n', '\r\n')
open(dst, 'wb').write(s.encode('utf-8', 'surrogateescape'))
print('mkvf439: wrote', dst)
