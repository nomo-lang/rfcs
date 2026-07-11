# RFC 0010：受约束泛型与 Interface 静态分派

> 语言 / Language: 中文 | [English](../../en/rfcs/0010-constrained-generics-and-static-interface-dispatch.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0010 |
| 标题 | 受约束泛型与 Interface 静态分派 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：interface/impl 校验、单 bound 泛型、显式 concrete type argument、函数体约束检查、单态化与静态方法分派均有 parser/compiler/codegen/LSP 测试 |
| 关联主题 | interface、generics、monomorphization、static dispatch、semantic owner |
| 关联 RFC | [RFC 0005](./0005-newline-sensitivity-and-dot-resolution.md)、[RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md) |

---

## 1. 摘要

v0.1 支持最小 interface 约束：每个 type parameter 最多一个 `T: Interface` bound；调用必须给出显式 concrete type argument；编译器只允许泛型函数体调用 bound 提供的操作，验证 concrete struct 的匹配 impl 后单态化并静态分派。

## 2. 动机

无约束泛型无法安全表达“某个 T 必须提供方法”，而完整 trait 系统会引入多 bound、where、associated type、动态分派和复杂一致性规则。v0.1 需要一个可检查、可生成 C 且不扩大到完整 trait 系统的中间点。

## 3. 语法

```rust
pub interface Display {
    fn to_string(self) -> string
}

fn render<T: Display>(value: T) -> string {
    return value.to_string()
}

let text: string = render<User>(user)
```

## 4. 语义

- interface impl 必须提供全部方法，并匹配 type parameter、参数数量、mutability、参数类型和返回类型。
- bound 函数体中的方法解析到 interface 声明，而不是任意 concrete impl。
- concrete 调用必须是 non-generic struct，并存在匹配 impl；当前不做 type argument 推断。
- codegen 单态化泛型函数，方法调用静态分派，不生成 vtable 或 trait object。

## 5. 备选方案

| 方案 | 问题 | 决议 |
| --- | --- | --- |
| 无 bound 泛型 | 无法安全调用类型相关行为 | 不足 |
| 完整 trait 系统 | 语义与实现范围过大 | 推迟 |
| 单 interface bound + 静态分派 | 可检查、可单态化、与 C 后端契合 | 接受 |

## 6. 缺点与风险

- 显式 concrete type argument 较啰嗦。
- 仅支持一个 bound，无法表达组合能力。
- impl 一致性当前只覆盖 v0.1 package/module 可见范围。

## 7. 对 v0.1 范围的影响

不支持多个 bound、`where`、associated type、blanket impl、trait object、动态分派、特化或高阶类型。formatter、doc、LSP signature 与导航必须保留并理解 bound。

## 8. 决议

接受单 interface bound、显式 concrete type argument、单态化和静态分派作为当前抽象边界。

## 9. 后续问题

- type argument 推断和多个 bound。
- orphan/coherence 规则的跨包稳定形式。
- associated type 或动态分派是否值得进入独立 RFC。

## 10. 参考

- constrained generic parser、interface validation、monomorphized codegen 与 semantic owner 测试。
- [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md)。
