# oozextract 0.5.5 (vendored)

Upstream: <https://github.com/lvlvllvlvllvlvl/oozextract>, crates.io `oozextract` 0.5.5,
MIT: the published crate declares `license = "MIT"` in its manifest and ships no license
file, so `LICENSE` here is the standard MIT text in the upstream authors' name. A Rust port of the open-source Oodle decompressors (Kraken, Mermaid,
Selkie, Leviathan, LZNA, Bitknit). `bc5-mount` uses its Kraken decoder for the inner image
of a PS5 package (`docs/formats/ps5pkg.md`).

Local changes, kept minimal so the crate can be updated and the change offered upstream:

- `src/algorithm/kraken.rs`, `src/decoder/mod.rs`: the Kraken chunk's "excess" length
  framing. After the 8-byte seed a chunk may carry a flag byte `10xxxxxx`: its low six bits
  (plus a continuation byte times 32 when they exceed 31) give the size of a substream at the
  end of the chunk holding the long length values; the entropy streams end before it, the
  number of long lengths is the number of 255 bytes in the packed length stream, and the
  values are read from both ends of that substream. Upstream (like the C++ `ooz` it ports)
  rejected such chunks with "excess bytes not supported". Every Kraken block of a PS5 package
  uses this framing. The format was taken from the two public decoders that implement it,
  LibProsperoPKG (`KrakenDecoder.cs`) and pkg-to-anyps5 (`src/kraken.rs`), both GPL-3.0,
  used as documentation only; `unpack_offsets` takes `Option<(start, end)>` of the substream
  instead of the unused `excess_flag` bool.
- `src/decoder/mod.rs`, `decode_bytes_type12`: a Huffman array whose table declares a single
  symbol is a memset of that symbol; the function returned `src - src_end` (0) as the number
  of bytes consumed, so its caller's `src_used == src_size` check failed and every such chunk
  was an error. It now returns `src_size`, as ooz's `Kraken_DecodeBytes_Type12` does. PS5
  packages store all-equal 128 KiB chunks this way (experiment 0036).
- `Cargo.toml`: `test-log` moved to the dev-dependencies it is used by (it pulled
  `env_logger` and `windows-sys` into every build, which the windows-gnu toolchain cannot
  link); the `cli` binary, the benchmark and the build script are dropped, as are the
  `wasm-test` and `perf` directories.

Everything else is the published 0.5.5 source.
