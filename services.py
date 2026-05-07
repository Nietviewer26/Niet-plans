"""
services.py — Registry for all external service adapters.
Pages call get_*() functions; they never instantiate adapters directly.
"""
from __future__ import annotations

import os

from interfaces import AdPlatform, EmailProvider, LLMProvider, MediaGenerator

_ad_platforms: dict[str, AdPlatform] = {}
_email_providers: dict[str, EmailProvider] = {}
_llm_providers: dict[str, LLMProvider] = {}
_media_generators: dict[str, MediaGenerator] = {}


def get_ad_platform(name: str) -> AdPlatform:
    if name not in _ad_platforms:
        if name == "meta":
            from adapters import MockMetaAdPlatform
            _ad_platforms[name] = MockMetaAdPlatform()
        else:
            raise ValueError(f"Unknown ad platform: {name!r}")
    return _ad_platforms[name]


def get_email_provider(name: str) -> EmailProvider:
    if name not in _email_providers:
        if name == "klaviyo":
            from adapters import MockKlaviyoEmailProvider
            _email_providers[name] = MockKlaviyoEmailProvider()
        else:
            raise ValueError(f"Unknown email provider: {name!r}")
    return _email_providers[name]


def get_llm(name: str = "anthropic") -> LLMProvider:
    if name not in _llm_providers:
        if name == "anthropic":
            # Fall back to MockLLMProvider when no API key is configured so
            # the platform demos end-to-end without a billing account.
            if os.environ.get("ANTHROPIC_API_KEY"):
                from adapters import AnthropicLLMProvider
                _llm_providers[name] = AnthropicLLMProvider()
            else:
                from adapters import MockLLMProvider
                _llm_providers[name] = MockLLMProvider()
        elif name == "mock":
            from adapters import MockLLMProvider
            _llm_providers[name] = MockLLMProvider()
        else:
            raise ValueError(f"Unknown LLM provider: {name!r}")
    return _llm_providers[name]


def get_media_generator(name: str = "placeholder") -> MediaGenerator:
    if name not in _media_generators:
        if name == "placeholder":
            from adapters import PlaceholderMediaGenerator
            _media_generators[name] = PlaceholderMediaGenerator()
        else:
            raise ValueError(f"Unknown media generator: {name!r}")
    return _media_generators[name]
