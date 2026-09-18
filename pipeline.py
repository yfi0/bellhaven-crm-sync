"""
Run this once to scrape the website, match against the CRM, and load proposals into decisions.db.
Safe to re-run — already-decided proposals are never re-proposed.
"""
import sys
from scraper import scrape_communities
from crm import fetch_all_accounts
from matcher import build_proposals
from db import init_db, upsert_proposal, counts


def run():
    print("=== Bellhaven CRM Sync Pipeline ===\n")

    print("Step 1/3: Scraping website...")
    locations = scrape_communities()

    print(f"\nStep 2/3: Fetching CRM accounts...")
    all_accounts = fetch_all_accounts()
    print(f"  fetched {len(all_accounts)} CRM accounts total")

    print(f"\nStep 3/3: Matching and building proposals...")
    proposals = build_proposals(locations, all_accounts)

    # Summary of what was found
    ptype_counts: dict[str, int] = {}
    for p in proposals:
        ptype_counts[p["ptype"]] = ptype_counts.get(p["ptype"], 0) + 1

    print("\nProposal summary:")
    for ptype, n in sorted(ptype_counts.items()):
        print(f"  {ptype}: {n}")

    # Load into DB (skips already-decided keys)
    init_db()
    new_count = 0
    for p in proposals:
        before = counts()
        upsert_proposal(p)
        after = counts()
        if after.get("pending", 0) > before.get("pending", 0):
            new_count += 1

    print(f"\n{new_count} new proposals added to decisions.db.")
    print(f"DB totals: {counts()}")
    print("\nDone. Run 'streamlit run app.py' to review proposals.")


if __name__ == "__main__":
    run()
