# RFC 0019：类型化 FFI Handle、Callback 与 Binding

> 语言 / Language: 中文 | [English](../../en/rfcs/0019-typed-ffi-handles-callbacks-and-bindings.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0019 |
| 标题 | 类型化 FFI Handle、Callback 与 Binding |
| 状态 | Proposed（已提案） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 未实现；当前边界只有通用 `Opaque`、`CString`、extern function 与 call-site `unsafe` |
| 关联主题 | FFI、opaque handle、nullable pointer、callback、C layout、binding generation |
| 关联 RFC | [RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md) |

---

## 1. 摘要

在 RFC 0011 的最小 C 边界上增加不互换的类型化 opaque handle、显式 nullable 值、受限 `extern "C"` callback 和经过 target 校验的 C struct/header binding。所有权与线程规则必须在声明处可见，安全 wrapper 仍由库作者显式编写。

## 2. 动机

通用 `Opaque` 足以调用简单 C API，却无法阻止不同 handle 混用，也不能表达 null、callback lifetime 或 struct ABI。直接开放任意 pointer 操作会绕过 Nomo 当前可检查的安全边界。

## 3. 提议设计

- `extern opaque type FileHandle` 创建 nominal、不可构造、不可互换的 handle；函数签名可标注 borrowed/owned return 与 release function。
- nullable C pointer 映射为 `Option<Handle>` 或专用 nullable scalar，不把 null 隐式转换为普通 handle。
- callback 只允许 `extern "C" fn(...) -> ...` ABI-safe 参数；捕获闭包不直接穿越边界，context pointer 必须与显式 trampoline/释放协议配对。
- `#[repr(C)]` 数据结构只允许固定布局字段，并由目标 ABI 表验证 size/alignment；bitfield、union、flexible array 首版拒绝。
- binding generator 读取受控 C header 子集，产出普通 Nomo source + provenance 文件；生成结果可审查并进入 package checksum。
- dereference、ownership transfer 与 callback registration 继续要求 `unsafe`，安全 wrapper 不自动生成。

## 4. 实现切片

1. nominal handle、nullability、ownership metadata 与 type-check diagnostics。
2. callback ABI、trampoline、panic/error containment 与 lifetime tests。
3. `repr(C)` layout engine 和跨 target ABI fixtures。
4. header subset parser、deterministic generator、provenance 与真实库集成测试。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 所有对象继续使用 `Opaque` | 类型混用只能在运行时发现 | 不足 |
| 开放 C 风格任意 pointer | 破坏当前所有权与安全检查边界 | 拒绝 |
| 分阶段类型化 FFI | 提升表达力且保持 unsafe 可见 | 提议 |

## 6. 缺点与风险

callback lifetime 与线程进入 runtime 极易产生 use-after-free；C ABI 在 targets 间变化，generator 不能声称支持完整 C。

## 7. 兼容与迁移

现有 `Opaque` API 保持有效但可获得 lint，引导库作者逐步换成 nominal handle。生成 binding 是源码，不引入隐式构建时执行。

## 8. 接受门槛

错误 handle 混用/null/callback 逃逸能被拒绝，至少两个 targets 的 layout fixtures 通过，并有一套 callback 与一套 header-generated 真实集成测试后才能 `Accepted`。

## 9. 未决问题

- owned handle 是否需要语言级析构协议，还是继续显式 `close` + `defer`。
- callback 是否允许从外部线程进入 Nomo runtime。
- binding generator 属于核心 CLI 还是独立工具。

## 10. 参考

- [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)。
