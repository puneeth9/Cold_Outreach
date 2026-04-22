from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.classifier import ClassificationResult
from src.core.message_service import MessageData
from src.models import Message


def save_message(session: Session, data: MessageData) -> Message:
    record = Message(
        outreach_id=data.outreach_id,
        direction=data.direction,
        gmail_message_id=data.gmail_message_id,
        subject=data.subject,
        body=data.body,
        sent_at=data.sent_at,
        classification=data.classification,
        classification_confidence=data.classification_confidence,
        classification_reasoning=data.classification_reasoning,
        created_at=datetime.now(timezone.utc),
    )
    session.add(record)
    session.flush()
    return record


def get_messages_for_outreach(session: Session, outreach_id: int) -> list[Message]:
    """Return all messages for an outreach ordered by sent_at ascending (thread order)."""
    return (
        session.query(Message)
        .filter(Message.outreach_id == outreach_id)
        .order_by(Message.sent_at.asc())
        .all()
    )


def get_local_gmail_ids(session: Session, outreach_id: int) -> set[str]:
    """Return the set of gmail_message_ids already stored for this outreach."""
    rows = (
        session.query(Message.gmail_message_id)
        .filter(
            Message.outreach_id == outreach_id,
            Message.gmail_message_id.isnot(None),
        )
        .all()
    )
    return {r[0] for r in rows}


def get_message_by_id(session: Session, message_id: int) -> Message | None:
    return session.query(Message).filter(Message.id == message_id).first()


def update_message_classification(
    session: Session, message_id: int, result: ClassificationResult
) -> None:
    session.query(Message).filter(Message.id == message_id).update({
        "classification": result.classification,
        "classification_confidence": result.confidence,
        "classification_reasoning": result.reasoning,
    })
