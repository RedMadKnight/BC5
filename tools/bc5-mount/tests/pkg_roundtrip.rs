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
    // Decode-ahead of every file, then the same bytes from its blocks.
    let p = PkgImage::open(bytes.clone()).unwrap();
    for idx in 0..p.entry_count() {
        p.prefetch_file(idx, 0, u64::MAX).unwrap();
    }
    let d = diff(&want, &hash_volume(&p, |_| {}).unwrap());
    assert!(d.is_empty(), "{name}: differs after decode-ahead: {d:?}");
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

/// Experiment 0112: with an on-disk block cache, a second open reads the
/// Kraken blocks back from disk, and every file still matches the spec.
#[test]
fn disk_cache_serves_a_second_open() {
    let spec = Spec::preset("mixed-compress").unwrap();
    let bytes = build(&spec);
    let dir = std::env::temp_dir().join(format!("bc5-pkg-diskcache-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    let want = expected(&spec);

    let first = PkgImage::open_with(bytes.clone(), Some((dir.as_path(), 1 << 30))).unwrap();
    assert!(
        first.info().stats.kraken > 0,
        "the preset must have Kraken blocks"
    );
    let d = diff(&want, &hash_volume(&first, |_| {}).unwrap());
    assert!(d.is_empty(), "first open differs from spec: {d:?}");
    drop(first);

    let before = bc5_mount::stats::snapshot();
    let second = PkgImage::open_with(bytes, Some((dir.as_path(), 1 << 30))).unwrap();
    let d = diff(&want, &hash_volume(&second, |_| {}).unwrap());
    assert!(d.is_empty(), "second open differs from spec: {d:?}");
    let after = bc5_mount::stats::snapshot();
    assert!(
        after.disk_blocks > before.disk_blocks,
        "no block came from disk"
    );
    let _ = std::fs::remove_dir_all(&dir);
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

/// `sce_sys/param.json` is synthesised from the content ID when the inner image has
/// none (experiment 0148): hosts take `TITLE_ID` from it.
#[test]
fn param_json_synthesised_from_the_content_id() {
    use bc5_mount::fixture::pkg_writer::write_pkg_with;
    use bc5_mount::fixture::DirSpec;
    use bc5_mount::pkg::PARAM_JSON_PATH;

    const ID: &str = "UP9000-PPSA03671_00-MARVELSWOLVERINE";
    let with_sce_sys = Spec::new(
        "sce-sys",
        DirSpec::new("")
            .file("eboot.bin", Content::Bytes(b"eboot".to_vec()))
            .dir(DirSpec::new("sce_sys").file("keystone", Content::Bytes(vec![7u8; 96]))),
    );
    let mut cur = Cursor::new(Vec::new());
    let info = write_pkg_with(&with_sce_sys, &mut cur, Some((ID, &[]))).unwrap();
    let bytes = cur.into_inner();
    assert_eq!(bytes.len() as u64, info.len);
    let p = PkgImage::open(bytes).unwrap();
    assert_eq!(p.content_id().as_deref(), Some(ID));
    assert!(p.param_json_synthesised());
    let idx = p
        .find(PARAM_JSON_PATH)
        .expect("the synthesised file is found");
    assert_eq!(
        p.find(r"SCE_SYS\Param.Json"),
        Some(idx),
        "case-insensitive, either slash"
    );
    let e = p.entry(idx).unwrap();
    assert_eq!(
        (e.name, e.path, e.is_dir),
        ("param.json", PARAM_JSON_PATH, false)
    );
    let sce_sys = p.find("sce_sys").unwrap();
    assert_eq!(e.parent, sce_sys);
    assert!(p.children(sce_sys).contains(&idx));
    assert_eq!(p.entry_count(), idx + 1);
    // Whole, and in pieces from an offset.
    let f = TreeFile::new(&p, idx).unwrap();
    let mut all = vec![0u8; e.size as usize];
    assert_eq!(f.read_at(0, &mut all).unwrap(), all.len());
    let text = std::str::from_utf8(&all).unwrap();
    assert!(text.contains("\"titleId\": \"PPSA03671\""), "{text}");
    let mut tail = vec![0u8; 8];
    assert_eq!(f.read_at(e.size - 3, &mut tail).unwrap(), 3);
    assert_eq!(&tail[..3], &all[all.len() - 3..]);
    assert_eq!(f.read_at(e.size + 10, &mut tail).unwrap(), 0);
    // The hashes of the volume list it alongside the real files.
    let got = hash_volume(&p, |_| {}).unwrap();
    assert!(
        got.iter()
            .any(|h| h.path.eq_ignore_ascii_case(PARAM_JSON_PATH)),
        "{got:?}"
    );

    // The inner image's own param.json wins; no sce_sys, nothing to add; no content ID, nothing.
    let own = Spec::new(
        "own",
        DirSpec::new("")
            .dir(DirSpec::new("sce_sys").file("param.json", Content::Bytes(b"{}".to_vec()))),
    );
    let mut cur = Cursor::new(Vec::new());
    write_pkg_with(&own, &mut cur, Some((ID, &[]))).unwrap();
    let p = PkgImage::open(cur.into_inner()).unwrap();
    assert!(!p.param_json_synthesised());
    let idx = p.find(PARAM_JSON_PATH).unwrap();
    assert_eq!(p.entry(idx).unwrap().size, 2);
    let no_dir = Spec::new(
        "no-dir",
        DirSpec::new("").file("a.txt", Content::Bytes(vec![1])),
    );
    let mut cur = Cursor::new(Vec::new());
    write_pkg_with(&no_dir, &mut cur, Some((ID, &[]))).unwrap();
    assert!(!PkgImage::open(cur.into_inner())
        .unwrap()
        .param_json_synthesised());
    let mut cur = Cursor::new(Vec::new());
    write_pkg(&with_sce_sys, &mut cur).unwrap();
    let p = PkgImage::open(cur.into_inner()).unwrap();
    assert_eq!(p.content_id(), None);
    assert!(!p.param_json_synthesised());
    assert_eq!(p.find(PARAM_JSON_PATH), None);
}

/// The container's own files show under `sce_sys` (experiment 0148): `param.json`
/// as the title wrote it, the icons, and the ones in subdirectories the inner image has.
#[test]
fn container_files_under_sce_sys() {
    use bc5_mount::fixture::pkg_writer::write_pkg_with;
    use bc5_mount::fixture::DirSpec;
    use bc5_mount::pkg::PARAM_JSON_PATH;

    const ID: &str = "UP9000-PPSA03671_00-MARVELSWOLVERINE";
    const PARAM: &[u8] =
        b"{\n  \"titleId\": \"PPSA03671\",\n  \"kernel\": {\"flexibleMemorySize\": 1}\n}\n";
    let icon: Vec<u8> = (0..70_000u32).map(|i| (i % 251) as u8).collect();
    let spec = Spec::new(
        "cnt",
        DirSpec::new("")
            .file("eboot.bin", Content::Bytes(b"eboot".to_vec()))
            .dir(
                DirSpec::new("sce_sys")
                    .file("keystone", Content::Bytes(vec![7u8; 96]))
                    .dir(DirSpec::new("uds")),
            ),
    );
    let files: Vec<(u32, &str, &[u8])> = vec![
        (0x2000, "param.json", PARAM),
        (0x1200, "icon0.png", &icon),
        (0x2020, "uds/npbind.dat", b"npbind"),
        (
            0x2021,
            "trophy2/npbind.dat",
            b"no such directory in the image",
        ),
        (0x100d, "keystone", b"the image's own keystone wins"),
    ];
    let mut cur = Cursor::new(Vec::new());
    let info = write_pkg_with(&spec, &mut cur, Some((ID, &files))).unwrap();
    let bytes = cur.into_inner();
    assert_eq!(bytes.len() as u64, info.len);
    let p = PkgImage::open(bytes).unwrap();
    assert!(
        !p.param_json_synthesised(),
        "the container's param.json is used"
    );
    let mut shown = p.container_files();
    shown.sort_unstable();
    assert_eq!(
        shown,
        [
            "sce_sys/icon0.png",
            "sce_sys/param.json",
            "sce_sys/uds/npbind.dat"
        ]
    );
    let read = |path: &str| -> Vec<u8> {
        let idx = p.find(path).unwrap_or_else(|| panic!("{path} not found"));
        let f = TreeFile::new(&p, idx).unwrap();
        let mut v = vec![0u8; f.len() as usize];
        assert_eq!(f.read_at(0, &mut v).unwrap(), v.len());
        v
    };
    assert_eq!(read(PARAM_JSON_PATH), PARAM);
    assert_eq!(read("SCE_SYS/ICON0.PNG"), icon);
    assert_eq!(read("sce_sys/uds/npbind.dat"), b"npbind");
    assert_eq!(read("sce_sys/keystone"), vec![7u8; 96]);
    assert_eq!(p.find("sce_sys/trophy2/npbind.dat"), None);
    let uds = p.find("sce_sys/uds").unwrap();
    let nb = p.find("sce_sys/uds/npbind.dat").unwrap();
    assert_eq!(p.children(uds), &[nb]);
    assert_eq!(p.entry(nb).unwrap().parent, uds);
    // A read in the middle of the icon, and past its end.
    let idx = p.find("sce_sys/icon0.png").unwrap();
    let mut mid = vec![0u8; 1000];
    assert_eq!(p.read_file_at(idx, 69_500, &mut mid).unwrap(), 500);
    assert_eq!(&mid[..500], &icon[69_500..]);
    assert_eq!(p.read_file_at(idx, 70_000, &mut mid).unwrap(), 0);
    let got = hash_volume(&p, |_| {}).unwrap();
    assert_eq!(
        got.iter()
            .filter(|h| h.path.to_ascii_lowercase().starts_with("sce_sys/"))
            .count(),
        4
    );
}
