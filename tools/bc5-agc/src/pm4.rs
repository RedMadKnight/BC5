// SPDX-License-Identifier: GPL-2.0-only
//! PM4 packet framing (`docs/formats/agc.md` §2). Header dword:
//! bits 31:30 type; type 3: 29:16 `count-1`, 15:8 opcode, bit 1 shader type,
//! bit 0 predicate; type 0: 29:16 `count-1`, 15:0 base register index;
//! type 2: filler. `count-1 == 0x3fff` encodes a zero-length packet.

/// One decoded packet.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Packet {
    /// Type 0: sequential register writes starting at `base` (dword index).
    Type0 {
        /// First register (MMIO dword offset).
        base: u16,
        /// Values written to `base`, `base + 1`, …
        values: Vec<u32>,
    },
    /// Type 2: one-dword filler.
    Type2,
    /// Type 3: an `IT_*` packet.
    Type3 {
        /// Opcode (`IT_*`).
        opcode: u8,
        /// Predicate bit.
        predicate: bool,
        /// Shader-type bit (compute vs graphics for some packets).
        shader_type: bool,
        /// Payload dwords after the header.
        payload: Vec<u32>,
    },
}

impl Packet {
    /// Total length in dwords including the header.
    pub fn len(&self) -> usize {
        match self {
            Packet::Type0 { values, .. } => 1 + values.len(),
            Packet::Type2 => 1,
            Packet::Type3 { payload, .. } => 1 + payload.len(),
        }
    }

    /// Never true: every packet has a header.
    pub fn is_empty(&self) -> bool {
        false
    }
}

/// Why parsing stopped.
#[derive(Debug, Clone, PartialEq, Eq, thiserror::Error)]
pub enum ParseError {
    /// The packet's declared length runs past the end of the stream.
    #[error("packet at dword {at} needs {need} more dwords, {have} left")]
    Truncated {
        /// Header position.
        at: usize,
        /// Payload dwords declared.
        need: usize,
        /// Dwords available after the header.
        have: usize,
    },
    /// Type 1 is reserved.
    #[error("reserved packet type 1 at dword {at}")]
    Type1 {
        /// Header position.
        at: usize,
    },
}

/// Packets decoded so far plus the error that stopped decoding, if any.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Parsed {
    /// `(header dword index, packet)` in stream order.
    pub packets: Vec<(usize, Packet)>,
    /// Set when the stream ended mid-packet or contained a reserved type.
    pub error: Option<ParseError>,
}

/// Payload length encoded in a type-0/3 header (`count-1` field, wrapping to
/// zero for `0x3fff`).
fn payload_len(header: u32) -> usize {
    let field = ((header >> 16) & 0x3fff) as usize;
    if field == 0x3fff {
        0
    } else {
        field + 1
    }
}

/// Decodes a dword stream. Stops at the first malformed packet and keeps
/// everything before it.
pub fn parse(dwords: &[u32]) -> Parsed {
    let mut out = Parsed::default();
    let mut at = 0usize;
    while at < dwords.len() {
        let header = dwords[at];
        let kind = header >> 30;
        if kind == 2 {
            out.packets.push((at, Packet::Type2));
            at += 1;
            continue;
        }
        if kind == 1 {
            out.error = Some(ParseError::Type1 { at });
            break;
        }
        let need = payload_len(header);
        let have = dwords.len() - at - 1;
        if need > have {
            out.error = Some(ParseError::Truncated { at, need, have });
            break;
        }
        let body = dwords[at + 1..at + 1 + need].to_vec();
        let packet = if kind == 0 {
            Packet::Type0 {
                base: (header & 0xffff) as u16,
                values: body,
            }
        } else {
            Packet::Type3 {
                opcode: ((header >> 8) & 0xff) as u8,
                predicate: header & 1 != 0,
                shader_type: header & 2 != 0,
                payload: body,
            }
        };
        out.packets.push((at, packet));
        at += 1 + need;
    }
    out
}

/// Builds a type-3 header for `payload` dwords of payload.
pub fn header3(opcode: u8, payload: usize) -> u32 {
    let count = if payload == 0 {
        0x3fff
    } else {
        (payload - 1) as u32 & 0x3fff
    };
    (3 << 30) | (count << 16) | (u32::from(opcode) << 8)
}

/// Builds a type-0 header.
pub fn header0(base: u16, values: usize) -> u32 {
    let count = if values == 0 {
        0x3fff
    } else {
        (values - 1) as u32 & 0x3fff
    };
    (count << 16) | u32::from(base)
}

/// The type-2 filler dword.
pub const FILLER: u32 = 2 << 30;

/// Splits little-endian bytes into dwords; returns the dwords and the number
/// of trailing bytes that did not form a whole dword.
pub fn dwords_from_le_bytes(bytes: &[u8]) -> (Vec<u32>, usize) {
    let words = bytes
        .chunks_exact(4)
        .map(|c| u32::from_le_bytes([c[0], c[1], c[2], c[3]]))
        .collect();
    (words, bytes.len() % 4)
}

/// Parses whitespace/comma-separated hex words (`0x` optional).
pub fn dwords_from_hex_text(text: &str) -> Result<Vec<u32>, String> {
    text.split(|c: char| c.is_whitespace() || c == ',')
        .filter(|t| !t.is_empty())
        .map(|t| {
            let t = t.trim_start_matches("0x").trim_start_matches("0X");
            u32::from_str_radix(t, 16).map_err(|e| format!("bad hex word {t:?}: {e}"))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    #[test]
    fn set_context_reg_header_from_kytyplus_matches() {
        // HANDOFF F2: 0xC0016900 seen in KytyPlus = SET_CONTEXT_REG with 2 payload dwords.
        assert_eq!(header3(0x69, 2), 0xC001_6900);
        let p = parse(&[0xC001_6900, 0x0000_0000, 0x1234_5678]);
        assert!(p.error.is_none());
        assert_eq!(
            p.packets,
            vec![(
                0,
                Packet::Type3 {
                    opcode: 0x69,
                    predicate: false,
                    shader_type: false,
                    payload: vec![0, 0x1234_5678]
                }
            )]
        );
    }

    #[test]
    fn fillers_type0_and_zero_length() {
        let stream = [FILLER, header0(0x2c00, 2), 7, 8, header3(0x10, 0), FILLER];
        let p = parse(&stream);
        assert!(p.error.is_none());
        assert_eq!(p.packets.len(), 4);
        assert_eq!(
            p.packets[1].1,
            Packet::Type0 {
                base: 0x2c00,
                values: vec![7, 8]
            }
        );
        assert_eq!(
            p.packets[2],
            (
                4,
                Packet::Type3 {
                    opcode: 0x10,
                    predicate: false,
                    shader_type: false,
                    payload: vec![]
                }
            )
        );
        assert_eq!(p.packets[2].1.len(), 1);
    }

    #[test]
    fn truncation_and_type1_are_reported_with_partial_results() {
        let p = parse(&[header3(0x10, 0), header3(0x69, 3), 1]);
        assert_eq!(p.packets.len(), 1);
        assert_eq!(
            p.error,
            Some(ParseError::Truncated {
                at: 1,
                need: 3,
                have: 1
            })
        );
        let p = parse(&[1 << 30]);
        assert_eq!(p.error, Some(ParseError::Type1 { at: 0 }));
    }

    #[test]
    fn byte_and_hex_inputs() {
        assert_eq!(
            dwords_from_le_bytes(&[0, 0x69, 1, 0xC0, 9]),
            (vec![0xC001_6900], 1)
        );
        assert_eq!(
            dwords_from_hex_text("0xC0016900, 0\n 12").unwrap(),
            vec![0xC001_6900, 0, 0x12]
        );
        assert!(dwords_from_hex_text("zz").is_err());
    }

    proptest! {
        #[test]
        fn parse_never_panics_and_consumes_everything(words in proptest::collection::vec(any::<u32>(), 0..64)) {
            let p = parse(&words);
            let consumed: usize = p.packets.iter().map(|(_, pk)| pk.len()).sum();
            prop_assert!(consumed <= words.len());
            prop_assert!(p.error.is_some() || consumed == words.len());
        }

        #[test]
        fn headers_round_trip(op in any::<u8>(), n in 0usize..0x3fff) {
            let p = parse(&{ let mut v = vec![header3(op, n)]; v.extend(std::iter::repeat(0).take(n)); v });
            prop_assert!(p.error.is_none());
            prop_assert_eq!(p.packets[0].1.len(), n + 1);
        }
    }
}
