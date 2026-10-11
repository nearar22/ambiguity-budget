# AmbiguityBudget

Automation fails most dangerously when an instruction sounds clear but supports two different operational effects. AmbiguityBudget is a pre-execution gate: validators read a published instruction beside its guardrail, identify one or two textually defensible action signatures, and bind each reading to exact quotations.

Contract code—not the language model—derives one of four outcomes: `SAFE_TO_EXECUTE`, `CLARIFICATION_REQUIRED`, `BLOCKED_BY_CONSTRAINT`, or `INCONCLUSIVE`. Two paraphrases are not ambiguity; alternative readings must differ in action, scope, or constraint effect.

## State path

`READY → ANALYZED → FINAL`

Analysis and finalization are permissionless. Missing source text, invented targets, unclear constraints, validator disagreement, and fabricated quotations cannot silently become approval.

## Local checks

```bash
python -m pytest tests -q
genvm-lint lint contracts/ambiguity_budget.py --json
```

The `docs/` records are synthetic test fixtures. They are not operational instructions. Target: GenLayer Studio Next (`61997`).
