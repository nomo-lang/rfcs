# RFC 0022: Structured HTTP Client and Toolchain-Owned Host Runtime

> Language: [中文](../../zh-CN/rfcs/0022-structured-http-client-and-host-runtime.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0022 |
| Title | Structured HTTP client and toolchain-owned host runtime |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-24 |
| Implementation | Not yet accepted; the existing runtime supports blocking plain HTTP only |
| Topics | HTTP, HTTPS, TLS, standard library, host runtime, secrets, C backend |
| Related RFCs | [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md), [RFC 0013](./0013-registry-protocol-and-package-integrity.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md) |

---

## 1. Summary

Nomo v0.1 should provide a blocking, certificate-verified HTTPS client with
structured requests, custom headers, explicit timeouts, bounded response
bodies, and stable transport errors. The public API remains canonical Nomo
source in `std.http`; applications do not declare C FFI, native sources, or
linker flags. The C99 backend calls a toolchain-owned host runtime that may use
platform libraries internally. Streaming, cancellation, connection pooling,
and async syntax are separate follow-up slices.

## 2. Motivation

A native Nomo CLI can currently open sockets and issue basic `http://` GET and
POST requests, but it cannot safely call a model endpoint. OpenAI-compatible
APIs require verified HTTPS, `Authorization` and `Content-Type` headers, JSON
POST bodies, timeouts, and an upper bound on data read from an untrusted peer.
Requiring each application to write unsafe C bindings would duplicate
security-sensitive code and make the standard library promise misleading.

The package resolver already performs verified HTTPS through its Rust
dependencies. That implementation belongs to the tool process and is not
available to a compiled Nomo program, whose current native artifact is a
self-contained C99 translation linked with the platform C toolchain. The
runtime boundary therefore needs an explicit design instead of silently
assuming the resolver transport can back `std.http`.

## 3. Current Evidence and Gaps

The proposal is based on the implementation, specification, tests, and
examples as of 2026-07-24.

| Surface | Current evidence | Gap for a native CLI agent |
| --- | --- | --- |
| Public API | `std/src/http.nomo` exposes `get(url)` and `post(url, body)` plus a basic server | No structured request, headers, timeout, body limit, or response headers |
| Compiler | `builtins_http.rs` lowers GET and POST to two fixed intrinsic calls | No request value or validation for security-sensitive fields |
| C99 runtime | `host_http_helpers.rs` accepts only `http://`, sends HTTP/1.0, and reads until close into a growing buffer | No TLS, no timeout, unbounded allocation, no chunk decoding, and naive response parsing |
| Tests | `crates/nomo/tests/examples.rs` uses a local plain TCP fixture | No verified TLS, custom-header, timeout, body-cap, or secret-redaction coverage |
| Example | `examples/std_http` exercises plain GET and POST | No realistic OpenAI-compatible request |
| Specification | both v0.1 specifications explicitly defer TLS and custom headers | The specification cannot claim model-call readiness |
| JSON | `JsonValue` stores validated raw JSON text only | Sufficient for a literal P0 request, but structured JSON construction remains a P1 gap |
| Process | synchronous shell-command helpers only | Long-lived child processes and framing remain a P1/P2 gap |
| Concurrency | v0.1 runtime uses non-atomic managed values and no task model | Streaming and parallel tool execution must not be smuggled into this HTTP slice |

## 4. Detailed Design

### 4.1 Public Nomo API

The existing convenience functions remain source-compatible. A new structured
request is the primitive operation:

```nomo
pub struct HttpHeader {
    pub name: string
    pub value: string
}

pub struct HttpRequest {
    pub method: string
    pub url: string
    pub headers: Array<HttpHeader>
    pub body: string
    pub timeout_millis: u64
    pub max_response_bytes: u64
}

pub struct HttpResponse {
    pub status: i64
    pub headers: Array<HttpHeader>
    pub body: string
}

pub struct HttpError {
    pub code: string
    pub message: string
}

http.send(request: HttpRequest) -> Result<HttpResponse, HttpError>
http.get(url: string) -> Result<HttpResponse, HttpError>
http.post(url: string, body: string) -> Result<HttpResponse, HttpError>
```

P0 accepts `GET` and `POST` method strings only. Restricting the initial method
set keeps request-body and redirect semantics reviewable while leaving the
request shape extensible. `get` and `post` call `send` with a 30-second timeout
and an 8 MiB response-body limit.

HTTP status codes, including 4xx and 5xx, produce `Ok(HttpResponse)`. `Err`
represents invalid input, unavailable host support, DNS/connect/TLS failures,
timeouts, body-limit violations, or malformed transport responses.

### 4.2 Validation and Limits

- URL schemes are limited to `http://` and `https://`. User-info and fragments
  are rejected. Query strings are allowed.
- HTTPS verifies the peer certificate and host name through platform trust.
  There is no insecure or skip-verification flag.
- Header names must be non-empty HTTP token strings. Names and values containing
  CR, LF, or NUL are rejected before network I/O.
- The runtime owns `Host`, `Connection`, and `Content-Length`; callers cannot
  override these hop/framing headers. `Authorization`, `Content-Type`, and
  application headers are allowed.
- `timeout_millis` is a total request deadline and must be positive.
- `max_response_bytes` must be positive and cannot exceed the runtime hard cap
  of 128 MiB. Response headers have a separate 64 KiB cap.
- Redirect following is disabled in P0 so credentials cannot be forwarded to a
  different origin by default.

The stable P0 error codes are `invalid_request`, `runtime_unavailable`,
`dns`, `connect`, `tls`, `timeout`, `response_too_large`, `protocol`, and
`transport`. The human-readable message may become more precise, but code
should branch on `code`.

### 4.3 Secret Handling

The runtime must never copy request-header values or the request body into an
`HttpError`, compiler diagnostic, trace line, or default log entry. It must not
include URL user-info or query text in an error. Tests use sentinel bearer
tokens and body values and assert that neither appears on failure.

The local TLS integration fixture may set `NOMO_HTTP_CA_BUNDLE` to a temporary
CA file. This is a test and controlled-development hook, not a certificate
verification bypass: the supplied CA becomes a trust root and host-name
verification remains required. Production defaults use platform trust.

### 4.4 Toolchain-Owned Host Runtime

The Nomo application sees only the safe `std.http` API. The compiler lowers
`http.send` to a controlled runtime symbol and owns the C representation of the
request, response, headers, and error. Applications do not add an `[ffi]`
section and do not use `extern`, `unsafe`, or `CString`.

The initial native adapters are:

- Unix-like targets: the generated runtime dynamically loads the stable libcurl
  easy interface. The toolchain release gate must either prove a compatible
  platform libcurl or bundle one with the target toolchain. Development headers
  are not required to compile a Nomo application.
- Windows targets: the generated runtime uses WinHTTP and toolchain-owned
  implicit linker metadata. Applications do not mention `winhttp`.

This is intentionally different from claiming that the toolchain uses no C or
system library. The requirement is that application code does not own the FFI
boundary. Backend-specific code stays behind one runtime contract and can be
replaced without changing Nomo source.

The browser WASM interpreter remains sandboxed and reports
`runtime_unavailable` for this native host operation. A browser-provided fetch
capability requires a separate host-capability design and is not part of the
native CLI acceptance gate.

### 4.5 C99 Backend and Ownership

`HttpRequest` is passed by value to the intrinsic and borrowed for the duration
of the synchronous call. The runtime retains no request strings or arrays after
return. Response headers and body are ordinary managed Nomo values and follow
the existing non-atomic reference-counting rules. Runtime callbacks enforce
limits before growing buffers and release all partial values on every error
path.

Target-specific system linkage is implicit toolchain metadata selected from the
canonical target triple. It does not enter `nomo.toml`, package checksums, or
the user FFI graph.

### 4.6 OpenAI-Compatible P0 Example

The repository adds a real Nomo example that:

1. reads an endpoint and bearer token from the environment;
2. constructs `Authorization` and `Content-Type` headers;
3. POSTs a non-streaming `/v1/chat/completions` JSON request over HTTPS;
4. checks the HTTP status and prints the response body.

Its integration test uses a localhost TLS server with a generated CA, validates
the request line, headers, and nested JSON payload, and returns an
OpenAI-compatible response. It never reads a real API key and never reaches the
public Internet.

## 5. Alternatives

| Option | Advantages | Disadvantages | Direction |
| --- | --- | --- | --- |
| Toolchain-owned libcurl/WinHTTP adapters | Keeps C99 output, mature TLS and HTTP parsing, no application FFI | Runtime packaging and platform adapter work | Proposed for P0 |
| Rust static runtime linked into every artifact | Reuses the resolver TLS stack and strong Rust types | Requires per-target runtime artifacts and changes the current C-only cross-build/distribution contract | Revisit after v0.1 |
| Application-owned C FFI package | Fast prototype and maximum backend choice | Exposes secrets and TLS safety to every application; violates the standard-library goal | Rejected |
| Keep plain HTTP helpers | No implementation cost | Cannot safely call production model endpoints | Rejected |

## 6. Drawbacks and Risks

- Dynamic library discovery must be deterministic and diagnosed clearly.
- libcurl and WinHTTP can differ in proxy, certificate-store, and error details;
  the stable Nomo contract must normalize observable behavior.
- Response-header parsing introduces managed arrays and additional cleanup
  paths in generated C.
- A synchronous total timeout does not provide streaming idle-timeout or
  cancellation semantics.
- The P0 example uses a literal JSON body because structured JSON construction
  is deliberately tracked as a later slice.

## 7. Impact on v0.1 Scope

HTTPS is a v0.1 blocker for a useful native Nomo CLI agent, but async syntax,
SSE, connection pooling, cookies, automatic redirects, compression controls,
HTTP servers over TLS, and arbitrary methods are not.

This RFC does not promise a complete Hermes-like product. It establishes a
reusable, bounded model-call transport on which an application can build one
agent loop in Nomo source.

## 8. Acceptance Gate

This RFC remains `Proposed` until all gates pass:

1. Canonical `std.http` source, compiler lowering, generated C ABI, docs, and
   both v0.1 specifications expose the same structured API.
2. Existing plain-HTTP `get` and `post` examples continue to pass.
3. A localhost TLS fixture proves certificate and host-name verification,
   custom `Authorization`/`Content-Type`, JSON POST, response headers, and
   chunked or content-length response decoding without public network access.
4. Deterministic tests prove timeout, response-body cap, invalid-header
   rejection, TLS failure, and stable error codes.
5. Failure-path tests prove that bearer tokens, request bodies, and URL query
   secrets do not appear in diagnostics, errors, or captured logs.
6. The OpenAI-compatible Nomo example runs against the TLS fixture without a
   real API key.
7. Formatting, Clippy, unit tests, CLI integration tests, browser-WASM
   unsupported behavior, macOS arm64-to-x86_64 cross-build, Linux
   x86_64-to-arm64 cross-build, and a Windows native compile/run path pass.
8. The implementation lands through signed commits, a child branch, PR review,
   and required CI. Only then may the RFC change to `Accepted`.

## 9. Deferred Follow-Ups

- Streaming response bodies and SSE parsing with cancellation and idle timeout.
- Reusable clients, connection pooling, proxies, redirect policy, and
  compression configuration.
- Structured JSON construction and field access.
- Browser host capabilities for `fetch`.
- A broader task/concurrency model for parallel tools and streaming.

## 10. References

- `std/src/http.nomo`
- `crates/nomo_compiler/src/builtins/builtins_http.rs`
- `crates/nomo_codegen_c/src/runtime/host_http_helpers.rs`
- `crates/nomo/tests/examples.rs`
- [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)
- [RFC 0013](./0013-registry-protocol-and-package-integrity.md)
- [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0017](./0017-target-triples-and-cross-compilation.md)
