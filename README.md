# Agency Platform V3

**Deployed at:** https://niet-plans.streamlit.app

An architectural slice of a production AI marketing agency platform.
Every layer talks end-to-end; one minimum-viable feature per layer.

---

## Deployment notes (Streamlit Community Cloud)

- Entry point is `app.py` at the repo root.
- Set `ANTHROPIC_API_KEY` in **Advanced settings → Secrets** to use real
  Claude. Without it, the platform automatically falls back to
  `MockLLMProvider` — deterministic templated ad copy, no API calls,
  shown as 🟡 mock in Settings → Vendors. This lets the full app demo
  end-to-end without a billing account.
- **`agency.db` is ephemeral.** Streamlit Community Cloud has no persistent
  disk — the SQLite file is recreated (and re-seeds the demo client) on
  every container restart. Any clients, campaigns, or generations created
  through the UI are lost on restart.
- For persistence, move to a host with a mounted disk (Railway, Render) or
  swap SQLite for Postgres. The DDL in `database.py` is already
  Postgres-compatible.

---

## What V3 proves

- **Interface isolation works.** Pages never import vendor names. Swap adapters by changing one line in `services.py`.
- **Real LLM calls work.** Anthropic Claude generates ad copy via a typed `CopyRequest → list[CopyVariant]` contract.
- **Mock adapters are deterministic.** Meta metrics are hash-seeded; two runs on the same day produce the same numbers — useful for demos.
- **Streamlit multi-page architecture scales.** Each page is a self-contained module; helpers are defined before UI code to avoid NameError on click.
- **No invented performance metrics.** There are no `success_rate` or `avg_roi` fields on templates. All performance numbers come from measured campaign data.

## What V3 does NOT do

- Real ad buying or email delivery
- Production authentication or multi-tenancy
- Billing, usage caps, or quota management
- A/B statistics with real traffic (heuristic suggestions only — see caption in Reporting)
- Image generation (SVG placeholder; swap `PlaceholderMediaGenerator` for a real adapter)

---

## Setup

```bash
# 1. Clone / unzip
cd agency_platform

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 5. Run
streamlit run app.py
```

The app opens at http://localhost:8501.
`agency.db` is created automatically on first run.

---

## Walkthrough order

1. **Clients** — select "Demo Boutique Coffee Co." or create your own client.
2. **Campaigns** — pick a template, adjust fields, click "Generate copy ✨". Review the variants, then "Launch campaign".
3. **Reporting** — select the campaign to see mocked 7-day metrics, KPI delta cards, per-variant table, and suggestions.
4. **Settings → White-label** — customise brand colours and preview live.
5. **Settings → Vendors** — see which adapters are mock vs real.
6. **Settings → API usage** — track generation count and cost.

---

## File structure

```
agency_platform/
├── app.py            — Entry point, KPI cards, architecture diagram
├── database.py       — SQLite persistence (Postgres-compatible DDL)
├── interfaces.py     — Abstract contracts; the only file pages import from
├── adapters.py       — Concrete implementations (vendor SDKs live here)
├── services.py       — Registry: get_ad_platform(), get_llm(), etc.
├── templates.py      — 6 campaign templates (no invented metrics)
├── pages/
│   ├── 1_Clients.py  — Client management
│   ├── 2_Campaigns.py — Campaign creation + launch
│   ├── 3_Reporting.py — Metrics, suggestions, A/B promotion
│   └── 4_Settings.py — Vendors, white-label, API usage
├── requirements.txt
├── .env.example
└── README.md
```

---

## Graduating a mock to a real adapter

The architectural guarantee: changing an adapter requires editing exactly **two files** — `adapters.py` and `services.py`. No page code changes.

### Example: graduating MockMetaAdPlatform to a real Meta Marketing API adapter

**Step 1 — Write the real adapter in `adapters.py`:**

```python
class RealMetaAdPlatform(AdPlatform):
    name = "meta"

    def __init__(self):
        import facebook_business  # install separately
        self._app_id = os.environ["META_APP_ID"]
        self._token = os.environ["META_ACCESS_TOKEN"]

    def launch_campaign(self, ad_account_external_id, draft):
        # ... real Meta Marketing API calls ...
        return LaunchResult(external_id="...", status="running", variant_external_ids=[...])

    def pause_variant(self, eid):
        # ... real API call ...
        pass

    def update_variant_weight(self, eid, weight):
        # ... real API call ...
        pass

    def fetch_metrics(self, eid, day):
        # ... real Insights API call ...
        return {"impressions": ..., "clicks": ..., ...}
```

**Step 2 — Change one line in `services.py`:**

```python
# Before:
_ad_platforms[name] = MockMetaAdPlatform()

# After:
_ad_platforms[name] = RealMetaAdPlatform()
```

**Step 3 — Add credentials to `.env`:**

```
META_APP_ID=your_app_id
META_ACCESS_TOKEN=your_token
```

That's it. `pages/2_Campaigns.py` and `pages/3_Reporting.py` are unchanged.

---

## Design decisions (ambiguous cases)

- **`true_ctr` / `true_cvr` on variants** — stored in DB but not used for metric simulation (mock adapter uses hash-seeded metrics). These fields exist to enable a coherent simulation layer in V4 where per-variant noise is seeded from the true values.
- **Email draft subject line** — uses the first variant's headline. A full implementation would generate subject lines with `generate_subject_lines()` and A/B test them.
- **No `numpy`** — all arithmetic uses built-in Python and `pandas`. The spec explicitly forbids numpy.

---

## Anti-patterns deliberately excluded

| Anti-pattern | Why excluded |
|---|---|
| `success_rate` on templates | Would be invented fiction. Performance comes from real data. |
| `avg_roi` on templates | Same reason. |
| `random.uniform(15,35)` labelled "expected improvement" | Meaningless. Heuristics are labelled as heuristics. |
| Vendor imports in `pages/` | Architecture rule. All vendor access goes through `services.py`. |
| OpenAI / scikit-learn / numpy | Spec explicitly forbids these dependencies. |
