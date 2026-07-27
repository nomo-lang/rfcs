# RFC 0030：集合字面量、索引与有序 Map

> 语言：中文 | [English](../../en/rfcs/0030-collection-literals-indexing-and-ordered-map.md)

## 元数据

| 字段 | 值 |
| --- | --- |
| 编号 | 0030 |
| 标题 | 集合字面量、索引与有序 Map |
| 决策状态 | Accepted（已接受） |
| 实现状态 | Implemented（已实现） |
| 实现证据 | [`nomo#19`](https://github.com/nomo-lang/nomo/pull/19)，merge [`8cb9fe1`](https://github.com/nomo-lang/nomo/commit/8cb9fe1cc39ca63c3bfeeda0dc2a11a35bfe5318) |
| 作者 | Nomo Language Working Group |
| 创建日期 | 2026-07-25 |
| 主题 | 数组、索引、COW、泛型、Map、确定性、Agent |
| 相关 RFC | [RFC 0003](./0003-arc-cow-runtime-cost.md)、[RFC 0004](./0004-mutable-borrow-uniqueness.md)、[RFC 0010](./0010-constrained-generics-and-static-interface-dispatch.md)、[RFC 0015](./0015-source-defined-standard-library-and-intrinsics.md) |

## 1. 摘要

Nomo v0.1 增加数组字面量、检查式索引和一个确定性的通用键值容器：

```nomo
let values = [1, 2, 3]                 // Array<i32>
let matrix = [[1, 2], [3, 4]]          // Array<Array<i32>>
let empty: Array<i32> = []
let second: i32 = matrix[0][1]
matrix[0][1] = 7

let mut tools: Map<string, ToolDefinition> = Map.new<string, ToolDefinition>()
let previous = map.set<string, ToolDefinition>(mut tools, "search", definition)
```

`Map<K,V>` 保持插入顺序。v0.1 不公开语义重复的 `HashMap<K,V>`：当前没有已验收的通用 `Hash`/`Eq` 契约，同时提供两个 API 重叠的容器没有合理依据。

## 2. 数组字面量推导

- 非空字面量类型为 `Array<T>`，所有元素的推导类型必须完全一致，不做隐式数值转换。
- 为保持源码兼容，Nomo 既有的无注解标量整数 fallback 仍为 `i64`。仅当无约束整数用于建立数组字面量元素类型时，采用固定宽度集合默认 `i32`，因此 `[1, 2, 3]` 为 `Array<i32>`。显式 `Array<I>` 上下文优先，不同显式数值类型仍报错。
- 嵌套字面量递归应用相同规则。
- `[]` 必须从绑定、返回值、参数、字段或外层字面量获得 `Array<T>` 上下文；否则报告 `E0860`。
- 类型不一致报告 `E0861`，指出元素位置、期望类型和实际类型。
- 元素从左到右且各求值一次。

## 3. 索引

`array[index]` 要求 `index: u64` 并返回 `T`。数组表达式先于索引求值，二者都只求值一次。越界以稳定消息 `array index out of bounds` 终止；原生 C99 与浏览器 WASM 行为一致。`Array.get(index) -> Option<T>` 继续作为安全、不 panic 的访问方式。

索引赋值要求根绑定可变。所有索引及右值按从左到右顺序各求值一次。嵌套写入从根执行路径式 COW：分离根数组，逐层读取并分离 managed 子数组，修改叶子，再逐层写回。因此 `matrix[0][1] = value` 不会修改别名，也不会把写入丢在临时值中。

v0.1 不支持字符串索引，因为字节、Unicode scalar 与 grapheme 的契约不同。非数组基值报告 `E0862`，非 `u64` 索引报告 `E0863`，不可变根报告 `E0864`。

## 4. 有序 `Map<K,V>`

`Map<K,V>` 保持插入顺序并采用 COW 值语义。首个实现使用有界线性索引而非哈希：这与 v0.1 尚无用户自定义 equality/hash 接口的事实一致，保证 C99/WASM 确定性，也足以服务有界的 Agent 元数据与 JSON 对象构造。

`K` 必须支持 Nomo 既有的 `==` 操作；不支持 equality 的类型在 Map 调用处按普通类型诊断拒绝。v0.1 不额外虚构 hashability 标记。未来若增加 `Hash` + `Eq` 与独立 `HashMap`，必须另行定义一致性、随机种子、碰撞、扩容、迭代顺序及对抗输入上限。

```nomo
Map.new<K, V>() -> Map<K, V>
map.len<K, V>(map: Map<K, V>) -> u64
map.is_empty<K, V>(map: Map<K, V>) -> bool
map.contains_key<K, V>(map: Map<K, V>, key: K) -> bool
map.get<K, V>(map: Map<K, V>, key: K) -> Option<V>
map.set<K, V>(mut map: Map<K, V>, key: K, value: V) -> Option<V>
map.remove<K, V>(mut map: Map<K, V>, key: K) -> Option<V>
map.clear<K, V>(mut map: Map<K, V>)
map.keys<K, V>(map: Map<K, V>) -> Array<K>
map.values<K, V>(map: Map<K, V>) -> Array<V>
```

`set` 替换既有值时不改变顺序并返回旧值；新增时追加并返回 `None`。`remove` 返回被移除值。`keys` 与 `values` 的配对快照顺序一致，可按索引确定性遍历条目。所有修改都要求可变参数/root 并遵循普通 COW。

Map 上限为 65,536 项，超过时以 `map capacity exceeded` panic。线性查询为 O(n)，没有碰撞型 hash flooding，CPU 成本仍受公开上限约束。

`StringMap` 与原 free functions 在 v0.1 保持源码兼容；本切片保留原实现，避免无证据改变 ABI 或行为。文档将其标为 legacy 并提供直接迁移写法。删除或改为包装必须等后续兼容 RFC 与稳定版本边界。`StringSet` 不变。

## 5. 工具链影响

- lexer/parser/AST 增加字面量、后缀索引与索引赋值。
- 类型检查为 `[]` 提供期望类型并记录精确索引路径。
- IR 显式表示字面量构造、检查式读取、路径更新与带类型 Map 操作。
- C99/WASM 共享边界、求值顺序、COW、所有权、panic 文本、Map 顺序、key equality 与容量上限。
- formatter 规范化逗号和空格；semantic/LSP 遍历所有新子表达式。
- Tree-sitter 暴露 `array_literal`/`index_expression`，Playground 用生产 WASM 提供可运行示例。

## 6. 验收门

parser、formatter、semantic、IR、C99、WASM、LSP bridge、Tree-sitter 与生产 Playground WASM 均已落实；一维/嵌套/jagged、COW 写回、诊断、泛型与 managed 值、Map 常用类型、StringMap 兼容以及受保护 CI 已提供证据，因此状态为 `Accepted`。
