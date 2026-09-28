// SPDX-License-Identifier: GPL-2.0-only
//! Wraps an exFAT image in a PFSC stream and a PFS v2 image with the fixed
//! four-inode layout of `.ffpfsc` (`docs/formats/ffpfsc.md` §1): superblock,
//! inode table, super-root, flat path table, (empty block), uroot, payload.

use std::io::{self, Seek, SeekFrom, Write};

use crate::error::{Error, Result};
use crate::pfs::{
    encode_dirent, fpt_hash, Inode, Superblock, DIRENT_DIR, DIRENT_DOT, DIRENT_DOTDOT, DIRENT_FILE,
    INODE_FLAG_COMPRESSED, INODE_FLAG_INTERNAL, INODE_FLAG_READONLY, INODE_MODE_DIR,
    INODE_MODE_FILE, INODE_PERM_RX, INODE_SIZE, MAGIC, MODE_CASE_INSENSITIVE, VERSION_PS5,
};

use super::exfat_writer::ExfatPlan;
use super::pfsc_writer::PfscEncoder;
use super::{BuildInfo, Spec, FIXED_TIMESTAMP};

/// Block index of the super-root directory.
pub const SUPER_ROOT_BLOCK: u32 = 2;
/// Block index of the flat path table.
pub const FPT_BLOCK: u32 = 3;
/// Block index of the user root directory (block 4 is left empty).
pub const UROOT_BLOCK: u32 = 5;
/// Block index where the payload starts.
pub const PAYLOAD_BLOCK: u32 = 6;
/// Inode number of the payload.
pub const PAYLOAD_INODE: u32 = 3;

fn inode(
    mode: u16,
    nlink: u16,
    flags: u32,
    size: u64,
    size_compressed: u64,
    blocks: u32,
    first: u32,
) -> Inode {
    let mut db = [-1i32; 12];
    db[0] = i32::try_from(first).expect("fixture block indices are small");
    Inode {
        mode,
        nlink,
        flags,
        size,
        size_compressed,
        time: FIXED_TIMESTAMP,
        blocks,
        db,
        ib: [-1; 5],
    }
}

/// Writes a complete container for `spec` into `out` at its current position
/// (normally 0).
pub fn write_container<W: Write + Seek>(spec: &Spec, out: &mut W) -> Result<BuildInfo> {
    let bs = spec.pfs_block_size;
    if !bs.is_power_of_two() || !(0x1000..=0x10_0000).contains(&bs) {
        return Err(Error::Unsupported(format!("PFS block size {bs:#x}")));
    }
    if !spec.inner_name.is_ascii()
        || spec.inner_name.contains(['/', '\\', '\0'])
        || spec.inner_name.is_empty()
    {
        return Err(Error::Unsupported(format!(
            "inner name {:?} must be plain ASCII",
            spec.inner_name
        )));
    }
    let bs64 = u64::from(bs);
    let plan = ExfatPlan::new(spec)?;
    let exfat_len = plan.image_len();
    let base = out.stream_position()?;

    let mut sb = Superblock {
        version: VERSION_PS5,
        magic: MAGIC,
        mode: if spec.case_insensitive {
            MODE_CASE_INSENSITIVE
        } else {
            0
        },
        block_size: bs,
        nblock: 1,
        ndinode: 4,
        ndblock: 0,
        ndinodeblock: 1,
    };
    let fpt = {
        let mut v = fpt_hash(&format!("/{}", spec.inner_name), spec.case_insensitive)
            .to_le_bytes()
            .to_vec();
        v.extend_from_slice(&PAYLOAD_INODE.to_le_bytes());
        v
    };
    let mut super_root = encode_dirent(1, DIRENT_FILE, "flat_path_table");
    super_root.extend(encode_dirent(2, DIRENT_DIR, "uroot"));
    let mut uroot = encode_dirent(2, DIRENT_DOT, ".");
    uroot.extend(encode_dirent(2, DIRENT_DOTDOT, ".."));
    uroot.extend(encode_dirent(PAYLOAD_INODE, DIRENT_FILE, &spec.inner_name));

    let mut inodes = [
        inode(
            INODE_MODE_DIR | INODE_PERM_RX,
            1,
            INODE_FLAG_INTERNAL | INODE_FLAG_READONLY,
            bs64,
            bs64,
            1,
            SUPER_ROOT_BLOCK,
        ),
        inode(
            INODE_MODE_FILE | INODE_PERM_RX,
            1,
            INODE_FLAG_INTERNAL | INODE_FLAG_READONLY,
            fpt.len() as u64,
            fpt.len() as u64,
            1,
            FPT_BLOCK,
        ),
        inode(
            INODE_MODE_DIR | INODE_PERM_RX,
            3,
            INODE_FLAG_READONLY,
            bs64,
            bs64,
            1,
            UROOT_BLOCK,
        ),
        inode(
            INODE_MODE_FILE | INODE_PERM_RX,
            1,
            INODE_FLAG_READONLY,
            0,
            0,
            1,
            PAYLOAD_BLOCK,
        ),
    ];
    // The super-root inode marks unused pointers with 0, as the public writers do.
    inodes[0].db[1..].fill(0);
    inodes[0].ib.fill(0);

    // Placeholder header and inode table; rewritten once the payload size is known.
    out.write_all(&sb.encode(FIXED_TIMESTAMP))?;
    write_inodes(out, &inodes)?;
    out.seek(SeekFrom::Start(base + u64::from(SUPER_ROOT_BLOCK) * bs64))?;
    out.write_all(&super_root)?;
    out.seek(SeekFrom::Start(base + u64::from(FPT_BLOCK) * bs64))?;
    out.write_all(&fpt)?;
    out.seek(SeekFrom::Start(base + u64::from(UROOT_BLOCK) * bs64))?;
    out.write_all(&uroot)?;
    let payload_offset = base + u64::from(PAYLOAD_BLOCK) * bs64;
    pad_to(out, payload_offset)?;

    let mut enc = PfscEncoder::new(&mut *out, exfat_len)?;
    plan.write(&mut enc)?;
    let (_, stats) = enc.finish()?;

    let payload_blocks = stats.stored_len.div_ceil(bs64).max(1);
    let end = payload_offset + payload_blocks * bs64;
    pad_to(out, end)?;
    sb.ndblock = u64::from(PAYLOAD_BLOCK) + payload_blocks;
    inodes[3] = inode(
        INODE_MODE_FILE | INODE_PERM_RX,
        1,
        INODE_FLAG_READONLY | INODE_FLAG_COMPRESSED,
        stats.stored_len,
        exfat_len,
        payload_blocks as u32,
        PAYLOAD_BLOCK,
    );
    out.seek(SeekFrom::Start(base))?;
    out.write_all(&sb.encode(FIXED_TIMESTAMP))?;
    write_inodes(out, &inodes)?;
    out.seek(SeekFrom::Start(end))?;
    out.flush()?;

    Ok(BuildInfo {
        container_len: end - base,
        exfat_len,
        pfsc_stored_len: stats.stored_len,
        pfsc_blocks: stats.blocks,
        compressed_blocks: stats.compressed_blocks,
        cluster_size: plan.cluster_size(),
        file_count: plan.file_count(),
        dir_count: plan.dir_count(),
    })
}

fn write_inodes(out: &mut impl Write, inodes: &[Inode]) -> io::Result<()> {
    let mut table = Vec::with_capacity(inodes.len() * INODE_SIZE);
    for i in inodes {
        table.extend_from_slice(&i.encode());
    }
    out.write_all(&table)
}

fn pad_to<W: Write + Seek>(out: &mut W, target: u64) -> io::Result<()> {
    let pos = out.stream_position()?;
    if pos > target {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "writer overran its block",
        ));
    }
    super::write_zeros(out, target - pos)
}
