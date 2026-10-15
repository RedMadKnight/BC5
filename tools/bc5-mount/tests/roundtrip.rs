// SPDX-License-Identifier: GPL-2.0-only
//! End-to-end: every preset is built, written to disk, opened through the full
//! stack (PFS → PFSC → exFAT) and compared, file by file, with the spec and
//! with a plain directory materialised from the same spec.

use std::path::PathBuf;

use bc5_mount::container::Container;
use bc5_mount::fixture::{build_in_memory, build_to_path, Spec};
use bc5_mount::io::ReadAt;
use bc5_mount::verify::{diff, hash_directory, hash_volume, FileHash};
use bc5_mount::Error;

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR"))
        .join(format!("fixture-{name}-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

fn expected(spec: &Spec) -> Vec<FileHash> {
    spec.expected_hashes()
        .into_iter()
        .map(|(path, size, sha256)| FileHash { path, size, sha256 })
        .collect()
}

fn check_preset(name: &str) {
    let spec = Spec::preset(name).unwrap();
    let dir = tmp(name);
    let container_path = dir.join("fixture.ffpfsc");
    let info = build_to_path(&spec, &container_path).unwrap();
    assert_eq!(info.file_count, spec.files().len(), "{name}: file count");
    assert_eq!(info.dir_count, spec.dirs().len(), "{name}: dir count");
    assert_eq!(
        std::fs::metadata(&container_path).unwrap().len(),
        info.container_len
    );
    assert_eq!(info.container_len % u64::from(spec.pfs_block_size), 0);

    let c = Container::open_path(&container_path).unwrap();
    assert_eq!(c.inner_name(), spec.inner_name);
    let ci = c.info().unwrap();
    assert_eq!(ci.logical_len, info.exfat_len);
    assert_eq!(ci.stored_len, info.pfsc_stored_len);
    assert_eq!(ci.pfsc_blocks, info.pfsc_blocks);
    assert_eq!(ci.compressed_blocks, info.compressed_blocks);
    assert_eq!(ci.file_count, spec.files().len());

    let got = hash_volume(c.exfat(), |_| {}).unwrap();
    let want = expected(&spec);
    let d = diff(&want, &got);
    assert!(d.is_empty(), "{name}: container differs from spec: {d:?}");

    let tree = dir.join("tree");
    spec.materialize(&tree).unwrap();
    let on_disk = hash_directory(&tree).unwrap();
    let d = diff(&want, &on_disk);
    assert!(
        d.is_empty(),
        "{name}: materialised tree differs from spec: {d:?}"
    );

    // Deterministic: building again yields identical bytes.
    let (again, _) = build_in_memory(&spec).unwrap();
    assert_eq!(again.len() as u64, info.container_len);
    let first = std::fs::read(&container_path).unwrap();
    assert!(first == again, "{name}: build is not deterministic");

    std::fs::remove_dir_all(&dir).unwrap();
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
    let spec = Spec::preset("mixed-compress").unwrap();
    let (_, info) = build_in_memory(&spec).unwrap();
    // zeros.bin and tail.bin compress; noise.bin (4 blocks) does not.
    assert!(info.compressed_blocks >= 4, "{info:?}");
    assert!(info.compressed_blocks < info.pfsc_blocks, "{info:?}");
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
    let (bytes, _) = build_in_memory(&Spec::preset("case").unwrap()).unwrap();
    let c = Container::open(bytes).unwrap();
    let t = c.title_info().unwrap().unwrap();
    assert_eq!(t.title_id.as_deref(), Some("BREW00001"));
    assert_eq!(t.title_name.as_deref(), Some("BC5 fixture"));
    assert!(c.exfat().find("SCE_SYS\\PARAM.JSON").is_some());
    assert!(c.exfat().find("sce_sys/nope").is_none());
}
#[test]
fn contiguous() {
    check_preset("contiguous");
}

/// One GiB logical, mostly zeros: exercises the grown PFSC header and 64-bit
/// offsets. Slow-ish; run explicitly (`cargo test -- --ignored`).
#[test]
#[ignore = "1 GiB fixture, ~1 min in release; run with --ignored"]
fn sparse_1g() {
    check_preset("sparse-1g");
}

#[test]
fn random_reads_match_spec() {
    let spec = Spec::preset("spanning").unwrap();
    let (bytes, _) = build_in_memory(&spec).unwrap();
    let c = Container::open(bytes).unwrap();
    let idx = c.exfat().find("big.bin").unwrap();
    let file = c.exfat().file(idx).unwrap();
    let content = &spec.files()[0].1;
    for (off, len) in [
        (0u64, 1usize),
        (0x7FFF, 2),
        (0xFFF0, 0x20),
        (200 * 1024, 1),
        (200 * 1024 + 1, 5),
        (12_345, 70_000),
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

/// Corrupting structural bytes must produce an error, never a panic, and
/// corrupting payload bytes must be caught by verification.
#[test]
fn corruption_is_reported_not_panicked() {
    let spec = Spec::preset("one-small").unwrap();
    let (clean, _) = build_in_memory(&spec).unwrap();
    assert!(Container::open(clean.clone()).is_ok());

    // Truncations at every block boundary and a few odd places.
    for cut in [
        0usize,
        1,
        0x47,
        0x10000,
        0x10000 + 0xA8 * 3 + 5,
        0x20010,
        0x60000,
        0x60030,
        clean.len() - 1,
    ] {
        let short = clean[..cut].to_vec();
        match Container::open(short) {
            Err(_) => {}
            Ok(_) => panic!("truncated at {cut} bytes still opened"),
        }
    }

    // Single-byte flips over every structural byte: superblock, inode table,
    // both directories, the flat path table, the PFSC header and offset table,
    // and the start of the exFAT boot sector inside the first PFSC block. The
    // container either fails to open or, when the byte was unused, still reads
    // (reads must not panic; a hash mismatch is tolerated for payload bytes).
    let want: Vec<FileHash> = spec
        .expected_hashes()
        .into_iter()
        .map(|(path, size, sha256)| FileHash { path, size, sha256 })
        .collect();
    let regions = [
        0usize..0x48,
        0x10000..0x10000 + 4 * 0xA8,
        0x20000..0x20040,
        0x30000..0x30008,
        0x50000..0x50050,
        0x60000..0x60030,
        0x60400..0x60410,
        0x70000..0x70040,
    ];
    let mut rejected = 0;
    let mut total = 0;
    for pos in regions.into_iter().flatten() {
        total += 1;
        let mut bad = clean.clone();
        bad[pos] ^= 0x5A;
        match Container::open(bad) {
            Err(
                Error::Format { .. } | Error::Unsupported(_) | Error::Io(_) | Error::NotFound(_),
            ) => rejected += 1,
            Ok(c) => {
                let _ = hash_volume(c.exfat(), |_| {}).map(|got| diff(&want, &got));
            }
        }
    }
    assert!(
        rejected * 2 > total,
        "only {rejected} of {total} structural flips were rejected"
    );
}
