"""
app.py — Entry point for the Agency Platform V3 Streamlit app.
"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database

database.init_db()

st.set_page_config(
    page_title="Agency Platform V3",
    page_icon="🚀",
    layout="wide",
)

st.title("🚀 Agency Platform V3")
st.caption("Architectural slice — every layer end-to-end, one feature per layer.")

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
clients = database.list_clients()
all_campaigns = database.list_campaigns()
running = [c for c in all_campaigns if c["status"] == "running"]

k1, k2, k3 = st.columns(3)
k1.metric("Total Clients", len(clients))
k2.metric("Total Campaigns", len(all_campaigns))
k3.metric("Running Campaigns", len(running))

st.divider()

# ---------------------------------------------------------------------------
# What V3 demonstrates
# ---------------------------------------------------------------------------
st.subheader("What V3 demonstrates")
st.markdown(
    """
V3 is an **architectural slice** — not a full product. It proves that every
layer of a production marketing platform can talk to each other correctly,
end-to-end, with one minimum-viable feature per layer:

| Layer | Feature | Implementation |
|---|---|---|
| **UI** | Multi-page Streamlit app | `pages/` |
| **Registry** | Swappable adapters via service locator | `services.py` |
| **Interfaces** | Typed contracts, no vendor leakage | `interfaces.py` |
| **Adapters** | Mock Meta, Mock Klaviyo, real Anthropic | `adapters.py` |
| **Persistence** | SQLite (Postgres-compatible DDL) | `database.py` |

**What it doesn't do:** real ad buying, real email delivery, production
auth, multi-tenancy, billing, or A/B statistics with real traffic.
"""
)

# ---------------------------------------------------------------------------
# Architecture diagram
# ---------------------------------------------------------------------------
st.subheader("Architecture")
st.code(
    """
┌─────────────────────────────────────────┐
│              UI Layer                   │
│   pages/1_Clients.py                    │
│   pages/2_Campaigns.py                  │
│   pages/3_Reporting.py                  │
│   pages/4_Settings.py                   │
└────────────────────┬────────────────────┘
                     │ calls get_*()
┌────────────────────▼────────────────────┐
│           Registry (services.py)        │
│   get_ad_platform()  get_llm()          │
│   get_email_provider() get_media_gen()  │
└────────────────────┬────────────────────┘
                     │ returns
┌────────────────────▼────────────────────┐
│       Interfaces (interfaces.py)        │
│   AdPlatform  EmailProvider             │
│   LLMProvider  MediaGenerator           │
└────────────────────┬────────────────────┘
                     │ implemented by
┌────────────────────▼────────────────────┐
│        Adapters (adapters.py)           │
│   MockMetaAdPlatform                    │
│   MockKlaviyoEmailProvider              │
│   AnthropicLLMProvider  (real API)      │
│   PlaceholderMediaGenerator             │
└─────────────────────────────────────────┘
""",
    language="text",
)

st.divider()
st.caption(
    "Navigate using the sidebar. Start with **Clients** to select or create a client, "
    "then **Campaigns** to generate and launch, then **Reporting** to view metrics."
)
