# Series e, switch 1: NpCppWebApi SessionManager V2 (notes for the build)

**What.** `mknp0401.py` adds ten `extern "C"` entry points to the box tree's `src/libs/libNpCppWebApi.cpp` (exp 0328's port, md5 `7c40b784e36ef45e816be07b0a3fb0a8`). Output md5 `935fcc7e4ab1108f3d2d8b33eaf65bf6`. These are the ten link-time stubs left after exp 0328 (F809, exp 0402 §1). They are registered in `InitNpCppWebApi_1` only when `KYTY_BC5_NP_SESSION_V2` is on (set, non-empty, not `0`). The switch is read at registration and not cached. Registration writes one stderr line through the unit's `RawLog`:

- on: `[bc5] exp 0401: NpCppWebApi SessionManager V2 on (10 exports registered)`
- off: `[bc5] exp 0401: NpCppWebApi SessionManager V2 off (the loader's stubs)`

With the switch off, the ten NIDs stay unregistered. On the laptop, the output with the two inserted blocks removed equals the input byte for byte. Braces and parentheses balance.

**Source.** AnyPS5 (boykopovar/AnyPS5, GPL-2.0-only), `core/libs/prx/libSceNpCppWebApi/Export.cpp` at `4f41f4c375f5abb487dbd184fbc150f31994d762` (blob `16b152f9`, 6,862 lines). Each definition is three lines:

| NID | Function | Export.cpp line | Body there → here |
|---|---|---|---|
| `eVU3cXIJz0w` | `PlayerSessionsApi::createPlayerSessions` | 2162 | `return SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN` |
| `BY1jyWLZrcA` | `joinPlayerSessionAsPlayer` | 1932 | same |
| `JiY4sfHkV34` | `leavePlayerSession` | 2003 | same |
| `LbhH9NeB93I` | `getPlayerSessionInvitations` | 2020 | same |
| `XuVY56j7GM0` | `ParameterToJoinPlayerSessionAsPlayer::initialize` | 2115 | `InitializeParameterWithBody(...)` → `return 0` (see below) |
| `fIzsqjyD5oY` | `RequestPlayerSessionFactory::create` | 2181 | NOT_SIGNED_IN |
| `sRn6qePT54Q` | `RequestCreatePlayerSessionPlayerFactory::create` | 2279 | NOT_SIGNED_IN |
| `-0Vv7HKZaBM` | `RequestPlayerSessionMemberPlayerFactory::create` | 1792 | NOT_SIGNED_IN |
| `yl3T9brJay4` | `PostPlayerSessionsRequestBodyFactory::create` | 2316 | NOT_SIGNED_IN |
| `xjVhrq2KPJA` | `PostPlayerSessionsSessionIdMemberPlayersRequestBodyFactory::create` | 2312 | NOT_SIGNED_IN |

AnyPS5's nine request and factory bodies take no parameters and are copied as they are. `APS5_VABI` becomes `KYTY_SYSV_ABI`, as in exp 0328. The factories no longer report success without writing their out-pointer, as the loader's return-0 stub did.

**Adapted: `initialize`.** At `4f41f4c37`, AnyPS5 routes it through `InitializeParameterWithBody`. That helper belongs to a parameter-object model in which the constructor zeroes `{base, implementation}`, `initialize` checks the context and the body, and `terminate` clears them (Export.cpp:351-392).

Our port was taken from `27c88a8` and has no such model. The same class's constructor (`exp…C1Ev`) and `terminate` are `return 0` stubs in our unit, so the helper would read an uninitialised `implementation`. Our port's other parameter `initialize`s return 0, and at `27c88a8` this body was `return 0` too (line 1201). The new function therefore takes the real arguments (`this`, `LibContext*`, `const char*`, `IntrusivePtr*`), ignores them and returns 0. This is a deliberate choice: porting the whole parameter model would be a separate change to the 136 existing entry points.

**R32.**
- `nid0401.py` (laptop) prints `nid0401: 10 of 10; end`. Each mangled name in `mknp0401.py`'s table hashes to its NID with exp 0327's calculator. The calculator is self-checked first on strcmp, strncmp and strcpy_s.
- On the laptop, each name occurs once in Export.cpp @ 4f41f4c37, at the listed line, with the listed body.
- `npgate0401.cpp` is the box half. It runs `Libs::InitAll` into a fresh `Loader::SymbolDatabase` and checks two lookups:
  - `FindByNid(nid, Func)` (first match)
  - `Find(key)` (the title's import key: `libSceNpCppWebApi` v1, module 1.1, Func; last registration wins). Together the two catch a collision in either order.
- With the switch on, both lookups must return the function's address, its debug name must be the mangled name, and its library and module must match exp 0328's `ZZpDSZob2Bs`. With the switch off, neither may find anything.
- The gate then calls the nine requests and factories with no arguments and expects `0x80552907`. It calls `initialize(nullptr × 4)` and expects 0. No call is skipped: every body ignores its arguments.

**Gate build step (box).**
1. Compile: take the compdb command for `src/CMakeFiles/kyty_emulator.dir/libs/libNpCppWebApi.cpp.o`, clean it as build0401.py does (drop `-MD -MT -MF`), and swap `-c` to `npgate0401.cpp` and `-o` to `npgate0401.o`. It needs only the tree's own headers (`common/abi.h`, `libs/libs.h`, `loader/symbolDatabase.h`), which the command already finds.
2. Link: take the `src/kyty_emulator` link command. Swap in every private object of series e, drop `…/main.cpp.o`, add `npgate0401.o`, point `-o` at `npgate0401`, and rewrite `-Wl,-Map=` and `--dependency-file=` as build0401.py does. Libraries stay as on the link line.
3. Run all three; each must end with `; end`:
   - `KYTY_BC5_NP_SESSION_V2=1 ./npgate0401 on`, expecting `npgate0401: on 10 of 10 registered as their functions in [NpCppWebApi_v1][NpCppWebApi_v1.1][Func], 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; end`
   - `KYTY_BC5_NP_SESSION_V2=0 ./npgate0401 off`, expecting `npgate0401: off 10 of 10 unregistered, 9 of 9 NOT_SIGNED_IN, initialize 1 of 1; end`
   - with the variable unset, `./npgate0401 off`
   Each run also prints the unit's `[bc5] exp 0401: … on|off` line on stderr.

**Doubts.**
- Not compiled anywhere yet (no compiler on the laptop).
- The gate assumes `InitAll` only registers. The two `LIB_DEFINE` bodies read (bc5LleAgc.cpp, libKernel.cpp) do only that; the others were not read.
- `RawLog` going to stderr is taken from exp 0328's README.
