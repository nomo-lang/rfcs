# RFC 0036：有界 Channel、Publication Move 与静态 Select

> 语言：[English](../../en/rfcs/0036-bounded-channels-publication-moves-and-static-select.md) | 中文

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0036 |
| 标题 | 有界 Channel、Publication Move 与静态 Select |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Partially implemented（部分已实现） |
| 实现证据 | P3-A [`nomo#41`](https://github.com/nomo-lang/nomo/pull/41)、P3-B [`nomo#42`](https://github.com/nomo-lang/nomo/pull/42)、P3-C [`nomo#43`](https://github.com/nomo-lang/nomo/pull/43)；P3-D/P4 尚未实现 |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-26 |
| 主题 | channel、select、move publication、Send、backpressure、cancellation、C99 |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0035](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md) |

## 1. 摘要

本 RFC 收紧 RFC 0031 与 RFC 0033 尚未确定的源码和所有权契约。Nomo 在
`std.task` 中增加有界 `Channel<T>`，为跨任务发送的值增加编译器检查的
publication move，并增加一个由编译器识别、arm 静态枚举的 `task.select`
语句。

普通 `Array<T>`、有序 `Map<K, V>`、string、struct 与 enum 继续保持
task-local 非原子 ARC/COW。只有显式 channel control block、select winner
metadata 以及未来跨 shard wakeup 使用私有 atomic runtime shim。未使用 async
能力的同步程序继续不生成 executor、channel、select 或 atomic runtime。

本 RFC 状态为 `Proposed`。它是实现门禁，不代表 capability、channel 或
select 验收测试已经通过。

## 2. 审计与问题

RFC 0033 已要求 channel 必须有界、send 消耗值、receive 产生 owned 值、
具备 FIFO、close 唤醒、取消安全 waiter 删除以及类型化立即结果。RFC 0031
也已要求确定性 selection 与 losing registration 的 exactly-once 取消。

但这些约束仍不足以直接实现公共 API：

- channel 的精确函数及 full/close 类型化结果尚未定义；
- Nomo 尚未实现 publication move 后的 use-after-move 分析；
- send 失败或 send arm 未胜出时必须仍只有一个 value owner；
- RFC 0031 明确保留了 select arm 语法；
- affine task handle 与被 move 的 send value 缺少 loser 语义；
- channel 容量、waiter storage、browser 行为、counter 与首个可审查实现切片
  尚未固定。

如果直接按旧文本实现，compiler 会悄悄选择语言语义。本 RFC 在实现前关闭
这些缺口。

## 3. 目标与非目标

目标如下：

1. 在不阻塞 executor worker 的情况下提供有界生产/消费 backpressure；
2. 通过结构化 `Send` 检查实现真正的 consuming publication；
3. 对较小的静态 arm 集提供确定性、取消安全的 selection；
4. 在成功、full、close、cancel、timeout 和 losing-select 路径上保证
   exactly-once ownership；
5. C99 ABI 先支持 current-thread，后续可扩展到跨 owner shard，而无需修改
   源码契约；
6. native 与 browser 要么真实实现，要么在求值会被消费的值之前拒绝。

首个实现不增加：

- unbounded channel；
- process-global channel registry；
- 隐式 actor mailbox；
- 通用 future、closure、`await` 或动态拼装的 select set；
- 公共 lock-free memory ordering 控制；
- 用户可自行实现的通用 `Send` 或 `Sync` interface；
- RFC 0030 有序 `Map<K, V>` 的替代品。

## 4. 公共标准库表面

canonical source-defined 表面位于 `std.task`：

```nomo
pub struct Channel<T> {
    handle: u64
}

pub struct ChannelError {
    pub code: string
    pub message: string
}

pub struct ChannelSendError<T> {
    pub error: ChannelError
    pub value: T
}

pub enum ChannelTrySend<T> {
    Sent
    Full(T)
    Closed(T)
    Failed(ChannelSendError<T>)
}

pub enum ChannelTryReceive<T> {
    Value(T)
    Empty
    Closed
}

pub fn channel<T>(capacity: u64) -> Result<Channel<T>, ChannelError>
pub suspend fn send<T>(
    channel: Channel<T>,
    value: T
) -> Result<void, ChannelSendError<T>>
pub suspend fn receive<T>(channel: Channel<T>) -> Option<T>
pub fn try_send<T>(channel: Channel<T>, value: T) -> ChannelTrySend<T>
pub fn try_receive<T>(channel: Channel<T>) -> ChannelTryReceive<T>
pub fn close<T>(channel: Channel<T>)
```

所有函数都是 RFC 0015 下拥有 source-defined signature 与文档的
compiler-known intrinsic。当普通 Nomo 推导无法确定 `T` 时，generic type
argument 继续显式书写：

```nomo
let created: Result<Channel<string>, ChannelError> =
    task.channel<string>(64)
```

`Channel<T>` 是显式共享 runtime carrier，不是普通 COW collection。复制
handle 指向同一个有界 queue。`close` 为共享且幂等的操作，不会消费其它全部
handle。

### 4.1 容量边界

channel 容量必须在 1 到 65,536 个元素之间。经过检查的 buffer 大小（包含
slot metadata，不包含显式 channel control block）不得超过 64 MiB。乘法和
对齐必须使用 checked arithmetic。

constructor failure 使用有界、secret-safe code：

| code | 含义 |
| --- | --- |
| `invalid_capacity` | capacity 为零 |
| `capacity_limit` | 元素数或 checked byte size 超过 v0.1 边界 |
| `allocation` | 无法分配有界 control block 或 buffer |
| `runtime_unavailable` | target 没有 channel backend |

错误消息不得包含 queued value、string 内容或派生 debug representation。

## 5. Publication Move 契约

`task.send`、`task.try_send` 和 `task.select` 的 send arm 对 value argument
而言都是 consuming publication boundary。随着 RFC 0033 落地，同一套
dataflow machinery 也适用于结构化 `task.spawn` argument。

本 RFC 不增加 `move` keyword。是否消费由 compiler-known parameter
position 决定：

```nomo
let message: string = build_message()
let sent = task.send(channel, message)
// error E0881：message 已被 channel publication 消费
```

Copy primitive 可以复制进入 publication boundary。命名的 non-copy binding
在 boundary 后的所有 continuation path 上都不可用。temporary 不存在后续
source use。

Publication 必须具备事务性：

1. 根据 compiler-known `Send` rule 递归验证 value；
2. 把 logical ownership move 到 operation-local rollback slot，并把 source
   binding 标为不可用；
3. 在 rollback slot 仍是唯一 owner 时准备所有必要的 COW detach，并执行
   message bound；
4. 成功时清除 rollback owner，并在跨 shard 时用一个 release/acquire edge
   发布；失败时把 rollback value move 进类型化 outcome。

唯一 COW backing 在不复制元素的情况下 move。存在 alias 的 backing 在发布
前 detach，确保 destination 不会与 source task 共享普通非原子 backing。

如果 publication preparation 失败，consuming operation 返回一个拥有该
logical value 的 `ChannelSendError<T>`。原 binding 仍不可用，但调用方可以
显式恢复 `error.value`。`ChannelTrySend.Full(value)` 与
`ChannelTrySend.Closed(value)` 使用相同规则。任何路径都不得同时保留原
binding 并返回 value。

这收紧了 RFC 0033 的事务性表述：preparation 不得部分发布或丢失 logical
value，但 source-language binding 在 compiler-known boundary 处无条件被
消费。v0.1 不会让 binding availability 取决于之后 match 到的 runtime
outcome。

对于挂起 send，pending coroutine frame 拥有已准备 value。task cancellation
或 panic 将其 drop 一次。close wakeup 通过 `ChannelSendError<T>` 返回它。
成功交付必须先清除 frame ownership bit，再让 receiver 或 buffer 成为 owner。

## 6. Channel 语义

### 6.1 Send 与 receive

`send` 行为如下：

- 已有 receiver 等待时，直接把 ownership 交给最早的 eligible receiver，
  不经过 buffer 完成 send；
- 否则 ring 有容量时，把 value 追加到末尾并完成；
- 否则 sender 以 FIFO 顺序注册一次并挂起；
- 交付前 channel close 时，恢复为
  `Err(ChannelSendError { error.code: "closed", value })`；
- structured task cancellation 按 RFC 0031 终止 sending task，并 drop
  frame-owned value，而不是返回 user code。

`receive` 行为如下：

- buffer 中存在 value 时，移除并返回最早 value；
- 否则有 sender 等待时，直接取得该 sender 的 value；
- 否则 channel 已关闭时返回 `None`；
- 否则注册一次并挂起。

close 后 buffered value 仍可接收。因此 `None` 表示“已关闭且已 drain”，
绝不只是“当前为空”。

### 6.2 立即操作

`try_send` 从不挂起：

- `Sent` 表示 receiver 或 buffer 已拥有 value；
- `Full(value)` 表示 open channel 当前无容量；
- `Closed(value)` 表示 channel 已关闭；
- `Failed(error)` 表示 publication preparation 失败。

`try_receive` 从不挂起：

- `Value(value)` 包含一个 owned value；
- `Empty` 表示 open 且当前没有可用 value；
- `Closed` 表示已关闭且已 drain。

### 6.3 Close 与销毁

`close` 只 linearize 一次，唤醒所有 pending receiver 与 sender，并且幂等。
pending receiver 先 drain 已经 linearize 进入 buffer 的 value；剩余
receiver 得到 `None`。尚未交付 value 的 pending sender 得到类型化 closed
结果。

channel handle 保持显式 control block 存活。wait registration 在 linked
期间持有 runtime reference，因此 waiter 仍指向 channel 时不可能 final
destroy。final destruction 必须 exactly-once drop 所有 buffered value。

FIFO 对 ring、单一 sender 的发送以及单一 receiver 的接收是强制要求。
竞争 producer/consumer 按 registration linearization 排序；不承诺 OS
scheduling order。

## 7. 静态 Select 语句

`task.select` 是拥有 2 到 8 个 source arm 的 compiler-recognized statement：

```nomo
task.select {
    task.receive(inbox) => received {
        if let Some(message) = received {
            io.println(message)
        }
    }
    task.sleep(time.duration_millis(250)) => elapsed {
        let checked: Result<void, TaskError> = elapsed
        io.println("idle")
    }
}
```

每个 arm 包含一个允许的 operation、`=>`、一个新的 immutable result
binding 和一个 lexical block。binding type 从 operation 推导：

| operation | binding type |
| --- | --- |
| `task.receive(channel)` | `Option<T>` |
| `task.send(channel, value)` | `Result<void, ChannelSendError<T>>` |
| `task.sleep(duration)` | `Result<void, TaskError>` |
| `task.join(child)` | `Result<T, TaskError>` |

arm 不是 closure，不能存储或动态追加。任意 suspend call、嵌套
`task.select` descriptor、`task.scope` 与 `task.deadline` 都不是 selectable
operation。

### 7.1 求值与 winner 顺序

Select 从上到下把 operation operand 求值一次，期间不挂起。然后先检查
cancellation 与 effective deadline，再观察 arm readiness。

如果一个或多个 arm 已 ready，则 source 中最前面的 arm 获胜。否则每个 arm
最多注册一次，parent task 挂起。只能有一个 arm 把 shared select token 从
pending 转换为 won。其 block 运行前，每个 losing registration 都必须被删除
或标记为无法获胜。

在 resume boundary 可见的 inherited cancellation 或 deadline 先于 arm
result 获胜，包括 operation 恰好在 effective deadline ready 的情况。这与
RFC 0031 deadline ordering 一致。

close、send、receive、timer、join 与 cancellation race 各自只有一个
linearization point。late wakeup 经过 generation 检查，不得运行 losing arm
或复用后的 frame。

### 7.2 Losing arm 的 ownership

receive 或 timer arm 不拥有尚未发布的 application value。取消它只需删除
registration。

send-arm value 在准备 select frame 时被消费。如果该 arm 获胜，成功会转移
它，或 arm binding 得到拥有该 value 的类型化失败。如果该 arm 未胜出，
select cleanup 从 registration 把 value 取回 select frame，并 exactly-once
drop；它不会重新使原 source binding 可用。

join arm 中命名的 affine task handle 在 select statement 后不可用。获胜
join 正常消费它。losing join registration 不取消 child；ownership 返回
surrounding structured scope，供强制 implicit cleanup 使用。这是为了避免
v0.1 出现 path-dependent source binding use。

首个实现切片可以先支持 receive 与 sleep arm，再支持 send 与 join arm；但
unsupported shape 必须产生 compile-time diagnostic，不得只在某个 backend
接受。

### 7.3 Arm 控制流

最终语义允许 selected arm fallthrough、`return`、传播 `?` 或 panic。在任何
此类 exit 前都必须清理 losing registration 与 staged value。较小实现切片
可以先在 E0876 下只允许 flat fallthrough arm body，但在所有 exit 共用已验证
drop plan 前，本 RFC 不得转为 `Accepted`。

## 8. Capability 规则

只有 `T` 满足 compiler-known `Send` 时才存在 `Channel<T>`。用户代码不能
不安全地自行实现 `Send`。

- immutable numeric、Boolean 与 character value 是 copyable 且 `Send`；
- owned string、array、有序 map 与 aggregate 通过 consuming publication
  和 recursive detach 成为 `Send`；
- `Frozen<T>` 与显式 shared carrier 遵循 RFC 0033；
- socket、HTTP stream、process、SQLite、query、FFI pointer、borrowed
  value、mutable borrow、guard 与 owner-reactor handle 保持 `Local/!Send`，
  除非后续 RFC 提供 exclusive transfer operation；
- 当 element contract 有效时，`Channel<T>` 自身作为显式 shared handle 是
  `Send + Sync`。

普通 COW value 不会因此成为 `Sync`，本 RFC 也不会给普通 collection 加锁。

## 9. C99 Lowering 与 Runtime

每个单态化 channel element type 获得私有 helper，用于：

- publication preparation 与 detach；
- move 进入或移出 ring slot；
- exactly-once slot/frame drop；
- 可选 debug-only type identity。

channel control block 包含 checked ring、closed state、handle count，以及
sender/receiver waiter 的 intrusive FIFO head/tail。wait node 存在于
coroutine/select frame，因此等待不会为每次 suspension 分配一个 heap node。
registration 与 cancellation 必须 exactly-once unlink。

current-thread operation 可以使用 owner-local 非原子 queue mutation。显式
shared lifetime metadata 与 cross-shard publication 使用 RFC 0032 私有 C99
atomic shim。GCC/Clang `__atomic_*` 与 Windows Interlocked 都只是 runtime
实现细节；普通 generated value 不包含 atomic field。

select frame 包含一个有界 arm registration array、一个 winner token、
selected arm result storage、staged ownership bit 与 continuation state。ready
fast path 不 enqueue、不 allocate。真正 pending 的 select 复用 enclosing
coroutine frame，并且 wake 时最多进入一次 owner ready queue。

禁止 process-global unsynchronized handle registry。

## 10. 错误与诊断

本 RFC 使用 RFC 0033 已有 code，并增加两个 select-shape code：

| code | 条件 | 必须提供的 help |
| --- | --- | --- |
| `E0880` | `Local/!Send` value 跨 spawn 或 channel publication | 指出首个 non-Send field 或 handle |
| `E0881` | publication move 后继续使用 binding | 指向 consuming source boundary |
| `E0883` | structural `Send` 推导失败 | 展示阻止推导的 field/path |
| `E0886` | select arm 数、语法或 operation 不合法 | 列出受支持的 static operation |
| `E0887` | affine join handle 或 moved send value 逃逸 select ownership rule | 解释 winner/loser ownership |

runtime channel error 使用 `closed`、`transfer_limit`、`capacity_limit`、
`allocation` 和 `runtime_unavailable` 等稳定 code。message 必须有界，且绝不
格式化 transferred value。

compiler、formatter、标准库文档、LSP semantic data、中英文诊断页与 browser
capability error 必须一致。

## 11. 平台与 Browser 契约

Linux、macOS/BSD 与 Windows 必须提供相同 source ordering、close、capacity
和 ownership 行为。平台 atomics 可以有内部差异。

Browser WASM 在 channel/select 支持启用时使用 host-driven current-thread
executor。缺少支持的 backend 必须在求值 constructor argument、send value
或会被消费的 select arm operand 之前返回或报告 `runtime_unavailable`。不得
运行顺序式“第一个 arm”近似实现。

## 12. 验收门禁

### 12.1 语义与 ownership 门禁

测试必须覆盖：

- structural `Send` 推导与首个失败 field path；
- straight-line 与 branch control flow 上的 use-after-publication-move；
- unique COW 零复制 publication 与 aliased recursive detach；
- full、closed 与 transfer-limit outcome 的类型化 value 恢复；
- failure 时不存在重复 retain/release 或 partially published value。

### 12.2 Channel 正确性门禁

测试必须覆盖：

- 精确 element 与 byte capacity 边界；
- FIFO wraparound 与 sender-to-receiver direct handoff；
- full/empty 立即结果；
- buffered 状态 close、blocked send、blocked receive 与 repeated close；
- registration 前、linked 期间与 wake 后的 cancellation；
- ASan/UBSan 下的 root/child drop、panic、timeout 与 queue saturation；
- sharded executor 存在后的 TSAN cross-shard stress。

### 12.3 Select 正确性门禁

测试必须覆盖：

- 多个 pre-ready arm 的 source-order choice；
- send/receive/timer/join race 下只有一个 winner；
- resume 时 cancellation 与 deadline priority；
- losing registration removal 与 late-event rejection；
- losing send-value 与 losing join-handle cleanup；
- winner 后的 `return`、`?`、panic 与 frame drop；
- 固定 arm-count 与 registration-memory bound。

### 12.4 性能与 no-cost 门禁

counter catalog 至少增加：

- channel construction 与 close transition；
- buffered send/receive 与 direct handoff；
- send/receive suspension；
- publication detach 与 copied byte；
- select registration、immediate win、suspended win 与 loser cancellation；
- live/peak buffered element 与 waiter。

RFC 0034 bounded-channel workload 使用固定 Go baseline 测量 same-shard 与未来
cross-shard throughput、backpressure、fairness、p50/p99/p999 latency、RSS 与
cancellation storm。这些 measurement 是证据，不是预先声明的性能结论。

sync-only 程序以及从未构造 channel/select 的 async 程序不得包含 channel
storage、atomic shim call 或 select metadata。

## 13. 实现阶段

实现拆为可审查的小 PR：

1. **P3-A capability 与 move dataflow——由
   [`nomo#41`](https://github.com/nomo-lang/nomo/pull/41) 实现：** compiler-known `Send` 推导、
   publication move/use-after-move 分析、IR ownership bit 与测试；尚不公开
   channel。
2. **P3-B current-thread channel——由
   [`nomo#42`](https://github.com/nomo-lang/nomo/pull/42) 实现：** constructor、send/receive、try operation、
   close、managed-value detach/drop、counter 与 native/browser capability gate。
3. **P3-C static receive/timer select——由
   [`nomo#43`](https://github.com/nomo-lang/nomo/pull/43) 实现：** 精确 parser/formatter form、immediate
   source ordering、pending registration、cancellation、deadline 与 loser
   cleanup。
4. **P3-D send/join select——计划中：** staged moved value、affine join ownership、early
   exit 与完整诊断。
5. **P4 cross-shard publication——计划中：** 私有 atomic shim、owner wakeup、stress test
   与 per-core 证据。

在实现、cross-platform CI、sanitizer test、browser contract 和 RFC 0034
benchmark gate 全部通过前，RFC 0031、0033 与本 RFC 都保持 `Proposed`。合并
本文档不会把其中任何一个标为 `Accepted`。

## 14. 备选方案

| 备选 | 不选择的原因 |
| --- | --- |
| unbounded channel | 隐藏 memory growth，并移除 backpressure |
| 给所有普通 collection 加锁 | 让非并发代码承担同步成本，并破坏 task-local ARC/COW model |
| 动态分配 future array | 需要 futures/closure model 与无界 registration storage |
| `select2`、`select3`、`select4` 函数 | 暂时绕过语法，但产生 heterogeneous carrier type，且无法表达 arm-local control flow |
| 先 poll readiness 再执行 operation | 在观察与消费之间引入 race |
| 把 losing send value 恢复到原 binding | 需要 v0.1 其它位置不存在的 path-dependent binding availability |
| 对 losing join arm 取消 child task | 混淆 wait registration cancellation 与 child cancellation |
| browser 静默退化为顺序执行 | 违反 selection 与 cancellation 语义 |

## 15. 风险

对于存在 alias 的 nested COW value，publication detach 可能昂贵。counter 与
message bound 让该成本可见。cross-shard channel correctness 明显比
current-thread 切片更难，因此必须经过 atomic shim 与 stress evidence 门禁。

即使没有 `move` keyword，consuming call position 仍是新的 dataflow 义务。
诊断必须清楚展示 boundary。如果真实使用证明这过于意外，后续 RFC 可以增加
显式 ownership annotation，但实现不得在评审前自行发明语法。

## 16. Proposed 决策

采纳本 RFC 的精确 bounded channel API、隐式 compiler-known publication
move，以及 static `task.select` arm 语法。先实现 capability/move checking，
再实现 current-thread channel，然后实现 receive/timer selection，之后再处理
send/join arm 与 cross-shard 优化。

## 17. 参考

- [RFC 0031：直写式挂起函数与结构化并发](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032：分片 Executor、Reactor 与 Blocking Pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033：任务所有权转移与并发值](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034：异步 Runtime 验收与基准门禁](./0034-async-runtime-acceptance-and-benchmark-gates.md)
- [RFC 0035：单调时钟挂起 Timer 与阻塞 Sleep 迁移](./0035-monotonic-suspend-timers-and-blocking-sleep-migration.md)
