# Task: AMM pool scatter fix (KYTY_BC5_AMM_SCATTER) for the BC5 host

## Background

The BC5 PS5 emulator (KytyPlus based) dies when guest memory is lowered to 12,704 or 12,800 MiB instead of 13,824. The
error is "AMM virtual-memory unmap is unsupported" from `KernelHandleReservedRangeAccessViolation` (memory.cpp): the
title touched an AMM page that was never mapped, because an AMM auto-pool map had been refused.

The cause is fragmentation (see `ammpool0401-notes.md`). At the failure the pool's free list held 212 MiB, but a 64 MiB
auto map needs ONE contiguous free range, and the contiguous direct-memory borrow failed too.

## What to build (design D1 in ammpool0401-notes.md)

A switch, `KYTY_BC5_AMM_SCATTER`:
- unset, empty or "0": off. Today's code, with exactly the same behaviour.
- `journal`: today's behaviour, plus one log line whenever a contiguous map fails but scattered pieces would fit.
- `rescue`: only where today's code returns EAGAIN or fails, satisfy the auto map from several free pieces, and borrow
  any shortfall from direct memory in pieces.
- `first`: always allow the scattered path.

`Bc5ExecuteAmmMap0401` looks up a single record; it must walk all the pieces.

Only `libAmpr.cpp` changes. `memory.cpp` stays untouched.

## Files

- `e8/x-amm/src/libs/libAmpr.cpp` (the input, md5 0a1762f6): the file to edit.
- `e8/x5-jit/src/kernel/memory.cpp` and `memoryAddressSpace.inc`: read only.
- `e8/mkamm0401.py` and `e8/amm0401.cpp`: the house style for an edit script and a CPU test.
- `ammpool0401-notes.md`: the design and its line references.
- `ref/kytyplus/src`: upstream KytyPlus headers and sources, read only.
- `ref/anyps5/`: AnyPS5's AMM/APR implementation and tests (GPL), for ideas only.

## Deliverables (all in work/)

1. **`work/mkpool0401.py <in libAmpr.cpp> <out dir>`.** It writes the edited libAmpr.cpp and prints its md5. A second run
   on its own output must refuse with "has the edit already", as `mkamm0401.py` does.
2. **`work/pool0401.cpp`.** A standalone CPU test (no GPU, no emulator) that copies the pool/allocator logic it needs and
   checks:
   - the 11-03 18:14 shape: 212 MiB free in pieces and a 64 MiB map. Off: refused. `rescue` and `first`: succeeds with
     pieces;
   - off, unset and "0" give results identical to the original code;
   - unmapping a scattered map frees every piece, with no overlap and no leak.

   Build: `g++ -std=c++20 -O1 -Wall work/pool0401.cpp -o work/pool0401 && ./work/pool0401`. It must print PASS lines and
   exit 0.
3. **`work/NOTES.md`.** What you changed, each edit with its line numbers, and the open risks.

## Rules

- Do not touch anything outside ~/bc5-agent. No network use, no sudo, no other services on this machine.
- No game files, no Sony material.
- Commit your work in ~/bc5-agent with git each time a deliverable passes.
