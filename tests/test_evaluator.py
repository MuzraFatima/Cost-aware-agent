import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.answer_evaluator import AnswerEvaluator
from backend.app.core.confidence_calibration import ConfidenceCalibrationService
from backend.app.core.router_engine import RouterEngine

client = TestClient(app)

def test_syntactic_evaluator_json_and_code():
    valid_json = '{"status": "ok", "code": 200}'
    malformed_json = '{"status": "incomplete", '
    
    score_ok, critiques_ok = AnswerEvaluator.evaluate_syntactic(valid_json, "json")
    assert score_ok >= 0.95
    assert len(critiques_ok) == 0

    score_fail, critiques_fail = AnswerEvaluator.evaluate_syntactic(malformed_json, "json")
    assert score_fail <= 0.20
    assert len(critiques_fail) > 0

    valid_py = "def add(a, b):\n    return a + b\n"
    invalid_py = "def broken(:\n return"

    py_ok, _ = AnswerEvaluator.evaluate_syntactic(valid_py, "python")
    assert py_ok == 1.0

    py_fail, py_critiques = AnswerEvaluator.evaluate_syntactic(invalid_py, "python")
    assert py_fail <= 0.20
    assert any("syntax" in c.lower() for c in py_critiques)

def test_semantic_and_hedging_evaluator():
    prompt = "Explain how quicksort works in computer science"
    good_resp = "Quicksort is an efficient divide-and-conquer sorting algorithm that selects a pivot element and partitions the array."
    hedged_resp = "I am not sure, but maybe quicksort is a sorting algorithm, though it might be incorrect."
    
    sem_score, sem_critiques = AnswerEvaluator.evaluate_semantic(prompt, good_resp, task_type="coding")
    assert sem_score >= 0.90

    hed_score_good, _ = AnswerEvaluator.evaluate_hedging(good_resp)
    assert hed_score_good == 1.0

    hed_score_bad, hed_critiques = AnswerEvaluator.evaluate_hedging(hedged_resp)
    assert hed_score_bad <= 0.40
    assert len(hed_critiques) >= 1

def test_factuality_evaluator_rag_grounding():
    sources = [
        {
            "document_name": "pricing_v2.pdf",
            "chunk_index": 1,
            "similarity_score": 0.88,
            "text_snippet": "Tier 1 commodity pricing is set at $0.05 per million tokens, while Frontier models cost $2.50 per million tokens."
        }
    ]
    
    grounded_resp = "According to the pricing specifications, Tier 1 pricing is $0.05 per million tokens and Frontier models cost $2.50 per million tokens."
    ungrounded_resp = "Elephants are large mammals native to Africa and Asia."

    fac_ok, _ = AnswerEvaluator.evaluate_factuality(grounded_resp, sources)
    assert fac_ok >= 0.80

    fac_bad, fac_critiques = AnswerEvaluator.evaluate_factuality(ungrounded_resp, sources)
    assert fac_bad <= 0.50
    assert len(fac_critiques) > 0

def test_domain_confidence_calibration():
    # Coding domain weights syntactic heavily (50%)
    coding_weights = ConfidenceCalibrationService.get_domain_weights("coding")
    assert coding_weights["syntactic"] == 0.50

    raw_scores_bad_syntax = {
        "syntactic": 0.10,
        "semantic": 1.0,
        "hedging": 1.0,
        "factuality": 1.0
    }
    # In coding, bad syntax triggers hard cap
    calibrated_coding = ConfidenceCalibrationService.calibrate_score(raw_scores_bad_syntax, domain="coding")
    assert calibrated_coding <= 0.20

    # In general Q&A, bad syntax has much lower impact
    calibrated_general = ConfidenceCalibrationService.calibrate_score(raw_scores_bad_syntax, domain="general")
    assert calibrated_general >= 0.70

def test_dynamic_threshold_calibration():
    base_thresh = 0.70
    # High complexity raises threshold
    thresh_high_comp = ConfidenceCalibrationService.calibrate_threshold(base_thresh, complexity_score=9, budget_pressure=20)
    assert thresh_high_comp >= base_thresh

    # High budget pressure lowers threshold to prevent expensive escalation
    thresh_budget_press = ConfidenceCalibrationService.calibrate_threshold(base_thresh, complexity_score=5, budget_pressure=90)
    assert thresh_budget_press <= base_thresh

@pytest.mark.asyncio
async def test_smart_escalation_with_critique():
    router = RouterEngine(mock_mode=True)
    # Require JSON output: Tier 1 cheap agent generates malformed JSON, which forces escalation
    res = await router.route(
        prompt="Output configuration JSON",
        domain="general",
        expected_format="json"
    )
    
    assert res["final_tier"] > 1
    assert "routing_path" in res["usage"]
    assert len(res["usage"]["routing_path"]) > 1
    
    first_step = res["usage"]["routing_path"][0]
    assert first_step["tier"] == 1
    assert first_step["confidence_score"] <= 0.20
    assert first_step["evaluation"]["verdict"] == "ESCALATE"
    assert first_step["evaluation"]["critique"] is not None
    assert "json" in first_step["evaluation"]["critique"].lower()

def test_evaluator_api_endpoints():
    # 1. POST /api/v1/evaluator/evaluate
    resp = client.post("/api/v1/evaluator/evaluate", json={
        "prompt": "Write a python function to compute factorial",
        "response_text": "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
        "expected_format": "python",
        "domain": "coding",
        "task_type": "coding",
        "threshold": 0.75
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_score"] >= 0.85
    assert data["verdict"] == "ACCEPTED"
    assert data["sub_scores"]["syntactic"] == 1.0

    # 2. GET /api/v1/evaluator/calibration
    cal_resp = client.get("/api/v1/evaluator/calibration")
    assert cal_resp.status_code == 200
    all_weights = cal_resp.json()["domain_weights"]
    assert "coding" in all_weights
    assert "rag" in all_weights

    # 3. PUT /api/v1/evaluator/calibration
    put_resp = client.put("/api/v1/evaluator/calibration", json={
        "domain": "coding",
        "weights": {
            "syntactic": 0.60,
            "semantic": 0.20,
            "hedging": 0.10,
            "factuality": 0.10
        }
    })
    assert put_resp.status_code == 200
    assert put_resp.json()["status"] == "success"
    # Reset back
    ConfidenceCalibrationService.reset_defaults()
