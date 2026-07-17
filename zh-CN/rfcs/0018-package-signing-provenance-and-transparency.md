# RFC 0018：包签名、来源证明与透明日志

> 语言 / Language: 中文 | [English](../../en/rfcs/0018-package-signing-provenance-and-transparency.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0018 |
| 标题 | 包签名、来源证明与透明日志 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已在 `nomo-supply-chain`、registry publish/owner-key API、resolver trust policy、lockfile evidence、独立 `nomo verify` CLI、双签名日志密钥轮换、signed-head gossip 与在线/离线 proof freshness 策略中实现 |
| 关联主题 | package signing、provenance、transparency log、registry、trust policy |
| 关联 RFC | [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0013](./0013-registry-protocol-and-package-integrity.md) |

---

## 1. 摘要

为 package release 增加对 canonical id、version、archive checksum 与 provenance 的签名 envelope；registry 返回可验证的 append-only transparency inclusion proof。resolver 按项目/组织 trust policy 校验，而不是把 registry TLS 等同于发布者身份。

## 2. 动机

checksum 能发现下载内容与 metadata 不一致，却不能证明谁授权了发布，也不能发现 registry 针对不同客户端展示不同历史。进入真实生态前需要密钥轮换、撤销和审计边界。

## 3. 设计

- 签名对象使用确定性编码，覆盖 canonical package、version、archive checksum、manifest checksum、publisher key id 与可选 provenance digest。
- namespace owner 显式登记 publisher public key；registry token 认证与 release signing key 分离。
- transparency log 为每个 release/owner-key 事件提供 signed tree head 与 inclusion proof；客户端缓存并检测回滚。
- version 2 signed tree head 绑定 log id、签发时间、签名 key 与前序
  size/root。日志 key rotation 是同时由旧 key 与新 key 签名、按 tree size
  单调激活且最终锚定 manifest 初始 pin 的事件。
- 客户端比较独立获得的 signed head；同一 size 不同 root 属于
  equivocation，新 head 必须用带签名的 predecessor chain 延伸到 cached 或
  gossip anchor。
- proof freshness 分别定义在线/离线最大年龄与 future clock skew；offline
  只放宽年龄，不放宽 pinned trust root、rotation chain、inclusion proof、
  rollback 或 equivocation 校验。
- trust policy 支持 `checksum-only`、`signed`、`signed+transparent`，公共 registry 默认最终提升到最高等级，私有 registry 可显式配置。
- key rotation/revocation 是新日志事件；已锁定工件不会被静默替换，重新获取时应用当前 policy。
- 私钥不进入 Nomo credentials 文件；CLI 接受外部 signer 或硬件/OS key provider。

## 4. 实现

1. `nomo-supply-chain` 定义 Ed25519 release envelope、canonical subject、
   provenance 文档、publisher key id、transparency event、version 2 signed
   tree head、双签名日志 key rotation 与 Merkle inclusion proof；序列化确定
   且拒绝未知字段。
2. `nomo publish --signer` 只把 canonical subject 流式发送给外部 signer，
   并分别上传 archive、provenance 与 attestation。`nomo owner key add|revoke`
   管理 publisher 授权；`nomo verify` 是独立的 archive/envelope/provenance
   验证器，并要求透明度校验显式提供 `--log-key`；支持重复 `--gossip`
   输入、输出可共享 `--write-gossip` checkpoint，以及在线/离线 freshness
   和 future-skew 参数。
3. manifest 解析 `checksum-only`、`signed`、`signed+transparent`；最后一项
   强制要求显式 `trust.transparency-keys`。resolver 将这些 pinned keys 传入
   transparency 校验，验证配置的 gossip checkpoint，执行在线/离线
   freshness 限制，并同时写入私有 cached head 与可共享 signed-head
   checkpoint。
4. lockfile 保存 publisher key id、subject/provenance digest 与 transparency
   root/size。测试覆盖确定性向量、publisher key 轮换与撤销、双签名日志
   key rotation、inclusion proof、未信任日志拒绝、回滚、gossip
   equivocation、在线/离线 proof freshness、离线 metadata 与 signed
   registry archive。

## 5. 备选方案

| 方案 | 问题 | 倾向 |
| --- | --- | --- |
| 仅 TLS + checksum | registry 仍是不可审计的单点信任 | 不足 |
| registry 代签所有包 | 无法区分 registry 与 publisher 身份 | 拒绝 |
| publisher signing + transparency | 可验证授权与历史一致性 | 接受 |

## 6. 缺点与风险

密钥恢复和撤销对用户复杂；不严谨的 canonical encoding 会造成跨实现签名不一致；透明日志带来运营成本。

## 7. 兼容与迁移

旧 registry 起始为显式 `checksum-only`，不能伪装成 signed。lockfile schema
增加可选 signature/proof identity，不改变 archive checksum 语义。新的
transparency bundle 使用 signed-head schema 2；schema 1 signature 因未绑定
log identity、签发时间、key lineage 与 predecessor state 而被拒绝。旧
cached size/root anchor 在有效 schema 2 history 延伸它时仍可使用。

## 8. 接受门槛

独立验证器能复现签名与 inclusion proof；publisher 与日志 key rotation、
撤销、未信任日志、回滚、gossip equivocation 及在线/离线 freshness 测试
通过；私钥不会进入 credentials、metadata、provenance、envelope 或
lockfile，因此实现与生产透明日志运营门槛均已完成。

## 9. 未决问题

- schema v1 之后 provenance 应采用哪一种标准 attestation 格式。

## 10. 参考

- [RFC 0013](./0013-registry-protocol-and-package-integrity.md)。
