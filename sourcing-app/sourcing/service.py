"""Glue between storage, Claude and deterministic scoring."""

from typing import Optional

from . import ai, db
from .scoring import (
    DEFAULT_WEIGHTS,
    donor_points,
    final_score,
    hunt_window,
    match_donor,
    tenure_months,
    weighted_criteria_score,
)


def score_parts(scorecard: dict, candidate: dict, assessment: Optional[dict]) -> dict:
    """0-100 per part. Parts without data are None and get skipped in the final score."""
    donors = scorecard.get("donor_companies", [])
    current = match_donor(candidate.get("current_company", ""), donors)
    past_tiers = []
    if assessment:
        for name in assessment.get("donor_companies_in_history", []):
            d = match_donor(name, donors)
            if d:
                past_tiers.append(d["tier"])
    parts = {
        "donor": donor_points(current, past_tiers),
        "must_have": None,
        "nice_to_have": None,
        "domain": None,
        "seniority": None,
    }
    if assessment:
        parts["must_have"] = weighted_criteria_score(assessment["must_have_scores"], scorecard.get("must_have", []))
        parts["nice_to_have"] = weighted_criteria_score(assessment["nice_to_have_scores"], scorecard.get("nice_to_have", []))
        parts["domain"] = min(10, max(0, assessment["domain_fit"])) * 10
        parts["seniority"] = min(10, max(0, assessment["seniority_fit"])) * 10
    return {"parts": parts, "current_donor": current}


def score_candidate(conn, vacancy: dict, candidate_id: int, use_ai: bool = True) -> int:
    candidate = db.get_candidate(conn, candidate_id)
    assessment = ai.assess_candidate(vacancy["scorecard"], candidate) if use_ai else None
    result = score_parts(vacancy["scorecard"], candidate, assessment)
    score = final_score(result["parts"], vacancy.get("weights") or DEFAULT_WEIGHTS)
    fields = {"score": score}
    if assessment:
        assessment["parts"] = result["parts"]
        fields["assessment"] = assessment
    db.update_pipeline(conn, vacancy["id"], candidate_id, **fields)
    return score


def enrich_row(row: dict, scorecard: Optional[dict]) -> dict:
    """Add tenure, hunt badge and donor tier for display."""
    months = tenure_months(row.get("start_date", ""), row.get("tenure_text", ""))
    badge, hint = hunt_window(months)
    donor = match_donor(row.get("current_company", ""), (scorecard or {}).get("donor_companies", []))
    return {
        **row,
        "tenure_months": months,
        "hunt_badge": badge,
        "hunt_hint": hint,
        "donor_tier": f"T{donor['tier']}" if donor else "",
    }
