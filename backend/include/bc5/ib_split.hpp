// SPDX-License-Identifier: GPL-2.0-only
// Experiment 0349: cut a job's executed IB into pieces the kernel accepts.
//
// amdgpu_cs refuses an IB longer than 0xfffff dwords (drivers/gpu/drm/amd/amdgpu/amdgpu_cs.c,
// amdgpu_cs_p2_ib: `chunk_ib->ib_bytes / 4 > amdgpu_cs_ib_packet_size_max_dw()`, the INDIRECT_BUFFER
// packet's 20-bit size field; torvalds/linux 62c457528529), and one submit carries up to four IBs
// through libdrm (amdgpu.h, AMDGPU_CS_MAX_IBS_PER_SUBMIT 4; the GFX ring itself takes 192,
// amdgpu_ring.c amdgpu_ring_max_ibs). The kernel runs the IBs of one job back to back from the ring,
// each as an IB1, so the title's own INDIRECT_BUFFERs stay IB2 (F421, F426).
//
// A cut is a packet boundary that is a multiple of `align_dw` dwords from the image's start (the
// image sits at a page-aligned VA) and lies outside every COND_EXEC range: a range that crossed an
// IB's end would skip into the next IB. Nothing is inserted or moved; the pieces are windows of the
// same image, so every packet decision of the passes before it is unchanged.
#pragma once

#include <cstddef>
#include <cstdint>
#include <span>
#include <vector>

namespace bc5::ib_split {

constexpr std::size_t kKernelMaxDwords = 0xfffff; // AMDGPU_GFX_SDMA_IB_PACKET_SIZE_MAX_DW, measured on the box (raw/ib-probe.out)
constexpr std::size_t kDefaultMaxDwords = 0xf0000; // the limit the submit cuts at: the kernel's less a 6 % margin
constexpr std::size_t kMaxPieces = 4;             // AMDGPU_CS_MAX_IBS_PER_SUBMIT

struct Piece {
    std::size_t off = 0; // dword offset in the image
    std::size_t n = 0;   // dwords
};

struct Stats {
    std::uint32_t cond_ranges = 0;    // COND_EXEC ranges found in [0, end)
    std::uint32_t pieces = 0;         // pieces returned (0 when nothing was cut)
    std::uint32_t fallback_cuts = 0;  // cuts that had to use `fallback_align_dw`
    bool failed = false;              // no cut set within max_pieces
    bool too_many_pieces = false;     // failed because more than max_pieces would be needed (else: no boundary)
    std::size_t failed_at = 0;        // the piece start that found no cut
};

// The pieces covering [0, end) of `image` in order, each at most `max_dw` dwords, at most
// `max_pieces` of them, every cut a packet boundary aligned to `align_dw` (else `fallback_align_dw`)
// and outside every COND_EXEC range. When `end <= max_dw` the one piece [0, end) is returned. Empty
// when no such cut set exists (stats.failed).
std::vector<Piece> split(std::span<const std::uint32_t> image, std::size_t end, std::size_t max_dw,
                         std::size_t max_pieces, std::size_t align_dw, std::size_t fallback_align_dw,
                         Stats &stats);

} // namespace bc5::ib_split
