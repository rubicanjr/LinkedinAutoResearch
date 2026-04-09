from __future__ import annotations

import mimetypes
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


class BlotatoError(RuntimeError):
    pass


@dataclass
class BlotatoClient:
    api_key: str
    base_url: str = "https://backend.blotato.com/v2"

    def _headers(self) -> dict[str, str]:
        return {
            "blotato-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key:
            raise BlotatoError("BLOTATO_API_KEY is missing.")
        resp = requests.request(
            method=method,
            url=f"{self.base_url}{path}",
            headers=self._headers(),
            json=payload,
            timeout=90,
        )
        if not resp.ok:
            raise BlotatoError(f"Blotato API error {resp.status_code}: {resp.text}")
        return resp.json()

    def list_accounts(self, platform: str = "linkedin") -> list[dict[str, Any]]:
        response = self._request("GET", f"/users/me/accounts?platform={platform}")
        if isinstance(response, list):
            return response
        if isinstance(response.get("items"), list):
            return response["items"]
        if isinstance(response.get("data"), list):
            return response["data"]
        if isinstance(response.get("accounts"), list):
            return response["accounts"]
        return []

    def resolve_account_id(self, preferred_account_id: str = "", platform: str = "linkedin") -> str:
        if preferred_account_id.strip():
            return preferred_account_id.strip()
        accounts = self.list_accounts(platform=platform)
        if not accounts:
            raise BlotatoError(f"No Blotato {platform} account found.")
        first = accounts[0]
        account_id = str(first.get("id") or first.get("accountId") or "").strip()
        if not account_id:
            raise BlotatoError("Unable to resolve account id from Blotato response.")
        return account_id

    def upload_media(self, media_path: Path) -> str:
        if not media_path.exists():
            raise BlotatoError(f"Media file not found: {media_path}")

        content_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"
        create_payload = {"filename": media_path.name, "contentType": content_type}
        create = self._request("POST", "/media", create_payload)

        upload_url = str(create.get("presignedUrl") or create.get("uploadUrl") or "").strip()
        public_url = str(create.get("mediaUrl") or create.get("publicUrl") or create.get("url") or "").strip()
        if not upload_url or not public_url:
            raise BlotatoError("Blotato media upload response is missing upload URL or media URL.")

        with media_path.open("rb") as stream:
            put_resp = requests.put(upload_url, data=stream, headers={"Content-Type": content_type}, timeout=120)
        if not put_resp.ok:
            raise BlotatoError(f"Media upload to storage failed: {put_resp.status_code} {put_resp.text}")
        return public_url

    def create_post(
        self,
        account_id: str,
        text: str,
        media_urls: list[str],
        platform: str = "linkedin",
        linkedin_page_id: str = "",
    ) -> str:
        if not account_id:
            raise BlotatoError("account_id is required.")
        if not text.strip():
            raise BlotatoError("Post text cannot be empty.")
        if not media_urls:
            raise BlotatoError("At least one media URL is required.")

        payload: dict[str, Any] = {
            "post": {
                "accountId": account_id,
                "content": {
                    "text": text,
                    "mediaUrls": media_urls,
                    "platform": platform,
                },
                "target": {
                    "targetType": platform,
                },
            }
        }
        if linkedin_page_id.strip():
            payload["post"]["target"]["pageId"] = linkedin_page_id.strip()

        created = self._request("POST", "/posts", payload)
        submission_id = str(
            created.get("postSubmissionId")
            or created.get("id")
            or (created.get("item") or {}).get("postSubmissionId")
            or (created.get("item") or {}).get("id")
            or ""
        ).strip()
        if not submission_id:
            raise BlotatoError(f"Could not read post submission id from response: {created}")
        return submission_id

    def get_post_status(self, post_submission_id: str) -> dict[str, Any]:
        if not post_submission_id:
            raise BlotatoError("post_submission_id is required.")
        return self._request("GET", f"/posts/{post_submission_id}")

    def wait_until_published(self, post_submission_id: str, timeout_seconds: int = 240) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        last_payload: dict[str, Any] = {}
        while time.time() < deadline:
            payload = self.get_post_status(post_submission_id)
            last_payload = payload
            item = payload.get("item") if isinstance(payload.get("item"), dict) else payload
            status = str(item.get("status") or payload.get("status") or "").lower()
            if status in {"published", "success", "completed"}:
                return payload
            if status in {"failed", "error"}:
                raise BlotatoError(f"Blotato post failed: {payload}")
            time.sleep(3)
        raise BlotatoError(f"Timed out waiting for Blotato publish. Last payload: {last_payload}")

    @staticmethod
    def extract_public_post_url(status_payload: dict[str, Any]) -> str:
        item = status_payload.get("item") if isinstance(status_payload.get("item"), dict) else status_payload
        return str(item.get("publicUrl") or item.get("postUrl") or item.get("url") or "").strip()
