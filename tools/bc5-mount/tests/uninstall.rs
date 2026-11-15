// SPDX-License-Identifier: GPL-2.0-only
//! Tests for the `uninstall` subcommand (experiment 0420): what it removes, what it refuses.
//! Every install here is synthetic: a directory with a few files and a record, under a test root.

use std::fs;
use std::path::{Path, PathBuf};

use bc5_mount::install::json_escape;
use bc5_mount::uninstall::{check, parse_record, read_record, uninstall, Refused, RECORD};

fn tmp(name: &str) -> PathBuf {
    let dir = PathBuf::from(env!("CARGO_TARGET_TMPDIR"))
        .join(format!("uninstall-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    dir
}

fn record_text(image: &str) -> String {
    format!(
        "{{\n  \"image\": \"{}\",\n  \"image_size\": 10,\n  \"file_count\": 2,\n  \"total_bytes\": 11,\n  \"sha256\": {{\n    \"a.bin\": \"00\",\n    \"sub/b.bin\": \"11\"\n  }},\n  \"date\": \"1\"\n}}\n",
        json_escape(image)
    )
}

/// A synthetic install `<root>/<name>` with two files and a record naming `image`.
fn make_install(root: &Path, name: &str, image: &str) -> PathBuf {
    let d = root.join(name);
    fs::create_dir_all(d.join("sub")).unwrap();
    fs::write(d.join("a.bin"), b"hello").unwrap();
    fs::write(d.join("sub").join("b.bin"), b"world!").unwrap();
    fs::write(d.join(RECORD), record_text(image)).unwrap();
    d
}

fn refused(r: anyhow::Result<bc5_mount::uninstall::Removed>) -> String {
    let e = r.expect_err("must be refused");
    e.downcast_ref::<Refused>()
        .unwrap_or_else(|| panic!("not a refusal: {e}"))
        .0
        .clone()
}

#[test]
fn removes_a_valid_install_and_counts_what_it_freed() {
    let root = tmp("valid");
    let image = root.join("src.ffpfsc");
    fs::write(&image, b"img").unwrap();
    let d = make_install(&root, "PPSA00001", image.to_str().unwrap());
    let r = uninstall(&d, &root, false).unwrap();
    assert!(!d.exists());
    assert!(image.exists(), "the source image must stay");
    assert!(r.image_present);
    assert_eq!(r.record.file_count, 2);
    assert_eq!(r.record.total_bytes, 11);
    // a.bin 5 + b.bin 6 + the record
    assert_eq!(
        r.bytes,
        11 + record_text(image.to_str().unwrap()).len() as u64
    );
    assert_eq!(r.entries, 5); // the directory, sub, a.bin, b.bin, the record
    assert!(root.exists(), "the root stays");
}

/// An install copied from a read-only mount keeps the image's modes: directories 0555, files 0444
/// (the maintainer's adopted install, 2026-11-15). It must still be removed, and a link inside it
/// must not lend its target write permission.
#[cfg(unix)]
#[test]
fn removes_an_install_with_read_only_directories() {
    use std::os::unix::fs::PermissionsExt;
    let root = tmp("readonly");
    let outside = root.join("outside");
    fs::create_dir_all(&outside).unwrap();
    fs::set_permissions(&outside, fs::Permissions::from_mode(0o555)).unwrap();
    let d = make_install(&root, "PPSA00009", "/nowhere/game.pkg");
    std::os::unix::fs::symlink(&outside, d.join("sub").join("link")).unwrap();
    for f in [d.join("a.bin"), d.join("sub").join("b.bin")] {
        fs::set_permissions(&f, fs::Permissions::from_mode(0o444)).unwrap();
    }
    fs::set_permissions(d.join("sub"), fs::Permissions::from_mode(0o555)).unwrap();
    let r = uninstall(&d, &root, false).unwrap();
    assert!(!d.exists());
    assert_eq!(r.entries, 6); // the directory, sub, a.bin, b.bin, the link, the record
    assert!(outside.exists(), "a link's target stays");
    let mode = fs::metadata(&outside).unwrap().permissions().mode() & 0o777;
    assert_eq!(mode, 0o555, "a link's target keeps its mode");
    fs::set_permissions(&outside, fs::Permissions::from_mode(0o755)).unwrap();
}

#[test]
fn dry_run_removes_nothing() {
    let root = tmp("dry");
    let d = make_install(&root, "PPSA00002", "/nowhere/game.pkg");
    let r = uninstall(&d, &root, true).unwrap();
    assert!(d.join("a.bin").exists());
    assert!(!r.image_present);
}

#[test]
fn reports_a_missing_image() {
    let root = tmp("missing");
    let d = make_install(&root, "PPSA00003", "/nowhere/game.pkg");
    let r = uninstall(&d, &root, false).unwrap();
    assert!(!r.image_present);
    assert_eq!(r.record.image, "/nowhere/game.pkg");
}

#[test]
fn refuses_the_root_itself() {
    let root = tmp("root");
    fs::write(root.join(RECORD), record_text("/x.pkg")).unwrap();
    assert!(refused(uninstall(&root, &root, false)).contains("games root itself"));
    assert!(root.join(RECORD).exists());
}

#[test]
fn refuses_a_deeper_path() {
    let root = tmp("deep");
    let d = make_install(&root, "PPSA00004", "/x.pkg");
    let inner = make_install(&d, "inner", "/x.pkg");
    assert!(refused(uninstall(&inner, &root, false)).contains("directly under"));
    assert!(inner.exists());
}

#[test]
fn refuses_a_path_outside_the_root() {
    let base = tmp("outside");
    let root = base.join("games");
    fs::create_dir_all(&root).unwrap();
    let other = make_install(&base, "elsewhere", "/x.pkg");
    assert!(refused(uninstall(&other, &root, false)).contains("directly under"));
    assert!(other.exists());
}

#[test]
fn refuses_a_parent_component() {
    let root = tmp("dotdot");
    let d = make_install(&root, "PPSA00005", "/x.pkg");
    let via = root.join("PPSA00005").join("..").join("PPSA00005");
    assert!(refused(uninstall(&via, &root, false)).contains(".."));
    assert!(d.exists());
}

#[test]
fn refuses_a_folder_without_a_record() {
    let root = tmp("norecord");
    let d = root.join("PPSA00006");
    fs::create_dir_all(&d).unwrap();
    fs::write(d.join("a.bin"), b"x").unwrap();
    assert!(refused(uninstall(&d, &root, false)).contains("holds no"));
    assert!(d.join("a.bin").exists());
}

#[test]
fn refuses_a_broken_record() {
    let root = tmp("broken");
    let d = make_install(&root, "PPSA00007", "/x.pkg");
    fs::write(d.join(RECORD), "{\n  \"image\": 5\n}\n").unwrap();
    assert!(refused(uninstall(&d, &root, false)).contains("not an install record"));
    assert!(d.exists());
}

#[test]
fn refuses_a_plain_file() {
    let root = tmp("file");
    let f = root.join("PPSA21567 - game.ffpfsc");
    fs::write(&f, b"image").unwrap();
    assert!(refused(uninstall(&f, &root, false)).contains("not a directory"));
    assert!(f.exists());
}

#[test]
fn refuses_a_missing_path() {
    let root = tmp("absent");
    let r = uninstall(&root.join("nothing"), &root, false);
    assert!(r.is_err());
}

#[cfg(unix)]
#[test]
fn refuses_a_link_to_a_valid_install() {
    let root = tmp("link");
    let real = make_install(&root, "PPSA00008", "/x.pkg");
    let link = root.join("PPSA00009");
    std::os::unix::fs::symlink(&real, &link).unwrap();
    assert!(refused(uninstall(&link, &root, false)).contains("symbolic link"));
    assert!(real.join("a.bin").exists());
}

#[cfg(unix)]
#[test]
fn a_link_inside_an_install_is_removed_as_a_link() {
    let base = tmp("inner-link");
    let root = base.join("games");
    fs::create_dir_all(&root).unwrap();
    let keep = base.join("keep");
    fs::create_dir_all(&keep).unwrap();
    fs::write(keep.join("precious.txt"), b"keep me").unwrap();
    let d = make_install(&root, "PPSA00010", "/x.pkg");
    std::os::unix::fs::symlink(&keep, d.join("saves")).unwrap();
    uninstall(&d, &root, false).unwrap();
    assert!(!d.exists());
    assert!(
        keep.join("precious.txt").exists(),
        "a link's target must stay"
    );
}

#[cfg(unix)]
#[test]
fn refuses_a_record_that_is_a_link() {
    let root = tmp("recordlink");
    let d = make_install(&root, "PPSA00011", "/x.pkg");
    let elsewhere = root.join("rec.json");
    fs::rename(d.join(RECORD), &elsewhere).unwrap();
    std::os::unix::fs::symlink(&elsewhere, d.join(RECORD)).unwrap();
    assert!(refused(uninstall(&d, &root, false)).contains("not a plain file"));
    assert!(d.exists());
}

#[test]
fn parses_what_install_writes_and_nothing_else() {
    let r = parse_record(&record_text("/a/b \"q\" \\ c.pkg")).unwrap();
    assert_eq!(r.image, "/a/b \"q\" \\ c.pkg");
    assert_eq!((r.file_count, r.total_bytes), (2, 11));
    assert!(parse_record("").is_none());
    assert!(parse_record("{}").is_none());
    assert!(
        parse_record("{\n  \"image\": \"\",\n  \"file_count\": 1,\n  \"total_bytes\": 1\n}")
            .is_none()
    );
    assert!(parse_record("{\n  \"image\": \"/x\",\n  \"file_count\": 1\n}").is_none());
    // a file named `"image":` inside the sha256 map is not the key
    let t = "{\n  \"file_count\": 1,\n  \"total_bytes\": 1,\n  \"sha256\": {\n    \"image\": \"/fake\"\n  }\n}\n";
    assert!(parse_record(t).is_none());
}

#[test]
fn reads_the_record_of_a_real_install_written_by_write_install_json() {
    use bc5_mount::fixture::{build_to_path, Content, DirSpec, Spec};
    use bc5_mount::install::{install, write_install_json};
    let base = tmp("real");
    // A name with a quote (a backslash on Windows would be a separator, and Windows refuses quotes).
    let image = base.join(if cfg!(unix) {
        "we \"quote\" \\ it.ffpfsc"
    } else {
        "we 'quote' it.ffpfsc"
    });
    let spec = Spec::new(
        "uninstall-test",
        DirSpec::new("")
            .dir(DirSpec::new("sce_sys").file("param.json", Content::Bytes(b"{}\n".to_vec())))
            .file("eboot.bin", Content::Bytes(b"not a real binary".to_vec())),
    );
    build_to_path(&spec, &image).unwrap();
    let root = base.join("games");
    fs::create_dir_all(&root).unwrap();
    let dest = root.join("TEST00001");
    let info = install(&image, &dest, false, true).unwrap();
    write_install_json(&dest, &image, &info).unwrap();
    let rec = read_record(&dest).unwrap();
    assert_eq!(rec.image, image.display().to_string());
    assert_eq!(rec.file_count, info.file_count as u64);
    assert!(check(&dest, &root).is_ok());
    let r = uninstall(&dest, &root, false).unwrap();
    assert!(!dest.exists() && image.exists() && r.image_present);
}

#[test]
fn install_to_a_bare_name_checks_space_in_the_current_directory() {
    // statvfs("") failed for a destination without a directory part; an empty parent is `.` now.
    use bc5_mount::fixture::{build_to_path, Content, DirSpec, Spec};
    use bc5_mount::install::install;
    let base = tmp("bare");
    let image = base.join("i.ffpfsc");
    let spec = Spec::new(
        "bare",
        DirSpec::new("").file("x.bin", Content::Bytes(b"x".to_vec())),
    );
    build_to_path(&spec, &image).unwrap();
    let cwd = std::env::current_dir().unwrap();
    std::env::set_current_dir(&base).unwrap();
    let r = install(&image, Path::new("bare-dest"), false, false);
    std::env::set_current_dir(cwd).unwrap();
    r.unwrap();
    assert!(base.join("bare-dest").join("x.bin").exists());
}
