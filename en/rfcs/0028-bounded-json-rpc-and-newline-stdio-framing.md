# RFC 0028: Bounded JSON-RPC and Newline-Framed Standard I/O

> Language: [中文](../../zh-CN/rfcs/0028-bounded-json-rpc-and-newline-stdio-framing.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0028 |
| Title | Bounded JSON-RPC and newline-framed standard I/O |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | JSON-RPC, MCP, stdio, framing, process, JSON, Agent |
| Related RFCs | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0024](./0024-controlled-child-processes-and-stdio.md), [RFC 0025](./0025-structured-json-values-and-construction.md), [RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md) |

---

## 1. Summary

Nomo v0.1 should provide `std.jsonrpc`, a bounded JSON-RPC 2.0 message codec
and incremental newline decoder. Together with the long-lived child-process
API accepted by RFC 0024, this is the missing reusable primitive for an MCP
stdio client written mainly in Nomo.

The transport baseline is the stable MCP 2025-06-18 stdio contract: a client
launches a subprocess, sends one JSON-RPC message per line on stdin, receives
one message per line on stdout, and keeps diagnostic text on stderr. JSON-RPC
batch arrays and `Content-Length` framing are not part of this contract.

`JsonRpcDecoder` is an opaque value state, not a native resource handle.
`feed` consumes one state and one arbitrary UTF-8 stdout chunk, then returns a
new state plus every complete validated message. The final incomplete suffix
remains in the new state. This value-oriented design works in both the C99
backend and browser WASM, needs no close operation, and cannot leak a global
decoder registry.

All public operations are bounded. Errors report stable categories and
positions or counts where safe, but never echo a rejected message, method,
parameters, result, error data, token, or stderr content.

## 2. Goals and Non-goals

### 2.1 Goals

1. Decode JSON-RPC messages across arbitrary stdout chunk boundaries.
2. Encode exactly one validated message followed by `\n`.
3. Validate the JSON-RPC 2.0 request, notification, success-response, and
   error-response envelope.
4. Provide constructors so ordinary Agent code does not manually assemble
   reserved JSON-RPC fields.
5. Interoperate with MCP stdio servers while preserving stderr and process
   lifecycle through `std.process`.
6. Enforce explicit message, buffer, and per-feed result limits.
7. Keep native and browser-WASM codec behavior identical.
8. Require no C FFI in Nomo application code.

### 2.2 Non-goals

This RFC does not add:

- an MCP session object, capability negotiation policy, tool registry,
  schema-to-Nomo code generation, or Agent product;
- MCP Streamable HTTP, legacy HTTP+SSE, WebSocket, or custom transports;
- JSON-RPC batch arrays;
- `Content-Length` framing;
- automatic request-id allocation, response correlation, retry, or timeout;
- concurrent use of one decoder state;
- binary messages or invalid UTF-8 recovery;
- shared mutable state, futures, `async`/`await`, or a new scheduler.

MCP method names and payload schemas evolve independently of the transport.
Applications or a later `std.mcp` layer own those protocol-level choices.

## 3. Current Gap Audit

| Area | Current implementation | Gap |
| --- | --- | --- |
| Process | `start`, bounded stdin writes, multiplexed stdout/stderr events, wait and termination | stdout is delivered as arbitrary chunks rather than complete protocol messages |
| String | UTF-8 strings, split, trim, prefix/suffix checks | no safe substring primitive for retaining an incomplete chunk suffix |
| JSON | opaque bounded `JsonValue`, traversal, construction, serialization | no JSON-RPC envelope validation or transport framing |
| Tasks | isolated native workers | not needed for one pull-based MCP connection |
| Browser WASM | deterministic JSON support but no host process | the codec can still be tested and reused without pretending that subprocesses exist |

RFC 0024 intentionally deferred JSON-RPC framing. Asking every application to
reconstruct it with string operations would duplicate limit handling and make
fragmentation, coalescing, CRLF interoperability, and secret-safe errors
inconsistent.

## 4. Detailed Design

### 4.1 Canonical `std.jsonrpc` API

```rust
pub enum JsonRpcMessageKind {
    Request
    Notification
    Success
    Error
}

pub struct JsonRpcProtocolError {
    pub code: string
    pub message: string
}

pub struct JsonRpcMessage {
    raw: string
}

pub struct JsonRpcDecoder {
    pending: string
    max_message_bytes: u64
}

pub struct JsonRpcDecodeBatch {
    pub decoder: JsonRpcDecoder
    pub messages: Array<JsonRpcMessage>
}

pub fn decoder(
    max_message_bytes: u64
) -> Result<JsonRpcDecoder, JsonRpcProtocolError>

pub fn feed(
    decoder: JsonRpcDecoder,
    chunk: string
) -> Result<JsonRpcDecodeBatch, JsonRpcProtocolError>

pub fn finish(
    decoder: JsonRpcDecoder
) -> Result<void, JsonRpcProtocolError>

pub fn parse(
    value: json.JsonValue,
    max_message_bytes: u64
) -> Result<JsonRpcMessage, JsonRpcProtocolError>

pub fn encode(
    message: JsonRpcMessage,
    max_message_bytes: u64
) -> Result<string, JsonRpcProtocolError>

pub fn value(message: JsonRpcMessage) -> json.JsonValue
pub fn kind(message: JsonRpcMessage) -> JsonRpcMessageKind

pub fn request(
    id: json.JsonValue,
    method: string,
    params: Option<json.JsonValue>
) -> Result<JsonRpcMessage, JsonRpcProtocolError>

pub fn notification(
    method: string,
    params: Option<json.JsonValue>
) -> Result<JsonRpcMessage, JsonRpcProtocolError>

pub fn success(
    id: json.JsonValue,
    result: json.JsonValue
) -> Result<JsonRpcMessage, JsonRpcProtocolError>

pub fn failure(
    id: json.JsonValue,
    code: i64,
    message: string,
    data: Option<json.JsonValue>
) -> Result<JsonRpcMessage, JsonRpcProtocolError>
```

`JsonRpcMessage` and `JsonRpcDecoder` have compiler-known nominal identities.
Their fields are private and cannot be constructed, read, or updated by source
code. `JsonRpcDecodeBatch` is public so callers can replace their current
decoder and iterate the returned messages.

`value` exposes the validated envelope as a normal `JsonValue`. Existing
`std.json` accessors provide method, id, params, result, error, and extension
field inspection without duplicating a second JSON object API.

### 4.2 Functional decoder state

`decoder(max_message_bytes)` accepts values from 1 through 1,048,575 bytes.
The upper bound reserves one byte for the newline so an encoded message fits
RFC 0024's 1 MiB stdin payload limit.

`feed` treats its input decoder as immutable. On success it returns:

- every complete line as one validated `JsonRpcMessage`, in order; and
- a new decoder containing only the final unterminated suffix.

Copying a decoder intentionally forks value state. There is no hidden
cross-call mutation, global handle, close operation, or stale-handle failure.
The managed string representation provides the normal ARC/COW lifecycle.

One `feed` operation accepts at most 1 MiB of chunk data, at most 2,097,151
bytes across the old pending suffix plus the new chunk, and at most 4,096
complete messages. Every individual line excluding its delimiter must fit
`max_message_bytes`. Exceeding any limit returns `limit` without mutating the
input state.

An empty chunk is a no-op. `finish` succeeds only when no unterminated bytes
remain. A non-empty suffix is a `framing` error even if it happens to contain
valid JSON, because the peer did not terminate the message.

### 4.3 Newline rules

The wire delimiter is `\n`. A preceding `\r` is removed so CRLF-producing
peers remain interoperable. A bare `\r` elsewhere remains part of the line
and normally causes JSON validation to fail.

Empty lines are `framing` errors. Literal line breaks therefore cannot occur
inside a message; JSON strings must use escaped `\n` or `\r`.

`encode` returns the validated JSON text followed by exactly one `\n`. It
rejects message storage containing a literal CR or LF and rechecks the
requested size limit. It does not add `Content-Length`, a second newline, or
transport metadata.

### 4.4 JSON-RPC envelope validation

Each message must be a JSON object with exactly `"jsonrpc": "2.0"` and one of
these shapes:

- request: string `method`, present non-null string or number `id`, optional
  object-or-array `params`;
- notification: string `method`, absent `id`, optional object-or-array
  `params`;
- success response: present string, number, or null `id`, present `result`;
- error response: present string, number, or null `id`, present `error`.

An error object requires an exact signed-64-bit integer `code`, string
`message`, and optional `data`.

`result` and error `data` may be any JSON value. Unknown top-level fields are
preserved for extensions such as MCP `_meta`. Duplicate reserved fields are
rejected. Request fields cannot be mixed with response fields, and a response
must contain exactly one of `result` and `error`. Top-level arrays are rejected
because the selected MCP transport does not use JSON-RPC batches.

Constructors apply the same validation. Request ids accept only strings or
numbers and reject null. Response ids additionally accept null for protocol
error interoperability. Callers create ids and payloads with `std.json`.

### 4.5 Integration with `std.process`

The codec does not own a subprocess. A client loop remains explicit:

1. start a shell-free `ProcessCommand`;
2. create a decoder and a JSON-RPC request;
3. encode and pass the line to `process.write_stdin`;
4. wait for `ProcessEvent.StdinFlushed` before the next write;
5. pass each `ProcessEvent.Stdout` chunk to `jsonrpc.feed`;
6. consume stderr separately and never feed it to the decoder;
7. correlate ids and enforce request timeout in application or protocol code;
8. call `finish` after exit, then close the child handle.

This separation keeps process cancellation, idle timeout, exit status, and
stderr policy in RFC 0024 while keeping the codec deterministic and reusable.

### 4.6 Error and secrecy contract

Stable error codes are:

| Code | Meaning |
| --- | --- |
| `invalid_request` | invalid public argument or forged opaque representation |
| `limit` | message, chunk, combined buffer, or batch count exceeded a bound |
| `framing` | empty line, unterminated final message, or literal newline in outbound storage |
| `json` | a complete line is not valid bounded JSON |
| `protocol` | JSON is valid but not one accepted JSON-RPC 2.0 envelope |

Error messages may name a category, field name, byte position, expected kind,
or configured limit. They must not contain the rejected line, method, id,
params, result, error data, stdout chunk, stderr text, Authorization value, or
token-shaped substring.

### 4.7 C99 backend and browser WASM

Canonical Nomo source declares the API and intrinsic identities. The C99
backend provides bounded scanning, line extraction, JSON validation, and
managed-value construction using the same ownership conventions as
`std.json`. It does not create a native thread, socket, file, process, or
decoder registry.

The browser-WASM interpreter implements the same codec and limits. Browser
WASM still rejects `std.process`; successful codec parity must not be described
as browser subprocess support.

## 5. Rejected Alternatives

### 5.1 `Content-Length` headers

The selected stable MCP stdio specification defines newline-delimited JSON-RPC
messages. Implementing legacy Language Server Protocol framing would add a
second parser, ambiguous mode selection, and unneeded attack surface. A future
non-MCP protocol can propose it separately.

### 5.2 Expose substring operations and leave framing to each application

General string slicing may be useful later, but it does not centralize JSON-RPC
shape checks, size limits, CRLF policy, or secret-safe diagnostics.

### 5.3 A runtime-owned mutable decoder handle

A handle requires a registry, allocation limits, stale-handle checks, explicit
close, and native/WASM lifecycle parity. Decoder state is only a bounded string
and one limit, so an opaque value is simpler and follows Nomo value semantics.

### 5.4 A combined `McpClient`

That would prematurely freeze MCP initialization, capability negotiation,
method schemas, request correlation, and server-version policy. This RFC first
lands the reusable transport and JSON-RPC layer.

## 6. Acceptance Gates

RFC 0028 may become `Accepted` only when all of these are complete:

1. bilingual RFC, specification, standard-library docs, and public source API
   agree exactly;
2. opaque-value construction and field access are rejected by semantic tests;
3. unit tests cover all four envelopes, reserved-field duplicates, invalid
   ids/params/errors, extensions, escaped newlines, CRLF, empty lines, partial
   lines, coalesced lines, finish, and every limit;
4. native and browser-WASM tests assert the same results and error codes;
5. a local no-network fixture is launched through `std.process`, deliberately
   fragments and coalesces stdout, writes independent stderr, handles at least
   two ids, and exits with a verified status;
6. an MCP-shaped Nomo example performs initialization and one subsequent
   request without application C FFI or a real API key;
7. Linux, macOS, and Windows CI pass; sanitizers or equivalent memory/lifecycle
   coverage exercise repeated decoder replacement and arrays of messages;
8. diagnostics are tested not to echo sentinel secrets;
9. generated C remains C99-compatible and programs not importing
   `std.jsonrpc` incur no codec-specific generated support;
10. commits are signed, the feature is merged through a child branch and PR,
    and synchronized local `main` worktrees are clean.

## 7. References

- [MCP 2025-06-18 transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [RFC 0024: Controlled child processes and multiplexed standard I/O](./0024-controlled-child-processes-and-stdio.md)
- [RFC 0025: Structured JSON values, access, and construction](./0025-structured-json-values-and-construction.md)
