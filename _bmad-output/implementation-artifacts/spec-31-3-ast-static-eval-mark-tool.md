---
title: '31-3 AST Static-Eval Policy for Dynamic JSX Expression Matching (Mark Tool)'
type: 'feature'
created: '2026-09-16'
status: 'done'
review_loop_iteration: 0
baseline_commit: '35a81b026'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `MarkToolASTMutator` only matches a JSX element by `className`/`id` when the attribute is a plain string literal. As soon as generated or user-edited JSX uses a dynamic expression — `className={cn("a b", ...)}`, `clsx(...)`, or a template literal `` `px-${s}` `` — `_get_attr_value` returns `None` and every class/id selector on that element silently misses, so the Mark Tool can't target real-world components.

**Approach:** Add a **safe static-eval policy** inside the mutator: recursively evaluate a `jsx_expression` only when every node is statically determinable (string literal, fully-literal template string, a whitelisted `cn`/`clsx`/`classnames` call over literal args, or a statically-known `&&`/`||`/`+`/`??` binary). Any identifier, call to a non-whitelisted function, or non-literal substitution → return `None` (no match, never guess). Never execute JavaScript — this is a security boundary, not just a matching improvement.

## Boundaries & Constraints

**Always:**
- Evaluate **only** statically-known values: `string`, `number`, `template_string` whose every `template_substitution` is itself statically-known, and whitelisted utility calls.
- Whitelist callees: `cn`, `clsx`, `classnames`, `classNames` (identifier callee only, e.g. `cn(...)` — not member calls like `utils.cn(...)`).
- `cn`/`clsx`/`classnames` semantics: flatten args, include a string arg's tokens when it is a literal, include the RHS literal of `cond && "x"`/`cond ? "x" : _` only when the whole expression is statically-known — otherwise treat that arg as **non-contributing but not fatal** only for `&&`/`||` truthy-guard patterns where the literal side is still emitted. Keep it conservative: when in doubt return `None`.
- On `None`, `_matches` keeps current behavior (class selector → `False`, so no match) — fail-safe, no false positives.
- Result of a resolved `className`/`id` is still a plain string fed to the existing `re.search` token matcher — unchanged downstream.
- Purely additive to `_get_attr_value`/`_attribute_value_text`: no change to patch-writing paths (`_patch_attribute` still always writes a string literal).
- No `eval`, no subprocess, no executing user code.

**Ask First:**
- Extending the callee whitelist beyond `cn`/`clsx`/`classnames`/`classNames`, or resolving member-expression callees (`x.cn`).
- Resolving identifier bindings (e.g. `const C = "a"; className={C}`) — this is scope/flow analysis, deliberately out of scope here.

**Never:**
- No executing or interpreting arbitrary JS (no `eval`, no Node subprocess, no Babel).
- No identifier/binding resolution or scope analysis.
- No behavior change to patch application, selector parsing, or non-`className`/`id` attribute matching.
- No frontend/route/schema changes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| `className` string literal (unchanged) | `<div className="a b">` sel `.a` | match | N/A |
| `cn` all-literal args | `<div className={cn("a b","c")}>` sel `.c` | resolve `"a b c"` → match | N/A |
| `clsx` nested literal | `<div className={clsx("a",["b","c"])}>` sel `.b` | resolve `a b c` → match | N/A |
| Template literal, all-literal subs | `<div className={`px-4 ${"m"}`}>` sel `.m` | resolve → match | N/A |
| `cn` with non-known arg | `<div className={cn("a", cond)}>` sel `.a` | resolve `"a"` → match `.a`; sel `.cond`→no match | conservative |
| `cond && "x"` guard | `<div className={cn("a", ok && "x")}>` sel `.a` | match `.a`; sel `.x`→no match (not statically-known) | conservative |
| Non-whitelisted call | `<div className={styles("a")}>` sel `.a` | `None` → no match | fail-safe |
| Identifier / member callee | `<div className={u.cn("a")}>` / `{C}` sel `.a` | `None` → no match | fail-safe |
| Template with identifier sub | `` <div className={`px-${s}`}>`` sel `.px-` | `None` → no match (sub not static) | fail-safe |
| `id` literal still works | `<div id="i">` sel `#i` | match | N/A |

## Code Map

- `nowing_backend/app/services/web_builder/mark_tool.py` — `MarkToolASTMutator`. `_get_attr_value` (:259) → `_attribute_value_text` (:271) currently returns the literal only for a `string` child and `None` otherwise. Add a static-eval resolver: when the `jsx_attribute`'s value child is a `jsx_expression`, evaluate its inner expression node to `str | None`. Feed the result into the existing literal path so `_matches` (:193) and `_patch_attribute` (:352) are unchanged.
- tree-sitter TSX node types (verified): `jsx_attribute` → `jsx_expression` → one of `string` / `template_string` / `call_expression` / `binary_expression` / `identifier`. `template_string` has `string_fragment` + `template_substitution` (`${expr}`) children. `call_expression` = `identifier` callee + `arguments` of expression children. `binary_expression` = left op right, op ∈ `&&`,`||`,`+`,`??`.
- Reuse `_node_text` (:31) to read node source; reuse `_attribute_value_text` literal-extraction for the `string` case.
- `nowing_backend/tests/unit/services/web_builder/test_mark_tool*.py` — existing mutator test file(s); add a `TestStaticEvalMatching` class covering the I/O matrix. Follow the file's existing fixture/assertion conventions.

## Tasks & Acceptance

**Execution:**
- [x] `nowing_backend/app/services/web_builder/mark_tool.py` — add a static-eval resolver (e.g. `_resolve_jsx_expr(node, source_bytes) -> str | None`) invoked from `_get_attr_value` when the attribute value is a `jsx_expression`; implement the whitelist + literal/template/binary rules from Boundaries — core matching widening, fail-safe on anything non-static
- [x] `nowing_backend/tests/unit/services/web_builder/test_mark_tool*.py` — `TestStaticEvalMatching` covering every I/O-matrix row — prove widening is correct and conservative

**Acceptance Criteria:**
- Given `className={cn("a b","c")}` and selector `.c`, when patching, then the element matches and is patched (previously missed).
- Given `className={cn("a", cond)}` or `{ok && "x"}`, when the selector targets the literal `.a`, then it matches; when it targets the non-static part, then it does **not** match.
- Given `className={styles("a")}` or `` `px-${s}` `` (non-static), when any class selector is used, then the element does not match (no false positive, no eval).
- Given an unchanged string-literal `className`/`id`, when matching, then behavior is identical to before (no regression).

## Spec Change Log

## Design Notes

- Conservative-by-default: the resolver returns `None` on any node it cannot prove static. For `cn`/`clsx` args that are `cond && "x"` / `cond ? "x" : _`, the literal side is emitted only under a runtime condition we cannot evaluate — so for *matching* we include the literal token only when it is unambiguous. Simplest safe rule adopted: a non-static arg contributes nothing; the call still resolves from its static args. This matches `.a` on `cn("a", cond)` without risking a `.x` false positive.
- Identifier/binding resolution is intentionally out of scope (scope analysis, not static-eval) — flagged under Ask First for a possible follow-up.

## Verification

**Commands:**
- `cd nowing_backend && uv run pytest tests/unit/services/web_builder/ -k mark_tool -q` — expected: all pass incl. new `TestStaticEvalMatching`
- `cd nowing_backend && uv run ruff check app/services/web_builder/mark_tool.py tests/unit/services/web_builder/` — expected: clean

## Suggested Review Order

**Static-eval resolver (security boundary)**

- Safe recursive evaluator: whitelist callee, `_UNKNOWN` fail-safe, never executes JS.
  [`mark_tool.py:65`](../../nowing_backend/app/services/web_builder/mark_tool.py#L65)
- `jsx_expression` dispatch — where dynamic `className`/`id` now resolves instead of returning `None`.
  [`mark_tool.py:559`](../../nowing_backend/app/services/web_builder/mark_tool.py#L559)

**JS-coercion correctness (review-driven fixes)**

- `_js_str` + `_js_truthy` — lowercase `true/false`, `null`, drop falsy `0`/""; match real clsx/cn semantics.
  [`mark_tool.py:37`](../../nowing_backend/app/services/web_builder/mark_tool.py#L37)
- `_decode_js_escapes` — decodes JS-only escapes (`\:`, `\xHH`, `\'`) so tokens aren't corrupted.
  [`mark_tool.py:65`](../../nowing_backend/app/services/web_builder/mark_tool.py#L65)

**Tests**

- `TestStaticEvalMatching` — one test per I/O-matrix row.
  [`test_mark_tool.py:356`](../../nowing_backend/tests/unit/services/web_builder/test_mark_tool.py#L356)
- `TestStaticEvalEdgeCases` — coercion/falsy/escape/top-level-expr regressions.
  [`test_mark_tool.py`](../../nowing_backend/tests/unit/services/web_builder/test_mark_tool.py)
