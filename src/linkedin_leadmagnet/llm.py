from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


class LLMError(RuntimeError):
    pass


@dataclass
class OpenAIChatClient:
    api_key: str
    model: str
    timeout_seconds: int = 60
    base_url: str = "https://api.openai.com/v1/chat/completions"

    def generate_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.api_key:
            raise LLMError("OPENAI_API_KEY is missing.")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "response_format": {"type": "json_object"},
        }

        resp = requests.post(
            self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )

        if not resp.ok:
            raise LLMError(f"LLM request failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        try:
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMError(f"Failed to parse JSON response: {exc}") from exc
