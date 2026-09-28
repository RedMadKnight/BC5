# 0002 — Languages and licence

**Status.** Accepted, 2026-09-28. Summarises decisions D2 and D6 in `docs/HANDOFF.md` §7.

**Context.** The host runtime, RPCSX, is C++ and GPL-2.0. The tooling (container mount, AGC decoder) is mostly binary-format parsing, where memory safety and property testing matter more than sharing code with RPCSX.

**Decision.**
- D2: everything we write is **GPL-2.0-only**, so the backend can go upstream into RPCSX without relicensing. Ported files keep their original licence and say so in their header; nothing is ported from non-open-source or unlicensed repositories.
- D6: tools under `tools/` are **Rust 2021** (stable, `fuser`, `anyhow`/`thiserror`, `proptest`); the backend under `backend/` is **C++20** (CMake ≥ 3.25, `libdrm_amdgpu`, Catch2), buildable standalone with a stub host before being wired into RPCSX.

**Consequences.** Two toolchains in one repository. The Rust tools and the C++ backend share no code; they meet only through file formats (captures, container contents). `cargo clippy -D warnings`, `cargo fmt --check` and warnings-as-errors in C++ are part of the definition of done.
