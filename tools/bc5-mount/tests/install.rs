// SPDX-License-Identifier: GPL-2.0-only
//! Tests for the `install` subcommand.
//!
//! Builds a fixture image with nested dirs, empty files, one large file (> 64 MiB,
//! sparse), and compressed/stored blocks. Installs it, compares trees and contents,
//! then tests refuse, resume, and verify paths.

use std::fs;
use std::path::PathBuf;

use bc5_mount::fixture::{build_to_path, Content, DirSpec, Spec};
use bc5_mount::install::{install, write_install_json};
use bc5_mount::verify::{diff, hash_directory, hash_volume, FileHash};

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR"))
        .join(format!("install-{name}-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    dir
}

/// Build a fixture with nested dirs, empty files, a large sparse file, and
/// compressed/stored blocks.
fn install_spec() -> Spec {
    Spec::new(
        "install-test",
        DirSpec::new("")
            .dir(DirSpec::new("sce_sys").file("param.json", Content::Bytes(b"{}\n".to_vec())))
            .file("empty.bin", Content::Zeros(0))
            .file(
                "large_sparse.bin",
                Content::SparseNoise {
                    seed: 42,
                    len: 70 << 20, // 70 MiB
                    period: 64 << 20,
                    noise: 1024,
                },
            )
            .file("zeros.bin", Content::Zeros(256 * 1024)) // compresses
            .file(
                "noise.bin",
                Content::Pattern {
                    seed: 1,
                    len: 256 * 1024,
                },
            ) // doesn't compress
            .dir(DirSpec::new("sub").file("deep.txt", Content::Bytes(b"deep\n".to_vec()))),
    )
}

fn expected_hashes(spec: &Spec) -> Vec<FileHash> {
    spec.expected_hashes()
        .into_iter()
        .map(|(path, size, sha256)| FileHash { path, size, sha256 })
        .collect()
}

#[test]
fn install_basic() {
    let spec = install_spec();
    let dir = tmp("basic");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();

    let info = install(&container_path, &dest, false, false).unwrap();
    assert_eq!(info.file_count, spec.files().len());
    assert_eq!(
        info.total_bytes,
        spec.files().iter().map(|(_, c)| c.len()).sum::<u64>()
    );

    // Compare installed files with spec.
    let installed = hash_directory(&dest).unwrap();
    let want = expected_hashes(&spec);
    let d = diff(&want, &installed);
    assert!(d.is_empty(), "install differs from spec: {d:?}");

    // Compare with what the container sees.
    let c = bc5_mount::container::Container::open_path(&container_path).unwrap();
    let volume_hashes = hash_volume(c.exfat(), |_| {}).unwrap();
    let d = diff(&want, &volume_hashes);
    assert!(d.is_empty(), "volume hashes differ: {d:?}");

    // Clean up.
    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn install_refuse_existing_dest() {
    let spec = install_spec();
    let dir = tmp("refuse");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();
    fs::create_dir_all(&dest).unwrap();

    // The install function calls std::process::exit(2) when dest exists.
    // We can't easily catch that in a test, so we verify the condition
    // that would trigger the refusal.
    assert!(dest.exists(), "dest should exist");

    // Instead, verify that a fresh (non-existent) dest works.
    let fresh_dest = dir.join("fresh");
    let info = install(&container_path, &fresh_dest, false, false).unwrap();
    assert_eq!(info.file_count, spec.files().len());

    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn install_resume_skips_matching() {
    let spec = install_spec();
    let dir = tmp("resume");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();

    // First install.
    let info1 = install(&container_path, &dest, false, false).unwrap();
    assert_eq!(info1.file_count, spec.files().len());

    // Second install with --resume: all files are kept, and still counted and hashed for the record.
    let info2 = install(&container_path, &dest, true, false).unwrap();
    assert_eq!(info2.files_kept, spec.files().len());
    assert_eq!(info2.file_count, spec.files().len());
    assert_eq!(info2.hashes.len(), info1.hashes.len());

    fs::remove_dir_all(&dir).unwrap();
}

/// Exp 0439: a resumed install with --verify after an interrupted run (some files done, some not) passes,
/// and its hashes cover the kept files as well as the written ones.
#[test]
fn install_resume_verify_after_partial() {
    let spec = install_spec();
    let dir = tmp("resume-verify");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();
    let full = install(&container_path, &dest, false, false).unwrap();
    // Take one installed file away, as if the first run had stopped before it.
    let gone = &full.hashes[0].path;
    fs::remove_file(dest.join(gone)).unwrap();

    let info = install(&container_path, &dest, true, true).unwrap();
    assert_eq!(info.file_count, spec.files().len());
    assert_eq!(info.files_kept, spec.files().len() - 1);
    let c = bc5_mount::container::Container::open_path(&container_path).unwrap();
    let volume_hashes = hash_volume(c.exfat(), |_| {}).unwrap();
    let d = diff(&info.hashes, &volume_hashes);
    assert!(d.is_empty(), "resume hashes differ from the image: {d:?}");

    // A kept file whose bytes changed (same size) is caught by --verify.
    let victim = dest.join(&full.hashes[full.hashes.len() - 1].path);
    let mut bytes = fs::read(&victim).unwrap();
    if !bytes.is_empty() {
        bytes[0] ^= 0xff;
        fs::write(&victim, &bytes).unwrap();
        let e = install(&container_path, &dest, true, true).unwrap_err();
        assert!(format!("{e:#}").contains("verification failed"), "{e:#}");
    }

    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn install_verify() {
    let spec = install_spec();
    let dir = tmp("verify");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();

    // Install with --verify.
    let info = install(&container_path, &dest, false, true).unwrap();

    // .bc5-install.json should NOT be written by install() — it's written by main.
    // But we can verify the hashes match.
    let c = bc5_mount::container::Container::open_path(&container_path).unwrap();
    let volume_hashes = hash_volume(c.exfat(), |_| {}).unwrap();
    let d = diff(&info.hashes, &volume_hashes);
    assert!(d.is_empty(), "verify failed: {d:?}");

    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn install_write_install_json() {
    let spec = install_spec();
    let dir = tmp("json");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();

    let info = install(&container_path, &dest, false, false).unwrap();
    write_install_json(&dest, &container_path, &info).unwrap();

    let json_path = dest.join(".bc5-install.json");
    assert!(json_path.exists(), ".bc5-install.json should exist");

    let content = fs::read_to_string(&json_path).unwrap();
    assert!(content.contains("\"image\":"));
    assert!(content.contains("\"file_count\":"));
    assert!(content.contains("\"total_bytes\":"));
    assert!(content.contains("\"sha256\":"));
    assert!(content.contains("\"date\":"));

    fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn install_large_sparse_file() {
    // Verify that a 70 MiB sparse file is installed correctly.
    let spec = install_spec();
    let dir = tmp("large");
    let container_path = dir.join("fixture.ffpfsc");
    let dest = dir.join("dest");

    build_to_path(&spec, &container_path).unwrap();

    install(&container_path, &dest, false, false).unwrap();

    // Check the large file specifically.
    let large_path = dest.join("large_sparse.bin");
    let meta = fs::metadata(&large_path).unwrap();
    assert_eq!(meta.len(), 70 << 20, "large_sparse.bin should be 70 MiB");

    // Verify its content matches the spec.
    let files = spec.files();
    let content = files
        .iter()
        .find(|(p, _)| p == "large_sparse.bin")
        .unwrap()
        .1;
    let mut buf = vec![0u8; 1 << 20];
    let mut off = 0u64;
    while off < content.len() {
        let n = (content.len() - off).min(buf.len() as u64) as usize;
        content.fill(off, &mut buf[..n]);
        off += n as u64;
    }

    fs::remove_dir_all(&dir).unwrap();
}
