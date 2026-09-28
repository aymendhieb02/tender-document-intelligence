# Requirements Intelligence V1

## Purpose

Requirements Intelligence turns candidate clauses from the deterministic CDC Analyzer into a typed, reviewable interpretation of tender obligations. It uses ordinary local rules only. It does not call an LLM, Ollama, embeddings, external services, OCR, or a PDF parser.

The data flow is:

`DocumentResult → CDC Analyzer → TenderDocument → app.requirements_intelligence`

The public entry point is `classify_document(tender_document)`. It reads CDC requirements, articles, clauses, and paragraphs already in the `TenderDocument`. It never opens the source file or invokes the CDC parser.

## Contract

`TenderRequirement` is a separate model from CDC's extraction candidate `Requirement`. CDC remains responsible for detecting and locating candidate text; this package adds category and obligation semantics without changing CDC's contract.

Each result includes:

- a deterministic ID, category, title, and original description;
- mandatory status, responsible party, action, and an explicit condition when recognized;
- the originating CDC candidate or article ID, when present;
- the complete original CDC evidence objects, their element IDs and producer source element IDs, and the first source evidence page;
- a qualitative confidence label and `NEEDS_REVIEW` status.

Evidence remains byte-for-byte represented by the existing typed evidence values. A result with no evidence is rejected by `classify_text` and omitted by `classify_document`; a page is populated only from supplied evidence. CDC value normalization is not reproduced or invented. When V1 sees a CDC requirement candidate with a value, its candidate ID is retained as `source_requirement_id`.

`related_value_refs` is empty until CDC provides explicit value-reference IDs. `source_requirement_id` is a link to the candidate and is not presented as a normalized value.

## Taxonomy

The extensible `RequirementCategory` enum currently contains:

`ADMINISTRATIVE`, `ELIGIBILITY`, `LEGAL`, `TECHNICAL`, `FINANCIAL`, `SUBMISSION`, `EXECUTION`, `PAYMENT`, `GUARANTEE`, `PENALTY`, `DEADLINE`, `REQUIRED_DOCUMENT`, `EXPERIENCE`, `PERSONNEL`, `EQUIPMENT`, `CERTIFICATION`, `INSURANCE`, `WARRANTY`, `EVALUATION`, and `OTHER`.

Obligation modality is `MANDATORY`, `OPTIONAL`, `CONDITIONAL`, or `UNCLEAR`. Review state is independently `NEEDS_REVIEW`, `REVIEWED`, `ACCEPTED`, or `REJECTED`. Machine classifications start as `NEEDS_REVIEW`; this package does not perform human approval.

## Deterministic rules

The classifier folds case and French diacritics, then checks explicit required-document cues followed by ordered topic patterns. Arabic category and obligation terms are recognized where the current evidence text contains them. Narrow cues such as `attestation` and `documents requis` identify a required document; a generic mention of a document does not.

Explicit obligation terms such as French `doit`, `sont tenus de`, `obligatoire` and Arabic `يجب`, `يلتزم`, `يتعين` support `MANDATORY`. Clear permissive terms such as `facultatif`, `peut` and `يمكن` support `OPTIONAL`. A recognized condition paired with obligation wording, such as `si ... doit`, `en cas de` or `إذا`, is `CONDITIONAL`. A topic or extracted candidate without clear modality remains `UNCLEAR`. Imperative action verbs help identify the action and discover clauses but do not alone prove mandatory modality.

No score threshold or document-specific rule is used. Confidence is `HIGH` only when a mandatory cue and a recognized non-`OTHER` category are both present; otherwise it is `LOW`. All outputs still need review.

## Examples

| Source wording | Category | Status | Action |
| --- | --- | --- | --- |
| `Le candidat doit fournir une attestation fiscale.` | `REQUIRED_DOCUMENT` | `MANDATORY` | `submit` |
| `Le candidat peut fournir une assurance facultative.` | `INSURANCE` | `OPTIONAL` | `submit` |
| `Si le candidat est retenu, il doit présenter son certificat.` | `REQUIRED_DOCUMENT` | `CONDITIONAL` | `submit` |
| `يلتزم المتعهد بتقديم ضمان بنكي` | `GUARANTEE` | `MANDATORY` | `submit` |
| `Garantie bancaire.` | `GUARANTEE` | `UNCLEAR` | unset |

Each example is only classified when the CDC item carries source evidence.

## Extension strategy

Add category patterns in `_CATEGORY_RULES`, keeping specific phrases before broad ones. Add modality or action phrases to the named rule groups and add positive and negative tests for both the recognized phrase and a nearby non-obligation. Keep output fields typed, deterministic, evidence-linked, and reviewable. New category enum members are additive; changing category interpretation or the serialized contract should be versioned and documented.

## Limitations

This is a bounded phrase classifier, not legal interpretation, full French/Arabic NLP, or a guarantee that every CDC obligation is found. It does not infer responsibility, values, deadlines, or legal effect absent explicit wording. Category patterns can overlap; their order is part of the current deterministic behavior. Arabic coverage is limited to the phrases encoded in the rules and tested examples. Human review remains required, and the classifier does not improve or alter benchmark ground truth.
