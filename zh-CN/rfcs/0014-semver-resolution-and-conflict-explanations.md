# RFC 0014：语义化版本求解与冲突解释

> 语言 / Language: 中文 | [English](../../en/rfcs/0014-semver-resolution-and-conflict-explanations.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0014 |
| 标题 | 语义化版本求解与冲突解释 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：严格 constraint、项目/工作区确定性单版本选择、稳定最小冲突、registry index 缓存、lockfile 精确版本输出、range-aware locked 校验、受约束的 precise update，以及 locked/offline/yank/pre-release/conflict 测试 |
| 关联主题 | semver、resolver、lockfile、registry、diagnostics |
| 关联 RFC | [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. 摘要

允许 manifest 使用精确版本、caret、tilde 与有界比较范围；resolver 对同一 canonical package 选择一个满足全部约束的最高非 yanked 版本，并把最终选择写入 workspace-root lockfile。无解时必须输出可追踪到依赖边的最小冲突解释。

## 2. 动机

exact version 保证可复现，却把兼容升级与约束协调全部交给用户。版本范围若没有确定的求解、锁定与诊断规则，又会破坏 RFC 0009 已建立的稳定图模型。

## 3. 提议设计

- 支持 `1.2.3`、`^1.2.3`、`~1.2.3`、`>=1.2, <2.0`；不支持通配字符串或隐式 `latest`。
- 首版采用单版本选择：一个解图中同一 canonical id 只能出现一个版本。
- 候选按稳定总序选择最高版本；fresh resolution 排除 yanked，locked resolution 可复用已校验的 yanked 版本。
- pre-release 只有在约束显式包含 pre-release 时参与选择。
- lockfile 继续记录 exact version、source 与 checksum；`--locked` 不重新求解，`update` 才允许改变选择。
- 冲突诊断列出 package、互斥约束、引入每个约束的依赖路径及可行动建议。

## 4. 实现切片

1. 独立的版本/约束解析与规范化库及性质测试。
2. registry index 候选读取、确定性单版本求解器与 conflict graph。
3. resolver/lockfile/CLI 集成及 `update -p` 精确更新。
4. offline、locked、yank、pre-release 和冲突快照测试。

### 4.1 已实现行为

共享 SemVer 类型由 `nomo-manifest` 持有，使 manifest、resolver 与 lockfile 使用同一套
解释。完整裸版本表示 exact；caret、tilde 与有界比较范围必须显式书写；wildcard、
alternative、隐式 `latest` 与 `=` exact 写法会被拒绝。类似
`0.0.0-20260713145859` 的时间戳快照是普通的显式 pre-release。

`nomo-resolver` 以稳定顺序读取 package index，排除 yanked 与未被显式要求的
pre-release，选择唯一最高版本，为 offline resolution 缓存 HTTP index metadata，
并在冲突时输出带 dependency path 的确定性不可约约束集合。若较晚出现的传递约束或
workspace member 约束改变早期选择，解析会重新执行 graph pass，使整个工作区收敛到
较低兼容版本，而不是保留贪心的首边结果。lockfile 继续只记录最终 exact version；
locked 校验只检查该版本仍满足当前 manifest requirement，不重新求解。
`nomo deps update --precise` 会拒绝不满足 manifest 原约束的版本。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 永久 exact-only | 升级成本持续转嫁给用户 | 拒绝 |
| 允许同包多版本 | codegen、类型身份和链接复杂度显著上升 | 后续 RFC |
| 单版本确定性求解 | 保持 canonical identity 与图模型简单 | 接受 |

## 6. 缺点与风险

单版本策略会拒绝部分生态中可由多版本共存解决的图；冲突解释若不稳定会使 CI snapshot 与用户排障困难。

## 7. 兼容与迁移

现有 exact manifest 与 lockfile 保持有效。范围只影响 fresh resolution；旧 lockfile 在仍满足约束时无需改写。

## 8. 接受门槛

求解器、workspace 收敛、冲突解释、lockfile 兼容，以及
locked/offline/update 端到端测试已全部落地，本 RFC 据此转为 `Accepted`。

## 9. 未决问题

- 是否在后续允许同一 canonical id 的多版本实例。
- lockfile format version 如何表达 solver 语义升级。
- registry protocol 是否需要批量 version metadata endpoint。

## 10. 参考

- [RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md)。
