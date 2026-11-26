// BC5 experiment 0329: libScePngEnc for the KytyPlus host — the PS5's PNG encoder library, as the console behaves.
// The parameter structures, the validation order and the error codes are ported from boykopovar/AnyPS5 (GPL-2.0,
// commit 27c88a8): core/libs/prx/libScePngEnc/Export.cpp and core/libs/SceTypes.hpp:1746-1772. The encoder itself
// (core/Decoder/Png/src/Png.cpp's Encode: a per-row filter chosen by the smallest sum of absolute values among the
// filters the caller allows, one IDAT, an IEND) is written here over the vendored zlib (KYTY_HAS_ZLIB=1 in
// src/CMakeLists.txt; AnyPS5 compresses through stb_image_write, which this tree does not instantiate).
// SPDX-License-Identifier: GPL-2.0-only
#include "common/abi.h"
#include "common/assert.h"
#include "common/common.h"
#include "common/logging/log.h"
#include "libs/errno.h"
#include "libs/libs.h"
#include "loader/symbolDatabase.h"

#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

#include <zlib.h>

namespace Libs::PngEnc {

LIB_VERSION("PngEnc", 1, "PngEnc", 1, 1);

constexpr int PNG_ENC_ERROR_INVALID_ADDR   = static_cast<int>(0x80690101u);
constexpr int PNG_ENC_ERROR_INVALID_SIZE   = static_cast<int>(0x80690102u);
constexpr int PNG_ENC_ERROR_INVALID_PARAM  = static_cast<int>(0x80690103u);
constexpr int PNG_ENC_ERROR_INVALID_HANDLE = static_cast<int>(0x80690104u);
constexpr int PNG_ENC_ERROR_DATA_OVERFLOW  = static_cast<int>(0x80690110u);
constexpr int PNG_ENC_ERROR_FATAL          = static_cast<int>(0x80690120u);

constexpr uint32_t MAX_IMAGE_WIDTH        = 1000000;
constexpr uint32_t MAX_IMAGE_HEIGHT       = 1000000;
constexpr uint32_t MAX_FILTER_NUMBER      = 5;
constexpr uint16_t COLOR_SPACE_RGB        = 3;
constexpr uint16_t COLOR_SPACE_RGBA       = 19;
constexpr uint16_t PIXEL_FORMAT_R8G8B8A8  = 0;
constexpr uint16_t PIXEL_FORMAT_B8G8R8A8  = 1;
constexpr uint16_t FILTER_SUB             = 1;
constexpr uint16_t FILTER_UP              = 2;
constexpr uint16_t FILTER_AVERAGE         = 4;
constexpr uint16_t FILTER_PAETH           = 8;
constexpr uint16_t FILTER_ALL             = FILTER_SUB | FILTER_UP | FILTER_AVERAGE | FILTER_PAETH;
constexpr uint64_t CONTEXT_MAGIC          = 0x434E45474E505341ull;

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

struct PngEncContext {
	uint64_t magic;
	uint32_t max_image_width;
	uint32_t reserved;
};

static_assert(sizeof(PngEncCreateParam) == 16);
static_assert(sizeof(PngEncEncodeParam) == 48);
static_assert(sizeof(PngEncOutputInfo) == 8);
static_assert(sizeof(PngEncContext) == 16);

static int ValidateCreateParam(const PngEncCreateParam* param) {
	if (param == nullptr) {
		return PNG_ENC_ERROR_INVALID_ADDR;
	}
	if (param->attribute != 0 || param->max_filter_number > MAX_FILTER_NUMBER) {
		return PNG_ENC_ERROR_INVALID_PARAM;
	}
	if (param->max_image_width == 0 || param->max_image_width > MAX_IMAGE_WIDTH) {
		return PNG_ENC_ERROR_INVALID_SIZE;
	}
	return OK;
}

static PngEncContext* Context(void* handle) {
	auto* ctx = static_cast<PngEncContext*>(handle);
	return (ctx != nullptr && ctx->magic == CONTEXT_MAGIC) ? ctx : nullptr;
}

// The PNG filter types (PNG specification, 9. Filtering): 0 none, 1 sub, 2 up, 3 average, 4 paeth. The library's
// filter_type is a mask of the four non-trivial ones; 0 means the none filter alone.
static uint8_t FilterMask(uint16_t filter_type) {
	if (filter_type == 0) {
		return 1u << 0;
	}
	uint8_t mask = 1u << 0;
	if ((filter_type & FILTER_SUB) != 0) {
		mask |= 1u << 1;
	}
	if ((filter_type & FILTER_UP) != 0) {
		mask |= 1u << 2;
	}
	if ((filter_type & FILTER_AVERAGE) != 0) {
		mask |= 1u << 3;
	}
	if ((filter_type & FILTER_PAETH) != 0) {
		mask |= 1u << 4;
	}
	return mask;
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

// One row through one filter into out; the cost is the sum of the filtered bytes' absolute values (the heuristic of
// libpng and of AnyPS5's encoder: the smallest sum compresses best).
static uint64_t FilterRow(const uint8_t* row, const uint8_t* prev, size_t row_size, uint32_t bpp, uint8_t type,
                          uint8_t* out) {
	uint64_t cost = 0;
	for (size_t i = 0; i < row_size; i++) {
		const int x = row[i];
		const int a = (i >= bpp) ? row[i - bpp] : 0;
		const int b = (prev != nullptr) ? prev[i] : 0;
		const int c = (prev != nullptr && i >= bpp) ? prev[i - bpp] : 0;
		uint8_t   v = 0;
		switch (type) {
			case 0: v = static_cast<uint8_t>(x); break;
			case 1: v = static_cast<uint8_t>(x - a); break;
			case 2: v = static_cast<uint8_t>(x - b); break;
			case 3: v = static_cast<uint8_t>(x - ((a + b) >> 1)); break;
			default: v = static_cast<uint8_t>(x - Paeth(a, b, c)); break;
		}
		out[i] = v;
		cost += static_cast<uint64_t>(v < 128 ? v : 256 - v);
	}
	return cost;
}

static void AppendBigEndian32(std::vector<uint8_t>& out, uint32_t v) {
	out.push_back(static_cast<uint8_t>(v >> 24));
	out.push_back(static_cast<uint8_t>(v >> 16));
	out.push_back(static_cast<uint8_t>(v >> 8));
	out.push_back(static_cast<uint8_t>(v));
}

static void AppendChunk(std::vector<uint8_t>& out, const char* type, const uint8_t* data, size_t size) {
	AppendBigEndian32(out, static_cast<uint32_t>(size));
	const size_t type_at = out.size();
	out.insert(out.end(), type, type + 4);
	if (size != 0) {
		out.insert(out.end(), data, data + size);
	}
	const auto crc = static_cast<uint32_t>(::crc32(0L, out.data() + type_at, static_cast<uInt>(4 + size)));
	AppendBigEndian32(out, crc);
}

// Encode: the rows (channels bytes per pixel, 8 bits) filtered, deflated at the given level, framed as a PNG.
// Returns false when zlib fails (memory) — the library's FATAL.
static bool Encode(const std::vector<uint8_t>& pixels, uint32_t width, uint32_t height, uint32_t channels,
                   uint8_t filter_mask, int level, std::vector<uint8_t>* png) {
	const size_t         row_size = static_cast<size_t>(width) * channels;
	std::vector<uint8_t> filtered((row_size + 1) * height);
	std::vector<uint8_t> candidate(row_size);
	for (uint32_t y = 0; y < height; y++) {
		const uint8_t* row  = pixels.data() + row_size * y;
		const uint8_t* prev = (y == 0) ? nullptr : row - row_size;
		uint8_t*       dst  = filtered.data() + (row_size + 1) * y;
		uint64_t       best = UINT64_MAX;
		for (uint8_t type = 0; type < 5; type++) {
			if ((filter_mask & (1u << type)) == 0) {
				continue;
			}
			const uint64_t cost = FilterRow(row, prev, row_size, channels, type, candidate.data());
			if (cost >= best) {
				continue;
			}
			best   = cost;
			dst[0] = type;
			std::memcpy(dst + 1, candidate.data(), row_size);
		}
	}

	uLongf               compressed_size = ::compressBound(static_cast<uLong>(filtered.size()));
	std::vector<uint8_t> compressed(compressed_size);
	if (::compress2(compressed.data(), &compressed_size, filtered.data(), static_cast<uLong>(filtered.size()), level) !=
	    Z_OK) {
		return false;
	}
	compressed.resize(compressed_size);

	static const uint8_t signature[8]         = {0x89, 'P', 'N', 'G', 0x0d, 0x0a, 0x1a, 0x0a};
	static const uint8_t color_type_by_ch[5] = {0, 0, 4, 2, 6};
	uint8_t              ihdr[13]             = {};
	ihdr[0]                                   = static_cast<uint8_t>(width >> 24);
	ihdr[1]                                   = static_cast<uint8_t>(width >> 16);
	ihdr[2]                                   = static_cast<uint8_t>(width >> 8);
	ihdr[3]                                   = static_cast<uint8_t>(width);
	ihdr[4]                                   = static_cast<uint8_t>(height >> 24);
	ihdr[5]                                   = static_cast<uint8_t>(height >> 16);
	ihdr[6]                                   = static_cast<uint8_t>(height >> 8);
	ihdr[7]                                   = static_cast<uint8_t>(height);
	ihdr[8]                                   = 8;
	ihdr[9]                                   = color_type_by_ch[channels];

	png->clear();
	png->reserve(8 + 3 * 12 + 13 + compressed.size());
	png->insert(png->end(), signature, signature + 8);
	AppendChunk(*png, "IHDR", ihdr, sizeof(ihdr));
	AppendChunk(*png, "IDAT", compressed.data(), compressed.size());
	AppendChunk(*png, "IEND", nullptr, 0);
	return true;
}

int KYTY_SYSV_ABI PngEncQueryMemorySize(const PngEncCreateParam* param) {
	PRINT_NAME();

	if (const int result = ValidateCreateParam(param); result != OK) {
		return result;
	}
	return static_cast<int>(sizeof(PngEncContext));
}

int KYTY_SYSV_ABI PngEncCreate(const PngEncCreateParam* param, void* memory, uint32_t memory_size, void** handle) {
	PRINT_NAME();

	if (const int result = ValidateCreateParam(param); result != OK) {
		return result;
	}
	if (memory == nullptr || handle == nullptr) {
		return PNG_ENC_ERROR_INVALID_ADDR;
	}
	if (memory_size < sizeof(PngEncContext)) {
		return PNG_ENC_ERROR_INVALID_SIZE;
	}

	LOGF("\t max_image_width = %u, max_filter_number = %u\n", param->max_image_width, param->max_filter_number);

	*static_cast<PngEncContext*>(memory) = {CONTEXT_MAGIC, param->max_image_width, 0};
	*handle                              = memory;
	return OK;
}

int KYTY_SYSV_ABI PngEncDelete(void* handle) {
	PRINT_NAME();

	PngEncContext* ctx = Context(handle);
	if (ctx == nullptr) {
		return PNG_ENC_ERROR_INVALID_HANDLE;
	}
	ctx->magic = 0;
	return OK;
}

// The return value on success is the PNG's size in bytes (AnyPS5 Export.cpp:136), output_info filled with the size
// and the rows processed; DATA_OVERFLOW (output_info zeroed) when the PNG does not fit png_mem_size.
int KYTY_SYSV_ABI PngEncEncode(void* handle, const PngEncEncodeParam* param, PngEncOutputInfo* output_info) {
	PRINT_NAME();

	const PngEncContext* ctx = Context(handle);
	if (ctx == nullptr) {
		return PNG_ENC_ERROR_INVALID_HANDLE;
	}
	if (param == nullptr) {
		return PNG_ENC_ERROR_INVALID_PARAM;
	}
	if (param->image_mem_addr == nullptr || param->png_mem_addr == nullptr) {
		return PNG_ENC_ERROR_INVALID_ADDR;
	}
	if ((param->pixel_format != PIXEL_FORMAT_R8G8B8A8 && param->pixel_format != PIXEL_FORMAT_B8G8R8A8) ||
	    (param->color_space != COLOR_SPACE_RGB && param->color_space != COLOR_SPACE_RGBA) || param->bit_depth != 8 ||
	    param->clut_number != 0 || (param->filter_type & ~FILTER_ALL) != 0 || param->compression_level > 9) {
		return PNG_ENC_ERROR_INVALID_PARAM;
	}

	const uint32_t width  = param->image_width;
	const uint32_t height = param->image_height;
	if (width == 0 || height == 0 || width > ctx->max_image_width || height > MAX_IMAGE_HEIGHT ||
	    param->png_mem_size == 0 || param->image_pitch < width * 4 ||
	    static_cast<uint64_t>(param->image_pitch) * (height - 1) + static_cast<uint64_t>(width) * 4 >
	        param->image_mem_size) {
		return PNG_ENC_ERROR_INVALID_SIZE;
	}

	LOGF("\t %u x %u, pitch %u, %s, %s, filters 0x%x, level %u, png buffer %u\n", width, height, param->image_pitch,
	     param->pixel_format == PIXEL_FORMAT_B8G8R8A8 ? "B8G8R8A8" : "R8G8B8A8",
	     param->color_space == COLOR_SPACE_RGBA ? "RGBA" : "RGB", param->filter_type, param->compression_level,
	     param->png_mem_size);

	const uint32_t       channels = (param->color_space == COLOR_SPACE_RGBA) ? 4 : 3;
	const bool           bgr      = (param->pixel_format == PIXEL_FORMAT_B8G8R8A8);
	std::vector<uint8_t> pixels;
	std::vector<uint8_t> png;
	{ // (the tree builds without exceptions: an allocation failure aborts, as the console's would)
		pixels.resize(static_cast<size_t>(width) * height * channels);
		uint8_t* dst = pixels.data();
		for (uint32_t y = 0; y < height; y++) {
			const uint8_t* src = param->image_mem_addr + static_cast<size_t>(y) * param->image_pitch;
			for (uint32_t x = 0; x < width; x++, src += 4) {
				*dst++ = src[bgr ? 2 : 0];
				*dst++ = src[1];
				*dst++ = src[bgr ? 0 : 2];
				if (channels == 4) {
					*dst++ = src[3];
				}
			}
		}
		if (!Encode(pixels, width, height, channels, FilterMask(param->filter_type), param->compression_level,
		            &png)) {
			return PNG_ENC_ERROR_FATAL;
		}
	}

	const bool overflow = png.size() > param->png_mem_size;
	if (output_info != nullptr) {
		*output_info = {overflow ? 0u : static_cast<uint32_t>(png.size()), overflow ? 0u : height};
	}
	if (overflow) {
		return PNG_ENC_ERROR_DATA_OVERFLOW;
	}
	std::memcpy(param->png_mem_addr, png.data(), png.size());
	return static_cast<int>(png.size());
}

LIB_DEFINE(InitPngEnc_1) {
	LIB_FUNC("9030RnBDoh4", PngEncQueryMemorySize);
	LIB_FUNC("7aGTPfrqT9s", PngEncCreate);
	LIB_FUNC("RUrWdwTWZy8", PngEncDelete);
	LIB_FUNC("xgDjJKpcyHo", PngEncEncode);
}

} // namespace Libs::PngEnc
