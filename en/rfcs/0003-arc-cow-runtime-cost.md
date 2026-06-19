# RFC 0003: The Runtime Implementation Cost of ARC + Copy-on-Write (COW)

> 语言 / Language: [中文](../../zh-CN/rfcs/0003-arc-cow-runtime-cost.md) | English

## Metadata

| Field | Content |
| --- | --- |
| Number | 0003 |
| Title | The v0.1 runtime cost and degradation strategy of value semantics + reference counting + copy-on-write |
| Status | Draft |
| Author | Nomo Language Working Group |
| Created | 2026-06-18 |
| Related topics | memory model, `string`, `Array<T>`, ARC, COW, C backend |
| Related RFCs | [RFC 0004](./0004-mutable-borrow-uniqueness.md) (mutable-borrow uniqueness), [RFC 0006](./0006-option-result-lang-items.md) (lang items) |

---

## 1. Summary

The current memory-model specification prescribes "value semantics + reference counting (ARC) + copy-on-write (COW)" for both `string` and `Array<T>`, layered on top of `mut`-borrow uniqueness. This is the part of the v0.1 runtime with the highest implementation complexity and the greatest risk of slipping: it requires correctly handling reference-count increments/decrements, COW trigger determination, the interaction with the C backend's value-passing semantics, and the trade-off of "whether ARC needs to be atomic" while concurrency does not yet exist. This RFC assesses the implementation cost and discusses whether v0.1 can degrade to a simpler strategy. It leans toward "using non-atomic reference counting + COW in v0.1, but confining COW to a few explicit write operations, and allowing `string` to be implemented first as immutable sharing (no COW, since it is inherently immutable)", remaining Draft.

---

## 2. Motivation

The delivery boundary lists `std.array` and `std.string` as must-deliver, and the current performance notes promise that "strings and dynamic arrays implement reference counting and copy-on-write in the standard library". This means ARC+COW is not optional but part of v0.1 acceptance content. But it involves:

- The correctness and memory safety of runtime functions (retain/release/clone-on-write).
- COW trigger-timing determination (when `refcount > 1` and a write is about to happen).
- The interaction with C99 value semantics, with `mut` borrows, and with the `defer` cleanup order.

If this part of the workload is underestimated, it is most likely to drag down v0.1's "complete pipeline" goal.

---

## 3. Status and Problem

### 3.1 Current Specification Status

- Memory classification: `string` and `Array<T>` are classified as "standard-library-managed values: reference counting + copy-on-write".
- Strings: `string` is **immutable**, assignment increments the reference count, concatenation produces a new string, and the C backend uses runtime functions to manage the count.
- Dynamic arrays: `Array<T>` shares the underlying storage on read, triggers COW on write when "reference count > 1", and authorizes modification via `mut`.
- Performance promise: performance is "based on benchmarks", with no promise to be close to C/Rust.
- C backend: the C backend must "generate readable C" and "link the standard library runtime as C source files".

### 3.2 Problem Analysis

1. **`string` actually does not need COW**: the current string design states that strings are immutable and concatenation produces a new string. Since it is immutable, there will never be an "in-place write", so the COW trigger point does not exist — `string` only needs sharing + reference counting, and COW is the mechanism that `Array<T>` truly needs. The current specification listing both as "ARC+COW" is an over-statement.
2. **COW trigger determination requires reliable "uniqueness" information**: `Array.push`/`set` copy when `refcount > 1`. The determination depends on the runtime `refcount`, whereas `mut`-borrow uniqueness (see [RFC 0004](./0004-mutable-borrow-uniqueness.md)) is a compile-time check. The two uniqueness semantics (compile-time borrow uniqueness vs runtime count uniqueness) need to be coordinated, otherwise there will be ambiguity where "the compile-time view considers it unique, but the runtime count is > 1".
3. **Atomicity**: v0.1 has no concurrency (`go`/`chan` are deferred). At this point the reference count does not need atomic operations. But if the runtime is written atomically from the start (to pave the way for the future), it would add gratuitous single-threaded overhead; if written non-atomically, it would have to be rewritten when concurrency arrives.
4. **Interaction with the C backend and `defer`**: a value leaving scope must be `release`d; `?` early exit and reverse-order `defer` execution all require correctly inserting release points in codegen — a miss means a memory leak or use-after-free.

---

## 4. Detailed Design

### 4.1 Option A: Full ARC + COW (literal current specification)

- **Runtime**: `nomo_rc_retain` / `nomo_rc_release` / `nomo_cow_make_unique`, with the `Array<T>` header containing `refcount + len + cap + data`.
- **C backend**: insert retain/release at every binding move/copy point; call `make_unique` before a write.
- **Cost**: highest. It must fully cover move semantics, early returns, and `defer` order, and the test matrix is large.
- **Risk**: most likely to become the long tail of v0.1.

### 4.2 Option B: Divide and conquer (preferred)

- **`string`**: implemented as **immutable sharing + reference counting, no COW**. Since it is immutable, it is never written in place, eliminating all COW complexity; concatenation (8.5 `concat`) always allocates a new string.
- **`Array<T>`**: keep **reference counting + COW**, but converge the COW trigger surface to explicit write APIs (`push`/`set`), calling `make_unique` before a write.
- **Reference counting**: v0.1 uses a **non-atomic** count (no concurrency, see 1.2), with a comment in the runtime header "see the v0.3 RFC for the concurrent version".
- **Diagnostics/codegen**: release-point insertion and `defer`/`?` early exit are handled uniformly in the HIR→C IR stage (12.2 three-layer IR).
- **Advantages**: cut out unnecessary `string` COW, focus energy on getting `Array<T>` COW right, with controllable schedule and without violating the external semantics of 5.x (what the user sees is still value semantics).

### 4.3 Option C: v0.1 degrades to pure copying (no reference counting)

- **Approach**: `string`/`Array<T>` assignment deep-copies, with no reference counting and no COW at all.
- **Advantages**: simplest implementation, easiest to test, never leaks.
- **Disadvantages**: violates the explicit promises of performance and the memory model; frequent copying of large arrays has poor performance; switching back to ARC later is an observable behavior change (although semantically equivalent to value semantics, the performance characteristics differ). It can serve as an "emergency fallback route".

### 4.4 Option D: Pure reference counting, no COW (shared mutable?)

- It conflicts with value semantics: shared mutable without COW would break "value semantics" (a change in one place is visible in another). Unless writing-then-aliasing on `Array` is forbidden, it is untenable. It therefore only applies to immutable types (i.e. equivalent to the Option-B treatment of `string`).

---

## 5. Alternatives

| Option | Approach | Advantages | Disadvantages |
| --- | --- | --- | --- |
| A Full ARC+COW | Literally implement both types | Fully matches the current memory model | Highest cost, most likely to slip |
| B Divide and conquer (preferred) | string no COW, Array has COW, non-atomic | Cut the pseudo-requirement, focus on the real complexity, semantics unchanged | Still need to get Array COW right |
| C Pure-copy degradation | Full deep copy | Simplest and safest | Violates performance and memory-model promises, poor performance |
| D Pure RC no COW | Shared mutable | Simple implementation | Breaks value semantics, unusable for mutable Array |

---

## 6. Drawbacks and Risks

- Option B still requires implementing `Array<T>`'s COW and release-point insertion, which is the real difficulty; it needs ample Mutability/Codegen tests.
- The non-atomic count is a one-time technical debt: when v0.3 introduces concurrency, it must switch to atomic or change strategy, which must be explicitly marked in the runtime source and the RFC to avoid being misused across threads.
- If compile-time borrow uniqueness ([RFC 0004](./0004-mutable-borrow-uniqueness.md)) is strong enough, in theory some writes could "modify in place without checking refcount"; but if v0.1 borrow checking is weak (see the lean of [RFC 0004](./0004-mutable-borrow-uniqueness.md)), a runtime refcount backstop is still needed, and the relationship between the two must be locked down across the two RFCs.

---

## 7. Impact on v0.1 Scope

- **Recommended to land in v0.1**: Option B. `string` takes "immutable sharing + non-atomic RC"; `Array<T>` takes "non-atomic RC + COW (triggered only by write APIs such as `push`/`set`)".
- **Recommended current-specification revision**: correct the "ARC+COW" in the current string design to "`string` is reference-counted sharing only (immutable, no COW needed)", to avoid misleading implementers.
- **Keep a fallback gate**: if `Array<T>` COW is still unstable before release, allow temporarily switching to Option C (pure copy) to preserve "complete pipeline", with COW as a patch following close behind.
- **Acceptance impact**: the acceptance test matrix needs to add runtime smoke + memory checks (e.g. ASan) for "COW trigger (write at refcount>1)" and "release points (`defer`/`?` early exit)".

---

## 8. Recommendation (remains Draft, not decided)

Lean toward **Option B**: distinguish `string` (immutable, COW-free) from `Array<T>` (RC+COW), use non-atomic counting uniformly, and treat pure copying (Option C) as the pre-release emergency fallback. This significantly reduces the implementation and slippage risk of the v0.1 runtime without weakening the external value semantics. Remains Draft.

---

## 9. Open Questions

- Does the `Array<T>` runtime header layout (`refcount/len/cap`) and the C backend ABI need to be fixed now? (4.4 mentions the Result layout can be optimized later; the same applies to arrays.)
- How much runtime refcount checking can compile-time borrow uniqueness eliminate? This depends on the conclusion of [RFC 0004](./0004-mutable-borrow-uniqueness.md).
- Do ASan/leak detection enter the v0.1 release gate?

---

## 10. References

- The current performance promise, memory model, `std.array`, `std.string`, C backend principles.
- [RFC 0004](./0004-mutable-borrow-uniqueness.md) (the difficulty of mutable-borrow uniqueness checking), [RFC 0006](./0006-option-result-lang-items.md) (lang items and runtime awareness).
