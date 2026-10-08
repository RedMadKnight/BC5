// SPDX-License-Identifier: GPL-2.0-only
//! Synthetic PS5 packages for tests: a [`Spec`] tree becomes a data-first
//! inner image (stored blocks, entropy-only "Kraken" blocks in their memcpy
//! form, sparse regions for all-zero files), its naps layout, a plaintext
//! outer PFS and the `\x7fFIH` header. Nothing here comes from a real package;
//! the shapes follow `docs/formats/ps5pkg.md`.

use std::io::{self, Seek, SeekFrom, Write};

use crate::error::Result;
use crate::fixture::{Content, Spec, FIXED_TIMESTAMP};
use crate::pfs::{
    encode_dirent, DIRENT_DIR, DIRENT_DOT, DIRENT_DOTDOT, DIRENT_FILE, INODE_MODE_DIR,
    INODE_MODE_FILE, INODE_PERM_RX, MAGIC, MODE_CASE_INSENSITIVE, VERSION_PS5,
};
use crate::pkg::naps::{
    encode_layout, Cblock, Counts, FileOffset, KIND_MOUNT, OUTER_BLOCK_SIZE, UBLOCK_SIZE,
};

/// Outer and inner PFS block size.
const BS: u64 = OUTER_BLOCK_SIZE;
/// Inner inode size (the compact layout).
const INNER_INODE_SIZE: usize = 0xa8;
/// Outer inode size (the signed layout).
const OUTER_INODE_SIZE: usize = 0x2c8;
/// Inner superblock mode: compact inodes, case-insensitive names.
const INNER_MODE: u16 = 0x18;
/// The seed of a plaintext outer image.
const PLAINTEXT_SEED: &[u8; 16] = b"PPSPLAIN-NOAUTH!";
/// Blocks of a file this long or shorter are written in the memcpy Kraken
/// form; longer blocks are stored as they are (a full 256 KiB block cannot
/// grow by the chunk headers, see the naps record's length field).
const MEMCPY_LIMIT: u64 = 0x3fff0;
/// Entropy-chunk header in its memcpy form: type 0, 24-bit length.
fn memcpy_header(len: usize) -> [u8; 3] {
    [(len >> 16) as u8, (len >> 8) as u8, len as u8]
}

/// What the writer produced, for assertions.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PkgBuildInfo {
    /// Total package length.
    pub len: u64,
    /// Stored length of the inner image.
    pub image_stored_len: u64,
    /// Logical length of the inner image.
    pub mount: u64,
    /// Blocks: stored, memcpy-Kraken, sparse.
    pub blocks: (usize, usize, usize),
}

struct Node {
    path: String,
    name: String,
    parent: usize,
    is_dir: bool,
    content: Option<Content>,
    logical: u64,
    size: u64,
    ino: u32,
}

fn put(b: &mut [u8], off: usize, v: &[u8]) {
    b[off..off + v.len()].copy_from_slice(v);
}

/// Writes a package for `spec` to `out`.
#[allow(clippy::too_many_lines)]
pub fn write_pkg<W: Write + Seek>(spec: &Spec, out: &mut W) -> Result<PkgBuildInfo> {
    // ---- the inner tree: super-root, uroot, then the spec's dirs and files ----
    let mut nodes = vec![
        Node {
            path: String::new(),
            name: String::new(),
            parent: 0,
            is_dir: true,
            content: None,
            logical: 0,
            size: 0,
            ino: 0,
        },
        Node {
            path: String::new(),
            name: "uroot".into(),
            parent: 0,
            is_dir: true,
            content: None,
            logical: 0,
            size: 0,
            ino: 1,
        },
    ];
    let mut dirs = spec.dirs();
    dirs.sort();
    for d in &dirs {
        let (parent_path, name) = split(d);
        let parent = nodes
            .iter()
            .position(|n| n.is_dir && n.ino >= 1 && n.path == parent_path)
            .expect("parent dir");
        let ino = nodes.len() as u32;
        nodes.push(Node {
            path: d.clone(),
            name: name.to_owned(),
            parent,
            is_dir: true,
            content: None,
            logical: 0,
            size: 0,
            ino,
        });
    }
    let mut files = spec.files();
    files.sort_by(|a, b| a.0.cmp(&b.0));
    for (path, content) in &files {
        let (parent_path, name) = split(path);
        let parent = nodes
            .iter()
            .position(|n| n.is_dir && n.ino >= 1 && n.path == parent_path)
            .expect("parent dir");
        let ino = nodes.len() as u32;
        nodes.push(Node {
            path: path.clone(),
            name: name.to_owned(),
            parent,
            is_dir: false,
            content: Some((*content).clone()),
            logical: 0,
            size: content.len(),
            ino,
        });
    }

    // ---- logical layout: file data from 0, 16-byte aligned; metadata on the next 64 KiB ----
    let mut logical = 0u64;
    let mut fidx: Vec<FileOffset> = Vec::new();
    for n in nodes.iter_mut().filter(|n| !n.is_dir) {
        n.logical = logical;
        if n.size > 0 {
            let sparse = matches!(n.content, Some(Content::Zeros(_)));
            fidx.push(FileOffset {
                kind: if sparse { KIND_MOUNT } else { 0 },
                offset: logical,
            });
            logical += n.size;
            logical = logical.next_multiple_of(16);
        }
    }
    let meta_base = logical.next_multiple_of(BS);
    fidx.push(FileOffset {
        kind: 0,
        offset: meta_base,
    });
    // metadata: superblock block, inode table block(s), one block per directory
    let inodes_per_block = BS as usize / INNER_INODE_SIZE;
    let inode_blocks = nodes.len().div_ceil(inodes_per_block) as u64;
    let dir_count = nodes.iter().filter(|n| n.is_dir).count() as u64;
    let mut dir_block = meta_base + BS * (1 + inode_blocks);
    let mut dirents_of: Vec<Vec<u8>> = Vec::new();
    for i in 0..nodes.len() {
        if !nodes[i].is_dir {
            dirents_of.push(Vec::new());
            continue;
        }
        let parent_ino = nodes[nodes[i].parent].ino;
        let mut d = Vec::new();
        d.extend_from_slice(&encode_dirent(nodes[i].ino, DIRENT_DOT, "."));
        d.extend_from_slice(&encode_dirent(parent_ino, DIRENT_DOTDOT, ".."));
        for (j, c) in nodes.iter().enumerate() {
            if j != 0 && c.parent == i && (i != 0 || c.ino == 1) {
                d.extend_from_slice(&encode_dirent(
                    c.ino,
                    if c.is_dir { DIRENT_DIR } else { DIRENT_FILE },
                    &c.name,
                ));
            }
        }
        nodes[i].logical = dir_block;
        nodes[i].size = d.len() as u64;
        dirents_of.push(d);
        dir_block += BS;
    }
    let mount = (meta_base + BS * (1 + inode_blocks + dir_count)).next_multiple_of(UBLOCK_SIZE);
    fidx.push(FileOffset {
        kind: KIND_MOUNT,
        offset: mount,
    });

    // the metadata region's bytes
    let mut meta = vec![0u8; (mount - meta_base) as usize];
    put(&mut meta, 0, &VERSION_PS5.to_le_bytes());
    put(&mut meta, 8, &MAGIC.to_le_bytes());
    meta[0x1a] = 1;
    put(&mut meta, 0x1c, &INNER_MODE.to_le_bytes());
    put(&mut meta, 0x20, &(BS as u32).to_le_bytes());
    put(&mut meta, 0x28, &1u64.to_le_bytes());
    put(&mut meta, 0x30, &(nodes.len() as u64).to_le_bytes());
    put(&mut meta, 0x38, &(mount / BS).to_le_bytes());
    put(&mut meta, 0x40, &inode_blocks.to_le_bytes());
    for (i, n) in nodes.iter().enumerate() {
        let at = BS as usize
            + (i / inodes_per_block) * BS as usize
            + (i % inodes_per_block) * INNER_INODE_SIZE;
        let rec = &mut meta[at..at + INNER_INODE_SIZE];
        let mode = if n.is_dir {
            INODE_MODE_DIR | INODE_PERM_RX
        } else {
            INODE_MODE_FILE | INODE_PERM_RX
        };
        put(rec, 0, &mode.to_le_bytes());
        put(rec, 2, &1u16.to_le_bytes());
        put(rec, 8, &n.size.to_le_bytes());
        put(rec, 0x10, &n.size.to_le_bytes());
        for t in 0..4 {
            put(rec, 0x18 + t * 8, &FIXED_TIMESTAMP.to_le_bytes());
        }
        put(rec, 0x60, &n.logical.to_le_bytes());
    }
    for (i, d) in dirents_of.iter().enumerate() {
        if nodes[i].is_dir {
            let at = (nodes[i].logical - meta_base) as usize;
            put(&mut meta, at, d);
        }
    }

    // ---- the stored image and the records ----
    let mut stored: Vec<u8> = Vec::new();
    let mut records = vec![Cblock {
        is_run_base: true,
        ..Cblock::default()
    }];
    let mut first_record_of_ublock: Vec<u32> = Vec::new();
    let mut counts = (0usize, 0usize, 0usize);
    let mut pos = 0u64;
    let bounds: Vec<u64> = fidx.iter().map(|f| f.offset).collect();
    let mut buf = Vec::new();
    while pos < mount {
        let entry = fidx.iter().find(|f| f.offset == pos).copied();
        let next_bound = bounds.iter().copied().find(|&b| b > pos).unwrap_or(mount);
        if let Some(e) = entry.filter(|e| e.kind == KIND_MOUNT && e.offset < mount) {
            // a sparse region: no records until the next boundary
            let mut p = pos;
            while p < next_bound {
                if p % UBLOCK_SIZE == 0 {
                    first_record_of_ublock.push(records.len() as u32);
                }
                let len = UBLOCK_SIZE.min(next_bound - p);
                counts.2 += 1;
                p += len;
            }
            let _ = e;
            pos = next_bound;
            continue;
        }
        let len = UBLOCK_SIZE.min(next_bound - pos);
        buf.clear();
        buf.resize(len as usize, 0);
        if pos >= meta_base {
            let s = (pos - meta_base) as usize;
            buf.copy_from_slice(&meta[s..s + len as usize]);
        } else {
            let n = nodes
                .iter()
                .find(|n| !n.is_dir && n.size > 0 && n.logical <= pos && pos < n.logical + n.size)
                .expect("file for block");
            let within = pos - n.logical;
            let take = (n.size - within).min(len) as usize;
            n.content
                .as_ref()
                .expect("content")
                .fill(within, &mut buf[..take]);
        }
        if pos % UBLOCK_SIZE == 0 {
            first_record_of_ublock.push(records.len() as u32);
        }
        let rec_pos = (stored.len() as u64 % UBLOCK_SIZE) as u32;
        let even_comp;
        if len <= MEMCPY_LIMIT {
            counts.1 += 1;
            let c0 = (len as usize).min(0x20000);
            stored.extend_from_slice(&memcpy_header(c0));
            stored.extend_from_slice(&buf[..c0]);
            even_comp = c0 as u32 + 3;
            if len as usize > c0 {
                stored.extend_from_slice(&memcpy_header(len as usize - c0));
                stored.extend_from_slice(&buf[c0..]);
            }
        } else {
            counts.0 += 1;
            stored.extend_from_slice(&buf);
            even_comp = (len as u32).min(0x20000);
        }
        records.push(Cblock {
            is_run_base: false,
            coffset_mod: rec_pos,
            clen_even_minus1: even_comp - 1,
            kde_predictor: 0,
            shuffle_idx: 0,
            coffset_start_256k: 0,
        });
        pos += len;
    }
    // the record after the last block marks where its stored bytes end
    records.push(Cblock {
        is_run_base: false,
        coffset_mod: (stored.len() as u64 % UBLOCK_SIZE) as u32,
        ..Cblock::default()
    });
    let image_stored_len = stored.len() as u64;
    let image_blocks = image_stored_len.div_ceil(BS).max(1);
    stored.resize((image_blocks * BS) as usize, 0);
    let layout = encode_layout(
        &Counts {
            num_files: fidx.len() as u32,
            compression_type: 2,
            num_keys: 1,
            num_shuffle: 0,
            num_ublocks: mount.div_ceil(UBLOCK_SIZE) as u32,
            num_outer_blocks: image_blocks as u32,
            num_cblock_info: records.len() as u32,
        },
        &fidx,
        &first_record_of_ublock,
        &records,
    );
    let layout_len = layout.len() as u64;
    let layout_blocks = layout_len.div_ceil(BS).max(1);

    // ---- the outer PFS: image, layout, superblock, inode table, root dirents, uroot dirents ----
    let pfs_offset = BS;
    let sb_block = image_blocks + layout_blocks;
    let outer_blocks = sb_block + 4;
    let mut outer_inodes = vec![[0u8; OUTER_INODE_SIZE]; 4];
    let outer = |rec: &mut [u8], mode: u16, size: u64, first: u64, blocks: u64| {
        put(rec, 0, &mode.to_le_bytes());
        put(rec, 2, &1u16.to_le_bytes());
        put(rec, 8, &size.to_le_bytes());
        put(rec, 16, &size.to_le_bytes());
        put(rec, 0x60, &(blocks as u32).to_le_bytes());
        for j in 0..12usize {
            let p: i32 = if (j as u64) < blocks {
                (first + j as u64) as i32
            } else {
                -1
            };
            put(rec, 0x64 + j * 36 + 32, &p.to_le_bytes());
        }
    };
    let root_dirents = [
        encode_dirent(0, DIRENT_DOT, "."),
        encode_dirent(0, DIRENT_DOTDOT, ".."),
        encode_dirent(1, DIRENT_DIR, "uroot"),
    ]
    .concat();
    let uroot_dirents = [
        encode_dirent(1, DIRENT_DOT, "."),
        encode_dirent(0, DIRENT_DOTDOT, ".."),
        encode_dirent(2, DIRENT_FILE, "pfs_image.dat"),
        encode_dirent(3, DIRENT_FILE, "naps_pkg_layout.dat"),
    ]
    .concat();
    outer(
        &mut outer_inodes[0],
        INODE_MODE_DIR | INODE_PERM_RX,
        root_dirents.len() as u64,
        sb_block + 2,
        1,
    );
    outer(
        &mut outer_inodes[1],
        INODE_MODE_DIR | INODE_PERM_RX,
        uroot_dirents.len() as u64,
        sb_block + 3,
        1,
    );
    outer(
        &mut outer_inodes[2],
        INODE_MODE_FILE | INODE_PERM_RX,
        image_stored_len,
        0,
        image_blocks,
    );
    outer(
        &mut outer_inodes[3],
        INODE_MODE_FILE | INODE_PERM_RX,
        layout_len,
        image_blocks,
        layout_blocks,
    );
    let mut sb = vec![0u8; BS as usize];
    put(&mut sb, 0, &VERSION_PS5.to_le_bytes());
    put(&mut sb, 8, &MAGIC.to_le_bytes());
    sb[0x1a] = 1;
    put(&mut sb, 0x1c, &MODE_CASE_INSENSITIVE.to_le_bytes());
    put(&mut sb, 0x20, &(BS as u32).to_le_bytes());
    put(&mut sb, 0x28, &1u64.to_le_bytes());
    put(&mut sb, 0x30, &4u64.to_le_bytes());
    put(&mut sb, 0x38, &outer_blocks.to_le_bytes());
    put(&mut sb, 0x40, &1u64.to_le_bytes());
    put(&mut sb, 0x370, PLAINTEXT_SEED);

    // ---- the header ----
    let mut head = vec![0u8; pfs_offset as usize];
    put(&mut head, 0, b"\x7fFIH");
    put(&mut head, 4, &[1, 0, 0, 3]);
    put(&mut head, 0x10, &pfs_offset.to_le_bytes());
    put(&mut head, 0x18, &(outer_blocks * BS).to_le_bytes());
    put(&mut head, 0x20, &(pfs_offset + sb_block * BS).to_le_bytes());
    put(&mut head, 0x28, &BS.to_le_bytes());

    out.seek(SeekFrom::Start(0))?;
    out.write_all(&head)?;
    out.write_all(&stored)?;
    write_padded(out, &layout, layout_blocks * BS)?;
    out.write_all(&sb)?;
    let mut table = vec![0u8; BS as usize];
    for (i, rec) in outer_inodes.iter().enumerate() {
        put(&mut table, i * OUTER_INODE_SIZE, rec);
    }
    out.write_all(&table)?;
    write_padded(out, &root_dirents, BS)?;
    write_padded(out, &uroot_dirents, BS)?;
    out.flush()?;
    Ok(PkgBuildInfo {
        len: pfs_offset + outer_blocks * BS,
        image_stored_len,
        mount,
        blocks: counts,
    })
}

fn write_padded<W: Write>(out: &mut W, data: &[u8], len: u64) -> io::Result<()> {
    out.write_all(data)?;
    let pad = vec![0u8; (len - data.len() as u64) as usize];
    out.write_all(&pad)
}

fn split(path: &str) -> (String, &str) {
    match path.rsplit_once('/') {
        Some((dir, name)) => (dir.to_owned(), name),
        None => (String::new(), path),
    }
}
