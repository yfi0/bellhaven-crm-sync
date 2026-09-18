import os

API_BASE = "https://analyst-assessment-production.up.railway.app/api/v1"
API_TOKEN = os.environ.get("CRM_API_TOKEN", "bh_eSBy7HwAMoHrSc62HK5gNg")
WEBSITE_BASE = "https://analyst-assessment-production.up.railway.app"
BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"
DB_PATH = "decisions.db"

HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

# Website care type → CRM care type
CARE_TYPE_MAP = {
    "Assisted Living": "Assisted Living",
    "Memory Support": "Memory Care",
    "Short-Term Rehabilitation & Nursing": "Skilled Nursing",
    "Short-Term Rehabilitation &amp; Nursing": "Skilled Nursing",
}
