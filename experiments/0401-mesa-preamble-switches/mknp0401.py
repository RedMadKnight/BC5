#!/usr/bin/env python3
"""BC5 experiment 0401 series e, switch 1: the box tree's src/libs/libNpCppWebApi.cpp (exp 0328's port, md5 7c40b784) with
the ten SessionManager V2 entry points exp 0328's port missed (F809; exp 0402 section 1), ported from AnyPS5
(boykopovar/AnyPS5, GPL-2.0-only) core/libs/prx/libSceNpCppWebApi/Export.cpp @ 4f41f4c375f5abb487dbd184fbc150f31994d762.
They are registered only with KYTY_BC5_NP_SESSION_V2 on; off leaves the ten NIDs unregistered, as today. Each anchor
must occur exactly once. Prints the output's md5.
usage: mknp0401.py <unit in> <unit out>"""
import hashlib
import sys

NOT_SIGNED_IN = "request"
INIT = "initialize"

# (NID, mangled name, kind, AnyPS5 Export.cpp @ 4f41f4c37 line of the definition). The names hash to the NIDs with
# exp 0327's calculator (nid0401.py checks it); they are the title's link-time stubs (exp 0402 raw/title-stubs-vs-hosts.txt).
TEN = (
    ("eVU3cXIJz0w", "_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi20createPlayerSessionsEiRKNS4_31ParameterToCreatePlayerSessionsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_30PostPlayerSessionsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE", NOT_SIGNED_IN, 2162),
    ("BY1jyWLZrcA", "_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi25joinPlayerSessionAsPlayerEiRKNS4_36ParameterToJoinPlayerSessionAsPlayerERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_52PostPlayerSessionsSessionIdMemberPlayersResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE", NOT_SIGNED_IN, 1932),
    ("JiY4sfHkV34", "_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi18leavePlayerSessionEiRKNS4_29ParameterToLeavePlayerSessionERNS1_6Common11TransactionINS8_15DefaultResponseENS8_12IntrusivePtrINS8_18ResponseHeaderBaseEEEEE", NOT_SIGNED_IN, 2003),
    ("LbhH9NeB93I", "_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi27getPlayerSessionInvitationsEiRKNS4_38ParameterToGetPlayerSessionInvitationsERNS1_6Common11TransactionINS8_12IntrusivePtrINS3_54GetUsersAccountIdPlayerSessionsInvitationsResponseBodyEEENSA_INS8_18ResponseHeaderBaseEEEEE", NOT_SIGNED_IN, 2020),
    ("XuVY56j7GM0", "_ZN3sce2Np9CppWebApi14SessionManager2V117PlayerSessionsApi36ParameterToJoinPlayerSessionAsPlayer10initializeEPNS1_6Common10LibContextEPKcNS6_12IntrusivePtrINS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE", INIT, 2115),
    ("fIzsqjyD5oY", "_ZN3sce2Np9CppWebApi14SessionManager2V127RequestPlayerSessionFactory6createEPNS1_6Common10LibContextEiNS5_12IntrusivePtrINS3_32RequestPlayerSessionMemberPlayerEEERKNS5_6VectorINS5_6StringEEENS8_INS3_15LocalizedStringEEEPNS8_INS3_20RequestPlayerSessionEEE", NOT_SIGNED_IN, 2181),
    ("sRn6qePT54Q", "_ZN3sce2Np9CppWebApi14SessionManager2V139RequestCreatePlayerSessionPlayerFactory6createEPNS1_6Common10LibContextEPKcS9_RKNS5_6VectorINS5_12IntrusivePtrINS3_24PlayerSessionPushContextEEEEEPNSB_INS3_32RequestCreatePlayerSessionPlayerEEE", NOT_SIGNED_IN, 2279),
    ("-0Vv7HKZaBM", "_ZN3sce2Np9CppWebApi14SessionManager2V139RequestPlayerSessionMemberPlayerFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_32RequestCreatePlayerSessionPlayerEEEEEPNS9_INS3_32RequestPlayerSessionMemberPlayerEEE", NOT_SIGNED_IN, 1792),
    ("yl3T9brJay4", "_ZN3sce2Np9CppWebApi14SessionManager2V136PostPlayerSessionsRequestBodyFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_20RequestPlayerSessionEEEEEPNS9_INS3_29PostPlayerSessionsRequestBodyEEE", NOT_SIGNED_IN, 2316),
    ("xjVhrq2KPJA", "_ZN3sce2Np9CppWebApi14SessionManager2V158PostPlayerSessionsSessionIdMemberPlayersRequestBodyFactory6createEPNS1_6Common10LibContextERKNS5_6VectorINS5_12IntrusivePtrINS3_26RequestPlayerSessionPlayerEEEEEPNS9_INS3_51PostPlayerSessionsSessionIdMemberPlayersRequestBodyEEE", NOT_SIGNED_IN, 2312),
)

HEAD = """// ---- experiment 0401 series e: SessionManager V2, the ten entry points exp 0328's port missed (F809, exp 0402) ----
// Ported from AnyPS5 (boykopovar/AnyPS5, GPL-2.0-only), core/libs/prx/libSceNpCppWebApi/Export.cpp @ 4f41f4c37
// (the names are there since 8cd400aa4, also at 27c88a8). The four PlayerSessionsApi requests and the five factories
// fail as a console without a PSN sign-in fails, with SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN, and leave their out-pointers
// alone (the loader's return-0 stub reported success without writing them). ParameterToJoinPlayerSessionAsPlayer::
// initialize succeeds as this port's other parameter initialize calls do: AnyPS5 4f41f4c37 routes it through
// InitializeParameterWithBody, part of a parameter-object model (constructor, initialize, terminate) that this port,
// taken from 27c88a8, does not have; at 27c88a8 its body was `return 0`. Registered only with KYTY_BC5_NP_SESSION_V2
// on (InitNpCppWebApi_1). Lesson R32: name -> NID (nid0401.py) -> SymbolDatabase after InitAll -> function
// (npgate0401.cpp). AnyPS5's copyright remains with its authors; GPL-2.0-only as the rest of this file.

"""

REQUEST_BODY = "int KYTY_SYSV_ABI {name}() {{\n    return SCE_NP_WEBAPI_ERROR_NOT_SIGNED_IN;\n}}\n\n"
INIT_BODY = ("int KYTY_SYSV_ABI {name}(void* self, const uint64_t* context, const char* sessionId, const IntrusivePtr* body) {{\n"
             "    (void)self;\n    (void)context;\n    (void)sessionId;\n    (void)body;\n    return 0;\n}}\n\n")

FUNC_ANCHOR = b'} // extern "C"\n\nLIB_DEFINE(InitNpCppWebApi_1) {\n'
REG_ANCHOR = b"}\n\n} // namespace Libs::NpCppWebApi\n"
REG_HEAD = """
\t// Experiment 0401 series e (KYTY_BC5_NP_SESSION_V2, default off): the ten SessionManager V2 entry points above. The
\t// switch is read here, not cached, so the R32 gate (npgate0401.cpp) checks both settings with one binary. Off: the
\t// ten NIDs stay unregistered and the loader answers them with its return-0 stub, as before.
\t{
\t\tconst char* v2 = std::getenv("KYTY_BC5_NP_SESSION_V2");
\t\tconst bool  on = v2 != nullptr && v2[0] != '\\0' && std::strcmp(v2, "0") != 0;
\t\t{
\t\t\tCommon::HostException::RawLog log;
\t\t\tlog.Append(on ? "[bc5] exp 0401: NpCppWebApi SessionManager V2 on (10 exports registered)\\n"
\t\t\t              : "[bc5] exp 0401: NpCppWebApi SessionManager V2 off (the loader's stubs)\\n");
\t\t\tlog.Flush();
\t\t}
\t\tif (on) {
"""
REG_TAIL = "\t\t}\n\t}\n"


def functions():
    out = HEAD
    for _, name, kind, _ in TEN:
        out += (INIT_BODY if kind == INIT else REQUEST_BODY).format(name=name)
    return out.encode()


def registration():
    out = REG_HEAD
    for nid, name, _, _ in TEN:
        out += f'\t\t\tLIB_FUNC("{nid}", {name});\n'
    return (out + REG_TAIL).encode()


def edit(s):
    assert b"KYTY_BC5_NP_SESSION_V2" not in s and b"experiment 0401 series e" not in s, "the unit has the block already"
    for nid, name, _, _ in TEN:
        assert name.encode() not in s, ("the unit defines it already", name[:60])
        assert f'LIB_FUNC("{nid}"'.encode() not in s, ("the unit registers it already", nid)
    assert len({n for n, _, _, _ in TEN}) == 10 and len({m for _, m, _, _ in TEN}) == 10
    assert s.count(FUNC_ANCHOR) == 1, ("the end of the extern block", s.count(FUNC_ANCHOR))
    assert s.count(REG_ANCHOR) == 1, ("the end of InitNpCppWebApi_1", s.count(REG_ANCHOR))
    assert s.index(FUNC_ANCHOR) < s.index(REG_ANCHOR)
    s = s.replace(FUNC_ANCHOR, functions() + FUNC_ANCHOR)
    s = s.replace(REG_ANCHOR, registration() + REG_ANCHOR)
    return s


def main():
    assert len(sys.argv) == 3, __doc__
    with open(sys.argv[1], "rb") as f:
        s = f.read()
    out = edit(s)
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    print(hashlib.md5(out).hexdigest())


if __name__ == "__main__":
    main()
