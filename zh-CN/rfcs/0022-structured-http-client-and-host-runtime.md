# RFC 0022：结构化 HTTP Client 与工具链托管 Host Runtime

> 语言 / Language: 中文 | [English](../../en/rfcs/0022-structured-http-client-and-host-runtime.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0022 |
| 标题 | 结构化 HTTP client 与工具链托管 host runtime |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-24 |
| 实现状态 | 尚未接受；当前 runtime 只支持阻塞式 plain HTTP |
| 关联主题 | HTTP、HTTPS、TLS、标准库、host runtime、secret、C backend |
| 关联 RFC | [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md) |

---

## 1. 摘要

Nomo v0.1 应提供阻塞式、校验证书的 HTTPS client，并支持结构化请求、自定义
header、显式 timeout、受限 response body 与稳定的传输错误。公共 API 继续由
`std.http` 的 canonical Nomo 源码定义；应用不声明 C FFI、native source 或
linker flag。C99 backend 调用工具链托管的 host runtime，该 runtime 内部可以
使用平台库。Streaming、取消、连接池与 async 语法属于后续独立切片。

## 2. 动机

Nomo 原生 CLI 目前可以打开 socket，并发出基础 `http://` GET/POST，但无法安全
调用模型 endpoint。OpenAI-compatible API 至少需要校验 HTTPS、`Authorization`
和 `Content-Type` header、JSON POST body、timeout，以及从不可信 peer 读取数据
时的容量上限。若要求每个应用自己编写 unsafe C binding，会重复安全敏感代码，
也会让标准库提供 HTTP 的承诺失去意义。

Package resolver 已通过 Rust dependency 完成 verified HTTPS，但该实现属于
tool 进程；编译后的 Nomo 程序当前是由平台 C toolchain 链接的 C99 产物，无法
直接使用 resolver transport。因此必须正式定义 runtime boundary，不能默认
`std.http` 会自动获得 resolver 的 HTTPS 能力。

## 3. 当前证据与 Gap

本提案基于 2026-07-24 的实现、规格、测试与示例。

| 表面 | 当前证据 | 原生 CLI Agent 的缺口 |
| --- | --- | --- |
| 公共 API | `std/src/http.nomo` 提供 `get(url)`、`post(url, body)` 与基础 server | 没有结构化 request、header、timeout、body limit 或 response header |
| Compiler | `builtins_http.rs` 把 GET/POST 降低为两个固定 intrinsic | 没有 request value，也没有安全敏感字段校验 |
| C99 runtime | `host_http_helpers.rs` 只接受 `http://`，发送 HTTP/1.0，并持续扩容读取到连接关闭 | 没有 TLS、timeout、容量上限、chunk decode，response 解析过于简单 |
| 测试 | `crates/nomo/tests/examples.rs` 使用本地 plain TCP fixture | 没有 verified TLS、自定义 header、timeout、body cap 或 secret redaction |
| 示例 | `examples/std_http` 只覆盖 plain GET/POST | 没有真实的 OpenAI-compatible request |
| 规格 | 中英文 v0.1 规格都明确推迟 TLS 与 custom header | 规格不能声称已经具备模型调用闭环 |
| JSON | `JsonValue` 仅保存校验过的 raw JSON text | 足够完成 P0 literal request，但结构化 JSON 构造仍是 P1 gap |
| Process | 只有同步 shell command helper | 长生命周期子进程与 framing 仍是 P1/P2 gap |
| 并发 | v0.1 runtime 使用非原子 managed value，且没有 task model | 不能把 streaming 或并行 tool execution 偷渡进本 HTTP 切片 |

## 4. 详细设计

### 4.1 公共 Nomo API

保留现有 convenience function 的源码兼容性。新的结构化 request 是 primitive
operation：

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

P0 只接受 `GET` 与 `POST` method string。限制初始 method 集可以让 request-body
与 redirect 语义保持可审查，同时 request shape 仍可扩展。`get` 和 `post`
调用 `send` 时使用 30 秒 timeout 与 8 MiB response-body limit。

HTTP status（包括 4xx 与 5xx）返回 `Ok(HttpResponse)`。`Err` 只表示非法输入、
host 支持不可用、DNS/connect/TLS 失败、timeout、body 超限或 transport response
格式错误。

### 4.2 校验与限制

- URL scheme 只允许 `http://` 与 `https://`；拒绝 user-info 与 fragment，允许
  query string。
- HTTPS 通过平台 trust 校验 peer certificate 与 host name，不提供 insecure 或
  skip-verification flag。
- Header name 必须是非空 HTTP token；在任何网络 I/O 前拒绝 name/value 中的
  CR、LF 或 NUL。
- Runtime 托管 `Host`、`Connection` 与 `Content-Length`，调用方不能覆盖这些
  hop/framing header；允许 `Authorization`、`Content-Type` 与应用 header。
- `timeout_millis` 是总请求 deadline，必须大于零。
- `max_response_bytes` 必须大于零，且不能超过 128 MiB 的 runtime hard cap；
  response header 有独立 64 KiB cap。
- P0 默认不跟随 redirect，避免 credential 自动转发到不同 origin。

稳定的 P0 error code 为 `invalid_request`、`runtime_unavailable`、`dns`、
`connect`、`tls`、`timeout`、`response_too_large`、`protocol` 与
`transport`。Human-readable message 可以变得更精确，但程序应按 `code` 分支。

### 4.3 Secret 处理

Runtime 不得把 request-header value 或 request body 复制进 `HttpError`、
compiler diagnostic、trace line 或默认 log。错误不得包含 URL user-info 或
query text。测试使用 sentinel bearer token 与 body，并断言 failure path 中均
不可见。

本地 TLS integration fixture 可以设置 `NOMO_HTTP_CA_BUNDLE` 指向临时 CA 文件。
这是测试和受控开发 hook，并不是关闭证书校验：该 CA 会成为 trust root，host-name
verification 仍然必须执行。生产默认使用平台 trust。

### 4.4 工具链托管 Host Runtime

Nomo 应用只看到安全的 `std.http` API。Compiler 把 `http.send` 降低为受控
runtime symbol，并拥有 request、response、header 与 error 的 C 表示。应用不
增加 `[ffi]`，也不使用 `extern`、`unsafe` 或 `CString`。

初始 native adapter 为：

- Unix-like target：生成的 runtime 动态加载稳定的 libcurl easy interface。
  Toolchain release gate 必须证明平台 libcurl 兼容，或随目标 toolchain 一起
  打包；编译 Nomo 应用不要求 development header。
- Windows target：生成的 runtime 使用 WinHTTP 与工具链托管的隐式 linker
  metadata；应用不写 `winhttp`。

这与“工具链内部完全不使用 C 或 system library”不是同一个承诺。这里要求的是
应用代码不拥有 FFI boundary。Backend-specific 代码被封装在单一 runtime contract
后，可在不改变 Nomo 源码的情况下替换。

Browser WASM interpreter 继续保持沙盒，并对该 native host operation 返回
`runtime_unavailable`。由浏览器提供 `fetch` capability 需要单独的 host-capability
设计，不属于原生 CLI acceptance gate。

### 4.5 C99 Backend 与 Ownership

`HttpRequest` 以值传给 intrinsic，在同步调用期间只借用其中内容；runtime 返回后
不保留 request string 或 array。Response header 与 body 是普通 managed Nomo
value，遵守现有非原子 reference-counting 规则。Runtime callback 必须在扩容前
检查限制，并在每条错误路径释放所有 partial value。

Target-specific system linkage 是由 canonical target triple 选择的隐式 toolchain
metadata，不进入 `nomo.toml`、package checksum 或用户 FFI graph。

### 4.6 OpenAI-Compatible P0 示例

仓库新增一个真实 Nomo 示例：

1. 从 environment 读取 endpoint 与 bearer token；
2. 构造 `Authorization` 与 `Content-Type` header；
3. 通过 HTTPS POST 一个非流式 `/v1/chat/completions` JSON request；
4. 检查 HTTP status 并打印 response body。

Integration test 使用带生成 CA 的 localhost TLS server，校验 request line、header
与嵌套 JSON payload，并返回 OpenAI-compatible response。测试不读取真实 API key，
也不访问公网。

## 5. 备选方案

| 方案 | 优点 | 缺点 | 倾向 |
| --- | --- | --- | --- |
| 工具链托管 libcurl/WinHTTP adapter | 保持 C99 产物；TLS/HTTP parser 成熟；应用无 FFI | 需要 runtime packaging 与平台 adapter 工作 | P0 提案 |
| 每个 artifact 链接 Rust static runtime | 可复用 resolver TLS stack 与 Rust 强类型 | 需要 per-target runtime artifact，并改变当前 C-only cross-build/distribution contract | v0.1 后重新评估 |
| 应用拥有 C FFI package | 原型快且 backend 选择自由 | 每个应用都承担 secret/TLS 安全；违背标准库目标 | 拒绝 |
| 继续 plain HTTP helper | 无实现成本 | 无法安全调用生产模型 endpoint | 拒绝 |

## 6. 缺点与风险

- Dynamic library discovery 必须确定且有清晰诊断。
- libcurl 与 WinHTTP 的 proxy、certificate store、error detail 不完全一致；稳定
  Nomo contract 必须归一化可观察行为。
- Response-header parsing 会在生成 C 中增加 managed array 与 cleanup path。
- 同步 total timeout 不能替代 streaming idle-timeout 或 cancellation。
- P0 示例使用 literal JSON body，因为结构化 JSON 构造被明确留在后续切片。

## 7. 对 v0.1 范围的影响

HTTPS 是可用 Nomo 原生 CLI Agent 的 v0.1 blocker；但 async syntax、SSE、连接池、
cookie、自动 redirect、compression control、TLS HTTP server 与任意 method 均
不在本 RFC 范围。

本 RFC 不承诺复刻完整 Hermes 产品，而是建立可复用、受限的模型调用 transport，
使应用能够用 Nomo 源码构建一个 agent loop。

## 8. Acceptance Gate

以下 gate 全部通过前，本 RFC 保持 `Proposed`：

1. Canonical `std.http` source、compiler lowering、生成 C ABI、文档与中英文 v0.1
   规格暴露完全一致的结构化 API。
2. 现有 plain-HTTP `get` 与 `post` 示例继续通过。
3. Localhost TLS fixture 在不访问公网的情况下证明 certificate/host-name
   verification、自定义 `Authorization`/`Content-Type`、JSON POST、response
   header，以及 chunked 或 content-length response decode。
4. 确定性测试证明 timeout、response-body cap、非法 header 拒绝、TLS failure 与
   稳定 error code。
5. Failure-path 测试证明 bearer token、request body 与 URL query secret 不会进入
   diagnostic、error 或 captured log。
6. OpenAI-compatible Nomo 示例无需真实 API key 即可在 TLS fixture 上运行。
7. Formatting、Clippy、unit test、CLI integration test、browser-WASM unsupported
   behavior、macOS arm64-to-x86_64 cross-build、Linux x86_64-to-arm64 cross-build，
   以及 Windows native compile/run path 全部通过。
8. 实现必须通过签名提交、子分支、PR review 与 required CI 合入；之后 RFC 才能转
   `Accepted`。

## 9. 推迟的后续工作

- Streaming response body 与 SSE parsing，包括 cancellation 与 idle timeout。
- Reusable client、连接池、proxy、redirect policy 与 compression 配置。
- 结构化 JSON 构造与字段访问。
- Browser `fetch` host capability。
- 用于并行 tool 与 streaming 的更广泛 task/concurrency model。

## 10. 参考

- `std/src/http.nomo`
- `crates/nomo_compiler/src/builtins/builtins_http.rs`
- `crates/nomo_codegen_c/src/runtime/host_http_helpers.rs`
- `crates/nomo/tests/examples.rs`
- [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)
- [RFC 0013](./0013-registry-protocol-and-package-integrity.md)
- [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0017](./0017-target-triples-and-cross-compilation.md)
