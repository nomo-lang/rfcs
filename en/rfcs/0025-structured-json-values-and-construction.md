# RFC 0025: Structured JSON Values, Access, and Construction

> Language: [中文](../../zh-CN/rfcs/0025-structured-json-values-and-construction.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0025 |
| Title | Structured JSON values, access, and construction |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-24 |
| Topics | JSON, standard library, Agent, Unicode, limits, C backend, browser WASM |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0022](./0022-structured-http-client-and-host-runtime.md), [RFC 0024](./0024-controlled-child-processes-and-stdio.md) |

---

## 1. Summary

Nomo v0.1 should extend `std.json` from a raw-text validator into a bounded,
structured API that can inspect all six JSON value kinds, traverse nested
arrays and objects, build request documents, and serialize them without
application-side C FFI.

`JsonValue` remains opaque and stores a validated JSON fragment. Existing
`parse` and `stringify` signatures remain available, and a successfully parsed
document keeps its original spelling and whitespace when stringified. New
accessors and constructors operate on that opaque representation, allowing the
runtime to add indexed or tree-backed storage later without freezing a public
recursive layout in v0.1.

The first structured API is deliberately bounded and synchronous. It specifies
input size, nesting depth, value count, Unicode handling, duplicate object
members, exact number text, deterministic lookup, secret-safe errors, and
native/browser parity.

## 2. Motivation

The HTTP and process slices now provide the transports needed by a native CLI
Agent, but the application cannot yet express the data loop:

1. build a nested OpenAI-compatible request object;
2. serialize it as an HTTP body;
3. parse a nested response;
4. select `choices[0].message.content`;
5. construct and consume JSON-RPC messages for a later MCP client.

The current `std.json` API only proves that a string is syntactically JSON and
returns the original raw text. Application code cannot ask whether the value is
an object, get a member, iterate an array, decode a string, or construct a JSON
document without manually concatenating and escaping text. Manual
concatenation is especially unsafe for prompts, tool results, and model output.

This is a reusable standard-library gap, not a reason to add an Agent-specific
SDK or expose a JSON library through application FFI.

## 3. Current Evidence and Gaps

| Surface | Current evidence | P1 gap |
| --- | --- | --- |
| Public type | Opaque `JsonValue { raw: string }` | No kind, access, traversal, or construction |
| Parsing | Recursive C syntax validator | No size/depth/value limits, UTF-8 validation, surrogate validation, or useful error location |
| Serialization | `stringify` retains and returns `raw` | No safe string escaping or object/array construction |
| Numbers | Number grammar is validated | No exact lexeme access or numeric constructors |
| Objects | Syntax is validated in source order | No member enumeration, duplicate policy, or lookup |
| Errors | `JsonError { message }` with `"invalid json"` | No stable code/offset contract; implementation cannot report limit versus syntax |
| Native runtime | Generated C scans NUL-terminated bytes | `\u0000` cannot be represented as a Nomo `string`; unpaired surrogates are currently accepted |
| Browser WASM | `JsonParse` and `JsonStringify` fall through to the generic unsupported-operation error | Pure JSON operations do not work in the Playground |
| Tests | One compiler/CLI parse-stringify happy path | No nested Agent payload, constructors, Unicode, duplicates, limits, lifecycle stress, or C/WASM parity |

## 4. Detailed Design

### 4.1 Public Nomo API

The canonical `std.json` surface becomes:

```nomo
pub enum JsonKind {
    Null
    Boolean
    Number
    String
    Array
    Object
}

pub struct JsonValue {
    raw: string
}

pub struct JsonMember {
    pub key: string
    pub value: JsonValue
}

pub struct JsonError {
    pub code: string
    pub message: string
    pub offset: u64
}

pub fn parse(value: string) -> Result<JsonValue, JsonError>
pub fn stringify(value: JsonValue) -> string

pub fn kind(value: JsonValue) -> JsonKind
pub fn is_null(value: JsonValue) -> bool
pub fn as_bool(value: JsonValue) -> Option<bool>
pub fn number_text(value: JsonValue) -> Option<string>
pub fn as_string(value: JsonValue) -> Option<string>
pub fn array_items(value: JsonValue) -> Option<Array<JsonValue>>
pub fn object_members(value: JsonValue) -> Option<Array<JsonMember>>
pub fn get(value: JsonValue, key: string) -> Option<JsonValue>

pub fn from_null() -> JsonValue
pub fn from_bool(value: bool) -> JsonValue
pub fn from_number_text(value: string) -> Result<JsonValue, JsonError>
pub fn from_i64(value: i64) -> JsonValue
pub fn from_u64(value: u64) -> JsonValue
pub fn from_string(value: string) -> Result<JsonValue, JsonError>
pub fn from_array(values: Array<JsonValue>) -> Result<JsonValue, JsonError>
pub fn from_object(
    members: Array<JsonMember>
) -> Result<JsonValue, JsonError>
```

`JsonValue.raw` remains private. The type is a validated value, so `kind` and
`stringify` cannot fail. Accessors return `None` when the value has the wrong
kind; `get` also returns `None` when the value is not an object or the member is
absent.

`array_items` returns values in document order. `object_members` returns every
member in document order. Returned nested `JsonValue` instances own or retain
their validated fragment and remain valid after the returned array is copied
or released.

The API uses free functions consistently with the existing v0.1 standard
library. It does not add indexing or dynamic field syntax to the language.
Callers use `std.array.get` after `array_items`.

### 4.2 Opaque Raw Representation

Parsing a document retains its validated raw text. `stringify(parse(text)?)`
therefore returns the same text, including insignificant whitespace, escape
spelling, exponent spelling, object order, and duplicate members.

Accessors scan the validated fragment and may allocate decoded strings, member
arrays, item arrays, or nested raw fragments. A first implementation may be
O(n) per accessor. The public representation remains opaque so a later runtime
can cache offsets or replace the scanner with a tree without changing source
code.

Constructors produce compact JSON with no insignificant whitespace. Values
created by constructors are indistinguishable from parsed values through the
public API.

### 4.3 Parsing Limits

Every `JsonValue` must satisfy all of these limits:

- at most 8 MiB of UTF-8 JSON text;
- at most 128 nested arrays/objects, with the root container at depth 1;
- at most 262,144 total JSON values, including the root and each object member
  value or array item.

The limits apply both to `parse` and to the complete output of aggregate
constructors. They are checked before an unbounded allocation or recursive C
call. The native parser must use an explicitly checked depth counter rather
than relying on the C stack.

Whitespace is limited to the four JSON whitespace bytes: space, horizontal
tab, line feed, and carriage return. Trailing non-whitespace input is a syntax
error.

`offset` is the zero-based UTF-8 byte offset at which parsing first detects the
failure. End-of-input errors use the input byte length. Aggregate constructor
limit failures use offset `0`.

### 4.4 Unicode and Nomo String Compatibility

Unescaped JSON text must be valid UTF-8. Escape decoding accepts the standard
JSON escapes. A high UTF-16 surrogate must be followed by a low surrogate and
the pair is decoded to one Unicode scalar. An unpaired surrogate is rejected
with `unsupported_string`.

The v0.1 Nomo string runtime is NUL-terminated and cannot preserve an embedded
U+0000. Consequently, `parse` rejects a JSON string or object name containing
escaped `\u0000` with `unsupported_string`. This restriction is explicit and
applies before producing a `JsonValue`, ensuring that `as_string`,
`object_members`, and `get` never silently truncate data.

`from_string` and object member keys accept any value representable by a Nomo
string. Serialization escapes quotation mark, reverse solidus, and control
characters; it emits valid UTF-8 for other Unicode scalars. A later
length-carrying Nomo string representation may remove the U+0000 restriction
without changing the JSON API.

### 4.5 Kinds and Scalar Access

`kind` reports exactly one of the six JSON kinds. `is_null` is a convenience
equivalent to comparing `kind(value)` with `JsonKind.Null`.

`as_bool` returns the represented boolean. `as_string` returns the decoded
Nomo string, not the quoted JSON token. `number_text` returns the exact
validated number lexeme, preserving sign, fractional digits, exponent case,
and exponent sign.

The first API does not coerce between JSON kinds. In particular, a JSON string
`"1"` is not a number and a JSON number `1` is not a string. Callers can pass
`number_text` to `std.num.parse_i64`, `parse_u64`, or `parse_f64` when a machine
numeric value is required.

### 4.6 Object Order, Duplicates, and Lookup

Parsing and `object_members` preserve source member order. `from_object`
preserves the supplied array order. Duplicate names are accepted because JSON
syntax permits them and existing `parse` already accepts them.

`get` uses deterministic last-member-wins lookup. This mirrors common JSON
consumer behavior while `object_members` preserves all entries for callers
that need to detect or reject duplicates. Serialization never silently
deduplicates members.

Object names are compared after JSON escape decoding, so `"name"` and
`"\u006eame"` identify the same lookup key.

### 4.7 Construction and Numbers

`from_null`, `from_bool`, `from_i64`, and `from_u64` cannot violate a JSON
limit and return directly.

`from_number_text` accepts exactly one JSON number token with no surrounding
whitespace. It preserves that token exactly and returns `invalid_number` for
leading zeroes, missing integer/fraction/exponent digits, non-finite spellings,
or trailing data.

`from_string`, `from_array`, and `from_object` return `limit` if their compact
serialized output would exceed 8 MiB, depth 128, or 262,144 values. They must
detect integer overflow while calculating sizes before allocation.

`from_f64` is deliberately not part of this RFC. Native C and browser
JavaScript/Rust formatting do not currently share a specified
shortest-round-trip decimal algorithm. Callers use `from_number_text` for
exact decimal values in v0.1. A later proposal may add deterministic finite
floating-point construction without changing this API.

### 4.8 Errors and Secret Handling

`JsonError.code` is one of:

- `syntax`: malformed JSON document;
- `limit`: input, output, depth, or value-count limit exceeded;
- `unsupported_string`: U+0000, unpaired surrogate, or invalid UTF-8;
- `invalid_number`: invalid input to `from_number_text`.

`message` is a stable generic explanation suitable for a user-facing
diagnostic. It may describe the expected token category, but neither it nor
default compiler/runtime logs may include source snippets, object names,
string values, number text, prompts, response bodies, tokens, or headers.
`offset` is the only input-specific parse detail.

This rule prevents a malformed model response or request containing a secret
from being copied into diagnostics.

### 4.9 Compiler, Native C, and Browser WASM

Canonical declarations remain in `std/src/json.nomo`. Compiler lowering uses
typed JSON IR operations for each public function. The generated C runtime owns
validation, scanning, decoding, escaping, checked sizing, and lifecycle
operations. Nomo applications declare no FFI source or linker metadata.

The native implementation must not call a system JSON library. This is an
implementation choice for portability, not a prohibition against all
toolchain-internal native/system facilities.

Browser WASM implements all operations in this RFC as pure computations. It
must not report a filesystem/network/process capability error. Its observable
kind, raw round trip, limits, errors, offsets, order, duplicate lookup, Unicode
decoding, and compact constructor output match the native C backend.

Adding a generic public dynamic-value representation to the browser
interpreter is not required. An internal raw JSON value may continue to use
the existing runtime `Struct` carrier as long as nominal type and lifecycle
behavior remain correct.

### 4.10 Compatibility and Migration

The following behavior remains compatible:

- `parse(string) -> Result<JsonValue, JsonError>`;
- `stringify(JsonValue) -> string`;
- exact raw round trip for every document accepted under the new limits;
- opaque `JsonValue` construction.

Two preview-stage tightenings are intentional:

1. inputs above the new bounds, invalid UTF-8, unpaired surrogates, and
   `\u0000` are rejected instead of being accepted by the old syntax-only
   validator;
2. `JsonError` gains `code` and `offset`, so external code that directly
   constructs a `JsonError` literal must add those fields.

Reading `error.message` and matching `Ok`/`Err` remain source-compatible.
The migration for a constructed error is mechanical, and standard-library
errors are not intended as application domain-error constructors.

## 5. Alternatives

| Option | Advantages | Disadvantages | Direction |
| --- | --- | --- | --- |
| Opaque validated fragment plus accessors/constructors | Preserves raw round trip; stable representation; incremental implementation | Repeated access may scan repeatedly | Proposed |
| Public recursive `JsonValue` enum | Natural pattern matching and direct construction | Freezes number/object representation, loses exact raw spelling, expands layout/lifecycle ABI | Rejected for v0.1 |
| String-only helper functions | Small compiler change | Repeated parsing, unsafe construction, no typed lifecycle | Rejected |
| Application-side C JSON library | Mature implementations exist | Every Agent must own FFI, allocation, linking, and cross-platform policy | Rejected |
| Reject duplicate object names | Stronger data model | Breaks existing accepted input and some external APIs | Rejected; expose all and use last-match lookup |
| Convert every number to `f64` | Simple runtime value | Loses large integers and exact decimals | Rejected |
| Add `from_f64` using platform formatting | Convenient | Native/browser output and round-trip behavior are not specified | Deferred |
| Redesign all Nomo strings as length-carrying now | Would represent U+0000 | Cross-cuts the runtime and all host APIs | Deferred |

## 6. Drawbacks and Risks

- Opaque fragment access can repeat scans for deeply nested workflows.
- Returning all members/items allocates arrays proportional to the selected
  container, though the document and value-count bounds cap that cost.
- The U+0000 restriction is narrower than unrestricted JSON.
- Last-member-wins lookup can hide duplicates unless callers enumerate them.
- Expanding `JsonError` is a small preview-stage source break for direct struct
  literals.
- Maintaining the same parser semantics in generated C and browser Rust needs
  shared fixtures rather than relying on two library defaults.

## 7. Impact on v0.1 Scope

This RFC closes the reusable JSON half of a non-streaming native CLI Agent
loop. Together with RFC 0022, Nomo code can construct an OpenAI-compatible
request, send it over HTTPS, and inspect a nested response. Together with RFC
0024, it supplies the value model needed by a later JSON-RPC/MCP framing slice.

It does not implement an OpenAI SDK, Agent product, schema derivation,
reflection, serde-like traits, JSONPath, automatic struct mapping, streaming
JSON parsing, mutable in-place JSON trees, or JSON-RPC protocol semantics.

## 8. Acceptance Gate

This RFC was accepted after all of these gates passed:

1. Canonical `std.json` source, standard-module registry, compiler lowering,
   typed IR, generated C ABI, browser WASM, docs, and both v0.1 specifications
   expose the same API and semantics.
2. Existing parse/stringify code remains source-compatible and valid
   documents within bounds preserve byte-exact raw round trips.
3. A Nomo example constructs a nested OpenAI-compatible non-streaming request
   and extracts `choices[0].message.content` from a fixture response without
   string concatenation or application-side FFI.
4. Tests cover null, boolean, number, string, array, object, wrong-kind
   access, missing members, empty containers, and nested traversal.
5. Tests cover safe construction and escaping of quotes, reverse solidus,
   controls, BMP Unicode, valid surrogate pairs, and non-ASCII UTF-8.
6. Tests cover invalid UTF-8, unpaired surrogates, U+0000, exact number
   lexemes, invalid number forms, `i64`/`u64` limits, and constructor overflow.
7. Tests prove source-order preservation, duplicate preservation, decoded-name
   comparison, and deterministic last-member-wins `get`.
8. Boundary tests cover exactly 8 MiB versus one byte over, depth 128 versus
   129, and 262,144 values versus one over without stack overflow or unbounded
   allocation.
9. Secret sentinels embedded in malformed strings, member names, number text,
   and nested values never appear in errors, diagnostics, or default logs.
10. Lifecycle stress repeatedly parses, traverses, copies, constructs, and
    releases nested values under AddressSanitizer or an equivalent native leak
    and use-after-free gate.
11. The same conformance fixture corpus passes through native Linux, native
    macOS, native Windows, and browser WASM; capability-denial tests confirm
    JSON remains available in the sandbox.
12. Formatting, Clippy, unit/CLI integration, release, WASM, cross-build, and
    platform smoke checks pass on the signed implementation PR and post-merge
    `main`.
13. Implementation lands from a signed child branch through a reviewed PR.
    Acceptance evidence and links are recorded here before the status changes
    to `Accepted`.

## 9. Acceptance Evidence

- The implementation landed through signed commits
  [`7f3d2c9`](https://github.com/nomo-lang/nomo/commit/7f3d2c905d5a66ea18660a28e9888a68066b83cf)
  and [`c47af0e`](https://github.com/nomo-lang/nomo/commit/c47af0e6018e97187a08e09ac5e5ec7dda2d2b3d)
  on reviewed [nomo PR #14](https://github.com/nomo-lang/nomo/pull/14),
  merged as [`fde7016`](https://github.com/nomo-lang/nomo/commit/fde701629fbb6d0d4eebf879c96083fd7cebff94).
- The final [PR smoke run](https://github.com/nomo-lang/nomo/actions/runs/30112910817)
  passed Linux smoke with AddressSanitizer/LeakSanitizer, Windows native host
  runtime checks, and the macOS structured JSON runtime.
- The post-merge [`main` CI run](https://github.com/nomo-lang/nomo/actions/runs/30113047313)
  passed formatting, Clippy, the complete workspace test suite, release and
  browser WASM builds, sandbox verification, compiler latency gates, examples,
  workspace checks, and real Linux x86_64-to-arm64 and macOS
  arm64-to-x86_64 cross-builds.
- Native and browser runtimes run the shared
  `tests/fixtures/structured_json_conformance.nomo` corpus. Boundary,
  invalid-UTF-8, lifecycle, secret-safety, and OpenAI-compatible example tests
  cover gates 2 through 11.
- This acceptance update synchronizes both v0.1 specifications and the RFC
  indexes with the shipped API and recorded CI evidence.

## 10. Deferred Follow-up

- Deterministic `from_f64` conversion.
- Incremental/streaming parser and a byte-buffer input type.
- Length-carrying Nomo strings and U+0000 support.
- Typed struct/enum derivation and schema validation.
- Cached indexes or a tree-backed optimization behind `JsonValue`.
- JSON Pointer, JSON Patch, JSONPath, and mutable update operations.
- JSON-RPC and MCP message framing, which build on this value API.

## 11. References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259)
- `std/src/json.nomo`
- `crates/nomo_compiler/src/builtins/builtins_extensions.rs`
- `crates/nomo_ir/src/lib.rs`
- `crates/nomo_codegen_c/src/runtime/host_json_helpers.rs`
- `crates/nomo_wasm/src/interpreter.rs`
- `crates/nomo/tests/cli_project.rs`
