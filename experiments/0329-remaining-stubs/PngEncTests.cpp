// BC5 experiment 0329: tests of the libScePngEnc unit (libPngEnc.cpp) — the validation order and the error codes of
// AnyPS5's Export.cpp, and the encoder's output decoded back with zlib and the PNG filters undone, pixel for pixel.
#include "common/abi.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include <zlib.h>

namespace Libs::PngEnc {
struct PngEncCreateParam {
	uint32_t this_size;
	uint32_t attribute;
	uint32_t max_image_width;
	uint32_t max_filter_number;
};
struct PngEncEncodeParam {
	const uint8_t* image_mem_addr;
	uint8_t*       png_mem_addr;
	uint32_t       image_mem_size;
	uint32_t       png_mem_size;
	uint32_t       image_width;
	uint32_t       image_height;
	uint32_t       image_pitch;
	uint16_t       pixel_format;
	uint16_t       color_space;
	uint16_t       bit_depth;
	uint16_t       clut_number;
	uint16_t       filter_type;
	uint16_t       compression_level;
};
struct PngEncOutputInfo {
	uint32_t data_size;
	uint32_t processed_height;
};
int KYTY_SYSV_ABI PngEncQueryMemorySize(const PngEncCreateParam* param);
int KYTY_SYSV_ABI PngEncCreate(const PngEncCreateParam* param, void* memory, uint32_t memory_size, void** handle);
int KYTY_SYSV_ABI PngEncDelete(void* handle);
int KYTY_SYSV_ABI PngEncEncode(void* handle, const PngEncEncodeParam* param, PngEncOutputInfo* output_info);
} // namespace Libs::PngEnc

using namespace Libs::PngEnc;

static int g_failed = 0;

static void Check(bool ok, const char* what) {
	if (!ok) {
		std::fprintf(stderr, "PngEncTests: FAILED: %s\n", what);
		g_failed++;
	}
}

constexpr int ERROR_INVALID_ADDR   = static_cast<int>(0x80690101u);
constexpr int ERROR_INVALID_SIZE   = static_cast<int>(0x80690102u);
constexpr int ERROR_INVALID_PARAM  = static_cast<int>(0x80690103u);
constexpr int ERROR_INVALID_HANDLE = static_cast<int>(0x80690104u);
constexpr int ERROR_DATA_OVERFLOW  = static_cast<int>(0x80690110u);

static uint32_t BigEndian32(const uint8_t* p) {
	return (static_cast<uint32_t>(p[0]) << 24) | (static_cast<uint32_t>(p[1]) << 16) |
	       (static_cast<uint32_t>(p[2]) << 8) | static_cast<uint32_t>(p[3]);
}

static uint8_t Paeth(int a, int b, int c) {
	const int p  = a + b - c;
	const int pa = std::abs(p - a);
	const int pb = std::abs(p - b);
	const int pc = std::abs(p - c);
	if (pa <= pb && pa <= pc) {
		return static_cast<uint8_t>(a);
	}
	if (pb <= pc) {
		return static_cast<uint8_t>(b);
	}
	return static_cast<uint8_t>(c);
}

// The PNG parsed: the signature, IHDR, every IDAT inflated, the rows unfiltered into pixels (channels per pixel).
// filters_seen collects the filter byte of each row. Returns false on a malformed file.
static bool DecodePng(const std::vector<uint8_t>& png, uint32_t* width, uint32_t* height, uint32_t* channels,
                      std::vector<uint8_t>* pixels, std::vector<uint8_t>* filters_seen) {
	static const uint8_t signature[8] = {0x89, 'P', 'N', 'G', 0x0d, 0x0a, 0x1a, 0x0a};
	if (png.size() < 8 + 25 || std::memcmp(png.data(), signature, 8) != 0) {
		return false;
	}
	std::vector<uint8_t> idat;
	size_t               at       = 8;
	bool                 ihdr     = false;
	bool                 iend     = false;
	while (at + 12 <= png.size()) {
		const uint32_t length = BigEndian32(&png[at]);
		const char*    type   = reinterpret_cast<const char*>(&png[at + 4]);
		if (at + 12 + length > png.size()) {
			return false;
		}
		const uint32_t crc = static_cast<uint32_t>(::crc32(0L, &png[at + 4], 4 + length));
		if (crc != BigEndian32(&png[at + 8 + length])) {
			std::fprintf(stderr, "PngEncTests: bad crc of chunk %.4s\n", type);
			return false;
		}
		if (std::memcmp(type, "IHDR", 4) == 0) {
			if (length != 13) {
				return false;
			}
			const uint8_t* d = &png[at + 8];
			*width           = BigEndian32(d);
			*height          = BigEndian32(d + 4);
			if (d[8] != 8 || d[10] != 0 || d[11] != 0 || d[12] != 0) {
				return false;
			}
			*channels = (d[9] == 6) ? 4 : (d[9] == 2) ? 3 : 0;
			ihdr      = true;
		} else if (std::memcmp(type, "IDAT", 4) == 0) {
			idat.insert(idat.end(), &png[at + 8], &png[at + 8] + length);
		} else if (std::memcmp(type, "IEND", 4) == 0) {
			iend = true;
		}
		at += 12 + length;
	}
	if (!ihdr || !iend || at != png.size() || *channels == 0) {
		return false;
	}
	const size_t         row_size = static_cast<size_t>(*width) * *channels;
	std::vector<uint8_t> raw((row_size + 1) * *height);
	uLongf               raw_size = static_cast<uLongf>(raw.size());
	if (::uncompress(raw.data(), &raw_size, idat.data(), static_cast<uLong>(idat.size())) != Z_OK ||
	    raw_size != raw.size()) {
		return false;
	}
	pixels->assign(row_size * *height, 0);
	filters_seen->clear();
	for (uint32_t y = 0; y < *height; y++) {
		const uint8_t* src  = raw.data() + (row_size + 1) * y;
		uint8_t*       dst  = pixels->data() + row_size * y;
		const uint8_t* prev = (y == 0) ? nullptr : dst - row_size;
		const uint8_t  type = src[0];
		filters_seen->push_back(type);
		for (size_t i = 0; i < row_size; i++) {
			const int a = (i >= *channels) ? dst[i - *channels] : 0;
			const int b = (prev != nullptr) ? prev[i] : 0;
			const int c = (prev != nullptr && i >= *channels) ? prev[i - *channels] : 0;
			const int x = src[1 + i];
			switch (type) {
				case 0: dst[i] = static_cast<uint8_t>(x); break;
				case 1: dst[i] = static_cast<uint8_t>(x + a); break;
				case 2: dst[i] = static_cast<uint8_t>(x + b); break;
				case 3: dst[i] = static_cast<uint8_t>(x + ((a + b) >> 1)); break;
				case 4: dst[i] = static_cast<uint8_t>(x + Paeth(a, b, c)); break;
				default: return false;
			}
		}
	}
	return true;
}

static void TestCreateAndDelete() {
	PngEncCreateParam bad_attr  = {16, 1, 64, 5};
	PngEncCreateParam bad_filt  = {16, 0, 64, 6};
	PngEncCreateParam bad_width = {16, 0, 0, 5};
	PngEncCreateParam good      = {16, 0, 64, 5};
	Check(PngEncQueryMemorySize(nullptr) == ERROR_INVALID_ADDR, "QueryMemorySize(null) is INVALID_ADDR");
	Check(PngEncQueryMemorySize(&bad_attr) == ERROR_INVALID_PARAM, "QueryMemorySize with an attribute is INVALID_PARAM");
	Check(PngEncQueryMemorySize(&bad_filt) == ERROR_INVALID_PARAM, "QueryMemorySize with 6 filters is INVALID_PARAM");
	Check(PngEncQueryMemorySize(&bad_width) == ERROR_INVALID_SIZE, "QueryMemorySize with width 0 is INVALID_SIZE");
	Check(PngEncQueryMemorySize(&good) == 16, "QueryMemorySize is the context's 16 bytes");

	alignas(8) uint8_t memory[16] = {};
	void*              handle     = nullptr;
	Check(PngEncCreate(&good, nullptr, 16, &handle) == ERROR_INVALID_ADDR, "Create without memory is INVALID_ADDR");
	Check(PngEncCreate(&good, memory, 16, nullptr) == ERROR_INVALID_ADDR, "Create without a handle is INVALID_ADDR");
	Check(PngEncCreate(&good, memory, 8, &handle) == ERROR_INVALID_SIZE, "Create with 8 bytes is INVALID_SIZE");
	Check(PngEncCreate(&good, memory, 16, &handle) == 0 && handle == memory, "Create returns the memory as the handle");
	Check(PngEncDelete(nullptr) == ERROR_INVALID_HANDLE, "Delete(null) is INVALID_HANDLE");
	Check(PngEncDelete(handle) == 0, "Delete succeeds");
	Check(PngEncDelete(handle) == ERROR_INVALID_HANDLE, "a deleted handle is INVALID_HANDLE");
	Check(PngEncEncode(handle, nullptr, nullptr) == ERROR_INVALID_HANDLE, "Encode on a deleted handle is INVALID_HANDLE");
}

static std::vector<uint8_t> Image(uint32_t width, uint32_t height, uint32_t pitch) {
	std::vector<uint8_t> image(static_cast<size_t>(pitch) * height);
	for (uint32_t y = 0; y < height; y++) {
		for (uint32_t x = 0; x < width; x++) {
			uint8_t* p = &image[static_cast<size_t>(y) * pitch + static_cast<size_t>(x) * 4];
			p[0]       = static_cast<uint8_t>(x * 37 + y * 11);
			p[1]       = static_cast<uint8_t>(x * 3 + y * 101);
			p[2]       = static_cast<uint8_t>(x * x + y);
			p[3]       = static_cast<uint8_t>(255 - x * 9);
		}
	}
	return image;
}

static void TestEncode() {
	PngEncCreateParam  create = {16, 0, 1024, 5};
	alignas(8) uint8_t memory[16];
	void*              handle = nullptr;
	Check(PngEncCreate(&create, memory, 16, &handle) == 0, "Create for the encode tests");

	const uint32_t       width = 37, height = 23, pitch = 37 * 4 + 12;
	std::vector<uint8_t> image = Image(width, height, pitch);
	std::vector<uint8_t> png(64 * 1024);

	PngEncEncodeParam param = {};
	param.image_mem_addr    = image.data();
	param.png_mem_addr      = png.data();
	param.image_mem_size    = static_cast<uint32_t>(image.size());
	param.png_mem_size      = static_cast<uint32_t>(png.size());
	param.image_width       = width;
	param.image_height      = height;
	param.image_pitch       = pitch;
	param.pixel_format      = 0;  // R8G8B8A8
	param.color_space       = 19; // RGBA
	param.bit_depth         = 8;
	param.clut_number       = 0;
	param.filter_type       = 15; // every filter
	param.compression_level = 6;

	// the validation
	{
		PngEncEncodeParam p = param;
		p.bit_depth         = 16;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_PARAM, "bit depth 16 is INVALID_PARAM");
		p           = param;
		p.color_space = 2;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_PARAM, "color space 2 is INVALID_PARAM");
		p                   = param;
		p.compression_level = 10;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_PARAM, "compression level 10 is INVALID_PARAM");
		p             = param;
		p.image_width = 0;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_SIZE, "width 0 is INVALID_SIZE");
		p             = param;
		p.image_width = 1025;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_SIZE, "a width over the context's is INVALID_SIZE");
		p             = param;
		p.image_pitch = width * 4 - 4;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_SIZE, "a pitch under the row is INVALID_SIZE");
		p                = param;
		p.image_mem_size = pitch * (height - 1) + width * 4 - 1;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_SIZE, "an image buffer one byte short is INVALID_SIZE");
		p                = param;
		p.image_mem_size = pitch * (height - 1) + width * 4;
		Check(PngEncEncode(handle, &p, nullptr) > 0, "an image buffer of exactly the rows is accepted");
		p              = param;
		p.png_mem_addr = nullptr;
		Check(PngEncEncode(handle, &p, nullptr) == ERROR_INVALID_ADDR, "no PNG buffer is INVALID_ADDR");
		Check(PngEncEncode(handle, nullptr, nullptr) == ERROR_INVALID_PARAM, "no parameters is INVALID_PARAM");
	}

	// RGBA, every filter: decoded back it is the image
	{
		PngEncOutputInfo info = {};
		const int        size = PngEncEncode(handle, &param, &info);
		Check(size > 0, "RGBA encode returns a size");
		Check(info.data_size == static_cast<uint32_t>(size) && info.processed_height == height, "output info filled");
		std::vector<uint8_t> file(png.begin(), png.begin() + size);
		uint32_t             w = 0, h = 0, ch = 0;
		std::vector<uint8_t> pixels, filters;
		Check(DecodePng(file, &w, &h, &ch, &pixels, &filters), "RGBA PNG parses and inflates");
		Check(w == width && h == height && ch == 4, "RGBA PNG header");
		bool same = (pixels.size() == static_cast<size_t>(width) * height * 4);
		for (uint32_t y = 0; same && y < height; y++) {
			same = std::memcmp(&pixels[static_cast<size_t>(y) * width * 4], &image[static_cast<size_t>(y) * pitch],
			                   width * 4) == 0;
		}
		Check(same, "RGBA pixels survive the round trip");
		bool filtered = false;
		for (auto f: filters) {
			filtered = filtered || (f != 0);
		}
		Check(filtered, "some row took a non-trivial filter");
	}

	// RGB from B8G8R8A8, the none filter only, level 0 (stored): the alpha dropped, the channels swapped back
	{
		PngEncEncodeParam p  = param;
		p.pixel_format       = 1;
		p.color_space        = 3;
		p.filter_type        = 0;
		p.compression_level  = 0;
		PngEncOutputInfo info = {};
		const int        size = PngEncEncode(handle, &p, &info);
		Check(size > 0, "RGB encode returns a size");
		std::vector<uint8_t> file(png.begin(), png.begin() + size);
		uint32_t             w = 0, h = 0, ch = 0;
		std::vector<uint8_t> pixels, filters;
		Check(DecodePng(file, &w, &h, &ch, &pixels, &filters), "RGB PNG parses and inflates");
		Check(w == width && h == height && ch == 3, "RGB PNG header");
		bool same = (pixels.size() == static_cast<size_t>(width) * height * 3);
		for (uint32_t y = 0; same && y < height; y++) {
			for (uint32_t x = 0; same && x < width; x++) {
				const uint8_t* s = &image[static_cast<size_t>(y) * pitch + static_cast<size_t>(x) * 4];
				const uint8_t* d = &pixels[(static_cast<size_t>(y) * width + x) * 3];
				same             = (d[0] == s[2] && d[1] == s[1] && d[2] == s[0]);
			}
		}
		Check(same, "RGB pixels from BGRA survive the round trip");
		bool none = true;
		for (auto f: filters) {
			none = none && (f == 0);
		}
		Check(none, "filter_type 0 writes the none filter in every row");
	}

	// the overflow: a PNG buffer too small
	{
		PngEncEncodeParam p = param;
		p.png_mem_size      = 40;
		PngEncOutputInfo info = {1, 1};
		Check(PngEncEncode(handle, &p, &info) == ERROR_DATA_OVERFLOW, "a 40-byte PNG buffer is DATA_OVERFLOW");
		Check(info.data_size == 0 && info.processed_height == 0, "the overflow zeroes the output info");
	}

	Check(PngEncDelete(handle) == 0, "Delete after the encodes");
}

int main() {
	TestCreateAndDelete();
	TestEncode();
	if (g_failed != 0) {
		std::fprintf(stderr, "PngEncTests: %d check(s) FAILED\n", g_failed);
		return 1;
	}
	std::fprintf(stderr, "PngEncTests: all checks passed\n");
	return 0;
}
