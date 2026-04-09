from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class LeadMagnetDraft:
    topic: str
    publish_date: str
    headline: str
    hook: str
    lead_magnet_title: str
    lead_magnet_type: str
    lead_magnet_summary: str
    lead_magnet_outline: list[str]
    cta: str
    linkedin_post: str
    variant_tag: str
    experiment_id: str
    post_url: str = ""
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LeadMagnetDraft":
        return cls(
            topic=str(payload.get("topic", "")),
            publish_date=str(payload.get("publish_date", "")),
            headline=str(payload.get("headline", "")),
            hook=str(payload.get("hook", "")),
            lead_magnet_title=str(payload.get("lead_magnet_title", "")),
            lead_magnet_type=str(payload.get("lead_magnet_type", "")),
            lead_magnet_summary=str(payload.get("lead_magnet_summary", "")),
            lead_magnet_outline=[str(x) for x in payload.get("lead_magnet_outline", [])],
            cta=str(payload.get("cta", "")),
            linkedin_post=str(payload.get("linkedin_post", "")),
            variant_tag=str(payload.get("variant_tag", "A")),
            experiment_id=str(payload.get("experiment_id", "")),
            post_url=str(payload.get("post_url", "")),
            notes=str(payload.get("notes", "")),
            created_at=str(payload.get("created_at", datetime.utcnow().isoformat(timespec="seconds") + "Z")),
        )


@dataclass
class PerformanceMetrics:
    impressions: int = 0
    reactions: int = 0
    comments: int = 0
    reposts: int = 0
    saves: int = 0
    clicks: int = 0
    engagement_score: float = 0.0
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchInsight:
    generated_at: str
    analyzed_records: int
    winning_patterns: list[str]
    losing_patterns: list[str]
    next_prompt_instructions: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
