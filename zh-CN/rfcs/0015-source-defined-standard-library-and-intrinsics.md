# RFC 0015：标准库源码化与受控 Intrinsic 身份

> 语言 / Language: 中文 | [English](../../en/rfcs/0015-source-defined-standard-library-and-intrinsics.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0015 |
| 标题 | 标准库源码化与受控 Intrinsic 身份 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 第一至八切片已落地：intrinsic 清单、经过校验的 source contract、核心、扩展、网络、HTTP 与 FFI 源码 API、源码驱动的 doc/LSP 导航与发行包已存在；表示相关 ABI 仍由编译器/runtime 提供 |
| 关联主题 | standard library、intrinsic、lang item、bootstrap、ABI |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0006](./0006-option-result-lang-items.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md) |

---

## 1. 摘要

把可用 Nomo 表达的标准库 API 与实现迁移到版本化的 `nomo-lang/std` 源码包；编译器只保留不能由普通语言表达的最小 intrinsic 集合。特殊身份由工具链内置、带版本的清单绑定到 canonical declaration，不开放用户自定义 `#[lang]`。

## 2. 动机

当前公共模块稳定，但 `Option`、`Result`、`string`、`Array` 的关键事实分散在编译器与 runtime。源码化能让标准库参与 doc、LSP、package checksum 与普通测试，同时必须避免自举循环和伪造 lang item。

## 3. 提议设计

- 工具链携带已锁定的 `nomo-lang/std` source package，并作为特殊只读依赖解析。
- `Option`/`Result` 的声明与可表达方法迁入 Nomo 源码；layout、`?`、ARC/COW 与底层 IO 等保留为受控 intrinsic。
- 内置 `intrinsics.toml` 以 canonical package/module/declaration + schema version 绑定身份；用户 manifest 不能覆盖。
- 编译器在 bootstrap 时验证必需声明、泛型形状、变体和 ABI，缺失或重复立即报工具链错误。
- 现有 `std.*` import、诊断码及生成 C ABI 在迁移阶段保持兼容。

## 4. 实现切片

1. intrinsic 清单 schema、加载器与一致性诊断。
2. `Option`/`Result` 声明和纯 Nomo 方法迁移，双实现对照测试。
3. `string`/`Array` 公共表面迁移并冻结 runtime ABI。
4. doc/LSP/source navigation、发行包和 bootstrap 验收。

### 4.1 第一切片：intrinsic 清单

第一切片新增 `std/intrinsics.toml`，记录 schema version、canonical package 身份、源码
模块映射、binding kind、ABI 标签和必需身份。`nomo-std` 暴露解析器与校验器；compiler
lowering 和 `nomo doc --std` 会调用校验。重复 binding、未知模块、源码映射漂移、不支持的
kind，以及缺失 `Option`/`Result`/`?` 必需身份都会报告稳定的 `E0800`。本切片尚未迁移
carrier 声明或 runtime lowering。

### 4.2 第二切片：carrier source contract

`std/src/option.nomo` 与 `std/src/result.nomo` 现在定义 canonical enum 形状及纯
`is_some`/`is_none`/`is_ok`/`is_err`/`unwrap_or` helper。toolchain 会把它们作为 library
module 解析并 type-check；compiler 测试将 source 形状与普通项目使用的兼容 carrier 注入
进行对照。由于当前语言还没有 function-value type，`map`、`map_err`、`and_then` 继续由
intrinsic 提供。

### 4.3 第三切片：`Array` 与 `string` source surface

`std/src/array.nomo` 与 `std/src/string.nomo` 现在声明完整的 v0.1 public
helper surface。其 body 将表示相关操作委托给现有 compiler lowering，因此迁移期间
source signature 与生成 C 行为保持一致。intrinsic 清单要求 canonical `Array` 与
`string` layout binding，并固定当前 ABI label：`array-header` 使用带类型的
`len`/`cap`/`data` 存储、非原子引用计数和写入时 COW；`string-header` 使用不可变
`data` 与非原子引用计数 ownership。source parse、type-check、manifest identity 与
标准库文档都覆盖这一契约。

### 4.4 第四切片：源码驱动工具链与发行包

compiler semantic query、`nomo doc --std` 与 `nomo-lsp` 现在读取 canonical
`std/src/*.nomo`，为 public signature、文档、hover、workspace symbol 与
definition 提供真实源码位置。迁移期间 `Array` 仍是 compiler-owned special
type，因此它的导航符号锚定到源码，但表示仍由 runtime ABI 提供。compiler 与
LSP 的发行包都会携带标准库源码；安装后的 binary 优先读取
`NOMO_STD_SOURCE_ROOT`，否则探测发行包旁边的 `std/src`。bootstrap 验收覆盖
源码解析、manifest identity、semantic query、文档输出与发行包目录布局。

### 4.5 第五切片：核心标准库源码 API surface

`std.io`、`std.fs`、`std.path`、`std.env`、`std.process`、`std.time`、
`std.num`、`std.math`、`std.char` 与 `std.os` 的 canonical source file 现在
声明 public struct、function、signature 与 doc comment。toolchain 会校验每个
source package declaration，并将其 public top-level name 与标准 import registry
对照。主机相关行为继续通过现有 compiler/runtime builtin 实现 lower，在保持
当前行为的同时让 source 成为 public documentation 与 semantic surface。数值
重载式行为仍是 compiler intrinsic boundary，等 constrained generic interface
可以直接表达后再进一步迁移。

### 4.6 第六切片：扩展标准库源码 API surface

source package 现在也声明 `std.collections`、`std.hash`、`std.crypto`、
`std.json`、`std.regex`、`std.debug`、`std.log` 与 `std.testing`。public
struct、function、contextual `debug.panic` 及文档都会从 source 解析，并与
import registry 对照校验；主机/runtime 行为继续使用现有 builtin lowering。
由于 `panic` 同时是表达式关键字和标准库必须提供的 API 名称，parser 允许
它作为 contextual function declaration name。

### 4.7 第七切片：网络与 HTTP 源码 API surface

source package 现在也声明 `std.net` 与 `std.http`。网络错误、响应、数据报、
opaque handle 类型以及阻塞式 client/server 函数都会与标准 import registry
对照校验；TCP、UDP、HTTP handle 的 source-level method 或 close helper 与现有
builtin lowering 保持一致。socket、HTTP parsing 与主机错误仍由 runtime 负责，
这些 source file 定义 public signature 与文档。调用方可以把 `defer` 与 postfix
`?` 组合，在正常返回和 propagation 路径上都关闭 exchange、server 及其他 handle。

### 4.8 第八切片：FFI source contract

`std/src/ffi.nomo` 现在声明 public `CString` 与 `Opaque` source surface，并记录
`CString.from_string`。compiler 仍负责二者的特殊 value representation、C ABI
lowering、ownership 检查，以及 foreign return 和 pointer operation 的限制。因此
这份 source contract 是 semantic/documentation anchor，不替代 compiler FFI 实现。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 永久编译器注入全部标准类型 | 难以由普通工具查看、测试和版本化 | 拒绝 |
| 开放通用 `#[lang]` | 第三方可伪造编译器特殊身份 | 拒绝 |
| 工具链清单 + 源码声明 | 可审计且控制自举边界 | 提议 |

## 6. 缺点与风险

迁移触及 parser/type checker/codegen/runtime/doc/LSP 的共同身份；清单与源码漂移可能使工具链无法启动。

## 7. 兼容与迁移

分阶段保留当前编译器 carrier 作为对照路径，直到同一测试矩阵同时通过；不在一次变更中重写公共 API 与底层表示。

## 8. 接受门槛

至少 `Option`/`Result` 已由 Nomo 源码定义，intrinsic 验证、ABI 对照、doc/LSP 导航及打包测试均通过后，RFC 才能转为 `Accepted`。

## 9. 未决问题

- 清单由编译器版本固定，还是由 toolchain manifest 固定。
- 哪些 runtime 操作必须长期保持 intrinsic。
- 标准库能否独立于编译器发布补丁版本。

## 10. 参考

- [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0006](./0006-option-result-lang-items.md)。
