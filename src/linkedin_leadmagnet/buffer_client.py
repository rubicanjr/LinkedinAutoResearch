from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class BufferError(RuntimeError):
    pass


@dataclass
class BufferClient:
    api_key: str
    base_url: str = "https://api.bufferapp.com/1"

    def _require_key(self) -> None:
        if not self.api_key:
            raise BufferError("BUFFER_API_KEY is missing.")

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self._require_key()
        query = {"access_token": self.api_key}
        if params:
            query.update(params)
        resp = requests.get(f"{self.base_url}{path}", params=query, timeout=60)
        if not resp.ok:
            raise BufferError(f"Buffer API error {resp.status_code}: {resp.text}")
        return resp.json()

    def _post(self, path: str, data: list[tuple[str, str]] | dict[str, str]) -> Any:
        self._require_key()
        resp = requests.post(
            f"{self.base_url}{path}",
            params={"access_token": self.api_key},
            data=data,
            timeout=60,
        )
        if not resp.ok:
            raise BufferError(f"Buffer API error {resp.status_code}: {resp.text}")
        return resp.json()

    def list_profiles(self) -> list[dict[str, Any]]:
        payload = self._get("/profiles.json")
        if isinstance(payload, list):
            return payload
        return []

    def resolve_linkedin_profile_id(self, preferred_profile_id: str = "") -> str:
        if preferred_profile_id.strip():
            return preferred_profile_id.strip()

        profiles = self.list_profiles()
        for profile in profiles:
            service = str(profile.get("service", "")).strip().lower()
            if service == "linkedin":
                profile_id = str(profile.get("id", "")).strip()
                if profile_id:
                    return profile_id

        raise BufferError("No LinkedIn profile found in Buffer account.")

    def create_update(self, profile_id: str, text: str, post_now: bool = True, link: str = "") -> dict[str, Any]:
        if not profile_id.strip():
            raise BufferError("Buffer profile_id is required.")
        body_text = text.strip()
        if not body_text:
            raise BufferError("Post text cannot be empty.")

        payload: list[tuple[str, str]] = [
            ("profile_ids[]", profile_id.strip()),
            ("text", body_text),
            ("now", "true" if post_now else "false"),
            ("shorten", "false"),
        ]
        if link.strip():
            payload.extend(
                [
                    ("media[link]", link.strip()),
                    ("media[description]", "Lead magnet details"),
                ]
            )

        result = self._post("/updates/create.json", payload)
        if not isinstance(result, dict):
            raise BufferError(f"Unexpected Buffer response: {result}")
        if result.get("success") is False:
            raise BufferError(f"Buffer rejected update: {result}")
        return result
