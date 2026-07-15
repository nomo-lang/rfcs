# RFC 0013：Registry 协议、认证与包完整性

> 语言 / Language: 中文 | [English](../../en/rfcs/0013-registry-protocol-and-package-integrity.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0013 |
| 标题 | Registry 协议、认证与包完整性 |
| 状态 | Accepted（已接受） |
| 作者 | Nomo 语言工作组 |
| 创建日期 | 2026-07-11 |
| 实现状态 | 已落地：file/HTTP/HTTPS registry、TLS 验证、metadata/index、archive checksum、cache、publish/search/yank/login/owner 与 bearer token 测试 |
| 关联主题 | registry、package archive、metadata、checksum、authentication、yank |
| 关联 RFC | [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0014](./0014-semver-resolution-and-conflict-explanations.md) |

---

## 1. 摘要

registry protocol 用 exact version 发布、描述并下载确定性 `.nomo-package` archive，
同时提供显式 metadata/checksum。endpoint 可为 `file://`、`http://` 或经证书验证的
`https://`；HTTP(S) 操作通过固定 `/api/v1` 路径完成，并按 endpoint 使用 Bearer
token。RFC 0014 后续接受了 manifest range 及基于 package index 的确定性选择，
但不改变这些 exact-version artifact path。

## 2. 动机

只有“从 URL 下载压缩包”不足以保证身份、版本、完整性、yank 语义或认证一致性。CLI、resolver、lockfile 与 registry server 需要一个最小但可验证的共同协议。

## 3. Metadata 与下载

- exact-version metadata 包含 `package`、`version`、archive `checksum`、`yanked`。
- package index 返回 package id 和 versions array；RFC 0014 使用该响应做 range 求解，
  隐式 `latest` 选择仍不支持。
- fresh resolution 拒绝 yanked version，并在解包前验证 archive checksum。
- 已有 lockfile 可继续使用已验证 cache/vendor 中的 yanked exact version。
- 解包后 source checksum另行写入 lockfile，不与 archive checksum混用。

## 4. 操作协议

- publish：`PUT /api/v1/packages/<owner>/<package>/<version>`。
- download/metadata：`GET` exact package/version path。
- search：`GET /api/v1/packages?query=<encoded>`。
- yank：`POST .../<version>/yank`。
- owner add/remove：`PUT`/`DELETE .../owners/<user>`。
- login 将 token 存入 `$NOMO_HOME/credentials.toml` 或 `$HOME/.nomo/credentials.toml`，同 endpoint 请求附带 `Authorization: Bearer`。

## 5. Archive 与传输

archive 必须包含 `nomo.toml` 与 `src/`，路径不得逃逸，文件 header 和内容 checksum 必须匹配。HTTPS 使用系统/客户端信任链验证证书，不提供默认 insecure 模式；endpoint 不允许 query 或 fragment 混入 base URL。

## 6. 备选方案

| 方案 | 问题 | 决议 |
| --- | --- | --- |
| Git-only 分发 | 无 publish/yank/owner/metadata 协议 | 不足 |
| 不验证 checksum 的 HTTP 下载 | 易被损坏或替换 | 拒绝 |
| exact version + metadata + checksum + TLS | 可复现、可认证、边界明确 | 接受 |

## 7. 缺点与风险

- 当前协议没有交互式 OAuth、token refresh 或批量 metadata endpoint。
- credentials 文件是 bearer secret，权限和日志必须避免泄漏。
- registry server 实现仍需遵守相同 metadata 与错误语义。

## 8. 决议

接受 exact-version `/api/v1` 协议、确定性 archive、双层 checksum、yank 保留、endpoint-scoped bearer token 和 verified HTTPS。

## 9. 后续问题

- 协议版本协商与服务器能力发现。
- namespace ownership verification、MFA、token scope/rotation。
- 签名包与 transparency log。

## 10. 参考

- `nomo-resolver` registry metadata/transport/archive API 与 registry CLI tests。
- [RFC 0008](./0008-canonical-package-identity-and-aliases.md)、[RFC 0009](./0009-reproducible-workspace-and-package-graphs.md)、[RFC 0014](./0014-semver-resolution-and-conflict-explanations.md)。
