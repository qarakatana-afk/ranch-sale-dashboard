
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = "ranch.db"


@contextmanager
def get_conn(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS deal (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                deal_name TEXT NOT NULL,
                owner TEXT NOT NULL,
                county TEXT NOT NULL,
                state TEXT NOT NULL,

                buyer TEXT,
                realtor TEXT NOT NULL,
                title_company TEXT NOT NULL,
                surveyor TEXT NOT NULL,
                attorney TEXT NOT NULL,

                price_per_acre INTEGER NOT NULL,
                contract_years INTEGER NOT NULL,
                has_1031 INTEGER NOT NULL DEFAULT 0,

                current_stage TEXT NOT NULL,
                stage_started_on TEXT NOT NULL, -- ISO date YYYY-MM-DD

                closing_date TEXT,              -- ISO date optional
                deadline_1031_identification TEXT,
                deadline_1031_completion TEXT
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL UNIQUE,  -- unique per deal (single deal)
                display_name TEXT NOT NULL,
                status TEXT NOT NULL,           -- missing/requested/received/verified
                holder TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                last_updated TEXT NOT NULL      -- ISO datetime
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL UNIQUE,      -- unique role
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                notes TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                at TEXT NOT NULL,               -- ISO datetime
                actor TEXT NOT NULL,            -- "Q" or "Grandpa"
                action TEXT NOT NULL,           -- e.g. "update_document"
                entity_type TEXT NOT NULL,      -- "document" / "deal" / "contact"
                entity_key TEXT NOT NULL,       -- e.g. doc_type or deal field
                old_value TEXT,
                new_value TEXT,
                note TEXT NOT NULL DEFAULT ''
            );
            """
        )


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_activity(
    conn: sqlite3.Connection,
    actor: str,
    action: str,
    entity_type: str,
    entity_key: str,
    old_value: Optional[str],
    new_value: Optional[str],
    note: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO activity_log (at, actor, action, entity_type, entity_key, old_value, new_value, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_now_iso(), actor, action, entity_type, entity_key, old_value, new_value, note or ""),
    )


def get_deal_snapshot(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Single read for UI: deal + documents + contacts + recent activity."""
    with get_conn(db_path) as conn:
        deal = conn.execute("SELECT * FROM deal WHERE id = 1").fetchone()
        documents = conn.execute("SELECT * FROM documents ORDER BY display_name").fetchall()
        contacts = conn.execute("SELECT * FROM contacts ORDER BY role").fetchall()
        activity = conn.execute(
            "SELECT * FROM activity_log ORDER BY id DESC LIMIT 25"
        ).fetchall()

        return {
            "deal": dict(deal) if deal else None,
            "documents": [dict(r) for r in documents],
            "contacts": [dict(r) for r in contacts],
            "activity": [dict(r) for r in activity],
        }


def update_document(
    doc_type: str,
    new_status: str,
    note: str = "",
    actor: str = "Q",
    db_path: str = DB_PATH,
) -> None:
    """
    Updates document status and logs the change.
    Enforces: status must be one of allowed values.
    """
    allowed = {"missing", "requested", "received", "verified"}
    if new_status not in allowed:
        raise ValueError(f"Invalid status '{new_status}'. Allowed: {sorted(allowed)}")

    with get_conn(db_path) as conn:
        row = conn.execute("SELECT status FROM documents WHERE doc_type = ?", (doc_type,)).fetchone()
        if not row:
            raise ValueError(f"Unknown doc_type: {doc_type}")

        old_status = row["status"]
        if old_status == new_status:
            # Still log note-only changes? Optional. For now: only log if status changes.
            return

        conn.execute(
            """
            UPDATE documents
            SET status = ?, last_updated = ?
            WHERE doc_type = ?
            """,
            (new_status, _now_iso(), doc_type),
        )
        log_activity(
            conn=conn,
            actor=actor,
            action="update_document",
            entity_type="document",
            entity_key=doc_type,
            old_value=old_status,
            new_value=new_status,
            note=note,
        )


def set_stage(
    new_stage: str,
    note: str = "",
    actor: str = "Q",
    db_path: str = DB_PATH,
) -> None:
    """
    Updates deal.current_stage and deal.stage_started_on with governance:
    - Prevents moving backwards without an explicit note.
    - (Later) can prevent moving forward if blockers exist; we’ll wire that in after rules.py is in place.
    """
    stages = [
        "locate_buyer",
        "negotiate",
        "appraisal",
        "due_diligence",
        "disclosure",
        "contract_signed",
        "title_review",
        "closing",
        "completed",
    ]
    if new_stage not in stages:
        raise ValueError(f"Invalid stage '{new_stage}'. Allowed: {stages}")

    with get_conn(db_path) as conn:
        deal = conn.execute("SELECT current_stage FROM deal WHERE id = 1").fetchone()
        if not deal:
            raise RuntimeError("Deal not initialized. Run seed.py first.")

        old_stage = deal["current_stage"]
        if old_stage == new_stage:
            return

        old_i = stages.index(old_stage)
        new_i = stages.index(new_stage)

        # No silent regression
        if new_i < old_i and not note.strip():
            raise ValueError("Moving stage backwards requires a note (why are we reverting?).")

        conn.execute(
            """
            UPDATE deal
            SET current_stage = ?, stage_started_on = ?
            WHERE id = 1
            """,
            (new_stage, datetime.now().date().isoformat()),
        )
        log_activity(
            conn=conn,
            actor=actor,
            action="set_stage",
            entity_type="deal",
            entity_key="current_stage",
            old_value=old_stage,
            new_value=new_stage,
            note=note,
        )


def update_deal_field(
    field: str,
    value: Any,
    note: str = "",
    actor: str = "Q",
    db_path: str = DB_PATH,
) -> None:
    """Safe-ish helper for a few whitelisted fields (buyer, deadlines, etc.)."""
    allowed_fields = {
        "buyer",
        "closing_date",
        "deadline_1031_identification",
        "deadline_1031_completion",
        "has_1031",
    }
    if field not in allowed_fields:
        raise ValueError(f"Field '{field}' not allowed to update.")

    with get_conn(db_path) as conn:
        old = conn.execute(f"SELECT {field} FROM deal WHERE id = 1").fetchone()
        if not old:
            raise RuntimeError("Deal not initialized. Run seed.py first.")
        old_value = old[field]

        conn.execute(f"UPDATE deal SET {field} = ? WHERE id = 1", (value,))
        log_activity(
            conn=conn,
            actor=actor,
            action="update_deal_field",
            entity_type="deal",
            entity_key=field,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(value) if value is not None else None,
            note=note,
        )

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

REQUIRED_DOC_TYPES = [
    "legal_description_verified",
    "warranty_deeds",
    "plat_map",
    "well_records",
    "septic_records",
    "tax_records",
]

LATE_TITLE_REVIEW_DAYS = 14
DEADLINE_WARNING_DAYS = 10

STAGES = [
    "locate_buyer",
    "negotiate",
    "appraisal",
    "due_diligence",
    "disclosure",
    "contract_signed",
    "title_review",
    "closing",
    "completed",
]


@dataclass
class ComputedStatus:
    health: str                # OK / BLOCKED / DELAYED
    blockers: List[str]
    alerts: List[str]
    next_action: str
    responsible: str


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    return datetime.strptime(d, "%Y-%m-%d").date()


def compute_status(snapshot: Dict) -> ComputedStatus:
    deal = snapshot["deal"]
    docs = snapshot["documents"]

    docs_by_type = {d["doc_type"]: d for d in docs}
    missing = []
    for dt in REQUIRED_DOC_TYPES:
        if dt not in docs_by_type or docs_by_type[dt]["status"] != "verified":
            missing.append(dt)

    blockers: List[str] = []
    alerts: List[str] = []

    stage = deal["current_stage"]
    stage_started_on = _parse_date(deal.get("stage_started_on")) or date.today()
    days_in_stage = (date.today() - stage_started_on).days

    # Blocker rule: if in later stages, missing docs blocks progress
    if stage in {"due_diligence", "contract_signed", "title_review", "closing"} and missing:
        blockers.append("Missing/Unverified documents: " + ", ".join(missing))

    # Delay rule: title review too long
    if stage == "title_review" and days_in_stage > LATE_TITLE_REVIEW_DAYS:
        alerts.append(f"Title review delayed: {days_in_stage} days waiting (>{LATE_TITLE_REVIEW_DAYS})")

    # 1031 rule: deadlines approaching
    if int(deal.get("has_1031") or 0) == 1:
        for label, key in [
            ("1031 identification deadline", "deadline_1031_identification"),
            ("1031 completion deadline", "deadline_1031_completion"),
        ]:
            dd = _parse_date(deal.get(key))
            if dd:
                days_left = (dd - date.today()).days
                if days_left <= DEADLINE_WARNING_DAYS:
                    alerts.append(f"{label} in {days_left} days ({dd.isoformat()})")

    # Health
    if blockers:
        health = "BLOCKED"
    elif any(a.startswith("Title review delayed") for a in alerts):
        health = "DELAYED"
    else:
        health = "OK"

    # Next action suggestions (simple + useful)
    if health == "BLOCKED":
        next_action = "Verify missing documents (start with the ones holding up closing/title)"
        responsible = "Title Company / Realtor"
    elif stage == "locate_buyer":
        next_action = "Locate and qualify buyer"
        responsible = "Realtor"
    elif stage == "title_review":
        next_action = "Follow up with title examiner for status + expected completion date"
        responsible = "Title Company"
    elif stage == "closing":
        next_action = "Confirm title cleared + schedule closing"
        responsible = "Title Company / Attorney"
    elif stage == "completed":
        next_action = "Deal complete — archive documents + final payment confirmation"
        responsible = "—"
    else:
        next_action = "Advance to next milestone when ready"
        responsible = "Realtor / Seller"

    return ComputedStatus(
        health=health,
        blockers=blockers,
        alerts=alerts,
        next_action=next_action,
        responsible=responsible,
    )

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
