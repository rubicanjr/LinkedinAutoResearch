from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


class LLMError(RuntimeError):
    pass


@dataclass
class GeminiClient:
    api_key: str
    model: str
    timeout_seconds: int = 60
    base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is missing.")

        payload = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json",
            },
        }

        resp = requests.post(
            f"{self.base_url}/models/{self.model}:generateContent",
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )

        if not resp.ok:
            raise LLMError(f"LLM request failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMError(f"Failed to parse JSON response: {exc}") from exc
