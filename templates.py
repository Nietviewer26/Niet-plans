"""
templates.py — Campaign templates with sensible defaults.
NOTE: No success_rate or avg_roi fields — performance numbers come from
real measured campaigns, never invented configuration-time stats.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CampaignTemplate:
    id: str
    name: str
    category: str
    description: str
    default_channel: str
    default_objective: str
    default_angle: str
    default_n_variants: int
    suggested_budget_gbp: int
    product_placeholder: str
    audience_hint: str


_TEMPLATES: list[CampaignTemplate] = [
    CampaignTemplate(
        id="ecom_holiday",
        name="Holiday e-commerce push",
        category="E-commerce",
        description=(
            "Drive sales during peak seasonal windows with urgency-led creative. "
            "Best deployed 2–3 weeks before key dates with a clear offer deadline."
        ),
        default_channel="meta_ads",
        default_objective="conversions",
        default_angle="scarcity",
        default_n_variants=4,
        suggested_budget_gbp=80,
        product_placeholder="20% off all orders over £40 — ends midnight Sunday",
        audience_hint="Online shoppers who have purchased gifts in the last 12 months, aged 25–55.",
    ),
    CampaignTemplate(
        id="saas_trial",
        name="SaaS free trial acquisition",
        category="SaaS",
        description=(
            "Acquire trial signups by leading with peer validation and risk-reversal. "
            "Pair with a short onboarding sequence to convert trials to paid."
        ),
        default_channel="meta_ads",
        default_objective="leads",
        default_angle="social proof",
        default_n_variants=3,
        suggested_budget_gbp=120,
        product_placeholder="Start your free 14-day trial — no credit card required",
        audience_hint="Founders, ops managers and team leads at 10–200-person companies.",
    ),
    CampaignTemplate(
        id="local_service",
        name="Local service business",
        category="Local",
        description=(
            "Generate enquiries for service businesses by emphasising local credibility "
            "and social proof. Works well for tradespeople, clinics, and studios."
        ),
        default_channel="meta_ads",
        default_objective="leads",
        default_angle="social proof",
        default_n_variants=3,
        suggested_budget_gbp=40,
        product_placeholder="Rated 4.9 ★ by 200+ local customers — book your free consultation",
        audience_hint="Residents within 10 miles of the business, aged 28–65, homeowners.",
    ),
    CampaignTemplate(
        id="b2b_leads",
        name="B2B lead generation",
        category="B2B",
        description=(
            "Educate and qualify senior decision-makers with content-led creative. "
            "Lower click volumes but higher-intent leads; pair with a gated asset."
        ),
        default_channel="meta_ads",
        default_objective="leads",
        default_angle="education",
        default_n_variants=3,
        suggested_budget_gbp=200,
        product_placeholder="Download the 2024 benchmark report — free for qualified teams",
        audience_hint="Directors, VPs and C-suite at companies with 50+ employees, B2B sector.",
    ),
    CampaignTemplate(
        id="email_winback",
        name="Email win-back",
        category="Email",
        description=(
            "Re-engage subscribers who haven't opened in 90+ days by telling the "
            "brand's origin story and offering a genuine reason to return."
        ),
        default_channel="email",
        default_objective="awareness",
        default_angle="story / origin",
        default_n_variants=3,
        suggested_budget_gbp=0,
        product_placeholder="We've missed you — here's why we started and what's new",
        audience_hint="Lapsed customers or subscribers inactive for 90 days or more.",
    ),
    CampaignTemplate(
        id="app_install",
        name="Mobile app install",
        category="Mobile",
        description=(
            "Drive app installs with FOMO-led creative showcasing a core feature "
            "or limited-time benefit. Short copy, strong visual."
        ),
        default_channel="meta_ads",
        default_objective="conversions",
        default_angle="FOMO",
        default_n_variants=4,
        suggested_budget_gbp=100,
        product_placeholder="Join 50,000 users already saving time — free on iOS & Android",
        audience_hint="Mobile-first adults aged 18–40 who use competitor apps or similar tools.",
    ),
]


def list_templates() -> list[CampaignTemplate]:
    return list(_TEMPLATES)


def get_template(template_id: str) -> CampaignTemplate | None:
    return next((t for t in _TEMPLATES if t.id == template_id), None)
