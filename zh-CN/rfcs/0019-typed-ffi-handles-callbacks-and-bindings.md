# RFC 0019：类型化 FFI Handle、Callback 与 Binding

> 语言 / Language: 中文 | [English](../../en/rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0019 |
| 标题 | 类型化 FFI Handle、Callback 与 Binding |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已实现：nominal handle、显式 nullability 与 ownership metadata、受限 callback、target-aware `repr(C)` layout、确定性 header binding、provenance 和真实 C 集成测试均已落地 |
| 关联主题 | FFI、opaque handle、nullable pointer、callback、C layout、binding generation |
| 关联 RFC | [RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md) |

---

## 1. 摘要

在 RFC 0011 的最小 C 边界上增加不互换的类型化 opaque handle、显式 nullable 值、受限 `extern "C"` callback 和经过 target 校验的 C struct/header binding。所有权与线程规则必须在声明处可见，安全 wrapper 仍由库作者显式编写。

## 2. 动机

通用 `Opaque` 足以调用简单 C API，却无法阻止不同 handle 混用，也不能表达 null、callback lifetime 或 struct ABI。直接开放任意 pointer 操作会绕过 Nomo 当前可检查的安全边界。

## 3. 提议设计

- `extern opaque type FileHandle release file_close` 创建 nominal、不可构造、不可互换且带显式 release contract 的 handle。`Owned<FileHandle>` 与 `Borrowed<FileHandle>` 表达 transfer/borrow 边界，`.borrow()` 是唯一的隐式 view 操作。
- nullable C pointer 使用 `Nullable<Handle>`，也可包装 owned/borrowed handle。`is_null()` 用于判断，`unwrap()` 是显式 checked conversion；null 不会隐式成为普通 handle。
- callback 只允许 `extern "C" fn(...) -> ...` ABI-safe 参数。首版仅接受签名精确匹配的非捕获 top-level function，并拒绝 callback 存储、返回或其他逃逸。callback panic 使用 fail-fast 路径，不会跨 C 边界 unwind。
- `#[repr(C)]` 数据结构只允许固定布局字段，并由目标 ABI 表验证 size/alignment；bitfield、union、flexible array 首版拒绝。
- `nomo ffi bindgen <header> --package <package> --output <file>` 读取受控 C header 子集，产出普通 Nomo source 与确定性 provenance 文件；生成源码可审查，签入 package 后会进入 checksum。
- dereference、ownership transfer 与 callback registration 继续要求 `unsafe`，安全 wrapper 不自动生成。

## 4. 实现切片

1. nominal handle、nullability、ownership metadata、release-contract 校验和错误 handle diagnostics 已实现。
2. exact-signature top-level callback ABI、逃逸拒绝、fail-fast panic containment 与真实 callback 执行已实现。捕获/context trampoline 和 retained callback 明确不属于本次接受范围。
3. `repr(C)` layout engine 与 Linux GNU/Windows MSVC x86-64 ABI fixtures 已实现。
4. 受控 header parser、确定性 generator、SHA-256 provenance、核心 CLI 命令与生成 binding 的 C link/run 集成已实现。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 所有对象继续使用 `Opaque` | 类型混用只能在运行时发现 | 不足 |
| 开放 C 风格任意 pointer | 破坏当前所有权与安全检查边界 | 拒绝 |
| 分阶段类型化 FFI | 提升表达力且保持 unsafe 可见 | 接受 |

## 6. 缺点与风险

callback lifetime 与 foreign-thread runtime entry 极易产生 use-after-free，因此本次接受范围拒绝 retained callback 与 foreign-thread entry。C ABI 在 targets 间变化；generator 会显式拒绝 union、bitfield、array、flexible array、variadic、多级 pointer 和未知 scalar spelling，不声称支持完整 C。

## 7. 兼容与迁移

现有 `Opaque` API 保持有效但可获得 lint，引导库作者逐步换成 nominal handle。生成 binding 是源码，不引入隐式构建时执行。

## 8. 接受门槛

已满足。compiler tests 会拒绝错误 handle 混用、非法 null 使用与 callback 逃逸；layout fixtures 覆盖 `x86_64-unknown-linux-gnu` 和 `x86_64-pc-windows-msvc`；`ffi_typed_handle` 会执行真实 C callback；CLI suite 会从 header 生成 binding，并与 C 一起编译、链接和运行。

## 9. 未决问题

- 完整线性所有权与自动析构留待后续；当前切片校验 ownership metadata 与 release signature，使用显式 `close` 和可选 `defer`。
- 当前 callback 不允许 retained，也不允许从 foreign thread 进入。未来 RFC 必须先定义 runtime attachment、lifetime 与同步规则。
- binding generator 已作为 `nomo ffi bindgen` 进入核心 CLI，不引入隐式 build-time execution。

## 10. 参考

- [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)。
