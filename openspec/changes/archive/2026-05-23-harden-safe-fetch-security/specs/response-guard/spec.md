## ADDED Requirements

### Requirement: Classifier timeout and failure policy
The response guard SHALL enforce `classifier_timeout` for optional LLM escalation and SHALL apply `classifier_failure_policy` when classification fails or times out.

#### Scenario: Classifier timeout fails closed
- **WHEN** a classifier call exceeds `classifier_timeout` and classifier failure policy is STRICT
- **THEN** `ClassifierError` is raised

#### Scenario: Classifier timeout warns
- **WHEN** a classifier call exceeds `classifier_timeout` and classifier failure policy is WARN
- **THEN** a safety event is recorded and local heuristic findings are preserved

### Requirement: Expanded prompt-injection pattern coverage
The response guard SHALL detect direct, indirect, typoglycemia, encoded, fake tool-call, instruction hierarchy, exfiltration, and Markdown/HTML prompt-injection indicators outside excluded code spans.

#### Scenario: Fake tool call is detected
- **WHEN** fetched prose contains a fake tool invocation instructing the agent to call a privileged tool
- **THEN** a response finding is produced

### Requirement: Redaction of normalized-only findings
The response guard SHALL redact or neutralize content that only matched after Unicode normalization according to configured `redaction_mode`.

#### Scenario: Normalized-only match is not returned verbatim in WARN mode
- **WHEN** NFKC normalization exposes an injection phrase that is not directly present in original text
- **THEN** safe output redacts or neutralizes the corresponding original content
