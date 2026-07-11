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
| 实现状态 | 第一至三切片已落地：intrinsic 清单与经过校验的 `Option`/`Result`、`Array`、`string` source contract 已存在；表示相关 ABI 仍由编译器/runtime 提供 |
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
