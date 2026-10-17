// SPDX-License-Identifier: GPL-2.0-only
//! The `\x7fCNT` container of a package: the title's metadata files
//! (`param.json`, the icons, `PlayGo` tables, `npbind.dat`, …) that a console
//! shows under `/app0/sce_sys` and that the inner image does not hold
//! (`docs/formats/ps5pkg.md`, section 6). The layout is the PS4 package
//! header's: big-endian fields, a table of 32-byte entries, the names in the
//! entry with id `0x200`. Only the plaintext entries are read; nothing is
//! decrypted.

use crate::error::{bail_format, Result};
use crate::io::ReadAt;

const LAYER: &str = "cnt";
/// The container magic.
pub const CNT_MAGIC: &[u8; 4] = b"\x7fCNT";
/// The entry that holds the names of the others, NUL-separated, starting with a NUL.
const ENTRY_NAMES: u32 = 0x200;
/// Entry flags: the entry lives in the body, which a retail image encrypts.
const FLAG_BODY: u32 = 0x0800_0000;
const ENTRY_SIZE: usize = 32;
const MAX_ENTRIES: u32 = 4096;
const MAX_NAMES: u64 = 1 << 20;

/// One named file of the container.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CntEntry {
    /// The entry id (`0x2000` is `param.json`, `0x1200` `icon0.png`, …).
    pub id: u32,
    /// Name from the names table, `/`-separated for the ones in subdirectories.
    pub name: String,
    /// Absolute offset of the data in the package file.
    pub offset: u64,
    /// Data length.
    pub size: u64,
    /// The entry sits in the body: readable in a debug image, encrypted in a
    /// retail one (*TODO(verify)*: flag bit 27, from the package seen).
    pub in_body: bool,
}

/// The container's named entries.
#[derive(Debug, Clone, Default)]
pub struct CntTable {
    /// Content ID, 36 ASCII bytes at +0x40.
    pub content_id: Option<String>,
    /// The entries that have a name, in table order.
    pub entries: Vec<CntEntry>,
}

fn be32(b: &[u8], off: usize) -> Option<u32> {
    b.get(off..off + 4)
        .map(|s| u32::from_be_bytes([s[0], s[1], s[2], s[3]]))
}

impl CntTable {
    /// Parses the container at `offset` of `source`. A missing or unreadable
    /// container is an empty table, not an error; a malformed one is an error.
    pub fn read<R: ReadAt + ?Sized>(source: &R, offset: u64) -> Result<Self> {
        if offset == 0 || offset.checked_add(0x100).map_or(true, |e| e > source.len()) {
            return Ok(Self::default());
        }
        let head = source.read_vec_at(offset, 0x100)?;
        if !head.starts_with(CNT_MAGIC) {
            return Ok(Self::default());
        }
        let content_id = {
            let id = &head[0x40..0x40 + 36];
            if id
                .iter()
                .all(|&b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
            {
                String::from_utf8(id.to_vec()).ok()
            } else {
                None
            }
        };
        let count = be32(&head, 0x10).unwrap_or(0);
        let table = u64::from(be32(&head, 0x18).unwrap_or(0));
        if count > MAX_ENTRIES {
            bail_format!(LAYER, "{count} entries");
        }
        let table_len = count as usize * ENTRY_SIZE;
        let table_abs = offset.checked_add(table).filter(|t| {
            t.checked_add(table_len as u64)
                .is_some_and(|e| e <= source.len())
        });
        let Some(table_abs) = table_abs else {
            bail_format!(
                LAYER,
                "entry table at {table:#x}+{table_len:#x} is outside the file"
            );
        };
        let raw = source.read_vec_at(table_abs, table_len)?;
        let mut entries = Vec::with_capacity(count as usize);
        let mut names: Option<(u64, u64)> = None;
        for rec in raw.chunks_exact(ENTRY_SIZE) {
            let (Some(id), Some(name_off), Some(flags1), Some(off), Some(size)) = (
                be32(rec, 0),
                be32(rec, 4),
                be32(rec, 8),
                be32(rec, 16),
                be32(rec, 20),
            ) else {
                continue;
            };
            if id == ENTRY_NAMES {
                names = Some((u64::from(off), u64::from(size)));
                continue;
            }
            entries.push((id, name_off, flags1, u64::from(off), u64::from(size)));
        }
        let Some((names_off, names_len)) = names else {
            return Ok(Self {
                content_id,
                entries: Vec::new(),
            });
        };
        if names_len > MAX_NAMES
            || offset
                .checked_add(names_off)
                .and_then(|a| a.checked_add(names_len))
                .map_or(true, |e| e > source.len())
        {
            bail_format!(
                LAYER,
                "names at {names_off:#x}+{names_len:#x} are outside the file"
            );
        }
        let names = source.read_vec_at(offset + names_off, names_len as usize)?;
        let name_at = |at: u32| -> Option<String> {
            let s = names.get(at as usize..)?;
            let end = s.iter().position(|&b| b == 0)?;
            if end == 0 {
                return None;
            }
            let name = std::str::from_utf8(&s[..end]).ok()?;
            (!name.contains("..") && name.bytes().all(|b| b.is_ascii_graphic()))
                .then(|| name.to_owned())
        };
        let entries = entries
            .into_iter()
            .filter_map(|(id, name_off, flags1, off, size)| {
                let name = name_at(name_off)?;
                let abs = offset.checked_add(off)?;
                (abs.checked_add(size)? <= source.len()).then_some(CntEntry {
                    id,
                    name,
                    offset: abs,
                    size,
                    in_body: flags1 & FLAG_BODY != 0,
                })
            })
            .collect();
        Ok(Self {
            content_id,
            entries,
        })
    }

    /// The entry with this name (case-insensitive).
    pub fn get(&self, name: &str) -> Option<&CntEntry> {
        self.entries
            .iter()
            .find(|e| e.name.eq_ignore_ascii_case(name))
    }
}

/// Builds a container for tests and the fixture writer: the header with the
/// content ID, the entry table at `+0x100`, the names, then the data; all
/// offsets relative to the start of the returned bytes. Files are given
/// `(id, name, data)`; the names entry is added.
pub fn build(content_id: &str, files: &[(u32, &str, &[u8])]) -> Vec<u8> {
    assert_eq!(content_id.len(), 36, "a content ID is 36 bytes");
    let mut names = vec![0u8];
    let mut name_offs = Vec::new();
    for (_, name, _) in files {
        name_offs.push(names.len() as u32);
        names.extend_from_slice(name.as_bytes());
        names.push(0);
    }
    let count = files.len() + 1;
    let table_off = 0x100usize;
    let names_off = table_off + count * ENTRY_SIZE;
    let mut data_off = names_off + names.len();
    data_off = (data_off + 15) & !15;
    let mut out = vec![0u8; data_off];
    out[..4].copy_from_slice(CNT_MAGIC);
    out[0x10..0x14].copy_from_slice(&(count as u32).to_be_bytes());
    out[0x18..0x1c].copy_from_slice(&(table_off as u32).to_be_bytes());
    out[0x40..0x40 + 36].copy_from_slice(content_id.as_bytes());
    let mut put_entry = |i: usize, id: u32, name_off: u32, flags1: u32, off: u32, size: u32| {
        let at = table_off + i * ENTRY_SIZE;
        out[at..at + 4].copy_from_slice(&id.to_be_bytes());
        out[at + 4..at + 8].copy_from_slice(&name_off.to_be_bytes());
        out[at + 8..at + 12].copy_from_slice(&flags1.to_be_bytes());
        out[at + 16..at + 20].copy_from_slice(&off.to_be_bytes());
        out[at + 20..at + 24].copy_from_slice(&size.to_be_bytes());
    };
    put_entry(
        0,
        ENTRY_NAMES,
        0,
        0x4000_0000,
        names_off as u32,
        names.len() as u32,
    );
    let mut off = data_off;
    for (i, (id, _, data)) in files.iter().enumerate() {
        let data: &[u8] = data;
        put_entry(i + 1, *id, name_offs[i], 0, off as u32, data.len() as u32);
        off += data.len();
    }
    out[names_off..names_off + names.len()].copy_from_slice(&names);
    for (_, _, data) in files {
        out.extend_from_slice(data);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::{build, CntTable};

    const ID: &str = "UP9000-PPSA03671_00-MARVELSWOLVERINE";

    /// The container somewhere inside a bigger file.
    fn in_file(cnt: &[u8]) -> (Vec<u8>, u64) {
        let mut file = vec![0xaau8; 0x1000];
        file.extend_from_slice(cnt);
        (file, 0x1000)
    }

    #[test]
    fn roundtrip_through_build() {
        let (file, at) = in_file(&build(
            ID,
            &[
                (0x2000, "param.json", b"{\"titleId\": \"PPSA03671\"}"),
                (0x1200, "icon0.png", b"\x89PNG"),
                (0x2020, "uds/npbind.dat", b"nb"),
            ],
        ));
        let t = CntTable::read(&file, at).unwrap();
        assert_eq!(t.content_id.as_deref(), Some(ID));
        let names: Vec<&str> = t.entries.iter().map(|e| e.name.as_str()).collect();
        assert_eq!(names, ["param.json", "icon0.png", "uds/npbind.dat"]);
        let p = t.get("PARAM.JSON").unwrap();
        assert_eq!((p.id, p.size, p.in_body), (0x2000, 24, false));
        assert_eq!(
            &file[p.offset as usize..p.offset as usize + 24],
            b"{\"titleId\": \"PPSA03671\"}"
        );
        let u = t.get("uds/npbind.dat").unwrap();
        assert_eq!(&file[u.offset as usize..u.offset as usize + 2], b"nb");
        assert!(t.get("pic0.png").is_none());
    }

    #[test]
    fn missing_or_foreign_is_empty_and_bad_is_an_error() {
        let file = vec![0u8; 0x400];
        for at in [0, 0x100, 0x380] {
            let t = CntTable::read(&file, at).unwrap();
            assert!(t.entries.is_empty(), "at {at:#x}: {t:?}");
            assert_eq!(t.content_id, None);
        }
        let mut bad = build(ID, &[(0x2000, "param.json", b"{}")]);
        bad[0x10..0x14].copy_from_slice(&u32::MAX.to_be_bytes());
        let (file, at) = in_file(&bad);
        assert!(CntTable::read(&file, at).is_err());
        let mut bad = build(ID, &[(0x2000, "param.json", b"{}")]);
        bad[0x18..0x1c].copy_from_slice(&0x7fff_fff0u32.to_be_bytes());
        let (file, at) = in_file(&bad);
        assert!(CntTable::read(&file, at).is_err());
        // A data offset past the file drops the entry, nothing else.
        let mut cut = build(
            ID,
            &[(0x2000, "param.json", b"{}"), (0x1200, "icon0.png", b"png")],
        );
        cut.truncate(cut.len() - 2);
        let (file, at) = in_file(&cut);
        let t = CntTable::read(&file, at).unwrap();
        assert_eq!(t.entries.len(), 1);
        assert_eq!(t.entries[0].name, "param.json");
    }
}
