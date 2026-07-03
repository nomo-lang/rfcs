# Nomo v0.1 设计实现计划

> 日期：2026-07-02
> 状态：落地执行稿
> 来源：`nomo_design_implementation_plan.md`

## 一句话目标

Nomo v0.1 要交付一条小而完整、可测试、可诊断的原生编译链路：

```text
.nomo source
  -> Lexer
  -> Parser
  -> AST
  -> Name Resolution
  -> Type Check + Mutability Check
  -> HIR
  -> C99 Codegen
  -> cc / clang / gcc
  -> Native Executable
```

Nomo 不做“更简单的 Rust”或“带类型的 Python”，而是一门用于可靠系统工具、命令行程序和小型服务的小型原生语言：比 C 更安全，比 Rust 更容易学，比 Go 更明确，比 Python 更可部署。

## v0.1 交付范围

- 项目工具：`nomo new/check/build/run/clean`。
- 单文件编译器：`nomoc check/build`、`--emit-c`、`--json-errors`。
- 编译器前端：Lexer、Parser、AST、名称解析、类型检查、可变性检查。
- C99 后端：生成可读 C，由系统 C 编译器产出原生可执行文件。
- 标准库：`std.io`、`std.fs`、`std.env`、`std.result`、`std.option`、`std.array`、`std.string`。
- 诊断：稳定错误码与 JSON 结构。
- 示例：`hello`、`args`、`read_file`、`result_chain`、`struct_methods`、`array_basic`。
- 包模型：namespace-first `nomo.toml`、dependency alias、path/git/registry source 草案、`nomo.lock` 初版。

## v0.1 明确不做

- 协程、goroutine、channel。
- GPU、WASM、裸机、GUI。
- 自举编译器。
- LLVM / Cranelift 后端。
- 完整 trait/interface 约束。
- 完整 lifetime/区域借用系统。
- 宏系统。
- 异常展开。
- null/nil/undefined。
- 隐式数值转换。
- 继承式 OOP。
- 中心化公共包注册服务。

## P0 决策

1. `string` 明确为不可变 RC 值，不做 COW。
2. `Array<T>` 明确为非原子 RC + COW，仅写 API 触发 `make_unique`。
3. `mut` 活动期限定为单个调用表达式。
4. v0.1 坚持无 trait/interface 约束。
5. `?` 在 v0.1 只支持同类型错误传播，跨层转换显式 `map_err`。

## 包管理模型

Nomo 采用 namespace-first package model：

```text
canonical package id = owner/package
```

`owner/package` 是语言和工具链层面的稳定包身份；Git URL、registry、branch、rev、local path 都只是依赖 source，不参与源码 import 的语义身份。

推荐 `nomo.toml`：

```toml
[package]
namespace = "fynn"
name = "hello"
version = "0.1.0"
edition = "2026"

[dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
local_utils = { package = "fynn/utils", path = "../utils" }
http = { package = "nomo-lang/http", git = "https://github.com/nomo-lang/http.git", rev = "2a4b8c1" }
```

源码 import 使用 dependency alias：

```nomo
package app.main

import json.parser
import local_utils.path
import http.client
```

## 验收矩阵

- `cargo test` 通过。
- `cargo fmt --check` 通过。
- `nomo new hello && cd hello && nomo run` 成功。
- `nomoc build --emit-c` 生成的 C 可由系统 C 编译器编译。
- JSON 诊断快照稳定。
- `hello/read_file/result_chain/array_basic/mut_borrow` 示例可检查和运行。
- `nomo deps resolve/tree` 能解析 namespace-first manifest 并解释直接依赖。
- CLI 与 LSP 复用同一套 compiler diagnostics。

## 当前落地切片

本计划先落地三个基础面：

1. 将设计宪法、路线图、RFC 贡献门槛和本执行稿纳入 `rfcs` 仓库。
2. 在 `nomo` 中生成 namespace-first `nomo.toml`。
3. 在 `nomo` 中实现 `nomo deps resolve/tree` 的最小闭环：解析 dependency alias、校验 canonical package id、写入 `nomo.lock`、显示依赖树。
4. `path` 依赖递归读取目标包 manifest，传递依赖进入 lockfile/tree；同一 canonical package id 的不同 source/version 在 v0.1 直接报错。
5. 项目级 `nomo check/build/run` 使用 manifest dependency alias 校验 import root；本地模块使用 Flat+Dir 查找（`src/foo.nomo`，回退 `src/foo/main.nomo`），`path` 与 `git` dependency module 在依赖包 `src/` 下使用同样规则；已 import 的本地模块与依赖模块会把 public API 纳入当前 v0.1 编译单元，private item 不导出；生成 C 的 function 与 nominal type symbol 使用 item 来源 package path 做 mangle；`nomoc` 保持单文件模式，不读取 manifest。
6. `git` 依赖克隆到项目本地 `.nomo/deps/git/` 缓存，checkout 声明的 `rev`，读取目标包 manifest 校验包身份，并把实际 `HEAD` rev 锁入 `nomo.lock`。
7. `nomo-lsp` 使用与项目级 `nomo check` 一致的 manifest-aware diagnostics：项目文件读取最近 `nomo.toml`，无 manifest 文件保持 `nomoc` 单文件行为。
8. registry/version 依赖作为 v0.1 叶子 source 记录到 lockfile/tree：允许显式 `registry` endpoint 元数据，但不做公共 registry 拉取；同一依赖不得混用 `path`、`git`、`version` 多种 source。
9. `nomo deps tree` 在已有 `nomo.lock` 时读取锁定依赖图；没有 lockfile 时才解析当前 manifest/source。
10. `std`、`nomo`、`core` namespace 作为保留命名空间处理，root package 与 dependency canonical owner 均不可占用。
11. `path` 与 `git` resolved package 在 `nomo.lock` 中写入 `sha256:` checksum，覆盖目标包 `nomo.toml` 与 `src/` 内容；registry leaf 因 v0.1 不拉取内容而暂不写 checksum。
12. git 依赖支持 `branch`、`tag`、`rev` checkout selector，并在 lockfile 中同时记录声明的 selector 与实际 `HEAD` rev；三者不可同时声明多个。
13. `nomo deps tree` 读取 lockfile 时，对仍可访问的 locked `path` source 和匹配的 git cache checkout 重新计算 checksum 并拒绝陈旧锁；缺失 path source 或 git cache entry 仍按离线锁定条目展示。
