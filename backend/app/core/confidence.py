import re
import json
import litellm
from typing import Dict, Any, Optional

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

class ConfidenceEvaluator:
    @staticmethod
    def evaluate_syntactic(response_text: str, expected_format: Optional[str] = None) -> float:
        """
        Evaluates structural formatting validity.
        Returns a score between 0.0 and 1.0.
        """
        if not response_text or not response_text.strip():
            return 0.0
            
        score = 1.0
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
                # Try parsing raw json
                json.loads(response_stripped)
                score = 1.0
            except json.JSONDecodeError:
                # Try finding json block inside markdown ```json ... ```
                json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
                if json_block_match:
                    try:
                        json.loads(json_block_match.group(1).strip())
                        score = 0.9  # slight penalty for requiring extraction
                    except json.JSONDecodeError:
                        # JSON malformed in markdown block
                        score = 0.1
                else:
                    # No JSON block found; if JSON expected, set score to 0.0 to force escalation
                    if expected_format == "json":
                        score = 0.0
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
            except SyntaxError:
                score = min(score, 0.2)
                    
        return score

    @staticmethod
    def evaluate_semantic_hedging(response_text: str) -> float:
        """
        Scans for expressions indicating uncertainty, lack of confidence or apologies.
        Returns a modifier score between 0.0 (high uncertainty) and 1.0 (no uncertainty).
        """
        text_lower = response_text.lower()
        matches = 0
        
        for keyword in HEDGING_KEYWORDS:
            if re.search(keyword, text_lower):
                matches += 1
                
        if matches == 0:
            return 1.0
        elif matches == 1:
            return 0.70
        elif matches == 2:
            return 0.40
        else:
            return 0.10

    @staticmethod
    async def evaluate_llm_judge(prompt: str, response_text: str, judge_model: str = "gpt-4o-mini") -> float:
        """
        Calls a cheap LLM judge to evaluate response accuracy and alignment with the prompt.
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
            # Asynchronous call to judge
            res = await litellm.acompletion(
                model=judge_model,
                messages=[{"role": "user", "content": judge_prompt}],
                max_tokens=5,
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
        judge_model: str = "gpt-4o-mini"
    ) -> float:
        """
        Aggregates multiple confidence models to return a final composite confidence score.
        """
        syntactic_score = cls.evaluate_syntactic(response_text, expected_format)
        hedging_score = cls.evaluate_semantic_hedging(response_text)
        
        # If response fails syntactic rules, penalize heavily
        if syntactic_score <= 0.2:
            return syntactic_score
            
        base_confidence = (0.4 * syntactic_score) + (0.6 * hedging_score)
        
        if use_judge:
            judge_score = await cls.evaluate_llm_judge(prompt, response_text, judge_model)
            # 50% heuristic-based, 50% LLM-judge based
            final_confidence = (0.5 * base_confidence) + (0.5 * judge_score)
        else:
            final_confidence = base_confidence
            
        return round(final_confidence, 2)
