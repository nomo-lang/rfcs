# RFC 0001: The Experience Tension Between `?` Propagation and the Lack of Automatic Error Conversion

> 语言 / Language: [中文](../../zh-CN/rfcs/0001-error-propagation-and-conversion.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0001 |
| Title | The experience tension between `?` propagation and the lack of automatic error conversion |
| Status | Draft |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Related topics | error handling, `Result`, `?` propagation, error conversion, C backend |
| Related RFCs | [RFC 0006](./0006-option-result-lang-items.md) (Option/Result as lang items) |

---

## 1. Summary

The current error-handling specification clearly states that "v0.1 does not provide anonymous error unions and does not automatically merge error types"; cross-layer error conversion must be written explicitly with `match`. This directly conflicts with the original intent of `?` (eliminating boilerplate and making propagation lightweight): in real multi-layer calls, the caller's error type is almost always different from the callee's, so `?` is barely usable anywhere, and developers are forced back to `match`. This RFC analyzes the tension, presents three alternatives (`From`/`Into`-style conversion traits, a standard-library `.map_err()` method, anonymous error unions), and leans toward "landing `.map_err()` in v0.1 first as the explicit conversion entry point, leaving automatic-conversion traits for a v0.2 RFC", while remaining Draft.

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

In the list of pending issues, the error-conversion topic also lists "whether `Result` error conversion introduces a `From`-style trait" as a pending issue.

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

- **Syntax**: in the `Err` branch, `?` automatically calls `AppError::from(err)` (the exact syntax is TBD, since v0.1 has no trait/interface, see 3.9). For example:

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
- **Cost**: v0.1 explicitly "does not support trait/interface constraints" (3.9); introducing a `From`-style mechanism amounts to introducing the trait system early or a specialized "conversion registration" subsystem, conflicting with the MVP boundary.

### 4.2 Option B: A standard-library `.map_err()` explicit method (preferred)

- **Syntax**: keep the semantics of `?` unchanged, and provide `map_err` on `std.result`:

```rust
fn read_config(path: string) -> Result<string, AppError> {
    let text = fs.read_to_string(path)
        .map_err(fn(e: FsError) -> AppError { AppError.ReadFailed(e.message) })?
    Result.Ok(text)
}
```

- **Semantics**: `map_err` maps `Result<T, E1>` to `Result<T, E2>`, after which `?` propagates under the premise of type equality. No implicit conversion or trait is needed.
- **C backend**: `map_err` is monomorphized into an ordinary function; it requires a function-value/closure argument (v0.1's closure capability is in the closure-representation topic of the pending-issues list; if closures are not ready, named conversion functions can be required first).
- **Diagnostics**: no new exhaustiveness/conversion error codes; type mismatch still goes through the existing N04xx.
- **Dependency**: the ideal form requires functions as arguments. If v0.1 closures are unavailable, it degrades to "passing a named `fn`": `.map_err(app_error_from_fs)?`.

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
| B `.map_err()` (preferred) | Explicit mapping then `?` | Does not break `?` semantics, no implicit magic, fits "explicit first"; can be a pure library implementation | Still some boilerplate; the ideal form depends on function values/closures |
| C Anonymous union | `Result<T, A \| B>` auto-merge | No need to write conversions by hand | Breaks the 4.4 fixed layout, complex type inference/diagnostics, clearly beyond v0.1 |

---

## 6. Drawbacks and Risks

- When choosing B, if v0.1 closures have not yet landed, `map_err` can only accept named functions, and the experience is slightly worse; it needs to coordinate with the closure-representation topic.
- Any option must first confirm the precise definition of "compatible `Result`" (the current 4.3 is vague), otherwise implementers will each interpret it differently.
- If we stay with B for a long time while A eventually has to be done too, there will be "first `map_err`, then `From`" two ways of writing it, in tension with the 2.2 principle — the recommended order needs to be made explicit in the documentation.

---

## 7. Impact on v0.1 Scope

- **Recommended to land in v0.1**: Option B's `std.result.map_err` (supporting named conversion functions first), and add a sentence to the current error-handling specification that "the recommended way to do cross-layer conversion is `.map_err(...)?`", while also rewriting the file-reading example into a form that can use `?` as an anchor.
- **Explicitly deferred**: Option A (`From`-style) and Option C (anonymous union) are left for a v0.2 RFC, bound to the error-conversion topic in the pending-issues list.
- **Acceptance impact**: the acceptance test matrix should add a "`map_err` + `?` cross-layer propagation" case (which can be merged into the `result_chain` example).

---

## 8. Recommendation (remains Draft, not decided)

Lean toward **Option B**: introduce `std.result.map_err` in v0.1, make cross-layer error conversion explicit so that `?` is usable in real code (including `read_config`), while not breaking the fixed C layout of 4.4 and not introducing traits early. `From`-style automatic conversion (Option A) continues to be discussed as a v0.2 candidate. Remains Draft.

---

## 9. Open Questions

- Does "compatible `Result`" only mean `E` is strictly equal? This needs to be settled when this RFC is accepted.
- Does `map_err` require v0.1 closures to be ready, or should it support named functions first? This depends on progress on the closure-representation topic in the pending-issues list.
- Whether to also provide `map` (for `Ok`) to keep the API symmetric.

---

## 10. References

- The current error handling, `Result<T, E>`, `?` propagation, C backend representation, file-reading example.
- The error-conversion pending topic (`From`-style trait pending).
- [RFC 0006](./0006-option-result-lang-items.md) (the coupling of `Option`/`Result` as lang items).
