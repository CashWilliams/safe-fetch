## Purpose
Normalize response scan text to catch Unicode-obfuscated injection phrases without changing returned content.

## Requirements

### Requirement: NFKC normalization before injection scanning
The response guard SHALL apply Unicode NFKC normalization to a copy of the fetched content before running pattern matching. The normalized copy is used only for scanning; the original (invisible-char-stripped) content is returned to the caller.

NFKC normalization collapses compatibility equivalents: circled letters (`ⓗⓞⓦ` → `how`), fullwidth ASCII (`ａｂｃ` → `abc`), superscripts (`²` → `2`), ligatures (`ﬁ` → `fi`), and similar Unicode variants that can disguise injection phrases from regex-based detectors.

#### Scenario: Circled-letter encoded phrase is detected
- **WHEN** fetched content contains `ⓗⓞⓦ ⓣⓞ ⓜⓐⓚⓔ` (circled letters encoding "how to make")
- **THEN** the normalized scan copy contains `how to make` and any pattern that would match that phrase fires normally

#### Scenario: Returned content is not altered by normalization
- **WHEN** fetched content contains fullwidth or circled Unicode characters
- **THEN** the content returned to the caller preserves the original characters; only the internal scan copy is normalized

#### Scenario: Normalization is always applied regardless of policy
- **WHEN** `response_policy=PERMISSIVE`
- **THEN** NFKC normalization is still applied to the scan copy (consistent with invisible-char stripping, which is also always applied)

#### Scenario: Normal ASCII content is unaffected
- **WHEN** fetched content contains only standard ASCII characters
- **THEN** NFKC normalization is a no-op and scanning behavior is unchanged
