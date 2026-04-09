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


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str
    gemini_model: str
    notion_token: str
    notion_parent_page_id: str
    notion_database_id: str
    apify_token: str
    apify_actor_id: str
    apify_run_timeout_seconds: int
    apify_dataset_limit: int
    apify_dataset_clean: bool
    apify_dataset_format: str
    timezone: str
    research_history_days: int
    output_dir: Path
    lead_magnet_school_path: Path
    notion_page_url_template: str
    buffer_api_key: str
    buffer_profile_id: str
    blotato_api_key: str
    blotato_platform: str
    blotato_account_id: str
    blotato_linkedin_page_id: str
    video_overlay_text: str
    scroll_record_seconds: float
    auto_publish_default: bool


def load_settings(env_file: str = ".env") -> Settings:
    load_dotenv(env_file)

    output_dir = Path(os.getenv("OUTPUT_DIR", "data")).resolve()
    school_path = Path(os.getenv("LEAD_MAGNET_SCHOOL_PATH", "knowledge/lead_magnet_school.md")).resolve()

    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3-pro").strip(),
        notion_token=os.getenv("NOTION_TOKEN", "").strip(),
        notion_parent_page_id=os.getenv("NOTION_PARENT_PAGE_ID", "").strip(),
        notion_database_id=os.getenv("NOTION_DATABASE_ID", "").strip(),
        apify_token=os.getenv("APIFY_TOKEN", "").strip(),
        apify_actor_id=os.getenv("APIFY_ACTOR_ID", "").strip(),
        apify_run_timeout_seconds=_read_int("APIFY_RUN_TIMEOUT_SECONDS", 280),
        apify_dataset_limit=_read_int("APIFY_DATASET_LIMIT", 100),
        apify_dataset_clean=_read_bool("APIFY_DATASET_CLEAN", True),
        apify_dataset_format=os.getenv("APIFY_DATASET_FORMAT", "json").strip() or "json",
        timezone=os.getenv("TIMEZONE", "Europe/Istanbul").strip(),
        research_history_days=_read_int("RESEARCH_HISTORY_DAYS", 30),
        output_dir=output_dir,
        lead_magnet_school_path=school_path,
        notion_page_url_template=os.getenv("NOTION_PAGE_URL_TEMPLATE", "https://www.notion.so/{page_id_nodash}").strip(),
        buffer_api_key=os.getenv("BUFFER_API_KEY", "").strip(),
        buffer_profile_id=os.getenv("BUFFER_PROFILE_ID", "").strip(),
        blotato_api_key=os.getenv("BLOTATO_API_KEY", "").strip(),
        blotato_platform=os.getenv("BLOTATO_PLATFORM", "linkedin").strip() or "linkedin",
        blotato_account_id=os.getenv("BLOTATO_ACCOUNT_ID", "").strip(),
        blotato_linkedin_page_id=os.getenv("BLOTATO_LINKEDIN_PAGE_ID", "").strip(),
        video_overlay_text=os.getenv("VIDEO_OVERLAY_TEXT", "Yorumlara CHECKLIST yaz, hemen gondereyim.").strip(),
        scroll_record_seconds=_read_float("SCROLL_RECORD_SECONDS", 6.7),
        auto_publish_default=_read_bool("AUTO_PUBLISH_DEFAULT", False),
    )
