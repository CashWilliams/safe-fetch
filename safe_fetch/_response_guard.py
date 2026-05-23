"""Post-fetch response scanning: invisible char stripping, injection detection."""
from __future__ import annotations

import logging
import re
import unicodedata
from inspect import isawaitable
from typing import Any

from ._exceptions import InjectionDetectedError, Policy
from ._types import InjectionFinding

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Invisible / zero-width character stripping
# ---------------------------------------------------------------------------

_INVISIBLE_CHARS = re.compile(
    r"[\u200b\u200c\u200d\u2060\u00ad\ufeff\u2028\u2029\u180e\u200e\u200f]"
)


def strip_invisible(text: str) -> str:
    """Remove zero-width and invisible Unicode characters. Always applied."""
    return _INVISIBLE_CHARS.sub("", text)


# ---------------------------------------------------------------------------
# Injection pattern library
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    # Instruction override phrases
    ("ignore_previous_instructions", re.compile(
        r"ignore\s+(previous|prior|all\s+previous)\s+instructions?", re.IGNORECASE
    )),
    ("disregard_instructions", re.compile(
        r"disregard\s+(your\s+)?(previous\s+)?instructions?", re.IGNORECASE
    )),
    ("forget_instructions", re.compile(
        r"forget\s+(your\s+)?(previous\s+)?instructions?", re.IGNORECASE
    )),
    ("new_instructions", re.compile(
        r"your\s+new\s+instructions?\s+are", re.IGNORECASE
    )),
    ("override_instructions", re.compile(
        r"override\s+your\s+(previous\s+)?instructions?", re.IGNORECASE
    )),
    # Role-play / persona hijacking
    ("you_are_now", re.compile(
        r"\byou\s+are\s+now\b(?!\s+able)", re.IGNORECASE
    )),
    ("act_as", re.compile(
        r"\bact\s+as\s+(a|an|the)\b", re.IGNORECASE
    )),
    ("pretend_you_are", re.compile(
        r"\bpretend\s+(you\s+are|to\s+be)\b", re.IGNORECASE
    )),
    ("your_true_self", re.compile(
        r"\byour\s+true\s+self\b", re.IGNORECASE
    )),
    # System prompt markers
    ("system_tag", re.compile(
        r"<\s*system\s*>", re.IGNORECASE
    )),
    ("im_start_system", re.compile(
        r"<\|im_start\|>\s*system", re.IGNORECASE
    )),
    ("inst_marker", re.compile(
        r"\[INST\]", re.IGNORECASE
    )),
    ("markdown_system_header", re.compile(
        r"^#{1,3}\s+(System|Instructions?)\s*:?\s*$", re.IGNORECASE | re.MULTILINE
    )),
    # Exfiltration attempts
    ("repeat_everything_above", re.compile(
        r"repeat\s+everything\s+(above|before)", re.IGNORECASE
    )),
    ("print_system_prompt", re.compile(
        r"print\s+(your\s+)?system\s+prompt", re.IGNORECASE
    )),
    ("what_were_your_instructions", re.compile(
        r"what\s+were\s+your\s+instructions?", re.IGNORECASE
    )),
    # LLM control-token injection (general <|...|> format)
    ("llm_control_token", re.compile(
        r"<\|[^|>\s][^|>]*\|>"
    )),
    # Override openers
    ("new_system_prompt", re.compile(
        r"\bnew\s+system\s+prompt\b", re.IGNORECASE
    )),
    ("new_rule_opener", re.compile(
        r"\bnew\s+rule\s*:", re.IGNORECASE
    )),
    # Fake authority-claim brackets (case-sensitive — avoids [admin] in logs, [System.out in Java)
    ("admin_claim", re.compile(
        r"\[ADMIN\s*:"
    )),
    ("system_override_claim", re.compile(
        r"\[SYSTEM\s+OVERRIDE"
    )),
]

# ---------------------------------------------------------------------------
# Code-block extraction (for scan copy only — not applied to returned content)
# ---------------------------------------------------------------------------

# Matches fenced code blocks: ```(lang)?\n...\n```
_FENCED_CODE_RE = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
# Matches inline code spans: `...` (single line only)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def _extract_prose(text: str) -> str:
    """Return text with fenced code blocks and inline code spans removed.

    Used only on the scan copy — the original content is returned to the caller.
    Prevents false positives on legitimate code examples in technical documentation.
    """
    text = _FENCED_CODE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def _redact_prose_only(text: str, pattern: re.Pattern) -> str:
    """Apply pattern.sub redaction to prose segments only, preserving code blocks verbatim."""
    result: list[str] = []
    last = 0
    for m in _FENCED_CODE_RE.finditer(text):
        # Redact the prose segment before this code block
        prose = text[last:m.start()]
        result.append(pattern.sub("[CONTENT REDACTED: potential injection]", prose))
        # Preserve the code block unchanged
        result.append(m.group())
        last = m.end()
    # Redact any trailing prose after the last code block
    result.append(pattern.sub("[CONTENT REDACTED: potential injection]", text[last:]))
    return "".join(result)


# Heuristic thresholds
_HEURISTIC_THRESHOLD = 0.7

# Sentence-ending punctuation for splitting
_SENTENCE_SPLIT = re.compile(r"[.!?]+\s+")

# Command verbs commonly starting imperative sentences
_COMMAND_VERBS = re.compile(
    r"^\s*(do|make|create|write|tell|say|give|show|provide|output|print|"
    r"ignore|forget|disregard|override|pretend|act|imagine|assume|respond|"
    r"return|list|explain|describe|repeat|reveal|expose)\b",
    re.IGNORECASE,
)

# Turn delimiter patterns
_TURN_DELIMITERS = re.compile(
    r"(^|\n)\s*(Human:|Assistant:|User:|System:|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\])",
    re.IGNORECASE,
)


def _snippet(text: str, match_start: int, match_end: int, context: int = 50) -> str:
    start = max(0, match_start - context)
    end = min(len(text), match_end + context)
    return text[start:end]


# ---------------------------------------------------------------------------
# Regex pattern scan
# ---------------------------------------------------------------------------

def _scan_patterns(text: str) -> list[InjectionFinding]:
    findings: list[InjectionFinding] = []
    for name, pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            findings.append(
                InjectionFinding(
                    confidence="HIGH",
                    pattern_matched=name,
                    heuristic=None,
                    snippet=_snippet(text, m.start(), m.end()),
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Structural heuristic scorer
# ---------------------------------------------------------------------------

def _structural_score(text: str) -> float:
    """Return a risk score 0.0–1.0 based on structural heuristics."""
    score = 0.0

    sentences = _SENTENCE_SPLIT.split(text)
    if not sentences:
        return 0.0

    # 1. Imperative sentence ratio
    imperative_count = sum(1 for s in sentences if _COMMAND_VERBS.match(s))
    imperative_ratio = imperative_count / len(sentences)
    score += imperative_ratio * 0.4

    # 2. Numbered step + command verb density (instruction-like lists)
    numbered_steps = re.findall(r"^\s*\d+\.\s+(.+)$", text, re.MULTILINE)
    if numbered_steps:
        cmd_steps = sum(1 for s in numbered_steps if _COMMAND_VERBS.match(s))
        step_density = cmd_steps / len(numbered_steps)
        score += step_density * 0.35

    # 3. Turn delimiter presence
    if _TURN_DELIMITERS.search(text):
        score += 0.35

    return min(score, 1.0)


def _heuristic_scan(text: str) -> list[InjectionFinding]:
    score = _structural_score(text)
    if score >= _HEURISTIC_THRESHOLD:
        return [
            InjectionFinding(
                confidence="MEDIUM",
                pattern_matched=None,
                heuristic=f"structural_score={score:.2f}",
                snippet=text[:100],
            )
        ]
    return []


# ---------------------------------------------------------------------------
# LLM escalation
# ---------------------------------------------------------------------------

async def _escalate_with_llm(finding: InjectionFinding, text: str, llm_client: Any) -> InjectionFinding:
    """Call llm_client.classify_injection(text) and upgrade finding if adversarial."""
    try:
        result = llm_client.classify_injection(text)
        is_adversarial = await result if isawaitable(result) else result
        if is_adversarial:
            return InjectionFinding(
                confidence="HIGH",
                pattern_matched=finding.pattern_matched,
                heuristic=finding.heuristic + "+llm_escalated" if finding.heuristic else "llm_escalated",
                snippet=finding.snippet,
            )
    except Exception as exc:
        log.warning("LLM escalation call failed: %s", exc)
    return finding


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def scan_response(
    content: str,
    policy: Policy,
    llm_client: Any = None,
) -> tuple[str, list[InjectionFinding]]:
    """
    Scan response content for injection.

    Returns (cleaned_content, findings).
    Raises InjectionDetectedError under STRICT policy on HIGH findings.
    """
    # Always strip invisible characters first
    cleaned = strip_invisible(content)

    # Build scan copy: NFKC-normalized + prose-only (code blocks excluded)
    # Normalization collapses homoglyphs/lookalikes; code extraction prevents FPs on docs.
    # Neither transformation is applied to `cleaned` — the caller receives the original.
    scan_text = _extract_prose(unicodedata.normalize("NFKC", cleaned))

    # Regex pattern scan — HIGH confidence
    pattern_findings = _scan_patterns(scan_text)

    # Structural heuristic scan — MEDIUM confidence
    heuristic_findings = _heuristic_scan(scan_text)

    # LLM escalation for MEDIUM findings (only if no HIGH already and client provided)
    upgraded_heuristic: list[InjectionFinding] = []
    if (
        policy in (Policy.STRICT, Policy.WARN)
        and llm_client is not None
        and heuristic_findings
        and not pattern_findings
    ):
        for f in heuristic_findings:
            upgraded = await _escalate_with_llm(f, cleaned, llm_client)
            upgraded_heuristic.append(upgraded)
    else:
        upgraded_heuristic = heuristic_findings

    all_findings = pattern_findings + upgraded_heuristic
    high_findings = [f for f in all_findings if f.confidence == "HIGH"]

    if not all_findings:
        return cleaned, []

    if policy == Policy.STRICT:
        raise InjectionDetectedError(
            f"Injection detected in response ({all_findings[0].pattern_matched or all_findings[0].heuristic})",
            findings=all_findings,
        )

    if policy == Policy.WARN:
        for f in all_findings:
            log.warning("safe-fetch injection finding: confidence=%s pattern=%s", f.confidence, f.pattern_matched or f.heuristic)
        if high_findings:
            # Redact matched snippets from prose only — preserve code blocks verbatim.
            # Split cleaned into segments, redact prose segments, reassemble.
            for f in high_findings:
                if f.pattern_matched:
                    for name, pattern in _INJECTION_PATTERNS:
                        if name == f.pattern_matched:
                            cleaned = _redact_prose_only(cleaned, pattern)
                            break

    return cleaned, all_findings
