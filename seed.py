from datetime import date
from db import init_db, get_conn

def seed():
    init_db()

    with get_conn() as conn:
        # Deal row (id=1)
        conn.execute("DELETE FROM activity_log")
        conn.execute("DELETE FROM documents")
        conn.execute("DELETE FROM contacts")
        conn.execute("DELETE FROM deal")

        conn.execute(
            """
            INSERT INTO deal (
                id, deal_name, owner, county, state,
                buyer, realtor, title_company, surveyor, attorney,
                price_per_acre, contract_years, has_1031,
                current_stage, stage_started_on,
                closing_date, deadline_1031_identification, deadline_1031_completion
            ) VALUES (
                1, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?
            )
            """,
            (
                "Valencia County Ranch Sale",
                "Willy Orona",
                "Valencia County",
                "New Mexico, USA",
                "CB Smith",
                "Ty Realty",
                "Socorro Security",
                "Saiz Surveying",
                "Reist",
                450,
                6,
                1,  # has_1031 (1=true)
                "locate_buyer",
                date.today().isoformat(),
                None,
                None,
                None,
            ),
        )

        # Documents (friendly display names matter for grandpa)
        docs = [
            ("legal_description_verified", "Legal Description Verified", "verified", "County Clerk", "Section/township + parcel code confirmed"),
            ("warranty_deeds", "Warranty Deeds", "received", "Title Company", ""),
            ("plat_map", "PLAT Map", "requested", "Surveyor", ""),
            ("well_records", "Well Records", "missing", "Williams Windmills", ""),
            ("septic_records", "Septic / Environmental Records", "requested", "Environmental Agency", ""),
            ("tax_records", "Tax Records", "received", "County", ""),
        ]

        for doc_type, display_name, status, holder, notes in docs:
            conn.execute(
                """
                INSERT INTO documents (doc_type, display_name, status, holder, notes, last_updated)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (doc_type, display_name, status, holder, notes),
            )

        # Contacts
        contacts = [
            ("buyer", "CB Smith", None, None, ""),
            ("realtor", "Ty Realty", None, None, ""),
            ("title_company", "Socorro Security", None, None, "Known delay risk: examiner timeliness"),
            ("surveyor", "Saiz Surveying", None, None, ""),
            ("attorney", "Reist", None, None, ""),
        ]
        for role, name, phone, email, notes in contacts:
            conn.execute(
                """
                INSERT INTO contacts (role, name, phone, email, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (role, name, phone, email, notes),
            )

    print("Seed complete. Database initialized: ranch.db")


if __name__ == "__main__":
    seed()