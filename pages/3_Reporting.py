"""
pages/3_Reporting.py — Campaign performance reporting.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database
import services

# ---------------------------------------------------------------------------
# Helpers — defined at TOP before any UI code
# ---------------------------------------------------------------------------

def _promote(campaign_id: int, winner_variant_id: int) -> None:
    """Set the winner to weight 0.8; share remainder among others."""
    variants = database.list_variants(campaign_id)
    active = [v for v in variants if v["status"] == "active"]
    others = [v for v in active if v["id"] != winner_variant_id]
    other_weight = round(0.2 / len(others), 3) if others else 0.0

    platform = services.get_ad_platform("meta")
    for v in active:
        w = 0.8 if v["id"] == winner_variant_id else other_weight
        database.update_variant_weight(v["id"], w)
        if v["external_id"]:
            platform.update_variant_weight(v["external_id"], w)


def _pause(variant_id: int) -> None:
    database.update_variant_status(variant_id, "paused")
    variants = database.list_variants(
        database._DB_PATH  # we'll fetch campaign via a different path
    )


def _pause_variant(variant_id: int) -> None:
    database.update_variant_status(variant_id, "paused")
    # Also tell mock adapter
    v_rows = None
    with database._conn() as con:
        row = con.execute("SELECT external_id FROM variants WHERE id = ?", (variant_id,)).fetchone()
        if row and row["external_id"]:
            services.get_ad_platform("meta").pause_variant(row["external_id"])


def _build_suggestions(summary_df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Return list of (severity, headline, reason) tuples."""
    suggestions: list[tuple[str, str, str]] = []

    if summary_df.empty:
        return suggestions

    avg_roas = summary_df["ROAS"].mean()
    avg_cpa = summary_df["CPA (£)"].mean()

    if avg_roas >= 2.0:
        suggestions.append(("success", "Healthy ROAS", "Current budget is appropriate."))
    if avg_roas < 1.0:
        suggestions.append(
            ("warning", "ROAS below 1.0×", "Investigate before scaling — you're losing money.")
        )

    for _, row in summary_df.iterrows():
        name = row.get("Variant", "")
        ctr = row.get("CTR (%)", 0)
        roas = row.get("ROAS", 0)
        cpa = row.get("CPA (£)", 0)

        if ctr >= 3.0 and roas >= 1.5:
            suggestions.append(("info", f"Scale candidate: {name}", "High CTR + solid ROAS."))
        if avg_cpa > 0 and cpa > 1.6 * avg_cpa:
            suggestions.append(
                ("warning", f"High CPA: {name}", f"CPA £{cpa:.2f} is >1.6× average. Consider pausing.")
            )
        if ctr < 1.0:
            suggestions.append(
                ("warning", f"Low CTR: {name}", "Creative may not be resonating with the audience.")
            )

    return suggestions


def _delta_card(col, label: str, current: float, previous: float, fmt: str) -> None:
    if previous and previous != 0:
        delta_pct = (current - previous) / abs(previous) * 100
        delta_str = f"{delta_pct:+.1f}% vs prev 7d"
    else:
        delta_str = "No prior data"
    col.metric(label, fmt.format(current), delta=delta_str)


def _fetch_window(variant_eid: str, start_offset: int, days: int) -> dict:
    """Aggregate metrics over a window. start_offset=0 means today, 7 means last week."""
    platform = services.get_ad_platform("meta")
    totals = {
        "impressions": 0,
        "clicks": 0,
        "conversions": 0,
        "spend_cents": 0,
        "revenue_cents": 0,
    }
    today = date.today()
    for offset in range(start_offset, start_offset + days):
        day = today - timedelta(days=offset)
        m = platform.fetch_metrics(variant_eid, day)
        for k in totals:
            totals[k] += m.get(k, 0)
    return totals


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Reporting — Agency Platform", layout="wide")
st.title("📊 Reporting")

active_id = st.session_state.get("active_client_id")
if not active_id:
    st.warning("No active client selected. Go to **Clients** first.")
    st.stop()

client = database.get_client(active_id)
if not client:
    st.warning("Client not found.")
    st.stop()

st.caption(f"Active client: **{client['name']}**")

campaigns = database.list_campaigns(active_id)
if not campaigns:
    st.info("No campaigns yet. Create one in **Campaigns**.")
    st.stop()

camp_map = {f"{c['name']} ({c['channel']})": c for c in campaigns}
chosen_label = st.selectbox("Select campaign", list(camp_map.keys()))
camp = camp_map[chosen_label]

variants = database.list_variants(camp["id"])

# ---------------------------------------------------------------------------
# Meta ads reporting
# ---------------------------------------------------------------------------
if camp["channel"] == "meta_ads":
    active_variants = [v for v in variants if v["external_id"]]

    if not active_variants:
        st.info("No variants with external IDs yet. Launch this campaign first.")
        st.stop()

    # Collect current + previous 7-day windows
    rows_current = []
    rows_prev = []
    daily_rows = []

    today = date.today()
    platform = services.get_ad_platform("meta")

    for v in active_variants:
        cur = _fetch_window(v["external_id"], 0, 7)
        prv = _fetch_window(v["external_id"], 7, 7)
        rows_current.append({"variant": v, "metrics": cur})
        rows_prev.append({"variant": v, "metrics": prv})

        for offset in range(7):
            day = today - timedelta(days=offset)
            m = platform.fetch_metrics(v["external_id"], day)
            daily_rows.append(
                {
                    "Date": day.isoformat(),
                    "Variant": v["headline"][:20] + "…" if len(v["headline"]) > 20 else v["headline"],
                    "Spend (£)": m["spend_cents"] / 100,
                }
            )

    # Aggregate headline KPIs
    def _agg(rows):
        agg = {"impressions": 0, "clicks": 0, "conversions": 0, "spend_cents": 0, "revenue_cents": 0}
        for r in rows:
            for k in agg:
                agg[k] += r["metrics"].get(k, 0)
        return agg

    cur_agg = _agg(rows_current)
    prv_agg = _agg(rows_prev)

    cur_spend = cur_agg["spend_cents"] / 100
    prv_spend = prv_agg["spend_cents"] / 100
    cur_rev = cur_agg["revenue_cents"] / 100
    prv_rev = prv_agg["revenue_cents"] / 100
    cur_conv = cur_agg["conversions"]
    prv_conv = prv_agg["conversions"]
    cur_roas = cur_rev / cur_spend if cur_spend else 0.0
    prv_roas = prv_rev / prv_spend if prv_spend else 0.0

    st.subheader("Headline KPIs — current 7 days")
    kc1, kc2, kc3, kc4 = st.columns(4)
    _delta_card(kc1, "Spend (£)", cur_spend, prv_spend, "£{:.2f}")
    _delta_card(kc2, "Revenue (£)", cur_rev, prv_rev, "£{:.2f}")
    _delta_card(kc3, "Conversions", cur_conv, prv_conv, "{:.0f}")
    _delta_card(kc4, "ROAS", cur_roas, prv_roas, "{:.2f}×")

    st.divider()

    # Per-variant table
    st.subheader("Per-variant performance (7d)")
    summary_rows = []
    for r in rows_current:
        v = r["variant"]
        m = r["metrics"]
        spend = m["spend_cents"] / 100
        rev = m["revenue_cents"] / 100
        impr = m["impressions"]
        clicks = m["clicks"]
        conv = m["conversions"]
        ctr = (clicks / impr * 100) if impr else 0.0
        cvr = (conv / clicks * 100) if clicks else 0.0
        cpa = spend / conv if conv else 0.0
        roas = rev / spend if spend else 0.0
        summary_rows.append(
            {
                "Variant": v["headline"][:30],
                "Impressions": impr,
                "Clicks": clicks,
                "CTR (%)": round(ctr, 2),
                "Conversions": conv,
                "CVR (%)": round(cvr, 2),
                "Spend (£)": round(spend, 2),
                "CPA (£)": round(cpa, 2),
                "Revenue (£)": round(rev, 2),
                "ROAS": round(roas, 2),
                "_variant_id": v["id"],
                "_ext_id": v["external_id"],
                "Weight": v["weight"],
            }
        )

    summary_df = pd.DataFrame(summary_rows)
    display_cols = [c for c in summary_df.columns if not c.startswith("_")]
    st.dataframe(summary_df[display_cols], use_container_width=True)

    # Daily spend chart
    st.subheader("Daily spend by variant (last 7 days)")
    if daily_rows:
        daily_df = pd.DataFrame(daily_rows)
        pivot = daily_df.pivot_table(index="Date", columns="Variant", values="Spend (£)", aggfunc="sum").fillna(0)
        st.line_chart(pivot)

    st.divider()

    # Suggestions
    st.subheader("💡 Suggestions")
    st.caption(
        "Deterministic heuristics. V2 replaces this section with Thompson sampling on real conversion data."
    )
    suggestions = _build_suggestions(summary_df[display_cols])
    if suggestions:
        for severity, headline, reason in suggestions:
            if severity == "success":
                st.success(f"**{headline}** — {reason}")
            elif severity == "warning":
                st.warning(f"**{headline}** — {reason}")
            else:
                st.info(f"**{headline}** — {reason}")
    else:
        st.info("No suggestions at this time.")

    st.divider()

    # A/B promotion
    st.subheader("Manual A/B promotion")
    if not summary_df.empty:
        best_row = summary_df.loc[summary_df["ROAS"].idxmax()]
        st.markdown(
            f"🏆 Suggested winner: **{best_row['Variant']}** (ROAS {best_row['ROAS']:.2f}×)"
        )

        btn_cols = st.columns(len(summary_df))
        for i, row in summary_df.iterrows():
            vid = row["_variant_id"]
            with btn_cols[i]:
                st.markdown(f"**{row['Variant'][:18]}**")
                if st.button("Promote", key=f"promote_{vid}"):
                    _promote(camp["id"], vid)
                    st.success("Weights updated.")
                    st.rerun()
                if st.button("Pause", key=f"pause_{vid}"):
                    _pause_variant(vid)
                    st.warning("Variant paused.")
                    st.rerun()

# ---------------------------------------------------------------------------
# Email reporting
# ---------------------------------------------------------------------------
elif camp["channel"] == "email":
    st.subheader("Email campaign metrics")
    email_provider = services.get_email_provider("klaviyo")

    if camp["external_id"]:
        em = email_provider.fetch_metrics(camp["external_id"])
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Recipients", f"{em['recipients']:,}")
        e2.metric("Opens", f"{em['opens']:,}")
        e3.metric("Open rate", f"{em['open_rate'] * 100:.1f}%")
        e4.metric("Click rate", f"{em['click_rate'] * 100:.1f}%")
    else:
        st.info("Campaign has no external ID — was it launched via the Campaigns page?")

    st.subheader("Variants used")
    for v in variants:
        with st.expander(v["headline"] or f"Variant {v['id']}"):
            st.markdown(v["body"] or "—")
            st.caption(f"CTA: {v['cta']}")
else:
    st.info(f"Reporting not yet implemented for channel: {camp['channel']}")
