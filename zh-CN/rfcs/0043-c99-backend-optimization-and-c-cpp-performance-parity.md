# RFC 0043：C99 后端优化与 C/C++ 性能持平

> 语言 / Language: 中文 | [English](../../en/rfcs/0043-c99-backend-optimization-and-c-cpp-performance-parity.md)

## 元信息

| 字段 | 值 |
| --- | --- |
| 编号 | 0043 |
| 标题 | C99 后端优化与 C/C++ 性能持平 |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Not implemented（未实现） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-28 |
| 关联主题 | C99 后端、release build、CFG MIR、基于证明的优化、Benchmarks Game、C、ISO C++20、性能证据 |
| 关联 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0016](./0016-incremental-semantic-graph-and-cache.md)、[RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. 摘要

本 RFC 提议为 Nomo C99 后端建立优化契约，并用狭义、可复现的性能门禁与等价 C
和 C++20 程序验证持平目标。新增以下公开 release 模式 CLI：

```text
nomo build --release
nomo run --release
nomo test --release
nomoc build --release
```

release 模式生成的 C 与工具链自带 C Runtime 翻译单元使用固定优化基线：

```text
-O3 -DNDEBUG -fomit-frame-pointer
```

该基线明确排除 fast-math、LTO、PGO 与 `-march=native`。只有编译器能够证明
Nomo 的边界、溢出、除零、写时复制、求值顺序、所有权与释放语义均被保留时，
release 模式才可执行相应优化。

编译器架构从 typed IR/HIR 进入控制流图 MIR，再执行基于证明的 pass，最后输出
C99。无法证明冗余的检查必须继续执行。禁止按 benchmark 名、函数名或源码 hash
添加特判。

性能门禁冻结三项单线程标量 workload，以官方 C `gcc #8` 算法和逐行等价的
C++20 派生实现作为对照。每项执行两次 warmup、30 个 paired block，使用 log
ratio 与单侧 99% 置信上界。即使未来通过，也只证明合格 canonical host 上冻结
suite 的结果，不代表所有 Nomo 程序、平台或 workload 都追平或超过 C/C++。

本文当前为 `Proposed` / `Not implemented`。已有临时优化 C 调用与探索性 CPU
baseline 尚未实现这里定义的公开 CLI、optimizer、C++20 对照或统计验收门禁。

## 2. 动机与边界

Nomo 已将经过类型检查的程序 lowering 到可移植 C99，但所有权检查、写时复制、
checked arithmetic 或聚合更新展开成 C 后，下游 C 编译器无法恢复全部高层事实。
稳定的 release 性能因此需要在 C 输出前增加理解语言语义的优化层，不能只依靠更强
的下游 C flag。

同时，性能承诺必须比“C99 输出很快”更严格、更狭窄：源码身份、输入、工具链、
安全语义、测量顺序、统计方法与判定阈值都必须固定。本 RFC 定义的正是这一窄契约。

本 RFC 不会：

- 承诺任意程序或全部 target platform 的性能持平；
- 允许不安全地移除边界、溢出、除零、所有权、COW 或清理行为；
- 改变 Nomo 语言语义、源码语法或 Preview 兼容政策；
- 对 async、I/O、内存占用、编译器延迟或二进制体积作出声明；
- 允许 release artifact 使用目标相关的 `-march=native`；
- 要求噪声较大的共享 CI runner 用 wall-time 阈值卡住 PR；或
- 宣称稳定 `v0.1.0`、生产就绪或任何 release gate 已完成。

RFC 0034 仍是 async Runtime 验收与 Agent workload benchmark 的权威来源。本 RFC
的 CPU suite 不会替代它。

## 3. 公开 release 模式 CLI

### 3.1 Canonical 命令

以下形式成为公开契约：

```text
nomo build [path] --release
nomo run [path] --release [-- program-arguments]
nomo test [path] --release
nomoc build <input> --release
```

在底层命令原本支持的范围内，现有 target、workspace、lockfile、offline、
diagnostic 与输出选项继续可与 `--release` 组合。help、verbose output、JSON
build record、cache key 与 provenance 都必须显示 release 模式。不认识或不支持
的组合要显式拒绝，不能静默回退到 debug build。

`nomo run --release` 先用 release 模式构建所选应用，再执行它。
`nomo test --release` 在 release 语义下构建 test harness 与被测单元，但测试发现、
隔离、失败报告和退出码保持不变。`nomoc build --release` 为直接使用 compiler 的
工作流暴露同一后端模式。

### 3.2 固定下游 C flag

验收基线要求 C 编译器除仓库原有 language-standard、target、include、link 与
platform flag 外，还收到：

```text
-O3 -DNDEBUG -fomit-frame-pointer
```

参数顺序不能让后面的默认值抵消固定优化级别。必须记录实际 compiler executable、
版本、target、参数、环境输入与最终 link command。

release 基线禁止：

- `-ffast-math`、`-Ofast` 或等价的宽松浮点模式；
- link-time optimization；
- profile-guided optimization；
- `-march=native`、`-mcpu=native` 或主机自动探测 ISA 扩展；以及
- 针对源码、函数或 benchmark 的 flag 注入。

未来 RFC 可以把这些模式作为单独命名的 profile 评估，但不能静默加入可移植
Preview release profile，也不能用于本 RFC 的验收证据。

仅由 Nomo 内部开发配置控制的 debug assertion 可以在 `-DNDEBUG` 下移除。语言
要求的 runtime check 与 cleanup 不是 C `assert`，除非基于证明的 pass 单独证明某
一检查冗余，否则必须保留。

## 4. 语义保持

release 与 debug build 具有相同的 Nomo 可观察语义。优化至少必须保留：

- 越界检测及其诊断/终止类别；
- 语言规定为 checked 的整数运算之溢出行为；
- 除零与有符号除法边界行为；
- string、array、map 与 aggregate 的写时复制隔离；
- 规定的从左到右求值与单次求值；
- borrow、move、publication 与所有权隔离；
- ARC retain/release 平衡、destructor/drop 顺序与 exactly-once cleanup；
- error propagation、panic、退出状态及外部可见 I/O 顺序；以及
- 现有非 fast-math 契约下的浮点行为。

“benchmark 输出相同”不足以作为证明。negative test 必须在优化 build 中覆盖越界
失败、溢出、除零、alias/COW 分离、副作用顺序与提前退出清理。sanitizer 与
generated-C 检查只是补充，不能替代语言级断言。

只有当用于解释删除原因的 MIR fact 或 analysis result 带有证明时，才能删除检查。
如果证明缺失、已失效、依赖 target 或超出分析预算，就保留该检查。没有优化是正确
行为；执行未经证明的不安全变换则不是。

## 5. 优化架构

### 5.1 Pipeline

release pipeline 为：

```text
parsed AST
  -> typed and ownership-checked IR/HIR
  -> control-flow graph MIR
  -> proof-producing analyses and transformations
  -> C99
  -> fixed release C compilation and link
```

typed IR/HIR 继续提供已消解身份、类型、effect、ownership 与源码诊断。CFG MIR
显式表示 basic block、terminator、join、loop、异常/清理 edge、ownership
operation、checked operation 与 effectful call。C99 emitter 消费优化后的 MIR；
它不能自行重新推断或绕过高层安全决定。

debug 与 release 模式可以共享同一 MIR；release 额外启用经过验证的 pass 与固定
C flag。cache key 必须包含优化 profile、target、compiler/runtime revision、
pass-pipeline version 与相关 toolchain 配置，避免 debug 或陈旧优化产物被复用。

### 5.2 基于证明的 pass

首批实现可以包含：

- 遵守 Nomo 溢出/浮点规则的 constant propagation 与 folding；
- 感知 effect/drop 的 unreachable-block 与 dead-value elimination；
- 面向 pure value 的 copy propagation 与局部 common-subexpression elimination；
- branch 与 jump simplification；
- range analysis 与冗余 bounds-check elimination；
- 针对除法检查的 nonzero/range proof；
- 基于 ownership/liveness 的 retain/release coalescing；
- 通过 uniqueness proof 避免不必要的 COW detach；
- 在 identity 与 cleanup 不变时执行 scalar replacement 与 aggregate-update
  simplification；以及
- 只有具备 dominance、effect、alias、overflow 与 cleanup proof 时才进行
  loop-invariant movement 或 induction simplification。

每个 pass 都要声明所保持的 invariant，并具备 unit、differential 与 negative
test。pass 顺序需要版本化；测试/debug compiler build 可在 pass 之间运行 verifier，
拒绝 malformed MIR。

### 5.3 禁止特判

compiler、Runtime、build driver 与 generated C template 都不能按以下内容分支：

- benchmark 或 project 名；
- 三项 workload 的身份；
- source path 或 content hash；
- suite 使用的 function、variable 或 package 名；
- formal input 值；或
- benchmark harness 是否存在。

优化必须基于通用 typed/MIR property 表述，并用无关的正反例程序测试。任何
benchmark-specific shortcut 都会让整批结果变为 `ineligible`，即使输出正确。

## 6. 冻结性能 suite

### 6.1 Workload 与输入

suite 冻结以下标量、单线程 workload：

| Workload | 正确性输入 | 正式输入 | C 算法身份 |
| --- | ---: | ---: | --- |
| `spectral-norm` | 100 | 5500 | Benchmarks Game [`spectralnorm-gcc-8`](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/spectralnorm-gcc-8.html) |
| `n-body` | 1000 | 50000000 | Benchmarks Game [`nbody-gcc-8`](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/nbody-gcc-8.html) |
| `fannkuch-redux` | 7 | 12 | Benchmarks Game [`fannkuchredux-gcc-8`](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/fannkuchredux-gcc-8.html) |

冻结基线来自
[`nomo#60`](https://github.com/nomo-lang/nomo/pull/60) 合并的 suite，并以
[`nomo@c6712c1`](https://github.com/nomo-lang/nomo/commit/c6712c1da1f65fcbdf0ce037224d11482b6a7e35)
中的状态为准。v2 manifest 必须记录并校验以下 SHA-256：

| Workload | Nomo source SHA-256 | C source SHA-256 | 正式 fixture SHA-256 |
| --- | --- | --- | --- |
| `spectral-norm` | `f0caae510fbdc02d998a8c49275c4aca0b771642348286ce871515840f47fe30` | `1f7f71ce5fc6f87432b3801fb57c3e8a619da2527c1b801154b8102c7af66c3e` | `f9d5b5e3eb7657cf1bbba4cc856651864df9cd9fd9a6be9b9bc5fcbb67150deb` |
| `n-body` | `30fb086f8d5c55e0b389b7451f921a463c953db286ec9f97bb55d8b7bc595988` | `a8649dd7babc5b9178fc363f4d61b468662c703668c2f8f4ddeab206b3e7e879` | `3e6c9ef9d26cfe312a4cd8e1b81b3f671b88fbce84de543e8c23c206a942504d` |
| `fannkuch-redux` | `0f6d0156c03cc3218b06a1adf560c5a3e3a99188fe9b7185b619b8a4ad8881e9` | `4d3135b2ed7a2fedb12b731c0f1a6bf901d763ac8421208fab6c4997c3ca9d80` | `4265a65135c506a68d90d6474003fb9030b7ee244a06c046bd89b3932a28ce20` |

该 commit 中冻结的 v1 `performance/benchmarksgame/manifest.json` SHA-256 为
`bd8e5016fb376741478806d13585ebc37ade2104995bd411a2a161592f65c15f`。
v2 manifest 必须记录其 predecessor identity，而不能改变现有 v1 result artifact
的含义。

任何算法、正式输入、正确性 fixture 或某一实现承担的语义工作发生变化，都需要新
RFC 或明确 amendment，并重新建立 baseline。即使只是格式变化，也要更新 manifest
SHA，并审查语义等价性。

### 6.2 C 与 C++20 reference

每项 workload：

- C comparator 是已经冻结并记录 upstream URL、license、抓取日期与 SHA 的官方
  naive `gcc #8` 源码；
- C++ comparator 是从该 C 源码逐行、算法等价派生的 ISO C++20 实现；
- C++ 版本必须使用匹配的 LLVM driver，并以固定命令形态
  `clang++ -std=c++20 -pedantic-errors -O3 -DNDEBUG -fomit-frame-pointer ...`
  在不依赖语言扩展的条件下编译；
- C `#8` 源码使用固定长度数组时，C++ 派生实现使用等价的标准固定长度表示；
- C `#8` 源码使用运行时长度 VLA 时，ISO C++20 无法保留其栈存储类别。派生实现可
  使用 `std::vector<T>` 或 `std::unique_ptr<T[]>` 等标准连续 RAII 表示，但必须
  保持相同数组数量、元素类型、逻辑元素容量、词法生命周期、每次调用的分配频率、
  初始化工作与访问顺序；
- 每个标准动态表示必须在对应 VLA 求值点按最终逻辑元素数量恰好构造一次，之后不
  得增长或重新分配。对当前冻结 suite，这一规则适用于 `spectral-norm` 与
  `fannkuch-redux` 中的运行时长度数组；
- 每次 VLA 替换都必须在 derivation metadata 与 result provenance 中明确记录 C
  栈存储变为标准 C++ 动态存储，并记录原始 count expression、所选表示、元素类型、
  逻辑容量、生命周期与分配频率；
- 标准容器只可用作 storage representation。派生实现不得使用更强的库算法、
  预计算、容量增长、自定义 allocator、SIMD 实现或线程；
- C 与 C++ 使用版本、target 相匹配的 Clang/Clang++ 以及相同的固定 release
  optimization flag；以及
- Nomo、C、C++ 的正式输出都必须与冻结 fixture 完全相同。

C++20 文件目前尚不存在。它们的首个实现 PR 必须包含 BSD 3-Clause
attribution/derivation 说明、source SHA、可审查的 C `#8` 映射与正确性测试，之后
timing result 才具备资格。
共享 CI 必须用 `-std=c++20 -pedantic-errors` 编译每份 C++ reference；若接受
Clang VLA 或其他非标准 C++ 扩展，则 reference gate 失败。

冻结的官方 C `#8` 实现继续作为独立决策性 comparator。C++ 中允许且已披露的
stack→standard dynamic storage 替换不会改变或放宽任何对 C 的单项或 suite gate，
也不会改变本 RFC 冻结的 workload、输入、统计方法、阈值或 comparator 角色。

Go 仍可作为 diagnostic lane 与历史 v1 对照，但不参与本 RFC 的 C/C++ parity 判定。
semantic-C 实验只能标记为非决策性 diagnostic control，不能进入 workload 或 suite
verdict。

## 7. 测量协议

### 7.1 Build 与主机资格

candidate 与 `main` 分别从独立 clean checkout 通过真实
`nomo build --release` 路径构建。harness 不能用 `--emit-c` 后自行编译来模拟
release 模式。它必须记录两个 Nomo binary、commit、dirty state、generated-C SHA、
final binary SHA、命令、compiler version 与 target。

C 使用所选 `clang` driver；C++ 使用同一 LLVM 安装和版本中匹配的 `clang++`
driver，并在第 3.2 节固定 flag 之外增加 `-std=c++20 -pedantic-errors`。二者使用
相同 target；同一 workload 的 link library 必须等价。全部 build 在计时前完成，
compile time 不进入运行计时。

canonical host record 包含 OS/kernel、architecture、CPU model/topology、memory、
power mode、适用时的 frequency/governor、thermal state、virtualization、clock
source/resolution、affinity/isolation、concurrent load、toolchain version 与完整
冻结 source lock。必要资格缺失时结果为 `ineligible`，绝不能是 `pass`。

### 7.2 Warmup 与 paired block

每个 workload、每一批次依次：

1. 用 correctness input 验证所有实现；
2. 构建全部正式 binary；
3. 每个计时 lane 执行两次 warmup，warmup 永远不计入 sample；
4. 执行 30 个 paired block；
5. 按预先声明的 balanced order，在每个 block 中将每个 lane 恰好执行一次；
6. 验证正式输出后才能接受对应 timing；以及
7. 保留每个原始 wall-time sample、顺序、退出状态与环境事件。

决策性配对为：

- candidate Nomo 对 C；
- candidate Nomo 对 C++20；以及
- candidate Nomo 对固定的 `main` Nomo build。

存在时，candidate、`main`、C、C++ 与 diagnostic Go lane 共用 balanced schedule。
thermal、power、后台负载、输出、timeout 或 collector 异常会让受影响批次失效，不能
静默丢弃。禁止移除 outlier。可以用预先声明的整批环境失效规则拒绝并重跑，但被拒
artifact 与原因必须保留。

### 7.3 Log ratio 与单侧 99% 上界

对 workload \(w\)、comparator \(q\) 与 block \(i\)，计算：

```text
x[w,q,i] = ln(candidate_wall[w,i] / comparator_wall[q,w,i])
```

对 30 个 paired observation，令 `mean` 为 `x` 的算术平均，`s` 为 sample standard
deviation，`SE = s / sqrt(30)`。点估计与单侧 99% 置信上界为：

```text
R[w,q]   = exp(mean)
U99[w,q] = exp(mean + t(0.99, 29) * SE)
```

实现必须固定 critical-value 计算/库，并用已知 vector 测试。比值越小越快：
`1.00` 表示持平，高于 `1.00` 表示更慢。

针对每个 comparator，suite block \(i\) 是三项 workload 在该 block 中 log ratio 的
等权平均。`R[suite,q]` 与 `U99[suite,q]` 对这 30 个 suite-block value 使用同一
公式。等权设计避免仅因某 workload 耗时更长就支配 suite。

## 8. 验收阈值

所有不等式均包含等号。C 与 C++20 分别独立参与判定：

| Gate | 必须满足 |
| --- | --- |
| 每项 workload 对 C | `U99[w,C] <= 1.05` |
| 每项 workload 对 C++20 | `U99[w,C++] <= 1.05` |
| Suite 对 C | `R[suite,C] <= 1.00` 且 `U99[suite,C] <= 1.03` |
| Suite 对 C++20 | `R[suite,C++] <= 1.00` 且 `U99[suite,C++] <= 1.03` |
| Candidate/main，每项 workload | `U99[w,main] <= 1.03` |
| Candidate/main，suite | `U99[suite,main] <= 1.02` |

只有每一行都通过，该批次才通过。对一个 comparator 更快不能抵消另一个 comparator
的失败；suite 通过不能隐藏单项失败；candidate/main 通过也不能替代绝对 C/C++
parity。

验收证据要求 canonical host 上两批完整、分别合格的测量。每批必须独立通过全部
gate，不能合并 sample 来挽救失败批次。artifact 必须记录两批时间顺序，以及中间
任何 reboot、toolchain、source、power 或 environment 变化。

## 9. 会话分离与证据治理

### 9.1 Benchmark authority

benchmark 会话负责：

- 冻结 source/input/fixture lock 与 C++ 等价性审查；
- harness、collector、balanced order、raw sample、统计、schema 与 verdict 计算；
- canonical-host 资格与两批验收测量；以及
- 不调整 compiler 的前提下公开失败、ineligible run 与不确定性。

它不能在决策性测量会话期间修改 optimizer pass 或性能关键的 generated template。

### 9.2 Optimizer authority

optimizer 会话负责：

- HIR/MIR 设计、通用 proof-based pass、C99 lowering 与 release CLI；
- semantic、differential、generated-C 与 regression test；
- 在不改变冻结测量契约的前提下调查 benchmark evidence；以及
- 提供在决策性批次期间保持固定的 candidate commit。

它不能为了让 candidate 通过而修改 benchmark 阈值、source payload、顺序、统计或
资格规则。若契约确需调整，必须先回到 RFC review，之后再采集新证据。

### 9.3 共享 CI 与 canonical evidence

共享 PR CI 负责验证 release 模式功能、冻结 SHA lock、C/C++/Nomo 正确性、统计、
schema、collector、语义保持与 candidate/main command provenance。共享 runner
不得使用 wall-time 阈值拒绝 PR。

性能验收只来自两批合格 canonical-host 测量。后续 RFC evidence PR 必须链接其 raw
artifact、environment record、candidate/main commit、toolchain identity、
generated-C/binary hash、计算后的 ratio、bound 与 verdict。未达到阈值的结果仍是
有价值的证据，但不能把 `Implementation Status` 改为 `Implemented`，也不能把
`Decision Status` 改为 `Accepted`。

## 10. 必需实现与测试证据

只有以下全部合并，才算实现完成：

1. 四种公开 `--release` 命令、help、diagnostic、cache/provenance 行为与固定 C
   flag；
2. typed IR/HIR 到 CFG MIR lowering，并验证 cleanup/control-flow invariant；
3. 具备 pass order/version 记录的通用 proof-based optimization pass；
4. 针对边界、溢出、除零、COW、求值顺序、所有权与 cleanup 的优化模式正反例语义
   test；
5. C99/native 与已支持 WASM 行为 test，证明支持表面没有 release/debug 语义分歧；
6. 冻结 v2 benchmark manifest/schema、C++20 reference、license、collector、
   balanced schedule、统计与 v1 result compatibility；
7. 不含 timing threshold 的共享 Linux、macOS、Windows correctness/collector CI；
8. 两批分别通过的 canonical-host 测量；
9. 准确陈述范围与失败/ineligible evidence 的文档；以及
10. 单独的双语 RFC 状态 PR，链接代码 PR、merge commit、受保护 CI 与 canonical
    artifact。

在此之前，本 RFC 保持 Proposed。只落地 CLI、只落地 MIR、只落地 compiler
optimization 或只落地 benchmark harness v2，都只是 partial slice，必须如实记录。

## 11. 风险与替代方案

### 11.1 全部交给 C 编译器

只增加 `-O3` 更简单，但在下游 optimizer 使用前已经丢失 typed ownership、bounds
与 COW fact。固定 flag 是必要条件，不是充分条件。

### 11.2 全局删除安全检查

这可能改善 benchmark，却改变语言语义，因此拒绝。只能删除被证明冗余的单个检查。

### 11.3 使用最小耗时或非配对 sample

最小耗时容易受幸运噪声影响；非配对组难以抵御温度漂移。paired log ratio 保留
block 内比较，并把不确定性门禁显式化。

### 11.4 用共享 runner timing 卡住每个 PR

这会造成 flaky、依赖环境的 merge。共享 CI 验证正确性和测量机制；受控 canonical
host 才产出性能决定。

### 11.5 宣称普遍的原生速度持平

三项标量程序不足以支撑该结论。即使未来通过，允许使用的措辞也只能限定在冻结
suite、toolchain、协议与合格主机证据内。

## 12. 建议与当前状态

建议把本契约采纳为 release 模式优化与狭义 C/C++20 parity 目标的 Proposed 方向。
先实现公开 release path 与保持语义的 optimizer，再实现独立 benchmark v2
authority，最后冻结 candidate 并采集两批 canonical-host 测量。

合并本文不会批准任何实现或性能结论。提升到 `Accepted` 与 `Implemented` 必须通过
第 10 节的独立 evidence PR。Nomo 仍处于 Preview；在平台、packaging、editor、
ecosystem、external-use 与 performance 要求真正满足前，`RELEASE-GATE.md` 保持
未完成状态。
