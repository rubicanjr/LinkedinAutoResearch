from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_settings
from .generator import LeadMagnetGenerator
from .pipeline import LinkedinLeadMagnetPipeline, PipelineError
from .utils import today_str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="LinkedIn Lead Magnet Autopilot")
    sub = parser.add_subparsers(dest="command", required=True)

    p_bootstrap = sub.add_parser("bootstrap-notion-db", help="Create Notion database")
    p_bootstrap.add_argument("--title", required=True, help="Notion database title")

    p_generate = sub.add_parser("generate", help="Generate daily lead magnet + post")
    p_generate.add_argument("--topic", required=False, default="", help="Topic for today's content")
    p_generate.add_argument("--publish-date", required=False, default="", help="YYYY-MM-DD")

    p_sync = sub.add_parser("sync-metrics", help="Pull metrics from Apify and update Notion")
    p_sync.add_argument("--apify-input", required=False, default="apify_input.json", help="Path to actor input JSON")

    p_attach = sub.add_parser("attach-post-url", help="Attach published LinkedIn URL by experiment id")
    p_attach.add_argument("--experiment-id", required=True, help="Experiment ID from generate command output")
    p_attach.add_argument("--post-url", required=True, help="Published LinkedIn post URL")

    p_publish = sub.add_parser("publish", help="Capture Notion page video, add text layer, publish via Blotato")
    p_publish.add_argument("--experiment-id", required=True, help="Experiment ID from generate command output")
    p_publish.add_argument("--notion-page-url", required=False, default="", help="Optional override for Notion page URL")

    sub.add_parser("research", help="Run ratchet research analysis")

    p_daily = sub.add_parser("daily-run", help="Run generate + sync-metrics + research")
    p_daily.add_argument("--topic", required=False, default="", help="Topic for daily run")
    p_daily.add_argument("--publish-date", required=False, default="", help="YYYY-MM-DD")
    p_daily.add_argument("--apify-input", required=False, default="apify_input.json", help="Path to actor input JSON")
    p_daily.add_argument("--auto-publish", action="store_true", help="Publish generated content via Blotato")
    return parser


def _resolve_topic(raw_topic: str) -> str:
    if raw_topic.strip():
        return raw_topic.strip()
    return LeadMagnetGenerator.default_topic()


def _resolve_date(raw_date: str, timezone_name: str) -> str:
    return raw_date.strip() or today_str(timezone_name)


def main() -> None:
    parser = _parser()
    args = parser.parse_args()

    settings = load_settings()
    pipeline = LinkedinLeadMagnetPipeline(settings)

    try:
        if args.command == "bootstrap-notion-db":
            database_id = pipeline.bootstrap_notion_database(title=args.title)
            print(json.dumps({"database_id": database_id}, indent=2))
            return

        if args.command == "generate":
            topic = _resolve_topic(args.topic)
            publish_date = _resolve_date(args.publish_date, settings.timezone)
            result = pipeline.generate_daily(topic=topic, publish_date=publish_date)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "sync-metrics":
            result = pipeline.sync_metrics(apify_input_path=Path(args.apify_input))
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "attach-post-url":
            result = pipeline.attach_post_url(experiment_id=args.experiment_id, post_url=args.post_url)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "publish":
            result = pipeline.publish_by_experiment_id(
                experiment_id=args.experiment_id,
                notion_page_url_override=args.notion_page_url,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "research":
            result = pipeline.run_research()
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        if args.command == "daily-run":
            topic = _resolve_topic(args.topic)
            publish_date = _resolve_date(args.publish_date, settings.timezone)
            result = pipeline.daily_run(
                topic=topic,
                publish_date=publish_date,
                apify_input_path=Path(args.apify_input),
                auto_publish=bool(args.auto_publish),
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        parser.print_help()
    except PipelineError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
