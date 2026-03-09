import streamlit as st
import seed
from db import init_db, get_deal_snapshot, update_document, set_stage
from rules import compute_status, STAGES

DOC_STATUSES = ["missing", "requested", "received", "verified"]


def pretty_stage(stage: str) -> str:
    return stage.replace("_", " ").title()


st.set_page_config(page_title="Ranch Sale Dashboard", layout="wide")

# Ensure DB exists
init_db()

st.title("Ranch Sale Dashboard")

st.markdown(
"""
### Governance-Driven Deal Tracker

This dashboard tracks the operational state of a ranch sale transaction.

It focuses on three questions:

• What stage is the deal in  
• What blockers exist  
• What is the next action required to move toward closing  

The system computes these automatically based on document verification and deal stage.
"""
)

top_left, top_right = st.columns([4, 1])

with top_left:
    st.caption("Decision-focused dashboard for governing a real-world ranch sale workflow.")

with top_right:
    if st.button("Reset Demo Data"):
        seed.seed()
        st.rerun()

snapshot = get_deal_snapshot()

if not snapshot["deal"]:
    st.error("Deal data is not initialized yet. Click 'Reset Demo Data' to load the demo dataset.")
    st.stop()

deal = snapshot["deal"]
docs = snapshot["documents"]
contacts = snapshot["contacts"]
activity = snapshot["activity"]

computed = compute_status(snapshot)

# -------------------------
# Decision Layer
# -------------------------

st.subheader("Current Objective")
st.info("Advance the ranch sale by clearing blockers and moving the deal toward closing.")

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric("Health", computed.health)

with m2:
    st.metric("Stage", pretty_stage(deal["current_stage"]))

with m3:
    st.metric("Owner", deal["owner"])

with m4:
    st.metric("Buyer", deal["buyer"] or "(not set)")

a1, a2, a3 = st.columns(3)

with a1:
    st.markdown("**What Was Just Completed**")
    if activity:
        latest = activity[0]
        st.write(f"{latest['action']} — {latest['entity_type']}:{latest['entity_key']}")
        if latest["note"]:
            st.caption(latest["note"])
    else:
        st.write("No recent activity recorded.")

with a2:
    st.markdown("**Next Step**")
    st.success(computed.next_action)

with a3:
    st.markdown("**Responsible Party**")
    st.warning(computed.responsible)

# -------------------------
# Blockers + Alerts
# -------------------------

st.subheader("Current Blockers")

if computed.blockers:
    for b in computed.blockers:
        st.error(b)
else:
    st.success("No active blockers.")

st.subheader("Alerts")

if computed.alerts:
    for a in computed.alerts:
        st.warning(a)
else:
    st.info("No active alerts.")

st.divider()

left, right = st.columns([2, 1])

# -------------------------
# Documents + Stage
# -------------------------

with left:

    st.subheader("Documents")

    for d in docs:

        cc1, cc2, cc3 = st.columns([2, 1, 3])

        with cc1:
            st.write(f"**{d['display_name']}**")
            st.caption(
                f"Status: {d['status'].title()} • Holder: {d['holder']} • Updated: {d['last_updated']}"
            )

            if d.get("notes"):
                st.caption(f"Notes: {d['notes']}")

        with cc2:

            new_status = st.selectbox(
                "Status",
                DOC_STATUSES,
                index=DOC_STATUSES.index(d["status"]),
                key=f"doc_status_{d['doc_type']}",
                label_visibility="collapsed",
            )

        with cc3:

            note = st.text_input(
                "Note (optional)",
                value=d.get("notes", ""),
                key=f"doc_note_{d['doc_type']}",
                label_visibility="collapsed",
            )

            if st.button("Save", key=f"doc_save_{d['doc_type']}"):

                try:
                    update_document(d["doc_type"], new_status, note=note, actor="Q")
                    st.rerun()

                except Exception as e:
                    st.error(str(e))

    st.divider()

    st.subheader("Deal Stage")

    stage_idx = STAGES.index(deal["current_stage"])

    new_stage = st.selectbox(
        "Current stage",
        STAGES,
        index=stage_idx,
        format_func=pretty_stage,
    )

    stage_note = st.text_input(
        "Stage change note (required if moving backwards)",
        key="stage_note",
    )

    if st.button("Update stage"):

        try:
            set_stage(new_stage, note=stage_note, actor="Q")
            st.rerun()

        except Exception as e:
            st.error(str(e))


# -------------------------
# Contacts + Activity
# -------------------------

with right:

    st.subheader("Contacts")

    if not contacts:
        st.info("No contacts saved yet.")

    else:

        for c in contacts:

            st.write(f"**{c['role'].replace('_', ' ').title()}** — {c['name']}")

            if c.get("phone"):
                st.caption(f"Phone: {c['phone']}")

            if c.get("email"):
                st.caption(f"Email: {c['email']}")

            if c.get("notes"):
                st.caption(c["notes"])

            st.write("---")

    st.subheader("Recent Activity")

    if not activity:
        st.info("No activity yet.")

    else:

        for a in activity:

            st.write(f"**{a['at']}** — {a['actor']} — {a['action']}")

            st.caption(
                f"{a['entity_type']}:{a['entity_key']} • {a['old_value']} → {a['new_value']}"
            )

            if a["note"]:
                st.caption(a["note"])

            st.write("---")
