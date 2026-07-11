# RFC 0001: The Experience Tension Between `?` Propagation and the Lack of Automatic Error Conversion

> 语言 / Language: [中文](../../zh-CN/rfcs/0001-error-propagation-and-conversion.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0001 |
| Title | The experience tension between `?` propagation and the lack of automatic error conversion |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Implementation | Landed: postfix `?` for `Result`/`Option`, same-carrier early return, and `std.result.map_err(named_converter)?` have compiler and runtime coverage |
| Related topics | error handling, `Result`, `?` propagation, error conversion, C backend |
| Related RFCs | [RFC 0006](./0006-option-result-lang-items.md) (compiler-owned Option/Result identities) |

---

## 1. Summary

The current error-handling specification clearly states that v0.1 does not provide anonymous error unions and does not automatically merge error types. Cross-layer error conversion therefore needs an explicit step before propagation. This RFC accepts `std.result.map_err(converter)?` as the v0.1 answer: `?` stays the only propagation syntax, `map_err` performs named-function error conversion, and `From`/`Into`-style automatic conversion plus anonymous error unions are deferred beyond v0.1.

---

## 2. Motivation

`?` is the core ergonomic selling point of v0.1 error handling (see the delivery boundary, where "postfix `?`" is listed as a must-deliver item). But if `?` can only be used when "the function's error type is exactly identical to the callee's error type", its applicability is severely compressed:

- Most business functions return custom errors (such as `AppError` in the file-reading example).
- Most low-level calls return library errors (such as `FsError`).
- The two types differ, so `?` directly reports a type incompatibility, and the developer can only write a `match` to convert manually.

The result: the `read_config` in the current specification's file-reading example **cannot use `?` at all** — it must be written as `match fs.read_to_string(path) { ... }` to convert `FsError` into `AppError.ReadFailed`. This shows that `?` is unusable even in the specification's own flagship example, which is an experience gap that must be faced.

---

## 3. Status and Problem

### 3.1 Current Specification Status

The current error-handling specification defines the semantics of `expr?`:

- `Result.Ok(value)` → evaluates to `value`;
- `Result.Err(error)` → the current function immediately performs `return Result.Err(error)`;
- "The current function's return type must also be a compatible `Result`."

It also emphasizes:

> v0.1 does not provide anonymous error unions and does not automatically merge error types. Cross-layer error conversion must be done explicitly.
> Automatic error unions can be a follow-up RFC and do not enter v0.1.

An early error-conversion issue also asked whether `Result` conversion should introduce a `From`-style trait; this RFC explicitly defers it to a later version.

### 3.2 Problem Analysis

In the current specification, "compatible `Result`" is not defined as to whether it means "the `E` type is strictly equal" or "`E` is convertible". Inferring from the rule "do not automatically merge error types", it can only mean **strict equality**. Thus:

```rust
fn read_config(path: string) -> Result<string, AppError> {
    // We want to write it this way, but fs.read_to_string returns Result<string, FsError>, and E is not AppError
    let text = fs.read_to_string(path)?   // ❌ incompatible type: expected AppError, found FsError
    Result.Ok(text)
}
```

We can only fall back to the explicit `match` conversion:

```rust
fn read_config(path: string) -> Result<string, AppError> {
    match fs.read_to_string(path) {
        Result.Ok(text) => Result.Ok(text)
        Result.Err(err) => Result.Err(AppError.ReadFailed(err.message))
    }
}
```

The tension: **the value of `?` lies in cross-layer propagation, and crossing layers almost inevitably involves a change of error type**. Forbidding automatic conversion = `?` is only usable in the few scenarios where "the error type never changes along the way" (e.g. within the same module, where the error type is already unified). This pushes users and AI-generated code toward "avoid `?` whenever possible", weakening the design goal of "avoiding multiple ways to write the same semantics".

---

## 4. Detailed Design

The three options below all revolve around "how to turn `FsError` into `AppError` and then propagate it".

### 4.1 Option A: Introduce a `From`/`Into`-style error-conversion trait

- **Syntax**: in the `Err` branch, `?` automatically calls `AppError::from(err)` (the exact syntax is TBD; v0.1's minimal interface constraints do not include associated/static conversion lookup). For example:

```rust
impl AppError {
    fn from_fs(err: FsError) -> AppError {
        AppError.ReadFailed(err.message)
    }
}
// The compiler implicitly inserts the from conversion in the Err branch of ?
```

- **Semantics**: for `expr?`, when `Err(e)`, if the current function's error type `E2 != E1`, look up a registered `E1 -> E2` conversion and apply it; report an error if none is found.
- **C backend**: insert one conversion-function call at the `?` expansion point, then `return` the wrapped `Result_T_E2`.
- **Diagnostics**: add a "no error conversion found" error code (in the E0400-E0499 type-checking range, e.g. `E0461`).
- **Cost**: v0.1 only supports a single static `T: Interface` bound and does not support associated functions, blanket impls, or implicit conversion lookup. A `From`-style mechanism would still require extending the interface system or adding a specialized conversion registry.

### 4.2 Option B: A standard-library `.map_err()` explicit method (accepted)

- **Syntax**: keep the semantics of `?` unchanged, and provide `map_err` on `std.result`:

```rust
fn read_config(path: string) -> Result<string, AppError> {
    let raw: Result<string, FsError> = fs.read_to_string(path)
    let text: string = raw.map_err(app_error_from_fs)?
    Result.Ok(text)
}
```

- **Semantics**: `map_err` maps `Result<T, E1>` to `Result<T, E2>`, after which `?` propagates under the premise of type equality. No implicit conversion or trait is needed.
- **C backend**: `map_err` is monomorphized into an ordinary helper that accepts a named, unqualified, non-generic converter function. Closures and anonymous function values remain out of scope for v0.1.
- **Diagnostics**: no new exhaustiveness/conversion error codes; type mismatch still goes through the existing N04xx.
- **Dependency**: v0.1 requires passing a named `fn`: `.map_err(app_error_from_fs)?`.

### 4.3 Option C: Anonymous error unions (implicit merging)

- **Syntax**: a function declaration `-> Result<T, FsError | ParseError>`, where `?` automatically packs the sub-error into the union.
- **Semantics**: the compiler injects `E1` into the union `E1 | E2 | ...` at `?`.
- **C backend**: the union needs a runtime tag; the layout is complex, and compared with the fixed `Result_T_E` structure of 4.4, it requires introducing an "error-type tag + multi-arm union".
- **Cost**: the current error-handling specification has already named this as a "follow-up RFC, not entering v0.1"; type inference and diagnostics complexity is high.

---

## 5. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| A `From` trait | `?` implicitly calls error conversion | Experience closest to Rust, least boilerplate | Requires introducing trait/conversion registration early, violating the 3.9 MVP boundary; implicitness reduces readability |
| B `.map_err()` (accepted) | Explicit mapping then `?` | Does not break `?` semantics, no implicit magic, fits "explicit first"; works in v0.1 with named converter functions | Still some boilerplate; closure-based inline converters are deferred |
| C Anonymous union | `Result<T, A \| B>` auto-merge | No need to write conversions by hand | Breaks the 4.4 fixed layout, complex type inference/diagnostics, clearly beyond v0.1 |

---

## 6. Drawbacks and Risks

- `map_err` accepts named converter functions in v0.1, so inline conversion remains more verbose than a closure-based form.
- "Compatible `Result`" is fixed as matching `Ok` payload type and strictly equal error type after any explicit conversion.
- If a future `From`-style mechanism is added, the language will need a migration story so `map_err(...)?` and implicit conversion do not become equally preferred duplicate idioms.

---

## 7. Impact on v0.1 Scope

- **Lands in v0.1**: Option B's `std.result.map_err` with named converter functions, documented as the recommended way to write cross-layer conversion before `?`.
- **Explicitly deferred**: Option A (`From`-style) and Option C (anonymous union) are left for separate v0.2+ RFCs.
- **Acceptance impact**: the acceptance matrix includes `map_err` + `?` cross-layer propagation examples and tests.

---

## 8. Decision

Accepted **Option B**. v0.1 uses postfix `?` as the only propagation syntax and uses explicit `std.result.map_err(named_converter)?` for cross-layer error conversion. `try` syntax, implicit `From` conversion, and anonymous error unions are not part of v0.1.

---

## 9. Open Questions

- Whether a later closure syntax should allow inline converters for `map_err`.
- Whether a later `From`-style conversion mechanism should coexist with or supersede explicit `map_err(...)?`.
- Whether to also provide `map` (for `Ok`) to keep the API symmetric.

---

## 10. References

- The current error handling, `Result<T, E>`, `?` propagation, C backend representation, file-reading example.
- Follow-up error-conversion work (`From`-style traits).
- [RFC 0006](./0006-option-result-lang-items.md) (compiler-owned `Option`/`Result` identities).
