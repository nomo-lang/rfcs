# RFC 0025：结构化 JSON Value、访问与构造

> 语言 / Language: 中文 | [English](../../en/rfcs/0025-structured-json-values-and-construction.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0025 |
| 标题 | 结构化 JSON Value、访问与构造 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-24 |
| 关联主题 | JSON、标准库、Agent、Unicode、limit、C backend、browser WASM |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0022](./0022-structured-http-client-and-host-runtime.md)、[RFC 0024](./0024-controlled-child-processes-and-stdio.md) |

---

## 1. 摘要

Nomo v0.1 应把 `std.json` 从 raw-text validator 扩展为受限的结构化 API，使应用
可以识别全部六种 JSON value kind、遍历嵌套 array/object、构造请求文档并安全
序列化，且无需应用侧 C FFI。

`JsonValue` 继续保持 opaque，并保存一段已验证的 JSON fragment。现有 `parse` 与
`stringify` 签名继续可用；成功解析的 document 在 stringify 时保留原始拼写与空白。
新增 accessor 与 constructor 作用于 opaque 表示，允许 runtime 以后增加 index 或
tree-backed storage，而不在 v0.1 冻结 public recursive layout。

首个结构化 API 刻意保持受限、同步，并明确 input size、nesting depth、value count、
Unicode、重复 object member、精确 number text、确定性 lookup、secret-safe error
及 native/browser parity。

## 2. 动机

HTTP 与 process slice 已提供原生 CLI Agent 所需 transport，但应用仍无法完成数据
闭环：

1. 构造嵌套的 OpenAI-compatible request object；
2. 序列化为 HTTP body；
3. 解析嵌套 response；
4. 取得 `choices[0].message.content`；
5. 为后续 MCP client 构造并消费 JSON-RPC message。

当前 `std.json` 只能证明 string 在语法上是 JSON，再返回原始文本。应用无法查询
value 是否为 object、取得 member、遍历 array、解码 string，也无法在不手工拼接、
转义 text 的情况下构造 JSON。对 prompt、tool result 与 model output 而言，手工
拼接尤其不安全。

这是可复用标准库能力缺口，不应通过增加 Agent-specific SDK 或把 JSON library 以
应用侧 FFI 暴露出来解决。

## 3. 当前证据与 Gap

| 表面 | 当前证据 | P1 缺口 |
| --- | --- | --- |
| Public type | Opaque `JsonValue { raw: string }` | 没有 kind、访问、遍历或构造 |
| Parsing | 递归 C 语法 validator | 没有 size/depth/value limit、UTF-8 validation、surrogate validation 或有效 error location |
| Serialization | `stringify` retain 并返回 `raw` | 没有安全 string escaping 或 object/array construction |
| Number | 验证 number grammar | 没有精确 lexeme access 或 numeric constructor |
| Object | 按源码顺序验证语法 | 没有 member enumeration、duplicate policy 或 lookup |
| Error | `JsonError { message }`，固定为 `"invalid json"` | 没有稳定 code/offset；实现无法区分 limit 与 syntax |
| Native runtime | 生成 C 扫描 NUL-terminated byte | `\u0000` 无法表示为 Nomo `string`；当前会接受 unpaired surrogate |
| Browser WASM | `JsonParse`/`JsonStringify` 落入 generic unsupported-operation error | Playground 无法执行纯 JSON 操作 |
| Test | 一个 compiler/CLI parse-stringify happy path | 没有嵌套 Agent payload、constructor、Unicode、duplicate、limit、lifecycle stress 或 C/WASM parity |

## 4. 详细设计

### 4.1 Public Nomo API

Canonical `std.json` 表面变为：

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

`JsonValue.raw` 保持 private。该类型代表已验证 value，因此 `kind` 与
`stringify` 不会失败。Value kind 不匹配时 accessor 返回 `None`；value 不是
object 或 member 不存在时，`get` 同样返回 `None`。

`array_items` 按 document order 返回 value；`object_members` 按 document order
返回每个 member。返回的 nested `JsonValue` 自己拥有或 retain 对应的已验证
fragment，在返回 array 被复制或释放后仍然有效。

API 与现有 v0.1 标准库保持一致，使用 free function，不给语言增加 indexing 或
dynamic field syntax。调用方在 `array_items` 后使用 `std.array.get`。

### 4.2 Opaque Raw Representation

解析 document 时 retain 已验证 raw text。因此 `stringify(parse(text)?)` 返回相同
text，包括无意义空白、escape 拼写、exponent 拼写、object order 与 duplicate
member。

Accessor 扫描已验证 fragment，并可分配 decoded string、member array、item array
或 nested raw fragment。第一个实现允许每次 accessor 为 O(n)。Public 表示保持
opaque，使后续 runtime 可以缓存 offset 或改为 tree，而无需修改源码。

Constructor 生成无无意义空白的 compact JSON。通过 public API 观察时，constructor
创建的 value 与 parsed value 没有差异。

### 4.3 Parsing Limit

每个 `JsonValue` 必须满足：

- UTF-8 JSON text 最大 8 MiB；
- array/object 最多嵌套 128 层，root container 的 depth 为 1；
- JSON value 总数最多 262,144，包括 root、每个 object member value 与 array
  item。

Limit 同时适用于 `parse` 与 aggregate constructor 的完整 output，并且必须在
unbounded allocation 或递归 C call 前检查。Native parser 必须使用显式、经过
检查的 depth counter，不能依赖 C stack 自然溢出。

Whitespace 只允许 JSON 的四个 byte：space、horizontal tab、line feed 与 carriage
return。尾部非 whitespace input 为 syntax error。

`offset` 是首次发现 parse failure 的 zero-based UTF-8 byte offset。End-of-input
error 使用 input byte length；aggregate constructor 的 limit failure 使用 `0`。

### 4.4 Unicode 与 Nomo String 兼容

未转义 JSON text 必须是合法 UTF-8。Escape decoding 接受标准 JSON escape。High
UTF-16 surrogate 后必须紧跟 low surrogate，并把这一对解码为一个 Unicode scalar；
unpaired surrogate 返回 `unsupported_string`。

v0.1 Nomo string runtime 采用 NUL-terminated 表示，不能保存嵌入的 U+0000。因此
`parse` 对包含 escaped `\u0000` 的 JSON string 或 object name 返回
`unsupported_string`。该限制在生成 `JsonValue` 前生效，保证 `as_string`、
`object_members` 与 `get` 永不静默截断数据。

`from_string` 与 object member key 接受 Nomo string 能表示的任意 value。序列化会
转义 quotation mark、reverse solidus 与 control character；其它 Unicode scalar
输出合法 UTF-8。后续 length-carrying Nomo string 表示可以在不修改 JSON API 的
情况下移除 U+0000 限制。

### 4.5 Kind 与 Scalar Access

`kind` 恰好返回六种 JSON kind 之一。`is_null` 是
`kind(value) == JsonKind.Null` 的 convenience。

`as_bool` 返回表示的 boolean。`as_string` 返回 decoded Nomo string，而非带 quote
的 JSON token。`number_text` 返回精确的已验证 number lexeme，保留 sign、
fractional digit、exponent 大小写与 exponent sign。

首个 API 不在 JSON kind 之间做 coercion。JSON string `"1"` 不是 number，JSON
number `1` 也不是 string。需要 machine numeric value 时，调用方可把
`number_text` 传给 `std.num.parse_i64`、`parse_u64` 或 `parse_f64`。

### 4.6 Object Order、Duplicate 与 Lookup

Parse 与 `object_members` 保持 source member order，`from_object` 保持输入 array
order。Duplicate name 被接受，因为 JSON syntax 允许，且现有 `parse` 已经接受。

`get` 采用确定性的 last-member-wins lookup。这与常见 JSON consumer 行为一致；
需要检测或拒绝 duplicate 的调用方仍可通过 `object_members` 观察全部 entry。
Serialization 永不静默 deduplicate member。

Object name 在 JSON escape decoding 后比较，所以 `"name"` 与 `"\u006eame"` 指向
同一个 lookup key。

### 4.7 构造与 Number

`from_null`、`from_bool`、`from_i64` 与 `from_u64` 不可能违反 JSON limit，直接
返回。

`from_number_text` 只接受一个 JSON number token，且不允许周围 whitespace。它
精确保留 token；leading zero、缺失 integer/fraction/exponent digit、non-finite
拼写或 trailing data 返回 `invalid_number`。

`from_string`、`from_array` 与 `from_object` 的 compact serialized output 超过
8 MiB、depth 128 或 262,144 values 时返回 `limit`。分配前计算 size 时必须检测
integer overflow。

本 RFC 刻意不加入 `from_f64`。Native C 与 browser JavaScript/Rust formatting
当前没有共同指定的 shortest-round-trip decimal algorithm。v0.1 调用方使用
`from_number_text` 表示精确 decimal value。后续提案可以增加 deterministic finite
floating-point construction，而无需修改本 API。

### 4.8 Error 与 Secret Handling

`JsonError.code` 为：

- `syntax`：malformed JSON document；
- `limit`：超过 input、output、depth 或 value-count limit；
- `unsupported_string`：U+0000、unpaired surrogate 或 invalid UTF-8；
- `invalid_number`：`from_number_text` 的 input 非法。

`message` 是适合 user-facing diagnostic 的稳定通用说明，可以描述预期 token
category；但它和默认 compiler/runtime log 都不得包含 source snippet、object
name、string value、number text、prompt、response body、token 或 header。
`offset` 是唯一 input-specific parse detail。

该规则避免 malformed model response 或含 secret 的 request 被复制到 diagnostic。

### 4.9 Compiler、Native C 与 Browser WASM

Canonical declaration 继续位于 `std/src/json.nomo`。Compiler lowering 为每个
public function 使用 typed JSON IR operation。生成 C runtime 负责 validation、
scanning、decoding、escaping、checked sizing 与 lifecycle。Nomo 应用无需声明 FFI
source 或 linker metadata。

Native 实现不得调用 system JSON library。这是为了 portability 的实现选择，并不
意味着工具链内部完全禁止 native/system facility。

Browser WASM 把本 RFC 的全部操作实现为 pure computation，不得报告
filesystem/network/process capability error。其可观察的 kind、raw round trip、
limit、error、offset、order、duplicate lookup、Unicode decoding 与 compact
constructor output 必须与 native C backend 一致。

无需给 browser interpreter 增加通用 public dynamic-value 表示。只要 nominal type
与 lifecycle 行为正确，internal raw JSON value 可以继续使用现有 runtime `Struct`
carrier。

### 4.10 兼容性与迁移

以下行为保持兼容：

- `parse(string) -> Result<JsonValue, JsonError>`；
- `stringify(JsonValue) -> string`；
- 新 limit 内每个合法 document 的 byte-exact raw round trip；
- opaque `JsonValue` construction。

两个 preview-stage tightening 是刻意的：

1. 超出新 bounds、invalid UTF-8、unpaired surrogate 与 `\u0000` 会被拒绝，不再
   被旧 syntax-only validator 接受；
2. `JsonError` 增加 `code` 与 `offset`，所以直接构造 `JsonError` literal 的外部
   代码必须补充这两个 field。

读取 `error.message` 与匹配 `Ok`/`Err` 保持源码兼容。构造 error 的迁移是机械式
修改，而且标准库 error 本就不应作为应用 domain-error constructor。

## 5. 备选方案

| 方案 | 优点 | 缺点 | 倾向 |
| --- | --- | --- | --- |
| Opaque validated fragment + accessor/constructor | 保留 raw round trip；表示稳定；可增量实现 | 重复访问可能重复扫描 | 提案 |
| Public recursive `JsonValue` enum | Pattern matching 与直接构造自然 | 冻结 number/object 表示，丢失精确 raw 拼写，扩大 layout/lifecycle ABI | v0.1 拒绝 |
| 只提供 string helper | Compiler 改动小 | 重复 parse、构造不安全、无 typed lifecycle | 拒绝 |
| 应用侧 C JSON library | 已有成熟实现 | 每个 Agent 都要负责 FFI、allocation、linking 与跨平台 policy | 拒绝 |
| 拒绝 duplicate object name | 数据模型更强 | 破坏既有 input 与部分外部 API | 拒绝；暴露全部并使用 last-match lookup |
| 把所有 number 转为 `f64` | Runtime value 简单 | 丢失大整数与精确 decimal | 拒绝 |
| 使用 platform formatting 增加 `from_f64` | 方便 | Native/browser output 与 round trip 未定义 | 推迟 |
| 立即把全部 Nomo string 改为 length-carrying | 可以表示 U+0000 | 横切 runtime 与所有 host API | 推迟 |

## 6. 缺点与风险

- Opaque fragment access 对 deeply nested workflow 可能重复扫描。
- 返回所有 member/item 会按选中 container 大小分配 array，但 document 与
  value-count bound 限制了成本。
- U+0000 限制比不受限 JSON 更窄。
- Last-member-wins lookup 会隐藏 duplicate，除非调用方主动枚举。
- 扩展 `JsonError` 对直接 struct literal 是小型 preview-stage source break。
- 生成 C 与 browser Rust 必须依靠共享 fixture 维持相同 parser semantic，不能只
  依赖两个 library default。

## 7. 对 v0.1 范围的影响

本 RFC 补齐 non-streaming 原生 CLI Agent loop 中可复用的 JSON 部分。结合 RFC
0022，Nomo 代码可以构造 OpenAI-compatible request、通过 HTTPS 发送，并检查嵌套
response；结合 RFC 0024，它提供后续 JSON-RPC/MCP framing 需要的 value model。

本 RFC 不实现 OpenAI SDK、Agent product、schema derivation、reflection、
serde-like trait、JSONPath、自动 struct mapping、streaming JSON parser、mutable
in-place JSON tree 或 JSON-RPC protocol semantic。

## 8. Acceptance Gate

本 RFC 在以下全部 gate 通过后被接受：

1. Canonical `std.json` source、standard-module registry、compiler lowering、
   typed IR、生成 C ABI、browser WASM、文档与两份 v0.1 specification 暴露一致
   API 与语义。
2. 现有 parse/stringify 代码保持源码兼容，bounds 内合法 document 保持
   byte-exact raw round trip。
3. Nomo 示例在不拼接 string、不使用应用侧 FFI 的情况下构造嵌套
   OpenAI-compatible non-streaming request，并从 fixture response 提取
   `choices[0].message.content`。
4. 测试覆盖 null、boolean、number、string、array、object、wrong-kind access、
   missing member、empty container 与 nested traversal。
5. 测试覆盖 quote、reverse solidus、control、BMP Unicode、合法 surrogate pair
   与 non-ASCII UTF-8 的安全构造和 escaping。
6. 测试覆盖 invalid UTF-8、unpaired surrogate、U+0000、精确 number lexeme、
   非法 number form、`i64`/`u64` boundary 与 constructor overflow。
7. 测试证明 source-order preservation、duplicate preservation、decoded-name
   comparison 与确定性 last-member-wins `get`。
8. Boundary test 覆盖恰好 8 MiB 与多一 byte、depth 128 与 129、262,144 values
   与多一个 value，且不会 stack overflow 或 unbounded allocation。
9. 嵌入 malformed string、member name、number text 与 nested value 的 secret
   sentinel 永不出现在 error、diagnostic 或默认 log。
10. Lifecycle stress 在 AddressSanitizer 或等价 native leak/use-after-free gate 下
    重复 parse、traverse、copy、construct 与 release nested value。
11. 相同 conformance fixture corpus 通过 native Linux、native macOS、native
    Windows 与 browser WASM；capability-denial test 证明 JSON 在 sandbox 中可用。
12. Formatting、Clippy、unit/CLI integration、release、WASM、cross-build 与
    platform smoke check 在签名 implementation PR 与 post-merge `main` 上通过。
13. 实现从签名 child branch 经 reviewed PR 合入；status 改为 `Accepted` 前，把
    acceptance evidence 与 link 记录到本 RFC。

## 9. 验收证据

- 实现通过已签名提交
  [`7f3d2c9`](https://github.com/nomo-lang/nomo/commit/7f3d2c905d5a66ea18660a28e9888a68066b83cf)
  和 [`c47af0e`](https://github.com/nomo-lang/nomo/commit/c47af0e6018e97187a08e09ac5e5ec7dda2d2b3d)
  在经 review 的 [nomo PR #14](https://github.com/nomo-lang/nomo/pull/14)
  合入，merge commit 为
  [`fde7016`](https://github.com/nomo-lang/nomo/commit/fde701629fbb6d0d4eebf879c96083fd7cebff94)。
- 最终 [PR smoke run](https://github.com/nomo-lang/nomo/actions/runs/30112910817)
  通过 Linux smoke 与 AddressSanitizer/LeakSanitizer、Windows native host
  runtime check 及 macOS structured JSON runtime。
- 合并后的 [`main` CI run](https://github.com/nomo-lang/nomo/actions/runs/30113047313)
  通过 formatting、Clippy、完整 workspace test suite、release 与 browser WASM
  build、sandbox verification、compiler latency gate、example、workspace check，
  以及真实 Linux x86_64→arm64 和 macOS arm64→x86_64 cross-build。
- Native 与 browser runtime 运行共享的
  `tests/fixtures/structured_json_conformance.nomo` corpus；boundary、
  invalid-UTF-8、lifecycle、secret-safety 与 OpenAI-compatible example test
  覆盖 gate 2 到 11。
- 本次接受更新把两份 v0.1 specification 与 RFC index 同步到已交付 API 和
  已记录的 CI 证据。

## 10. 推迟的后续工作

- Deterministic `from_f64` conversion。
- Incremental/streaming parser 与 byte-buffer input type。
- Length-carrying Nomo string 与 U+0000 support。
- Typed struct/enum derivation 与 schema validation。
- `JsonValue` 背后的 cached index 或 tree-backed optimization。
- JSON Pointer、JSON Patch、JSONPath 与 mutable update operation。
- 建立在本 value API 上的 JSON-RPC 与 MCP message framing。

## 11. 参考

- [RFC 8259：JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259)
- `std/src/json.nomo`
- `crates/nomo_compiler/src/builtins/builtins_extensions.rs`
- `crates/nomo_ir/src/lib.rs`
- `crates/nomo_codegen_c/src/runtime/host_json_helpers.rs`
- `crates/nomo_wasm/src/interpreter.rs`
- `crates/nomo/tests/cli_project.rs`
