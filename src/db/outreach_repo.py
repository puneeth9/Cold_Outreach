from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.outreach_service import OutreachData
from src.models import Outreach


def save_outreach(session: Session, data: OutreachData) -> Outreach:
    record = Outreach(
        recipient_email=data.recipient_email,
        recipient_name=data.recipient_name,
        company=data.company,
        role=data.role,
        follow_up_after_days=data.follow_up_after_days,
        archived=data.archived,
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.flush()
    return record


def get_outreach_by_id(session: Session, outreach_id: int) -> Outreach | None:
    return session.query(Outreach).filter(Outreach.id == outreach_id).first()


def list_outreaches(session: Session) -> list[Outreach]:
    return session.query(Outreach).order_by(Outreach.created_at.desc()).all()


def update_outreach(session: Session, outreach_id: int, **fields) -> Outreach | None:
    record = session.query(Outreach).filter(Outreach.id == outreach_id).first()
    if not record:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(record, key, value)
    session.flush()
    return record


def set_thread_id(session: Session, outreach_id: int, thread_id: str) -> None:
    session.query(Outreach).filter(Outreach.id == outreach_id).update(
        {"gmail_thread_id": thread_id}
    )


def get_unresolved_outreaches(session: Session) -> list[Outreach]:
    """Return non-archived outreaches that don't have a Gmail thread ID yet."""
    return (
        session.query(Outreach)
        .filter(Outreach.archived.is_(False), Outreach.gmail_thread_id.is_(None))
        .all()
    )


def get_active_outreaches(session: Session) -> list[Outreach]:
    """Return all non-archived outreaches that have a resolved Gmail thread ID."""
    return (
        session.query(Outreach)
        .filter(Outreach.archived.is_(False), Outreach.gmail_thread_id.isnot(None))
        .all()
    )
