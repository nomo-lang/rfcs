# RFC 0021：由 Manifest 派生模块根并映射依赖别名

> 语言 / Language: 中文 | [English](../../en/rfcs/0021-manifest-derived-module-roots.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0021 |
| 标题 | 由 Manifest 派生模块根并映射依赖别名 |
| 决策状态 | Proposed（已提案） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-23 |
| 实现状态 | Not implemented（尚未实现） |
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

模块根只从 `[package].name` 进行确定性的 `lower_snake_case` 变换。
package `namespace`、canonical `owner/package` identity 与所有消费方选择的
dependency alias 都不参与结果。

对于已经通过 Manifest v2 校验的 package name，变换规则为：

1. 把 `-` 转为 `_`；
2. ASCII 大写字母的前一字符为小写/数字时，或连续大写之后紧跟小写时，在该大写字母
   前插入 `_`；
3. ASCII 大写字母转为小写；
4. 连续 `_` 折叠为一个；
5. 校验结果是单个、非保留的 Nomo 标识符。

Manifest v2 仍优先要求 lowercase kebab name。CamelCase 处理只是确定性迁移行为，
不是扩大 manifest grammar。

示例：

| Manifest name | 模块根 |
| --- | --- |
| `hello` | `hello` |
| `hello-world` | `hello_world` |
| `HelloWorld`（legacy） | `hello_world` |
| `HTTPServer`（legacy） | `http_server` |

无法得到合法标识符的 manifest 必须在加载源码前失败。

## 4. 文件到模块的映射

给定 `name = "hello-world"`：

| 文件 | 声明 |
| --- | --- |
| `src/main.nomo` | `package hello_world` |
| `src/math.nomo` | `package hello_world.math` |
| `src/http/client.nomo` | `package hello_world.http.client` |
| `src/http/main.nomo` | `package hello_world.http` |

编译器通过去掉 `src/` 前缀与 `.nomo` 后缀计算期望声明：

- `src/main.nomo` 直接映射到 manifest root；
- 嵌套 `main.nomo` 映射到其所在目录路径；
- 其它文件映射到相对目录路径加文件名 stem。

因此入口文件不追加 `.main`。项目发现必须先加载 manifest，再校验任何源码声明；
编译器不得从 `src/main.nomo` 声明的第一个 segment 反推或替换项目根。

`E0904` 同时覆盖入口与被导入模块不匹配。诊断包含 manifest 派生的期望声明、实际
声明、源码路径、manifest 路径，以及修改声明或移动文件的安全修复。CLI、compiler、
doc、formatter 与 LSP 必须共享同一映射 helper。

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
5. 恰好一个开发 snapshot 接受旧入口声明 `package app.main` 与
   `package <root>.main`，以及对应的 `app.<relative-path>` package layout，并给出
   迁移诊断 `W0904`。
6. 迁移标准库、示例、Playground、LSP fixtures 和编辑器文档。

迁移命令从 `path`（默认 `.`）只发现一个当前 package，在写入前计算全部修改，然后
原子替换该 package 的 Nomo 源文件。任一文件无法读取、校验、格式化或暂存时，不得
修改任何源码。`--check` 执行相同的发现与校验但不写入：无需修改时成功退出，需要
迁移时失败退出并列出文件。正常迁移第二次运行必须是 no-op。

只有解析为当前 package 的声明与 self-import 可以修改。依赖源码树、dependency
alias、generated/vendor/cache 目录，以及通过 dependency alias 解析的 import
永不重写。Workspace 调用默认只迁移显式选择的 member；其它 member 必须分别选择。

兼容窗口从同时包含新 validator 与 `nomo fix module-roots` 的首个 snapshot 开始。
`W0904` 必须说明接受的 legacy form、canonical replacement、迁移命令与移除 snapshot。
只有 standard library、template、example、fixture、benchmark probe、`nomo-hello`、
Playground、LSP 与 editor surface 全部 canonical，且仓库门禁确认除刻意 negative
fixture 外不再存在 legacy declaration 后，下一个开发 snapshot 才移除兼容路径。

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
- `src/main.nomo`、`src/math.nomo`、`src/http/main.nomo` 分别映射为
  `hello_world`、`hello_world.math`、`hello_world.http`。
- 入口或被导入模块不匹配时由 manifest mapping 产生 `E0904`，即使入口声明的第一段
  在自身看来一致也不能反推项目根。
- Workspace member 分别从自身 manifest 派生 root。
- 同一依赖可在两个消费者中使用不同 alias，依赖源码不变化；canonical identity
  仍能区分相同 source root。
- 本包模块、依赖模块、workspace member 的 definition/rename 与文档链接保持正确。
- `--check` 不写入、正常迁移幂等、注入失败不留下部分写入，dependency source 与
  alias import 保持逐字节不变。
- Legacy 入口只在文档指定 snapshot 编译并发出 `W0904`；移除门禁 fixture 证明后续
  snapshot 会拒绝它们。
- C99 与 browser-WASM example gate 使用 canonical module root 编译。

## 11. 决策与实现证据门禁

评审期间本 RFC 保持 `Proposed` 与 `Not implemented`。只有 compiler、迁移命令、
formatter、scaffolder、doc、LSP、grammar、editor、example、standard library、
C99/WASM path 及以上文档门禁全部通过受保护 CI 后，才可在独立证据 PR 中改为
`Accepted`。该 PR 必须记录相关 merged commit 与 snapshot/退场条件；内部测试不能
被当作 production readiness 证据。
