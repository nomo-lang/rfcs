# RFC 0027：内置 SQLite 持久化与 Pull-Based Query

> 语言 / Language: 中文 | [English](../../en/rfcs/0027-bundled-sqlite-persistence-and-pull-queries.md)

## 元数据

| 字段 | 内容 |
| --- | --- |
| 编号 | 0027 |
| 标题 | 内置 SQLite 持久化与 Pull-Based Query |
| 状态 | Accepted（已接受） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 主题 | SQLite、持久化、database、标准库、C99 backend、Agent |
| 关联 RFC | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0019](./0019-typed-ffi-handles-callbacks-and-bindings.md)、[RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0025](./0025-structured-json-values-and-construction.md)、[RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md) |

---

## 1. 摘要

Nomo v0.1 应提供受限的 `std.sqlite` API，使 Agent 可以持久化状态，而不要求应用侧
编写 C FFI、安装平台 package 或部署独立 database service。

工具链固定使用官方 SQLite 3.53.3 amalgamation，并在源码进入仓库前校验上游公布的
SHA3-256。CLI 将 amalgamation 作为 toolchain data 携带，只有程序实际使用
`std.sqlite` 时才物化 `sqlite3.c` 与 `sqlite3.h`。所选 target C compiler 会将
SQLite 作为与 Nomo 生成 C 并列的独立 translation unit 编译。不使用 `std.sqlite`
的程序不承担 SQLite 编译与链接成本。

公共 API 有意采用 pull-based 设计。`execute` 处理一条受限、参数化且不返回 row
的 statement。`query` 创建一个 opaque prepared-query handle，`next` 每次最多把
一个受限 row 复制为 Nomo value。Database 与 query handle 由 runtime 持有、显式
关闭且不可伪造。SQL 与绑定值绝不出现在诊断或默认日志中。

本 RFC 区分两个不同要求：

- Nomo Agent 应用代码不声明 C FFI、native source、linker flag 或系统 SQLite 依赖；
- 工具链内部可以编译上游 SQLite C amalgamation。

它不声称工具链内部也只能用 Nomo 实现。

## 2. 目标与非目标

### 2.1 目标

1. 在 Linux、macOS 与 Windows 的 native CLI 进程之间持久化结构化 Agent 状态。
2. 保持应用 API 参数化、受限、pull-based，并显式表达 handle lifecycle。
3. 交付一个可复现的 SQLite 实现，而不是接受 host library 版本与 compile option
   漂移。
4. 保持现有 C99 backend 与 target-conditioned cross-build 模型。
5. 防止 SQL 文本、路径、prompt、token、BLOB 与绑定值通过默认诊断泄露。
6. 提供 schema 创建、transaction、insert、update、delete 与增量 row 读取所需能力。
7. 通过显式 capability denial 保持 browser WASM 行为确定。

### 2.2 非目标

本 RFC 不增加：

- ORM、migration framework、query builder、schema language 或生成式 record mapping；
- 网络 database client、connection pool、replication、backup service 或分布式事务；
- 自动 vector embedding、vector search、FTS policy 或 Agent memory ranking；
- 应用自定义 SQLite function、collation、virtual table、loadable extension 或裸
  `sqlite3_*` pointer；
- 任意 multi-statement execution；
- 隐式 transaction 或 write 自动重试；
- 基于 OPFS、IndexedDB 或 SQLite WASM 的 browser persistence；
- task-safe database handle 或从 `std.task` 并发使用同一 handle；
- 应用存储配额。总磁盘用量仍由 deployment 或操作系统 quota 负责。

## 3. 当前 Gap Audit

| 领域 | 当前实现 | 缺口 |
| --- | --- | --- |
| Filesystem | 受限 file helper 与 opaque `File` handle | 应用必须自行发明 locking、recovery、index 与 transaction |
| JSON | 结构化、受限的 JSON 构造与遍历 | JSON 本身不提供持久 index 或原子更新 |
| Process | 长生命周期 shell-free child process 与 framing 基础能力 | 驱动 `sqlite3` executable 依赖部署环境，且丢失 typed binding 语义 |
| FFI | 带 manifest linker metadata 的显式 typed C boundary | 否则每个 Agent 都要负责不安全 SQLite 声明、allocation 与平台链接 |
| Build | Target-aware C99 emission 与应用 FFI source | 还不能根据标准库使用情况选择 toolchain-owned optional native source |
| Task | 使用 copied string boundary 的隔离 native worker | Database handle 是 thread-confined，不能传入 worker |
| Browser WASM | 无 host import 的 capability-denying interpreter | 没有持久 native SQLite VFS |

第一版 portable contract 不能只动态加载 host `sqlite3` library。Windows 与精简 Linux
上的 library presence、version、compile option、extension policy 与 ABI 可用性并不
一致。Shell command 同样不是 native 标准库 contract。

## 4. 详细设计

### 4.1 Canonical `std.sqlite` API

```rust
pub struct SqliteDatabase {
    handle: u64
}

pub struct SqliteQuery {
    handle: u64
}

pub struct SqliteError {
    pub code: string
    pub message: string
    pub native_code: i64
}

pub enum SqliteOpenMode {
    ReadOnly
    ReadWrite
    ReadWriteCreate
}

pub enum SqliteValue {
    Null
    Integer(i64)
    Real(f64)
    Text(string)
    Blob(Array<u32>)
}

pub struct SqliteColumn {
    pub name: string
    pub value: SqliteValue
}

pub struct SqliteRow {
    pub columns: Array<SqliteColumn>
}

pub struct SqliteExecuteResult {
    pub changes: u64
    pub last_insert_rowid: i64
}

pub fn open(
    path: string,
    mode: SqliteOpenMode,
    busy_timeout_millis: u64
) -> Result<SqliteDatabase, SqliteError>

pub fn open_memory(
    busy_timeout_millis: u64
) -> Result<SqliteDatabase, SqliteError>

pub fn execute(
    database: SqliteDatabase,
    sql: string,
    params: Array<SqliteValue>
) -> Result<SqliteExecuteResult, SqliteError>

pub fn query(
    database: SqliteDatabase,
    sql: string,
    params: Array<SqliteValue>
) -> Result<SqliteQuery, SqliteError>

pub fn next(
    query_value: SqliteQuery,
    max_row_bytes: u64
) -> Result<Option<SqliteRow>, SqliteError>

pub fn reset(
    query_value: SqliteQuery,
    params: Array<SqliteValue>
) -> Result<void, SqliteError>

pub fn close_query(
    query_value: SqliteQuery
) -> Result<void, SqliteError>

pub fn close(
    database: SqliteDatabase
) -> Result<void, SqliteError>
```

`SqliteDatabase` 与 `SqliteQuery` 是 opaque type。它们的字段不公开，不能读取、
写入或直接构造。复制 Nomo value 只会复制一个 integer capability；该 capability
是否仍有效由 runtime registry 决定。

`SqliteColumn` 保留结果顺序并允许重复 column name。需要 name lookup 的应用可以
自行选择 first、last 或 error policy，而不是接收一个有歧义的内建映射。

### 4.2 Open 语义

`open` 拒绝空路径、内嵌 NUL 与特殊名称 `:memory:`。内存 database 必须通过
`open_memory` 创建，避免意外混淆 persistent 与 ephemeral storage。

Mode 映射到以下 `sqlite3_open_v2` policy：

- `ReadOnly`：`SQLITE_OPEN_READONLY`；
- `ReadWrite`：`SQLITE_OPEN_READWRITE`，文件不存在时失败；
- `ReadWriteCreate`：`SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE`。

每个 connection 还使用 `SQLITE_OPEN_FULLMUTEX`、
`SQLITE_OPEN_PRIVATECACHE` 与 extended result code。不会启用 URI filename
解析，因此 query-string flag 不能悄悄改变 VFS、cache、locking、immutable-file
或 open-mode 行为。

相对路径由 SQLite 基于进程 working directory 解析。按照上游 API，Windows 路径以
UTF-8 传入。第一版遵循普通 host symbolic-link 行为；后续 capability-based
filesystem 设计可以增加 rooted 或 no-follow open。

`busy_timeout_millis` 必须位于 `0..=300_000`。零表示 SQLite 遇到 contention
立即返回；非零值只约束 SQLite 的 lock wait，并不是任意 SQL 的 execution deadline。

成功打开后，runtime 会启用 extended result code、`foreign_keys`，以及固定 SQLite
API 支持的 defensive/trusted-schema 设置。初始化失败必须先关闭 partial handle
再返回错误。

### 4.3 单 Statement 与 Positional Binding

`execute` 和 `query` 只接受一条 SQL statement。空 SQL 与 prepare tail 中第二条
非注释 statement 会被拒绝。SQL 可以包含空白与注释，但不能包含内嵌 NUL。

参数在 SQLite boundary 上按一开始的 position 绑定。Nomo array 绑定
`1..=len`；其长度必须等于 `sqlite3_bind_parameter_count`。可以使用普通 `?`、
编号 `?NNN` 与 SQLite named placeholder，但稀疏 placeholder number 仍计入精确
array 长度与 1024 parameter limit。

Text 与 BLOB 参数使用 `SQLITE_TRANSIENT`，因此 SQLite 会在 Nomo 调用返回前取得
自己的副本。`Array<u32>` BLOB 的每个元素必须位于 `0..=255`，更大数值返回
`invalid_request`。

应用应绑定数据，而不是把数据插值进 SQL。API 不提供不安全 raw-binding escape hatch。

### 4.4 Execute

`execute` 在内部 prepare、bind 并 step 一条 statement。只有第一次 step 返回
`SQLITE_DONE` 才成功。若 statement 产生 row，则返回 `unexpected_row`，调用方必须
使用 `query`。

成功时返回 statement 之后立即观察到的 per-connection `changes` 与
`last_insert_rowid`。内部 statement 在所有成功与错误路径上都会 finalize。

Transaction 使用显式 SQL：

```rust
sqlite.execute(db, "BEGIN IMMEDIATE", Array.new<SqliteValue>())?
sqlite.execute(db, "INSERT INTO memory(value) VALUES (?)", values)?
sqlite.execute(db, "COMMIT", Array.new<SqliteValue>())?
```

Runtime 不会悄悄 begin、commit、rollback 或 retry transaction。应用在可恢复的
transaction error 之后必须按需发出 `ROLLBACK`。

### 4.5 Pull-Based Query

`query` prepare 并 bind 一条 statement，然后把 native prepared statement 放入
runtime-owned query registry。它不会执行到产生 row。

`next` 执行一次 `sqlite3_step`：

- `SQLITE_ROW` 把一个 row 复制到 `SqliteRow`；
- `SQLITE_DONE` 返回 `None`；
- contention、constraint、corruption、I/O 与其他失败返回经过分类的
  `SqliteError`。

在 `SQLITE_DONE` 之后重复调用 `next` 仍返回 `None`。只有全部 column name 与 value
都通过 bounds 和 encoding 检查后才构造 row，因此失败时不会泄露 partial row。

`reset` 调用 `sqlite3_reset`、清除旧 binding、校验新 parameter array 并重新 bind。
这样可以复用 prepared query，又不暴露 raw statement pointer。Step error 之后的
reset 返回经过分类的 reset/bind 结果，不会隐藏之前的错误状态。

### 4.6 Value Mapping 与复制

SQLite storage class 映射如下：

| SQLite storage class | Nomo value |
| --- | --- |
| `NULL` | `SqliteValue.Null` |
| 64-bit signed integer | `SqliteValue.Integer(i64)` |
| IEEE 754 double | `SqliteValue.Real(f64)` |
| UTF-8 text | `SqliteValue.Text(string)` |
| bytes | `SqliteValue.Blob(Array<u32>)` |

Text 与 BLOB 结果在 caller thread 上复制进新的 Nomo-managed value。SQLite pointer
绝不存进 Nomo string 或 array。SQLite `TEXT` 中的无效 UTF-8 返回 `encoding`；
需要任意 byte 的应用必须存取 BLOB。

SQLite integer 与 real 转换使用对应的 native 64-bit API，不发生基于 string 或
locale-sensitive formatting 的 number conversion。

### 4.7 精确限制

第一版固定以下 limit：

- 每进程最多 32 个 live 且未关闭的 database handle；
- 每进程最多 256 个 live 且未关闭的 query handle；
- persistent database path 最多 4096 UTF-8 byte；
- SQL statement 最多 1 MiB；
- 每 statement 最多 1024 个 parameter；
- 单个 text 或 BLOB parameter 最多 8 MiB；
- 每 statement 的 parameter encoded byte 总量最多 16 MiB；
- 最多 256 个 result column；
- 单个 text 或 BLOB result value 最多 8 MiB；
- caller 提供的 `max_row_bytes` 位于 `1..=16 MiB`；
- `busy_timeout_millis` 位于 `0..=300_000`。

生成的 SQLite build 会把可兼容的 engine limit 降到相同或更严格。Per-connection
`sqlite3_limit` 会再次设置关键的 length、SQL、column、expression-depth、
variable-number、function-argument、compound-select 与 LIKE-pattern limit，避免
未来 toolchain 变更悄悄放宽既有 public contract。

Row 过大时，query 进入 terminal `limit`，但仍可关闭。所有 bound 都在构造
Nomo-managed output 之前计算。

Database file 总大小不是标准库 memory bound。操作系统、container、deployment
policy 与后续 storage-capability 工作可以设置 disk quota。当 filesystem 或已配置
database page limit 拒绝增长时，SQLite 仍返回 `full`。

### 4.8 Lifecycle

`close_query` finalize prepared statement、移除 registry entry 并使 handle 失效。
关闭已关闭或 stale query 返回 `closed`。

只有 database 不再拥有 live query 时，`close(database)` 才成功。否则返回
`busy_handle` 并保持 connection 打开。成功关闭后，registry entry 被移除，该 handle
的全部 copied Nomo capability 都会失效。

进程正常返回但仍存在 live SQLite handle 时，只输出一条 generic lifecycle
diagnostic，并 best-effort finalize 与 close。消息只包含计数，不包含路径、SQL、
schema name 或 value。

Browser interpreter 永不创建这些 registry。

### 4.9 Error Contract

`SqliteError.code` 取以下值之一：

- `invalid_request`：mode、timeout、path、SQL shape、parameter 或 row limit 无效；
- `limit`：超出 Nomo 或已配置 SQLite resource limit；
- `open`：无法打开请求的 database；
- `prepare`：无法编译 statement；
- `bind`：无法绑定 parameter；
- `step`：statement execution 失败且没有更具体分类；
- `busy`：database locked 或 busy；
- `constraint`：operation 被 constraint 拒绝；
- `read_only`：通过 read-only connection 或 file 发起 write；
- `corrupt`：SQLite 报告 database content corrupt 或 invalid；
- `full`：storage growth 被拒绝；
- `encoding`：标记为 text 的 result 不是有效 UTF-8；
- `unexpected_row`：把产生 row 的 statement 传给 `execute`；
- `busy_handle`：database 仍拥有 live query；
- `closed`：使用 stale 或 closed database/query handle；
- `runtime_unavailable`：当前 runtime 不能提供 native SQLite；
- `internal`：registry、allocation 或 engine invariant 失败。

存在 SQLite extended numeric result code 时，`native_code` 携带该值；Nomo 侧校验失败
时为零。除非应用有意依赖固定 engine，否则必须按 stable string code 分支。

Message 稳定、受限且通用。Runtime 不调用 `sqlite3_expanded_sql`、不启用 tracing，
也不复述 SQL、parameter、path、prompt、token、BLOB、row content 或可能包含应用
identifier 的 SQLite error string。

### 4.10 内置 SQLite Source 与可复现性

第一版固定：

- 上游版本：SQLite 3.53.3；
- archive：`sqlite-amalgamation-3530300.zip`；
- 上游 SHA3-256：
  `d45c688a8cb23f68611a894a756a12d7eb6ab6e9e2468ca70adbeab3808b5ab9`。

仓库记录 upstream URL、version、digest、retrieval date、public-domain notice 与精确
extracted-file digest。不交付生成的 autoconf 或 shell build product。

更新 SQLite 必须是经过 review 的 dependency update，并包含：

1. 已验证的 upstream digest；
2. 隔离的签名 commit；
3. upstream release/security note review；
4. native、sanitizer、cross-build 与 persistence regression evidence；
5. 更新后的 provenance metadata。

不会自动 fallback 到 host `libsqlite3`。固定一个 engine 才能在不同 host 上保持行为
与 compile option 可复现。

### 4.11 C99 Backend 与 CLI Build

当 typed IR 包含 SQLite operation 时，生成 C 会包含 stable feature marker 与
toolchain-owned wrapper。CLI 随后：

1. 将嵌入的固定 `sqlite3.c` 与 `sqlite3.h` 写入 target-scoped build directory；
2. 在调用 compiler 前校验 toolchain 内嵌 digest；
3. 用所选 target C toolchain 把 SQLite 编译为独立 translation unit；
4. 与 Nomo 生成 C 一起链接；
5. 把 SQLite version、source digest 与 compile-option set 纳入 persistent
   codegen/build cache key。

SQLite translation unit 使用经过 review 的选项，包括 serialized threading、禁用
double-quoted string literal、默认 untrusted schema、默认 foreign key、API armor
与收紧的 resource limit。Nomo wrapper 永不启用 loadable extension 或 shared-cache
mode。

程序使用 SQLite 时，`nomo build --emit-c` 会物化 `main.c`、`sqlite3.c`、
`sqlite3.h` 与 provenance metadata。只输出 `main.c` 不是可重建的 C artifact。

不使用 `std.sqlite` 的程序不会物化、编译或链接 SQLite。

### 4.12 并发与 `std.task`

固定 engine 以 serialized mode 构建用于防御性安全，但 Nomo SQLite handle 仍由
runtime 持有且 thread-confined。`std.sqlite` 属于 RFC 0026 task-safe forbidden set。
Handle 不能跨越 task string boundary，第一版 worker 也不能自行打开 database。

后续可以在 registry ownership、process-exit cleanup、busy policy 与确定性 fixture
通过独立 acceptance gate 后，允许每个隔离 task 使用自己的 connection。本 RFC
不隐含这项变化。

### 4.13 Browser WASM

Browser interpreter 对相同 API 完成 type-check，但 `open` 与 `open_memory` 返回
`runtime_unavailable`。不增加 SQLite WASM、OPFS、IndexedDB、host import、network
fetch 或 memory-limit increase。

对无效 browser handle 的 operation 返回 `closed`。参数校验不读取文件，也不调用
任何 host capability。

## 5. 兼容性与迁移

本提案是 additive。现有 filesystem、JSON、process、FFI、task 与 manifest 行为
不变。

SQLite amalgamation 是 toolchain implementation dependency，不是 Nomo package
dependency，也不是应用 `[ffi]` metadata。因此 lockfile 不会增加伪造的 `sqlite3`
package entry。可复现证据属于 compiler/toolchain 版本与 emitted C provenance。

API 使用 opaque handle 而非 public native layout，因此未来 storage backend 或
SQLite 更新不会改变 Nomo value ABI。

## 6. 替代方案

| 替代方案 | 优点 | 代价 / 拒绝原因 |
| --- | --- | --- |
| 应用 C FFI 调用 SQLite | 工具链改动最少 | 每个 Agent 都重复不安全声明、ownership、compile flag 与平台链接 |
| 动态加载 host `libsqlite3` | Release artifact 较小 | Host presence、version、feature 与 security option 不可复现，Windows/精简 Linux 尤其明显 |
| 通过 `std.process` 运行 `sqlite3` CLI | 复用现有 process API | Executable 可选、framing 脆弱且丢失安全 typed binding |
| 纯 Nomo append-only JSON store | 无 native dependency | 会低质量地重新实现 locking、crash recovery、index、transaction 与 compaction |
| 把 Rust database 放进 `nomo` CLI | Rust 生态成熟 | 编译后的 Nomo executable 需要 sidecar RPC runtime，否则不再 standalone |
| 把 SQLite 塞进每个 generated C file | 简单 single-file output | 未使用时也增加数 MB 与编译成本，并使 codegen snapshot 不可管理 |
| Toolchain-owned optional amalgamation | 可复现、standalone、cross-target、应用无 FFI | 增加 toolchain 体积与 SQLite 程序 build 时间；为 native persistence slice 接受 |

## 7. 缺点与风险

- Compiler/toolchain release 会因压缩和嵌入的 amalgamation 变大。
- 每个 target 第一次构建 SQLite 程序时需要编译较大的 C translation unit。
- Vendoring 需要显式 upstream 更新与 security review 流程。
- Pull-based row 比 ORM 更底层，需要应用自行 mapping。
- 使用 `Array<u32>` 表示 copied BLOB 并不紧凑，未来 `bytes` RFC 可以改进。
- 本 API 不限制总磁盘增长。
- SQLite handle 有意不在 isolated task 内可用。
- Generic error message 能保护 secret，但原始 engine detail 更少。

## 8. 对 Native CLI Agent 目标的影响

结合 RFC 0022 至 0026，本 slice 允许 Nomo CLI Agent：

1. 在没有应用 FFI 的情况下创建 schema 与持久 state database；
2. 使用 bound parameter 保存 conversation、tool metadata、checkpoint 与 JSON document；
3. 通过显式 SQL transaction 原子更新多条 record；
4. Pull bounded row，而不是一次加载完整 result set；
5. 在另一个进程重启并恢复持久化状态；
6. 保持 prompt、token 与 row content 不进入默认诊断。

它不增加 semantic memory ranking、vector search 或完整 Agent 产品。

## 9. Acceptance Gate

本 RFC 状态为 `Accepted`。以下 gate 均已在接受前通过：

1. 两份 v0.1 specification、标准库文档与本 RFC 一致定义精确 API、limit、
   lifecycle、error、task-safety 与 browser contract。
2. Canonical `std.sqlite` source 与 standard-module registry 暴露上述全部 type/function，
   并支持 LSP/doc navigation。
3. Compiler lowering 与 typed IR 校验精确 database/query/value type，拒绝伪造或读取
   opaque handle field，并且只在真正使用时选择 SQLite runtime。
4. 官方 SQLite 3.53.3 amalgamation、public-domain notice、upstream SHA3-256、
   extracted-file digest 与 provenance metadata 已提交并独立验证。
5. Build、run、test 与 `--emit-c` 路径物化并编译相同 target-scoped SQLite source；
   cache key 包含 version、digest 与 compile option。
6. Compiler/codegen test 覆盖每项 operation 的 mode、timeout、SQL、parameter、value
   与 return-type validation。
7. Native integration test 覆盖 persistent reopen、in-memory isolation、schema 创建、
   五种 value class、parameter binding、execute metadata、row order、重复 name、
   repeated `None`、reset/rebind 与显式 transaction。
8. Test 覆盖精确 handle、path、SQL、parameter、value、column、row 与 timeout limit，
   包括每个 limit failure 后的 cleanup。
9. Lifecycle test 覆盖 busy database close、query close、stale/copy handle、
   process-exit cleanup、prepare/bind/step error 与全部 finalization path。
10. Failure fixture 覆盖 contention timeout、read-only write、constraint、corrupt
    database input、full storage、invalid UTF-8 text，以及把 row-producing statement
    传入 `execute`。
11. Path、SQL、parameter、BLOB、row 与 schema value 中的 secret sentinel 绝不出现在
    compiler diagnostic、runtime error、lifecycle warning 或默认日志。
12. AddressSanitizer/LeakSanitizer 与重复 open/query/reset/close stress 不发现 wrapper
    或 cross-boundary lifetime error。Nomo 不修改 upstream SQLite。
13. Conformance suite 在 Linux、macOS 与 Windows 运行；真实 macOS
    arm64-to-x86_64 与 Linux x86_64-to-arm64 build 为 target 编译并链接固定
    amalgamation。
14. Browser WASM 返回 `runtime_unavailable`，不增加 import，并保持既有 memory gate。
15. 一个 Nomo example 实现小型 durable Agent-memory/checkpoint store，使用 parameter
    binding 与显式 transaction，在第二个进程中重启，并且不声明应用 FFI。
16. Formatting、Clippy、unit/CLI integration、release、WASM、cross-build 与 platform
    smoke 在签名 implementation PR 及 merge 后 `main` 上通过。
17. Implementation 从签名 child branch 经 reviewed PR 合入；状态改为 `Accepted`
    前在此记录 acceptance evidence 与链接。

### 9.1 验收证据

- 实现通过
  [nomo PR #16](https://github.com/nomo-lang/nomo/pull/16) 合入，merge commit 为
  [`a6405a5`](https://github.com/nomo-lang/nomo/commit/a6405a55e9a98434ec95b536fc1585b8e381ebb4)。
- GitHub 验证了 child branch 上的全部五个签名提交，包括固定上游 amalgamation、
  runtime/compiler 实现、Windows 换行完整性、跨平台输出断言与 portable 文档源码路径。
- 最终 PR smoke
  [run 30128914455](https://github.com/nomo-lang/nomo/actions/runs/30128914455)
  通过 Linux compiler/runtime 检查，以及 Windows 与 macOS 上的完整 SQLite
  conformance。
- 最终签名分支完整 CI
  [run 30128918597](https://github.com/nomo-lang/nomo/actions/runs/30128918597)
  通过 formatting、Clippy、全部 workspace test、release/WASM/performance gate、
  两进程 Agent checkpoint、macOS arm64-to-x86_64 链接，以及 Linux
  x86_64-to-arm64 链接与执行。
- Merge 后 `main` CI
  [run 30129166251](https://github.com/nomo-lang/nomo/actions/runs/30129166251)
  再次完整通过上述 gate。

## 10. 延后工作

- 紧凑 `bytes` type 与 zero-copy bounded BLOB read；
- Typed row decoding 与 schema-derived mapping；
- Schema migration helper 与 migration journal policy；
- Online backup、integrity-check 与 recovery API；
- FTS5 与 Agent-memory retrieval policy；
- Vector-search extension 评估；
- Per-task independent connection 与 bounded connection pool；
- Storage quota 与 capability-rooted path；
- 通过独立 gate 的 SQLite WASM/VFS browser persistence。

## 11. 参考

- `std/src/sqlite.nomo`
- `crates/nomo_compiler/src/builtins/builtins_sqlite.rs`
- `crates/nomo_codegen_c/src/runtime/host_sqlite.c`
- `crates/nomo/src/project/build.rs`
- [SQLite 3.53.3 下载与 amalgamation digest](https://www.sqlite.org/download.html)
- [SQLite amalgamation](https://www.sqlite.org/amalgamation.html)
- [SQLite public-domain 声明](https://www.sqlite.org/copyright.html)
- [SQLite threading mode](https://www.sqlite.org/threadsafe.html)
- [SQLite implementation limit](https://www.sqlite.org/limits.html)
- [SQLite compile-time option](https://www.sqlite.org/compile.html)
- [`sqlite3_open_v2`](https://www.sqlite.org/c3ref/open.html)
- [`sqlite3_prepare_v3`](https://www.sqlite.org/c3ref/prepare.html)
- [SQLite parameter binding](https://www.sqlite.org/c3ref/bind_blob.html)
