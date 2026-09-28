// SPDX-License-Identifier: GPL-2.0-only
//! Minimal exFAT image writer for fixtures: 512-byte sectors, one FAT at
//! sector 128, a main and a backup boot region, an allocation bitmap, a
//! truncated up-case table (ASCII only), and every allocation laid out as one
//! consecutive run. Layout mirrors what the public writers produce
//! (`docs/formats/ffpfsc.md` §7), with the FAT filled with chains and the
//! `NoFatChain` flag optional.

use std::io::{self, Write};

use crate::exfat::{
    boot_checksum, entry_set_checksum, name_hash, table_checksum, BootSector, ATTR_ARCHIVE,
    ATTR_DIRECTORY, ENTRY_BITMAP, ENTRY_FILE, ENTRY_LABEL, ENTRY_NAME, ENTRY_STREAM, ENTRY_UPCASE,
    FIRST_CLUSTER, STREAM_ALLOC_POSSIBLE, STREAM_NO_FAT_CHAIN,
};

use super::{Content, DirSpec, Spec};

const SECTOR: u64 = 512;
const FAT_OFFSET_SECTORS: u64 = 128;
const BOOT_REGION_SECTORS: u64 = 12;
const VOLUME_SERIAL: u32 = 0x4D6B_5046; // "MkPF", as the public writers use.
/// exFAT timestamp 2024-01-01 00:00:00 (DOS-style packed date/time).
const FIXED_EXFAT_TIME: u32 = ((2024 - 1980) << 25) | (1 << 21) | (1 << 16);

#[derive(Debug)]
struct Node {
    name: String,
    is_dir: bool,
    content: Option<Content>,
    // Directories: index of parent node; children listed in `children`.
    children: Vec<usize>,
    first_cluster: u32,
    cluster_count: u32,
    data_len: u64,
}

/// Cluster layout for a spec, computed before any byte is written.
#[derive(Debug)]
pub struct ExfatPlan {
    nodes: Vec<Node>,
    cluster_size: u32,
    bitmap_clusters: u32,
    upcase_clusters: u32,
    cluster_count: u32,
    fat_length_sectors: u32,
    heap_offset_sectors: u32,
    image_len: u64,
    upcase: Vec<u8>,
    no_fat_chain: bool,
}

/// The up-case table we emit: identity for U+0000..U+007F except a–z → A–Z.
/// Truncated tables are allowed by the specification; characters past the end
/// map to themselves.
pub fn upcase_table() -> Vec<u8> {
    (0u16..128)
        .map(|c| {
            if (0x61..=0x7A).contains(&c) {
                c - 0x20
            } else {
                c
            }
        })
        .flat_map(u16::to_le_bytes)
        .collect()
}

fn upcase_unit(c: u16) -> u16 {
    if (0x61..=0x7A).contains(&c) {
        c - 0x20
    } else {
        c
    }
}

impl ExfatPlan {
    /// Lays out `spec` in clusters of `spec.cluster_size` bytes.
    pub fn new(spec: &Spec) -> io::Result<Self> {
        let cs = spec.cluster_size;
        if !cs.is_power_of_two() || !(0x1000..=0x200_0000).contains(&cs) {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "cluster size must be a power of two in 4 KiB..32 MiB",
            ));
        }
        let mut nodes = Vec::new();
        collect(&spec.root, &mut nodes, true)?;

        let upcase = upcase_table();
        let cs64 = u64::from(cs);
        let upcase_clusters = (upcase.len() as u64).div_ceil(cs64) as u32;
        let mut content_clusters = u64::from(upcase_clusters);
        for i in 0..nodes.len() {
            let n = if nodes[i].is_dir {
                let entries = dir_entry_count(&nodes, i);
                (entries as u64 * 32).div_ceil(cs64).max(1)
            } else {
                nodes[i].data_len.div_ceil(cs64)
            };
            nodes[i].cluster_count = u32::try_from(n)
                .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "file too large"))?;
            content_clusters += n;
        }
        let mut bitmap_clusters: u64 = 1;
        loop {
            let total = content_clusters + bitmap_clusters;
            let needed = total.div_ceil(8).div_ceil(cs64).max(1);
            if needed == bitmap_clusters {
                break;
            }
            bitmap_clusters = needed;
        }
        let cluster_count = content_clusters + bitmap_clusters;
        if cluster_count >= u64::from(u32::MAX) - 2 {
            return Err(io::Error::new(
                io::ErrorKind::InvalidInput,
                "too many clusters",
            ));
        }
        let spc = cs64 / SECTOR;
        let fat_bytes = (cluster_count + 2) * 4;
        let fat_length_sectors = fat_bytes.div_ceil(SECTOR).div_ceil(spc) * spc;
        let heap_offset_sectors = (FAT_OFFSET_SECTORS + fat_length_sectors).div_ceil(spc) * spc;
        let volume_sectors = heap_offset_sectors + cluster_count * spc;

        let mut next = u64::from(FIRST_CLUSTER) + bitmap_clusters + u64::from(upcase_clusters);
        for node in &mut nodes {
            if node.cluster_count == 0 {
                node.first_cluster = 0;
                continue;
            }
            node.first_cluster = next as u32;
            next += u64::from(node.cluster_count);
            if node.is_dir {
                node.data_len = u64::from(node.cluster_count) * cs64;
            }
        }
        debug_assert_eq!(next, u64::from(FIRST_CLUSTER) + cluster_count);

        Ok(Self {
            nodes,
            cluster_size: cs,
            bitmap_clusters: bitmap_clusters as u32,
            upcase_clusters,
            cluster_count: cluster_count as u32,
            fat_length_sectors: fat_length_sectors as u32,
            heap_offset_sectors: heap_offset_sectors as u32,
            image_len: volume_sectors * SECTOR,
            upcase,
            no_fat_chain: spec.no_fat_chain,
        })
    }

    /// Length of the image this plan writes.
    pub fn image_len(&self) -> u64 {
        self.image_len
    }

    /// Cluster size.
    pub fn cluster_size(&self) -> u32 {
        self.cluster_size
    }

    /// Number of files.
    pub fn file_count(&self) -> usize {
        self.nodes.iter().filter(|n| !n.is_dir).count()
    }

    /// Number of directories excluding the root.
    pub fn dir_count(&self) -> usize {
        self.nodes.iter().filter(|n| n.is_dir).count() - 1
    }

    fn boot_sector(&self) -> BootSector {
        BootSector {
            volume_length: self.image_len / SECTOR,
            fat_offset: FAT_OFFSET_SECTORS as u32,
            fat_length: self.fat_length_sectors,
            cluster_heap_offset: self.heap_offset_sectors,
            cluster_count: self.cluster_count,
            root_cluster: self.nodes[0].first_cluster,
            serial: VOLUME_SERIAL,
            revision: 0x0100,
            sector_shift: 9,
            cluster_shift: (self.cluster_size / SECTOR as u32).trailing_zeros() as u8,
            num_fats: 1,
        }
    }

    /// Writes the whole image sequentially.
    pub fn write(&self, out: &mut impl Write) -> io::Result<()> {
        let mut written: u64 = 0;
        let boot = self.boot_region();
        out.write_all(&boot)?;
        out.write_all(&boot)?;
        written += 2 * BOOT_REGION_SECTORS * SECTOR;
        written += write_zeros(out, FAT_OFFSET_SECTORS * SECTOR - written)?;

        written += self.write_fat(out)?;
        let heap = u64::from(self.heap_offset_sectors) * SECTOR;
        written += write_zeros(out, heap - written)?;

        written += self.write_bitmap(out)?;
        out.write_all(&self.upcase)?;
        written += self.upcase.len() as u64;
        let upcase_end = u64::from(self.upcase_clusters) * u64::from(self.cluster_size);
        written += write_zeros(out, upcase_end - self.upcase.len() as u64)?;

        for i in 0..self.nodes.len() {
            let node = &self.nodes[i];
            if node.is_dir {
                written += self.write_directory(out, i)?;
            } else if let Some(content) = &node.content {
                content.write_to(out)?;
                let padded = u64::from(node.cluster_count) * u64::from(self.cluster_size);
                written += content.len() + write_zeros(out, padded - content.len())?;
            }
        }
        debug_assert_eq!(written, self.image_len);
        Ok(())
    }

    fn boot_region(&self) -> Vec<u8> {
        let mut region = vec![0u8; (BOOT_REGION_SECTORS * SECTOR) as usize];
        region[..512].copy_from_slice(&self.boot_sector().encode());
        for sector in 1..=8 {
            let end = (sector + 1) * 512;
            region[end - 4..end].copy_from_slice(&0xAA55_0000u32.to_le_bytes());
        }
        let sum = boot_checksum(&region[..11 * 512]);
        for chunk in region[11 * 512..].chunks_exact_mut(4) {
            chunk.copy_from_slice(&sum.to_le_bytes());
        }
        region
    }

    fn write_fat(&self, out: &mut impl Write) -> io::Result<u64> {
        let total = u64::from(self.fat_length_sectors) * SECTOR;
        let entries = u64::from(self.cluster_count) + 2;
        let mut chain_ends = vec![false; entries as usize];
        let bitmap_end = FIRST_CLUSTER + self.bitmap_clusters - 1;
        chain_ends[bitmap_end as usize] = true;
        if self.upcase_clusters > 0 {
            chain_ends[(bitmap_end + self.upcase_clusters) as usize] = true;
        }
        for n in &self.nodes {
            if n.cluster_count > 0 {
                chain_ends[(n.first_cluster + n.cluster_count - 1) as usize] = true;
            }
        }
        let mut buf = Vec::with_capacity(1 << 20);
        let mut written = 0u64;
        for cluster in 0..entries {
            let v: u32 = match cluster {
                0 => 0xFFFF_FFF8,
                1 => 0xFFFF_FFFF,
                c if chain_ends[c as usize] => 0xFFFF_FFFF,
                c => (c + 1) as u32,
            };
            buf.extend_from_slice(&v.to_le_bytes());
            if buf.len() >= 1 << 20 {
                out.write_all(&buf)?;
                written += buf.len() as u64;
                buf.clear();
            }
        }
        out.write_all(&buf)?;
        written += buf.len() as u64;
        write_zeros(out, total - written)?;
        Ok(total)
    }

    fn write_bitmap(&self, out: &mut impl Write) -> io::Result<u64> {
        let total = u64::from(self.bitmap_clusters) * u64::from(self.cluster_size);
        let used_bytes = u64::from(self.cluster_count).div_ceil(8);
        let mut written = 0u64;
        let full = u64::from(self.cluster_count) / 8;
        let mut buf = vec![0xFFu8; (1 << 20).min(full as usize)];
        let mut left = full;
        while left > 0 {
            let n = (buf.len() as u64).min(left) as usize;
            buf.truncate(n);
            out.write_all(&buf)?;
            written += n as u64;
            left -= n as u64;
        }
        if used_bytes > full {
            let bits = self.cluster_count % 8;
            out.write_all(&[((1u16 << bits) - 1) as u8])?;
            written += 1;
        }
        write_zeros(out, total - written)?;
        Ok(total)
    }

    fn write_directory(&self, out: &mut impl Write, idx: usize) -> io::Result<u64> {
        let node = &self.nodes[idx];
        let mut data = Vec::new();
        if idx == 0 {
            let mut label = [0u8; 32];
            label[0] = ENTRY_LABEL;
            data.extend_from_slice(&label);
            let mut bitmap = [0u8; 32];
            bitmap[0] = ENTRY_BITMAP;
            bitmap[0x14..0x18].copy_from_slice(&FIRST_CLUSTER.to_le_bytes());
            bitmap[0x18..0x20]
                .copy_from_slice(&u64::from(self.cluster_count).div_ceil(8).to_le_bytes());
            data.extend_from_slice(&bitmap);
            let mut upcase = [0u8; 32];
            upcase[0] = ENTRY_UPCASE;
            upcase[0x04..0x08].copy_from_slice(&table_checksum(&self.upcase).to_le_bytes());
            upcase[0x14..0x18]
                .copy_from_slice(&(FIRST_CLUSTER + self.bitmap_clusters).to_le_bytes());
            upcase[0x18..0x20].copy_from_slice(&(self.upcase.len() as u64).to_le_bytes());
            data.extend_from_slice(&upcase);
        }
        for &child in &node.children {
            data.extend(self.entry_set(&self.nodes[child]));
        }
        let total = u64::from(node.cluster_count) * u64::from(self.cluster_size);
        debug_assert!(data.len() as u64 <= total);
        out.write_all(&data)?;
        write_zeros(out, total - data.len() as u64)?;
        Ok(total)
    }

    fn entry_set(&self, node: &Node) -> Vec<u8> {
        let units: Vec<u16> = node.name.encode_utf16().collect();
        let name_entries = units.len().div_ceil(15);
        let secondary = 1 + name_entries;
        let mut set = vec![0u8; (secondary + 1) * 32];
        set[0] = ENTRY_FILE;
        set[1] = secondary as u8;
        let attrs = if node.is_dir {
            ATTR_DIRECTORY
        } else {
            ATTR_ARCHIVE
        };
        set[4..6].copy_from_slice(&attrs.to_le_bytes());
        for off in [0x08, 0x0C, 0x10] {
            set[off..off + 4].copy_from_slice(&FIXED_EXFAT_TIME.to_le_bytes());
        }
        let stream = &mut set[32..64];
        stream[0] = ENTRY_STREAM;
        let allocated = node.first_cluster >= FIRST_CLUSTER;
        stream[1] = if allocated {
            STREAM_ALLOC_POSSIBLE
                | if self.no_fat_chain {
                    STREAM_NO_FAT_CHAIN
                } else {
                    0
                }
        } else {
            0
        };
        stream[3] = units.len() as u8;
        let upcased: Vec<u16> = units.iter().map(|&u| upcase_unit(u)).collect();
        stream[4..6].copy_from_slice(&name_hash(&upcased).to_le_bytes());
        stream[0x08..0x10].copy_from_slice(&node.data_len.to_le_bytes());
        stream[0x14..0x18]
            .copy_from_slice(&(if allocated { node.first_cluster } else { 0 }).to_le_bytes());
        stream[0x18..0x20].copy_from_slice(&node.data_len.to_le_bytes());
        for (i, chunk) in units.chunks(15).enumerate() {
            let e = &mut set[(2 + i) * 32..(3 + i) * 32];
            e[0] = ENTRY_NAME;
            for (j, unit) in chunk.iter().enumerate() {
                e[2 + j * 2..4 + j * 2].copy_from_slice(&unit.to_le_bytes());
            }
        }
        let sum = entry_set_checksum(&set);
        set[2..4].copy_from_slice(&sum.to_le_bytes());
        set
    }
}

fn collect(dir: &DirSpec, nodes: &mut Vec<Node>, is_root: bool) -> io::Result<usize> {
    let idx = nodes.len();
    nodes.push(Node {
        name: if is_root {
            String::new()
        } else {
            dir.name.clone()
        },
        is_dir: true,
        content: None,
        children: Vec::new(),
        first_cluster: 0,
        cluster_count: 0,
        data_len: 0,
    });
    // Children sorted by lower-cased name, files and directories together.
    let mut items: Vec<(String, Option<&DirSpec>, Option<&super::FileSpec>)> = Vec::new();
    for f in &dir.files {
        validate_name(&f.name)?;
        items.push((f.name.to_lowercase(), None, Some(f)));
    }
    for d in &dir.dirs {
        validate_name(&d.name)?;
        items.push((d.name.to_lowercase(), Some(d), None));
    }
    items.sort_by(|a, b| a.0.cmp(&b.0));
    let mut children = Vec::new();
    for (_, d, f) in items {
        if let Some(d) = d {
            children.push(collect(d, nodes, false)?);
        } else if let Some(f) = f {
            children.push(nodes.len());
            nodes.push(Node {
                name: f.name.clone(),
                is_dir: false,
                data_len: f.content.len(),
                content: Some(f.content.clone()),
                children: Vec::new(),
                first_cluster: 0,
                cluster_count: 0,
            });
        }
    }
    nodes[idx].children = children;
    Ok(idx)
}

fn validate_name(name: &str) -> io::Result<()> {
    let units = name.encode_utf16().count();
    if units == 0
        || units > 255
        || name == "."
        || name == ".."
        || name.contains(['/', '\\', '\0', ':', '*', '?', '"', '<', '>', '|'])
    {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("invalid exFAT name {name:?}"),
        ));
    }
    Ok(())
}

fn dir_entry_count(nodes: &[Node], idx: usize) -> usize {
    let base = if idx == 0 { 3 } else { 0 };
    nodes[idx]
        .children
        .iter()
        .map(|&c| 2 + nodes[c].name.encode_utf16().count().div_ceil(15))
        .sum::<usize>()
        + base
}

fn write_zeros(out: &mut impl Write, n: u64) -> io::Result<u64> {
    super::write_zeros(out, n)?;
    Ok(n)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::exfat::ExfatVolume;
    use crate::io::ReadAt;

    fn image(spec: &Spec) -> Vec<u8> {
        let plan = ExfatPlan::new(spec).unwrap();
        let mut out = Vec::new();
        plan.write(&mut out).unwrap();
        assert_eq!(out.len() as u64, plan.image_len());
        out
    }

    #[test]
    fn empty_volume_parses() {
        let img = image(&Spec::preset("empty").unwrap());
        let vol = ExfatVolume::open(img).unwrap();
        assert_eq!(vol.entries().len(), 1);
        assert!(vol.children(0).is_empty());
    }

    #[test]
    fn files_round_trip_through_the_reader() {
        for preset in [
            "one-small",
            "spanning",
            "deep",
            "wide",
            "case",
            "contiguous",
        ] {
            let spec = Spec::preset(preset).unwrap();
            let img = image(&spec);
            let vol = ExfatVolume::open(img).unwrap();
            for (path, content) in spec.files() {
                let idx = vol
                    .find(&path)
                    .unwrap_or_else(|| panic!("{preset}: {path} missing"));
                let e = vol.entry(idx).unwrap();
                assert_eq!(e.size, content.len(), "{preset}: {path}");
                // Unallocated (empty) files never carry NoFatChain.
                assert_eq!(e.contiguous, spec.no_fat_chain && !content.is_empty());
                let got = vol
                    .file(idx)
                    .unwrap()
                    .read_vec_at(0, content.len() as usize)
                    .unwrap();
                let mut want = vec![0u8; content.len() as usize];
                content.fill(0, &mut want);
                assert!(got == want, "{preset}: {path} content differs");
            }
            for d in spec.dirs() {
                let idx = vol.find(&d).unwrap();
                assert!(vol.entry(idx).unwrap().is_dir);
            }
            assert_eq!(
                vol.entries().len(),
                1 + spec.files().len() + spec.dirs().len()
            );
        }
    }

    #[test]
    fn lookup_is_case_insensitive() {
        let vol = ExfatVolume::open(image(&Spec::preset("case").unwrap())).unwrap();
        assert!(vol.find("SCE_SYS/PARAM.JSON").is_some());
        assert!(vol.find("/sce_sys/").is_some());
        assert!(vol.find("missing").is_none());
    }
}
