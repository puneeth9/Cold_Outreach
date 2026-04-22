from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.outreach_service import OutreachData
from src.models import Outreach, OutreachStatus


def save_outreach(session: Session, data: OutreachData) -> Outreach:
    now = datetime.now(timezone.utc)
    record = Outreach(
        recipient_email=data.recipient_email,
        recipient_name=data.recipient_name,
        company=data.company,
        role_context=data.role_context,
        subject=data.subject,
        body=data.body,
        sent_at=data.sent_at,
        created_at=now,
        status=data.status,
    )
    session.add(record)
    session.flush()  # populate id before caller returns
    return record


def update_outreach(session: Session, outreach_id: int, **fields) -> Outreach | None:
    record = session.query(Outreach).filter(Outreach.id == outreach_id).first()
    if not record:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(record, key, value)
    session.flush()
    return record


def list_outreach(session: Session, status_filter: str | None = None) -> list[Outreach]:
    query = session.query(Outreach)
    if status_filter is not None:
        query = query.filter(Outreach.status == OutreachStatus(status_filter))
    return query.order_by(Outreach.sent_at.desc()).all()
