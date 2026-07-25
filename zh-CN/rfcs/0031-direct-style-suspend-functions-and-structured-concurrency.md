# RFC 0031：直写式挂起函数与结构化并发

> 语言 / Language: 中文 | [English](../../en/rfcs/0031-direct-style-suspend-functions-and-structured-concurrency.md)

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0031 |
| 标题 | 直写式挂起函数与结构化并发 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 关联主题 | suspend 函数、effect、stackless coroutine、结构化并发、取消、ARC、C99 |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. 摘要

Nomo 用显式函数 effect `suspend fn` 标记可能挂起的函数，但调用点仍保持
同步直写形式：挂起调用和普通调用写法相同，不引入 `await` 表达式。普通
`fn` 仍是普通 C99 函数，不能调用 `suspend fn`。并发工作只能在词法
`task.scope` 中通过显式 `task.spawn` 创建，并在 scope 退出前完成 join。

C99 后端把可达的 suspend 调用链降低为 stackless 状态机。coroutine frame
只保存状态和跨可能挂起点仍存活的值。正常完成、取消、超时、错误值完成与
panic 清理共用一份 exactly-once ARC/COW drop 计划。

本 RFC 状态是 `Proposed`。它是实现前的语义门禁，不表示挂起函数或 runtime
已经存在。

## 2. 动机

RFC 0022 至 0024 接受的同步 pull API 足以实现小型 CLI Agent，但阻塞的 HTTP
stream、process pipe 或 timer 会占用调用线程。RFC 0026 通过“一任务一原生
线程”提供隔离，但该成本与固定的 string copy 边界不适合大量大部分时间处于
空闲状态的 Agent 连接。

Nomo 需要并发能力，同时不能让普通程序承担 async runtime、atomic RC 或
coroutine metadata 成本。取消与所有权清理也必须能由编译器验证，而不能散落成
应用约定。

## 3. 现状审计

- lexer 与 AST 有 `fn`，没有 suspend/effect 标记；
- typed IR 把所有函数和调用都表示为同步 body/普通表达式；
- C99 后端已经为分支、循环、`?`、`defer` 和 return 生成细致的 ARC/COW
  retain/release 计划；
- RFC 0026 的 `task fn` 是 OS-thread runtime 使用的受限 callback 类型，
  不是 async 函数声明；
- Nomo 尚无通用 closure 或用户可见 lifetime，第一版结构化并发不得依赖二者。

所以 `task fn` 与 `suspend fn` 含义不同：前者是 blocking work 兼容 callback，
后者是参与 coroutine lowering 的编译器 effect。

## 4. 源码模型

### 4.1 函数 effect

`suspend` 成为保留关键字，写在 `fn` 前：

```nomo
suspend fn fetch(url: string) -> Result<HttpResponse, HttpError> {
    return http.send(HttpRequest.get(url))
}

fn normalize(value: string) -> string {
    return value.trim()
}
```

effect 是函数类型与导出签名的一部分。可能挂起的函数值写作
`suspend fn(A, B) -> T`，不能赋给 `fn(A, B) -> T` 或
`task fn(A, B) -> T`。

必须满足以下规则：

1. `fn` 可以调用 `fn`，不能调用 `suspend fn`；
2. `suspend fn` 可以调用两者，调用点保持直写；
3. 名称解析和泛型单态化后传递地检查 effect；
4. FFI 函数默认同步；只有 toolchain-owned runtime intrinsic 可以向
   `suspend fn` 提供可轮询操作；
5. 程序入口可使用 `suspend fn main() -> void` 或
   `suspend fn main() -> Result<void, E>`。同步 `fn main` 沿用现有启动
   路径，不初始化 async runtime。

设计不引入 `await` token。函数声明让“可能挂起”在边界可见，结构化操作让
“创建并发”在创建点可见。

### 4.2 结构化 task scope

第一版使用 `std.task` 命名空间下由编译器识别的 block：

```nomo
suspend fn load_pair(left_url: string, right_url: string)
    -> Result<Array<HttpResponse>, AgentError> {
    task.scope {
        let left = task.spawn fetch(left_url)
        let right = task.spawn fetch(right_url)
        let left_response = task.join(left)?
        let right_response = task.join(right)?
        return Ok([left_response, right_response])
    }
}
```

`task.spawn f(args...)` 只接受一个对 `suspend fn` 的直接调用。参数从左到右
各求值一次，并 move 到 child。该限制避免仅为 capture task body 就引入
closure。返回值是 `Task<T>`，其中 `T` 是 callee 的返回类型。

`task.join(handle)` 自身可挂起。task handle：

- 归属其词法 scope；
- 可在 scope 内 move；
- 不得 return、存入全局、被更长生命周期的值捕获或未消费地离开 scope；
- 只能 join 一次。

`task.scope` 返回前所有 child 必须完成。正常退出时，未 join 的 child 先被
取消，再被 join。提前 `return`、`?` 传播或 panic 时，先取消 sibling，再
清理 child，最后执行原始控制转移。这是语言语义，不是可省略的 library cleanup。

### 4.3 取消、deadline 与 select

取消是协作式但具有结构：

- parent cancellation token 被所有 child 继承；
- 取消 scope 会传播到 descendants；
- 每个 runtime suspension 前后都观察取消，也可调用
  `task.check_cancelled()`；
- pending I/O registration 或 timer 必须先移除，再 drop frame；
- 取消不暴露部分初始化的返回值。

`task.deadline(duration) { ... }` 是带 monotonic deadline 的 scope；更早的
parent deadline 优先。timeout 由观察到它的操作返回 typed task/runtime error，
不是 panic。

`task.select` 等待静态枚举操作中的第一个 ready 项。selected arm 执行前先取消
非 winning registration。select 开始时已经 ready 的多个操作按源码顺序确定性
选择。arm 具体语法可以在 RFC 变为 `Accepted` 前细化，但这些语义不变。

detached work 不是普通逃生口。`task.daemon_scope` capability 只提供给进程
root 或 host embedding API，并必须声明 shutdown deadline 与 error sink。
普通 library 不能 detach child。

## 5. 类型检查与挂起安全

编译器在 call effect 已知后计算可能挂起点，并在每个点做 local liveness 分析：

- mutable borrow、mutable receiver loan、C pointer borrow、lock guard、
  runtime buffer view 不能跨挂起点；
- 存入 frame 的值必须有合法的生成式 move/drop；
- child 只能接收 RFC 0033 允许 transfer 的值；
- local/affine runtime handle 只能在 owner executor 使用；
- suspend function 的 `defer` action 必须同步，并在所有状态机出口仍有效。

immutable owned value 可以跨挂起点。这不会把 backing RC 变成 atomic：除非经过
显式 transfer 边界，frame 与 owner task 始终固定在同一 executor shard。

## 6. C99 lowering 与 ABI

### 6.1 生成物

每个单态化 suspend function 生成等价于以下形式的私有 C99 结构：

```c
typedef struct nomo_frame_fetch nomo_frame_fetch;
nomo_poll nomo_fetch_poll(nomo_frame_fetch *frame, nomo_context *context);
void nomo_fetch_drop(nomo_frame_fetch *frame);
```

私有 symbol 拼写不是稳定 API。frame 包含：

- 紧凑 resume-state tag；
- exactly-once destruction 所需的初始化/move bit；
- 只包含跨可能挂起点存活的 parameter/local；
- caller 拥有的 result storage；
- parent cancellation/deadline 与 executor affinity metadata；
- 仅在 call site 可能 pending 时存在的 child-frame/reactor-registration 状态。

第一次挂起前已经结束生命周期的 local 仍是普通 C local。suspend call 如果立即
完成，则在同一次 poll 继续执行，不 enqueue task，也不分配额外 scheduling node。

### 6.2 Poll 契约

内部 `nomo_poll` 有 `READY`、`PENDING` 与 runtime termination 状态。Nomo
`Result.Err` 是普通 ready value，不是 runtime failure。取消与 timeout 通过
声明的 task/runtime error type 完成结构化操作。

Nomo panic 仍表示 defect，不是可恢复异常。runtime 标记 task 正在 panic、取消
sibling、执行生成的 frame drop，再继续进程级 panic termination；用户代码
不能 catch。

### 6.3 Exactly-once drop

lowering pass 为以下路径生成统一 cleanup table 或等价控制流：

- 普通 return；
- `Result`/`Option` 的 `?` 传播；
- 观察到取消；
- deadline timeout；
- reactor registration 失败；
- child panic 传播；
- 进程级 panic cleanup。

每个初始化过的 frame field 有一个 ownership bit。move field 时先清除 bit，
再让 callee/result slot 接管责任。drop frame 时测试并清除每个 bit。测试必须
记录 retain/release 次数，并证明每条路径只释放一次 ARC/COW 值。

coroutine ABI 在 v0.1 中是 toolchain-private。不同 compiler build 生成的 C，
除非记录的 compiler/runtime ABI revision 相同，否则不能假定可链接。

## 7. 标准库影响

`std.task` 增加 structured scope、typed task、cancellation、deadline、yield、
join 与 select。Agent I/O API 按 RFC 0032 获得 suspend 能力，但调用保持直写。

RFC 0026 仍是其 isolated native-task API 的历史契约。其 `task fn`、
`TaskContext` 与 copied-string entry point 成为 deprecated compatibility
surface，并迁移到 RFC 0032 的 bounded blocking pool；不能把它们当作
`suspend fn` alias。

## 8. 诊断

| 代码 | 条件 | 必需指导 |
| --- | --- | --- |
| `E0870` | 同步 `fn` 调用 `suspend fn` | 将 caller 标为 `suspend`，或使用显式 blocking boundary |
| `E0871` | `task.spawn` 出现在 `task.scope` 外 | 把 task 创建放入 structured scope |
| `E0872` | task handle 或 scope-owned child 逃逸 | 在 scope 内 join |
| `E0873` | mutable borrow、guard 或 borrowed host view 跨挂起点 | 在 suspend call 前结束 borrow/guard |
| `E0874` | suspend frame 的 `defer` 可挂起或使用无效状态 | 使用同步且局部拥有的 cleanup |
| `E0875` | spawn target 不是一个直接 `suspend fn` 调用 | 提取命名 suspend function 并显式传参 |

诊断必须同时指向值的 origin 与 suspension/escape site。JSON diagnostics 和
中英文诊断文档是实现门禁的一部分。

## 9. 测试计划

正向测试覆盖 direct suspend chain、immediate-ready、nested scope、typed result、
取消、deadline、select、early return、`?` 与合法 immutable local。

负向测试覆盖上述每个诊断，包括 transitive effect、generic instantiation、
handle escape、double join、mutable field/index loan、lock guard 与 FFI borrow。

C99 lifecycle 测试检查生成 frame，并对所有完成/cleanup 路径做计数。native
集成测试在支持的平台用 sanitizer 执行 cancellation storm 与 panic cleanup。
browser WASM 由 host event loop 驱动同一状态机。性能与跨平台门禁见 RFC 0034。

## 10. 兼容性、备选与风险

`suspend` 成为保留字，现有同名 identifier 会发生源码破坏，需要 migration
diagnostic 与 formatter-assisted rename。effect 变化属于 API 变化，必须出现在
生成文档与 semantic/LSP 数据中。

| 备选 | 不选择原因 |
| --- | --- |
| 到处使用 `async fn` + `await` | 增加每个调用点语法，不能改善已选 direct-style effect 边界 |
| stackful fiber | 增加 C99 portability、内存边界与精确 frame ownership 难度 |
| 每个 suspend call 隐式 spawn | 隐藏并发、生命周期、取消与背压 |
| 继续一任务一原生线程 | 无法满足大量空闲 Agent 连接的成本模型 |
| 不受限 detached task | 使 shutdown、error 与资源所有权失去局部性 |

主要风险是控制流 lowering 与 drop 正确性的编译器复杂度。因此实现必须拆为可评审
slice；RFC 0034 的门禁全部满足前，本 RFC 不能变为 `Accepted`。

## 11. 实施阶段与决定

1. effect metadata、call-graph checking、diagnostics 与 benchmark hook；
2. C99 state-machine IR/lowering，以及 yield/timer/join/cancel/drop 测试；
3. structured scope、deadline、select 与 nonblocking I/O 集成；
4. 仅在正确性与测量证据后优化。

**提议决定：**采用显式 `suspend fn`、direct-style suspend call 与编译器强制的
structured task scope；第一版不增加 `await`、隐式并发或通用 detached task。

`task.select` arm 拼写和 daemon capability 构造方式可在评审中细化；effect
边界、stackless lowering、structured lifetime 与 exactly-once drop 不是开放的
实现选项。

## 12. 参考

- [RFC 0026：隔离原生任务与协作式取消](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0032：分片 executor、reactor 与 blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033：任务所有权转移与并发值](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0034：异步 runtime 验收与基准门禁](./0034-async-runtime-acceptance-and-benchmark-gates.md)
