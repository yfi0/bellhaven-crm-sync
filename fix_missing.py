"""
Fix unmatched website locations — facilities rejected from the Name Update queue
because the matcher linked them to wrong CRM accounts.

For each facility: search CRM by city, decide whether to patch an existing account
or create a new one under the Bellhaven parent.
"""
from crm import fetch_all_accounts, patch_account, create_account
from config import BELLHAVEN_PARENT_ID

MISSING = [
    {
        "name": "Bellhaven of Kettering",
        "street": "3313 Wilmington Pike",
        "city": "Kettering",
        "state": "OH",
        "zip": "45429",
        "care_type": "Skilled Nursing",
    },
    {
        "name": "Bellhaven of Chagrin Falls",
        "street": "150 River St",
        "city": "Chagrin Falls",
        "state": "OH",
        "zip": "44022",
        "care_type": "Assisted Living",
    },
    {
        "name": "Bellhaven Willow Creek",
        "street": "",
        "city": "Portage",
        "state": "MI",
        "zip": "",
        "care_type": "Memory Care",
    },
    {
        "name": "Bellhaven of Batavia",
        "street": "",
        "city": "Batavia",
        "state": "OH",
        "zip": "",
        "care_type": "Skilled Nursing",
    },
    {
        "name": "Bellhaven of Chesterton",
        "street": "",
        "city": "Chesterton",
        "state": "IN",
        "zip": "",
        "care_type": "Skilled Nursing",
    },
]


def main():
    print("Fetching all CRM accounts...")
    all_accounts = fetch_all_accounts()
    print(f"  {len(all_accounts)} accounts loaded\n")

    for loc in MISSING:
        city = loc["city"].lower()
        state = loc["state"].upper()
        name = loc["name"].lower()

        # Find candidates in this city+state
        candidates = [
            a for a in all_accounts
            if (a.get("billing_city") or "").lower() == city
            and (a.get("billing_state") or "").upper() == state
        ]

        print(f"── {loc['name']} ({loc['city']}, {loc['state']}) ──")

        if not candidates:
            # No CRM account at all — create one
            print(f"  No CRM account found. Creating new account under Bellhaven parent...")
            payload = {
                "name": loc["name"],
                "parent_id": BELLHAVEN_PARENT_ID,
                "billing_street": loc["street"],
                "billing_city": loc["city"],
                "billing_state": loc["state"],
                "billing_zip": loc["zip"],
                "care_type": loc["care_type"],
                "status": "Active",
                "note": "Created by fix_missing.py — was not matched by pipeline due to name mismatch.",
            }
            result = create_account(payload)
            print(f"  ✅ Created: {result.get('account_id')} — {loc['name']}")

        else:
            print(f"  Found {len(candidates)} CRM account(s) in {loc['city']}, {loc['state']}:")
            for a in candidates:
                print(f"    [{a['account_id']}] \"{a['name']}\" | parent: {a.get('parent_name')} | status: {a.get('status')}")

            # Pick the best candidate: prefer same parent, then any active account
            bellhaven_match = next(
                (a for a in candidates if a.get("parent_id") == BELLHAVEN_PARENT_ID), None
            )
            name_match = next(
                (a for a in candidates if loc["name"].lower() in (a.get("name") or "").lower()
                 or (a.get("name") or "").lower() in loc["name"].lower()), None
            )
            target = bellhaven_match or name_match or candidates[0]

            if target.get("parent_id") == BELLHAVEN_PARENT_ID and target.get("status") == "Active":
                # Already correct — just update the name if needed
                if target.get("name") != loc["name"]:
                    patch_account(target["account_id"], {
                        "name": loc["name"],
                        "note": "Name corrected by fix_missing.py to match website.",
                    })
                    print(f"  ✅ Name updated: \"{target['name']}\" → \"{loc['name']}\"")
                else:
                    print(f"  ✅ Already correct — no changes needed.")
            else:
                # Wrong parent or inactive — patch it
                ar = target.get("outstanding_ar") or 0
                rev = target.get("lifetime_revenue") or 0
                if rev > 0 and ar > 0:
                    # CHOW: create new, preserve old
                    print(f"  ⚠️  CHOW required (revenue={rev}, ar={ar}). Creating new account...")
                    new_payload = {
                        "name": loc["name"],
                        "parent_id": BELLHAVEN_PARENT_ID,
                        "billing_street": loc["street"],
                        "billing_city": loc["city"],
                        "billing_state": loc["state"],
                        "billing_zip": loc["zip"],
                        "care_type": loc["care_type"],
                        "status": "Active",
                        "note": f"CHOW successor to {target['account_id']} via fix_missing.py.",
                    }
                    new_acct = create_account(new_payload)
                    new_id = new_acct.get("account_id", "")
                    patch_account(target["account_id"], {
                        "chow_current_account": new_id,
                        "note": f"CHOW: new account {new_id} created by fix_missing.py.",
                    })
                    print(f"  ✅ CHOW complete: new {new_id}, old {target['account_id']} preserved.")
                else:
                    # Safe to re-parent / fix directly
                    patch_account(target["account_id"], {
                        "name": loc["name"],
                        "parent_id": BELLHAVEN_PARENT_ID,
                        "care_type": loc["care_type"],
                        "status": "Active",
                        "note": "Parent and name corrected by fix_missing.py.",
                    })
                    print(f"  ✅ Patched [{target['account_id']}]: parent → Bellhaven, name → \"{loc['name']}\"")

        print()


if __name__ == "__main__":
    main()
