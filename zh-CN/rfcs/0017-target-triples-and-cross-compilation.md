# RFC 0017：Target Triple、条件依赖与交叉编译

> 语言 / Language: 中文 | [English](../../en/rfcs/0017-target-triples-and-cross-compilation.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0017 |
| 标题 | Target Triple、条件依赖与交叉编译 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已完整实现：canonical target、受限 manifest predicate、完整条件 lockfile、按 target 过滤的 workspace/package/module/FFI graph、隔离产物目录，以及真实 macOS 与 GNU/Linux cross-build CI 路径均已落地 |
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

1. **已落地：**共享 `nomo-target` crate 中的 target triple parser、
   canonicalization、host detection 与 ABI table。
2. **已落地：**dependency entry 支持受限 `arch`、`os`、`env` 等值/集合
   predicate。resolver 保留完整已知图，条件 lockfile edge 保存 canonical
   predicate，workspace、package、module 与 CLI tree 使用同一 target context
   过滤。
3. **已落地：**target context 已贯穿 C emission、依赖选择、条件 C
   source/library/search path/flag、ABI validation 与 native linking。Apple
   Clang 和 target-prefixed GNU compiler 提供首批显式
   compiler/linker/sysroot bundle。
4. **已落地：**arm64 macOS CI 会链接并检查真实 x86-64 Mach-O；x86-64
   Linux CI 会链接 AArch64 ELF，以 `readelf`/`file` 检查，并通过 QEMU 配合
   target sysroot 实际执行，随后上传 target-scoped 证据。

显式 `nomo build --target <triple>` 会把工件放在
`build/<canonical-target>/{c,bin}`。`nomoc build --target` 与
`nomo build --emit-c --target` 会在生成的 C 中嵌入 canonical target macros。
非 host native linking 若没有具体 toolchain path 会提前失败；识别 triple
本身不代表已经支持该目标的链接。

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

验收门槛已由 canonical target unit tests、manifest/lockfile round trip、按
target 过滤的 locked-build integration test、target-scoped artifact/FFI
metadata，以及真实 macOS 与 GNU/Linux cross-build job 满足。

## 9. 后续扩展

- 为每个 recognized target 定义正式支持等级与发布承诺。
- 用户自定义 JSON target 与 custom compiler/linker/sysroot bundle。
- 在条件 dependency/native metadata 之外支持 target-specific module 替换。

## 10. 参考

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0011](./0011-c-ffi-safety-and-link-boundary.md)。
