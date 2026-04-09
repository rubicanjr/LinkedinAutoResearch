from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .apify_client import ApifyClient, ApifyError
from .buffer_client import BufferClient, BufferError
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
        self.buffer = BufferClient(api_key=settings.buffer_api_key) if settings.buffer_api_key else None
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
        notion_page_url = ""
        if self.notion and self.settings.notion_database_id:
            try:
                notion_page_id, notion_page_url = self.notion.create_draft_page(self.settings.notion_database_id, draft)
                self.notion.append_lead_magnet_blocks(notion_page_id, draft)
                public_page_url = self.notion.build_page_url(
                    notion_page_id,
                    self.settings.notion_page_url_template,
                )
                self.notion.update_lead_magnet_page_url(notion_page_id, public_page_url)
                notion_page_url = public_page_url or notion_page_url
            except NotionError as exc:
                raise PipelineError(str(exc)) from exc

        return {
            "draft_path": str(draft_path),
            "notion_page_id": notion_page_id,
            "notion_page_url": notion_page_url,
            "experiment_id": draft.experiment_id,
            "variant_tag": draft.variant_tag,
            "headline": draft.headline,
        }

    def _find_draft_by_experiment_id(self, experiment_id: str) -> Path:
        drafts_dir = self.settings.output_dir / "drafts"
        if not drafts_dir.exists():
            raise PipelineError("Drafts directory does not exist.")
        matches = sorted(drafts_dir.glob(f"*_{experiment_id}.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not matches:
            raise PipelineError(f"No draft file found for experiment_id={experiment_id}")
        return matches[0]

    def _load_draft_from_file(self, draft_path: Path) -> LeadMagnetDraft:
        payload = load_json(draft_path)
        return LeadMagnetDraft.from_dict(payload)

    def _build_publish_text(self, draft: LeadMagnetDraft, notion_page_url: str) -> str:
        text = draft.linkedin_post.strip()
        if notion_page_url.strip() and notion_page_url not in text:
            text = f"{text}\n\nLead magnet: {notion_page_url.strip()}"
        return text

    def publish_by_experiment_id(self, experiment_id: str, notion_page_url_override: str = "") -> dict[str, Any]:
        if not self.buffer:
            raise PipelineError("Buffer client is not configured. Set BUFFER_API_KEY.")

        draft_path = self._find_draft_by_experiment_id(experiment_id.strip())
        draft = self._load_draft_from_file(draft_path)

        notion_page_url = notion_page_url_override.strip()
        page_id = ""
        if self.notion and self.settings.notion_database_id:
            pages = self.notion.query_by_experiment_id(self.settings.notion_database_id, experiment_id.strip())
            if pages:
                record = self.notion.page_to_record(pages[0])
                page_id = record.get("page_id", "")
                notion_page_url = notion_page_url or record.get("lead_magnet_page_url", "") or record.get("notion_url", "")
                if not notion_page_url and page_id:
                    notion_page_url = self.notion.build_page_url(page_id, self.settings.notion_page_url_template)

        if not notion_page_url:
            raise PipelineError(
                "Could not resolve Notion page URL. Provide --notion-page-url or set NOTION_PAGE_URL_TEMPLATE."
            )

        stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        try:
            profile_id = self.buffer.resolve_linkedin_profile_id(
                preferred_profile_id=self.settings.buffer_profile_id,
            )
            publish_text = self._build_publish_text(draft, notion_page_url)
            publish_result = self.buffer.create_update(
                profile_id=profile_id,
                text=publish_text,
                post_now=True,
                link=notion_page_url,
            )
            update_id = ""
            updates = publish_result.get("updates")
            if isinstance(updates, list) and updates:
                update_id = str(updates[0].get("id", "")).strip()
        except BufferError as exc:
            raise PipelineError(str(exc)) from exc

        result = {
            "experiment_id": experiment_id,
            "draft_path": str(draft_path),
            "notion_page_url": notion_page_url,
            "buffer_profile_id": profile_id,
            "buffer_update_id": update_id,
        }
        dump_json(self.settings.output_dir / "runs" / f"{stamp}_{experiment_id}_publish.json", result)
        return result

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
        apify_query_options = {
            "timeout": self.settings.apify_run_timeout_seconds,
            "format": self.settings.apify_dataset_format,
            "clean": int(self.settings.apify_dataset_clean),
            "limit": self.settings.apify_dataset_limit,
        }
        try:
            raw_items = self.apify.run_actor_sync_items(
                self.settings.apify_actor_id,
                actor_input,
                query_options=apify_query_options,
            )
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

    def daily_run(self, topic: str, publish_date: str, apify_input_path: Path, auto_publish: bool = False) -> dict[str, Any]:
        generation = self.generate_daily(topic=topic, publish_date=publish_date)
        publish: dict[str, Any] | None = None
        should_publish = auto_publish or self.settings.auto_publish_default
        if should_publish:
            publish = self.publish_by_experiment_id(
                experiment_id=str(generation["experiment_id"]),
                notion_page_url_override=str(generation.get("notion_page_url", "")),
            )
        metrics = self.sync_metrics(apify_input_path=apify_input_path)
        research = self.run_research()
        summary: dict[str, Any] = {"generation": generation, "metrics": metrics, "research": research}
        if publish:
            summary["publish"] = publish
        dump_json(self.settings.output_dir / "runs" / f"{publish_date}_daily_run.json", summary)
        return summary
