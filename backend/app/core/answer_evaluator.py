"""
answer_evaluator.py
===================
Comprehensive multi-metric answer evaluation engine for CAAR 2.0.

Evaluates candidate responses across:
1. Syntactic validity (JSON, Python AST, schema adherence)
2. Semantic completeness & prompt intent fulfillment
3. Hedging & uncertainty detection
4. Factuality & context grounding (RAG citations & context overlap)
5. LLM-as-Judge qualitative assessment (optional)

Produces structured sub-scores, calibrated confidence, verdict (ACCEPTED/ESCALATE),
and actionable escalation critiques for cascading tiers.
"""

import re
import json
from typing import Dict, Any, Optional, List, Tuple

from backend.app.core.confidence_calibration import ConfidenceCalibrationService

HEDGING_KEYWORDS = [
    r"i'm not sure",
    r"i cannot confirm",
    r"i do not have access",
    r"as an ai",
    r"i apologize",
    r"unable to verify",
    r"may be outdated",
    r"please verify",
    r"it is difficult to say",
    r"i am not qualified",
    r"cannot guarantee",
    r"not fully certain",
    r"probably",
    r"maybe",
    r"not sure",
    r"uncertain",
    r"unsure",
    r"might be incorrect",
    r"could be incorrect",
]

class AnswerEvaluator:
    @staticmethod
    def evaluate_syntactic(
        response_text: str,
        expected_format: Optional[str] = None
    ) -> Tuple[float, List[str]]:
        """
        Evaluates structural formatting and syntax validity.
        Returns (score, list_of_critiques).
        """
        if not response_text or not response_text.strip():
            return 0.0, ["Response is empty."]
            
        score = 1.0
        critiques = []
        response_stripped = response_text.strip()
        
        # 1. JSON formatting verification
        is_trying_to_be_json = (
            expected_format == "json" or 
            response_stripped.startswith("{") or 
            response_stripped.startswith("[") or 
            "```json" in response_text
        )
        
        if is_trying_to_be_json:
            try:
                json.loads(response_stripped)
                score = 1.0
            except json.JSONDecodeError:
                json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_block_match:
                    try:
                        json.loads(json_block_match.group(1).strip())
                        score = 0.9
                    except json.JSONDecodeError:
                        score = 0.1
                        critiques.append("Malformed JSON syntax in markdown code block.")
                else:
                    if expected_format == "json":
                        score = 0.0
                        critiques.append("Expected valid JSON but could not parse response as JSON.")
                    else:
                        score = 0.7
                        
        # 2. Python Code formatting verification
        is_trying_to_be_python = (
            expected_format == "python" or 
            "def " in response_text or 
            "```python" in response_text
        )
        
        if is_trying_to_be_python:
            code_block_match = re.search(r"```python\s*(.*?)\s*```", response_text, re.DOTALL)
            code_to_check = code_block_match.group(1) if code_block_match else response_text
            try:
                compile(code_to_check, "<string>", "exec")
                score = min(score, 1.0)
            except SyntaxError as e:
                score = min(score, 0.2)
                critiques.append(f"Python syntax compilation error: {e.msg} at line {e.lineno}")
                
        return score, critiques

    @staticmethod
    def evaluate_semantic(
        prompt: str,
        response_text: str,
        task_type: str = "general"
    ) -> Tuple[float, List[str]]:
        """
        Evaluates semantic depth, completeness, and prompt intent fulfillment.
        Returns (score, list_of_critiques).
        """
        critiques = []
        if not response_text or len(response_text.strip()) < 5:
            return 0.1, ["Response is severely brief or uninformative."]
            
        score = 1.0
        resp_lower = response_text.lower()
        prompt_lower = prompt.lower()
        
        # Check for evasive phrases
        evasive_phrases = ["i don't know", "i cannot answer", "no idea", "unable to assist"]
        for phrase in evasive_phrases:
            if phrase in resp_lower and len(response_text.strip().split()) < 20:
                return 0.2, [f"Response appears evasive or unhelpful ('{phrase}')."]

        # Check prompt token overlap for topical alignment
        prompt_words = [w for w in re.findall(r"\b[a-zA-Z]{3,}\b", prompt_lower) if w not in ("what", "when", "where", "which", "how", "why", "the", "and", "for")]
        if prompt_words:
            matched_words = [w for w in prompt_words if w in resp_lower]
            overlap_ratio = len(matched_words) / len(prompt_words)
            if overlap_ratio < 0.15:
                score = min(score, 0.6)
                critiques.append("Response lacks key topical concepts from the original prompt.")

        # Length / completeness expectations by task type
        word_count = len(response_text.strip().split())
        if task_type in ("coding", "research") and word_count < 15:
            score = min(score, 0.5)
            critiques.append(f"Response too brief for complex {task_type} task ({word_count} words).")
            
        return score, critiques

    @staticmethod
    def evaluate_hedging(response_text: str) -> Tuple[float, List[str]]:
        """
        Scans for expressions of uncertainty, lack of confidence, or apologies.
        Returns (score, list_of_critiques).
        """
        text_lower = response_text.lower()
        detected_hedges = []
        
        for keyword in HEDGING_KEYWORDS:
            if re.search(keyword, text_lower):
                detected_hedges.append(keyword.replace(r"\b", "").strip())
                
        matches = len(detected_hedges)
        if matches == 0:
            return 1.0, []
        elif matches == 1:
            return 0.70, [f"Hedging language detected: '{detected_hedges[0]}'"]
        elif matches == 2:
            return 0.40, [f"Multiple hedging phrases detected: {', '.join(detected_hedges[:2])}"]
        else:
            return 0.10, [f"High level of uncertainty detected: {', '.join(detected_hedges[:3])}"]

    @staticmethod
    def evaluate_factuality(
        response_text: str,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[float, List[str]]:
        """
        Evaluates grounding and citation consistency when RAG context or sources exist.
        Returns (score, list_of_critiques).
        """
        if not sources:
            # If no RAG sources were expected/used, neutral 1.0
            return 1.0, []

        critiques = []
        resp_lower = response_text.lower()
        
        # Check if response references knowledge base facts
        source_texts = " ".join([s.get("text_snippet", "").lower() for s in sources])
        source_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", source_texts))
        
        if not source_words:
            return 0.8, []
            
        resp_words = set(re.findall(r"\b[a-zA-Z]{4,}\b", resp_lower))
        overlap = source_words.intersection(resp_words)
        overlap_ratio = len(overlap) / min(len(source_words), 20)
        
        if overlap_ratio >= 0.40:
            score = 1.0
        elif overlap_ratio >= 0.20:
            score = 0.80
        else:
            score = 0.45
            critiques.append("Response has low factual overlap with the retrieved knowledge base sources.")
            
        return score, critiques

    @classmethod
    def synthesize_critique(
        cls,
        critiques: List[str],
        sub_scores: Dict[str, float],
        expected_format: Optional[str] = None
    ) -> str:
        """
        Synthesizes actionable, constructive feedback for escalating to the next tier agent.
        """
        if not critiques and all(s >= 0.7 for s in sub_scores.values()):
            return "Higher reasoning and verification requested to satisfy high confidence threshold."
            
        feedback_lines = []
        if sub_scores.get("syntactic", 1.0) <= 0.2:
            if expected_format == "json":
                feedback_lines.append("CRITICAL: The previous attempt generated invalid JSON. Ensure the output is strictly valid JSON parsable by json.loads().")
            elif expected_format == "python":
                feedback_lines.append("CRITICAL: The previous attempt contained Python syntax errors. Verify all syntax, indentation, and function definitions.")
            else:
                feedback_lines.append("CRITICAL: Syntax or structural requirements were not met.")
                
        if sub_scores.get("hedging", 1.0) <= 0.5:
            feedback_lines.append("The previous model exhibited severe hedging and uncertainty. Provide a clear, authoritative, and direct answer.")
            
        if sub_scores.get("semantic", 1.0) <= 0.5:
            feedback_lines.append("The previous response was insufficient or missed key aspects of the prompt. Provide a thorough, complete response.")

        if sub_scores.get("factuality", 1.0) <= 0.5:
            feedback_lines.append("Ensure the answer is strictly grounded in the provided reference context and documents.")

        for c in critiques:
            if c not in feedback_lines:
                feedback_lines.append(c)

        return " | ".join(feedback_lines[:3])

    @classmethod
    async def evaluate(
        cls,
        prompt: str,
        response_text: str,
        expected_format: Optional[str] = None,
        domain: str = "general",
        task_type: str = "general",
        sources: Optional[List[Dict[str, Any]]] = None,
        threshold: float = 0.70,
        use_judge: bool = False
    ) -> Dict[str, Any]:
        """
        Executes multi-metric evaluation, calculates calibrated confidence,
        and determines whether the candidate generation is ACCEPTED or requires ESCALATION.
        """
        syntactic_score, syn_critiques = cls.evaluate_syntactic(response_text, expected_format)
        semantic_score, sem_critiques = cls.evaluate_semantic(prompt, response_text, task_type)
        hedging_score, hed_critiques = cls.evaluate_hedging(response_text)
        factuality_score, fac_critiques = cls.evaluate_factuality(response_text, sources)
        
        all_critiques = syn_critiques + sem_critiques + hed_critiques + fac_critiques
        
        raw_scores = {
            "syntactic": syntactic_score,
            "semantic": semantic_score,
            "hedging": hedging_score,
            "factuality": factuality_score,
        }
        
        calibrated_score = ConfidenceCalibrationService.calibrate_score(
            raw_scores,
            domain=domain,
            expected_format=expected_format
        )
        
        # Verdict: ACCEPTED if calibrated_score >= threshold, else ESCALATE
        verdict = "ACCEPTED" if calibrated_score >= threshold else "ESCALATE"
        
        critique_for_escalation = None
        if verdict == "ESCALATE":
            critique_for_escalation = cls.synthesize_critique(all_critiques, raw_scores, expected_format)
            
        return {
            "overall_score": calibrated_score,
            "sub_scores": raw_scores,
            "verdict": verdict,
            "feedback_reasons": all_critiques,
            "critique_for_escalation": critique_for_escalation,
            "calibrated_threshold": threshold,
            "domain": domain,
        }
