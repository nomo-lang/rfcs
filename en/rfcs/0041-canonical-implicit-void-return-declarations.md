# RFC 0041: Canonical Implicit `void` Return Declarations

> Language: [中文](../../zh-CN/rfcs/0041-canonical-implicit-void-return-declarations.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0041 |
| Title | Canonical implicit `void` return declarations |
| Decision Status | Proposed |
| Implementation Status | Not implemented |
| Author | Nomo Language Working Group |
| Created | 2026-07-27 |
| Related topics | function declarations, methods, suspend functions, interfaces, extern declarations, formatter, docs, LSP, grammars |
| Related RFCs | [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md), [RFC 0011](./0011-c-ffi-safety-and-link-boundary.md), [RFC 0012](./0012-shared-semantic-identities-and-verified-rename.md), [RFC 0031](./0031-direct-style-suspend-functions-and-structured-concurrency.md) |

## 1. Summary

Nomo uses an omitted return annotation as the canonical spelling of a
declaration that returns `void`. This applies uniformly to ordinary
functions, methods, `suspend fn`, interface requirements, and functions inside
an `extern` block.

The parser continues to accept explicit `-> void` declarations for source
compatibility. The formatter, scaffolder, `nomo doc`, shared compiler/LSP
signature renderer, hover, signature help, and canonical examples omit it.
This is a presentation and syntax-convergence change; it does not remove the
`void` type or change ABI, effect, ownership, or control-flow semantics.

Callable types always retain an explicit return type. In particular,
`task fn(string) -> void` is not shortened. Type arguments and values such as
`Result<void, E>` and `Ok(void)` are unchanged.

## 2. Motivation

The current source tree repeats `-> void` on nearly every entry point, helper,
method, async operation, interface requirement, and no-result FFI call. That
spelling adds noise without disambiguating a declaration: an omitted
declaration return already has one unambiguous meaning.

At the same time, removing every occurrence of `-> void` would be incorrect.
A callable type needs a complete input/output shape, and `void` remains a real
type used in generic arguments and values. The convergence rule therefore
must be declaration-context-specific and shared by all renderers.

Without one RFC-level contract, the formatter could omit the annotation while
docs or editors reinsert it, producing perpetual churn and contradictory
examples.

## 3. Canonical declaration grammar

### 3.1 Source forms

Canonical declarations omit `-> void`:

```nomo
fn log(message: string) {
    io.println(message)
}

impl Buffer {
    pub fn clear(mut self) {
        self.bytes.clear()
    }
}

suspend fn yield_once() {
    task.yield_now()
}

pub interface Close {
    fn close(self)
}

extern "C" {
    fn release(handle: Owned<Handle>)
}
```

A declaration whose result is not `void` still writes its result type:

```nomo
fn length(value: string) -> u64 {
    return value.byte_length()
}
```

The compatibility spelling remains parseable:

```nomo
fn log(message: string) -> void {
    io.println(message)
}
```

Both forms create the same typed declaration. There is no overload or semantic
identity distinction based on whether `-> void` was written.

### 3.2 Context boundary

Omission applies only to declaration return annotations:

- free and exported `fn`;
- methods and interface implementations;
- `suspend fn`;
- interface function requirements; and
- functions declared inside `extern` blocks.

It does not apply to callable types or type/value positions:

```nomo
let worker: task fn(string) -> void = print_message
let completed: Result<void, TaskError> = Ok(void)
```

`task fn(string)` is not a synonym for `task fn(string) -> void`. Callable
types remain syntactically complete so higher-order signatures, ABI
descriptions, and diagnostics always show their result.

### 3.3 Parser and AST

The declaration return grammar remains optional. When absent, the parser
constructs the same semantic `void` result as explicit `-> void`. The AST may
preserve source-range information for formatting diagnostics, but type
checking and symbol identity observe one result type.

The parser must continue accepting explicit `-> void`; this RFC does not set a
removal snapshot. Non-`void` result annotations remain mandatory.

Tree-sitter already models the return type as optional. Its grammar should not
gain a second production. Regression corpus cases must cover each declaration
position and ensure callable types still require the arrow/result.

## 4. Canonical rendering and migration

The following producers must use the same declaration-signature renderer and
omit a semantic `void` result:

- `nomo fmt`;
- `nomo new` and repository project templates;
- `nomo doc`, including interface and extern items;
- compiler-owned signature data shared with `nomo-lsp`;
- LSP hover, signature help, symbols, completion details, and code actions;
- Playground examples and displayed signatures; and
- human-maintained standard-library, example, benchmark, and editor fixtures.

The formatter rewrites explicit declaration `-> void` to the omitted form. It
is idempotent. It must not alter:

```nomo
Result<void, E>
Option<Result<void, E>>
Ok(void)
task fn(string) -> void
```

TextMate and IntelliJ fallback lexers must tokenize both source forms without
assuming that a declaration contains `->`. Tree-sitter, Zed, and VS Code
corpora/examples use the canonical form while retaining one explicit
compatibility fixture.

## 5. Type checking, control flow, and diagnostics

An omitted declaration result is exactly `void`:

- fallthrough and existing `return` rules are unchanged;
- all existing no-result validation applies;
- interface conformance treats omitted and explicit forms as identical;
- extern ABI lowering still uses the existing C `void` result; and
- `suspend fn` effect checking is independent of result spelling.

No new type error is required. Diagnostics that print declarations use the
canonical omitted spelling. A diagnostic quoting the user's source may retain
the original token range, but suggested replacements and generated snippets
omit `-> void`.

If a callable type omits its return type, the parser continues to report the
existing missing-return-type syntax error rather than inferring `void`.

## 6. Backend and runtime impact

The C99 and WASM backends receive the same typed `void` result as before.
Symbol mangling, C prototypes, return lowering, coroutine frame layout, extern
ABI, and runtime representation do not change.

This RFC does not alter RFC 0031-0040 async semantics. A declaration such as
`suspend fn main()` is still suspend/effectful; only its result annotation is
canonicalized.

## 7. Compatibility

This is source-compatible for parsing and behavior:

- old explicit declarations continue to compile;
- canonical formatting produces a source diff;
- tools consuming compiler semantic data see the same `void` type; and
- callable/type/value uses remain byte-for-byte meaningful.

Repositories migrate in one coordinated change so formatter output, docs,
LSP, grammars, editor examples, standard library, tests, and Playground do not
oscillate. Fixtures intentionally testing explicit compatibility are named and
excluded from the canonical-source gate.

## 8. Alternatives

| Alternative | Result | Decision |
| --- | --- | --- |
| Keep explicit `-> void` canonical | Consistent but noisy, with no added declaration information | Reject |
| Remove `void` and infer it everywhere | Breaks generic results, values, callable types, and ABI descriptions | Reject |
| Permit omission only on ordinary functions | Leaves methods, interfaces, suspend, extern, docs, and LSP inconsistent | Reject |
| Canonical omission in declaration contexts only | Concise declarations with complete callable and generic types | Proposed |

## 9. Risks

- Independent renderers can drift unless signature rendering is shared.
- Mechanical replacement can corrupt callable types or `Result<void, E>` if
  it is text-based instead of syntax-aware.
- Editor fallback lexers may accidentally assume an arrow follows parameters.
- A repository-wide formatting migration creates a large but low-semantic-risk
  diff that must remain separate from async behavior changes.

## 10. Acceptance gates

Protected CI must prove:

1. parser parity for omitted and explicit forms on ordinary, method,
   `suspend`, interface, and extern declarations;
2. formatter omission in every declaration position and idempotence;
3. preservation of `Result<void, E>`, nested type arguments, `Ok(void)`, and
   `task fn(string) -> void`;
4. unchanged C99 prototypes/behavior and WASM behavior;
5. canonical `nomo doc`, LSP hover, signature help, symbols, completion
   details, and code actions;
6. canonical scaffolder, standard library, examples, fixtures, benchmark
   probes, `nomo-hello`, Playground, VS Code, IntelliJ, Tree-sitter, and Zed
   examples;
7. grammar/editor regression tests for omitted declarations and explicit
   compatibility; and
8. a documentation gate that rejects declaration `-> void` outside named
   compatibility fixtures while permitting callable/type/value uses.

## 11. Decision and implementation gate

This RFC initially lands as `Proposed` with `Implementation Status:
Not implemented`. No implementation branch may depend on acceptance by
assertion alone.

After the implementation and all applicable protected CI gates merge, a
separate evidence PR may set the decision to `Accepted` and implementation to
`Implemented`. That PR records merged compiler and ecosystem commits plus the
exact validation commands. It must not equate internal test coverage with
production readiness.
