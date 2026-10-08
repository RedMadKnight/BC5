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
        return run(&frame(&[(src, sub0, lz0)]), dst);
    }
    let chunk0_dst = CHUNK_MAX;
    let (c0, c1) = src.split_at(even_comp);
    check_lz(lz0, c0.len(), chunk0_dst)?;
    check_lz(lz1, c1.len(), dst.len() - chunk0_dst)?;
    if flags & FLAG_CHUNK1_RESTART != 0 {
        // The second chunk decodes on its own: no references into the first.
        let (d0, d1) = dst.split_at_mut(chunk0_dst);
        run(&frame(&[(c0, sub0, lz0)]), d0)?;
        run(&frame(&[(c1, sub1, lz1)]), d1)
    } else {
        run(&frame(&[(c0, sub0, lz0), (c1, sub1, lz1)]), dst)
    }
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

/// Synthesises the Oodle framing around the chunks `(bytes, sub-literals, lz)`.
fn frame(chunks: &[(&[u8], bool, bool)]) -> Vec<u8> {
    let total: usize = chunks
        .iter()
        .map(|(d, _, lz)| d.len() + if *lz { 3 } else { 0 })
        .sum();
    let mut v = Vec::with_capacity(total + 5);
    v.extend_from_slice(&BLOCK_HEADER);
    let q = (total - 1) as u32;
    v.extend_from_slice(&[(q >> 16) as u8, (q >> 8) as u8, q as u8]);
    for (d, sub, lz) in chunks {
        if *lz {
            // Bit 23: LZ chunk; bits 19–22: literal mode (0 = sub, 1 = raw); low 19 bits: length.
            let mode: u32 = u32::from(!*sub);
            let h = 0x80_0000 | (mode << 19) | d.len() as u32;
            v.extend_from_slice(&[(h >> 16) as u8, (h >> 8) as u8, h as u8]);
        }
        v.extend_from_slice(d);
    }
    v
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

    #[test]
    fn garbage_is_an_error_not_a_panic() {
        let src = vec![0xffu8; 300];
        let mut out = vec![0u8; 4096];
        assert!(decode_block(&src, src.len(), FLAG_CHUNK0_LZ, &mut out).is_err());
        assert!(decode_block(&src, src.len(), 0, &mut out).is_err());
        assert!(decode_block(&[], 0, 0, &mut out).is_err());
    }
}
