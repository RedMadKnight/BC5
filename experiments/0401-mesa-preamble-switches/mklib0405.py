#!/usr/bin/env python3
"""BC5 experiment 0405 (series e5 of experiment 0401), tag "lib": exp 0405's R1 items #1-#4 and R2 KS05, SK07, KL03 in four
library units of the e5 input tree (KytyPlus f266548 + patch 0001 + e4's private units), each behind a switch that is off by
default and read once (off is today's path exactly):
  src/libs/libJson2.cpp          KYTY_BC5_JSON2_FIXES           value,string,array,object  R1 #1 + R2 KS05 (AnyPS5
                                                                  fa8239009 f8e4d8acb e237f1bfe 3e03f8df7; KytyPS5 dfec14a)
  src/libs/libUlt.cpp            KYTY_BC5_ULT_FIXES             join,queue                 R1 #2 (AnyPS5 ffe469199) +
                                                                                             R2 SK07 (sharpemu 514d766)
  src/libs/libUserService.cpp    KYTY_BC5_USERSERVICE_VALUES    age,login,name,zoom        R1 #3 + R2 KL03 (AnyPS5 debt
                                                                  libSceUserService.md:54,57,58: PS5 13.60; KytyPS5 dfec14a)
  src/libs/libSystemService.cpp  KYTY_BC5_SYSTEMSERVICE_VALUES  int,table,string           R1 #4 (AnyPS5 debt
                                 KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000                      libSceSystemService.md:69,74,216)
A value naming items ("value,object") turns on only those; any other non-empty value but "0" turns on all of them.
Each unit's input md5 is pinned and asserted; a unit that has the edit already is refused; every anchor must occur exactly
once; every edit keeps braces, parentheses and brackets balanced; the inserted text is ASCII; line ends stay as they are
(libUserService.cpp is CRLF, the other three LF). After editing, the script undoes its own edits on the output and asserts
that this gives the input back byte for byte. Only the four units are written. Prints "<relpath> <md5>" per written file.
Notes: lib0405-notes.md; CPU test: lib0405.cpp.
usage: mklib0405.py <tree root in> <out dir>"""
import hashlib
import os
import sys

MARKS = (b"experiment 0405", b"KYTY_BC5_JSON2_FIXES", b"KYTY_BC5_ULT_FIXES", b"KYTY_BC5_USERSERVICE_VALUES",
         b"KYTY_BC5_SYSTEMSERVICE_VALUES", b"KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000", b"Bc5Json2", b"Bc5Ult", b"Bc5User",
         b"Bc5Sys")


def T(text, crlf=False):
    """C++ text written with a visible tab ("»") for each tab of the file's indentation, as ASCII bytes."""
    out = text.replace("»", "\t").encode("ascii")
    if crlf:
        assert b"\r" not in out
        out = out.replace(b"\n", b"\r\n")
    return out


# =====================================================================================================================
# src/libs/libJson2.cpp (R1 #1, R2 KS05)
# =====================================================================================================================
JSON2_BLOCK_ANCHOR = "static void JsonValueCopy(JsonValue* dst, const JsonValue* src) {\n"
JSON2_BLOCK = r"""// ---- BC5 experiment 0405 (series e5 of experiment 0401): KYTY_BC5_JSON2_FIXES, assignment that copies its source first ----
// Ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @ 4f41f4c375f5abb487dbd184fbc150f31994d762,
// core/libs/prx/libSceJson2/Export.cpp:1299-1320 (OwnsPayload, AssignPayload) and 1370-1383 (AssignNode): a source that the
// destination owns, or that lies below it, is copied into a temporary before the destination is released. Commits fa8239009
// and 3e03f8df7 (descendant assignment), f8e4d8acb (collection self-setting), e237f1bfe (String setter aliases). Also KytyPS5
// (github.com/KytyPS5/KytyPS5, GPL-2.0) @ dfec14a src/libs/libJson2.cpp:626-636 and 987-996 (exp 0405 R2 KS05: SetObject and
// Object::operator= build the copy before they destroy the target). Only that idea is taken. Not taken: AnyPS5's allocator
// details, and what its f8e4d8acb / e237f1bfe notes found on an SDK reference module (that self-setting rebuilds a
// collection, that a self-aliased String keeps its storage): reference-module facts, held tonight. Here a value set to its
// own String, Array or Object, and an Object assigned to itself, stay as they are, as Value::operator= with dst == src
// already did. Today the clear of the destination frees a source inside it before the source is read: v = v["a"],
// v.set(v.getString()), v.set(v.getString().c_str()), v.set(v.getArray()), v.set(v["a"].getObject()) read freed memory, and
// obj = obj empties obj. KYTY_BC5_JSON2_FIXES: unset, empty or "0" is off (today's path exactly); any other value turns every
// item on, unless it names items (comma-separated): "value" (Value::operator= 4zrm6VrgIAw, set(const Value&) XL8+BUqjB1w),
// "string" (set(const String&) 6l3Bv2gysNc, set(const char*) n6FC+l9DU70), "array" (set(const Array&) 195ad-jAsTU),
// "object" (set(const Object&) dFCphqnd+a4, Object::operator= urOpESTBZmo). Read once; one stderr line at registration.
// AnyPS5's and KytyPS5's copyrights remain with their authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_JSON2_FIX_VALUE  = 1u;
static constexpr uint32_t BC5_JSON2_FIX_STRING = 2u;
static constexpr uint32_t BC5_JSON2_FIX_ARRAY  = 4u;
static constexpr uint32_t BC5_JSON2_FIX_OBJECT = 8u;
static constexpr uint32_t BC5_JSON2_FIX_ALL    = 15u;

static uint32_t Bc5Json2FixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»static const char* const names[] = {"value", "string", "array", "object"}; // bit i is names[i]
»uint32_t                 parts   = 0;
»const char*              p       = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (uint32_t i = 0; i < 4; i++) {
»»»if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
»»»»parts |= 1u << i;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : BC5_JSON2_FIX_ALL;
}

// The items of KYTY_BC5_JSON2_FIXES that are on (0: off), read once; the first call prints the switch's line.
static uint32_t Bc5Json2Fixes() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5Json2FixesParse(std::getenv("KYTY_BC5_JSON2_FIXES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: json2 off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: json2 on (items:%s%s%s%s)\n", (p & BC5_JSON2_FIX_VALUE) != 0 ? " value" : "",
»»»             (p & BC5_JSON2_FIX_STRING) != 0 ? " string" : "", (p & BC5_JSON2_FIX_ARRAY) != 0 ? " array" : "",
»»»             (p & BC5_JSON2_FIX_OBJECT) != 0 ? " object" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

static bool Bc5Json2Fix(uint32_t item) {
»return (Bc5Json2Fixes() & item) != 0;
}

static void JsonValueCopy(JsonValue* dst, const JsonValue* src); // below; the copies here go into fresh values (today's path)

// True when clearing the value frees memory that a source could be in (its string, array or object).
static bool Bc5Json2Owns(const JsonValue* v) {
»return v->type == JsonValueTypeString || v->type == JsonValueTypeArray || v->type == JsonValueTypeObject;
}

// Moves the payload of `from` (a fresh value no one else refers to) into `to`, just cleared, and points the moved members'
// parent at `to`, as today's copy does; `from` is left null. `to`'s parent and rootparam stay as the clear left them.
static void Bc5Json2Adopt(JsonValue* to, JsonValue* from) {
»to->type = from->type;
»switch (from->type) {
»»case JsonValueTypeBoolean: to->boolean = from->boolean; break;
»»case JsonValueTypeInteger: to->integer = from->integer; break;
»»case JsonValueTypeUInteger: to->uinteger = from->uinteger; break;
»»case JsonValueTypeReal: to->real = from->real; break;
»»case JsonValueTypeString: to->string = from->string; break;
»»case JsonValueTypeArray:
»»»to->array = from->array;
»»»for (auto* item: *JsonArrayImpl(to->array)) {
»»»»item->parent = to;
»»»}
»»»break;
»»case JsonValueTypeObject:
»»»to->object = from->object;
»»»for (auto& item: *JsonObjectImpl(to->object)) {
»»»»item.second->parent = to;
»»»}
»»»break;
»»default: to->uinteger = 0; break;
»}
»JsonValueInit(from);
}

// "value": JsonValueCopy into a value that owns a payload copies the source into a fresh value first, then clears the
// value and moves the copy in (v = v["a"], v["a"] = v). A value that owns nothing takes today's path: its clear frees
// nothing a source could be in. False: today's path.
static bool Bc5Json2CopySnapshot(JsonValue* dst, const JsonValue* src) {
»if (!Bc5Json2Owns(dst) || !Bc5Json2Fix(BC5_JSON2_FIX_VALUE)) {
»»return false;
»}
»JsonValue copy {};
»JsonValueInit(&copy);
»JsonValueCopy(&copy, src); // `copy` owns nothing: today's path, which reads src while it is whole
»JsonValueClear(dst);
»Bc5Json2Adopt(dst, &copy);
»return true;
}

// "string": set(const String&) and set(const char*), given the text as a copy taken before the clear. `own` is the String
// argument (nullptr for a char*): the value's own String leaves the value as it is.
static void Bc5Json2SetText(JsonValue* self, const JsonString* own, std::string text) {
»if (self != nullptr && own != nullptr && self->type == JsonValueTypeString && self->string == own) {
»»return;
»}
»JsonValueClear(self);
»if (self != nullptr) {
»»self->type   = JsonValueTypeString;
»»self->string = JsonStringNew(text);
»}
}

// "array": set(const Array&) builds the copy in a fresh value first, then clears the value and moves the copy in (the
// Array may be the value's own or a member's). The value's own Array leaves it as it is. False: today's path (off, or the
// value owns nothing a source could be in).
static bool Bc5Json2SetArray(JsonValue* self, const JsonArray* src) {
»if (self == nullptr || !Bc5Json2Owns(self) || !Bc5Json2Fix(BC5_JSON2_FIX_ARRAY)) {
»»return false;
»}
»if (self->type == JsonValueTypeArray && self->array == src) {
»»return true;
»}
»JsonValue copy {};
»JsonValueInit(&copy);
»copy.type  = JsonValueTypeArray;
»copy.array = JsonArrayNew();
»for (auto* item: *JsonArrayImpl(src)) {
»»auto* c = JsonValueNew();
»»JsonValueCopy(c, item);
»»copy.array->impl->push_back(c);
»}
»JsonValueClear(self);
»Bc5Json2Adopt(self, &copy);
»return true;
}

// "object": set(const Object&), as Bc5Json2SetArray for an Object (KytyPS5 dfec14a libJson2.cpp:626-636).
static bool Bc5Json2SetObject(JsonValue* self, const JsonObject* src) {
»if (self == nullptr || !Bc5Json2Owns(self) || !Bc5Json2Fix(BC5_JSON2_FIX_OBJECT)) {
»»return false;
»}
»if (self->type == JsonValueTypeObject && self->object == src) {
»»return true;
»}
»JsonValue copy {};
»JsonValueInit(&copy);
»copy.type   = JsonValueTypeObject;
»copy.object = JsonObjectNew();
»for (const auto& item: *JsonObjectImpl(src)) {
»»auto* c = JsonValueNew();
»»JsonValueCopy(c, item.second);
»»(*copy.object->impl)[item.first] = c;
»}
»JsonValueClear(self);
»Bc5Json2Adopt(self, &copy);
»return true;
}

// "object": Object::operator= copies the source's members before it destroys the object's own (the source may be the
// object itself or a member's object; KytyPS5 dfec14a libJson2.cpp:987-996); an Object assigned to itself stays as it is.
// The copies' parent stays null, as today's copy constructor leaves it. False: today's path.
static bool Bc5Json2ObjectAssign(JsonObject* self, const JsonObject* src) {
»if (!Bc5Json2Fix(BC5_JSON2_FIX_OBJECT)) {
»»return false;
»}
»if (self == nullptr || self == src) {
»»return true;
»}
»auto* impl = new std::map<std::string, JsonValue*>;
»for (const auto& item: *JsonObjectImpl(src)) {
»»auto* copy = JsonValueNew();
»»JsonValueCopy(copy, item.second);
»»(*impl)[item.first] = copy;
»}
»if (self->impl != nullptr) {
»»for (auto& item: *self->impl) {
»»»JsonValueDelete(item.second);
»»}
»»delete self->impl;
»}
»self->impl = impl;
»return true;
}
// ---- end of experiment 0405's Json2 helpers ----

"""

JSON2_EDITS = (
    ("include <cstdio>",
     "#include <cstdlib>\n#include <cstring>\n#include <map>\n",
     "#include <cstdio> // BC5 experiment 0405: std::fprintf\n#include <cstdlib>\n#include <cstring>\n#include <map>\n"),
    ("JsonValueCopy: value",
     "»if (dst == nullptr || src == nullptr || dst == src) {\n»»return;\n»}\n\n»JsonValueClear(dst);\n»dst->type = src->type;\n",
     "»if (dst == nullptr || src == nullptr || dst == src) {\n»»return;\n»}\n"
     "»if (Bc5Json2CopySnapshot(dst, src)) { // BC5 experiment 0405 (KYTY_BC5_JSON2_FIXES \"value\"); false when off\n"
     "»»return;\n»}\n\n»JsonValueClear(dst);\n»dst->type = src->type;\n"),
    ("JsonValueSetString: string",
     "static void KYTY_SYSV_ABI JsonValueSetString(JsonValue* self, const JsonString* value) {\n»PRINT_NAME();\n\n»JsonValueClear(self);\n",
     "static void KYTY_SYSV_ABI JsonValueSetString(JsonValue* self, const JsonString* value) {\n»PRINT_NAME();\n\n"
     "»if (Bc5Json2Fix(BC5_JSON2_FIX_STRING)) { // BC5 experiment 0405 (KYTY_BC5_JSON2_FIXES \"string\"): the text first\n"
     "»»Bc5Json2SetText(self, value, *JsonStringImpl(value));\n»»return;\n»}\n»JsonValueClear(self);\n"),
    ("JsonObjectAssign: object",
     "static JsonObject* KYTY_SYSV_ABI JsonObjectAssign(JsonObject* self, const JsonObject* src) {\n»PRINT_NAME();\n\n»JsonObjectDtor(self);\n",
     "static JsonObject* KYTY_SYSV_ABI JsonObjectAssign(JsonObject* self, const JsonObject* src) {\n»PRINT_NAME();\n\n"
     "»if (Bc5Json2ObjectAssign(self, src)) { // BC5 experiment 0405 (KYTY_BC5_JSON2_FIXES \"object\"); false when off\n"
     "»»return self;\n»}\n»JsonObjectDtor(self);\n"),
    ("JsonValueSetArrayCopy: array",
     "static void JsonValueSetArrayCopy(JsonValue* self, const JsonArray* src) {\n»JsonValueClear(self);\n",
     "static void JsonValueSetArrayCopy(JsonValue* self, const JsonArray* src) {\n"
     "»if (Bc5Json2SetArray(self, src)) { // BC5 experiment 0405 (KYTY_BC5_JSON2_FIXES \"array\"); false when off\n"
     "»»return;\n»}\n»JsonValueClear(self);\n"),
    ("JsonValueSetObject: object",
     "static void KYTY_SYSV_ABI JsonValueSetObject(JsonValue* self, const JsonObject* src) {\n»PRINT_NAME();\n\n»JsonValueClear(self);\n",
     "static void KYTY_SYSV_ABI JsonValueSetObject(JsonValue* self, const JsonObject* src) {\n»PRINT_NAME();\n\n"
     "»if (Bc5Json2SetObject(self, src)) { // BC5 experiment 0405 (KYTY_BC5_JSON2_FIXES \"object\"); false when off\n"
     "»»return;\n»}\n»JsonValueClear(self);\n"),
    ("JsonValueSetCString: string",
     "static void KYTY_SYSV_ABI JsonValueSetCString(JsonValue* self, const char* str) {\n»PRINT_NAME();\n\n»JsonValueClear(self);\n",
     "static void KYTY_SYSV_ABI JsonValueSetCString(JsonValue* self, const char* str) {\n»PRINT_NAME();\n\n"
     "»if (Bc5Json2Fix(BC5_JSON2_FIX_STRING)) { // BC5 experiment 0405 (KYTY_BC5_JSON2_FIXES \"string\"): the text first\n"
     "»»Bc5Json2SetText(self, nullptr, str != nullptr ? str : \"\");\n»»return;\n»}\n»JsonValueClear(self);\n"),
    ("registration: the switch's line",
     "LIB_DEFINE(InitNet_1_Json2) {\n",
     "LIB_DEFINE(InitNet_1_Json2) {\n"
     "»(void)Bc5Json2Fixes(); // BC5 experiment 0405: reads KYTY_BC5_JSON2_FIXES once and prints its line, on or off\n"),
)
JSON2_BEFORE = ("static void JsonValueClear(JsonValue* self) {\n", "static JsonValue* JsonValueNew() {\n",
                "static void JsonValueDelete(JsonValue* self) {\n", "static void JsonValueInit(JsonValue* self) {\n",
                "static JsonArray* JsonArrayNew() {\n", "static JsonObject* JsonObjectNew() {\n",
                "static JsonString* JsonStringNew(const std::string& value) {\n")
JSON2_AFTER = ("static void KYTY_SYSV_ABI JsonValueSetString(", "static JsonObject* KYTY_SYSV_ABI JsonObjectAssign(",
               "static void JsonValueSetArrayCopy(", "static void KYTY_SYSV_ABI JsonValueSetObject(",
               "static void KYTY_SYSV_ABI JsonValueSetCString(", "LIB_DEFINE(InitNet_1_Json2) {")
JSON2_USES = (("static uint32_t Bc5Json2Fixes()", 1), ("Bc5Json2Fixes()", 3), ("Bc5Json2Fix(", 7),
              ("Bc5Json2CopySnapshot(", 2), ("Bc5Json2SetText(", 3), ("Bc5Json2SetArray(", 2),
              ("Bc5Json2SetObject(", 2), ("Bc5Json2ObjectAssign(", 2), ("Bc5Json2Adopt(", 4), ("Bc5Json2Owns(", 4))

# =====================================================================================================================
# src/libs/libUlt.cpp (R1 #2, R2 SK07)
# =====================================================================================================================
ULT_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI UltUlthreadCreate(void* ulthread, const char* name, UltUlthreadEntry entry,\n"
ULT_BLOCK = r"""// ---- BC5 experiment 0405 (series e5 of experiment 0401): KYTY_BC5_ULT_FIXES ----
// "join" (exp 0405 R1 #2): ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @
// 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceUlt/Export.cpp:125-185 (gCurrentUlthread, ulthreadRunner,
// joinUlthread) and 881-916 (sceUltUlthreadCreate, sceUltUlthreadJoin), commit ffe469199 "serialize ulthread publication and
// join ownership". Today UltUlthreadCreate publishes the handle before PthreadCreate has made the thread, and
// UltUlthreadJoin takes no claim: a join that finds the handle early reads a thread not made yet, and two joins of one
// ulthread (or a join from the ulthread itself) call PthreadJoin on one thread twice. With "join": a join of a handle
// whose creation still runs waits for it (a per-ulthread mutex the creator holds from the publication until PthreadCreate
// returned; AnyPS5 holds its global lock across PthreadCreate instead, which would make every other Ult call wait for a
// thread creation); a second join while one is in progress, and a join from the ulthread itself, get ULT_ERROR_STATE
// without calling PthreadJoin; a failed PthreadJoin releases the claim; a failed PthreadCreate unpublishes the handle.
// Host lifecycle rules, not console facts: the STATE answer to the losing joiner is AnyPS5's choice (its debt note
// docs/dev/debt/libSceUlt.md: native concurrent-join errors unverified). TODO(verify) on a console.
// "queue" (exp 0405 R2 SK07): after sharpemu (GPL-2.0-or-later) @ 514d766 SharpEmu.Libs/Ult/UltExports.Sync.cs:518-560: a
// push to a queue that holds as many items as its data pool's num_data keeps the item (the queue grows) where today it is
// dropped with OK returned; capacity stays informational. sharpemu says the console blocks such a push and that a push
// that never blocks cannot deadlock a guest; TODO(verify) the console's blocking. The first 8 such pushes get a stderr line.
// KYTY_BC5_ULT_FIXES: unset, empty or "0" is off (today's path exactly); any other value turns both items on, unless it
// names them (comma-separated "join", "queue"). Read once; one stderr line at registration.
// AnyPS5's and sharpemu's copyrights remain with their authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_ULT_FIX_JOIN  = 1u;
static constexpr uint32_t BC5_ULT_FIX_QUEUE = 2u;

static uint32_t Bc5UltFixesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»uint32_t    parts = 0;
»const char* p     = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»if (n == 4 && std::strncmp(p, "join", n) == 0) {
»»»parts |= BC5_ULT_FIX_JOIN;
»»} else if (n == 5 && std::strncmp(p, "queue", n) == 0) {
»»»parts |= BC5_ULT_FIX_QUEUE;
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : (BC5_ULT_FIX_JOIN | BC5_ULT_FIX_QUEUE);
}

// The items of KYTY_BC5_ULT_FIXES that are on (0: off), read once; the first call prints the switch's line.
static uint32_t Bc5UltFixes() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5UltFixesParse(std::getenv("KYTY_BC5_ULT_FIXES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: ult off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: ult on (items:%s%s)\n", (p & BC5_ULT_FIX_JOIN) != 0 ? " join" : "",
»»»             (p & BC5_ULT_FIX_QUEUE) != 0 ? " queue" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

// "join": the ulthread whose entry this host thread runs (AnyPS5's gCurrentUlthread), set by Bc5UltUlthreadRun.
static thread_local UltUlthreadState* g_bc5_current_ulthread = nullptr;

static KYTY_SYSV_ABI void* Bc5UltUlthreadRun(void* arg) {
»auto* state            = static_cast<UltUlthreadState*>(arg);
»g_bc5_current_ulthread = state;
»return reinterpret_cast<void*>(static_cast<intptr_t>(state->entry(state->arg)));
}

// "join": UltUlthreadCreate after its argument checks. The handle is checked and published as today, but the creator holds
// the ulthread's create mutex from the publication until PthreadCreate returned, so that a join of the handle waits for
// the thread (lock order: create mutex, then g_ult_mutex; a join never holds g_ult_mutex while it waits).
static int Bc5UltUlthreadCreate(void* ulthread, const char* name, const std::shared_ptr<UltUlthreadState>& state,
                                void* runtime) {
»std::unique_lock<std::mutex> create_lock(state->bc5_create_mutex);
»{
»»std::scoped_lock lock(g_ult_mutex);
»»if (g_ult_runtimes.find(runtime) == g_ult_runtimes.end()) {
»»»return ULT_ERROR_STATE;
»»}
»»if (g_ult_ulthreads.find(ulthread) != g_ult_ulthreads.end()) {
»»»return ULT_ERROR_STATE;
»»}
»»std::memset(ulthread, 0, 512);
»»g_ult_ulthreads[ulthread] = state;
»}

»const auto result = LibKernel::PthreadCreate(&state->thread, nullptr, Bc5UltUlthreadRun, state.get(),
»                                             name != nullptr ? name : "");
»if (result != OK) {
»»state->thread = nullptr; // a join that waited sees no thread: ULT_ERROR_STATE
»»std::scoped_lock lock(g_ult_mutex);
»»auto             it = g_ult_ulthreads.find(ulthread);
»»if (it != g_ult_ulthreads.end() && it->second == state) {
»»»g_ult_ulthreads.erase(it);
»»}
»»return ULT_ERROR_AGAIN;
»}

»return OK;
}

// "join": UltUlthreadJoin after its null check (AnyPS5's joinUlthread, blocking).
static int Bc5UltUlthreadJoin(void* ulthread, int32_t* status) {
»std::shared_ptr<UltUlthreadState> state;
»{
»»std::scoped_lock lock(g_ult_mutex);
»»auto             it = g_ult_ulthreads.find(ulthread);
»»if (it == g_ult_ulthreads.end()) {
»»»return ULT_ERROR_STATE;
»»}
»»state = it->second;
»»if (state->bc5_joining || state.get() == g_bc5_current_ulthread) {
»»»return ULT_ERROR_STATE;
»»}
»»state->bc5_joining = true;
»}
»{
»»std::scoped_lock create_lock(state->bc5_create_mutex); // the creator has stored the thread, or failed
»}

»void* result = nullptr;
»if (state->thread == nullptr || LibKernel::PthreadJoin(state->thread, &result) != OK) {
»»std::scoped_lock lock(g_ult_mutex);
»»state->bc5_joining = false;
»»return ULT_ERROR_STATE;
»}
»if (status != nullptr) {
»»*status = static_cast<int32_t>(reinterpret_cast<intptr_t>(result));
»}

»std::scoped_lock lock(g_ult_mutex);
»auto             it = g_ult_ulthreads.find(ulthread);
»if (it != g_ult_ulthreads.end() && it->second == state) {
»»g_ult_ulthreads.erase(it);
»}
»return OK;
}

// "queue": a stderr line for each of the first 8 pushes that took a queue past its data pool's num_data (under the
// queue's mutex). Nothing when "queue" is off or the queue is within its capacity.
static void Bc5UltQueueTell(const void* queue, const UltQueueState& state) {
»if ((Bc5UltFixes() & BC5_ULT_FIX_QUEUE) == 0 || state.capacity == 0 || state.items.size() <= state.capacity) {
»»return;
»}
»static std::atomic<uint32_t> told {0};
»if (told.fetch_add(1, std::memory_order_relaxed) < 8) {
»»std::fprintf(stderr, "[bc5] exp 0405: ult queue 0x%016" PRIx64 " holds %zu items, over its data pool's num_data %" PRIu32 " (kept; dropped when off)\n",
»»             reinterpret_cast<uint64_t>(queue), state.items.size(), state.capacity);
»»std::fflush(stderr);
»}
}
// ---- end of experiment 0405's Ult helpers ----

"""

ULT_EDITS = (
    ("includes",
     "#include <condition_variable>\n#include <cstring>\n",
     "#include <atomic>  // BC5 experiment 0405\n#include <condition_variable>\n"
     "#include <cstdio>  // BC5 experiment 0405: std::fprintf\n#include <cstdlib> // BC5 experiment 0405: std::getenv\n"
     "#include <cstring>\n"),
    ("the ulthread's state",
     "»LibKernel::Pthread thread = nullptr;\n};\n",
     "»LibKernel::Pthread thread = nullptr;\n"
     "»// BC5 experiment 0405 (KYTY_BC5_ULT_FIXES \"join\"; used only when it is on)\n"
     "»std::mutex bc5_create_mutex;    // held by the creator from the publication until PthreadCreate returned\n"
     "»bool       bc5_joining = false; // a join holds the claim (under g_ult_mutex)\n"
     "};\n"),
    ("UltUlthreadCreate: join",
     "»state->arg   = arg;\n\n»{\n»»std::scoped_lock lock(g_ult_mutex);\n»»if (g_ult_runtimes.find(runtime) == g_ult_runtimes.end()) {\n",
     "»state->arg   = arg;\n\n"
     "»if ((Bc5UltFixes() & BC5_ULT_FIX_JOIN) != 0) { // BC5 experiment 0405 (KYTY_BC5_ULT_FIXES \"join\"); today's path when off\n"
     "»»return Bc5UltUlthreadCreate(ulthread, name, state, runtime);\n»}\n\n"
     "»{\n»»std::scoped_lock lock(g_ult_mutex);\n»»if (g_ult_runtimes.find(runtime) == g_ult_runtimes.end()) {\n"),
    ("UltUlthreadJoin: join",
     "»if (ulthread == nullptr) {\n»»return ULT_ERROR_NULL;\n»}\n\n»std::shared_ptr<UltUlthreadState> state;\n",
     "»if (ulthread == nullptr) {\n»»return ULT_ERROR_NULL;\n»}\n"
     "»if ((Bc5UltFixes() & BC5_ULT_FIX_JOIN) != 0) { // BC5 experiment 0405 (KYTY_BC5_ULT_FIXES \"join\"); today's path when off\n"
     "»»return Bc5UltUlthreadJoin(ulthread, status);\n»}\n\n»std::shared_ptr<UltUlthreadState> state;\n"),
    ("UltQueuePush: the capacity",
     "»if (state->capacity != 0 && state->items.size() >= state->capacity) {\n",
     "»if (state->capacity != 0 && state->items.size() >= state->capacity &&\n"
     "»    (Bc5UltFixes() & BC5_ULT_FIX_QUEUE) == 0) { // BC5 experiment 0405 (KYTY_BC5_ULT_FIXES \"queue\"): on, it grows\n"),
    ("UltQueuePush: the catcher",
     "»»std::memcpy(item.data(), data, item.size());\n»}\n\n»return OK;\n}\n\nstatic int KYTY_SYSV_ABI UltQueueTryPop(",
     "»»std::memcpy(item.data(), data, item.size());\n»}\n"
     "»Bc5UltQueueTell(queue, *state); // BC5 experiment 0405 (KYTY_BC5_ULT_FIXES \"queue\"); nothing when off\n"
     "\n»return OK;\n}\n\nstatic int KYTY_SYSV_ABI UltQueueTryPop("),
    ("registration: the switch's line",
     "LIB_DEFINE(InitUlt_1) {\n",
     "LIB_DEFINE(InitUlt_1) {\n"
     "»(void)Bc5UltFixes(); // BC5 experiment 0405: reads KYTY_BC5_ULT_FIXES once and prints its line, on or off\n"),
)
ULT_BEFORE = ("struct UltUlthreadState {\n", "struct UltQueueState {\n",
              "static std::unordered_map<void*, std::shared_ptr<UltUlthreadState>>  g_ult_ulthreads;\n",
              "static std::unordered_map<void*, UltRuntimeState>                    g_ult_runtimes;\n")
ULT_AFTER = ("static int KYTY_SYSV_ABI UltUlthreadJoin(", "static int KYTY_SYSV_ABI UltQueuePush(", "LIB_DEFINE(InitUlt_1) {")
ULT_USES = (("static uint32_t Bc5UltFixes()", 1), ("Bc5UltFixes()", 6), ("Bc5UltUlthreadRun", 3),
            ("Bc5UltUlthreadCreate(", 2), ("Bc5UltUlthreadJoin(", 2), ("Bc5UltQueueTell(", 2),
            ("g_bc5_current_ulthread", 3), ("bc5_create_mutex", 3), ("bc5_joining", 4))

# =====================================================================================================================
# src/libs/libUserService.cpp (R1 #3, R2 KL03); CRLF
# =====================================================================================================================
USER_BLOCK_ANCHOR = "struct UserServiceLoginUserIdList {\n"
USER_BLOCK = r"""// ---- BC5 experiment 0405 (series e5 of experiment 0401): KYTY_BC5_USERSERVICE_VALUES ----
// Answers a PS5 (firmware 13.60) gave, as AnyPS5's debt note docs/dev/debt/libSceUserService.md:54, 57, 58 records them
// (console measurements), ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @
// 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceUserService/Export.cpp:42-51 (ReportAccessibilitySetting),
// 159-161 (ZoomFollowFocus), 163-174 (GetAgeLevel) and 238-252 (GetUserName); GetUserName also after KytyPS5
// (github.com/KytyPS5/KytyPS5, GPL-2.0) @ dfec14a src/libs/libUserService.cpp:113-132 (exp 0405 R2 KL03). "Logged in" stays
// this file's IsLocalUser (users 1000 to 1003).
//   "age"   sceUserServiceGetAgeLevel writes 0xFFFFFFFF, a user without a parental restriction (:57); today 9.
//   "login" a user who is not logged in gets USER_SERVICE_ERROR_NOT_LOGGED_IN with or without an output, so before the null
//           check, in GetAgeLevel and the six accessibility getters (:57, :58); today the null output is checked first.
//   "name"  sceUserServiceGetUserName returns errors where today it EXITs (or writes through a null name): a null name
//           0x80960005 (both sources), a user id the console does not know 0x80960105 (:54, measured; KytyPS5 answers
//           NOT_LOGGED_IN there), a buffer too short for the name USER_SERVICE_ERROR_BUFFER_TOO_SHORT without writing
//           (KytyPS5's rule; AnyPS5 also clears the buffer; TODO(verify): neither is measured). The name stays "Kyty-<n>".
//   "zoom"  sceUserServiceGetAccessibilityZoomFollowFocus reports 1, a user with default settings (:58); today 0.
// KYTY_BC5_USERSERVICE_VALUES: unset, empty or "0" is off (today's path exactly); any other value turns every item on,
// unless it names items (comma-separated). Read once; one stderr line at registration.
// AnyPS5's and KytyPS5's copyrights remain with their authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_USER_AGE                        = 1u;
static constexpr uint32_t BC5_USER_LOGIN                      = 2u;
static constexpr uint32_t BC5_USER_NAME                       = 4u;
static constexpr uint32_t BC5_USER_ZOOM                       = 8u;
static constexpr uint32_t BC5_USER_ALL                        = 15u;
static constexpr int      BC5_USER_SERVICE_ERROR_UNKNOWN_USER = -2137652987; // 0x80960105 (AnyPS5's name for it)

static uint32_t Bc5UserValuesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»static const char* const names[] = {"age", "login", "name", "zoom"}; // bit i is names[i]
»uint32_t                 parts   = 0;
»const char*              p       = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (uint32_t i = 0; i < 4; i++) {
»»»if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
»»»»parts |= 1u << i;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : BC5_USER_ALL;
}

// The items of KYTY_BC5_USERSERVICE_VALUES that are on (0: off), read once; the first call prints the switch's line.
static uint32_t Bc5UserValues() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5UserValuesParse(std::getenv("KYTY_BC5_USERSERVICE_VALUES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: userservice off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: userservice on (items:%s%s%s%s)\n", (p & BC5_USER_AGE) != 0 ? " age" : "",
»»»             (p & BC5_USER_LOGIN) != 0 ? " login" : "", (p & BC5_USER_NAME) != 0 ? " name" : "",
»»»             (p & BC5_USER_ZOOM) != 0 ? " zoom" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

static bool Bc5UserValue(uint32_t item) {
»return (Bc5UserValues() & item) != 0;
}

// "login": true when the item is on and the user is not logged in (the getters check it before their output's null check).
static bool Bc5UserNotLoggedInFirst(int user_id) {
»return Bc5UserValue(BC5_USER_LOGIN) && !IsLocalUser(user_id);
}

// "name": sceUserServiceGetUserName without an EXIT; nothing is written on an error.
static int Bc5UserServiceGetUserName(int user_id, char* name, size_t size) {
»if (name == nullptr) {
»»return USER_SERVICE_ERROR_INVALID_ARGUMENT;
»}
»if (!IsLocalUser(user_id)) {
»»return BC5_USER_SERVICE_ERROR_UNKNOWN_USER;
»}
»char      text[32];
»const int player = Libs::Controller::ControllerIndexFromUserId(user_id) + 1;
»const int n      = std::snprintf(text, sizeof(text), "Kyty-%d", player);
»if (n < 0 || size <= static_cast<size_t>(n)) {
»»return USER_SERVICE_ERROR_BUFFER_TOO_SHORT;
»}
»std::memcpy(name, text, static_cast<size_t>(n) + 1);
»return OK;
}
// ---- end of experiment 0405's UserService helpers ----

"""

USER_LOGIN_FIRST = ("»if (Bc5UserNotLoggedInFirst(user_id)) { // BC5 experiment 0405 (KYTY_BC5_USERSERVICE_VALUES \"login\"); false when off\n"
                    "»»return USER_SERVICE_ERROR_NOT_LOGGED_IN;\n»}\n")
USER_EDITS = tuple(
    [("UserServiceGetUserName: name",
      "static KYTY_SYSV_ABI int UserServiceGetUserName(int user_id, char* name, size_t size) {\n»EXIT_NOT_IMPLEMENTED(!IsLocalUser(user_id));\n",
      "static KYTY_SYSV_ABI int UserServiceGetUserName(int user_id, char* name, size_t size) {\n"
      "»if (Bc5UserValue(BC5_USER_NAME)) { // BC5 experiment 0405 (KYTY_BC5_USERSERVICE_VALUES \"name\"); today's path when off\n"
      "»»return Bc5UserServiceGetUserName(user_id, name, size);\n»}\n»EXIT_NOT_IMPLEMENTED(!IsLocalUser(user_id));\n"),
     ("UserServiceGetAgeLevel: age",
      "»*age_level = 9;\n",
      "»*age_level = Bc5UserValue(BC5_USER_AGE) ? 0xFFFFFFFFu : 9; // BC5 experiment 0405 (\"age\"): 9 when off\n"),
     ("UserServiceGetAccessibilityZoomFollowFocus: zoom",
      "»*zoom_follow_focus = 0;\n",
      "»*zoom_follow_focus = Bc5UserValue(BC5_USER_ZOOM) ? 1 : 0; // BC5 experiment 0405 (\"zoom\"): 0 when off\n")]
    + [("%s: login" % out,
        "»PRINT_NAME();\n\n»if (%s == nullptr) {\n" % out,
        "»PRINT_NAME();\n\n" + USER_LOGIN_FIRST + "»if (%s == nullptr) {\n" % out)
       for out in ("vibration", "trigger_effect", "age_level", "chat_transcription", "press_and_hold_delay",
                   "zoom_enabled", "zoom_follow_focus")]
    + [("registration: the switch's line",
        "LIB_DEFINE(InitUserService_1) {\n",
        "LIB_DEFINE(InitUserService_1) {\n"
        "»(void)UserService::Bc5UserValues(); // BC5 experiment 0405: reads KYTY_BC5_USERSERVICE_VALUES once, prints its line\n")])
USER_BEFORE = ("static bool IsLocalUser(int user_id) {\n",)
USER_AFTER = ("static KYTY_SYSV_ABI int UserServiceGetUserName(", "static KYTY_SYSV_ABI int UserServiceGetAgeLevel(",
              "LIB_DEFINE(InitUserService_1) {")
USER_USES = (("static uint32_t Bc5UserValues()", 1), ("Bc5UserValues()", 3), ("Bc5UserValue(", 5),
             ("Bc5UserNotLoggedInFirst(", 8), ("Bc5UserServiceGetUserName(", 2))

# =====================================================================================================================
# src/libs/libSystemService.cpp (R1 #4)
# =====================================================================================================================
SYS_BLOCK_ANCHOR = "static int KYTY_SYSV_ABI SystemServiceParamGetInt(int param_id, int* value) {\n"
SYS_BLOCK = r"""// ---- BC5 experiment 0405 (series e5 of experiment 0401): KYTY_BC5_SYSTEMSERVICE_VALUES, ..._PARAMS_7_1000 ----
// Answers a PS5 gave, as AnyPS5's debt note docs/dev/debt/libSceSystemService.md:69, 74, 216 records them (console
// measurements), ported in adapted form from AnyPS5 (github.com/boykopovar/AnyPS5, GPL-2.0-only) @
// 4f41f4c375f5abb487dbd184fbc150f31994d762, core/libs/prx/libSceSystemService/Export.cpp:40-49 (the measured table) and
// 549-578 (sceSystemServiceParamGetInt, sceSystemServiceParamGetString).
//   "int"    ParamGetInt answers only parameters 1 to 5, 100 to 111, 200 to 213, 300 and 400; any other parameter returns
//            SYSTEM_SERVICE_ERROR_PARAMETER (0x80A10003) without writing (:74: firmware 13.40, ptrace calls inside a retail
//            title, a sweep of 0 to 2048). Today any other parameter answers 0. 7 and 1000 have their own switch (below).
//            The parameters that answer keep today's values unless "table" is on. Parameter 400 keeps today's answer 0:
//            that it is the language, as AnyPS5 answers, rests on firmware modules read (debt :70), held tonight.
//   "table"  101 to 111, 200 to 213 and 300 answer what that console returned with its settings at the time (:216): 101 1,
//            102 2, 103 100, 104 0x20202, 107 100, 109 100, 110 0x20202, 209 1, 210 71, the others 0. What each one means
//            is not known. TODO(verify) on another console. Today they answer 0.
//   "string" ParamGetString answers only parameter 6 (the system name, this file's "Kyty"); any other parameter, a null
//            buffer or one under 65 bytes returns 0x80A10003 without writing; the name is written NUL-padded to the whole
//            buffer (:69: firmware 13.60, a payload process). Today another parameter EXITs and 5 to 64 bytes answer.
// KYTY_BC5_SYSTEMSERVICE_VALUES: unset, empty or "0" is off (today's path exactly); any other value turns every item on,
// unless it names items (comma-separated "int", "table", "string").
// KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000 (its own switch: titles read these today): ParamGetInt parameters 7 (game parental
// level) and 1000 (enter button assignment) return 0x80A10003 without writing, as the 13.40 measurement found (:74);
// today they answer 0 (parental off) and 1 (cross). Unset, empty or "0" is off.
// Both read once; one stderr line each at registration; one stderr line per parameter the switches refuse.
// AnyPS5's copyright remains with its authors; GPL-2.0 as the rest of this file.
static constexpr uint32_t BC5_SYS_INT    = 1u;
static constexpr uint32_t BC5_SYS_TABLE  = 2u;
static constexpr uint32_t BC5_SYS_STRING = 4u;
static constexpr uint32_t BC5_SYS_ALL    = 7u;

struct Bc5SysParam {
»int id;
»int value;
};

// The parameters 100 to 111, 200 to 213 and 300 with the values the 13.40 console returned (debt :216; Export.cpp:45-49).
static constexpr Bc5SysParam BC5_SYS_TABLE_VALUES[] = {
    {100, 0}, {101, 1}, {102, 2}, {103, 100}, {104, 0x20202}, {105, 0}, {106, 0}, {107, 100}, {108, 0}, {109, 100},
    {110, 0x20202}, {111, 0}, {200, 0}, {201, 0}, {202, 0}, {203, 0}, {204, 0}, {205, 0}, {206, 0}, {207, 0}, {208, 0},
    {209, 1}, {210, 71}, {211, 0}, {212, 0}, {213, 0}, {300, 0}};

static uint32_t Bc5SysValuesParse(const char* e) {
»if (e == nullptr || e[0] == '\0' || std::strcmp(e, "0") == 0) {
»»return 0;
»}
»static const char* const names[] = {"int", "table", "string"}; // bit i is names[i]
»uint32_t                 parts   = 0;
»const char*              p       = e;
»for (;;) {
»»const char*  comma = std::strchr(p, ',');
»»const size_t n     = comma != nullptr ? static_cast<size_t>(comma - p) : std::strlen(p);
»»for (uint32_t i = 0; i < 3; i++) {
»»»if (n == std::strlen(names[i]) && std::strncmp(p, names[i], n) == 0) {
»»»»parts |= 1u << i;
»»»}
»»}
»»if (comma == nullptr) {
»»»break;
»»}
»»p = comma + 1;
»}
»return parts != 0 ? parts : BC5_SYS_ALL;
}

// The items of KYTY_BC5_SYSTEMSERVICE_VALUES that are on (0: off), read once; the first call prints the switch's line.
static uint32_t Bc5SysValues() {
»static const uint32_t parts = [] {
»»const uint32_t p = Bc5SysValuesParse(std::getenv("KYTY_BC5_SYSTEMSERVICE_VALUES"));
»»if (p == 0) {
»»»std::fprintf(stderr, "[bc5] exp 0405: systemservice off\n");
»»} else {
»»»std::fprintf(stderr, "[bc5] exp 0405: systemservice on (items:%s%s%s)\n", (p & BC5_SYS_INT) != 0 ? " int" : "",
»»»             (p & BC5_SYS_TABLE) != 0 ? " table" : "", (p & BC5_SYS_STRING) != 0 ? " string" : "");
»»}
»»std::fflush(stderr);
»»return p;
»}();
»return parts;
}

// KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000, read once; the first call prints the switch's line.
static bool Bc5SysParams71000() {
»static const bool on = [] {
»»const char* e = std::getenv("KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000");
»»const bool  v = e != nullptr && e[0] != '\0' && std::strcmp(e, "0") != 0;
»»std::fprintf(stderr, "[bc5] exp 0405: systemservice-params-7-1000 %s\n", v ? "on (items: 7 1000)" : "off");
»»std::fflush(stderr);
»»return v;
»}();
»return on;
}

// One stderr line for each parameter the switches refuse, once per parameter and function.
static void Bc5SysTellRefused(bool string_param, int param_id) {
»static std::mutex    m;
»static std::set<int> seen[2];
»std::scoped_lock     lock(m);
»if (seen[string_param ? 1 : 0].insert(param_id).second) {
»»std::fprintf(stderr, "[bc5] exp 0405: system param %d (%s) -> 0x80A10003\n", param_id, string_param ? "string" : "int");
»»std::fflush(stderr);
»}
}

// ParamGetInt: true when the switches make the parameter return SYSTEM_SERVICE_ERROR_PARAMETER without writing.
static bool Bc5SysParamRefused(int param_id) {
»if (param_id == PARAM_ID_GAME_PARENTAL_LEVEL || param_id == PARAM_ID_ENTER_BUTTON_ASSIGN) {
»»return Bc5SysParams71000();
»}
»if ((Bc5SysValues() & BC5_SYS_INT) == 0) {
»»return false;
»}
»if ((param_id >= PARAM_ID_LANG && param_id <= PARAM_ID_SUMMERTIME) || param_id == 400) {
»»return false;
»}
»for (const auto& p: BC5_SYS_TABLE_VALUES) {
»»if (p.id == param_id) {
»»»return false;
»»}
»}
»return true;
}

// ParamGetInt with "table": a measured parameter's value into *v; nothing for the others or when off.
static void Bc5SysParamTable(int param_id, int* v) {
»if ((Bc5SysValues() & BC5_SYS_TABLE) == 0) {
»»return;
»}
»for (const auto& p: BC5_SYS_TABLE_VALUES) {
»»if (p.id == param_id) {
»»»*v = p.value;
»»}
»}
}

// "string": sceSystemServiceParamGetString as measured (debt :69); nothing is written on an error.
static int Bc5SysParamGetString(int param_id, char* buf, size_t buf_size) {
»if (param_id != PARAM_ID_SYSTEM_NAME || buf == nullptr || buf_size < static_cast<size_t>(MAX_SYSTEM_NAME_LENGTH)) {
»»Bc5SysTellRefused(true, param_id);
»»return SYSTEM_SERVICE_ERROR_PARAMETER;
»}
»static constexpr char name[] = "Kyty"; // this file's system name (AnyPS5 answers "PS5")
»std::memset(buf, 0, buf_size);
»std::memcpy(buf, name, sizeof(name));
»LOGF(" %d = %s\n", param_id, name);
»return OK;
}
// ---- end of experiment 0405's SystemService helpers ----

"""

SYS_EDITS = (
    ("include <cstdlib>",
     "#include <cstring>\n#include <deque>\n#include <mutex>\n",
     "#include <cstdlib> // BC5 experiment 0405: std::getenv\n#include <cstring>\n#include <deque>\n#include <mutex>\n"),
    ("ParamGetInt: refused parameters",
     "»if (value == nullptr) {\n»»return SYSTEM_SERVICE_ERROR_PARAMETER;\n»}\n\n»int v = 0;\n",
     "»if (value == nullptr) {\n»»return SYSTEM_SERVICE_ERROR_PARAMETER;\n»}\n"
     "»if (Bc5SysParamRefused(param_id)) { // BC5 experiment 0405 (KYTY_BC5_SYSTEMSERVICE_VALUES \"int\", ..._PARAMS_7_1000); false when off\n"
     "»»Bc5SysTellRefused(false, param_id);\n»»return SYSTEM_SERVICE_ERROR_PARAMETER;\n»}\n\n»int v = 0;\n"),
    ("ParamGetInt: the measured table",
     "»LOGF(\" %d = %d\\n\", param_id, v);\n",
     "»Bc5SysParamTable(param_id, &v); // BC5 experiment 0405 (KYTY_BC5_SYSTEMSERVICE_VALUES \"table\"); nothing when off\n"
     "»LOGF(\" %d = %d\\n\", param_id, v);\n"),
    ("ParamGetString: string",
     "static int KYTY_SYSV_ABI SystemServiceParamGetString(int param_id, char* buf, size_t buf_size) {\n»PRINT_NAME();\n\n",
     "static int KYTY_SYSV_ABI SystemServiceParamGetString(int param_id, char* buf, size_t buf_size) {\n»PRINT_NAME();\n\n"
     "»if ((Bc5SysValues() & BC5_SYS_STRING) != 0) { // BC5 experiment 0405 (KYTY_BC5_SYSTEMSERVICE_VALUES \"string\"); today's path when off\n"
     "»»return Bc5SysParamGetString(param_id, buf, buf_size);\n»}\n"),
    ("registration: the switches' lines",
     "LIB_DEFINE(InitSystemService_1) {\n",
     "LIB_DEFINE(InitSystemService_1) {\n"
     "»(void)SystemService::Bc5SysValues();      // BC5 experiment 0405: reads KYTY_BC5_SYSTEMSERVICE_VALUES once, prints its line\n"
     "»(void)SystemService::Bc5SysParams71000(); // BC5 experiment 0405: the same for KYTY_BC5_SYSTEMSERVICE_PARAMS_7_1000\n"),
)
SYS_BEFORE = ("[[maybe_unused]] constexpr int PARAM_ID_ENTER_BUTTON_ASSIGN = 1000;\n",
              "[[maybe_unused]] constexpr int MAX_SYSTEM_NAME_LENGTH = 65;\n")
SYS_AFTER = ("static int KYTY_SYSV_ABI SystemServiceParamGetString(", "LIB_DEFINE(InitSystemService_1) {")
SYS_USES = (("static uint32_t Bc5SysValues()", 1), ("Bc5SysValues()", 5), ("Bc5SysParams71000()", 3),
            ("Bc5SysParamRefused(", 2), ("Bc5SysParamTable(", 2), ("Bc5SysParamGetString(", 2), ("Bc5SysTellRefused(", 3))

UNITS = (
    # rel, pinned input md5, crlf, block anchor, block, edits, defined-before, used-after, helper uses
    ("src/libs/libJson2.cpp", "d38d30582b49f57f9ef3fea6d84584be", False, JSON2_BLOCK_ANCHOR, JSON2_BLOCK, JSON2_EDITS,
     JSON2_BEFORE, JSON2_AFTER, JSON2_USES),
    ("src/libs/libUlt.cpp", "9198f40703960fe46e9ba066a6c58ac3", False, ULT_BLOCK_ANCHOR, ULT_BLOCK, ULT_EDITS, ULT_BEFORE,
     ULT_AFTER, ULT_USES),
    ("src/libs/libUserService.cpp", "4f90ba6b94167d9b857c8efa89f1cf47", True, USER_BLOCK_ANCHOR, USER_BLOCK, USER_EDITS,
     USER_BEFORE, USER_AFTER, USER_USES),
    ("src/libs/libSystemService.cpp", "6c2a2925078d2facd4abe9412408dd57", False, SYS_BLOCK_ANCHOR, SYS_BLOCK, SYS_EDITS,
     SYS_BEFORE, SYS_AFTER, SYS_USES),
)


def balance(b):
    return (b.count(b"{") - b.count(b"}"), b.count(b"(") - b.count(b")"), b.count(b"[") - b.count(b"]"))


def md5(b):
    return hashlib.md5(b).hexdigest()


def edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses):
    for m in MARKS:
        assert m not in s, ("the unit has the edit already", rel, m)
    assert (b"\r\n" in s) == crlf, ("line ends are not the expected ones", rel)
    if not crlf:
        assert b"\r" not in s, ("a CR in an LF unit", rel)
    A = T(anchor, crlf)
    B = T(block, crlf)
    assert balance(B) == (0, 0, 0), ("the block is not balanced", rel, balance(B))
    assert s.count(A) == 1, ("the block's anchor", rel, s.count(A))
    at = s.index(A)
    for b in before:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) < at, ("must be defined before the block, once", rel, b[:70], s.count(bb))
    for b in after:
        bb = T(b, crlf)
        assert s.count(bb) == 1 and s.index(bb) > at, ("must come after the block, once", rel, b[:70], s.count(bb))
    out = s.replace(A, B + A)
    done = []
    for what, old, new in edits:
        o, n = T(old, crlf), T(new, crlf)
        assert out.count(o) == 1, ("anchor", rel, what, out.count(o))
        assert balance(o) == balance(n), ("the edit changes the balance", rel, what, balance(o), balance(n))
        out = out.replace(o, n)
        done.append((o, n))
    assert balance(out) == balance(s), ("the unit's balance changed", rel, balance(s), balance(out))
    for name, n in uses:
        c = out.count(name.encode("ascii"))
        assert c == n, ("helper uses", rel, name, c, n)
    # Undo the edits on the output (last first) and the block: the input must come back byte for byte.
    back = out
    for o, n in reversed(done):
        assert back.count(n) == 1, ("undo", rel, n[:60])
        back = back.replace(n, o)
    assert back.count(B) == 1
    back = back.replace(B, b"")
    assert back == s, ("undoing the edits does not give the input back", rel)
    # The inserted text is ASCII.
    B.decode("ascii")
    for o, n in done:
        n.decode("ascii")
    if crlf:
        assert out.count(b"\n") == out.count(b"\r\n"), ("a bare LF in the CRLF unit", rel)
    else:
        assert b"\r" not in out, ("a CR in the LF unit", rel)
    return out


def main():
    assert len(sys.argv) == 3, __doc__
    root, outdir = sys.argv[1], sys.argv[2]
    assert os.path.abspath(root) != os.path.abspath(outdir), "the out dir must not be the tree"
    outs = []
    for rel, expect, crlf, anchor, block, edits, before, after, uses in UNITS:
        with open(os.path.join(root, rel), "rb") as f:
            s = f.read()
        for m in MARKS:
            assert m not in s, ("refused: the unit has the edit already", rel, m.decode())
        assert md5(s) == expect, ("refused: not the pinned input", rel, md5(s), expect)
        out = edit_unit(rel, s, crlf, anchor, block, edits, before, after, uses)
        print(f"# in:  {rel} {md5(s)}  ({len(s)} bytes, {'CRLF' if crlf else 'LF'})", file=sys.stderr)
        outs.append((rel, out))
    for rel, out in outs:  # written only when all four are done
        dst = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(out)
        print(f"{rel} {md5(out)}")


if __name__ == "__main__":
    main()
