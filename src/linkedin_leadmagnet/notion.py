from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests

from .models import LeadMagnetDraft, PerformanceMetrics


class NotionError(RuntimeError):
    pass


@dataclass
class NotionClient:
    token: str
    notion_version: str = "2022-06-28"
    base_url: str = "https://api.notion.com/v1"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.token:
            raise NotionError("NOTION_TOKEN is missing.")
        resp = requests.request(
            method=method,
            url=f"{self.base_url}{path}",
            headers=self._headers(),
            json=payload,
            timeout=60,
        )
        if not resp.ok:
            raise NotionError(f"Notion API error {resp.status_code}: {resp.text}")
        return resp.json()

    @staticmethod
    def _rich_text(value: str) -> list[dict[str, Any]]:
        text = value.strip()
        if not text:
            return []
        chunks = [text[i : i + 1900] for i in range(0, len(text), 1900)]
        return [{"type": "text", "text": {"content": chunk}} for chunk in chunks]

    def create_database(self, parent_page_id: str, title: str) -> str:
        if not parent_page_id:
            raise NotionError("NOTION_PARENT_PAGE_ID is missing.")
        payload = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": {
                "Name": {"title": {}},
                "Status": {"select": {"options": [{"name": "Draft"}, {"name": "Scheduled"}, {"name": "Published"}]}},
                "Publish Date": {"date": {}},
                "Topic": {"rich_text": {}},
                "Lead Magnet Type": {"select": {"options": [{"name": "Checklist"}, {"name": "Guide"}, {"name": "Template"}, {"name": "Calculator"}, {"name": "Other"}]}},
                "Lead Magnet CTA": {"rich_text": {}},
                "Hook": {"rich_text": {}},
                "LinkedIn Post": {"rich_text": {}},
                "Lead Magnet Body": {"rich_text": {}},
                "Post URL": {"url": {}},
                "Impressions": {"number": {"format": "number"}},
                "Reactions": {"number": {"format": "number"}},
                "Comments": {"number": {"format": "number"}},
                "Shares": {"number": {"format": "number"}},
                "Saves": {"number": {"format": "number"}},
                "Clicks": {"number": {"format": "number"}},
                "Engagement Score": {"number": {"format": "number"}},
                "Experiment ID": {"rich_text": {}},
                "Variant Tag": {"rich_text": {}},
                "Notes": {"rich_text": {}},
            },
        }
        db = self._request("POST", "/databases", payload)
        return str(db["id"])

    def create_draft_page(self, database_id: str, draft: LeadMagnetDraft) -> str:
        if not database_id:
            raise NotionError("NOTION_DATABASE_ID is missing.")

        outline_text = "\n".join(f"- {line}" for line in draft.lead_magnet_outline)
        body = f"{draft.lead_magnet_summary}\n\n{outline_text}".strip()

        payload = {
            "parent": {"database_id": database_id},
            "properties": {
                "Name": {"title": [{"type": "text", "text": {"content": draft.headline[:120]}}]},
                "Status": {"select": {"name": "Draft"}},
                "Publish Date": {"date": {"start": draft.publish_date}},
                "Topic": {"rich_text": self._rich_text(draft.topic)},
                "Lead Magnet Type": {"select": {"name": draft.lead_magnet_type if draft.lead_magnet_type else "Other"}},
                "Lead Magnet CTA": {"rich_text": self._rich_text(draft.cta)},
                "Hook": {"rich_text": self._rich_text(draft.hook)},
                "LinkedIn Post": {"rich_text": self._rich_text(draft.linkedin_post)},
                "Lead Magnet Body": {"rich_text": self._rich_text(body)},
                "Post URL": {"url": draft.post_url or None},
                "Impressions": {"number": 0},
                "Reactions": {"number": 0},
                "Comments": {"number": 0},
                "Shares": {"number": 0},
                "Saves": {"number": 0},
                "Clicks": {"number": 0},
                "Engagement Score": {"number": 0},
                "Experiment ID": {"rich_text": self._rich_text(draft.experiment_id)},
                "Variant Tag": {"rich_text": self._rich_text(draft.variant_tag)},
                "Notes": {"rich_text": self._rich_text(draft.notes)},
            },
        }
        page = self._request("POST", "/pages", payload)
        return str(page["id"])

    def query_recent_pages(self, database_id: str, days: int) -> list[dict[str, Any]]:
        if not database_id:
            raise NotionError("NOTION_DATABASE_ID is missing.")
        since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        payload = {
            "filter": {
                "property": "Publish Date",
                "date": {"on_or_after": since},
            },
            "sorts": [{"property": "Publish Date", "direction": "descending"}],
            "page_size": 100,
        }
        response = self._request("POST", f"/databases/{database_id}/query", payload)
        return list(response.get("results", []))

    def query_by_experiment_id(self, database_id: str, experiment_id: str) -> list[dict[str, Any]]:
        if not database_id:
            raise NotionError("NOTION_DATABASE_ID is missing.")
        payload = {
            "filter": {
                "property": "Experiment ID",
                "rich_text": {"contains": experiment_id},
            },
            "page_size": 10,
        }
        response = self._request("POST", f"/databases/{database_id}/query", payload)
        return list(response.get("results", []))

    def update_post_url(self, page_id: str, post_url: str, status: str = "Published") -> None:
        payload = {
            "properties": {
                "Post URL": {"url": post_url},
                "Status": {"select": {"name": status}},
            }
        }
        self._request("PATCH", f"/pages/{page_id}", payload)

    def update_metrics(self, page_id: str, metrics: PerformanceMetrics) -> None:
        payload = {
            "properties": {
                "Impressions": {"number": metrics.impressions},
                "Reactions": {"number": metrics.reactions},
                "Comments": {"number": metrics.comments},
                "Shares": {"number": metrics.reposts},
                "Saves": {"number": metrics.saves},
                "Clicks": {"number": metrics.clicks},
                "Engagement Score": {"number": metrics.engagement_score},
            }
        }
        self._request("PATCH", f"/pages/{page_id}", payload)

    @staticmethod
    def _read_rich_text(prop: dict[str, Any]) -> str:
        values = prop.get("rich_text", [])
        return "".join(part.get("plain_text", "") for part in values).strip()

    @staticmethod
    def _read_title(prop: dict[str, Any]) -> str:
        values = prop.get("title", [])
        return "".join(part.get("plain_text", "") for part in values).strip()

    @staticmethod
    def _read_number(prop: dict[str, Any]) -> int:
        val = prop.get("number")
        if val is None:
            return 0
        return int(val)

    def page_to_record(self, page: dict[str, Any]) -> dict[str, Any]:
        props = page.get("properties", {})
        post_url = props.get("Post URL", {}).get("url") or ""
        publish_date = props.get("Publish Date", {}).get("date", {}).get("start", "")
        return {
            "page_id": str(page.get("id", "")),
            "headline": self._read_title(props.get("Name", {})),
            "topic": self._read_rich_text(props.get("Topic", {})),
            "hook": self._read_rich_text(props.get("Hook", {})),
            "lead_magnet_type": props.get("Lead Magnet Type", {}).get("select", {}).get("name", "") or "",
            "variant_tag": self._read_rich_text(props.get("Variant Tag", {})),
            "experiment_id": self._read_rich_text(props.get("Experiment ID", {})),
            "post_url": post_url,
            "publish_date": publish_date,
            "impressions": self._read_number(props.get("Impressions", {})),
            "reactions": self._read_number(props.get("Reactions", {})),
            "comments": self._read_number(props.get("Comments", {})),
            "shares": self._read_number(props.get("Shares", {})),
            "saves": self._read_number(props.get("Saves", {})),
            "clicks": self._read_number(props.get("Clicks", {})),
            "engagement_score": float(props.get("Engagement Score", {}).get("number") or 0.0),
        }
