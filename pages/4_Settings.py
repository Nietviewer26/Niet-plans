"""
pages/4_Settings.py — Settings: vendor config, white-label branding, API usage.
"""
from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Settings — Agency Platform", layout="wide")
st.title("⚙️ Settings")

tab_vendors, tab_brand, tab_usage = st.tabs(["Vendors", "White-label", "API usage"])

# ---------------------------------------------------------------------------
# Tab 1 — Vendors
# ---------------------------------------------------------------------------
with tab_vendors:
    st.subheader("Provider status")

    has_anthropic_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

    providers = [
        {
            "name": "Meta Ads",
            "kind": "Ad Platform",
            "status": "mock",
            "detail": "MockMetaAdPlatform — deterministic metrics, no real spend.",
        },
        {
            "name": "Klaviyo",
            "kind": "Email Provider",
            "status": "mock",
            "detail": "MockKlaviyoEmailProvider — hash-seeded metrics, no real sends.",
        },
        {
            "name": "Anthropic Claude" if has_anthropic_key else "LLM (mock fallback)",
            "kind": "LLM Provider",
            "status": "real" if has_anthropic_key else "mock",
            "detail": (
                "Real Anthropic adapter — API calls using claude-sonnet-4-6."
                if has_anthropic_key
                else "MockLLMProvider — deterministic templated copy, no API calls. "
                     "Set ANTHROPIC_API_KEY in Streamlit secrets to switch to real Claude."
            ),
        },
        {
            "name": "Image Generation",
            "kind": "Media Generator",
            "status": "mock",
            "detail": "PlaceholderMediaGenerator — SVG data URIs, no real image gen.",
        },
    ]

    icon_map = {"real": "🟢", "mock": "🟡", "broken": "🔴"}

    for p in providers:
        icon = icon_map[p["status"]]
        st.markdown(f"**{icon} {p['name']}** ({p['kind']})")
        st.caption(p["detail"])
        st.markdown("---")

    st.subheader("How to swap in a real adapter")
    st.markdown(
        """
To graduate a mock adapter to production:

1. Add a new class in `adapters.py` that inherits the relevant interface, e.g.:
   ```python
   class RealMetaAdPlatform(AdPlatform):
       name = "meta"
       def launch_campaign(self, ...): ...
   ```
2. Change **one line** in `services.py`:
   ```python
   # Before:
   _ad_platforms[name] = MockMetaAdPlatform()
   # After:
   _ad_platforms[name] = RealMetaAdPlatform()
   ```
3. Add the required credentials to `.env` and restart.

No changes needed in any `pages/` file — that's the architecture guarantee.
"""
    )

# ---------------------------------------------------------------------------
# Tab 2 — White-label branding
# ---------------------------------------------------------------------------
with tab_brand:
    st.subheader("Client branding")

    clients = database.list_clients()
    if not clients:
        st.info("No clients yet.")
        st.stop()

    client_names = [c["name"] for c in clients]
    chosen_name = st.selectbox("Select client", client_names, key="brand_client")
    chosen_client = next(c for c in clients if c["name"] == chosen_name)
    branding = database.get_branding(chosen_client["id"])

    with st.form("branding_form"):
        brand_name = st.text_input(
            "Brand name override",
            value=branding.get("brand_name") or chosen_client["name"],
            help="Displayed instead of the client name in branded outputs.",
        )
        col1, col2 = st.columns(2)
        with col1:
            primary_color = st.color_picker(
                "Primary colour",
                value=branding.get("primary_color") or "#1F2937",
            )
        with col2:
            accent_color = st.color_picker(
                "Accent colour",
                value=branding.get("accent_color") or "#10B981",
            )
        logo_url = st.text_input(
            "Logo URL (optional)",
            value=branding.get("logo_url") or "",
        )
        saved = st.form_submit_button("Save branding")
        if saved:
            database.upsert_branding(
                client_id=chosen_client["id"],
                brand_name=brand_name.strip() or None,
                primary_color=primary_color,
                accent_color=accent_color,
                logo_url=logo_url.strip() or None,
            )
            st.success("Branding saved.")

    st.subheader("Live preview")
    preview_html = f"""
    <div style="
        border-left: 6px solid {primary_color};
        padding: 16px 20px;
        background: {accent_color}22;
        border-radius: 4px;
        font-family: sans-serif;
        margin: 8px 0;
    ">
        <div style="font-size: 22px; font-weight: 700; color: {primary_color};">
            {brand_name}
        </div>
        <div style="font-size: 13px; color: #555; margin: 6px 0;">
            Sample tagline — your brand, your voice.
        </div>
        <button style="
            background: {accent_color};
            color: #fff;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            font-size: 14px;
            cursor: pointer;
            margin-top: 8px;
        ">Take action</button>
    </div>
    """
    st.markdown(preview_html, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tab 3 — API usage
# ---------------------------------------------------------------------------
with tab_usage:
    st.subheader("API usage — last 30 days")
    summary = database.usage_summary(30)

    u1, u2 = st.columns(2)
    u1.metric("Total generations", summary["total_count"])
    total_cost_gbp = summary["total_cost_cents"] / 100
    u2.metric("Estimated cost", f"£{total_cost_gbp:.4f}")

    st.subheader("Breakdown by kind")
    if summary["by_kind"]:
        for kind, count in summary["by_kind"].items():
            st.markdown(f"- **{kind}**: {count} generation{'s' if count != 1 else ''}")
    else:
        st.info("No generations recorded yet.")
