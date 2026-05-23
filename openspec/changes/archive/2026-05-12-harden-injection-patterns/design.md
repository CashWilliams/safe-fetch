## Context

The response guard currently scans fetched content as a flat string. This works for simple prose injection but misses two classes of attack seen in the wild:

1. **Encoding evasion**: Unicode homoglyphs and lookalike characters (e.g. circled letters `ⓗⓞⓦ` = "how") rewrite injection phrases so regex patterns never match. NFKC normalization (Python stdlib `unicodedata.normalize`) collapses these to ASCII equivalents before scanning.

2. **Token-format injection**: LLM control-token syntax like `<|GODMODE:ENABLED|>`, `<|vq_420|>`, `<|channel|>` does not match the existing `<|im_start|>system` pattern. A generalized `<|...|>` pattern would cover the whole class.

There is also a gap in prose-level patterns: "New system prompt." and authority-claim brackets `[ADMIN: ...]` are common in real jailbreak payloads but absent from the library.

**The critical constraint**: safe-fetch is used by agents reading technical documentation. Code examples in docs routinely contain things that look like injections — LLM tokenizer examples reference `<|im_start|>`, API templates use `{variable}` syntax, tutorials include `[System.out.println]` in log output. Scanning code examples would cause false positives that break the agent's ability to fetch docs. This is treated as a hard constraint: new patterns must only fire on prose, not code.

## Goals / Non-Goals

**Goals:**
- NFKC normalization applied to response content before any scanning
- Code-block-aware scan: fenced blocks (` ``` ... ``` `) and inline code (`` `...` ``) are extracted and excluded from pattern matching, then restored in the returned content
- New patterns for: general `<|...|>` token format, "New system prompt" / "new rule:" openers, `[ADMIN:` / `[SYSTEM OVERRIDE` authority-claim brackets
- All new patterns apply exclusively to prose text (non-code portions)

**Non-Goals:**
- Emoji proximity heuristics — FP risk too high; emoji appear legitimately in content
- Generic `{variable}` template syntax — extremely common in all documentation
- ML-based classification beyond the existing `llm_client` escalation path
- Modifying the `strip_invisible` step — it already runs unconditionally and is separate from pattern scanning

## Decisions

**D1: NFKC normalization scope — normalize for scanning only, not for returned content**

Normalize a copy of the text for scanning purposes but return the original (invisible-char-stripped) content to the caller. Rationale: NFKC changes characters (e.g. `ﬁ` → `fi`, `²` → `2`), which would alter content the agent sees. The agent should receive the original; we only need normalization to make our patterns more effective.

Alternative considered: normalize the returned content too. Rejected because it modifies content in ways the caller may not expect, and could garble mathematical notation, ligatures, or non-Latin scripts in legitimate content.

**D2: Code-block extraction strategy — regex pre-pass, not a full Markdown parser**

Strip code before pattern scanning using two regexes:
- Fenced blocks: ` ```(language)?\n...\n``` ` (multiline, non-greedy)
- Inline code: `` `[^`]+` ``

Rationale: a full Markdown AST parser (e.g. `mistletoe`, `markdown-it-py`) is an additional dependency and adds latency. The regex approach handles the overwhelming majority of real-world cases. Edge cases (nested fences, indented code blocks) are acceptable misses — indented code blocks are rare in fetched web content.

Alternative considered: scanning code blocks separately with a lower-sensitivity profile. Rejected as over-engineering; the right call is to skip them entirely.

**D3: `[ADMIN:` pattern boundary — require uppercase and colon, bound on the right**

Pattern: `\[ADMIN\s*:|\[SYSTEM\s+OVERRIDE` — not `\[admin\]` or `\[System\]`.

The uppercase + colon form is the jailbreak convention. Lowercase `[admin]` appears legitimately in log output, role assignments, etc. `[System.out` is matched by `\[System\s+` only if followed by a space + word boundary, so Java log output is safe.

**D4: General `<|...|>` pattern — require at least one non-whitespace character inside**

Pattern: `<\|[^|>\s][^|>]*\|>` — must have content, prevents matching `<||>` decorative dividers that appear in some pages.

Wait — actually `<||>` is used as a custom delimiter in the jailbreak payload we observed. Include it. Revised: `<\|[^>]*\|>` with a minimum content length of 1 char. A plain `<||>` (two pipes, no content) would still match, which is correct.

## Risks / Trade-offs

**[Risk] Regex code-block extraction misses indented code blocks and edge cases** → Mitigation: acceptable; indented code is rare in fetched HTML-derived markdown. Add a note in code comments. The practical impact is low because indented code blocks rarely contain LLM token syntax.

**[Risk] NFKC normalization changes mathematical superscripts (e.g. `²` → `2`)** → Mitigation: normalization is applied to the scan copy only, not the returned content (see D1). No impact on agent-facing output.

**[Risk] `<\|...\|>` pattern fires on pages that happen to document LLM tokenizers** → Mitigation: those code examples will be inside fenced code blocks (e.g. Python `tiktoken` docs), which are excluded before pattern matching. Prose references like "the model uses `<|im_start|>` tokens" contain inline code and are also excluded.

**[Risk] New "new system prompt" pattern fires on academic/security research articles discussing jailbreaks** → Mitigation: this is a known limitation of any injection scanner. Under `WARN` policy (the default) the content is returned with findings recorded; only `STRICT` raises. An agent receiving content with findings can decide what to do. Consider this acceptable.
