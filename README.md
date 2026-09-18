# Bellhaven CRM Sync

A daily pipeline that scrapes Bellhaven Senior Living's community directory and keeps their CRM accurate — syncing facility names, addresses, parent accounts, and care types.

Built as a take-home assessment for Clipboard Health (Sales Operations Analyst).

---

## What it does

1. **Scrapes** all ~35 Bellhaven communities from the website (name, address, city, state, zip, care types)
2. **Fetches** all ~120 accounts from the CRM sandbox
3. **Matches** each website location to the right CRM account using fuzzy name matching + city/state/zip signals
4. **Classifies** each match into one of:
   - `CONFIDENT` — already correct, no change needed
   - `FIX_PARENT` — account exists but under the wrong parent company
   - `CHOW` — wrong parent AND has billing history + outstanding AR (billing team constraint applies)
   - `FIX_NAME` — account found but name is stale
   - `FIX_FIELDS` — minor field discrepancies (care type, status)
   - `NEW` — location on website with no CRM account
   - `ORPHAN` — CRM account under Bellhaven parent with no matching website location
5. **Queues proposals** in a local SQLite DB — safe to re-run, already-decided items are skipped
6. **Review app** (Streamlit) shows each proposal with evidence and Approve/Reject buttons — approved changes write immediately to the CRM via API

---

## Setup

```bash
cd 260917_bellhaven_crm_sync
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Run

```bash
# Step 1: scrape website + match against CRM + load proposals into decisions.db
python pipeline.py

# Step 2: open review app in browser
streamlit run app.py
```

Then in the app: review each proposal, click Approve for the ones you agree with. Approved changes write to the CRM immediately.

---

## CHOW Rule

When re-parenting an account that has **both** `lifetime_revenue > 0` and `outstanding_ar > 0`:
- The old account is **preserved exactly as-is** (billing team needs it)
- A **new account** is created under the correct parent
- `chow_current_account` is set on the old account pointing to the new one

If either field is zero, the existing account is re-parented directly.

---

## Idempotency

Every proposal gets a SHA-256 fingerprint based on (ptype, account_id, slug, proposed changes). On re-run, proposals already marked approved or rejected are skipped. Only genuinely new or changed proposals surface.

---

## Schedule

See `.github/workflows/schedule.yml` — runs daily at 06:00 UTC via GitHub Actions.

To use in production:
1. Store the API token in GitHub repo secrets as `CRM_API_TOKEN`
2. Update `config.py` to read from `os.environ["CRM_API_TOKEN"]`
3. Push to GitHub — the cron job activates automatically

---

## Project structure

```
├── config.py          # credentials + constants
├── scraper.py         # website scraper
├── crm.py             # CRM API wrapper
├── matcher.py         # matching logic + proposal builder
├── db.py              # SQLite decision store
├── actions.py         # executes approved proposals against CRM
├── pipeline.py        # orchestrates scrape → match → load
├── app.py             # Streamlit review app
├── decisions.db       # created on first run (gitignored)
├── requirements.txt
└── .github/workflows/schedule.yml
```
