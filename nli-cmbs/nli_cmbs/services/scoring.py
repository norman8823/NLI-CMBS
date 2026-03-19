"""Scoring functions for evaluating AI extraction accuracy against ground truth.

This module defines the interface: score(extraction, ground_truth) -> result.
The initial implementation handles Tier 1 (exact match on numeric/text fields).
Tier 2 and Tier 3 scoring will be added post-hackathon.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass
class FieldScore:
    """Score for a single field extraction."""
    field_name: str
    ground_truth: str
    extracted: str | None
    match: bool
    error: float | None  # For numeric fields: absolute percentage error. None for text/missing.
    tier: int


@dataclass
class ExtractionScorecard:
    """Aggregate scores for one model run against one filing."""
    total_fields: int
    matched_fields: int
    missing_fields: int
    accuracy: float
    tier_1_accuracy: float | None
    tier_2_accuracy: float | None
    mean_absolute_error: float | None
    field_scores: list[FieldScore]


def score_numeric_field(
    ground_truth: str, extracted: str | None, tolerance: float = 0.001,
) -> tuple[bool, float | None]:
    """Score a numeric field extraction.

    Returns (match, error) where error is relative absolute error.
    """
    if extracted is None:
        return False, None

    try:
        gt = Decimal(ground_truth)
        ex = Decimal(extracted)
    except (InvalidOperation, ValueError):
        return False, None

    if gt == 0:
        return ex == 0, float(abs(ex)) if ex != 0 else 0.0

    error = float(abs(ex - gt) / abs(gt))
    return error <= tolerance, error


def score_text_field(ground_truth: str, extracted: str | None) -> tuple[bool, None]:
    """Score a text field extraction (exact match after normalization)."""
    if extracted is None:
        return False, None
    return ground_truth.strip().lower() == extracted.strip().lower(), None


def score_extraction(
    ground_truth_entries: list[dict],
    extracted_values: dict[str, str | None],
) -> ExtractionScorecard:
    """Score a complete extraction against ground truth entries.

    Args:
        ground_truth_entries: List of dicts with field_name, field_value, field_type, tier
        extracted_values: Dict mapping field_name to the model's extracted value

    Returns:
        ExtractionScorecard with per-field and aggregate scores
    """
    field_scores: list[FieldScore] = []
    errors: list[float] = []
    tier_results: dict[int, list[bool]] = {1: [], 2: [], 3: []}

    for entry in ground_truth_entries:
        fname = entry["field_name"]
        gt_value = entry["field_value"]
        ftype = entry["field_type"]
        tier = entry.get("tier", 1)
        extracted = extracted_values.get(fname)

        if ftype == "numeric":
            match, error = score_numeric_field(gt_value, extracted)
            if error is not None:
                errors.append(error)
        else:
            match, error = score_text_field(gt_value, extracted)

        field_scores.append(FieldScore(
            field_name=fname,
            ground_truth=gt_value,
            extracted=extracted,
            match=match,
            error=error,
            tier=tier,
        ))

        if tier in tier_results:
            tier_results[tier].append(match)

    total = len(field_scores)
    matched = sum(1 for fs in field_scores if fs.match)
    missing = sum(1 for fs in field_scores if fs.extracted is None)

    def _tier_acc(tier: int) -> float | None:
        results = tier_results.get(tier, [])
        return sum(results) / len(results) if results else None

    return ExtractionScorecard(
        total_fields=total,
        matched_fields=matched,
        missing_fields=missing,
        accuracy=matched / total if total > 0 else 0.0,
        tier_1_accuracy=_tier_acc(1),
        tier_2_accuracy=_tier_acc(2),
        mean_absolute_error=sum(errors) / len(errors) if errors else None,
        field_scores=field_scores,
    )
