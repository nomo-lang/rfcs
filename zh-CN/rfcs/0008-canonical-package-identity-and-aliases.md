# RFC 0008：Canonical 包身份与依赖别名分离

> 语言 / Language: 中文 | [English](../../en/rfcs/0008-canonical-package-identity-and-aliases.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0008 |
| 标题 | Canonical 包身份与依赖别名分离 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：标准 TOML manifest、`owner/package` 校验、dependency alias import、保留 namespace 与旧 `std` 声明兼容均有 manifest/CLI 测试 |
| 关联主题 | package identity、manifest、dependency alias、import、兼容性 |
| 关联 RFC | [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. 摘要

Nomo 包的稳定身份是 `owner/package`；manifest 中的 dependency key 只是当前包内的 import alias，Git URL、registry endpoint、path、branch、tag 和 rev 都只是 source。源码只依赖 alias，不把下载位置写入语言身份。

## 2. 动机

若把 URL、目录名或本地 alias 当成包身份，同一个包会因获取方式不同而变成多个类型来源，迁移 registry 或 vendor 也会改变 import。稳定身份、局部命名与物理来源必须分离。

## 3. 当前实现

- `[package]` 使用 `namespace`、`name`、`version`、`edition`，canonical id 为 `namespace/name`。
- `[dependencies]` 的 key 必须是 Nomo 标识符，并成为源码 import root。
- dependency 的 `package` 必须是两个合法段组成的 `owner/package`。
- `std`、`nomo`、`core` namespace 被保留；`std` 是内建 import root，不进入普通 lockfile package entry。
- 旧 `std = "0.1.0"` 声明仅作为兼容输入接受并忽略。

## 4. 详细设计

```toml
[package]
namespace = "fynn"
name = "app"
version = "0.1.0"
edition = "2026"

[dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
utils = { package = "fynn/utils", path = "../utils" }
```

源码写 `import json.parser`、`import utils.path`。`json`/`utils` 是局部 alias；诊断、lockfile、发布与冲突判定使用 canonical id。一个 dependency declaration 在 `path`、`git`、`version` 三类 source 中必须且只能选择一种。

## 5. 备选方案

| 方案 | 结果 | 决议 |
| --- | --- | --- |
| URL 即身份 | 获取地址泄漏到源码，镜像迁移会改变类型身份 | 拒绝 |
| alias 即身份 | 不同依赖方对同一包产生不同全局身份 | 拒绝 |
| `owner/package` + alias + source 分层 | 身份稳定、局部命名自由、来源可替换 | 接受 |

## 6. 缺点与风险

- namespace 所有权需要 registry 侧治理。
- alias 与 canonical id 同时出现在诊断和 lockfile 中，工具必须明确区分。
- legacy manifest 兼容是迁移策略，不应阻止未来移除旧输入。

## 7. 对 v0.1 范围的影响

该决议固定 `nomo.toml`、import、lockfile、workspace 和 registry 的共同身份模型。同一 canonical id 解析到冲突 source/version 时，v0.1 直接报错，不进行多版本求解。

## 8. 决议

接受 namespace-first 模型：canonical id 为 `owner/package`；dependency alias 只控制当前源码 import；source metadata 不参与语言身份。

## 9. 后续问题

- namespace 转移、组织验证和名称争议流程。
- 何时结束 legacy manifest 与显式 `std` dependency 兼容。
- 多版本依赖是否以及如何进入后续 resolver。

## 10. 参考

- `nomo-manifest`、项目 import 校验、`nomo add/remove` 与 namespace/reserved-name CLI 测试。
- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md)。
