"""
Bellhaven CRM Sync — Review App
Run: streamlit run app.py
"""
import streamlit as st
from db import init_db, get_proposals, mark_decision, counts
from actions import execute_proposal

st.set_page_config(page_title="Bellhaven CRM Sync", layout="wide")

init_db()

PTYPE_LABELS = {
    "NEW": ("🆕 New Account", "#1a73e8"),
    "FIX_PARENT": ("🔗 Wrong Parent", "#e37400"),
    "CHOW": ("🏦 CHOW — Billing Hold", "#d32f2f"),
    "FIX_NAME": ("✏️ Name Update", "#6200ea"),
    "FIX_FIELDS": ("🔧 Field Fix", "#0097a7"),
    "ORPHAN": ("👻 Orphan", "#555555"),
    "CONFIDENT": ("✅ Confident Match", "#2e7d32"),
}

PTYPE_ORDER = ["CHOW", "FIX_PARENT", "NEW", "FIX_NAME", "FIX_FIELDS", "ORPHAN", "CONFIDENT"]

ACTION_TYPES = {"NEW", "FIX_PARENT", "CHOW", "FIX_NAME", "FIX_FIELDS", "ORPHAN"}


def badge(ptype: str) -> str:
    label, _ = PTYPE_LABELS.get(ptype, (ptype, "#999"))
    return label


def render_changes(changes: dict) -> str:
    if not changes:
        return "No changes needed."
    lines = []
    for field, diff in changes.items():
        lines.append(f"**{field}:** `{diff.get('from','?')}` → `{diff.get('to','?')}`")
    return "  \n".join(lines)


# ── Header ────────────────────────────────────────────────────────────────────
st.title("Bellhaven CRM Sync — Review Queue")
st.caption("⚠️ Deadline: **19 Sept 2026 14:26 PDT** — approve all correct proposals before then.")

c = counts()
col1, col2, col3, col4 = st.columns(4)
col1.metric("Pending", c.get("pending", 0))
col2.metric("Approved", c.get("approved", 0))
col3.metric("Rejected", c.get("rejected", 0))
col4.metric("Total", sum(c.values()))

st.divider()

# ── Tab layout ────────────────────────────────────────────────────────────────
tab_pending, tab_approved, tab_rejected, tab_confident = st.tabs([
    "⏳ Pending Review", "✅ Approved", "❌ Rejected", "🔍 Confident Matches"
])

# ── Pending tab ───────────────────────────────────────────────────────────────
with tab_pending:
    pending = [p for p in get_proposals("pending") if p["ptype"] in ACTION_TYPES]
    if not pending:
        st.success("No pending proposals — all done!")
    else:
        # Group by ptype in priority order
        by_type: dict[str, list] = {}
        for p in pending:
            by_type.setdefault(p["ptype"], []).append(p)

        for ptype in PTYPE_ORDER:
            batch = by_type.get(ptype, [])
            if not batch:
                continue
            label, colour = PTYPE_LABELS.get(ptype, (ptype, "#999"))
            st.subheader(f"{label} ({len(batch)})")

            for p in batch:
                key = p["key"]
                with st.expander(
                    f"{p.get('website_name') or p.get('crm_name','?')} "
                    f"— {p.get('website_city') or p.get('website_state','')}"
                ):
                    col_a, col_b = st.columns(2)

                    with col_a:
                        st.markdown("**Website data**")
                        if p.get("website_name"):
                            st.write(f"Name: {p['website_name']}")
                            st.write(f"Address: {p.get('website_street','')} · {p.get('website_city','')}, {p.get('website_state','')} {p.get('website_zip','')}")
                            st.write(f"Care types: {', '.join(p.get('website_care_types', []))}")
                        else:
                            st.write("_(no website location — orphan)_")

                    with col_b:
                        st.markdown("**CRM data**")
                        if p.get("crm_name"):
                            st.write(f"Name: {p['crm_name']}")
                            st.write(f"Account ID: `{p.get('account_id','')}`")
                            st.write(f"Parent: {p.get('crm_parent_name','')}")
                            st.write(f"Revenue: ${p.get('lifetime_revenue',0):,.0f} · AR: ${p.get('outstanding_ar',0):,.0f}")
                        else:
                            st.write("_(no existing CRM account)_")

                    st.markdown("**Proposed changes**")
                    st.markdown(render_changes(p.get("changes", {})))

                    if ptype == "CHOW":
                        st.warning(
                            "⚠️ CHOW path: this account has revenue history AND outstanding AR. "
                            "The old account will be preserved. A new account will be created under Bellhaven parent, "
                            "and `chow_current_account` will be set on the old record."
                        )

                    st.caption(f"Evidence: {p.get('evidence','')}")

                    btn_col1, btn_col2, _ = st.columns([1, 1, 4])
                    if btn_col1.button("✅ Approve", key=f"approve_{key}"):
                        ok, msg = execute_proposal(p)
                        if ok:
                            mark_decision(key, "approved")
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                    if btn_col2.button("❌ Reject", key=f"reject_{key}"):
                        mark_decision(key, "rejected", note="Manually rejected in review app.")
                        st.rerun()

# ── Approved tab ──────────────────────────────────────────────────────────────
with tab_approved:
    approved = get_proposals("approved")
    if not approved:
        st.info("Nothing approved yet.")
    else:
        for p in approved:
            st.write(f"{badge(p['ptype'])} — **{p.get('website_name') or p.get('crm_name')}**")

# ── Rejected tab ──────────────────────────────────────────────────────────────
with tab_rejected:
    rejected = get_proposals("rejected")
    if not rejected:
        st.info("Nothing rejected.")
    else:
        for p in rejected:
            st.write(f"{badge(p['ptype'])} — **{p.get('website_name') or p.get('crm_name')}** — _{p.get('_note','')}_")

# ── Confident matches tab ─────────────────────────────────────────────────────
with tab_confident:
    confident = [p for p in get_proposals() if p["ptype"] == "CONFIDENT"]
    st.write(f"{len(confident)} accounts already match the website — no changes needed.")
    for p in confident:
        st.write(f"✅ **{p.get('crm_name')}** — {p.get('website_city')}, {p.get('website_state')} · Score: {p.get('score',0):.0f}")
