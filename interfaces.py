"""
interfaces.py — Abstract contracts for all external services.
Pages and database code import ONLY from this module, never from vendor SDKs.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CreativeAsset:
    headline: str
    body: str
    cta: str
    image_url: str | None = None


@dataclass
class AdCampaignDraft:
    name: str
    objective: str
    daily_budget_cents: int
    variants: list[CreativeAsset]


@dataclass
class LaunchResult:
    external_id: str
    status: str
    variant_external_ids: list[str] = field(default_factory=list)


@dataclass
class EmailCampaignDraft:
    name: str
    subject: str
    html_body: str
    sender_name: str
    sender_email: str
    audience_id: str


@dataclass
class CopyRequest:
    brand_voice: str
    target_audience: str
    product: str
    angle: str
    n_variants: int = 3


@dataclass
class CopyVariant:
    headline: str
    body: str
    cta: str


@dataclass
class ImageRequest:
    description: str
    aspect_ratio: str = "1:1"
    style_hint: str | None = None


# ---------------------------------------------------------------------------
# Abstract base classes
# ---------------------------------------------------------------------------

class AdPlatform(ABC):
    name: str

    @abstractmethod
    def launch_campaign(self, ad_account_external_id: str, draft: AdCampaignDraft) -> LaunchResult:
        ...

    @abstractmethod
    def pause_variant(self, eid: str) -> None:
        ...

    @abstractmethod
    def update_variant_weight(self, eid: str, weight: float) -> None:
        ...

    @abstractmethod
    def fetch_metrics(self, eid: str, day) -> dict:
        ...


class EmailProvider(ABC):
    name: str

    @abstractmethod
    def send_campaign(self, account_eid: str, draft: EmailCampaignDraft) -> LaunchResult:
        ...

    @abstractmethod
    def fetch_metrics(self, eid: str) -> dict:
        ...

    @abstractmethod
    def list_audiences(self, account_eid: str) -> list[dict]:
        ...


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate_copy(self, req: CopyRequest) -> list[CopyVariant]:
        ...

    @abstractmethod
    def generate_subject_lines(self, brand_voice: str, body_summary: str, n: int = 5) -> list[str]:
        ...


class MediaGenerator(ABC):
    name: str

    @abstractmethod
    def generate_image(self, req: ImageRequest) -> str:
        """Returns a URL or data URI."""
        ...
