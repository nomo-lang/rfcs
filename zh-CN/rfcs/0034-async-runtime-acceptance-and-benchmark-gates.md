# RFC 0034：异步 Runtime 验收与基准门禁

> 语言 / Language: 中文 | [English](../../en/rfcs/0034-async-runtime-acceptance-and-benchmark-gates.md)

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0034 |
| 标题 | 异步 runtime 验收与基准门禁 |
| 状态 | Proposed（已提案） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 关联主题 | performance、memory、benchmark、Go comparison、low-end device、cross-platform、correctness |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0033](./0033-task-ownership-transfer-and-concurrent-values.md)、[RFC 0040](./0040-owner-affine-async-http-and-sse-migration.md) |

## 1. 摘要

本 RFC 定义 Nomo async 模型实现与稳定化所需证据。“未使用时零成本”表示同步
程序没有 async runtime 初始化、thread、coroutine metadata、scheduler branch
或普通 collection atomic operation。ready suspend path 不做 frame allocation/
enqueue；真正 spawn 的 task 在 allocator warm-up 后至多一次 logical slab/frame
allocation；frame 只包含跨挂起点存活的 value。

与 Go 的性能比较只限于同机、等价的 I/O-bound Agent workload。吞吐至少
`1.10x`、RSS 至多 `0.80x`、p99 不差于 pinned Go baseline 是设计目标，不是
测量前可保证的事实。没有达到时也必须报告真实结果与瓶颈。

implementation、platform matrix、correctness stress test、docs、example 与
reproducible benchmark 全部满足下列门禁前，本 RFC 保持 `Proposed`。

## 2. 为什么单独设门禁 RFC

“stackless”“C99”“没有 tracing GC”不能证明低开销。compiler 仍可能 spill
所有 local、每次 call 都 allocate、产生大量 RC churn、enqueue 已 ready 的 work，
或泄漏 cancelled registration。

当前仓库有 compiler clean-build/check latency gate，但没有 async runtime
benchmark harness。因此实现必须先落 measurement hook 与 reference workload，
后续优化不能悄悄修改比较规则。

## 3. 可复现 Harness

`performance/async/` 将包含：

- machine-readable benchmark manifest；
- 精确 Nomo compiler/runtime revision 与 build flag；
- 精确 Go patch version 与 toolchain/container checksum；
- 实现相同协议与业务逻辑的 Nomo/Go reference source；
- workload generator version/configuration 与 TLS fixture；
- warm-up、sample count、duration、connection count、payload、timeout、random seed；
- raw per-run result 与 summarized JSON schema；
- host OS/kernel、CPU topology、memory、power mode、compiler 与 limit。

比较固定 available core、支持时的 process affinity、fd limit、TLS mode、
keep-alive policy、payload、validation work 与 logging。两边必须生成并验证相同
bytes。任何一方都不能为了分数关闭 safety、略去 error handling、预计算 response
或使用不同协议。

warm-up 后至少五次 measured run。报告 median、p50/p99/p999、throughput、CPU
time/utilization、peak/steady RSS、可测量的 allocation/bytes、open fd/handle，
以及 runtime-specific queue/frame/buffer counter。raw data 保留为 CI/release
evidence。

## 4. 必需 Workload

| Workload | 必需测量 |
| --- | --- |
| task spawn/complete | same/cross shard throughput、allocation、p99 |
| idle suspended task | 不同规模下 RSS/task、wake latency |
| timer wheel | insert/cancel/expire throughput、drift、cancellation storm |
| bounded channel | same/cross shard throughput、backpressure、fairness |
| TCP echo | throughput、p50/p99/p999、CPU/RSS、connection churn |
| HTTP keep-alive | request/s、TLS/plain、connection reuse |
| SSE/MCP stream | long-lived idle RSS、incremental latency、cancellation |
| process pipe | bidirectional stdio throughput、exit/cancel/timeout |
| connection churn | connect/close rate、stale-event defense、fd/buffer leak |
| cancellation storm | completion latency、CPU spike、exactly-once cleanup |

Agent scenario 组合 HTTPS model-style request、SSE token stream、MCP stdio、
bounded JSON-RPC framing、timer 与经 blocking pool 的 SQLite checkpoint。只用
local fixture，不使用真实 service credential。

“超过 Go”只适用于语义等价的 high-connection I/O-bound row；不声称 CPU-bound、
compiler speed、任意程序或所有平台都更优。

## 5. Zero-Cost 与 Allocation 门禁

### 5.1 未使用 async

代表性同步程序必须证明：

- 没有 async executor/reactor startup 或 worker thread；
- typed IR/generated C 没有 coroutine frame/state metadata；
- ordinary call 没有 scheduler polling branch；
- 除 toolchain 正常 dead-code/link behavior 外，不因未使用 async module 增加
  runtime dependency；
- ordinary string/array/ordered-map helper 没有 atomic RC/lock operation。

由 generated-C snapshot 与 symbol/runtime instrumentation 强制门禁。

### 5.2 Ready path 与 spawn

- 整条调用链 ready 的 suspend function inline 完成；
- ready fast path 为零 heap/slab allocation、零 ready-queue enqueue/dequeue；
- slab warm-up 后 true spawned task 至多一次 logical frame/slab allocation；
  slab chunk growth 单独报告；
- sequential suspend call 不仅因为“可挂起”就分配 task；
- reactor registration/select arm 使用有界且可回收 storage。

### 5.3 精确 frame 与 ARC

compiler test 比较 source liveness 与 frame layout；挂起前已经 dead 的 local 不得
进入 frame。alignment/padding 与 runtime metadata 和 user live data 分开报告。

instrumentation 记录 local/atomic retain/release、COW detach count/bytes、
publish copy、frame drop 与 peak live frame。不能仅凭“没有 tracing GC”推定
churn 低。

## 6. 正确性与资源门禁

每个 backend 必须通过：

- ready/cancel/timeout/close race 与 late event；
- result delivery 与 frame/value drop exactly once；
- parent-child cancellation 与 structured-scope shutdown；
- process termination 前的 panic cleanup；
- bounded queue/blocking-pool saturation；
- stale generation 与 owner-affinity enforcement；
- channel/select winner race 与 moved-value recovery；
- lock cancellation 与 guard release；
- steady state/cancellation storm 后无 fd、HANDLE、socket、timer、buffer、task、
  frame、registry、blocking-job leak；
- secret-safe diagnostics/tracing。

支持的平台使用 sanitizer、model/stress test 与 debug counter。平台跳过项必须有
等价验证，或明确为 stabilization blocker。

## 7. 平台与设备矩阵

| 环境 | 必需证据 |
| --- | --- |
| Linux x86-64 | native `epoll` correctness、stress、leak、完整 benchmark |
| Linux arm64 | native 或长期维护的模拟 correctness，加 low-memory/one-core 证据；稳定性能声明前需 native result |
| macOS arm64/x86-64 | native `kqueue` correctness 与 representative benchmark |
| Windows x86-64 | native IOCP correctness、cancellation、process-pipe、representative benchmark |
| browser WASM | host-driven current-thread correctness、size/startup budget、timer 与受支持 network host API |
| one core / low memory | 无额外 async worker、有界 memory、压力下 backpressure/cancellation |
| multi-core | shard scaling、cross-shard cost、imbalance、optional-stealing experiment |

cross-compilation 证明 build portability，不能替代 native runtime test。optional
`io_uring` 与 stealing 还要对比 mandatory fallback/default，不能只对比 Go。

## 8. 性能决定规则

第一版正确实现先记录 baseline，再优化。后续 PR 为受影响 workload 附
before/after result，并解释 noise control。

等价 high-connection I/O Agent workload 的设计目标：

- Nomo throughput `>= 1.10x` pinned Go baseline；
- Nomo steady/peak RSS `<= 0.80x` Go baseline；
- 同 offered load/success rate 下 Nomo p99 不差于 Go。

这些是优化目标。失败不能成为更换 Go version、语义、负载、payload、safety
check 或 sample selection 的理由；报告应给出 bottleneck、confidence/noise 与
next action。

每阶段 acceptance gate 是真实可复现证据，并且没有相对上一版 Nomo baseline
无法解释的 regression。稳定 marketing claim 要求命名 workload/platform 都达到
目标；RFC 状态变化本身不能产生性能声明。

## 9. 分阶段交付门禁

| 阶段 | merge 必需证据 |
| --- | --- |
| P0：语义/harness | effect/type diagnostic、benchmark manifest、Go reference、counter、sync-unused snapshot |
| P1：stackless/current-thread | lowering/drop test、ready zero-allocation、yield/timer/join/cancel example |
| P2：reactor/I/O/blocking | epoll+kqueue，再 IOCP/WASM；TCP/HTTP/SSE/process fixture；bounded blocking pool |
| P3：structured ownership | scope/deadline/select、channel backpressure、capability/guard diagnostic |
| P4：shard | one-core、owner affinity、cross-shard transfer、scaling result；stealing 仍关闭 |
| P5：shared/collection | Frozen/Shared、lock、Accepted Hash+Eq 前置、concurrent-container stress |
| P6：优化/稳定 | slab/elision/batching、optional io_uring/stealing、完整 matrix report |

每个阶段同时更新 Nomo example、unit/CLI integration test、已实现行为的中英文
docs/SPEC、diagnostic docs 与 platform CI。PR 保持可评审 slice，不做一个巨大
implementation change。

## 10. 验收 Example

example matrix 逐步增加：

- `async_timer_and_cancel`；
- `structured_http_pair`；
- `async_sse_agent`；
- `mcp_stdio_client`；
- `bounded_pipeline`；
- `blocking_sqlite_checkpoint`；
- `affine_handle_negative`；
- `frozen_shared_snapshot`。

example 使用 local fixture、显式 limit/deadline、无 API key，并记录 native/WASM
availability 与 expected output。

## 11. 兼容性与报告

benchmark result schema 版本化。改变 workload semantic 或 measurement method
会建立新的可比较序列，并保留旧 raw result。CI 可用宽松 regression threshold；
release/stabilization evidence 使用专用受控 host，不能从 noisy shared runner 推断。

公开文档必须区分：

- design target 与 measured result；
- current-thread 与 sharded runtime；
- mandatory backend 与 optional optimization；
- application-side 无 C FFI 与 toolchain 内部使用 system library；
- 已实现 platform support 与仅 cross-build support。

### 11.1 已交付的 P2 process-pipe 证据

[`nomo#58`](https://github.com/nomo-lang/nomo/pull/58) 增加确定性的
16-child saturation、类型化 overflow、32 次 slot reuse 与 15 个 queued job
cancellation storm，并在 Linux、macOS、Windows 上验证精确的 zero-live cleanup
counter。[`nomo#59`](https://github.com/nomo-lang/nomo/pull/59) 启动 result
schema 2 与第一个 enabled P2 跨语言 workload。Nomo 与固定 Go 1.25.12 对同一个
C99 fixture 执行 256 次、63-byte 的 bidirectional process-pipe protocol。
Linux collector 强制单核 affinity、2 GiB address-space ceiling 与 128 MiB
peak-RSS budget，并记录 CPU/RSS/fd/thread observation 与 p50/p99/p999。

通过的 pull-request artifact 报告 Nomo/Go throughput `0.958986`、p99 wall
ratio `1.004829` 与 peak-RSS ratio `0.997620`；两侧 peak RSS 都约为
15.5 MiB。这些 hosted-runner 数字会作为 raw diagnostic evidence 保留，但尚未
达到 1.10 throughput 与 0.80 RSS 设计目标，不能产生性能声明。
controlled-host 重复、Windows-native resource collector，以及其余命名
workload/platform matrix 仍然必需，因此本 RFC 继续保持 `Proposed`。

## 12. 备选与风险

| 备选 | 不选择原因 |
| --- | --- |
| 先优化再加 counter/reference workload | regression 与 claim 无法评审 |
| 只用 microbenchmark | 遗漏 buffer、TLS、cancellation 与 long-lived Agent behavior |
| Nomo 最好一次对比 Go 平均值 | 统计与运营上不公平 |
| P0 起就把目标比例设为硬 merge blocker | 正确 baseline 前会激励 benchmark distortion |
| 由 cross-compilation 推断 portability | 无法执行 reactor race/cancellation |

harness 维护与专用 host 有成本，但小于稳定化一个不可测 concurrency model 或发布
无证据性能声明的成本。

## 13. 提议决定

将这些 correctness、no-cost、allocation、resource、platform、device 与 benchmark
gate 作为 RFC 0031 至 0033 的必需证据。受控结果支持更窄的声明前，Go 比例只作为
明确设计目标。保留所有 raw result，不通过削弱比较来隐藏未达标。

## 14. 参考

- [Nomo Preview Stabilization Gate](../../RELEASE-GATE.md)
- [RFC 0031：直写式挂起函数与结构化并发](./0031-direct-style-suspend-functions-and-structured-concurrency.md)
- [RFC 0032：分片 executor、reactor 与 blocking pool](./0032-sharded-executor-reactor-and-blocking-pool.md)
- [RFC 0033：任务所有权转移与并发值](./0033-task-ownership-transfer-and-concurrent-values.md)
- [RFC 0040：Owner-affine async HTTP/HTTPS、SSE 与 blocking migration](./0040-owner-affine-async-http-and-sse-migration.md)
