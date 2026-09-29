// SPDX-License-Identifier: GPL-2.0-only
//! GFX10 register names and PM4 opcode names from the vendored Mesa tables
//! (`regdb/NOTICE.md`). Loaded once from the TSV files embedded at build time.

use std::collections::HashMap;
use std::sync::OnceLock;

const REGISTERS_TSV: &str = include_str!("../regdb/gfx10-registers.tsv");
const EXTRA_REGISTERS_TSV: &str = include_str!("../regdb/extra-registers.tsv");
const OPCODES_TSV: &str = include_str!("../regdb/pm4-opcodes.tsv");

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

/// Lookup tables.
#[derive(Debug)]
pub struct RegDb {
    registers: HashMap<u32, &'static str>,
    opcodes: HashMap<u8, &'static str>,
}

impl RegDb {
    fn load() -> Self {
        let registers = REGISTERS_TSV
            .lines()
            .chain(EXTRA_REGISTERS_TSV.lines())
            .filter(|l| !l.starts_with('#'))
            .filter_map(|l| {
                let (off, name) = l.split_once('\t')?;
                Some((
                    u32::from_str_radix(off.trim_start_matches("0x"), 16).ok()?,
                    name,
                ))
            })
            .collect();
        let opcodes = OPCODES_TSV
            .lines()
            .filter_map(|l| {
                let (op, name) = l.split_once('\t')?;
                Some((
                    u8::from_str_radix(op.trim_start_matches("0x"), 16).ok()?,
                    name,
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

    /// Name of the register at MMIO dword offset `mm`.
    pub fn register_name(&self, mm: u32) -> Option<&'static str> {
        self.registers.get(&mm).copied()
    }

    /// MMIO dword offset of a register by name (linear scan; tests only).
    pub fn register_offset(&self, name: &str) -> Option<u32> {
        self.registers
            .iter()
            .find(|(_, n)| **n == name)
            .map(|(o, _)| *o)
    }

    /// `IT_*` name of an opcode.
    pub fn opcode_name(&self, opcode: u8) -> Option<&'static str> {
        self.opcodes.get(&opcode).copied()
    }

    /// Number of registers known.
    pub fn register_count(&self) -> usize {
        self.registers.len()
    }

    /// Number of opcodes known.
    pub fn opcode_count(&self) -> usize {
        self.opcodes.len()
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
        assert!(db
            .register_offset("COMPUTE_STATIC_THREAD_MGMT_SE0")
            .is_some());
        assert!(db.register_offset("SPI_SHADER_PGM_RSRC3_PS").is_some());
        assert!(is_cu_mask_register("SPI_SHADER_PGM_RSRC3_GS"));
        assert!(!is_cu_mask_register("SPI_SHADER_PGM_LO_PS"));
    }

    #[test]
    fn opcode_blocks() {
        assert_eq!(Block::for_opcode(0x69), Some(Block::Context));
        assert_eq!(Block::for_opcode(0x76), Some(Block::Sh));
        assert_eq!(Block::for_opcode(0x10), None);
        assert_eq!(Block::Context.base(), 0xa000);
    }
}
