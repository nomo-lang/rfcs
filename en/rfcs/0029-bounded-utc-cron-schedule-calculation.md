# RFC 0029: Bounded UTC Cron Schedule Calculation

> Language: [中文](../../zh-CN/rfcs/0029-bounded-utc-cron-schedule-calculation.md) | English

## Metadata

| Field | Value |
| --- | --- |
| Number | 0029 |
| Title | Bounded UTC cron schedule calculation |
| Status | Proposed |
| Author | Nomo Language Working Group |
| Created | 2026-07-25 |
| Topics | cron, scheduling, time, Agent, bounds, browser WASM |
| Related RFCs | [RFC 0024](./0024-controlled-child-processes-and-stdio.md), [RFC 0026](./0026-isolated-native-tasks-and-cooperative-cancellation.md), [RFC 0027](./0027-bundled-sqlite-persistence-and-pull-queries.md) |

---

## 1. Summary

Nomo v0.1 should provide `std.cron`, a bounded, deterministic API for parsing
five-field UTC cron expressions, testing whether a minute matches, and finding
the next matching minute strictly after a supplied Unix timestamp.

The API performs schedule calculation only. It does not own a background
thread, persist jobs, execute callbacks, or choose a missed-run policy. A
long-running native Agent combines `std.cron` with `std.time`,
`std.task`, and, when needed, `std.sqlite`. Keeping those policy choices in
application code prevents a small standard-library primitive from becoming a
process-global scheduler.

Schedule calculation is pure after receiving its expression and timestamp.
It is therefore available in both the native C99 backend and browser WASM and
is safe inside an isolated task. Waiting remains an explicit native
`std.time.sleep_millis` operation.

## 2. Goals and Non-goals

### 2.1 Goals

1. Parse a familiar, explicitly bounded five-field cron syntax.
2. Use UTC and Unix milliseconds so results are independent of host locale,
   timezone database, and daylight-saving changes.
3. Match a supplied minute and find the next matching minute.
4. Define day-of-month and day-of-week interaction precisely.
5. Bound expression size, parsing work, timestamp range, and next-match search.
6. Return stable errors without panicking on untrusted schedule input.
7. Keep native and browser-WASM behavior identical.
8. Require no C FFI in Nomo application code.

### 2.2 Non-goals

This RFC does not add:

- a daemon, job registry, callback closure, background thread, or global event
  loop;
- persistence, leases, leader election, retries, overlap control, or a
  missed-run policy;
- local timezone or daylight-saving behavior;
- seconds or year fields;
- month/day names, `L`, `W`, `#`, `?`, `@daily`, or implementation-specific
  cron extensions;
- sub-minute timers, async/await, signals, or forceful task cancellation.

## 3. Current Gap

`std.time` exposes wall-clock and monotonic milliseconds plus blocking sleep.
`std.task` exposes isolated native workers and cooperative cancellation.
`std.sqlite` can persist application checkpoints. None of these APIs describes
calendar schedules or calculates a next trigger.

Applications can currently hand-roll modulo arithmetic or delegate scheduling
to a host-specific daemon. The former duplicates subtle Gregorian and
day-field behavior; the latter prevents one portable Nomo CLI Agent from
owning its scheduling policy.

## 4. Proposed Design

### 4.1 Canonical `std.cron` API

```rust
pub struct CronSchedule {
    expression: string
}

pub struct CronError {
    pub code: string
    pub message: string
    pub field: u64
}

cron.parse(expression: string) -> Result<CronSchedule, CronError>
cron.matches(schedule: CronSchedule, unix_millis: i64) -> Result<bool, CronError>
cron.next_after(schedule: CronSchedule, unix_millis: i64) -> Result<i64, CronError>
```

`CronSchedule` is opaque to application code: only `cron.parse` constructs it
and direct field access is rejected. `CronError.field` is zero through four
for minute, hour, day of month, month, and day of week. A whole-expression or
timestamp error uses five.

`matches` treats the timestamp as belonging to its UTC minute; seconds and
milliseconds do not affect the result.

`next_after` returns a minute boundary ending in `:00.000` and is strictly
greater than the supplied instant. Even when the input is exactly a matching
minute boundary, that same occurrence is not returned.

### 4.2 Expression grammar

An expression contains exactly five ASCII-whitespace-separated fields:

```text
minute hour day-of-month month day-of-week
```

Field ranges are:

| Field | Range |
| --- | --- |
| minute | `0..59` |
| hour | `0..23` |
| day of month | `1..31` |
| month | `1..12` |
| day of week | `0..6`, where `0` is Sunday |

Each field accepts:

- `*`;
- one unsigned decimal value;
- an inclusive range such as `1-5`;
- a list such as `1,3,5`;
- a wildcard or range followed by a positive step, such as `*/15` or
  `1-20/3`.

Lists may combine values, ranges, and stepped ranges. Whitespace inside a
field, empty list members, descending ranges, leading signs, values outside
the field range, zero steps, and unsupported names or extensions are rejected.

The complete expression is at most 256 UTF-8 bytes and must contain only ASCII
syntax accepted above. Duplicate selected values are harmless.

### 4.3 Day-field semantics

Minute, hour, and month must all match.

For day of month and day of week, a field is *unrestricted* when its selected
set covers its complete legal range, regardless of whether that set was
written as `*`, `*/1`, or a full range.

- if both day fields are unrestricted, every calendar day matches;
- if exactly one is unrestricted, the restricted field must match;
- if both are restricted, either field matching is sufficient.

This makes equivalent selected sets behave equivalently and removes the
surprising syntactic distinction between `*` and `*/1`.

### 4.4 UTC, range, and search bound

Timestamps use the proleptic Gregorian calendar in UTC and are limited to
`1970-01-01T00:00:00.000Z` through `9999-12-31T23:59:59.999Z`.

`next_after` checks at most 4,208,400 consecutive minute boundaries, slightly
more than the longest eight-year leap-day gap. This covers the longest valid
recurrence needed by the accepted grammar, including the Gregorian non-leap
century gap around 2100. If no match exists in that bound or before the
maximum timestamp, it returns `no_match`.

The implementation may skip impossible spans for efficiency, but observable
results must match a minute-by-minute search.

### 4.5 Error contract

`CronError.code` uses:

| Code | Meaning |
| --- | --- |
| `syntax` | wrong field count or malformed field grammar |
| `range` | value, range, or step is outside the field contract |
| `limit` | expression or bounded search limit is exceeded |
| `timestamp_range` | supplied timestamp is outside the supported UTC range |
| `no_match` | no later occurrence exists within the defined search/range |

Messages are stable enough for people but callers branch on `code`. Errors do
not reproduce the complete rejected expression.

### 4.6 Agent loop composition

A native Agent can keep policy explicit:

1. parse one schedule during startup;
2. read a persisted last-completed timestamp when catch-up behavior is wanted;
3. call `next_after`;
4. calculate the non-negative wait from `time.now_millis`;
5. sleep in a bounded loop so cancellation or shutdown can be observed;
6. launch or call the work;
7. persist completion before calculating the following occurrence.

The application decides whether to skip, coalesce, or replay missed
occurrences and whether overlapping work is permitted.

## 5. Alternatives

### 5.1 Add a process-global scheduler

Rejected for v0.1. It would require callback storage, ownership, shutdown,
overlap, panic, persistence, and thread-safety semantics before the language
has general closures or async tasks.

### 5.2 Support local timezones

Rejected for this slice. Correct local scheduling depends on a timezone
database and requires explicit behavior for nonexistent and duplicated civil
times. UTC is portable and sufficient for an Agent foundation.

### 5.3 Expose only interval timers

Monotonic interval timers are useful but do not cover daily or weekly
calendar work. Existing monotonic time and sleep already let applications
construct bounded interval loops.

### 5.4 Delegate all cron work to the operating system

Host cron or service managers remain valid deployment choices, but they cannot
support one portable Agent process that dynamically owns and persists its
schedule.

## 6. Acceptance Gates

RFC 0029 may become `Accepted` only when all of these are complete:

1. bilingual RFC, specification, standard-library docs, and source API agree;
2. parser tests cover every grammar form, field range, malformed input, and
   the 256-byte bound;
3. calendar tests cover epoch, leap years, non-leap centuries, month ends,
   all day-field cases, and strict next-minute behavior;
4. exact search and timestamp boundaries have tests;
5. `CronSchedule` construction and private field access are rejected;
6. native C99 and browser-WASM tests assert identical results and error codes;
7. a Nomo example demonstrates deterministic schedule calculation and an
   application-owned timer-loop pattern without application C FFI;
8. the pure operations are accepted from isolated tasks;
9. generated C remains C99-compatible and code not importing `std.cron`
   receives no cron-specific runtime support;
10. Linux, macOS, and Windows CI pass, commits are signed, the feature is
    merged through a child branch and PR, and synchronized local `main`
    worktrees are clean.

## 7. References

- [RFC 0026: Isolated native tasks and cooperative cancellation](./0026-isolated-native-tasks-and-cooperative-cancellation.md)
- [RFC 0027: Bundled SQLite persistence and pull-based queries](./0027-bundled-sqlite-persistence-and-pull-queries.md)
