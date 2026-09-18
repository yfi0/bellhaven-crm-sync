"""CRM API wrapper — read and write operations."""
import requests
from config import API_BASE, HEADERS


def _get(path: str, params: dict = None) -> dict:
    r = requests.get(API_BASE + path, headers=HEADERS, params=params or {}, timeout=15)
    r.raise_for_status()
    return r.json()


def _patch(path: str, payload: dict) -> dict:
    r = requests.patch(API_BASE + path, headers=HEADERS, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def _post(path: str, payload: dict) -> dict:
    r = requests.post(API_BASE + path, headers=HEADERS, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def fetch_all_accounts() -> list[dict]:
    """Fetch every account in the CRM (auto-paginate)."""
    accounts = []
    page = 1
    while True:
        data = _get("/accounts", {"page": page, "page_size": 50})
        batch = data.get("data", [])
        if not batch:
            break
        accounts.extend(batch)
        total = data.get("total", 0)
        if len(accounts) >= total:
            break
        page += 1
    return accounts


def get_account(account_id: str) -> dict:
    return _get(f"/accounts/{account_id}")


def patch_account(account_id: str, fields: dict) -> dict:
    return _patch(f"/accounts/{account_id}", fields)


def create_account(fields: dict) -> dict:
    return _post("/accounts", fields)
