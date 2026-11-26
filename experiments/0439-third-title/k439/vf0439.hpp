// SPDX-License-Identifier: GPL-2.0-only
// BC5 exp 0439 (tag vf439, 11-22 night, the top session's order after the intro-movie noise of the maintainer's run on a
// fresh boot): every byte of the title's decode slot written. videoDec2Decoder.cpp CopyFrame writes an NV12 frame of
// pitch = width rounded to 256: luma pitch x height, chroma pitch x ceil(height / 2) right after it, after zeroing that
// span. Left as it was: the slot's tail after the chroma (the slot is sized from the stream, vd439: 40,960 bytes for
// 1920x1080, 20 rows of the pitch), never written, so a title that samples past the chroma (an aligned height, 1088)
// reads whatever the memory held. pad() makes the padding columns and the tail neutral: luma 0x10 (black in limited
// range), chroma 0x80 (no colour), after the planes are written, so nothing in the slot is left from before.
// Note: CopyFrame already wrote every byte of luma and chroma rows; a whole-frame colour noise with an intact luma is NOT
// explained by this (see the exp 0439 README's movie-noise item); pad() closes the only unwritten bytes.
// Det-tested by test_vf0439.cpp (a slot pre-filled with 0xA5: none may remain).
#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace bc5::vf439 {

inline void pad(uint8_t* dst, size_t size, uint32_t width, uint32_t height, uint32_t pitch) {
	if (dst == nullptr || pitch == 0 || width > pitch) return;
	const uint64_t chroma_rows = (static_cast<uint64_t>(height) + 1u) / 2u;
	const uint64_t luma_end    = static_cast<uint64_t>(pitch) * height;
	const uint64_t end         = luma_end + static_cast<uint64_t>(pitch) * chroma_rows;
	if (end > size) return;
	if (width < pitch) {
		for (uint32_t y = 0; y < height; y++) std::memset(dst + static_cast<size_t>(y) * pitch + width, 0x10, pitch - width);
		for (uint64_t y = 0; y < chroma_rows; y++) std::memset(dst + luma_end + y * pitch + width, 0x80, pitch - width);
	}
	if (end < size) std::memset(dst + end, 0x80, size - static_cast<size_t>(end));
}

} // namespace bc5::vf439
