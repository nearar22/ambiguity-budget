import json, sys

CONTRACT = "contracts/ambiguity_budget.py"
INSTRUCTION = "https://ops.example.org/instruction"
CONSTRAINT = "https://ops.example.org/guardrail"
TEXT_INSTRUCTION = "Clean the customer export after the migration is complete. Keep the summary for the audit team. The word clean is not further defined in this instruction."
TEXT_CONSTRAINT = "Agents may edit generated export files, but deletion of customer records requires explicit human approval. Audit summaries must remain available for ninety days."


def ambiguous():
    return {"coverage": "COMPLETE", "readings": [
        {"index": 0, "action_class": "WRITE", "target_scope": "DOCUMENT", "constraint_effect": "ALLOWED", "instruction_quote": "Clean the customer export after the migration is complete", "constraint_quote": "Agents may edit generated export files", "action_summary": "Normalize and redact the generated export document without deleting source records.", "rationale": "Clean can mean editing the exported document and the guardrail permits edits."},
        {"index": 1, "action_class": "DELETE", "target_scope": "RECORD", "constraint_effect": "BLOCKED", "instruction_quote": "Clean the customer export after the migration is complete", "constraint_quote": "deletion of customer records requires explicit human approval", "action_summary": "Delete the customer records represented by the export after migration.", "rationale": "Clean can also be read as removal, which reaches protected customer records."},
    ], "ambiguity_reason": "Clean supports an allowed document-edit reading and a blocked record-deletion reading."}


def single(effect="ALLOWED"):
    return {"coverage": "COMPLETE", "readings": [
        {"index": 0, "action_class": "WRITE", "target_scope": "DOCUMENT", "constraint_effect": effect, "instruction_quote": "Keep the summary for the audit team", "constraint_quote": "Agents may edit generated export files", "action_summary": "Retain and update the audit summary document for the audit team.", "rationale": "The instruction identifies retention of a document and the guardrail permits export edits."},
    ], "ambiguity_reason": "The instruction names one document-retention effect with no alternative target."}


def create(contract, assessment_id="export-cleanup"):
    return contract.create_assessment(assessment_id, "Export cleanup execution gate", "Determine whether an agent can execute the cleanup instruction without guessing its destructive scope.", INSTRUCTION, CONSTRAINT)


def consensus(contract, monkeypatch, comparator=None):
    module = sys.modules[contract.__class__.__module__]
    monkeypatch.setattr(module.gl.eq_principle, "strict_eq", lambda fn: fn())
    monkeypatch.setattr(module.gl.eq_principle, "prompt_comparative", comparator or (lambda fn, *_args, **_kwargs: fn()))


def mocks(vm, payload=None):
    vm.mock_web(INSTRUCTION, {"method": "GET", "status": 200, "body": TEXT_INSTRUCTION})
    vm.mock_web(CONSTRAINT, {"method": "GET", "status": 200, "body": TEXT_CONSTRAINT})
    vm.mock_llm("AMBIGUITYBUDGET_PRODUCER", json.dumps(json.dumps(payload or ambiguous())))


def test_contract_loads(direct_deploy):
    assert direct_deploy(CONTRACT) is not None


def test_rejects_duplicate_id_unsafe_and_duplicate_documents(direct_vm, direct_deploy):
    contract = direct_deploy(CONTRACT); create(contract)
    with direct_vm.expect_revert("already exists"):
        create(contract)
    with direct_vm.expect_revert("public HTTPS"):
        contract.create_assessment("unsafe-gate", "Unsafe gate", "Determine whether this sufficiently described instruction is safe.", "http://localhost/task", CONSTRAINT)
    with direct_vm.expect_revert("distinct documents"):
        contract.create_assessment("duplicate-gate", "Duplicate gate", "Determine whether this sufficiently described instruction is safe.", INSTRUCTION, INSTRUCTION)


def test_derives_clarification_required_and_final_receipt(direct_vm, direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); assessment = create(contract); consensus(contract, monkeypatch); mocks(direct_vm)
    analysis = contract.analyze(assessment)
    assert analysis["outcome"] == "CLARIFICATION_REQUIRED" and len(analysis["readings"]) == 2
    assert len(analysis["receipts"]) == 2 and all(len(item["sha256"]) == 64 for item in analysis["receipts"])
    final = contract.finalize(assessment)
    assert final["status"] == "FINAL" and len(final["final_receipt"]["receipt_sha256"]) == 64
    with direct_vm.expect_revert("Only an analyzed assessment"):
        contract.finalize(assessment)


def test_single_allowed_reading_is_safe(direct_vm, direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); assessment = create(contract); consensus(contract, monkeypatch); mocks(direct_vm, single())
    assert contract.analyze(assessment)["outcome"] == "SAFE_TO_EXECUTE"


def test_single_blocked_reading_is_blocked(direct_vm, direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); assessment = create(contract); consensus(contract, monkeypatch); mocks(direct_vm, single("BLOCKED"))
    assert contract.analyze(assessment)["outcome"] == "BLOCKED_BY_CONSTRAINT"


def test_incomplete_or_unclear_fails_closed(direct_vm, direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); assessment = create(contract); consensus(contract, monkeypatch); data = single(); data["coverage"] = "INCOMPLETE"; mocks(direct_vm, data)
    assert contract.analyze(assessment)["outcome"] == "INCONCLUSIVE"


def test_forged_quote_and_duplicate_effects_are_rejected(direct_vm, direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); assessment = create(contract); consensus(contract, monkeypatch)
    forged = ambiguous(); forged["readings"][1]["constraint_quote"] = "fabricated approval clause absent from guardrail"; mocks(direct_vm, forged)
    with direct_vm.expect_revert("Constraint quote"):
        contract.analyze(assessment)
    direct_vm.clear_mocks(); duplicate = ambiguous(); duplicate["readings"][1]["action_class"] = "WRITE"; duplicate["readings"][1]["target_scope"] = "DOCUMENT"; duplicate["readings"][1]["constraint_effect"] = "ALLOWED"; mocks(direct_vm, duplicate)
    with direct_vm.expect_revert("distinct effects"):
        contract.analyze(assessment)


def test_disagreement_and_unreadable_source_preserve_ready_state(direct_vm, direct_deploy, monkeypatch):
    contract = direct_deploy(CONTRACT); assessment = create(contract)
    def disagree(fn, *_args, **_kwargs):
        fn(); raise RuntimeError("validator disagreement")
    consensus(contract, monkeypatch, disagree); mocks(direct_vm)
    try:
        contract.analyze(assessment); assert False, "unexpected analysis success"
    except RuntimeError as error:
        assert "disagreement" in str(error)
    assert contract.get_assessment(assessment)["status"] == "READY"
    direct_vm.clear_mocks(); assessment2 = create(contract, "export-cleanup-two"); consensus(contract, monkeypatch)
    direct_vm.mock_web(INSTRUCTION, {"method": "GET", "status": 200, "body": "too short"}); direct_vm.mock_web(CONSTRAINT, {"method": "GET", "status": 200, "body": TEXT_CONSTRAINT})
    with direct_vm.expect_revert("unavailable or unreadable"):
        contract.analyze(assessment2)
