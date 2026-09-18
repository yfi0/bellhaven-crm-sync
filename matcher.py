"""Matching logic: links website locations to CRM accounts and produces proposals."""
import re
import hashlib
import json
from rapidfuzz import fuzz
from config import BELLHAVEN_PARENT_ID


# ── Name normalisation ────────────────────────────────────────────────────────

def _norm(name: str) -> str:
    """Lowercase, strip leading 'the ', collapse punctuation/spaces."""
    n = name.lower().strip()
    n = re.sub(r"^the\s+", "", n)
    n = re.sub(r"[^\w\s]", " ", n)   # punctuation → space
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _name_score(a: str, b: str) -> float:
    """Token-sort ratio (0–100) ignoring word order."""
    return fuzz.token_sort_ratio(_norm(a), _norm(b))


# ── Matching ──────────────────────────────────────────────────────────────────

def _city_state_match(loc: dict, acct: dict) -> bool:
    return (
        loc["city"].lower() == (acct.get("billing_city") or "").lower()
        and loc["state"].upper() == (acct.get("billing_state") or "").upper()
    )


def _find_best_match(location: dict, all_accounts: list[dict]) -> tuple[dict | None, float]:
    """
    Search ALL accounts (not just Bellhaven parent) for the best name+location match.
    Returns (account, score) or (None, 0).
    """
    candidates = []
    for acct in all_accounts:
        name_s = _name_score(location["name"], acct["name"])
        loc_match = _city_state_match(location, acct)
        # Combined score: name is primary, city/state is a strong bonus
        combined = name_s + (15 if loc_match else 0)
        if name_s >= 55:  # only consider plausible name matches
            candidates.append((acct, combined, name_s, loc_match))

    if not candidates:
        return None, 0

    candidates.sort(key=lambda x: x[1], reverse=True)
    best_acct, combined, name_s, loc_match = candidates[0]
    return best_acct, combined


# ── CHOW check ────────────────────────────────────────────────────────────────

def _chow_required(acct: dict) -> bool:
    """Billing team must keep old account if it has both revenue history AND outstanding AR."""
    return (acct.get("lifetime_revenue") or 0) > 0 and (acct.get("outstanding_ar") or 0) > 0


# ── Proposal building ─────────────────────────────────────────────────────────

def _proposal_key(proposal: dict) -> str:
    """Stable fingerprint so re-runs don't re-propose decided items."""
    identity = {
        "ptype": proposal["ptype"],
        "account_id": proposal.get("account_id", ""),
        "slug": proposal.get("slug", ""),
        "changes": sorted((proposal.get("changes") or {}).items()),
    }
    raw = json.dumps(identity, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_proposals(locations: list[dict], all_accounts: list[dict]) -> list[dict]:
    """
    For each website location: find the best CRM match, classify, build a proposal.
    Also detect orphan CRM accounts (under Bellhaven parent, not on website).
    """
    proposals = []
    matched_account_ids: set[str] = set()

    for loc in locations:
        best_acct, score = _find_best_match(loc, all_accounts)

        if best_acct is None or score < 60:
            # No usable match → create a new account
            p = {
                "ptype": "NEW",
                "slug": loc["slug"],
                "website_name": loc["name"],
                "website_city": loc["city"],
                "website_state": loc["state"],
                "website_zip": loc["zip"],
                "website_street": loc["street"],
                "website_care_types": loc["care_types"],
                "care_type_crm": loc["care_type_crm"],
                "account_id": None,
                "crm_name": None,
                "score": score,
                "changes": {},
                "evidence": f"No CRM account found for {loc['name']} ({loc['city']}, {loc['state']}). Score: {score:.0f}",
            }
            p["key"] = _proposal_key(p)
            proposals.append(p)
            continue

        matched_account_ids.add(best_acct["account_id"])
        issues: dict[str, dict] = {}

        # Wrong parent?
        if best_acct.get("parent_id") != BELLHAVEN_PARENT_ID:
            issues["parent_id"] = {
                "from": best_acct.get("parent_id"),
                "from_name": best_acct.get("parent_name"),
                "to": BELLHAVEN_PARENT_ID,
                "to_name": "Bellhaven Senior Living (Parent Account)",
            }

        # Name mismatch?
        if _name_score(loc["name"], best_acct["name"]) < 90:
            issues["name"] = {"from": best_acct["name"], "to": loc["name"]}

        # Care type mismatch?
        crm_care = (best_acct.get("care_type") or "").strip()
        expected_care = loc["care_type_crm"]
        if crm_care and expected_care and crm_care != expected_care:
            issues["care_type"] = {"from": crm_care, "to": expected_care}

        # Status not Active?
        if best_acct.get("status") != "Active":
            issues["status"] = {"from": best_acct.get("status"), "to": "Active"}

        if not issues:
            ptype = "CONFIDENT"
        elif "parent_id" in issues:
            ptype = "CHOW" if _chow_required(best_acct) else "FIX_PARENT"
        elif "name" in issues:
            ptype = "FIX_NAME"
        else:
            ptype = "FIX_FIELDS"

        evidence_parts = [f"Name score: {score:.0f}/100"]
        if _city_state_match(loc, best_acct):
            evidence_parts.append("City/state match ✓")
        if best_acct.get("billing_zip") == loc["zip"] and loc["zip"]:
            evidence_parts.append("Zip match ✓")
        evidence_parts.append(f"CRM: \"{best_acct['name']}\" → Website: \"{loc['name']}\"")

        p = {
            "ptype": ptype,
            "slug": loc["slug"],
            "website_name": loc["name"],
            "website_city": loc["city"],
            "website_state": loc["state"],
            "website_zip": loc["zip"],
            "website_street": loc["street"],
            "website_care_types": loc["care_types"],
            "care_type_crm": loc["care_type_crm"],
            "account_id": best_acct["account_id"],
            "crm_name": best_acct["name"],
            "crm_parent_id": best_acct.get("parent_id"),
            "crm_parent_name": best_acct.get("parent_name"),
            "lifetime_revenue": best_acct.get("lifetime_revenue", 0),
            "outstanding_ar": best_acct.get("outstanding_ar", 0),
            "score": score,
            "changes": issues,
            "evidence": " · ".join(evidence_parts),
        }
        p["key"] = _proposal_key(p)
        proposals.append(p)

    # Orphan detection: Bellhaven parent accounts not matched by any website location
    for acct in all_accounts:
        if (
            acct.get("parent_id") == BELLHAVEN_PARENT_ID
            and acct["account_id"] not in matched_account_ids
            and acct.get("status") == "Active"
        ):
            p = {
                "ptype": "ORPHAN",
                "slug": None,
                "website_name": None,
                "account_id": acct["account_id"],
                "crm_name": acct["name"],
                "crm_parent_id": acct.get("parent_id"),
                "crm_parent_name": acct.get("parent_name"),
                "lifetime_revenue": acct.get("lifetime_revenue", 0),
                "outstanding_ar": acct.get("outstanding_ar", 0),
                "score": 0,
                "changes": {"status": {"from": "Active", "to": "Needs Review"}},
                "evidence": f"Account \"{acct['name']}\" is Active under Bellhaven parent but has no matching website location.",
            }
            p["key"] = _proposal_key(p)
            proposals.append(p)

    return proposals
