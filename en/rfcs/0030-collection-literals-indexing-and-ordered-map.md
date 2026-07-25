# RFC 0030: Collection Literals, Indexing, and Ordered Map

> Language: [中文](../../zh-CN/rfcs/0030-collection-literals-indexing-and-ordered-map.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0030 |
| Title | Collection literals, indexing, and ordered Map |
| Status | Accepted |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | arrays, indexing, COW, generics, map, determinism, Agent |
| Related RFCs | [RFC 0003](./0003-arc-cow-runtime-cost.md), [RFC 0004](./0004-mutable-borrow-uniqueness.md), [RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md), [RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md) |

## 1. Summary

Nomo v0.1 adds array literals, checked indexing, and one deterministic generic
key-value container:

```nomo
let values = [1, 2, 3]                 // Array<i32>
let matrix = [[1, 2], [3, 4]]          // Array<Array<i32>>
let empty: Array<i32> = []
let second: i32 = matrix[0][1]
matrix[0][1] = 7

let mut tools: Map<string, ToolDefinition> = Map.new<string, ToolDefinition>()
let previous = map.set<string, ToolDefinition>(mut tools, "search", definition)
```

`Map<K,V>` preserves insertion order. v0.1 does not expose a second
`HashMap<K,V>` name: the language has no accepted general `Hash`/`Eq` contract,
and two containers with overlapping APIs would add surface without a sound
semantic distinction.

## 2. Array literal inference

- A non-empty literal has type `Array<T>`, where every element must have exactly
  the same inferred type. There are no implicit numeric conversions.
- Nomo's established unannotated scalar-integer fallback remains `i64` for
  source compatibility. An unconstrained integer used to establish an array
  literal's element type uses the fixed-width collection default `i32`, so
  `[1, 2, 3]` is `Array<i32>`. An explicit `Array<I>` context wins; mixed
  explicitly typed numeric values still fail.
- Nested literals apply the same rule recursively.
- `[]` requires an expected `Array<T>` from a binding, return, argument, field,
  or enclosing literal. Without one it reports `E0860`.
- A mismatch reports `E0861`, identifies the element position, expected type,
  and found type.
- Literal elements evaluate once, left to right.

## 3. Indexing

`array[index]` requires `index: u64` and returns `T`. It evaluates the array
expression before the index, exactly once each. Out of bounds terminates with
the stable panic message `array index out of bounds`; native C99 and browser
WASM use the same rule. `Array.get(index) -> Option<T>` remains the safe,
non-panicking access API.

An indexed assignment requires a mutable root binding. Every index expression
and the right-hand side evaluate exactly once, left to right. For a nested
assignment, the compiler performs path COW from the root: it detaches the root,
loads and detaches each managed child, updates the leaf, and writes each child
back to its parent. Thus `matrix[0][1] = value` cannot mutate an alias and
cannot lose the write through a temporary.

Strings are not indexable in v0.1 because byte, scalar, and grapheme indexing
have different contracts. Other non-array bases report `E0862`; non-`u64`
indices report `E0863`; immutable roots report `E0864`.

## 4. Ordered `Map<K,V>`

### 4.1 Choice and key constraint

`Map<K,V>` is insertion ordered and uses value semantics with COW. The first
implementation uses a bounded linear index, not hashing. This is honest about
v0.1's missing user-defined equality/hash interfaces, deterministic across
C99/WASM, and sufficient for bounded Agent metadata and JSON object building.

`K` must support Nomo's existing `==` operation; unsupported equality is
rejected at the map call with the normal type diagnostic. v0.1 deliberately
does not invent a separate hashability marker. A future RFC may add `Hash` +
`Eq` and a separately justified `HashMap`; it must define equality coherence,
seeded hashing, collision handling, growth, iteration, and adversarial-input
limits.

### 4.2 API

```nomo
Map.new<K, V>() -> Map<K, V>
map.len<K, V>(map: Map<K, V>) -> u64
map.is_empty<K, V>(map: Map<K, V>) -> bool
map.contains_key<K, V>(map: Map<K, V>, key: K) -> bool
map.get<K, V>(map: Map<K, V>, key: K) -> Option<V>
map.set<K, V>(mut map: Map<K, V>, key: K, value: V) -> Option<V>
map.remove<K, V>(mut map: Map<K, V>, key: K) -> Option<V>
map.clear<K, V>(mut map: Map<K, V>) -> void
map.keys<K, V>(map: Map<K, V>) -> Array<K>
map.values<K, V>(map: Map<K, V>) -> Array<V>
```

`set` replaces in place without changing order and returns the previous value;
insertion appends and returns `None`. `remove` returns the removed value.
The paired snapshots returned by `keys` and `values` have matching insertion
order and provide deterministic entry iteration by index. All mutation
requires a mutable argument/root and follows normal COW rules.

Maps are limited to 65,536 entries. Insertion beyond the limit panics with
`map capacity exceeded`. Linear lookup is O(n), eliminating collision-based
hash flooding while leaving CPU proportional to the documented bound.

### 4.3 Compatibility

`StringMap` and its free functions remain source compatible for v0.1. Their
existing implementation is retained to avoid changing ABI or behavior in this
slice. Documentation identifies them as legacy and gives direct replacements;
removal or a wrapper conversion requires a later compatibility RFC and stable
release boundary. `StringSet` is unchanged.

## 5. Toolchain impact

- Lexer/parser/AST add literal and postfix index nodes plus indexed assignment.
- Type checking supplies expected types to empty literals and records precise
  indexed paths.
- IR represents literal construction, checked index reads, path updates, and
  typed map operations explicitly.
- C99 and WASM share bounds, evaluation order, COW, ownership, panic strings,
  map order, key equality, and capacity limits.
- Formatter preserves compact literals and canonical comma/space layout.
- Semantic facts and LSP include references inside literals, bases, indices,
  and assigned values. Tree-sitter highlights brackets as punctuation and
  exposes `array_literal`/`index_expression` nodes.
- Playground ships at least one runnable literal/index/map example using the
  production WASM.

## 6. Acceptance gate

This RFC becomes `Accepted` only after:

1. parser, formatter, semantic, IR, C99, WASM, LSP bridge, Tree-sitter, and
   Playground integration are implemented or an audited repository is proven
   unaffected;
2. one- and multi-dimensional/jagged literals and reads pass on native/WASM;
3. nested indexed writes pass alias/COW and single-evaluation tests;
4. empty/mixed literals, wrong indices, bounds, and immutable roots have stable
   diagnostic/runtime tests;
5. arrays of generic, struct, enum, string, and managed values pass lifecycle
   tests under ASan/LeakSanitizer;
6. `Map<string,JsonValue>` and `Map<string,ToolDefinition>` exercise every API,
   order, replacement, removal, clear, COW, capacity, and managed-value
   lifecycle behavior;
7. `StringMap` compatibility tests remain green and migration docs exist;
8. format, Clippy, full workspace tests, release C99, browser WASM, and required
   platform/cross-build CI pass.

The implementation, cross-backend tests, Tree-sitter corpus, production
Playground WASM, documentation, and protected CI provide the evidence for
`Accepted` status.
