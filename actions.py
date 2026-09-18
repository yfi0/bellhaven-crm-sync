"""
Executes approved proposals against the CRM API.
Called by the Streamlit app when a user clicks Approve.
"""
import json
from crm import patch_account, create_account
from config import BELLHAVEN_PARENT_ID


def execute_proposal(proposal: dict) -> tuple[bool, str]:
    """
    Execute one approved proposal. Returns (success, message).
    """
    ptype = proposal["ptype"]
    account_id = proposal.get("account_id")
    changes = proposal.get("changes", {})

    try:
        if ptype == "CONFIDENT":
            return True, "No change needed — account already correct."

        elif ptype == "NEW":
            # Create a new account under Bellhaven parent
            payload = {
                "name": proposal["website_name"],
                "parent_id": BELLHAVEN_PARENT_ID,
                "billing_street": proposal.get("website_street", ""),
                "billing_city": proposal.get("website_city", ""),
                "billing_state": proposal.get("website_state", ""),
                "billing_zip": proposal.get("website_zip", ""),
                "care_type": proposal.get("care_type_crm", ""),
                "status": "Active",
                "note": "Created by Bellhaven CRM sync pipeline.",
            }
            result = create_account(payload)
            new_id = result.get("account_id", "")
            return True, f"Created new account {new_id} — {proposal['website_name']}"

        elif ptype == "FIX_PARENT":
            # Re-parent directly (no billing history issue)
            result = patch_account(account_id, {
                "parent_id": BELLHAVEN_PARENT_ID,
                "note": "Parent corrected by Bellhaven CRM sync pipeline.",
            })
            return True, f"Re-parented {account_id} to Bellhaven parent."

        elif ptype == "CHOW":
            # Billing team constraint: preserve old account, create new under correct parent
            # Step 1: create new account under Bellhaven parent
            new_payload = {
                "name": proposal["website_name"],
                "parent_id": BELLHAVEN_PARENT_ID,
                "billing_street": proposal.get("website_street", ""),
                "billing_city": proposal.get("website_city", ""),
                "billing_state": proposal.get("website_state", ""),
                "billing_zip": proposal.get("website_zip", ""),
                "care_type": proposal.get("care_type_crm", ""),
                "status": "Active",
                "note": (
                    f"CHOW: created as successor to {account_id} "
                    f"({proposal.get('crm_name','')}) by sync pipeline."
                ),
            }
            new_acct = create_account(new_payload)
            new_id = new_acct.get("account_id", "")

            # Step 2: set chow_current_account on OLD account, leave everything else
            patch_account(account_id, {
                "chow_current_account": new_id,
                "note": (
                    f"CHOW: ownership transferred. New account: {new_id}. "
                    f"Preserved because lifetime_revenue={proposal.get('lifetime_revenue',0)} "
                    f"and outstanding_ar={proposal.get('outstanding_ar',0)}."
                ),
            })
            return True, f"CHOW complete: new account {new_id} created; old account {account_id} preserved with chow_current_account set."

        elif ptype in ("FIX_NAME", "FIX_FIELDS"):
            # Patch name and/or other fields
            patch_payload: dict = {}
            if "name" in changes:
                patch_payload["name"] = changes["name"]["to"]
            if "care_type" in changes:
                patch_payload["care_type"] = changes["care_type"]["to"]
            if "status" in changes:
                patch_payload["status"] = changes["status"]["to"]
            patch_payload["note"] = "Updated by Bellhaven CRM sync pipeline."
            patch_account(account_id, patch_payload)
            return True, f"Patched {account_id}: {list(patch_payload.keys())}"

        elif ptype == "ORPHAN":
            patch_account(account_id, {
                "status": "Needs Review",
                "note": "Flagged by sync pipeline: not found on Bellhaven website. Verify if facility is closed or renamed.",
            })
            return True, f"Marked {account_id} as Needs Review (orphan)."

        else:
            return False, f"Unknown proposal type: {ptype}"

    except Exception as e:
        return False, f"API error: {e}"
