# RFC 0043: C99 Backend Optimization and C/C++ Performance Parity

> Language: [中文](../../zh-CN/rfcs/0043-c99-backend-optimization-and-c-cpp-performance-parity.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0043 |
| Title | C99 backend optimization and C/C++ performance parity |
| Decision Status | Proposed |
| Implementation Status | Not implemented |
| Author | Nomo Language Working Group |
| Created | 2026-07-28 |
| Related topics | C99 backend, release builds, CFG MIR, proof-based optimization, Benchmarks Game, C, ISO C++20, performance evidence |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0016](./0016-incremental-semantic-graph-and-cache.md), [RFC 0017](./0017-target-triples-and-cross-compilation.md), [RFC 0034](./0034-async-runtime-acceptance-and-benchmark-gates.md) |

## 1. Summary

This RFC proposes an optimization contract for Nomo's C99 backend and a narrow,
reproducible performance-parity gate against equivalent C and C++20 programs.
It adds public release-mode CLI forms:

```text
nomo build --release
nomo run --release
nomo test --release
nomoc build --release
```

Release-mode generated C and toolchain-owned C Runtime translation units are
compiled with the fixed optimization baseline:

```text
-O3 -DNDEBUG -fomit-frame-pointer
```

The baseline expressly excludes fast-math, LTO, PGO, and `-march=native`.
Release mode may optimize only where the compiler proves that Nomo's bounds,
overflow, division-by-zero, copy-on-write, evaluation-order, ownership, and
release semantics are preserved.

The compiler architecture evolves from typed IR/HIR through a control-flow
graph MIR and proof-based passes before C99 emission. Checks that are not proven
redundant remain executable. Benchmark-name, function-name, or source-hash
special cases are forbidden.

The performance gate freezes three single-threaded scalar workloads and compares
the candidate with the official C `gcc #8` algorithm and a line-equivalent
C++20 derivative. It uses two warmups, 30 paired blocks, log ratios, and a
one-sided 99% upper confidence bound. Passing this RFC is evidence only for the
frozen suite on qualified canonical hosts; it is not a claim that all Nomo
programs, platforms, or workloads match or exceed C or C++.

This document is `Proposed` / `Not implemented`. Existing optimized ad-hoc C
invocations and the exploratory CPU baseline do not implement the public CLI,
optimizer, C++20 comparison, or statistical acceptance gate defined here.

## 2. Motivation and boundaries

Nomo already lowers typed programs to portable C99, but a C compiler cannot
recover every high-level fact after ownership checks, copy-on-write operations,
checked arithmetic, or aggregate updates have been expanded into C. Stable
release performance therefore needs a language-aware optimization layer before
C emission, not only a stronger downstream C flag.

At the same time, a performance promise must be narrower than “C99 output is
fast.” It must pin source identities, inputs, toolchains, safety semantics,
measurement order, statistics, and the exact thresholds that decide the result.
This RFC defines that narrow contract.

This RFC does not:

- promise parity for arbitrary programs or all target platforms;
- authorize unsafe removal of bounds, overflow, division, ownership, COW, or
  cleanup behavior;
- change Nomo language semantics, source syntax, or the Preview compatibility
  policy;
- make async, I/O, memory-use, compiler-latency, or binary-size claims;
- permit target-specific `-march=native` release artifacts;
- require noisy shared CI runners to pass a wall-time threshold; or
- mark a stable `v0.1.0`, production readiness, or any release gate complete.

RFC 0034 remains the authority for async Runtime acceptance and Agent workload
benchmarks. The CPU suite in this RFC does not replace it.

## 3. Public release-mode CLI

### 3.1 Canonical commands

The following forms become the public contract:

```text
nomo build [path] --release
nomo run [path] --release [-- program-arguments]
nomo test [path] --release
nomoc build <input> --release
```

The existing target, workspace, lockfile, offline, diagnostic, and output
options remain composable with `--release` where the underlying command already
supports them. Release mode must be visible in help, verbose output, JSON build
records, cache keys, and provenance. An unknown or unsupported combination is
rejected explicitly; it must not silently fall back to a debug build.

`nomo run --release` builds the selected application in release mode before
execution. `nomo test --release` builds both the test harness and tested units
under release semantics while keeping test discovery, isolation, failure
reporting, and exit codes unchanged. `nomoc build --release` exposes the same
backend mode for direct compiler workflows.

### 3.2 Fixed downstream C flags

For the acceptance baseline, the C compiler receives:

```text
-O3 -DNDEBUG -fomit-frame-pointer
```

in addition to the repository's normal language-standard, target, include,
link, and platform flags. Their order must not allow a later default to cancel
the fixed optimization level. The effective compiler executable, version,
target, arguments, environment inputs, and final link command are recorded.

The release baseline forbids:

- `-ffast-math`, `-Ofast`, or equivalent relaxed floating-point modes;
- link-time optimization;
- profile-guided optimization;
- `-march=native`, `-mcpu=native`, or host-autodetected ISA expansion; and
- source-, function-, or benchmark-specific flag injection.

A future RFC may evaluate those modes as separately named profiles. They cannot
be silently added to the portable Preview release profile or used for this
RFC's acceptance evidence.

Debug assertions controlled only by Nomo's internal development configuration
may be removed under `-DNDEBUG`. Language-mandated runtime checks and cleanup
are not C `assert` statements and must remain unless a proof-based pass removes
an individual redundant check.

## 4. Semantic preservation

Release and debug builds have the same observable Nomo semantics. Optimization
must preserve at least:

- out-of-bounds detection and diagnostic/termination class;
- checked integer overflow behavior for operations that are checked by the
  language;
- division-by-zero and signed-division edge behavior;
- string, array, map, and aggregate copy-on-write separation;
- left-to-right evaluation and single evaluation where specified;
- borrow, move, publication, and ownership isolation;
- ARC retain/release balance, destructor/drop ordering, and exactly-once
  cleanup;
- error propagation, panic, exit status, and externally visible I/O order; and
- floating-point behavior under the existing non-fast-math contract.

“The benchmark output matches” is not sufficient proof. Negative tests must
exercise failing bounds, overflow, division, alias/COW separation, side-effect
order, and early-exit cleanup in optimized builds. Sanitizers and generated-C
inspection supplement, but do not replace, language-level assertions.

An optimization may remove a check only when its proof is attached to the MIR
fact or analysis result that justifies removal. If a proof is absent,
invalidated, target-dependent, or exceeds an analysis budget, the check remains.
Failing to optimize is correct; compiling an unproven unsafe transformation is
not.

## 5. Optimization architecture

### 5.1 Pipeline

The release pipeline is:

```text
parsed AST
  -> typed and ownership-checked IR/HIR
  -> control-flow graph MIR
  -> proof-producing analyses and transformations
  -> C99
  -> fixed release C compilation and link
```

The typed IR/HIR remains the source of resolved identities, types, effects,
ownership, and source diagnostics. CFG MIR introduces explicit basic blocks,
terminators, joins, loops, exceptional/cleanup edges, ownership operations,
checked operations, and effectful calls. C99 emission consumes optimized MIR;
it must not independently rediscover or bypass high-level safety decisions.

Debug and release modes may share the same MIR. Release enables additional
validated passes and the fixed C flags. Cache keys include the optimization
profile, target, compiler/runtime revision, pass-pipeline version, and relevant
toolchain configuration so debug or stale optimized artifacts cannot be reused.

### 5.2 Proof-based passes

Initial implementation may include:

- constant propagation and folding under Nomo overflow/floating-point rules;
- unreachable-block and dead-value elimination with effect/drop awareness;
- copy propagation and local common-subexpression elimination for pure values;
- branch and jump simplification;
- range analysis and redundant bounds-check elimination;
- nonzero/range proof for division checks;
- ownership/liveness-based retain/release coalescing;
- uniqueness proof for avoiding unnecessary COW detachment;
- scalar replacement and aggregate-update simplification where identity and
  cleanup remain unchanged; and
- loop-invariant movement or induction simplification only with dominance,
  effect, alias, overflow, and cleanup proofs.

Every pass declares preserved invariants and has unit, differential, and
negative tests. Pass order is versioned. Verification can reject malformed MIR
between passes in test/debug compiler builds.

### 5.3 Anti-special-casing rule

The compiler, Runtime, build driver, and generated C templates must not branch
on:

- benchmark or project names;
- the three workload identities;
- source paths or content hashes;
- function, variable, or package names used by the suite;
- formal input values; or
- the presence of the benchmark harness.

Optimizations must be stated over general typed/MIR properties and tested on
unrelated positive and negative programs. A benchmark-specific shortcut makes
the entire batch ineligible, even if output is correct.

## 6. Frozen performance suite

### 6.1 Workloads and inputs

The suite freezes these scalar, single-threaded workloads:

| Workload | Correctness input | Formal input | C algorithm identity |
| --- | ---: | ---: | --- |
| `spectral-norm` | 100 | 5500 | Benchmarks Game [`spectralnorm-gcc-8`](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/spectralnorm-gcc-8.html) |
| `n-body` | 1000 | 50000000 | Benchmarks Game [`nbody-gcc-8`](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/nbody-gcc-8.html) |
| `fannkuch-redux` | 7 | 12 | Benchmarks Game [`fannkuchredux-gcc-8`](https://benchmarksgame-team.pages.debian.net/benchmarksgame/program/fannkuchredux-gcc-8.html) |

The frozen baseline is the suite merged in
[`nomo#60`](https://github.com/nomo-lang/nomo/pull/60), as present at
[`nomo@c6712c1`](https://github.com/nomo-lang/nomo/commit/c6712c1da1f65fcbdf0ce037224d11482b6a7e35).
The v2 manifest must record and verify the following SHA-256 values:

| Workload | Nomo source SHA-256 | C source SHA-256 | Formal fixture SHA-256 |
| --- | --- | --- | --- |
| `spectral-norm` | `f0caae510fbdc02d998a8c49275c4aca0b771642348286ce871515840f47fe30` | `1f7f71ce5fc6f87432b3801fb57c3e8a619da2527c1b801154b8102c7af66c3e` | `f9d5b5e3eb7657cf1bbba4cc856651864df9cd9fd9a6be9b9bc5fcbb67150deb` |
| `n-body` | `30fb086f8d5c55e0b389b7451f921a463c953db286ec9f97bb55d8b7bc595988` | `a8649dd7babc5b9178fc363f4d61b468662c703668c2f8f4ddeab206b3e7e879` | `3e6c9ef9d26cfe312a4cd8e1b81b3f671b88fbce84de543e8c23c206a942504d` |
| `fannkuch-redux` | `0f6d0156c03cc3218b06a1adf560c5a3e3a99188fe9b7185b619b8a4ad8881e9` | `4d3135b2ed7a2fedb12b731c0f1a6bf901d763ac8421208fab6c4997c3ca9d80` | `4265a65135c506a68d90d6474003fb9030b7ee244a06c046bd89b3932a28ce20` |

The v1 `performance/benchmarksgame/manifest.json` frozen at that commit has
SHA-256
`bd8e5016fb376741478806d13585ebc37ade2104995bd411a2a161592f65c15f`.
The v2 manifest records its predecessor identity rather than mutating the
meaning of existing v1 result artifacts.

Changes to an algorithm, formal input, correctness fixture, or semantic work
performed by one implementation require a new RFC or an explicit amendment and
a fresh baseline. Formatting-only source changes still update the manifest SHA
and are reviewed for semantic equivalence.

### 6.2 C and C++20 references

For each workload:

- the C comparator is the frozen official naive `gcc #8` source already
  recorded with its upstream URL, license, retrieval date, and SHA;
- the C++ comparator is a line- and algorithm-equivalent ISO C++20 derivative
  of that C source;
- the C++ version must compile without language extensions using the matching
  LLVM driver and the fixed command shape
  `clang++ -std=c++20 -pedantic-errors -O3 -DNDEBUG -fomit-frame-pointer ...`;
- where the C `#8` source uses a fixed-size array, the C++ derivative uses an
  equivalent standard fixed-size representation;
- where the C `#8` source uses a runtime-sized VLA, ISO C++20 cannot preserve
  its stack storage class. The derivative may use a standard contiguous RAII
  representation such as `std::vector<T>` or `std::unique_ptr<T[]>`, provided
  it preserves the same number of arrays, element type, logical element
  capacity, lexical lifetime, allocation frequency per invocation,
  initialization work, and access order;
- each standard dynamic representation must be constructed exactly once at the
  corresponding VLA evaluation, with its final logical element count, and must
  not grow or reallocate. For the frozen suite this rule applies to the
  runtime-sized arrays in `spectral-norm` and `fannkuch-redux`;
- every VLA substitution must state in derivation metadata and result
  provenance that C stack storage became standard C++ dynamic storage, and
  must record the original count expression, chosen representation, element
  type, logical capacity, lifetime, and allocation frequency;
- a standard container is permitted only as the storage representation. The
  derivative must not use a stronger library algorithm, precomputation,
  capacity growth, custom allocator, SIMD implementation, or thread; and
- C and C++ use matching Clang/Clang++ versions, target, and fixed release
  optimization flags; and
- all Nomo, C, and C++ formal outputs must match the frozen fixture exactly.

The C++20 files do not yet exist. Their initial implementation PR must include
BSD 3-Clause attribution/derivation notes, source SHA values, a reviewable
mapping to C `#8`, and correctness tests before any timing result is eligible.
Shared CI must compile every C++ reference with `-std=c++20 -pedantic-errors`;
acceptance of a Clang VLA or any other non-standard C++ extension fails the
reference gate.

The frozen official C `#8` implementation remains a separate decisive
comparator. An allowed, disclosed stack-to-standard-dynamic-storage
substitution in C++ neither changes nor relaxes any per-workload or suite gate
against C. It also does not change the frozen workloads, inputs, statistical
method, thresholds, or comparator roles in this RFC.

Go remains a useful diagnostic lane and historical v1 comparison, but it does
not decide the C/C++ parity gates in this RFC. A semantic-C experiment may be
reported as a diagnostic control only; it must be labeled non-decisional and
must not enter workload or suite verdicts.

## 7. Measurement protocol

### 7.1 Build and host qualification

Candidate and `main` are built by their real `nomo build --release` path from
separate clean checkouts. The harness must not emulate release mode by invoking
`--emit-c` and compiling that output itself. It records both Nomo binaries,
commits, dirty state, generated-C SHA, final binary SHA, commands, compiler
versions, and target.

C uses the selected `clang` driver. C++ uses the matching `clang++` driver from
the same LLVM installation and version, with `-std=c++20 -pedantic-errors` plus
the fixed flags in section 3.2. Both use the same target; link libraries must be
equivalent for the same workload. Builds are completed before timing and
compile time is excluded.

A canonical host record includes OS/kernel, architecture, CPU model/topology,
memory, power mode, frequency/governor where applicable, thermal state,
virtualization, clock source/resolution, affinity/isolation, concurrent load,
toolchain versions, and the complete frozen-source lock. Missing required
qualification yields `ineligible`, never `pass`.

### 7.2 Warmup and paired blocks

For each workload and batch:

1. verify all implementations on the correctness input;
2. build all formal binaries;
3. run two warmups per timed lane; warmups are never samples;
4. execute 30 paired blocks;
5. run every lane exactly once in each block using a predeclared balanced order;
6. validate formal output before accepting its timing; and
7. retain every raw wall-time sample, order, exit status, and environment event.

The decisive pairings are:

- candidate Nomo versus C;
- candidate Nomo versus C++20; and
- candidate Nomo versus the pinned `main` Nomo build.

Candidate, `main`, C, C++, and diagnostic Go lanes share the balanced schedule
when present. Thermal, power, background-load, output, timeout, or collector
anomalies invalidate the affected batch rather than being silently discarded.
Outlier removal is forbidden. A predeclared whole-batch environmental
invalidation rule may reject and rerun a batch, but both the rejected artifact
and reason are retained.

### 7.3 Log ratios and one-sided 99% bounds

For workload \(w\), comparator \(q\), and block \(i\), calculate:

```text
x[w,q,i] = ln(candidate_wall[w,i] / comparator_wall[q,w,i])
```

For 30 paired observations, let `mean` be the arithmetic mean of `x`, `s` its
sample standard deviation, and `SE = s / sqrt(30)`. The point ratio and
one-sided 99% upper confidence bound are:

```text
R[w,q]   = exp(mean)
U99[w,q] = exp(mean + t(0.99, 29) * SE)
```

The implementation pins the critical-value calculation/library and tests it
against known vectors. A smaller ratio is faster: `1.00` is parity and values
above `1.00` are slower.

For each comparator, suite block \(i\) is the equal-weight mean of the three
workload log ratios in that block. `R[suite,q]` and `U99[suite,q]` use the same
formula over those 30 suite-block values. Equal weighting prevents a long
workload from dominating the suite merely because it takes more seconds.

## 8. Acceptance thresholds

Every inequality is inclusive. Both C and C++20 are independently decisive:

| Gate | Required result |
| --- | --- |
| Each workload vs C | `U99[w,C] <= 1.05` |
| Each workload vs C++20 | `U99[w,C++] <= 1.05` |
| Suite vs C | `R[suite,C] <= 1.00` and `U99[suite,C] <= 1.03` |
| Suite vs C++20 | `R[suite,C++] <= 1.00` and `U99[suite,C++] <= 1.03` |
| Candidate/main, each workload | `U99[w,main] <= 1.03` |
| Candidate/main, suite | `U99[suite,main] <= 1.02` |

A batch passes only if every row passes. A workload faster than one comparator
cannot offset failure against the other comparator. A suite pass cannot hide a
workload failure, and a candidate/main pass cannot replace absolute C/C++
parity.

The acceptance evidence requires two complete, independently qualified batches
on the canonical host. Each batch must pass all gates on its own; samples are
not pooled to rescue a failed batch. The artifacts record their temporal order
and any intervening reboot, toolchain, source, power, or environment change.

## 9. Session separation and evidence governance

### 9.1 Benchmark authority

The benchmark session owns:

- frozen source/input/fixture locks and C++ equivalence review;
- harness, collectors, balanced ordering, raw samples, statistics, schema, and
  verdict calculation;
- canonical-host qualification and the two acceptance batches; and
- publication of failures, ineligible runs, and uncertainty without tuning the
  compiler.

It must not change optimizer passes or performance-critical generated templates
during a decisive measurement session.

### 9.2 Optimizer authority

The optimizer session owns:

- HIR/MIR design, general proof-based passes, C99 lowering, and release CLI;
- semantic, differential, generated-C, and regression tests;
- investigation of benchmark evidence without changing the frozen measurement
  contract; and
- a candidate commit that remains fixed while decisive batches run.

It must not edit benchmark thresholds, source payloads, order, statistics, or
eligibility rules to make a candidate pass. Any necessary contract change
returns through RFC review before new evidence is collected.

### 9.3 Shared CI and canonical evidence

Shared PR CI validates release-mode functionality, frozen SHA locks, C/C++/Nomo
correctness, statistics, schema, collectors, semantic preservation, and
candidate/main command provenance. It must not reject a PR using wall-time
thresholds from shared runners.

Performance acceptance comes only from the two qualified canonical-host
batches. Their raw artifacts, environment records, candidate/main commits,
toolchain identities, generated-C/binary hashes, computed ratios, bounds, and
verdicts are linked from a later RFC evidence PR. Results that miss a threshold
remain useful evidence but cannot set `Implementation Status: Implemented` or
`Decision Status: Accepted`.

## 10. Required implementation and test evidence

Implementation is complete only when all of the following have merged:

1. all four public `--release` command forms, help, diagnostics, cache/provenance
   behavior, and fixed C flags;
2. typed IR/HIR to CFG MIR lowering with verified cleanup/control-flow
   invariants;
3. general proof-based optimization passes with pass-order/version records;
4. positive and negative optimized semantic tests for bounds, overflow,
   division, COW, evaluation order, ownership, and cleanup;
5. C99/native and supported WASM behavior tests showing no release/debug
   semantic divergence for the supported surface;
6. frozen v2 benchmark manifest/schema, C++20 references, licenses, collectors,
   balanced schedule, statistics, and v1 result compatibility;
7. shared Linux, macOS, and Windows correctness/collector CI without timing
   thresholds;
8. two independently passing canonical-host batches;
9. documentation that states the exact scope and failed/ineligible evidence;
   and
10. a separate bilingual RFC status PR linking code PRs, merge commits,
    protected CI, and canonical artifacts.

Until then, this RFC remains Proposed. Landing only the CLI, only a MIR, only
compiler optimizations, or only benchmark harness v2 is a partial slice and
must be reported as such.

## 11. Risks and alternatives

### 11.1 Delegating everything to the C compiler

Only adding `-O3` is simpler, but loses typed ownership, bounds, and COW facts
before the downstream optimizer can use them. The fixed flags are necessary,
not sufficient.

### 11.2 Removing safety checks globally

This could improve a benchmark while changing the language. It is rejected.
Only proof-redundant individual checks may be removed.

### 11.3 Using minimum time or unpaired samples

Minimum time is sensitive to lucky noise, and unpaired groups respond poorly to
thermal drift. Paired log ratios preserve within-block comparison and make the
uncertainty gate explicit.

### 11.4 Gating every PR on shared-runner timing

This creates flaky and environment-dependent merges. Shared CI verifies
correctness and the measurement machinery; controlled canonical hosts produce
performance decisions.

### 11.5 Claiming universal native-speed parity

Three scalar programs cannot justify that claim. The accepted wording, if the
gate later passes, is limited to parity under this frozen suite, toolchain,
protocol, and qualified-host evidence.

## 12. Recommendation and current status

Adopt this contract as a Proposed direction for release-mode optimization and a
narrow C/C++20 parity target. Implement the public release path and semantic
optimizer first, implement the independent benchmark v2 authority second, then
freeze a candidate and collect two canonical-host batches.

No implementation or performance claim is approved by merging this document.
Promotion to `Accepted` and `Implemented` requires the separate evidence PR in
section 10. Nomo remains Preview, and `RELEASE-GATE.md` remains unchanged until
its own platform, packaging, editor, ecosystem, external-use, and performance
requirements are actually satisfied.
