# RFC 0042：Windows ARM64 Preview 平台支持

> 语言：中文 | [English](../../en/rfcs/0042-windows-arm64-preview-platform-support.md)

## 元数据

| 字段 | 内容 |
| --- | --- |
| 编号 | 0042 |
| 标题 | Windows ARM64 Preview 平台支持 |
| 决策状态 | Proposed（已提案） |
| 实现状态 | Not implemented（未实现） |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-28 |
| 相关主题 | Windows 11、ARM64、target triple、C99 backend、MSVC ABI、发布打包、平台 parity |
| 相关 RFC | [RFC 0017](./0017-target-triples-and-cross-compilation.md)、[RFC 0018](./0018-package-signing-provenance-and-transparency.md)、[RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md)、[RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. 摘要

本 RFC 提议把 Windows 11 ARM64 作为一等 Nomo Preview target，canonical target
triple 为 `aarch64-pc-windows-msvc`。该 target 使用 LLVM Clang GNU-style
driver，同时保持 MSVC ABI，并链接已安装 Visual Studio ARM64 library 与 Windows
SDK。

Preview 支持必须具备 ARM64 原生 build、run、test 与 release 证据。Windows x64
host 只有在安装 ARM64 Visual Studio/SDK component 时才能构建 ARM64 artifact；
这种 cross-build 可作为打包证据，但永远不能替代 ARM64 原生 Runtime test。

验收门禁覆盖 compiler、generated application、Windows Runtime、LSP、installer、
release archive、checksum 与 attestation。本提案不声称已经实现、已经稳定或已可用于
生产。

## 2. 范围与平台身份

### 2.1 支持的 Preview 环境

提议的平台契约如下：

| 维度 | 契约 |
| --- | --- |
| 操作系统 | Windows 11 ARM64 |
| Nomo target triple | `aarch64-pc-windows-msvc` |
| Object/executable 格式 | COFF / PE32+ ARM64 |
| C compiler frontend | LLVM Clang GNU-style driver |
| C/C++ ABI | Microsoft ARM64 ABI |
| 链接输入 | ARM64 MSVC library 与支持 ARM64 的 Windows SDK |
| 原生执行 host | Windows 11 ARM64 |
| 可选构建 host | 已安装 ARM64 VS/SDK component 的 Windows x64 |

不能只根据模拟运行的 process 推断 target。原生证据同时记录 OS architecture 与
process architecture，避免把在 ARM64 Windows 上通过 x64 emulation 运行的
`nomo.exe` 误认为原生 ARM64 toolchain。

### 2.2 非目标

本 RFC 不增加或承诺：

- Windows ARM32；
- ARM64EC binary、ARM64X mixed image 或通过 ARM64EC ABI 与 x64 互操作；
- MinGW、GNU Windows CRT 或 `windows-gnu` target；
- 非 Windows host cross-link MSVC binary；
- 在 Windows x64 CI runner 上执行 ARM64 output；
- 稳定 `v0.1.0` 支持保证；
- 解决既有 Windows-wide path、Regex 或大文件限制。

这些 target 会改变 ABI、link、Runtime、分发或测试假设，必须另行制定契约。

## 3. Toolchain 契约

### 3.1 Clang driver 与 ABI

C99 backend 使用 GNU-style `clang` driver 并显式指定 target：

```text
clang --target=aarch64-pc-windows-msvc ...
```

实现不得把该 target 静默切换到 MinGW、ARM64EC 或 host architecture。它可以通过
现有 Nomo toolchain 配置或经过校验的 Visual Studio/LLVM installation 发现
Clang，但 verbose diagnostic 与 CI artifact 必须可查看所选 executable、version、
target triple、Windows SDK version、library path 与实际参数。

使用 GNU-style driver 是 command-line 契约，不改变 ABI。生成 object/executable
采用 Microsoft ARM64 ABI，并链接 ARM64 MSVC/Windows SDK 输入。Installation 中
可以存在 `clang-cl`，但它不是本 RFC 选择的 driver。

### 3.2 必需的 Visual Studio 与 SDK component

原生和 x64→ARM64 构建环境都必须具备：

- 支持 `aarch64-pc-windows-msvc` 的 LLVM Clang；
- 通过 Visual Studio 或 Visual Studio Build Tools 安装的 ARM64 C/C++ build
  tools 与 library；
- 包含 ARM64 library/header 的 Windows SDK；
- library path 只解析到 ARM64 输入的 link environment。

只安装 x86/x64 C++ tools 的 x64 环境不满足要求。缺少 ARM64 component 时必须给出
可操作的 target-unavailable diagnostic，不能生成 x64 binary，也不能只返回难以理解
的 linker error。

本 RFC 不固定唯一 Visual Studio product version 或 Windows SDK revision。每个
release set 记录并 attest 实际版本，release gate 可另行固定经过验证的版本范围。

### 3.3 原生与 cross-build 命令

Windows 11 ARM64 原生 host 必须支持：

```powershell
nomo build --target aarch64-pc-windows-msvc
nomo run --target aarch64-pc-windows-msvc
nomo test --target aarch64-pc-windows-msvc
nomo build --release --target aarch64-pc-windows-msvc
nomoc build src/main.nomo --target aarch64-pc-windows-msvc
```

原生 release pipeline 还必须 build 并运行 ARM64 `nomo.exe`、`nomoc.exe`、
generated application、test binary 与所需 helper program。

Windows x64 只接受面向构建的命令：

```powershell
nomo build --target aarch64-pc-windows-msvc
nomo build --release --target aarch64-pc-windows-msvc
nomoc build src/main.nomo --target aarch64-pc-windows-msvc
```

没有显式原生 ARM64 execution provider 时，`nomo run` 和需要执行的 `nomo test`
不得报告成功。本 RFC 不定义 remote execution、emulation 或自动部署。Cross-build
job 只记录 compile/link/PE 证据。

## 4. Windows x64 Preview parity

Windows ARM64 支持以当前声明的 Windows x64 Preview surface 为基准。x64 已工作的
feature 在 ARM64 上执行等价行为、错误路径与资源清理之前，不得标为已支持。

Parity 意味着：

- 相同 Nomo source 与 manifest 语义；
- 相同 CLI command、JSON diagnostic、exit-code class 与 build directory 契约；
- 相同 ownership、ARC/COW、overflow、bounds、division、求值顺序、cancellation
  与 cleanup 语义；
- 相同 C99 Runtime API 与 Windows system API family；
- 相同 release metadata 与 snapshot compatibility policy；
- 普通应用不需要 architecture-specific source annotation。

Parity 不会消除既有 Windows-wide limitation。在分别实现并接受之前，Windows x64
与 Windows ARM64 都必须记录：

- narrow/ANSI path boundary 仍存在时，非 ASCII/Unicode path 保证不完整；
- 完整 Regex feature/behavior coverage 尚未完成；
- 大文件边界的验证与保证尚未完成。

这些是 Windows-wide known limitation，不是 ARM64 独有回归；ARM64 支持不得宣称已
解决它们。

## 5. Compiler、backend 与 artifact 要求

### 5.1 Compiler 与 generated C

Compiler 必须：

1. 把 `aarch64-pc-windows-msvc` 解析并校验为受支持 target；
2. 在 typed lowering 中传递 pointer width、integer layout、alignment、calling
   convention 与 target capability；
3. 生成不含 x64-only intrinsic、inline assembly、type-size 或 object-format 假设
   的 C99；
4. 为 ARM64 编译所有 toolchain-owned Runtime translation unit；
5. final link 只使用 ARM64 library；
6. 在 diagnostic 与 build record 中保留确定性的 target metadata。

Host 与 target 身份保持分离。在 ARM64 上运行 compiler process 不代表默认选中
ARM64 target；x64 host 选择 ARM64 target 也不代表已经验证 Runtime。

### 5.2 PE Machine 校验

Release gate 检查每个 executable 及相关 object/import library。原生 ARM64 PE image
必须报告：

```text
IMAGE_FILE_MACHINE_ARM64 = 0xAA64
```

至少覆盖：

- `nomo.exe`；
- `nomoc.exe`；
- 一个 generated hello-world executable；
- 一个同步 Runtime probe；
- ARM64 ZIP 中每个单独分发的 executable。

x64 (`0x8664`)、ARM64EC (`0xA641`)、ARM64X (`0xA64E`) 或 unknown machine
value 都使 ARM64 release gate 失败。

### 5.3 Architecture-sensitive code

所有 private atomic、IOCP、socket、process、TLS/WinHTTP、SQLite、clock 或 alignment
shim 都必须在 ARM64 原生编译和运行。Architecture-specific code 隔离到 target
module，并具备：

- compile-time target assertion；
- exact-width integer 与 pointer conversion；
- 不依赖 unaligned access；
- 文档化的 memory-order behavior；
- target positive/negative test。

本 RFC 不授权 cross-shard Runtime 工作，也不改变 RFC 0031–0040 语义。

## 6. 必需的 Runtime 与生态证据

Windows 11 ARM64 原生 CI 或受控 release host 必须执行：

| 范围 | 必需的 ARM64 原生证据 |
| --- | --- |
| CLI/compiler | `nomo`、`nomoc`、new/check/build/run/test/doc/fmt、JSON diagnostic |
| Generated application | Debug/release C99 compile/link/run、panic 与非零退出 |
| IOCP | registration、completion、cancellation、stale-generation cleanup |
| Task Runtime | scope、join、cancellation、deadline、frame drop |
| Channel/select | send/receive/close、timer、receive/send/join select、loser cleanup |
| TCP | DNS、connect、read/write、half-close、timeout/cancellation |
| Process | start、stdin/stdout/stderr、exit、terminate、handle cleanup |
| HTTP | WinHTTP HTTP/HTTPS、timeout、header、redirect 与已支持 streaming boundary |
| SQLite | bundled ARM64 compilation、open/execute/query/close、文件与 memory database |
| File/time/environment | 已支持 path class、bounded I/O、clock、args/env |
| `nomo-lsp` | 原生 ARM64 server startup、initialize、hover/signature/diagnostic smoke |
| `setup-nomo` | ARM64 host detection、archive selection、checksum verification、install smoke |

测试对每个 probe 适用的 handle/task/frame/channel/timer/process/socket counter 记录零
live leak。Cross-build 证据可覆盖 compile/link 与 PE identity，但所有执行行为的行
都必须有 ARM64 原生结果。

## 7. Release 与供应链契约

Windows ARM64 Preview release 是独立的 timestamped artifact。发布证据包括：

- 明确包含 architecture 的 ZIP 名称；
- `nomo.exe`、`nomoc.exe`、所需 license 与 release metadata；
- archive 与每个单独发布 binary 的 SHA-256；
- source revision 与 coordinated release-set version；
- Rust、Clang、Visual Studio toolset 与 Windows SDK version；
- host OS build、native host architecture 与 target triple；
- PE machine inspection 结果；
- protected CI 与 controlled-host runtime test 链接；
- 标识 workflow、source、builder 与 subject 的 signed provenance/attestation；
- `setup-nomo` 选择 ARM64 archive 并在安装前校验 digest 的 installer 证据。

包含 emulated x64 `nomo.exe` 的 x64 archive 不是 ARM64 release。Release note 必须
区分原生 compiler execution、原生 generated application 与 x64→ARM64 cross-build
证据。

## 8. Diagnostic 与失败行为

实现增加稳定、可操作的 diagnostic，覆盖：

- 未识别或尚未启用的 ARM64 target；
- Clang 缺少对应 target 支持；
- 缺少 ARM64 MSVC library 或 Windows SDK component；
- x64 link input 混入 ARM64 link；
- 没有原生 execution provider 时尝试 run/test ARM64 output；
- 生成 PE image 的 machine type 不是 ARM64；
- 使用 Windows ARM64 尚未支持的 Runtime capability。

Diagnostic 必须输出 requested target、检测到的 host/process architecture、所选
compiler 与缺失 component category，但不泄露本地 credential 或无关 environment
variable。Toolchain 必须 fail closed；绝不能 fallback 到 Windows x64 后仍把 artifact
标为 ARM64。

## 9. 验收门禁

只有以下全部适用门禁通过后，RFC 才可在独立 evidence PR 中改为 `Accepted`，
implementation 才可改为 `Implemented`：

1. Windows 11 ARM64 原生 `nomo` 与 `nomoc` build 并执行；
2. debug/release generated application 原生 compile、link、execute；
3. 每个 shipped executable 的 PE inspection 报告 `0xAA64`；
4. x64→ARM64 build 只在经过校验的 ARM64 Visual Studio/SDK 环境成功；
5. cross-build job 与 native runtime job 明确分离；
6. IOCP、task、channel、timer、TCP、process、WinHTTP、SQLite 原生 probe 通过且
   resource counter 有界；
7. `nomo-lsp` 原生启动并完成 protocol smoke；
8. `setup-nomo` 检测 ARM64、选择正确 ZIP、验证 SHA-256 并运行 installed-tool
   smoke；
9. 发布 ARM64 ZIP、checksum、provenance/attestation、release note 与 coordinated
   snapshot metadata；
10. Windows x64 Preview regression gate 保持绿色；
11. 平台文档明确 Windows-wide path、Regex 与大文件限制；
12. 双语 RFC 记录 protected CI 链接与精确 merge commit。

仅在 x64 通过编译不够；仅有一个 ARM64 hello-world 也不足以满足 Runtime 与 release
门禁。

## 10. 备选方案

| 方案 | 优点 | 不采用原因 |
| --- | --- | --- |
| 只在 Windows ARM emulation 下发布 x64 tool | 工程工作最少 | 没有原生 compiler/generated-app 证据 |
| 把 x64→ARM64 cross-build 当作完整支持 | 可使用常见 hosted runner | 无法证明 ARM64 Runtime 行为与清理 |
| 使用 ARM64EC | 可与 x64 module 互操作 | ABI/artifact 契约不同，明确不在范围内 |
| 使用 MinGW | 避免 MSVC library | 偏离现有 Windows Preview ABI 与 SDK 路径 |
| 原生 ARM64 + 受限 x64 cross-build | 保持 Windows parity 并分离证据 | Proposed |

## 11. 风险与回滚

- Hosted Windows ARM64 容量可能有限；受控 release host 必须可审计维护并生成
  attestation。
- Transitive native dependency 可能编译成功但因 alignment、memory ordering 或
  Windows API 差异失败。
- 如果未逐项验证路径，Clang、Visual Studio 与 Windows SDK discovery 可能混合
  architecture。
- x64 emulation 可能掩盖所谓原生工具实际为 x64。
- 在 Runtime parity 前发布 package 会产生只能通过 hello-world 的误导性下载。

Accepted 前，该 target 保持显式 Preview capability gate，不进入 stable-support
声明。失败的 release candidate 可撤回，不改变 Windows x64 status。

## 12. 决策与实施计划

本 RFC 首次以 `Proposed`、`Implementation Status: Not implemented` 合并。建议顺序：

1. target model、Clang/MSVC/SDK discovery 与 PE inspection；
2. compiler 与 generated application 原生 build/run；
3. Windows Runtime 与 dependency parity；
4. `nomo-lsp` 与 `setup-nomo`；
5. release packaging、checksum 与 attestation；
6. 分离 native 与 x64 cross-build CI；
7. 通过独立 evidence PR 做任何状态提升。

任何 implementation branch 都不能仅凭提案断言其已经 Accepted。在 merged code 与
test 能支持更精确的 evidence-backed 更新之前，实现状态必须保持
`Not implemented`。

## 13. 参考

- [Microsoft：Visual Studio on Arm-powered devices](https://learn.microsoft.com/en-us/visualstudio/install/visual-studio-on-arm-devices)
- [Microsoft：配置项目 target platform](https://learn.microsoft.com/en-us/visualstudio/ide/how-to-configure-projects-to-target-platforms)
- [Microsoft：PE format 与 ARM64 machine/relocation](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
- [Microsoft：为 Windows 应用增加 Arm 支持](https://learn.microsoft.com/en-us/windows/arm/add-arm-support)
- [LLVM Clang：cross-compilation](https://clang.llvm.org/docs/CrossCompilation.html)
- [LLVM Clang Compiler User's Manual](https://clang.llvm.org/docs/UsersManual.html)
