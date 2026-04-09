from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def dump_json(path: Path, payload: dict) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def today_str(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).date().isoformat()


def utc_timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
