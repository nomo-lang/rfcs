# RFC 0033：任务所有权转移与并发值

> 语言 / Language: 中文 | [English](../../en/rfcs/0033-task-ownership-transfer-and-concurrent-values.md)

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0033 |
| 标题 | 任务所有权转移与并发值 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 关联主题 | Send、Sync、Local、Freeze、move、channel、lock、concurrent collection、ARC、COW |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md)、[RFC 0019](./0019-typed-ffi-handles-callbacks-and-bindings.md)、[RFC 0030](./0030-collection-literals-indexing-and-ordered-map.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md)、[RFC 0036](./0036-bounded-channels-publication-moves-and-static-select.md) |

## 1. 摘要

Nomo 普通值与 collection 继续使用 task-local non-atomic ARC/COW。跨 task 边界
要求真正的 move，并由编译器内建 `Send`、`Sync`、`Local`、`Freeze`
capability 检查。unique COW backing 可零拷贝 move；有 alias 时先 detach，再
publish，确保 non-atomic storage 永不跨 worker 共享。

只读共享通过显式 `Frozen<T>`/`Shared<T>` 实现，只有这类 storage 使用 atomic
RC。共享修改必须显式使用 async-aware `Mutex<T>`/`RwLock<T>`、bounded channel
或专用 concurrent container。普通 `Array<T>`、RFC 0030 ordered `Map<K,V>`、
未来 `HashMap`/`Set` 与 string 不增加 hidden lock 或 atomic RC。

本 RFC 是 `Proposed`；文档不等于 capability inference、transfer lowering 或
concurrent container 已经实现。

## 2. 动机与现状

RFC 0003 为可预测的单线程值语义选择 non-atomic RC/COW。RFC 0026 通过在线程
边界 copy string，并限制 task 内 stdlib 调用来保持安全，但该边界无法满足 typed
structured task 与高吞吐 message passing。

给所有 RC 改 atomic 或所有 collection 内置锁，会让同步程序为未使用的并发付费；
也会让 compound operation 看似安全但仍存在 race。Nomo 需要显式 publication
rule 与专用 shared abstraction。

RFC 0030 接受使用 bounded linear index 的确定性 insertion-ordered `Map<K,V>`，
并有意不定义 `Hash`/`Eq` 或 `HashMap`。并发工作必须保留该契约。

## 3. Capability 模型

第一版使用编译器内建 capability：

| Capability | 含义 |
| --- | --- |
| `Send` | owned value 可以通过规定的 move-publication 操作跨 task/shard |
| `Sync` | type 的显式 shared representation 可在其 API 约束下由多个 task 访问 |
| `Local` / `!Send` | value 固定在一个 executor/host context，不能跨 task |
| `Freeze` | 消耗 value 后可生成 immutable shareable snapshot |

这些名称在 v0.1 是保留语义 capability，不是用户可不安全实现的普通 interface。
编译器按 struct/enum 所有 field 结构化推导；host handle 由 toolchain 声明。

primitive immutable scalar 是 `Send + Sync + Freeze`。function value 只有在没有
environment 且 ABI 允许时才 `Send`。raw/borrowed FFI pointer、mutable borrow、
lock guard、socket/stream/process/SQLite handle 与 executor registration 是
`Local`。

所有 field 都可 publish 时 owned struct/enum 为 `Send`；所有 field 都可 freeze
时为 `Freeze`。普通 COW collection 通过 consuming publication 成为 `Send`，
不会因 element immutable 就自动 `Sync`。

## 4. Move Publication

`task.spawn`、channel send 和少量符合条件的 cross-shard scheduler move 是
publication boundary。source binding 被消耗，之后不可使用。

对 non-atomic COW backing：

1. backing unique 时，ownership 零 element copy 移到 destination；
2. 存在 local alias 时，在 enqueue 前 detach/deep-copy 要移动的 logical value；
3. destination 得到 source-task alias 不再引用的 backing；
4. queue publication 使用 atomic shim 的 release/acquire edge。

该规则递归应用于 string、array、ordered map 与 aggregate field。编译器只在
cross-task boundary 生成 type-directed `publish_move` helper；普通赋值保持已有
local ARC/COW 行为。

detach 若会超过配置的 collection/message bound，则返回 typed `TransferError`，
不得部分 move。

## 5. Frozen 与 Shared Value

`freeze(value)` 消耗 `T: Freeze`，返回 `Frozen<T>`，其 immutable representation
为 `Send + Sync`。ordinary backing unique 时，runtime 可以把 payload 移入 atomic
shared control block 而不复制 element；有 alias 时先 detach。

`Shared<T>` 是 runtime/shared primitive 使用的显式 atomic ownership carrier。
`Frozen<T>` 只暴露只读操作，不提供 mutable COW method。thaw 只能消耗 uniquely
held frozen value，或创建 detached task-local `T`。

atomic RC 只存在于这些显式 shared control block 与 runtime/channel metadata。
overflow 是 panic-level defect；decrement-to-zero 使用 acquire/release destruction。
nested ordinary value 在共享期间 immutable，并由最后 owner drop 一次。

## 6. Bounded Channel 与 Select

`Channel<T: Send>` 构造时必须给出容量。send 消耗 `T`，receive 产生 owned `T`。
full sender 与 empty receiver 挂起而不阻塞 executor worker。`try_send`/
`try_receive` 返回 typed immediate outcome。close 唤醒所有 waiter；已 buffer 的
message 仍可 receive，之后 send 失败。

实现可为 same-shard channel 使用无 atomic 优化，但跨 shard 行为与 ordering
一致。每个 waiter 只注册一次，取消只移除一次，一个 value 最多交给一个 receiver。
同一 sender 和单 receiver 要求 FIFO；不承诺 global multi-producer schedule order。

RFC 0031 的 `task.select` 可选择 channel send/receive、timer、task join 与 reactor
operation。registration、winner election、losing-arm cancellation 与 moved-value
recovery 必须 atomic 且 exactly once。

RFC 0036 固定这些要求的 source-defined channel API、带类型化 rollback owner 的
无条件 consuming-binding rule、static select arm 语法、capacity bound 与分阶段
验收门禁。

## 7. Lock 与 Guard

`Mutex<T: Send>` 与 `RwLock<T: Send + Sync>` 是显式 shared container。acquire 是
async-aware，可能在返回 guard 前挂起；waiter 必须有界，或受 admission
backpressure 控制。

guard 是 `Local`、noncopyable，且不能跨任何挂起点。编译器同时报告 guard origin
与 suspend call。unlock 在 lexical end、explicit consume、`?`、early return、
cancellation cleanup 与 panic cleanup 时确定性执行。

以下代码被拒绝：

```nomo
let guard = mutex.lock()
http.send(request) // error: guard would cross a suspension point
```

程序应 copy/move 所需的 task-local value，释放 guard，再 suspend。runtime 内部可
使用私有短临界区锁，但不是公共 async lock API。

## 8. Collection

### 8.1 普通 collection

- `Array<T>`、ordered `Map<K,V>`、未来 `HashMap<K,V>` 与 `Set<T>` 保持
  task-local non-atomic ARC/COW；
- 不含 hidden mutex；
- shared dynamic-array mutation 使用 `Mutex<Array<T>>`；
- producer/consumer 使用 bounded `Channel<T>` 或 `ConcurrentQueue<T>`；
- 不提供通用 `ConcurrentArray`。

### 8.2 Hash 前置条件

独立 Accepted RFC 定义稳定 `Hash + Eq` coherence、numeric/string rule、
user-type derive/implementation、hash-flood policy 与 deterministic testing 前，
不得交付 `HashMap`、`HashSet`、`ConcurrentHashMap` 或 `ConcurrentSet`。
RFC 0030 ordered `Map` 继续 insertion ordered，不改名或重实现为 hash map。

### 8.3 专用 concurrent container

hash contract 落地后：

- `ConcurrentHashMap<K,V>` 第一版使用 bounded shard lock；
- 提供 compound `entry`、`compute`、compare-and-swap/replace、remove-if API，
  避免 caller 组合 racy get/set；
- `ConcurrentSet<T>` 遵循相同 shard/compound rule；
- `ConcurrentQueue<T>` 有界，提供 suspend/try push-pop；
- iteration 明确为 snapshot 或 weakly consistent view，不暗示 global atomic
  iteration。

capacity、shard count、每次操作 allocation 与 denial-of-service bound 都必须显式。
这些类型通过名称/API 选择并发，因此可使用 atomic/shared storage。

## 9. Affine Resource

socket、HTTP stream、server/exchange、process child/pipe、SQLite database/query、
reactor token、lock guard 与 borrowed runtime buffer 第一版都是 `Local/!Send`，
有一个 owner shard 和独占 close path。

应用跨 task 发送 request/response data，而不是 handle。未来某种 resource 只有在
聚焦 RFC 定义 reactor registration、pending operation、buffer 与 close authority
如何转移后，才可变成 transferable。

该规则替代当前 process-global handle registry 的隐含假设，防止 concurrent
close/use race。

## 10. 诊断

| 代码 | 条件 | 必需指导 |
| --- | --- | --- |
| `E0880` | `!Send`/`Local` value 跨 spawn/channel publication | 保持 handle local，发送 owned data |
| `E0881` | publication move 后继续使用 | 指向 consuming boundary |
| `E0882` | lock guard 跨挂起点 | call 前释放 guard |
| `E0883` | type 无法推导 `Send`、`Sync` 或 `Freeze` | 展示第一个阻止推导的 field/path |
| `E0884` | shared mutable operation 作用于普通 COW storage | 使用 mutex、channel 或显式 concurrent container |
| `E0885` | concurrent hash container 缺少稳定 `Hash + Eq` | 指明缺少的 constraint/implementation |

transfer error 与 capacity/backpressure outcome 是 typed value，且不得记录被 transfer
的内容。compiler、LSP、generated docs 与中英文 diagnostic reference 必须一致。

## 11. C99 与 Runtime 影响

编译器生成 type-specific local retain/release、`publish_move`、freeze/thaw、
shared-drop 与 capability metadata。普通 helper 保持 non-atomic。shared control
block 与 concurrent primitive 使用 RFC 0032 私有 atomic shim。

capability inference 记录在 typed IR 与 semantic tooling。生成 C 的 debug metadata
可记录 owner shard，但 release build 不给普通 task-local collection operation
增加 owner check。

publish helper 必须 transactional：所有 detach/allocation 完成后才 consume source。
RFC 0031 frame-drop ownership bit 覆盖 partially prepared send/select arm 中的 value。

## 12. 测试与验收

必须覆盖：

- structural capability derivation 与所有负向诊断；
- nested COW value 的 unique zero-copy 和 aliased-detach publication；
- use-after-move 拒绝；
- channel FIFO、close、saturation、cancellation 与 winner race；
- lock fairness policy、cancellation、early return、panic drop、guard suspend 拒绝；
- affine-handle cross-task 与 close/use 拒绝；
- atomic shared destruction exactly once；
- 独立 hash RFC 之后 concurrent-map compound operation。

支持的平台使用 thread/address/undefined behavior 工具做 stress。instrumentation 记录
local/atomic ARC traffic、detach、copy bytes、queue contention 与 allocation count。
no-cost/performance 门禁见 RFC 0034。

## 13. 兼容性、备选与风险

capability bound 会成为 exported generic API 的一部分，可能拒绝 RFC 0026 以前只能
通过 copied string 接受的代码。Nomo 尚未 1.0，可在 migration 中收紧边界，但
diagnostic 与 example 必须同步。

| 备选 | 不选择原因 |
| --- | --- |
| 所有 managed value 使用 atomic RC | 普通程序付费并隐藏 publication boundary |
| 锁住所有 collection | 加重简单 value，且 compound action 仍不自动 atomic |
| 所有 task message 都 copy | 安全但失去 unique backing zero-copy transfer |
| ordinary COW backing 跨 worker 共享 | non-atomic RC 与 uniqueness check 会 race |
| 一个万能 concurrent collection | 混淆 queue、map、lock 与 snapshot 语义 |
| 所有 handle 都 `Send` | 允许 wrong-reactor access 与 close race |

主要风险是 capability inference 不健全或 publication 漏掉 alias。第一版 capability
由编译器控制，不允许 unsafe user implementation；transfer helper 在稳定化前必须
通过 exhaustive lifecycle/stress test。

## 14. 提议决定

采用编译器内建 `Send`、`Sync`、`Local/!Send`、`Freeze`；consuming
publication（unique zero-copy、aliased detach）；显式 frozen/shared atomic
storage；bounded channel；suspension-safe lock rule；专用 concurrent container。

不改变普通 collection storage 或 RFC 0030 ordered-map 语义。hash-based 普通/
concurrent collection 实现前，必须先有独立 `Hash + Eq` RFC。

## 15. 参考

- [RFC 0003：ARC 与 COW runtime 成本](./0003-arc-cow-runtime-cost.md)
- [RFC 0030：Collection literal、indexing 与 ordered Map](./0030-collection-literals-indexing-and-ordered-map.md)
- [RFC 0031：直写式挂起函数与结构化并发](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032：分片 executor、reactor 与 blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0034：异步 runtime 验收与基准门禁](./0034-async-runtime-acceptance-and-benchmark-gates.md)
