"""
confidence_calibration.py
=========================
Dynamic confidence calibration module for CAAR 2.0.

Provides domain-adaptive weighting matrices and calibrated probability scoring
to account for varying quality criteria across domains (e.g. coding vs RAG vs general Q&A).
"""

from typing import Dict, Any, Optional

DEFAULT_DOMAIN_WEIGHTS: Dict[str, Dict[str, float]] = {
    "coding": {
        "syntactic": 0.50,
        "semantic": 0.25,
        "hedging": 0.15,
        "factuality": 0.10,
    },
    "math": {
        "syntactic": 0.45,
        "semantic": 0.35,
        "hedging": 0.20,
        "factuality": 0.00,
    },
    "rag": {
        "factuality": 0.40,
        "semantic": 0.30,
        "hedging": 0.20,
        "syntactic": 0.10,
    },
    "research": {
        "factuality": 0.35,
        "semantic": 0.35,
        "hedging": 0.20,
        "syntactic": 0.10,
    },
    "analysis": {
        "syntactic": 0.40,
        "semantic": 0.30,
        "factuality": 0.20,
        "hedging": 0.10,
    },
    "general": {
        "semantic": 0.40,
        "hedging": 0.40,
        "syntactic": 0.20,
        "factuality": 0.00,
    },
}

class ConfidenceCalibrationService:
    _weights: Dict[str, Dict[str, float]] = {k: dict(v) for k, v in DEFAULT_DOMAIN_WEIGHTS.items()}

    @classmethod
    def get_domain_weights(cls, domain: str = "general") -> Dict[str, float]:
        norm_domain = domain.lower()
        if norm_domain in cls._weights:
            return dict(cls._weights[norm_domain])
        return dict(cls._weights.get("general", DEFAULT_DOMAIN_WEIGHTS["general"]))

    @classmethod
    def get_all_weights(cls) -> Dict[str, Dict[str, float]]:
        return {k: dict(v) for k, v in cls._weights.items()}

    @classmethod
    def update_domain_weights(cls, domain: str, weights: Dict[str, float]) -> Dict[str, float]:
        norm_domain = domain.lower()
        total = sum(weights.values())
        if total <= 0:
            raise ValueError("Weight sum must be greater than zero.")
        # Normalize weights so they sum to 1.0
        normalized = {k: round(v / total, 4) for k, v in weights.items()}
        cls._weights[norm_domain] = normalized
        return normalized

    @classmethod
    def reset_defaults(cls):
        cls._weights = {k: dict(v) for k, v in DEFAULT_DOMAIN_WEIGHTS.items()}

    @classmethod
    def calibrate_score(
        cls,
        raw_scores: Dict[str, float],
        domain: str = "general",
        expected_format: Optional[str] = None
    ) -> float:
        """
        Combines sub-scores according to domain calibration weights.
        Applies non-linear penalties if a crucial domain dimension is critically low.
        """
        weights = cls.get_domain_weights(domain)
        
        # Hard penalty rule: In coding or math, OR when an explicit format is required (e.g. json, python),
        # if syntactic check fails (score <= 0.2), cap score heavily
        if (domain in ("coding", "math") or expected_format in ("json", "python")) and raw_scores.get("syntactic", 1.0) <= 0.2:
            return round(raw_scores.get("syntactic", 0.0), 2)

        composite = 0.0
        applied_weight_sum = 0.0

        for dimension, weight in weights.items():
            if dimension in raw_scores and raw_scores[dimension] is not None:
                composite += weight * raw_scores[dimension]
                applied_weight_sum += weight

        if applied_weight_sum > 0:
            composite = composite / applied_weight_sum
        else:
            composite = 0.5

        # Severe uncertainty rule: If hedging score is critically low,
        # cap composite score to reflect genuine model hesitation
        if raw_scores.get("hedging", 1.0) <= 0.20:
            composite = min(composite, 0.45)
        elif raw_scores.get("hedging", 1.0) <= 0.40:
            composite = min(composite, 0.60)

        # Platt-style smoothing to prevent overconfident clustering around 0.5
        calibrated = min(max(composite, 0.0), 1.0)
        return round(calibrated, 2)

    @classmethod
    def calibrate_threshold(
        cls,
        base_threshold: float,
        complexity_score: int = 5,
        budget_pressure: int = 0
    ) -> float:
        """
        Calibrates the threshold dynamically based on query complexity and budget pressure.
        - Higher complexity slightly raises standard for lower tiers to ensure safety.
        - High budget pressure slightly relaxes threshold to prevent unnecessary expensive escalations.
        """
        threshold = base_threshold
        
        # If budget pressure is high (>= 75), lower threshold slightly to avoid escalation
        if budget_pressure >= 85:
            threshold -= 0.10
        elif budget_pressure >= 70:
            threshold -= 0.05
            
        # If complexity is very high (>= 8) and budget allows, tighten threshold slightly
        if complexity_score >= 8 and budget_pressure < 50:
            threshold += 0.05
            
        # Bound between 0.30 and 0.95
        return round(min(max(threshold, 0.30), 0.95), 2)
