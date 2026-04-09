from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlencode

import requests

from .models import PerformanceMetrics


class ApifyError(RuntimeError):
    pass


def _to_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def compute_engagement_score(metrics: PerformanceMetrics) -> float:
    weighted = (
        metrics.reactions
        + (2 * metrics.comments)
        + (3 * metrics.reposts)
        + (2 * metrics.saves)
        + (2 * metrics.clicks)
    )
    if metrics.impressions <= 0:
        return float(weighted)
    return round((weighted / metrics.impressions) * 1000, 2)


@dataclass
class ApifyClient:
    token: str
    base_url: str = "https://api.apify.com/v2"

    def run_actor_sync_items(
        self,
        actor_id: str,
        actor_input: dict[str, Any],
        query_options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self.token:
            raise ApifyError("APIFY_TOKEN is missing.")
        if not actor_id:
            raise ApifyError("APIFY_ACTOR_ID is missing.")

        params: dict[str, Any] = {"token": self.token}
        if query_options:
            for key, value in query_options.items():
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                params[key] = value

        encoded_actor_id = quote(actor_id, safe="~")
        query = urlencode(params, doseq=True)
        url = f"{self.base_url}/acts/{encoded_actor_id}/run-sync-get-dataset-items?{query}"

        timeout_seconds = int(params.get("timeout", 280))
        request_timeout = max(120, timeout_seconds + 30)
        resp = requests.post(url, json=actor_input, timeout=request_timeout)
        if resp.status_code == 408:
            raise ApifyError(
                "Apify run-sync endpoint timed out (HTTP 408). "
                "Lower the `timeout`/`limit` values or switch to async run endpoint."
            )
        if not resp.ok:
            raise ApifyError(f"Apify API error {resp.status_code}: {resp.text}")
        payload = resp.json()
        if isinstance(payload, list):
            return payload
        return list(payload.get("items", []))

    @staticmethod
    def normalize_metrics(item: dict[str, Any]) -> tuple[str, PerformanceMetrics]:
        post_url = str(item.get("postUrl") or item.get("url") or item.get("post_url") or "").strip()
        metrics = PerformanceMetrics(
            impressions=_to_int(item.get("impressions") or item.get("views")),
            reactions=_to_int(item.get("reactions") or item.get("likes")),
            comments=_to_int(item.get("comments")),
            reposts=_to_int(item.get("shares") or item.get("reposts")),
            saves=_to_int(item.get("saves")),
            clicks=_to_int(item.get("clicks") or item.get("linkClicks")),
            source="apify",
        )
        metrics.engagement_score = compute_engagement_score(metrics)
        return post_url, metrics
