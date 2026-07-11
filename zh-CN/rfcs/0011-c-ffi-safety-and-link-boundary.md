# RFC 0011：C FFI 的安全、所有权与链接边界

> 语言 / Language: 中文 | [English](../../en/rfcs/0011-c-ffi-safety-and-link-boundary.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0011 |
| 标题 | C FFI 的安全、所有权与链接边界 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：`extern "C"`、调用时 `unsafe`、primitive/CString/Opaque 映射、manifest linker metadata、package-relative C source、checksum/publish/vendor 聚合均有测试 |
| 关联主题 | FFI、unsafe、CString、Opaque、linker metadata、native source |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md) |

---

## 1. 摘要

Nomo 的 C FFI 把“不安全性”放在调用点：`extern "C"` 只声明签名，真正调用必须位于 `unsafe` block。跨边界字符串使用 owned `CString`，未知 foreign handle 使用不可解引用的 `Opaque`；native linker 信息由 package manifest 声明并随依赖图聚合。

## 2. 动机

直接把 Nomo `string` 或任意指针暴露给 C 会混淆 NUL 终止、生命周期、释放责任和别名规则。只在 declaration 上标记 unsafe 又会隐藏真正发生风险的调用位置。

## 3. 类型边界

- primitive integer、float、bool、char 和 `void` 直接映射到受支持的 C ABI 类型。
- `CString.from_string` 创建 owned NUL-terminated copy，作为参数映射到 `const char *`；C 不直接返回 `CString`，因为 ownership 未知。
- `Opaque` 映射到 `void *`，可由 extern 返回、保存并传回 extern，但不能解引用、比较或参与运算。
- C struct 自动布局、裸指针运算和 header binding generation 不属于当前范围。

## 4. 调用与链接

```rust
import std.ffi

extern "C" { fn puts(message: CString) -> i32 }

let message: CString = CString.from_string("hello")
unsafe { puts(message) }
```

`[ffi]` 支持 `libraries`、`library_paths`、`sources`、`frameworks` 和 `link_args`。相对路径按声明 package root 解析；root 与 source dependency 的 metadata 在 build/test 时聚合。standalone script 不读取 manifest，因此不使用这些链接参数。

## 5. 备选方案

| 方案 | 问题 | 决议 |
| --- | --- | --- |
| 隐式 `string -> char *` | ownership 与 NUL 语义不清 | 拒绝 |
| declaration-only unsafe | 调用点风险不可见 | 拒绝 |
| 显式 CString/Opaque + call-site unsafe | 边界清晰、可静态检查 | 接受 |

## 6. 缺点与风险

- `link_args` 是 raw escape hatch，可能破坏可移植性。
- `Opaque` 无法表达细粒度 handle 类型，误配仍由 foreign API 负责。
- ABI 兼容最终仍依赖目标平台 C compiler 和 library。

## 7. 对 v0.1 范围的影响

FFI source 必须进入 package checksum、archive 和 vendor；依赖包的 linker metadata 也参与最终链接。诊断使用 E1500-E1599 范围。

## 8. 决议

接受 call-site `unsafe`、显式 `CString`/`Opaque` 和 manifest-owned native link metadata 作为 v0.1 C 边界。

## 9. 后续问题

- typed opaque handle、nullable pointer 和 callback ABI。
- C struct layout、header import 与 binding generation。
- target-specific linker metadata 与交叉编译。

## 10. 参考

- FFI parser/compiler/codegen tests、`ffi_puts`/native source 示例和 manifest link tests。
- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)。
