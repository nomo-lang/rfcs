# RFC 0042: Windows ARM64 Preview Platform Support

> Language: [中文](../../zh-CN/rfcs/0042-windows-arm64-preview-platform-support.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0042 |
| Title | Windows ARM64 Preview platform support |
| Decision Status | Proposed |
| Implementation Status | Not implemented |
| Author | Nomo Language Working Group |
| Created | 2026-07-28 |
| Related topics | Windows 11, ARM64, target triples, C99 backend, MSVC ABI, release packaging, platform parity |
| Related RFCs | [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0018](./0018-package-signing-provenance-and-transparency.md), [RFC 0032](./0032-sharded-executor-reactor-and-blocking-pool.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. Summary

This RFC proposes Windows 11 on ARM64 as a first-class Nomo Preview target
under the canonical target triple `aarch64-pc-windows-msvc`. The target uses
the LLVM Clang GNU-style driver while preserving the MSVC ABI and linking
against the installed Visual Studio ARM64 libraries and Windows SDK.

Preview support requires native ARM64 build, run, test, and release evidence.
An x64 Windows host may build ARM64 artifacts only when the ARM64 Visual
Studio and SDK components are installed; such a cross-build is useful
packaging evidence but never substitutes for native ARM64 runtime tests.

The acceptance gate covers the compiler, generated applications, the
Windows Runtime surface, LSP, installer, release archive, checksums, and
attestation. This proposal does not claim implementation, stable support, or
production readiness.

## 2. Scope and platform identity

### 2.1 Supported Preview environment

The proposed platform contract is:

| Dimension | Contract |
| --- | --- |
| Operating system | Windows 11 on ARM64 |
| Nomo target triple | `aarch64-pc-windows-msvc` |
| Object and executable format | COFF / PE32+ ARM64 |
| C compiler frontend | LLVM Clang GNU-style driver |
| C/C++ ABI | Microsoft ARM64 ABI |
| Link inputs | ARM64 MSVC libraries plus an ARM64-capable Windows SDK |
| Native execution host | Windows 11 ARM64 |
| Optional build host | Windows x64 with ARM64 VS/SDK components installed |

The target is not inferred from an emulated process alone. Native evidence
records both the operating-system architecture and the process architecture so
an x64-emulated `nomo.exe` cannot be mistaken for a native ARM64 toolchain.

### 2.2 Non-goals

This RFC does not add or promise:

- ARM32 Windows;
- ARM64EC binaries, mixed ARM64X images, or x64 interoperability through the
  ARM64EC ABI;
- MinGW, GNU Windows CRTs, or a `windows-gnu` target;
- non-Windows hosts cross-linking MSVC binaries;
- execution of ARM64 output on a Windows x64 CI runner;
- a stable `v0.1.0` support guarantee; or
- resolution of existing Windows-wide path, Regex, or large-file limitations.

Those targets require separate contracts because they change ABI, link,
runtime, distribution, or test assumptions.

## 3. Toolchain contract

### 3.1 Clang driver and ABI

The C99 backend invokes the GNU-style `clang` driver with an explicit target:

```text
clang --target=aarch64-pc-windows-msvc ...
```

The implementation must not silently switch this target to MinGW, ARM64EC, or
the host architecture. It may discover Clang through the existing Nomo
toolchain configuration or a validated Visual Studio/LLVM installation, but
the selected executable, version, target triple, Windows SDK version, library
paths, and effective arguments must be available in verbose diagnostics and CI
artifacts.

Using the GNU-style driver is a command-line contract, not an ABI change.
Generated objects and executables use the Microsoft ARM64 ABI and link against
ARM64 MSVC/Windows SDK inputs. `clang-cl` may exist in the installation, but it
is not the driver selected by this RFC.

### 3.2 Required Visual Studio and SDK components

Both native and x64-to-ARM64 build environments require:

- an LLVM Clang installation that supports
  `aarch64-pc-windows-msvc`;
- the ARM64 C/C++ build tools and libraries installed through Visual Studio
  or Visual Studio Build Tools;
- a Windows SDK installation containing ARM64 libraries and headers; and
- a link environment whose library paths resolve to ARM64 inputs.

An x64 installation containing only x86/x64 C++ tools is insufficient. Missing
ARM64 components must produce an actionable target-unavailable diagnostic
rather than an x64 binary or an opaque link failure.

The RFC does not freeze one Visual Studio product version or Windows SDK
revision. Each release set records and attests the versions actually used, and
the release gate may pin a tested range.

### 3.3 Native and cross-build commands

On a native Windows 11 ARM64 host, the target must support:

```powershell
nomo build --target aarch64-pc-windows-msvc
nomo run --target aarch64-pc-windows-msvc
nomo test --target aarch64-pc-windows-msvc
nomo build --release --target aarch64-pc-windows-msvc
nomoc build src/main.nomo --target aarch64-pc-windows-msvc
```

The native release pipeline also builds and runs ARM64 `nomo.exe`,
`nomoc.exe`, generated applications, test binaries, and required helper
programs.

On Windows x64, only build-oriented commands are accepted for this target:

```powershell
nomo build --target aarch64-pc-windows-msvc
nomo build --release --target aarch64-pc-windows-msvc
nomoc build src/main.nomo --target aarch64-pc-windows-msvc
```

`nomo run` and execution-backed `nomo test` must not report success without an
explicit native ARM64 execution provider. This RFC does not define remote
execution, emulation, or automatic deployment. A cross-build job records
compile/link/PE evidence only.

## 4. Windows x64 Preview parity

Windows ARM64 support is measured against the currently declared Windows x64
Preview surface. A feature that works on x64 may not be marked supported on
ARM64 until equivalent ARM64 behavior is exercised, including error paths and
resource cleanup.

Parity means:

- the same Nomo source and manifest semantics;
- the same CLI commands, JSON diagnostics, exit-code classes, and build
  directory contract;
- the same ownership, ARC/COW, overflow, bounds, division, evaluation-order,
  cancellation, and cleanup semantics;
- the same C99 Runtime API and Windows system API families;
- the same release metadata and snapshot compatibility policy; and
- no architecture-specific source annotations for ordinary applications.

Parity does not erase existing Windows-wide limitations. Until separately
implemented and accepted, both Windows x64 and Windows ARM64 must document:

- incomplete non-ASCII/Unicode path guarantees where narrow or ANSI path
  boundaries remain;
- incomplete full Regex feature/behavior coverage; and
- incomplete validation and guarantees for large-file boundaries.

These are known Windows-wide limitations, not ARM64-specific regressions.
ARM64 support must not advertise them as solved.

## 5. Compiler, backend, and artifact requirements

### 5.1 Compiler and generated C

The compiler must:

1. parse and validate `aarch64-pc-windows-msvc` as a supported target;
2. propagate pointer width, integer layout, alignment, calling convention, and
   target capability facts through typed lowering;
3. generate C99 without x64-only intrinsics, inline assembly, type sizes, or
   object-file assumptions;
4. compile every toolchain-owned Runtime translation unit for ARM64;
5. use only ARM64 libraries at the final link; and
6. preserve deterministic target metadata in diagnostics and build records.

Host and target identities remain separate. Running an ARM64 compiler process
does not imply the default target was selected, and an x64 host selecting the
ARM64 target does not imply runtime validation.

### 5.2 PE machine validation

The release gate inspects every executable and relevant object/import library.
Native ARM64 PE images must report:

```text
IMAGE_FILE_MACHINE_ARM64 = 0xAA64
```

At minimum this check covers:

- `nomo.exe`;
- `nomoc.exe`;
- one generated hello-world executable;
- one synchronous Runtime probe; and
- every separately shipped executable in the ARM64 ZIP.

An x64 (`0x8664`), ARM64EC (`0xA641`), ARM64X (`0xA64E`), or unknown machine
value fails the ARM64 release gate.

### 5.3 Architecture-sensitive code

Any private atomic, IOCP, socket, process, TLS/WinHTTP, SQLite, clock, or
alignment shim must compile and run natively on ARM64. Architecture-specific
code is isolated behind target modules with:

- compile-time target assertions;
- exact-width integer and pointer conversions;
- no unaligned access assumptions;
- documented memory-order behavior; and
- positive and negative target tests.

This RFC does not authorize cross-shard Runtime work or change RFC 0031-0040
semantics.

## 6. Required runtime and ecosystem evidence

Native Windows 11 ARM64 CI or a controlled release host must exercise the
following matrix:

| Area | Required native ARM64 evidence |
| --- | --- |
| CLI/compiler | `nomo`, `nomoc`, new/check/build/run/test/doc/fmt, JSON diagnostics |
| Generated application | Debug and release C99 compile/link/run, panic and non-zero exit |
| IOCP | registration, completion, cancellation, stale-generation cleanup |
| Task Runtime | scopes, join, cancellation, deadlines, frame drops |
| Channels/select | send/receive/close, timers, receive/send/join select, loser cleanup |
| TCP | DNS, connect, read/write, half-close, timeout/cancellation |
| Process | start, stdin/stdout/stderr, exit, terminate, handle cleanup |
| HTTP | WinHTTP HTTP/HTTPS, timeout, headers, redirects and supported streaming boundaries |
| SQLite | bundled ARM64 compilation, open/execute/query/close, file and memory databases |
| Files/time/environment | supported path classes, bounded I/O, clocks, args/env |
| `nomo-lsp` | native ARM64 server startup, initialize, hover/signature/diagnostic smoke |
| `setup-nomo` | ARM64 host detection, archive selection, checksum verification, install smoke |

Tests record zero live-handle/task/frame/channel/timer/process/socket leaks for
the counters applicable to each probe. Cross-build evidence may cover
compile/link and PE identity, but every row that executes behavior requires a
native ARM64 result.

## 7. Release and supply-chain contract

A Windows ARM64 Preview release is a separate timestamped artifact. Its
published evidence includes:

- an architecture-explicit ZIP name;
- `nomo.exe`, `nomoc.exe`, required licenses, and release metadata;
- SHA-256 for the archive and each independently published binary;
- the source revision and coordinated release-set version;
- Rust, Clang, Visual Studio toolset, and Windows SDK versions;
- host OS build, native host architecture, and target triple;
- PE machine inspection results;
- protected CI and controlled-host runtime-test links;
- a signed provenance/attestation identifying workflow, source, builder, and
  subjects; and
- installer evidence showing `setup-nomo` selected the ARM64 archive and
  verified its digest before installation.

An x64 archive containing an emulated `nomo.exe` is not an ARM64 release.
Release notes must distinguish native compiler execution, native generated
applications, and x64-to-ARM64 cross-build evidence.

## 8. Diagnostics and failure behavior

The implementation adds stable, actionable diagnostics for:

- an unrecognized or not-yet-enabled ARM64 target;
- missing Clang target support;
- missing ARM64 MSVC libraries or Windows SDK components;
- an x64 link input entering an ARM64 link;
- attempts to run/test ARM64 output without a native execution provider;
- a produced PE image whose machine type is not ARM64; and
- use of a Runtime capability that remains unsupported on Windows ARM64.

Diagnostics must print the requested target, detected host/process
architecture, selected compiler, and the missing component category without
leaking local credentials or unrelated environment variables. The toolchain
must fail closed; it must never fall back to Windows x64 and still label the
artifact ARM64.

## 9. Acceptance gate

The RFC may move to `Accepted` and implementation to `Implemented` only in a
separate evidence PR after all applicable gates pass:

1. native Windows 11 ARM64 `nomo` and `nomoc` build and execute;
2. debug and release generated applications compile, link, and execute
   natively;
3. PE inspection reports `0xAA64` for every shipped executable;
4. x64-to-ARM64 build succeeds only in an environment with validated ARM64
   Visual Studio/SDK components;
5. cross-build jobs are clearly separated from native runtime jobs;
6. IOCP, task, channel, timer, TCP, process, WinHTTP, and SQLite native probes
   pass with bounded resource counters;
7. `nomo-lsp` starts and completes a protocol smoke natively;
8. `setup-nomo` detects ARM64, selects the correct ZIP, verifies SHA-256, and
   runs an installed-tool smoke;
9. the ARM64 ZIP, checksums, provenance/attestation, release notes, and
   coordinated snapshot metadata are published;
10. Windows x64 Preview regression gates remain green;
11. platform documentation identifies the Windows-wide path, Regex, and
    large-file limitations; and
12. protected CI links and exact merge commits are recorded in both language
    versions of this RFC.

Passing compilation on x64 is insufficient. Passing one native hello-world is
also insufficient for the Runtime and release gates.

## 10. Alternatives

| Alternative | Benefit | Why it is not selected |
| --- | --- | --- |
| Ship x64 tools under Windows ARM emulation only | Minimal engineering work | Does not provide native compiler/generated-app evidence |
| Accept x64-to-ARM64 cross-build as full support | Uses common hosted runners | Cannot prove Runtime behavior or cleanup on ARM64 |
| Use ARM64EC | Interoperates with x64 modules | Different ABI and artifact contract; explicitly out of scope |
| Use MinGW | Avoids MSVC libraries | Diverges from the existing Windows Preview ABI and SDK path |
| Native ARM64 plus bounded x64 cross-build | Preserves Windows parity and separates evidence | Proposed |

## 11. Risks and rollback

- Hosted native Windows ARM64 capacity may be limited; controlled release
  hosts require auditable maintenance and attestation.
- A transitive native dependency may compile but fail because of alignment,
  memory ordering, or Windows API differences.
- Clang, Visual Studio, and Windows SDK discovery can accidentally mix
  architectures unless every selected path is validated.
- x64 emulation can hide that a supposedly native tool is x64.
- Supporting packaging before Runtime parity would create a misleading
  download that passes only hello-world tests.

Until acceptance, the target remains behind an explicit Preview capability
gate and is absent from stable-support claims. A failed release candidate is
withdrawn without changing Windows x64 status.

## 12. Decision and implementation plan

This RFC initially lands as `Proposed` with `Implementation Status:
Not implemented`. The recommended implementation order is:

1. target model, Clang/MSVC/SDK discovery, and PE inspection;
2. compiler plus generated-application native build/run;
3. Windows Runtime and dependency parity;
4. `nomo-lsp` and `setup-nomo`;
5. release packaging, checksums, and attestation;
6. native and x64 cross-build CI separation; and
7. a separate evidence PR for any status promotion.

No implementation branch may treat this proposal as accepted by assertion.
The implementation status must remain `Not implemented` until merged code and
tests justify a more precise evidence-backed update.

## 13. References

- [Microsoft: Visual Studio on Arm-powered devices](https://learn.microsoft.com/en-us/visualstudio/install/visual-studio-on-arm-devices)
- [Microsoft: configure projects to target platforms](https://learn.microsoft.com/en-us/visualstudio/ide/how-to-configure-projects-to-target-platforms)
- [Microsoft: PE format and ARM64 machine/relocations](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)
- [Microsoft: add Arm support to Windows applications](https://learn.microsoft.com/en-us/windows/arm/add-arm-support)
- [LLVM Clang: cross-compilation](https://clang.llvm.org/docs/CrossCompilation.html)
- [LLVM Clang Compiler User's Manual](https://clang.llvm.org/docs/UsersManual.html)
