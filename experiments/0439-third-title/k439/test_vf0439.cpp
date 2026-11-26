// BC5 exp 0439 (tag vf439): det test of vf0439.hpp. A slot pre-filled with 0xA5, written as CopyFrame writes it (the
// span zeroed, luma and chroma rows copied, width bytes each), then pad(): no 0xA5 may remain anywhere in the slot.
//   clang++ -std=c++20 -Wall -Wextra -Werror -o test_vf0439 test_vf0439.cpp && ./test_vf0439
#include "vf0439.hpp"

#include <cstdio>
#include <vector>

static int run(uint32_t w, uint32_t h, size_t slot) {
	const uint32_t pitch = (w + 255u) & ~255u, chroma_rows = (h + 1u) / 2u;
	std::vector<uint8_t> s(slot, 0xA5);
	const size_t req = static_cast<size_t>(pitch) * h + static_cast<size_t>(pitch) * chroma_rows;
	if (req > slot) return 1;
	std::memset(s.data(), 0, req); // CopyFrame
	for (uint32_t y = 0; y < h; y++) std::memset(s.data() + static_cast<size_t>(y) * pitch, 0x40, w);
	for (uint32_t y = 0; y < chroma_rows; y++) std::memset(s.data() + static_cast<size_t>(pitch) * h + static_cast<size_t>(y) * pitch, 0x70, w);
	bc5::vf439::pad(s.data(), s.size(), w, h, pitch);
	size_t left = 0, bad_luma = 0, bad_chroma = 0;
	for (size_t i = 0; i < s.size(); i++) left += s[i] == 0xA5;
	for (uint32_t y = 0; y < h; y++) {
		bad_luma += s[static_cast<size_t>(y) * pitch + (w - 1)] != 0x40;           // data kept
		bad_luma += w < pitch && s[static_cast<size_t>(y) * pitch + w] != 0x10;     // padding black
	}
	for (uint32_t y = 0; y < chroma_rows; y++) {
		const size_t r = static_cast<size_t>(pitch) * h + static_cast<size_t>(y) * pitch;
		bad_chroma += s[r] != 0x70 || (w < pitch && s[r + pitch - 1] != 0x80);
	}
	const bool tail = req == slot || s[req] == 0x80;
	std::printf("  %ux%u slot %zu: 0xA5 left %zu, luma %zu, chroma %zu, tail %s\n", w, h, slot, left, bad_luma, bad_chroma, tail ? "neutral" : "WRONG");
	return (left == 0 && bad_luma == 0 && bad_chroma == 0 && tail) ? 0 : 1;
}

int main() {
	int f = 0;
	f += run(1920, 1080, 3358720); // the third title's slot (vd439)
	f += run(1920, 1080, 2048 * 1620); // no tail
	f += run(1280, 720, 1 << 21);
	f += run(2048, 1081, 2048 * 1622); // odd height, no padding columns
	std::vector<uint8_t> small(100, 0xA5); // a slot too small: untouched
	bc5::vf439::pad(small.data(), small.size(), 1920, 1080, 2048);
	f += small[0] != 0xA5;
	std::printf("test_vf0439: %s (%d failed)\n", f == 0 ? "PASS" : "FAIL", f);
	return f == 0 ? 0 : 1;
}
