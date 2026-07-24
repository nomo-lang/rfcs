# RFC 0024：受控子进程与多路复用标准 I/O

> 语言 / Language: 中文 | [English](../../en/rfcs/0024-controlled-child-processes-and-stdio.md)

## 元信息

| 字段 | 内容 |
| --- | --- |
| 编号 | 0024 |
| 标题 | 受控子进程与多路复用标准 I/O |
| 状态 | Accepted（已接受） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-24 |
| 实现状态 | 由 [nomo PR #13](https://github.com/nomo-lang/nomo/pull/13) 实现；acceptance gate 于 2026-07-24 全部通过 |
| 关联主题 | process、child process、stdin、stdout、stderr、timeout、termination、MCP、C backend |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0023](./0023-pull-based-http-streaming-and-sse.md) |

---

## 1. 摘要

Nomo v0.1 应增加 shell-free 的长生命周期 child-process API，提供显式 argument
与 environment、受限 queued stdin、多路复用的增量 stdout/stderr event、退出
观察、per-pull timeout、强制终止与幂等清理。

API 继续保持同步且 pull-based，不增加语言级 `async`/`await`、Nomo thread、
callback、PTY、terminal emulation 或 binary I/O。工具链托管 native code 可以在
内部使用平台 polling 或操作系统 worker facility；Nomo 应用代码无需声明 C FFI。

## 2. 动机

原生 CLI Agent 需要的不只是一次性 shell execution。尤其是 MCP stdio client
必须能够在不调用 shell 的情况下启动一个 server，通过 stdin 发送多条 JSON-RPC
message，在不 deadlock 的前提下消费 stdout/stderr，观察最终 status，对 stalled
I/O 执行 timeout，并终止或清理 server。

当前 `std.process` 无法形成该闭环：

- `process.spawn(command: string)` 调用 shell 并等待完成，因此其名字并不代表长
  生命周期 spawned child。
- `status` 重复相同行为。
- `exec` 只捕获 stdout，并把非零 status 当作 error。
- `output` 通过无上限临时文件捕获 stdout/stderr。
- 所有 command 都是 shell string，argument、quoting 与 injection 行为随平台变化。
- 不存在 child handle、stdin write、增量 output、timeout、terminate 或
  stale-handle contract。

分别使用两个独立 blocking function 读取 stdout 与 stderr 也不够。Child 可能在
parent 阻塞读取一个 pipe 时填满另一个 pipe，形成确定性 deadlock。因此第一个受控
API 必须提供单一 multiplexed event 操作。

## 3. 当前证据与 Gap

| 表面 | 当前证据 | P1 缺口 |
| --- | --- | --- |
| 公共 API | `exit`、阻塞式 `spawn`/`status`、`exec` 与 `output` | 没有 command model 或长生命周期 handle |
| 调用 | `system`/`popen` 接收一个 shell string | 没有 shell-free program/argv 边界 |
| 标准 I/O | `exec` 读取 stdout；`output` 把两个 stream redirect 到临时文件 | 没有 stdin、增量 output、公平性或受限 pending data |
| 退出 | 等待结束后返回最终整数 status | 没有 non-consuming poll 或 exit event |
| Timeout | 无 | Stalled child 或 pipe 可以永久阻塞 |
| 终止 | 无 | Agent 无法停止或 reap server |
| Error | `ProcessError` 只包含平台派生 message | 没有稳定 code 或 secret-redaction contract |
| Native runtime | 生成 C 使用 libc shell helper | 没有 registry、pipe、`poll`/`waitpid` 或 Windows `CreateProcessW` adapter |
| Browser WASM | 现有 process expression 返回 `NOMO-WASM-003` | 每个新 entry point 都必须在参数求值前拒绝 |
| 测试 | 一个原生 happy-path CLI test | 没有 Windows execution、pressure、timeout、terminate、UTF-8 split 或 secret test |

## 4. 详细设计

### 4.1 公共 Nomo API

现有 shell-command helper 保持源码兼容。受控扩展为：

```nomo
pub struct ProcessEnv {
    pub name: string
    pub value: string
}

pub struct ProcessCommand {
    pub program: string
    pub args: Array<string>
    pub cwd: Option<string>
    pub env: Array<ProcessEnv>
    pub inherit_env: bool
}

pub struct ProcessChild {
    handle: u64
}

pub struct ProcessExit {
    pub code: i32
    pub signal: i32
}

pub enum ProcessEvent {
    StdinFlushed
    Stdout(string)
    Stderr(string)
    Exited(ProcessExit)
}

pub struct ProcessControlError {
    pub code: string
    pub message: string
}

process.start(
    command: ProcessCommand
) -> Result<ProcessChild, ProcessControlError>

process.write_stdin(
    child: ProcessChild,
    data: string
) -> Result<void, ProcessControlError>

process.close_stdin(
    child: ProcessChild
) -> Result<void, ProcessControlError>

process.next_event(
    child: ProcessChild,
    max_chunk_bytes: u64,
    timeout_millis: u64
) -> Result<ProcessEvent, ProcessControlError>

process.try_wait(
    child: ProcessChild
) -> Result<Option<ProcessExit>, ProcessControlError>

process.terminate(
    child: ProcessChild
) -> Result<void, ProcessControlError>

process.close_child(child: ProcessChild) -> void
```

`start` 永不调用 shell。`program` 标识 executable，每个 `args` element 都是一个
argument。空 `program`、嵌入 NUL、非法 environment name、重复 environment name
或非法 working directory 返回 `invalid_request` 或 `spawn`，且 error 不包含被拒
value。

`program` 包含 path separator 时，直接解析该路径；若不是 absolute path，则相对
选定的 child cwd 解析。否则 runtime 在最终 child environment 的 `PATH` 中搜索。
不存在 `PATH` 时，bare name 返回 `spawn` error。Windows 搜索先尝试原名，再尝试
`.exe`，且不解释 `PATHEXT`。

`cwd = None` 继承当前 working directory。`inherit_env` 为 true 时，`env` entry
覆盖同名 inherited value；为 false 时，child 只接收显式 entry 与平台运行所需
variable。Environment name 必须非空，且不能包含 `=` 或 NUL。Unix-like target
按大小写区分 name，Windows 不区分。v0.1 唯一隐式 entry 是调用方未提供时的
Windows `SystemRoot`；Unix-like target 不增加任何 entry。

三个 child stream 全部使用 pipe，以保持第一个 API 小而确定。继承特定 terminal
stream、null stream、PTY 与 binary handle 需要后续扩展。

### 4.2 受限 Queued Stdin

`write_stdin` 把一个非空、最大 1 MiB 的 UTF-8 string 复制到工具链托管 pending
storage，并在 payload 被接受后返回；它不声称全部 byte 已经到达 child。每次只允许
一个 pending payload；再次 write 返回 `busy`。

`next_event` 在 stdout、stderr 与 child-exit 观察之外同时推进 pending payload。
完整 payload 到达 child 后，它会恰好返回一次 `StdinFlushed`。Timeout 会把尚未
发送的 suffix 保留在 registry，因此调用方必须继续调用 `next_event`，而不能再次
enqueue 同一 payload。这避免了 blocking `write_stdin(..., timeout)` 的 partial
write 歧义。

stdin 已关闭时，`close_stdin` 保持幂等。如果仍有 pending payload，它返回
`busy`；调用方应先等待 `StdinFlushed`。关闭 stdin 后，line-oriented 或
EOF-delimited child 可以自然结束。

### 4.3 多路复用 Output 与 Backpressure

`next_event` 等待 stdin progress、stdout、stderr 与 process exit 中下一个可观察
event。`timeout_millis` 必须大于零且不超过 15 分钟。过期返回 `timeout`，不会
关闭 child 或丢弃 pending data。

`max_chunk_bytes` 必须在 4 bytes 到 1 MiB 之间。`Stdout` 与 `Stderr` payload 是
非空 UTF-8 string，且不会切断 UTF-8 scalar。非法 UTF-8 或嵌入 NUL 返回
`protocol`。Binary child protocol 需要未来 byte-buffer API。

`protocol` failure 会强制终止 child 并关闭其 registry entry，因为让未消费的
binary stream 继续运行可能使 process deadlock。复制出的 handle 仍可安全传给
幂等 `close_child`。

stdout 与 stderr 各自内部保持顺序。两个 pipe 没有共同 byte clock，因此不承诺
cross-stream order。当两个 stream 同时 ready 时，runtime 交替第一选择，避免 noisy
stream 永久饿死另一个。

Runtime 每次最多读取调用方请求的 chunk 后就返回 Nomo。操作系统 pipe capacity
提供 backpressure；registry 不得累计无上限 output buffer。

### 4.4 Exit、Termination 与 Ownership

`try_wait` 观察但不消费 child exit。Process 仍运行时返回 `None`，操作系统报告
结束后返回 `Some(ProcessExit)`。

`next_event` 只有在 process status 已知且 stdout/stderr 均到达 EOF 后才发出
`Exited`，避免静默丢失最终 output。正常退出时 `signal = 0`，`code` 是平台 exit
code。Unix-like target 因 signal 结束时，`signal` 是 signal number，规范化
`code` 为 `128 + signal`；Windows 始终报告 `signal = 0`。

`terminate` 请求立即强制终止，对已经退出的 child 保持幂等。Unix-like target
使用 `SIGKILL`，Windows 使用 `TerminateProcess`。应用级 graceful shutdown 应先
通过 stdin 发送。Termination 只作用于直接 child；process-group 与 descendant
tree policy 继续推迟。未来 API 可以另行增加 graceful signal。

`ProcessChild.handle` 是 opaque registry identifier，绝不是 native pointer。复制
出的 value 指向同一个 child。`close_child` 保持幂等；它关闭所有 pipe，若 child
仍在运行则强制终止并 reap。程序应在 `start` 后立即注册
`defer process.close_child(child)`。

`Exited` 发出后，继续调用 `next_event` 返回 `invalid_request`；registry entry
关闭前，`try_wait`、`terminate` 与 `close_child` 继续安全。

### 4.5 Error 与 Secret Handling

`ProcessControlError.code` 为：

- `invalid_request`：非法 command、limit、timeout 或 stale handle。
- `busy`：前一个 stdin payload 尚未 flush。
- `spawn`：executable、working-directory 或 environment setup failure。
- `io`：pipe create、read、write、wait 或 close failure。
- `timeout`：`next_event` 在 deadline 前没有 caller-visible progress。
- `protocol`：stdout/stderr 不是受支持的合法文本。
- `runtime_unavailable`：target 不存在 controlled-process adapter。

Error 与默认 diagnostic 不得包含 `program`、argument、environment name/value、
cwd、stdin payload、已接收 stdout/stderr 或临时 native identifier。该规则避免通过
environment variable 或 JSON-RPC payload 传入的 token 泄露到 log。

现有 `ProcessError` 保持不变，以兼容 legacy shell helper。新代码使用具有稳定 code
的 `ProcessControlError`。

### 4.6 工具链托管 Native Runtime

应用无需声明 C FFI、native source 或 linker metadata。

- Unix-like target 创建 close-on-exec pipe，使用 `fork` + `execve` 或等价
  shell-free primitive，设置 nonblocking parent descriptor，并通过 `poll` 与
  `waitpid(..., WNOHANG)` 推进。
- Windows 使用具有显式 application name 的 `CreateProcessW`、确定性 argv
  quoting、UTF-16 environment block、继承的 child pipe end、nonblocking/
  overlapped parent-side progress 与 process-handle wait。
- 只有 native C buffer 与 OS handle 可以穿过任何内部 worker boundary。
  Nomo-managed string/array 在 `start` 或 `write_stdin` 时复制，绝不由其他 thread
  持有。
- 每个 error、timeout、terminate、exit 与 close path 都必须明确 handle/buffer
  cleanup owner。

Browser WASM interpreter 对 `start`、`write_stdin`、`close_stdin`、
`next_event`、`try_wait`、`terminate` 与 `close_child` 均在参数求值前返回
`NOMO-WASM-003`。

### 4.7 Legacy Shell Helper

本切片保留 `process.spawn`、`status`、`exec` 与 `output` 已接受的 v0.1 行为。
其文档必须明确标记为 legacy blocking shell helper，并警告不得把不受信任文本拼接
进 command。

`process.start` 是 Agent tool 与 MCP server 的推荐 API。本 RFC 不会悄悄把
`spawn(command: string)` 改成返回 handle 的函数，因为那会造成源码与语义破坏。

## 5. 备选方案

| 方案 | 优点 | 缺点 | 倾向 |
| --- | --- | --- | --- |
| Shell-free command + multiplexed event | 确定 argv、不发生 dual-pipe deadlock、支持 MCP stdio | Registry 与平台 adapter 更大 | 提案 |
| 分离 blocking `read_stdout`/`read_stderr` | 表面简单 | 未观察 pipe 填满时会 deadlock | 拒绝 |
| 带 timeout 的 blocking stdin write | API 常见 | Partial delivery 使 retry 破坏 message framing | 拒绝；queue 并发出 `StdinFlushed` |
| 每个 stream 一个后台 Nomo task | 并发自然 | 需要 task model 与 thread-safe managed value | 推迟 |
| 返回 raw OS handle | Runtime 工作少 | 把 unsafe、平台相关 ownership 泄露给应用 | 拒绝 |
| 替换 legacy `spawn` | 命名更干净 | 破坏现有代码与已接受行为 | v0.1 拒绝 |

## 6. 缺点与风险

- Windows overlapped pipe 与 argv quoting 需要大量平台专项测试。
- Text-only pipe 无法承载 binary protocol。
- 只提供 forced `terminate` 是刻意的强硬边界。
- Cross-stream event order 无法重建完全准确的 write interleaving。
- 一次一个 pending stdin payload 要求调用方等待 `StdinFlushed` 后才能 enqueue
  下一条 message。
- Opaque copied handle 需要 stale-handle 校验与幂等清理。

## 7. 对 v0.1 范围的影响

本 RFC 提供原生 CLI Agent loop 可复用的 process 部分，以及后续 MCP stdio client
需要的 transport。它不实现 Agent、JSON-RPC framing、MCP semantic、cron、PTY、
shell parsing、pipeline syntax、后台 Nomo task 或 async syntax。

JSON-RPC framing 仍是建立在 `ProcessEvent.Stdout` 上的后续切片；结构化 JSON 继续
独立 gated。

## 8. Acceptance Gate

以下 acceptance gate 已于 2026-07-24 全部通过：

1. Canonical `std.process` source、compiler lowering、生成 C ABI、文档与中英文
   v0.1 规格暴露完全一致的 API 与语义。
2. 现有 blocking shell helper 保持源码兼容，既有测试全部通过。
3. Nomo 示例以 shell-free 方式启动本地 fixture，发送至少两条 framed stdin
   message，接收交错 stdout/stderr，观察 exit，且不使用应用侧 C FFI。
4. 测试覆盖含空格/quote 的 argv boundary、cwd、继承/替换 environment、非法
   name、缺失 executable 与非零 exit。
5. Pipe-pressure 测试证明 multiplexed output 不 deadlock，每个 stream 各自保持
   顺序且不 starvation。
6. 测试覆盖拆分 UTF-8 scalar、非法 UTF-8、4-byte/1-MiB chunk boundary、一个
   pending stdin payload、`StdinFlushed`、close-stdin 与 timeout 后 pending write
   继续保留。
7. Timeout 后 child 继续可用；terminate/close 幂等；close 强制 reap 运行中的
   child；复制出的 stale handle 不 double-close。
8. argv、environment、cwd、stdin、stdout 与 stderr 中的 secret sentinel 均不会
   出现在 error、diagnostic 或默认 log。
9. Browser WASM 在参数求值前拒绝每个新 process entry point。
10. Formatting、Clippy、unit/CLI integration test 与 Windows native
    compile/run test 在
    [PR smoke run 30104105032](https://github.com/nomo-lang/nomo/actions/runs/30104105032)
    中通过；Linux x86_64-to-arm64 实际执行与 macOS arm64-to-x86_64 实际链接在
    [post-merge main CI run 30104404704](https://github.com/nomo-lang/nomo/actions/runs/30104404704)
    中通过。
11. 实现通过 SSH 签名提交与子分支，在 required check 通过后由
    [nomo PR #13](https://github.com/nomo-lang/nomo/pull/13) 合入；上述
    post-merge main run 为绿色。

## 9. 推迟的后续工作

- JSON-RPC line/content-length framing 与 MCP stdio client。
- PTY、terminal resize、inherited/null per-stream mode 与 binary buffer。
- Graceful signal 选择与 process-group/tree termination policy。
- Task/concurrency model 接受后的后台 task integration。
- Shell pipeline builder 与 shell-specific quoting helper。

## 10. 参考

- `std/src/process.nomo`
- `crates/nomo_compiler/src/builtins/builtins_process.rs`
- `crates/nomo_codegen_c/src/runtime/host_env_process_helpers.rs`
- `crates/nomo/tests/cli_project.rs`
- `crates/nomo_wasm/src/interpreter.rs`
- [RFC 0003](./0003-arc-cow-runtime-cost.md)
- [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md)
- [RFC 0017](./0017-target-triples-and-cross-compilation.md)
- [RFC 0023](./0023-pull-based-http-streaming-and-sse.md)
