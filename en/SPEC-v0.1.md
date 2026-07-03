# Nomo v0.1 Specification Baseline

> 语言 / Language: [中文](../zh-CN/SPEC-v0.1.md) | English

> **Status**: Draft baseline
> **Purpose**: To serve as the common discussion baseline for all RFCs in this RFC repository.
> **Principle**: First define an implementable, testable, deliverable v0.1 closed loop, then evolve the language capabilities through RFCs.

---

## 0. Summary

The goal of Nomo v0.1 is to deliver a minimal but complete Stage 0 compilation pipeline:

1. `nomo new` creates a project.
2. `nomo check` performs syntax, name resolution, type, and mutability checking.
3. `nomo build` invokes `nomoc` to transpile `.nomo` source into C99.
4. The system C compiler produces an executable.
5. `nomo run` builds and runs the example program.
6. `nomo fmt` normalizes v0.1 source formatting for projects and standalone files.

v0.1 does not pursue maximal feature coverage, but rather a closed loop of specification, implementation, testing, and RFC decisions.

---

## 1. v0.1 Delivery Boundary

### 1.1 Must Deliver

| Module | Deliverable | Acceptance method |
| --- | --- | --- |
| Project tooling | `nomo new`, `nomo check`, `nomo build`, `nomo run`, `nomo fmt` | Example projects can be created, checked, built, run, and formatted |
| Compiler frontend | Lexer, Parser, AST, syntax diagnostics | golden tests stable |
| Name resolution | Resolution of packages, imports, types, functions, fields, enum variants | Success/failure cases covered |
| Type checking | Basic types, functions, structs, enums, generics, `Result`, `Option` | Type checking tests pass |
| Mutability checking | `let mut`, call-site `mut`, mutable-borrow uniqueness | Mutability tests covered |
| C99 backend | HIR/C IR to readable C99 | Generated C compiles with `clang` or `gcc` |
| Minimal standard library | `std.io`, `std.fs`, `std.env`, `std.result`, `std.option`, `std.array`, `std.string` | Example programs usable |
| JSON diagnostics | Stable machine-readable error structure | Snapshot tests covered |

### 1.2 Explicitly Out of Scope for v0.1

- `go` coroutines, `chan<T>`, implicit Context.
- GPU kernels, PTX, SPIR-V.
- WebAssembly, bare metal, GUI.
- Full Tensor, BigDecimal, package-publishing ecosystem.
- Self-hosting compiler.
- LLVM / Cranelift native backends.
- Full trait/interface constraint system.
- Full lifetime/region borrow system.

---

## 2. Language Core

### 2.1 Files, Packages, and Imports

Each `.nomo` file belongs to a package:

```rust
package app.main

import std.io
import std.fs
import std.result.Result
```

v0.1 supports importing a package or a specific type/function. Wildcard imports are not supported. The origin of every symbol must be traceable.

### 2.2 Bindings and Mutability

```rust
let name = "Nomo"
let mut count = 0
count = count + 1
```

- `let` is immutable by default.
- `let mut` allows reassignment or modification of internal state.
- Reading an uninitialized variable is not allowed.
- v0.1 does not allow variable shadowing.

### 2.3 Basic Types

Built into v0.1:

```text
bool i32 i64 u32 u64 f64 char string void
```

`int` is not introduced as an alias for now, to avoid platform bit-width ambiguity.

### 2.4 Explicit Conversion

Implicit numeric conversion is forbidden:

```rust
let age: i32 = 18
let ratio: f64 = age as f64
```

### 2.5 Functions

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

- Function parameters are immutable by default.
- The last expression is the return value.
- An explicit `return expr` is allowed, mainly for early returns.
- A `void`-returning function may omit the trailing expression.

### 2.6 Structs and Methods

```rust
pub struct User {
    pub id: string
    email: string
}

impl User {
    pub fn get_email(self) -> string {
        self.email
    }
}
```

- Types, fields, functions, and methods are private by default.
- `pub` means visible outside the package.
- v0.1 only allows adding `impl` methods to types defined within the current package.

### 2.7 Enums and `match`

```rust
pub enum Option<T> {
    Some(T)
    None
}
```

```rust
fn label(value: Option<i32>) -> string {
    match value {
        Option.Some(n) => "some"
        Option.None => "none"
    }
}
```

- `match` must be exhaustive over all variants.
- v0.1 does not yet support the `_` wildcard arm.
- Whether `Option` / `Result` allow unqualified variants is discussed in [RFC 0007](./rfcs/0007-unqualified-variant-access.md).

### 2.8 Generics

v0.1 supports generic functions, structs, and enums, and generates concrete C code via monomorphization:

```rust
pub fn identity<T>(value: T) -> T {
    value
}
```

v0.1 does not support trait/interface constraints, higher-kinded types, or generic specialization.

---

## 2.9 Package Identity and Dependency Aliases

Nomo v0.1 uses a namespace-first package model. A package's stable identity is
`owner/package`, for example `nomo-lang/json`; Git URLs, registries, branches,
revisions, and local paths are dependency sources rather than source-level import
identities.

Basic `nomo.toml` shape:

```toml
[package]
namespace = "fynn"
name = "hello"
version = "0.1.0"
edition = "2026"

[dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
local_utils = { package = "fynn/utils", path = "../utils" }
http = { package = "nomo-lang/http", git = "https://github.com/nomo-lang/http.git", rev = "2a4b8c1" }
cli = { package = "nomo-lang/cli", git = "https://github.com/nomo-lang/cli.git", branch = "stable" }
fmt = { package = "nomo-lang/fmt", git = "https://github.com/nomo-lang/fmt.git", tag = "v0.1.0" }
```

`nomo.toml` is parsed as standard TOML. Comments, escaped strings, inline
tables, and dependency subtables such as `[dependencies.local_utils]` are valid
TOML inputs and must not be reimplemented with a line-oriented parser.

Workspace roots may share package defaults and dependencies:

```toml
[workspace]
members = ["apps/*", "packages/*"]
default-members = ["apps/cli"]
resolver = "1"

[workspace.package]
namespace = "fynn"
edition = "2026"

[workspace.dependencies]
json = { package = "nomo-lang/json", version = "0.1.0" }
core = { package = "fynn/core", path = "packages/core" }
```

Member packages inherit explicit fields with TOML dotted keys:

```toml
[package]
name = "cli"
version = "0.1.0"
namespace.workspace = true
edition.workspace = true

[dependencies]
json.workspace = true
core.workspace = true
```

Source imports use dependency aliases:

```rust
package app.main

import json.parser
import local_utils.path
import http.client
```

v0.1 must validate:

- `[package]` namespace, name, version, and edition.
- Dependency aliases using Nomo identifier rules.
- Dependency `package` values using `owner/package` canonical IDs.
- The `std`, `nomo`, and `core` namespaces are reserved and cannot be used as
  package owners.
- `std` is a built-in reserved import root. User manifests do not need to
  declare it, ordinary dependencies cannot use `std` as an alias, and `std` is
  not written as a normal package entry in `nomo.lock`.
- Exactly one dependency source among `path`, `git`, and `version`.
- Legacy manifests that still declare `std = "0.1.0"` or
  `std = { package = "nomo-lang/std", version = "0.1.0" }` may be accepted as
  compatibility input, but the declaration is ignored as a normal dependency.
- Registry/version sources are recorded as leaf lockfile entries in v0.1; an
  optional `registry` endpoint may be stored as source metadata, but public
  registry fetching is out of scope.
- `nomo.lock` is standard TOML. Package entries are stored as `[[package]]`
  tables with `id`, `alias`, `source`, optional source metadata, `checksum`, and
  dependency edge strings. Workspace lockfiles additionally store `[[root]]`
  tables that map each member package ID to its direct dependency edges. Invalid
  TOML, unknown package fields, and mismatched field types are rejected.
- Workspace member manifests may inherit `namespace`, `name`, `version`, and
  `edition` from `[workspace.package]` using `<field>.workspace = true`.
- Workspace member dependencies may inherit a dependency with
  `<alias>.workspace = true`; the alias must exist in `[workspace.dependencies]`.
  Workspace dependency `path` sources are interpreted from the workspace root
  and rebased for member package resolution.
- A manifest containing `[workspace]` but no `[package]` is a workspace root,
  not a package manifest. Member-level project commands operate on the selected
  member package; `nomo deps resolve` for a member writes the lockfile at the
  workspace root. `nomo check --workspace`, `nomo build --workspace`,
  `nomo deps resolve --workspace`, and `nomo deps tree --workspace` discover the
  workspace root, expand `members` minus `exclude`, and visit each member
  package in stable path order. Other workspace-wide batch commands are defined
  by later workspace graph work.
- `path` sources are resolved by reading the target package's `nomo.toml` and are
  included recursively in `nomo.lock` and `nomo deps tree`.
- `git` sources are cloned into a project-local `.nomo/deps/git/` cache, checked
  out to the requested `branch`, `tag`, or `rev` when one is declared, validated
  against the expected canonical package ID, and locked to the actual `HEAD`
  revision. A manifest dependency may specify only one checkout selector:
  `branch`, `tag`, or `rev`.
- Resolved `path` and `git` packages are locked with a `sha256:` checksum over
  the package `nomo.toml` and `src/` contents. Registry leaves do not carry a
  checksum in v0.1 because registry archive fetching is out of scope.
- `nomo deps tree` reads the existing `nomo.lock` when present, verifies
  reachable locked `path` sources and matching git cache checkouts against their
  checksum, and falls back to resolving the current manifest when no lockfile
  exists. Missing `path` sources and git cache entries may still be shown as
  offline locked entries.
- The same canonical package ID resolving to different sources or versions is a
  v0.1 error.
- Project-level `nomo check/build/run` validates source imports against
  dependency aliases declared in `nomo.toml`. Local project modules use Flat+Dir
  lookup: `import app.util` first resolves `src/util.nomo`, then
  `src/util/main.nomo`; `import app.main` resolves `src/main.nomo`. Imported
  `path` and `git` dependency modules use the same lookup under the dependency
  `src/` directory. Imported local modules and imported dependency modules
  contribute public API to the current v0.1 compile unit, including public
  functions, constants, structs, enums, and public methods; private items are
  not exported. `nomoc` remains a standalone source-file compiler and only
  accepts built-in `std.*` imports.
- `nomo-lsp` diagnostics should match project-level `nomo check`: project files
  read dependency aliases from the nearest `nomo.toml`, while standalone files
  without a manifest keep `nomoc` behavior.
- `nomo run <source.nomo>` supports a direct standalone source file outside a
  project manifest. The file still uses the normal `package` declaration and
  normal imports. If it has no explicit `fn main`, then top-level script
  statements after all declarations are compiled as a synthesized
  `main() -> void`. Declarations must appear before top-level script statements,
  and an explicit `main` cannot be combined with top-level script statements.
  Project-level `check/build/run` and `nomoc check/build` do not enable this
  script entry mode.
- `nomo fmt [path] [--check] [--json-errors]` is an AST-based formatter for
  v0.1 source. With no path or a directory path it discovers the project
  manifest and formats `src/**/*.nomo` in stable path order. With a direct
  `.nomo` file path it formats only that file and does not require a manifest.
  `--check` reports `would format <path>` without writing and exits with
  failure if any target differs. The formatter emits canonical whitespace,
  indentation, and package/import/item spacing; it does not preserve original
  layout trivia. Because v0.1 has no comment tokens, comment-like input remains
  a syntax error instead of being preserved by `fmt`. `nomoc` does not gain a
  formatter command in v0.1.

Public registry fetching and complex version solving are out of scope for v0.1;
v0.1 may reject multiple versions of the same canonical package ID directly.

---

## 3. Error Handling

### 3.1 Dual-Track System

| Type | Mechanism | Example |
| --- | --- | --- |
| Program defect | `panic` | Out of bounds, unreachable branch, internal error |
| Business failure | `Result<T, E>` | File not found, parse failure, network failure |

v0.1 does not implement exception unwinding. Business failures must be reflected in the function signature.

### 3.2 `Result<T, E>`

```rust
package std.result

pub enum Result<T, E> {
    Ok(T)
    Err(E)
}
```

### 3.3 `?` Propagation

Rules for `expr?`:

- `Result.Ok(value)` evaluates to `value`.
- `Result.Err(error)` causes the current function to return `Result.Err(error)` early.
- The current function's return type must be a compatible `Result`.

v0.1 does not automatically merge error types. Cross-layer error conversion is discussed in [RFC 0001](./rfcs/0001-error-propagation-and-conversion.md).

### 3.4 The Compiler's Awareness of `Option` / `Result`

`Option` and `Result` are both standard library types and are used by `?`, exhaustiveness checking, and the C backend layout. Whether to fix them as lang items is discussed in [RFC 0006](./rfcs/0006-option-result-lang-items.md).

---

## 4. Memory Model

v0.1 adopts three categories of values:

| Category | Example | Management |
| --- | --- | --- |
| Pure values | `bool`, integers, floats, small structs | C value semantics |
| Standard-library-managed values | `string`, `Array<T>` | Reference counting; arrays copy-on-write |
| Explicit heap objects | Later versions' `Box<T>` / `Rc<T>` | Not available in v0.1 |

### 4.1 `string`

`string` is an immutable value-semantics type. Assignment shares the underlying storage and increments the reference count; concatenation produces a new string.

### 4.2 `Array<T>`

`Array<T>` is a value-semantics managed container:

```rust
import std.array.Array

let mut nums = Array.new<i32>()
nums.push(1)
```

- Read operations share the underlying storage.
- Write operations trigger copy-on-write when the reference count is greater than 1.
- `Array.get` returns `Option<T>`.
- `Array.set` triggers a `panic` on out-of-bounds.

The runtime cost and degradation strategy of ARC/COW are discussed in [RFC 0003](./rfcs/0003-arc-cow-runtime-cost.md).

### 4.3 Mutable Borrow

```rust
fn inc(mut counter: Counter) {
    counter.value = counter.value + 1
}

fn main() {
    let mut counter = Counter { value: 0 }
    inc(mut counter)
}
```

- `mut` must be written at both the declaration site and the call site.
- `mut p: T` denotes a mutable borrow within the current call stack, not an ordinary copy.
- A mutable borrow must not escape.
- The same value must not be mutably borrowed more than once within the same call expression.

The checking strength is discussed in [RFC 0004](./rfcs/0004-mutable-borrow-uniqueness.md).

---

## 5. Syntax and Name Resolution

### 5.1 Significant Newlines

v0.1 uses significant newlines as the default separator for statements, fields, enum variants, and `match` arms. Semicolons are not used as the regular statement terminator.

The newline rules and continuation anchors are fixed by [RFC 0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md).

### 5.2 Dot Access

`.` is unified as postfix dot access:

```rust
std.io
Result.Ok
self.email
items.get(i)
```

The parser produces an unresolved dot chain; name resolution dispatches it as a module path, type member, enum variant, field, or method based on the kind of the left-hand entity.

---

## 6. Standard Library v0.1

```text
std.io
std.fs
std.env
std.result
std.option
std.array
std.string
```

### 6.1 `std.io`

```rust
io.println("hello")
io.eprintln("error")
```

### 6.2 `std.fs`

```rust
pub struct FsError {
    pub message: string
}

fn read_to_string(path: string) -> Result<string, FsError>
fn write_string(path: string, content: string) -> Result<void, FsError>
```

### 6.3 `std.array`

```rust
Array.new<T>() -> Array<T>
Array.len(self) -> u64
Array.push(mut self, value: T)
Array.get(self, index: u64) -> Option<T>
Array.set(mut self, index: u64, value: T) -> void
```

### 6.4 `std.string`

```rust
string.len(self) -> u64
string.concat(self, other: string) -> string
```

---

## 7. Compiler Architecture

The Stage 0 pipeline:

```text
.nomo source
  -> Lexer
  -> Parser
  -> AST
  -> Name Resolution
  -> Type Check + Mutability Check
  -> HIR
  -> C99 Codegen
  -> cc / clang / gcc
  -> Executable
```

Recommended internal representations:

| Layer | Role |
| --- | --- |
| AST | Preserves source structure, used for diagnostics |
| HIR | The core representation after name resolution, type checking, and mutability checking |
| C IR | A simplified representation oriented toward C99 output |

C backend principles:

- Generate readable C.
- Package paths participate in symbol mangling to avoid naming collisions.
  v0.1 generated C function and nominal type symbols use each item's source
  package path, so dependency APIs are not emitted as root-application package
  symbols.
- The standard library runtime is linked as C source files.
- Layouts such as `Result`, `Option`, `Array` must be covered by tests.

---

## 8. Diagnostics Specification

Diagnostics must support both human-readable output and JSON output.

Error code ranges:

| Range | Category |
| --- | --- |
| `N0100-N0199` | Lexical errors |
| `N0200-N0299` | Syntax errors |
| `N0300-N0399` | Name resolution |
| `N0400-N0499` | Type checking |
| `N0500-N0599` | Borrow and mutability |
| `N0600-N0699` | Modules and packages |
| `N0700-N0799` | C backend |

A JSON diagnostic contains at least:

```json
{
  "status": "error",
  "error_code": "N0203",
  "severity": "error",
  "message": "type mismatch",
  "source": {
    "file": "src/main.nomo",
    "line": 4,
    "column": 18,
    "length": 3
  },
  "suggestions": []
}
```

---

## 9. Examples Directory

v0.1 requires at least the following examples:

```text
examples/
├── hello/
├── args/
├── read_file/
├── result_chain/
├── struct_methods/
└── array_basic/
```

Each example supports at least:

```bash
nomo check examples/hello
nomo run examples/hello
```

---

## 10. Acceptance Matrix

Before releasing v0.1, the following must be satisfied:

- `cargo test` passes.
- `cargo fmt --check` passes.
- `nomo fmt --check` succeeds on checked-in `.nomo` examples and fixtures.
- Lexer / Parser golden tests are stable.
- Type checking, name resolution, and mutability tests cover both success and failure paths.
- C backend generated code compiles with at least one mainstream C compiler.
- `hello`, `read_file`, `result_chain` can `nomo run`.
- JSON diagnostic snapshots are stable.

---

## 11. RFC Index Entry

Currently pending RFCs:

- [RFC 0001](./rfcs/0001-error-propagation-and-conversion.md): Error propagation and conversion.
- [RFC 0002](./rfcs/0002-match-wildcard-and-nesting.md): `match` wildcard and nested destructuring.
- [RFC 0003](./rfcs/0003-arc-cow-runtime-cost.md): ARC/COW runtime cost.
- [RFC 0004](./rfcs/0004-mutable-borrow-uniqueness.md): Mutable-borrow uniqueness.
- [RFC 0005](./rfcs/0005-newline-sensitivity-and-dot-resolution.md): Newline-sensitive syntax and `.` resolution.
- [RFC 0006](./rfcs/0006-option-result-lang-items.md): `Option`/`Result` lang items.
- [RFC 0007](./rfcs/0007-unqualified-variant-access.md): Unqualified enum variants.
