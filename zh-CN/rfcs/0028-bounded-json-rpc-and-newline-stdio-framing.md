# RFC 0028：受限 JSON-RPC 与换行分帧标准 I/O

> 语言 / Language: 中文 | [English](../../en/rfcs/0028-bounded-json-rpc-and-newline-stdio-framing.md)

## 元数据

| 字段 | 内容 |
| --- | --- |
| 编号 | 0028 |
| 标题 | 受限 JSON-RPC 与换行分帧标准 I/O |
| 状态 | Accepted（已接受） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 主题 | JSON-RPC、MCP、stdio、framing、process、JSON、Agent |
| 关联 RFC | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0025](./0025-structured-json-values-and-construction.md)、[RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md) |

---

## 1. 摘要

Nomo v0.1 应提供 `std.jsonrpc`：一个受限的 JSON-RPC 2.0 message codec 与增量
换行 decoder。它与 RFC 0024 已接受的长生命周期 child-process API 组合后，构成用
Nomo 原生代码编写 MCP stdio client 所缺少的可复用基础能力。

Transport 基线采用稳定版 MCP 2025-06-18 stdio contract：client 启动 subprocess，
在 stdin 上每行发送一条 JSON-RPC message，在 stdout 上每行接收一条 message，
诊断文本只走 stderr。JSON-RPC batch array 与 `Content-Length` framing 不属于该
contract。

`JsonRpcDecoder` 是 opaque value state，而不是 native resource handle。`feed`
消费一个 state 与任意 UTF-8 stdout chunk，返回新 state 以及全部完整且通过验证的
message。最后一个不完整 suffix 保存在新 state 中。这种 value-oriented 设计同时适用
于 C99 backend 与 browser WASM，不需要 close，也不会泄漏全局 decoder registry。

所有公共操作都有明确上限。错误只报告稳定类别以及安全的 position 或 count，绝不回显
被拒绝的 message、method、params、result、error data、token 或 stderr 内容。

## 2. 目标与非目标

### 2.1 目标

1. 跨任意 stdout chunk 边界解码 JSON-RPC message。
2. 编码一条经过验证的 message，并只追加一个 `\n`。
3. 验证 JSON-RPC 2.0 request、notification、success response 与 error response
   envelope。
4. 提供 constructor，使普通 Agent 代码无需手工拼装 JSON-RPC 保留字段。
5. 与 MCP stdio server 互操作，并继续由 `std.process` 管理 stderr 与 process
   lifecycle。
6. 强制执行 message、buffer 与单次 `feed` result 上限。
7. 保证 native 与 browser-WASM codec 行为一致。
8. Nomo 应用代码不需要 C FFI。

### 2.2 非目标

本 RFC 不增加：

- MCP session object、capability negotiation policy、tool registry、
  schema-to-Nomo code generation 或 Agent 产品；
- MCP Streamable HTTP、旧 HTTP+SSE、WebSocket 或 custom transport；
- JSON-RPC batch array；
- `Content-Length` framing；
- 自动 request-id 分配、response correlation、retry 或 timeout；
- 同一个 decoder state 的并发使用；
- binary message 或 invalid UTF-8 recovery；
- shared mutable state、future、`async`/`await` 或新 scheduler。

MCP method 名称和 payload schema 会独立演进，应由 application 或后续 `std.mcp`
层负责这些 protocol-level 选择。

## 3. 当前 Gap Audit

| 领域 | 当前实现 | 缺口 |
| --- | --- | --- |
| Process | `start`、受限 stdin write、多路复用 stdout/stderr event、wait 与 terminate | stdout 以任意 chunk 交付，并不是完整 protocol message |
| String | UTF-8 string、split、trim、prefix/suffix check | 没有可安全保留不完整 chunk suffix 的 substring primitive |
| JSON | opaque 且受限的 `JsonValue`、traversal、construction、serialization | 没有 JSON-RPC envelope validation 或 transport framing |
| Task | 隔离 native worker | 单个 pull-based MCP connection 不需要 task |
| Browser WASM | 确定性 JSON 支持，但没有 host process | codec 仍可独立测试和复用，但不能假装存在 subprocess |

RFC 0024 有意推迟了 JSON-RPC framing。如果让每个 application 用 string operation
自行重建，就会重复 limit handling，并导致 fragmentation、coalescing、CRLF
interoperability 与 secret-safe error 行为不一致。

## 4. 详细设计

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

`JsonRpcMessage` 与 `JsonRpcDecoder` 具有 compiler-known nominal identity。其
字段为 private，source code 不能构造、读取或更新。`JsonRpcDecodeBatch` 为 public，
使 caller 可以替换当前 decoder 并遍历返回的 message。

`value` 将已验证 envelope 暴露为普通 `JsonValue`。现有 `std.json` accessor 足以
读取 method、id、params、result、error 与 extension field，不需要再复制第二套
JSON object API。

### 4.2 函数式 decoder state

`decoder(max_message_bytes)` 接受 1 到 1,048,575 bytes。上限为换行保留一个
byte，使编码后的 message 能放入 RFC 0024 的 1 MiB stdin payload limit。

`feed` 将输入 decoder 视为 immutable。成功时返回：

- 按顺序排列的所有完整行，每行一个经过验证的 `JsonRpcMessage`；
- 只保存最终未终止 suffix 的新 decoder。

复制 decoder 会有意 fork value state。不存在 hidden cross-call mutation、global
handle、close operation 或 stale-handle failure。Managed string representation
沿用普通 ARC/COW lifecycle。

单次 `feed` 最多接受 1 MiB chunk；旧 pending suffix 与新 chunk 合计最多
2,097,151 bytes；最多产出 4,096 条完整 message。每一行在去掉 delimiter 后都必须
不超过 `max_message_bytes`。超过任一上限返回 `limit`，且不修改输入 state。

空 chunk 是 no-op。只有没有任何未终止 byte 时 `finish` 才成功。非空 suffix 即使
恰好是有效 JSON，也属于 `framing` error，因为 peer 没有终止该 message。

### 4.3 换行规则

Wire delimiter 是 `\n`。若其前面紧邻 `\r`，则移除该字符，以兼容产生 CRLF 的
peer。其他位置的裸 `\r` 仍属于该行，通常会导致 JSON validation 失败。

空行属于 `framing` error。因此 literal line break 不能出现在 message 内；JSON
string 必须使用转义后的 `\n` 或 `\r`。

`encode` 返回经过验证的 JSON text，并恰好追加一个 `\n`。如果 message storage
包含 literal CR/LF，或者超过请求的 size limit，则拒绝。它不增加
`Content-Length`、第二个换行或 transport metadata。

### 4.4 JSON-RPC envelope validation

每条 message 必须是 JSON object，且恰好包含 `"jsonrpc": "2.0"`，并符合以下一种
shape：

- request：string `method`、存在且非 null 的 string 或 number `id`，以及可选的
  object-or-array `params`；
- notification：string `method`、不存在 `id`，以及可选的 object-or-array
  `params`；
- success response：存在 string、number 或 null `id`，并包含 `result`；
- error response：存在 string、number 或 null `id`，并包含 `error`。

Error object 必须包含 exact signed-64-bit integer `code`、string `message`，以及
可选 `data`。

`result` 与 error `data` 可以是任意 JSON value。未知 top-level field 会被保留，以
支持 MCP `_meta` 等扩展。重复的 reserved field 会被拒绝。Request field 不得与
response field 混用；response 必须且只能包含 `result` 与 `error` 之一。Top-level
array 会被拒绝，因为所选 MCP transport 不使用 JSON-RPC batch。

Constructor 采用相同 validation。Request id 只接受 string 或 number，并拒绝
null。Response id 额外接受 null，以支持 protocol error 互操作。Caller 使用
`std.json` 构造 id 与 payload。

### 4.5 与 `std.process` 集成

Codec 不拥有 subprocess。Client loop 保持显式：

1. 启动 shell-free `ProcessCommand`；
2. 创建 decoder 与 JSON-RPC request；
3. encode 后把该行传给 `process.write_stdin`；
4. 等待 `ProcessEvent.StdinFlushed` 后再写下一条；
5. 把每个 `ProcessEvent.Stdout` chunk 交给 `jsonrpc.feed`；
6. 独立消费 stderr，绝不把它交给 decoder；
7. application 或 protocol code 负责 id correlation 与 request timeout；
8. exit 后调用 `finish`，再关闭 child handle。

这种分离让 RFC 0024 继续负责 process cancellation、idle timeout、exit status 与
stderr policy，同时保持 codec 确定且可复用。

### 4.6 Error 与 secrecy contract

稳定 error code 为：

| Code | 含义 |
| --- | --- |
| `invalid_request` | 无效公共参数或伪造的 opaque representation |
| `limit` | message、chunk、组合 buffer 或 batch count 超过上限 |
| `framing` | 空行、未终止 final message 或 outbound storage 中的 literal newline |
| `json` | 完整行不是有效的受限 JSON |
| `protocol` | JSON 有效，但不是被接受的 JSON-RPC 2.0 envelope |

Error message 可以包含 category、field name、byte position、expected kind 或配置
limit，但不得包含被拒绝的 line、method、id、params、result、error data、stdout
chunk、stderr text、Authorization value 或 token-shaped substring。

### 4.7 C99 backend 与 browser WASM

Canonical Nomo source 声明 API 与 intrinsic identity。C99 backend 使用与
`std.json` 相同的 ownership convention 提供受限 scanning、line extraction、JSON
validation 与 managed-value construction。它不创建 native thread、socket、file、
process 或 decoder registry。

Browser-WASM interpreter 实现相同 codec 与 limit。Browser WASM 仍拒绝
`std.process`；codec parity 成功不得描述为 browser subprocess support。

## 5. 被拒绝的替代方案

### 5.1 `Content-Length` header

所选稳定 MCP stdio specification 使用换行分隔 JSON-RPC message。实现旧 Language
Server Protocol framing 会增加第二个 parser、含糊的 mode selection 与不必要的
attack surface。未来非 MCP protocol 可以单独提案。

### 5.2 暴露 substring，让每个 application 自行 framing

通用 string slicing 以后可能仍有价值，但无法集中 JSON-RPC shape check、size
limit、CRLF policy 或 secret-safe diagnostic。

### 5.3 Runtime-owned mutable decoder handle

Handle 需要 registry、allocation limit、stale-handle check、显式 close，以及
native/WASM lifecycle parity。Decoder state 只有受限 string 与一个 limit，因此
opaque value 更简单，也符合 Nomo value semantics。

### 5.4 合并成 `McpClient`

这会过早冻结 MCP initialization、capability negotiation、method schema、request
correlation 与 server-version policy。本 RFC 先交付可复用 transport 与 JSON-RPC
层。

## 6. 验收门

只有完成以下全部项目，RFC 0028 才可改为 `Accepted`：

1. 双语 RFC、specification、标准库文档与 public source API 完全一致；
2. semantic test 证明 opaque value construction 与 field access 被拒绝；
3. unit test 覆盖四种 envelope、reserved-field duplicate、非法 id/params/error、
   extension、escaped newline、CRLF、空行、partial line、coalesced line、finish
   与每个 limit；
4. native 与 browser-WASM test 断言相同 result 与 error code；
5. 通过 `std.process` 启动本地无网络 fixture，故意 fragment/coalesce stdout、
   独立写 stderr、处理至少两个 id，并验证 exit status；
6. 一个 MCP-shaped Nomo example 完成 initialization 与后续一条 request，不使用
   应用 C FFI 或真实 API key；
7. Linux、macOS 与 Windows CI 通过；sanitizer 或等价 memory/lifecycle coverage
   覆盖重复 decoder replacement 与 message array；
8. 测试证明 diagnostic 不会回显 sentinel secret；
9. generated C 保持 C99-compatible；未 import `std.jsonrpc` 的程序不生成
   codec-specific support；
10. commit 有签名，通过 child branch 与 PR 合并，且同步后的本地 `main` worktree
    保持干净。

## 7. 参考资料

- [MCP 2025-06-18 transports](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)
- [RFC 0024：受控子进程与多路复用标准 I/O](./0024-controlled-child-processes-and-stdio.md)
- [RFC 0025：结构化 JSON Value、访问与构造](./0025-structured-json-values-and-construction.md)
