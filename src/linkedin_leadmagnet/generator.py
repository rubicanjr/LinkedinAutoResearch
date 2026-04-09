from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config import Settings
from .llm import LLMError, OpenAIChatClient
from .models import LeadMagnetDraft


def _sanitize_variant(value: str) -> str:
    match = re.search(r"[A-Z]", value.upper())
    return match.group(0) if match else "A"


class LeadMagnetGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = OpenAIChatClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    def _school_context(self) -> str:
        path = self.settings.lead_magnet_school_path
        if not path.exists():
            return "No school content file found. Use fundamentals only."
        return path.read_text(encoding="utf-8")

    def _fallback_draft(self, topic: str, publish_date: str, research_hint: str) -> LeadMagnetDraft:
        experiment_id = f"{publish_date}-{uuid4().hex[:8]}"
        hook = f"{topic} konusunda fark yaratan 1 hata ve 1 hizli cozum."
        summary = "Pratik, uygulanabilir bir kontrol listesi."
        post = (
            f"{hook}\n\n"
            f"Bugun {topic} icin uygulanabilir bir mini cerceve paylasiyorum.\n"
            "1) Sorunu netlestir\n"
            "2) Darbogazi tespit et\n"
            "3) 7 gunluk aksiyon plani yaz\n\n"
            f"Lead magnet: '{topic} Action Checklist'.\n"
            "Yorumlara CHECKLIST yazarsan gonderecegim."
        )
        notes = "Generated with fallback template because LLM was unavailable."
        if research_hint.strip():
            notes += f" Research hint used: {research_hint.strip()[:300]}"
        return LeadMagnetDraft(
            topic=topic,
            publish_date=publish_date,
            headline=f"{topic}: 7 Gunluk Aksiyon Cizelgesi",
            hook=hook,
            lead_magnet_title=f"{topic} Action Checklist",
            lead_magnet_type="Checklist",
            lead_magnet_summary=summary,
            lead_magnet_outline=[
                "Hedef kitle ve hedef sonuc",
                "Yuksek etkili 5 adim",
                "Olcum KPI listesi",
                "Yaygin hata kontrolu",
            ],
            cta="CHECKLIST yaz, DM ile gonderelim.",
            linkedin_post=post,
            variant_tag="A",
            experiment_id=experiment_id,
            notes=notes,
        )

    def _build_prompt(self, topic: str, publish_date: str, research_hint: str) -> tuple[str, str]:
        system_prompt = (
            "You are a B2B growth strategist focused on LinkedIn lead magnets. "
            "Return strict JSON only."
        )
        user_prompt = (
            "Create one high-converting LinkedIn post and one lead magnet for the topic.\n\n"
            f"Topic: {topic}\n"
            f"Publish date: {publish_date}\n\n"
            "School context:\n"
            f"{self._school_context()}\n\n"
            "Research hint from previous runs:\n"
            f"{research_hint or 'No prior hint.'}\n\n"
            "Output JSON with keys:\n"
            "headline, hook, lead_magnet_title, lead_magnet_type, lead_magnet_summary, "
            "lead_magnet_outline (array), cta, linkedin_post, variant_tag\n"
            "Constraints:\n"
            "- Keep post under 220 words.\n"
            "- Include one clear CTA.\n"
            "- Use concrete outcomes and practical language.\n"
            "- Avoid hype words.\n"
        )
        return system_prompt, user_prompt

    def _parse_draft(self, payload: dict[str, Any], topic: str, publish_date: str) -> LeadMagnetDraft:
        experiment_id = f"{publish_date}-{uuid4().hex[:8]}"
        outline_raw = payload.get("lead_magnet_outline", [])
        outline = [str(x).strip() for x in outline_raw if str(x).strip()] if isinstance(outline_raw, list) else []
        if not outline:
            outline = ["Problem framing", "Step-by-step process", "Checklist", "KPIs"]

        return LeadMagnetDraft(
            topic=topic,
            publish_date=publish_date,
            headline=str(payload.get("headline", "")).strip() or f"{topic} Playbook",
            hook=str(payload.get("hook", "")).strip() or f"{topic} icin en kritik darbogaz ve cozum",
            lead_magnet_title=str(payload.get("lead_magnet_title", "")).strip() or f"{topic} Guide",
            lead_magnet_type=str(payload.get("lead_magnet_type", "")).strip() or "Guide",
            lead_magnet_summary=str(payload.get("lead_magnet_summary", "")).strip() or "Practical framework.",
            lead_magnet_outline=outline,
            cta=str(payload.get("cta", "")).strip() or "Yorumlara GUIDE yazin.",
            linkedin_post=str(payload.get("linkedin_post", "")).strip() or "",
            variant_tag=_sanitize_variant(str(payload.get("variant_tag", "A"))),
            experiment_id=experiment_id,
        )

    def generate(self, topic: str, publish_date: str, research_hint: str = "") -> LeadMagnetDraft:
        if not self.settings.openai_api_key:
            return self._fallback_draft(topic, publish_date, research_hint)

        system_prompt, user_prompt = self._build_prompt(topic, publish_date, research_hint)
        try:
            payload = self.client.generate_json(system_prompt=system_prompt, user_prompt=user_prompt)
            return self._parse_draft(payload=payload, topic=topic, publish_date=publish_date)
        except LLMError as exc:
            fallback = self._fallback_draft(topic, publish_date, research_hint)
            fallback.notes = f"{fallback.notes} LLMError: {exc}"
            return fallback

    @staticmethod
    def default_topic() -> str:
        return f"B2B growth lever #{datetime.utcnow().day}"
