# RFC 0017：Target Triple、条件依赖与交叉编译

> 语言 / Language: 中文 | [English](../../en/rfcs/0017-target-triples-and-cross-compilation.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0017 |
| 标题 | Target Triple、条件依赖与交叉编译 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 部分前置已落地：C99 backend、native linker metadata 与多平台 release workflow 已有；统一 target 模型未实现 |
| 关联主题 | target triple、cross compilation、conditional dependency、linker、sysroot |
| 关联 RFC | [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0011](./0011-c-ffi-safety-and-link-boundary.md) |

---

## 1. 摘要

定义规范化 target triple，并让 compiler、resolver、lockfile、标准库选择和 native linker metadata 共享同一 target context。host 与 target 明确分离，条件依赖只可使用受限且可静态求值的 target predicates。

## 2. 动机

C 后端便于移植，但“生成 C”不等于可复现交叉编译。若 target 在依赖求解、ABI、标准库与链接阶段含义不同，同一 lockfile 会构造出不同图或错误二进制。

## 3. 提议设计

- triple 规范为 `arch-vendor-os-env`，提供明确 canonicalization 与 unsupported-target 诊断。
- CLI 使用 `--target`；未指定时解析 host triple。target 是编译 cache 与 artifact identity 的组成部分。
- manifest 可按 `target.os/arch/env` 的受限等值/集合 predicate 声明 dependencies、C sources、libraries、search paths 与 flags。
- lockfile 记录完整已知依赖和 target 条件，不因当前 host 静默删除其它条件边。
- toolchain target bundle 提供 ABI facts、C compiler/linker 配置和标准库/runtime 工件；环境变量只通过显式配置层进入。
- build script 与任意代码执行不属于首版。

## 4. 实现切片

1. target triple parser、canonicalization、host detection 与 ABI table。
2. manifest predicate、graph filtering 与 lockfile 表示。
3. C compiler/linker/sysroot 配置及 FFI target metadata。
4. 至少 Linux/macOS 的 host + cross CI matrix 和 artifact inspection。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 完全依赖宿主 C 环境 | 不可复现且错误发现太晚 | 拒绝 |
| 通用脚本条件 | 难以静态求图并扩大供应链执行面 | 拒绝 |
| 受限 predicates + target bundle | 可分析、可缓存、可测试 | 提议 |

## 6. 缺点与风险

目标矩阵会迅速扩大；错误的 ABI facts 或 linker flag 比普通语法错误更难诊断。

## 7. 兼容与迁移

无 target 配置的项目保持 host build 行为。现有全局 native metadata 视为适用于所有 targets，并提供逐步迁移诊断。

## 8. 接受门槛

host/target 图一致性、条件 lockfile、FFI 链接、cache 隔离及至少一条真实 cross-build CI 路径全部验证后才能 `Accepted`。

## 9. 未决问题

- 官方支持 target 的等级和发布承诺。
- 是否允许用户定义 custom JSON target。
- target-specific source 是否允许覆盖同名模块。

## 10. 参考

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)。
