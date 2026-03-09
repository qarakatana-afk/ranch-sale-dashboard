from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

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

STAGE_REQUIRED_DOCS = {
    "due_diligence": ["warranty_deeds", "plat_map"],
    "disclosure": ["warranty_deeds", "plat_map", "well_records", "septic_records"],
    "title_review": ["legal_description_verified", "warranty_deeds", "plat_map", "tax_records"],
    "closing": [
        "legal_description_verified",
        "warranty_deeds",
        "plat_map",
        "well_records",
        "septic_records",
        "tax_records",
    ],
    "completed": [
        "legal_description_verified",
        "warranty_deeds",
        "plat_map",
        "well_records",
        "septic_records",
        "tax_records",
    ],
}

DOC_RESPONSIBILITY = {
    "warranty_deeds": "Title Company",
    "plat_map": "Surveyor / Title Company",
    "well_records": "Seller / County",
    "septic_records": "Seller / Environmental Agency",
    "tax_records": "County / Title Company",
    "legal_description_verified": "County / Title Company",
}


@dataclass
class ComputedStatus:
    health: str
    blockers: List[str]
    alerts: List[str]
    next_action: str
    responsible: str


def _parse_date(d: Optional[str]) -> Optional[date]:
    if not d:
        return None
    return datetime.strptime(d, "%Y-%m-%d").date()


def get_required_docs_for_stage(stage: str) -> List[str]:
    return STAGE_REQUIRED_DOCS.get(stage, [])


def get_missing_verified_docs(snapshot: Dict, required_doc_types: List[str]) -> List[str]:
    docs = snapshot["documents"]
    docs_by_type = {d["doc_type"]: d for d in docs}

    missing = []
    for dt in required_doc_types:
        if dt not in docs_by_type or docs_by_type[dt]["status"] != "verified":
            missing.append(dt)
    return missing


def get_stage_blockers(snapshot: Dict, stage: str) -> List[str]:
    required = get_required_docs_for_stage(stage)
    missing = get_missing_verified_docs(snapshot, required)

    if not missing:
        return []

    return ["Missing/Unverified documents: " + ", ".join(missing)]


def can_move_to_stage(snapshot: Dict, new_stage: str) -> Tuple[bool, List[str]]:
    blockers = get_stage_blockers(snapshot, new_stage)
    return (len(blockers) == 0, blockers)


def _responsible_for_missing_docs(missing_docs: List[str]) -> str:
    if not missing_docs:
        return "Title Company / Realtor"

    owners = []
    for doc in missing_docs[:2]:
        owner = DOC_RESPONSIBILITY.get(doc)
        if owner and owner not in owners:
            owners.append(owner)

    return " / ".join(owners) if owners else "Title Company / Realtor"


def compute_status(snapshot: Dict) -> ComputedStatus:
    deal = snapshot["deal"]
    stage = deal["current_stage"]

    blockers: List[str] = []
    alerts: List[str] = []

    required_docs = get_required_docs_for_stage(stage)
    missing = get_missing_verified_docs(snapshot, required_docs)

    stage_started_on = _parse_date(deal.get("stage_started_on")) or date.today()
    days_in_stage = (date.today() - stage_started_on).days

    # Blocker rule
    if missing:
        blockers.append("Missing/Unverified documents: " + ", ".join(missing))

    # Delay rule
    if stage == "title_review" and days_in_stage > LATE_TITLE_REVIEW_DAYS:
        alerts.append(
            f"Title review delayed: {days_in_stage} days waiting (>{LATE_TITLE_REVIEW_DAYS})"
        )

    # 1031 deadline alerts
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

    # Next action + responsible
    if blockers:
        next_action = f"Resolve blocked documents: {', '.join(missing[:2])}"
        responsible = _responsible_for_missing_docs(missing)
    elif stage == "locate_buyer":
        next_action = "Locate and qualify buyer"
        responsible = "Realtor"
    elif stage == "title_review":
        next_action = "Follow up with title examiner for status and expected completion date"
        responsible = "Title Company"
    elif stage == "closing":
        next_action = "Confirm title cleared and schedule closing"
        responsible = "Title Company / Attorney"
    elif stage == "completed":
        next_action = "Deal complete — archive documents and confirm final payment"
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