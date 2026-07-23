# RFC 0021：由 Manifest 派生模块根并映射依赖别名

> 语言 / Language: 中文 | [English](../../en/rfcs/0021-manifest-derived-module-roots.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0021 |
| 标题 | 由 Manifest 派生模块根并映射依赖别名 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-23 |
| 实现状态 | 尚未实现；本文固定迁移顺序与兼容边界 |
| 关联主题 | package declaration、module identity、dependency alias、manifest migration、LSP |
| 关联 RFC | [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0020](./0020-manifest-v2-workspace-and-project-configuration.md) |

## 1. 摘要

项目源码的模块根由自身 `nomo.toml` 的 `[package].name` 确定，而不是由
`src/main.nomo` 中任意选择的 `app` 占位符确定。`src/main.nomo` 声明
`package <root>`，其它模块声明 `package <root>.<path>`。

依赖 alias 只属于消费方 import。编译器把消费方 alias 映射到依赖包自身的模块根，
但不会要求依赖源码使用消费方选择的 alias。

## 2. 动机

当前示例通常写：

```nomo
package app.main
```

`app` 既不是 manifest package name，也不是 canonical package id。更严重的是，当前
模块加载器会把 dependency alias 当作依赖源码声明的一部分。若同一个
`nomo-lang/utils` 在两个项目中分别命名为 `utils` 与 `local_utils`，同一份源码不可能
同时声明两个不同的 package path。这与 RFC 0008 的“alias 只控制消费方 import”决议
冲突。

## 3. 名称派生

模块根通过确定性的 `lower_snake` 变换从 package name 派生：

- ASCII 大写字母转为小写，并在小写/数字到大写的边界插入 `_`；
- `-` 转为 `_`；
- 连续 `_` 折叠为一个；
- Manifest v2 仍优先要求 lowercase kebab package name，CamelCase 变换主要用于旧
  manifest 迁移。

示例：

| Manifest name | 模块根 |
| --- | --- |
| `hello` | `hello` |
| `hello-world` | `hello_world` |
| `HelloWorld`（legacy） | `hello_world` |

派生结果必须是合法 Nomo 标识符。无法得到合法标识符的 manifest 在项目发现阶段失败。

## 4. 文件到模块的映射

给定 `name = "hello-world"`：

| 文件 | 声明 |
| --- | --- |
| `src/main.nomo` | `package hello_world` |
| `src/math.nomo` | `package hello_world.math` |
| `src/http/client.nomo` | `package hello_world.http.client` |
| `src/http/main.nomo` | `package hello_world.http` |

入口文件不追加 `.main`。文件路径与 package declaration 不一致时继续使用稳定诊断
`E0904`，LSP 提供更新声明或重命名文件的 quick fix。

## 5. 依赖 alias 映射

依赖包：

```toml
[package]
namespace = "nomo-lang"
name = "utils"
```

其源码固定声明：

```nomo
package utils.path
```

消费方可以自由选择 alias：

```toml
[dependencies]
local_utils = { package = "nomo-lang/utils", version = "0.1.0" }
```

并写：

```nomo
import local_utils.path
```

解析器先把 `local_utils` 映射到 canonical package `nomo-lang/utils`，再校验被加载源码
声明的是 `utils.path`。编译器内部语义身份使用
`canonical package id + source module path`，因此两个不同 canonical package 即使拥有
相同 manifest name 也不会共享类型身份。

依赖 alias 不得与当前包模块根或保留根 `std` 冲突。

## 6. 迁移

实现按以下顺序落地：

1. 在 manifest crate 中提供唯一的 package-name-to-module-root 函数。
2. Module graph 显式携带 canonical package id、source module root 与 consumer alias，
   不再把三者表示成一个字符串。
3. CLI、compiler、LSP、doc 和 formatter 使用同一个文件到模块映射。
4. 增加 `nomo fix module-roots [path] [--check]`，原子更新 package declarations 与本包
   import。
5. 一个开发 snapshot 接受旧 `app.*` 并给出迁移诊断；下一个 snapshot 移除兼容。
6. 迁移标准库、示例、Playground、LSP fixtures 和编辑器文档。

迁移工具不得修改 dependency alias import，除非该 import 实际引用当前包的旧
`app.*` 根。

## 7. 备选方案

| 方案 | 结果 | 决议 |
| --- | --- | --- |
| 永久保留 `app` 根 | 多个 package 的源码身份不可读，manifest name 不参与模块契约 | 拒绝 |
| 源码使用 canonical `owner/package` | `/` 与模块语法冲突，组织迁移会污染所有源码 | 拒绝 |
| 源码使用消费方 alias | 同一包无法被不同 alias 复用 | 拒绝 |
| manifest 派生源码根 + consumer alias 映射 | 源码稳定、import 可本地命名、内部身份无歧义 | 提案 |

## 8. 风险

- 这是源码兼容性变更，需要机械迁移全部示例和测试 fixture。
- Module graph 必须区分显示路径与 canonical 身份，不能只做字符串替换。
- 两个依赖可具有相同 manifest name；它们必须通过不同 alias 导入，并在内部用
  canonical package id 区分。

## 9. 对 v0.1 的影响

该变更应在 v0.1 Preview 1 之前完成，但不要求立即发布 Preview 1。它修复既有 package
identity 决议与实现之间的矛盾，不增加新的语言表达能力。

## 10. 验收

- `nomo new hello-world` 生成 `package hello_world`。
- 主模块声明与 manifest name 不一致时产生 `E0904`。
- 同一依赖可在两个消费者中使用不同 alias，依赖源码不变化。
- 本包模块、依赖模块、workspace member 的 definition/rename 与文档链接保持正确。
- 迁移命令支持 `--check`、幂等、失败时不留下部分写入。

