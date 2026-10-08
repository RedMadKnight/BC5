// SPDX-License-Identifier: GPL-2.0-only
//! End-to-end for packages: every preset is written as a synthetic package,
//! opened through the full stack (FIH → outer PFS → naps → blocks → inner
//! PFS) and compared, file by file, with the spec.

use std::io::Cursor;

use bc5_mount::fixture::pkg_writer::write_pkg;
use bc5_mount::fixture::{Content, Spec};
use bc5_mount::io::ReadAt;
use bc5_mount::pkg::PkgImage;
use bc5_mount::tree::{FileTree, TreeFile};
use bc5_mount::verify::{diff, hash_volume, FileHash};
use bc5_mount::Error;

fn build(spec: &Spec) -> Vec<u8> {
    let mut cur = Cursor::new(Vec::new());
    let info = write_pkg(spec, &mut cur).unwrap();
    let bytes = cur.into_inner();
    assert_eq!(bytes.len() as u64, info.len);
    bytes
}

fn expected(spec: &Spec) -> Vec<FileHash> {
    spec.expected_hashes()
        .into_iter()
        .map(|(path, size, sha256)| FileHash { path, size, sha256 })
        .collect()
}

fn check_preset(name: &str) {
    let spec = Spec::preset(name).unwrap();
    let bytes = build(&spec);
    let p = PkgImage::open(bytes.clone()).unwrap();
    let info = p.info();
    assert_eq!(info.file_count, spec.files().len(), "{name}: file count");
    assert_eq!(info.dir_count, spec.dirs().len(), "{name}: dir count");
    assert_eq!(
        info.stats.stored + info.stats.kraken + info.stats.sparse,
        info.blocks,
        "{name}: block kinds add up"
    );
    let got = hash_volume(&p, |_| {}).unwrap();
    let want = expected(&spec);
    let d = diff(&want, &got);
    assert!(d.is_empty(), "{name}: package differs from spec: {d:?}");
    // Deterministic: building again yields identical bytes.
    assert!(build(&spec) == bytes, "{name}: build is not deterministic");
}

#[test]
fn empty() {
    check_preset("empty");
}

#[test]
fn one_small() {
    check_preset("one-small");
}

#[test]
fn spanning() {
    check_preset("spanning");
}

#[test]
fn mixed_compress() {
    check_preset("mixed-compress");
}

#[test]
fn deep() {
    check_preset("deep");
}

#[test]
fn wide() {
    check_preset("wide");
}

#[test]
fn case() {
    check_preset("case");
}

#[test]
fn contiguous() {
    check_preset("contiguous");
}

#[test]
fn block_kinds_follow_the_content() {
    // A file over 256 KiB is stored as it is, a small one in the memcpy Kraken
    // form, an all-zero one as a sparse region.
    let spec = Spec::preset("mixed-compress").unwrap();
    let mut cur = Cursor::new(Vec::new());
    let info = write_pkg(&spec, &mut cur).unwrap();
    let (stored, kraken, sparse) = info.blocks;
    assert!(kraken > 0, "memcpy blocks: {info:?}");
    let has_zeros = spec
        .files()
        .iter()
        .any(|(_, c)| matches!(c, Content::Zeros(n) if *n > 0));
    assert_eq!(sparse > 0, has_zeros, "sparse blocks: {info:?}");
    assert!(stored + kraken + sparse > 0);
}

#[test]
fn random_reads_match_spec() {
    let spec = Spec::preset("spanning").unwrap();
    let p = PkgImage::open(build(&spec)).unwrap();
    let idx = p.find("big.bin").unwrap();
    let file = TreeFile::new(&p, idx).unwrap();
    let content = &spec.files()[0].1;
    for (off, len) in [
        (0u64, 1usize),
        (0x7FFF, 2),
        (0xFFF0, 0x20),
        (0x3FFFF, 2),
        (200 * 1024, 1),
        (200 * 1024 + 1, 5),
        (12_345, 70_000),
        (0x40000 - 100, 300_000),
    ] {
        let got = {
            let mut b = vec![0u8; len];
            let n = file.read_at(off, &mut b).unwrap();
            b.truncate(n);
            b
        };
        let want_len = (content.len().saturating_sub(off)).min(len as u64) as usize;
        let mut want = vec![0u8; want_len];
        content.fill(off, &mut want);
        assert_eq!(got, want, "read at {off} len {len}");
    }
}

#[test]
fn lookups_are_case_insensitive_and_paths_work() {
    let spec = Spec::preset("deep").unwrap();
    let p = PkgImage::open(build(&spec)).unwrap();
    for (path, _) in spec.files() {
        let idx = p.find(&path).unwrap_or_else(|| panic!("{path} not found"));
        assert_eq!(p.entry(idx).unwrap().path, path);
        let upper = path.to_uppercase();
        assert_eq!(p.find(&upper), Some(idx), "{upper}");
        let backslashes = path.replace('/', "\\");
        assert_eq!(p.find(&backslashes), Some(idx), "{backslashes}");
    }
    assert_eq!(p.find(""), Some(0));
    assert!(p.find("no/such/file").is_none());
}

/// Corrupting structural bytes must produce an error, never a panic.
#[test]
fn corruption_is_reported_not_panicked() {
    let spec = Spec::preset("one-small").unwrap();
    let clean = build(&spec);
    let mut bad = clean.clone();
    bad[0] = 0;
    assert!(matches!(PkgImage::open(bad), Err(Error::Format { .. })));
    // every header word zeroed in turn
    for off in (0x10..0x28).step_by(8) {
        let mut bad = clean.clone();
        bad[off..off + 8].fill(0);
        assert!(PkgImage::open(bad).is_err(), "header word at {off:#x}");
    }
    // the outer superblock magic
    let sb = u64::from_le_bytes(clean[0x20..0x28].try_into().unwrap()) as usize;
    let mut bad = clean.clone();
    bad[sb + 8] ^= 1;
    assert!(PkgImage::open(bad).is_err());
    // an encrypted outer image is refused, not decrypted
    let mut bad = clean.clone();
    bad[sb + 0x1c] |= 0x4;
    bad[sb + 0x370..sb + 0x380].fill(0xaa);
    assert!(matches!(PkgImage::open(bad), Err(Error::Unsupported(_))));
    // a truncated file
    let short = clean[..clean.len() - 0x10000].to_vec();
    assert!(PkgImage::open(short).is_err());
}
