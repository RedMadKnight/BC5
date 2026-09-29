// SPDX-License-Identifier: GPL-2.0-only
//! Packets → events, and the report that answers "what is in this stream".

use std::collections::BTreeMap;
use std::fmt::Write;

use crate::pm4::{Packet, Parsed};
use crate::regdb::{is_cu_mask_register, Block, RegDb};

/// Something a packet did.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Event {
    /// A register write (from `SET_*_REG` or a type-0 packet).
    RegWrite {
        /// Block of a `SET_*_REG`; `None` for type-0 (absolute) writes.
        block: Option<Block>,
        /// MMIO dword offset.
        mm: u32,
        /// Register name, when the tables know it.
        name: Option<&'static str>,
        /// Value written.
        value: u32,
    },
    /// Any other type-3 packet.
    Packet {
        /// Opcode.
        opcode: u8,
        /// Opcode name, when known.
        name: Option<&'static str>,
        /// Payload dwords.
        payload: Vec<u32>,
    },
    /// A type-2 filler.
    Filler,
}

/// Expands parsed packets into events.
pub fn events(parsed: &Parsed) -> Vec<Event> {
    let db = RegDb::get();
    let mut out = Vec::new();
    for (_, packet) in &parsed.packets {
        match packet {
            Packet::Type2 => out.push(Event::Filler),
            Packet::Type0 { base, values } => {
                for (i, &value) in values.iter().enumerate() {
                    let mm = u32::from(*base) + i as u32;
                    out.push(Event::RegWrite {
                        block: None,
                        mm,
                        name: db.register_name(mm),
                        value,
                    });
                }
            }
            Packet::Type3 {
                opcode, payload, ..
            } => {
                // Plain SET_*_REG: dword1 = offset (16 bits) | index << 26, then values.
                let is_plain_set = matches!(opcode, 0x68 | 0x69 | 0x76 | 0x79);
                match (Block::for_opcode(*opcode), payload.first()) {
                    (Some(block), Some(first)) if is_plain_set => {
                        let offset = first & 0xffff;
                        for (i, &value) in payload[1..].iter().enumerate() {
                            let mm = block.base() + offset + i as u32;
                            out.push(Event::RegWrite {
                                block: Some(block),
                                mm,
                                name: db.register_name(mm),
                                value,
                            });
                        }
                    }
                    _ => out.push(Event::Packet {
                        opcode: *opcode,
                        name: db.opcode_name(*opcode),
                        payload: payload.clone(),
                    }),
                }
            }
        }
    }
    out
}

/// Counts over one or more streams.
#[derive(Debug, Default, Clone)]
pub struct Report {
    /// Streams added.
    pub streams: usize,
    /// Packets seen (all types).
    pub packets: u64,
    /// Opcode → count, known opcodes.
    pub known_opcodes: BTreeMap<u8, u64>,
    /// Opcode → count, opcodes absent from the table.
    pub unknown_opcodes: BTreeMap<u8, u64>,
    /// MMIO offset → count for register writes the tables can name.
    pub registers: BTreeMap<u32, u64>,
    /// MMIO offset → count for writes the tables cannot name.
    pub unresolved: BTreeMap<u32, u64>,
    /// CU-mask register writes by name (HANDOFF Q3).
    pub cu_mask_writes: BTreeMap<&'static str, u64>,
    /// Parse errors, one line per stream that had one.
    pub errors: Vec<String>,
}

impl Report {
    /// Adds one parsed stream.
    pub fn add(&mut self, label: &str, parsed: &Parsed) {
        let db = RegDb::get();
        self.streams += 1;
        self.packets += parsed.packets.len() as u64;
        for (_, packet) in &parsed.packets {
            if let Packet::Type3 { opcode, .. } = packet {
                let bucket = if db.opcode_name(*opcode).is_some() {
                    &mut self.known_opcodes
                } else {
                    &mut self.unknown_opcodes
                };
                *bucket.entry(*opcode).or_default() += 1;
            }
        }
        for event in events(parsed) {
            if let Event::RegWrite { mm, name, .. } = event {
                match name {
                    Some(n) => {
                        *self.registers.entry(mm).or_default() += 1;
                        if is_cu_mask_register(n) {
                            *self.cu_mask_writes.entry(n).or_default() += 1;
                        }
                    }
                    None => *self.unresolved.entry(mm).or_default() += 1,
                }
            }
        }
        if let Some(e) = &parsed.error {
            self.errors.push(format!("{label}: {e}"));
        }
    }

    /// Human-readable summary.
    pub fn render(&self) -> String {
        let db = RegDb::get();
        let mut s = String::new();
        let _ = writeln!(s, "streams: {}  packets: {}", self.streams, self.packets);
        let _ = writeln!(s, "known opcodes ({}):", self.known_opcodes.len());
        for (op, n) in &self.known_opcodes {
            let _ = writeln!(
                s,
                "  {op:#04x} {:<28} {n}",
                db.opcode_name(*op).unwrap_or("?")
            );
        }
        let _ = writeln!(s, "unknown opcodes ({}):", self.unknown_opcodes.len());
        for (op, n) in &self.unknown_opcodes {
            let _ = writeln!(s, "  {op:#04x} {:<28} {n}", "-");
        }
        let _ = writeln!(
            s,
            "register writes: {} named, {} unresolved offsets",
            self.registers.len(),
            self.unresolved.len()
        );
        for (mm, n) in &self.unresolved {
            let _ = writeln!(
                s,
                "  unresolved:{}+{:#06x} (mm {mm:#07x}) {n}",
                block_of(*mm).map_or("abs", Block::label),
                mm - block_of(*mm).map_or(0, Block::base)
            );
        }
        let _ = writeln!(
            s,
            "cu-mask register writes (Q3): {}",
            self.cu_mask_writes.values().sum::<u64>()
        );
        for (name, n) in &self.cu_mask_writes {
            let _ = writeln!(s, "  {name:<36} {n}");
        }
        if !self.errors.is_empty() {
            let _ = writeln!(s, "parse errors:");
            for e in &self.errors {
                let _ = writeln!(s, "  {e}");
            }
        }
        s
    }
}

/// The block whose range contains `mm`, for labelling unresolved offsets.
fn block_of(mm: u32) -> Option<Block> {
    match mm {
        0x2000..=0x2bff => Some(Block::Config),
        0x2c00..=0x2fff => Some(Block::Sh),
        0xa000..=0xa3ff => Some(Block::Context),
        0xc000..=0xc3ff => Some(Block::UConfig),
        _ => None,
    }
}

/// One line per event, for `bc5-agc dump`.
pub fn format_event(event: &Event) -> String {
    match event {
        Event::Filler => "filler".into(),
        Event::RegWrite {
            block,
            mm,
            name,
            value,
        } => format!(
            "{:<8} {:<36} = {value:#010x}",
            block.map_or("type0", Block::label),
            name.map_or_else(|| format!("mm {mm:#07x}"), str::to_string),
        ),
        Event::Packet {
            opcode,
            name,
            payload,
        } => {
            let words: Vec<String> = payload
                .iter()
                .take(8)
                .map(|w| format!("{w:#010x}"))
                .collect();
            format!(
                "{:<8} {:<36} [{}{}]",
                "pkt",
                name.map_or_else(|| format!("opcode {opcode:#04x} (unknown)"), str::to_string),
                words.join(" "),
                if payload.len() > 8 { " …" } else { "" }
            )
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pm4::{header0, header3, parse, FILLER};

    #[test]
    fn set_reg_packets_become_named_writes() {
        let db = RegDb::get();
        let se0 = db
            .register_offset("COMPUTE_STATIC_THREAD_MGMT_SE0")
            .unwrap();
        let stream = [
            header3(0x69, 2),
            0,
            0x11, // DB_RENDER_CONTROL
            header3(0x76, 3),
            se0 - 0x2c00,
            0xffff_ffff,
            0x1, // SE0 and the next register
            header0(0xa000, 1),
            0x22,
            FILLER,
            header3(0xEE, 1),
            0, // unknown opcode
            header3(0x69, 2),
            0x3ff,
            0, // unresolved context offset
        ];
        let parsed = parse(&stream);
        assert!(parsed.error.is_none());
        let ev = events(&parsed);
        assert!(matches!(
            ev[0],
            Event::RegWrite {
                block: Some(Block::Context),
                mm: 0xa000,
                name: Some("DB_RENDER_CONTROL"),
                value: 0x11
            }
        ));
        assert!(matches!(
            ev[1],
            Event::RegWrite {
                block: Some(Block::Sh),
                name: Some("COMPUTE_STATIC_THREAD_MGMT_SE0"),
                ..
            }
        ));
        assert!(matches!(
            ev[3],
            Event::RegWrite {
                block: None,
                mm: 0xa000,
                ..
            }
        ));
        assert_eq!(ev[4], Event::Filler);
        assert!(matches!(
            ev[5],
            Event::Packet {
                opcode: 0xEE,
                name: None,
                ..
            }
        ));

        let mut r = Report::default();
        r.add("t", &parsed);
        assert_eq!(r.packets, 6);
        assert_eq!(r.unknown_opcodes.get(&0xEE), Some(&1));
        assert_eq!(r.known_opcodes.get(&0x69), Some(&2));
        assert_eq!(
            r.cu_mask_writes.get("COMPUTE_STATIC_THREAD_MGMT_SE0"),
            Some(&1)
        );
        assert_eq!(r.unresolved.len(), 1);
        let text = r.render();
        assert!(text.contains("unknown opcodes (1)"));
        assert!(text.contains("unresolved:context+0x03ff"));
        assert!(text.contains("cu-mask register writes (Q3): 2"), "{text}");
    }
}
