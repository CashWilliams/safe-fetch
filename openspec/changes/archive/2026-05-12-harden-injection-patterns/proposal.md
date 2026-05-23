## Why

The response injection scanner misses several active-in-the-wild jailbreak techniques seen in real fetched content: Unicode homoglyph encoding that disguises harmful text, LLM control-token injection (`<|GODMODE|>` etc.), and common prose-level override phrases ("New system prompt.", "new rule:"). At the same time, the scanner must not flag legitimate content — code examples in technical documentation routinely contain tokens, template variables, and command-like syntax that are valid and useful to an agent reading docs.

## What Changes

- **Pre-scan NFKC normalization**: normalize Unicode before any pattern matching so homoglyph-encoded text (circled letters, fullwidth chars, lookalike scripts) is collapsed to ASCII equivalents and caught by existing patterns.
- **Code-block-aware scanning**: extract fenced markdown code blocks (` ``` `) and inline code (`` ` ``) before running pattern detection; patterns are applied only to prose text, preventing false positives on documentation code examples.
- **New prose-level patterns**: add pattern library entries for:
  - General LLM control-token format `<|...|>` (covers `<|GODMODE:ENABLED|>`, `<|vq_420|>`, etc.)
  - "New system prompt" / "new rule:" override openers
  - Fake authority-claim brackets `[ADMIN:`, `[SYSTEM OVERRIDE` (bounded to avoid `[System.out`, `[admin]` in log output)
- **Patterns deliberately excluded** due to unacceptable FP risk on real content: emoji proximity heuristics, generic `{variable}` template syntax, bare keyword lists.

## Capabilities

### New Capabilities

- `unicode-normalization`: NFKC normalization applied to response content before injection scanning
- `code-block-aware-scan`: prose/code separation before pattern matching to protect technical documentation

### Modified Capabilities

- `response-guard`: new patterns added to `_INJECTION_PATTERNS`; scanner receives pre-normalized, code-stripped text

## Impact

- `safe_fetch/_response_guard.py`: normalization step, code-block extraction, new patterns
- `tests/test_response_guard.py`: new test cases for each new pattern and for normalization
- No new dependencies — stdlib `unicodedata` for normalization, regex for code-block extraction
- No API changes; `InjectionFinding` and `scan_response` signatures unchanged
