# RFC 0029：受限 UTC Cron Schedule 计算

> 语言 / Language: 中文 | [English](../../en/rfcs/0029-bounded-utc-cron-schedule-calculation.md)

## 元数据

| 字段 | 值 |
| --- | --- |
| 编号 | 0029 |
| 标题 | 受限 UTC cron schedule 计算 |
| 决策状态 | Accepted（已接受） |
| 实现状态 | Implemented（已实现） |
| 实现证据 | [`nomo#18`](https://github.com/nomo-lang/nomo/pull/18)，merge [`bf290fd`](https://github.com/nomo-lang/nomo/commit/bf290fd75e235c083c5b9df441e9043292076096) |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 主题 | cron、scheduling、time、Agent、bounds、browser WASM |
| 相关 RFC | [RFC 0024](./0024-controlled-child-processes-and-stdio.md)、[RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md)、[RFC 0027](./0027-bundled-sqlite-persistence-and-pull-queries.md) |

---

## 1. 摘要

Nomo v0.1 应提供 `std.cron`：一个受限、确定性的 API，用于解析五字段 UTC cron
expression、判断某一分钟是否匹配，以及计算严格晚于给定 Unix timestamp 的下一
个匹配分钟。

本 API 只负责 schedule 计算，不持有后台 thread、不持久化 job、不执行 callback，
也不选择 missed-run policy。长期运行的 native Agent 可以组合 `std.cron`、
`std.time`、`std.task`，并在需要时使用 `std.sqlite`。把这些 policy 留在应用代码
中，可以避免一个小型标准库 primitive 演变为 process-global scheduler。

Schedule 计算在接收 expression 与 timestamp 后是纯计算，因此 native C99 backend
与 browser WASM 都可用，并且可安全用于 isolated task。等待仍由显式 native
`std.time.sleep_millis` 完成。

## 2. 目标与非目标

### 2.1 目标

1. 解析熟悉且显式受限的五字段 cron syntax。
2. 使用 UTC 与 Unix milliseconds，使结果不依赖 host locale、timezone database
   或 daylight-saving change。
3. 匹配给定分钟，并计算下一匹配分钟。
4. 精确定义 day-of-month 与 day-of-week 的交互。
5. 限制 expression 大小、解析工作量、timestamp range 与 next-match search。
6. 对不可信 schedule input 返回稳定 error，而不是 panic。
7. 保持 native 与 browser-WASM 行为一致。
8. Nomo 应用代码无需 C FFI。

### 2.2 非目标

本 RFC 不增加：

- daemon、job registry、callback closure、后台 thread 或全局 event loop；
- persistence、lease、leader election、retry、overlap control 或 missed-run
  policy；
- local timezone 或 daylight-saving 行为；
- seconds 或 year 字段；
- month/day name、`L`、`W`、`#`、`?`、`@daily` 或实现专用 cron extension；
- sub-minute timer、async/await、signal 或强制 task cancellation。

## 3. 当前缺口

`std.time` 提供 wall-clock、monotonic milliseconds 与阻塞 sleep。`std.task`
提供隔离式 native worker 与 cooperative cancellation。`std.sqlite` 可以持久化
应用 checkpoint。这些 API 都不描述日历 schedule，也不计算下一 trigger。

应用目前只能自行编写取模计算，或把调度委托给 host-specific daemon。前者会重复
Gregorian calendar 与 day-field 的微妙语义；后者无法让一个可移植 Nomo CLI
Agent 自主拥有 scheduling policy。

## 4. 提案设计

### 4.1 Canonical `std.cron` API

```rust
pub struct CronSchedule {
    expression: string
}

pub struct CronError {
    pub code: string
    pub message: string
    pub field: u64
}

cron.parse(expression: string) -> Result<CronSchedule, CronError>
cron.matches(schedule: CronSchedule, unix_millis: i64) -> Result<bool, CronError>
cron.next_after(schedule: CronSchedule, unix_millis: i64) -> Result<i64, CronError>
```

`CronSchedule` 对应用代码 opaque：只有 `cron.parse` 能构造它，直接 field access
会被拒绝。`CronError.field` 对 minute、hour、day of month、month 与 day of week
分别使用零到四；whole-expression 或 timestamp error 使用五。

`matches` 把 timestamp 视为其所属 UTC minute；second 与 millisecond 不影响结果。

`next_after` 返回以 `:00.000` 结尾的 minute boundary，并且严格大于输入 instant。
即使输入正好位于匹配 minute boundary，也不会返回同一次 occurrence。

### 4.2 Expression grammar

Expression 恰好包含五个 ASCII-whitespace-separated field：

```text
minute hour day-of-month month day-of-week
```

Field range 为：

| Field | Range |
| --- | --- |
| minute | `0..59` |
| hour | `0..23` |
| day of month | `1..31` |
| month | `1..12` |
| day of week | `0..6`，其中 `0` 为 Sunday |

每个 field 接受：

- `*`；
- 一个 unsigned decimal value；
- `1-5` 这样的 inclusive range；
- `1,3,5` 这样的 list；
- wildcard 或 range 加 positive step，例如 `*/15` 或 `1-20/3`。

List 可以组合 value、range 与 stepped range。Field 内 whitespace、空 list
member、descending range、leading sign、超出 field range 的值、zero step，以及
不支持的 name 或 extension 都会被拒绝。

完整 expression 最多 256 个 UTF-8 byte，并且只能包含上述 grammar 接受的 ASCII
syntax。重复选择同一 value 不影响结果。

### 4.3 Day-field 语义

Minute、hour 与 month 必须全部匹配。

当 day of month 或 day of week 的 selected set 覆盖其完整 legal range 时，该
field 为 *unrestricted*，无论它写成 `*`、`*/1` 还是 full range。

- 两个 day field 都 unrestricted 时，每个 calendar day 都匹配；
- 恰好一个 unrestricted 时，另一个 restricted field 必须匹配；
- 两个都 restricted 时，任意一个匹配即可。

这样 equivalent selected set 就有 equivalent behavior，也消除了 `*` 与 `*/1`
之间令人意外的 syntactic distinction。

### 4.4 UTC、range 与 search bound

Timestamp 使用 UTC proleptic Gregorian calendar，并限制在
`1970-01-01T00:00:00.000Z` 到 `9999-12-31T23:59:59.999Z`。

`next_after` 最多检查连续 4,208,400 个 minute boundary，略多于最长的八年
leap-day gap。这覆盖 accepted grammar 所需的最长有效 recurrence，包括 2100
附近 Gregorian non-leap century gap。如果该 bound 内或 maximum timestamp 之前
没有 match，则返回 `no_match`。

实现可以跳过不可能的时间段以提高效率，但可观察结果必须与 minute-by-minute
search 一致。

### 4.5 Error contract

`CronError.code` 使用：

| Code | 含义 |
| --- | --- |
| `syntax` | field count 错误或 field grammar 非法 |
| `range` | value、range 或 step 超出 field contract |
| `limit` | expression size limit 被超过 |
| `timestamp_range` | timestamp 不在支持的 UTC range 内 |
| `no_match` | 定义的 search/range 内没有更晚 occurrence |

Message 供人阅读并保持稳定，caller 应按 `code` 分支。Error 不回显完整的被拒绝
expression。

### 4.6 Agent loop 组合

Native Agent 可以显式保留 policy：

1. 启动时 parse 一次 schedule；
2. 需要 catch-up 时读取持久化的 last-completed timestamp；
3. 调用 `next_after`；
4. 根据 `time.now_millis` 计算 non-negative wait；
5. 以 bounded loop sleep，从而可以观察 cancellation 或 shutdown；
6. 启动或调用实际工作；
7. 持久化 completion，再计算下一 occurrence。

应用自行决定 skip、coalesce 或 replay missed occurrence，以及是否允许工作重叠。

## 5. 备选方案

### 5.1 增加 process-global scheduler

v0.1 拒绝。它会在语言尚无 general closure 或 async task 时就要求定义 callback
storage、ownership、shutdown、overlap、panic、persistence 与 thread-safety 语义。

### 5.2 支持 local timezone

本切片拒绝。正确的 local scheduling 依赖 timezone database，并且必须明确
nonexistent 与 duplicated civil time 的行为。UTC 可移植，足以作为 Agent 基础。

### 5.3 只提供 interval timer

Monotonic interval timer 很有用，但无法覆盖 daily 或 weekly calendar work。
现有 monotonic time 与 sleep 已能让应用构造 bounded interval loop。

### 5.4 把所有 cron 工作委托给操作系统

Host cron 或 service manager 仍是有效 deployment choice，但不能支持一个动态
拥有并持久化自身 schedule 的可移植 Agent process。

## 6. 验收门

只有完成以下全部项目，RFC 0029 才可改为 `Accepted`：

1. 双语 RFC、specification、标准库文档与 source API 一致；
2. parser test 覆盖每种 grammar form、field range、malformed input 与 256-byte
   bound；
3. calendar test 覆盖 epoch、leap year、non-leap century、month end、全部
   day-field case 与 strict next-minute behavior；
4. exact search 与 timestamp boundary 有测试；
5. `CronSchedule` construction 与 private field access 被拒绝；
6. native C99 与 browser-WASM test 断言相同 result 与 error code；
7. Nomo example 展示 deterministic schedule calculation 与 application-owned
   timer-loop pattern，且无应用 C FFI；
8. pure operation 可在 isolated task 内使用；
9. generated C 保持 C99-compatible，未 import `std.cron` 的代码不获得
   cron-specific runtime support；
10. Linux、macOS 与 Windows CI 通过，commit 有签名，feature 通过 child branch
    与 PR 合并，且同步后的本地 `main` worktree 干净。

## 7. 参考资料

- [RFC 0026：隔离式 Native Task 与协作取消](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0027：内置 SQLite 持久化与 Pull-Based Query](./0027-bundled-sqlite-persistence-and-pull-queries.md)
