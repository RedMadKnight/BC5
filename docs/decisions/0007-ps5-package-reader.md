# 0007 — Read PS5 packages in `bc5-mount`, with a vendored, patched Kraken decoder

Date: 2026-10-08. Status: accepted.

## Context

The maintainer builds packages (`.pkg`, `\x7fFIH`) from games they own, and a package is a
second way a game reaches the host besides the `.ffpfsc` container of ADR 0003. Its inner
image is stored as 256 KiB blocks, most of them Oodle Kraken-compressed (`docs/formats/ps5pkg.md`).
Three facts shaped the decision:

- Every public package reader is GPL-3.0 (LibProsperoPKG, pkg-to-anyps5, PS5PCEM), which our
  GPL-2.0-only cannot take code from (ADR 0003 had the same constraint for `.ffpfsc`).
- The Kraken blocks need a decoder. Writing one is weeks; the open-source C++ `ooz` has a
  Rust port, `oozextract` 0.5.5 (MIT), but neither implements the "excess" length framing
  every block of the test package uses.
- `oozextract` pulls `test-log` (hence `windows-sys`) into every build, which the maintainer's
  windows-gnu toolchain cannot link.

## Decision

1. `bc5-mount` reads packages as a second container format behind one `FileTree` trait
   (`src/tree.rs`) that the CLI and the FUSE mount work on; the file's magic picks the
   reader. The format notes are written from the public readers' documentation and
   verified against the maintainer's package; no code is ported.
2. `oozextract` is vendored in `tools/third_party/oozextract` (MIT, license kept, changes
   listed in `README-bc5.md`): the excess framing added, `test-log` moved to the
   dev-dependencies, the binary and benchmark dropped. The crate is excluded from the
   workspace so it keeps its own lints. The change will be offered upstream; until then the
   vendored copy is the dependency, approved by the maintainer on 2026-10-08.
3. Only plaintext outer images are read. An encrypted one (retail, or built with a passcode)
   is refused with a message; the key schedule is not implemented and will not be.
4. Tests use synthetic packages from the fixture writer (stored, entropy-only and sparse
   blocks). The LZ decoder is covered by experiment 0031 on the maintainer's package, which
   is never committed; the Kraken encoder is out of scope.

## Consequences

- One more format in `bc5-mount`, ~1,400 lines plus the vendored 6,700 of the decoder.
- Windows builds work again without toolchain tricks.
- A package with a producer's layout variant the walk rejects fails loudly (`inspect`
  prints why) rather than producing wrong files.
- The vendored crate must be refreshed by hand when upstream moves; the README lists what
  to reapply.
