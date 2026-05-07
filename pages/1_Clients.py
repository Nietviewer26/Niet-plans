"""
pages/1_Clients.py — Client management page.
"""
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

import database

# ---------------------------------------------------------------------------
# Helpers (must be defined before any UI code)
# ---------------------------------------------------------------------------

def _set_active(client_id: int) -> None:
    st.session_state["active_client_id"] = client_id


def _create_client_and_activate(name: str, industry: str, brand_voice: str, audience: str) -> None:
    new_id = database.create_client(
        name=name,
        industry=industry,
        brand_voice=brand_voice,
        target_audience=audience,
    )
    st.session_state["active_client_id"] = new_id


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Clients — Agency Platform", layout="wide")
st.title("👥 Clients")

clients = database.list_clients()
client_map = {c["name"]: c["id"] for c in clients}

# Active client selectbox
st.subheader("Active client")
if clients:
    names = [c["name"] for c in clients]
    current_id = st.session_state.get("active_client_id")
    current_name = next((c["name"] for c in clients if c["id"] == current_id), names[0])
    if current_name not in names:
        current_name = names[0]
    chosen = st.selectbox("Select active client", names, index=names.index(current_name))
    chosen_id = client_map[chosen]
    if chosen_id != st.session_state.get("active_client_id"):
        _set_active(chosen_id)
        st.rerun()
else:
    st.info("No clients yet. Create one below.")

# Active client details
active_id = st.session_state.get("active_client_id")
if active_id:
    client = database.get_client(active_id)
    if client:
        st.divider()
        st.subheader(f"📋 {client['name']}")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Industry:** {client['industry'] or '—'}")
            st.markdown(f"**Target audience:** {client['target_audience'] or '—'}")
        with c2:
            st.markdown(f"**Brand voice:** {client['brand_voice'] or '—'}")

        # Connected accounts
        st.subheader("Connected accounts")
        ad_accounts = database.list_ad_accounts(active_id)
        email_accounts = database.list_email_accounts(active_id)
        if ad_accounts or email_accounts:
            for acct in ad_accounts:
                st.markdown(
                    f"🟢 **{acct['platform'].upper()}** ad account — `{acct['external_account_id']}` "
                    f"({acct['name'] or 'unnamed'})"
                )
            for acct in email_accounts:
                st.markdown(
                    f"🟢 **{acct['provider'].upper()}** email account — `{acct['external_account_id']}` "
                    f"({acct['name'] or 'unnamed'})"
                )
        else:
            st.info("No connected accounts. Add them in Settings.")

st.divider()

# ---------------------------------------------------------------------------
# Create new client
# ---------------------------------------------------------------------------
st.subheader("➕ Create new client")
with st.form("new_client_form", clear_on_submit=True):
    new_name = st.text_input("Client name *", placeholder="Acme Coffee Co.")
    new_industry = st.text_input("Industry", placeholder="Specialty coffee, DTC")
    new_audience = st.text_area(
        "Target audience",
        placeholder="Coffee enthusiasts aged 28–55, urban, willing to spend £15+ per bag.",
        height=80,
    )
    new_voice = st.text_area(
        "Brand voice",
        placeholder="Warm, knowledgeable, slightly nerdy. UK English.",
        height=80,
    )
    submitted = st.form_submit_button("Create client")
    if submitted:
        if not new_name.strip():
            st.error("Client name is required.")
        else:
            _create_client_and_activate(new_name.strip(), new_industry, new_voice, new_audience)
            st.success(f"Client '{new_name}' created and set as active.")
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# All clients
# ---------------------------------------------------------------------------
st.subheader("All clients")
if clients:
    for c in clients:
        active_badge = " 🔵 **active**" if c["id"] == st.session_state.get("active_client_id") else ""
        with st.expander(f"{c['name']}{active_badge}"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Industry:** {c['industry'] or '—'}")
                st.markdown(f"**Audience:** {c['target_audience'] or '—'}")
                st.markdown(f"**Brand voice:** {c['brand_voice'] or '—'}")
                st.caption(f"Created: {c['created_at']}")
            with col2:
                if c["id"] != st.session_state.get("active_client_id"):
                    if st.button("Set active", key=f"activate_{c['id']}"):
                        _set_active(c["id"])
                        st.rerun()
else:
    st.info("No clients yet.")
