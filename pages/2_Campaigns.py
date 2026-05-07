"""
pages/2_Campaigns.py — Campaign creation and listing.
"""
from __future__ import annotations

import random
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database
import templates as tmpl
import services
from interfaces import (
    AdCampaignDraft,
    CreativeAsset,
    CopyRequest,
    EmailCampaignDraft,
    ImageRequest,
)

# ---------------------------------------------------------------------------
# Helpers — defined at TOP before any UI code
# ---------------------------------------------------------------------------

def _launch_campaign(client: dict, pending: dict) -> None:
    """Insert campaign + variants into DB, call the appropriate adapter."""
    channel = pending["channel"]
    daily_budget_cents = pending.get("daily_budget_cents", 0)

    campaign_id = database.create_campaign(
        client_id=client["id"],
        name=pending["campaign_name"],
        objective=pending["objective"],
        channel=channel,
        daily_budget_cents=daily_budget_cents,
        status="launching",
    )

    variants = pending["variants"]
    images = pending["images"]

    if channel == "meta_ads":
        ad_accounts = database.list_ad_accounts(client["id"])
        account_eid = ad_accounts[0]["external_account_id"] if ad_accounts else "act_unknown"

        creative_assets = [
            CreativeAsset(
                headline=v.headline,
                body=v.body,
                cta=v.cta,
                image_url=images[i] if i < len(images) else None,
            )
            for i, v in enumerate(variants)
        ]
        draft = AdCampaignDraft(
            name=pending["campaign_name"],
            objective=pending["objective"],
            daily_budget_cents=daily_budget_cents,
            variants=creative_assets,
        )
        platform = services.get_ad_platform("meta")
        result = platform.launch_campaign(account_eid, draft)
        database.update_campaign_external_id(campaign_id, result.external_id, result.status)

        for i, v in enumerate(variants):
            ext_id = result.variant_external_ids[i] if i < len(result.variant_external_ids) else None
            true_ctr = random.uniform(0.012, 0.038)
            true_cvr = random.uniform(0.03, 0.09)
            database.create_variant(
                campaign_id=campaign_id,
                name=f"Variant {i + 1}",
                headline=v.headline,
                body=v.body,
                cta=v.cta,
                image_url=images[i] if i < len(images) else None,
                true_ctr=true_ctr,
                true_cvr=true_cvr,
                external_id=ext_id,
            )

    else:  # email
        email_accounts = database.list_email_accounts(client["id"])
        account_eid = email_accounts[0]["external_account_id"] if email_accounts else "klav_unknown"

        first_variant = variants[0]
        draft = EmailCampaignDraft(
            name=pending["campaign_name"],
            subject=first_variant.headline,
            html_body=f"<p>{first_variant.body}</p><p><strong>{first_variant.cta}</strong></p>",
            sender_name=client["name"],
            sender_email="hello@example.com",
            audience_id="aud_all",
        )
        provider = services.get_email_provider("klaviyo")
        result = provider.send_campaign(account_eid, draft)
        database.update_campaign_external_id(campaign_id, result.external_id, result.status)

        for i, v in enumerate(variants):
            database.create_variant(
                campaign_id=campaign_id,
                name=f"Variant {i + 1}",
                headline=v.headline,
                body=v.body,
                cta=v.cta,
                image_url=images[i] if i < len(images) else None,
                external_id=result.external_id if i == 0 else None,
            )

    st.session_state.pop("pending_campaign", None)
    st.success(f"Campaign launched! External ID: `{result.external_id}`")


def _get_audience(client, template: tmpl.CampaignTemplate | None) -> str:
    if client["target_audience"]:
        return client["target_audience"]
    if template and template.audience_hint:
        return template.audience_hint
    return "General consumers."


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Campaigns — Agency Platform", layout="wide")
st.title("📣 Campaigns")

active_id = st.session_state.get("active_client_id")
if not active_id:
    st.warning("No active client selected. Go to **Clients** first.")
    st.stop()

client = database.get_client(active_id)
if not client:
    st.warning("Active client not found. Please re-select.")
    st.stop()

st.caption(f"Active client: **{client['name']}**")

tab_create, tab_existing = st.tabs(["Create campaign", "Existing campaigns"])

# ---------------------------------------------------------------------------
# Tab 1 — Create campaign
# ---------------------------------------------------------------------------
with tab_create:
    all_templates = tmpl.list_templates()
    template_options = ["— start from scratch —"] + [
        f"{t.name} ({t.category})" for t in all_templates
    ]
    template_choice = st.selectbox("Start from a template", template_options)

    selected_template: tmpl.CampaignTemplate | None = None
    if template_choice != "— start from scratch —":
        idx = template_options.index(template_choice) - 1
        selected_template = all_templates[idx]
        with st.expander("Template details"):
            st.markdown(f"**{selected_template.name}** — {selected_template.description}")
            st.markdown(f"Sample offer: *{selected_template.product_placeholder}*")
            st.markdown(f"Audience hint: *{selected_template.audience_hint}*")

    # Pending campaign review
    pending = st.session_state.get("pending_campaign")
    if pending:
        st.subheader("📝 Review generated campaign")
        st.markdown(f"**{pending['campaign_name']}** — {pending['channel']} / {pending['objective']}")
        variants = pending["variants"]
        images = pending["images"]
        cols = st.columns(min(len(variants), 3))
        for i, v in enumerate(variants):
            col = cols[i % len(cols)]
            with col:
                if i < len(images) and images[i]:
                    st.image(images[i], use_container_width=True)
                st.markdown(f"**{v.headline}**")
                st.markdown(v.body)
                st.caption(f"CTA: {v.cta}")

        st.markdown("---")
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("🚀 Launch campaign", type="primary"):
                with st.spinner("Launching…"):
                    _launch_campaign(client, pending)
                st.rerun()
        with btn_col2:
            if st.button("🗑️ Discard"):
                st.session_state.pop("pending_campaign", None)
                st.rerun()
        st.stop()

    # Campaign creation form
    st.subheader("Campaign settings")
    with st.form("campaign_form"):
        default_name = selected_template.name if selected_template else ""
        campaign_name = st.text_input("Campaign name *", value=default_name)

        channel_options = ["meta_ads", "email"]
        default_channel = selected_template.default_channel if selected_template else "meta_ads"
        channel = st.selectbox(
            "Channel",
            channel_options,
            index=channel_options.index(default_channel),
        )

        objective_options = ["conversions", "leads", "awareness", "traffic"]
        default_obj = selected_template.default_objective if selected_template else "conversions"
        if default_obj not in objective_options:
            objective_options.insert(0, default_obj)
        objective = st.selectbox(
            "Objective",
            objective_options,
            index=objective_options.index(default_obj),
        )

        daily_budget_gbp = 0
        if channel == "meta_ads":
            default_budget = selected_template.suggested_budget_gbp if selected_template else 50
            daily_budget_gbp = st.number_input(
                "Daily budget (£)", min_value=1, max_value=10000, value=max(1, default_budget)
            )

        default_product = selected_template.product_placeholder if selected_template else ""
        product = st.text_area(
            "Product / offer *",
            value=default_product,
            placeholder="Describe what you're promoting…",
            height=80,
        )

        angle_options = [
            "scarcity",
            "social proof",
            "education",
            "FOMO",
            "story / origin",
            "authority",
            "curiosity",
        ]
        default_angle = selected_template.default_angle if selected_template else "social proof"
        if default_angle not in angle_options:
            angle_options.insert(0, default_angle)
        angle = st.selectbox(
            "Creative angle",
            angle_options,
            index=angle_options.index(default_angle),
        )

        default_n = selected_template.default_n_variants if selected_template else 3
        n_variants = st.slider("Number of variants", 2, 6, value=default_n)

        submitted = st.form_submit_button("Generate copy ✨", type="primary")

    if submitted:
        if not campaign_name.strip():
            st.error("Campaign name is required.")
        elif not product.strip():
            st.error("Product / offer description is required.")
        else:
            audience = _get_audience(client, selected_template)
            brand_voice = client["brand_voice"] or "Professional and engaging."

            req = CopyRequest(
                brand_voice=brand_voice,
                target_audience=audience,
                product=product,
                angle=angle,
                n_variants=n_variants,
            )

            with st.spinner("Generating copy with Claude…"):
                try:
                    llm = services.get_llm()
                    copy_variants = llm.generate_copy(req)
                    cost = llm.last_usage.get("cost_cents", 0)
                    model = getattr(llm, "_model", "claude-sonnet-4-6")

                    database.record_generation(
                        client_id=active_id,
                        kind="copy",
                        prompt=f"{angle} | {product[:100]}",
                        output=f"{len(copy_variants)} variants",
                        model=model,
                        cost_cents=cost,
                    )
                except Exception as exc:
                    st.error(f"Copy generation failed: {exc}")
                    st.stop()

            img_gen = services.get_media_generator()
            images = []
            with st.spinner("Generating placeholder images…"):
                for v in copy_variants:
                    img_req = ImageRequest(
                        description=f"{v.headline} — {product[:60]}",
                        aspect_ratio="1:1" if channel == "meta_ads" else "9:16",
                    )
                    img_url = img_gen.generate_image(img_req)
                    images.append(img_url)
                    database.record_generation(
                        client_id=active_id,
                        kind="image",
                        prompt=img_req.description,
                        output=f"svg:{len(img_url)} chars",
                        model="placeholder",
                        cost_cents=0,
                    )

            st.session_state["pending_campaign"] = {
                "campaign_name": campaign_name,
                "channel": channel,
                "objective": objective,
                "daily_budget_cents": daily_budget_gbp * 100,
                "variants": copy_variants,
                "images": images,
            }
            st.rerun()

# ---------------------------------------------------------------------------
# Tab 2 — Existing campaigns
# ---------------------------------------------------------------------------
with tab_existing:
    campaigns = database.list_campaigns(active_id)
    if not campaigns:
        st.info("No campaigns yet. Create one in the 'Create campaign' tab.")
    else:
        for camp in campaigns:
            variants = database.list_variants(camp["id"])
            status_icon = {"running": "🟢", "draft": "⚪", "launching": "🟡", "paused": "🔴"}.get(
                camp["status"], "❓"
            )
            with st.expander(
                f"{status_icon} **{camp['name']}** — {camp['channel']} / {camp['objective']}"
            ):
                c1, c2, c3 = st.columns(3)
                c1.markdown(f"**Status:** {camp['status']}")
                c2.markdown(f"**Budget:** £{camp['daily_budget_cents'] / 100:.0f}/day")
                c3.markdown(f"**Variants:** {len(variants)}")
                if camp["external_id"]:
                    st.caption(f"External ID: `{camp['external_id']}`")
                st.caption(f"Created: {camp['created_at']}")
