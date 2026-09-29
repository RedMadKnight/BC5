// SPDX-License-Identifier: GPL-2.0-only
//! GFX10 register names, bit fields and enums from Mesa's `gfx10.json`, plus
//! PM4 opcode names, all vendored under `regdb/` (`regdb/NOTICE.md`). Parsed
//! once on first use.

use std::collections::HashMap;
use std::sync::OnceLock;

use serde::Deserialize;

const GFX10_JSON: &str = include_str!("../regdb/gfx10.json");
const OPCODES_TSV: &str = include_str!("../regdb/pm4-opcodes.tsv");
const EXTRA_REGISTERS_TSV: &str = include_str!("../regdb/extra-registers.tsv");

/// Register block a `SET_*_REG` packet addresses; the value is the block's
/// MMIO dword base (`docs/formats/agc.md` §2).
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Block {
    /// `SET_CONFIG_REG` (0x68).
    Config = 0x2000,
    /// `SET_SH_REG` (0x76) and friends.
    Sh = 0x2c00,
    /// `SET_CONTEXT_REG` (0x69) and friends.
    Context = 0xa000,
    /// `SET_UCONFIG_REG` (0x79) and friends.
    UConfig = 0xc000,
}

impl Block {
    /// MMIO dword base.
    pub fn base(self) -> u32 {
        self as u32
    }

    /// The block a register-writing opcode targets, if it is one.
    pub fn for_opcode(opcode: u8) -> Option<Block> {
        match opcode {
            0x68 | 0x60 => Some(Block::Config),
            0x69 | 0x61 | 0x73 | 0x9f => Some(Block::Context),
            0x76 | 0x77 | 0x5f | 0x63 => Some(Block::Sh),
            0x79 | 0x7a | 0x5e | 0x64 => Some(Block::UConfig),
            _ => None,
        }
    }

    /// Short name for reports.
    pub fn label(self) -> &'static str {
        match self {
            Block::Config => "config",
            Block::Sh => "sh",
            Block::Context => "context",
            Block::UConfig => "uconfig",
        }
    }
}

// --- Mesa JSON shape (only what we read) ---------------------------------

#[derive(Debug, Deserialize)]
struct MesaDb {
    #[serde(default)]
    enums: HashMap<String, MesaEnum>,
    #[serde(default)]
    register_mappings: Vec<MesaMapping>,
    #[serde(default)]
    register_types: HashMap<String, MesaType>,
}

#[derive(Debug, Deserialize)]
struct MesaEnum {
    entries: Vec<MesaEnumEntry>,
}

#[derive(Debug, Deserialize)]
struct MesaEnumEntry {
    name: String,
    value: u64,
}

#[derive(Debug, Deserialize)]
struct MesaMapping {
    map: MesaMap,
    name: String,
    #[serde(default)]
    type_ref: Option<String>,
}

#[derive(Debug, Deserialize)]
struct MesaMap {
    at: u64,
    to: String,
}

#[derive(Debug, Deserialize)]
struct MesaType {
    fields: Vec<MesaField>,
}

#[derive(Debug, Deserialize)]
struct MesaField {
    bits: [u32; 2],
    name: String,
    #[serde(default)]
    enum_ref: Option<String>,
}

// --- Our tables -----------------------------------------------------------

/// One bit field of a register.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Field {
    /// Field name.
    pub name: String,
    /// Lowest bit.
    pub lo: u32,
    /// Highest bit (inclusive).
    pub hi: u32,
    /// `(value, name)` pairs when the field is an enum.
    pub values: Vec<(u64, String)>,
}

impl Field {
    /// Extracts this field from a register value.
    pub fn extract(&self, value: u32) -> u32 {
        let width = self.hi - self.lo + 1;
        let mask = if width >= 32 {
            u32::MAX
        } else {
            (1u32 << width) - 1
        };
        (value >> self.lo) & mask
    }

    /// Enum name for `v`, if any.
    pub fn value_name(&self, v: u32) -> Option<&str> {
        self.values
            .iter()
            .find(|(n, _)| *n == u64::from(v))
            .map(|(_, s)| s.as_str())
    }
}

/// A register: name and, when Mesa describes it, its fields.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Register {
    /// Register name.
    pub name: String,
    /// Bit fields in ascending bit order; empty when unknown.
    pub fields: Vec<Field>,
    /// Other names the same offset is known under (e.g. the kernel header's
    /// `COMPUTE_DESTINATION_EN_SE0` for `COMPUTE_STATIC_THREAD_MGMT_SE0`).
    pub aliases: Vec<String>,
}

/// Lookup tables.
#[derive(Debug)]
pub struct RegDb {
    registers: HashMap<u32, Register>,
    opcodes: HashMap<u8, String>,
}

impl RegDb {
    fn load() -> Self {
        let mesa: MesaDb = serde_json::from_str(GFX10_JSON).unwrap_or_else(|e| {
            // The file is vendored and validated by tests; a parse failure is a build defect.
            panic!("regdb/gfx10.json does not parse: {e}")
        });
        let mut registers = HashMap::new();
        for m in mesa.register_mappings.iter().filter(|m| m.map.to == "mm") {
            let mm = (m.map.at / 4) as u32;
            let fields = m
                .type_ref
                .as_deref()
                .and_then(|t| mesa.register_types.get(t))
                .map(|t| {
                    let mut f: Vec<Field> = t
                        .fields
                        .iter()
                        .map(|f| Field {
                            name: f.name.clone(),
                            lo: f.bits[0],
                            hi: f.bits[1].max(f.bits[0]).min(31),
                            values: f
                                .enum_ref
                                .as_deref()
                                .and_then(|e| mesa.enums.get(e))
                                .map(|e| {
                                    e.entries
                                        .iter()
                                        .map(|x| (x.value, x.name.clone()))
                                        .collect()
                                })
                                .unwrap_or_default(),
                        })
                        .collect();
                    f.sort_by_key(|f| f.lo);
                    f
                })
                .unwrap_or_default();
            registers.entry(mm).or_insert(Register {
                name: m.name.clone(),
                fields,
                aliases: Vec::new(),
            });
        }
        for l in EXTRA_REGISTERS_TSV.lines().filter(|l| !l.starts_with('#')) {
            if let Some((off, name)) = split_tsv(l) {
                if let Ok(mm) = u32::from_str_radix(off.trim_start_matches("0x"), 16) {
                    // Extra entries take the primary name; Mesa's name becomes an alias.
                    let name = name.trim().to_string();
                    match registers.get_mut(&mm) {
                        Some(reg) if reg.name != name => {
                            let old = std::mem::replace(&mut reg.name, name);
                            reg.aliases.push(old);
                        }
                        Some(_) => {}
                        None => {
                            registers.insert(
                                mm,
                                Register {
                                    name,
                                    fields: Vec::new(),
                                    aliases: Vec::new(),
                                },
                            );
                        }
                    }
                }
            }
        }
        let opcodes = OPCODES_TSV
            .lines()
            .filter_map(|l| {
                let (op, name) = split_tsv(l)?;
                Some((
                    u8::from_str_radix(op.trim_start_matches("0x"), 16).ok()?,
                    name.trim().to_string(),
                ))
            })
            .collect();
        Self { registers, opcodes }
    }

    /// The process-wide tables.
    pub fn get() -> &'static RegDb {
        static DB: OnceLock<RegDb> = OnceLock::new();
        DB.get_or_init(RegDb::load)
    }

    /// The register at MMIO dword offset `mm`.
    pub fn register(&self, mm: u32) -> Option<&Register> {
        self.registers.get(&mm)
    }

    /// Name of the register at MMIO dword offset `mm`.
    pub fn register_name(&self, mm: u32) -> Option<&str> {
        self.registers.get(&mm).map(|r| r.name.as_str())
    }

    /// MMIO dword offset of a register by name (linear scan; tools and tests).
    pub fn register_offset(&self, name: &str) -> Option<u32> {
        self.registers
            .iter()
            .find(|(_, r)| r.name == name || r.aliases.iter().any(|a| a == name))
            .map(|(o, _)| *o)
    }

    /// `IT_*` name of an opcode.
    pub fn opcode_name(&self, opcode: u8) -> Option<&str> {
        self.opcodes.get(&opcode).map(String::as_str)
    }

    /// Number of registers known.
    pub fn register_count(&self) -> usize {
        self.registers.len()
    }

    /// Number of opcodes known.
    pub fn opcode_count(&self) -> usize {
        self.opcodes.len()
    }

    /// Renders the non-zero fields of `value` for the register at `mm`, e.g.
    /// `ENABLE=1 COLOR_SRCBLEND=BLEND_ONE`. `None` when no fields are known.
    pub fn describe(&self, mm: u32, value: u32) -> Option<String> {
        let reg = self.registers.get(&mm)?;
        if reg.fields.is_empty() {
            return None;
        }
        let parts: Vec<String> = reg
            .fields
            .iter()
            .filter_map(|f| {
                let v = f.extract(value);
                if v == 0 {
                    return None;
                }
                Some(match f.value_name(v) {
                    Some(n) => format!("{}={n}", f.name),
                    None => format!("{}={v:#x}", f.name),
                })
            })
            .collect();
        Some(parts.join(" "))
    }
}

/// Splits a table line at its first run of whitespace (tab or spaces).
fn split_tsv(line: &str) -> Option<(&str, &str)> {
    let mut it = line.splitn(2, char::is_whitespace);
    let key = it.next()?.trim();
    let value = it.next()?.trim();
    if key.is_empty() || value.is_empty() {
        None
    } else {
        Some((key, value))
    }
}

/// True for the CU-mask registers HANDOFF Q3 asks about.
pub fn is_cu_mask_register(name: &str) -> bool {
    name.starts_with("COMPUTE_STATIC_THREAD_MGMT_SE") || name.starts_with("SPI_SHADER_PGM_RSRC3_")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tables_load_and_contain_known_entries() {
        let db = RegDb::get();
        assert!(db.register_count() > 1500, "{}", db.register_count());
        assert!(db.opcode_count() > 60, "{}", db.opcode_count());
        assert_eq!(db.opcode_name(0x69), Some("SET_CONTEXT_REG"));
        assert_eq!(db.opcode_name(0x76), Some("SET_SH_REG"));
        assert_eq!(db.opcode_name(0x10), Some("NOP"));
        assert_eq!(db.opcode_name(0x49), Some("RELEASE_MEM"));
        assert_eq!(db.register_name(0xa000), Some("DB_RENDER_CONTROL"));
        assert_eq!(db.register_offset("SPI_SHADER_PGM_RSRC3_PS"), Some(0x2c07));
        assert_eq!(
            db.register_offset("COMPUTE_STATIC_THREAD_MGMT_SE0"),
            Some(0x2e16)
        );
        assert_eq!(
            db.register_offset("COMPUTE_DESTINATION_EN_SE0"),
            Some(0x2e16)
        );
        assert_eq!(
            db.register(0x2e16).unwrap().aliases,
            vec!["COMPUTE_DESTINATION_EN_SE0".to_string()]
        );
        assert_eq!(
            db.register_offset("COMPUTE_STATIC_THREAD_MGMT_SE2"),
            Some(0x2e19)
        );
        assert!(is_cu_mask_register("SPI_SHADER_PGM_RSRC3_GS"));
        assert!(!is_cu_mask_register("SPI_SHADER_PGM_LO_PS"));
    }

    #[test]
    fn fields_and_enums_decode() {
        let db = RegDb::get();
        let mm = db.register_offset("CB_BLEND0_CONTROL").unwrap();
        let reg = db.register(mm).unwrap();
        assert!(reg
            .fields
            .iter()
            .any(|f| f.name == "COLOR_SRCBLEND" && !f.values.is_empty()));
        // ENABLE is bit 30; COLOR_SRCBLEND bits 0..4 = 1 (BLEND_ONE in Mesa's BlendOp enum).
        let text = db.describe(mm, (1 << 30) | 1).unwrap();
        assert!(text.contains("ENABLE=0x1"), "{text}");
        assert!(text.contains("COLOR_SRCBLEND=BLEND_ONE"), "{text}");
        assert_eq!(db.describe(mm, 0).as_deref(), Some(""));
        assert_eq!(db.describe(0x2e16, 5), None); // extra register, no field info
        let f = Field {
            name: "x".into(),
            lo: 4,
            hi: 7,
            values: vec![],
        };
        assert_eq!(f.extract(0xF0), 0xF);
        assert_eq!(f.extract(0x0F), 0);
    }

    #[test]
    fn opcode_blocks() {
        assert_eq!(Block::for_opcode(0x69), Some(Block::Context));
        assert_eq!(Block::for_opcode(0x76), Some(Block::Sh));
        assert_eq!(Block::for_opcode(0x10), None);
        assert_eq!(Block::Context.base(), 0xa000);
    }
}
