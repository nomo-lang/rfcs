# RFC 0035：单调时钟挂起 Timer 与阻塞 Sleep 迁移

> 语言 / Language: 中文 | [English](../../en/rfcs/0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0035 |
| 标题 | 单调时钟挂起 timer 与阻塞 sleep 迁移 |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Implemented（已实现） |
| 实现证据 | blocking gate [`nomo#26`](https://github.com/nomo-lang/nomo/pull/26)、owner-local timer [`nomo#28`](https://github.com/nomo-lang/nomo/pull/28)、deadline/cancellation [`nomo#40`](https://github.com/nomo-lang/nomo/pull/40) |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 关联主题 | suspend function、timer、monotonic clock、取消、blocking compatibility、C99 |
| 关联 RFC | [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md)、[RFC 0029](./0029-bounded-utc-cron-schedule-calculation.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. 摘要

Nomo 增加唯一一个使用单调时钟、可挂起的 timer 操作：

```nomo
pub suspend fn sleep(duration: Duration) -> Result<void, TaskError>
```

该声明位于 `std.task`，caller 以 `task.sleep` 调用。`task.sleep` 参与 RFC 0031
的 direct-style suspend effect，并使用 RFC 0032
owner-local timer wheel。非正 duration 在当前 poll 内直接完成，不分配、不注册、
不入队也不 yield。正 duration 注册一个有界 timer 并返回 `PENDING`；不早于其
monotonic deadline 恢复。

现有同步 `time.sleep` 与 `time.sleep_millis` 在 preview 迁移窗口内继续供普通
同步代码和 RFC 0026 compatibility worker 使用。它们属于已知阻塞操作；从
`suspend fn` 直接或间接可达时必须拒绝。这样既不会让阻塞调用占住 async
worker，也不会在 coroutine 模型尚未覆盖 legacy `task fn` 时强行迁移旧代码。

本 RFC 状态为 `Proposed`。它是实现门禁，不表示 timer wheel 或 suspend timer
已经交付。

## 2. 背景与动机

RFC 0031/0032 要求 timer wheel、deadline、取消和 ready fast path，但尚未确定
公开 sleep API，也没有说明如何从已经实现的同步 `std.time` 函数迁移。

当前实现包含：

- 同步 `time.sleep(Duration)`；
- 同步 `time.sleep_millis(i64)`；
- 作为首个 suspend runtime primitive 的 `task.yield_now()`；
- 有意在 async executor 之外使用 blocking sleep 的 legacy `task fn` worker
  和 cron 示例；
- 尚无 timer registration、timer wakeup 或 cancellation-safe timer state。

直接把 `time.sleep` 改成 `suspend fn`，会在 bounded blocking pool 可用前破坏
普通程序、cron 示例和 RFC 0026 worker；允许它继续从 `suspend fn` 调用，又会
阻塞无关 async task。同时增加 `time.sleep_async` 与 `task.sleep_millis` 会重复
API，并在已有 `Duration` 类型时继续把单位写进操作名。

因此，timer slice 必须在实现前明确 suspend operation 与 compatibility rule。

## 3. 详细设计

### 3.1 公开 API

`std.task` 增加：

```nomo
import std.result
import std.time.Duration

pub suspend fn sleep(duration: Duration) -> Result<void, TaskError>
```

典型调用仍保持 direct-style：

```nomo
package agent

import std.result
import std.task
import std.time

suspend fn heartbeat() -> Result<void, TaskError> {
    task.sleep(time.duration_seconds(1))?
    return Ok()
}
```

本 API 有意不增加 `task.sleep_millis`。caller 使用 `time.duration_millis` 或
`time.duration_seconds` 构造 `Duration`，让单位集中由一个标准类型表达，避免
平行 timer surface。

`TaskError` 继续使用稳定公开的 `code` 与 `message` 字段。suspend timer 可返回：

| code | 含义 |
| --- | --- |
| `timer_limit` | owner executor 的有界 timer capacity 已耗尽 |
| `runtime` | target timer backend 无法正确注册或等待 |

消息必须有界，且不含源码值或 secret。非正 duration 不是错误；它通过 ready
fast path 返回 `Ok()`。

### 3.2 Effect 与阻塞规则

`task.sleep` 是 `suspend fn` intrinsic：

1. 同步 `fn` 不能调用它，并收到 E0870；
2. `suspend fn` 不写 `await`，直接调用；
3. 此调用是 liveness、borrow、frame drop、取消和 affinity 检查中的可能挂起点；
4. generic 和跨 module call summary 保留 suspend effect。

现有 `time.sleep` 与 `time.sleep_millis` 在一个有文档的 preview 迁移窗口内继续
作为同步 compatibility operation。它们被分类为 known blocking intrinsic。
`suspend fn` 不能直接或通过同步 helper 调用它们；E0891 报告完整 call path，并
建议使用 `task.sleep`。

RFC 0026 的 `task fn` worker 不是 suspend function，在迁移到 RFC 0032 bounded
blocking pool 前可继续使用同步操作。compatibility function 必须标注为
blocking，不能作为 async 代码的逃生口。

### 3.3 时间语义

`task.sleep` 使用 monotonic clock。wall-clock 校时、时区修改和夏令时变化都不
改变 deadline。

- `duration.millis <= 0`：立即返回 `Ok()`；
- `duration.millis > 0`：计算经过检查并饱和处理的 monotonic deadline，注册一个
  当前 executor shard 拥有的 timer；
- expiry 只让 task 具备运行资格，不承诺在 deadline 时刻精确调度；
- task 只会在 deadline 之后，并按 executor fairness policy 处理 already-ready
  work 后恢复；
- 超长 duration 可以按有界 timer-wheel round 重新插入，不改变逻辑 deadline。

该操作不能 busy-poll。没有 ready task 时，native executor 等到最早 timer 或
reactor event；browser host 记录 deadline 并请求 host wakeup，不能在 WebAssembly
内部自旋。

### 3.4 取消与 Drop

每个 pending sleep 只拥有一个经过 generation check 的 timer registration。

- parent/scope cancellation 在 drop coroutine frame 前 disarm registration；
- expiry 与 cancellation 通过一个 owner-local terminal transition 竞争；
- cancelled 或已复用 slot 的 late event 由 generation 忽略；
- timer registration 和 frame 拥有的 `Duration` 值都只释放一次；
- drop 已完成或已取消 frame 必须幂等。

取消按照 RFC 0031 终止被取消 task。被取消的 `task.sleep` body 不以可被用户忽略
的 `Err` 恢复；观察方 `task.join`/scope operation 报告 typed `cancelled` task
outcome。`timer_limit` 与本地 backend registration failure 发生在 operation
进入 pending 前，并向当前 task 返回 `Err(TaskError)`。

deadline 后续复用同一个 timer-registration primitive，但 `task.deadline` scope
语法和 timeout result typing 仍由 RFC 0031 structured-scope 阶段决定。

### 3.5 Executor 与 C99 Lowering

对于可能 pending 的 sleep，生成的 C99 frame 只包含该 call site 所需状态：

```c
typedef struct {
    uint32_t slot;
    uint32_t generation;
    int64_t deadline_millis;
    uint8_t armed;
} nomo_async_timer_registration;
```

精确 layout 和 symbol name 属于 toolchain-private。lowering 必须：

1. duration 只求值一次；
2. 非正值走 inline ready path；
3. 尝试保留一个有界 owner-local timer slot；
4. 在返回 `PENDING` 前写入并 arm registration；
5. 后续 poll 验证 generation 与 terminal state；
6. 在产出 `Ok()` 或转移 cleanup 前清除 `armed`；
7. cancellation/frame drop 使用相同幂等路径 disarm。

executor 必须区分 cooperative yield 与 reactor/timer pending。
`task.yield_now` 把当前 task 放入 FIFO ready queue；`task.sleep` 不能立即重新入队，
只能由 timer expiry 调度。只含 ready operation 的程序不初始化 timer storage；
zero-duration sleep 不入队也不分配。

首个 native current-thread 实现只可在 ready queue 为空时通过 platform
monotonic facility 等待。Linux `epoll`、macOS/BSD `kqueue`、Windows IOCP 和
browser host-driven 集成后续共享 RFC 0032 的同一 registration contract。

### 3.6 与结构化并发的交互

timer 继承当前 task 的 owner shard、cancellation token 和最早 parent deadline。
armed 期间不能跨 shard 移动。sleeping child 在自身 owner shard 创建 timer；
parent 不直接 poll 或 close 该 registration。

只有在 non-winning registration cleanup 和 typed outcome rule 落地后，
`task.select`/`task.deadline` 才可组合同一 primitive。本 RFC 不引入 detached
timer、callback、global scheduler 或 cron execution。

## 4. 类型检查规则

compiler 必须：

- 仅通过 `std.task` 或 specific import 解析 `task.sleep`；
- 要求恰好一个 `Duration` 参数；
- 把结果类型设为 `Result<void, TaskError>`；
- 应用 suspend-call E0870；
- 将调用加入 suspension-point liveness；
- 对跨 sleep 的非法 mutable borrow、guard、host view 或 affine handle 报 E0873；
- 对 suspend function 直接/间接调用 blocking `time.sleep*` 报 E0891；
- 保持普通 `fn` 与 legacy `task fn` compatibility worker 使用同步
  `time.sleep*` 合法。

不增加 integer milliseconds 到 `Duration` 的隐式转换。

## 5. 标准库影响

`std.task` 增加 `task.sleep` 的源码声明与 intrinsic identity；`std.time.Duration`
继续作为唯一 public duration type。`std.time.sleep` 与
`std.time.sleep_millis` 明确记录为同步阻塞 compatibility operation。

生成文档、semantic/LSP signature、import completion 与 diagnostic example
必须显示 suspend effect 和 `Result<void, TaskError>` 返回类型。

## 6. 诊断影响

| code | 条件 | 必需指导 |
| --- | --- | --- |
| `E0870` | 同步代码调用 `task.sleep` | 将 call chain 标记为 `suspend` |
| `E0873` | 非法 borrow/guard/affine view 跨 timer | 在 sleep 前结束它 |
| `E0891` | suspend call chain 到达 blocking `time.sleep*` | 使用 `task.sleep`，或把完整操作移到 bounded blocking pool |
| 现有 type/arity code | duration 错误、缺 import 或 required shape 错误 | 指明预期的 `Duration` 和 `Result<void, TaskError>` |

诊断不能建议用 `time.sleep*` 绕过 async 规则。

## 7. 测试与验收计划

正向 compiler/C99 测试覆盖：

- 非正值 ready completion，且零 allocation/enqueue/registration；
- 正 timer 排序且不提前 wake；
- 相同 deadline timer 的确定性 FIFO tie-breaking；
- direct/transitive suspend call chain；
- managed local 跨 sleep 和 exactly-once frame drop；
- pending 前 `timer_limit` 及 capacity 释放后的恢复；
- expiry 前取消、expiry/cancel race、late event、slot generation reuse 和重复 drop；
- native current-thread 执行不 busy-poll；
- host-driven browser WASM wakeup；
- 未使用 async timer 时同步 `fn` codegen 不变。

负向测试覆盖 E0870、E0873、带 transitive call path 的 E0891、错误参数和非 owner
使用 timer registration。

sanitizer/debug counter 必须证明无 timer、frame、buffer 或 managed-value leak。
RFC 0034 benchmark 记录 zero-duration latency、timer insert/expiry、idle
suspended-task RSS、cancellation storm、idle CPU，以及单核低内存和普通 host 的
p50/p99/p999 wake latency。

platform CI 必须在 Linux、macOS、Windows 执行 native timer behavior；cross-build
不足以验收。browser 测试必须证明 host wakeup 和有界 memory/fuel。

## 8. 兼容性影响

本提案增加 `task.sleep`，不改变现有同步源码签名。source break 只发生在
`suspend fn` 调用 known-blocking `time.sleep*`；该行为本就不符合新 executor
契约，E0891 提供直接迁移指导。

同步 sleep 的 preview compatibility window 只有在 bounded blocking pool 及其
显式应用 surface 完成文档和实现后才能结束。删除或重命名 `time.sleep*` 需要
后续 RFC；本 RFC 不偷偷改变它们的 effect。

## 9. 备选方案

| 备选 | 不选择原因 |
| --- | --- |
| 原地把 `time.sleep*` 改为 suspend | 在 blocking compatibility path 存在前破坏普通代码和 RFC 0026 worker |
| 允许 async worker 调用 `time.sleep*` | 阻塞无关 task，违反 RFC 0032 |
| 增加 `time.sleep_async` | effect 已在 signature 中表达，`async` 后缀重复信息 |
| 增加 `task.sleep_millis` | 与 `Duration` 已提供的单位构造重复 |
| 返回 `void` | 无法报告有界 timer capacity 或本地 registration failure |
| busy-poll monotonic clock | 浪费 CPU，无法满足低功耗/低内存验收 |
| 在本 RFC 实现 cron callback | 混淆 RFC 0029 的纯 schedule calculation 与进程调度/持久化 |

## 10. 缺点与风险

compiler 除 suspend-effect analysis 外，还必须增加 transitive known-blocking
analysis。executor 必须停止把每个 `PENDING` poll 都当成立即 ready-queue yield。
timer cancellation 与 generation reuse 引入 race-sensitive lifecycle state，
需要 native platform test。

preview 窗口内保留同步 sleep，会暂时存在执行模型不同的两个 operation；文档和
E0891 必须明确区分。

## 11. 未决问题

没有问题阻塞第一实现 slice。同步 `time.sleep*` 最终删除或改名、
`task.deadline` 最终 block syntax，以及 public executor configuration，分别
延后到 migration 与 structured-concurrency RFC 工作。

## 12. 最终决定

**提议决定：**把 `task.sleep(Duration) -> Result<void, TaskError>` 作为第一版
唯一 suspend timer；使用 monotonic、有界、owner-local、cancellation-safe
registration，并提供非正 duration 的 zero-cost ready path；在 async worker 上
transitively 拒绝同步 `time.sleep*`，同时在 preview 迁移期为普通与 legacy
blocking code 保留它们。

在实现、native/browser 平台测试、sanitizer lifecycle gate、文档与 RFC 0034
benchmark evidence 完成前，本 RFC 保持 `Proposed`。

## 13. 参考

- [RFC 0026：隔离原生任务与协作式取消](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0029：受限 UTC Cron Schedule 计算](./0029-bounded-utc-cron-schedule-calculation.md)
- [RFC 0031：直写式挂起函数与结构化并发](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032：分片 Executor、Reactor 与 Blocking Pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0034：异步 Runtime 验收与基准门禁](./0034-async-runtime-acceptance-and-benchmark-gates.md)
