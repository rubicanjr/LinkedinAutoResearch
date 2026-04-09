from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from .models import ResearchInsight
from .utils import utc_timestamp


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(round(mean(values), 2))


def _quartiles(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not records:
        return [], []
    ordered = sorted(records, key=lambda x: float(x.get("engagement_score", 0.0)))
    k = max(1, len(ordered) // 3)
    bottom = ordered[:k]
    top = ordered[-k:]
    return top, bottom


def _pattern_summary(records: list[dict[str, Any]]) -> dict[str, float]:
    by_type: dict[str, list[float]] = defaultdict(list)
    for r in records:
        magnet_type = str(r.get("lead_magnet_type") or "Unknown")
        by_type[magnet_type].append(float(r.get("engagement_score", 0.0)))
    return {k: _safe_mean(v) for k, v in by_type.items()}


def build_research_insight(records: list[dict[str, Any]]) -> ResearchInsight:
    top, bottom = _quartiles(records)
    type_top = _pattern_summary(top)
    type_bottom = _pattern_summary(bottom)

    winning_patterns: list[str] = []
    losing_patterns: list[str] = []

    if type_top:
        best = sorted(type_top.items(), key=lambda x: x[1], reverse=True)[:3]
        winning_patterns.extend([f"Top magnet type: {name} (avg score {score})" for name, score in best])

    if type_bottom:
        worst = sorted(type_bottom.items(), key=lambda x: x[1])[:3]
        losing_patterns.extend([f"Weak magnet type: {name} (avg score {score})" for name, score in worst])

    top_hooks = [str(r.get("hook", "")) for r in top if str(r.get("hook", "")).strip()]
    bottom_hooks = [str(r.get("hook", "")) for r in bottom if str(r.get("hook", "")).strip()]
    if top_hooks:
        winning_patterns.append("Winning hooks are concrete and outcome-led.")
    if bottom_hooks:
        losing_patterns.append("Underperforming hooks are vague and non-specific.")

    next_prompt_instructions = (
        "Generate 2 concrete variants focused on measurable outcomes, "
        "use one clear CTA, and prioritize the top lead magnet type from winning patterns. "
        "Avoid generic motivational language."
    )

    return ResearchInsight(
        generated_at=utc_timestamp(),
        analyzed_records=len(records),
        winning_patterns=winning_patterns or ["Not enough data yet."],
        losing_patterns=losing_patterns or ["Not enough data yet."],
        next_prompt_instructions=next_prompt_instructions,
    )


def render_recommendation_markdown(insight: ResearchInsight) -> str:
    lines: list[str] = []
    lines.append("# Daily LinkedIn Research Recommendation")
    lines.append("")
    lines.append(f"- Generated at: `{insight.generated_at}`")
    lines.append(f"- Records analyzed: `{insight.analyzed_records}`")
    lines.append("")
    lines.append("## Winning patterns")
    for item in insight.winning_patterns:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Losing patterns")
    for item in insight.losing_patterns:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Next prompt instructions")
    lines.append(insight.next_prompt_instructions)
    lines.append("")
    return "\n".join(lines)
