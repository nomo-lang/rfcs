# Nomo Roadmap

This roadmap turns the v0.1 design plan into staged implementation goals.

## v0.1: Closed Loop

Goal: users can write, check, compile, and run small native programs.

- Freeze the v0.1 specification baseline.
- Complete the lexer, parser, AST, name resolution, type checks, and mutability checks.
- Keep `Option`, `Result`, `?`, `let mut`, call-site `mut`, structs, enums, and generics aligned with examples and tests.
- Keep the C99 backend readable and compilable by the system C compiler.
- Ship the minimal standard library: `std.io`, `std.fs`, `std.env`, `std.result`, `std.option`, `std.array`, `std.string`.
- Support stable JSON diagnostics for CLI, LSP, CI, and snapshot tests.
- Establish the namespace-first package model in `nomo.toml`, dependency aliases, `nomo.lock`, and `nomo deps`.

## v0.2: Developer Experience

- `nomo fmt`.
- `nomo test`.
- `nomo doc`.
- LSP hover, go-to-definition, and rename.
- Better multi-file and multi-package workspace support.
- Resolver cache, better dependency diagnostics, `nomo deps update`, and `nomo deps vendor`.
- Initial C FFI.
- `std.path`, `std.process`, and `std.time`.

## v0.3: Abstraction

- Minimal interface or trait model.
- Constrained generics.
- Richer pattern matching.
- More complete module visibility.
- Registry protocol or private-registry story.
- Better version conflict explanation.

## v0.4: Systems Boundary

- More complete C FFI.
- `unsafe` blocks.
- Cross-compilation configuration.
- Static linking strategy.
- Runtime configuration.

## v1.0: Stability Promise

Before v1.0, Nomo must stabilize syntax, core types, standard library APIs,
diagnostic codes, JSON diagnostic format, package structure, `nomo.toml`,
`nomo.lock`, canonical package IDs, C backend semantics, docs, and RFC process.
