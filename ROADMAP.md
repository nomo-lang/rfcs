# Nomo Roadmap

This roadmap follows the current-full-scope preview strategy. Capabilities are
implemented in reviewable slices, but formatter, workspace, package management,
LSP, interfaces, FFI, registry, documentation, and editor support are all part
of the current preview target rather than deferred version buckets.

## Current Preview Delivery Tracks

- Compiler pipeline: lexer, parser, AST, semantic checks, mutability checks,
  monomorphization, C99 code generation, and native linking.
- Language model: `Option`, `Result`, postfix `?`, structs, enums, pattern
  matching, generics, minimal interfaces, `T: Interface` constraints, C FFI,
  and explicit `unsafe` blocks.
- Project tooling: `nomo new/check/build/run/fmt/test/doc/clean` plus the
  standalone `nomoc` compiler driver.
- Package model: standard TOML manifests, workspace inheritance, canonical
  package identities, dependency aliases, a workspace-root lockfile, resolver
  cache, update, vendor, locked/offline/frozen modes, and registry sources.
- Compilation graphs: `WorkspaceGraph -> PackageGraph -> ModuleGraph`, including
  stable dependency order, visibility, source metadata, and cycle diagnostics.
- Standard library: a canonical toolchain `nomo-lang/std` workspace package,
  shared compiler/doc/LSP module metadata, and built-in modules for core values,
  collections, IO, filesystem, environment, path, process, time, numeric
  helpers, JSON, network, HTTP, crypto, hash, regex, testing, debug, and logging.
- Tooling protocol: stable E-code diagnostics, JSON diagnostics, diagnostic
  documentation, formatter reuse, and LSP navigation, symbols, completion,
  semantic tokens, code actions, rename, formatting, and inlay hints.
- Ecosystem: package archives, publish/search/yank/owner/login flows, private
  registry authentication, examples, editor integrations, CI, and release
  packaging.

## Stabilization Gate

The current preview is complete only when the implementation, English and
Chinese specifications, RFCs, examples, editor integrations, and CI acceptance
matrix agree. Remaining work is tracked as current-scope slices; it must not be
reclassified as v0.2/v0.3 work merely to make the preview appear complete.

## v1.0: Stability Promise

Before v1.0, Nomo must stabilize syntax, core types, standard library APIs,
diagnostic codes, JSON diagnostic format, package structure, `nomo.toml`,
`nomo.lock`, canonical package IDs, C backend semantics, docs, and RFC process.
