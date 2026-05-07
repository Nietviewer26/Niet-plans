"""
adapters.py — Concrete implementations of interfaces.
This is the ONLY file allowed to import vendor SDKs (anthropic, etc.).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import textwrap
import uuid
from datetime import date

from interfaces import (
    AdCampaignDraft,
    AdPlatform,
    CopyRequest,
    CopyVariant,
    EmailCampaignDraft,
    EmailProvider,
    ImageRequest,
    LaunchResult,
    LLMProvider,
    MediaGenerator,
)


# ---------------------------------------------------------------------------
# MockMetaAdPlatform
# ---------------------------------------------------------------------------

class MockMetaAdPlatform(AdPlatform):
    name = "meta"

    def launch_campaign(self, ad_account_external_id: str, draft: AdCampaignDraft) -> LaunchResult:
        campaign_id = f"mcamp_{uuid.uuid4().hex[:16]}"
        variant_ids = [f"mad_{uuid.uuid4().hex[:16]}" for _ in draft.variants]
        return LaunchResult(
            external_id=campaign_id,
            status="running",
            variant_external_ids=variant_ids,
        )

    def pause_variant(self, eid: str) -> None:
        pass  # Mock — no side effects

    def update_variant_weight(self, eid: str, weight: float) -> None:
        pass  # Mock — no side effects

    def fetch_metrics(self, eid: str, day) -> dict:
        if isinstance(day, date):
            day_str = day.isoformat()
        else:
            day_str = str(day)
        seed_hex = hashlib.md5(f"{eid}:{day_str}".encode()).hexdigest()
        seed = int(seed_hex, 16) % (2**31)
        rng = random.Random(seed)

        impressions = rng.randint(800, 4000)
        ctr = rng.uniform(0.012, 0.038)
        cvr = rng.uniform(0.03, 0.09)
        cpc_cents = rng.randint(40, 180)
        rev_per_conv_cents = rng.randint(2500, 6000)

        clicks = int(impressions * ctr)
        conversions = int(clicks * cvr)
        spend_cents = clicks * cpc_cents
        revenue_cents = conversions * rev_per_conv_cents

        return {
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "spend_cents": spend_cents,
            "revenue_cents": revenue_cents,
        }


# ---------------------------------------------------------------------------
# MockKlaviyoEmailProvider
# ---------------------------------------------------------------------------

class MockKlaviyoEmailProvider(EmailProvider):
    name = "klaviyo"

    def send_campaign(self, account_eid: str, draft: EmailCampaignDraft) -> LaunchResult:
        campaign_id = f"klcamp_{uuid.uuid4().hex[:16]}"
        return LaunchResult(external_id=campaign_id, status="scheduled")

    def fetch_metrics(self, eid: str) -> dict:
        seed_hex = hashlib.md5(f"{eid}:email".encode()).hexdigest()
        seed = int(seed_hex, 16) % (2**31)
        rng = random.Random(seed)

        recipients = rng.randint(1500, 12000)
        open_rate = rng.uniform(0.18, 0.42)
        click_rate = rng.uniform(0.015, 0.06)
        opens = int(recipients * open_rate)
        clicks = int(recipients * click_rate)

        return {
            "recipients": recipients,
            "opens": opens,
            "clicks": clicks,
            "open_rate": open_rate,
            "click_rate": click_rate,
        }

    def list_audiences(self, account_eid: str) -> list[dict]:
        return [
            {"id": "aud_all", "name": "All Subscribers", "size": 8400},
            {"id": "aud_active", "name": "Active 90d", "size": 3200},
            {"id": "aud_lapsed", "name": "Lapsed 180d+", "size": 1950},
        ]


# ---------------------------------------------------------------------------
# AnthropicLLMProvider
# ---------------------------------------------------------------------------

class AnthropicLLMProvider(LLMProvider):
    name = "anthropic"

    # Per-1M-token rates in £ (input, output)
    _RATES_GBP: dict[str, tuple[float, float]] = {
        "claude-sonnet-4-6": (2.40, 12.00),
        "claude-haiku-4-5": (0.64, 3.20),
        "claude-opus-4-7": (12.00, 60.00),
    }

    def __init__(self, model: str = "claude-sonnet-4-6"):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")
        import anthropic as _anthropic
        self._client = _anthropic.Anthropic(api_key=api_key)
        self._model = model
        self.last_usage: dict = {}

    def _record_usage(self, usage) -> None:
        input_tok = getattr(usage, "input_tokens", 0)
        output_tok = getattr(usage, "output_tokens", 0)
        rates = self._RATES_GBP.get(self._model, (2.40, 12.00))
        cost_gbp = (input_tok / 1_000_000) * rates[0] + (output_tok / 1_000_000) * rates[1]
        self.last_usage = {
            "input_tokens": input_tok,
            "output_tokens": output_tok,
            "cost_cents": int(round(cost_gbp * 100)),
        }

    def generate_copy(self, req: CopyRequest) -> list[CopyVariant]:
        system_prompt = (
            "You are a direct-response copywriter. "
            "Respond ONLY with valid JSON, no markdown fences, no extra text."
        )
        user_prompt = (
            f"Brand voice: {req.brand_voice}\n"
            f"Target audience: {req.target_audience}\n"
            f"Product/offer: {req.product}\n"
            f"Angle: {req.angle}\n\n"
            f"Write {req.n_variants} ad copy variants. "
            "Each variant must have: headline (<40 chars), body (<125 chars), cta (2-4 words).\n"
            f"Return JSON: {{\"variants\": [{{\"headline\": \"...\", \"body\": \"...\", \"cta\": \"...\"}}]}}"
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        self._record_usage(response.usage)
        raw = response.content[0].text.strip()
        # Strip ```json fences if present
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return [
            CopyVariant(
                headline=v["headline"],
                body=v["body"],
                cta=v["cta"],
            )
            for v in data["variants"]
        ]

    def generate_subject_lines(self, brand_voice: str, body_summary: str, n: int = 5) -> list[str]:
        system_prompt = (
            "You are an email subject line specialist. "
            "Respond ONLY with valid JSON, no markdown fences."
        )
        user_prompt = (
            f"Brand voice: {brand_voice}\n"
            f"Email summary: {body_summary}\n"
            f"Write {n} email subject lines (under 60 chars each).\n"
            f"Return JSON: {{\"subjects\": [\"...\", ...]}}"
        )
        response = self._client.messages.create(
            model=self._model,
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        self._record_usage(response.usage)
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return data["subjects"]


# ---------------------------------------------------------------------------
# PlaceholderMediaGenerator
# ---------------------------------------------------------------------------

class PlaceholderMediaGenerator(MediaGenerator):
    name = "placeholder"

    _PALETTES = [
        ("#F59E0B", "#FEF3C7"),  # amber
        ("#6366F1", "#EEF2FF"),  # indigo
        ("#10B981", "#D1FAE5"),  # emerald
        ("#EF4444", "#FEE2E2"),  # red
        ("#8B5CF6", "#EDE9FE"),  # violet
    ]

    _ASPECT_SIZES = {
        "1:1": (800, 800),
        "9:16": (720, 1280),
        "16:9": (1280, 720),
        "4:5": (800, 1000),
    }

    def generate_image(self, req: ImageRequest) -> str:
        w, h = self._ASPECT_SIZES.get(req.aspect_ratio, (800, 800))
        seed = int(hashlib.md5(req.description.encode()).hexdigest(), 16) % 5
        primary, light = self._PALETTES[seed]

        # Wrap description text
        lines = textwrap.wrap(req.description, width=24)[:5]
        text_lines = "".join(
            f'<tspan x="{w // 2}" dy="1.4em">{line}</tspan>' for line in lines
        )
        text_y = h // 2 - len(lines) * 14

        cx1, cy1 = int(w * 0.25), int(h * 0.30)
        cx2, cy2 = int(w * 0.75), int(h * 0.70)
        r1, r2 = int(w * 0.28), int(w * 0.22)

        footer_y = h - 20
        footer_x = w // 2

        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect width="{w}" height="{h}" fill="{light}"/>
  <circle cx="{cx1}" cy="{cy1}" r="{r1}" fill="{primary}" opacity="0.18"/>
  <circle cx="{cx2}" cy="{cy2}" r="{r2}" fill="{primary}" opacity="0.14"/>
  <text x="{w // 2}" y="{text_y}" font-family="sans-serif" font-size="28"
        font-weight="bold" fill="{primary}" text-anchor="middle" dominant-baseline="middle">
    {text_lines}
  </text>
  <text x="{footer_x}" y="{footer_y}" font-family="sans-serif" font-size="14"
        fill="{primary}" opacity="0.6" text-anchor="middle">
    placeholder · swap PlaceholderMediaGenerator for a real adapter
  </text>
</svg>"""
        encoded = base64.b64encode(svg.encode()).decode()
        return f"data:image/svg+xml;base64,{encoded}"
