from __future__ import annotations

from pathlib import Path
from typing import Any

from .apify_client import ApifyClient, ApifyError
from .config import Settings
from .generator import LeadMagnetGenerator
from .models import LeadMagnetDraft
from .notion import NotionClient, NotionError
from .research import build_research_insight, render_recommendation_markdown
from .utils import dump_json, load_json


class PipelineError(RuntimeError):
    pass


class LinkedinLeadMagnetPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.generator = LeadMagnetGenerator(settings)
        self.notion = NotionClient(token=settings.notion_token) if settings.notion_token else None
        self.apify = ApifyClient(token=settings.apify_token) if settings.apify_token else None
        self.settings.output_dir.mkdir(parents=True, exist_ok=True)

    def _research_hint_path(self) -> Path:
        return self.settings.output_dir / "research" / "latest_insight.json"

    def _load_research_hint(self) -> str:
        path = self._research_hint_path()
        if not path.exists():
            return ""
        payload = load_json(path)
        return str(payload.get("next_prompt_instructions", "")).strip()

    def bootstrap_notion_database(self, title: str) -> str:
        if not self.notion:
            raise PipelineError("Notion client is not configured. Set NOTION_TOKEN.")
        try:
            db_id = self.notion.create_database(parent_page_id=self.settings.notion_parent_page_id, title=title)
            return db_id
        except NotionError as exc:
            raise PipelineError(str(exc)) from exc

    def generate_daily(self, topic: str, publish_date: str) -> dict[str, Any]:
        hint = self._load_research_hint()
        draft: LeadMagnetDraft = self.generator.generate(topic=topic, publish_date=publish_date, research_hint=hint)

        draft_path = self.settings.output_dir / "drafts" / f"{publish_date}_{draft.experiment_id}.json"
        dump_json(draft_path, draft.to_dict())

        notion_page_id = ""
        if self.notion and self.settings.notion_database_id:
            try:
                notion_page_id = self.notion.create_draft_page(self.settings.notion_database_id, draft)
            except NotionError as exc:
                raise PipelineError(str(exc)) from exc

        return {
            "draft_path": str(draft_path),
            "notion_page_id": notion_page_id,
            "experiment_id": draft.experiment_id,
            "variant_tag": draft.variant_tag,
            "headline": draft.headline,
        }

    def sync_metrics(self, apify_input_path: Path) -> dict[str, Any]:
        if not self.apify:
            raise PipelineError("Apify client is not configured. Set APIFY_TOKEN.")
        if not self.notion:
            raise PipelineError("Notion client is not configured. Set NOTION_TOKEN.")
        if not self.settings.notion_database_id:
            raise PipelineError("NOTION_DATABASE_ID is missing.")
        if not apify_input_path.exists():
            raise PipelineError(f"Apify input file not found: {apify_input_path}")

        actor_input = load_json(apify_input_path)
        try:
            raw_items = self.apify.run_actor_sync_items(self.settings.apify_actor_id, actor_input)
        except ApifyError as exc:
            raise PipelineError(str(exc)) from exc

        metrics_by_url: dict[str, Any] = {}
        for item in raw_items:
            post_url, metrics = self.apify.normalize_metrics(item)
            if post_url:
                metrics_by_url[post_url] = metrics

        pages = self.notion.query_recent_pages(self.settings.notion_database_id, self.settings.research_history_days)
        updated = 0
        unmatched = 0
        for page in pages:
            record = self.notion.page_to_record(page)
            url = record.get("post_url", "")
            if not url:
                continue
            if url not in metrics_by_url:
                unmatched += 1
                continue
            self.notion.update_metrics(record["page_id"], metrics_by_url[url])
            updated += 1

        out = {
            "apify_items": len(raw_items),
            "matched_urls": len(metrics_by_url),
            "updated_pages": updated,
            "unmatched_pages": unmatched,
        }
        dump_json(self.settings.output_dir / "metrics" / "last_sync.json", out)
        return out

    def attach_post_url(self, experiment_id: str, post_url: str) -> dict[str, Any]:
        if not self.notion:
            raise PipelineError("Notion client is not configured. Set NOTION_TOKEN.")
        if not self.settings.notion_database_id:
            raise PipelineError("NOTION_DATABASE_ID is missing.")
        if not experiment_id.strip():
            raise PipelineError("experiment_id is required.")
        if not post_url.strip():
            raise PipelineError("post_url is required.")

        pages = self.notion.query_by_experiment_id(self.settings.notion_database_id, experiment_id.strip())
        if not pages:
            raise PipelineError(f"No Notion record found for experiment_id={experiment_id}")
        page_id = str(pages[0].get("id", ""))
        self.notion.update_post_url(page_id=page_id, post_url=post_url.strip(), status="Published")
        result = {"page_id": page_id, "experiment_id": experiment_id, "post_url": post_url}
        dump_json(self.settings.output_dir / "metrics" / "last_post_url_attach.json", result)
        return result

    def run_research(self) -> dict[str, Any]:
        if not self.notion:
            raise PipelineError("Notion client is not configured. Set NOTION_TOKEN.")
        if not self.settings.notion_database_id:
            raise PipelineError("NOTION_DATABASE_ID is missing.")

        pages = self.notion.query_recent_pages(self.settings.notion_database_id, self.settings.research_history_days)
        records = [self.notion.page_to_record(page) for page in pages]
        insight = build_research_insight(records)

        insight_path = self.settings.output_dir / "research" / "latest_insight.json"
        dump_json(insight_path, insight.to_dict())

        recommendation = render_recommendation_markdown(insight)
        recommendation_path = self.settings.output_dir / "research" / "latest_recommendation.md"
        recommendation_path.parent.mkdir(parents=True, exist_ok=True)
        recommendation_path.write_text(recommendation, encoding="utf-8")

        return {
            "insight_path": str(insight_path),
            "recommendation_path": str(recommendation_path),
            "records_analyzed": insight.analyzed_records,
        }

    def daily_run(self, topic: str, publish_date: str, apify_input_path: Path) -> dict[str, Any]:
        generation = self.generate_daily(topic=topic, publish_date=publish_date)
        metrics = self.sync_metrics(apify_input_path=apify_input_path)
        research = self.run_research()
        summary = {"generation": generation, "metrics": metrics, "research": research}
        dump_json(self.settings.output_dir / "runs" / f"{publish_date}_daily_run.json", summary)
        return summary
