import re
import json
import litellm
from typing import Dict, Any, Optional

from backend.app.core.answer_evaluator import AnswerEvaluator, HEDGING_KEYWORDS

from backend.app.utils.llm_client import _push_keys, format_model_name

class ConfidenceEvaluator:
    @staticmethod
    def evaluate_syntactic(response_text: str, expected_format: Optional[str] = None) -> float:
        """
        Evaluates structural formatting validity.
        Returns a score between 0.0 and 1.0.
        Preserves 100% backward compatibility with existing tests.
        """
        score, _ = AnswerEvaluator.evaluate_syntactic(response_text, expected_format)
        return score

    @staticmethod
    def evaluate_semantic_hedging(response_text: str) -> float:
        """
        Scans for expressions indicating uncertainty, lack of confidence or apologies.
        Returns a modifier score between 0.0 (high uncertainty) and 1.0 (no uncertainty).
        """
        score, _ = AnswerEvaluator.evaluate_hedging(response_text)
        return score

    @staticmethod
    async def evaluate_llm_judge(prompt: str, response_text: str, judge_model: str = "groq/openai/gpt-oss-20b") -> float:
        """
        Calls an LLM judge to evaluate response accuracy and alignment with the prompt.
        Runs asynchronously. Returns a confidence score between 0.0 and 1.0.
        """
        judge_prompt = f"""
You are an expert critic evaluating a model's response to a user prompt.
Evaluate if the response completely, accurately, and confidently answers the prompt.
Provide your assessment as a single float between 0.0 and 1.0, where:
- 1.0: Perfect, correct, authoritative, free of errors or hedging.
- 0.8: Mostly correct, but has minor styling or verbose issues.
- 0.5: Helpful but contains uncertainty, warnings, or missing details.
- 0.2: Partially incorrect or severely hesitant.
- 0.0: Fully wrong, hallucinatory, or empty.

Respond with ONLY the float number (e.g. 0.85). Do not write any other text.

---
USER PROMPT:
{prompt}

---
MODEL RESPONSE:
{response_text}
"""
        try:
            _push_keys()
            target_model = format_model_name(judge_model)
            res = await litellm.acompletion(
                model=target_model,
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=25,
                temperature=0.0
            )
            val_text = res.choices[0].message.content.strip()
            score_match = re.search(r"(\d+(\.\d+)?)", val_text)
            if score_match:
                return min(max(float(score_match.group(1)), 0.0), 1.0)
            return 0.5
        except Exception:
            return 0.5 # fallback on API error

    @classmethod
    async def calculate_confidence(
        cls,
        prompt: str,
        response_text: str,
        expected_format: Optional[str] = None,
        use_judge: bool = False,
        judge_model: str = "groq/openai/gpt-oss-20b",
        domain: str = "general"
    ) -> float:
        """
        Aggregates multiple confidence models using calibrated domain weights.
        Returns final composite confidence score.
        """
        syntactic_score = cls.evaluate_syntactic(response_text, expected_format)
        hedging_score = cls.evaluate_semantic_hedging(response_text)
        
        # If response fails syntactic rules, penalize heavily
        if syntactic_score <= 0.2:
            return syntactic_score
            
        base_confidence = (0.4 * syntactic_score) + (0.6 * hedging_score)
        
        if use_judge:
            judge_score = await cls.evaluate_llm_judge(prompt, response_text, judge_model)
            final_confidence = (0.5 * base_confidence) + (0.5 * judge_score)
        else:
            final_confidence = base_confidence
            
        return round(final_confidence, 2)
