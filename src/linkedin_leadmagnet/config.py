from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    notion_token: str
    notion_parent_page_id: str
    notion_database_id: str
    apify_token: str
    apify_actor_id: str
    timezone: str
    research_history_days: int
    output_dir: Path
    lead_magnet_school_path: Path


def load_settings(env_file: str = ".env") -> Settings:
    load_dotenv(env_file)

    output_dir = Path(os.getenv("OUTPUT_DIR", "data")).resolve()
    school_path = Path(os.getenv("LEAD_MAGNET_SCHOOL_PATH", "knowledge/lead_magnet_school.md")).resolve()

    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        notion_token=os.getenv("NOTION_TOKEN", "").strip(),
        notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID", "").strip(),
        notion_database_id=os.getenv("NOTION_DATABASE_ID", "").strip(),
        apify_token=os.getenv("APIFY_TOKEN", "").strip(),
        apify_actor_id=os.getenv("APIFY_ACTOR_ID", "").strip(),
        timezone=os.getenv("TIMEZONE", "Europe/Istanbul").strip(),
        research_history_days=_read_int("RESEARCH_HISTORY_DAYS", 30),
        output_dir=output_dir,
        lead_magnet_school_path=school_path,
    )
