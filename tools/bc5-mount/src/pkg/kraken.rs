// SPDX-License-Identifier: GPL-2.0-only
//! Kraken blocks of the inner image, decoded with the vendored `oozextract`.
//!
//! A stored block is one or two 128 KiB Kraken chunks without the Oodle block
//! and quantum headers that a standalone Oodle stream carries; the naps record
//! supplies what those headers would say (`docs/formats/ps5pkg.md` §5). The
//! headers are synthesised here so the standard decoder can take the block:
//! a Kraken block header, a quantum header with the total stored size, then
//! per chunk either a 3-byte LZ chunk header (LZ flag, literal mode, stored
//! length) followed by its bytes, or the bare entropy-coded bytes.

use crate::error::{bail_format, Result};
use crate::pkg::naps::{
    FLAG_CHUNK0_LZ, FLAG_CHUNK0_SUB_LITERALS, FLAG_CHUNK1_LZ, FLAG_CHUNK1_RESTART,
    FLAG_CHUNK1_SUB_LITERALS,
};

const LAYER: &str = "kraken";
const CHUNK_MAX: usize = 0x20000;
/// A quantum header's 18-bit stored length plus one.
const QUANTUM_MAX: usize = 0x40000;

/// Oodle block header: Kraken, decoder restart, not stored, no checksums.
const BLOCK_HEADER: [u8; 2] = [0x8C, 0x06];

/// Decodes one stored block of `dst.len()` logical bytes.
///
/// `even_comp` is the stored length of the first chunk (used when the block
/// spans two chunks); `flags` are the naps record's Kraken flags.
pub fn decode_block(src: &[u8], even_comp: usize, flags: u8, dst: &mut [u8]) -> Result<()> {
    if dst.is_empty() {
        if src.is_empty() {
            return Ok(());
        }
        bail_format!(LAYER, "{} stored bytes for an empty block", src.len());
    }
    if src.is_empty() {
        bail_format!(LAYER, "no stored bytes for a {}-byte block", dst.len());
    }
    let sub0 = flags & FLAG_CHUNK0_SUB_LITERALS != 0;
    let lz0 = flags & FLAG_CHUNK0_LZ != 0;
    let sub1 = flags & FLAG_CHUNK1_SUB_LITERALS != 0;
    let lz1 = flags & FLAG_CHUNK1_LZ != 0;
    let one_chunk = even_comp == 0 || even_comp >= src.len() || dst.len() <= CHUNK_MAX;
    if one_chunk {
        check_lz(lz0, src.len(), dst.len())?;
        return chunk(src, sub0, lz0, dst);
    }
    let chunk0_dst = CHUNK_MAX;
    let (c0, c1) = src.split_at(even_comp);
    check_lz(lz0, c0.len(), chunk0_dst)?;
    check_lz(lz1, c1.len(), dst.len() - chunk0_dst)?;
    let raw0 = !lz0 && c0.len() == chunk0_dst;
    let raw1 = !lz1 && c1.len() == dst.len() - chunk0_dst;
    if flags & FLAG_CHUNK1_RESTART != 0 || raw1 {
        // The second chunk decodes on its own: no references into the first
        // (restart), or none at all (stored).
        let (d0, d1) = dst.split_at_mut(chunk0_dst);
        chunk(c0, sub0, lz0, d0)?;
        chunk(c1, sub1, lz1, d1)
    } else {
        run(
            &frame(&[(c0, sub0, lz0, raw0), (c1, sub1, lz1, false)])?,
            dst,
        )
    }
}

/// Decodes one chunk on its own. A chunk that is not LZ and stores exactly as
/// many bytes as it outputs is stored as is (the encoder stores a chunk that
/// does not shrink; `docs/formats/ps5pkg.md` §5).
fn chunk(src: &[u8], sub: bool, lz: bool, dst: &mut [u8]) -> Result<()> {
    if !lz && src.len() == dst.len() {
        dst.copy_from_slice(src);
        return Ok(());
    }
    run(&frame(&[(src, sub, lz, false)])?, dst)
}

/// An LZ chunk's stored bytes must be fewer than its output (the decoder
/// treats equal sizes as a stored chunk).
fn check_lz(lz: bool, comp: usize, uncomp: usize) -> Result<()> {
    if lz && comp >= uncomp {
        bail_format!(
            LAYER,
            "LZ chunk of {comp} stored bytes for {uncomp} output bytes"
        );
    }
    Ok(())
}

/// Synthesises the Oodle framing around the chunks `(bytes, sub-literals, lz,
/// stored)`. A stored chunk gets an entropy-array header of type 0 (a copy), so
/// a following LZ chunk can still reference its bytes.
fn frame(chunks: &[(&[u8], bool, bool, bool)]) -> Result<Vec<u8>> {
    let total: usize = chunks
        .iter()
        .map(|(d, _, lz, raw)| d.len() + if *lz || *raw { 3 } else { 0 })
        .sum();
    if total == 0 || total > QUANTUM_MAX {
        bail_format!(LAYER, "{total} framed bytes do not fit one quantum");
    }
    let mut v = Vec::with_capacity(total + 5);
    v.extend_from_slice(&BLOCK_HEADER);
    let q = (total - 1) as u32;
    v.extend_from_slice(&[(q >> 16) as u8, (q >> 8) as u8, q as u8]);
    for (d, sub, lz, raw) in chunks {
        if *lz {
            // Bit 23: LZ chunk; bits 19–22: literal mode (0 = sub, 1 = raw); low 19 bits: length.
            let mode: u32 = u32::from(!*sub);
            let h = 0x80_0000 | (mode << 19) | d.len() as u32;
            v.extend_from_slice(&[(h >> 16) as u8, (h >> 8) as u8, h as u8]);
        } else if *raw {
            // Type 0 (copy), long form: 3-byte big-endian length below 2^18.
            let n = d.len() as u32;
            v.extend_from_slice(&[(n >> 16) as u8, (n >> 8) as u8, n as u8]);
        }
        v.extend_from_slice(d);
    }
    Ok(v)
}

fn run(input: &[u8], dst: &mut [u8]) -> Result<()> {
    let mut ex = oozextract::Extractor::new();
    match ex.read_from_slice(input, dst) {
        Ok(n) if n == dst.len() => Ok(()),
        Ok(n) => bail_format!(LAYER, "decoded {n} of {} bytes", dst.len()),
        Err(e) => bail_format!(LAYER, "{e}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// An entropy-only chunk in its memcpy form: type 0, 3-byte big-endian length.
    fn memcpy_chunk(data: &[u8]) -> Vec<u8> {
        let n = data.len() as u32;
        let mut v = vec![(n >> 16) as u8, (n >> 8) as u8, n as u8];
        v.extend_from_slice(data);
        v
    }

    #[test]
    fn stored_entropy_chunk_decodes() {
        let data: Vec<u8> = (0..1000u32).map(|i| (i * 7) as u8).collect();
        let src = memcpy_chunk(&data);
        let mut out = vec![0u8; data.len()];
        decode_block(&src, src.len(), 0, &mut out).unwrap();
        assert_eq!(out, data);
    }

    #[test]
    fn two_entropy_chunks_decode() {
        let data: Vec<u8> = (0..CHUNK_MAX as u32 + 5000)
            .map(|i| (i ^ (i >> 7)) as u8)
            .collect();
        let c0 = memcpy_chunk(&data[..CHUNK_MAX]);
        let c1 = memcpy_chunk(&data[CHUNK_MAX..]);
        let mut src = c0.clone();
        src.extend_from_slice(&c1);
        let mut out = vec![0u8; data.len()];
        decode_block(&src, c0.len(), 0, &mut out).unwrap();
        assert_eq!(out, data);
        let mut out2 = vec![0u8; data.len()];
        decode_block(&src, c0.len(), FLAG_CHUNK1_RESTART, &mut out2).unwrap();
        assert_eq!(out2, data);
    }

    /// A bare chunk whose Huffman table declares a single symbol: the whole chunk
    /// is that byte. Built from the fields: entropy header type 2 in long mode
    /// (byte 0 = type << 4 | bits 14-17 of dst - 1; then 32 bits big-endian:
    /// bits 0-13 of dst - 1 at bit 18, the payload length below), then the
    /// payload: bit 0 = old code-length format, bit 0 = explicit symbol list,
    /// 8 bits symbol count 1, 8 bits the symbol. PS5 packages store all-equal
    /// 128 KiB chunks this way (experiment 0036).
    #[test]
    fn single_symbol_huffman_chunk_decodes() {
        let fill = 0x5Au8;
        let dst_len = CHUNK_MAX;
        let payload_bits: u32 = (1 << 8 | u32::from(fill)) << 6; // 0, 0, count, symbol, pad
        let payload = [
            (payload_bits >> 16) as u8,
            (payload_bits >> 8) as u8,
            payload_bits as u8,
        ];
        let d = (dst_len - 1) as u32;
        let words = ((d & 0x3fff) << 18) | payload.len() as u32;
        let mut chunk = vec![0x20 | ((d >> 14) & 0xf) as u8];
        chunk.extend_from_slice(&words.to_be_bytes());
        chunk.extend_from_slice(&payload);
        assert_eq!(chunk.len(), 8);
        let mut out = vec![0u8; dst_len];
        decode_block(&chunk, chunk.len(), 0, &mut out).unwrap();
        assert!(out.iter().all(|&b| b == fill));
        // As the second chunk of a two-chunk block, after an entropy-only first chunk.
        let first: Vec<u8> = (0..CHUNK_MAX as u32).map(|i| (i * 13) as u8).collect();
        let c0 = memcpy_chunk(&first);
        let mut src = c0.clone();
        src.extend_from_slice(&chunk);
        let mut out2 = vec![0u8; 2 * CHUNK_MAX];
        decode_block(&src, c0.len(), FLAG_CHUNK1_RESTART, &mut out2).unwrap();
        assert_eq!(&out2[..CHUNK_MAX], &first[..]);
        assert!(out2[CHUNK_MAX..].iter().all(|&b| b == fill));
    }

    /// A chunk that stores as many bytes as it outputs is stored as is: first
    /// or second chunk, next to an entropy-coded or a single-symbol chunk.
    #[test]
    fn stored_chunk_inside_a_block_decodes() {
        let plain: Vec<u8> = (0..CHUNK_MAX as u32).map(|i| (i * 31 + 7) as u8).collect();
        let second: Vec<u8> = (0..5000u32).map(|i| (i ^ 0x55) as u8).collect();
        let c1 = memcpy_chunk(&second);
        // Stored first chunk, entropy-coded second chunk, continuing (no restart).
        let mut src = plain.clone();
        src.extend_from_slice(&c1);
        let mut out = vec![0u8; CHUNK_MAX + second.len()];
        decode_block(&src, plain.len(), 0, &mut out).unwrap();
        assert_eq!(&out[..CHUNK_MAX], &plain[..]);
        assert_eq!(&out[CHUNK_MAX..], &second[..]);
        // Entropy-coded first chunk, stored second chunk.
        let mut first = second.clone();
        first.resize(CHUNK_MAX, 0);
        let c0 = memcpy_chunk(&first);
        let mut src2 = c0.clone();
        src2.extend_from_slice(&plain);
        let mut out2 = vec![0u8; 2 * CHUNK_MAX];
        decode_block(&src2, c0.len(), 0, &mut out2).unwrap();
        assert_eq!(&out2[..CHUNK_MAX], &first[..]);
        assert_eq!(&out2[CHUNK_MAX..], &plain[..]);
        // A one-chunk block stored as is.
        let mut out3 = vec![0u8; CHUNK_MAX];
        decode_block(&plain, plain.len(), 0, &mut out3).unwrap();
        assert_eq!(out3, plain);
    }

    #[test]
    fn garbage_is_an_error_not_a_panic() {
        let src = vec![0xffu8; 300];
        let mut out = vec![0u8; 4096];
        assert!(decode_block(&src, src.len(), FLAG_CHUNK0_LZ, &mut out).is_err());
        assert!(decode_block(&src, src.len(), 0, &mut out).is_err());
        assert!(decode_block(&[], 0, 0, &mut out).is_err());
    }
}
