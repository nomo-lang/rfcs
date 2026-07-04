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
7. `nomo test` discovers and runs `#[test]` functions in a project or workspace.
8. `nomo doc` generates project or workspace documentation from doc comments.

v0.1 does not pursue maximal feature coverage, but rather a closed loop of specification, implementation, testing, and RFC decisions.

---

## 1. v0.1 Delivery Boundary

### 1.1 Must Deliver

| Module | Deliverable | Acceptance method |
| --- | --- | --- |
| Project tooling | `nomo new`, `nomo check`, `nomo build`, `nomo run`, `nomo fmt`, `nomo test`, `nomo doc` | Example projects can be created, checked, built, run, formatted, tested, and documented |
| Compiler frontend | Lexer, Parser, AST, syntax diagnostics | golden tests stable |
| Name resolution | Resolution of packages, imports, types, functions, fields, enum variants | Success/failure cases covered |
| Type checking | Basic types, functions, structs, enums, generics, `Result`, `Option` | Type checking tests pass |
| Mutability checking | `let mut`, call-site `mut`, mutable-borrow uniqueness | Mutability tests covered |
| C99 backend | HIR/C IR to readable C99 | Generated C compiles with `clang` or `gcc` |
| Minimal standard library | `std.io`, `std.fs`, `std.env`, `std.result`, `std.option`, `std.array`, `std.string`, `std.char`, `std.os`, `std.time`, `std.process`, `std.testing`, `std.debug`, `std.log`, `std.path`, `std.math`, `std.num`, `std.hash`, `std.crypto`, `std.json`, `std.net`, `std.http`, `std.regex`, `std.collections` | Example programs usable |
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

### 2.5 Numeric Operators

Current preview builds support binary numeric arithmetic with standard
precedence:

```rust
let value: i64 = a - b * c / d % e
let ratio: f64 = total / count
let grouped: i64 = -(a + b) * c
let ready: bool = !failed && connected || cached
let mut masked: i64 = value & mask &^ clear << 1 >> shift | extra ^ flags
masked &^= clear
masked++
masked--
```

- `+`, `-`, `*`, and `/` require two matching numeric operands and return the
  same type.
- Parenthesized subexpressions override precedence.
- Unary `-` requires an `i32`, `i64`, or `f64` operand and returns the same type.
- `%` requires two matching integer operands and returns the same integer type.
- `&&` and `||` require two `bool` operands, return `bool`, and short-circuit
  left-to-right.
- `!` requires one `bool` operand and returns `bool`.
- `&`, `|`, `^`, and `&^` require two matching integer operands and return the
  same integer type.
- `<<` and `>>` require an integer left operand and an integer shift amount, and
  return the left operand type.
- Equality and ordering comparisons return `bool`.
- Statement-level compound assignment supports `+=`, `-=`, `*=`, `/=`, `%=`,
  `<<=`, `>>=`, `&=`, `^=`, `|=`, and `&^=` for mutable variables and mutable
  struct fields. Each form type-checks as `target = target op value`.
- Statement-level postfix update supports `target++` and `target--` for mutable
  variables and mutable struct fields. They type-check as `target += 1` and
  `target -= 1`, are not expressions, and do not produce values.
- Runtime divide-by-zero, signed `i32`/`i64` arithmetic overflow, and invalid
  shift amounts panic. Signed right shift is defined as arithmetic shift:
  negative values shift in `1` bits, and non-negative values shift in `0` bits.

### 2.6 Functions

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```

- Function parameters are immutable by default.
- The last expression is the return value.
- An explicit `return expr` is allowed, mainly for early returns.
- A `void`-returning function may omit the trailing expression.

### 2.7 Structs and Methods

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

v0.1 supports minimal `interface` declarations and static `impl Interface for Type` method implementations:

```rust
pub interface Display {
    fn to_string(self) -> string
}

impl Display for User {
    fn to_string(self) -> string {
        return self.name
    }
}
```

The compiler checks `impl Interface for Type` blocks statically: the interface
must be declared or imported as public API, every required method must exist on
the impl, and method type parameters, parameter count, parameter mutability,
parameter types, and return type must match after substituting `Self` with the
concrete impl target.

The current interface MVP does not support trait objects, associated types,
blanket impls, dynamic dispatch, or generic constraints such as
`fn print<T: Display>(value: T)`. That full constraint system remains outside
v0.1. Higher-kinded types and generic specialization are also out of scope.

### 2.9 C FFI and `unsafe`

v0.1 supports a minimal C FFI entry point:

```rust
extern "C" {
    fn puts(message: string) -> i32
}

fn main() -> void {
    unsafe {
        puts("hello")
    }
}
```

`extern "C"` declarations describe C function signatures; extern calls must be
inside an `unsafe { ... }` block. The current MVP supports passing a Nomo
`string` to C `puts`; codegen passes the underlying NUL-terminated byte buffer.
Arbitrary raw pointers, C struct layout inference, header binding generation,
multi-statement unsafe blocks, and general link metadata are left for later slices.

---

## 2.10 Package Identity and Dependency Aliases

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
  `nomo test --workspace`, `nomo doc --workspace`,
  `nomo deps resolve --workspace`, and `nomo deps tree --workspace` discover the
  workspace root, expand `members` minus `exclude`, and visit each member
  package in stable path order.
- `path` sources are resolved by reading the target package's `nomo.toml` and are
  included recursively in `nomo.lock` and `nomo deps tree`.
- `git` sources use a project-local `.nomo/deps/git/` cache keyed by canonical
  package ID and source URL. Cache misses clone the repository; cache hits run
  `git fetch --tags --prune origin` before checkout. The resolver checks out the
  requested `branch`, `tag`, or `rev` when one is declared; branch sources also
  run `git pull --ff-only`. The checkout is validated against the expected
  canonical package ID and locked to the actual `HEAD` revision. A manifest
  dependency may specify only one checkout selector: `branch`, `tag`, or `rev`.
- `nomo deps clean-cache [path]` removes the project or workspace
  `.nomo/deps/git` cache and leaves `nomo.lock`, source files, and build
  artifacts untouched. The command is idempotent.
- `nomo deps update [path] [alias-or-package]` refreshes the lockfile from the
  current manifest sources. Without a target it updates all dependencies; with
  an alias or canonical package ID it first verifies that the target is a direct
  dependency, then rewrites the lockfile. The current implementation rewrites
  the full lockfile. `--precise <version-or-rev>` requires a direct dependency
  target and only changes the source used for this lockfile update, without
  editing `nomo.toml`: registry dependencies use the value as `version`, git
  dependencies use it as `rev` with branch/tag selectors cleared, and path
  dependencies are rejected.
- `nomo deps vendor [path] [--workspace] [--dir vendor] [--sync]` ensures a
  lockfile exists, copies locked `path` and `git` dependency sources into the
  vendor directory, and writes `nomo-vendor.toml`. `--sync` removes the vendor
  directory before copying. Registry leaves are recorded as skipped until
  registry archive fetching is implemented. Locked/offline project module
  loading falls back to the default `vendor/` directory when the original locked
  path source or git cache checkout is missing.
- Resolved `path` and `git` packages are locked with a `sha256:` checksum over
  the package `nomo.toml` and `src/` contents. Registry leaves do not carry a
  checksum in v0.1 because registry archive fetching is out of scope.
- `nomo deps tree` reads the existing `nomo.lock` when present, verifies
  reachable locked `path` sources and matching git cache checkouts against their
  checksum, and falls back to resolving the current manifest when no lockfile
  exists. Missing `path` sources and git cache entries may still be shown as
  offline locked entries.
- `--locked` is accepted by `nomo build`, `nomo deps resolve`, and
  `nomo deps tree`. It requires an existing lockfile and rejects missing or
  out-of-date direct dependencies without rewriting `nomo.lock`.
- `--offline` prevents git fetch/clone and uses existing lockfiles or git cache
  checkouts. Without a lockfile, uncached git dependencies fail instead of
  accessing the network. `--frozen` is equivalent to `--locked --offline`.
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
  v0.1 source. With no path or a project directory path it discovers the project
  manifest and formats `src/**/*.nomo` in stable path order. With a workspace
  root it formats each member's `src/**/*.nomo`. With a loose source directory
  that has no `nomo.toml`, it recursively formats contained `.nomo` files. With a
  direct `.nomo` file path it formats only that file and does not require a manifest.
  `--check` reports `would format <path>` without writing and exits with
  failure if any target differs. The formatter emits canonical whitespace,
  indentation, and package/import/item spacing while preserving Rust-style line
  comments (`//`, `///`, `//!`) and nested block comments (`/* */`, `/** */`,
  `/*! */`) as leading or trailing trivia attached to nearby declarations and
  statements. `nomoc` does not gain a formatter command in v0.1.
- `nomo test [path] [--workspace] [--package <package>] [--filter <text>] [--json] [--locked] [--offline] [--frozen]`
  discovers top-level `#[test]` functions in project `src/**/*.nomo` and runs
  them one by one. Test functions must be non-generic, take no parameters,
  return `void`, and must not be named `main`. Each test reuses the project
  module resolver and dependency resolver, compiling a temporary runner
  `main() -> void` that calls the test function; an existing project `main` is
  not executed as the test entrypoint. `--filter` keeps tests whose full name
  contains the filter text, `--workspace` runs workspace members, `--package`
  selects a package id or member name, and `--json` emits a stable test report.
- `nomo doc [path] [--workspace] [--package <package>] [--std] [--open] [--json] [--output <dir>]`
  extracts module and item documentation from Rust-style doc comments (`//!`,
  `///`, `/*! */`, `/** */`) and combines it with parser AST signatures,
  visibility, and source locations for packages/modules, functions, extern
  functions, structs, enums, interfaces, methods, and constants. Struct fields,
  enum variants, and interface methods are emitted as child documentation items
  and participate in the search index. By default it writes
  `build/doc/index.html`, package/module HTML
  pages, and `search-index.json`; `--json` emits the machine-readable
  documentation model without writing files. `--workspace` documents workspace members, `--package`
  selects a package id or member name, and `--std` generates the current
  built-in standard-library module index.

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
- `Option.Some(value)` evaluates to `value`.
- `Option.None` causes the current function to return `Option.None` early.
- The current function's return type must be a compatible carrier: using `expr?` on a `Result` value requires the current function to return a compatible `Result`; using `expr?` on an `Option` value requires the current function to return a compatible `Option`.

v0.1 does not introduce a `try` keyword or statement syntax; postfix `?` is
the unified propagation syntax for errors and absence.

v0.1 does not automatically merge error types. Cross-layer error conversion uses explicit `std.result.map_err(named_converter)?`, as accepted by [RFC 0001](./rfcs/0001-error-propagation-and-conversion.md).

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
- `Array.pop` and `Array.remove` return `Option<T>`; empty arrays and
  out-of-bounds removals return `None`.
- `Array.set` and `Array.insert` trigger a `panic` on out-of-bounds.
- `Array.iter` returns a snapshot value accepted by `for ... in`; a full
  iterator type is deferred until traits/interfaces exist.

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
std.char
std.os
std.time
std.process
std.testing
std.debug
std.log
std.path
std.math
std.num
std.hash
std.crypto
std.json
std.regex
std.collections
```

### 6.1 `std.io`

```rust
pub struct IoError {
    pub message: string
}

io.print("hello")
io.println("hello")
io.eprint("error")
io.eprintln("error")
io.read_line() -> Result<string, IoError>
```

### 6.2 `std.fs`

```rust
pub struct FsError {
    pub message: string
}

pub struct FileMetadata {
    pub is_file: bool
    pub is_dir: bool
    pub size: u64
}

pub struct File

fn read_to_string(path: string) -> Result<string, FsError>
fn write_string(path: string, content: string) -> Result<void, FsError>
fn read_bytes(path: string) -> Result<Array<u32>, FsError>
fn write_bytes(path: string, bytes: Array<u32>) -> Result<void, FsError>
fn exists(path: string) -> bool
fn metadata(path: string) -> Result<FileMetadata, FsError>
fn create_dir(path: string) -> Result<void, FsError>
fn remove_dir(path: string) -> Result<void, FsError>
fn read_dir(path: string) -> Result<Array<string>, FsError>
fn open(path: string) -> Result<File, FsError>

impl File {
    fn read_to_string(self) -> Result<string, FsError>
    fn write_string(self, content: string) -> Result<void, FsError>
    fn close(self) -> void
}
```

`metadata` returns file-type flags and byte size. Directory size is
platform-defined.
`open` opens an existing file for reading and writing. `File.read_to_string`
reads the whole file from the beginning; `File.write_string` writes at the
beginning and flushes.
`read_dir` returns entry names, not full paths, and skips `.` and `..`.
`remove_dir` removes an empty directory only.

### 6.3 `std.env`

`env.set` mutates the current process environment and panics if the platform
call fails. `env.cwd` panics if the current directory cannot be read.
`env.temp_dir` reads `TMPDIR`, `TEMP`, then `TMP`, and falls back to `/tmp`.

```rust
env.args() -> Array<string>
env.get(name: string) -> Option<string>
env.set(name: string, value: string) -> void
env.cwd() -> string
env.home_dir() -> Option<string>
env.temp_dir() -> string
```

### 6.4 `std.array`

```rust
Array.new<T>() -> Array<T>
Array.len(self) -> u64
Array.push(mut self, value: T)
Array.get(self, index: u64) -> Option<T>
Array.pop(mut self) -> Option<T>
Array.remove(mut self, index: u64) -> Option<T>
Array.set(mut self, index: u64, value: T) -> void
Array.insert(mut self, index: u64, value: T) -> void
Array.clear(mut self) -> void
Array.iter(self) -> Array<T>
```

### 6.5 `std.result`

`std.result` helpers are available as module functions, specific imports, and
value methods. `map`, `map_err`, and `and_then` take named, unqualified,
non-generic converter functions in v0.1; closures are out of scope. `and_then`
requires the converter to return a `Result<U, E>` with the same error type.

```rust
result.is_ok(value: Result<T, E>) -> bool
result.is_err(value: Result<T, E>) -> bool
result.unwrap_or(value: Result<T, E>, default: T) -> T
result.map(value: Result<T, E>, converter: fn(T) -> U) -> Result<U, E>
result.map_err(value: Result<T, E1>, converter: fn(E1) -> E2) -> Result<T, E2>
result.and_then(value: Result<T, E>, converter: fn(T) -> Result<U, E>) -> Result<U, E>
```

### 6.6 `std.option`

`std.option` helpers are available as module functions, specific imports, and
value methods. `map` and `and_then` take named, unqualified, non-generic
converter functions in v0.1; closures are out of scope.

```rust
option.is_some(value: Option<T>) -> bool
option.is_none(value: Option<T>) -> bool
option.unwrap_or(value: Option<T>, default: T) -> T
option.map(value: Option<T>, converter: fn(T) -> U) -> Option<U>
option.and_then(value: Option<T>, converter: fn(T) -> Option<U>) -> Option<U>
```

### 6.7 `std.string`

`std.string` helpers operate on UTF-8 byte strings in v0.1. `trim` and case
conversion use ASCII character classes rather than Unicode grapheme or locale
rules. `string.split(value, separator)` panics if `separator` is empty.

```rust
string.len(self) -> u64
string.concat(self, other: string) -> string
string.is_empty(self) -> bool
string.contains(self, needle: string) -> bool
string.starts_with(self, prefix: string) -> bool
string.ends_with(self, suffix: string) -> bool
string.split(self, separator: string) -> Array<string>
string.trim(self) -> string
string.to_lower(self) -> string
string.to_upper(self) -> string
```

### 6.8 `std.char`

`std.char` character-class helpers use ASCII character classes in v0.1.
`char.to_string` encodes a Nomo `char` scalar as a UTF-8 string.

```rust
char.is_digit(value: char) -> bool
char.is_alpha(value: char) -> bool
char.is_whitespace(value: char) -> bool
char.to_string(value: char) -> string
```

### 6.9 `std.os`

`std.os` helpers report properties of the C compiler target used for the
generated program.

```rust
os.platform() -> string
os.arch() -> string
os.path_separator() -> string
os.line_ending() -> string
```

`os.platform()` returns `windows`, `macos`, `linux`, `freebsd`, or `unknown`.
`os.arch()` returns `aarch64`, `x86_64`, `x86`, `arm`, or `unknown`.

### 6.10 `std.time`

`std.time` provides basic wall-clock, monotonic-clock, duration, formatting, and
sleep helpers.
`time.now_millis()` returns Unix epoch milliseconds. `time.monotonic_millis()`
is suitable for measuring elapsed time within one process and must not be
compared with wall-clock timestamps. `Duration` stores a signed millisecond
count. `time.format_duration` uses the stable v0.1 form `<millis>ms`, for
example `1500ms`. `time.duration_seconds` panics if converting seconds to
milliseconds would overflow `i64`. `time.sleep` and `time.sleep_millis` panic
for negative durations or platform sleep failures.

```rust
struct Duration {
    millis: i64
}

time.now_millis() -> i64
time.monotonic_millis() -> i64
time.duration_millis(millis: i64) -> Duration
time.duration_seconds(seconds: i64) -> Duration
time.duration_as_millis(duration: Duration) -> i64
time.format_duration(duration: Duration) -> string
time.sleep(duration: Duration) -> void
time.sleep_millis(duration: i64) -> void
```

### 6.11 `std.process`

```rust
pub struct ProcessError {
    pub message: string
}

pub struct ProcessOutput {
    pub status: i32
    pub stdout: string
    pub stderr: string
}
```

`std.process` provides synchronous process helpers. `process.spawn` starts a
shell command, waits for it to finish, and returns its exit code without
capturing stdout or stderr. `process.status` has the same exit-code behavior
and remains as the descriptive helper name for callers that only need the final
status. `process.exec` captures stdout and returns `Err` for spawn, read,
close, or non-zero-exit failures. `process.output` captures stdout and stderr
separately and returns `Ok(ProcessOutput)` even when the command exits non-zero;
callers inspect `status`. v0.1 does not expose asynchronous process handles.

```rust
process.exit(code: i64) -> void
process.spawn(command: string) -> Result<i32, ProcessError>
process.status(command: string) -> Result<i32, ProcessError>
process.exec(command: string) -> Result<string, ProcessError>
process.output(command: string) -> Result<ProcessOutput, ProcessError>
```

### 6.12 `std.path`

`std.path` provides pure string path helpers. v0.1 uses POSIX-style `/`
separators and does not query the host filesystem or resolve symlinks.

```rust
path.join(left: string, right: string) -> string
path.basename(path: string) -> string
path.dirname(path: string) -> string
path.extension(path: string) -> string
path.normalize(path: string) -> string
path.is_absolute(path: string) -> bool
```

### 6.13 `std.math`

`std.math` provides basic numeric helpers. `abs`, `min`, and `max` preserve
the input numeric type and require matching numeric operands. The remaining
helpers are `f64` functions.

```rust
math.abs(value: number) -> same number type
math.min(left: number, right: same number type) -> same number type
math.max(left: number, right: same number type) -> same number type
math.floor(value: f64) -> f64
math.ceil(value: f64) -> f64
math.round(value: f64) -> f64
math.sqrt(value: f64) -> f64
math.pow(base: f64, exponent: f64) -> f64
math.sin(value: f64) -> f64
math.cos(value: f64) -> f64
```

### 6.14 `std.num`

`std.num` provides numeric conversion helpers. Parse helpers return
`Result<T, NumError>` and are intended to compose with the `?` operator.
Checked integer helpers return `Option<T>`; wrapping integer helpers return the
same integer type with wraparound semantics.
`num.to_string` is module-qualified in v0.1 to avoid colliding with
`char.to_string`.

```rust
pub struct NumError {
    pub message: string
}

num.parse_i64(value: string) -> Result<i64, NumError>
num.parse_u64(value: string) -> Result<u64, NumError>
num.parse_f64(value: string) -> Result<f64, NumError>
num.to_string(value: i64 | i32 | u32 | u64 | f64) -> string
num.checked_add(left: integer, right: same integer type) -> Option<same integer type>
num.checked_sub(left: integer, right: same integer type) -> Option<same integer type>
num.checked_mul(left: integer, right: same integer type) -> Option<same integer type>
num.wrapping_add(left: integer, right: same integer type) -> same integer type
num.wrapping_sub(left: integer, right: same integer type) -> same integer type
num.wrapping_mul(left: integer, right: same integer type) -> same integer type
```

### 6.15 `std.hash`

`std.hash` provides stable non-cryptographic FNV-1a 64-bit hashing helpers for
strings and `Array<u32>` byte arrays. `HashState` carries incremental hash state
by value, so callers can build the same hash from multiple string or byte
chunks without mutable references. Byte arrays use the same `0..255` element
convention as `std.fs` byte helpers and `std.crypto.random_bytes`.
Cryptographic digests belong to `std.crypto`, not `std.hash`.

```rust
pub struct HashState {
    pub value: u64
}

hash.string(value: string) -> u64
hash.bytes(value: Array<u32>) -> u64
hash.new() -> HashState
hash.write_string(state: HashState, value: string) -> HashState
hash.write_bytes(state: HashState, value: Array<u32>) -> HashState
hash.finish(state: HashState) -> u64
```

### 6.16 `std.crypto`

`std.crypto` provides cryptographic helpers. Digest helpers hash string input
as UTF-8 bytes and return lowercase hexadecimal strings. `random_bytes`
returns OS-generated random bytes as `u32` values in the inclusive range
`0..255`; v0.1 uses `Array<u32>` until a dedicated byte array type exists.

```rust
crypto.sha256(value: string) -> string
crypto.sha512(value: string) -> string
crypto.random_bytes(count: u64) -> Array<u32>
```

### 6.17 `std.json`

`std.json` provides a v0.1 JSON validation and serialization boundary.
`JsonValue` stores validated raw JSON text. `json.parse` validates JSON syntax
and returns `Result<JsonValue, JsonError>`; `json.stringify` returns the stored
JSON text. Structured field/index access remains a later slice.

```rust
pub struct JsonValue {
    pub raw: string
}

pub struct JsonError {
    pub message: string
}

json.parse(value: string) -> Result<JsonValue, JsonError>
json.stringify(value: JsonValue) -> string
```

### 6.18 `std.net`

`std.net` provides blocking TCP and UDP helpers in the current slice.
`net.connect` opens a TCP connection to a host and port. `net.listen` binds a
blocking `TcpListener`; `TcpListener.accept` returns the next `TcpStream`, and
`TcpListener.close` closes the listener socket. `TcpStream.write_string` writes
a string to the peer, `TcpStream.read_to_string` reads until the peer closes its
write side, and `TcpStream.close` closes the stream socket. `net.udp_bind` binds
a blocking `UdpSocket`; `UdpSocket.recv_from_string` receives a datagram as a
`UdpDatagram` with `data`, `host`, and `port`, `UdpSocket.send_to_string` sends
a datagram, and `UdpSocket.close` closes the socket. Listener address
inspection, backlog configuration, and nonblocking handles remain later
`std.net` slices.

```rust
pub struct NetError {
    pub message: string
}

pub struct TcpStream

pub struct TcpListener

pub struct UdpDatagram {
    pub data: string
    pub host: string
    pub port: i64
}

pub struct UdpSocket

net.connect(host: string, port: i64) -> Result<TcpStream, NetError>
net.listen(host: string, port: i64) -> Result<TcpListener, NetError>
net.udp_bind(host: string, port: i64) -> Result<UdpSocket, NetError>

impl TcpListener {
    fn accept(self) -> Result<TcpStream, NetError>
    fn close(self) -> void
}

impl TcpStream {
    fn write_string(self, content: string) -> Result<void, NetError>
    fn read_to_string(self) -> Result<string, NetError>
    fn close(self) -> void
}

impl UdpSocket {
    fn recv_from_string(self, max_bytes: i64) -> Result<UdpDatagram, NetError>
    fn send_to_string(self, content: string, host: string, port: i64) -> Result<void, NetError>
    fn close(self) -> void
}
```

### 6.19 `std.http`

`std.http` provides blocking plain-HTTP client and basic server helpers in the
current slice. `http.get` requests an `http://` URL. `http.post` sends a string
body to an `http://` URL. Responses expose the numeric HTTP status and response
body. `http.listen` creates a blocking server socket, `http.accept` accepts one
request exchange, and `http.respond_string` writes a string response. Programs
should close handles with `defer http.close_exchange(exchange)` and
`defer http.close_server(server)` so cleanup runs on both normal returns and `?`
early returns. TLS, custom headers, redirects, chunked transfer decoding,
streaming bodies, routing, and concurrent server helpers remain later
`std.http` slices.

```rust
pub struct HttpError {
    pub message: string
}

pub struct HttpResponse {
    pub status: i64
    pub body: string
}

pub struct HttpServer {
}

pub struct HttpExchange {
    pub method: string
    pub path: string
    pub body: string
}

http.get(url: string) -> Result<HttpResponse, HttpError>
http.post(url: string, body: string) -> Result<HttpResponse, HttpError>
http.listen(host: string, port: i64) -> Result<HttpServer, HttpError>
http.accept(server: HttpServer) -> Result<HttpExchange, HttpError>
http.respond_string(exchange: HttpExchange, status: i64, body: string) -> Result<void, HttpError>
http.close_server(server: HttpServer) -> void
http.close_exchange(exchange: HttpExchange) -> void
```

### 6.20 `std.regex`

`std.regex` provides v0.1 regular expression helpers. `Regex` stores the
source pattern after compile-time validation by `regex.compile`. Compile
failures are reported as `Result.Err(RegexError)`, so callers use postfix `?`
for propagation. `regex.captures` returns `None` when there is no match, or
`Some(Array<string>)` containing the full match followed by capture groups.

```rust
pub struct Regex {
    pub pattern: string
}

pub struct RegexError {
    pub message: string
}

regex.compile(pattern: string) -> Result<Regex, RegexError>
regex.is_match(regex: Regex, value: string) -> bool
regex.captures(regex: Regex, value: string) -> Option<Array<string>>
```

### 6.21 `std.collections`

`std.collections` provides v0.1 string-specialized collections. `StringMap`
stores string keys and string values. `StringSet` stores unique strings. Update
helpers return the updated collection value; generic `HashMap` remains deferred
until interface/trait-constrained generics are available.

```rust
pub struct StringMap {
    pub keys: Array<string>
    pub values: Array<string>
}

pub struct StringSet {
    pub values: Array<string>
}

collections.map_new() -> StringMap
collections.map_len(map: StringMap) -> u64
collections.map_get(map: StringMap, key: string) -> Option<string>
collections.map_contains(map: StringMap, key: string) -> bool
collections.map_set(map: StringMap, key: string, value: string) -> StringMap
collections.map_remove(map: StringMap, key: string) -> StringMap

collections.set_new() -> StringSet
collections.set_len(set: StringSet) -> u64
collections.set_contains(set: StringSet, value: string) -> bool
collections.set_insert(set: StringSet, value: string) -> StringSet
collections.set_remove(set: StringSet, value: string) -> StringSet
```

### 6.22 `std.testing`

`std.testing` provides assertion helpers intended for `#[test]` functions. A
failed assertion panics, which makes the current test fail under `nomo test`.
`testing.assert_equal` supports strings plus primitive bool, char, integer, and
`f64` values with matching types. `testing.assert_error` accepts any
`Result<T, E>` and passes only for `Err`.

```rust
testing.assert(condition: bool, message: string) -> void
testing.assert_equal<T: primitive-or-string>(left: T, right: T) -> void
testing.assert_error<T, E>(result: Result<T, E>) -> void
```

### 6.23 `std.debug`

`std.debug` provides lightweight debugging helpers. Print helpers write to
stderr. `debug.panic` uses the same panic path as the language builtin.
`debug.backtrace` is a stable placeholder in v0.1; it returns a string so code
can depend on the API before real stack capture is available.

```rust
debug.print(message: string) -> void
debug.println(message: string) -> void
debug.panic(message: string) -> void
debug.backtrace() -> string
```

### 6.24 `std.log`

`std.log` provides lightweight leveled logging helpers. Log messages are
written to stderr as `[level] message` lines. `NOMO_LOG` controls the minimum
enabled level; accepted values are `debug`, `info`, `warn`, `error`, and
`off`. Unset or unknown values use the default `info` threshold.

```rust
log.debug(message: string) -> void
log.info(message: string) -> void
log.warn(message: string) -> void
log.error(message: string) -> void
log.enabled(level: string) -> bool
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
| `E0100-E0199` | Lexical errors |
| `E0200-E0299` | Syntax errors |
| `E0300-E0399` | Name resolution |
| `E0400-E0499` | Type checking |
| `E0500-E0599` | Borrow and mutability |
| `E0600-E0699` | Modules and packages |
| `E0700-E0799` | C backend |
| `E0800-E0899` | Standard library and runtime API |
| `E0900-E0999` | Manifest, lockfile, and dependency resolver |
| `E1000-E1099` | Workspace |
| `E1100-E1199` | Test runner |
| `E1200-E1299` | Documentation generator |
| `E1300-E1399` | LSP semantic API |
| `E1400-E1499` | Registry and publish |
| `E1500-E1599` | FFI and unsafe |

A JSON diagnostic contains at least:

```json
{
  "status": "error",
  "error_code": "E0203",
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

Diagnostic documentation lives under `docs/diagnostics/`. LSP diagnostics should
set `codeDescription` to the matching error-code page, for example `E0404.md`.

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
